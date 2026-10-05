"""User endpoints: minimal set needed for this slice.

- GET /api/users: authenticated users see active accounts (needed for team assignment).
- POST /api/users: admin-only user creation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.audit.service import Actions, ResourceTypes, record
from app.modules.auth.dependencies import get_current_user, require_admin
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import create_user, list_active

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [UserRead.model_validate(u) for u in list_active(db)]


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
