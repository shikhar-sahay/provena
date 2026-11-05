"""Immutable event selections and detection execution history; shared finding review."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class InvestigationEventSet(Base):
    __tablename__ = 'investigation_event_sets'
    __table_args__ = (UniqueConstraint('investigation_id','semantic_key',name='uq_investigation_event_set'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey('investigations.id',ondelete='CASCADE'),index=True)
    semantic_key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(16),default='1')
    selected_runs: Mapped[list] = mapped_column(JSON)
    coverage: Mapped[dict] = mapped_column(JSON)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())


class EventSetMember(Base):
    __tablename__ = 'investigation_event_set_members'
    set_id: Mapped[int] = mapped_column(ForeignKey('investigation_event_sets.id',ondelete='CASCADE'),primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('security_events.id',ondelete='RESTRICT'),primary_key=True)
    observation_key: Mapped[str] = mapped_column(String(64))
    included: Mapped[bool] = mapped_column(default=True)


class AuthenticationDetectionRun(Base):
    __tablename__ = 'authentication_detection_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey('investigations.id',ondelete='CASCADE'),index=True)
    event_set_id: Mapped[int] = mapped_column(ForeignKey('investigation_event_sets.id',ondelete='RESTRICT'),index=True)
    initiated_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
    status: Mapped[str] = mapped_column(String(24),default='running')
    engine_version: Mapped[str] = mapped_column(String(16),default='1')
    configuration: Mapped[dict] = mapped_column(JSON)
    coverage: Mapped[dict] = mapped_column(JSON,default=dict)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DetectionRunFinding(Base):
    __tablename__ = 'authentication_detection_run_findings'
    run_id: Mapped[int] = mapped_column(ForeignKey('authentication_detection_runs.id',ondelete='CASCADE'),primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey('findings.id',ondelete='RESTRICT'),primary_key=True)
