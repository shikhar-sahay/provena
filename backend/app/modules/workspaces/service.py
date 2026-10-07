"""Workspace creation, selection, invitations, and authorization helpers."""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.users.models import Role, User
from app.modules.audit.service import Actions, ResourceTypes, record
from app.modules.workspaces.models import Workspace, WorkspaceInvite, WorkspaceMembership
from app.modules.workspaces.schemas import InviteCreate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slug_base(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return value[:60] or "workspace"


def _unique_slug(db: Session, name: str) -> str:
    base = _slug_base(name)
    slug = base
    suffix = 2
    while db.execute(select(Workspace.id).where(Workspace.slug == slug)).scalar_one_or_none():
        slug = f"{base[:55]}-{suffix}"
        suffix += 1
    return slug


def get_membership(db: Session, user: User, workspace_id: int | None = None) -> WorkspaceMembership | None:
    target = workspace_id if workspace_id is not None else user.active_workspace_id
    if target is None:
        return None
    return db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == target,
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.is_active.is_(True),
        )
    ).scalar_one_or_none()


def require_membership(db: Session, user: User, workspace_id: int | None = None) -> WorkspaceMembership:
    membership = get_membership(db, user, workspace_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace access required.")
    return membership


def role_for(db: Session, user: User, workspace_id: int | None = None) -> str | None:
    membership = get_membership(db, user, workspace_id)
    return membership.role if membership else None


def is_admin(db: Session, user: User, workspace_id: int | None = None) -> bool:
    return role_for(db, user, workspace_id) == Role.ADMIN.value


def create_workspace(db: Session, user: User, name: str) -> Workspace:
    clean = name.strip()
    if len(clean) < 2:
        raise HTTPException(status_code=422, detail="Workspace name is required.")
    workspace = Workspace(name=clean, slug=_unique_slug(db, clean), created_by_id=user.id)
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMembership(
            workspace_id=workspace.id, user_id=user.id, role=Role.ADMIN.value, is_active=True
        )
    )
    user.active_workspace_id = workspace.id
    user.role = Role.ADMIN.value
    record(
        db, action=Actions.WORKSPACE_CREATED, resource_type=ResourceTypes.WORKSPACE,
        resource_id=workspace.id, actor_id=user.id, metadata={"name": workspace.name, "slug": workspace.slug},
    )
    db.commit()
    db.refresh(workspace)
    return workspace


def list_workspaces(db: Session, user: User) -> list[tuple[Workspace, WorkspaceMembership]]:
    rows = db.execute(
        select(Workspace, WorkspaceMembership)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.is_active.is_(True),
            Workspace.is_active.is_(True),
        )
        .order_by(Workspace.name)
    ).all()
    return list(rows)


def select_workspace(db: Session, user: User, workspace_id: int) -> Workspace:
    membership = require_membership(db, user, workspace_id)
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or not workspace.is_active:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    user.active_workspace_id = workspace_id
    user.role = membership.role
    db.commit()
    db.refresh(user)
    return workspace


def list_members(db: Session, user: User) -> list[WorkspaceMembership]:
    membership = require_membership(db, user)
    return list(
        db.execute(
            select(WorkspaceMembership)
            .where(WorkspaceMembership.workspace_id == membership.workspace_id)
            .options(selectinload(WorkspaceMembership.user))
            .order_by(WorkspaceMembership.joined_at, WorkspaceMembership.id)
        ).scalars().all()
    )


def create_invite(db: Session, user: User, payload: InviteCreate) -> tuple[WorkspaceInvite, str]:
    membership = require_membership(db, user)
    if membership.role != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail="Only workspace administrators can create invites.")
    raw = "PRV-" + secrets.token_urlsafe(18).replace("_", "").replace("-", "")
    expires = _now() + timedelta(days=payload.expires_in_days) if payload.expires_in_days else None
    invite = WorkspaceInvite(
        workspace_id=membership.workspace_id,
        code_hash=hashlib.sha256(raw.encode()).hexdigest(),
        code_hint=raw[-6:],
        role=payload.role.value,
        created_by_id=user.id,
        expires_at=expires,
        max_uses=payload.max_uses,
    )
    db.add(invite)
    record(
        db, action=Actions.WORKSPACE_INVITE_CREATED, resource_type=ResourceTypes.WORKSPACE,
        resource_id=membership.workspace_id, actor_id=user.id,
        metadata={"role": payload.role.value, "expires_at": expires.isoformat() if expires else None, "max_uses": payload.max_uses},
    )
    db.commit()
    db.refresh(invite)
    return invite, raw


def list_invites(db: Session, user: User) -> list[WorkspaceInvite]:
    membership = require_membership(db, user)
    if membership.role != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail="Only workspace administrators can view invites.")
    return list(db.execute(
        select(WorkspaceInvite)
        .where(WorkspaceInvite.workspace_id == membership.workspace_id)
        .order_by(WorkspaceInvite.id.desc())
    ).scalars().all())


def join_workspace(db: Session, user: User, code: str) -> Workspace:
    digest = hashlib.sha256(code.strip().encode()).hexdigest()
    invite = db.execute(
        select(WorkspaceInvite).where(WorkspaceInvite.code_hash == digest)
    ).scalar_one_or_none()
    now = _now()
    expires_at = invite.expires_at if invite is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if (
        invite is None
        or invite.revoked_at is not None
        or (expires_at is not None and expires_at < now)
        or invite.use_count >= invite.max_uses
    ):
        raise HTTPException(status_code=400, detail="Invite code is invalid, expired, or no longer available.")
    existing = db.execute(select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == invite.workspace_id,
        WorkspaceMembership.user_id == user.id,
    )).scalar_one_or_none()
    if existing is not None and existing.is_active:
        raise HTTPException(status_code=409, detail="You are already a member of this workspace.")
    if existing is None:
        db.add(WorkspaceMembership(
            workspace_id=invite.workspace_id, user_id=user.id, role=invite.role, is_active=True
        ))
    else:
        existing.is_active = True
        existing.role = invite.role
    invite.use_count += 1
    user.active_workspace_id = invite.workspace_id
    user.role = invite.role
    record(
        db, action=Actions.WORKSPACE_JOINED, resource_type=ResourceTypes.WORKSPACE,
        resource_id=invite.workspace_id, actor_id=user.id, metadata={"role": invite.role},
    )
    db.commit()
    workspace = db.get(Workspace, invite.workspace_id)
    assert workspace is not None
    return workspace


def update_member_role(db: Session, actor: User, user_id: int, role: Role) -> WorkspaceMembership:
    actor_membership = require_membership(db, actor)
    if actor_membership.role != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail="Only workspace administrators can manage roles.")
    target = db.execute(select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == actor_membership.workspace_id,
        WorkspaceMembership.user_id == user_id,
    )).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Workspace member not found.")
    if target.role == Role.ADMIN.value and role != Role.ADMIN:
        admins = db.execute(select(func.count()).select_from(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == actor_membership.workspace_id,
            WorkspaceMembership.role == Role.ADMIN.value,
            WorkspaceMembership.is_active.is_(True),
        )).scalar_one()
        if admins <= 1:
            raise HTTPException(status_code=400, detail="At least one active workspace administrator is required.")
    target.role = role.value
    target_user = db.get(User, target.user_id)
    if target_user is not None and target_user.active_workspace_id == target.workspace_id:
        target_user.role = role.value
    record(
        db, action=Actions.WORKSPACE_ROLE_CHANGED, resource_type=ResourceTypes.WORKSPACE,
        resource_id=target.workspace_id, actor_id=actor.id,
        metadata={"user_id": target.user_id, "role": role.value},
    )
    db.commit()
    db.refresh(target)
    return target
