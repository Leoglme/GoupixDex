from services.leboncoin_service import LeboncoinService


def test_listing_id_is_read_from_the_published_ad_url() -> None:
    assert LeboncoinService._extract_listing_id("https://www.leboncoin.fr/ad/collection/3000000001") == "3000000001"


def test_listing_id_is_read_from_the_confirmation_query() -> None:
    url = "https://www.leboncoin.fr/deposer-une-annonce/confirmation?listing_id=2999999999"
    assert LeboncoinService._extract_listing_id(url) == "2999999999"


def test_confirmation_without_listing_id_gives_none() -> None:
    assert LeboncoinService._extract_listing_id("https://www.leboncoin.fr/deposer-une-annonce/confirmation") is None
