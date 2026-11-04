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
    finally:
        engine.dispose()
