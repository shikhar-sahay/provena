"""User service: creation and lookup. Password handling lives in core.security."""

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserRegister


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


def list_all(db: Session) -> list[User]:
    stmt = select(User).order_by(User.username)
    return list(db.execute(stmt).scalars().all())


def set_active(db: Session, user: User, active: bool) -> User:
    user.is_active = active
    db.commit()
    db.refresh(user)
    return user


def count_active_admins(db: Session) -> int:
    from app.modules.users.models import Role

    return db.execute(
        select(func.count())
        .select_from(User)
        .where(User.role == Role.ADMIN.value, User.is_active.is_(True))
    ).scalar_one()


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


def create_registered_user(db: Session, payload: UserRegister) -> User:
    """Create a self-service account with no workspace until onboarding."""
    user = User(
        username=payload.username.strip(),
        email=payload.email.lower().strip(),
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role="investigator",
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("Username or email is already taken.")
    db.refresh(user)
    return user
