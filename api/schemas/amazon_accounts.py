from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class AmazonAccountResponse(BaseModel):
    id: int
    label: str | None
    amazon_email: str
    has_password: bool
    created_at: str
    updated_at: str


class AmazonAccountCreate(BaseModel):
    label: str | None = Field(default=None, max_length=120)
    amazon_email: EmailStr
    password: str = Field(min_length=1, max_length=512)


class AmazonAccountUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=120)
    amazon_email: EmailStr | None = None
    password: str | None = Field(default=None, max_length=512)
    clear_password: bool = False


class AmazonAccountCredentials(BaseModel):
    amazon_email: str
    password: str


class AmazonAccountsOverview(BaseModel):
    accounts: list[AmazonAccountResponse]
    active_account_id: int | None


class AmazonActiveAccountUpdate(BaseModel):
    account_id: int | None = None


class AmazonProvisionInboundWatchRequest(BaseModel):
    email: EmailStr


class AmazonProvisionInboundCodeResponse(BaseModel):
    email: str
    code: str | None = None
