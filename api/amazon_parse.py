"""
Amazon HTML parsing (search + product page) — same business logic as the legacy scraper.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from amazon_config import AMAZON_BASE_URL


def parse_search_page(soup: BeautifulSoup, base_url: str = AMAZON_BASE_URL) -> List[Dict]:
    """Extract « invite-only » result rows from a search results page."""
    all_items: List[Dict] = []
    items = soup.find_all("div", {"data-component-type": "s-search-result"})

    for idx, item in enumerate(items, 1):
        try:
            invitation_span = item.find("span", {"aria-label": "Disponible sur invitation"})
            item_html = str(item)
            has_invitation_text = "Disponible sur invitation" in item_html
            has_available_for_you_text = "Disponible pour vous à l'achat" in item_html

            if not (invitation_span or has_invitation_text or has_available_for_you_text):
                continue

            asin = item.get("data-asin", "")
            if not asin:
                continue

            title_elem = item.find("h2", class_="a-size-mini")
            if not title_elem:
                title_elem = item.find("span", class_="a-size-medium")
            if not title_elem:
                title_elem = item.find("h2")
            title = title_elem.get_text(strip=True) if title_elem else "Title unavailable"

            img_elem = item.find("img", class_="s-image")
            image = img_elem.get("src", "") if img_elem else None
            product_url = f"{base_url}/dp/{asin}"

            price = None
            price_elem = item.find("span", class_="a-price")
            if price_elem:
                price_whole = price_elem.find("span", class_="a-price-whole")
                price_fraction = price_elem.find("span", class_="a-price-fraction")
                if price_whole:
                    price = price_whole.get_text(strip=True)
                    if price_fraction:
                        price += price_fraction.get_text(strip=True)
                    price += "€"

            all_items.append(
                {
                    "asin": asin,
                    "title": title,
                    "price": price,
                    "image": image,
                    "url": product_url,
                    "available_on_invitation": True,
                    "date_found": datetime.now().isoformat(),
                }
            )
        except Exception:
            continue

    return all_items


def parse_product_page(
    page_source: str,
    asin: str,
    base_url: str = AMAZON_BASE_URL,
) -> Optional[Dict]:
    """
    Return the item dict or None if the listing should be skipped (e.g. not an invite sale).
    """
    soup = BeautifulSoup(page_source, "html.parser")
    url = f"{base_url}/dp/{asin}"

    title_elem = soup.find("span", id="productTitle")
    title = title_elem.get_text(strip=True) if title_elem else "Title unavailable"

    add_to_cart = soup.find("input", id="add-to-cart-button")
    can_order = add_to_cart is not None
    if not can_order:
        add_to_cart_alt = soup.find("input", {"name": "submit.add-to-cart"})
        can_order = add_to_cart_alt is not None

    invitation_status = None
    invitation_requested = False

    if can_order:
        invitation_status = "accepted"
        invitation_requested = True
    else:
        has_invite_button_text = "Demander une invitation" in page_source
        if has_invite_button_text:
            invitation_status = "not_requested"
            invitation_requested = False
        else:
            invitation_status = "requested"
            invitation_requested = True

    price = None
    price_elem = soup.find("span", class_="a-price")
    if price_elem:
        price_whole = price_elem.find("span", class_="a-price-whole")
        price_fraction = price_elem.find("span", class_="a-price-fraction")
        if price_whole:
            price = price_whole.get_text(strip=True)
            if price_fraction:
                price += price_fraction.get_text(strip=True)
            price += "€"

    img_elem = soup.find("img", id="landingImage")
    if not img_elem:
        img_elem = soup.find("img", class_="a-dynamic-image")
    image = img_elem.get("src", "") if img_elem else None

    invitation_text = soup.find("span", {"aria-label": "Disponible sur invitation"})
    available_for_you_text = "Disponible pour vous à l'achat" in page_source
    available_on_invitation = invitation_text is not None or available_for_you_text

    if not available_on_invitation and can_order:
        return None

    if not available_on_invitation and not can_order and invitation_status == "not_requested":
        has_invite_elements = bool(
            soup.find("div", id="hdp-detail-requested-id")
            or soup.find("input", {"name": "submit.inviteButton"})
            or soup.find("span", id="hdp-invite-button")
        )
        if not has_invite_elements:
            return None

    return {
        "asin": asin,
        "title": title,
        "price": price,
        "image": image,
        "url": url,
        "available_on_invitation": available_on_invitation,
        "can_order": can_order,
        "invitation_status": invitation_status,
        "invitation_requested": invitation_requested,
        "date_found": datetime.now().isoformat(),
    }


_SLATE_PATTERNS = (
    re.compile(r'"encryptedSlateToken"\s*:\s*"([^"]+)"'),
    re.compile(r"'encryptedSlateToken'\s*:\s*'([^']+)'"),
    re.compile(
        r"x-amzn-encrypted-slate-token\s*[:=]\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    ),
    re.compile(
        r'name=["\']x-amzn-encrypted-slate-token["\'][^>]*value=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'value=["\']([^"\']+)["\'][^>]*name=["\']x-amzn-encrypted-slate-token["\']',
        re.IGNORECASE,
    ),
)


def _extract_slate_token_from_html(html: str) -> Optional[str]:
    """Token required by the `request-invite` API (often embedded in scripts / JSON state)."""
    for pat in _SLATE_PATTERNS:
        m = pat.search(html)
        if m:
            tok = m.group(1).strip()
            if len(tok) > 8:
                return tok
    meta = re.search(
        r'<meta\s+[^>]*name=["\']encrypted-slate-token["\'][^>]*content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if meta:
        return meta.group(1).strip()
    return None


def parse_hdp_invite_api_fields(page_source: str) -> Optional[Dict[str, Any]]:
    """
    Lit les champs du bloc « Demander une invitation » (buy box HDP).
    Retourne post_url (https://data.amazon.fr/...), csrf, slate_token optionnel.
    """
    soup = BeautifulSoup(page_source, "html.parser")
    csrf_el = soup.find("input", id="hdp-ib-csrf-token")
    ep_el = soup.find("input", id="hdp-ib-ajax-endpoint")
    if not csrf_el or not ep_el:
        return None
    csrf = (csrf_el.get("value") or "").strip()
    endpoint_raw = (ep_el.get("value") or "").strip()
    if not csrf or not endpoint_raw:
        return None
    post_url = endpoint_raw
    if not post_url.startswith("http"):
        post_url = "https://" + post_url.lstrip("/")

    signed_el = soup.find("input", id="hdp-ib-signedIn")
    signed_in: Optional[bool]
    if signed_el is not None:
        signed_in = (signed_el.get("value") or "").lower() == "true"
    else:
        signed_in = None

    slate_token = _extract_slate_token_from_html(page_source)

    return {
        "csrf": csrf,
        "post_url": post_url,
        "slate_token": slate_token,
        "signed_in_flag": signed_in,
    }
