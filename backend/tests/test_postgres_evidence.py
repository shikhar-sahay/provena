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
