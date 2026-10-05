"""Investigation service: case numbers, lifecycle rules, authorization.

Authorization model (enforced here, on the backend):
- Admins can access and manage everything.
- Other users can access investigations they are members of.
- Investigations can be created by admins and investigators.
- Managing (edit, status, team) requires admin, creator, or lead investigator.
- Archived investigations are read-only for ordinary users; only admins
  can move them out of archived.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.audit.service import Actions, ResourceTypes, record
from app.modules.investigations.models import (
    Investigation,
    InvestigationMember,
    InvestigationPriority,
    InvestigationStatus,
    TeamRole,
)
from app.modules.investigations.schemas import InvestigationCreate, InvestigationUpdate, MemberAdd
from app.modules.users.models import Role, User
from app.modules.users.service import get_by_id

CASE_NUMBER_PREFIX = "PRV"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_case_number(db: Session) -> str:
    """Next PRV-YYYY-NNNN number. Unique constraint + retry guards races."""
    year = _now().year
    prefix = f"{CASE_NUMBER_PREFIX}-{year}-"
    stmt = select(func.max(Investigation.case_number)).where(
        Investigation.case_number.like(f"{prefix}%")
    )
    current_max = db.execute(stmt).scalar_one_or_none()
    seq = int(current_max.rsplit("-", 1)[1]) + 1 if current_max else 1
    return f"{prefix}{seq:04d}"


def is_member(db: Session, investigation_id: int, user_id: int) -> bool:
    stmt = select(InvestigationMember.id).where(
        InvestigationMember.investigation_id == investigation_id,
        InvestigationMember.user_id == user_id,
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def can_access(db: Session, inv: Investigation, user: User) -> bool:
    return user.role == Role.ADMIN.value or is_member(db, inv.id, user.id)


def can_manage(db: Session, inv: Investigation, user: User) -> bool:
    if user.role == Role.ADMIN.value:
        return True
    return user.id in (inv.created_by_id, inv.lead_investigator_id)


def ensure_access(db: Session, inv: Investigation | None, user: User) -> Investigation:
    # Unknown and inaccessible investigations both report 404 so membership
    # cannot be probed through id enumeration.
    if inv is None or not can_access(db, inv, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found.")
    return inv


def ensure_manage(db: Session, inv: Investigation | None, user: User) -> Investigation:
    inv = ensure_access(db, inv, user)
    if not can_manage(db, inv, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
    return inv


def get_investigation(db: Session, investigation_id: int) -> Investigation | None:
    stmt = (
        select(Investigation)
        .where(Investigation.id == investigation_id)
        .options(
            selectinload(Investigation.created_by),
            selectinload(Investigation.lead_investigator),
            selectinload(Investigation.members).selectinload(InvestigationMember.user),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def list_accessible(db: Session, user: User, status_filter: InvestigationStatus | None = None):
    stmt = (
        select(Investigation)
        .options(
            selectinload(Investigation.created_by),
            selectinload(Investigation.lead_investigator),
            selectinload(Investigation.members).selectinload(InvestigationMember.user),
        )
        .order_by(Investigation.updated_at.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(Investigation.status == status_filter.value)
    if user.role != Role.ADMIN.value:
        stmt = stmt.where(
            Investigation.id.in_(
                select(InvestigationMember.investigation_id).where(
                    InvestigationMember.user_id == user.id
                )
            )
        )
    return list(db.execute(stmt).scalars().unique().all())


def create_investigation(db: Session, payload: InvestigationCreate, creator: User) -> Investigation:
    if creator.role not in (Role.ADMIN.value, Role.INVESTIGATOR.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only investigators and admins can create investigations.",
        )
    lead_id = payload.lead_investigator_id or creator.id
    lead = get_by_id(db, lead_id)
    if lead is None or not lead.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid lead investigator.")
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Title is required.")

    inv = Investigation(
        case_number="",
        title=title,
        description=payload.description.strip(),
        status=InvestigationStatus.OPEN.value,
        priority=payload.priority.value,
        created_by_id=creator.id,
        lead_investigator_id=lead.id,
    )
    # Retry on the (unlikely) case-number race; the unique constraint is the arbiter.
    for _ in range(5):
        inv.case_number = _generate_case_number(db)
        db.add(inv)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
    else:  # pragma: no cover - defensive; effectively unreachable at this scale
        raise HTTPException(status_code=500, detail="Could not assign a case number.")

    member_ids = {creator.id, lead.id}
    for uid in member_ids:
        db.add(
            InvestigationMember(
                investigation_id=inv.id,
                user_id=uid,
                team_role=TeamRole.LEAD.value if uid == lead.id else TeamRole.MEMBER.value,
            )
        )
    record(
        db,
        action=Actions.INVESTIGATION_CREATED,
        resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,
        actor_id=creator.id,
        metadata={"case_number": inv.case_number, "title": inv.title},
    )
    db.commit()
    db.refresh(inv)
    return get_investigation(db, inv.id)


def _apply_status(inv: Investigation, new_status: InvestigationStatus) -> bool:
    """Apply lifecycle rules. Returns True if the status actually changed."""
    old = inv.status
    if old == InvestigationStatus.ARCHIVED.value and new_status != InvestigationStatus.ARCHIVED:
        # Only admins may reopen archived investigations (checked by caller).
        pass
    if old == new_status.value:
        return False
    inv.status = new_status.value
    if new_status == InvestigationStatus.CLOSED:
        inv.closed_at = _now()
    elif old == InvestigationStatus.CLOSED.value:
        inv.closed_at = None
    return True


def update_investigation(
    db: Session, inv: Investigation, payload: InvestigationUpdate, actor: User
) -> Investigation:
    if inv.status == InvestigationStatus.ARCHIVED.value and actor.role != Role.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Archived investigations are read-only.",
        )
    changes: dict = {}
    if payload.title is not None and payload.title.strip() != inv.title:
        if not payload.title.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Title is required."
            )
        inv.title = payload.title.strip()
        changes["title"] = inv.title
    if payload.description is not None and payload.description.strip() != inv.description:
        inv.description = payload.description.strip()
        changes["description"] = True
    if payload.priority is not None and payload.priority.value != inv.priority:
        inv.priority = payload.priority.value
        changes["priority"] = inv.priority
    if payload.lead_investigator_id is not None and payload.lead_investigator_id != inv.lead_investigator_id:
        lead = get_by_id(db, payload.lead_investigator_id)
        if lead is None or not lead.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid lead investigator.")
        old_lead = inv.lead_investigator_id
        inv.lead_investigator_id = lead.id
        _ensure_member(db, inv.id, lead.id, TeamRole.LEAD)
        changes["lead_investigator_id"] = {"from": old_lead, "to": lead.id}
    status_changed = False
    old_status = inv.status
    if payload.status is not None:
        if (
            inv.status == InvestigationStatus.ARCHIVED.value
            and payload.status != InvestigationStatus.ARCHIVED
            and actor.role != Role.ADMIN.value
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can reopen archived investigations.",
            )
        status_changed = _apply_status(inv, payload.status)
        if status_changed:
            changes["status"] = {"from": old_status, "to": inv.status}

    if changes:
        record(
            db,
            action=Actions.INVESTIGATION_UPDATED,
            resource_type=ResourceTypes.INVESTIGATION,
            resource_id=inv.id,
            actor_id=actor.id,
            metadata={"changes": list(changes)},
        )
        if status_changed:
            record(
                db,
                action=Actions.INVESTIGATION_STATUS_CHANGED,
                resource_type=ResourceTypes.INVESTIGATION,
                resource_id=inv.id,
                actor_id=actor.id,
                metadata={"from": old_status, "to": inv.status},
            )
    db.commit()
    db.refresh(inv)
    return get_investigation(db, inv.id)


def _ensure_member(db: Session, investigation_id: int, user_id: int, team_role: TeamRole) -> None:
    stmt = select(InvestigationMember).where(
        InvestigationMember.investigation_id == investigation_id,
        InvestigationMember.user_id == user_id,
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is None:
        db.add(
            InvestigationMember(
                investigation_id=investigation_id, user_id=user_id, team_role=team_role.value
            )
        )
        db.flush()


def add_member(db: Session, inv: Investigation, payload: MemberAdd, actor: User) -> Investigation:
    target = get_by_id(db, payload.user_id)
    if target is None or not target.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user.")
    stmt = select(InvestigationMember).where(
        InvestigationMember.investigation_id == inv.id,
        InvestigationMember.user_id == target.id,
    )
    if db.execute(stmt).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User is already a member."
        )
    db.add(
        InvestigationMember(
            investigation_id=inv.id, user_id=target.id, team_role=payload.team_role.value
        )
    )
    record(
        db,
        action=Actions.INVESTIGATION_MEMBER_ADDED,
        resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,
        actor_id=actor.id,
        metadata={"user_id": target.id, "username": target.username},
    )
    db.commit()
    return get_investigation(db, inv.id)


def remove_member(db: Session, inv: Investigation, user_id: int, actor: User) -> Investigation:
    if user_id == inv.lead_investigator_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reassign the lead investigator before removing them.",
        )
    stmt = select(InvestigationMember).where(
        InvestigationMember.investigation_id == inv.id,
        InvestigationMember.user_id == user_id,
    )
    membership = db.execute(stmt).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found.")
    removed_username = membership.user.username
    db.delete(membership)
    record(
        db,
        action=Actions.INVESTIGATION_MEMBER_REMOVED,
        resource_type=ResourceTypes.INVESTIGATION,
        resource_id=inv.id,
        actor_id=actor.id,
        metadata={"user_id": user_id, "username": removed_username},
    )
    db.commit()
    return get_investigation(db, inv.id)
