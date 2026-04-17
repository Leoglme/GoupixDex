"""Fetch eBay merchant locations and business policies for setup UI."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import AppSettings, get_settings
from services.ebay_oauth_service import _api_base_url

logger = logging.getLogger(__name__)


def _marketplace_header(marketplace_id: str) -> dict[str, str]:
    return {"X-EBAY-C-MARKETPLACE-ID": marketplace_id.strip()}


async def fetch_inventory_locations(access_token: str, *, app: AppSettings | None = None) -> list[dict[str, Any]]:
    s = app or get_settings()
    root = _api_base_url(s)
    url = f"{root}/sell/inventory/v1/location"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code >= 400:
        logger.warning("eBay locations: %s %s", resp.status_code, resp.text[:400])
        resp.raise_for_status()
    data = resp.json()
    locs = data.get("locations") or []
    out: list[dict[str, Any]] = []
    for row in locs:
        if not isinstance(row, dict):
            continue
        key = row.get("merchantLocationKey")
        if not key:
            continue
        out.append(
            {
                "merchantLocationKey": key,
                "name": row.get("name"),
            },
        )
    return out


async def fetch_fulfillment_policies(
    access_token: str,
    marketplace_id: str,
    *,
    app: AppSettings | None = None,
) -> list[dict[str, Any]]:
    s = app or get_settings()
    root = _api_base_url(s)
    url = f"{root}/sell/account/v1/fulfillment_policy"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        **_marketplace_header(marketplace_id),
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, params={"marketplace_id": marketplace_id}, headers=headers)
    if resp.status_code >= 400:
        logger.warning("eBay fulfillment policies: %s %s", resp.status_code, resp.text[:400])
        resp.raise_for_status()
    data = resp.json()
    rows = data.get("fulfillmentPolicies") or []
    return [
        {"fulfillmentPolicyId": str(r.get("fulfillmentPolicyId")), "name": r.get("name")}
        for r in rows
        if isinstance(r, dict) and r.get("fulfillmentPolicyId") is not None
    ]


async def fetch_payment_policies(
    access_token: str,
    marketplace_id: str,
    *,
    app: AppSettings | None = None,
) -> list[dict[str, Any]]:
    s = app or get_settings()
    root = _api_base_url(s)
    url = f"{root}/sell/account/v1/payment_policy"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        **_marketplace_header(marketplace_id),
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, params={"marketplace_id": marketplace_id}, headers=headers)
    if resp.status_code >= 400:
        logger.warning("eBay payment policies: %s %s", resp.status_code, resp.text[:400])
        resp.raise_for_status()
    data = resp.json()
    rows = data.get("paymentPolicies") or []
    return [
        {"paymentPolicyId": str(r.get("paymentPolicyId")), "name": r.get("name")}
        for r in rows
        if isinstance(r, dict) and r.get("paymentPolicyId") is not None
    ]


async def fetch_return_policies(
    access_token: str,
    marketplace_id: str,
    *,
    app: AppSettings | None = None,
) -> list[dict[str, Any]]:
    s = app or get_settings()
    root = _api_base_url(s)
    url = f"{root}/sell/account/v1/return_policy"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        **_marketplace_header(marketplace_id),
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, params={"marketplace_id": marketplace_id}, headers=headers)
    if resp.status_code >= 400:
        logger.warning("eBay return policies: %s %s", resp.status_code, resp.text[:400])
        resp.raise_for_status()
    data = resp.json()
    rows = data.get("returnPolicies") or []
    return [
        {"returnPolicyId": str(r.get("returnPolicyId")), "name": r.get("name")}
        for r in rows
        if isinstance(r, dict) and r.get("returnPolicyId") is not None
    ]
