"""Investigation endpoints: CRUD, team membership, per-investigation audit history."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.audit.service import list_for_investigation
from app.modules.auth.dependencies import get_current_user
from app.modules.investigations import service
from app.modules.investigations.models import InvestigationStatus
from app.modules.investigations.schemas import (
    AuditEntryRead,
    InvestigationCreate,
    InvestigationRead,
    InvestigationUpdate,
    MemberAdd,
)
from app.modules.users.models import Role, User
from app.modules.workspaces.models import WorkspaceMembership

router = APIRouter(prefix="/investigations", tags=["investigations"])


def _to_read(db: Session, inv) -> InvestigationRead:
    data = InvestigationRead.model_validate(inv)
    roles = dict(db.execute(select(
        WorkspaceMembership.user_id, WorkspaceMembership.role
    ).where(WorkspaceMembership.workspace_id == inv.workspace_id)).all())
    for member in data.members:
        if member.user.id in roles:
            member.user.role = Role(roles[member.user.id])
    if data.created_by.id in roles:
        data.created_by.role = Role(roles[data.created_by.id])
    if data.lead_investigator.id in roles:
        data.lead_investigator.role = Role(roles[data.lead_investigator.id])
    return data


@router.get("", response_model=list[InvestigationRead])
def list_investigations(
    status: InvestigationStatus | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return [_to_read(db, inv) for inv in service.list_accessible(db, user, status)]


@router.post("", response_model=InvestigationRead, status_code=201)
def create_investigation(
    payload: InvestigationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _to_read(db, service.create_investigation(db, payload, user))


@router.get("/{investigation_id}", response_model=InvestigationRead)
def get_investigation(
    investigation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = service.ensure_access(db, service.get_investigation(db, investigation_id), user)
    return _to_read(db, inv)


@router.patch("/{investigation_id}", response_model=InvestigationRead)
def update_investigation(
    investigation_id: int,
    payload: InvestigationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = service.ensure_manage(db, service.get_investigation(db, investigation_id), user)
    return _to_read(db, service.update_investigation(db, inv, payload, user))


@router.get("/{investigation_id}/members", response_model=InvestigationRead)
def list_members(
    investigation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Membership is part of the investigation aggregate for this slice.
    inv = service.ensure_access(db, service.get_investigation(db, investigation_id), user)
    return _to_read(db, inv)


@router.post("/{investigation_id}/members", response_model=InvestigationRead)
def add_member(
    investigation_id: int,
    payload: MemberAdd,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = service.ensure_manage(db, service.get_investigation(db, investigation_id), user)
    return _to_read(db, service.add_member(db, inv, payload, user))


@router.delete("/{investigation_id}/members/{member_user_id}", response_model=InvestigationRead)
def remove_member(
    investigation_id: int,
    member_user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = service.ensure_manage(db, service.get_investigation(db, investigation_id), user)
    return _to_read(db, service.remove_member(db, inv, member_user_id, user))


@router.get("/{investigation_id}/audit", response_model=list[AuditEntryRead])
def investigation_audit(
    investigation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.ensure_access(db, service.get_investigation(db, investigation_id), user)
    entries = []
    for event in list_for_investigation(db, investigation_id):
        entry = AuditEntryRead.model_validate(event)
        actor = event.actor_id and db.get(User, event.actor_id)
        entry.actor_username = actor.username if actor else None
        entries.append(entry)
    return entries
