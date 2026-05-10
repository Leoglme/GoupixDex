#!/usr/bin/env python3
"""
Outil d'agregation des vendeurs Cardmarket pour des cartes Pokemon precises.

Fonctionnalites principales :
    - Liste d'URLs de pages produit Cardmarket (singles) ; filtres Near Mint et langue en query.
    - Analyse de la liste des vendeurs disponibles pour chaque carte.
    - Agregation des vendeurs pour identifier ceux qui couvrent le plus de cartes de la liste.

Le script repose sur `nodriver` (Chrome, visible par defaut comme GoupixDex/VintedService) pour charger
les pages et sur `BeautifulSoup` pour analyser le HTML. Le mode ``--headless`` est optionnel car souvent
plus bloque par Cloudflare (erreur 1015, etc.).
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import nodriver as uc
from bs4 import BeautifulSoup
from bs4.element import Tag
from nodriver.cdp import runtime as cdp_runtime

BASE_URL = "https://www.cardmarket.com"
GAME_SEGMENT = "/fr/Pokemon"
DEFAULT_LANGUAGE_ID = 7  # Japonais
DEFAULT_MIN_CONDITION_ID = 2  # Near Mint
REQUEST_TIMEOUT = 45  # secondes (pages lourdes + challenge eventuel)
REQUEST_SLEEP = 2.5  # delai entre cartes (evite le burst type Cloudflare 1015)
DEFAULT_MAX_RETRIES = 4
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_MAX_BACKOFF = 90.0
DEFAULT_JITTER_RANGE = (0.5, 2.5)
EXTRA_RATE_LIMIT_ATTEMPTS = 3
# Pause apres blocage Cloudflare / 429 avant nouveau navigateur (cf. GoupixDex : laisser retomber la limite)
RATE_LIMIT_COOLDOWN = 45.0
# Meme strategie que GoupixDex/api/services/vinted_service.py : navigateur visible = moins de signaux "bot"
DEFAULT_HEADLESS = False

# Flags Chrome alignes sur GoupixDex (VintedService) pour reduire les signaux d'automatisation
_DEFAULT_BROWSER_ARGS: List[str] = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--start-maximized",
]

# Pages d'erreur Cloudflare (souvent HTTP 200 avec ce HTML — Error 1015 = rate limit cote CF)
_CLOUDFLARE_BLOCK_MARKERS: Tuple[str, ...] = (
    "error 1015",
    "you are being rate limited",
    "cf-error-details",
    "checking your browser before accessing",
    "just a moment...",
    "cf-browser-verification",
)

HOME_POKEMON_URL = f"{BASE_URL}{GAME_SEGMENT}"


@dataclass(frozen=True)
class FetchedPage:
    """Reponse HTTP minimale (equivalent pratique a requests.Response pour le parsing)."""

    url: str
    text: str
    status_code: int


ITEM_PAGE_URLS: List[str] = [
    "https://www.cardmarket.com/fr/Pokemon/Products/Singles/MEGA-Dream-ex/Ethans-Magcargo-V2-m2a197?language=7",
    "https://www.cardmarket.com/fr/Pokemon/Products/Singles/Pokemon-Card-151/Tangela-V2-sv2a178?language=7",
    "https://www.cardmarket.com/fr/Pokemon/Products/Singles/Pokemon-Card-151/Wigglytuff-ex-V2-sv2a189?language=7",
    "https://www.cardmarket.com/fr/Pokemon/Products/Singles/Pokemon-Card-151/Nidoking-V2-sv2a174?language=7",
    "https://www.cardmarket.com/fr/Pokemon/Products/Singles/VSTAR-Universe/Rayquaza-VMAX-s12a108?language=7",
    "https://www.cardmarket.com/fr/Pokemon/Products/Singles/Ancient-Roar/Magby-V2-sv4K068?language=7",
    "https://www.cardmarket.com/fr/Pokemon/Products/Singles/Inferno-X/Flygon-V2-m2088?language=7",
    "https://www.cardmarket.com/fr/Pokemon/Products/Singles/Inferno-X/Zacian-V2-m2087?language=7",
    "https://www.cardmarket.com/fr/Pokemon/Products/Singles/Inferno-X/Toxtricity-V2-m2089?language=7",
    "https://www.cardmarket.com/fr/Pokemon/Products/Singles/Inferno-X/Wigglytuff-V2-m2091?language=7",
    "https://www.cardmarket.com/fr/Pokemon/Products/Singles/Inferno-X/Ambipom-V2-m2092?language=7",
    
]


def _label_from_item_url(url: str) -> str:
    """Libelle court pour les rapports (dernier segment du chemin, ex. Sprigatito-V2-sv4a201)."""
    path = urlparse(url).path.rstrip("/")
    if not path:
        return url
    return path.split("/")[-1]


class CardMarketError(RuntimeError):
    """Erreur personnalisee pour signaler un probleme lors de la recuperation des donnees."""


class RateLimitError(CardMarketError):
    """Erreur specifique pour signaler un blocage 429 persistant."""


@dataclass(frozen=True)
class Offer:
    seller_name: str
    price_eur: float
    quantity: int
    seller_location: Optional[str] = None
    shipping_time_days: Optional[int] = None
    comments: Optional[str] = None
    article_id: Optional[str] = None


@dataclass
class CardResult:
    code: str
    product_name: Optional[str]
    product_url: Optional[str]
    offers: List[Offer] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RetryConfig:
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR
    max_backoff: float = DEFAULT_MAX_BACKOFF
    jitter_min: float = DEFAULT_JITTER_RANGE[0]
    jitter_max: float = DEFAULT_JITTER_RANGE[1]
    base_sleep: float = REQUEST_SLEEP


def _merge_url_query(url: str, params: Optional[Dict[str, Any]]) -> str:
    """Fusionne des parametres de requete dans une URL (conservation des query existantes)."""
    if not params:
        return url
    parsed = urlparse(url)
    merged = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        merged[key] = str(value)
    new_query = urlencode(merged)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )


def _html_looks_like_cloudflare_block(html: str) -> bool:
    """
    Detecte les interstitiels Cloudflare (souvent HTTP 200), dont l'erreur 1015 (rate limit).
    """
    if not html or len(html) < 200:
        return False
    lower = html.lower()
    return any(marker in lower for marker in _CLOUDFLARE_BLOCK_MARKERS)


async def _navigation_http_status(tab: uc.Tab) -> int:
    """Lit le code HTTP du document principal via l'API Performance (Chrome)."""
    expr = (
        "(() => { const n = performance.getEntriesByType('navigation')[0]; "
        "if (!n) return 200; const s = n.responseStatus; return (s && s > 0) ? s : 200; })()"
    )
    try:
        raw = await tab.evaluate(expr, return_by_value=True)
    except Exception:
        return 200
    if isinstance(raw, cdp_runtime.ExceptionDetails):
        return 200
    if isinstance(raw, bool):
        return 200
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 200


async def create_browser(
    *,
    proxy: Optional[str] = None,
    headless: bool = DEFAULT_HEADLESS,
    user_data_dir: Optional[pathlib.Path] = None,
) -> uc.Browser:
    """
    Demarre Chrome via nodriver avec les memes garde-fous que GoupixDex (VintedService) :
    flags anti-``AutomationControlled``, sandbox desactive, fenetre maximisee.
    """
    browser_args = list(_DEFAULT_BROWSER_ARGS)
    if proxy:
        browser_args.append(f"--proxy-server={proxy}")
    kwargs: Dict[str, Any] = {
        "headless": headless,
        "browser_args": browser_args,
        "sandbox": False,
    }
    if user_data_dir is not None:
        kwargs["user_data_dir"] = str(user_data_dir)
    return await uc.start(**kwargs)


async def warm_up_cardmarket_session(browser: uc.Browser, *, debug: bool = False) -> None:
    """
    Chauffe la session : about:blank puis hub Pokemon FR, comme l'approche GoupixDex (delais + navigation reelle).
    """
    tab = await browser.get("about:blank")
    await tab
    await asyncio.sleep(0.5 + random.uniform(0, 0.5))
    tab = await browser.get(HOME_POKEMON_URL)
    await tab
    await asyncio.sleep(random.uniform(2.5, 5.5))
    html = await tab.get_content()
    if _html_looks_like_cloudflare_block(html):
        raise RateLimitError(
            "Cloudflare bloque deja sur la page Pokemon (ex. Error 1015). "
            "Attendez plusieurs minutes, essayez une autre connexion (4G, autre IP) ou un VPN residentiel."
        )
    if debug:
        print("[DEBUG] Session chauffee (about:blank -> Pokemon FR).")


def clean_price(raw_price: str) -> float:
    """Convertit une chaine de type '3,80 EUR' en float."""
    normalized = (
        raw_price.replace("\u202f", "")
        .replace("\xa0", "")
        .replace("\u20ac", "")
        .replace(" ", "")
        .strip()
    )
    normalized = normalized.replace(",", ".")
    try:
        return float(normalized)
    except ValueError as exc:  # pragma: no cover - securite supplementaire
        raise CardMarketError(f"Impossible de convertir le prix '{raw_price}'.") from exc


def parse_int(value: str) -> Optional[int]:
    """Tente de convertir une chaine en int, renvoie None en cas d'echec."""
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return None


def extract_product_name(soup: BeautifulSoup) -> Optional[str]:
    """
    Recupere le nom affiche sur la page produit, s'il existe.
    Habituellement present dans la balise <h1 class="page-title">.
    """
    header = soup.select_one("h1.page-title, h1.product-title")
    if header:
        return header.get_text(strip=True)
    return None


def extract_offers_from_product_page(soup: BeautifulSoup) -> List[Offer]:
    """Parcourt la table des vendeurs et en extrait les informations cles."""
    offers: List[Offer] = []
    for row in soup.select("div.article-row"):
        seller_anchor = row.select_one(".seller-name a[href*='/Users/']")
        if not seller_anchor:
            continue
        seller_name = seller_anchor.get_text(strip=True)

        price_span = row.select_one(".price-container span.color-primary")
        if not price_span:
            continue
        price_eur = clean_price(price_span.get_text())

        quantity_span = row.select_one(".amount-container .item-count")
        quantity = parse_int(quantity_span.get_text()) if quantity_span else None
        if quantity is None:
            quantity = 1

        location_span = row.select_one(".seller-name span[aria-label]")
        seller_location = (
            location_span.get("aria-label").replace("Localisation de l'article: ", "").strip()
            if location_span and location_span.get("aria-label")
            else None
        )

        shipping_span = row.select_one(".seller-info .shippingTime-info")
        shipping_time_days = parse_int(shipping_span.get_text()) if shipping_span else None

        comment_span = row.select_one(".product-comments span.text-truncate")
        comments = comment_span.get_text(strip=True) if comment_span else None

        form_hidden = row.select_one("form input[name='idArticle']")
        article_id = form_hidden.get("value") if isinstance(form_hidden, Tag) else None

        offers.append(
            Offer(
                seller_name=seller_name,
                price_eur=price_eur,
                quantity=quantity,
                seller_location=seller_location,
                shipping_time_days=shipping_time_days,
                comments=comments,
                article_id=article_id,
            )
        )
    return offers


def _retry_delay(config: RetryConfig, attempt: int, retry_after_header: Optional[str]) -> float:
    """
    Calcule le delai de retry a appliquer en fonction de l'en-tete Retry-After ou
    d'un backoff exponentiel.
    """
    if retry_after_header:
        try:
            retry_after = float(retry_after_header)
            if retry_after > 0:
                return min(config.max_backoff, retry_after)
        except (TypeError, ValueError):
            pass
    base = config.base_sleep if config.base_sleep > 0 else 0.5
    backoff = base * (config.backoff_factor ** attempt)
    jitter = random.uniform(config.jitter_min, config.jitter_max)
    return min(config.max_backoff, backoff + jitter)


async def _fetch_page_once(
    browser: uc.Browser,
    full_url: str,
    *,
    timeout: float = REQUEST_TIMEOUT,
) -> FetchedPage:
    async def _load() -> FetchedPage:
        tab = await browser.get(full_url)
        await tab
        await asyncio.sleep(random.uniform(0.15, 0.45))
        status = await _navigation_http_status(tab)
        html = await tab.get_content()
        final_url = tab.target.url or full_url
        if _html_looks_like_cloudflare_block(html):
            status = 429
        return FetchedPage(url=final_url, text=html, status_code=status)

    return await asyncio.wait_for(_load(), timeout=timeout)


async def get_with_retry(
    browser: uc.Browser,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = REQUEST_TIMEOUT,
    config: Optional[RetryConfig] = None,
    debug: bool = False,
    description: Optional[str] = None,
) -> FetchedPage:
    """
    Charge une URL via nodriver avec retries sur 429 / erreurs reseau.
    """
    if config is None:
        config = RetryConfig()
    full_url = _merge_url_query(url, params)
    last_exception: Optional[Exception] = None
    attempt = 0
    total_attempts = config.max_retries + 1
    saw_rate_limit = False
    while attempt < total_attempts:
        try:
            page = await _fetch_page_once(browser, full_url, timeout=timeout)
        except asyncio.TimeoutError as exc:
            last_exception = exc
            if debug:
                print(f"[DEBUG] Timeout apres {timeout}s sur {description or full_url}.")
        except Exception as exc:
            last_exception = exc
            if debug:
                print(f"[DEBUG] Tentative {attempt + 1}/{total_attempts} echouee ({exc}).")
        else:
            if page.status_code == 429:
                saw_rate_limit = True
                delay = _retry_delay(config, attempt, None)
                if debug:
                    reason = description or full_url
                    print(
                        f"[DEBUG] 429 sur {reason}. Tentative {attempt + 1}/{total_attempts}. "
                        f"Pause de {delay:.2f}s avant retry."
                    )
                await asyncio.sleep(delay)
                attempt += 1
                continue
            if page.status_code >= 400:
                last_exception = CardMarketError(f"HTTP {page.status_code}")
                if debug:
                    reason = description or full_url
                    print(
                        f"[DEBUG] Tentative {attempt + 1}/{total_attempts} "
                        f"echouee ({reason}) avec statut {page.status_code}."
                    )
            else:
                return page

        delay = _retry_delay(config, attempt, None)
        await asyncio.sleep(delay)
        attempt += 1

    message = f"Echec de la requete {description or full_url} apres {total_attempts} tentatives."
    if saw_rate_limit:
        raise RateLimitError(message) from last_exception
    raise CardMarketError(message) from last_exception




def _dump_html(content: str, path: pathlib.Path, debug: bool) -> None:
    try:
        path.write_text(content, encoding="utf-8")
        if debug:
            print(f"[DEBUG] HTML sauvegarde dans {path}")
    except OSError as exc:
        if debug:
            print(f"[DEBUG] Echec ecriture {path}: {exc}")


async def fetch_product_page(
    browser: uc.Browser,
    product_url: str,
    *,
    code: str,
    debug: bool = False,
    dump_dir: Optional[pathlib.Path] = None,
    retry_config: RetryConfig,
    language: Optional[int] = None,
) -> CardResult:
    """
    Charge une page produit (URL directe) et extrait les offres.
    Fusionne minCondition, langue et reverse holo dans la query.
    """
    result = CardResult(code=code, product_name=None, product_url=None)

    params: Dict[str, Any] = {"minCondition": DEFAULT_MIN_CONDITION_ID}
    language_to_use = language if language is not None else DEFAULT_LANGUAGE_ID
    params["language"] = language_to_use
    if code.endswith("R"):
        params["isReverseHolo"] = "Y"

    product_response = await get_with_retry(
        browser,
        product_url,
        params=params,
        timeout=REQUEST_TIMEOUT,
        debug=debug,
        description=f"page produit '{code}'",
        config=retry_config,
    )
    if product_response.status_code >= 400:
        result.warnings.append(
            f"Impossible de charger la page produit (statut {product_response.status_code})."
        )
        return result
    if debug:
        print(
            "[DEBUG] Page produit (filtres) "
            f"{product_response.url} (status {product_response.status_code})"
        )
    if dump_dir:
        _dump_html(product_response.text, dump_dir / f"{code.replace(' ', '_')}_product.html", debug)

    product_soup = BeautifulSoup(product_response.text, "html.parser")
    result.product_name = extract_product_name(product_soup)
    result.product_url = product_response.url
    result.offers = extract_offers_from_product_page(product_soup)
    if not result.offers:
        result.warnings.append("Aucune offre trouvee avec les filtres demandes.")
    return result


def aggregate_sellers(card_results: Iterable[CardResult]) -> Dict[str, Dict[str, Offer]]:
    """
    Construit un mapping {vendeur -> {code_carte -> offre}}.
    Si un vendeur est trouve plusieurs fois pour la meme carte, on garde l'offre la moins chere.
    """
    seller_map: Dict[str, Dict[str, Offer]] = defaultdict(dict)
    for card in card_results:
        for offer in card.offers:
            existing = seller_map[offer.seller_name].get(card.code)
            if existing is None or offer.price_eur < existing.price_eur:
                seller_map[offer.seller_name][card.code] = offer
    return seller_map


def summarize_sellers(
    sellers: Dict[str, Dict[str, Offer]], target_codes: List[str]
) -> List[Tuple[str, Dict[str, Offer], float, int]]:
    """
    Retourne une liste triee des vendeurs :
        - par nombre de cartes couvertes (descendant),
        - puis par prix total (ascendant).
    """
    summary: List[Tuple[str, Dict[str, Offer], float, int]] = []
    for seller, offers in sellers.items():
        covered = len(offers)
        total_price = sum(o.price_eur for o in offers.values())
        summary.append((seller, offers, total_price, covered))
    summary.sort(key=lambda item: (-item[3], item[2], item[0].lower()))
    return summary


def summarize_sellers_by_value(
    sellers: Dict[str, Dict[str, Offer]], cheapest_by_card: Dict[str, Optional[float]]
) -> List[Tuple[str, Dict[str, Offer], float, float, int]]:
    """
    Cree une liste triee des vendeurs en fonction du surcout relatif total par rapport
    au meilleur prix pour chaque carte. Les vendeurs sont tries par
    - surcout relatif (ascendant),
    - nombre de cartes (descendant),
    - nom (ascendant).
    """
    summary: List[Tuple[str, Dict[str, Offer], float, float, int]] = []
    for seller, offers in sellers.items():
        covered = len(offers)
        total_price = sum(o.price_eur for o in offers.values())
        total_cheapest = 0.0
        for code, offer in offers.items():
            cheapest = cheapest_by_card.get(code)
            if cheapest is not None and cheapest > 0:
                total_cheapest += cheapest
        if total_cheapest > 0:
            overpay_ratio = max(0.0, (total_price - total_cheapest) / total_cheapest)
        else:
            overpay_ratio = float("inf") if total_price > 0 else 0.0
        summary.append((seller, offers, total_price, overpay_ratio, covered))
    summary.sort(key=lambda item: (item[3], -item[4], item[0].lower()))
    return summary


def _print_seller_table(
    header: str,
    seller_summary: List[Tuple[str, Dict[str, Offer], float, int]],
    cheapest_by_card: Dict[str, Optional[float]],
    *,
    limit: Optional[int] = None,
    min_cards: int = 1,
) -> None:
    print("\n" + "=" * 80)
    print(header)
    filtered = [entry for entry in seller_summary if entry[3] >= min_cards]
    iterable = filtered if limit is None else filtered[:limit]
    for rank, (seller, offers, total_price, covered) in enumerate(iterable, start=1):
        cheapest_total = 0.0
        for code, offer in offers.items():
            cheapest = cheapest_by_card.get(code)
            if cheapest is not None and cheapest > 0:
                cheapest_total += cheapest
            else:
                cheapest_total += offer.price_eur
        overpay_value = max(0.0, total_price - cheapest_total)
        if cheapest_total > 0:
            overpay_pct = (overpay_value / cheapest_total) * 100.0
        else:
            overpay_pct = 0.0
        if overpay_value > 1e-9:
            summary_suffix = f" (+{overpay_pct:.2f}% | +{overpay_value:.2f} EUR vs min)"
        else:
            summary_suffix = " (aligné sur les meilleurs prix)"
        print(f"{rank}. {seller} - {covered} cartes - Total {total_price:.2f} EUR{summary_suffix}")
        for code, offer in sorted(offers.items(), key=lambda item: item[0]):
            comment = f" - {offer.comments}" if offer.comments else ""
            location = f" - {offer.seller_location}" if offer.seller_location else ""
            cheapest = cheapest_by_card.get(code)
            if cheapest is not None:
                diff = offer.price_eur - cheapest
                if abs(diff) < 1e-9:
                    delta = " (meilleur prix)"
                else:
                    if cheapest > 0:
                        diff_pct = (diff / cheapest) * 100.0
                        delta = f" (+{diff_pct:.2f}% | +{diff:.2f} EUR vs min)"
                    else:
                        delta = f" (+{diff:.2f} EUR vs min)"
            else:
                delta = ""
            print(
                f"    - {code} : {offer.price_eur:.2f} EUR (x{offer.quantity}){delta}{location}{comment}"
            )
        print()


def display_report(
    card_results: List[CardResult],
    seller_summary: List[Tuple[str, Dict[str, Offer], float, int]],
    seller_value_summary: List[Tuple[str, Dict[str, Offer], float, float, int]],
    top: int,
    *,
    min_cards_for_value: int,
) -> None:
    """Affiche un rapport lisible en console."""
    cheapest_by_card: Dict[str, Optional[float]] = {}
    for card in card_results:
        if card.offers:
            cheapest_by_card[card.code] = min(offer.price_eur for offer in card.offers)
        else:
            cheapest_by_card[card.code] = None

    print("=" * 80)
    print("RECAPITULATIF DES CARTES")
    for card in card_results:
        status = "OK" if card.offers else "WARN"
        name = card.product_name or "Nom inconnu"
        print(f"- {status} {card.code} - {name}")
        if card.product_url:
            print(f"    URL : {card.product_url}")
        if card.warnings:
            for warn in card.warnings:
                print(f"    AVERTISSEMENT : {warn}")
        elif card.offers:
            best_offer = min(card.offers, key=lambda offer: offer.price_eur)
            print(
                f"    Meilleur prix: {best_offer.price_eur:.2f} EUR par {best_offer.seller_name} "
                f"(x{best_offer.quantity})"
            )

    limit = min(top, 20) if top and top > 0 else None
    if top and top > 0:
        _print_seller_table(
            f"TOP {min(20, len(seller_summary))} VENDEURS LES PLUS RENTABLES (Nombre de cartes couvertes puis prix total)",
            seller_summary,
            cheapest_by_card,
            limit=limit,
            min_cards=2,
        )
    else:
        _print_seller_table(
            "CLASSEMENT COMPLET DES VENDEURS (Nombre de cartes couvertes puis prix total)",
            seller_summary,
            cheapest_by_card,
            min_cards=2,
        )

    filtered_value_summary = [
        (seller, offers, total_price, total_overpay_ratio, covered)
        for seller, offers, total_price, total_overpay_ratio, covered in seller_value_summary
        if covered >= min_cards_for_value
    ]
    value_limit = 20 if top and top > 0 else None
    header_value = (
        f"TOP {min(20, len(filtered_value_summary))} VENDEURS AU MEILLEUR PRIX GLOBAL (Surcout total vs meilleurs prix)"
        if top and top > 0
        else "CLASSEMENT COMPLET DES VENDEURS AU MEILLEUR PRIX GLOBAL (Surcout total vs meilleurs prix)"
    )
    print("\n" + "=" * 80)
    print(header_value)
    iterable_value = (
        filtered_value_summary if value_limit is None else filtered_value_summary[:value_limit]
    )
    for rank, (seller, offers, total_price, total_overpay_ratio, covered) in enumerate(
        iterable_value, start=1
    ):
        print(
            f"{rank}. {seller} - {covered} cartes - Total {total_price:.2f} EUR "
            f"(surcout total {total_overpay_ratio * 100:.2f} %)"
        )
        for code, offer in sorted(offers.items(), key=lambda item: item[0]):
            comment = f" - {offer.comments}" if offer.comments else ""
            location = f" - {offer.seller_location}" if offer.seller_location else ""
            cheapest = cheapest_by_card.get(code)
            if cheapest is not None:
                diff = offer.price_eur - cheapest
                if abs(diff) < 1e-9:
                    delta = " (meilleur prix)"
                else:
                    if cheapest > 0:
                        diff_pct = (diff / cheapest) * 100.0
                        delta = f" (+{diff_pct:.2f}% | +{diff:.2f} EUR vs min)"
                    else:
                        delta = f" (+{diff:.2f} EUR vs min)"
            else:
                delta = ""
            print(
                f"    - {code} : {offer.price_eur:.2f} EUR (x{offer.quantity}){delta}{location}{comment}"
            )
        print()

    missing_sellers = [
        card.code for card in card_results if not card.offers or all(o.quantity <= 0 for o in card.offers)
    ]
    if missing_sellers:
        print("Cartes sans vendeurs correspondant aux filtres :", ", ".join(missing_sellers))


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Identifie les vendeurs Cardmarket couvrant le plus de cartes donnees."
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Nombre de vendeurs a afficher dans le classement final (0 pour tous, defaut: 20).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=REQUEST_SLEEP,
        help="Delai (en secondes) entre deux requetes pour eviter de surcharger Cardmarket.",
    )
    parser.add_argument(
        "--no-debug",
        action="store_false",
        dest="debug",
        help="Desactive les logs detailles.",
    )
    parser.set_defaults(debug=True)
    parser.add_argument(
        "--dump-html",
        help="Dossier dans lequel sauvegarder les pages HTML recuperees (cree si inexistant).",
    )
    parser.add_argument(
        "--proxy",
        help="URL d'un proxy HTTP(S) pour Chrome (ex: http://user:pass@host:port), via --proxy-server.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Chrome sans fenetre (souvent plus bloque par Cloudflare ; par defaut : fenetre visible).",
    )
    parser.add_argument(
        "--user-data-dir",
        type=str,
        default=None,
        help="Dossier de profil Chrome persistant (cookies / session), peut aider sur la duree.",
    )
    parser.add_argument(
        "--retry-max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Nombre de retries supplementaires autorises sur une requete avant abandon (defaut: {DEFAULT_MAX_RETRIES}).",
    )
    parser.add_argument(
        "--retry-backoff-factor",
        type=float,
        default=DEFAULT_BACKOFF_FACTOR,
        help=f"Facteur multiplicatif du backoff exponentiel (defaut: {DEFAULT_BACKOFF_FACTOR}).",
    )
    parser.add_argument(
        "--retry-max-backoff",
        type=float,
        default=DEFAULT_MAX_BACKOFF,
        help=f"Delai maximal entre deux tentatives de retry (defaut: {DEFAULT_MAX_BACKOFF}s).",
    )
    parser.add_argument(
        "--retry-base-sleep",
        type=float,
        help="Delai de base utilise pour calculer le backoff. Par defaut egale a --sleep.",
    )
    parser.add_argument(
        "--retry-jitter",
        type=float,
        nargs=2,
        metavar=("MIN", "MAX"),
        help=f"Borne min/max du jitter ajoute au backoff (defaut: {DEFAULT_JITTER_RANGE[0]} {DEFAULT_JITTER_RANGE[1]}).",
    )
    parser.add_argument(
        "--language",
        type=int,
        default=None,
        help="ID de la langue pour filtrer les offres (ex: 2 pour anglais, 7 pour japonais). Par defaut, aucun filtre de langue n'est applique.",
    )
    return parser.parse_args(argv)


async def _run_async(args: argparse.Namespace) -> int:
    item_urls = list(ITEM_PAGE_URLS)
    codes = [_label_from_item_url(u) for u in item_urls]

    dump_path: Optional[pathlib.Path] = None
    if args.dump_html:
        dump_path = pathlib.Path(args.dump_html).expanduser().resolve()
        dump_path.mkdir(parents=True, exist_ok=True)
        if args.debug:
            print(f"[DEBUG] Sauvegarde des HTML activee dans {dump_path}")

    retry_jitter_min, retry_jitter_max = DEFAULT_JITTER_RANGE
    if args.retry_jitter:
        jitter_min, jitter_max = args.retry_jitter
        if jitter_min > jitter_max:
            jitter_min, jitter_max = jitter_max, jitter_min
        retry_jitter_min, retry_jitter_max = jitter_min, jitter_max

    default_sleep_between_cards = args.sleep if args.sleep is not None else REQUEST_SLEEP
    retry_base_sleep = (
        args.retry_base_sleep if args.retry_base_sleep is not None else default_sleep_between_cards
    )
    retry_config = RetryConfig(
        max_retries=max(0, args.retry_max_retries),
        backoff_factor=max(1.0, args.retry_backoff_factor),
        max_backoff=max(0.5, args.retry_max_backoff),
        jitter_min=max(0.0, retry_jitter_min),
        jitter_max=max(0.0, retry_jitter_max),
        base_sleep=max(0.0, retry_base_sleep),
    )

    headless = bool(args.headless or DEFAULT_HEADLESS)
    profile_dir: Optional[pathlib.Path] = None
    if args.user_data_dir:
        profile_dir = pathlib.Path(args.user_data_dir).expanduser().resolve()
        profile_dir.mkdir(parents=True, exist_ok=True)
    if args.debug:
        print(f"[DEBUG] nodriver headless={headless} user_data_dir={profile_dir or 'ephemere'}")

    browser: Optional[uc.Browser] = None
    extra_rate_limit_attempts = EXTRA_RATE_LIMIT_ATTEMPTS
    cooldown_after_rate_limit = RATE_LIMIT_COOLDOWN

    async def _open_browser_and_warm() -> uc.Browser:
        br = await create_browser(
            proxy=args.proxy, headless=headless, user_data_dir=profile_dir
        )
        await warm_up_cardmarket_session(br, debug=args.debug)
        return br

    try:
        browser = await _open_browser_and_warm()
    except RateLimitError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    card_results: List[CardResult] = []
    try:
        for idx, product_url in enumerate(item_urls):
            code = codes[idx]
            card_result: Optional[CardResult] = None
            last_exception: Optional[Exception] = None
            for attempt_round in range(extra_rate_limit_attempts + 1):
                if browser is None:
                    try:
                        browser = await _open_browser_and_warm()
                    except RateLimitError as warm_exc:
                        last_exception = warm_exc
                        if args.debug:
                            print(f"[DEBUG] Navigateur indisponible apres rate limit: {warm_exc}")
                        await asyncio.sleep(_retry_delay(retry_config, attempt_round, None))
                        continue
                try:
                    card_result = await fetch_product_page(
                        browser,
                        product_url,
                        code=code,
                        debug=args.debug,
                        dump_dir=dump_path,
                        retry_config=retry_config,
                        language=args.language,
                    )
                    break
                except RateLimitError as exc:  # pragma: no cover - dependant du site
                    last_exception = exc
                    if args.debug:
                        print("[DEBUG] Redemarrage du navigateur nodriver apres 429 / Cloudflare.")
                    if browser is not None:
                        browser.stop()
                        browser = None
                    pause = max(0.0, cooldown_after_rate_limit)
                    if pause > 0 and args.debug:
                        print(f"[DEBUG] Pause supplementaire de {pause:.2f}s apres rate limit.")
                    if pause > 0:
                        await asyncio.sleep(pause)
                    if attempt_round == extra_rate_limit_attempts:
                        break
                    browser = await _open_browser_and_warm()
                except Exception as exc:  # pragma: no cover - gestion d'erreurs inattendues
                    last_exception = exc
                    break

            if browser is None and idx < len(item_urls) - 1:
                try:
                    browser = await _open_browser_and_warm()
                except RateLimitError as warm_exc:
                    if args.debug:
                        print(f"[DEBUG] Echec reouverture navigateur entre cartes: {warm_exc}")

            if card_result is None:
                card_result = CardResult(code=code, product_name=None, product_url=None)
                message = (
                    f"Erreur lors de la recuperation : {last_exception}"
                    if last_exception
                    else "Erreur inconnue lors de la recuperation."
                )
                card_result.warnings.append(message)
            card_results.append(card_result)
            if idx < len(item_urls) - 1 and default_sleep_between_cards:
                await asyncio.sleep(default_sleep_between_cards)
    finally:
        if browser is not None:
            browser.stop()

    seller_map = aggregate_sellers(card_results)
    seller_summary = summarize_sellers(seller_map, codes)
    value_summary = summarize_sellers_by_value(
        seller_map,
        {
            card.code: (min(o.price_eur for o in card.offers) if card.offers else None)
            for card in card_results
        },
    )
    display_report(
        card_results,
        seller_summary,
        value_summary,
        top=args.top,
        min_cards_for_value=2,
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    return uc.loop().run_until_complete(_run_async(args))


if __name__ == "__main__":
    sys.exit(main())


