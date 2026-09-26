from typing import Any

import pytest

from services import card_image_fallback_service as fallback
from services.catalog_browse_service import (
    _ghost_set_ids,
    _merge_subset_rows,
    readable_set_name,
)


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


def test_match_unown_letters_including_the_encoded_question_mark(monkeypatch: pytest.MonkeyPatch) -> None:
    cards = [_pokemontcg_card("?", "Unown"), _pokemontcg_card("A", "Unown"), _pokemontcg_card("!", "Unown")]
    monkeypatch.setattr(fallback, "_pokemontcg_cards", lambda _pokemontcg_id: cards)
    english_names = {"!": "unown", "%3F": "unown", "A": "unown"}

    found = fallback._match_pokemontcg("exu", ["!", "%3F", "A"], english_names)

    assert fallback.pokemontcg_set_id("exu") == "ex10"
    assert found["!"].low == "https://img.test/!/small"
    assert found["%3F"].low == "https://img.test/?/small"
    assert found["A"].low == "https://img.test/A/small"


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


def _tcgplayer_card(number: str, name: str, product_id: int) -> fallback._TcgplayerCard:
    return fallback._TcgplayerCard(
        number=fallback._tcgplayer_number(number),
        name=fallback._tcgplayer_name(name),
        is_variant="(" in name,
        urls=fallback.CardImageUrls(low=f"https://tcg.test/{product_id}_400w.jpg", high=f"https://tcg.test/{product_id}_hd.jpg"),
    )


def test_tcgplayer_trainer_kit_half_is_chosen_by_name_never_guessed(monkeypatch: pytest.MonkeyPatch) -> None:
    cards = [
        _tcgplayer_card("8/30", "Fairy Energy (#8)", 1),
        _tcgplayer_card("8/30", "Psychic Energy (#8)", 2),
        _tcgplayer_card("9/30", "Noibat (#9)", 3),
        _tcgplayer_card("9/30", "Spritzee (#9)", 4),
    ]
    monkeypatch.setattr(fallback, "_tcgplayer_group", lambda _locale, _set_id: (3, 1532))
    monkeypatch.setattr(fallback, "_tcgplayer_cards", lambda _category, _group: cards)

    found = fallback._match_tcgplayer("fr", {"id": "tk-xy-n"}, ["8", "9"], {"8": "psychicenergy", "9": "pumpkaboo"})

    assert found == {"8": cards[1].urls}


def test_tcgplayer_japanese_number_prefers_the_regular_print(monkeypatch: pytest.MonkeyPatch) -> None:
    cards = [_tcgplayer_card("122/100", "Elesa's Sparkle (Master Ball)", 1), _tcgplayer_card("122/100", "Elesa's Sparkle - 122/100", 2)]
    monkeypatch.setattr(fallback, "_tcgplayer_group", lambda _locale, _set_id: (85, 23627))
    monkeypatch.setattr(fallback, "_tcgplayer_cards", lambda _category, _group: cards)

    found = fallback._match_tcgplayer("ja", {"id": "S8"}, ["122"], {})

    assert found == {"122": cards[1].urls}


def test_tcgplayer_unnumbered_japanese_group_matches_english_names(monkeypatch: pytest.MonkeyPatch) -> None:
    cards = [_tcgplayer_card("", "Dark Crobat", 1), _tcgplayer_card("", "Nidoran M", 2), _tcgplayer_card("", "Pikachu", 3)]
    monkeypatch.setattr(fallback, "_tcgplayer_group", lambda _locale, _set_id: (85, 23729))
    monkeypatch.setattr(fallback, "_tcgplayer_cards", lambda _category, _group: cards)
    monkeypatch.setattr(
        fallback,
        "_japanese_card_english_names",
        lambda _detail, _local_ids: {"001": "darkcrobat", "002": "nidoranm", "003": "raichu"},
    )

    found = fallback._match_tcgplayer("ja", {"id": "neo4"}, ["001", "002", "003"], {})

    assert found == {"001": cards[0].urls, "002": cards[1].urls}


def test_japanese_english_name_uses_prefix_species_and_energy_types() -> None:
    assert fallback._japanese_english_name("暗いクロバット", 169) == "Dark Crobat"
    assert fallback._japanese_english_name("R団のファイヤー", 146) == "Rocket's Moltres"
    assert fallback._japanese_english_name("基本闘エネルギー", None) == "Fighting Energy"
    assert fallback._japanese_english_name("オーキドはかせ", None) is None
    assert fallback._tcgplayer_name(fallback._japanese_english_name("ニドラン♂", 32) or "") == "nidoranm"


def test_reprint_artwork_skips_the_same_set_and_tcg_pocket(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {
        "fr/cards/2018sm-fr-2": {"illustrator": "Akira Komayama"},
        "fr/cards": [
            {"id": "2018sm-fr-2", "image": "https://assets.test/fr/sm/2018sm-fr/2"},
            {"id": "A3-018", "image": "https://assets.test/fr/tcgp/A3/018"},
            {"id": "sm1-18", "image": "https://assets.test/fr/sm/sm1/18"},
        ],
    }
    monkeypatch.setattr(fallback, "_tcgdex_json", lambda path, params=None: responses.get(path))

    found = fallback._match_reprint_artwork(
        "fr", {"id": "2018sm-fr", "cards": [{"id": "2018sm-fr-2", "localId": "2", "name": "Croquine"}]}, ["2"]
    )

    assert found == {"2": fallback.CardImageUrls(low="https://assets.test/fr/sm/sm1/18/low.webp", high="https://assets.test/fr/sm/sm1/18/high.webp")}
