from typing import Any

import pytest

from services import card_image_fallback_service as fallback
from services.catalog_browse_service import _ghost_set_ids, _merge_subset_rows, readable_set_name


def _pokemontcg_card(number: str, name: str) -> dict[str, Any]:
    return {
        "number": number,
        "name": name,
        "images": {"small": f"https://img.test/{number}/small", "large": f"https://img.test/{number}/large"},
    }


def test_pokemontcg_set_id_follows_rule_and_exceptions() -> None:
    assert fallback.pokemontcg_set_id("sv03.5") == "sv3pt5"
    assert fallback.pokemontcg_set_id("me01") == "me1"
    assert fallback.pokemontcg_set_id("swsh12.5gg") == "swsh12pt5gg"
    assert fallback.pokemontcg_set_id("30th-c") == "me55c"
    assert fallback.pokemontcg_set_id("basep") == "basep"


def test_match_by_name_when_numbering_follows_the_original_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    cards = [
        _pokemontcg_card("100", "Darkrai & Cresselia LEGEND"),
        _pokemontcg_card("4", "Charizard"),
        _pokemontcg_card("99", "Darkrai & Cresselia LEGEND"),
        _pokemontcg_card("106", "Palkia LV.X"),
    ]
    monkeypatch.setattr(fallback, "_pokemontcg_cards", lambda _pokemontcg_id: cards)
    english_names = {
        "001": fallback._normalize_name("Charizard"),
        "019": fallback._normalize_name("Darkrai & Cresselia LEGEND"),
        "020": fallback._normalize_name("Darkrai & Cresselia LEGEND"),
        "022": fallback._normalize_name("Palkia"),
    }

    found = fallback._match_pokemontcg("30th-c", ["001", "019", "020", "022"], english_names)

    assert found["001"].low == "https://img.test/4/small"
    assert found["019"].low == "https://img.test/99/small"
    assert found["020"].low == "https://img.test/100/small"
    assert found["022"].high == "https://img.test/106/large"


def test_match_by_number_when_numbering_and_names_agree(monkeypatch: pytest.MonkeyPatch) -> None:
    cards = [_pokemontcg_card("TG01", "Flareon"), _pokemontcg_card("TG02", "Vaporeon")]
    monkeypatch.setattr(fallback, "_pokemontcg_cards", lambda _pokemontcg_id: cards)
    english_names = {"TG1": "flareon", "TG2": "vaporeon"}

    found = fallback._match_pokemontcg("swsh9tg", ["TG2"], english_names)

    assert list(found) == ["TG2"]
    assert found["TG2"].low == "https://img.test/TG02/small"


def test_no_match_without_english_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fallback, "_pokemontcg_cards", lambda _pokemontcg_id: [_pokemontcg_card("1", "Pikachu")])

    assert fallback._match_pokemontcg("2018sm-fr", ["1"], {}) == {}


def test_readable_set_name_splits_glued_numbers_only_after_a_word() -> None:
    assert readable_set_name("Collection Classique30ᵉ Anniversaire") == "Collection Classique 30ᵉ Anniversaire"
    assert readable_set_name("Collection McDonald's 2019") == "Collection McDonald's 2019"
    assert readable_set_name("sm2+") == "sm2+"


def test_merge_subset_rows_moves_classic_collection_into_its_parent() -> None:
    series = [
        {
            "id": "me",
            "sets": [
                {"id": "30th-c", "name": "Collection Classique30ᵉ Anniversaire", "cardCount": {"total": 30}},
                {"id": "30th", "name": "30ᵉ Anniversaire", "cardCount": {"total": 161, "official": 128}},
            ],
        }
    ]

    merged = _merge_subset_rows(series, "fr")

    assert [row["id"] for row in merged[0]["sets"]] == ["30th"]
    assert merged[0]["sets"][0]["cardCount"] == {"total": 191, "official": 128}
    assert series[0]["sets"][1]["cardCount"]["total"] == 161


def test_ghost_sets_are_empty_twins_or_repeated_placeholders() -> None:
    series = [
        {
            "sets": [
                {"id": "SM1p", "name": "サン＆ムーン"},
                {"id": "SM1+", "name": "サン＆ムーン"},
                {"id": "PMCG1", "name": "拡張パック"},
                {"id": "ADV1", "name": "拡張パック"},
                {"id": "S4a", "name": "シャイニースターV"},
                {"id": "CS1a", "name": "トリプレットビート"},
                {"id": "CS1b", "name": "トリプレットビート"},
                {"id": "CS2a", "name": "トリプレットビート"},
            ]
        }
    ]
    facts = {
        "SM1p": ("2017-01-27", 68),
        "SM1+": ("2017-01-27", 0),
        "PMCG1": ("1996-10-20", 102),
        "ADV1": ("2003-01-31", 0),
        "S4a": ("2020-11-20", 0),
        "CS1a": ("2024-04-26", 0),
        "CS1b": ("2024-04-26", 0),
        "CS2a": ("2024-04-26", 0),
    }

    assert _ghost_set_ids(series, facts) == {"SM1+", "CS1a", "CS1b", "CS2a"}
