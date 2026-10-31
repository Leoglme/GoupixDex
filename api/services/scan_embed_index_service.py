"""
Embeddings MobileCLIP-S0 des cartes que l'index visuel du scanner livré avec le site ne connaît pas encore.

Le scanner reconnaît une carte avec deux index livrés avec le site : les empreintes pHash de l'illustration
(complétées chaque nuit par ``scan_phash_index_service``) et les embeddings MobileCLIP-S0 de
``web/public/scan-index/embed-v3``, les seuls à reconnaître une carte holo sombre que les reflets éloignent de son
empreinte. Construit depuis les images TCGdex, ce second index n'a presque aucune carte japonaise récente (ni
SV11B/SV11W, ni la série M). Chaque nuit, ce service calcule l'embedding des cartes TCGdex qui y manquent, avec le
modèle même que le navigateur exécute, et le garde en base ; le scanner les ajoute à son index au chargement
(``GET /scan-index/embed-delta``).
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import gzip
import hashlib
import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx
import numpy as np
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from config import get_settings
from core.database import SessionLocal
from models.scan_embed_card import ScanEmbedCard
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

EMBEDDING_DIM = 512
MAX_NEW_CARDS_PER_RUN = 20000
_INDEX_VERSION = 3
_INPUT_EDGE = 256
_MIN_SHIPPED_CARDS = 40000
_MISSING_IMAGE_RETRY = dt.timedelta(days=3)
_STARTUP_DELAY_SEC = 300.0
_RETRY_AFTER_INCOMPLETE_RUN_SEC = 3600.0
_DOWNLOAD_WORKERS = 6
_STORE_BATCH_SIZE = 300
_INFERENCE_BATCH_SIZE = 16
_INFERENCE_THREADS = 2
_DELTA_CACHE_TTL_SEC = 900.0


@dataclass(frozen=True)
class ScanEmbedDelta:
    """Complément servi au scanner : son JSON compressé, et l'ETag qui évite de le retélécharger tant qu'il ne change pas."""

    etag: str
    gzip_body: bytes


def _pixel_values(image_bytes: bytes | None) -> np.ndarray | None:
    """Image 256×256 en CHW float32 dans [0, 1], sans normalisation, comme l'index livré ; ``None`` si illisible."""
    if image_bytes is None:
        return None
    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            rgb = source.convert("RGB").resize((_INPUT_EDGE, _INPUT_EDGE), Image.Resampling.BILINEAR)
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    return (np.asarray(rgb, dtype=np.float32) / 255.0).transpose(2, 0, 1)


def quantised_embedding(vector: np.ndarray) -> bytes:
    """
    Embedding normalisé puis quantifié comme une ligne de l'index livré.

    Returns:
        516 octets : 512 int8, puis l'échelle float32 petit-boutiste (int8 × échelle ≈ composante normalisée).
    """
    normalised = vector.astype(np.float32) / (float(np.linalg.norm(vector)) + 1e-9)
    scale = float(np.abs(normalised).max()) / 127.0 or 1.0
    quantised = np.clip(np.round(normalised / scale), -127, 127).astype(np.int8)
    return quantised.tobytes() + np.array([scale], dtype="<f4").tobytes()


class _MobileClipEmbedder:
    """Tour visuel MobileCLIP-S0 du scanner ; onnxruntime n'est chargé que le temps d'un passage."""

    def __init__(self, model_bytes: bytes) -> None:
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = _INFERENCE_THREADS
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(model_bytes, sess_options=options, providers=["CPUExecutionProvider"])
        self._input_name: str = self._session.get_inputs()[0].name

    def embed_images(self, images: list[bytes | None]) -> list[bytes | None]:
        """Embeddings quantifiés des images, ``None`` pour une image absente ou illisible."""
        pixels = [_pixel_values(image) for image in images]
        embeddings: list[bytes | None] = [None] * len(images)
        readable = [i for i, values in enumerate(pixels) if values is not None]
        for start in range(0, len(readable), _INFERENCE_BATCH_SIZE):
            chunk = readable[start : start + _INFERENCE_BATCH_SIZE]
            batch = np.stack([pixels[i] for i in chunk])
            output = self._session.run(None, {self._input_name: batch})[0]
            vectors = np.asarray(output, dtype=np.float32).reshape(len(chunk), EMBEDDING_DIM)
            for i, vector in zip(chunk, vectors, strict=True):
                embeddings[i] = quantised_embedding(vector)
        return embeddings


def _load_card_embedder() -> _MobileClipEmbedder:
    """
    Charge le modèle que le site sert au scanner : les embeddings calculés ici et ceux du navigateur sont comparables.

    Raises:
        httpx.HTTPError: Le modèle est injoignable.
    """
    response = httpx.get(
        get_settings().scan_embed_model_url,
        headers={"User-Agent": SCAN_INDEX_USER_AGENT},
        timeout=120.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    return _MobileClipEmbedder(response.content)


def _stored_cards_snapshot(db: Session) -> dict[tuple[str, str], StoredCard]:
    """
    Cartes déjà enregistrées, puis connexion rendue : le parcours de TCGdex qui suit dure plusieurs minutes et la
    base distante coupe une connexion restée inactive aussi longtemps.
    """
    rows = db.query(
        ScanEmbedCard.locale,
        ScanEmbedCard.tcgdex_card_id,
        ScanEmbedCard.embedding.is_not(None),
        ScanEmbedCard.image_url,
        ScanEmbedCard.checked_at,
    ).all()
    db.rollback()
    return {
        (locale, card_id): StoredCard(is_computed=bool(is_embedded), image_url=image_url, checked_at=as_utc(checked_at))
        for locale, card_id, is_embedded, image_url, checked_at in rows
    }


def _save_computed_cards(
    db: Session, cards: list[PendingCard], embeddings: list[bytes | None], now: dt.datetime
) -> None:
    """Enregistre un lot dans sa propre transaction ; le scanner le reçoit dès la requête suivante."""
    rows_by_card = {
        (row.locale, row.tcgdex_card_id): row
        for row in db.query(ScanEmbedCard)
        .filter(ScanEmbedCard.tcgdex_card_id.in_({card.card_id for card in cards}))
        .all()
    }
    for card, embedding in zip(cards, embeddings, strict=True):
        row = rows_by_card.get((card.locale, card.card_id))
        if row is None:
            row = ScanEmbedCard(locale=card.locale, tcgdex_card_id=card.card_id, created_at=now)
            db.add(row)
            rows_by_card[(card.locale, card.card_id)] = row
        row.set_id = card.set_id
        row.local_id = card.local_id
        row.name = card.name[:255]
        row.embedding = embedding
        row.image_url = card.image_url if embedding is not None else None
        row.checked_at = now
    db.commit()
    _delta_cache.clear()


def refresh_scan_embed_cards(db: Session, *, max_new_cards: int = MAX_NEW_CARDS_PER_RUN) -> ScanIndexRefreshReport:
    """
    Calcule et enregistre les embeddings des cartes TCGdex absentes de l'index visuel livré.

    Les images sont celles des empreintes pHash (scans de repli, Limitless pour les sets aux images TCGdex
    mélangées) ; le modèle n'est téléchargé qu'au premier lot qui a une image.

    Raises:
        httpx.HTTPError: L'index livré ou le modèle est injoignable.
        RuntimeError: L'index livré est incomplet.
    """
    shipped = load_shipped_index(get_settings().scan_embed_index_url, min_cards=_MIN_SHIPPED_CARDS)
    stored = _stored_cards_snapshot(db)
    now = dt.datetime.now(dt.UTC)
    report = ScanIndexRefreshReport()
    client = TcgdexClientService()
    pending: list[PendingCard] = []
    for locale in INDEXED_LOCALES:
        pending.extend(pending_cards_for_locale(client, locale, shipped, stored, now - _MISSING_IMAGE_RETRY, report))
    pending = pending[:max_new_cards]
    embedder: _MobileClipEmbedder | None = None
    with (
        httpx.Client(headers={"User-Agent": SCAN_INDEX_USER_AGENT}, timeout=45.0, follow_redirects=True) as http,
        ThreadPoolExecutor(max_workers=_DOWNLOAD_WORKERS) as pool,
    ):
        for start in range(0, len(pending), _STORE_BATCH_SIZE):
            batch = pending[start : start + _STORE_BATCH_SIZE]
            images = list(pool.map(lambda card: download_image(http, card.image_url), batch))
            if embedder is None and any(image is not None for image in images):
                embedder = _load_card_embedder()
            embeddings = embedder.embed_images(images) if embedder is not None else [None] * len(images)
            _save_computed_cards(db, batch, embeddings, now)
            report.cards_computed += sum(1 for embedding in embeddings if embedding is not None)
            report.cards_without_image += sum(1 for embedding in embeddings if embedding is None)
    return report


_delta_cache: DeltaPayloadCache[ScanEmbedDelta] = DeltaPayloadCache(_DELTA_CACHE_TTL_SEC)


def scan_embed_delta(db: Session) -> ScanEmbedDelta:
    """
    Cartes calculées, au format de l'index livré : le scanner les ajoute à son index d'embeddings.

    Le JSON ``{"version", "dim", "count", "cards": [[id, langue, nom, set, numéro, embedding base64], …]}`` pèse
    plusieurs Mo : il est servi compressé.
    """
    cached = _delta_cache.get()
    if cached is not None:
        return cached
    rows = db.query(ScanEmbedCard).filter(ScanEmbedCard.embedding.is_not(None)).order_by(ScanEmbedCard.id).all()
    body = json.dumps(
        {
            "version": _INDEX_VERSION,
            "dim": EMBEDDING_DIM,
            "count": len(rows),
            "cards": [
                [
                    row.tcgdex_card_id,
                    row.locale,
                    row.name,
                    row.set_id,
                    row.local_id,
                    base64.b64encode(row.embedding or b"").decode("ascii"),
                ]
                for row in rows
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    delta = ScanEmbedDelta(etag=f'"{hashlib.sha256(body).hexdigest()[:32]}"', gzip_body=gzip.compress(body, 6))
    _delta_cache.set(delta)
    return delta


def run_scan_embed_refresh() -> ScanIndexRefreshReport:
    """Un passage complet dans sa propre session (à lancer hors de la boucle asyncio)."""
    db = SessionLocal()
    try:
        return refresh_scan_embed_cards(db)
    finally:
        db.close()


async def scan_embed_refresh_loop_async() -> None:
    """Complète l'index visuel peu après le démarrage, puis chaque nuit ; un passage incomplet est repris une heure après."""
    settings = get_settings()
    await asyncio.sleep(_STARTUP_DELAY_SEC)
    while True:
        is_run_complete = False
        try:
            report = await asyncio.to_thread(run_scan_embed_refresh)
            logger.info("Scan embedding refresh: %s", report)
            is_run_complete = not report.unavailable_locales
        except Exception:
            logger.exception("Scan embedding refresh crashed")
        await asyncio.sleep(
            seconds_until_next_run(settings.scan_embed_refresh_hour_local)
            if is_run_complete
            else _RETRY_AFTER_INCOMPLETE_RUN_SEC
        )
