"""
Cartes TCGdex qui manquent à un index de scan livré avec le site, avec l'image qui servira à les calculer.

Les deux index du scanner (``web/public/scan-index`` : empreintes pHash de l'illustration, embeddings MobileCLIP-S0)
sont figés à leur génération. Chaque nuit, leurs services de complément listent ici les cartes TCGdex (ja, en, fr)
qui leur manquent, puis calculent ce qu'il faut depuis l'image retenue. Le parcours tourne sur le VPS : le runner
GitHub reçoit de TCGdex des données en retard de plusieurs semaines.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

import httpx

from services.card_image_fallback_service import CardImageUrls, fallback_card_images
from services.catalog_external_cards_service import SETS_WITH_SHUFFLED_TCGDEX_IMAGES, external_set_cards
from services.tcgdex_client_service import SETS_PER_PAGE_MAX, TcgdexClientService, TcgdexUnavailableError

logger = logging.getLogger(__name__)

INDEXED_LOCALES: tuple[str, ...] = ("ja", "en", "fr")
SCAN_INDEX_USER_AGENT = "GoupixDex/1.0 (+scan-index)"
_TCGDEX_COMEBACK_PAUSES_SEC: tuple[float, ...] = (60.0, 180.0)
_POCKET_SERIES_ID = "tcgp"
#: Sets calculés depuis Limitless : TCGdex mélange leurs images (M1S), ou l'index livré a des empreintes fausses (M4, n° 103 et 120).
SETS_COMPUTED_FROM_LIMITLESS: frozenset[tuple[str, str]] = SETS_WITH_SHUFFLED_TCGDEX_IMAGES | frozenset({("ja", "M4")})

PayloadT = TypeVar("PayloadT")


@dataclass(frozen=True)
class ShippedIndex:
    """Index livré avec le site : nom de chaque carte, par clé ``langue/id``."""

    names: dict[str, str]


@dataclass
class PendingCard:
    """Carte TCGdex absente de l'index livré, avec l'image qui servira au calcul."""

    locale: str
    card_id: str
    set_id: str
    local_id: str
    name: str
    image_url: str | None = None


@dataclass(frozen=True)
class StoredCard:
    """Carte déjà enregistrée : si son calcul est fait, depuis quelle image, et quand elle a été tentée."""

    is_computed: bool
    image_url: str | None
    checked_at: dt.datetime


@dataclass
class ScanIndexRefreshReport:
    """Bilan d'un passage : sets relus, cartes calculées, cartes encore sans image."""

    sets_read: int = 0
    cards_computed: int = 0
    cards_without_image: int = 0
    unavailable_locales: list[str] = field(default_factory=list)


def load_shipped_index(url: str, *, min_cards: int) -> ShippedIndex:
    """
    Lit les métadonnées d'un index servi aux clients (celles que le scanner charge).

    Raises:
        httpx.HTTPError: L'index est injoignable.
        RuntimeError: L'index a moins de ``min_cards`` cartes (sans lui, tout serait recalculé).
    """
    response = httpx.get(url, headers={"User-Agent": SCAN_INDEX_USER_AGENT}, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    rows: list[list[str]] = response.json()["cards"]
    if len(rows) < min_cards:
        msg = f"Index de scan livré incomplet ({len(rows)} cartes)"
        raise RuntimeError(msg)
    return ShippedIndex(names={f"{row[1]}/{row[0]}": row[2] for row in rows})


def _comparable_name(name: str) -> str:
    """Nom de carte sans espaces ni écarts de largeur ou de casse (« ホゲータ ex » ≡ « ホゲータex »)."""
    return unicodedata.normalize("NFKC", name).replace(" ", "").casefold()


def _is_shipped_under_this_name(shipped: ShippedIndex, key: str, tcgdex_name: str) -> bool:
    """Vrai quand l'index livré a cette carte ; faux s'il a l'id pour une autre carte (M6a-R : énergie, puis Mew)."""
    shipped_name = shipped.names.get(key)
    return shipped_name is not None and _comparable_name(shipped_name) == _comparable_name(tcgdex_name)


def as_utc(value: dt.datetime) -> dt.datetime:
    """MariaDB rend des dates sans fuseau : elles sont en UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.UTC)


def _list_all_sets(client: TcgdexClientService, locale: str) -> list[dict[str, Any]]:
    """Tous les sets d'une langue, sans ceux de Pokémon TCG Pocket (cartes de l'appli mobile)."""
    try:
        pocket_sets = client.get_series(locale, _POCKET_SERIES_ID).get("sets") or []
    except TcgdexUnavailableError:
        raise
    except RuntimeError:
        pocket_sets = []
    pocket_ids = {row.get("id") for row in pocket_sets}
    sets: list[dict[str, Any]] = []
    page = 1
    while True:
        rows = client.list_sets(locale, page=page, per_page=SETS_PER_PAGE_MAX)
        sets.extend(dict(row) for row in rows if row.get("id") not in pocket_ids)
        if len(rows) < SETS_PER_PAGE_MAX:
            return sets
        page += 1


def _list_all_sets_once_tcgdex_answers(client: TcgdexClientService, locale: str) -> list[dict[str, Any]] | None:
    """Sets d'une langue, en laissant à TCGdex quelques minutes pour revenir s'il est tombé ; ``None`` s'il reste muet."""
    for pause_sec in (0.0, *_TCGDEX_COMEBACK_PAUSES_SEC):
        time.sleep(pause_sec)
        try:
            return _list_all_sets(client, locale)
        except TcgdexUnavailableError as exc:
            logger.warning("Scan index refresh: TCGdex unavailable for %s (%s)", locale, exc)
    return None


def _fallback_images(locale: str, detail: dict[str, Any]) -> dict[str, CardImageUrls]:
    """Scans de repli du catalogue pour ce set, vides si une de leurs sources ne répond pas."""
    try:
        return fallback_card_images(locale, detail)
    except (RuntimeError, httpx.HTTPError) as exc:
        logger.warning("Scan index refresh: fallback images of %s/%s unavailable (%s)", locale, detail.get("id"), exc)
        return {}


def _limitless_low_images(set_id: str) -> dict[str, str]:
    """Images Limitless d'un set calculé depuis Limitless, par numéro (« 070 ») ; vides si la source ne répond pas."""
    try:
        return {card.local_id: card.images.low for card in external_set_cards(set_id) if card.images is not None}
    except (RuntimeError, ValueError, httpx.HTTPError) as exc:
        logger.warning("Scan index refresh: Limitless images of %s unavailable (%s)", set_id, exc)
        return {}


def pending_cards_for_locale(
    client: TcgdexClientService,
    locale: str,
    shipped: ShippedIndex,
    stored: dict[tuple[str, str], StoredCard],
    retry_before: dt.datetime,
    report: ScanIndexRefreshReport,
) -> list[PendingCard]:
    """
    Cartes d'une langue à calculer, des sets les plus récents aux plus anciens : absentes de l'index livré (ou qu'il
    a sous un autre nom), jamais calculées, ou restées sans image depuis avant ``retry_before``. Un set de
    ``SETS_COMPUTED_FROM_LIMITLESS`` est entièrement calculé depuis Limitless, et recalculé si l'image enregistrée
    était autre. Si TCGdex tombe en route, les sets déjà lus sont gardés ; un set illisible est sauté.
    """
    sets = _list_all_sets_once_tcgdex_answers(client, locale)
    if sets is None:
        report.unavailable_locales.append(locale)
        return []
    pending: list[PendingCard] = []
    for brief in reversed(sets):
        set_id = str(brief.get("id") or "")
        if not set_id:
            continue
        try:
            detail: dict[str, Any] = dict(client.get_set(locale, set_id))
        except TcgdexUnavailableError as exc:
            logger.warning("Scan index refresh: TCGdex unavailable during %s (%s)", locale, exc)
            report.unavailable_locales.append(locale)
            return pending
        except RuntimeError as exc:
            logger.warning("Scan index refresh: set %s/%s skipped (%s)", locale, set_id, exc)
            continue
        report.sets_read += 1
        fallback_images: dict[str, CardImageUrls] | None = None
        limitless_images: dict[str, str] | None = (
            _limitless_low_images(set_id) if (locale, set_id) in SETS_COMPUTED_FROM_LIMITLESS else None
        )
        for card in detail.get("cards") or []:
            card_id = card.get("id")
            local_id = card.get("localId")
            if not isinstance(card_id, str) or not isinstance(local_id, str):
                continue
            name = str(card.get("name") or "")
            stored_card = stored.get((locale, card_id))
            image_url: str | None
            if limitless_images is not None:
                image_url = limitless_images.get(local_id)
                if stored_card is not None and stored_card.is_computed and stored_card.image_url == image_url:
                    continue
            else:
                if _is_shipped_under_this_name(shipped, f"{locale}/{card_id}", name):
                    continue
                if stored_card is not None and (stored_card.is_computed or stored_card.checked_at >= retry_before):
                    continue
                if fallback_images is None:
                    fallback_images = _fallback_images(locale, detail)
                fallback = fallback_images.get(local_id)
                image = card.get("image")
                if fallback is not None:
                    image_url = fallback.low
                elif isinstance(image, str) and image:
                    image_url = f"{image.rstrip('/')}/low.webp"
                else:
                    image_url = None
            pending.append(
                PendingCard(
                    locale=locale,
                    card_id=card_id,
                    set_id=set_id,
                    local_id=local_id,
                    name=name,
                    image_url=image_url,
                )
            )
    return pending


def download_image(http: httpx.Client, url: str | None) -> bytes | None:
    """Contenu de l'image à cette URL, ``None`` si elle est introuvable."""
    if url is None:
        return None
    try:
        response = http.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code != 200 or not response.content:
        return None
    return response.content


class DeltaPayloadCache(Generic[PayloadT]):
    """Charge utile d'un complément d'index servie au scanner, gardée quelques minutes et vidée à chaque lot enregistré."""

    def __init__(self, ttl_sec: float) -> None:
        self._ttl_sec = ttl_sec
        self._lock = threading.Lock()
        self._entry: tuple[float, PayloadT] | None = None

    def get(self) -> PayloadT | None:
        with self._lock:
            if self._entry is None or time.monotonic() - self._entry[0] > self._ttl_sec:
                return None
            return self._entry[1]

    def set(self, payload: PayloadT) -> None:
        with self._lock:
            self._entry = (time.monotonic(), payload)

    def clear(self) -> None:
        with self._lock:
            self._entry = None
