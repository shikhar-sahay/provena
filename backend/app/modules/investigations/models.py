"""Investigation and membership persistence models.

An investigation has a surrogate integer primary key plus a unique,
human-readable case number (e.g. PRV-2026-0001). Multiple users participate
through InvestigationMember rows; the lead investigator and creator are also
members so "can access" is a single membership check (admins bypass it).
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.modules.users.models import User


class InvestigationStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    CLOSED = "closed"
    ARCHIVED = "archived"


class InvestigationPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TeamRole(str, enum.Enum):
    LEAD = "lead"
    MEMBER = "member"


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    case_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(4000), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=InvestigationStatus.OPEN.value, index=True
    )
    priority: Mapped[str] = mapped_column(
        String(32), nullable=False, default=InvestigationPriority.MEDIUM.value
    )
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    lead_investigator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    lead_investigator: Mapped[User] = relationship(foreign_keys=[lead_investigator_id])
    members: Mapped[list["InvestigationMember"]] = relationship(
        back_populates="investigation", cascade="save-update, merge", passive_deletes=True
    )


class InvestigationMember(Base):
    __tablename__ = "investigation_members"
    __table_args__ = (
        UniqueConstraint("investigation_id", "user_id", name="uq_investigation_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    team_role: Mapped[str] = mapped_column(String(32), nullable=False, default=TeamRole.MEMBER.value)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    investigation: Mapped[Investigation] = relationship(back_populates="members")
    user: Mapped[User] = relationship()
