"""
Aggregate scraped sold-listings into a "top sold cards" ranking.

Strategy: build a coarse fingerprint per listing title (set/card-number when
parseable, otherwise the first few significant tokens), keep the grade
(PSA / BGS / CGC) on a separate axis so a graded card never collapses with
its raw counterpart, then group + count + price stats.

The fingerprint is intentionally lossy: « Pikachu VMAX 044/185 Vivid Voltage »
and « Pikachu VMAX Vivid Voltage 44/185 PSA10 » will land in the same group
when ungraded — the second goes to a separate ``PSA 10`` bucket.
"""

from __future__ import annotations

import re
import unicodedata
from statistics import median
from typing import Any, Literal


Category = Literal["cards", "graded", "sealed"]

_CARD_NUMBER_RX = re.compile(r"\b(\d{1,3})\s*/\s*(\d{1,3})\b")

#: Recognised grading companies. PCA (Pokémon Card Authentication, FR) and
#: CCC / CGG appear regularly on ebay.fr listings even though they are smaller
#: than PSA / BGS / CGC. Order in the alternation does not matter — the regex
#: is anchored on word boundaries.
_GRADERS: tuple[str, ...] = (
    "psa",
    "bgs",
    "cgc",
    "cgg",
    "ccc",
    "pca",
    "beckett",
    "ace",
    "sgc",
    "hga",
    "tag",
    "get",
    "mnt",
    "gma",
)

_GRADE_RX = re.compile(
    r"\b(?P<co>" + "|".join(_GRADERS) + r")\s*"
    # Longer alternatives first so « 9.5 » beats « 9 ». Comma is the French
    # decimal separator (« CCC 9,5 ») and is normalised to a dot below.
    r"(?P<grade>10|9[.,]5|9|8[.,]5|8|7[.,]5|7|6[.,]5|6|5[.,]5|5)\b",
    re.IGNORECASE,
)

#: Strong sealed-product signals (matched on the diacritic-stripped lowercased
#: title). Order does not matter — first hit classifies the listing.
_SEALED_STRONG_SIGNALS: tuple[str, ...] = (
    "etb",
    "elite trainer",
    "trainer box",
    "demi display",
    "display",
    "booster box",
    "boite booster",
    "boite de booster",
    "box booster",
    "mini tin",
    "tin pokemon",
    "pokemon tin",
    "blister",
    "tripack",
    "tri pack",
    "triple pack",
    "coffret",
    "premium collection",
    "collection box",
    "sleeved booster",
    "booster bundle",
    "build battle",
    "ultra premium",
    "pokebox",
)

#: Weak sealed hints often used for single cards in blister/sleeve.
#: We only use these when no card-level hint is detected.
_SEALED_WEAK_SIGNALS: tuple[str, ...] = (
    "scelle",
    "sealed",
)

#: Single-card set/promo codes commonly seen in French listings
#: (e.g. "SWSH291", "SVP 052", "MEP031", "TG07").
_CARD_CODE_RX = re.compile(
    r"\b(?:svp|swsh|tg|gg|mep|sm|xy|bw|dp|hgss|sw|svp)\s*-?\s*\d{1,3}\b",
    re.IGNORECASE,
)

_STOPWORDS: frozenset[str] = frozenset(
    {
        "pokemon",
        "pokémon",
        "carte",
        "cartes",
        "card",
        "cards",
        "tcg",
        "ccg",
        "the",
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "de",
        "du",
        "et",
        "and",
        "or",
        "fr",
        "eng",
        "en",
        "ja",
        "jp",
        "jap",
        "japonais",
        "japanese",
        "japonaise",
        "anglais",
        "anglaise",
        "english",
        "francais",
        "francaise",
        "french",
        "near",
        "mint",
        "nm",
        "neuf",
        "neuve",
        "occasion",
        "rare",
        "common",
        "uncommon",
        "holographic",
        "officiel",
        "officielle",
        "original",
        "originale",
        "scellee",
        "scellees",
        "scelle",
        "scelles",
        "sealed",
        "boite",
        "promo",
        "lot",
    }
)

_NON_WORD = re.compile(r"[^a-z0-9]+")


def _strip_diacritics(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c))


def _extract_grade(title_norm: str) -> str | None:
    """Return a normalized grade label like ``PSA 10`` / ``PCA 9.5`` if present."""
    m = _GRADE_RX.search(title_norm)
    if not m:
        return None
    grade = m.group("grade").replace(",", ".")
    return f"{m.group('co').upper()} {grade}"


def _significant_tokens(title_norm: str) -> list[str]:
    """Tokenize a normalized title and drop stopwords + tiny tokens."""
    raw = _NON_WORD.sub(" ", title_norm).split()
    out: list[str] = []
    for tok in raw:
        if len(tok) < 2:
            continue
        if tok in _STOPWORDS:
            continue
        out.append(tok)
    return out


def _classify(
    title_norm: str,
    *,
    has_grade: bool,
    has_card_number: bool,
    has_card_code: bool,
) -> Category:
    """
    Decide if the listing is a graded card, a sealed product, or a raw card.

    Priority:

    1. ``has_grade`` — graded items always win, even if they happen to mention
       a sealed-product keyword (graded sealed boosters are ultra-rare).
    2. ``has_card_number`` or ``has_card_code`` — single-card hints (``12/102``,
       ``SWSH291``, ``SVP052``, ``TG07``, …). Listings using « scellé(e) » in
       this case mean *the card is sealed in plastic*, not unopened sealed
       product — we keep them as cards.
    3. Strong sealed-product keywords (ETB, display, booster box, coffret…) — sealed.
    4. Weak sealed hints ("scellé"/"sealed"):
       - if single-card hints are present (promo/code set), keep as card;
       - otherwise sealed.
    5. Default — raw card.
    """
    if has_grade:
        return "graded"
    if has_card_number or has_card_code:
        return "cards"
    for sig in _SEALED_STRONG_SIGNALS:
        if sig in title_norm:
            return "sealed"
    has_weak_sealed = any(sig in title_norm for sig in _SEALED_WEAK_SIGNALS)
    if has_weak_sealed:
        has_card_hint = "promo" in title_norm or bool(_CARD_CODE_RX.search(title_norm))
        if has_card_hint:
            return "cards"
        return "sealed"
    return "cards"


def _build_fingerprint(title: str) -> tuple[str, str | None, Category]:
    """
    Return ``(group_key, grade_label, category)``.

    ``group_key`` ignores grade so the same card raw / PSA / BGS share a slug;
    grade is carried separately and the caller groups by ``(slug, grade)``.
    """
    norm = _strip_diacritics(title).lower()
    grade = _extract_grade(norm)
    if grade:
        norm = _GRADE_RX.sub(" ", norm)

    card_match = _CARD_NUMBER_RX.search(norm)
    has_card_code = _CARD_CODE_RX.search(norm) is not None
    category = _classify(
        norm,
        has_grade=grade is not None,
        has_card_number=card_match is not None,
        has_card_code=has_card_code,
    )
    tokens = _significant_tokens(norm)

    if card_match:
        # Use the card number as the primary anchor — robust to word order
        # and language variants ("Pikachu VMAX" vs "VMAX Pikachu").
        a = card_match.group(1).zfill(3)
        b = card_match.group(2).zfill(3)
        anchor = tokens[0] if tokens else "card"
        return f"{anchor}-{a}-{b}", grade, category

    # No card number (typical for sealed): hash on the first 3 meaningful tokens.
    if not tokens:
        return _NON_WORD.sub("-", norm)[:40] or "unknown", grade, category
    return "-".join(tokens[:3]), grade, category


def _pick_display_title(titles: list[str]) -> str:
    """Pick the longest title as it usually carries the most context."""
    return max(titles, key=len) if titles else ""


def aggregate_top_sold(
    rows: list[dict[str, Any]],
    *,
    min_count: int = 1,
    limit_per_category: int = 20,
) -> dict[str, list[dict[str, Any]]]:
    """
    Group scraped sold rows by ``(category, fingerprint, grade)`` and rank
    each category independently.

    Returns ``{"cards": [...], "graded": [...], "sealed": [...]}``. Each list
    is sorted by count desc, then total value desc, with a per-category
    ``rank`` field starting at 1.

    Per-group fields: ``count``, ``total_value_eur``, ``median_price_eur``,
    ``min_price_eur``, ``max_price_eur``, ``display_title``, ``image_url``,
    ``sample_listing_url``, ``grade`` (``None`` outside the graded bucket),
    ``category``, ``approx_hours_min``.
    """
    buckets: dict[tuple[Category, str, str | None], dict[str, Any]] = {}
    for row in rows:
        title = (row.get("title") or "").strip()
        if not title:
            continue
        slug, grade, category = _build_fingerprint(title)
        key = (category, slug, grade)
        b = buckets.get(key)
        if b is None:
            b = {
                "category": category,
                "fingerprint": slug,
                "grade": grade,
                "titles": [],
                "prices": [],
                "image_url": None,
                "sample_listing_url": None,
                "approx_hours_values": [],
            }
            buckets[key] = b
        b["titles"].append(title)
        price = row.get("price_eur")
        if isinstance(price, (int, float)) and price > 0:
            b["prices"].append(float(price))
        if not b["image_url"] and row.get("image_url"):
            b["image_url"] = row["image_url"]
        if not b["sample_listing_url"] and row.get("listing_url"):
            b["sample_listing_url"] = row["listing_url"]
        h = row.get("approx_hours_ago")
        if isinstance(h, (int, float)):
            b["approx_hours_values"].append(float(h))

    grouped: dict[str, list[dict[str, Any]]] = {"cards": [], "graded": [], "sealed": []}
    for b in buckets.values():
        count = len(b["titles"])
        if count < min_count:
            continue
        prices: list[float] = b["prices"]
        approx: list[float] = b["approx_hours_values"]
        grouped[b["category"]].append(
            {
                "category": b["category"],
                "fingerprint": b["fingerprint"],
                "grade": b["grade"],
                "display_title": _pick_display_title(b["titles"]),
                "image_url": b["image_url"],
                "sample_listing_url": b["sample_listing_url"],
                "count": count,
                "total_value_eur": round(sum(prices), 2) if prices else 0.0,
                "median_price_eur": round(median(prices), 2) if prices else None,
                "min_price_eur": round(min(prices), 2) if prices else None,
                "max_price_eur": round(max(prices), 2) if prices else None,
                "approx_hours_min": round(min(approx), 1) if approx else None,
            },
        )

    for cat, items in grouped.items():
        items.sort(
            key=lambda x: (
                -int(x["count"]),
                -float(x["total_value_eur"] or 0),
                x["display_title"].lower(),
            ),
        )
        trimmed = items[:limit_per_category]
        for rank, it in enumerate(trimmed, start=1):
            it["rank"] = rank
        grouped[cat] = trimmed
    return grouped
