"""
Build static catalogue browse JSON (series + sets) for instant client load.

Outputs under ``web/public/catalog-index/``:

- ``manifest.json`` — version, generation time, per-locale filenames
- ``browse-{locale}-v{N}.json`` — slim tree consumed by the Nuxt catalogue page

Usage (from repo root)::

    python api/scripts/build_catalog_browse_index.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
API_DIR = SCRIPT_DIR.parent
REPO_ROOT = API_DIR.parent
OUT_DIR = REPO_ROOT / "web" / "public" / "catalog-index"

INDEX_VERSION = 2
LOCALES = ("fr", "en", "ja")


def _setup_import_path() -> None:
    if str(API_DIR) not in sys.path:
        sys.path.insert(0, str(API_DIR))


def build_locale_payload(locale: str) -> list[dict]:
    from services.catalog_browse_service import browse_catalog_for_ui, _cache  # noqa: PLC0415
    from services.catalog_set_logos import slim_browse_series_row  # noqa: PLC0415

    _cache._store.clear()
    raw = browse_catalog_for_ui(locale)
    return [slim_browse_series_row(s) for s in raw if isinstance(s, dict)]


def main() -> int:
    _setup_import_path()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest_locales: dict[str, str] = {}
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for loc in LOCALES:
        print(f"Building browse index for {loc}…", flush=True)
        series = build_locale_payload(loc)
        filename = f"browse-{loc}-v{INDEX_VERSION}.json"
        out_path = OUT_DIR / filename
        payload = {"locale": loc, "version": INDEX_VERSION, "generated_at": generated_at, "series": series}
        out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        manifest_locales[loc] = filename
        print(f"  -> {len(series)} series, {out_path.stat().st_size // 1024} KiB", flush=True)

    manifest = {
        "version": INDEX_VERSION,
        "generated_at": generated_at,
        "locales": manifest_locales,
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Wrote {OUT_DIR / 'manifest.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
