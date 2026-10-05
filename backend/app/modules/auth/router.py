"""Auth endpoints: login, logout, current user."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.modules.audit.service import Actions, ResourceTypes, record
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import LoginRequest, MessageResponse, TokenResponse
from app.modules.users.models import User
from app.modules.users.schemas import UserRead
from app.modules.users.service import get_by_login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = get_by_login(db, payload.username_or_email)
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        # Same message for unknown user, inactive user, and wrong password
        # so callers cannot probe which accounts exist.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials."
        )
    record(
        db,
        action=Actions.USER_LOGIN,
        resource_type=ResourceTypes.USER,
        resource_id=user.id,
        actor_id=user.id,
    )
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id), user=UserRead.model_validate(user))


@router.post("/logout", response_model=MessageResponse)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Tokens are stateless bearer tokens: the client discards its copy.
    # The server records the event for the audit trail.
    record(
        db,
        action=Actions.USER_LOGOUT,
        resource_type=ResourceTypes.SESSION,
        actor_id=user.id,
    )
    db.commit()
    return MessageResponse(detail="Logged out.")


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return UserRead.model_validate(user)
