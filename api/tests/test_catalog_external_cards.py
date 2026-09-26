from typing import Any

import pytest

from services import card_image_fallback_service as fallback
from services import catalog_external_cards_service as external
from services import catalog_limitless_ja_service as limitless
from services import collection_card_lookup_service as lookup
from services.catalog_browse_service import _hidden_set_ids
from services.species_locale_names_service import SpeciesLocaleNamesService

LIMITLESS_CDN = "https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpc"


def _limitless_card(
    number: str, name_ja: str, name_en: str | None, card_type: str = "G Basic"
) -> limitless.LimitlessCard:
    return limitless.LimitlessCard(
        number=number,
        name_ja=name_ja,
        name_en=name_en,
        card_type=card_type,
        rarity="Common",
        image_xs=f"{LIMITLESS_CDN}/XY8r/XY8r_{number}_R_JP_XS.png",
    )


def test_limitless_twin_sets_use_their_own_codes() -> None:
    index = {"XY8b": "Blue Counterattack", "XY8r": "Red Light Flash", "S4a": "Shiny Star V", "SM1+": "Sun & Moon+"}

    assert limitless._resolve_limitless_code("XY8a", index) == "XY8b"
    assert limitless._resolve_limitless_code("XY8b", index) == "XY8r"
    assert limitless._resolve_limitless_code("S4a", index) == "S4a"
    assert limitless._resolve_limitless_code("SM1p", index) == "SM1+"
    assert limitless._resolve_limitless_code("XY11a", index) is None


def test_limitless_list_rows_keep_type_rarity_and_scan() -> None:
    page = """
    <table>
      <tr><th>Set</th><th>No</th><th>Name</th><th>Type</th><th>Rarity</th></tr>
      <tr data-hover="https://cdn.test/S4a/S4a_1_R_JP_XS.png">
        <td><span>S4a</span></td><td><a href="/cards/jp/S4a/1">1</a></td><td><a>モクロー</a></td>
        <td>G Basic</td><td>Common</td>
      </tr>
    </table>
    """

    assert limitless._parse_limitless_list_table(page) == [
        {
            "no": "1",
            "name": "モクロー",
            "type": "G Basic",
            "rarity": "Common",
            "image": "https://cdn.test/S4a/S4a_1_R_JP_XS.png",
        }
    ]


def test_external_cards_come_from_limitless_without_unnumbered_energies(monkeypatch: pytest.MonkeyPatch) -> None:
    cards = [
        _limitless_card("1", "パラス", None),
        _limitless_card("64", "サカキの計画", None, card_type="Supporter"),
        _limitless_card("G", "基本草エネルギー", None, card_type="Basic Energy"),
    ]
    monkeypatch.setattr(external, "limitless_jp_cards", lambda _set_id: cards)
    english_names = {"1": "Paras", "64": "Giovanni's Scheme"}
    monkeypatch.setattr(external, "tcgplayer_japanese_card_names", lambda _set_id: english_names)

    found = external.external_set_cards("XY8b")

    assert [card.local_id for card in found] == ["001", "064"]
    assert [card.name_en for card in found] == ["Paras", "Giovanni's Scheme"]
    assert found[0].images == fallback.CardImageUrls(
        low=f"{LIMITLESS_CDN}/XY8r/XY8r_1_R_JP_SM.png",
        high=f"{LIMITLESS_CDN}/XY8r/XY8r_1_R_JP_LG.png",
    )
    assert found[0].source == "limitless"


def test_external_cards_fall_back_to_tcgplayer_before_the_xy_era(monkeypatch: pytest.MonkeyPatch) -> None:
    listings = [
        fallback.TcgplayerCardListing(number="001", name="Koffing", rarity="Common", urls=None),
        fallback.TcgplayerCardListing(number="014", name="Goldeen", rarity="Common", urls=None),
    ]
    monkeypatch.setattr(external, "limitless_jp_cards", lambda _set_id: [])
    monkeypatch.setattr(external, "tcgplayer_japanese_card_listings", lambda _set_id: listings)

    found = external.external_card("ADV1", "14")

    assert found is not None
    assert (found.local_id, found.name_en, found.name_ja, found.source) == ("014", "Goldeen", None, "tcgplayer")
    assert external.external_card("ADV1", "099") is None


def test_tcgplayer_listings_prefer_the_normal_print_and_keep_online_scans(monkeypatch: pytest.MonkeyPatch) -> None:
    def product(product_id: int, name: str, number: str) -> dict[str, Any]:
        return {
            "productId": product_id,
            "name": name,
            "imageUrl": f"https://tcg.test/{product_id}_200w.jpg",
            "extendedData": [{"name": "Number", "value": number}, {"name": "Rarity", "value": "Common"}],
        }

    products = [
        product(2, "Bill (Mirror Holofoil)", "069/070"),
        product(1, "Bill", "069/070"),
        product(3, "Weedle", "001/070"),
        {"productId": 4, "name": "Booster Box", "extendedData": []},
    ]
    monkeypatch.setattr(fallback, "_tcgplayer_group", lambda _locale, _set_id: (85, 24025))
    monkeypatch.setattr(fallback, "_tcgplayer_json", lambda _path: products)
    monkeypatch.setattr(fallback, "_assets_exist", lambda urls: ["/3_" not in url for url in urls])

    listings = fallback.tcgplayer_japanese_card_listings("L1a-test")

    assert [(listing.number, listing.name) for listing in listings] == [("001", "Weedle"), ("069", "Bill")]
    assert listings[0].urls is None
    assert listings[1].urls == fallback.CardImageUrls(
        low="https://tcg.test/1_400w.jpg", high="https://tcg.test/1_in_1000x1000.jpg"
    )


class _TcgdexWithEmptyJapaneseSet:
    def get_set(self, locale: str, set_id: str) -> dict[str, Any]:
        if locale != "ja":
            raise ValueError("no such set")
        return {"id": set_id, "name": "シャイニースターV", "cards": []}

    def get_card(self, _locale: str, card_id: str) -> dict[str, Any]:
        raise ValueError(f"no card {card_id}")


def test_collection_lookup_reads_the_external_card_of_an_empty_japanese_set(monkeypatch: pytest.MonkeyPatch) -> None:
    card = external.ExternalCard(
        local_id="001",
        name_ja="モクロー",
        name_en="Rowlet",
        rarity="Common",
        images=fallback.CardImageUrls(low="https://cdn.test/sm.png", high="https://cdn.test/lg.png"),
        source="limitless",
    )
    monkeypatch.setattr(lookup, "external_card", lambda _set_id, _local_id: card)
    species = SpeciesLocaleNamesService("Brindibou", "モクロー")
    monkeypatch.setattr(lookup, "fetch_species_locale_names", lambda _name: species)

    row = lookup.fetch_card_for_collection(
        tcgdex_card_id="S4a-001", physical_language="ja", tcgdex=_TcgdexWithEmptyJapaneseSet()
    )

    assert row["tcgdex_card_id"] == "S4a-001"
    assert (row["card_name_en"], row["card_name_fr"], row["card_name_ja"]) == ("Rowlet", "Brindibou", "モクロー")
    assert row["display_name"] == "Brindibou"
    assert (row["image_url"], row["image_url_high"]) == ("https://cdn.test/sm.png", "https://cdn.test/lg.png")
    assert (row["market_price_eur"], row["cardmarket_id_product"], row["source"]) == (None, None, "limitless")


def test_collection_lookup_never_borrows_a_japanese_card_for_another_language(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lookup, "external_card", lambda _set_id, _local_id: pytest.fail("JP-only fallback"))

    with pytest.raises(ValueError, match="TCGdex has no card"):
        lookup.fetch_card_for_collection(
            tcgdex_card_id="S4a-001", physical_language="fr", tcgdex=_TcgdexWithEmptyJapaneseSet()
        )


def test_empty_sets_stay_listed_only_when_another_source_fills_them() -> None:
    series = [{"sets": [{"id": "S4a", "name": "シャイニースターV"}, {"id": "jumbo", "name": "Jumbo cards"}]}]
    facts = {"S4a": ("2020-11-20", 0), "jumbo": ("2000-02-01", 0)}

    assert _hidden_set_ids(series, facts, {"S4a": 326}) == {"jumbo"}
