# -*- coding: utf-8 -*-
"""
Construit le catalogue statique des produits scellés (parcours par série vers extension).

Fusionne trois sources publiques :
- **TCGplayer via TCGCSV** (base) : produits scellés + **vraies images** (renders officiels).
- **TCGdex** : nom FR + logo + série de l'extension (comme le catalogue des cartes).
- **Cardmarket** : prix de référence en € (via l'``idProduct``) — repli prix TCGplayer sinon.

Sortie : ``web/public/sealed-catalog/sealed-v2.json`` chargé côté client pour l'écran
« Ajouter un produit », régénéré chaque nuit par la CI ``catalog-index.yml``.

Usage (depuis la racine du repo) : ``python api/scripts/build_sealed_catalog.py``
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
OUT_DIR = REPO_ROOT / "web" / "public" / "sealed-catalog"
UA = {"User-Agent": "Mozilla/5.0 (compatible; GoupixDex/1.0; +https://goupixdex.dibodev.fr)"}
CATALOG_VERSION = 2
POKEMON_CATEGORY = 3  # TCGplayer / TCGCSV
USD_TO_EUR = 0.92  # repli approximatif quand le prix Cardmarket manque.

CARDMARKET_NONSINGLES = "https://downloads.s3.cardmarket.com/productCatalog/productList/products_nonsingles_6.json"

#: Préfixe de nom TCGplayer vers série FR (repli quand TCGdex ne matche pas l'extension).
SERIE_BY_PREFIX: dict[str, str] = {
    "SV": "Écarlate et Violet",
    "SVE": "Écarlate et Violet",
    "ME": "Méga-Évolution",
    "MEE": "Méga-Évolution",
    "SWSH": "Épée et Bouclier",
    "SM": "Soleil et Lune",
    "XY": "XY",
    "BW": "Noir & Blanc",
    "HGSS": "HeartGold SoulSilver",
    "DP": "Diamant & Perle",
}
SERIE_OTHER = "Autres"


def norm(value: str) -> str:
    """Normalise un nom pour le matching (minuscules, sans accents, sans préfixe de set/ponctuation)."""
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    text = re.sub(r"^[a-z]{1,5}\d*(?:\.\d+)?[a-z]?:\s*", "", text)  # « sv08: », « me: » …
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def name_prefix(name: str) -> str:
    """Préfixe de série d'un nom TCGplayer (« SV08: Surging Sparks » vers « SV »)."""
    match = re.match(r"^([A-Za-z]+)\d", name) or re.match(r"^([A-Za-z]+):", name)
    return match.group(1).upper() if match else ""


_TYPE_RULES: tuple[tuple[str, str], ...] = (
    ("elite trainer box", "etb"),
    ("etb", "etb"),
    ("build & battle", "box_set"),
    ("build battle", "box_set"),
    ("booster box", "display"),
    ("booster display", "display"),
    ("sleeved booster case", "display"),
    ("booster case", "display"),
    ("display", "display"),
    ("booster bundle", "display"),
    ("premium collection", "box_set"),
    ("ultra-premium", "box_set"),
    ("ultra premium", "box_set"),
    ("special collection", "box_set"),
    ("collection", "box_set"),
    ("gift box", "box_set"),
    ("box set", "box_set"),
    ("tin", "tin"),
    ("blister", "blister"),
    ("checklane", "blister"),
    ("theme deck", "theme_deck"),
    ("deck", "theme_deck"),
    ("trainer kit", "trainer_kit"),
    ("booster pack", "booster"),
    ("booster", "booster"),
    ("bundle", "box_set"),
    ("box", "box_set"),
)


def product_type(name: str) -> str:
    """Type normalisé déduit du nom du produit (ETB, display, tin…)."""
    low = name.lower()
    for needle, kind in _TYPE_RULES:
        if needle in low:
            return kind
    return "autre"


#: Motifs de produits **non physiques** (codes en ligne) à exclure du catalogue scellé.
_NON_PHYSICAL = ("code card", "online code", "ptcgo", "tcg live", "[code]", "(code)")


def _is_non_physical(name: str) -> bool:
    """Vrai pour un code en ligne (carte code booster, etc.), pas un produit scellé physique."""
    low = name.lower()
    return any(token in low for token in _NON_PHYSICAL)


_CACHE_DIR = SCRIPT_DIR.parent / "var" / "tcgcsv_cache"
_CACHE_TTL_SEC = 18 * 3600.0


def _fetch_json(url: str, *, timeout: float = 60.0, cache: bool = False) -> Any:
    """
    GET JSON avec cache disque optionnel (dev) et backoff sur blocage transitoire.

    Le cache évite de re-marteler TCGCSV entre deux exécutions locales ; la CI
    (IP neuve, une passe par nuit) tourne sans cache.
    """
    cache_path: Path | None = None
    if cache:
        import hashlib

        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = _CACHE_DIR / f"{hashlib.sha1(url.encode()).hexdigest()}.json"
        if cache_path.exists() and (time.time() - cache_path.stat().st_mtime) < _CACHE_TTL_SEC:
            return json.loads(cache_path.read_text(encoding="utf-8"))

    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = httpx.get(url, headers=UA, timeout=timeout, follow_redirects=True)
            if response.status_code in (401, 403, 429, 500, 502, 503):
                raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)
            response.raise_for_status()
            data = response.json()
            if cache_path is not None:
                cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except httpx.HTTPError as exc:
            last_error = exc
            time.sleep(2**attempt)
    raise SystemExit(f"Échec de récupération après retries : {url} ({last_error})")


def _lcp(names: list[str]) -> str:
    """Plus long préfixe commun (frontière de mot) — sert de nom d'extension Cardmarket."""
    if not names:
        return ""
    a, b = min(names), max(names)
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[:i].strip(" -:")


def _remainder(name_norm: str, set_norm: str) -> str:
    """Reste d'un nom une fois le nom d'extension retiré (« … elite trainer box »)."""
    if set_norm and name_norm.startswith(set_norm):
        return name_norm[len(set_norm):].strip()
    return name_norm


def load_cardmarket() -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """
    Deux index Cardmarket ``nom vers idProduct`` (fichier public, sans guide de prix) :

    - ``global_index`` : ``norm(nom)`` vers idProduct — correspondance exacte de nom.
    - ``exp_index`` : ``norm(extension)`` vers { reste vers idProduct } — correspondance par
      type au sein d'une extension (rattrape les libellés de set qui divergent).

    Le prix € des produits appariés est ensuite calculé côté serveur (guide Cardmarket
    du VPS) à l'ajout et chaque nuit ; ce build reste autonome (httpx seul) pour la CI.
    """
    raw = httpx.get(CARDMARKET_NONSINGLES, headers=UA, timeout=120.0)
    try:
        payload = json.loads(raw.content)
    except UnicodeDecodeError:
        payload = json.loads(raw.content.decode("cp1252"))

    by_expansion: dict[int, list[dict]] = defaultdict(list)
    for product in payload.get("products", []):
        if isinstance(product.get("idProduct"), int) and isinstance(product.get("name"), str):
            if isinstance(product.get("idExpansion"), int):
                by_expansion[product["idExpansion"]].append(product)

    global_index: dict[str, int] = {}
    exp_index: dict[str, dict[str, int]] = {}
    for products in by_expansion.values():
        label_norm = norm(_lcp([p["name"] for p in products]) or products[0]["name"])
        bucket = exp_index.setdefault(label_norm, {}) if label_norm else None
        for product in products:
            id_product = product["idProduct"]
            name_norm = norm(product["name"])
            global_index.setdefault(name_norm, id_product)
            if bucket is not None:
                bucket.setdefault(_remainder(name_norm, label_norm), id_product)
    return global_index, exp_index


def load_tcgdex_sets() -> tuple[dict[str, dict], list[dict]]:
    """Index TCGdex ``norm(nom)`` vers infos extension (FR + logo + série), et la liste des séries."""
    fr_series = _fetch_json("https://api.tcgdex.net/v2/fr/series", cache=True)
    en_sets = {s["id"]: s.get("name", "") for s in _fetch_json("https://api.tcgdex.net/v2/en/sets", cache=True)}
    index: dict[str, dict] = {}
    series_meta: list[dict] = []
    for serie in fr_series:
        detail = _fetch_json(f"https://api.tcgdex.net/v2/fr/series/{serie['id']}", cache=True)
        series_meta.append({"id": serie["id"], "name": serie.get("name", ""), "logo": serie.get("logo")})
        for st in detail.get("sets", []):
            info = {
                "set_id": st["id"],
                "fr_name": st.get("name", ""),
                "logo": st.get("logo"),
                "serie_id": serie["id"],
                "serie_name": serie.get("name", ""),
            }
            for key in {norm(en_sets.get(st["id"], "")), norm(st.get("name", ""))}:
                if key:
                    index.setdefault(key, info)
    return index, series_meta


def load_tcgcsv_groups() -> list[dict]:
    """Groupes TCGplayer (extensions) + leurs produits scellés (nom + image) + prix marché USD."""
    groups = _fetch_json("https://tcgcsv.com/tcgplayer/3/groups", cache=True)["results"]
    out: list[dict] = []
    for group in groups:
        gid = group["groupId"]
        try:
            products = _fetch_json(f"https://tcgcsv.com/tcgplayer/{POKEMON_CATEGORY}/{gid}/products", cache=True)["results"]
            prices = _fetch_json(f"https://tcgcsv.com/tcgplayer/{POKEMON_CATEGORY}/{gid}/prices", cache=True)["results"]
        except (httpx.HTTPError, SystemExit):
            continue
        price_by_id = {p["productId"]: p.get("marketPrice") for p in prices if p.get("marketPrice")}
        sealed = [
            p
            for p in products
            if not any(e.get("name") == "Number" for e in (p.get("extendedData") or []))
            and not _is_non_physical(p.get("name", ""))
        ]
        if not sealed:
            continue
        out.append(
            {
                "name": group["name"],
                "abbr": group.get("abbreviation") or "",
                "published_on": group.get("publishedOn") or "",
                "products": sealed,
                "price_by_id": price_by_id,
            }
        )
        time.sleep(0.25)
    return out


def build() -> dict[str, Any]:
    """Assemble le catalogue série vers extension vers produits."""
    global_cm, exp_cm = load_cardmarket()
    tcgdex, series_meta = load_tcgdex_sets()
    groups = load_tcgcsv_groups()

    serie_order = {s["name"]: i for i, s in enumerate(series_meta)}
    serie_logo = {s["name"]: s["logo"] for s in series_meta}
    series: dict[str, dict] = {}

    stat_img = stat_total = stat_cm_price = 0
    for group in groups:
        set_norm = norm(group["name"])
        set_clean = re.sub(r"^[A-Za-z]+\d*(?:\.\d+)?[a-z]?:\s*", "", group["name"]).strip()
        cm_bucket = exp_cm.get(set_norm)
        td = tcgdex.get(set_norm)
        if td:
            exp_name = td["fr_name"]
            exp_logo = td["logo"]
            serie_name = td["serie_name"]
        else:
            exp_name = re.sub(r"^[A-Za-z]+\d*(?:\.\d+)?:\s*", "", group["name"]).strip() or group["name"]
            exp_logo = None
            serie_name = SERIE_BY_PREFIX.get(name_prefix(group["name"]), SERIE_OTHER)
            serie_logo.setdefault(serie_name, None)

        products: list[dict] = []
        for tp in group["products"]:
            stat_total += 1
            name = tp["name"]
            key = norm(name)
            id_product = global_cm.get(key)
            if id_product is None and cm_bucket is not None:
                id_product = cm_bucket.get(_remainder(key, set_norm))
            if id_product is not None:
                stat_cm_price += 1
            usd = group["price_by_id"].get(tp["productId"])
            price = round(float(usd) * USD_TO_EUR, 2) if usd else None
            image = tp.get("imageUrl")
            if image:
                stat_img += 1
                image = image.replace("_200w.jpg", "_400w.jpg")
            short = name
            if set_clean and short.lower().startswith(set_clean.lower()):
                short = short[len(set_clean):].strip(" -:()") or name
            products.append(
                {
                    "tp": tp["productId"],
                    "p": id_product,
                    "n": short,
                    "full": name,
                    "c": product_type(name),
                    "img": image,
                    "price": price,
                }
            )
        products.sort(key=lambda x: x["n"])

        bucket = series.setdefault(
            serie_name,
            {"name": serie_name, "logo": serie_logo.get(serie_name), "expansions": []},
        )
        bucket["expansions"].append(
            {
                "id": group["abbr"] or set_norm,
                "name": exp_name,
                "logo": exp_logo,
                "published_on": group["published_on"],
                "count": len(products),
                "products": products,
            }
        )

    ordered = sorted(
        series.values(),
        key=lambda s: (serie_order.get(s["name"], 999 if s["name"] != SERIE_OTHER else 1000), s["name"]),
    )
    for serie in ordered:
        serie["expansions"].sort(key=lambda e: e["published_on"], reverse=True)

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    print(
        f"produits {stat_total} | images {stat_img} ({100 * stat_img // max(stat_total, 1)}%) "
        f"| idProduct Cardmarket {stat_cm_price} ({100 * stat_cm_price // max(stat_total, 1)}%) "
        f"| séries {len(ordered)}"
    )
    return {"version": CATALOG_VERSION, "generated_at": generated_at, "series": ordered}


def main() -> int:
    payload = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "sealed-v2.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    total = sum(e["count"] for s in payload["series"] for e in s["expansions"])
    exps = sum(len(s["expansions"]) for s in payload["series"])
    size_kb = out_path.stat().st_size // 1024
    print(f"sealed-v2: {exps} extensions, {total} produits | {size_kb} KiB -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
