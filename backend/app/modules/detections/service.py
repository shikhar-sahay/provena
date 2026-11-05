"""Case-locked immutable event sets, integrity-gated runs and shared findings."""
from collections import defaultdict
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, func
from app.events import detections as engine
from app.events.adapters import ADAPTER_VERSION, NORMALIZATION_VERSION
from app.modules.events.models import EventIngestionRun, EventRunMember, SecurityEvent, SourceProfile
from app.modules.events.schemas import EventRead
from app.modules.events.service import lock_case
from app.modules.evidence.models import Evidence
from app.modules.evidence import storage
from app.modules.evidence.service import record_verification
from app.modules.intelligence.models import Finding
from app.modules.audit.service import record, ResourceTypes
from .models import InvestigationEventSet, EventSetMember, AuthenticationDetectionRun, DetectionRunFinding


def audit(db, inv, actor, action, metadata):
    record(db,action=action,resource_type=ResourceTypes.INVESTIGATION,resource_id=inv.id,actor_id=actor.id,metadata=metadata)


def get_set(db, inv, set_id):
    item=db.scalar(select(InvestigationEventSet).where(InvestigationEventSet.id==set_id,InvestigationEventSet.investigation_id==inv.id))
    if item is None:
        raise HTTPException(404,'Event set not found in this investigation.')
    return item


def members(db, item, included=True):
    stmt=select(SecurityEvent).join(EventSetMember,EventSetMember.event_id==SecurityEvent.id).where(EventSetMember.set_id==item.id)
    if included:
        stmt=stmt.where(EventSetMember.included.is_(True))
    return list(db.scalars(stmt.order_by(SecurityEvent.semantic_key).limit(engine.LIMIT+1)))


def event_data(event):
    return EventRead.model_validate(event).model_dump(mode='json')


def create_set(db, inv, payload, actor):
    lock_case(db,inv)
    runs=list(db.scalars(select(EventIngestionRun).where(EventIngestionRun.investigation_id==inv.id,EventIngestionRun.id.in_(payload.run_ids))))
    if len(runs)!=len(payload.run_ids):
        raise HTTPException(404,'Selected ingestion run not found in this investigation.')
    interpretations={}
    coverage=[]
    for run in runs:
        if run.status not in ('completed','partial'):
            raise HTTPException(409,'Only completed or explicitly partial ingestion runs can be selected.')
        if run.adapter_version!=ADAPTER_VERSION or run.normalization_version!=NORMALIZATION_VERSION:
            raise HTTPException(409,'Historical adapter semantics require explicit reingestion before detection.')
        signature=(run.profile_id,run.adapter_version,run.normalization_version)
        for source in (('evidence',run.evidence_id),('digest',run.input_sha256)):
            if source in interpretations and interpretations[source]!=signature:
                raise HTTPException(409,'Alternative interpretations of the same source cannot be combined. Select one profile.')
            interpretations[source]=signature
        clean={k:v for k,v in run.coverage.items() if k!='events_created'}
        coverage.append({'input_sha256':run.input_sha256,'profile_key':db.get(SourceProfile,run.profile_id).semantic_key,
                         'adapter_version':run.adapter_version,'normalization_version':run.normalization_version,
                         'status':run.status,'coverage':clean})
    events=list(db.scalars(select(SecurityEvent).where(SecurityEvent.investigation_id==inv.id,
        SecurityEvent.id.in_(select(EventRunMember.event_id).where(EventRunMember.run_id.in_(payload.run_ids))))
        .order_by(SecurityEvent.semantic_key).limit(engine.LIMIT+1)))
    if len(events)>engine.LIMIT:
        raise HTTPException(422,'Selection exceeds 10000 events; select fewer ingestion runs.')
    if not events:
        raise HTTPException(422,'Selected runs contain no recognized events.')
    # Keep distinct source locations. Count identical copies/partitions at most once
    # per occurrence ordinal. Temporal alternatives of overlapping records are rejected.
    source_occurrences=defaultdict(list)
    time_interpretations={}
    evidence_map={e.id:e for e in db.scalars(select(Evidence).where(Evidence.id.in_({e.evidence_id for e in events})))}
    for event in events:
        if not current_event(db,event,evidence_map):
            raise HTTPException(409,'Selected evidence is not currently registered and verified.')
        obs=engine.observation(event_data(event))
        timekey=engine.digest(event.time_semantics)
        if obs in time_interpretations and time_interpretations[obs]!=timekey:
            raise HTTPException(409,'Overlapping records have conflicting time interpretations. Select one interpretation.')
        time_interpretations[obs]=timekey
        source_occurrences[(obs,event.evidence_id)].append(event)
    representatives={}
    for (obs,_), occurrences in source_occurrences.items():
        occurrences.sort(key=lambda e:(engine.digest(e.locator),e.semantic_key))
        for ordinal,event in enumerate(occurrences):
            key=(obs,ordinal)
            old=representatives.get(key)
            if old is None or (event.input_sha256,event.semantic_key)<(old.input_sha256,old.semantic_key):
                representatives[key]=event
    selected=sorted(representatives.values(),key=lambda e:e.semantic_key)
    canonical_coverage=sorted({engine.digest(c):c for c in coverage}.values(),key=engine.digest)
    key=engine.digest({'version':'1','events':sorted(e.semantic_key for e in events),'coverage':canonical_coverage})
    existing=db.scalar(select(InvestigationEventSet).where(InvestigationEventSet.investigation_id==inv.id,InvestigationEventSet.semantic_key==key))
    if existing:
        db.commit()
        return existing
    if db.scalar(select(func.count()).select_from(InvestigationEventSet).where(InvestigationEventSet.investigation_id==inv.id))>=200:
        raise HTTPException(409,'Event set limit reached (200). Reuse an existing selection.')
    time_counts=defaultdict(int)
    for event in selected:
        time_counts[event.time_semantics.get('certainty','unknown')]+=1
    item=InvestigationEventSet(investigation_id=inv.id,semantic_key=key,name=payload.name,version='1',selected_runs=payload.run_ids,
        created_by_id=actor.id,coverage={'sources':canonical_coverage,'selected_events':len(events),'included_events':len(selected),
        'authentication_events':sum(e.category=='authentication' for e in selected),
        'evidence_count':len(evidence_map),'timestamp_certainty_counts':dict(time_counts),
        'duplicate_source_occurrences_excluded':len(events)-len(selected),'partial':any(r.status=='partial' for r in runs),
        'warnings':['Overlapping copied/partitioned observations are not independent corroboration.',
                    'UTC projection does not establish source-clock synchronization or causal order.']})
    db.add(item)
    db.flush()
    selected_ids={e.id for e in selected}
    for event in events:
        db.add(EventSetMember(set_id=item.id,event_id=event.id,observation_key=engine.observation(event_data(event)),included=event.id in selected_ids))
    audit(db,inv,actor,'AUTH_EVENT_SET_CREATED',{'set_id':item.id,'semantic_key':key,'run_ids':payload.run_ids,'coverage':item.coverage})
    db.commit()
    db.refresh(item)
    return item


def current_event(db,event,evidence_map=None):
    evidence=evidence_map.get(event.evidence_id) if evidence_map is not None else db.get(Evidence,event.evidence_id)
    return bool(evidence and evidence.registration_status=='ready' and evidence.integrity_status=='verified' and evidence.sha256==event.input_sha256)


def support_current(db,finding):
    snapshot=finding.support_snapshot or {}
    if finding.rule_version!=engine.VERSION or snapshot.get('engine_version')!=engine.VERSION:
        return False
    item=db.get(InvestigationEventSet,snapshot.get('event_set_id'))
    if item is None or item.investigation_id!=finding.investigation_id or item.semantic_key!=snapshot.get('event_set_key'):
        return False
    keys=snapshot.get('event_keys',[])
    if not keys or len(keys)>engine.LIMIT or len(set(keys))!=len(keys):
        return False
    stmt=select(SecurityEvent.semantic_key,SecurityEvent.evidence_id).join(EventSetMember,EventSetMember.event_id==SecurityEvent.id).join(Evidence,Evidence.id==SecurityEvent.evidence_id).where(
        EventSetMember.set_id==item.id,EventSetMember.included.is_(True),SecurityEvent.investigation_id==finding.investigation_id,
        SecurityEvent.semantic_key.in_(keys),SecurityEvent.input_sha256==Evidence.sha256,Evidence.registration_status=='ready',
        Evidence.integrity_status=='verified',SecurityEvent.adapter_version==ADAPTER_VERSION,SecurityEvent.normalization_version==NORMALIZATION_VERSION)
    valid=db.execute(stmt).all()
    return len(valid)==len(keys) and {r.evidence_id for r in valid}==set(finding.evidence_ids)


def finish(db,inv,actor,run,status,error=None):
    run.status,run.error,run.completed_at=status,error,datetime.now(timezone.utc)
    audit(db,inv,actor,'AUTH_DETECTION_FINISHED',{'run_id':run.id,'event_set_id':run.event_set_id,'status':status,'coverage':run.coverage})
    db.commit()
    db.refresh(run)
    return run


def execute(db,inv,payload,actor):
    item=get_set(db,inv,payload.event_set_id)
    run=AuthenticationDetectionRun(investigation_id=inv.id,event_set_id=item.id,initiated_by_id=actor.id,
        engine_version=engine.VERSION,status='running',configuration=payload.configuration.model_dump(),
        coverage={'input_coverage':item.coverage,'event_set_key':item.semantic_key,'evaluated':0,'result_count':0})
    db.add(run)
    try:
        db.flush()
        run_id=run.id
        audit(db,inv,actor,'AUTH_DETECTION_STARTED',{'run_id':run.id,'event_set_key':item.semantic_key})
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(503,'Could not confirm detection attempt registration. Inspect run history before retrying.') from exc
    db.info['verification_journal']=[]
    try:
        lock_case(db,inv)
        db.refresh(run)
        if run.status!='running':
            return run  # A recovery that obtained the lock before execution remains final.
        events=members(db,item)
        if len(events)>engine.LIMIT:
            return finish(db,inv,actor,run,'blocked','Event selection exceeds evaluation budget.')
        all_selected=members(db,item,included=False)
        evidence_ids=sorted({e.evidence_id for e in all_selected})
        evidence_map={e.id:e for e in db.scalars(select(Evidence).where(Evidence.id.in_(evidence_ids)))}
        checks=[]
        for evidence_id in evidence_ids:
            evidence=evidence_map[evidence_id]
            if evidence.registration_status!='ready' or evidence.integrity_status!='verified':
                return finish(db,inv,actor,run,'blocked','Selected evidence is unavailable or not verified.')
            try:
                with storage.snapshot(evidence.storage_key,evidence.file_size) as verified:
                    observed=verified.sha256
                check=record_verification(db,inv,evidence,observed,actor.id,'authentication_detection')
            except storage.SizeMismatch:
                check=record_verification(db,inv,evidence,None,actor.id,'authentication_detection',size_mismatch=True)
            except (OSError,ValueError):
                check=record_verification(db,inv,evidence,None,actor.id,'authentication_detection')
            checks.append({'evidence_id':evidence.id,'input_sha256':evidence.sha256,'verification_id':check.id,'integrity_status':evidence.integrity_status})
            run.coverage={'verification_checks':list(checks)}
        if not events or not all(current_event(db,e,evidence_map) for e in all_selected):
            return finish(db,inv,actor,run,'blocked','Selected source integrity failed; historical events were not treated as current evidence.')
        proposals,coverage=engine.evaluate([event_data(e) for e in events],run.configuration)
        run.coverage={**coverage,'verification_checks':checks,'input_coverage':item.coverage,'event_set_key':item.semantic_key}
        bykey={e.semantic_key:e for e in events}
        for proposal in proposals:
            if item.coverage['partial']:
                proposal['limitations'].append('Selected source coverage is partial. Unsupported, rejected or omitted records were not evaluated as absent activity.')
            key=engine.digest({'set':item.semantic_key,'proposal':proposal['semantic_key'],'engine':engine.VERSION})
            finding=db.scalar(select(Finding).where(Finding.investigation_id==inv.id,Finding.rule_id==proposal['rule_id'],Finding.inputs_key==key))
            if finding is None:
                support=[bykey[k] for k in proposal['event_keys']]
                finding=Finding(investigation_id=inv.id,rule_id=proposal['rule_id'],rule_version=engine.VERSION,
                    title=proposal['title'],summary=proposal['summary'],severity=proposal['severity'],confidence=0,factors=[],
                    evidence_ids=sorted({e.evidence_id for e in support}),artifact_ids=[],correlation_ids=[],inputs_key=key,
                    recommendations=['Review source records and account context; validate benign explanations before drawing conclusions.'],
                    support_snapshot={'kind':'authentication_detection','engine_version':engine.VERSION,'event_set_id':item.id,
                        'event_set_key':item.semantic_key,'event_keys':proposal['event_keys'],'detection':proposal,'input_coverage':item.coverage,
                        'source_events':[event_data(e) for e in support[:200]],
                        'source_event_snapshot_omitted':max(0,len(support)-200)},status='pending_review')
                db.add(finding)
                db.flush()
            db.add(DetectionRunFinding(run_id=run.id,finding_id=finding.id))
        return finish(db,inv,actor,run,'completed')
    except Exception as exc:
        checks=list(db.info.get('verification_journal',[]))
        db.rollback()
        lock_case(db,inv)
        run=db.get(AuthenticationDetectionRun,run_id)
        if run.status=='completed':
            return run
        retained=[]
        for eid,observed,actor_id,size_changed in checks:
            check=record_verification(db,inv,db.get(Evidence,eid),observed,actor_id,'authentication_detection_failure',size_mismatch=size_changed)
            retained.append({'evidence_id':eid,'verification_id':check.id,'integrity_status':check.result})
        run.coverage={**run.coverage,'verification_checks':retained,'result_count':0,'evaluation_complete':False}
        finish(db,inv,actor,run,'failed','Detection failed safely; no partial results were published. Retry or inspect run history.')
        raise HTTPException(503,'Detection could not complete. Inspect run history before retrying.') from exc
    finally:
        db.info.pop('verification_journal',None)


def recover(db,inv,run_id,actor):
    lock_case(db,inv)
    run=db.scalar(select(AuthenticationDetectionRun).where(AuthenticationDetectionRun.id==run_id,AuthenticationDetectionRun.investigation_id==inv.id))
    if not run:
        raise HTTPException(404,'Detection run not found.')
    if run.status=='running':
        return finish(db,inv,actor,run,'failed','Interrupted execution recovered. No partial result set was published; retry explicitly.')
    return run
