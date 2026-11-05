"""Authorized selection, detection history and uncertainty-aware timeline."""
import ipaddress
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.events.router import case, current_integrity
from app.modules.events.schemas import EventRead
from app.modules.events.models import SecurityEvent
from app.modules.intelligence import reasoning
from app.modules.intelligence.models import Finding
from app.modules.intelligence.router import _to_finding_read
from app.modules.audit.models import AuditEvent
from . import service
from .models import InvestigationEventSet, EventSetMember, AuthenticationDetectionRun, DetectionRunFinding
from .schemas import EventSetCreate, DetectionCreate

router=APIRouter(prefix='/investigations/{investigation_id}/authentication',tags=['authentication-investigation'])


@router.get('/rules')
def rules(investigation_id:int,user=Depends(get_current_user),db=Depends(get_db)):
    from app.events.detections import RULE_DEFINITIONS, VERSION
    from .schemas import DetectionConfig
    case(db,investigation_id,user)
    return {'engine_version':VERSION,'rules':RULE_DEFINITIONS,'defaults':DetectionConfig().model_dump(),
            'configuration_schema':DetectionConfig.model_json_schema(),
            'timestamp_requirement':'Justified UTC projection with second or finer precision; profile assumptions require opt-in.'}


def fields(row, names):
    return {name:getattr(row,name) for name in names.split()}


def set_read(row):
    return fields(row,'id investigation_id semantic_key name version selected_runs coverage created_by_id created_at')


def run_read(row):
    return fields(row,'id event_set_id status engine_version configuration coverage error created_at completed_at')


@router.get('/sets')
def sets(investigation_id:int,user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user)
    return [set_read(s) for s in db.scalars(select(InvestigationEventSet).where(InvestigationEventSet.investigation_id==inv.id).order_by(InvestigationEventSet.id.desc()).limit(200))]


@router.post('/sets',status_code=201)
def create_set(investigation_id:int,payload:EventSetCreate,user=Depends(get_current_user),db=Depends(get_db)):
    inv=reasoning.ensure_finding_produce(db,case(db,investigation_id,user),user)
    return set_read(service.create_set(db,inv,payload,user))


@router.post('/runs',status_code=201)
def execute(investigation_id:int,payload:DetectionCreate,user=Depends(get_current_user),db=Depends(get_db)):
    inv=reasoning.ensure_finding_produce(db,case(db,investigation_id,user),user)
    return run_read(service.execute(db,inv,payload,user))


@router.get('/runs')
def runs(investigation_id:int,event_set_id:int|None=Query(None,gt=0),limit:int=Query(25,ge=1,le=100),offset:int=Query(0,ge=0,le=100000),user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user)
    stmt=select(AuthenticationDetectionRun).where(AuthenticationDetectionRun.investigation_id==inv.id)
    if event_set_id:
        service.get_set(db,inv,event_set_id)
        stmt=stmt.where(AuthenticationDetectionRun.event_set_id==event_set_id)
    total=db.scalar(select(func.count()).select_from(stmt.subquery()))
    return {'items':[run_read(r) for r in db.scalars(stmt.order_by(AuthenticationDetectionRun.id.desc()).limit(limit).offset(offset))],'total':total,'limit':limit,'offset':offset}


@router.post('/runs/{run_id}/recover')
def recover(investigation_id:int,run_id:int,user=Depends(get_current_user),db=Depends(get_db)):
    inv=reasoning.ensure_finding_produce(db,case(db,investigation_id,user),user)
    return run_read(service.recover(db,inv,run_id,user))


@router.get('/findings')
def findings(investigation_id:int,event_set_id:int=Query(gt=0),run_id:int|None=Query(None,gt=0),limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0,le=100000),user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user)
    service.get_set(db,inv,event_set_id)
    ids=select(DetectionRunFinding.finding_id).join(AuthenticationDetectionRun,AuthenticationDetectionRun.id==DetectionRunFinding.run_id).where(
        AuthenticationDetectionRun.investigation_id==inv.id,AuthenticationDetectionRun.event_set_id==event_set_id,AuthenticationDetectionRun.status=='completed')
    if run_id:
        ids=ids.where(AuthenticationDetectionRun.id==run_id)
    # PostgreSQL JSON columns have no equality operator; deduplicate membership
    # through scalar identifiers rather than SELECT DISTINCT on whole findings.
    stmt=select(Finding).where(Finding.investigation_id==inv.id,Finding.id.in_(ids))
    total=db.scalar(select(func.count()).select_from(stmt.subquery()))
    return {'items':[_to_finding_read(db,f) for f in db.scalars(stmt.order_by(Finding.rule_id,Finding.inputs_key).limit(limit).offset(offset))],'total':total,'limit':limit,'offset':offset}


@router.get('/findings/{finding_id}/history')
def history(investigation_id:int,finding_id:int,user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user)
    finding=reasoning.get_finding(db,inv,finding_id)
    if not finding:
        raise HTTPException(404,'Finding not found.')
    # SQL JSON extraction avoids scanning unrelated audit bodies.
    stmt=select(AuditEvent).where(AuditEvent.resource_type=='investigation',AuditEvent.resource_id==str(inv.id),
        AuditEvent.event_metadata['finding_id'].as_integer()==finding_id).order_by(AuditEvent.id.desc()).limit(100)
    return [{'actor_id':r.actor_id,'created_at':r.created_at,'action':r.action,'decision':r.event_metadata} for r in db.scalars(stmt)]


@router.get('/timeline')
def timeline(investigation_id:int,event_set_id:int=Query(gt=0),
    lane:Literal['utc','assumed','uncertain']='utc',username:str|None=Query(None,max_length=256),
    account_domain:str|None=Query(None,max_length=256),domain_missing:bool=False,
    provider:str|None=Query(None,max_length=100),host:str|None=Query(None,max_length=256),
    source_ip:str|None=Query(None,max_length=100),outcome:Literal['success','failure','unknown']|None=None,
    event_type:str|None=Query(None,max_length=64),finding_id:int|None=Query(None,gt=0),
    start:datetime|None=None,end:datetime|None=None,limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0,le=100000),
    user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user)
    item=service.get_set(db,inv,event_set_id)
    for value in (start,end):
        if value and (value.tzinfo is None or value.utcoffset() is None):
            raise HTTPException(422,'Time boundaries require explicit timezone offsets.')
    if start and end and start>end:
        raise HTTPException(422,'Time range start must precede end.')
    if lane=='uncertain' and (start or end):
        raise HTTPException(422,'Uncertain timestamps cannot be filtered using a UTC range.')
    stmt=select(SecurityEvent).join(EventSetMember,EventSetMember.event_id==SecurityEvent.id).where(EventSetMember.set_id==item.id,EventSetMember.included.is_(True),SecurityEvent.investigation_id==inv.id)
    certainty=SecurityEvent.time_semantics['certainty'].as_string()
    if lane=='utc':
        stmt=stmt.where(SecurityEvent.timestamp_utc.is_not(None),certainty.in_(['source_offset','source_utc_field']))
    elif lane=='assumed':
        stmt=stmt.where(SecurityEvent.timestamp_utc.is_not(None),certainty.in_(['profile_offset','profile_zone']))
    else:
        stmt=stmt.where(SecurityEvent.timestamp_utc.is_(None))
    for field,value in [('username',username),('account_domain',account_domain),('provider',provider),('hostname',host),('outcome',outcome),('event_type',event_type)]:
        if value is not None:
            stmt=stmt.where(getattr(SecurityEvent,field)==value)
    if domain_missing:
        if account_domain:
            raise HTTPException(422,'Choose an explicit domain or missing-domain scope, not both.')
        stmt=stmt.where(SecurityEvent.account_domain.is_(None))
    if source_ip:
        try: source_ip=str(ipaddress.ip_address(source_ip))
        except ValueError as exc: raise HTTPException(422,'Source IP must be valid.') from exc
        stmt=stmt.where(SecurityEvent.source_ip==source_ip)
    if start: stmt=stmt.where(SecurityEvent.timestamp_utc>=start)
    if end: stmt=stmt.where(SecurityEvent.timestamp_utc<=end)
    if finding_id:
        finding=reasoning.get_finding(db,inv,finding_id)
        if not finding or (finding.support_snapshot or {}).get('event_set_id')!=item.id:
            raise HTTPException(404,'Finding does not belong to this event set.')
        stmt=stmt.where(SecurityEvent.semantic_key.in_(finding.support_snapshot['event_keys']))
    total=db.scalar(select(func.count()).select_from(stmt.subquery()))
    order=(SecurityEvent.evidence_id,SecurityEvent.semantic_key) if lane=='uncertain' else (SecurityEvent.timestamp_utc,SecurityEvent.semantic_key)
    rows=list(db.scalars(stmt.order_by(*order).limit(limit).offset(offset)))
    return {'items':[{**EventRead.model_validate(e).model_dump(),'support_verified':current_integrity(db,e)} for e in rows],
        'total':total,'limit':limit,'offset':offset,'lane':lane,'coverage':item.coverage,
        'ordering':'UTC projections with explicit assumptions; not causal order.' if lane!='uncertain' else 'Grouped by source; stable display ordering is not event-time ordering.'}
