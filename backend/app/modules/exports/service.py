"""Case-scoped snapshot exports with explicit originals and durable failure states."""
import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from zipfile import ZipFile, ZIP_STORED
from fastapi import HTTPException
from sqlalchemy import select, func, cast, Text
from app.core.config import settings
from app.ops.archive import canonical, file_digest, inspect_package, EXPORT_SCHEMA, CHUNK, MAX_FILES
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import record, ResourceTypes
from app.modules.evidence.models import Evidence, EvidenceVerification, CustodyEvent
from app.modules.evidence import storage
from app.modules.evidence.service import record_verification
from app.modules.events.models import SourceProfile, EventIngestionRun, SecurityEvent, EventRunMember
from app.modules.detections.models import InvestigationEventSet, EventSetMember, AuthenticationDetectionRun, DetectionRunFinding
from app.modules.events.service import lock_case
from app.modules.intelligence.models import Finding, Report, Artifact, Correlation, CorrelationArtifact, AnalysisRun, AnalysisRunEvidence, InvestigationNote
from app.modules.investigations import service as investigations
from .models import InvestigationExport
from . import artifacts

MAX_ROWS=20000
PRIVATE={'storage_key','artifact_key','staging_ref','password_hash','password','token','secret_key','database_url','registration_key','request_key'}


def public(value):
    if isinstance(value,dict): return {k:public(v) for k,v in value.items() if k not in PRIVATE}
    if isinstance(value,list): return [public(v) for v in value]
    if isinstance(value,datetime): return value.isoformat()
    return value


def row_data(row):
    return public({column.key:getattr(row,column.key) for column in row.__mapper__.column_attrs})


class PackageWriter:
    def __init__(self,archive):
        self.archive=archive;self.files=[];self.total=0;self.metadata=0

    def write(self,name,chunks,metadata=False):
        if len(self.files)>=MAX_FILES-1: raise ValueError('Package file limit reached.')
        digest=hashlib.sha256();size=0
        with self.archive.open(name,'w',force_zip64=True) as target:
            for chunk in chunks:
                size+=len(chunk);self.total+=len(chunk)
                if metadata: self.metadata+=len(chunk)
                if self.total>settings.export_max_bytes-2*1024*1024 or self.metadata>settings.export_metadata_max_bytes:
                    raise ValueError('Export budget exceeded; select fewer sources or reports.')
                digest.update(chunk);target.write(chunk)
        entry={'path':name,'sha256':digest.hexdigest(),'size':size}
        self.files.append(entry)
        return entry

    def rows(self,name,rows):
        def chunks():
            buffer=bytearray()
            for count,row in enumerate(rows,1):
                if count>MAX_ROWS: raise ValueError('Metadata record limit exceeded; narrow the selection.')
                encoder=json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False,default=str)
                for part in encoder.iterencode(row_data(row)):
                    encoded=part.encode('utf-8')
                    for offset in range(0,len(encoded),65536):
                        buffer.extend(encoded[offset:offset+65536])
                        if len(buffer)>=65536:
                            yield bytes(buffer);buffer.clear()
                buffer.extend(b'\n')
            if buffer: yield bytes(buffer)
        self.write('metadata/'+name+'.jsonl',chunks(),metadata=True)


def audit(db,item,actor,action):
    record(db,action=action,resource_type=ResourceTypes.INVESTIGATION,resource_id=item.investigation_id,
        actor_id=actor.id,metadata={'export_id':item.id,'mode':item.mode,'status':item.status,'package_sha256':item.package_sha256,'automated':actor.id is None})


def get_export(db,inv,export_id):
    item=db.scalar(select(InvestigationExport).where(InvestigationExport.id==export_id,InvestigationExport.investigation_id==inv.id))
    if item is None: raise HTTPException(404,'Export not found in this investigation.')
    return item


def expired(item):
    created=item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
    return datetime.now(timezone.utc)>created+timedelta(hours=settings.export_retention_hours)


def create(db,inv,payload,actor,request_key=None):
    if payload.mode=='originals': investigations.ensure_manage(db,inv,actor)
    lock_case(db,inv)
    selection=payload.model_dump();selection_hash=hashlib.sha256(canonical(selection)).hexdigest()
    key=hashlib.sha256(request_key.encode()).hexdigest() if request_key else None
    if key:
        existing=db.scalar(select(InvestigationExport).where(InvestigationExport.investigation_id==inv.id,
            InvestigationExport.requested_by_id==actor.id,InvestigationExport.request_key==key))
        if existing:
            if existing.selection_hash!=selection_hash: raise HTTPException(409,'Idempotency key already identifies a different export selection.')
            return existing
    if db.scalar(select(func.count()).select_from(InvestigationExport).where(InvestigationExport.investigation_id==inv.id,InvestigationExport.status.in_(['running','completed'])))>=20:
        raise HTTPException(409,'Export retention limit reached. Recover interrupted exports or prune expired artifacts.')
    item=InvestigationExport(investigation_id=inv.id,requested_by_id=actor.id,mode=payload.mode,selection=selection,
        selection_hash=selection_hash,request_key=key,artifact_key=uuid.uuid4().hex+'.zip',status='running',manifest_summary={})
    db.add(item)
    try:
        db.flush();item_id=item.id;inv_id=inv.id;actor_id=actor.id;artifact_key=item.artifact_key
        audit(db,item,actor,'EXPORT_STARTED');db.commit()
    except Exception as exc:
        db.rollback();raise HTTPException(503,'Could not confirm export registration. Inspect export history before retrying.') from exc
    db.info['verification_journal']=[]
    try:
        if db.get_bind().dialect.name=='postgresql':
            db.connection(execution_options={'isolation_level':'REPEATABLE READ'})
        # Reauthorize after durable registration, inside the snapshot transaction.
        db.refresh(actor)
        inv=investigations.ensure_access(db,investigations.get_investigation(db,inv_id),actor)
        if item.mode=='originals': investigations.ensure_manage(db,inv,actor)
        lock_case(db,inv);db.refresh(item)
        if item.status!='running': return item
        with artifacts.building(artifact_key) as temporary:
            manifest=build(db,inv,actor,item,temporary)
            inspect_package(temporary,max_bytes=settings.export_max_bytes)
            with temporary.open('rb') as handle: package_hash,byte_size=file_digest(handle,settings.export_max_bytes)
        item.status='completed';item.completed_at=datetime.now(timezone.utc)
        item.package_sha256=package_hash;item.byte_size=byte_size
        item.manifest_summary={'schema':manifest['schema'],'files':len(manifest['files']),
            'originals':len(selection['evidence_ids']),'warnings':manifest['warnings'],'event_set_keys':manifest['event_set_keys']}
        audit(db,item,actor,'EXPORT_COMPLETED');db.commit();db.refresh(item)
        return item
    except Exception as exc:
        checks=list(db.info.get('verification_journal',[]));db.rollback()
        lock_case(db,inv);item=db.get(InvestigationExport,item_id)
        if item.status=='completed': return item
        cleanup_pending=False
        try: artifacts.remove(artifact_key)
        except OSError: cleanup_pending=True
        for eid,observed,uid,size_changed in checks:
            record_verification(db,inv,db.get(Evidence,eid),observed,uid,'export_failure',size_mismatch=size_changed)
        item.status='failed';item.completed_at=datetime.now(timezone.utc)
        item.manifest_summary={'cleanup_pending':cleanup_pending}
        item.error='Export failed safely. Verify selected evidence and reduce selections if limits were reached; no partial package is downloadable.'
        audit(db,item,actor,'EXPORT_FAILED');db.commit();db.refresh(item)
        return item
    finally:
        db.info.pop('verification_journal',None)


def build(db,inv,actor,item,target):
    selection=item.selection
    sets=list(db.scalars(select(InvestigationEventSet).where(InvestigationEventSet.investigation_id==inv.id,
        InvestigationEventSet.id.in_(selection['event_set_ids']))))
    report_filter=(Report.investigation_id==inv.id,Report.id.in_(selection['report_ids']))
    length=func.octet_length(cast(Report.content,Text)) if db.get_bind().dialect.name=='postgresql' else func.length(cast(Report.content,Text))*4
    if (db.scalar(select(func.sum(length)).where(*report_filter)) or 0)>settings.export_metadata_max_bytes:
        raise ValueError('Selected reports exceed the metadata budget.')
    reports=list(db.scalars(select(Report).where(*report_filter)))
    originals=list(db.scalars(select(Evidence).where(Evidence.investigation_id==inv.id,Evidence.id.in_(selection['evidence_ids']))))
    if len(sets)!=len(selection['event_set_ids']) or len(reports)!=len(selection['report_ids']) or len(originals)!=len(selection['evidence_ids']):
        raise ValueError('Selection contains an unavailable case resource.')
    if sum(e.file_size for e in originals)>settings.export_max_bytes-2*1024*1024:
        raise ValueError('Original evidence selection exceeds the package budget.')
    evidence=list(db.scalars(select(Evidence).where(Evidence.investigation_id==inv.id).order_by(Evidence.id).limit(1001)))
    if len(evidence)>1000: raise ValueError('Evidence inventory exceeds export budget.')
    manifest={'schema':EXPORT_SCHEMA,'hash_algorithm':'sha256','authenticity':'unsigned-integrity-only',
        'created_at':datetime.now(timezone.utc).isoformat(),'actor':{'id':actor.id,'username':actor.username},
        'investigation':{'id':inv.id,'case_number':inv.case_number,'title':inv.title},'export_id':item.id,
        'mode':item.mode,'selection':selection,'event_set_keys':sorted(s.semantic_key for s in sets),
        'processing_versions':sorted({(r.rule_version) for r in db.scalars(select(Finding).where(Finding.investigation_id==inv.id).limit(MAX_ROWS+1))}),
        'warnings':['Unsigned hash manifest establishes internal integrity consistency, not authenticity or certification.',
            'Metadata integrity states are historical snapshots; only explicitly included originals receive fresh byte verification.',
            'Normalized events cover only selected event sets. Immutable report snapshots may reference additional historical context.',
            'Download and subsequent custody events remain in the server audit history after this package snapshot.'],
        'coverage':[s.coverage for s in sets],'evidence':[],'reports':[],'files':[]}
    with ZipFile(target,'w',compression=ZIP_STORED,allowZip64=True) as archive:
        writer=PackageWriter(archive)
        for original in originals:
            if original.registration_status!='ready' or original.integrity_status!='verified':
                raise ValueError('Original evidence must be registered and independently verified.')
            try:
                with storage.snapshot(original.storage_key,original.file_size) as copied:
                    record_verification(db,inv,original,copied.sha256,actor.id,'export')
                    if copied.sha256!=original.sha256: raise ValueError('Evidence baseline mismatch.')
                    entry=writer.write(f'evidence/{original.id}.bin',iter(lambda:copied.handle.read(CHUNK),b''))
                    if entry['sha256']!=original.sha256: raise ValueError('Snapshot bytes changed unexpectedly.')
            except storage.SizeMismatch:
                record_verification(db,inv,original,None,actor.id,'export',size_mismatch=True);raise
            except OSError:
                record_verification(db,inv,original,None,actor.id,'export');raise
            db.add(CustodyEvent(evidence_id=original.id,action='exported',performed_by_id=actor.id,notes=f'Original baseline bytes included in investigation export #{item.id}.'))
        for e in evidence:
            manifest['evidence'].append({'id':e.id,'sha256':e.sha256,'size':e.file_size,'integrity_status':e.integrity_status,
                'registration_status':e.registration_status,'included_path':f'evidence/{e.id}.bin' if e.id in selection['evidence_ids'] else None})
        db.flush()
        event_ids=select(EventSetMember.event_id).where(EventSetMember.set_id.in_(selection['event_set_ids']))
        detection_ids=select(AuthenticationDetectionRun.id).where(AuthenticationDetectionRun.investigation_id==inv.id,
            AuthenticationDetectionRun.event_set_id.in_(selection['event_set_ids']))
        finding_ids=select(DetectionRunFinding.finding_id).where(DetectionRunFinding.run_id.in_(detection_ids))
        evidence_ids=select(Evidence.id).where(Evidence.investigation_id==inv.id)
        queries={
            'investigation':select(type(inv)).where(type(inv).id==inv.id),
            'evidence':select(Evidence).where(Evidence.investigation_id==inv.id),
            'verifications':select(EvidenceVerification).where(EvidenceVerification.evidence_id.in_(evidence_ids)),
            'custody':select(CustodyEvent).where(CustodyEvent.evidence_id.in_(evidence_ids)),
            'audit':select(AuditEvent).where(AuditEvent.resource_type=='investigation',AuditEvent.resource_id==str(inv.id)),
            'source_profiles':select(SourceProfile).where(SourceProfile.investigation_id==inv.id),
            'event_ingestion_runs':select(EventIngestionRun).where(EventIngestionRun.investigation_id==inv.id),
            'event_sets':select(InvestigationEventSet).where(InvestigationEventSet.id.in_(selection['event_set_ids'])),
            'event_set_members':select(EventSetMember).where(EventSetMember.set_id.in_(selection['event_set_ids'])),
            'events':select(SecurityEvent).where(SecurityEvent.investigation_id==inv.id,SecurityEvent.id.in_(event_ids)),
            'event_run_members':select(EventRunMember).join(EventIngestionRun,EventIngestionRun.id==EventRunMember.run_id).where(EventIngestionRun.investigation_id==inv.id,EventRunMember.event_id.in_(event_ids)),
            'detection_runs':select(AuthenticationDetectionRun).where(AuthenticationDetectionRun.id.in_(detection_ids)),
            'detection_findings':select(DetectionRunFinding).where(DetectionRunFinding.run_id.in_(detection_ids)),
            'findings':select(Finding).where(Finding.investigation_id==inv.id,(Finding.id.in_(finding_ids)) | Finding.rule_id.not_like('auth.%')),
            'notes':select(InvestigationNote).where(InvestigationNote.investigation_id==inv.id),
            'analysis_runs':select(AnalysisRun).where(AnalysisRun.investigation_id==inv.id),
            'analysis_inputs':select(AnalysisRunEvidence).join(AnalysisRun,AnalysisRun.id==AnalysisRunEvidence.run_id).where(AnalysisRun.investigation_id==inv.id),
            'artifacts':select(Artifact).where(Artifact.investigation_id==inv.id),
            'correlations':select(Correlation).where(Correlation.investigation_id==inv.id),
            'correlation_members':select(CorrelationArtifact).join(Correlation,Correlation.id==CorrelationArtifact.correlation_id).where(Correlation.investigation_id==inv.id),
        }
        for name,query in queries.items():
            model=query.column_descriptions[0]['entity']
            query=query.order_by(*model.__table__.primary_key.columns).limit(MAX_ROWS+1).execution_options(yield_per=100)
            writer.rows(name,db.scalars(query))
        for report in reports:
            # Preserve the original report's exact canonical hash convention.
            data=json.dumps(report.content,sort_keys=True,default=str).encode()
            if hashlib.sha256(data).hexdigest()!=report.content_sha256:
                raise ValueError('Stored report content no longer matches its immutable hash.')
            entry=writer.write(f'reports/{report.id}.json',[data],metadata=True)
            manifest['reports'].append({'id':report.id,'path':entry['path'],'content_sha256':report.content_sha256})
        manifest['files']=writer.files
        encoded=canonical(manifest)
        if len(encoded)>2*1024*1024: raise ValueError('Manifest budget exceeded.')
        archive.writestr('manifest.json',encoded)
    return manifest


def recover(db,inv,item,actor,prune=False):
    lock_case(db,inv);db.refresh(item)
    cleanup_failed=item.status=='failed' and item.manifest_summary.get('cleanup_pending',False)
    if item.status=='running' or cleanup_failed or (prune and item.status=='completed' and expired(item)):
        artifacts.remove(item.artifact_key)
        item.status='expired' if prune and expired(item) else 'failed'
        item.error='Generated package is unavailable; create a new export with a new request key.'
        item.manifest_summary={**item.manifest_summary,'cleanup_pending':False}
        item.completed_at=datetime.now(timezone.utc)
        audit(db,item,actor,'EXPORT_RECOVERED');db.commit();db.refresh(item)
    return item
