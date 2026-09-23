"""
Garde « Ma Collection » alignée sur les articles en vente.

Principe métier : une carte mise en vente est **possédée**, donc présente dans la collection
comme n'importe quelle carte (image, noms, cote, courbe, détection par le catalogue) ; une fois
**vendue**, elle en sort. Un article (fiche de vente) n'a pas d'identité TCGdex : on la résout
depuis son set/numéro et ses noms — l'anglais d'abord, seule langue complète sur TCGdex — avec
repli minimal (photo de l'article) si TCGdex ne connaît pas la carte.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from models.article import Article
from models.collection_card import CollectionCard
from services import collection_card_price_history_service, collection_card_service
from services.cardmarket_local_price_service import resolve_market_price_eur
from services.collection_card_lookup_service import fetch_card_for_collection
from services.species_locale_names_service import fetch_species_names_by_dex
from services.tcgdex_client_service import TcgdexClientService
from services.tcgdex_lookup_service import (
    resolve_tcgdex_card_id_from_ocr,
    search_cards_by_name,
)

#: Langue par défaut d'une carte créée depuis un article (les articles n'en portent pas).
_DEFAULT_LANGUAGE = "fr"
#: Préfixe d'id des cartes créées sans correspondance TCGdex (repli minimal).
MANUAL_CARD_ID_PREFIX = "manual-article-"
#: Jeton ressemblant à un id de set TCGdex dans un titre d'annonce (``s12a``, ``sv8``, ``m1s``, ``ME02``…).
_TCGDEX_SET_TOKEN_RE = re.compile(r"\b((?:swsh|sv|sm|xy|me|s|m)\d{1,2}(?:\.\d)?[a-z]?)\b", re.IGNORECASE)
#: Mots d'un titre d'annonce étrangers au nom de la carte.
_TITLE_NOISE_WORDS = frozenset(
    {
        "pokémon",
        "pokemon",
        "japonais",
        "japanese",
        "jap",
        "english",
        "anglais",
        "français",
        "francais",
        "carte",
        "card",
        "nm",
        "psa",
        "gradé",
        "graded",
    }
)
_NAME_SUFFIX_RE = re.compile(r"\s+(ex|vmax|vstar|v-union|v|gx)\s*$", re.IGNORECASE)
_MEGA_PREFIX_RE = re.compile(r"^m[ée]ga[\s-]+", re.IGNORECASE)
#: Écriture japonaise (kana, kanji) : un nom affiché doit rester en alphabet latin.
_CJK_RE = re.compile(r"[぀-ヿ㐀-鿿]")
#: Plafond d'appels au résolveur TCGdex par article (chacun peut chercher dans trois langues).
_MAX_RESOLUTION_ATTEMPTS = 10


def _to_decimal(value: object) -> Decimal | None:
    """Montant arrondi au centime, ``None`` si absent."""
    if value is None:
        return None
    return Decimal(str(round(float(str(value)), 2)))


def _latin_article_name(article: Article) -> str | None:
    """Nom de la carte saisi dans l'annonce, s'il est en alphabet latin."""
    name = (article.pokemon_name or "").strip()
    return name if name and not _CJK_RE.search(name) else None


def _has_card_identity(article: Article) -> bool:
    """Vrai si l'article décrit une carte (set + numéro) — faux pour un produit scellé ou une saisie incomplète."""
    return bool(article.set_code and article.set_code.strip() and article.card_number and article.card_number.strip())


def is_unresolved(card: CollectionCard) -> bool:
    """Vrai pour une carte créée sans fiche TCGdex (repli minimal : ni cote, ni courbe, ni détection catalogue)."""
    return card.tcgdex_card_id.startswith(MANUAL_CARD_ID_PREFIX)


def linked_collection_card(db: Session, article: Article) -> CollectionCard | None:
    """Carte de collection déjà reliée à cet article, le cas échéant."""
    return (
        db.query(CollectionCard)
        .filter(CollectionCard.user_id == article.user_id, CollectionCard.article_id == article.id)
        .first()
    )


def _title_language(article: Article) -> str:
    """Langue physique d'après le titre de l'annonce (repli quand TCGdex ne résout pas la carte)."""
    title = (article.title or "").lower()
    if "japonais" in title or "japanese" in title or " jap" in title:
        return "ja"
    if "english" in title or "anglais" in title:
        return "en"
    return _DEFAULT_LANGUAGE


def _physical_language(article: Article, tcgdex_card_id: str) -> str:
    """
    Langue physique d'une carte résolue : les sets japonais de TCGdex ont un id en majuscule (``SV3``,
    ``S12a``, ``M1S``) — plus fiable que le titre, qui ne dit pas toujours « japonais ». Pour un set
    international, le titre départage anglais et français.
    """
    if tcgdex_card_id.split("-", 1)[0][:1].isupper():
        return "ja"
    title = (article.title or "").lower()
    return "en" if ("english" in title or "anglais" in title) else _DEFAULT_LANGUAGE


def _title_name_candidates(article: Article) -> list[str]:
    """
    Noms plausibles lus dans le titre (« Plumeline / Oricorio ex PFL … », « Rotom V (LOR 176) … - Motisma V ») :
    mots de tête de chaque segment, jusqu'au code de set, à un numéro ou à un mot parasite.
    """
    stop_tokens = {(article.set_code or "").strip().lower()} - {""}
    candidates: list[str] = []
    for segment in re.split(r"\s/\s|\s-\s|\(", article.title or ""):
        words: list[str] = []
        for raw_word in segment.split():
            word = raw_word.strip(",:;)")
            lowered = word.lower()
            if not word or lowered in stop_tokens or lowered in _TITLE_NOISE_WORDS or any(ch.isdigit() for ch in word):
                break
            words.append(word)
            if len(words) == 4:
                break
        name = " ".join(words)
        if len(name) >= 3 and name not in candidates:
            candidates.append(name)
    return candidates


def _english_names_via_pokedex(french_name: str, client: TcgdexClientService) -> list[str]:
    """
    Traduit un nom de carte français en anglais via le n° de Pokédex (TCGdex FR → ``dexId`` → nom EN),
    en conservant le préfixe Méga et le suffixe (ex, V, VMAX…) : TCGdex n'est complet qu'en anglais.
    """
    suffix_match = _NAME_SUFFIX_RE.search(french_name)
    suffix = suffix_match.group(1) if suffix_match else ""
    is_mega = bool(_MEGA_PREFIX_RE.match(french_name))
    base = _NAME_SUFFIX_RE.sub("", _MEGA_PREFIX_RE.sub("", french_name)).strip()
    if len(base) < 3:
        return []
    for row in search_cards_by_name("fr", base)[:3]:
        try:
            dex_ids = dict(client.get_card("fr", str(row["id"]))).get("dexId")
        except (RuntimeError, ValueError):
            continue
        dex = next((d for d in dex_ids or [] if isinstance(d, int) and d > 0), None)
        if dex is None:
            continue
        _, species_en, _ = fetch_species_names_by_dex(dex)
        if species_en:
            english = f"{'Mega ' if is_mega else ''}{species_en} {suffix}".strip()
            return list(dict.fromkeys([english, species_en]))
    return []


def _try_resolve(set_code: str, number: str, denominator: str | None, name: str | None, language: str) -> str | None:
    """Un appel au résolveur TCGdex (set + numéro + nom), ``None`` si rien ne correspond."""
    try:
        return resolve_tcgdex_card_id_from_ocr(
            ocr_set_code=set_code,
            ocr_card_number=number,
            ocr_card_number_denominator=denominator,
            ocr_pokemon_name_english=name,
            ocr_pokemon_name=name,
            physical_language=language,
        )
    except (RuntimeError, ValueError):
        return None


def resolve_article_tcgdex_card_id(article: Article) -> str | None:
    """
    Id TCGdex de la carte d'un article, ``None`` si TCGdex ne la connaît pas.

    Chemin rapide d'abord (set TCGdex + numéro, langue du titre) ; sinon recherche par nom dans toutes
    les langues avec les noms lus dans le titre, puis leur traduction anglaise via le Pokédex. Un id de
    set TCGdex présent dans le titre (``s12a``) prime sur un code de set saisi approximatif (``VSTAR``).
    """
    if not _has_card_identity(article):
        return None
    number, _, denominator = (article.card_number or "").strip().partition("/")
    denominator_value = denominator.strip() or None
    set_code = (article.set_code or "").strip()
    title_set_codes = [t for t in _TCGDEX_SET_TOKEN_RE.findall(article.title or "") if t.lower() != set_code.lower()]
    set_codes = list(dict.fromkeys([*title_set_codes, set_code]))

    resolved = _try_resolve(set_codes[0], number, denominator_value, article.pokemon_name, _title_language(article))
    if resolved:
        return resolved
    if denominator_value:
        # Certains sets japonais ont un total TCGdex (secrètes incluses) différent du dénominateur imprimé
        # (SV11B : 174 contre 086) : même set + numéro sans ce contrôle, en cherchant d'abord côté japonais.
        resolved = _try_resolve(set_codes[0], number, None, article.pokemon_name, "ja")
        if resolved:
            return resolved

    attempts = 2
    french_names = list(dict.fromkeys(n for n in [*_title_name_candidates(article), article.pokemon_name] if n))
    client = TcgdexClientService()
    for french_name in french_names:
        for name in [french_name, *_english_names_via_pokedex(french_name, client)]:
            for code in set_codes:
                if attempts >= _MAX_RESOLUTION_ATTEMPTS:
                    return None
                attempts += 1
                # Langue « fr » : le résolveur cherche alors le nom en anglais, français et japonais.
                resolved = _try_resolve(code, number, denominator_value, name, _DEFAULT_LANGUAGE)
                if resolved:
                    return resolved
    return None


def _collection_fields_for_article(article: Article) -> dict[str, Any]:
    """
    Colonnes « identité + cote » de la carte de collection d'un article : fiche TCGdex complète si la
    carte est résolue, sinon repli minimal sur la photo et le set/numéro de l'article.
    """
    article_photo = article.images[0].image_url if article.images else None
    tcgdex_card_id = resolve_article_tcgdex_card_id(article)
    if tcgdex_card_id is not None:
        language = _physical_language(article, tcgdex_card_id)
        try:
            payload = fetch_card_for_collection(tcgdex_card_id=tcgdex_card_id, physical_language=language)
        except (RuntimeError, ValueError):
            payload = None
        if payload is not None:
            display_name = str(payload["display_name"])
            card_name_fr = payload.get("card_name_fr")
            article_name = _latin_article_name(article)
            if article_name and _CJK_RE.search(display_name):
                # Carte japonaise sans nom latin sur TCGdex (dresseurs, objets) : le nom de l'annonce prend le relais.
                display_name = article_name
                card_name_fr = card_name_fr or article_name
            return {
                "tcgdex_card_id": str(payload["tcgdex_card_id"]),
                "tcgdex_set_id": str(payload["tcgdex_set_id"]),
                "set_code": payload.get("set_code"),
                "set_name": payload.get("set_name"),
                "card_number": str(payload["card_number"]),
                "card_name_en": payload.get("card_name_en"),
                "card_name_fr": card_name_fr,
                "card_name_ja": payload.get("card_name_ja"),
                "display_name": display_name,
                "rarity": payload.get("rarity"),
                "language": str(payload.get("language") or language),
                "image_url": payload.get("image_url") or article_photo,
                "cardmarket_id_product": payload.get("cardmarket_id_product"),
                "market_price_eur": _to_decimal(payload.get("market_price_eur")),
            }

    market_price = _to_decimal(article.market_cardmarket_eur)
    if market_price is None and article.cardmarket_id_product is not None:
        market_price = _to_decimal(resolve_market_price_eur(article.cardmarket_id_product, None))
    return {
        "tcgdex_card_id": f"{MANUAL_CARD_ID_PREFIX}{article.id}",
        "tcgdex_set_id": article.set_code or "manual",
        "set_code": article.set_code,
        "set_name": None,
        "card_number": article.card_number or "?",
        "card_name_en": None,
        "card_name_fr": article.pokemon_name or None,
        "card_name_ja": None,
        "display_name": (article.pokemon_name or article.title or "Carte").strip(),
        "rarity": None,
        "language": _title_language(article),
        "image_url": article_photo,
        "cardmarket_id_product": article.cardmarket_id_product,
        "market_price_eur": market_price,
    }


def _apply_market_fields(card: CollectionCard, fields: dict[str, Any]) -> None:
    """Pose idProduct + cote comme un ajout classique (horodatage compris), sans toucher une cote saisie à la main."""
    if card.market_price_overridden:
        return
    market = fields["market_price_eur"]
    collection_card_service.apply_market_price(
        card,
        cardmarket_id_product=fields["cardmarket_id_product"],
        market_price_eur=float(market) if market is not None else None,
    )


def _record_price_snapshot(db: Session, card: CollectionCard) -> None:
    """Premier point de la courbe de prix, comme à l'ajout d'une carte depuis le catalogue."""
    if card.market_price_eur is None:
        return
    collection_card_price_history_service.record_snapshot(db, card.id, float(card.market_price_eur))
    db.commit()


def ensure_collection_card_for_article(db: Session, article: Article) -> CollectionCard | None:
    """
    Garantit qu'un article en vente possède sa carte de collection reliée (idempotent).

    Ne fait rien pour un article vendu (la carte a alors quitté la collection), déjà relié, ou sans
    set + numéro (produit scellé, saisie incomplète). Retourne la carte reliée (existante ou créée),
    ou ``None`` si rien n'est fait.
    """
    if article.is_sold or not _has_card_identity(article):
        return None
    existing = linked_collection_card(db, article)
    if existing is not None:
        return existing
    fields = _collection_fields_for_article(article)
    identity = {k: v for k, v in fields.items() if k not in {"cardmarket_id_product", "market_price_eur"}}
    card = CollectionCard(
        user_id=article.user_id,
        quantity=1,
        purchase_price_eur=_to_decimal(article.purchase_price),
        article_id=article.id,
        **identity,
    )
    _apply_market_fields(card, fields)
    db.add(card)
    db.commit()
    db.refresh(card)
    _record_price_snapshot(db, card)
    return card


def needs_refresh(card: CollectionCard, article: Article) -> bool:
    """
    Carte reliée à re-résoudre : sans fiche TCGdex, langue incohérente avec son set TCGdex, ou nom
    affiché en japonais alors que l'annonce en donne un en alphabet latin.
    """
    if is_unresolved(card):
        return True
    if card.language != _physical_language(article, card.tcgdex_card_id):
        return True
    return bool(_latin_article_name(article) and _CJK_RE.search(card.display_name or ""))


def refresh_collection_card_from_article(db: Session, card: CollectionCard, article: Article) -> bool:
    """
    Ré-résout une carte déjà reliée (id TCGdex, langue, image, noms, cote) **sans la recréer** : son id
    (placements en classeur), sa quantité, ses notes et son prix d'achat sont conservés. Une carte déjà
    résolue n'est jamais dégradée en repli minimal (TCGdex injoignable) : seule sa langue est corrigée.

    Retourne ``True`` si l'identité, la langue ou le nom affiché de la carte a changé.
    """
    before = (card.tcgdex_card_id, card.language, card.display_name)
    fields = _collection_fields_for_article(article)
    if str(fields["tcgdex_card_id"]).startswith(MANUAL_CARD_ID_PREFIX) and not is_unresolved(card):
        card.language = _physical_language(article, card.tcgdex_card_id)
    else:
        for key, value in fields.items():
            if key not in {"cardmarket_id_product", "market_price_eur"}:
                setattr(card, key, value)
        _apply_market_fields(card, fields)
    db.commit()
    db.refresh(card)
    _record_price_snapshot(db, card)
    return (card.tcgdex_card_id, card.language, card.display_name) != before


def attach_collection_card(db: Session, *, user_id: int, collection_card_id: int, article: Article) -> bool:
    """
    Relie une carte de collection existante à cet article (vente depuis la collection) ; ``True`` si reliée.
    Une carte sans prix d'achat reprend celui de l'article.
    """
    card = (
        db.query(CollectionCard)
        .filter(CollectionCard.id == collection_card_id, CollectionCard.user_id == user_id)
        .first()
    )
    if card is None:
        return False
    card.article_id = article.id
    if card.purchase_price_eur is None:
        card.purchase_price_eur = _to_decimal(article.purchase_price)
    db.commit()
    return True


def remove_collection_card_for_sold_article(db: Session, article: Article) -> bool:
    """
    Carte vendue → elle quitte la collection : la ligne reliée est supprimée, ou, si elle compte
    plusieurs exemplaires, décrémentée d'un et déliée (les autres restent possédés).
    ``True`` si la collection a changé.
    """
    card = linked_collection_card(db, article)
    if card is None:
        return False
    if int(card.quantity) > 1:
        card.quantity = int(card.quantity) - 1
        card.article_id = None
    else:
        db.delete(card)
    db.commit()
    return True


def sync_purchase_price_to_collection(db: Session, article: Article) -> None:
    """Répercute le prix d'achat de l'article sur sa carte de collection reliée (même carte physique)."""
    card = linked_collection_card(db, article)
    if card is None:
        return
    card.purchase_price_eur = _to_decimal(article.purchase_price)
    db.commit()


def sync_purchase_price_to_article(db: Session, card: CollectionCard) -> None:
    """Répercute le prix d'achat d'une carte de collection sur l'article en vente qui lui est relié."""
    if card.article_id is None or card.purchase_price_eur is None:
        return
    article = db.query(Article).filter(Article.id == card.article_id, Article.user_id == card.user_id).first()
    if article is None:
        return
    article.purchase_price = card.purchase_price_eur
    db.commit()
