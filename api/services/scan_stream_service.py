"""
Async pipeline: a card photo arrives, we run OCR, resolve the TCGdex id,
insert / increment a ``CollectionCard`` row, and broadcast each phase to the
user's WebSocket via :mod:`services.scan_stream_hub`.

Design goals (in priority order):

1. **Never block the phone request.** ``submit_scan`` returns an ``event_id``
   in < 100 ms after persisting the image bytes; the heavy work runs in an
   ``asyncio`` background task.
2. **Make the desktop UI feel "snappy".** Every state transition (queued →
   ocr_done → identified → added | failed) is published right away so the
   listener can animate the card landing in the binder.
3. **Tolerate Groq backpressure.** A module-level :class:`asyncio.Semaphore`
   caps concurrent vision calls (default 4) — busy uploads queue silently
   rather than tipping the rate limit.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from typing import Any

from core.database import SessionLocal
from models.collection_card import CollectionCard
from services import collection_card_service
from services.card_image_gate import assess_card_image
from services.collection_card_lookup_service import fetch_card_for_collection
from services.ocr_service import extract_card_from_bytes
from services.scan_service import detect_physical_language_from_ocr
from services.scan_stream_hub import get_scan_stream_hub
from services.tcgdex_client_service import SUPPORTED_LOCALES
from services.tcgdex_lookup_service import resolve_tcgdex_card_id_from_ocr

logger = logging.getLogger(__name__)

#: Max concurrent OCR calls across all users on this process.
_GROQ_PARALLELISM = 4
_groq_sem = asyncio.Semaphore(_GROQ_PARALLELISM)

#: Per-user guards so a "cash register" frame stream becomes *one* Groq call
#: per physical card instead of a burst (the source of the 429s).
#: - ``_inflight``: a scan is already being processed for this user.
#: - ``_last_accept``: epoch of the last frame that passed the gate.
_MIN_OCR_INTERVAL_SEC = 2.5
_inflight: set[int] = set()
_last_accept: dict[int, float] = {}


def _now_iso() -> float:
    return time.time()


def _public_event(
    *,
    event_id: str,
    user_id: int,
    status: str,
    physical_language: str,
    image_preview_data_url: str | None = None,
    ocr: dict[str, Any] | None = None,
    tcgdex_card_id: str | None = None,
    collection_card: dict[str, Any] | None = None,
    error: str | None = None,
    created: bool | None = None,
) -> dict[str, Any]:
    """Shape published to the WebSocket (snake_case, JSON-serialisable)."""
    return {
        "event_id": event_id,
        "user_id": user_id,
        "status": status,
        "physical_language": physical_language,
        "image_preview_data_url": image_preview_data_url,
        "ocr": ocr,
        "tcgdex_card_id": tcgdex_card_id,
        "collection_card": collection_card,
        "created": created,
        "error": error,
        "ts": _now_iso(),
    }


def _short_preview_data_url(image_bytes: bytes, mime: str) -> str | None:
    """
    Lightweight preview pushed to the desktop so the placeholder thumbnail
    shows the *exact* photo the phone shot. Caps at ~120 kB to keep the WS
    frame small (above that we just drop the preview).
    """
    if len(image_bytes) > 120_000:
        return None
    import base64

    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _add_or_increment(
    user_id: int,
    meta: dict[str, Any],
    *,
    notes: str | None,
) -> tuple[CollectionCard, bool]:
    """
    Insert a new row or bump the quantity when ``(tcgdex_card_id, language)``
    already exists for this user. Returns ``(row, created)``.
    """
    db = SessionLocal()
    try:
        existing = collection_card_service.find_existing_for_user(
            db,
            user_id,
            tcgdex_card_id=meta["tcgdex_card_id"],
            language=meta["language"],
        )
        if existing is not None:
            existing.quantity = int(existing.quantity) + 1
            if notes:
                existing.notes = notes.strip() or existing.notes
            db.commit()
            db.refresh(existing)
            return existing, False

        row = CollectionCard(
            user_id=user_id,
            tcgdex_card_id=meta["tcgdex_card_id"],
            tcgdex_set_id=meta["tcgdex_set_id"],
            set_code=meta["set_code"],
            set_name=meta["set_name"],
            card_number=meta["card_number"],
            card_name_en=meta["card_name_en"],
            card_name_fr=meta["card_name_fr"],
            card_name_ja=meta["card_name_ja"],
            display_name=meta["display_name"],
            rarity=meta["rarity"],
            language=meta["language"],
            image_url=meta["image_url"],
            quantity=1,
            notes=(notes.strip() if notes else None),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row, True
    finally:
        db.close()


async def _process_scan(
    *,
    event_id: str,
    user_id: int,
    image_bytes: bytes,
    filename: str,
    mime: str,
    physical_language: str,
    user_hint: str | None,
) -> None:
    """End-to-end processing for a single scan event (gate already passed)."""
    hub = get_scan_stream_hub()

    preview = _short_preview_data_url(image_bytes, mime)
    await hub.publish(
        user_id,
        _public_event(
            event_id=event_id,
            user_id=user_id,
            status="queued",
            physical_language=physical_language,
            image_preview_data_url=preview,
        ),
    )

    loop = asyncio.get_running_loop()

    # --- 1. OCR (Groq vision). Sync function in a thread to avoid blocking.
    async with _groq_sem:
        await hub.publish(
            user_id,
            _public_event(
                event_id=event_id,
                user_id=user_id,
                status="ocr_running",
                physical_language=physical_language,
                image_preview_data_url=preview,
            ),
        )
        try:
            # PokéWallet enrichment is *on* here even though we skip pricing
            # later: it gives us a reliable English Pokémon name for JA prints
            # (the OCR alone returns the kanji name), which is critical for the
            # ``/cards?name=...`` TCGdex search to land.
            ocr_result = await loop.run_in_executor(
                None,
                lambda: extract_card_from_bytes(
                    image_bytes,
                    filename,
                    enrich_from_pokewallet=True,
                    user_hint=user_hint,
                ),
            )
        except Exception as exc:
            logger.warning("scan-stream OCR failed for event=%s: %s", event_id, exc)
            await hub.publish(
                user_id,
                _public_event(
                    event_id=event_id,
                    user_id=user_id,
                    status="failed",
                    physical_language=physical_language,
                    image_preview_data_url=preview,
                    error=f"OCR indisponible : {exc}",
                ),
            )
            return

    ocr_payload = dict(ocr_result)

    # Auto-detect from OCR unless the caller pinned an explicit locale. From
    # here on every event/lookup uses ``resolved_language`` so the scan page
    # never needs a manual language picker.
    if physical_language in SUPPORTED_LOCALES:
        resolved_language = physical_language
    else:
        resolved_language = detect_physical_language_from_ocr(ocr_payload)

    await hub.publish(
        user_id,
        _public_event(
            event_id=event_id,
            user_id=user_id,
            status="ocr_done",
            physical_language=resolved_language,
            image_preview_data_url=preview,
            ocr=ocr_payload,
        ),
    )

    # --- 2. Resolve the TCGdex card id from the OCR triplet.
    try:
        tcgdex_card_id = await loop.run_in_executor(
            None,
            lambda: resolve_tcgdex_card_id_from_ocr(
                ocr_set_code=ocr_payload.get("set_code"),
                ocr_card_number=ocr_payload.get("card_number"),
                ocr_pokemon_name_english=ocr_payload.get("pokemon_name_english"),
                ocr_pokemon_name=ocr_payload.get("pokemon_name"),
                physical_language=resolved_language,
            ),
        )
    except Exception as exc:
        logger.warning("scan-stream TCGdex lookup failed for event=%s: %s", event_id, exc)
        tcgdex_card_id = None

    if not tcgdex_card_id:
        await hub.publish(
            user_id,
            _public_event(
                event_id=event_id,
                user_id=user_id,
                status="needs_review",
                physical_language=resolved_language,
                image_preview_data_url=preview,
                ocr=ocr_payload,
                error=(
                    "Carte non identifiée automatiquement — touchez « ajouter manuellement » "
                    "pour la finir depuis le catalogue."
                ),
            ),
        )
        return

    # --- 3. Fetch full metadata + insert into ``collection_cards``.
    raw_name_en = ocr_payload.get("pokemon_name_english")
    ocr_name_en = raw_name_en if isinstance(raw_name_en, str) else None
    try:
        meta = await loop.run_in_executor(
            None,
            lambda: fetch_card_for_collection(
                tcgdex_card_id=tcgdex_card_id,
                physical_language=resolved_language,
                fallback_name_en=ocr_name_en,
            ),
        )
    except Exception as exc:
        logger.warning("scan-stream fetch_card_for_collection failed event=%s: %s", event_id, exc)
        await hub.publish(
            user_id,
            _public_event(
                event_id=event_id,
                user_id=user_id,
                status="failed",
                physical_language=resolved_language,
                image_preview_data_url=preview,
                ocr=ocr_payload,
                tcgdex_card_id=tcgdex_card_id,
                error=f"Méta-données TCGdex indisponibles : {exc}",
            ),
        )
        return

    try:
        row, created = await loop.run_in_executor(
            None,
            lambda: _add_or_increment(user_id, meta, notes=None),
        )
    except Exception as exc:
        logger.exception("scan-stream DB insert failed event=%s", event_id)
        await hub.publish(
            user_id,
            _public_event(
                event_id=event_id,
                user_id=user_id,
                status="failed",
                physical_language=resolved_language,
                image_preview_data_url=preview,
                ocr=ocr_payload,
                tcgdex_card_id=tcgdex_card_id,
                error=f"Insertion impossible : {exc}",
            ),
        )
        return

    await hub.publish(
        user_id,
        _public_event(
            event_id=event_id,
            user_id=user_id,
            status="added",
            physical_language=resolved_language,
            image_preview_data_url=preview,
            ocr=ocr_payload,
            tcgdex_card_id=tcgdex_card_id,
            collection_card=collection_card_service.collection_card_to_dict(row),
            created=created,
        ),
    )


async def _run_scan_pipeline(
    *,
    event_id: str,
    user_id: int,
    image_bytes: bytes,
    filename: str,
    mime: str,
    physical_language: str,
    user_hint: str | None,
) -> None:
    """
    Pre-Groq gate. A streaming camera sends many frames; we only let one
    through per real card:

    * **in-flight guard** — a scan is already running for this user → drop.
    * **debounce** — last accepted frame < ``_MIN_OCR_INTERVAL_SEC`` ago → drop.
    * **card pre-detection** — empty / blurry / not-a-card → drop.

    Rejections are silent (no websocket event), so the live feed only shows
    real cards — like the existing phone card-scanner apps. No Groq call is
    made unless a frame clears every check, which is what stops the 429s.
    """
    now = time.time()
    if user_id in _inflight:
        logger.debug("scan-stream: drop (in-flight) user=%s", user_id)
        return
    if now - _last_accept.get(user_id, 0.0) < _MIN_OCR_INTERVAL_SEC:
        logger.debug("scan-stream: drop (debounce) user=%s", user_id)
        return

    loop = asyncio.get_running_loop()
    gate = await loop.run_in_executor(None, lambda: assess_card_image(image_bytes))
    if not gate.is_card:
        logger.debug(
            "scan-stream: drop (%s) user=%s detail=%.1f focus=%.1f fill=%.2f",
            gate.reason,
            user_id,
            gate.detail,
            gate.focus,
            gate.fill,
        )
        return

    _inflight.add(user_id)
    _last_accept[user_id] = now
    try:
        await _process_scan(
            event_id=event_id,
            user_id=user_id,
            image_bytes=image_bytes,
            filename=filename,
            mime=mime,
            physical_language=physical_language,
            user_hint=user_hint,
        )
    finally:
        _inflight.discard(user_id)


def submit_scan(
    *,
    user_id: int,
    image_bytes: bytes,
    filename: str,
    mime: str,
    physical_language: str,
    user_hint: str | None,
) -> str:
    """
    Enqueue a scan for processing. The returned ``event_id`` lets the phone
    correlate the upload with the websocket events it sees (or the user can
    just ignore it — they're delivered in upload order anyway).
    """
    event_id = secrets.token_urlsafe(10)
    asyncio.create_task(
        _run_scan_pipeline(
            event_id=event_id,
            user_id=user_id,
            image_bytes=image_bytes,
            filename=filename,
            mime=mime,
            physical_language=physical_language,
            user_hint=user_hint,
        )
    )
    return event_id
