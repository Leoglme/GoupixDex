"""eBay Fulfillment API: list buyer orders pending shipment (for label generation)."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import httpx

from config import AppSettings, get_settings
from services.ebay_oauth_service import _api_base_url

logger = logging.getLogger(__name__)


def _orders_url(app: AppSettings) -> str:
    return f"{_api_base_url(app)}/sell/fulfillment/v1/order"


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


async def list_unshipped_orders(
    access_token: str,
    *,
    app: AppSettings | None = None,
    days_back: int = 90,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Return orders whose fulfillment status is ``NOT_STARTED`` or ``IN_PROGRESS`` (i.e. not yet
    fully shipped) created within the last ``days_back`` days.

    Uses the ``filter`` query syntax of the Fulfillment API:
    ``orderfulfillmentstatus:{NOT_STARTED|IN_PROGRESS},creationdate:[<from>..]``.
    """
    s = app or get_settings()
    url = _orders_url(s)

    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=max(1, int(days_back)))
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    fulfillment_filter = "orderfulfillmentstatus:%7BNOT_STARTED%7CIN_PROGRESS%7D"
    creation_filter = f"creationdate:%5B{since_iso}..%5D"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    out: list[dict[str, Any]] = []
    offset = 0
    page_size = 50

    async with httpx.AsyncClient(timeout=60.0) as client:
        while len(out) < limit:
            params_qs = (
                f"filter={fulfillment_filter},{creation_filter}"
                f"&limit={page_size}&offset={offset}"
            )
            full_url = f"{url}?{params_qs}"
            resp = await client.get(full_url, headers=headers)
            if resp.status_code == 204:
                break
            if resp.status_code >= 400:
                logger.warning("eBay getOrders failed: %s %s", resp.status_code, resp.text[:500])
                resp.raise_for_status()
            data = resp.json() if resp.content else {}
            orders = data.get("orders") or []
            if not isinstance(orders, list) or not orders:
                break
            for raw in orders:
                if not isinstance(raw, dict):
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
