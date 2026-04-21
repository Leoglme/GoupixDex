from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ArticleUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    pokemon_name: str | None = None
    set_code: str | None = None
    card_number: str | None = None
    condition: str | None = None
    is_graded: bool | None = None
    graded_grader_value_id: str | None = None
    graded_grade_value_id: str | None = None
    graded_cert_number: str | None = None
    purchase_price: Decimal | None = None
    sell_price: Decimal | None = None


class SoldPatch(BaseModel):
    """Mark as sold: actual proceeds and channel (listing price ``sell_price`` is unchanged)."""

    sold_price: Decimal = Field(ge=0)
    sale_source: Literal["vinted", "ebay"] = "vinted"


class BulkIdsBody(BaseModel):
    """Bulk delete articles (same owner)."""

    ids: list[int] = Field(min_length=1, max_length=500)


class VintedBatchStartBody(BaseModel):
    """Start a grouped Vinted publish job (single Chrome session)."""

    article_ids: list[int] = Field(min_length=1, max_length=40)
