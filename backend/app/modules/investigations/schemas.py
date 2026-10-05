"""Investigation request/response schemas. Timestamps are server-controlled."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.investigations.models import InvestigationPriority, InvestigationStatus, TeamRole
from app.modules.users.schemas import UserRead


class InvestigationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)
    priority: InvestigationPriority = InvestigationPriority.MEDIUM
    # Optional: defaults to the creating user.
    lead_investigator_id: int | None = None


class InvestigationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    priority: InvestigationPriority | None = None
    status: InvestigationStatus | None = None
    lead_investigator_id: int | None = None


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserRead
    team_role: TeamRole
    created_at: datetime


class MemberAdd(BaseModel):
    user_id: int
    team_role: TeamRole = TeamRole.MEMBER


class InvestigationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_number: str
    title: str
    description: str
    status: InvestigationStatus
    priority: InvestigationPriority
    created_by: UserRead
    lead_investigator: UserRead
    members: list[MemberRead] = []
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class AuditEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    resource_type: str
    resource_id: str | None
    actor_id: int | None
    actor_username: str | None = None
    event_metadata: dict | None = None
    created_at: datetime
