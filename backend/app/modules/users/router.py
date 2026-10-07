"""User endpoints: minimal set needed for this slice.

- GET /api/users: authenticated users see active accounts (needed for team assignment).
- POST /api/users: admin-only user creation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.audit.service import Actions, ResourceTypes, record
from app.modules.auth.dependencies import get_current_user, require_admin
from app.modules.users.models import Role, User
from app.modules.users.schemas import UserActiveUpdate, UserAdminRead, UserCreate, UserMembership, UserRead
from app.modules.users.service import count_active_admins, create_user, list_active, list_all, set_active

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.modules.workspaces import service as workspace_service
    result = []
    for item in workspace_service.list_members(db, user):
        if not item.user.is_active:
            continue
        data = UserRead.model_validate(item.user)
        data.role = Role(item.role)
        result.append(data)
    return result


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    payload: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        user = create_user(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    from app.modules.workspaces import service as workspace_service
    from app.modules.workspaces.models import WorkspaceMembership
    admin_membership = workspace_service.require_membership(db, admin)
    db.add(WorkspaceMembership(
        workspace_id=admin_membership.workspace_id, user_id=user.id,
        role=payload.role.value, is_active=True,
    ))
    user.active_workspace_id = admin_membership.workspace_id
    record(
        db,
        action=Actions.USER_CREATED,
        resource_type=ResourceTypes.USER,
        resource_id=user.id,
        actor_id=admin.id,
        metadata={"username": user.username, "role": user.role},
    )
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/users", response_model=list[UserAdminRead])
def admin_list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from app.modules.investigations.models import Investigation, InvestigationMember
    from sqlalchemy import select as sa_select

    from app.modules.workspaces import service as workspace_service
    workspace_membership = workspace_service.require_membership(db, admin)
    memberships = db.execute(
        sa_select(
            InvestigationMember.user_id,
            Investigation.id,
            Investigation.case_number,
            Investigation.title,
        )
        .join(Investigation, Investigation.id == InvestigationMember.investigation_id)
        .where(Investigation.workspace_id == workspace_membership.workspace_id)
        .order_by(Investigation.case_number)
    ).all()
    by_user: dict[int, list] = {}
    for user_id, inv_id, case_number, title in memberships:
        by_user.setdefault(user_id, []).append(
            UserMembership(id=inv_id, case_number=case_number, title=title)
        )
    out = []
    accounts = [item.user for item in workspace_service.list_members(db, admin)]
    for account in accounts:
        data = UserAdminRead.model_validate(account)
        data.investigations = by_user.get(account.id, [])
        out.append(data)
    return out


@admin_router.patch("/users/{user_id}", response_model=UserAdminRead)
def admin_update_user(
    user_id: int,
    payload: UserActiveUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.modules.users.models import Role

    target = db.get(User, user_id)
    from app.modules.workspaces import service as workspace_service
    member_ids = {item.user_id for item in workspace_service.list_members(db, admin)}
    if target is None or target.id not in member_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if not payload.is_active:
        if target.id == admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account.",
            )
        if target.role == Role.ADMIN.value and count_active_admins(db) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one active admin is required.",
            )
    updated = set_active(db, target, payload.is_active)
    return UserAdminRead.model_validate(updated)
