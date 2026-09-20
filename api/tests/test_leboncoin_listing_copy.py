from models.article import Article
from services.leboncoin_listing_copy import build_leboncoin_listing_copy


def test_description_no_leboncoin_meta_label() -> None:
    a = Article()
    a.title = "Dracaufeu SV"
    a.condition = "Near Mint"
    a.description = "Belle carte."
    _, desc = build_leboncoin_listing_copy(a)
    assert "État Leboncoin" not in desc
    assert "État :" in desc


def test_description_strips_urls_and_competitors() -> None:
    a = Article()
    a.title = "Pikachu"
    a.condition = "Good"
    a.description = "Voir https://ebay.com/foo\nAussi sur Vinted\nCarte propre."
    _, desc = build_leboncoin_listing_copy(a)
    assert "ebay" not in desc.lower()
    assert "vinted" not in desc.lower()
    assert "Carte propre" in desc
