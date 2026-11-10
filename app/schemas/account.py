"""Account responses. Password hashes and session token hashes are not part of this contract."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str | None = None
    status: str
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


class AccountSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    expires_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime


class LoginHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str | None = None
    login_status: str
    ip_address: str | None = None
    created_at: datetime


class AccountCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=128)
    email: str | None = Field(default=None, max_length=254)
