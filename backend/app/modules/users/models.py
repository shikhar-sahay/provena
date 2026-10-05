"""User persistence model and roles.

Roles are stored as plain strings (validated against the Role enum in
Python) rather than native database enums, so adding a value later does
not require an enum migration on PostgreSQL.
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Role(str, enum.Enum):
    ADMIN = "admin"
    INVESTIGATOR = "investigator"
    FORENSIC_ANALYST = "forensic_analyst"
    EVIDENCE_CUSTODIAN = "evidence_custodian"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # bcrypt hash. Never exposed through API schemas.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default=Role.INVESTIGATOR.value, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
