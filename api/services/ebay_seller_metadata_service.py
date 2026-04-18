"""Fetch eBay merchant locations and business policies for setup UI."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import AppSettings, get_settings
from services.ebay_oauth_service import _api_base_url

logger = logging.getLogger(__name__)

# Locale per marketplace (eBay REST request components) for Account API policy calls.
_MARKETPLACE_LOCALE: dict[str, str] = {
    "EBAY_US": "en-US",
    "EBAY_MOTORS_US": "en-US",
    "EBAY_AT": "de-AT",
    "EBAY_AU": "en-AU",
    "EBAY_BE": "fr-BE",
    "EBAY_CA": "fr-CA",
    "EBAY_CH": "de-CH",
    "EBAY_DE": "de-DE",
    "EBAY_ES": "es-ES",
    "EBAY_FR": "fr-FR",
    "EBAY_GB": "en-GB",
    "EBAY_HK": "zh-HK",
    "EBAY_IE": "en-IE",
    "EBAY_IT": "it-IT",
    "EBAY_MY": "en-US",
    "EBAY_NL": "nl-NL",
    "EBAY_PH": "en-PH",
    "EBAY_PL": "pl-PL",
    "EBAY_SG": "en-US",
    "EBAY_TW": "zh-TW",
}


def _marketplace_locale(marketplace_id: str) -> str:
    return _MARKETPLACE_LOCALE.get(marketplace_id.strip().upper(), "en-US")


def _marketplace_header(marketplace_id: str) -> dict[str, str]:
    return {"X-EBAY-C-MARKETPLACE-ID": marketplace_id.strip()}


def _account_api_headers(access_token: str, marketplace_id: str) -> dict[str, str]:
    loc = _marketplace_locale(marketplace_id)
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Content-Language": loc,
        "Accept-Language": loc,
        **_marketplace_header(marketplace_id),
    }


async def opt_in_selling_policy_management(access_token: str, *, app: AppSettings | None = None) -> None:
    """
    Opt seller into Business Policies (SELLING_POLICY_MANAGEMENT).
    Fixes "User is not eligible for Business Policy" on getFulfillmentPolicies; eBay may take up to ~24h
    to process (see getOptedInPrograms).
    """
    s = app or get_settings()
    root = _api_base_url(s)
    url = f"{root}/sell/account/v1/program/opt_in"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            json={"programType": "SELLING_POLICY_MANAGEMENT"},
            headers=headers,
        )
    if resp.status_code == 200:
        logger.info("eBay opt_in SELLING_POLICY_MANAGEMENT: OK")
        return
    if resp.status_code in (409, 400):
        logger.info(
            "eBay opt_in SELLING_POLICY_MANAGEMENT: %s %s (often already opted in or pending)",
            resp.status_code,
            resp.text[:400],
        )
        return
    logger.warning("eBay opt_in SELLING_POLICY_MANAGEMENT: %s %s", resp.status_code, resp.text[:500])


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
    headers = _account_api_headers(access_token, marketplace_id)
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
    headers = _account_api_headers(access_token, marketplace_id)
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


# Fulfillment policy created/updated via Account API (createFulfillmentPolicy / updateFulfillmentPolicy).
GOUPIXDEX_FR_FULFILLMENT_POLICY_NAME = "GoupixDex — Envoi"


def _eur_amount(value: str) -> dict[str, str]:
    return {"value": value, "currency": "EUR"}


def goupixdex_fr_fulfillment_policy_request_body() -> dict[str, Any]:
    """
    Same intent as the FR seller UI: multiple paid domestic options, international,
    max handling time 3 days (handlingTime).
    Service codes: eBay FR enums (see ShippingService / business policy docs).
    """
    return {
        "name": GOUPIXDEX_FR_FULFILLMENT_POLICY_NAME,
        "marketplaceId": "EBAY_FR",
        "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
        "handlingTime": {"value": 3, "unit": "DAY"},
        "globalShipping": False,
        "shippingOptions": [
            {
                "costType": "FLAT_RATE",
                "optionType": "DOMESTIC",
                "shippingServices": [
                    {
                        "sortOrder": 1,
                        "shippingServiceCode": "FR_Ecopli",
                        "shippingCost": _eur_amount("1.8"),
                        "additionalShippingCost": _eur_amount("0.0"),
                        "freeShipping": False,
                        "buyerResponsibleForShipping": False,
                    },
                    {
                        "sortOrder": 2,
                        "shippingServiceCode": "FR_PostOfficeLetterFollowed",
                        "shippingCost": _eur_amount("2.5"),
                        "additionalShippingCost": _eur_amount("0.0"),
                        "freeShipping": False,
                        "buyerResponsibleForShipping": False,
                    },
                    {
                        "sortOrder": 3,
                        "shippingServiceCode": "FR_LivraisonEnRelaisMondialRelay",
                        "shippingCost": _eur_amount("4.5"),
                        "additionalShippingCost": _eur_amount("0.0"),
                        "freeShipping": False,
                        "buyerResponsibleForShipping": False,
                    },
                    {
                        "sortOrder": 4,
                        "shippingServiceCode": "FR_ColiposteColissimo",
                        "shippingCost": _eur_amount("5.5"),
                        "additionalShippingCost": _eur_amount("0.0"),
                        "freeShipping": False,
                        "buyerResponsibleForShipping": False,
                    },
                ],
            },
            {
                "costType": "FLAT_RATE",
                "optionType": "INTERNATIONAL",
                "shippingServices": [
                    {
                        "sortOrder": 1,
                        "shippingServiceCode": "FR_LaPosteInternationalPriorityCourier",
                        "shippingCost": _eur_amount("2.5"),
                        "additionalShippingCost": _eur_amount("0.0"),
                        "freeShipping": False,
                        "buyerResponsibleForShipping": False,
                        "shipToLocations": {"regionIncluded": [{"regionName": "Worldwide"}]},
                    },
                    {
                        "sortOrder": 2,
                        "shippingServiceCode": "FR_LaPosteLetterSuivieIntl",
                        "shippingCost": _eur_amount("5.5"),
                        "additionalShippingCost": _eur_amount("0.0"),
                        "freeShipping": False,
                        "buyerResponsibleForShipping": False,
                        "shipToLocations": {"regionIncluded": [{"regionName": "Worldwide"}]},
                    },
                ],
            },
        ],
    }


async def ensure_goupixdex_fr_fulfillment_policy(
    access_token: str,
    *,
    app: AppSettings | None = None,
) -> str:
    """
    Creates or updates (PUT) the « GoupixDex — Envoi » policy for EBAY_FR via the Account API.
    Returns ``fulfillmentPolicyId`` to store in user settings.
    """
    s = app or get_settings()
    root = _api_base_url(s)
    mp = "EBAY_FR"
    existing = await fetch_fulfillment_policies(access_token, mp, app=s)
    body = goupixdex_fr_fulfillment_policy_request_body()
    headers = _account_api_headers(access_token, mp)

    async with httpx.AsyncClient(timeout=120.0) as client:
        match = next(
            (
                p
                for p in existing
                if (p.get("name") or "").strip() == GOUPIXDEX_FR_FULFILLMENT_POLICY_NAME
            ),
            None,
        )
        if match and match.get("fulfillmentPolicyId"):
            pid = str(match["fulfillmentPolicyId"])
            url = f"{root}/sell/account/v1/fulfillment_policy/{pid}"
            resp = await client.put(url, json=body, headers=headers)
        else:
            url = f"{root}/sell/account/v1/fulfillment_policy"
            resp = await client.post(url, json=body, headers=headers)

    if resp.status_code not in (200, 201):
        logger.warning("eBay fulfillment policy ensure failed: %s %s", resp.status_code, resp.text[:2500])
        raise RuntimeError(f"eBay fulfillment policy: {resp.status_code} {resp.text[:2000]}")

    try:
        data = resp.json() if resp.content else {}
    except Exception:  # noqa: BLE001
        data = {}
    fid = data.get("fulfillmentPolicyId")
    if not fid and match and match.get("fulfillmentPolicyId"):
        fid = match["fulfillmentPolicyId"]
    if not fid:
        raise RuntimeError(f"eBay fulfillment policy: missing id in {str(data)[:1500]}")
    return str(fid)


async def fetch_return_policies(
    access_token: str,
    marketplace_id: str,
    *,
    app: AppSettings | None = None,
) -> list[dict[str, Any]]:
    s = app or get_settings()
    root = _api_base_url(s)
    url = f"{root}/sell/account/v1/return_policy"
    headers = _account_api_headers(access_token, marketplace_id)
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
