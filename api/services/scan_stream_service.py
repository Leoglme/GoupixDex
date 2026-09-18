"""
Async pipeline: a card photo arrives, we run OCR, resolve the TCGdex id,
then either insert / increment a ``CollectionCard`` row (``direction='in'``)
or decrement / delete it (``direction='out'``, "cash register" checkout),
broadcasting each phase to the user's WebSocket via
:mod:`services.scan_stream_hub`.

Design goals (in priority order):

1. **Never block the phone request.** ``submit_scan`` returns an ``event_id``
   in < 100 ms after persisting the image bytes; the heavy work runs in an
   ``asyncio`` background task.
2. **Every frame gets an answer.** Frames rejected by the pre-OCR gate publish
   a transient ``dropped`` event (with the reason) instead of disappearing:
   the phone can vibrate/flash so the user never wonders whether the scan
   "worked".
3. **Tolerate Groq backpressure.** A module-level :class:`asyncio.Semaphore`
   caps concurrent vision calls (default 1) — busy uploads queue silently
   rather than tipping the rate limit.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from typing import Any, Literal

from core.database import SessionLocal
from models.collection_card import CollectionCard
from services import collection_card_service
from services.card_image_enhance import enhance_for_ocr
from services.card_image_gate import assess_card_image
from services.collection_card_lookup_service import fetch_card_for_collection
from services.ocr_service import extract_card_from_bytes
from services.scan_service import detect_physical_language_from_ocr
from services.scan_stream_hub import get_scan_stream_hub
from services.tcgdex_client_service import SUPPORTED_LOCALES
from services.tcgdex_lookup_service import resolve_tcgdex_card_id_from_ocr

logger = logging.getLogger(__name__)

ScanDirection = Literal["in", "out"]

#: Max concurrent OCR calls across all users on this process.
#: Qwen 3.6 free tier is 8k TPM — more than one inflight vision call 429s immediately.
_GROQ_PARALLELISM = 1
_groq_sem = asyncio.Semaphore(_GROQ_PARALLELISM)

#: Per-user debounce so a "cash register" frame stream becomes *one* Groq call
#: per physical card instead of a burst (the source of the 429s). The client
#: re-arms only after the card left the frame, so 1.5 s is enough to catch
#: stray duplicate frames without eating a legitimate next card.
_MIN_OCR_INTERVAL_SEC = 1.5
_last_accept: dict[int, float] = {}

#: Accepted frames wait in a small per-user FIFO instead of being dropped
#: while the previous card is still in the (slow) OCR pipeline — the user can
#: chain cards at their own pace and nothing is lost.
_MAX_QUEUED_PER_USER = 3
_user_queues: dict[int, asyncio.Queue[dict[str, Any]]] = {}
_user_consumers: dict[int, asyncio.Task[None]] = {}

#: Keep strong references to background tasks: ``asyncio.create_task`` results
#: may otherwise be garbage-collected mid-flight (scans silently vanishing).
_background_tasks: set[asyncio.Task[None]] = set()


def _now_iso() -> float:
    return time.time()


def _prune_last_accept(now: float) -> None:
    """Bound the per-user debounce map (long-lived process hygiene)."""
    if len(_last_accept) <= 500:
        return
    stale = [uid for uid, ts in _last_accept.items() if now - ts > 3600]
    for uid in stale:
        _last_accept.pop(uid, None)


def _public_event(
    *,
    event_id: str,
    user_id: int,
    status: str,
    physical_language: str,
    direction: ScanDirection = "in",
    image_preview_data_url: str | None = None,
    ocr: dict[str, Any] | None = None,
    tcgdex_card_id: str | None = None,
    collection_card: dict[str, Any] | None = None,
    error: str | None = None,
    created: bool | None = None,
    deleted: bool | None = None,
    remaining_quantity: int | None = None,
    drop_reason: str | None = None,
) -> dict[str, Any]:
    """Shape published to the WebSocket (snake_case, JSON-serialisable)."""
    return {
        "event_id": event_id,
        "user_id": user_id,
        "status": status,
        "physical_language": physical_language,
        "direction": direction,
        "image_preview_data_url": image_preview_data_url,
        "ocr": ocr,
        "tcgdex_card_id": tcgdex_card_id,
        "collection_card": collection_card,
        "created": created,
        "deleted": deleted,
        "remaining_quantity": remaining_quantity,
        "drop_reason": drop_reason,
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


def _short_error(exc: Exception, prefix: str) -> str:
    """User-facing error line — never dump a raw provider response body."""
    text = " ".join(str(exc).split())
    if len(text) > 160:
        text = text[:160] + "…"
    return f"{prefix} : {text}" if text else prefix


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


def _decrement_or_delete(
    user_id: int,
    tcgdex_card_id: str,
    language: str,
) -> tuple[dict[str, Any] | None, bool, int]:
    """
    Checkout counterpart of :func:`_add_or_increment`.

    Finds the user's row for ``tcgdex_card_id`` — exact language first, then
    any language when exactly one row matches — and decrements its quantity,
    deleting the row when it reaches zero.

    Returns ``(card_dict, deleted, remaining_quantity)``;
    ``card_dict`` is ``None`` when the card is not in the collection.
    """
    db = SessionLocal()
    try:
        row = collection_card_service.find_existing_for_user(
            db,
            user_id,
            tcgdex_card_id=tcgdex_card_id,
            language=language,
        )
        if row is None:
            candidates = (
                db.query(CollectionCard)
                .filter(
                    CollectionCard.user_id == user_id,
                    CollectionCard.tcgdex_card_id == tcgdex_card_id,
                )
                .all()
            )
            if len(candidates) == 1:
                row = candidates[0]
        if row is None:
            return None, False, 0

        snapshot = collection_card_service.collection_card_to_dict(row)
        remaining = int(row.quantity) - 1
        if remaining <= 0:
            db.delete(row)
            db.commit()
            snapshot["quantity"] = 0
            return snapshot, True, 0

        row.quantity = remaining
        db.commit()
        db.refresh(row)
        return collection_card_service.collection_card_to_dict(row), False, remaining
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
    direction: ScanDirection,
    user_hint: str | None,
) -> None:
    """
    End-to-end processing for a single scan event. The gate already passed and
    the ``queued`` event (with preview) was already published at admission.
    """
    hub = get_scan_stream_hub()
    preview = _short_preview_data_url(image_bytes, mime)
    loop = asyncio.get_running_loop()
    stage_started_at = time.monotonic()
    stage_timings_ms: dict[str, int] = {}

    def _mark_stage(stage: str) -> None:
        """Record elapsed ms since the previous stage boundary (log-only telemetry)."""
        nonlocal stage_started_at
        now = time.monotonic()
        stage_timings_ms[stage] = int((now - stage_started_at) * 1000)
        stage_started_at = now

    # --- 1. OCR (Groq vision). Sync function in a thread to avoid blocking.
    async with _groq_sem:
        # Intermediate events skip the preview on purpose: the client merges by
        # event_id and keeps the thumbnail it already has (smaller WS frames).
        await hub.publish(
            user_id,
            _public_event(
                event_id=event_id,
                user_id=user_id,
                status="ocr_running",
                physical_language=physical_language,
                direction=direction,
            ),
        )
        # Auto-contrast + light sharpening on the deskewed card recovers OCR
        # accuracy on soft / flat / over-lit shots without ever degrading a
        # clean one. Runs in the executor so we don't block the loop.
        ocr_bytes = await loop.run_in_executor(None, lambda: enhance_for_ocr(image_bytes))
        try:
            # PokéWallet enrichment is *on* here even though we skip pricing
            # later: it gives us a reliable English Pokémon name for JA prints
            # (the OCR alone returns the kanji name), which is critical for the
            # ``/cards?name=...`` TCGdex search to land.
            ocr_result = await loop.run_in_executor(
                None,
                lambda: extract_card_from_bytes(
                    ocr_bytes,
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
                    direction=direction,
                    image_preview_data_url=preview,
                    error=_short_error(exc, "OCR indisponible"),
                ),
            )
            return

    _mark_stage("ocr")
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
            direction=direction,
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
                ocr_card_number_denominator=ocr_payload.get("card_number_denominator"),
            ),
        )
    except Exception as exc:
        logger.warning("scan-stream TCGdex lookup failed for event=%s: %s", event_id, exc)
        tcgdex_card_id = None
    _mark_stage("resolve")
    logger.info(
        "scan-stream timings event=%s ocr=%sms resolve=%sms card=%s",
        event_id,
        stage_timings_ms.get("ocr"),
        stage_timings_ms.get("resolve"),
        tcgdex_card_id or "none",
    )

    if not tcgdex_card_id:
        await hub.publish(
            user_id,
            _public_event(
                event_id=event_id,
                user_id=user_id,
                status="needs_review",
                physical_language=resolved_language,
                direction=direction,
                image_preview_data_url=preview,
                ocr=ocr_payload,
                error=(
                    "Carte non identifiée automatiquement — touchez « ajouter manuellement » "
                    "pour la finir depuis le catalogue."
                ),
            ),
        )
        return

    # --- 3a. Checkout mode: decrement / delete straight from the local row —
    # no TCGdex metadata fetch needed, the row already carries everything.
    if direction == "out":
        try:
            card_dict, deleted, remaining = await loop.run_in_executor(
                None,
                lambda: _decrement_or_delete(user_id, tcgdex_card_id, resolved_language),
            )
        except Exception as exc:
            logger.exception("scan-stream DB decrement failed event=%s", event_id)
            await hub.publish(
                user_id,
                _public_event(
                    event_id=event_id,
                    user_id=user_id,
                    status="failed",
                    physical_language=resolved_language,
                    direction=direction,
                    image_preview_data_url=preview,
                    ocr=ocr_payload,
                    tcgdex_card_id=tcgdex_card_id,
                    error=_short_error(exc, "Sortie impossible"),
                ),
            )
            return

        if card_dict is None:
            await hub.publish(
                user_id,
                _public_event(
                    event_id=event_id,
                    user_id=user_id,
                    status="not_in_collection",
                    physical_language=resolved_language,
                    direction=direction,
                    image_preview_data_url=preview,
                    ocr=ocr_payload,
                    tcgdex_card_id=tcgdex_card_id,
                    error="Cette carte n'est pas dans votre collection.",
                ),
            )
            return

        await hub.publish(
            user_id,
            _public_event(
                event_id=event_id,
                user_id=user_id,
                status="removed",
                physical_language=resolved_language,
                direction=direction,
                image_preview_data_url=preview,
                ocr=ocr_payload,
                tcgdex_card_id=tcgdex_card_id,
                collection_card=card_dict,
                deleted=deleted,
                remaining_quantity=remaining,
            ),
        )
        return

    # --- 3b. Intake mode: fetch full metadata + insert into ``collection_cards``.
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
                direction=direction,
                image_preview_data_url=preview,
                ocr=ocr_payload,
                tcgdex_card_id=tcgdex_card_id,
                error=_short_error(exc, "Méta-données TCGdex indisponibles"),
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
                direction=direction,
                image_preview_data_url=preview,
                ocr=ocr_payload,
                tcgdex_card_id=tcgdex_card_id,
                error=_short_error(exc, "Insertion impossible"),
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
            direction=direction,
            image_preview_data_url=preview,
            ocr=ocr_payload,
            tcgdex_card_id=tcgdex_card_id,
            collection_card=collection_card_service.collection_card_to_dict(row),
            created=created,
        ),
    )


async def _publish_dropped(
    *,
    event_id: str,
    user_id: int,
    physical_language: str,
    direction: ScanDirection,
    reason: str,
    message: str,
) -> None:
    """Transient feedback for a frame the gate rejected (never stored in history)."""
    hub = get_scan_stream_hub()
    await hub.publish(
        user_id,
        _public_event(
            event_id=event_id,
            user_id=user_id,
            status="dropped",
            physical_language=physical_language,
            direction=direction,
            drop_reason=reason,
            error=message,
        ),
        transient=True,
    )


async def _consume_user_queue(user_id: int) -> None:
    """Drain the user's scan FIFO one card at a time, then retire itself."""
    me = asyncio.current_task()
    queue = _user_queues.get(user_id)
    if queue is None:
        if _user_consumers.get(user_id) is me:
            _user_consumers.pop(user_id, None)
        return
    try:
        while True:
            try:
                job = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                await _process_scan(**job)
            except Exception:
                logger.exception("scan-stream: pipeline crashed event=%s", job.get("event_id"))
    finally:
        if _user_consumers.get(user_id) is me:
            _user_consumers.pop(user_id, None)
        if queue.empty():
            _user_queues.pop(user_id, None)
        else:
            # A job slipped in between our last poll and this cleanup.
            _ensure_consumer(user_id)


def _ensure_consumer(user_id: int) -> None:
    """Start the per-user queue consumer when none is running."""
    task = _user_consumers.get(user_id)
    if task is not None and not task.done():
        return
    task = asyncio.create_task(_consume_user_queue(user_id))
    _user_consumers[user_id] = task
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _admit_scan(
    *,
    event_id: str,
    user_id: int,
    image_bytes: bytes,
    filename: str,
    mime: str,
    physical_language: str,
    direction: ScanDirection,
    user_hint: str | None,
) -> None:
    """
    Pre-Groq admission. A streaming camera sends many frames; we only let one
    through per real card:

    * **debounce** — last accepted frame < ``_MIN_OCR_INTERVAL_SEC`` ago;
    * **card pre-detection** — empty / blurry / not-a-card;
    * **bounded FIFO** — accepted frames queue up (max ``_MAX_QUEUED_PER_USER``)
      behind the slow OCR pipeline instead of being thrown away.

    Every rejection publishes a transient ``dropped`` event so the phone can
    tell the user *why* nothing happened (the historical silent drops were the
    single biggest "it's broken" report). Accepted frames publish ``queued``
    immediately, before OCR even starts.
    """
    now = time.time()
    _prune_last_accept(now)
    if now - _last_accept.get(user_id, 0.0) < _MIN_OCR_INTERVAL_SEC:
        logger.debug("scan-stream: drop (debounce) user=%s", user_id)
        await _publish_dropped(
            event_id=event_id,
            user_id=user_id,
            physical_language=physical_language,
            direction=direction,
            reason="debounce",
            message="Photo trop rapprochée de la précédente — ignorée.",
        )
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
        await _publish_dropped(
            event_id=event_id,
            user_id=user_id,
            physical_language=physical_language,
            direction=direction,
            reason=str(gate.reason or "not_a_card"),
            message="Aucune carte nette détectée sur la photo — réessayez.",
        )
        return

    queue = _user_queues.setdefault(user_id, asyncio.Queue(maxsize=_MAX_QUEUED_PER_USER))
    job: dict[str, Any] = {
        "event_id": event_id,
        "user_id": user_id,
        "image_bytes": image_bytes,
        "filename": filename,
        "mime": mime,
        "physical_language": physical_language,
        "direction": direction,
        "user_hint": user_hint,
    }
    try:
        queue.put_nowait(job)
    except asyncio.QueueFull:
        logger.debug("scan-stream: drop (queue_full) user=%s", user_id)
        await _publish_dropped(
            event_id=event_id,
            user_id=user_id,
            physical_language=physical_language,
            direction=direction,
            reason="queue_full",
            message="File de scan pleine — laissez les cartes en cours se terminer.",
        )
        return

    _last_accept[user_id] = now
    hub = get_scan_stream_hub()
    await hub.publish(
        user_id,
        _public_event(
            event_id=event_id,
            user_id=user_id,
            status="queued",
            physical_language=physical_language,
            direction=direction,
            image_preview_data_url=_short_preview_data_url(image_bytes, mime),
        ),
    )
    _ensure_consumer(user_id)


#: Debounce for on-device match commits — the phone re-arm gate already spaces
#: real cards out; this only guards against a double POST for the same card.
_MATCH_DEBOUNCE_SEC = 1.2
_last_match_accept: dict[tuple[int, str, str], float] = {}


async def _process_matched_scan(
    *,
    event_id: str,
    user_id: int,
    tcgdex_card_id: str,
    physical_language: str,
    direction: ScanDirection,
) -> None:
    """
    Commit a card identified **on the phone** by the visual match index: no
    photo, no OCR, no TCGdex resolution — straight to the collection, with the
    same ``queued`` → ``added`` / ``removed`` events the OCR pipeline emits so
    every listening client renders it identically (just seconds earlier).
    """
    hub = get_scan_stream_hub()
    loop = asyncio.get_running_loop()

    now = time.time()
    key = (user_id, tcgdex_card_id.lower(), direction)
    if now - _last_match_accept.get(key, 0.0) < _MATCH_DEBOUNCE_SEC:
        await _publish_dropped(
            event_id=event_id,
            user_id=user_id,
            physical_language=physical_language,
            direction=direction,
            reason="debounce",
            message="Scan identique trop rapproché — ignoré.",
        )
        return
    _last_match_accept[key] = now
    if len(_last_match_accept) > 512:
        cutoff = now - 60.0
        for stale_key in [k for k, ts in _last_match_accept.items() if ts < cutoff]:
            _last_match_accept.pop(stale_key, None)

    await hub.publish(
        user_id,
        _public_event(
            event_id=event_id,
            user_id=user_id,
            status="queued",
            physical_language=physical_language,
            direction=direction,
            tcgdex_card_id=tcgdex_card_id,
        ),
    )

    if direction == "out":
        try:
            card_dict, deleted, remaining = await loop.run_in_executor(
                None,
                lambda: _decrement_or_delete(user_id, tcgdex_card_id, physical_language),
            )
        except Exception as exc:
            logger.exception("scan-match DB decrement failed event=%s", event_id)
            await hub.publish(
                user_id,
                _public_event(
                    event_id=event_id,
                    user_id=user_id,
                    status="failed",
                    physical_language=physical_language,
                    direction=direction,
                    tcgdex_card_id=tcgdex_card_id,
                    error=_short_error(exc, "Sortie impossible"),
                ),
            )
            return
        if card_dict is None:
            await hub.publish(
                user_id,
                _public_event(
                    event_id=event_id,
                    user_id=user_id,
                    status="not_in_collection",
                    physical_language=physical_language,
                    direction=direction,
                    tcgdex_card_id=tcgdex_card_id,
                    error="Cette carte n'est pas dans votre collection.",
                ),
            )
            return
        await hub.publish(
            user_id,
            _public_event(
                event_id=event_id,
                user_id=user_id,
                status="removed",
                physical_language=physical_language,
                direction=direction,
                tcgdex_card_id=tcgdex_card_id,
                collection_card=card_dict,
                deleted=deleted,
                remaining_quantity=remaining,
            ),
        )
        return

    try:
        meta = await loop.run_in_executor(
            None,
            lambda: fetch_card_for_collection(
                tcgdex_card_id=tcgdex_card_id,
                physical_language=physical_language,
                fallback_name_en=None,
            ),
        )
        row, created = await loop.run_in_executor(
            None,
            lambda: _add_or_increment(user_id, meta, notes=None),
        )
    except Exception as exc:
        logger.warning("scan-match commit failed event=%s card=%s: %s", event_id, tcgdex_card_id, exc)
        await hub.publish(
            user_id,
            _public_event(
                event_id=event_id,
                user_id=user_id,
                status="failed",
                physical_language=physical_language,
                direction=direction,
                tcgdex_card_id=tcgdex_card_id,
                error=_short_error(exc, "Ajout impossible"),
            ),
        )
        return

    await hub.publish(
        user_id,
        _public_event(
            event_id=event_id,
            user_id=user_id,
            status="added",
            physical_language=physical_language,
            direction=direction,
            tcgdex_card_id=tcgdex_card_id,
            collection_card=collection_card_service.collection_card_to_dict(row),
            created=created,
        ),
    )


def submit_matched_scan(
    *,
    user_id: int,
    tcgdex_card_id: str,
    physical_language: str,
    direction: ScanDirection = "in",
) -> str:
    """
    Enqueue the commit of a card identified on-device (visual match). Returns
    the ``event_id`` the WebSocket events will carry.
    """
    event_id = secrets.token_urlsafe(10)
    task = asyncio.create_task(
        _process_matched_scan(
            event_id=event_id,
            user_id=user_id,
            tcgdex_card_id=tcgdex_card_id,
            physical_language=physical_language,
            direction=direction,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return event_id


def submit_scan(
    *,
    user_id: int,
    image_bytes: bytes,
    filename: str,
    mime: str,
    physical_language: str,
    direction: ScanDirection = "in",
    user_hint: str | None,
) -> str:
    """
    Enqueue a scan for processing. The returned ``event_id`` lets the phone
    correlate the upload with the websocket events it sees (or the user can
    just ignore it — they're delivered in upload order anyway).
    """
    event_id = secrets.token_urlsafe(10)
    task = asyncio.create_task(
        _admit_scan(
            event_id=event_id,
            user_id=user_id,
            image_bytes=image_bytes,
            filename=filename,
            mime=mime,
            physical_language=physical_language,
            direction=direction,
            user_hint=user_hint,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return event_id
