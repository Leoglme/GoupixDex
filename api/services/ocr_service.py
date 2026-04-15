"""Wraps Groq vision OCR for card photos."""

from __future__ import annotations

import logging
from pathlib import Path

from app_types.groq_vision import GroqVisionCardCollectorResult, GroqVisionImageMimeType
from services.groq_vision_client import GroqVisionClient

logger = logging.getLogger(__name__)


def _mime_from_name(filename: str) -> GroqVisionImageMimeType:
    suffix = Path(filename).suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


def extract_card_from_bytes(
    data: bytes,
    filename: str,
    *,
    enrich_from_pokewallet: bool = True,
    user_hint: str | None = None,
) -> GroqVisionCardCollectorResult:
    """
    Run OCR-style extraction on raw image bytes.

    Args:
        data: Image file bytes.
        filename: Original filename (used to pick MIME type).
        enrich_from_pokewallet: When True, enables PokéWallet + PokéAPI enrichment when keys exist.
        user_hint: Optional short text to help the vision model (Pokémon, set code, etc.).
    """
    client = GroqVisionClient()
    mime = _mime_from_name(filename)
    opts: dict[str, bool | float | str] = {
        "resolve_english_name_from_poke_wallet": enrich_from_pokewallet,
    }
    if user_hint is not None:
        t = " ".join(user_hint.strip().split())
        if t:
            opts["user_hint"] = t[:500]
    return client.extract_card_collector_from_image_bytes(data, mime, opts)  # type: ignore[arg-type]
