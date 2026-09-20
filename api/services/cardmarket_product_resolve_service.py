"""
Résolution best-effort d'une fiche produit Cardmarket vers ``idProduct`` + nom + image.

Sert au pré-remplissage du formulaire « ajouter un produit scellé » : on récupère
l'``idProduct`` depuis la page, puis le **prix vient du guide local** (précis, sans
quota). Tout échec (blocage Cardmarket, markup inconnu) est silencieux : le front
retombe sur la saisie manuelle.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from services.cardmarket_local_price_service import get_price_api

logger = logging.getLogger(__name__)

_ALLOWED_HOST_SUFFIX = "cardmarket.com"
_REQUEST_TIMEOUT_SEC = 12.0
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

#: Motifs d'``idProduct`` rencontrés dans le HTML / le JS des fiches Cardmarket.
_ID_PRODUCT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'"idProduct"\s*:\s*"?(\d{2,})"?'),
    re.compile(r'data-id-product=["\'](\d{2,})["\']'),
    re.compile(r'[?&]idProduct=(\d{2,})'),
)
_OG_TITLE = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)
_OG_IMAGE = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)


def _is_cardmarket_url(url: str) -> bool:
    """Vrai uniquement pour un http(s) hébergé sur ``cardmarket.com`` (anti-SSRF)."""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return host == _ALLOWED_HOST_SUFFIX or host.endswith(f".{_ALLOWED_HOST_SUFFIX}")


def _first_id_product(page: str) -> int | None:
    """Premier ``idProduct`` plausible extrait du HTML."""
    for pattern in _ID_PRODUCT_PATTERNS:
        match = pattern.search(page)
        if match:
            try:
                value = int(match.group(1))
            except ValueError:
                continue
            if value > 0:
                return value
    return None


def _clean_title(raw: str) -> str:
    """Nettoie un ``og:title`` Cardmarket (déséchappe, retire le suffixe marque)."""
    title = html.unescape(raw).strip()
    for sep in (" | ", " – ", " - "):
        if sep in title:
            head = title.split(sep)[0].strip()
            if head:
                title = head
                break
    return title


def resolve_cardmarket_product(url: str) -> dict[str, Any]:
    """
    Tente de résoudre une fiche produit Cardmarket.

    Retourne ``{id_product, name, image_url, market_price_eur, error}`` — chaque
    champ pouvant être ``None``. ``error`` est renseigné quand rien n'a pu être lu.
    """
    empty: dict[str, Any] = {
        "id_product": None,
        "name": None,
        "image_url": None,
        "market_price_eur": None,
        "error": None,
    }
    if not _is_cardmarket_url(url):
        return {**empty, "error": "URL Cardmarket invalide."}

    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT_SEC, follow_redirects=True, headers=_BROWSER_HEADERS) as client:
            response = client.get(url.strip())
            response.raise_for_status()
            page = response.text
    except httpx.HTTPError as exc:
        logger.info("Résolution Cardmarket échouée (%s): %s", url, exc)
        return {**empty, "error": "Fiche Cardmarket inaccessible (saisis les champs à la main)."}

    id_product = _first_id_product(page)
    title_match = _OG_TITLE.search(page)
    image_match = _OG_IMAGE.search(page)
    name = _clean_title(title_match.group(1)) if title_match else None
    image_url = html.unescape(image_match.group(1)).strip() if image_match else None

    market_price_eur: float | None = None
    if id_product is not None:
        local = get_price_api().get_card_prices(id_product)
        if local is not None and local.reference_eur is not None:
            market_price_eur = round(local.reference_eur, 2)

    error = None if (id_product or name) else "Produit introuvable sur cette page."
    return {
        "id_product": id_product,
        "name": name,
        "image_url": image_url,
        "market_price_eur": market_price_eur,
        "error": error,
    }
