"""Dashboard summary: counts and recent activity scoped to the current user.

Admins see the whole workspace; everyone else sees only investigations they
are members of. No fabricated analytics: each figure is a direct count over
records the caller is authorized to see.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.audit.service import ResourceTypes
from app.modules.dashboard.schemas import ActivityItem, DashboardSummary
from app.modules.evidence.models import Evidence, IntegrityStatus
from app.modules.investigations import service as inv_service
from app.modules.investigations.models import InvestigationStatus
from app.modules.users.models import User

RECENT_LIMIT = 15
OPEN_STATUSES = {
    InvestigationStatus.OPEN.value,
    InvestigationStatus.IN_PROGRESS.value,
    InvestigationStatus.UNDER_REVIEW.value,
}


def get_summary(db: Session, user: User) -> DashboardSummary:
    investigations = inv_service.list_accessible(db, user)
    ids = [inv.id for inv in investigations]
    by_id = {inv.id: inv for inv in investigations}

    by_status: dict[str, int] = {}
    for inv in investigations:
        by_status[inv.status] = by_status.get(inv.status, 0) + 1

    evidence_total = 0
    integrity_issues = 0
    if ids:
        evidence_total = db.execute(
            select(func.count())
            .select_from(Evidence)
            .where(Evidence.investigation_id.in_(ids))
        ).scalar_one()
        integrity_issues = db.execute(
            select(func.count())
            .select_from(Evidence)
            .where(
                Evidence.investigation_id.in_(ids),
                Evidence.integrity_status.in_(
                    [IntegrityStatus.MISMATCH.value, IntegrityStatus.UNAVAILABLE.value]
                ),
            )
        ).scalar_one()

    recent: list[ActivityItem] = []
    if ids:
        events = (
            db.execute(
                select(AuditEvent)
                .where(
                    AuditEvent.resource_type == ResourceTypes.INVESTIGATION,
                    AuditEvent.resource_id.in_([str(i) for i in ids]),
                )
                .order_by(AuditEvent.id.desc())
                .limit(RECENT_LIMIT)
            )
        ).scalars().all()
        actor_ids = {e.actor_id for e in events if e.actor_id}
        actors = (
            {u.id: u.username for u in db.execute(select(User).where(User.id.in_(actor_ids))).scalars().all()}
            if actor_ids
            else {}
        )
        for event in events:
            inv_id = int(event.resource_id) if event.resource_id else 0
            inv = by_id.get(inv_id)
            if inv is None:
                continue
            meta = event.event_metadata or {}
            number = meta.get("evidence_number")
            recent.append(
                ActivityItem(
                    id=event.id,
                    action=event.action,
                    actor_username=actors.get(event.actor_id) if event.actor_id else None,
                    investigation_id=inv_id,
                    investigation_title=inv.title,
                    evidence_number=str(number) if number else None,
                    created_at=event.created_at,
                )
            )

    return DashboardSummary(
        investigations_total=len(investigations),
        by_status=by_status,
        evidence_total=evidence_total,
        integrity_issues=integrity_issues,
        open_investigations=[inv.id for inv in investigations if inv.status in OPEN_STATUSES],
        recent_activity=recent,
    )
