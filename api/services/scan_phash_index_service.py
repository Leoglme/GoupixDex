"""
Empreintes pHash des cartes que l'index de scan livré avec le site ne connaît pas encore.

L'index du scanner (``web/public/scan-index/phash-v1.*``) est figé à sa génération : un set sorti
ensuite, ou complété plus tard sur TCGdex (les secrètes de ``M6a``), n'y figure pas et ses cartes ne
sont jamais reconnues. Chaque nuit, ce service liste les cartes TCGdex (fr, en, ja), calcule
l'empreinte de celles qui manquent à l'index livré et la garde en base ; le scanner les ajoute à son
index au chargement (``GET /scan-index/phash-delta``). Il tourne sur le VPS : le runner GitHub reçoit
de TCGdex des données en retard de plusieurs semaines.

Le calcul reproduit celui de l'index livré (``scripts/scan-index.mjs`` de TailTCG, avec sharp) :
luminance Rec. 709 en lumière linéaire, réduction Lanczos à 96×132, puis DCT 32×32 de la carte
entière et de l'illustration, bloc 16×16 comparé à sa médiane.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import io
import logging
import math
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from config import get_settings
from core.database import SessionLocal
from models.scan_phash_card import ScanPhashCard
from services.card_image_fallback_service import CardImageUrls, fallback_card_images
from services.market_price_refresh_service import seconds_until_next_run
from services.tcgdex_client_service import SETS_PER_PAGE_MAX, TcgdexClientService, TcgdexUnavailableError

logger = logging.getLogger(__name__)

INDEXED_LOCALES: tuple[str, ...] = ("ja", "en", "fr")
MAX_NEW_CARDS_PER_RUN = 10000
_MIN_SHIPPED_CARDS = 50000
_MISSING_IMAGE_RETRY = dt.timedelta(days=3)
_STARTUP_DELAY_SEC = 180.0
_TCGDEX_COMEBACK_PAUSES_SEC: tuple[float, ...] = (60.0, 180.0)
_RETRY_AFTER_INCOMPLETE_RUN_SEC = 3600.0
_DOWNLOAD_WORKERS = 6
_STORE_BATCH_SIZE = 300
_DELTA_CACHE_TTL_SEC = 900.0
_USER_AGENT = "GoupixDex/1.0 (+scan-index)"
_POCKET_SERIES_ID = "tcgp"

_GRAY_WIDTH = 96
_GRAY_HEIGHT = 132
_DCT_SIZE = 32
_DCT_BLOCK = 16
_SUPERSAMPLING = 3
_WHOLE_WINDOW = (0.0, 0.0, 1.0, 1.0)
_ART_WINDOW = (0.07, 0.11, 0.86, 0.4)
_DCT_COS = [
    [math.cos(((2 * x + 1) * u * math.pi) / (2 * _DCT_SIZE)) for x in range(_DCT_SIZE)] for u in range(_DCT_BLOCK)
]


def _srgb_to_linear(value: int) -> float:
    c = value / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


_LUMA_R = [0.2126 * _srgb_to_linear(v) for v in range(256)]
_LUMA_G = [0.7152 * _srgb_to_linear(v) for v in range(256)]
_LUMA_B = [0.0722 * _srgb_to_linear(v) for v in range(256)]


def _linear_to_srgb_byte(luminance: float) -> int:
    s = luminance * 12.92 if luminance <= 0.0031308 else 1.055 * luminance ** (1 / 2.4) - 0.055
    return min(255, max(0, int(s * 255.0 + 0.5)))


def _card_gray(image_bytes: bytes) -> list[float]:
    """
    Image de carte en niveaux de gris 96×132, comme sharp ``grayscale().resize(lanczos3)``.

    La luminance est calculée en lumière linéaire (ce que fait libvips) ; une première réduction à
    deux fois la taille finale garde le calcul pixel par pixel rapide sans écart mesurable.
    """
    with Image.open(io.BytesIO(image_bytes)) as source:
        rgb = source.convert("RGB")
    if rgb.width > 2 * _GRAY_WIDTH:
        rgb = rgb.resize((2 * _GRAY_WIDTH, 2 * _GRAY_HEIGHT), Image.Resampling.LANCZOS)
    data = rgb.tobytes()
    luma = bytes(
        _linear_to_srgb_byte(_LUMA_R[data[i]] + _LUMA_G[data[i + 1]] + _LUMA_B[data[i + 2]])
        for i in range(0, len(data), 3)
    )
    gray = Image.frombytes("L", rgb.size, luma).resize((_GRAY_WIDTH, _GRAY_HEIGHT), Image.Resampling.LANCZOS)
    return [float(v) for v in gray.tobytes()]


def _gray_at(gray: list[float], x: float, y: float) -> float:
    """Lecture bilinéaire de l'image 96×132, bords répétés."""
    x = min(max(x, 0.0), _GRAY_WIDTH - 1.001)
    y = min(max(y, 0.0), _GRAY_HEIGHT - 1.001)
    x0 = int(x)
    y0 = int(y)
    fx = x - x0
    fy = y - y0
    i = y0 * _GRAY_WIDTH + x0
    top = gray[i] * (1 - fx) + gray[i + 1] * fx
    bottom = gray[i + _GRAY_WIDTH] * (1 - fx) + gray[i + _GRAY_WIDTH + 1] * fx
    return top * (1 - fy) + bottom * fy


def _window_grid(gray: list[float], window: tuple[float, float, float, float]) -> list[float]:
    """Fenêtre de la carte échantillonnée en 32×32 (moyenne 3×3 par point), sans recadrage."""
    left, top, width, height = window
    out: list[float] = []
    for j in range(_DCT_SIZE):
        for i in range(_DCT_SIZE):
            acc = 0.0
            for b in range(_SUPERSAMPLING):
                v = top + height * (j + (b + 0.5) / _SUPERSAMPLING) / _DCT_SIZE
                y = _GRAY_HEIGHT / 2 + (v - 0.5) * _GRAY_HEIGHT
                for a in range(_SUPERSAMPLING):
                    u = left + width * (i + (a + 0.5) / _SUPERSAMPLING) / _DCT_SIZE
                    acc += _gray_at(gray, _GRAY_WIDTH / 2 + (u - 0.5) * _GRAY_WIDTH, y)
            out.append(acc / (_SUPERSAMPLING * _SUPERSAMPLING))
    return out


def _dct_hash(grid: list[float]) -> bytes:
    """256 bits : bloc 16×16 basse fréquence de la DCT 32×32, comparé à sa médiane (composante continue ignorée)."""
    rows = [
        [sum(grid[y * _DCT_SIZE + x] * _DCT_COS[u][x] for x in range(_DCT_SIZE)) for y in range(_DCT_SIZE)]
        for u in range(_DCT_BLOCK)
    ]
    coefficients = [
        sum(rows[u][y] * _DCT_COS[v][y] for y in range(_DCT_SIZE)) for u in range(_DCT_BLOCK) for v in range(_DCT_BLOCK)
    ]
    median = sorted(coefficients[1:])[(len(coefficients) - 1) >> 1]
    bits = bytearray(_DCT_BLOCK * _DCT_BLOCK // 8)
    for i in range(1, len(coefficients)):
        if coefficients[i] > median:
            bits[i >> 3] |= 1 << (i & 7)
    return bytes(bits)


def compute_card_phash(image_bytes: bytes) -> bytes:
    """
    Empreintes d'une image de carte, au format de l'index livré.

    Returns:
        64 octets : 32 pour la carte entière, puis 32 pour l'illustration.

    Raises:
        UnidentifiedImageError: Le contenu n'est pas une image lisible.
    """
    gray = _card_gray(image_bytes)
    return _dct_hash(_window_grid(gray, _WHOLE_WINDOW)) + _dct_hash(_window_grid(gray, _ART_WINDOW))


@dataclass(frozen=True)
class _ShippedIndex:
    """Index livré avec le site : clés ``langue/id`` et nombre de cartes par set."""

    keys: frozenset[str]
    cards_per_set: Counter[tuple[str, str]]


@dataclass
class _PendingCard:
    """Carte TCGdex absente de l'index livré, avec l'image qui servira au calcul."""

    locale: str
    card_id: str
    set_id: str
    local_id: str
    name: str
    image_url: str | None = None


@dataclass(frozen=True)
class _StoredCard:
    """Carte déjà enregistrée : son set, si son empreinte est calculée, et quand elle a été tentée."""

    set_id: str
    is_hashed: bool
    checked_at: dt.datetime


@dataclass
class ScanPhashRefreshReport:
    """Bilan d'un passage : sets relus, cartes calculées, cartes encore sans image."""

    sets_read: int = 0
    cards_hashed: int = 0
    cards_without_image: int = 0
    unavailable_locales: list[str] = field(default_factory=list)


def _load_shipped_index(url: str) -> _ShippedIndex:
    """Lit les métadonnées de l'index servi aux clients (celles que le scanner charge)."""
    response = httpx.get(url, headers={"User-Agent": _USER_AGENT}, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    rows: list[list[str]] = response.json()["cards"]
    if len(rows) < _MIN_SHIPPED_CARDS:
        msg = f"Index de scan livré incomplet ({len(rows)} cartes)"
        raise RuntimeError(msg)
    return _ShippedIndex(
        keys=frozenset(f"{row[1]}/{row[0]}" for row in rows),
        cards_per_set=Counter((row[1], row[3]) for row in rows),
    )


def _as_utc(value: dt.datetime) -> dt.datetime:
    """MariaDB rend des dates sans fuseau : elles sont en UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.UTC)


def _stored_cards_snapshot(db: Session) -> dict[tuple[str, str], _StoredCard]:
    """
    Cartes déjà enregistrées, puis connexion rendue : le parcours de TCGdex qui suit dure plusieurs minutes et la
    base distante coupe une connexion restée inactive aussi longtemps.
    """
    rows = db.query(
        ScanPhashCard.locale,
        ScanPhashCard.tcgdex_card_id,
        ScanPhashCard.set_id,
        ScanPhashCard.hashes.is_not(None),
        ScanPhashCard.checked_at,
    ).all()
    db.rollback()
    return {
        (locale, card_id): _StoredCard(set_id=set_id, is_hashed=bool(is_hashed), checked_at=_as_utc(checked_at))
        for locale, card_id, set_id, is_hashed, checked_at in rows
    }


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
            logger.warning("Scan pHash refresh: TCGdex unavailable for %s (%s)", locale, exc)
    return None


def _fallback_images(locale: str, detail: dict[str, Any]) -> dict[str, CardImageUrls]:
    """Scans de repli du catalogue pour ce set, vides si une de leurs sources ne répond pas."""
    try:
        return fallback_card_images(locale, detail)
    except (RuntimeError, httpx.HTTPError) as exc:
        logger.warning("Scan pHash refresh: fallback images of %s/%s unavailable (%s)", locale, detail.get("id"), exc)
        return {}


def _pending_cards_for_locale(
    client: TcgdexClientService,
    locale: str,
    shipped: _ShippedIndex,
    stored: dict[tuple[str, str], _StoredCard],
    retry_before: dt.datetime,
    report: ScanPhashRefreshReport,
) -> list[_PendingCard]:
    """
    Cartes d'une langue à calculer, des sets les plus récents aux plus anciens : absentes de l'index livré, jamais
    calculées, ou restées sans image depuis plus de ``_MISSING_IMAGE_RETRY``. Si TCGdex tombe en route, les sets
    déjà lus sont gardés ; un set illisible est sauté.
    """
    sets = _list_all_sets_once_tcgdex_answers(client, locale)
    if sets is None:
        report.unavailable_locales.append(locale)
        return []
    stored_per_set = Counter(card.set_id for (card_locale, _), card in stored.items() if card_locale == locale)
    sets_to_retry = {
        card.set_id
        for (card_locale, _), card in stored.items()
        if card_locale == locale and not card.is_hashed and card.checked_at < retry_before
    }
    pending: list[_PendingCard] = []
    for brief in reversed(sets):
        set_id = str(brief.get("id") or "")
        card_count = brief.get("cardCount")
        total = card_count.get("total") if isinstance(card_count, dict) else None
        known = shipped.cards_per_set[(locale, set_id)] + stored_per_set[set_id]
        if not set_id or (isinstance(total, int) and known >= total and set_id not in sets_to_retry):
            continue
        try:
            detail: dict[str, Any] = dict(client.get_set(locale, set_id))
        except TcgdexUnavailableError as exc:
            logger.warning("Scan pHash refresh: TCGdex unavailable during %s (%s)", locale, exc)
            report.unavailable_locales.append(locale)
            return pending
        except RuntimeError as exc:
            logger.warning("Scan pHash refresh: set %s/%s skipped (%s)", locale, set_id, exc)
            continue
        report.sets_read += 1
        fallback_images: dict[str, CardImageUrls] | None = None
        for card in detail.get("cards") or []:
            card_id = card.get("id")
            local_id = card.get("localId")
            if not isinstance(card_id, str) or not isinstance(local_id, str):
                continue
            if f"{locale}/{card_id}" in shipped.keys:
                continue
            stored_card = stored.get((locale, card_id))
            if stored_card is not None and (stored_card.is_hashed or stored_card.checked_at >= retry_before):
                continue
            if fallback_images is None:
                fallback_images = _fallback_images(locale, detail)
            fallback = fallback_images.get(local_id)
            image = card.get("image")
            if fallback is not None:
                image_url: str | None = fallback.low
            elif isinstance(image, str) and image:
                image_url = f"{image.rstrip('/')}/low.webp"
            else:
                image_url = None
            pending.append(
                _PendingCard(
                    locale=locale,
                    card_id=card_id,
                    set_id=set_id,
                    local_id=local_id,
                    name=str(card.get("name") or ""),
                    image_url=image_url,
                )
            )
    return pending


def _hash_image_at(http: httpx.Client, url: str | None) -> bytes | None:
    """Empreintes de l'image à cette URL, ``None`` si elle est introuvable ou illisible."""
    if url is None:
        return None
    try:
        response = http.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code != 200 or not response.content:
        return None
    try:
        return compute_card_phash(response.content)
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _save_computed_cards(db: Session, cards: list[_PendingCard], hashes: list[bytes | None], now: dt.datetime) -> None:
    """Enregistre un lot dans sa propre transaction ; le scanner le reçoit dès la requête suivante."""
    rows_by_card = {
        (row.locale, row.tcgdex_card_id): row
        for row in db.query(ScanPhashCard)
        .filter(ScanPhashCard.tcgdex_card_id.in_({card.card_id for card in cards}))
        .all()
    }
    for card, card_hashes in zip(cards, hashes, strict=True):
        row = rows_by_card.get((card.locale, card.card_id))
        if row is None:
            row = ScanPhashCard(locale=card.locale, tcgdex_card_id=card.card_id, created_at=now)
            db.add(row)
            rows_by_card[(card.locale, card.card_id)] = row
        row.set_id = card.set_id
        row.local_id = card.local_id
        row.name = card.name[:255]
        row.hashes = card_hashes
        row.image_url = card.image_url if card_hashes is not None else None
        row.checked_at = now
    db.commit()
    _delta_cache.clear()


def refresh_scan_phash_cards(db: Session, *, max_new_cards: int = MAX_NEW_CARDS_PER_RUN) -> ScanPhashRefreshReport:
    """
    Calcule et enregistre les empreintes des cartes TCGdex absentes de l'index livré.

    Seuls les sets dont TCGdex annonce plus de cartes que l'index livré et la base n'en connaissent
    sont relus. Une langue où TCGdex reste injoignable quelques minutes est sautée, les autres continuent.

    Raises:
        httpx.HTTPError: L'index livré est injoignable (sans lui, tout serait recalculé).
        RuntimeError: L'index livré est incomplet.
    """
    shipped = _load_shipped_index(get_settings().scan_index_base_url)
    stored = _stored_cards_snapshot(db)
    now = dt.datetime.now(dt.UTC)
    report = ScanPhashRefreshReport()
    client = TcgdexClientService()
    pending: list[_PendingCard] = []
    for locale in INDEXED_LOCALES:
        pending.extend(_pending_cards_for_locale(client, locale, shipped, stored, now - _MISSING_IMAGE_RETRY, report))
    pending = pending[:max_new_cards]
    with httpx.Client(headers={"User-Agent": _USER_AGENT}, timeout=45.0, follow_redirects=True) as http:
        with ThreadPoolExecutor(max_workers=_DOWNLOAD_WORKERS) as pool:
            for start in range(0, len(pending), _STORE_BATCH_SIZE):
                batch = pending[start : start + _STORE_BATCH_SIZE]
                hashes = list(pool.map(lambda card: _hash_image_at(http, card.image_url), batch))
                _save_computed_cards(db, batch, hashes, now)
                report.cards_hashed += sum(1 for card_hashes in hashes if card_hashes is not None)
                report.cards_without_image += sum(1 for card_hashes in hashes if card_hashes is None)
    return report


class _DeltaCache:
    """Charge utile de ``GET /scan-index/phash-delta``, gardée quelques minutes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entry: tuple[float, dict[str, Any]] | None = None

    def get(self) -> dict[str, Any] | None:
        with self._lock:
            if self._entry is None or time.monotonic() - self._entry[0] > _DELTA_CACHE_TTL_SEC:
                return None
            return self._entry[1]

    def set(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._entry = (time.monotonic(), payload)

    def clear(self) -> None:
        with self._lock:
            self._entry = None


_delta_cache = _DeltaCache()


def scan_phash_delta_payload(db: Session) -> dict[str, Any]:
    """
    Cartes calculées, au format de l'index livré complété de l'image : le scanner les ajoute à son index.

    Returns:
        ``{"version", "count", "cards": [[id, langue, nom, set, numéro, empreintes base64, image], …]}``.
    """
    cached = _delta_cache.get()
    if cached is not None:
        return cached
    rows = db.query(ScanPhashCard).filter(ScanPhashCard.hashes.is_not(None)).order_by(ScanPhashCard.id).all()
    payload: dict[str, Any] = {
        "version": 1,
        "count": len(rows),
        "cards": [
            [
                row.tcgdex_card_id,
                row.locale,
                row.name,
                row.set_id,
                row.local_id,
                base64.b64encode(row.hashes or b"").decode("ascii"),
                row.image_url or "",
            ]
            for row in rows
        ],
    }
    _delta_cache.set(payload)
    return payload


def run_scan_phash_refresh() -> ScanPhashRefreshReport:
    """Un passage complet dans sa propre session (à lancer hors de la boucle asyncio)."""
    db = SessionLocal()
    try:
        return refresh_scan_phash_cards(db)
    finally:
        db.close()


async def scan_phash_refresh_loop_async() -> None:
    """Complète l'index de scan peu après le démarrage, puis chaque nuit ; un passage incomplet est repris une heure après."""
    settings = get_settings()
    await asyncio.sleep(_STARTUP_DELAY_SEC)
    while True:
        is_run_complete = False
        try:
            report = await asyncio.to_thread(run_scan_phash_refresh)
            logger.info("Scan pHash refresh: %s", report)
            is_run_complete = not report.unavailable_locales
        except Exception:
            logger.exception("Scan pHash refresh crashed")
        await asyncio.sleep(
            seconds_until_next_run(settings.scan_phash_refresh_hour_local)
            if is_run_complete
            else _RETRY_AFTER_INCOMPLETE_RUN_SEC
        )
