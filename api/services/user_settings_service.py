"""Per-user ``settings`` row (margin + marketplace options)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.margin_settings import MarginSettings


def get_or_create_user_settings(db: Session, user_id: int) -> MarginSettings:
    row = db.query(MarginSettings).filter(MarginSettings.user_id == user_id).first()
    if row is None:
        row = MarginSettings(user_id=user_id, margin_percent=20)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def ebay_listing_config_complete(ms: MarginSettings) -> bool:
    return bool(
        (ms.ebay_category_id or "").strip()
        and (ms.ebay_merchant_location_key or "").strip()
        and (ms.ebay_fulfillment_policy_id or "").strip()
        and (ms.ebay_payment_policy_id or "").strip()
        and (ms.ebay_return_policy_id or "").strip()
    )
