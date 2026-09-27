import asyncio
from decimal import Decimal
from typing import Any

import pytest

from services.vinted_service import VintedService

TITLE = "Absol s12a 191/172 AR - Vstar Universe - Pokémon Japonais"


def _wardrobe_row(item_id: int, title: str = TITLE, price: str = "5.0", **status_flags: bool) -> dict[str, Any]:
    return {"id": item_id, "title": title, "price": price, "is_closed": False, "is_draft": False, **status_flags}


def fake_wardrobe(
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict[str, Any]] | None,
    *,
    profile_tile_match: int | None = None,
) -> None:
    async def member_id() -> int:
        return 198987080

    async def wardrobe_rows(_tab: object, _member_id: int) -> list[dict[str, Any]] | None:
        return rows

    async def profile_tiles_lookup(_tab: object, **_criteria: Any) -> int | None:
        return profile_tile_match

    monkeypatch.setattr(VintedService, "fetch_logged_in_vinted_user_numeric_id", member_id)
    monkeypatch.setattr(VintedService, "_fetch_member_wardrobe_rows", wardrobe_rows)
    monkeypatch.setattr(VintedService, "find_member_listing_item_id_for_match", profile_tiles_lookup)


def find_listing(vinted_id: int | None, title: str = TITLE) -> int | None:
    return asyncio.run(
        VintedService.find_live_member_listing(object(), vinted_id=vinted_id, title=title, sell_price=Decimal("5.00"))
    )


def test_known_listing_still_online_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_wardrobe(monkeypatch, [_wardrobe_row(8963916746)])
    assert find_listing(8963916746) == 8963916746


def test_known_listing_deleted_or_sold_on_vinted_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_wardrobe(monkeypatch, [_wardrobe_row(1), _wardrobe_row(8963916746, is_closed=True)])
    assert find_listing(8963916746) is None


def test_listing_without_id_is_found_by_title_and_price(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_wardrobe(monkeypatch, [_wardrobe_row(1, title="Autre carte"), _wardrobe_row(42)])
    assert find_listing(None) == 42


def test_listing_without_id_missing_from_the_wardrobe_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_wardrobe(monkeypatch, [_wardrobe_row(1, title="Autre carte")])
    assert find_listing(None) is None


def test_duplicate_titles_without_the_expected_price_are_not_guessed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_wardrobe(monkeypatch, [_wardrobe_row(1, price="6.0"), _wardrobe_row(2, price="7.0")])
    with pytest.raises(RuntimeError, match="Plusieurs annonces"):
        find_listing(None)


def test_unreadable_wardrobe_never_marks_a_listing_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_wardrobe(monkeypatch, None, profile_tile_match=None)
    assert find_listing(8963916746) == 8963916746
    with pytest.raises(RuntimeError, match="illisible"):
        find_listing(None)
