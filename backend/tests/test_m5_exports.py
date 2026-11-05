"""Synthetic export generation, offline integrity and authorization checks."""
import io
import json
from zipfile import ZipFile, ZIP_STORED
import pytest
from sqlalchemy import select
from app.ops.archive import inspect_package, canonical
from app.modules.exports.models import InvestigationExport
from app.core.config import settings
from tests.test_m4_workbench import scenario, selection, execute
from tests.conftest import auth_headers, login, make_user
from tests.test_evidence_foundation import backend, setup_item


@pytest.fixture(autouse=True)
def export_root(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'export_storage_root',str(tmp_path/'exports'))


def package(client,user,db):
    base,h,item,profile,run,token,_=scenario(client,user)
    selected=selection(client,base,h,[run['id']]);execute(client,base,h,selected['id'])
    finding=client.get(base+f"/authentication/findings?event_set_id={selected['id']}",headers=h).json()['items'][0]
    client.post(base+f"/analysis/findings/{finding['id']}/review",headers=h,json={'status':'accepted'}).raise_for_status()
    report=client.post(base+f"/analysis/reports?event_set_id={selected['id']}",headers=h).json()
    return base,h,item,selected,report


@pytest.mark.parametrize('mode',['metadata','originals'])
def test_export_verifies_and_preserves_report_hash(client,investigator,db_session,storage_dir,mode):
    base,h,item,selected,report=package(client,investigator,db_session)
    payload={'mode':mode,'event_set_ids':[selected['id']],'report_ids':[report['id']],
        'evidence_ids':[item['id']] if mode=='originals' else []}
    response=client.post(base+'/exports',headers={**h,'Idempotency-Key':'synthetic-export'},json=payload)
    assert response.status_code==201,response.text
    result=response.json();assert result['status']=='completed',result
    assert not any(key in response.text for key in ('storage_key','artifact_key','staging_ref'))
    download=client.get(base+f"/exports/{result['id']}/download",headers=h)
    assert download.status_code==200
    manifest=inspect_package(io.BytesIO(download.content))
    assert manifest['reports'][0]['content_sha256']==report['content_sha256']
    assert bool(manifest['evidence'][0]['included_path'])==(mode=='originals')
    with ZipFile(io.BytesIO(download.content)) as archive:
        assert b'storage_key' not in archive.read('metadata/evidence.jsonl')
        assert len(archive.read('metadata/events.jsonl').splitlines())==6
    repeat=client.post(base+'/exports',headers={**h,'Idempotency-Key':'synthetic-export'},json=payload).json()
    assert repeat['id']==result['id']
    assert client.post(base+'/exports',headers={**h,'Idempotency-Key':'synthetic-export'},json={'mode':'metadata'}).status_code==409


def test_cross_case_access_and_tampered_originals(client,investigator,db_session,storage_dir):
    from app.modules.evidence import storage
    from app.modules.evidence.models import Evidence
    base,h,item,selected,report=package(client,investigator,db_session)
    stranger=make_user(db_session,'export_stranger')
    foreign=auth_headers(login(client,stranger.username))
    assert client.post(base+'/exports',headers=foreign,json={'mode':'metadata'}).status_code==404
    assert client.post(base+'/exports',headers=h,json={'mode':'originals'}).status_code==422
    evidence=db_session.get(Evidence,item['id'])
    storage.resolve(evidence.storage_key).write_bytes(b'changed')
    result=client.post(base+'/exports',headers=h,json={'mode':'originals','evidence_ids':[item['id']]}).json()
    assert result['status']=='failed'
    assert client.get(base+f"/exports/{result['id']}/download",headers=h).status_code==409
    assert db_session.get(Evidence,item['id']).integrity_status=='mismatch'


def test_offline_verifier_detects_tampering_and_paths(client,investigator,db_session,storage_dir):
    base,h,item,selected,report=package(client,investigator,db_session)
    result=client.post(base+'/exports',headers=h,json={'mode':'metadata','report_ids':[report['id']]}).json()
    assert result['status']=='completed',result
    content=client.get(base+f"/exports/{result['id']}/download",headers=h).content
    with ZipFile(io.BytesIO(content)) as original:
        files={name:original.read(name) for name in original.namelist()}
    for change in ('altered','missing','unexpected','traversal','unsupported','report'):
        mutated=dict(files)
        if change=='altered': mutated['metadata/evidence.jsonl']+=b'changed'
        if change=='missing': del mutated['metadata/evidence.jsonl']
        if change=='unexpected': mutated['unexpected.txt']=b'unlisted'
        if change=='traversal': mutated['../escape']=b'unsafe'
        if change in ('unsupported','report'):
            manifest=json.loads(mutated['manifest.json'])
            if change=='unsupported': manifest['schema']='unsupported/9'
            else: manifest['reports'][0]['content_sha256']='0'*64
            mutated['manifest.json']=canonical(manifest)
        out=io.BytesIO()
        with ZipFile(out,'w',compression=ZIP_STORED) as archive:
            for name,value in mutated.items(): archive.writestr(name,value)
        with pytest.raises(ValueError): inspect_package(io.BytesIO(out.getvalue()))


def test_viewer_cannot_export_original_bytes(client,investigator,db_session,storage_dir):
    from app.modules.investigations.models import InvestigationMember
    base,h,item,selected,report=package(client,investigator,db_session)
    viewer=make_user(db_session,'export_viewer')
    db_session.add(InvestigationMember(investigation_id=int(base.rsplit('/',1)[1]),user_id=viewer.id,team_role='member'))
    db_session.commit()
    vh=auth_headers(login(client,viewer.username))
    assert client.post(base+'/exports',headers=vh,json={'mode':'metadata'}).json()['status']=='completed'
    payload={'mode':'originals','evidence_ids':[item['id']]}
    assert client.post(base+'/exports',headers=vh,json=payload).status_code==403
    original=client.post(base+'/exports',headers=h,json=payload).json()
    assert client.get(base+f"/exports/{original['id']}/download",headers=vh).status_code==403


@pytest.mark.parametrize('failure',['build','commit_before','commit_after','cleanup'])
def test_failed_exports_and_ambiguous_commits(client,investigator,db_session,storage_dir,monkeypatch,failure):
    from app.modules.exports import service,artifacts
    base,h,item,selected,report=package(client,investigator,db_session)
    original_build=service.build
    if failure in ('build','cleanup'):
        def fail_build(*args): raise OSError('Synthetic private location must never appear')
        monkeypatch.setattr(service,'build',fail_build)
    if failure=='cleanup':
        def fail_remove(*args): raise OSError('Synthetic cleanup failure')
        monkeypatch.setattr(artifacts,'remove',fail_remove)
    if failure in ('commit_before','commit_after'):
        original_commit=db_session.commit
        calls=[]
        def uncertain_commit():
            calls.append(True)
            if len(calls)==2:
                if failure=='commit_after': original_commit()
                raise OSError('Synthetic lost acknowledgement')
            original_commit()
        monkeypatch.setattr(db_session,'commit',uncertain_commit)
    response=client.post(base+'/exports',headers=h,json={'mode':'metadata'})
    assert response.status_code==201,response.text
    result=response.json()
    assert result['status']==('completed' if failure=='commit_after' else 'failed')
    assert 'Synthetic' not in response.text
    if result['status']=='failed':
        assert client.get(base+f"/exports/{result['id']}/download",headers=h).status_code==409
    monkeypatch.setattr(service,'build',original_build)
    if failure=='cleanup':
        assert db_session.get(InvestigationExport,result['id']).manifest_summary['cleanup_pending']
        monkeypatch.undo()


def test_expiry_and_changed_package_fail_safely(client,investigator,db_session,storage_dir):
    from datetime import datetime,timedelta,timezone
    from app.modules.exports import artifacts
    base,h,item,selected,report=package(client,investigator,db_session)
    result=client.post(base+'/exports',headers=h,json={'mode':'metadata'}).json()
    row=db_session.get(InvestigationExport,result['id'])
    artifacts.path(row.artifact_key).write_bytes(b'altered generated archive')
    assert client.get(base+f"/exports/{row.id}/download",headers=h).status_code==409
    row.created_at=datetime.now(timezone.utc)-timedelta(days=8);db_session.commit()
    recovered=client.post(base+f"/exports/{row.id}/recover",headers=h).json()
    assert recovered['status']=='expired'
    assert not artifacts.path(row.artifact_key).exists()
    assert db_session.get(InvestigationExport,row.id) is not None


def test_registration_commit_failure_creates_no_usable_archive(client,investigator,db_session,storage_dir,monkeypatch):
    from app.modules.exports import artifacts
    base,h,item,selected,report=package(client,investigator,db_session)
    def unavailable(): raise OSError('Synthetic database private connection details')
    monkeypatch.setattr(db_session,'commit',unavailable)
    response=client.post(base+'/exports',headers=h,json={'mode':'metadata'})
    assert response.status_code==503 and 'private connection' not in response.text
    assert db_session.scalar(select(InvestigationExport)) is None
    assert not artifacts.root().exists()


def test_explicit_selection_and_budgets_fail_closed(client,investigator,db_session,storage_dir,monkeypatch):
    base,h,item,selected,report=package(client,investigator,db_session)
    for payload in ({'mode':'metadata','event_set_ids':[99999]}, {'mode':'metadata','report_ids':[99999]}):
        result=client.post(base+'/exports',headers=h,json=payload).json()
        assert result['status']=='failed'
    monkeypatch.setattr(settings,'export_metadata_max_bytes',1)
    result=client.post(base+'/exports',headers=h,json={'mode':'metadata'}).json()
    assert result['status']=='failed'
    assert client.get(base+f"/exports/{result['id']}/download",headers=h).status_code==409


def test_interrupted_builder_cleanup_is_operation_scoped(tmp_path,monkeypatch):
    from app.modules.exports import artifacts
    monkeypatch.setattr(settings,'export_storage_root',str(tmp_path/'exports'))
    root=artifacts.root();root.mkdir()
    key='a'*32+'.zip'
    owned=root/('building-'+key+'-synthetic');owned.mkdir();(owned/'package.zip').write_bytes(b'partial')
    unrelated=root/'building-unrelated';unrelated.mkdir();(unrelated/'private.txt').write_text('preserve')
    artifacts.remove(key)
    assert not owned.exists() and (unrelated/'private.txt').read_text()=='preserve'
    unsafe=root/('building-'+key+'-unexpected');unsafe.mkdir();(unsafe/'other.txt').write_text('preserve')
    with pytest.raises(OSError): artifacts.remove(key)
    assert (unsafe/'other.txt').read_text()=='preserve'


@pytest.mark.parametrize('phase',['build','commit_before','commit_after'])
def test_interruption_preserves_completed_exports_and_durable_recovery(client,investigator,db_session,storage_dir,monkeypatch,phase):
    from app.modules.exports import service,artifacts
    from app.modules.exports.schemas import ExportCreate
    from app.modules.investigations.models import Investigation
    from app.modules.audit.models import AuditEvent
    class Interrupted(BaseException): pass
    base,h,item,selected,report=package(client,investigator,db_session)
    completed=client.post(base+'/exports',headers=h,json={'mode':'metadata'}).json()
    stable=db_session.get(InvestigationExport,completed['id'])
    stable_path=artifacts.path(stable.artifact_key)
    stable_bytes=stable_path.read_bytes()
    inv=db_session.get(Investigation,int(base.rsplit('/',1)[1]))
    original_build=service.build;original_commit=db_session.commit
    if phase=='build':
        def interrupted_build(db,inv,actor,item,target):
            target.write_bytes(b'synthetic interrupted builder')
            raise Interrupted()
        monkeypatch.setattr(service,'build',interrupted_build)
    else:
        commits=[]
        def interrupted_commit():
            commits.append(True)
            if len(commits)==2:
                if phase=='commit_after': original_commit()
                raise Interrupted()
            original_commit()
        monkeypatch.setattr(db_session,'commit',interrupted_commit)
    with pytest.raises(Interrupted):
        service.create(db_session,inv,ExportCreate(mode='metadata'),investigator,'interrupted-synthetic')
    db_session.rollback()
    monkeypatch.setattr(service,'build',original_build)
    monkeypatch.setattr(db_session,'commit',original_commit)
    interrupted=db_session.scalar(select(InvestigationExport).where(InvestigationExport.id!=stable.id))
    assert interrupted.status==('completed' if phase=='commit_after' else 'running')
    assert not list(artifacts.root().glob('building-*'))
    retry=client.post(base+'/exports',headers={**h,'Idempotency-Key':'interrupted-synthetic'},json={'mode':'metadata'}).json()
    assert retry['id']==interrupted.id
    expected=200 if phase=='commit_after' else 409
    assert client.get(base+f'/exports/{interrupted.id}/download',headers=h).status_code==expected
    recovered=client.post(base+f'/exports/{interrupted.id}/recover',headers=h).json()
    assert recovered['status']==('completed' if phase=='commit_after' else 'failed')
    assert artifacts.path(interrupted.artifact_key).exists()==(phase=='commit_after')
    assert stable_path.read_bytes()==stable_bytes
    assert client.post(base+f'/exports/{stable.id}/recover',headers=h).json()['status']=='completed'
    assert stable_path.read_bytes()==stable_bytes
    if phase!='commit_after':
        assert db_session.scalar(select(AuditEvent).where(AuditEvent.action=='EXPORT_RECOVERED')) is not None
        replacement=client.post(base+'/exports',headers={**h,'Idempotency-Key':'fresh-after-recovery'},json={'mode':'metadata'}).json()
        assert replacement['status']=='completed' and replacement['id']!=interrupted.id


@pytest.mark.parametrize('change',['unchanged','missing','after_snapshot'])
def test_original_export_storage_contract(backend,client,investigator,db_session,monkeypatch,change):
    from contextlib import contextmanager
    from app.modules.evidence import storage
    store,replace,remove=backend
    _,_,item,base,h,row=setup_item(client,investigator,db_session)
    if change=='missing': remove(row.storage_key)
    if change=='after_snapshot':
        original_snapshot=storage.snapshot
        @contextmanager
        def mutation_after_copy(*args,**kwargs):
            with original_snapshot(*args,**kwargs) as copied:
                replace(row.storage_key,b'mutated after private snapshot')
                yield copied
        monkeypatch.setattr(storage,'snapshot',mutation_after_copy)
    result=client.post(base+'/exports',headers=h,json={'mode':'originals','evidence_ids':[item['id']]}).json()
    assert result['status']==('failed' if change=='missing' else 'completed'),result
    if result['status']=='completed':
        content=client.get(base+f"/exports/{result['id']}/download",headers=h).content
        manifest=inspect_package(io.BytesIO(content))
        assert manifest['evidence'][0]['sha256']==item['sha256']
    else:
        db_session.refresh(row)
        assert row.integrity_status=='unavailable'
