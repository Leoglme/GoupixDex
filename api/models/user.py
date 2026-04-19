"""User ORM model."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

#: Application-wide allowed user statuses.
USER_STATUSES = ("pending", "approved", "rejected", "banned")


class User(Base):
    """Application user with login and optional Vinted credentials (hashed)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    #: Bcrypt hash. ``None`` while the user has only requested access (no password yet).
    password: Mapped[str | None] = mapped_column("password", String(255), nullable=True)
    vinted_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vinted_password: Mapped[str | None] = mapped_column("vinted_password", String(255), nullable=True)
    ebay_refresh_token: Mapped[str | None] = mapped_column(Text(), nullable=True)
    ebay_access_token: Mapped[str | None] = mapped_column(Text(), nullable=True)
    ebay_access_expires_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    #: True only for the admin user (seeded from SEED_USER_EMAIL).
    is_admin: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="0", nullable=False)
    #: pending | approved | rejected | banned
    status: Mapped[str] = mapped_column(
        String(16),
        default="pending",
        server_default="pending",
        nullable=False,
    )
    #: Message attached to the access request (filled from /request).
    request_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    #: Single-use token allowing the user to set/reset their password.
    password_setup_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    password_setup_expires_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )

    articles: Mapped[list["Article"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    margin_settings: Mapped["MarginSettings | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
