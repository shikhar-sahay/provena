"""Durable bounded export attempts; package bytes are private expiring artifacts."""
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class InvestigationExport(Base):
    __tablename__='investigation_exports'
    __table_args__=(UniqueConstraint('investigation_id','requested_by_id','request_key',name='uq_export_request'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    investigation_id: Mapped[int]=mapped_column(ForeignKey('investigations.id',ondelete='CASCADE'),index=True)
    requested_by_id: Mapped[int | None]=mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
    request_key: Mapped[str | None]=mapped_column(String(64))
    selection_hash: Mapped[str]=mapped_column(String(64))
    selection: Mapped[dict]=mapped_column(JSON)
    mode: Mapped[str]=mapped_column(String(16))
    status: Mapped[str]=mapped_column(String(16),default='running')
    artifact_key: Mapped[str]=mapped_column(String(64))
    package_sha256: Mapped[str | None]=mapped_column(String(64))
    byte_size: Mapped[int | None]=mapped_column(BigInteger)
    manifest_summary: Mapped[dict]=mapped_column(JSON,default=dict)
    error: Mapped[str | None]=mapped_column(String(300))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    completed_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
