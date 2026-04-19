"""Schemas for the access-request flow and password setup tokens."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class AccessRequestCreate(BaseModel):
    email: EmailStr
    message: str | None = Field(default=None, max_length=2000)


class AccessRequestSubmittedResponse(BaseModel):
    """Public confirmation that the request has been recorded."""

    ok: bool = True
    email: str


class PasswordSetupTokenResponse(BaseModel):
    """Returned to the admin when generating a one-shot link."""

    token: str
    expires_at: str
    setup_url: str


class PasswordSetupInfoResponse(BaseModel):
    """Public payload describing the user behind a setup token (no secrets)."""

    email: str
    expires_at: str


class PasswordSetupCompleteRequest(BaseModel):
    password: str = Field(min_length=8, max_length=255)
