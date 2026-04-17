"""Publish an article to eBay via Inventory API (inventory item → offer → publish)."""

from __future__ import annotations

import html
import logging
import uuid
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.orm import Session

from config import AppSettings, get_settings
from core.security import decrypt_ebay_token, store_ebay_token
from models.article import Article
from models.margin_settings import MarginSettings
from models.user import User
from services.ebay_oauth_service import _api_base_url, refresh_user_access_token
from services.user_settings_service import ebay_listing_config_complete, effective_ebay_category_id

logger = logging.getLogger(__name__)

_CONDITION_TO_EBAY: dict[str, str] = {
    "Mint": "USED_EXCELLENT",
    "Near Mint": "USED_EXCELLENT",
    "NM": "USED_EXCELLENT",
    "Excellent": "USED_EXCELLENT",
    "Good": "USED_GOOD",
    "Lightly Played": "USED_GOOD",
    "Played": "USED_ACCEPTABLE",
    "Poor": "USED_ACCEPTABLE",
}

# Catégories feuille « cartes à jouer / TCG » (descripteur d’état carte obligatoire — Metadata / MIP eBay).
_TCG_LEAF_CATEGORY_IDS = frozenset({"183050", "183454", "261328"})
# Descripteur « état de la carte » (cartes non gradées) — name + value IDs eBay.
_CARD_CONDITION_DESCRIPTOR_NAME = "40001"
_APP_TO_CARD_CONDITION_VALUE_ID: dict[str, str] = {
    "Mint": "400010",
    "Near Mint": "400010",
    "NM": "400010",
    "Excellent": "400011",
    "Good": "400012",
    "Lightly Played": "400015",
    "Played": "400016",
    "Poor": "400017",
}

_MARKETPLACE_CURRENCY: dict[str, str] = {
    "EBAY_US": "USD",
    "EBAY_GB": "GBP",
    "EBAY_AU": "AUD",
    "EBAY_CA": "CAD",
}


def _currency_for_marketplace(marketplace_id: str) -> str:
    return _MARKETPLACE_CURRENCY.get(marketplace_id.strip().upper(), "EUR")


def _ebay_condition(app_condition: str) -> str:
    return _CONDITION_TO_EBAY.get(app_condition.strip(), "USED_EXCELLENT")


def _card_condition_descriptor_value_id(app_condition: str) -> str:
    """ID valeur du descripteur « Card Condition » (cartes non gradées), voir MIP eBay."""
    key = (app_condition or "").strip()
    return _APP_TO_CARD_CONDITION_VALUE_ID.get(key, "400010")


def _listing_price_eur(article: Article) -> Decimal:
    if article.sell_price is not None:
        return article.sell_price
    return article.purchase_price


def _sku_for_listing(article_id: int) -> str:
    suffix = uuid.uuid4().hex[:12]
    raw = f"gpx{article_id}{suffix}"
    return "".join(c for c in raw if c.isalnum())[:50]


async def ensure_ebay_access_token(db: Session, user: User, *, app: AppSettings | None = None) -> str:
    """Return a valid user access token, refreshing (and persisting) when needed."""
    import datetime as dt

    s = app or get_settings()
    now = dt.datetime.now(dt.UTC)
    plain_access = decrypt_ebay_token(user.ebay_access_token)
    exp = user.ebay_access_expires_at
    if plain_access and exp is not None:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=dt.UTC)
        if exp > now + dt.timedelta(minutes=5):
            return plain_access

    rt = decrypt_ebay_token(user.ebay_refresh_token)
    if not rt:
        raise RuntimeError("ebay_not_connected")

    data = await refresh_user_access_token(rt, app=s)
    access = data.get("access_token")
    if not access or not isinstance(access, str):
        raise RuntimeError("ebay_token_response_invalid")

    user.ebay_access_token = store_ebay_token(access)
    if data.get("refresh_token"):
        user.ebay_refresh_token = store_ebay_token(str(data["refresh_token"]))
    expires_in = int(data.get("expires_in", 7200))
    user.ebay_access_expires_at = now + dt.timedelta(seconds=expires_in)
    db.add(user)
    db.commit()
    db.refresh(user)
    return access


def _description_html(article: Article) -> str:
    plain = (article.description or "").strip()
    if not plain:
        plain = article.title
    esc = html.escape(plain)
    return f"<p>{esc}</p>"


def _product_aspects(article: Article) -> dict[str, list[str]]:
    aspects: dict[str, list[str]] = {"Brand": ["Pokémon"]}
    if article.pokemon_name:
        aspects["Character"] = [article.pokemon_name.strip()]
    if article.set_code:
        aspects["Set"] = [article.set_code.strip()]
    if article.card_number:
        aspects["Card Number"] = [article.card_number.strip()]
    return aspects


async def publish_article_to_ebay(
    db: Session,
    article: Article,
    user: User,
    ms: MarginSettings,
    image_urls: list[str],
    *,
    app: AppSettings | None = None,
) -> dict[str, Any]:
    """
    Create inventory + offer + publish. Returns ``{ "ok": True, "listing_id": "..." }`` or
    ``{ "ok": False, "detail": "..." }``.
    """
    s = app or get_settings()
    if not ms.ebay_enabled:
        return {"ok": False, "detail": "ebay_disabled"}
    if not ebay_listing_config_complete(ms):
        return {"ok": False, "detail": "ebay_listing_config_incomplete"}

    https_images = [u.strip() for u in image_urls if u.startswith("https://")]
    if not https_images:
        return {"ok": False, "detail": "ebay_requires_https_images"}

    try:
        token = await ensure_ebay_access_token(db, user, app=s)
    except RuntimeError as exc:
        return {"ok": False, "detail": str(exc)}

    root = _api_base_url(s)
    marketplace_id = (ms.ebay_marketplace_id or "EBAY_FR").strip()
    currency = _currency_for_marketplace(marketplace_id)
    sku = _sku_for_listing(article.id)
    title = (article.title or "Carte Pokémon").strip()[:80]
    price = _listing_price_eur(article)
    price_str = f"{price.quantize(Decimal('0.01'))}"

    inv_payload: dict[str, Any] = {
        "availability": {"shipToLocationAvailability": {"quantity": 1}},
        "condition": _ebay_condition(article.condition),
        "conditionDescription": html.escape((article.condition or "")[:1000]),
        "product": {
            "title": title,
            "description": _description_html(article),
            "aspects": _product_aspects(article),
            "imageUrls": https_images[:24],
        },
    }

    category_id = effective_ebay_category_id(ms).strip()
    if category_id in _TCG_LEAF_CATEGORY_IDS:
        inv_payload["conditionDescriptors"] = [
            {
                "name": _CARD_CONDITION_DESCRIPTOR_NAME,
                "values": [_card_condition_descriptor_value_id(article.condition)],
            }
        ]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Content-Language": "fr-FR",
    }

    inv_url = f"{root}/sell/inventory/v1/inventory_item/{sku}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        inv_resp = await client.put(inv_url, json=inv_payload, headers=headers)
        if inv_resp.status_code not in (200, 201, 204):
            logger.warning("eBay inventory_item failed: %s %s", inv_resp.status_code, inv_resp.text[:800])
            return {
                "ok": False,
                "detail": f"ebay_inventory_error:{inv_resp.status_code}",
                "ebay_body": inv_resp.text[:2000],
            }

        offer_payload: dict[str, Any] = {
            "sku": sku,
            "marketplaceId": marketplace_id,
            "format": "FIXED_PRICE",
            "listingDuration": "GTC",
            "categoryId": effective_ebay_category_id(ms),
            "merchantLocationKey": str(ms.ebay_merchant_location_key).strip(),
            "listingPolicies": {
                "fulfillmentPolicyId": str(ms.ebay_fulfillment_policy_id).strip(),
                "paymentPolicyId": str(ms.ebay_payment_policy_id).strip(),
                "returnPolicyId": str(ms.ebay_return_policy_id).strip(),
            },
            "pricingSummary": {
                "price": {"currency": currency, "value": price_str},
            },
            "availableQuantity": 1,
            "includeCatalogProductDetails": False,
        }

        off_resp = await client.post(
            f"{root}/sell/inventory/v1/offer",
            json=offer_payload,
            headers=headers,
        )
        if off_resp.status_code not in (200, 201):
            logger.warning("eBay create offer failed: %s %s", off_resp.status_code, off_resp.text[:800])
            return {
                "ok": False,
                "detail": f"ebay_offer_error:{off_resp.status_code}",
                "ebay_body": off_resp.text[:2000],
            }
        offer_data = off_resp.json()
        offer_id = offer_data.get("offerId")
        if not offer_id:
            return {"ok": False, "detail": "ebay_missing_offer_id", "ebay_body": str(offer_data)[:1000]}

        pub_resp = await client.post(
            f"{root}/sell/inventory/v1/offer/{offer_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        if pub_resp.status_code not in (200, 201):
            logger.warning("eBay publish failed: %s %s", pub_resp.status_code, pub_resp.text[:800])
            return {
                "ok": False,
                "detail": f"ebay_publish_error:{pub_resp.status_code}",
                "ebay_body": pub_resp.text[:2000],
            }
        pub_data = pub_resp.json()
        listing_id = pub_data.get("listingId")
        if not listing_id:
            return {"ok": False, "detail": "ebay_missing_listing_id", "ebay_body": str(pub_data)[:1000]}

    return {"ok": True, "listing_id": str(listing_id), "sku": sku}
