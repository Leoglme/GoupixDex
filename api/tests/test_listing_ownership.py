from typing import Any

from services.listing_ownership_service import ListingOwnershipService

TITLE = "Émetteur-Récepteur de la Team Rocket ASC 263/217  -  Héros Transcendants -  Pokémon Français"


def article(article_id: int, **fields: Any) -> dict[str, Any]:
    return {"id": article_id, "title": TITLE, "is_sold": False, **fields}


def test_titles_differing_only_by_accents_case_or_spacing_are_the_same() -> None:
    assert ListingOwnershipService.build_comparable_title(TITLE) == ListingOwnershipService.build_comparable_title(
        "emetteur recepteur de la team rocket asc 263/217 - heros transcendants - pokemon francais"
    )


def test_listing_ids_of_the_other_articles_exclude_the_article_itself() -> None:
    articles = [
        article(73, vinted_id=8740266821),
        article(74, vinted_id=8740266999),
        article(75, vinted_id=None),
    ]

    assert ListingOwnershipService.collect_other_articles_listing_ids(articles, 73, "vinted") == frozenset(
        {"8740266999"}
    )


def test_only_an_unsold_copy_listed_without_id_makes_the_title_ambiguous() -> None:
    sold_article = article(73, is_sold=True, published_on_leboncoin=True)
    articles = [
        sold_article,
        article(74, published_on_leboncoin=True, leboncoin_listing_id="3278047139"),
        article(75, is_sold=True, published_on_leboncoin=True, leboncoin_listing_id=None),
        article(76, published_on_leboncoin=False, leboncoin_listing_id=None),
    ]
    assert ListingOwnershipService.find_other_unsold_copy_without_listing_id(articles, sold_article, "leboncoin") is None

    articles.append(article(77, published_on_leboncoin=True, leboncoin_listing_id=None))
    assert ListingOwnershipService.find_other_unsold_copy_without_listing_id(articles, sold_article, "leboncoin") == 77
