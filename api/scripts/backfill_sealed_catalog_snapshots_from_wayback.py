# -*- coding: utf-8 -*-
"""
Rattrapage ponctuel des relevés Cardmarket des scellés depuis les captures Wayback du guide de prix.

Télécharge chaque capture quotidienne archivée de ``price_guide_6.json``, en extrait le prix de référence
de chaque produit des catégories scellées (même règle que ``resolve_market_price_eur``), et écrit
``api/data/sealed_catalog_price_backfill.json`` que l'API importe au démarrage dans ``sealed_catalog_price_snapshots``.

Usage (depuis la racine du repo) : ``python api/scripts/backfill_sealed_catalog_snapshots_from_wayback.py``
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
API_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(API_DIR))

from cardmarket_api.services.card_price_service import CardPriceService  # noqa: E402
from services.sealed_catalog_price_history_service import SEALED_GUIDE_CATEGORY_IDS  # noqa: E402

GUIDE_URL = "https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_6.json"
CDX_URL = (
    "https://web.archive.org/cdx/search/cdx?url=" + GUIDE_URL + "&output=json&fl=timestamp,statuscode"
    "&filter=statuscode:200&collapse=timestamp:8&limit=400"
)
CACHE_DIR = API_DIR / "var" / "wayback_price_guide_cache"
OUT_PATH = API_DIR / "data" / "sealed_catalog_price_backfill.json"
#: Captures plus anciennes ignorées : un point isolé des mois avant les autres ne fait pas une courbe lisible.
MAX_CAPTURE_AGE_DAYS = 200
UA = {"User-Agent": "Mozilla/5.0 (compatible; GoupixDex/1.0; +https://goupixdex.dibodev.fr)"}


def _get_with_retry(client: httpx.Client, url: str, *, attempts: int = 6) -> httpx.Response | None:
    """GET tolérant aux indisponibilités passagères d'archive.org."""
    for attempt in range(attempts):
        try:
            resp = client.get(url, headers=UA, timeout=180.0, follow_redirects=True)
        except httpx.HTTPError:
            resp = None
        if resp is not None and resp.status_code == 200 and not resp.text.lstrip().startswith("<html"):
            return resp
        time.sleep(8.0 * (attempt + 1))
    return None


def list_capture_timestamps(client: httpx.Client) -> list[str]:
    """Horodatages Wayback (un par jour) des captures réussies du guide."""
    resp = _get_with_retry(client, CDX_URL)
    if resp is None:
        raise RuntimeError("Index Wayback injoignable.")
    rows = resp.json()[1:]
    oldest_allowed = (datetime.now(UTC) - timedelta(days=MAX_CAPTURE_AGE_DAYS)).strftime("%Y%m%d")
    return [row[0] for row in rows if row[1] == "200" and row[0][:8] >= oldest_allowed]


def load_capture(client: httpx.Client, timestamp: str) -> dict[str, Any] | None:
    """Contenu JSON d'une capture (cache disque), ``None`` si le téléchargement échoue."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{timestamp}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            path.unlink()
    resp = _get_with_retry(client, f"https://web.archive.org/web/{timestamp}id_/{GUIDE_URL}")
    if resp is None:
        return None
    try:
        payload = resp.json()
    except ValueError:
        return None
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return payload


def main() -> int:
    points: dict[str, dict[str, float]] = {}
    with httpx.Client() as client:
        timestamps = list_capture_timestamps(client)
        print(f"{len(timestamps)} capture(s) Wayback : {timestamps[0][:8]} -> {timestamps[-1][:8]}", flush=True)
        for timestamp in timestamps:
            payload = load_capture(client, timestamp)
            if payload is None:
                print(f"  {timestamp[:8]} : téléchargement impossible, ignorée", flush=True)
                continue
            created_at = str(payload.get("createdAt") or timestamp[:8])
            day = created_at[:10] if "-" in created_at else f"{created_at[:4]}-{created_at[4:6]}-{created_at[6:8]}"
            kept = 0
            for row in payload.get("priceGuides") or []:
                if not isinstance(row, dict) or row.get("idCategory") not in SEALED_GUIDE_CATEGORY_IDS:
                    continue
                price = CardPriceService.pick_reference_eur_from_mapping(row)
                if price is None:
                    continue
                points.setdefault(str(row["idProduct"]), {})[day] = round(float(price), 2)
                kept += 1
            print(f"  {timestamp[:8]} -> {day} : {kept} scellés", flush=True)
    series = {
        id_product: sorted([[day, price] for day, price in by_day.items()], key=lambda point: point[0])
        for id_product, by_day in points.items()
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    OUT_PATH.write_text(
        json.dumps({"v": 1, "generated_at": generated_at, "points": series}, separators=(",", ":")),
        encoding="utf-8",
    )
    total = sum(len(values) for values in series.values())
    print(f"terminé : {len(series)} produits, {total} points -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
