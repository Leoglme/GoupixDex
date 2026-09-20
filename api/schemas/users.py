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


class ProfileUpdate(BaseModel):
    """Self-service profile fields (drawer « Mon profil »)."""

    full_name: str | None = Field(default=None, max_length=120)
    sender_line1: str | None = Field(default=None, max_length=180)
    sender_line2: str | None = Field(default=None, max_length=180)
    sender_postal_code: str | None = Field(default=None, max_length=20)
    sender_city: str | None = Field(default=None, max_length=80)
    phone_e164: str | None = Field(default=None, max_length=20)


class ProfileResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    sender_line1: str | None
    sender_line2: str | None
    sender_postal_code: str | None
    sender_city: str | None
    sender_address_complete: bool
    phone_e164: str | None
    amazon_provision_profile_complete: bool


class UserResponse(BaseModel):
    """Light response returned to the user themselves (``/users/me``)."""

    id: int
    email: str
    full_name: str | None
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
    Plaintext Vinted password — for the local desktop worker only (HTTPS + JWT).
    """

    vinted_email: str | None
    vinted_password: str | None
