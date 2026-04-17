"""Per-user margin settings (table ``settings``)."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class MarginSettings(Base):
    """Margin percentage and marketplace integration toggles / eBay listing defaults."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    margin_percent: Mapped[int] = mapped_column(Integer(), default=20)
    vinted_enabled: Mapped[bool] = mapped_column(Boolean(), default=True)
    ebay_enabled: Mapped[bool] = mapped_column(Boolean(), default=False)
    ebay_marketplace_id: Mapped[str] = mapped_column(String(32), default="EBAY_FR")
    ebay_category_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ebay_merchant_location_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ebay_fulfillment_policy_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ebay_payment_policy_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ebay_return_policy_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    user: Mapped["User"] = relationship(back_populates="margin_settings")
