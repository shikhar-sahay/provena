"""User service: creation and lookup. Password handling lives in core.security."""

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_by_login(db: Session, identifier: str) -> User | None:
    """Find a user by username (exact) or email (case-insensitive)."""
    stmt = select(User).where(
        or_(User.username == identifier, User.email == identifier.lower())
    )
    return db.execute(stmt).scalar_one_or_none()


def list_active(db: Session) -> list[User]:
    stmt = select(User).where(User.is_active.is_(True)).order_by(User.username)
    return list(db.execute(stmt).scalars().all())


def create_user(db: Session, payload: UserCreate) -> User:
    user = User(
        username=payload.username,
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role.value,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("Username or email is already taken.")
    db.refresh(user)
    return user
