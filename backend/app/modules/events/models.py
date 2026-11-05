"""Immutable source interpretations, ingestion attempts and normalized events."""
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class SourceProfile(Base):
    __tablename__ = 'event_source_profiles'
    __table_args__ = (UniqueConstraint('investigation_id', 'semantic_key', name='uq_event_profile'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey('investigations.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    semantic_key: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(16), default='1')
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventIngestionRun(Base):
    __tablename__ = 'event_ingestion_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey('investigations.id', ondelete='CASCADE'), index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey('evidence.id', ondelete='RESTRICT'), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey('event_source_profiles.id', ondelete='RESTRICT'))
    initiated_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    status: Mapped[str] = mapped_column(String(24), default='running')
    input_sha256: Mapped[str | None] = mapped_column(String(64))
    verification_id: Mapped[int | None] = mapped_column(ForeignKey('evidence_verifications.id', ondelete='RESTRICT'))
    adapter_version: Mapped[str] = mapped_column(String(16))
    normalization_version: Mapped[str] = mapped_column(String(16))
    coverage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SecurityEvent(Base):
    __tablename__ = 'security_events'
    __table_args__ = (
        UniqueConstraint('investigation_id', 'semantic_key', name='uq_security_event'),
        Index('ix_event_case_time', 'investigation_id', 'timestamp_utc', 'semantic_key'),
        Index('ix_event_case_user', 'investigation_id', 'username'),
        Index('ix_event_case_source', 'investigation_id', 'source_ip'),
        Index('ix_event_case_host', 'investigation_id', 'hostname'),
        Index('ix_event_case_outcome', 'investigation_id', 'outcome'),
        Index('ix_event_case_type', 'investigation_id', 'event_type'),
        Index('ix_event_case_provider', 'investigation_id', 'provider', 'event_id'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey('investigations.id', ondelete='CASCADE'))
    evidence_id: Mapped[int] = mapped_column(ForeignKey('evidence.id', ondelete='RESTRICT'), index=True)
    first_run_id: Mapped[int] = mapped_column(ForeignKey('event_ingestion_runs.id', ondelete='RESTRICT'))
    profile_id: Mapped[int] = mapped_column(ForeignKey('event_source_profiles.id', ondelete='RESTRICT'))
    semantic_key: Mapped[str] = mapped_column(String(64))
    input_sha256: Mapped[str] = mapped_column(String(64))
    record_fingerprint: Mapped[str] = mapped_column(String(64))
    locator: Mapped[dict[str, Any]] = mapped_column(JSON)
    profile_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    adapter_version: Mapped[str] = mapped_column(String(16))
    normalization_version: Mapped[str] = mapped_column(String(16))
    coverage_status: Mapped[str] = mapped_column(String(16))
    source_format: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(40))
    event_type: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(24))
    event_id: Mapped[str | None] = mapped_column(String(32))
    username: Mapped[str | None] = mapped_column(String(256))
    account_domain: Mapped[str | None] = mapped_column(String(256))
    hostname: Mapped[str | None] = mapped_column(String(256))
    source_ip: Mapped[str | None] = mapped_column(String(45))
    destination_ip: Mapped[str | None] = mapped_column(String(45))
    source_port: Mapped[int | None] = mapped_column()
    destination_port: Mapped[int | None] = mapped_column()
    original_timestamp: Mapped[str | None] = mapped_column(String(128))
    timestamp_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_semantics: Mapped[dict[str, Any]] = mapped_column(JSON)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON)


class EventRunMember(Base):
    __tablename__ = 'event_run_members'
    run_id: Mapped[int] = mapped_column(ForeignKey('event_ingestion_runs.id', ondelete='CASCADE'), primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('security_events.id', ondelete='RESTRICT'), primary_key=True)
