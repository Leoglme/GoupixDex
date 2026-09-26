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
import os
import re
import time
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
OUT_DIR = REPO_ROOT / "web" / "public" / "sealed-catalog"
#: Logos embarqués des groupes TCGplayer hors TCGdex (Delta Reign, Battle Academy…), nommés ``tp-<groupId>.webp``.
GROUP_LOGO_DIR = REPO_ROOT / "web" / "public" / "set-logos" / "fr"
HISTORY_DIR = OUT_DIR / "history"
HISTORY_VERSION = 1
HISTORY_SHARDS = 64  # doit rester égal à PRICE_HISTORY_SHARDS de web/app/composables/useSealedCatalog.ts
HISTORY_MAX_DAYS = 730
UA = {"User-Agent": "Mozilla/5.0 (compatible; GoupixDex/1.0; +https://goupixdex.dibodev.fr)"}
CATALOG_VERSION = 2
POKEMON_CATEGORY = 3  # TCGplayer / TCGCSV
USD_TO_EUR = 0.92  # repli approximatif quand le prix Cardmarket manque.

CARDMARKET_NONSINGLES = "https://downloads.s3.cardmarket.com/productCatalog/productList/products_nonsingles_6.json"

#: Préfixe de nom TCGplayer (« SV08: », « SM - »…) vers id de série TCGdex (repli quand l'extension n'est pas appariée).
SERIE_ID_BY_PREFIX: dict[str, str] = {
    "col": "col",
    "dp": "dp",
    "ex": "ex",
    "hgss": "hgss",
    "hs": "hgss",
    "me": "me",
    "mee": "me",
    "neo": "neo",
    "pl": "pl",
    "pop": "pop",
    "sm": "sm",
    "sv": "sv",
    "sve": "sv",
    "swsh": "swsh",
    "tk": "tk",
    "bw": "bw",
    "xy": "xy",
}
#: Début de nom TCGplayer (normalisé) vers id de série TCGdex, pour les groupes sans préfixe.
SERIE_ID_BY_PHRASE: tuple[tuple[str, str], ...] = (
    ("scarlet violet", "sv"),
    ("sword shield", "swsh"),
    ("sun moon", "sm"),
    ("black white", "bw"),
    ("black and white", "bw"),
    ("diamond pearl", "dp"),
    ("diamond and pearl", "dp"),
    ("platinum", "pl"),
    ("heartgold soulsilver", "hgss"),
    ("call of legends", "col"),
    ("mega evolution", "me"),
    ("pop series", "pop"),
    ("mcdonald", "mc"),
    ("expedition", "ecard"),
    ("aquapolis", "ecard"),
    ("skyridge", "ecard"),
    ("base set", "base"),
    ("jungle", "base"),
    ("fossil", "base"),
    ("team rocket", "base"),
    ("gym ", "base"),
    ("legendary collection", "base"),
    ("neo ", "neo"),
    ("southern islands", "neo"),
    ("ex ", "ex"),
)
#: Préfixe de série vers nom (normalisé) du premier set de la série, pour « SM Base Set », « XY Base Set »…
SERIE_BASE_SET_NAMES: dict[str, str] = {
    "black and white": "black white",
    "bw": "black white",
    "diamond and pearl": "diamond pearl",
    "dp": "diamond pearl",
    "scarlet violet": "scarlet violet",
    "sm": "sun moon",
    "sv": "scarlet violet",
    "sword shield": "sword shield",
    "swsh": "sword shield",
    "xy": "xy",
}
#: Noms de série qui précèdent le nom d'extension chez TCGplayer (« Scarlet & Violet 151 »).
SERIE_NAME_PHRASES: tuple[str, ...] = (
    "scarlet violet",
    "sword shield",
    "sun moon",
    "black white",
    "diamond pearl",
    "heartgold soulsilver",
    "mega evolution",
)
#: Groupes TCGplayer dont le nom ne ressemble pas à celui de l'extension TCGdex (kits dresseur, promos McDonald's).
TCGDEX_ID_BY_GROUP_NAME: dict[str, str] = {
    "bw trainer kit excadrill zoroark": "tk-bw-e",
    "dp trainer kit manaphy lucario": "tk-dp-m",
    "ex trainer kit 1 latias latios": "tk-ex-latia",
    "ex trainer kit 2 plusle minun": "tk-ex-p",
    "hgss trainer kit gyarados raichu": "tk-hs-g",
    "mcdonald s 25th anniversary promos": "2021swsh",
    "sm trainer kit lycanroc alolan raichu": "tk-sm-r",
    "xy trainer kit bisharp wigglytuff": "tk-xy-b",
    "xy trainer kit latias latios": "tk-xy-latia",
    "xy trainer kit pikachu libre suicune": "tk-xy-p",
    "xy trainer kit sylveon noivern": "tk-xy-sy",
}
#: Groupes TCGplayer hors TCGdex dont le logo existe sous un autre nom chez pokemontcg.io.
POKEMONTCG_NAME_BY_GROUP_NAME: dict[str, str] = {"wotc promo": "wizards black star promos"}
#: Tirages d'une même extension vendus en groupes TCGplayer distincts (« Base Set (Shadowless) »).
PRINT_RUN_RE = re.compile(r"\s+(shadowless|1st edition|unlimited)$")
PRINT_RUN_LABELS: dict[str, str] = {"shadowless": "Shadowless", "1st edition": "Édition 1", "unlimited": "Unlimited"}
POKEMONTCG_SETS = "https://raw.githubusercontent.com/PokemonTCG/pokemon-tcg-data/master/sets/en.json"
POKECARDEX_LOGOS = "https://pokecardex.b-cdn.net/assets/images/logos/{code}.png"
SERIE_OTHER = "Autres"


def norm(value: str) -> str:
    """Normalise un nom pour le matching (minuscules, sans accents, sans préfixe de set/ponctuation)."""
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    text = re.sub(r"^[a-z]{1,5}\d*(?:\.\d+)?[a-z]?:\s*", "", text)  # « sv08: », « me: » …
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def name_prefix(name: str) -> str:
    """Préfixe de série d'un nom TCGplayer (« SV08: Surging Sparks » ou « SM - Team Up » donnent « sv » / « sm »)."""
    match = re.match(r"^([A-Za-z]+)\d", name) or re.match(r"^([A-Za-z]+)\s*[:—-]", name)
    return match.group(1).lower() if match else ""


def set_keys(group_name: str) -> list[str]:
    """Clés candidates d'une extension TCGdex pour un groupe TCGplayer, de la plus précise à la plus large."""
    name = norm(group_name)
    without_print_run = PRINT_RUN_RE.sub("", name)
    keys: list[str] = [name, without_print_run, name.replace(" and ", " ")]
    base_match = re.match(r"^(.*?)\s+base set$", name)
    if base_match:
        base = base_match.group(1)
        keys.extend([SERIE_BASE_SET_NAMES.get(base, base), base])
    without_prefix = re.sub(r"^(sm|swsh|sv|bw|dp|hgss|xy|me|ex)\s+", "", name)
    for phrase in SERIE_NAME_PHRASES:
        for source in (name, without_prefix):
            if source.startswith(f"{phrase} ") and source[len(phrase) + 1 :] != "base set":
                keys.append(source[len(phrase) + 1 :])
    # Jamais réduit à « base set » : ce serait le Set de Base de 1999.
    if without_prefix != name and without_prefix != "base set":
        keys.append(without_prefix)
    variants = [variant for key in keys for variant in (key, key.replace(" and ", " "), key.replace(" promos ", " collection "))]
    return list(dict.fromkeys(key for key in variants if key))


def fallback_serie_name(group_name: str, serie_names: dict[str, str]) -> str:
    """Série FR d'un groupe TCGplayer sans extension TCGdex : par préfixe, puis par début de nom, sinon « Autres »."""
    serie_id = SERIE_ID_BY_PREFIX.get(name_prefix(group_name))
    if serie_id is None:
        name = norm(group_name)
        serie_id = next(
            (target for phrase, target in SERIE_ID_BY_PHRASE if name == phrase.strip() or name.startswith(phrase)),
            None,
        )
    return serie_names.get(serie_id, SERIE_OTHER) if serie_id else SERIE_OTHER


def _url_exists(url: str) -> bool:
    """Vrai quand l'URL répond 200 (requête HEAD)."""
    try:
        return httpx.head(url, headers=UA, timeout=20.0, follow_redirects=True).status_code == 200
    except httpx.HTTPError:
        return False


def load_pokemontcg_logos() -> dict[str, str]:
    """Logos des sets pokemontcg.io indexés par nom normalisé (repli pour les groupes absents de TCGdex)."""
    logos: dict[str, str] = {}
    for pokemontcg_set in _fetch_json(POKEMONTCG_SETS, cache=True):
        images = pokemontcg_set.get("images")
        if isinstance(images, dict) and images.get("logo"):
            logos.setdefault(norm(pokemontcg_set.get("name", "")), images["logo"])
    return logos


def embedded_group_logo(group: dict) -> str | None:
    """Logo embarqué dans le site pour ce groupe TCGplayer, prioritaire : les sources externes n'en ont pas."""
    path = GROUP_LOGO_DIR / f"tp-{group['group_id']}.webp"
    return f"/set-logos/fr/{path.name}" if path.exists() else None


def unmatched_group_logo(group: dict, pokemontcg_logos: dict[str, str]) -> str | None:
    """Logo d'un groupe TCGplayer sans extension TCGdex : set pokemontcg.io du même nom (ou de son alias), sinon logo Pokécardex de son code."""
    alias = POKEMONTCG_NAME_BY_GROUP_NAME.get(norm(group["name"]))
    for key in ([alias] if alias else []) + set_keys(group["name"]):
        if key in pokemontcg_logos:
            return pokemontcg_logos[key]
    code = (group.get("abbr") or "").strip()
    if len(code) >= 3 and re.fullmatch(r"[A-Za-z0-9]+", code):
        url = POKECARDEX_LOGOS.format(code=code.upper())
        if _url_exists(url):
            return url
    return None


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


def _is_wholesale(name: str) -> bool:
    """Vrai pour un lot grossiste (« … Case » = carton de N boîtes), inutile à un collectionneur."""
    return re.search(r"\bcase\b", name.lower()) is not None


def _is_card(product: dict) -> bool:
    """Vrai pour une carte (a une « Rarity » en extendedData) — les scellés ont une « UPC », pas de Rarity."""
    return any(e.get("name") == "Rarity" for e in (product.get("extendedData") or []))


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
    """Index TCGdex ``norm(nom)`` vers infos extension (FR + logo + série), sets connus seulement en anglais compris."""
    fr_series = _fetch_json("https://api.tcgdex.net/v2/fr/series", cache=True)
    en_series = _fetch_json("https://api.tcgdex.net/v2/en/series", cache=True)
    en_sets = {s["id"]: s.get("name", "") for s in _fetch_json("https://api.tcgdex.net/v2/en/sets", cache=True)}
    index: dict[str, dict] = {}
    series_meta: list[dict] = []
    for serie in fr_series:
        detail = _fetch_json(f"https://api.tcgdex.net/v2/fr/series/{serie['id']}", cache=True)
        series_meta.append({"id": serie["id"], "name": serie.get("name", ""), "logo": serie.get("logo")})
        for st in detail.get("sets", []):
            # Certaines sorties récentes (30e Anniversaire) n'ont pas d'asset logo FR mais un EN :
            # on construit une base EN de repli, GoupixDexCatalogSetLogo teste l'extension et retombe sur l'icône.
            logo = st.get("logo") or f"https://assets.tcgdex.net/en/{serie['id']}/{st['id']}/logo"
            info = {
                "set_id": st["id"],
                "fr_name": st.get("name", ""),
                "logo": logo,
                "serie_id": serie["id"],
                "serie_name": serie.get("name", ""),
            }
            for key in {norm(en_sets.get(st["id"], "")), norm(st.get("name", ""))}:
                if key:
                    index.setdefault(key, info)
    fr_serie_names = {meta["id"]: meta["name"] for meta in series_meta}
    for serie in en_series:
        if serie["id"] == "tcgp":
            continue
        detail = _fetch_json(f"https://api.tcgdex.net/v2/en/series/{serie['id']}", cache=True)
        if serie["id"] not in fr_serie_names:
            series_meta.append(
                {"id": serie["id"], "name": serie.get("name", ""), "logo": serie.get("logo"), "english_only": True}
            )
        for st in detail.get("sets", []):
            key = norm(st.get("name", ""))
            if key and key not in index:
                index[key] = {
                    "set_id": st["id"],
                    "fr_name": st.get("name", ""),
                    "logo": st.get("logo") or f"https://assets.tcgdex.net/en/{serie['id']}/{st['id']}/logo",
                    "serie_id": serie["id"],
                    "serie_name": fr_serie_names.get(serie["id"]) or serie.get("name", ""),
                }
    return index, series_meta


#: Passes sur les groupes TCGCSV en échec : la CI se fait limiter par rafales et perdait jusqu'à 20 extensions par nuit.
TCGCSV_GROUP_PASSES = 3
TCGCSV_RETRY_PAUSE_SEC = 120.0


def load_tcgcsv_group(group: dict) -> dict | None:
    """Produits scellés (nom + image) et prix marché USD d'un groupe TCGplayer, ``None`` s'il n'a aucun scellé."""
    gid = group["groupId"]
    products = _fetch_json(f"https://tcgcsv.com/tcgplayer/{POKEMON_CATEGORY}/{gid}/products", cache=True)["results"]
    prices = _fetch_json(f"https://tcgcsv.com/tcgplayer/{POKEMON_CATEGORY}/{gid}/prices", cache=True)["results"]
    sealed = [
        p
        for p in products
        if not _is_card(p) and not _is_non_physical(p.get("name", "")) and not _is_wholesale(p.get("name", ""))
    ]
    if not sealed:
        return None
    return {
        "group_id": gid,
        "name": group["name"],
        "abbr": group.get("abbreviation") or "",
        "published_on": group.get("publishedOn") or "",
        "products": sealed,
        "price_by_id": {p["productId"]: p.get("marketPrice") for p in prices if p.get("marketPrice")},
    }


def load_tcgcsv_groups() -> tuple[list[dict], list[dict]]:
    """Groupes TCGplayer (extensions) avec leurs scellés, et les groupes que TCGCSV a refusés à chaque passe."""
    pending = _fetch_json("https://tcgcsv.com/tcgplayer/3/groups", cache=True)["results"]
    out: list[dict] = []
    for attempt in range(TCGCSV_GROUP_PASSES):
        failed: list[dict] = []
        for group in pending:
            try:
                loaded = load_tcgcsv_group(group)
            except (httpx.HTTPError, SystemExit):
                failed.append(group)
                continue
            if loaded:
                out.append(loaded)
            time.sleep(0.25)
        pending = failed
        if not pending:
            break
        if attempt < TCGCSV_GROUP_PASSES - 1:
            print(f"TCGCSV : {len(pending)} groupe(s) en échec, nouvelle passe dans {TCGCSV_RETRY_PAUSE_SEC:.0f} s", flush=True)
            time.sleep(TCGCSV_RETRY_PAUSE_SEC)
    if pending:
        print("TCGCSV : groupes abandonnés : " + ", ".join(group["name"] for group in pending), flush=True)
    return out, pending


def previous_expansions_by_group(path: Path) -> dict[int, tuple[str, dict]]:
    """Extensions du dernier catalogue publié (série et contenu) par groupe TCGplayer."""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        expansion["group_id"]: (serie["name"], expansion)
        for serie in payload.get("series", [])
        for expansion in serie.get("expansions", [])
        if isinstance(expansion.get("group_id"), int)
    }


def build() -> dict[str, Any]:
    """Assemble le catalogue série vers extension vers produits."""
    global_cm, exp_cm = load_cardmarket()
    tcgdex, series_meta = load_tcgdex_sets()
    tcgdex_by_id = {info["set_id"]: info for info in tcgdex.values()}
    pokemontcg_logos = load_pokemontcg_logos()
    groups, abandoned_groups = load_tcgcsv_groups()
    previous_expansions = previous_expansions_by_group(OUT_DIR / "sealed-v2.json")

    serie_logo = {s["name"]: s["logo"] for s in series_meta}
    serie_names = {s["id"]: s["name"] for s in series_meta}
    series: dict[str, dict] = {}

    stat_img = stat_total = stat_cm_price = stat_matched = stat_logo = 0
    for group in groups:
        set_norm = norm(group["name"])
        set_clean = re.sub(r"^[A-Za-z]+\d*(?:\.\d+)?[a-z]?:\s*", "", group["name"]).strip()
        cm_bucket = exp_cm.get(set_norm)
        td = tcgdex_by_id.get(TCGDEX_ID_BY_GROUP_NAME.get(set_norm, "")) or next(
            (tcgdex[key] for key in set_keys(group["name"]) if key in tcgdex), None
        )
        if td:
            stat_matched += 1
            print_run = PRINT_RUN_RE.search(set_norm)
            # Sans le tirage, deux groupes (Set de Base / Shadowless) auraient le même nom, donc le même lien.
            exp_name = f"{td['fr_name']} ({PRINT_RUN_LABELS[print_run.group(1)]})" if print_run else td["fr_name"]
            exp_logo = embedded_group_logo(group) or td["logo"]
            serie_name = td["serie_name"]
        else:
            exp_name = re.sub(r"^(SM|SWSH|SV|BW|DP|HGSS|XY|ME|EX)\s+-\s+", "", set_clean, flags=re.IGNORECASE)
            exp_name = exp_name.strip() or group["name"]
            exp_logo = embedded_group_logo(group) or unmatched_group_logo(group, pokemontcg_logos)
            serie_name = fallback_serie_name(group["name"], serie_names)
            serie_logo.setdefault(serie_name, None)
        if exp_logo:
            stat_logo += 1

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
                "group_id": group["group_id"],
                "tcgdex_id": td["set_id"] if td else None,
                "name": exp_name,
                "logo": exp_logo,
                "published_on": group["published_on"],
                "count": len(products),
                "products": products,
            }
        )

    # Un groupe refusé par TCGCSV à chaque passe garde son extension de la veille plutôt que de disparaître.
    for group in abandoned_groups:
        kept = previous_expansions.get(group["groupId"])
        if kept is None:
            continue
        serie_name, expansion = kept
        bucket = series.setdefault(
            serie_name,
            {"name": serie_name, "logo": serie_logo.get(serie_name), "expansions": []},
        )
        bucket["expansions"].append(expansion)
        print(f"TCGCSV : « {group['name']} » repris du catalogue précédent", flush=True)

    # Extensions récentes en premier dans chaque série ; séries dans l'ordre chronologique
    # inverse de TCGdex (série la plus récente d'abord), inconnues puis « Autres » en dernier.
    for serie in series.values():
        serie["expansions"].sort(key=lambda e: e["published_on"], reverse=True)
    serie_pos = {s["name"]: i for i, s in enumerate(series_meta) if not s.get("english_only")}
    last = len(series_meta)

    def _serie_rank(serie: dict[str, Any]) -> int:
        name = serie["name"]
        if name == SERIE_OTHER:
            return last + 1
        return last - serie_pos[name] if name in serie_pos else last

    ordered = sorted(series.values(), key=_serie_rank)

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    print(
        f"produits {stat_total} | images {stat_img} ({100 * stat_img // max(stat_total, 1)}%) "
        f"| idProduct Cardmarket {stat_cm_price} ({100 * stat_cm_price // max(stat_total, 1)}%) "
        f"| extensions TCGdex {stat_matched}/{len(groups)} | logos {stat_logo}/{len(groups)} "
        f"| séries {len(ordered)}"
    )
    return {"version": CATALOG_VERSION, "generated_at": generated_at, "series": ordered}


TCGPLAYER_HISTORY_URL = "https://infinite-api.tcgplayer.com/price/history/{tp}/detailed?range={range}"
#: Plages TCGplayer relevées pour amorcer un produit : « month » = 30 points quotidiens, « quarter » = 30 points tous les 3 jours.
TCGPLAYER_HISTORY_RANGES = ("month", "quarter")
#: Produits sans historique amorcés par nuit (le reste attend la nuit suivante) ; surchargeable via HISTORY_BOOTSTRAP_LIMIT.
HISTORY_BOOTSTRAP_PER_RUN = int(os.environ.get("HISTORY_BOOTSTRAP_LIMIT") or 300)
#: Pause entre deux lectures TCGplayer : au-delà d'environ deux requêtes par seconde, l'anti-bot répond 403.
TCGPLAYER_HISTORY_PAUSE_SEC = 0.6


def history_shard(tp: int) -> int:
    """Index du fichier ``history/{n}.json`` qui porte un idProduct TCGplayer."""
    return int(tp) % HISTORY_SHARDS


class TcgplayerBlockedError(RuntimeError):
    """TCGplayer refuse nos requêtes (403 anti-bot) : inutile d'insister pendant cette exécution."""


def fetch_tcgplayer_price_history(client: httpx.Client, tp: int, range_name: str) -> list[list[Any]] | None:
    """Points ``[date, prix €]`` (croissants) de l'historique public TCGplayer d'un produit ; ``[]`` sans données, ``None`` si la lecture a échoué."""
    url = TCGPLAYER_HISTORY_URL.format(tp=int(tp), range=range_name)
    for attempt in range(3):
        try:
            resp = client.get(url, headers={**UA, "Accept": "application/json"}, timeout=30.0)
        except httpx.HTTPError:
            time.sleep(1.5 * (attempt + 1))
            continue
        if resp.status_code == 404:
            return []
        if resp.status_code == 403:
            raise TcgplayerBlockedError(f"TCGplayer a répondu 403 pour {url}")
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(5.0 * (attempt + 1))
            continue
        if resp.status_code != 200:
            return None
        try:
            payload = resp.json()
        except ValueError:
            return None
        variants = [v for v in (payload.get("result") or []) if isinstance(v, dict)]
        if not variants:
            return []
        variant = next((v for v in variants if v.get("variant") == "Normal"), None) or max(
            variants, key=lambda v: len(v.get("buckets") or [])
        )
        points: list[list[Any]] = []
        for bucket in variant.get("buckets") or []:
            day = str(bucket.get("bucketStartDate") or "")[:10]
            try:
                usd = float(bucket.get("marketPrice") or 0)
            except (TypeError, ValueError):
                continue
            if len(day) == 10 and usd > 0:
                points.append([day, round(usd * USD_TO_EUR, 2)])
        points.sort(key=lambda point: point[0])
        return points
    return None


def merge_history_points(series: list[list[Any]], points: list[list[Any]]) -> list[list[Any]]:
    """Complète une série ``[date, prix]`` avec les points dont la date manque (les relevés existants gagnent), triée et plafonnée."""
    known = {point[0] for point in series if isinstance(point, list) and len(point) == 2}
    merged = [point for point in series if isinstance(point, list) and len(point) == 2]
    merged.extend(point for point in points if point[0] not in known)
    merged.sort(key=lambda point: str(point[0]))
    return merged[-HISTORY_MAX_DAYS:]


def bootstrap_missing_price_history(payload: dict[str, Any], history_dir: Path = HISTORY_DIR, limit: int = HISTORY_BOOTSTRAP_PER_RUN) -> int:
    """Amorce depuis TCGplayer l'historique des produits qui ont moins de deux points (au plus ``limit`` produits) ; renvoie le nombre amorcés."""
    products = [
        product
        for serie in payload["series"]
        for expansion in serie["expansions"]
        for product in expansion["products"]
        if product.get("price") is not None
    ]
    shards: dict[int, dict[str, Any]] = {}
    for product in products:
        shard = history_shard(product["tp"])
        if shard not in shards:
            path = history_dir / f"{shard}.json"
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
    pending = [p for p in products if len(shards[history_shard(p["tp"])]["products"].get(str(p["tp"])) or []) < 2]
    bootstrapped = 0
    touched: set[int] = set()
    with httpx.Client() as client:
        for product in pending[:limit]:
            points: list[list[Any]] = []
            try:
                for range_name in TCGPLAYER_HISTORY_RANGES:
                    fetched = fetch_tcgplayer_price_history(client, product["tp"], range_name)
                    points = merge_history_points(points, fetched or [])
                    time.sleep(TCGPLAYER_HISTORY_PAUSE_SEC)
            except TcgplayerBlockedError as exc:
                print(f"historique prix: arrêt de l'amorçage ({exc})", flush=True)
                break
            if not points:
                continue
            shard = history_shard(product["tp"])
            key = str(product["tp"])
            shards[shard]["products"][key] = merge_history_points(shards[shard]["products"].get(key) or [], points)
            touched.add(shard)
            bootstrapped += 1
    history_dir.mkdir(parents=True, exist_ok=True)
    for shard in sorted(touched):
        (history_dir / f"{shard}.json").write_text(
            json.dumps(shards[shard], ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
    return bootstrapped


def append_history_point(series: list[list[Any]], day: str, price_eur: float) -> list[list[Any]]:
    """Ajoute (ou remplace) le point d'une journée dans une série ``[date, prix]`` triée, plafonnée à ``HISTORY_MAX_DAYS`` points."""
    kept = [point for point in series if isinstance(point, list) and len(point) == 2 and point[0] != day]
    kept.append([day, round(float(price_eur), 2)])
    kept.sort(key=lambda point: str(point[0]))
    return kept[-HISTORY_MAX_DAYS:]


def update_price_history(payload: dict[str, Any], day: str, history_dir: Path = HISTORY_DIR) -> int:
    """Relève le prix du jour de chaque produit du catalogue dans ``history/{n}.json`` ; renvoie le nombre de produits relevés."""
    by_shard: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for serie in payload["series"]:
        for expansion in serie["expansions"]:
            for product in expansion["products"]:
                if product.get("price") is not None:
                    by_shard[history_shard(product["tp"])].append((product["tp"], product["price"]))
    history_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for shard, products in sorted(by_shard.items()):
        path = history_dir / f"{shard}.json"
        data: dict[str, Any] = {"v": HISTORY_VERSION, "products": {}}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                loaded = None
            if isinstance(loaded, dict) and isinstance(loaded.get("products"), dict):
                data = {"v": HISTORY_VERSION, "products": loaded["products"]}
        for tp, price in products:
            data["products"][str(tp)] = append_history_point(data["products"].get(str(tp)) or [], day, price)
            written += 1
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return written


def main() -> int:
    payload = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "sealed-v2.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    total = sum(e["count"] for s in payload["series"] for e in s["expansions"])
    exps = sum(len(s["expansions"]) for s in payload["series"])
    size_kb = out_path.stat().st_size // 1024
    print(f"sealed-v2: {exps} extensions, {total} produits | {size_kb} KiB -> {out_path}")
    day = datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
    recorded = update_price_history(payload, day)
    print(f"historique prix: {recorded} produits relevés pour {day} -> {HISTORY_DIR}")
    bootstrapped = bootstrap_missing_price_history(payload)
    print(f"historique prix: {bootstrapped} produit(s) amorcé(s) depuis TCGplayer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
