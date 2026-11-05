"""Case-scoped event profiles, verified ingestion, coverage and exploration."""
import ipaddress
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, exists
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.investigations import service as investigations
from app.modules.intelligence.service import ensure_analysis_initiate
from app.modules.events import service
from app.modules.events.models import SourceProfile, EventIngestionRun, SecurityEvent, EventRunMember
from app.modules.events.schemas import ProfileCreate, ProfileRead, IngestRequest, RunRead, EventRead
from app.modules.evidence.models import Evidence

router=APIRouter(prefix='/investigations/{investigation_id}/events',tags=['security-events'])


def case(db,investigation_id,user,write=False):
    inv=investigations.get_investigation(db,investigation_id)
    return ensure_analysis_initiate(db,inv,user) if write else investigations.ensure_access(db,inv,user)


@router.get('/profiles',response_model=list[ProfileRead])
def profiles(investigation_id:int,user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user)
    return db.scalars(select(SourceProfile).where(SourceProfile.investigation_id==inv.id).order_by(SourceProfile.id).limit(200)).all()


@router.post('/profiles',response_model=ProfileRead,status_code=201)
def create_profile(investigation_id:int,payload:ProfileCreate,user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user,True)
    return service.create_profile(db,inv,payload,user)


@router.post('/runs',response_model=RunRead,status_code=201)
def ingest(investigation_id:int,payload:IngestRequest,user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user,True)
    return service.ingest(db,inv,payload.evidence_id,payload.profile_id,user)


@router.get('/runs')
def runs(investigation_id:int,limit:int=Query(25,ge=1,le=100),offset:int=Query(0,ge=0,le=100000),
         user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user)
    condition=EventIngestionRun.investigation_id==inv.id
    return {'items':[RunRead.model_validate(r) for r in db.scalars(select(EventIngestionRun).where(condition)
        .order_by(EventIngestionRun.id.desc()).limit(limit).offset(offset))],
        'total':db.scalar(select(func.count()).select_from(EventIngestionRun).where(condition)),
        'limit':limit,'offset':offset}


@router.post('/runs/{run_id}/recover',response_model=RunRead)
def recover(investigation_id:int,run_id:int,user=Depends(get_current_user),db=Depends(get_db)):
    return service.recover_run(db,case(db,investigation_id,user,True),run_id,user)


def current_integrity(db,item):
    evidence=db.get(Evidence,item.evidence_id)
    return bool(evidence and evidence.registration_status=='ready' and evidence.integrity_status=='verified'
        and item.input_sha256==evidence.sha256)


@router.get('')
def events(investigation_id:int,category:str|None=Query(None,max_length=40),event_type:str|None=Query(None,max_length=64),
    outcome:str|None=Query(None,pattern='^(success|failure|unknown)$'),username:str|None=Query(None,max_length=256),
    host:str|None=Query(None,max_length=256),source_ip:str|None=Query(None,max_length=100),
    destination_ip:str|None=Query(None,max_length=100),provider:str|None=Query(None,max_length=100),
    event_id:str|None=Query(None,max_length=32),evidence_id:int|None=Query(None,gt=0),
    profile_id:int|None=Query(None,gt=0),run_id:int|None=Query(None,gt=0),
    start:datetime|None=None,end:datetime|None=None,limit:int=Query(50,ge=1,le=200),
    offset:int=Query(0,ge=0,le=100000),user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user)
    for value in (start,end):
        if value and (value.tzinfo is None or value.utcoffset() is None):
            raise HTTPException(422,'Time range boundaries require explicit offsets.')
    if start and end and start>end:
        raise HTTPException(422,'Time range start must precede end.')
    stmt=select(SecurityEvent).where(SecurityEvent.investigation_id==inv.id)
    for field,value in [('category',category),('event_type',event_type),('outcome',outcome),('username',username),
        ('hostname',host),('provider',provider),('event_id',event_id),('evidence_id',evidence_id),('profile_id',profile_id)]:
        if value is not None:
            stmt=stmt.where(getattr(SecurityEvent,field)==value)
    for field,value in [('source_ip',source_ip),('destination_ip',destination_ip)]:
        if value is not None:
            try:
                value=str(ipaddress.ip_address(value))
            except ValueError as exc:
                raise HTTPException(422,'IP filters require a valid IPv4 or IPv6 address.') from exc
            stmt=stmt.where(getattr(SecurityEvent,field)==value)
    if start: stmt=stmt.where(SecurityEvent.timestamp_utc>=start)
    if end: stmt=stmt.where(SecurityEvent.timestamp_utc<=end)
    if run_id:
        stmt=stmt.where(exists(select(EventRunMember.event_id).where(
            EventRunMember.run_id==run_id,EventRunMember.event_id==SecurityEvent.id)))
    total=db.scalar(select(func.count()).select_from(stmt.subquery()))
    # Stable semantic ordering, unknown UTC last; a range excludes unknowns.
    items=db.scalars(stmt.order_by(SecurityEvent.timestamp_utc.asc().nulls_last(),SecurityEvent.semantic_key)
        .limit(limit).offset(offset)).all()
    evidence_map={e.id:e for e in db.scalars(select(Evidence).where(Evidence.investigation_id==inv.id,Evidence.id.in_([e.evidence_id for e in items])))}
    return {'items':[{**EventRead.model_validate(e).model_dump(),
        'evidence_number':evidence_map[e.evidence_id].evidence_number,
        'support_verified':current_integrity(db,e)} for e in items], 'total':total,'limit':limit,'offset':offset,
        'time_policy':'UTC ranges exclude unknown/ambiguous times; profile assumptions remain labeled.',
        'view_policy':'Immutable historical event snapshots across all profiles. Filter by profile or run to select one interpretation.'}


@router.get('/{event_key}')
def detail(investigation_id:int,event_key:str,user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user)
    if len(event_key)!=64:
        raise HTTPException(404,'Event not found.')
    item=db.scalar(select(SecurityEvent).where(SecurityEvent.investigation_id==inv.id,SecurityEvent.semantic_key==event_key))
    if item is None:
        raise HTTPException(404,'Event not found.')
    return {**EventRead.model_validate(item).model_dump(),'support_verified':current_integrity(db,item),
        'evidence_number':db.get(Evidence,item.evidence_id).evidence_number}
