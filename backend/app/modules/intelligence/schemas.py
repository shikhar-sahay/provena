"""Intelligence request/response schemas. Storage paths never appear."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.intelligence.models import ArtifactType, RunEvidenceStatus, RunStatus


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
