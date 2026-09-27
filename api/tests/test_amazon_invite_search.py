from __future__ import annotations

import pytest

import scraper
from scraper import AmazonScraper, _select_best_title_matches, _split_search_words

# Titres copiés d'Amazon.fr : « 30ᵉ » s'y écrit avec un « ᵉ » exposant.
ELITE_TRAINER_BOX_30TH = (
    "Pokémon : Coffret Dresseur d’élite 30ᵉ Anniversaire du JCC Pokémon "
    "(1 Carte Promo entièrement illustrée, 9 boosters et des Accessoires de Jeu Premium)"
)
POSTER_COLLECTION_30TH = (
    "Pokémon : Collection Poster 30ᵉ Anniversaire du JCC Pokémon (3 Cartes Promo, 1 Poster et 3 boosters)"
)
NYMPHALI_BOX_30TH = (
    "Pokémon : Boîte 30ᵉ Anniversaire – Nymphali-ex du JCC Pokémon (1 Carte Promo Brillante et 4 boosters)"
)
BOOSTER_BUNDLE_30TH = "Pokémon : Lot de boosters 30ᵉ Anniversaire du JCC Pokémon (6 boosters)"
BLISTER_30TH = (
    "Pokémon : Blister de 2 boosters 30ᵉ Anniversaire du JCC Pokémon (1 Carte Brillante, 1 pièce et 2 boosters)"
)
PIKACHU_MINI_TIN_30TH = (
    "Pokémon : Mini-boîte 30ᵉ Anniversaire – Pikachu du JCC Pokémon (1 Autocollant, 1 Carte Artistique et 2 boosters)"
)
BINDER_COLLECTION_30TH = "Pokémon : Collection classeur 30ᵉ Anniversaire du JCC Pokémon (1 classeur et 5 boosters)"
MEWTWO_MINI_TIN_30TH = (
    "Pokémon : Mini-boîte 30ᵉ Anniversaire – Mewtwo du JCC Pokémon (1 Autocollant, 1 Carte Artistique et 2 boosters)"
)
FIRST_PARTNERS_COLLECTION = (
    "Pokémon : Collection Illustration Premiers Partenaires – Série 1 "
    "(3 Cartes Promo, 2 boosters et 1 Page d’Autocollants) du JCC Pokémon"
)
BLACK_NIGHT_ELITE_TRAINER_BOX = (
    "Pokémon : Coffret Dresseur d’élite Méga-Évolution – Nuit Noire "
    "(1 Carte Promo entièrement illustrée, 9 boosters et des Accessoires de Jeu Premium)"
)
TRANSCENDING_HEROES_ELITE_TRAINER_BOX = (
    "Pokémon : Coffret Dresseur d’élite Méga-Évolution – Héros Transcendants "
    "(1 Carte Promo entièrement illustrée, 9 boosters et des Accessoires de Jeu Premium)"
)
ILLUMIS_MINI_TIN = (
    "Pokémon : Mini-boîte Illumis – Gallame et Mucuscule (2 boosters, 1 Carte Artistique et 1 Page d’Autocollants)"
)
KANTO_MINI_TIN_BUNDLE = (
    "Pokémon : Lot de 5 Mini-boîtes Puissance de Kanto (10 boosters, 5 pièces et 5 Cartes artistiques)"
)

SEARCH_RESULTS_IN_AMAZON_ORDER = [
    ELITE_TRAINER_BOX_30TH,
    POSTER_COLLECTION_30TH,
    NYMPHALI_BOX_30TH,
    BOOSTER_BUNDLE_30TH,
    BLISTER_30TH,
    PIKACHU_MINI_TIN_30TH,
    BINDER_COLLECTION_30TH,
    FIRST_PARTNERS_COLLECTION,
    MEWTWO_MINI_TIN_30TH,
    BLACK_NIGHT_ELITE_TRAINER_BOX,
    ILLUMIS_MINI_TIN,
    TRANSCENDING_HEROES_ELITE_TRAINER_BOX,
    KANTO_MINI_TIN_BUNDLE,
]
THIRTIETH_ANNIVERSARY_PRODUCTS = [
    ELITE_TRAINER_BOX_30TH,
    POSTER_COLLECTION_30TH,
    NYMPHALI_BOX_30TH,
    BOOSTER_BUNDLE_30TH,
    BLISTER_30TH,
    PIKACHU_MINI_TIN_30TH,
    BINDER_COLLECTION_30TH,
    MEWTWO_MINI_TIN_30TH,
]


def build_rows(titles: list[str]) -> list[dict]:
    return [{"asin": f"B0TEST{index:04d}", "title": title} for index, title in enumerate(titles)]


def extract_titles(rows: list[dict]) -> list[str]:
    return [row["title"] for row in rows]


def build_result_block(asin: str, title: str, invite_only: bool) -> str:
    badge = (
        '<span aria-label="Disponible sur invitation"><span>Disponible sur invitation</span></span>'
        if invite_only
        else ""
    )
    return (
        f'<div data-component-type="s-search-result" data-asin="{asin}">'
        f"<h2><span>{title}</span></h2>{badge}</div>"
    )


def test_superscript_ordinal_reads_as_the_number() -> None:
    assert _split_search_words("Coffret Dresseur d’élite 30ᵉ Anniversaire") == [
        "coffret",
        "dresseur",
        "d",
        "elite",
        "30",
        "anniversaire",
    ]
    assert _split_search_words("30ème, 1er, 30th") == ["30", "1", "30"]


def test_pokemon_30_ans_keeps_every_30th_anniversary_product() -> None:
    kept = _select_best_title_matches(build_rows(SEARCH_RESULTS_IN_AMAZON_ORDER), "pokemon 30 ans")

    assert extract_titles(kept) == THIRTIETH_ANNIVERSARY_PRODUCTS


def test_mini_boite_30_keeps_only_the_30th_mini_tins() -> None:
    kept = _select_best_title_matches(build_rows(SEARCH_RESULTS_IN_AMAZON_ORDER), "pokemon mini-boite 30")

    assert extract_titles(kept) == [PIKACHU_MINI_TIN_30TH, MEWTWO_MINI_TIN_30TH]


def test_query_word_inside_a_title_word_does_not_match() -> None:
    kept = _select_best_title_matches(
        build_rows([TRANSCENDING_HEROES_ELITE_TRAINER_BOX, ELITE_TRAINER_BOX_30TH]), "pokemon 30 ans"
    )

    assert extract_titles(kept) == [ELITE_TRAINER_BOX_30TH]


def test_words_found_in_no_title_keep_the_amazon_order() -> None:
    rows = build_rows(SEARCH_RESULTS_IN_AMAZON_ORDER)

    assert extract_titles(_select_best_title_matches(rows, "pokemon etb")) == SEARCH_RESULTS_IN_AMAZON_ORDER
    assert extract_titles(_select_best_title_matches(rows, "pokemon cartes")) == SEARCH_RESULTS_IN_AMAZON_ORDER


def test_search_url_uses_relevance_like_the_browser() -> None:
    first_page_url = AmazonScraper()._build_invite_search_url("pokemon 30 ans", 1)

    assert "k=pokemon+30+ans" in first_page_url
    assert "rh=p_6%3AA1X6FK5RDHNB96" in first_page_url
    assert "date-desc-rank" not in first_page_url
    assert AmazonScraper()._build_invite_search_url("pokemon 30 ans", 2) == f"{first_page_url}&page=2"


def test_search_sends_the_query_and_stops_on_a_page_without_new_invites(monkeypatch: pytest.MonkeyPatch) -> None:
    html_by_page = {
        1: "".join(
            [
                build_result_block("B0AAAAAAA1", ELITE_TRAINER_BOX_30TH, invite_only=True),
                build_result_block("B0AAAAAAA2", BLACK_NIGHT_ELITE_TRAINER_BOX, invite_only=True),
                build_result_block("B0AAAAAAA3", "Funko Pop! Games: Pokemon - Mew", invite_only=False),
                build_result_block("B0AAAAAAA4", PIKACHU_MINI_TIN_30TH, invite_only=True),
            ]
        ),
        2: build_result_block("B0AAAAAAA5", "LEGO Pokémon Évoli 72151", invite_only=False),
    }
    fetched_urls: list[str] = []

    def fake_fetch_html(url: str) -> str:
        fetched_urls.append(url)
        page = int(url.rsplit("&page=", 1)[1]) if "&page=" in url else 1
        return f"<html><body>{html_by_page[page]}</body></html>"

    amazon_scraper = AmazonScraper()
    monkeypatch.setattr(amazon_scraper, "_fetch_html", fake_fetch_html)
    monkeypatch.setattr(scraper.time, "sleep", lambda _seconds: None)

    found_products = amazon_scraper.search_invitation_items("Pokémon 30 ans", max_pages=16, max_items=30)

    assert [product["asin"] for product in found_products] == ["B0AAAAAAA1", "B0AAAAAAA4"]
    assert len(fetched_urls) == 2
    assert "k=pokemon+30+ans" in fetched_urls[0]
