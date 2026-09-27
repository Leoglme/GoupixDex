from models.article import Article
from schemas.articles import ArticleUpdate
from services.article_service import update_article_from_body


def test_update_records_the_vinted_listing_id() -> None:
    article = Article(title="Coiffeton / Quaxly sv1a 081/073 AR", published_on_vinted=True, vinted_id=None)

    update_article_from_body(article, ArticleUpdate(vinted_id=6543210987))

    assert article.vinted_id == 6543210987
    assert article.title == "Coiffeton / Quaxly sv1a 081/073 AR"


def test_update_without_vinted_id_keeps_the_stored_one() -> None:
    article = Article(title="Stalgamin / Snorunt m2a 200/193 AR", vinted_id=1234567890)

    update_article_from_body(article, ArticleUpdate(title="Stalgamin / Snorunt m2a 200/193 AR - JP"))

    assert article.vinted_id == 1234567890
