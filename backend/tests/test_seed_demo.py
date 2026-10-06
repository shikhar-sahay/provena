"""Demo seed tests: realistic synthetic investigation built only from real services."""

from pathlib import Path

from sqlalchemy import func, select

from app.modules.audit.models import AuditEvent
from app.modules.evidence.models import CustodyEvent, Evidence, EvidenceVerification
from app.modules.investigations.models import Investigation
from app.seed_demo import DEMO_FILES, DEMO_TITLE, find_demo, run_demo
from tests.conftest import make_user
from app.modules.users.models import Role


def write_sample_files(sample_dir: Path):
    sample_dir.mkdir(parents=True, exist_ok=True)
    for filename, *_ in DEMO_FILES:
        (sample_dir / filename).write_text(f"synthetic {filename}\nline two\n")


def seed_roles(db_session):
    make_user(db_session, "investigator", Role.INVESTIGATOR)
    make_user(db_session, "analyst", Role.FORENSIC_ANALYST)
    make_user(db_session, "custodian", Role.EVIDENCE_CUSTODIAN)


def test_demo_seed_builds_genuine_records(db_session, storage_dir, tmp_path):
    seed_roles(db_session)
    sample_dir = tmp_path / "sample-data"
    write_sample_files(sample_dir)

    inv = run_demo(db_session, sample_dir)

    assert inv.title == DEMO_TITLE
    assert inv.status == "in_progress"
    items = db_session.execute(select(Evidence)).scalars().all()
    assert len(items) == len(DEMO_FILES)
    assert [e.evidence_number for e in items] == ["E-001", "E-002", "E-003", "E-004"]
    assert all(e.integrity_status == "verified" for e in items)
    assert db_session.execute(select(func.count()).select_from(EvidenceVerification)).scalar_one() == 4
    custody = db_session.execute(select(CustodyEvent)).scalars().all()
    assert len(custody) == len(DEMO_FILES) + 1
    assert any(c.action == "transferred" for c in custody)
    actions = set(db_session.execute(select(AuditEvent.action)).scalars().all())
    for expected in ("INVESTIGATION_CREATED", "INVESTIGATION_MEMBER_ADDED",
                     "EVIDENCE_REGISTERED", "EVIDENCE_VERIFIED", "CUSTODY_TRANSFERRED",
                     "INVESTIGATION_STATUS_CHANGED"):
        assert expected in actions
    # No fake AI output anywhere in the audit trail.
    assert not {a for a in actions if a.startswith("AI_") or "REPORT" in a}


def test_demo_seed_is_idempotent(db_session, storage_dir, tmp_path):
    seed_roles(db_session)
    sample_dir = tmp_path / "sample-data"
    write_sample_files(sample_dir)

    first = run_demo(db_session, sample_dir)
    second = run_demo(db_session, sample_dir)

    assert first.id == second.id
    assert find_demo(db_session) is not None
    assert db_session.execute(select(func.count()).select_from(Investigation)).scalar_one() == 1
    assert db_session.execute(select(func.count()).select_from(Evidence)).scalar_one() == len(DEMO_FILES)
