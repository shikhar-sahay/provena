"""Workspace API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.users.models import Role


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    role: Role | None = None
    member_count: int | None = None


class WorkspaceMemberRead(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: Role
    is_active: bool
    joined_at: datetime


class InviteCreate(BaseModel):
    role: Role = Role.INVESTIGATOR
    expires_in_days: int | None = Field(default=7, ge=1, le=90)
    max_uses: int = Field(default=25, ge=1, le=100)

    @field_validator("role")
    @classmethod
    def prevent_admin_invite(cls, value: Role) -> Role:
        if value == Role.ADMIN:
            raise ValueError("Administrator access must be assigned by an existing administrator.")
        return value


class InviteRead(BaseModel):
    id: int
    code: str | None = None
    code_hint: str
    role: Role
    expires_at: datetime | None
    revoked_at: datetime | None
    use_count: int
    max_uses: int
    created_at: datetime


class JoinWorkspace(BaseModel):
    code: str = Field(min_length=8, max_length=80)


class MembershipRoleUpdate(BaseModel):
    role: Role
