"""Authorized metadata/original export selection, history, recovery and downloads."""
import hashlib
import tempfile
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy import select
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.investigations import service as investigations
from app.modules.events.router import case
from app.core.config import settings
from app.ops.archive import CHUNK
from .models import InvestigationExport
from .schemas import ExportCreate, ExportRead
from . import service, artifacts

router=APIRouter(prefix='/investigations/{investigation_id}/exports',tags=['investigation-exports'])


@router.get('',response_model=list[ExportRead])
def history(investigation_id:int,limit:int=Query(25,ge=1,le=100),offset:int=Query(0,ge=0,le=100000),user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user)
    return list(db.scalars(select(InvestigationExport).where(InvestigationExport.investigation_id==inv.id)
        .order_by(InvestigationExport.id.desc()).limit(limit).offset(offset)))


@router.post('',response_model=ExportRead,status_code=201)
def create(investigation_id:int,payload:ExportCreate,request_key:str|None=Header(None,alias='Idempotency-Key',min_length=1,max_length=128),user=Depends(get_current_user),db=Depends(get_db)):
    return service.create(db,case(db,investigation_id,user),payload,user,request_key)


@router.post('/{export_id}/recover',response_model=ExportRead)
def recover(investigation_id:int,export_id:int,user=Depends(get_current_user),db=Depends(get_db)):
    inv=investigations.ensure_manage(db,case(db,investigation_id,user),user)
    return service.recover(db,inv,service.get_export(db,inv,export_id),user,prune=True)


@router.get('/{export_id}/download')
def download(investigation_id:int,export_id:int,user=Depends(get_current_user),db=Depends(get_db)):
    inv=case(db,investigation_id,user)
    item=service.get_export(db,inv,export_id)
    if item.mode=='originals': investigations.ensure_manage(db,inv,user)
    if item.status!='completed' or service.expired(item): raise HTTPException(409,'Export is incomplete or expired. Generate a new package.')
    snapshot=tempfile.TemporaryFile(mode='w+b')
    try:
        digest=hashlib.sha256();size=0
        with artifacts.path(item.artifact_key).open('rb') as source:
            while chunk:=source.read(CHUNK):
                size+=len(chunk)
                if size>settings.export_max_bytes: raise ValueError('Package limit exceeded.')
                digest.update(chunk);snapshot.write(chunk)
        if digest.hexdigest()!=item.package_sha256 or size!=item.byte_size:
            raise ValueError('Package integrity check failed.')
        snapshot.seek(0)
        service.audit(db,item,user,'EXPORT_DOWNLOADED');db.commit()
    except Exception as exc:
        snapshot.close();db.rollback()
        raise HTTPException(409,'Export package is unavailable or changed. Generate a new package.') from exc
    def chunks():
        try:
            while chunk:=snapshot.read(CHUNK): yield chunk
        finally: snapshot.close()
    return StreamingResponse(chunks(),media_type='application/zip',background=BackgroundTask(snapshot.close),headers={
        'Content-Disposition':f'attachment; filename="provena-case-{inv.id}-export-{item.id}.zip"',
        'Content-Length':str(size),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
        'Content-Security-Policy':"default-src 'none'"})
