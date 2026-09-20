"""Per-user ``settings`` row (margin + marketplace options)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from config import EBAY_FR_DEFAULT_LEAF_CATEGORY_ID
from models.margin_settings import MarginSettings
from models.user import User


def get_or_create_user_settings(db: Session, user_id: int) -> MarginSettings:
    row = db.query(MarginSettings).filter(MarginSettings.user_id == user_id).first()
    if row is None:
        row = MarginSettings(user_id=user_id, margin_percent=20)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def effective_ebay_category_id(ms: MarginSettings) -> str:
    """User override when set; otherwise the application default France leaf category."""
    user_cat = (ms.ebay_category_id or "").strip()
    if user_cat:
        return user_cat
    return EBAY_FR_DEFAULT_LEAF_CATEGORY_ID.strip()


def effective_sender_full_name(user: User, ms: MarginSettings) -> str:
    """Nom expéditeur : profil utilisateur, repli sur l’ancien champ ``settings``."""
    return (user.full_name or ms.sender_full_name or "").strip()


def normalize_phone_e164(raw: str | None) -> str | None:
    """Keep + and digits only; require at least 10 digits (FR mobile and similar)."""
    if not raw or not str(raw).strip():
        return None
    cleaned = "".join(c for c in str(raw).strip() if c.isdigit() or c == "+")
    if cleaned.count("+") > 1 or (cleaned.startswith("+") and "+" in cleaned[1:]):
        return None
    digits = "".join(c for c in cleaned if c.isdigit())
    if len(digits) < 10 or len(digits) > 15:
        return None
    if cleaned.startswith("+"):
        return f"+{digits}"
    return digits


def amazon_provision_profile_complete(ms: MarginSettings, user: User) -> bool:
    """Profil prêt pour « Créer sur Amazon » (nom + adresse ; mobile / inbox SMS optionnels)."""
    return sender_address_complete(ms, user)


def sender_address_complete(ms: MarginSettings, user: User | None = None) -> bool:
    """True when the envelope flap (return) address is filled in for label printing."""
    name = (
        effective_sender_full_name(user, ms)
        if user is not None
        else (ms.sender_full_name or "").strip()
    )
    return bool(
        name
        and (ms.sender_line1 or "").strip()
        and (ms.sender_postal_code or "").strip()
        and (ms.sender_city or "").strip()
    )


def ebay_listing_config_complete(ms: MarginSettings) -> bool:
    return bool(
        effective_ebay_category_id(ms)
        and (ms.ebay_merchant_location_key or "").strip()
        and (ms.ebay_fulfillment_policy_id or "").strip()
        and (ms.ebay_payment_policy_id or "").strip()
        and (ms.ebay_return_policy_id or "").strip()
    )
