"""Intelligence request/response schemas. Storage paths never appear."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.intelligence.models import ArtifactType, FindingStatus, RunEvidenceStatus, RunStatus


class RunStart(BaseModel):
    evidence_ids: list[int] = Field(min_length=1, max_length=100)


class RunEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: int
    evidence_number: str | None = None
    status: RunEvidenceStatus
    error: str | None = None
    artifact_count: int


class AnalysisRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investigation_id: int
    run_number: int
    run_label: str | None = None
    initiated_by_username: str | None = None
    status: RunStatus
    pipeline_version: str
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    evidence_count: int
    artifact_count: int
    correlation_count: int
    created_at: datetime
    evidence_outcomes: list[RunEvidenceRead] = []


class EligibilityEntry(BaseModel):
    evidence_id: int
    evidence_number: str
    title: str
    integrity_status: str
    supported: bool
    eligible: bool
    reason: str | None = None


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investigation_id: int
    evidence_id: int
    evidence_number: str | None = None
    evidence_title: str | None = None
    artifact_type: ArtifactType
    raw_value: str
    normalized_value: str
    locator: dict
    source_key: str
    context: str
    method: str
    extractor_name: str
    extractor_version: str
    created_at: datetime


class CorrelationEvidence(BaseModel):
    evidence_id: int
    evidence_number: str
    evidence_title: str
    artifact_count: int


class CorrelationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investigation_id: int
    correlation_type: str
    artifact_type: ArtifactType
    normalized_value: str
    evidence_count: int
    artifact_count: int
    created_at: datetime
    evidence_items: list[CorrelationEvidence] = []


class CorrelationArtifactRead(BaseModel):
    id: int
    evidence_id: int
    evidence_number: str
    artifact_type: ArtifactType
    raw_value: str
    normalized_value: str
    locator: dict
    source_key: str
    context: str
    method: str
    extractor_name: str
    extractor_version: str


class CorrelationDetailRead(CorrelationRead):
    artifacts: list[CorrelationArtifactRead] = []


class FindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investigation_id: int
    rule_id: str
    rule_version: str
    title: str
    summary: str
    severity: str
    confidence: int
    factors: list[dict]
    evidence_ids: list[int]
    artifact_ids: list[int]
    correlation_ids: list[int]
    recommendations: list[str]
    status: FindingStatus
    reviewer_username: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime
    updated_at: datetime


class FindingGenerateResult(BaseModel):
    findings: list[FindingRead]
    new_count: int


class FindingReview(BaseModel):
    status: Literal["accepted", "rejected"] = Field(
        description="Findings can only be accepted or rejected, never auto-validated."
    )
    note: str | None = Field(default=None, max_length=1000)


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    finding_id: int | None = None


class NoteUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investigation_id: int
    finding_id: int | None
    author_username: str | None = None
    body: str
    created_at: datetime
    updated_at: datetime


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investigation_id: int
    report_number: int
    report_label: str | None = None
    generated_by_username: str | None = None
    content: dict
    content_sha256: str
    created_at: datetime
