from decimal import Decimal

from models.article import Article
from services.stats_service import _channel_split


def sold_article(sale_source: str, sold_price: str) -> Article:
    article = Article()
    article.is_sold = True
    article.sale_source = sale_source
    article.sold_price = Decimal(sold_price)
    article.sell_price = None
    article.purchase_price = Decimal("1")
    return article


def test_each_sale_channel_has_its_own_count_and_revenue() -> None:
    split = _channel_split(
        [sold_article("vinted", "4.50"), sold_article("leboncoin", "3"), sold_article("leboncoin", "2.50")]
    )

    assert split == {
        "vinted_count": 1,
        "vinted_revenue_eur": 4.5,
        "ebay_count": 0,
        "ebay_revenue_eur": 0,
        "leboncoin_count": 2,
        "leboncoin_revenue_eur": 5.5,
    }
