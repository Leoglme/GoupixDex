"""Per-user margin settings (table ``settings``)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class MarginSettings(Base):
    """Margin percentage applied to suggested resale price."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    margin_percent: Mapped[int] = mapped_column(Integer(), default=20)

    user: Mapped["User"] = relationship(back_populates="margin_settings")
