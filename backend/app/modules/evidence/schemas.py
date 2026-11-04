"""Evidence request/response schemas.

Storage keys never appear in API responses: clients reference evidence by
investigation id plus evidence id, and the server resolves files internally.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal

from app.modules.evidence.models import CustodyAction, EvidenceType, IntegrityStatus
from app.modules.users.schemas import UserRead


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investigation_id: int
    evidence_number: str
    title: str
    description: str
    evidence_type: EvidenceType
    original_filename: str
    content_type: str | None
    source: str
    acquired_at: datetime | None
    registered_by: UserRead
    current_holder: UserRead | None = None
    file_size: int
    sha256: str
    integrity_status: IntegrityStatus
    registration_status: Literal["pending", "failed", "ready"] = "ready"
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EvidenceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    evidence_type: EvidenceType | None = None
    source: str | None = Field(default=None, max_length=255)
    acquired_at: datetime | None = None


class VerificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: int
    performed_by: UserRead | None = None
    expected_sha256: str
    observed_sha256: str | None
    result: IntegrityStatus
    reason: str | None
    purpose: str = "manual"
    created_at: datetime


class CustodyEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: int
    action: CustodyAction
    from_user: UserRead | None = None
    to_user: UserRead | None = None
    performed_by: UserRead | None = None
    notes: str
    created_at: datetime


class CustodyCreate(BaseModel):
    action: CustodyAction = CustodyAction.TRANSFERRED
    to_user_id: int | None = None
    notes: str = Field(default="", max_length=1000)

    @field_validator("action")
    @classmethod
    def user_actions_only(cls, value):
        if value in {CustodyAction.REGISTERED, CustodyAction.VERIFIED, CustodyAction.INTEGRITY_MISMATCH, CustodyAction.UNAVAILABLE, CustodyAction.RECOVERED}:
            raise ValueError("This custody action is recorded by the system only.")
        return value


class TimelineEntry(BaseModel):
    occurred_at: datetime
    kind: str
    title: str
    detail: str
    actor_username: str | None = None
    evidence_number: str | None = None
