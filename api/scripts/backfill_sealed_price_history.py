# -*- coding: utf-8 -*-
"""
Rattrapage ponctuel de l'historique de prix TCGplayer de tout le catalogue scellé.

Pour chaque produit du catalogue qui a un prix, lit l'historique public TCGplayer
(30 points quotidiens + 30 points tous les 3 jours) et complète ``web/public/sealed-catalog/history/{n}.json``
sans écraser les relevés déjà présents. Les réponses sont mises en cache dans ``api/var/tcgplayer_history_cache/``
pour pouvoir reprendre après une interruption.

Usage (depuis la racine du repo) : ``python api/scripts/backfill_sealed_price_history.py``
Pour aller plus vite : plusieurs ``--fetch-only --worker K --workers N`` en parallèle (cache seulement),
puis une exécution normale qui fusionne tout depuis le cache.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from build_sealed_catalog import (
    HISTORY_DIR,
    HISTORY_VERSION,
    OUT_DIR,
    TCGPLAYER_HISTORY_PAUSE_SEC,
    TCGPLAYER_HISTORY_RANGES,
    TcgplayerBlockedError,
    fetch_tcgplayer_price_history,
    history_shard,
    merge_history_points,
)

CACHE_DIR = Path(__file__).resolve().parent.parent / "var" / "tcgplayer_history_cache"


def _cached_history(client: httpx.Client, tp: int, range_name: str, *, allow_fetch: bool = True) -> list[list[Any]]:
    """Historique d'un produit pour une plage, servi depuis le cache disque s'il existe ; un échec de lecture n'est pas mis en cache."""
    path = CACHE_DIR / f"{tp}_{range_name}.json"
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(cached, list):
                return cached
        except ValueError:
            pass
    if not allow_fetch:
        return []
    points = fetch_tcgplayer_price_history(client, tp, range_name)
    if points is None:
        return []
    path.write_text(json.dumps(points, separators=(",", ":")), encoding="utf-8")
    time.sleep(TCGPLAYER_HISTORY_PAUSE_SEC)
    return points


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--worker", type=int, default=0)
    parser.add_argument("--fetch-only", action="store_true", help="remplit le cache sans écrire les fichiers d'historique")
    args = parser.parse_args()
    payload = json.loads((OUT_DIR / "sealed-v2.json").read_text(encoding="utf-8"))
    products = [
        product
        for index, product in enumerate(
            product
            for serie in payload["series"]
            for expansion in serie["expansions"]
            for product in expansion["products"]
            if product.get("price") is not None
        )
        if index % args.workers == args.worker
    ]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    if args.fetch_only:
        with httpx.Client() as client:
            for index, product in enumerate(products, start=1):
                try:
                    for range_name in TCGPLAYER_HISTORY_RANGES:
                        _cached_history(client, int(product["tp"]), range_name)
                except TcgplayerBlockedError as exc:
                    print(f"worker {args.worker}: arrêt, {exc}", flush=True)
                    return 2
                if index % 100 == 0 or index == len(products):
                    print(f"worker {args.worker}: {index}/{len(products)} produits en cache", flush=True)
        return 0
    shards: dict[int, dict[str, Any]] = {}
    for shard in range(64):
        path = HISTORY_DIR / f"{shard}.json"
        loaded: Any = None
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                loaded = None
        shards[shard] = (
            {"v": HISTORY_VERSION, "products": loaded["products"]}
            if isinstance(loaded, dict) and isinstance(loaded.get("products"), dict)
            else {"v": HISTORY_VERSION, "products": {}}
        )

    filled = 0
    empty = 0
    blocked = False
    started = time.monotonic()
    with httpx.Client() as client:
        for index, product in enumerate(products, start=1):
            tp = int(product["tp"])
            points: list[list[Any]] = []
            for range_name in TCGPLAYER_HISTORY_RANGES:
                try:
                    fetched = _cached_history(client, tp, range_name, allow_fetch=not blocked)
                except TcgplayerBlockedError as exc:
                    blocked = True
                    print(f"arrêt des lectures ({exc}) : fusion de ce qui est déjà en cache", flush=True)
                    fetched = _cached_history(client, tp, range_name, allow_fetch=False)
                points = merge_history_points(points, fetched)
            if points:
                shard = shards[history_shard(tp)]
                shard["products"][str(tp)] = merge_history_points(shard["products"].get(str(tp)) or [], points)
                filled += 1
            else:
                empty += 1
            if index % 100 == 0 or index == len(products):
                elapsed = time.monotonic() - started
                print(f"{index}/{len(products)} produits | {filled} avec historique, {empty} sans | {elapsed:.0f}s", flush=True)
                for shard_index, data in shards.items():
                    (HISTORY_DIR / f"{shard_index}.json").write_text(
                        json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
                    )
    total_points = sum(len(series) for data in shards.values() for series in data["products"].values())
    print(f"terminé : {filled} produits avec historique, {total_points} points au total -> {HISTORY_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
