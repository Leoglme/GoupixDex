from decimal import Decimal
from typing import Any

from services.vinted_service import VintedService

CATALOG_OVERLAY = (
    "Dimoclès AR 98/88\nPlein d'autre cartes dans ma collection\nBonne, "
    "Marque: Pokémon, État: Neuf sans étiquette, 2.00 €, 2.80 €"
)
MEMBER_OVERLAY = (
    "T-shirt bershka, marque: Bershka, état: Satisfaisant, taille: S, "
    "2,00 €, 2,80 € Protection acheteurs incluse"
)


def _pick(rows: list[dict[str, Any]], title: str, price: Decimal | float | int | None) -> int | None:
    return VintedService._pick_member_listing_match(
        rows,
        normalized_title=VintedService._normalize_match_token(title),
        price_fragments=VintedService._price_match_fragments(price),
    )


def test_matches_catalog_overlay_with_dot_price() -> None:
    rows = [{"id": 10085760293, "overlay": CATALOG_OVERLAY, "title": "Pokémon", "price": "2,00 €"}]
    assert _pick(rows, "Dimoclès AR 98/88", Decimal("2.00")) == 10085760293


def test_matches_member_overlay_with_comma_and_nbsp_price() -> None:
    rows = [{"id": 42, "overlay": MEMBER_OVERLAY, "title": "Bershka", "price": "2,00 €"}]
    assert _pick(rows, "t-shirt   bershka", 2) == 42


def test_price_mismatch_rejects_tile() -> None:
    rows = [{"id": 42, "overlay": MEMBER_OVERLAY, "title": "", "price": "2,00 €"}]
    assert _pick(rows, "T-shirt bershka", 5.5) is None


def test_title_only_when_price_unknown() -> None:
    rows = [{"id": 7, "overlay": MEMBER_OVERLAY, "title": "", "price": ""}]
    assert _pick(rows, "T-shirt bershka", None) == 7


def test_first_tile_wins_on_duplicates() -> None:
    rows = [
        {"id": 1, "overlay": MEMBER_OVERLAY, "title": "", "price": ""},
        {"id": 2, "overlay": MEMBER_OVERLAY, "title": "", "price": ""},
    ]
    assert _pick(rows, "T-shirt bershka", 2.0) == 1


def test_no_tile_returns_none_without_error() -> None:
    assert _pick([], "Pikachu", 3) is None
    rows = [{"id": 9, "overlay": "Autre chose, 3,00 €", "title": "", "price": "3,00 €"}]
    assert _pick(rows, "Pikachu", 3) is None
