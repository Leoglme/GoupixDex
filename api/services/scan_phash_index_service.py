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
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from config import get_settings
from core.database import SessionLocal
from models.scan_phash_card import ScanPhashCard
from services.market_price_refresh_service import seconds_until_next_run
from services.scan_index_cards_service import (
    INDEXED_LOCALES,
    SCAN_INDEX_USER_AGENT,
    DeltaPayloadCache,
    PendingCard,
    ScanIndexRefreshReport,
    StoredCard,
    as_utc,
    download_image,
    load_shipped_index,
    pending_cards_for_locale,
)
from services.tcgdex_client_service import TcgdexClientService

logger = logging.getLogger(__name__)

MAX_NEW_CARDS_PER_RUN = 10000
_MIN_SHIPPED_CARDS = 50000
_MISSING_IMAGE_RETRY = dt.timedelta(days=3)
_STARTUP_DELAY_SEC = 180.0
_RETRY_AFTER_INCOMPLETE_RUN_SEC = 3600.0
_DOWNLOAD_WORKERS = 6
_STORE_BATCH_SIZE = 300
_DELTA_CACHE_TTL_SEC = 900.0

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


def _stored_cards_snapshot(db: Session) -> dict[tuple[str, str], StoredCard]:
    """
    Cartes déjà enregistrées, puis connexion rendue : le parcours de TCGdex qui suit dure plusieurs minutes et la
    base distante coupe une connexion restée inactive aussi longtemps.
    """
    rows = db.query(
        ScanPhashCard.locale,
        ScanPhashCard.tcgdex_card_id,
        ScanPhashCard.hashes.is_not(None),
        ScanPhashCard.image_url,
        ScanPhashCard.checked_at,
    ).all()
    db.rollback()
    return {
        (locale, card_id): StoredCard(is_computed=bool(is_hashed), image_url=image_url, checked_at=as_utc(checked_at))
        for locale, card_id, is_hashed, image_url, checked_at in rows
    }


def _hash_image_at(http: httpx.Client, url: str | None) -> bytes | None:
    """Empreintes de l'image à cette URL, ``None`` si elle est introuvable ou illisible."""
    image_bytes = download_image(http, url)
    if image_bytes is None:
        return None
    try:
        return compute_card_phash(image_bytes)
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _save_computed_cards(db: Session, cards: list[PendingCard], hashes: list[bytes | None], now: dt.datetime) -> None:
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


def refresh_scan_phash_cards(db: Session, *, max_new_cards: int = MAX_NEW_CARDS_PER_RUN) -> ScanIndexRefreshReport:
    """
    Calcule et enregistre les empreintes des cartes TCGdex absentes de l'index livré.

    Chaque set est relu : une carte ajoutée tard (secrètes) ou un id réattribué par TCGdex est repéré. Une langue
    où TCGdex reste injoignable quelques minutes est sautée, les autres continuent.

    Raises:
        httpx.HTTPError: L'index livré est injoignable (sans lui, tout serait recalculé).
        RuntimeError: L'index livré est incomplet.
    """
    shipped = load_shipped_index(get_settings().scan_index_base_url, min_cards=_MIN_SHIPPED_CARDS)
    stored = _stored_cards_snapshot(db)
    now = dt.datetime.now(dt.UTC)
    report = ScanIndexRefreshReport()
    client = TcgdexClientService()
    pending: list[PendingCard] = []
    for locale in INDEXED_LOCALES:
        pending.extend(pending_cards_for_locale(client, locale, shipped, stored, now - _MISSING_IMAGE_RETRY, report))
    pending = pending[:max_new_cards]
    with httpx.Client(headers={"User-Agent": SCAN_INDEX_USER_AGENT}, timeout=45.0, follow_redirects=True) as http:
        with ThreadPoolExecutor(max_workers=_DOWNLOAD_WORKERS) as pool:
            for start in range(0, len(pending), _STORE_BATCH_SIZE):
                batch = pending[start : start + _STORE_BATCH_SIZE]
                hashes = list(pool.map(lambda card: _hash_image_at(http, card.image_url), batch))
                _save_computed_cards(db, batch, hashes, now)
                report.cards_computed += sum(1 for card_hashes in hashes if card_hashes is not None)
                report.cards_without_image += sum(1 for card_hashes in hashes if card_hashes is None)
    return report


_delta_cache: DeltaPayloadCache[dict[str, Any]] = DeltaPayloadCache(_DELTA_CACHE_TTL_SEC)


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


def run_scan_phash_refresh() -> ScanIndexRefreshReport:
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
