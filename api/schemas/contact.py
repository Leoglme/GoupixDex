"""Schemas of the public contact page (``POST /contact``)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app_types.contact import ContactTopic


class ContactMessageCreate(BaseModel):
    """A message written on the contact page; ``website`` is a honeypot that only bots fill in."""

    model_config = ConfigDict(str_strip_whitespace=True)

    topic: ContactTopic = "other"
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    message: str = Field(min_length=1, max_length=5000)
    website: str | None = Field(default=None, max_length=300)

    @field_validator("name", "phone")
    @classmethod
    def collapse_to_single_line(cls, value: str | None) -> str | None:
        """Keep the name and the phone on one line (they go in the subject or the table); drop an empty phone."""
        if value is None:
            return None
        return " ".join(value.split()) or None


class ContactMessageSentResponse(BaseModel):
    """The message left (or was silently dropped as spam)."""

    ok: bool = True
