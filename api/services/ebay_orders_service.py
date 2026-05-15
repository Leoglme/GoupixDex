"""eBay Fulfillment API: list buyer orders pending shipment (for label generation)."""

from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from config import AppSettings, get_settings
from services.ebay_oauth_service import EbayOAuthError, _api_base_url

logger = logging.getLogger(__name__)

_PENDING_FULFILLMENT = frozenset({"NOT_STARTED", "IN_PROGRESS"})


def _orders_url(app: AppSettings) -> str:
    return f"{_api_base_url(app)}/sell/fulfillment/v1/order"


def _fulfillment_headers(access_token: str, marketplace_id: str) -> dict[str, str]:
    mp = (marketplace_id or "EBAY_FR").strip() or "EBAY_FR"
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Language": "fr-FR",
        "X-EBAY-C-MARKETPLACE-ID": mp,
    }


def _parse_ebay_error_body(text: str) -> str:
    try:
        payload = json.loads(text) if text else {}
    except ValueError:
        return text[:400] if text else ""
    if not isinstance(payload, dict):
        return text[:400] if text else ""
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        parts: list[str] = []
        for err in errors:
            if not isinstance(err, dict):
                continue
            msg = str(err.get("longMessage") or err.get("message") or "").strip()
            eid = err.get("errorId")
            if msg:
                parts.append(f"[{eid}] {msg}" if eid is not None else msg)
        if parts:
            return " · ".join(parts)
    return str(payload.get("message") or payload)[:400]


def _fulfillment_access_denied_message(ebay_detail: str) -> str:
    base = (
        "Accès refusé à l'API Fulfillment eBay (commandes acheteur). "
        "Vérifiez que votre application **production** sur developer.ebay.com inclut le scope "
        "« sell.fulfillment » (OAuth Scopes), puis révoquez GoupixDex dans vos paramètres eBay "
        "(Confidentialité → Applications tierces) et reconnectez-vous."
    )
    if ebay_detail:
        return f"{base} Détail eBay : {ebay_detail}"
    return base


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_ship_to(order: dict[str, Any]) -> dict[str, Any] | None:
    """
    Pull buyer name + shipping address from a Fulfillment API order payload.

    The address lives under ``fulfillmentStartInstructions[*].shippingStep.shipTo`` and
    ``shippingStep.shipTo.contactAddress`` (postal address structure with addressLine1, city,
    stateOrProvince, postalCode, countryCode).
    """
    instructions = order.get("fulfillmentStartInstructions") or []
    if not isinstance(instructions, list):
        return None
    for inst in instructions:
        if not isinstance(inst, dict):
            continue
        ship = inst.get("shippingStep") or {}
        ship_to = ship.get("shipTo") if isinstance(ship, dict) else None
        if isinstance(ship_to, dict):
            return ship_to
    return None


def _normalize_order(order: dict[str, Any]) -> dict[str, Any] | None:
    """Reshape an eBay order into the minimal payload our shipping-label UI consumes."""
    order_id = _safe_str(order.get("orderId"))
    if not order_id:
        return None

    ship_to = _extract_ship_to(order) or {}
    full_name = _safe_str(ship_to.get("fullName"))
    contact_addr = ship_to.get("contactAddress") if isinstance(ship_to, dict) else None
    addr = contact_addr if isinstance(contact_addr, dict) else {}

    line1 = _safe_str(addr.get("addressLine1"))
    line2 = _safe_str(addr.get("addressLine2")) or None
    city = _safe_str(addr.get("city"))
    state = _safe_str(addr.get("stateOrProvince")) or None
    postal_code = _safe_str(addr.get("postalCode"))
    country_code = _safe_str(addr.get("countryCode")).upper()

    line_items = order.get("lineItems") or []
    items_summary: list[dict[str, Any]] = []
    if isinstance(line_items, list):
        for li in line_items:
            if not isinstance(li, dict):
                continue
            items_summary.append(
                {
                    "title": _safe_str(li.get("title")),
                    "sku": _safe_str(li.get("sku")) or None,
                    "quantity": int(li.get("quantity") or 1),
                    "line_item_id": _safe_str(li.get("lineItemId")) or None,
                }
            )

    creation_date = _safe_str(order.get("creationDate")) or None
    fulfillment_status = _safe_str(order.get("orderFulfillmentStatus")) or None

    return {
        "order_id": order_id,
        "creation_date": creation_date,
        "order_fulfillment_status": fulfillment_status,
        "buyer_username": _safe_str(order.get("buyer", {}).get("username")) or None
        if isinstance(order.get("buyer"), dict)
        else None,
        "address": {
            "full_name": full_name,
            "line1": line1,
            "line2": line2,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country_code": country_code,
        },
        "items": items_summary,
    }


def _parse_creation_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.UTC)
        return parsed
    except ValueError:
        return None


def _order_matches_pending_filters(
    order: dict[str, Any],
    *,
    since: dt.datetime,
) -> bool:
    status = _safe_str(order.get("orderFulfillmentStatus")).upper()
    if status not in _PENDING_FULFILLMENT:
        return False
    created = _parse_creation_date(_safe_str(order.get("creationDate")) or None)
    if created is not None and created < since:
        return False
    return True


def _raise_for_fulfillment_error(resp: httpx.Response) -> None:
    ebay_detail = _parse_ebay_error_body(resp.text)
    if resp.status_code == 403:
        raise EbayOAuthError(
            "ebay_fulfillment_denied",
            _fulfillment_access_denied_message(ebay_detail),
            status=403,
        )
    resp.raise_for_status()


async def list_unshipped_orders(
    access_token: str,
    *,
    app: AppSettings | None = None,
    marketplace_id: str = "EBAY_FR",
    days_back: int = 90,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Return orders whose fulfillment status is ``NOT_STARTED`` or ``IN_PROGRESS`` (i.e. not yet
    fully shipped) created within the last ``days_back`` days.

    Uses ``getOrders`` without server-side ``filter`` (filtered client-side). Some tokens /
    app configs return 403 when combining ``orderfulfillmentstatus`` + ``creationdate`` filters
    despite valid ``sell.fulfillment`` scope; the default endpoint returns the last 90 days.
    """
    s = app or get_settings()
    url = _orders_url(s)
    headers = _fulfillment_headers(access_token, marketplace_id)

    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=max(1, int(days_back)))

    out: list[dict[str, Any]] = []
    offset = 0
    page_size = 50

    async with httpx.AsyncClient(timeout=60.0) as client:
        while len(out) < limit:
            qs = urlencode({"limit": page_size, "offset": offset})
            resp = await client.get(f"{url}?{qs}", headers=headers)
            if resp.status_code == 204:
                break
            if resp.status_code >= 400:
                logger.warning("eBay getOrders failed: %s %s", resp.status_code, resp.text[:800])
                _raise_for_fulfillment_error(resp)
            data = resp.json() if resp.content else {}
            orders = data.get("orders") or []
            if not isinstance(orders, list) or not orders:
                break
            for raw in orders:
                if not isinstance(raw, dict):
                    continue
                if not _order_matches_pending_filters(raw, since=since):
                    continue
                normalized = _normalize_order(raw)
                if normalized:
                    out.append(normalized)
                    if len(out) >= limit:
                        break
            if len(orders) < page_size:
                break
            offset += page_size

    return out
