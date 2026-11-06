"""Native legacy backup/restore rehearsal with synthetic data and disposable PostgreSQL."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.modules.evidence import storage
from app.ops.recovery import fingerprints, native, pg_environment, validate_reports


def test_native_legacy_restore_then_m6_upgrade(tmp_path, monkeypatch):
    url = os.getenv('M1_POSTGRES_TEST_URL')
    pg_bin = os.getenv('M5_PG_BIN')
    if not url or not pg_bin:
        pytest.skip('Disposable PostgreSQL and native utilities are required.')
    parsed = make_url(url)
    assert parsed.database == 'provena_ci' and parsed.host in {'127.0.0.1', 'localhost'}
    suffix = uuid.uuid4().hex
    names = ['provena_legacy_' + suffix, 'provena_legacy_restore_' + suffix]
    urls = [parsed.set(database=name).render_as_string(hide_password=False) for name in names]
    controller = create_engine(url)
    created, engines = [], []
    def migrate(target, *args):
        result = subprocess.run([sys.executable, '-m', 'alembic', *args],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=120,
            env={**os.environ, 'APP_ENV': 'test', 'DATABASE_URL': target})
        assert result.returncode == 0, result.stdout + result.stderr
    try:
        with controller.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            for name in names:
                connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
                created.append(name)
        migrate(urls[0], 'upgrade', '9b6e5c4d3a21')
        source, target = [create_engine(item) for item in urls]
        engines.extend([source, target])
        metadata = MetaData()
        metadata.reflect(bind=source)
        monkeypatch.setattr(settings, 'evidence_storage_backend', 'local')
        monkeypatch.setattr(settings, 'evidence_storage_root', str(tmp_path / 'source-evidence'))
        content = {'synthetic': 'Preserved legacy report'}
        report_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        with source.begin() as connection:
            def insert(table_name, **values):
                table = metadata.tables[table_name]
                return connection.scalar(table.insert().values(**values).returning(table.c.id))
            uid = insert('users', username='synthetic_owner', email='owner@example.test', full_name='Synthetic',
                password_hash='unused-synthetic-hash', role='admin', is_active=True)
            wid = insert('workspaces', name='Synthetic legacy', slug='synthetic-legacy', created_by_id=uid)
            insert('workspace_memberships', workspace_id=wid, user_id=uid, role='admin', is_active=True)
            iid = insert('investigations', case_number='LEGACY-RESTORE', title='Synthetic legacy', description='',
                status='open', priority='medium', created_by_id=uid, lead_investigator_id=uid, workspace_id=wid)
            local = storage.LocalEvidenceStorage(settings.evidence_storage_root)
            upload = local.stage(io.BytesIO(b'2026-11-05T12:00:00Z synthetic sshd[1]: Failed password for mira from 192.0.2.10 port 2200 ssh2\n'), iid, 4096)
            local.finalize(upload)
            eid = insert('evidence', investigation_id=iid, evidence_number='E001', title='Synthetic', description='',
                evidence_type='log', original_filename='synthetic.log', source='Synthetic', registered_by_id=uid,
                file_size=upload.size, storage_key=upload.storage_key, sha256=upload.sha256, integrity_status='verified')
            insert('evidence_verifications', evidence_id=eid, performed_by_id=uid,
                expected_sha256=upload.sha256, observed_sha256=upload.sha256, result='verified')
            insert('custody_events', evidence_id=eid, performed_by_id=uid, action='registered', notes='Synthetic')
            for index, decision in enumerate(('accepted', 'rejected')):
                insert('findings', investigation_id=iid, rule_id='legacy.synthetic', rule_version='1', title='Synthetic',
                    summary='Historical review', severity='low', confidence=10, factors=[], evidence_ids=[eid],
                    artifact_ids=[], correlation_ids=[], inputs_key=str(index) * 64, recommendations=[], status=decision)
            insert('reports', investigation_id=iid, report_number=1, generated_by_id=uid,
                content=content, content_sha256=report_hash)
        with source.connect() as connection:
            connection.execute(text("SET TIME ZONE 'UTC'"))
            before = fingerprints(connection)
            validate_reports(connection)
        # No application or external writer exists during this synthetic boundary.
        dump = tmp_path / 'legacy.dump'
        result = subprocess.run([native('pg_dump', pg_bin), '--format=custom', '--no-owner', '--no-acl',
            '--file=' + str(dump)], env=pg_environment(urls[0]), capture_output=True, timeout=120)
        assert result.returncode == 0
        evidence_copy = tmp_path / 'legacy-evidence.bin'
        with storage.snapshot(upload.storage_key, upload.size) as snapshot:
            assert snapshot.sha256 == upload.sha256
            with evidence_copy.open('xb') as output:
                while chunk := snapshot.handle.read(1024 * 1024):
                    output.write(chunk)
        with source.begin() as connection:
            connection.execute(metadata.tables['investigation_notes'].insert().values(
                investigation_id=iid, author_id=uid, body='Synthetic post-boundary write'))
        with target.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'")) == 0
        result = subprocess.run([native('pg_restore', pg_bin), '--single-transaction', '--exit-on-error',
            '--no-owner', '--no-acl', '--dbname=' + names[1], str(dump)],
            env=pg_environment(urls[1]), capture_output=True, timeout=120)
        assert result.returncode == 0
        restored = storage.LocalEvidenceStorage(tmp_path / 'restored-evidence')
        restored.prepare_restore()
        with evidence_copy.open('rb') as copied:
            restored.restore_verified(upload.storage_key, copied, upload.sha256, upload.size)
        with target.connect() as connection:
            connection.execute(text("SET TIME ZONE 'UTC'"))
            assert fingerprints(connection) == before
            validate_reports(connection)
            assert connection.scalar(text('SELECT count(*) FROM investigation_notes')) == 0
        restored.complete_restore()
        migrate(urls[1], 'upgrade', 'head')
        migrate(urls[1], 'check')
        with target.connect() as connection:
            assert connection.scalar(text('SELECT version_num FROM alembic_version')) == 'ee5b99eb5ce4'
            assert connection.scalar(text('SELECT content_sha256 FROM reports')) == report_hash
            assert set(connection.scalars(text('SELECT status FROM findings'))) == {'accepted', 'rejected'}
            assert connection.scalar(text('SELECT count(*) FROM custody_events')) == 1
            assert connection.scalar(text('SELECT count(*) FROM workspace_memberships')) == 1
            assert connection.scalar(text('SELECT sha256 FROM evidence')) == upload.sha256
        with restored.open(upload.storage_key) as handle:
            assert hashlib.sha256(handle.read(4096)).hexdigest() == upload.sha256
    finally:
        for engine in engines:
            engine.dispose()
        with controller.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            for name in reversed(created):
                assert name in names and name.endswith(suffix)
                connection.exec_driver_sql(f'DROP DATABASE "{name}"')
        controller.dispose()
