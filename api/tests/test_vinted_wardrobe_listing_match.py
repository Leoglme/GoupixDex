from decimal import Decimal
from typing import Any

from services.vinted_service import VintedService

LISTING_TITLE = "Cornèbre / Team Rocket's Murkrow sv10 106/098 AR - The Glory of Team Rocket - Pokémon Japonais"


def _wardrobe_row(item_id: Any, title: str = LISTING_TITLE, price: str = "4.0", **status_flags: bool) -> dict[str, Any]:
    return {"id": item_id, "title": title, "price": price, "is_closed": False, "is_draft": False, **status_flags}


def _pick(rows: list[dict[str, Any]], title: str, price: Decimal | float | int | None) -> int | None:
    return VintedService._pick_wardrobe_item_match(rows, title=title, sell_price=price)


def test_exact_title_and_price_match() -> None:
    rows = [_wardrobe_row(1, title="Autre carte"), _wardrobe_row(9704050387)]
    assert _pick(rows, LISTING_TITLE, Decimal("4.00")) == 9704050387


def test_title_ignores_case_and_repeated_spaces() -> None:
    rows = [_wardrobe_row(5, title="Émetteur-Récepteur de la Team Rocket ASC 263/217  -  Héros Transcendants")]
    assert _pick(rows, "émetteur-récepteur de la team rocket asc 263/217 - héros transcendants", 4) == 5


def test_single_title_match_survives_a_price_changed_on_vinted() -> None:
    assert _pick([_wardrobe_row(7, price="3.5")], LISTING_TITLE, Decimal("4.00")) == 7


def test_expected_price_breaks_a_title_tie() -> None:
    rows = [_wardrobe_row(1, price="6.0"), _wardrobe_row(2, price="4.0")]
    assert _pick(rows, LISTING_TITLE, 4.0) == 2


def test_newest_listing_wins_when_duplicates_share_the_price() -> None:
    rows = [_wardrobe_row(20), _wardrobe_row(10)]
    assert _pick(rows, LISTING_TITLE, Decimal("4.00")) == 20


def test_ambiguous_duplicates_are_not_picked() -> None:
    rows = [_wardrobe_row(1, price="6.0"), _wardrobe_row(2, price="7.0")]
    assert _pick(rows, LISTING_TITLE, Decimal("4.00")) is None
    assert _pick(rows, LISTING_TITLE, None) is None


def test_sold_and_draft_listings_are_ignored() -> None:
    rows = [_wardrobe_row(1, is_closed=True), _wardrobe_row(2, is_draft=True), _wardrobe_row(3, price="9.0")]
    assert _pick(rows, LISTING_TITLE, Decimal("4.00")) == 3
    assert _pick(rows[:2], LISTING_TITLE, Decimal("4.00")) is None


def test_partial_title_is_not_a_match() -> None:
    rows = [_wardrobe_row(1, title="Pikachu ex 063/165")]
    assert _pick(rows, "Pikachu", None) is None
    assert _pick(rows, "", None) is None


def test_rows_without_usable_id_are_skipped() -> None:
    rows = [_wardrobe_row(None), _wardrobe_row("abc"), _wardrobe_row(0), _wardrobe_row(42)]
    assert _pick(rows, LISTING_TITLE, Decimal("4.00")) == 42


def test_price_in_cents_reads_api_and_goupixdex_amounts() -> None:
    assert VintedService._price_in_cents("4.0") == 400
    assert VintedService._price_in_cents(Decimal("12.30")) == 1230
    assert VintedService._price_in_cents(12.3) == 1230
    assert VintedService._price_in_cents(3) == 300
    assert VintedService._price_in_cents("") is None
    assert VintedService._price_in_cents(None) is None
    assert VintedService._price_in_cents("abc") is None
