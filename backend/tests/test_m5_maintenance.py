"""Maintenance selects eligible work before applying its bounded scan limit."""
from datetime import datetime,timedelta,timezone
import uuid
from sqlalchemy import insert,select,func
from app.core.config import settings
from app.modules.exports.models import InvestigationExport
from app.modules.exports import artifacts
from app.ops import maintenance
from tests.conftest import login
from tests.test_evidence import make_investigation


def test_retention_does_not_starve_behind_recent_completed_work(client,investigator,db_session,tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'export_storage_root',str(tmp_path/'exports'))
    inv=make_investigation(client,login(client,investigator.username))
    now=datetime.now(timezone.utc)
    common={'investigation_id':inv['id'],'requested_by_id':investigator.id,'selection_hash':'0'*64,
        'selection':{},'mode':'metadata','status':'completed','manifest_summary':{},'created_at':now}
    db_session.execute(insert(InvestigationExport),[{**common,'artifact_key':uuid.uuid4().hex+'.zip'} for _ in range(5001)])
    expired=InvestigationExport(**{**common,'artifact_key':uuid.uuid4().hex+'.zip','created_at':now-timedelta(days=8)})
    failed=InvestigationExport(**{**common,'status':'failed','artifact_key':uuid.uuid4().hex+'.zip','manifest_summary':{'cleanup_pending':True}})
    db_session.add_all([expired,failed]);db_session.commit()
    ids=expired.id,failed.id
    artifacts.root().mkdir()
    for item in (expired,failed): artifacts.path(item.artifact_key).write_bytes(b'synthetic cache')
    engine=db_session.get_bind()
    monkeypatch.setattr(maintenance,'create_engine',lambda url:engine)
    monkeypatch.setattr(engine,'dispose',lambda:None)
    result=maintenance.prune('sqlite://')
    assert result['closed_operations']==2
    db_session.expire_all()
    assert db_session.get(InvestigationExport,ids[0]).status=='expired'
    assert db_session.get(InvestigationExport,ids[1]).manifest_summary['cleanup_pending'] is False
    assert db_session.scalar(select(func.count()).select_from(InvestigationExport))==5003
    assert not list(artifacts.root().iterdir())
