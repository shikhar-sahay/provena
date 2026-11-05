"""Real native PostgreSQL dump/restore of a synthetic, authorized investigation."""
import os
import uuid
import subprocess
import sys
import time
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.modules.users.models import Role
from tests.conftest import make_user, login, auth_headers
from tests.test_m5_exports import package
from app.ops.archive import inspect_package, BACKUP_SCHEMA
from app.ops.recovery import backup, restore


def test_real_synthetic_export_backup_restore(tmp_path,monkeypatch):
    url=os.getenv('M1_POSTGRES_TEST_URL')
    if not url: pytest.skip('Disposable PostgreSQL database not configured.')
    parsed=make_url(url)
    assert parsed.database=='provena_ci' and parsed.host in ('localhost','127.0.0.1')
    monkeypatch.setattr(settings,'evidence_storage_backend','local')
    monkeypatch.setattr(settings,'evidence_storage_root',str(tmp_path/'source-evidence'))
    monkeypatch.setattr(settings,'export_storage_root',str(tmp_path/'source-exports'))
    suffix=uuid.uuid4().hex[:10]
    source_name='provena_backup_'+suffix
    source_url=parsed.set(database=source_name).render_as_string(hide_password=False)
    controller=create_engine(url)
    with controller.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{source_name}"')
    controller.dispose()
    migrated=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],
        env={**os.environ,'DATABASE_URL':source_url,'APP_ENV':'test'},cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=120)
    assert migrated.returncode==0,migrated.stdout+migrated.stderr
    source=create_engine(source_url)
    target_name='provena_restore_'+suffix
    target_url=parsed.set(database=target_name).render_as_string(hide_password=False)
    try:
        with Session(source) as db:
            def dependency(): yield db
            app.dependency_overrides[get_db]=dependency
            user=make_user(db,username='recovery_'+suffix,role=Role.ADMIN)
            uid=user.id
            username=user.username
            stranger=make_user(db,username='recovery_stranger_'+suffix,role=Role.INVESTIGATOR)
            stranger_name=stranger.username
            with TestClient(app) as client:
                base,h,evidence,selected,report=package(client,user,db)
                export=client.post(base+'/exports',headers=h,json={'mode':'originals','event_set_ids':[selected['id']],
                    'report_ids':[report['id']],'evidence_ids':[evidence['id']]}).json()
                assert export['status']=='completed',export
                download=client.get(base+f"/exports/{export['id']}/download",headers=h)
                assert download.status_code==200
                import io
                inspect_package(io.BytesIO(download.content))
                from zipfile import ZipFile,ZIP_STORED
                altered=io.BytesIO()
                with ZipFile(io.BytesIO(download.content)) as original,ZipFile(altered,'w',compression=ZIP_STORED) as changed:
                    for name in original.namelist():
                        content=original.read(name)
                        changed.writestr(name,content+b'changed' if name=='metadata/evidence.jsonl' else content)
                with pytest.raises(ValueError): inspect_package(io.BytesIO(altered.getvalue()))
            app.dependency_overrides.pop(get_db,None)
        # Concurrent retries share one durable export, not two independent snapshots.
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from app.modules.exports import service as exports
        from app.modules.exports.schemas import ExportCreate
        from app.modules.users.models import User
        from app.modules.investigations.models import Investigation
        barrier=Barrier(2)
        def export_retry():
            with Session(source) as db:
                actor=db.get(User,uid);case=db.get(Investigation,int(base.rsplit('/',1)[1]))
                barrier.wait(timeout=15)
                return exports.create(db,case,ExportCreate(mode='metadata',event_set_ids=[selected['id']]),actor,'concurrent-synthetic').id
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(export_retry) for _ in range(2)]
            assert futures[0].result(timeout=60)==futures[1].result(timeout=60)
        pg_bin=os.getenv('M5_PG_BIN')
        output=tmp_path/'synthetic.provena-backup.zip'
        # A row committed after the exported snapshot must not enter the dump.
        from app.ops import recovery
        from app.modules.intelligence.models import InvestigationNote
        original_popen=recovery.subprocess.Popen
        inserted=[]
        def concurrent_write(arguments,**kwargs):
            process=original_popen(arguments,**kwargs)
            if '--format=custom' in arguments and not inserted:
                with Session(source) as db:
                    db.add(InvestigationNote(investigation_id=int(base.rsplit('/',1)[1]),author_id=uid,body='Synthetic post-boundary annotation'))
                    db.commit();inserted.append(True)
            return process
        monkeypatch.setattr(recovery.subprocess,'Popen',concurrent_write)
        before=time.perf_counter();saved=backup(source_url,output,pg_bin=pg_bin)
        backup_duration=time.perf_counter()-before
        monkeypatch.setattr(recovery.subprocess,'Popen',original_popen)
        assert inserted
        manifest=inspect_package(output,expected_schema=BACKUP_SCHEMA,max_bytes=4*1024**3)
        assert manifest['table_fingerprints']['findings']['count']>=2
        guarded_name=target_name+'_guarded'
        with source.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{guarded_name}"')
        guarded_url=parsed.set(database=guarded_name).render_as_string(hide_password=False)
        guarded=create_engine(guarded_url)
        try:
            with guarded.begin() as connection:
                connection.exec_driver_sql('CREATE FUNCTION synthetic_guard() RETURNS integer LANGUAGE SQL AS $$ SELECT 1 $$')
            with pytest.raises(ValueError,match='not empty'):
                restore(guarded_url,output,tmp_path/'guarded-evidence',tmp_path/'guarded-exports',saved['sha256'],pg_bin=pg_bin)
            assert not (tmp_path/'guarded-evidence').exists()
            with guarded.connect() as connection: assert connection.scalar(text('SELECT synthetic_guard()'))==1
        finally: guarded.dispose()
        with source.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{target_name}"')
        before=time.perf_counter()
        result=restore(target_url,output,tmp_path/'restored-evidence',tmp_path/'restored-exports',saved['sha256'],pg_bin=pg_bin)
        restore_duration=time.perf_counter()-before
        assert result['restored']
        with pytest.raises(ValueError,match='not empty'):
            restore(target_url,output,tmp_path/'another-evidence',tmp_path/'another-exports',saved['sha256'],pg_bin=pg_bin)
        with pytest.raises(ValueError,match='SHA-256'):
            restore(target_url,output,tmp_path/'unused',tmp_path/'unused-cache','0'*64,pg_bin=pg_bin)
        monkeypatch.setattr(settings,'evidence_storage_root',str(tmp_path/'restored-evidence'))
        monkeypatch.setattr(settings,'export_storage_root',str(tmp_path/'restored-exports'))
        restored=create_engine(target_url)
        try:
            with Session(restored) as db:
                def restored_dependency(): yield db
                app.dependency_overrides[get_db]=restored_dependency
                with TestClient(app) as client:
                    assert client.get(base+'/evidence').status_code==401
                    h=auth_headers(login(client,username))
                    assert client.get(base+'/evidence',headers=h).status_code==200
                    findings=client.get(base+f"/authentication/findings?event_set_id={selected['id']}",headers=h).json()
                    assert findings['total']==2 and any(f['status']=='accepted' for f in findings['items'])
                    assert client.get(base+f"/analysis/reports/{report['id']}",headers=h).json()['content_sha256']==report['content_sha256']
                    assert client.get(base+f"/exports/{export['id']}/download",headers=h).status_code==200
                    assert client.get(base+f"/authentication/timeline?event_set_id={selected['id']}",headers=h).json()['total']==6
                    foreign=auth_headers(login(client,stranger_name))
                    assert client.get(base+'/evidence',headers=foreign).status_code==404
                assert db.scalar(text('SELECT count(*) FROM investigation_notes'))==0
            print('M5_POSTGRES_RECOVERY '+json.dumps({'database':'disposable PostgreSQL 16','package_bytes':saved['size'],
                'backup_seconds':backup_duration,'restore_seconds':restore_duration,'report_hash_preserved':True,
                'post_boundary_write_excluded':True,'concurrent_retry_stable':True},sort_keys=True))
        finally: restored.dispose()
    finally:
        app.dependency_overrides.pop(get_db,None)
        source.dispose()
