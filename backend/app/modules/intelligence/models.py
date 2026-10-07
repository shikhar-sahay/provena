"""Intelligence persistence models: runs, artifacts, correlations.

- ``AnalysisRun`` records one explicit analyst-initiated processing pass.
- ``AnalysisRunEvidence`` records each selected item's outcome, so partial
  failures stay explicit instead of silent.
- ``Artifact`` is the canonical deduplicated store of extracted entities.
- ``Correlation`` is deterministic derived state, rebuilt on each completed
  run from the current artifact store. Correlations explain themselves
  through ``CorrelationArtifact`` links; they carry no conclusions.
- ``Finding`` is a rule-engine proposal with deterministic confidence,
  validated by humans (pending/accepted/rejected). Never auto-validated.
- ``InvestigationNote`` attaches human context to investigations or findings.
- ``Report`` snapshots accepted findings and case data deterministically.

Statuses and types are plain strings validated against Python enums, matching
existing backend conventions (no database enum migrations).
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.modules.users.models import User


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunEvidenceStatus(str, enum.Enum):
    PROCESSED = "processed"
    BLOCKED_NOT_VERIFIED = "blocked_not_verified"
    BLOCKED_MISMATCH = "blocked_mismatch"
    BLOCKED_UNAVAILABLE = "blocked_unavailable"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class ArtifactType(str, enum.Enum):
    IP_ADDRESS = "IP_ADDRESS"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    USERNAME = "USERNAME"
    HOSTNAME = "HOSTNAME"
    DOMAIN = "DOMAIN"
    FILE_PATH = "FILE_PATH"
    FILE_NAME = "FILE_NAME"
    HASH = "HASH"
    USB_DEVICE = "USB_DEVICE"
    TIMESTAMP = "TIMESTAMP"
    URL = "URL"
    PORT = "PORT"
    MAC_ADDRESS = "MAC_ADDRESS"
    PROCESS_NAME = "PROCESS_NAME"


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        UniqueConstraint("investigation_id", "run_number", name="uq_analysis_run_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Per-investigation sequence, displayed as RUN-0004.
    run_number: Mapped[int] = mapped_column(nullable=False)
    initiated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RunStatus.PENDING.value)
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    evidence_count: Mapped[int] = mapped_column(nullable=False, default=0)
    artifact_count: Mapped[int] = mapped_column(nullable=False, default=0)
    correlation_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    initiated_by: Mapped[User | None] = relationship(foreign_keys=[initiated_by_id])
    evidence_outcomes: Mapped[list["AnalysisRunEvidence"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class AnalysisRunEvidence(Base):
    __tablename__ = "analysis_run_evidence"
    __table_args__ = (
        UniqueConstraint("run_id", "evidence_id", name="uq_run_evidence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # Short safe reason. No paths, no file content.
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    artifact_count: Mapped[int] = mapped_column(nullable=False, default=0)

    run: Mapped[AnalysisRun] = relationship(back_populates="evidence_outcomes")


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint(
            "evidence_id",
            "artifact_type",
            "normalized_value",
            "source_key",
            "extractor_name",
            "extractor_version",
            name="uq_artifact_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    # Structured provenance, e.g. {"kind": "line", "line": 37}.
    locator: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # Canonical locator string, e.g. "line:37". Part of the dedup identity.
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    # Bounded human-readable excerpt. Never whole files or storage paths.
    context: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    extractor_name: Mapped[str] = mapped_column(String(64), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class Correlation(Base):
    __tablename__ = "correlations"
    __table_args__ = (
        UniqueConstraint(
            "investigation_id", "artifact_type", "normalized_value",
            name="uq_correlation_value",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    correlation_type: Mapped[str] = mapped_column(String(32), nullable=False, default="shared_value")
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    normalized_value: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    evidence_count: Mapped[int] = mapped_column(nullable=False, default=0)
    artifact_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    members: Mapped[list["CorrelationArtifact"]] = relationship(
        back_populates="correlation", cascade="all, delete-orphan", passive_deletes=True
    )


class CorrelationArtifact(Base):
    __tablename__ = "correlation_artifacts"
    __table_args__ = (
        UniqueConstraint("correlation_id", "artifact_id", name="uq_correlation_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    correlation_id: Mapped[int] = mapped_column(
        ForeignKey("correlations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    correlation: Mapped[Correlation] = relationship(back_populates="members")


class FindingStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint(
            "investigation_id", "rule_id", "inputs_key", name="uq_finding_inputs"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rule_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    # Deterministic weighted score 0-100 for ranking, not a probability.
    confidence: Mapped[int] = mapped_column(nullable=False, default=0)
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    evidence_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    artifact_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    correlation_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    # Stable dedup identity over rule version plus sorted inputs.
    inputs_key: Mapped[str] = mapped_column(String(64), nullable=False)
    recommendations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=FindingStatus.PENDING_REVIEW.value, index=True
    )
    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    generated_by_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_id])


class InvestigationNote(Base):
    __tablename__ = "investigation_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[int | None] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=True, index=True
    )
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    author: Mapped[User | None] = relationship(foreign_keys=[author_id])


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("investigation_id", "report_number", name="uq_report_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Per-investigation sequence, displayed as RPT-0001.
    report_number: Mapped[int] = mapped_column(nullable=False)
    generated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Full deterministic snapshot plus its SHA-256 for traceability.
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    generated_by: Mapped[User | None] = relationship(foreign_keys=[generated_by_id])
