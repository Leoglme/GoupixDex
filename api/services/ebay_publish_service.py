"""Publish an article to eBay via Inventory API (inventory item → offer → publish)."""

from __future__ import annotations

import html
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
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

ProgressFn = Callable[[dict[str, Any]], Awaitable[None]]


async def _emit_ebay(
    progress: ProgressFn | None,
    step: str,
    message: str,
    *,
    detail: str | None = None,
) -> None:
    if progress is None:
        return
    ev: dict[str, Any] = {"type": "log", "step": step, "message": message}
    if detail:
        ev["detail"] = detail
    await progress(ev)


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

# TCG leaf categories (card condition descriptor required — eBay Metadata / MIP).
_TCG_LEAF_CATEGORY_IDS = frozenset({"183050", "183454", "261328"})
# Card condition descriptor (non-graded cards) — eBay name + value IDs.
_CARD_CONDITION_DESCRIPTOR_NAME = "40001"
# Maps article form « Condition » (ArticleForm.vue) + legacy DB values.
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
# Inventory item condition (conditionId) for TCG categories — from ``article.condition``.
_TCG_ITEM_CONDITION_ENUM: dict[str, str] = {
    "Mint": "USED_VERY_GOOD",
    "Near Mint": "USED_VERY_GOOD",
    "NM": "USED_VERY_GOOD",
    "Excellent": "USED_VERY_GOOD",
    "Good": "USED_GOOD",
    "Lightly Played": "USED_GOOD",
    "Played": "USED_ACCEPTABLE",
    "Poor": "USED_ACCEPTABLE",
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


def _ebay_condition_for_category(category_id: str, app_condition: str) -> str:
    """
    For TCG card categories, item condition + card descriptor must follow eBay rules
    (not ``USED_EXCELLENT`` / 3000 alone). Each article form label has an explicit mapping.
    """
    if category_id.strip() in _TCG_LEAF_CATEGORY_IDS:
        c = (app_condition or "").strip()
        return _TCG_ITEM_CONDITION_ENUM.get(c, "USED_VERY_GOOD")
    return _ebay_condition(app_condition)


def _card_condition_descriptor_value_id(app_condition: str) -> str:
    """Value ID for the Card Condition descriptor (non-graded cards); see eBay MIP."""
    key = (app_condition or "").strip()
    return _APP_TO_CARD_CONDITION_VALUE_ID.get(key, "400010")


def _extract_language_from_description(description: str) -> str | None:
    """Parse a ``Langue : …`` line from free text (e.g. card listing copy) when present."""
    if not description or not description.strip():
        return None
    for line in description.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^\s*Langue\s*:\s*(.+?)\s*$", line, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            return val[:80] if val else None
    return None


def _product_aspects_core(
    article: Article,
    *,
    category_id: str,
    marketplace_id: str,
) -> dict[str, list[str]]:
    """Stable required aspects (retried without optional FR fields if needed)."""
    aspects: dict[str, list[str]] = {"Brand": ["Pokémon"]}
    if article.pokemon_name and article.pokemon_name.strip():
        aspects["Character"] = [article.pokemon_name.strip()]
    if article.set_code:
        aspects["Set"] = [article.set_code.strip()]
    if article.card_number:
        aspects["Card Number"] = [article.card_number.strip()]
    if marketplace_id.strip().upper() == "EBAY_FR" and category_id.strip() in _TCG_LEAF_CATEGORY_IDS:
        aspects["Jeu"] = ["Pokémon"]
    return aspects


def _product_aspects_optional_fr(
    article: Article,
    *,
    category_id: str,
    marketplace_id: str,
) -> dict[str, list[str]]:
    """
    Extra fields for the French site (Type de la carte, Personnage, Langue).
    Merged on first attempt; dropped if the inventory API rejects them.
    """
    if marketplace_id.strip().upper() != "EBAY_FR" or category_id.strip() not in _TCG_LEAF_CATEGORY_IDS:
        return {}
    extra: dict[str, list[str]] = {"Type de la carte": ["Pokémon"]}
    if article.pokemon_name and article.pokemon_name.strip():
        extra["Personnage"] = [article.pokemon_name.strip()]
    lang = _extract_language_from_description(article.description or "")
    if lang:
        extra["Langue"] = [lang]
    return extra


def _merge_aspects(
    core: dict[str, list[str]],
    optional: dict[str, list[str]] | None,
) -> dict[str, list[str]]:
    out = dict(core)
    if optional:
        out.update(optional)
    return out


def _inventory_error_suggests_retry_without_optional(body: str) -> bool:
    """Heuristic: aspect / item-specifics error → retry without optional FR fields."""
    lower = body.lower()
    if "aspect" in lower or "caractéristique" in lower or "item specifics" in lower:
        return True
    if "25002" in body or "25003" in body or "25059" in body:
        return True
    if "invalid" in lower and ("value" in lower or "name" in lower):
        return True
    return False


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
    """One ``<p>`` per non-empty line (similar to the eBay.fr listing editor)."""
    plain = (article.description or "").strip()
    if not plain:
        plain = (article.title or "").strip() or " "
    text = plain.replace("\r\n", "\n").replace("\r", "\n")
    parts: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        parts.append(f"<p>{html.escape(stripped)}</p>")
    if not parts:
        return f"<p>{html.escape((article.title or '')[:500])}</p>"
    return "".join(parts)


async def publish_article_to_ebay(
    db: Session,
    article: Article,
    user: User,
    ms: MarginSettings,
    image_urls: list[str],
    *,
    app: AppSettings | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    """
    Create inventory + offer + publish. Returns ``{ "ok": True, "listing_id": "..." }`` or
    ``{ "ok": False, "detail": "..." }``.
    """
    await _emit_ebay(progress, "start", "Preparing eBay listing…")
    s = app or get_settings()
    if not ms.ebay_enabled:
        await _emit_ebay(progress, "error", "eBay is disabled in settings.", detail="ebay_disabled")
        return {"ok": False, "detail": "ebay_disabled"}
    if not ebay_listing_config_complete(ms):
        await _emit_ebay(
            progress,
            "error",
            "eBay setup incomplete (category, location, policies).",
            detail="ebay_listing_config_incomplete",
        )
        return {"ok": False, "detail": "ebay_listing_config_incomplete"}

    https_images = [u.strip() for u in image_urls if u.startswith("https://")]
    if not https_images:
        await _emit_ebay(progress, "error", "At least one HTTPS image is required.", detail="ebay_requires_https_images")
        return {"ok": False, "detail": "ebay_requires_https_images"}

    try:
        await _emit_ebay(progress, "auth", "Connecting to the eBay API…")
        token = await ensure_ebay_access_token(db, user, app=s)
    except Exception as exc:
        # Covers RuntimeError (ebay_not_connected, ebay_oauth_not_configured, …)
        # and EbayOAuthError (invalid_scope, invalid_grant, …). We must not let
        # httpx.HTTPStatusError escape: the "auth → error" log has to be emitted
        # so the publish journal always shows the real reason.
        logger.warning("eBay token acquisition failed for user=%s: %s", user.id, exc)
        detail = str(exc) or exc.__class__.__name__
        await _emit_ebay(progress, "error", "Could not obtain an eBay token.", detail=detail)
        return {"ok": False, "detail": detail}

    await _emit_ebay(progress, "auth", "eBay token obtained.")
    root = _api_base_url(s)
    marketplace_id = (ms.ebay_marketplace_id or "EBAY_FR").strip()
    currency = _currency_for_marketplace(marketplace_id)
    sku = _sku_for_listing(article.id)
    title = (article.title or "Carte Pokémon").strip()[:80]
    price = _listing_price_eur(article)
    price_str = f"{price.quantize(Decimal('0.01'))}"

    category_id = effective_ebay_category_id(ms).strip()
    core_aspects = _product_aspects_core(article, category_id=category_id, marketplace_id=marketplace_id)
    optional_fr_aspects = _product_aspects_optional_fr(
        article, category_id=category_id, marketplace_id=marketplace_id
    )

    inv_payload: dict[str, Any] = {
        "availability": {"shipToLocationAvailability": {"quantity": 1}},
        "condition": _ebay_condition_for_category(category_id, article.condition),
        "conditionDescription": html.escape((article.condition or "")[:1000]),
        "product": {
            "title": title,
            "description": _description_html(article),
            "aspects": _merge_aspects(core_aspects, optional_fr_aspects or None),
            "imageUrls": https_images[:24],
        },
    }

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
        await _emit_ebay(progress, "inventory", "Sending inventory item (SKU, photos, listing body)…")
        inv_resp = await client.put(inv_url, json=inv_payload, headers=headers)
        if inv_resp.status_code not in (200, 201, 204) and optional_fr_aspects:
            if inv_resp.status_code == 400 or _inventory_error_suggests_retry_without_optional(
                inv_resp.text
            ):
                await _emit_ebay(
                    progress,
                    "inventory",
                    "Optional item specifics (card type, character, language) rejected — retrying without them.",
                )
                inv_payload["product"]["aspects"] = core_aspects
                inv_resp = await client.put(inv_url, json=inv_payload, headers=headers)
        if inv_resp.status_code not in (200, 201, 204):
            logger.warning("eBay inventory_item failed: %s %s", inv_resp.status_code, inv_resp.text[:800])
            await _emit_ebay(
                progress,
                "error",
                "Failed to create or update the inventory item.",
                detail=f"HTTP {inv_resp.status_code}",
            )
            return {
                "ok": False,
                "detail": f"ebay_inventory_error:{inv_resp.status_code}",
                "ebay_body": inv_resp.text[:2000],
            }

        await _emit_ebay(progress, "inventory", "Inventory saved on eBay.")
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
            "bestOfferTerms": {"bestOfferEnabled": True},
        }

        await _emit_ebay(progress, "offer", "Creating offer (price, policies, best offer)…")
        off_resp = await client.post(
            f"{root}/sell/inventory/v1/offer",
            json=offer_payload,
            headers=headers,
        )
        if off_resp.status_code not in (200, 201) and offer_payload.get("bestOfferTerms"):
            await _emit_ebay(
                progress,
                "offer",
                "Best offer rejected by the API — retrying without best offer.",
            )
            offer_payload.pop("bestOfferTerms", None)
            off_resp = await client.post(
                f"{root}/sell/inventory/v1/offer",
                json=offer_payload,
                headers=headers,
            )
        if off_resp.status_code not in (200, 201):
            logger.warning("eBay create offer failed: %s %s", off_resp.status_code, off_resp.text[:800])
            await _emit_ebay(
                progress,
                "error",
                "Failed to create the offer.",
                detail=f"HTTP {off_resp.status_code}",
            )
            return {
                "ok": False,
                "detail": f"ebay_offer_error:{off_resp.status_code}",
                "ebay_body": off_resp.text[:2000],
            }
        offer_data = off_resp.json()
        offer_id = offer_data.get("offerId")
        if not offer_id:
            await _emit_ebay(progress, "error", "eBay response missing offer id.", detail="ebay_missing_offer_id")
            return {"ok": False, "detail": "ebay_missing_offer_id", "ebay_body": str(offer_data)[:1000]}

        await _emit_ebay(progress, "offer", f"Offer created (offerId {offer_id}).")
        await _emit_ebay(progress, "publish", "Publishing the listing…")
        pub_resp = await client.post(
            f"{root}/sell/inventory/v1/offer/{offer_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        if pub_resp.status_code not in (200, 201):
            logger.warning("eBay publish failed: %s %s", pub_resp.status_code, pub_resp.text[:800])
            await _emit_ebay(
                progress,
                "error",
                "Failed to publish the listing.",
                detail=f"HTTP {pub_resp.status_code}",
            )
            return {
                "ok": False,
                "detail": f"ebay_publish_error:{pub_resp.status_code}",
                "ebay_body": pub_resp.text[:2000],
            }
        pub_data = pub_resp.json()
        listing_id = pub_data.get("listingId")
        if not listing_id:
            await _emit_ebay(progress, "error", "eBay response missing listing id.", detail="ebay_missing_listing_id")
            return {"ok": False, "detail": "ebay_missing_listing_id", "ebay_body": str(pub_data)[:1000]}

    await _emit_ebay(
        progress,
        "done",
        "Listing published on eBay.",
        detail=f"listingId={listing_id}",
    )
    return {"ok": True, "listing_id": str(listing_id), "sku": sku}
