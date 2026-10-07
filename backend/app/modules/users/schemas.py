"""User request/response schemas. Password hashes never leave the server."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.users.models import Role


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str
    role: Role
    active_workspace_id: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    """Admin-only user creation payload."""

    username: str = Field(min_length=3, max_length=64)
    # Basic shape check only (user@domain). Deliberately not a DNS-backed
    # EmailStr: dev addresses use non-routable .local domains and validation
    # must work offline.
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(default="", max_length=255)
    password: str = Field(min_length=8, max_length=72)
    role: Role = Role.INVESTIGATOR

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        if "@" not in value or " " in value or "." not in value.split("@")[-1]:
            raise ValueError("Enter a valid email address.")
        return value


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(default="", max_length=255)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        if "@" not in value or " " in value or "." not in value.split("@")[-1]:
            raise ValueError("Enter a valid email address.")
        return value.lower()


class UserMembership(BaseModel):
    id: int
    case_number: str
    title: str


class UserAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    investigations: list[UserMembership] = []


class UserActiveUpdate(BaseModel):
    is_active: bool
