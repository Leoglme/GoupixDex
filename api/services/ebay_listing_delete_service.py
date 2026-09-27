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


async def _end_offer_listing(
    client: httpx.AsyncClient,
    root: str,
    headers: dict[str, str],
    offer: dict[str, Any],
) -> bool:
    """
    Met fin à l’annonce d’une offre eBay, puis supprime l’offre.

    Returns:
        Vrai dès que l’annonce n’est plus en ligne, même si la suppression de l’offre a échoué.
    """
    offer_id = str(offer.get("offerId") or "").strip()
    has_listing_ended = str(offer.get("status") or "").upper() != "PUBLISHED"
    if not has_listing_ended:
        withdraw_response = await client.post(f"{root}/sell/inventory/v1/offer/{offer_id}/withdraw", headers=headers)
        has_listing_ended = withdraw_response.status_code in (200, 204)
        if not has_listing_ended:
            logger.warning(
                "eBay withdraw failed offer=%s: %s %s",
                offer_id,
                withdraw_response.status_code,
                withdraw_response.text[:300],
            )
    try:
        # Supprimer une offre encore publiée met aussi fin à son annonce.
        delete_response = await client.delete(f"{root}/sell/inventory/v1/offer/{offer_id}", headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("eBay deleteOffer unreachable offer=%s: %r", offer_id, exc)
        return has_listing_ended
    if delete_response.status_code in (200, 204, 404):
        return True
    logger.warning(
        "eBay deleteOffer failed offer=%s: %s %s",
        offer_id,
        delete_response.status_code,
        delete_response.text[:300],
    )
    return has_listing_ended


async def _delete_inventory_item(client: httpx.AsyncClient, root: str, headers: dict[str, str], sku: str) -> None:
    """Supprime l’article d’inventaire eBay d’un SKU dont l’annonce est terminée ; un échec est seulement journalisé."""
    try:
        response = await client.delete(f"{root}/sell/inventory/v1/inventory_item/{sku}", headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("eBay deleteInventoryItem unreachable sku=%s: %r", sku, exc)
        return
    if response.status_code not in (200, 204, 404):
        logger.warning("eBay deleteInventoryItem failed sku=%s: %s %s", sku, response.status_code, response.text[:300])


async def delete_ebay_listing_for_article(
    db: Session,
    article: Article,
    user: User,
    *,
    app: AppSettings | None = None,
) -> tuple[bool, str | None]:
    """
    Met fin à l’annonce eBay de cet article, puis supprime son offre et son inventaire.

    Returns:
        ``(ok, message_erreur_fr)`` : ``ok`` dès que l’annonce n’est plus en ligne sur eBay, même si le ménage de l’offre ou de l’inventaire échoue.
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

    try:
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
            # eBay répond 404 quand plus aucune offre n’existe pour ce SKU : l’annonce n’est plus en ligne.
            if off_r.status_code == 404:
                await _delete_inventory_item(client, root, headers, sku)
                return True, None
            if off_r.status_code != 200:
                return False, f"Lecture des offres eBay impossible (HTTP {off_r.status_code})."
            offers: list[dict[str, Any]] = (off_r.json() or {}).get("offers") or []
            for offer in offers:
                if not str(offer.get("offerId") or "").strip():
                    continue
                if not await _end_offer_listing(client, root, headers, offer):
                    return False, "eBay n’a pas mis fin à l’annonce : réessayez dans quelques minutes."
            await _delete_inventory_item(client, root, headers, sku)
    except httpx.HTTPError as exc:
        logger.warning("eBay listing removal unreachable article=%s: %r", article.id, exc)
        return False, "eBay ne répond pas pour le moment : réessayez dans quelques minutes."

    return True, None


def clear_ebay_publication_fields(article: Article) -> None:
    article.published_on_ebay = False
    article.ebay_listing_id = None
    article.ebay_inventory_sku = None
    article.ebay_published_at = None
