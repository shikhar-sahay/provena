"""Development demo seed: a realistic synthetic investigation. Idempotent.

Usage (from backend/, after the user seed):
    python -m app.seed_demo

Builds the "Suspected Internal Data Exfiltration" scenario from
sample-data/*.log using only real application services, so every record,
digest, custody event, verification, and audit entry is genuine. No fake AI
output is created. Safe to rerun: an existing demo investigation is detected
by title and left untouched. Refuses to run when APP_ENV=production.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.modules.evidence import service as ev_service
from app.modules.evidence.models import CustodyAction, EvidenceType
from app.modules.evidence.schemas import CustodyCreate
from app.modules.investigations import service as inv_service
from app.modules.investigations.models import Investigation, InvestigationPriority, InvestigationStatus
from app.modules.investigations.schemas import InvestigationCreate, InvestigationUpdate, MemberAdd
from app.modules.users.service import get_by_login

DEMO_TITLE = "Suspected Internal Data Exfiltration"
REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = REPO_ROOT / "sample-data"

DEMO_FILES = [
    (
        "authentication.log",
        "Authentication log (Jan 12-14)",
        "Odd-hour logins and failures for m.okafor from an unfamiliar address.",
        "SIEM export, identity gateway",
        EvidenceType.LOG,
    ),
    (
        "usb_activity.log",
        "USB activity log (Jan 12-14)",
        "USB insertions on ws-114 coinciding with the suspect sessions.",
        "Endpoint agent, workstation ws-114",
        EvidenceType.LOG,
    ),
    (
        "file_access.log",
        "File access log (Jan 12-14)",
        "Reads and copies of restricted files to removable media.",
        "File server audit share",
        EvidenceType.LOG,
    ),
    (
        "network_activity.log",
        "Network activity log (Jan 12-14)",
        "Large outbound uploads to an external destination.",
        "Perimeter firewall export",
        EvidenceType.LOG,
    ),
    (
        "employee-access-report.pdf",
        "Employee access review (synthetic PDF)",
        "Machine-readable access review naming the same account, host, "
        "device, files, and destinations as the logs.",
        "Fictional quarterly access review",
        EvidenceType.DOCUMENT,
    ),
]


def find_demo(db: Session) -> Investigation | None:
    stmt = select(Investigation).where(Investigation.title == DEMO_TITLE)
    return db.execute(stmt).scalar_one_or_none()


def run_demo(db: Session, sample_dir: Path = SAMPLE_DIR) -> Investigation:
    """Create the demo investigation and its evidence. Returns existing on rerun."""
    existing = find_demo(db)
    if existing is not None:
        print(f"exists: demo investigation {existing.case_number}")
        return existing

    investigator = get_by_login(db, "investigator")
    analyst = get_by_login(db, "analyst")
    custodian = get_by_login(db, "custodian")
    missing = [name for user, name in
               [(investigator, "investigator"), (analyst, "analyst"), (custodian, "custodian")]
               if user is None]
    if missing:
        raise SystemExit(f"Missing seed users: {', '.join(missing)}. Run python -m app.seed first.")
    assert investigator is not None and analyst is not None and custodian is not None

    inv = inv_service.create_investigation(
        db,
        InvestigationCreate(
            title=DEMO_TITLE,
            description=(
                "Fictional scenario for walkthroughs: unusual logins, USB activity, "
                "restricted file copies, and outbound uploads attributed to one "
                "workstation over three days. All data is synthetic."
            ),
            priority=InvestigationPriority.HIGH,
        ),
        investigator,
    )
    assert inv is not None
    for member, role in ((analyst, "member"), (custodian, "member")):
        inv = inv_service.add_member(db, inv, MemberAdd(user_id=member.id), investigator)
    assert inv is not None

    items = []
    for filename, title, description, source, evidence_type in DEMO_FILES:
        path = sample_dir / filename
        if not path.exists():
            raise SystemExit(f"Sample file missing: {path}")
        with open(path, "rb") as handle:
            item = ev_service.register_evidence(
                db,
                inv,
                title=title,
                description=description,
                evidence_type=evidence_type,
                source=source,
                acquired_at=None,
                filename=filename,
                content_type="text/plain" if filename.endswith(".log") else "application/pdf",
                stream=handle,
                actor=investigator,
            )
        items.append(item)
        print(f"registered: {item.evidence_number} {filename} sha256={item.sha256[:16]}...")

    for item in items:
        verification = ev_service.verify_evidence(db, inv, item, investigator)
        print(f"verified: {item.evidence_number} -> {verification.result}")

    first = items[0]
    ev_service.record_custody(
        db,
        inv,
        first,
        CustodyCreate(
            action=CustodyAction.TRANSFERRED,
            to_user_id=custodian.id,
            notes="Demo handoff: custodian takes holding custody of the auth log.",
        ),
        investigator,
    )
    print(f"custody: {first.evidence_number} transferred to custodian")

    inv = inv_service.update_investigation(
        db, inv, InvestigationUpdate(status=InvestigationStatus.IN_PROGRESS), investigator
    )
    assert inv is not None
    print(f"demo ready: {inv.case_number} ({inv.status})")
    return inv


def main() -> None:
    if settings.app_env == "production":
        raise SystemExit("Refusing to seed demo data in production.")
    if SessionLocal is None or engine is None:
        raise SystemExit("DATABASE_URL is not configured.")
    with SessionLocal() as db:
        run_demo(db)


if __name__ == "__main__":
    main()
