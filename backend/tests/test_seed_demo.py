"""Demo seed tests: rich synthetic state built through real services."""

from sqlalchemy import func, select

from app.modules.audit.models import AuditEvent
from app.modules.evidence.models import CustodyEvent, Evidence, EvidenceVerification
from app.modules.intelligence.models import AnalysisRun, Artifact, Correlation, Finding, Report
from app.modules.investigations.models import Investigation
from app.modules.users.models import Role
from app.seed_demo import DEMO_TITLE, SAMPLE_DIR, find_demo, run_demo
from tests.conftest import make_user


def seed_roles(db_session):
    make_user(db_session, "investigator", Role.INVESTIGATOR)
    make_user(db_session, "analyst", Role.FORENSIC_ANALYST)
    make_user(db_session, "custodian", Role.EVIDENCE_CUSTODIAN)


def counts(db_session):
    models = (Investigation, Evidence, EvidenceVerification, CustodyEvent, AnalysisRun, Artifact, Correlation, Finding, Report, AuditEvent)
    return tuple(db_session.scalar(select(func.count()).select_from(model)) for model in models)


def test_demo_seed_builds_real_pipeline_state(db_session, storage_dir):
    seed_roles(db_session)
    hero = run_demo(db_session, SAMPLE_DIR)

    assert hero.title == DEMO_TITLE
    assert hero.status == "under_review"
    investigations = db_session.scalars(select(Investigation).order_by(Investigation.case_number)).all()
    assert len(investigations) == 5
    assert {entry.status for entry in investigations} == {"open", "in_progress", "under_review", "closed"}

    hero_evidence = db_session.scalars(select(Evidence).where(Evidence.investigation_id == hero.id)).all()
    assert len(hero_evidence) == 9
    assert {entry.integrity_status for entry in hero_evidence} == {"verified", "not_verified", "mismatch"}
    assert db_session.scalar(select(func.count(AnalysisRun.id)).where(AnalysisRun.investigation_id == hero.id)) == 2
    assert db_session.scalar(select(func.count(Artifact.id)).where(Artifact.investigation_id == hero.id)) > 20
    assert db_session.scalar(select(func.count(Correlation.id)).where(Correlation.investigation_id == hero.id)) >= 3
    findings = db_session.scalars(select(Finding).where(Finding.investigation_id == hero.id)).all()
    assert findings
    assert "accepted" in {entry.status for entry in findings}
    assert db_session.scalar(select(func.count(Report.id)).where(Report.investigation_id == hero.id)) == 1

    actions = set(db_session.scalars(select(AuditEvent.action)).all())
    for expected in ("INVESTIGATION_CREATED", "EVIDENCE_REGISTERED", "EVIDENCE_VERIFIED", "EVIDENCE_INTEGRITY_MISMATCH", "AI_ANALYSIS_COMPLETED", "AI_FINDING_GENERATED", "REPORT_GENERATED"):
        assert expected in actions


def test_demo_seed_is_idempotent_across_all_generated_state(db_session, storage_dir):
    seed_roles(db_session)
    first = run_demo(db_session, SAMPLE_DIR)
    before = counts(db_session)
    second = run_demo(db_session, SAMPLE_DIR)

    assert first.id == second.id
    assert find_demo(db_session) is not None
    assert counts(db_session) == before
