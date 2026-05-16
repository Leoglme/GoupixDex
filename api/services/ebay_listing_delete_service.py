"""Retrait définitif d’une annonce eBay (Inventory API : withdraw → delete offer → delete SKU)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from config import AppSettings, get_settings
from models.article import Article
from models.user import User
from services.ebay_oauth_service import _api_base_url
from services.ebay_publish_service import ensure_ebay_access_token

logger = logging.getLogger(__name__)

_MAX_SKU_SCAN = 400


async def _find_sku_for_listing_id(
    client: httpx.AsyncClient,
    root: str,
    token: str,
    listing_id: str,
) -> str | None:
    """Parcourt les SKU inventaire jusqu’à trouver une offre dont le listingId correspond."""
    want = str(listing_id).strip()
    if not want:
        return None
    offset = 0
    limit = 50
    scanned = 0
    headers = {"Authorization": f"Bearer {token}"}
    while scanned < _MAX_SKU_SCAN:
        r = await client.get(
            f"{root}/sell/inventory/v1/inventory_item",
            params={"limit": limit, "offset": offset},
            headers=headers,
        )
        if r.status_code != 200:
            logger.warning("eBay getInventoryItems failed: %s %s", r.status_code, r.text[:400])
            return None
        data = r.json()
        items = data.get("inventoryItems") or []
        if not isinstance(items, list) or not items:
            return None
        for inv in items:
            if scanned >= _MAX_SKU_SCAN:
                break
            sku = (inv.get("sku") or "").strip()
            if not sku:
                continue
            scanned += 1
            off_r = await client.get(
                f"{root}/sell/inventory/v1/offer",
                params={"sku": sku},
                headers=headers,
            )
            if off_r.status_code != 200:
                continue
            offers = (off_r.json() or {}).get("offers") or []
            for off in offers:
                listing = off.get("listing") or {}
                lid = str(listing.get("listingId") or "").strip()
                if lid == want:
                    return sku
        if len(items) < limit:
            break
        offset += limit
    return None


async def delete_ebay_listing_for_article(
    db: Session,
    article: Article,
    user: User,
    *,
    app: AppSettings | None = None,
) -> tuple[bool, str | None]:
    """
    Retire puis supprime l’offre et l’inventaire eBay pour cet article.

    Returns:
        ``(ok, message_erreur_fr)`` — ``message_erreur_fr`` est ``None`` si succès ou rien à faire.
    """
    s = app or get_settings()
    if not s.ebay_client_id or not article.published_on_ebay:
        return True, None
    if not article.ebay_listing_id and not article.ebay_inventory_sku:
        return True, None

    try:
        token = await ensure_ebay_access_token(db, user, app=s)
    except Exception as exc:  # noqa: BLE001
        logger.warning("eBay token for delete failed user=%s: %s", user.id, exc)
        return False, "Connexion eBay indisponible ou token expiré. Reconnectez-vous dans Paramètres."

    root = _api_base_url(s)
    sku = (article.ebay_inventory_sku or "").strip() or None
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=90.0) as client:
        if not sku and article.ebay_listing_id:
            sku = await _find_sku_for_listing_id(client, root, token, str(article.ebay_listing_id))
            if sku:
                article.ebay_inventory_sku = sku[:50]
                db.add(article)
                db.commit()
        if not sku:
            return False, "SKU eBay introuvable pour cette annonce (réimportez ou supprimez-la sur eBay.fr)."

        off_r = await client.get(f"{root}/sell/inventory/v1/offer", params={"sku": sku}, headers=headers)
        if off_r.status_code != 200:
            return False, f"Lecture des offres eBay impossible (HTTP {off_r.status_code})."
        offers: list[dict[str, Any]] = (off_r.json() or {}).get("offers") or []
        if not offers:
            return True, None

        for off in offers:
            offer_id = (off.get("offerId") or "").strip()
            if not offer_id:
                continue
            status = (off.get("status") or "").upper()
            if status == "PUBLISHED":
                w = await client.post(
                    f"{root}/sell/inventory/v1/offer/{offer_id}/withdraw",
                    headers=headers,
                )
                if w.status_code not in (200, 204):
                    logger.warning(
                        "eBay withdraw non bloquant offer=%s: %s %s",
                        offer_id,
                        w.status_code,
                        w.text[:300],
                    )

            d = await client.delete(f"{root}/sell/inventory/v1/offer/{offer_id}", headers=headers)
            if d.status_code not in (200, 204):
                logger.warning("eBay deleteOffer failed offer=%s: %s %s", offer_id, d.status_code, d.text[:500])
                return False, "Impossible de supprimer l’offre eBay."

        inv_d = await client.delete(f"{root}/sell/inventory/v1/inventory_item/{sku}", headers=headers)
        if inv_d.status_code not in (200, 204):
            logger.warning("eBay deleteInventoryItem failed sku=%s: %s %s", sku, inv_d.status_code, inv_d.text[:500])
            return False, "L’offre est retirée mais la suppression de l’inventaire eBay a échoué."

    return True, None


def clear_ebay_publication_fields(article: Article) -> None:
    article.published_on_ebay = False
    article.ebay_listing_id = None
    article.ebay_inventory_sku = None
    article.ebay_published_at = None
