"""Verified synchronous event ingestion and case-scoped query services."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, func, insert
from app.events import adapters
from app.events.records import parse_records, RecordError, canonical_hash, MAX_BYTES
from app.events.time import event_time
from app.modules.events.models import SourceProfile, EventIngestionRun, SecurityEvent, EventRunMember
from app.modules.events.schemas import ProfileConfig
from app.modules.evidence import storage
from app.modules.evidence.models import Evidence
from app.modules.evidence.service import record_verification
from app.modules.audit.service import record, ResourceTypes
from app.modules.investigations.models import Investigation


def lock_case(db, inv):
    db.execute(select(Investigation.id).where(Investigation.id==inv.id).with_for_update()).scalar_one()


def create_profile(db, inv, payload, actor):
    lock_case(db, inv)
    config = payload.configuration.model_dump()
    key = canonical_hash({'profile_version':'1', 'configuration':config})
    existing = db.scalar(select(SourceProfile).where(SourceProfile.investigation_id==inv.id, SourceProfile.semantic_key==key))
    if existing:
        return existing
    if db.scalar(select(func.count()).select_from(SourceProfile).where(SourceProfile.investigation_id==inv.id)) >= 200:
        raise HTTPException(409,'Profile limit reached for this investigation (200). Reuse an existing interpretation.')
    profile = SourceProfile(investigation_id=inv.id, name=payload.name, semantic_key=key,
        version='1', configuration=config, created_by_id=actor.id)
    db.add(profile)
    db.flush()
    record(db,action='EVENT_PROFILE_CREATED',resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,actor_id=actor.id,metadata={'profile_id':profile.id,'semantic_key':key})
    db.commit()
    db.refresh(profile)
    return profile


def _finish(db, run, state, message=None):
    run.status, run.error, run.completed_at = state, message, datetime.now(timezone.utc)
    record(db,action='EVENT_INGESTION_FINISHED',resource_type=ResourceTypes.INVESTIGATION,
        resource_id=run.investigation_id,actor_id=run.initiated_by_id,
        metadata={'run_id':run.id,'status':state,'coverage':run.coverage})
    db.commit()
    db.refresh(run)
    return run


def ingest(db, inv, evidence_id, profile_id, actor):
    evidence = db.scalar(select(Evidence).where(Evidence.id==evidence_id,Evidence.investigation_id==inv.id))
    profile = db.scalar(select(SourceProfile).where(SourceProfile.id==profile_id,SourceProfile.investigation_id==inv.id))
    if evidence is None or profile is None:
        raise HTTPException(404,'Evidence or profile not found in this investigation.')
    config = ProfileConfig.model_validate(profile.configuration).model_dump()
    run = EventIngestionRun(investigation_id=inv.id,evidence_id=evidence.id,profile_id=profile.id,
        initiated_by_id=actor.id,status='running',adapter_version=adapters.ADAPTER_VERSION,
        normalization_version=adapters.NORMALIZATION_VERSION,coverage={})
    db.add(run)
    db.flush()
    record(db,action='EVENT_INGESTION_STARTED',resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,actor_id=actor.id,metadata={'run_id':run.id,'evidence_id':evidence.id,'profile_id':profile.id})
    try:
        db.commit()  # Durable attempt, then one locked transaction for the entire set.
    except Exception as exc:
        db.rollback()
        raise HTTPException(503,'Could not confirm ingestion attempt registration. Inspect run history before retrying.') from exc
    run_id = run.id
    db.info['verification_journal'] = []
    try:
        lock_case(db, inv)
        db.refresh(run)
        db.refresh(evidence)
        if run.status != 'running':
            return run  # Explicit recovery won the case lock before preparation.
        if evidence.registration_status != 'ready' or evidence.integrity_status != 'verified':
            return _finish(db,run,'blocked','Ready registration and independent verification are required.')
        try:
            with storage.snapshot(evidence.storage_key,evidence.file_size) as copied:
                check = record_verification(db,inv,evidence,copied.sha256,actor.id,'event_ingestion')
                run.verification_id = check.id
                if check.result != 'verified':
                    return _finish(db,run,'blocked','Evidence no longer matches its baseline.')
                run.input_sha256 = copied.sha256
                data = copied.handle.read(MAX_BYTES+1)
        except storage.SizeMismatch:
            check = record_verification(db,inv,evidence,None,actor.id,'event_ingestion',size_mismatch=True)
            run.verification_id = check.id
            return _finish(db,run,'blocked','Evidence size changed after verification.')
        except (OSError,ValueError):
            check = record_verification(db,inv,evidence,None,actor.id,'event_ingestion')
            run.verification_id = check.id
            return _finish(db,run,'blocked','Evidence storage is unavailable.')
        try:
            batch = parse_records(data,config)
        except RecordError as exc:
            run.coverage = {'status':'rejected','warnings':[str(exc)],'records_total':None,
                'recognized':0,'unrecognized':0,'rejected':0,'omitted':None}
            return _finish(db,run,'rejected',str(exc))
        coverage = batch.coverage
        pending = []
        issue_samples = []
        for source in batch.records:
            if source.error:
                coverage['rejected'] += 1
                if len(issue_samples)<20:
                    issue_samples.append({'locator':source.locator,'reason':source.error})
                continue
            try:
                event = adapters.adapt(source.value,config)
            except (adapters.AdapterReject,ValueError,TypeError,KeyError):
                coverage['rejected'] += 1
                if len(issue_samples)<20:
                    issue_samples.append({'locator':source.locator,'reason':'Invalid or oversized supported event fields.'})
                continue
            if event is None:
                coverage['unrecognized'] += 1
                if len(issue_samples)<20:
                    issue_samples.append({'locator':source.locator,'reason':'Unsupported program, event, provider or structure.'})
                continue
            raw_time = event['original_timestamp']
            time_config = config
            if event['attributes'].get('timestamp_field')=='UtcTime':
                time_config = {**config,'timezone':'+00:00'}
            temporal = event_time(raw_time,time_config)
            if event['attributes'].get('timestamp_field')=='UtcTime' and temporal['utc']:
                temporal['certainty']='source_utc_field'
                temporal['assumptions']=[]
            event['warnings'].extend(temporal['warnings'])
            coverage['recognized'] += 1
            identity = canonical_hash({'case':inv.case_number,'evidence':evidence.evidence_number,
                'input_sha256':run.input_sha256,'profile':profile.semantic_key,'profile_version':profile.version,
                'adapter':config['adapter'],'adapter_version':adapters.ADAPTER_VERSION,
                'normalization_version':adapters.NORMALIZATION_VERSION,
                'record':source.locator,'record_fingerprint':source.fingerprint})
            pending.append({**event,'semantic_key':identity,'investigation_id':inv.id,
                'evidence_id':evidence.id,'first_run_id':run.id,'profile_id':profile.id,
                'input_sha256':run.input_sha256,'record_fingerprint':source.fingerprint,
                'locator':source.locator,'profile_snapshot':{'version':profile.version,
                    'semantic_key':profile.semantic_key,'configuration':config},
                'adapter_version':adapters.ADAPTER_VERSION,'normalization_version':adapters.NORMALIZATION_VERSION,
                'source_format':config['format'],'coverage_status':'complete',
                'timestamp_utc':datetime.fromisoformat(temporal['utc']) if temporal['utc'] else None,
                'time_semantics':temporal})
        if coverage['omitted'] or coverage['rejected'] or coverage['unrecognized']:
            coverage['status']='partial'
            coverage['warnings'].append('Some records were unsupported, rejected or omitted; inspect counts and issue locators.')
        coverage['issues']=issue_samples
        coverage['issue_sample_limit']=20
        coverage['events_created']=0
        # Immutable rows and memberships are committed together; repeated runs
        # create only membership links. Chunk queries stay below SQLite bind limits.
        for offset in range(0,len(pending),250):
            chunk=pending[offset:offset+250]
            keys=[row['semantic_key'] for row in chunk]
            existing=set(db.scalars(select(SecurityEvent.semantic_key).where(
                SecurityEvent.investigation_id==inv.id,SecurityEvent.semantic_key.in_(keys))))
            fresh=[{**row,'coverage_status':coverage['status']} for row in chunk if row['semantic_key'] not in existing]
            if fresh:
                db.execute(insert(SecurityEvent),fresh)
            coverage['events_created']+=len(fresh)
            members=list(db.scalars(select(SecurityEvent.id).where(
                SecurityEvent.investigation_id==inv.id,SecurityEvent.semantic_key.in_(keys))))
            if members:
                db.execute(insert(EventRunMember),[{'run_id':run.id,'event_id':eid} for eid in members])
        run.coverage=coverage
        return _finish(db,run,'partial' if coverage['status']=='partial' else 'completed')
    except Exception:
        checks=list(db.info.get('verification_journal',[]))
        db.rollback()  # No partial events or memberships survive a failed transaction.
        lock_case(db,inv)
        run=db.get(EventIngestionRun,run_id)
        if run.status in ('completed','partial'):
            return run  # A successful commit whose acknowledgement was lost.
        for eid,observed,actor_id,size_changed in checks:
            check=record_verification(db,inv,db.get(Evidence,eid),observed,actor_id,'event_ingestion_failure',size_mismatch=size_changed)
            run.verification_id=check.id
        run.coverage={'status':'failed','recognized':0,'events_created':0,'warnings':['Analytical transaction rolled back. Retry ingestion.']}
        return _finish(db,run,'failed','Ingestion failed. No partial event set was retained; retry is safe.')
    finally:
        db.info.pop('verification_journal',None)


def recover_run(db,inv,run_id,actor):
    lock_case(db,inv)
    run=db.scalar(select(EventIngestionRun).where(EventIngestionRun.id==run_id,EventIngestionRun.investigation_id==inv.id))
    if run is None:
        raise HTTPException(404,'Ingestion run not found.')
    db.refresh(run)
    if run.status!='running':
        return run
    # Active processing holds the same case lock; this cannot interrupt its txn.
    record(db,action='EVENT_INGESTION_RECOVERED',resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,actor_id=actor.id,metadata={'run_id':run.id})
    return _finish(db,run,'failed','Interrupted attempt closed by analyst. Start a new ingestion attempt.')
