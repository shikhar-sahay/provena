"""Evidence persistence models.

Three tables, three separate concerns:

- ``Evidence`` describes the item itself and its integrity baseline.
- ``EvidenceVerification`` records each explicit integrity check.
- ``CustodyEvent`` is the append-only chain of custody.

Roles, statuses, and actions are plain strings validated against Python
enums, so new values never require a database enum migration.
"""

import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.modules.users.models import User


class EvidenceType(str, enum.Enum):
    LOG = "log"
    DOCUMENT = "document"
    IMAGE = "image"
    NETWORK = "network"
    EMAIL = "email"
    DEVICE = "device"
    ARCHIVE = "archive"
    OTHER = "other"


class IntegrityStatus(str, enum.Enum):
    NOT_VERIFIED = "not_verified"
    VERIFIED = "verified"
    MISMATCH = "mismatch"
    UNAVAILABLE = "unavailable"


class CustodyAction(str, enum.Enum):
    REGISTERED = "registered"
    TRANSFERRED = "transferred"
    RELEASED_FOR_ANALYSIS = "released_for_analysis"
    RETURNED_TO_CUSTODY = "returned_to_custody"
    RECEIVED = "received"
    OTHER = "other"


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint("investigation_id", "evidence_number", name="uq_evidence_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Human-readable identifier, unique within the investigation (E-001, ...).
    evidence_number: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(4000), nullable=False, default="")
    evidence_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=EvidenceType.OTHER.value, index=True
    )
    # Original filename is metadata only; storage never trusts it.
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Investigator-supplied provenance timestamp (e.g. when the log was taken).
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registered_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Internal storage key relative to the storage root. Never a user path.
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # Baseline SHA-256 digest of the bytes accepted at ingestion. Immutable.
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    integrity_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=IntegrityStatus.NOT_VERIFIED.value, index=True
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    registered_by: Mapped[User] = relationship(foreign_keys=[registered_by_id])


class EvidenceVerification(Base):
    __tablename__ = "evidence_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    performed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expected_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Short, safe failure reason. No paths, no system internals.
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    performed_by: Mapped[User | None] = relationship()


class CustodyEvent(Base):
    __tablename__ = "custody_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    from_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    to_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    performed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    from_user: Mapped[User | None] = relationship(foreign_keys=[from_user_id])
    to_user: Mapped[User | None] = relationship(foreign_keys=[to_user_id])
    performed_by: Mapped[User | None] = relationship(foreign_keys=[performed_by_id])
