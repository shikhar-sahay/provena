"""Deterministic development seed for the synthetic Provena Demo Workspace.

All records are created through application services. The seed is additive,
idempotent, offline, and disabled in production.
"""

import io
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.modules.evidence import service as ev_service
from app.modules.evidence import storage
from app.modules.evidence.models import CustodyAction, CustodyEvent, Evidence, EvidenceType, IntegrityStatus
from app.modules.evidence.schemas import CustodyCreate
from app.modules.intelligence import reasoning
from app.modules.intelligence import service as intelligence_service
from app.modules.intelligence.models import AnalysisRun, FindingStatus, InvestigationNote, Report
from app.modules.investigations import service as inv_service
from app.modules.investigations.models import Investigation, InvestigationPriority, InvestigationStatus
from app.modules.investigations.schemas import InvestigationCreate, InvestigationUpdate, MemberAdd
from app.modules.users.models import User
from app.modules.users.service import get_by_login

DEMO_TITLE = "Suspected Internal Data Exfiltration"
REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = REPO_ROOT / "sample-data"


@dataclass(frozen=True)
class EvidenceSeed:
    filename: str
    title: str
    content: str | None
    evidence_type: EvidenceType = EvidenceType.LOG
    state: str = "verified"


@dataclass(frozen=True)
class CaseSeed:
    title: str
    description: str
    priority: InvestigationPriority
    status: InvestigationStatus
    evidence: tuple[EvidenceSeed, ...]
    analysis: str = "none"
    report: bool = False


def item(filename: str, title: str, content: str, *, state: str = "verified", evidence_type: EvidenceType = EvidenceType.LOG) -> EvidenceSeed:
    return EvidenceSeed(filename, title, content, evidence_type, state)


HERO_EXTRA = (
    item("email_activity.json", "Email activity export", '[{"timestamp":"2026-01-13T02:31:00Z","user":"m.okafor","email":"m.okafor@example.com","host":"ws-114","url":"https://archive-mirror.example.net/upload","attachment":"vendor-pricing-2026.xlsx"}]', evidence_type=EvidenceType.EMAIL),
    item("workstation_events.log", "Workstation event log", "2026-01-13 02:15:01 user=m.okafor host=ws-114 process=explorer.exe\n2026-01-13 02:16:10 user=m.okafor host=ws-114 usb serial=4C5300FICTIONAL01\n2026-01-13 02:46:02 user=m.okafor host=ws-114 process=curl.exe dst=203.0.113.44"),
    item("investigation_note.txt", "New investigator intake note", "Synthetic intake note awaiting independent integrity verification. Account m.okafor and host ws-114 require review.", state="not_verified", evidence_type=EvidenceType.DOCUMENT),
    item("transfer_manifest.csv", "Transfer manifest with integrity mismatch", "timestamp,user,host,file,destination\n2026-01-13T02:45:40Z,m.okafor,ws-114,customer-list-2026.csv,203.0.113.44\n", state="mismatch", evidence_type=EvidenceType.DOCUMENT),
)

CASES = (
    CaseSeed("Unauthorized Privileged Account Access", "Synthetic review of unusual administrator authentication and workstation activity.", InvestigationPriority.HIGH, InvestigationStatus.IN_PROGRESS, (
        item("admin_auth.log", "Privileged authentication log", "2026-02-03 01:14:00 accepted login user=s.rahman host=admin-ws-22 src=198.51.100.24\n2026-02-03 01:16:00 sudo user=s.rahman host=admin-ws-22 process=powershell.exe"),
        item("vpn_access.log", "VPN access log", "2026-02-03 01:12:00 user=s.rahman host=admin-ws-22 src=198.51.100.24 port=443"),
        item("directory_audit.csv", "Directory service audit", "timestamp,user,host,action\n2026-02-03T01:18:00Z,s.rahman,admin-ws-22,group-read\n", evidence_type=EvidenceType.DOCUMENT),
        item("endpoint_processes.json", "Endpoint process export", '[{"timestamp":"2026-02-03T01:16:00Z","user":"s.rahman","host":"admin-ws-22","process":"powershell.exe"}]', evidence_type=EvidenceType.DOCUMENT),
        item("admin_followup.txt", "Administrator follow-up note", "Awaiting verification for synthetic follow-up from s.rahman.", state="not_verified", evidence_type=EvidenceType.DOCUMENT),
    ), analysis="verified"),
    CaseSeed("Phishing Email Investigation", "Synthetic email triage covering headers, URLs, domains, and an attachment name.", InvestigationPriority.MEDIUM, InvestigationStatus.OPEN, (
        item("message_headers.txt", "Suspicious message headers", "2026-03-08 09:22:00 from=alerts@billing-example.net to=n.iyer@example.com host=mail-ws-09 src=203.0.113.81", evidence_type=EvidenceType.EMAIL),
        item("mail_gateway.log", "Mail gateway event", "2026-03-08 09:22:02 recipient=n.iyer@example.com url=https://billing-example.net/review attachment=invoice-review.zip", evidence_type=EvidenceType.EMAIL),
        item("attachment_inventory.csv", "Attachment inventory", "timestamp,user,file,hash\n2026-03-08T09:23:00Z,n.iyer,invoice-review.zip,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n", state="not_verified", evidence_type=EvidenceType.ARCHIVE),
        item("user_statement.txt", "User statement", "Synthetic statement from n.iyer about billing-example.net.", state="not_verified", evidence_type=EvidenceType.DOCUMENT),
    ), analysis="verified"),
    CaseSeed("Removable Media Policy Violation", "Synthetic removable-media review with trusted, pending, and mismatched evidence.", InvestigationPriority.MEDIUM, InvestigationStatus.OPEN, (
        item("usb_policy.log", "USB policy event", "2026-04-11 15:04:00 user=p.kapoor host=ws-318 usb serial=DEMO-USB-318"),
        item("device_inventory.csv", "Device inventory", "timestamp,user,host,device\n2026-04-11T15:04:00Z,p.kapoor,ws-318,DEMO-USB-318\n", state="not_verified", evidence_type=EvidenceType.DEVICE),
        item("file_copy.log", "File copy event", "2026-04-11 15:06:00 user=p.kapoor host=ws-318 copied policy-draft.docx to E:", state="mismatch"),
    ), analysis="all"),
    CaseSeed("Suspicious External Network Activity", "Closed synthetic case documenting reviewed outbound activity and final reporting.", InvestigationPriority.LOW, InvestigationStatus.CLOSED, (
        item("historical_auth.log", "Historical authentication log", "2026-05-02 18:01:00 user=l.chen host=ws-404 src=192.0.2.44"),
        item("historical_file.log", "Historical file access", "2026-05-02 18:04:00 user=l.chen host=ws-404 read quarterly-summary.csv"),
        item("historical_network.log", "Historical network log", "2026-05-02 18:06:00 user=l.chen host=ws-404 https upload quarterly-summary.csv to archive.example.org dst=203.0.113.90"),
        item("historical_review.txt", "Historical review note", "2026-05-02 18:10:00 user=l.chen host=ws-404 review completed", evidence_type=EvidenceType.DOCUMENT),
    ), analysis="verified", report=True),
)


def find_demo(db: Session) -> Investigation | None:
    return db.execute(select(Investigation).where(Investigation.title == DEMO_TITLE)).scalar_one_or_none()


def _users(db: Session) -> tuple[User, User, User]:
    values = tuple(get_by_login(db, name) for name in ("investigator", "analyst", "custodian"))
    if any(value is None for value in values):
        raise SystemExit("Missing demo users. Run python -m app.seed first.")
    investigator, analyst, custodian = values
    assert investigator and analyst and custodian
    return investigator, analyst, custodian


def _ensure_evidence(db: Session, inv: Investigation, specs: tuple[EvidenceSeed, ...], actor: User, sample_dir: Path) -> list[Evidence]:
    existing = {entry.original_filename: entry for entry in ev_service.list_evidence(db, inv)}
    result = []
    for spec in specs:
        evidence = existing.get(spec.filename)
        if evidence is None:
            stream = io.BytesIO(spec.content.encode()) if spec.content is not None else open(sample_dir / spec.filename, "rb")
            try:
                evidence = ev_service.register_evidence(db, inv, title=spec.title, description="Synthetic demonstration evidence.", evidence_type=spec.evidence_type, source="Provena synthetic demo source", acquired_at=None, filename=spec.filename, content_type="application/json" if spec.filename.endswith(".json") else "text/csv" if spec.filename.endswith(".csv") else "application/pdf" if spec.filename.endswith(".pdf") else "text/plain", stream=stream, actor=actor)
            finally:
                stream.close()
        if spec.state == "verified" and evidence.integrity_status == IntegrityStatus.NOT_VERIFIED.value:
            ev_service.verify_evidence(db, inv, evidence, actor)
        elif spec.state == "mismatch" and evidence.integrity_status == IntegrityStatus.NOT_VERIFIED.value:
            storage.replace_for_demo(evidence.storage_key, b"Synthetic altered bytes for integrity mismatch demonstration.\n")
            ev_service.verify_evidence(db, inv, evidence, actor)
        result.append(evidence)
    return result


def _ensure_analysis(db: Session, inv: Investigation, mode: str, analyst: User) -> None:
    if mode == "none" or db.scalar(select(func.count(AnalysisRun.id)).where(AnalysisRun.investigation_id == inv.id)):
        return
    evidence = ev_service.list_evidence(db, inv)
    selected = evidence if mode == "all" else [entry for entry in evidence if entry.integrity_status == IntegrityStatus.VERIFIED.value]
    if selected:
        run = intelligence_service.start_run(db, inv, [entry.id for entry in selected], analyst)
        reasoning.generate_findings(db, inv, analyst, run.id)


def _ensure_case(db: Session, spec: CaseSeed, investigator: User, analyst: User, custodian: User, sample_dir: Path) -> Investigation:
    inv = db.execute(select(Investigation).where(Investigation.title == spec.title)).scalar_one_or_none()
    if inv is None:
        inv = inv_service.create_investigation(db, InvestigationCreate(title=spec.title, description=spec.description, priority=spec.priority), investigator)
    assert inv is not None
    for member in (analyst, custodian):
        if not inv_service.is_member(db, inv.id, member.id):
            inv_service.add_member(db, inv, MemberAdd(user_id=member.id), investigator)
    _ensure_evidence(db, inv, spec.evidence, investigator, sample_dir)
    _ensure_analysis(db, inv, spec.analysis, analyst)
    if spec.report and db.scalar(select(func.count(Report.id)).where(Report.investigation_id == inv.id)) == 0:
        for finding in reasoning.list_findings(db, inv):
            if finding.status == FindingStatus.PENDING_REVIEW.value:
                reasoning.review_finding(db, inv, finding, FindingStatus.ACCEPTED.value, "Accepted for the synthetic historical case.", investigator)
        reasoning.generate_report(db, inv, investigator, force_deterministic=True)
    if inv.status != spec.status.value:
        inv = inv_service.update_investigation(db, inv, InvestigationUpdate(status=spec.status), investigator)
    assert inv is not None
    return inv


def _hero_spec() -> CaseSeed:
    base = (
        EvidenceSeed("authentication.log", "Authentication log (Jan 12-14)", None),
        EvidenceSeed("usb_activity.log", "USB activity log (Jan 12-14)", None),
        EvidenceSeed("file_access.log", "File access log (Jan 12-14)", None),
        EvidenceSeed("network_activity.log", "Network activity log (Jan 12-14)", None, EvidenceType.NETWORK),
        EvidenceSeed("employee-access-report.pdf", "Employee access review (synthetic PDF)", None, EvidenceType.DOCUMENT),
    )
    return CaseSeed(DEMO_TITLE, "Fictional scenario for walkthroughs: unusual logins, removable media, restricted file access, and outbound activity attributed to one workstation. All data is synthetic.", InvestigationPriority.HIGH, InvestigationStatus.UNDER_REVIEW, base + HERO_EXTRA, analysis="verified")


def _ensure_custody(db: Session, inv: Investigation, evidence: Evidence, investigator: User, analyst: User, custodian: User) -> None:
    actions = set(db.scalars(select(CustodyEvent.action).where(CustodyEvent.evidence_id == evidence.id)).all())
    for action, target, note in (
        (CustodyAction.RECEIVED, custodian, "Custodian received the synthetic evidence item."),
        (CustodyAction.RELEASED_FOR_ANALYSIS, analyst, "Released for deterministic analysis."),
        (CustodyAction.RETURNED_TO_CUSTODY, custodian, "Returned to controlled custody after analysis."),
    ):
        if action.value not in actions:
            ev_service.record_custody(db, inv, evidence, CustodyCreate(action=action, to_user_id=target.id, notes=note), investigator)


def _prepare_hero(db: Session, investigator: User, analyst: User, custodian: User, sample_dir: Path) -> Investigation:
    inv = _ensure_case(db, _hero_spec(), investigator, analyst, custodian, sample_dir)
    runs = list(db.scalars(select(AnalysisRun).where(AnalysisRun.investigation_id == inv.id)).all())
    evidence = ev_service.list_evidence(db, inv)
    if len(runs) == 1:
        blocked = [entry.id for entry in evidence if entry.integrity_status != IntegrityStatus.VERIFIED.value]
        if blocked:
            intelligence_service.start_run(db, inv, blocked, analyst)
    findings = reasoning.list_findings(db, inv)
    pending = [entry for entry in findings if entry.status == FindingStatus.PENDING_REVIEW.value]
    if pending and not any(entry.status == FindingStatus.ACCEPTED.value for entry in findings):
        reasoning.review_finding(db, inv, pending[0], FindingStatus.ACCEPTED.value, "Accepted after reviewing the recorded synthetic provenance.", investigator)
    findings = reasoning.list_findings(db, inv)
    pending = [entry for entry in findings if entry.status == FindingStatus.PENDING_REVIEW.value]
    if pending and not any(entry.status == FindingStatus.REJECTED.value for entry in findings):
        reasoning.review_finding(db, inv, pending[0], FindingStatus.REJECTED.value, "Rejected because recurrence alone is insufficient.", investigator)
    if db.scalar(select(func.count(InvestigationNote.id)).where(InvestigationNote.investigation_id == inv.id)) == 0:
        reasoning.create_note(db, inv, "Synthetic review note: verify authorization for the removable-media session and external destination before drawing conclusions.", investigator)
    _ensure_custody(db, inv, next(entry for entry in evidence if entry.original_filename == "authentication.log"), investigator, analyst, custodian)
    if db.scalar(select(func.count(Report.id)).where(Report.investigation_id == inv.id)) == 0:
        reasoning.generate_report(db, inv, investigator, force_deterministic=True)
    return inv


def run_demo(db: Session, sample_dir: Path = SAMPLE_DIR) -> Investigation:
    investigator, analyst, custodian = _users(db)
    hero = _prepare_hero(db, investigator, analyst, custodian, sample_dir)
    for spec in CASES:
        _ensure_case(db, spec, investigator, analyst, custodian, sample_dir)
    print(f"demo ready: {hero.case_number} and {len(CASES)} supporting investigations")
    return hero


def main() -> None:
    if settings.app_env == "production":
        raise SystemExit("Refusing to seed demo data in production.")
    if SessionLocal is None or engine is None:
        raise SystemExit("DATABASE_URL is not configured.")
    with SessionLocal() as db:
        run_demo(db)


if __name__ == "__main__":
    main()
