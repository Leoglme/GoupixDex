"""Auto-setup eBay FR: inventory location + business policies (Account API)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from config import AppSettings, get_settings
from models.margin_settings import MarginSettings
from models.user import User
from services.ebay_oauth_service import _api_base_url
from services.ebay_publish_service import ensure_ebay_access_token
from services.ebay_seller_metadata_service import (
    ensure_goupixdex_fr_fulfillment_policy,
    fetch_inventory_locations,
    fetch_payment_policies,
    fetch_return_policies,
    opt_in_selling_policy_management,
)
from services.user_settings_service import ebay_listing_config_complete

logger = logging.getLogger(__name__)

MARKETPLACE_FR = "EBAY_FR"
MERCHANT_LOCATION_KEY = "goupixdex_home"


def _fr_account_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Content-Language": "fr-FR",
        "Accept-Language": "fr-FR",
        "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_FR,
    }


async def _create_inventory_location(
    token: str,
    *,
    merchant_key: str,
    name: str,
    phone: str | None,
    address_line1: str,
    address_line2: str | None,
    city: str,
    postal_code: str,
    country: str,
    app: AppSettings | None = None,
) -> None:
    s = app or get_settings()
    root = _api_base_url(s)
    url = f"{root}/sell/inventory/v1/location/{merchant_key}"
    addr: dict[str, Any] = {
        "addressLine1": address_line1.strip(),
        "city": city.strip(),
        "postalCode": postal_code.strip(),
        "country": country.strip().upper(),
    }
    if address_line2 and address_line2.strip():
        addr["addressLine2"] = address_line2.strip()
    body: dict[str, Any] = {
        "name": name.strip()[:64],
        "location": {"address": addr},
        "locationTypes": ["WAREHOUSE"],
        "merchantLocationStatus": "ENABLED",
    }
    if phone and phone.strip():
        body["phone"] = phone.strip()[:32]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=body, headers=headers)
    if resp.status_code in (200, 201, 204):
        return
    if resp.status_code in (400, 409):
        logger.info(
            "eBay createInventoryLocation: %s %s (may already exist)",
            resp.status_code,
            resp.text[:400],
        )
        return
    resp.raise_for_status()


async def _create_payment_policy_fr(token: str, *, app: AppSettings | None = None) -> str:
    s = app or get_settings()
    root = _api_base_url(s)
    # Managed Payments: do not send ``paymentMethods`` / card brands (CREDIT_CARD can trigger
    # 20403 PAYMENT_METHOD_NOT_ALLOWED on FR production).
    payload: dict[str, Any] = {
        "name": "GoupixDex — Paiement",
        "marketplaceId": MARKETPLACE_FR,
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "immediatePay": True,
    }
    url = f"{root}/sell/account/v1/payment_policy"
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers=_fr_account_headers(token))
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"eBay createPaymentPolicy: {resp.status_code} {resp.text[:2000]}")
    data = resp.json()
    pid = data.get("paymentPolicyId")
    if not pid:
        raise RuntimeError(f"eBay createPaymentPolicy missing id: {str(data)[:1500]}")
    return str(pid)


async def _create_return_policy_fr(token: str, *, app: AppSettings | None = None) -> str:
    s = app or get_settings()
    root = _api_base_url(s)
    payload: dict[str, Any] = {
        "name": "GoupixDex — Retours 30 jours",
        "marketplaceId": MARKETPLACE_FR,
        "returnsAccepted": True,
        "returnPeriod": {"value": 30, "unit": "DAY"},
        "refundMethod": "MONEY_BACK",
        "returnShippingCostPayer": "BUYER",
    }
    url = f"{root}/sell/account/v1/return_policy"
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers=_fr_account_headers(token))
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"eBay createReturnPolicy: {resp.status_code} {resp.text[:2000]}")
    data = resp.json()
    rid = data.get("returnPolicyId")
    if not rid:
        raise RuntimeError(f"eBay createReturnPolicy missing id: {str(data)[:1500]}")
    return str(rid)


async def run_ebay_onboarding(
    db: Session,
    user: User,
    ms: MarginSettings,
    *,
    location_name: str,
    phone: str,
    address_line1: str,
    address_line2: str | None,
    city: str,
    postal_code: str,
    country: str,
    app: AppSettings | None = None,
) -> dict[str, Any]:
    """
    Idempotent: reuse existing location / policies when present; otherwise create defaults for EBAY_FR.
    """
    s = app or get_settings()
    token = await ensure_ebay_access_token(db, user, app=s)
    await opt_in_selling_policy_management(token, app=s)

    ms.ebay_marketplace_id = MARKETPLACE_FR

    locs = await fetch_inventory_locations(token, app=s)
    if locs:
        ms.ebay_merchant_location_key = str(locs[0].get("merchantLocationKey") or "").strip()
    else:
        await _create_inventory_location(
            token,
            merchant_key=MERCHANT_LOCATION_KEY,
            name=location_name,
            phone=phone,
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            postal_code=postal_code,
            country=country,
            app=s,
        )
        locs2 = await fetch_inventory_locations(token, app=s)
        if not locs2:
            raise RuntimeError("eBay inventory location was not created or is not visible yet.")
        ms.ebay_merchant_location_key = str(locs2[0].get("merchantLocationKey") or "").strip()

    ms.ebay_fulfillment_policy_id = await ensure_goupixdex_fr_fulfillment_policy(token, app=s)

    pay = await fetch_payment_policies(token, MARKETPLACE_FR, app=s)
    if pay:
        ms.ebay_payment_policy_id = str(pay[0].get("paymentPolicyId") or "").strip()
    else:
        ms.ebay_payment_policy_id = await _create_payment_policy_fr(token, app=s)

    ret = await fetch_return_policies(token, MARKETPLACE_FR, app=s)
    if ret:
        ms.ebay_return_policy_id = str(ret[0].get("returnPolicyId") or "").strip()
    else:
        ms.ebay_return_policy_id = await _create_return_policy_fr(token, app=s)

    db.add(ms)
    db.commit()
    db.refresh(ms)

    return {
        "ok": True,
        "marketplace_id": MARKETPLACE_FR,
        "ebay_listing_config_complete": ebay_listing_config_complete(ms),
        "merchant_location_key": ms.ebay_merchant_location_key,
        "fulfillment_policy_id": ms.ebay_fulfillment_policy_id,
        "payment_policy_id": ms.ebay_payment_policy_id,
        "return_policy_id": ms.ebay_return_policy_id,
    }
