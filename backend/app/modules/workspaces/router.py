"""Workspace onboarding and membership endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.users.models import Role
from app.modules.workspaces import service
from app.modules.workspaces.models import WorkspaceMembership
from app.modules.workspaces.schemas import (
    InviteCreate,
    InviteRead,
    JoinWorkspace,
    MembershipRoleUpdate,
    WorkspaceCreate,
    WorkspaceMemberRead,
    WorkspaceRead,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _workspace_read(db: Session, workspace, role=None) -> WorkspaceRead:
    count = db.execute(select(func.count()).select_from(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == workspace.id,
        WorkspaceMembership.is_active.is_(True),
    )).scalar_one()
    data = WorkspaceRead.model_validate(workspace)
    data.role = Role(role) if role else None
    data.member_count = count
    return data


@router.get("", response_model=list[WorkspaceRead])
def workspaces(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_workspace_read(db, workspace, membership.role) for workspace, membership in service.list_workspaces(db, user)]


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _workspace_read(db, service.create_workspace(db, user, payload.name), role="admin")


@router.post("/join", response_model=WorkspaceRead)
def join_workspace(payload: JoinWorkspace, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    workspace = service.join_workspace(db, user, payload.code)
    return _workspace_read(db, workspace, service.role_for(db, user, workspace.id))


@router.post("/{workspace_id}/select", response_model=WorkspaceRead)
def select_workspace(workspace_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    workspace = service.select_workspace(db, user, workspace_id)
    return _workspace_read(db, workspace, service.role_for(db, user, workspace.id))


@router.get("/current/members", response_model=list[WorkspaceMemberRead])
def members(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [WorkspaceMemberRead(
        id=item.user.id, username=item.user.username, email=item.user.email,
        full_name=item.user.full_name, role=item.role, is_active=item.is_active,
        joined_at=item.joined_at,
    ) for item in service.list_members(db, user)]


@router.patch("/current/members/{user_id}", response_model=WorkspaceMemberRead)
def update_member(user_id: int, payload: MembershipRoleUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = service.update_member_role(db, user, user_id, payload.role)
    db.refresh(item, ["user"])
    return WorkspaceMemberRead(
        id=item.user.id, username=item.user.username, email=item.user.email,
        full_name=item.user.full_name, role=item.role, is_active=item.is_active,
        joined_at=item.joined_at,
    )


@router.post("/current/invites", response_model=InviteRead, status_code=status.HTTP_201_CREATED)
def create_invite(payload: InviteCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    invite, code = service.create_invite(db, user, payload)
    return InviteRead(
        id=invite.id, code=code, code_hint=invite.code_hint, role=invite.role,
        expires_at=invite.expires_at, revoked_at=invite.revoked_at,
        use_count=invite.use_count, max_uses=invite.max_uses, created_at=invite.created_at,
    )


@router.get("/current/invites", response_model=list[InviteRead])
def invites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [InviteRead(
        id=item.id, code_hint=item.code_hint, role=item.role,
        expires_at=item.expires_at, revoked_at=item.revoked_at,
        use_count=item.use_count, max_uses=item.max_uses, created_at=item.created_at,
    ) for item in service.list_invites(db, user)]
