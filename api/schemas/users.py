from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    vinted_email: str | None = None
    vinted_password: str | None = None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    vinted_email: str | None = None
    vinted_password: str | None = None


class VintedCredentialsUpdate(BaseModel):
    """Self-service Vinted account linking from /settings/marketplaces."""

    vinted_email: str | None = Field(default=None, max_length=255)
    vinted_password: str | None = Field(default=None, max_length=255)


class UserResponse(BaseModel):
    """Light response returned to the user themselves (``/users/me``)."""

    id: int
    email: str
    vinted_email: str | None
    is_admin: bool
    status: str
    created_at: str

    model_config = {"from_attributes": False}


class AdminUserResponse(BaseModel):
    """Full payload exposed to admins on the /users page."""

    id: int
    email: str
    vinted_email: str | None
    vinted_linked: bool
    vinted_enabled: bool
    ebay_enabled: bool
    margin_percent: int
    is_admin: bool
    status: str
    request_message: str | None
    created_at: str
    has_password: bool
    has_password_setup_link: bool


class VintedDecryptedResponse(BaseModel):
    """
    Mot de passe Vinted en clair — réservé au worker desktop local (HTTPS + JWT).
    """

    vinted_email: str | None
    vinted_password: str | None
