from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Limite champ titre Vinted (espaces comptés comme un caractère).
ARTICLE_TITLE_MAX_LEN_VINTED = 100


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
    #: Remet l’article en « non publié » côté GoupixDex (ne supprime pas l’annonce sur Vinted).
    clear_vinted_publication: bool | None = None
    #: Idem eBay : efface le suivi local et l’identifiant d’annonce enregistré.
    clear_ebay_publication: bool | None = None

    @field_validator("title")
    @classmethod
    def title_vinted_max_length(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if len(s) > ARTICLE_TITLE_MAX_LEN_VINTED:
            raise ValueError(
                f"Le titre ne doit pas dépasser {ARTICLE_TITLE_MAX_LEN_VINTED} caractères "
                f"(limite Vinted, espaces inclus). Longueur : {len(s)}."
            )
        return s


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
