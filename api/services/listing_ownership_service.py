"""Appartenance des annonces aux articles du compte : une annonce cherchée sans son identifiant ne doit jamais être celle d’un autre article."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal

import httpx

MarketplaceWithPcRemoval = Literal["vinted", "leboncoin"]


class ListingOwnershipService:
    """Annonces des autres articles du compte, à écarter quand le PC cherche une annonce par son titre."""

    _PUBLISHED_FIELD: dict[MarketplaceWithPcRemoval, str] = {
        "vinted": "published_on_vinted",
        "leboncoin": "published_on_leboncoin",
    }
    _LISTING_ID_FIELD: dict[MarketplaceWithPcRemoval, str] = {
        "vinted": "vinted_id",
        "leboncoin": "leboncoin_listing_id",
    }

    @staticmethod
    def build_comparable_title(title: str) -> str:
        """
        Réduit un titre à ses lettres et chiffres, sans accents ni casse.

        Args:
            title: Titre d’un article.

        Returns:
            Le titre comparable.
        """
        decomposed_title = unicodedata.normalize("NFKD", title or "")
        unaccented_title = "".join(char for char in decomposed_title if not unicodedata.combining(char))
        return " ".join(re.sub(r"[^a-z0-9]+", " ", unaccented_title.lower()).split())

    @staticmethod
    async def fetch_account_articles(
        client: httpx.AsyncClient, remote_base: str, headers: dict[str, str]
    ) -> list[dict[str, Any]]:
        """
        Lit tous les articles du compte sur l’API GoupixDex.

        Args:
            client: Client HTTP du worker.
            remote_base: URL de l’API GoupixDex.
            headers: En-têtes portant le JWT de l’utilisateur.

        Returns:
            Les articles, tels que renvoyés par ``GET /articles``.

        Raises:
            httpx.HTTPError: L’API n’a pas répondu.
        """
        response = await client.get(f"{remote_base}/articles", headers=headers)
        response.raise_for_status()
        return [article for article in response.json() if isinstance(article, dict)]

    @classmethod
    def collect_other_articles_listing_ids(
        cls, articles: list[dict[str, Any]], article_id: int, marketplace: MarketplaceWithPcRemoval
    ) -> frozenset[str]:
        """
        Relève les identifiants d’annonce des autres articles du compte sur cette marketplace.

        Args:
            articles: Articles du compte.
            article_id: Article dont on cherche l’annonce.
            marketplace: Marketplace de l’annonce.

        Returns:
            Les identifiants, en texte.
        """
        listing_id_field = cls._LISTING_ID_FIELD[marketplace]
        return frozenset(
            str(article[listing_id_field])
            for article in articles
            if article.get("id") != article_id and article.get(listing_id_field) not in (None, "")
        )

    @classmethod
    def find_other_unsold_copy_without_listing_id(
        cls, articles: list[dict[str, Any]], sold_article: dict[str, Any], marketplace: MarketplaceWithPcRemoval
    ) -> int | None:
        """
        Cherche un autre article en vente sous le même titre, publié sur cette marketplace sans identifiant d’annonce.

        Args:
            articles: Articles du compte.
            sold_article: Article vendu dont l’annonce doit être retirée.
            marketplace: Marketplace de l’annonce.

        Returns:
            L’id de cet autre article, ou None.
        """
        published_field = cls._PUBLISHED_FIELD[marketplace]
        listing_id_field = cls._LISTING_ID_FIELD[marketplace]
        sold_article_title = cls.build_comparable_title(str(sold_article.get("title") or ""))
        for article in articles:
            if article.get("id") == sold_article.get("id") or article.get("is_sold"):
                continue
            if not article.get(published_field) or article.get(listing_id_field) not in (None, ""):
                continue
            if cls.build_comparable_title(str(article.get("title") or "")) == sold_article_title:
                return int(article["id"])
        return None
