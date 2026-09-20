"""Mapping GoupixDex → libellés Leboncoin."""

from decimal import Decimal

from models.article import Article
from services.leboncoin_listing_maps import (
    LEBONCOIN_COND_BOITE,
    LEBONCOIN_ETAT_NEUF,
    LEBONCOIN_ETAT_TRES_BON,
    leboncoin_conditionnement_from_article,
    leboncoin_etat_from_app_condition,
    leboncoin_listing_fields_from_article,
)


def test_etat_near_mint() -> None:
    assert leboncoin_etat_from_app_condition("Near Mint") == LEBONCOIN_ETAT_TRES_BON


def test_etat_graded() -> None:
    assert leboncoin_etat_from_app_condition("Played", is_graded=True) == LEBONCOIN_ETAT_NEUF


def test_fields_from_article() -> None:
    a = Article()
    a.condition = "Good"
    a.is_graded = False
    a.title = "Carte Pokémon test"
    a.set_code = "SV7"
    fields = leboncoin_listing_fields_from_article(a)
    assert fields.produit == "Jeux de cartes"
    assert fields.etat == "Bon état"
    assert fields.conditionnement == "Sans emballage"
    assert fields.epoque == "Après 2010"


def test_conditionnement_graded() -> None:
    a = Article()
    a.is_graded = True
    a.title = "PSA 10"
    assert leboncoin_conditionnement_from_article(a) == LEBONCOIN_COND_BOITE
