"""User ORM model."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class User(Base):
    """Application user with login and optional Vinted credentials (hashed)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password: Mapped[str] = mapped_column("password", String(255))
    vinted_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vinted_password: Mapped[str | None] = mapped_column("vinted_password", String(255), nullable=True)
    ebay_refresh_token: Mapped[str | None] = mapped_column(Text(), nullable=True)
    ebay_access_token: Mapped[str | None] = mapped_column(Text(), nullable=True)
    ebay_access_expires_at: Mapped[dt.datetime | None] = mapped_column(
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
