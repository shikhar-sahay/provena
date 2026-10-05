"""Auth request/response schemas."""

from pydantic import BaseModel, Field

from app.modules.users.schemas import UserRead


class LoginRequest(BaseModel):
    username_or_email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class MessageResponse(BaseModel):
    detail: str
