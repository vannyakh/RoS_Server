"""Authentication request and response bodies."""

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    # Operator tokens only: when the sign-in chain ends however often it is refreshed.
    session_expires_at: datetime | None = None


class PlayerCreated(BaseModel):
    id: str
    username: str
