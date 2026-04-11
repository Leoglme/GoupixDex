"""
Run Groq vision OCR on a card image path and print structured collector JSON.

Usage (from ``api/``):

    python scripts/test_groq_card_ocr.py path/to/card.webp

Requires ``GROQ_API_KEY``. Optional: ``POKE_WALLET_API_KEY`` when using enrichment.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_ROOT / ".env")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python scripts/test_groq_card_ocr.py <image_path>", file=sys.stderr)
        raise SystemExit(2)

    image_path = sys.argv[1].strip()
    if not image_path:
        print("Image path must be non-empty.", file=sys.stderr)
        raise SystemExit(2)

    from services.groq_vision_client import GroqVisionClient

    client = GroqVisionClient()
    result = client.extract_card_collector_from_image_path(
        image_path,
        {
            "include_raw_assistant_json": True,
            "resolve_english_name_from_poke_wallet": True,
        },
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
