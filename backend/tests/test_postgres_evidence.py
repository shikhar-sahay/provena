"""Opt-in concurrency check against the disposable CI database only."""
import io
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.evidence.models import CustodyEvent, Evidence, EvidenceType
from app.modules.evidence.service import register_evidence
from app.modules.investigations.models import Investigation
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace


def test_postgres_parallel_registration_retry(tmp_path, monkeypatch):
    url = os.getenv("M1_POSTGRES_TEST_URL")
    if not url:
        pytest.skip("Disposable PostgreSQL CI database not configured.")
    parsed = make_url(url)
    assert parsed.database == "provena_ci" and parsed.host in {"127.0.0.1", "localhost"}
    monkeypatch.setattr(settings, "evidence_storage_backend", "local")
    monkeypatch.setattr(settings, "evidence_storage_root", str(tmp_path))
    engine = create_engine(url)
    suffix = uuid.uuid4().hex[:12]
    try:
        with Session(engine) as db:
            user = User(username=f"m1_{suffix}", email=f"{suffix}@example.test",
                        full_name="Synthetic CI", role="admin", password_hash="unused-test-hash")
            db.add(user)
            db.flush()
            workspace = Workspace(name="Synthetic CI", slug=f"m1-{suffix}", created_by_id=user.id)
            db.add(workspace)
            db.flush()
            inv = Investigation(title="Synthetic parallel retry", case_number=f"CI-{suffix}",
                workspace_id=workspace.id, created_by_id=user.id, lead_investigator_id=user.id)
            db.add(inv)
            db.commit()
            uid, inv_id = user.id, inv.id
        barrier = Barrier(2)
        def attempt():
            with Session(engine) as db:
                actor, investigation = db.get(User, uid), db.get(Investigation, inv_id)
                barrier.wait(timeout=15)
                return register_evidence(db, investigation, title="Retry", description="",
                    evidence_type=EvidenceType.LOG, source="Synthetic CI", acquired_at=None,
                    filename="retry.log", content_type="text/plain", stream=io.BytesIO(b"user=synthetic\n"),
                    actor=actor, request_key="parallel-retry").id
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt) for _ in range(2)]
            ids = [future.result(timeout=30) for future in futures]
        assert ids[0] == ids[1]
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Evidence).where(Evidence.investigation_id == inv_id)) == 1
            assert db.scalar(select(func.count()).select_from(CustodyEvent).where(
                CustodyEvent.evidence_id == ids[0], CustodyEvent.action == "registered")) == 1
        # Concurrent analytical passes must serialize identities and proposals,
        # not merely succeed on SQLite's different locking model.
        from app.modules.evidence.service import verify_evidence
        from app.modules.intelligence.service import start_run
        from app.modules.intelligence.reasoning import generate_findings
        from app.modules.intelligence.models import Correlation, Finding
        with Session(engine) as db:
            actor, investigation = db.get(User, uid), db.get(Investigation, inv_id)
            evidence_ids = [ids[0]]
            for filename in ["second.log", "third.log"]:
                evidence_ids.append(register_evidence(db, investigation, title="Synthetic", description="",
                    evidence_type=EvidenceType.LOG, source="Synthetic CI", acquired_at=None,
                    filename=filename, content_type="text/plain", stream=io.BytesIO(b"user=synthetic\n"),
                    actor=actor).id)
            for eid in evidence_ids:
                verify_evidence(db, investigation, db.get(Evidence, eid), actor)
        barrier = Barrier(2)
        def analyse():
            with Session(engine) as db:
                actor, investigation = db.get(User, uid), db.get(Investigation, inv_id)
                barrier.wait(timeout=15)
                run = start_run(db, investigation, evidence_ids, actor)
                assert run.status == "completed"
                findings, _ = generate_findings(db, investigation, actor)
                return [f.id for f in findings]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(analyse) for _ in range(2)]
            findings = [future.result(timeout=60) for future in futures]
        assert findings[0] == findings[1] and findings[0]
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Finding).where(Finding.investigation_id == inv_id)) == 1
            assert db.scalar(select(func.count()).select_from(Correlation).where(Correlation.investigation_id == inv_id)) == 1
    finally:
        engine.dispose()


@pytest.mark.parametrize('baseline', ['000a8976b7f1', '9b6e5c4d3a21'])
def test_deployment_legacy_upgrade_preserves_history(tmp_path, baseline):
    """Synthetic legacy schemas are not proof of the unknown production schema."""
    import hashlib
    import json
    import subprocess
    import sys
    from pathlib import Path
    from sqlalchemy import MetaData
    from app.ops.recovery import backup

    url = os.getenv('M1_POSTGRES_TEST_URL')
    if not url:
        pytest.skip('Disposable PostgreSQL database not configured.')
    parsed = make_url(url)
    assert parsed.database == 'provena_ci' and parsed.host in {'127.0.0.1', 'localhost'}
    schema = 'deployment_upgrade_' + uuid.uuid4().hex
    control = create_engine(url)
    with control.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    control.dispose()
    isolated = parsed.update_query_dict({'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    environment = {**os.environ, 'DATABASE_URL': isolated, 'APP_ENV': 'test'}
    def migrate(*args):
        result = subprocess.run([sys.executable, '-m', 'alembic', *args], env=environment,
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
    migrate('upgrade', '000a8976b7f1')
    engine = create_engine(isolated)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    content = {'synthetic': 'Legacy immutable report'}
    report_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    original_digest = hashlib.sha256(b'Synthetic legacy metadata fixture').hexdigest()
    try:
        with engine.begin() as connection:
            def insert(name, **values):
                table = metadata.tables[name]
                return connection.scalar(table.insert().values(**values).returning(table.c.id))
            uid = insert('users', username='legacy_synthetic', email='legacy@example.test', full_name='Synthetic',
                password_hash='unused-synthetic-hash', role='admin', is_active=True)
            iid = insert('investigations', case_number='LEGACY-SYNTHETIC', title='Synthetic legacy case',
                description='', status='open', priority='medium', created_by_id=uid, lead_investigator_id=uid)
            eid = insert('evidence', investigation_id=iid, evidence_number='E001', title='Synthetic metadata',
                description='', evidence_type='log', original_filename='synthetic.log', source='Synthetic',
                registered_by_id=uid, file_size=len(b'Synthetic legacy metadata fixture'), storage_key='synthetic-legacy-key', sha256=original_digest,
                integrity_status='verified')
            for index, decision in enumerate(('accepted', 'rejected')):
                insert('findings', investigation_id=iid, rule_id='legacy.synthetic', rule_version='1',
                    title='Historical decision', summary='Synthetic', severity='low', confidence=10,
                    factors=[], evidence_ids=[eid], artifact_ids=[], correlation_ids=[],
                    inputs_key=str(index) * 64, recommendations=[], status=decision)
            insert('reports', investigation_id=iid, report_number=1, generated_by_id=uid,
                content=content, content_sha256=report_hash)
        if baseline != '000a8976b7f1':
            migrate('upgrade', baseline)
        # Rejection must occur before evidence access: this backup tool is not a
        # legacy pre-upgrade backup strategy and must never be presented as one.
        with pytest.raises(ValueError, match='Backup schema must match'):
            backup(isolated, tmp_path / 'must-not-create.zip')
        assert not (tmp_path / 'must-not-create.zip').exists()
        migrate('upgrade', 'head')
        migrate('check')
        with engine.connect() as connection:
            from sqlalchemy import text
            assert connection.scalar(text('SELECT version_num FROM alembic_version')) == 'ee5b99eb5ce4'
            assert connection.scalar(text('SELECT content_sha256 FROM reports')) == report_hash
            assert connection.scalar(text('SELECT content FROM reports')) == content
            assert set(connection.scalars(text('SELECT status FROM findings'))) == {'accepted', 'rejected'}
            assert connection.scalar(text('SELECT count(*) FROM findings WHERE support_snapshot IS NOT NULL')) == 0
            assert connection.scalar(text('SELECT sha256 FROM evidence')) == original_digest
            assert connection.scalar(text('SELECT registration_status FROM evidence')) == 'ready'
            assert connection.scalar(text('SELECT count(*) FROM workspace_memberships')) == 1
            assert connection.scalar(text('SELECT workspace_id FROM investigations')) is not None
            assert connection.scalar(text('SELECT count(*) FROM security_events')) == 0
    finally:
        engine.dispose()


def test_postgres_parallel_authentication_selection_and_detection(tmp_path, monkeypatch):
    url=os.getenv('M1_POSTGRES_TEST_URL')
    if not url:
        pytest.skip('Disposable PostgreSQL CI database not configured.')
    parsed=make_url(url)
    assert parsed.database=='provena_ci' and parsed.host in {'127.0.0.1','localhost'}
    from app.modules.events.service import create_profile, ingest
    from app.modules.events.schemas import ProfileCreate
    from app.modules.evidence.service import verify_evidence
    from app.modules.detections.service import create_set, execute
    from app.modules.detections.schemas import EventSetCreate, DetectionCreate
    from app.modules.detections.models import InvestigationEventSet, DetectionRunFinding, AuthenticationDetectionRun
    from app.modules.intelligence.models import Finding
    from app.modules.workspaces.models import WorkspaceMembership
    monkeypatch.setattr(settings,'evidence_storage_backend','local')
    monkeypatch.setattr(settings,'evidence_storage_root',str(tmp_path))
    engine=create_engine(url)
    suffix=uuid.uuid4().hex[:12]
    try:
        with Session(engine) as db:
            actor=User(username=f'auth_{suffix}',email=f'{suffix}@example.test',full_name='Synthetic CI',role='admin',password_hash='unused')
            db.add(actor);db.flush()
            workspace=Workspace(name='Synthetic Authentication',slug=f'auth-{suffix}',created_by_id=actor.id)
            db.add(workspace);db.flush()
            actor.active_workspace_id=workspace.id
            db.add(WorkspaceMembership(workspace_id=workspace.id,user_id=actor.id,role='admin',is_active=True))
            inv=Investigation(title='Synthetic authentication',case_number=f'AUTH-{suffix}',workspace_id=workspace.id,created_by_id=actor.id,lead_investigator_id=actor.id)
            db.add(inv);db.commit()
            data=''.join(f'2026-11-05T12:00:{i*3:02d}Z host sshd[123]: Failed password for mira from 192.0.2.1 port {2200+i} ssh2\n' for i in range(5)).encode()
            evidence=register_evidence(db,inv,title='Synthetic auth',description='',evidence_type=EvidenceType.LOG,source='Synthetic',acquired_at=None,filename='auth.log',content_type='text/plain',stream=io.BytesIO(data),actor=actor)
            verify_evidence(db,inv,evidence,actor)
            profile=create_profile(db,inv,ProfileCreate(name='Linux',configuration={'adapter':'linux_auth','format':'syslog'}),actor)
            ingestion=ingest(db,inv,evidence.id,profile.id,actor)
            uid,inv_id,ingestion_id=actor.id,inv.id,ingestion.id
        barrier=Barrier(2)
        def select_inputs():
            with Session(engine) as db:
                actor,inv=db.get(User,uid),db.get(Investigation,inv_id)
                barrier.wait(timeout=15)
                return create_set(db,inv,EventSetCreate(name='Concurrent selection',run_ids=[ingestion_id]),actor).id
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(select_inputs) for _ in range(2)]
            set_ids=[f.result(timeout=60) for f in futures]
        assert set_ids[0]==set_ids[1]
        barrier=Barrier(2)
        def detect():
            with Session(engine) as db:
                actor,inv=db.get(User,uid),db.get(Investigation,inv_id)
                barrier.wait(timeout=15)
                run=execute(db,inv,DetectionCreate(event_set_id=set_ids[0]),actor)
                assert run.status=='completed',run.error
                return run.id
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(detect) for _ in range(2)]
            run_ids=[f.result(timeout=60) for f in futures]
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(InvestigationEventSet).where(InvestigationEventSet.investigation_id==inv_id))==1
            findings=list(db.scalars(select(Finding).where(Finding.investigation_id==inv_id)))
            assert len(findings)==1
            assert db.scalar(select(func.count()).select_from(DetectionRunFinding).where(DetectionRunFinding.run_id.in_(run_ids)))==2
            findings[0].status='accepted';db.commit()
            actor,inv=db.get(User,uid),db.get(Investigation,inv_id)
            assert execute(db,inv,DetectionCreate(event_set_id=set_ids[0]),actor).status=='completed'
            assert db.get(Finding,findings[0].id).status=='accepted'
            assert db.scalar(select(func.count()).select_from(AuthenticationDetectionRun).where(AuthenticationDetectionRun.investigation_id==inv_id))==3
            # Exercise real JSON-bearing PostgreSQL queries, not SQLite DISTINCT semantics.
            from app.modules.detections.router import findings as query_findings, history
            page=query_findings(inv_id,event_set_id=set_ids[0],run_id=None,limit=50,offset=0,user=actor,db=db)
            assert page['total']==1 and page['items'][0].support_current
            assert history(inv_id,findings[0].id,user=actor,db=db)==[]
            finding_id=findings[0].id
        barrier=Barrier(2)
        def review(state):
            from app.modules.intelligence.reasoning import review_finding
            with Session(engine) as db:
                actor,inv,finding=db.get(User,uid),db.get(Investigation,inv_id),db.get(Finding,finding_id)
                barrier.wait(timeout=15)
                review_finding(db,inv,finding,state,'Synthetic concurrent decision',actor)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(review,state) for state in ('accepted','rejected')]
            for future in futures: future.result(timeout=60)
        with Session(engine) as db:
            from app.modules.audit.models import AuditEvent
            events=list(db.scalars(select(AuditEvent).where(AuditEvent.resource_id==str(inv_id),
                AuditEvent.event_metadata['finding_id'].as_integer()==finding_id).order_by(AuditEvent.id)))
            assert len(events)==2
            assert events[0].event_metadata['previous_decision']['status']=='accepted'
            assert events[1].event_metadata['previous_decision']['status']==events[0].event_metadata['decision']['status']
            assert db.get(Finding,finding_id).status==events[1].event_metadata['decision']['status']
    finally:
        engine.dispose()

def test_postgres_parallel_event_ingestion(tmp_path, monkeypatch):
    url=os.getenv('M1_POSTGRES_TEST_URL')
    if not url:
        pytest.skip('Disposable PostgreSQL CI database not configured.')
    parsed=make_url(url)
    assert parsed.database=='provena_ci' and parsed.host in {'127.0.0.1','localhost'}
    from app.modules.events.service import create_profile, ingest
    from app.modules.events.schemas import ProfileCreate
    from app.modules.events.models import SecurityEvent, EventRunMember
    from app.modules.evidence.service import verify_evidence
    from app.modules.evidence.models import Evidence
    monkeypatch.setattr(settings,'evidence_storage_backend','local')
    monkeypatch.setattr(settings,'evidence_storage_root',str(tmp_path))
    engine=create_engine(url)
    suffix=uuid.uuid4().hex[:12]
    try:
        with Session(engine) as db:
            actor=User(username=f'event_{suffix}',email=f'{suffix}@example.test',full_name='Synthetic CI',role='admin',password_hash='unused')
            db.add(actor);db.flush()
            workspace=Workspace(name='Synthetic Events',slug=f'event-{suffix}',created_by_id=actor.id)
            db.add(workspace);db.flush()
            inv=Investigation(title='Synthetic events',case_number=f'EV-{suffix}',workspace_id=workspace.id,created_by_id=actor.id,lead_investigator_id=actor.id)
            db.add(inv);db.commit()
            data=b'2026-11-05T12:00:00Z host sshd[123]: Failed password for mira from 192.0.2.1 port 2222 ssh2\n'
            evidence=register_evidence(db,inv,title='Synthetic auth',description='',evidence_type=EvidenceType.LOG,source='Synthetic',acquired_at=None,filename='auth.log',content_type='text/plain',stream=io.BytesIO(data+data),actor=actor)
            verify_evidence(db,inv,evidence,actor)
            profile=create_profile(db,inv,ProfileCreate(name='Linux',configuration={'adapter':'linux_auth','format':'syslog'}),actor)
            uid,inv_id,eid,pid=actor.id,inv.id,evidence.id,profile.id
        barrier=Barrier(2)
        def attempt():
            with Session(engine) as db:
                actor,inv=db.get(User,uid),db.get(Investigation,inv_id)
                barrier.wait(timeout=15)
                run=ingest(db,inv,eid,pid,actor)
                assert run.status=='completed',run.error
                return run.id
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(attempt) for _ in range(2)]
            runs=[future.result(timeout=60) for future in futures]
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(SecurityEvent).where(SecurityEvent.investigation_id==inv_id))==2
            for run_id in runs:
                assert db.scalar(select(func.count()).select_from(EventRunMember).where(EventRunMember.run_id==run_id))==2
    finally:
        engine.dispose()


@pytest.mark.parametrize('baseline',['294d21d0205e','53d6b8a0e88b'])
def test_postgres_m3_upgrade_preserves_investigation_history(tmp_path, monkeypatch, baseline):
    """Fresh isolated M3/M4 schemas upgrade without rewriting populated history."""
    import hashlib
    import json
    import subprocess
    import sys
    from pathlib import Path
    from app.modules.events.service import create_profile, ingest
    from app.modules.events.schemas import ProfileCreate
    from app.modules.events.models import SecurityEvent, EventRunMember
    from app.modules.evidence.service import verify_evidence
    from app.modules.intelligence.models import Finding, Report
    url=os.getenv('M1_POSTGRES_TEST_URL')
    if not url:
        pytest.skip('Disposable PostgreSQL CI database not configured.')
    parsed=make_url(url)
    assert parsed.database=='provena_ci' and parsed.host in {'127.0.0.1','localhost'}
    schema='m4_upgrade_'+uuid.uuid4().hex
    control=create_engine(url)
    with control.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    control.dispose()
    isolated=parsed.update_query_dict({'options':f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    environment={**os.environ,'DATABASE_URL':isolated,'APP_ENV':'test'}
    def migrate(*args):
        result=subprocess.run([sys.executable,'-m','alembic',*args],env=environment,
            cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=120)
        assert result.returncode==0,result.stdout+result.stderr
    migrate('upgrade',baseline)
    monkeypatch.setattr(settings,'evidence_storage_backend','local')
    monkeypatch.setattr(settings,'evidence_storage_root',str(tmp_path))
    engine=create_engine(isolated)
    try:
        with Session(engine) as db:
            actor=User(username='migration_synthetic',email='migration@example.test',password_hash='unused',role='admin')
            db.add(actor);db.flush()
            workspace=Workspace(name='Historical',slug='historical',created_by_id=actor.id)
            db.add(workspace);db.flush()
            inv=Investigation(title='M3 preserved',case_number='M3-UPGRADE',workspace_id=workspace.id,created_by_id=actor.id,lead_investigator_id=actor.id)
            db.add(inv);db.commit()
            evidence=register_evidence(db,inv,title='Original synthetic',description='',evidence_type=EvidenceType.LOG,source='Synthetic',acquired_at=None,filename='auth.log',content_type='text/plain',stream=io.BytesIO(b'2026-11-05T12:00:00Z host sshd[1]: Failed password for mira from 192.0.2.1 port 2200 ssh2\n'),actor=actor)
            verify_evidence(db,inv,evidence,actor)
            profile=create_profile(db,inv,ProfileCreate(name='M3 original',configuration={'adapter':'linux_auth','format':'syslog'}),actor)
            ingestion=ingest(db,inv,evidence.id,profile.id,actor)
            event=db.scalar(select(SecurityEvent))
            original_event_key=event.semantic_key
            for index,state in enumerate(('accepted','rejected')):
                db.add(Finding(investigation_id=inv.id,rule_id='m2.historical',rule_version='2',inputs_key=str(index)*64,
                    title='Historical finding',summary='Synthetic preserved history',severity='low',confidence=10,factors=[],
                    evidence_ids=[evidence.id],artifact_ids=[],correlation_ids=[],recommendations=[],status=state))
            content={'generator':'grounded-report-v4','synthetic':'Historical immutable snapshot'}
            report_hash=hashlib.sha256(json.dumps(content,sort_keys=True).encode()).hexdigest()
            db.add(Report(investigation_id=inv.id,report_number=1,content=content,content_sha256=report_hash,generated_by_id=actor.id))
            db.commit()
            inv_id,eid,run_id=inv.id,evidence.id,ingestion.id
        migrate('upgrade','head')
        migrate('check')
        with Session(engine) as db:
            assert db.scalar(select(Report.content_sha256))==report_hash
            assert set(db.scalars(select(Finding.status)))=={'accepted','rejected'}
            assert db.scalar(select(SecurityEvent.semantic_key))==original_event_key
            assert db.scalar(select(EventRunMember.run_id))==run_id
            assert db.get(Evidence,eid).integrity_status=='verified'
            from app.modules.detections.models import InvestigationEventSet
            assert db.scalar(select(func.count()).select_from(InvestigationEventSet))==0
    finally:
        engine.dispose()
