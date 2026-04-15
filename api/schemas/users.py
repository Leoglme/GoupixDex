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


class UserResponse(BaseModel):
    id: int
    email: str
    vinted_email: str | None
    created_at: str

    model_config = {"from_attributes": False}


class VintedDecryptedResponse(BaseModel):
    """
    Mot de passe Vinted en clair — réservé au worker desktop local (HTTPS + JWT).
    """

    vinted_email: str | None
    vinted_password: str | None
