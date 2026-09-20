"""
Construit le catalogue statique des produits scellés (parcours par extension).

Source : ``products_nonsingles_6.json`` (bucket public Cardmarket) — 5k produits
scellés Pokémon avec ``idProduct`` + nom + catégorie + ``idExpansion``. Cardmarket
ne publie PAS les noms d'extension : on les déduit du **plus long préfixe commun**
des noms de produits d'une même extension (repli : nom le plus court sans le
suffixe de type).

Sortie : ``web/public/sealed-catalog/sealed-v1.json`` chargé côté client pour
l'écran « Ajouter un produit » (parcours extension + recherche), comme le
catalogue TCGdex des cartes.

Usage (depuis la racine du repo) : ``python api/scripts/build_sealed_catalog.py``
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
OUT_DIR = REPO_ROOT / "web" / "public" / "sealed-catalog"
SOURCE_URL = "https://downloads.s3.cardmarket.com/productCatalog/productList/products_nonsingles_6.json"
USER_AGENT = "cardmarket-api/0.1 (+https://goupixdex.dibodev.fr)"
CATALOG_VERSION = 1

#: idCategory Cardmarket vers type de produit normalisé (les Coins/1017 sont exclus).
CATEGORY_TO_TYPE: dict[int, str] = {
    52: "booster",
    53: "display",
    54: "theme_deck",
    1013: "trainer_kit",
    1014: "tin",
    1015: "box_set",
    1016: "etb",
    1064: "autre",
    1083: "blister",
    1654: "box_set",
}
EXCLUDED_CATEGORIES: frozenset[int] = frozenset({1017})  # Coins : pas des produits scellés.

#: Suffixes de type retirés d'un nom pour retrouver l'extension (repli), du plus long au plus court.
_TYPE_SUFFIXES: tuple[str, ...] = (
    "Elite Trainer Box",
    "Pokemon Center Elite Trainer Box",
    "Build & Battle Box",
    "Build & Battle Stadium",
    "Premium Collection",
    "Special Collection",
    "Collection Box",
    "Booster Display",
    "Booster Bundle",
    "Sleeved Booster",
    "Booster Box",
    "Booster Pack",
    "Booster",
    "Display",
    "Theme Deck",
    "Trainer Kit",
    "Gift Box",
    "Box Set",
    "Tin",
    "Blister",
    "Collection",
    "Bundle",
    "Box",
    "Pack",
    "Set",
)


def _load_products() -> list[dict]:
    """Télécharge et décode la liste non-singles (Cardmarket sert du cp1252 malgré le .json)."""
    response = httpx.get(SOURCE_URL, timeout=120.0, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    try:
        payload = json.loads(response.content)
    except UnicodeDecodeError:
        payload = json.loads(response.content.decode("cp1252"))
    products = payload.get("products")
    if not isinstance(products, list):
        raise SystemExit("products_nonsingles_6.json : clé 'products' absente ou invalide.")
    return products


def _longest_common_prefix(names: list[str]) -> str:
    """Plus long préfixe commun d'une liste de noms, coupé sur une frontière de mot."""
    if not names:
        return ""
    shortest, longest = min(names), max(names)
    length = 0
    while length < len(shortest) and shortest[length] == longest[length]:
        length += 1
    return shortest[:length].strip(" -–:")


def _strip_type_suffix(name: str) -> str:
    """Retire le suffixe de type connu d'un nom de produit (« Neo Genesis Booster » donne « Neo Genesis »)."""
    for suffix in _TYPE_SUFFIXES:
        if name.lower().endswith(suffix.lower()):
            return name[: -len(suffix)].strip(" -–:")
    return name


def _expansion_label(names: list[str]) -> str:
    """Nom d'extension : préfixe commun, sinon nom le plus court sans son suffixe de type."""
    prefix = _longest_common_prefix(names)
    if len(prefix) >= 3:
        return prefix
    stripped = [_strip_type_suffix(n) for n in names]
    stripped = [s for s in stripped if len(s) >= 3]
    if stripped:
        return min(stripped, key=len)
    return min(names, key=len)


def main() -> int:
    products = _load_products()
    by_expansion: dict[int, list[dict]] = defaultdict(list)
    for product in products:
        category = product.get("idCategory")
        if not isinstance(category, int) or category in EXCLUDED_CATEGORIES:
            continue
        id_product = product.get("idProduct")
        name = product.get("name")
        expansion = product.get("idExpansion")
        if not isinstance(id_product, int) or not isinstance(name, str) or not isinstance(expansion, int):
            continue
        by_expansion[expansion].append(
            {"p": id_product, "n": name.strip(), "c": CATEGORY_TO_TYPE.get(category, "autre")}
        )

    expansions: list[dict] = []
    for expansion_id, items in by_expansion.items():
        items.sort(key=lambda it: it["n"])
        label = _expansion_label([it["n"] for it in items])
        expansions.append({"id": expansion_id, "label": label, "count": len(items), "products": items})
    expansions.sort(key=lambda e: e["label"].lower())

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {"version": CATALOG_VERSION, "generated_at": generated_at, "expansions": expansions}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "sealed-v1.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    total = sum(e["count"] for e in expansions)
    size_kb = out_path.stat().st_size // 1024
    print(f"sealed-v1: {len(expansions)} extensions, {total} produits | {size_kb} KiB -> {out_path}")
    empty = [e for e in expansions if len(e["label"]) < 3]
    if empty:
        print(f"  ⚠ {len(empty)} extension(s) sans label lisible (ex. ids {[e['id'] for e in empty[:5]]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
