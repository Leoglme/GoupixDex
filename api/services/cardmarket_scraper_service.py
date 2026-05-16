"""Cardmarket product pages: fetch HTML via nodriver, parse offers with BeautifulSoup."""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import nodriver as uc
from bs4 import BeautifulSoup
from bs4.element import Tag
from nodriver.cdp import runtime as cdp_runtime

from services.cardmarket_product_types import CardmarketCardResult, CardmarketOffer
from services.os_service import OsService

logger = logging.getLogger(__name__)

BASE_URL = "https://www.cardmarket.com"
GAME_SEGMENT = "/fr/Pokemon"
HOME_POKEMON_URL = f"{BASE_URL}{GAME_SEGMENT}"

DEFAULT_LANGUAGE_ID = 7
DEFAULT_MIN_CONDITION_ID = 2
REQUEST_TIMEOUT = 45.0
REQUEST_SLEEP = 1.0
DEFAULT_BETWEEN_CARDS_SLEEP = 2.5
BETWEEN_CARDS_JITTER: tuple[float, float] = (0.6, 1.6)
DEFAULT_MAX_RETRIES = 4
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_MAX_BACKOFF = 60.0
DEFAULT_JITTER_RANGE = (0.35, 1.2)
EXTRA_RATE_LIMIT_ATTEMPTS = 3
RATE_LIMIT_COOLDOWN = 20.0
DEFAULT_HEADLESS = False

CLOUDFLARE_HUMAN_WAIT_MAX_SEC = 300.0
CLOUDFLARE_HUMAN_WAIT_POLL_SEC = 2.5

_CLOUDFLARE_HARD_BLOCK_MARKERS: tuple[str, ...] = (
    "error 1015",
    "error 1020",
    "you are being rate limited",
    "cf-error-details",
)

_CLOUDFLARE_INTERACTIVE_MARKERS: tuple[str, ...] = (
    "vérification de sécurité en cours",
    "vérifiez que vous êtes humain",
    "verify you are human",
    "challenges.cloudflare.com",
    "cf-turnstile",
    "cf-challenge",
    "challenge-platform",
    "checking your browser before accessing",
    "just a moment",
)

_DEFAULT_BROWSER_ARGS: list[str] = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--start-maximized",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-session-crashed-bubble",
    "--homepage=about:blank",
]


class CardmarketScrapeError(RuntimeError):
    """Raised when a Cardmarket page cannot be loaded or parsed."""


class CardmarketRateLimitError(CardmarketScrapeError):
    """Persistent 429 / Cloudflare rate limit."""


@dataclass(frozen=True)
class _FetchedPage:
    url: str
    text: str
    status_code: int


@dataclass(frozen=True)
class _RetryConfig:
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR
    max_backoff: float = DEFAULT_MAX_BACKOFF
    jitter_min: float = DEFAULT_JITTER_RANGE[0]
    jitter_max: float = DEFAULT_JITTER_RANGE[1]
    base_sleep: float = REQUEST_SLEEP


def label_from_item_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if not path:
        return url
    return path.split("/")[-1]


def _merge_url_query(url: str, params: dict[str, Any] | None) -> str:
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


def _html_looks_like_cloudflare_hard_block(html: str) -> bool:
    """Persistent Cloudflare block (rate-limit pages 1015 / 1020) that won't be solved by a human."""
    if not html or len(html) < 200:
        return False
    lower = html.lower()
    return any(marker in lower for marker in _CLOUDFLARE_HARD_BLOCK_MARKERS)


def _html_looks_like_cloudflare_interactive_challenge(html: str) -> bool:
    """Interactive Cloudflare challenge (« Vérification de sécurité ») waiting for a human action."""
    if not html or len(html) < 100:
        return False
    lower = html.lower()
    return any(marker in lower for marker in _CLOUDFLARE_INTERACTIVE_MARKERS)


async def _wait_for_cloudflare_resolution(
    tab: uc.Tab,
    *,
    max_wait_s: float = CLOUDFLARE_HUMAN_WAIT_MAX_SEC,
    poll_interval_s: float = CLOUDFLARE_HUMAN_WAIT_POLL_SEC,
) -> bool:
    """Poll the open tab every ``poll_interval_s`` until the interactive challenge is gone or ``max_wait_s`` elapses.

    Periodically re-activates the tab so the user always sees the challenge in the foreground.
    """
    loop = asyncio.get_event_loop()
    started = loop.time()
    activations = 0
    while True:
        if loop.time() - started > max_wait_s:
            return False
        if activations % 4 == 0:
            try:
                await tab.activate()
            except Exception as exc:  # noqa: BLE001
                logger.debug("activate during cf wait: %s", exc)
        activations += 1
        await asyncio.sleep(poll_interval_s)
        try:
            html = await asyncio.wait_for(tab.get_content(), timeout=8.0)
        except (asyncio.TimeoutError, Exception):  # noqa: BLE001
            continue
        if _html_looks_like_cloudflare_hard_block(html):
            return False
        if not _html_looks_like_cloudflare_interactive_challenge(html):
            return True


async def _navigation_http_status(tab: uc.Tab) -> int:
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


async def _count_article_rows(tab: uc.Tab) -> int:
    """Count offer rows in the live DOM (class ``article-row``, any tag)."""
    expr = "(() => document.querySelectorAll('.article-row').length)()"
    try:
        raw = await tab.evaluate(expr, return_by_value=True)
    except Exception:
        return 0
    if isinstance(raw, cdp_runtime.ExceptionDetails):
        return 0
    if isinstance(raw, bool):
        return 0
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


async def _wait_for_article_rows(
    tab: uc.Tab,
    *,
    timeout_s: float = 9.0,
    poll_s: float = 0.4,
) -> int:
    """Poll the live DOM until at least one ``.article-row`` is visible or timeout."""
    loop = asyncio.get_running_loop()
    started = loop.time()
    last = 0
    while loop.time() - started < timeout_s:
        last = await _count_article_rows(tab)
        if last > 0:
            return last
        await asyncio.sleep(poll_s)
    return last


async def _get_outer_html(tab: uc.Tab) -> str | None:
    """Return ``document.documentElement.outerHTML`` (live DOM, post-hydration)."""
    expr = "(() => document.documentElement && document.documentElement.outerHTML || '')()"
    try:
        raw = await tab.evaluate(expr, return_by_value=True)
    except Exception:
        return None
    if isinstance(raw, cdp_runtime.ExceptionDetails):
        return None
    if isinstance(raw, str):
        return raw
    return None


def _maybe_dump_debug_html(profile_dir: Path, code: str, html: str) -> None:
    """Best-effort dump of the page HTML when 0 offers were parsed (debugging aid)."""
    try:
        dump_dir = profile_dir / "debug-dumps"
        dump_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        path = dump_dir / f"{code or 'unknown'}-{ts}.html"
        path.write_text(html, encoding="utf-8")
        logger.warning(
            "Cardmarket: 0 offers parsed for %s — full HTML dumped to %s for debugging.",
            code,
            path,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("debug dump failed: %s", exc)


def _chrome_executable() -> str | None:
    for key in ("CARDMARKET_CHROME_EXECUTABLE", "VINTED_CHROME_EXECUTABLE"):
        v = (os.environ.get(key) or "").strip()
        if v:
            return v
    return None


async def create_browser(
    *,
    proxy: str | None = None,
    headless: bool = DEFAULT_HEADLESS,
    user_data_dir: Path | None = None,
) -> uc.Browser:
    browser_args = list(_DEFAULT_BROWSER_ARGS)
    if proxy:
        browser_args.append(f"--proxy-server={proxy}")
    kwargs: dict[str, Any] = {
        "headless": headless,
        "browser_args": browser_args,
        "sandbox": False,
    }
    if user_data_dir is not None:
        kwargs["user_data_dir"] = str(user_data_dir)
    exe = _chrome_executable()
    if exe:
        kwargs["browser_executable_path"] = exe
    return await uc.start(**kwargs)


async def _try_activate_tab(tab: uc.Tab) -> None:
    """Bring the tab to the foreground in Chrome, swallowing any errors."""
    try:
        await tab.activate()
    except Exception as exc:  # noqa: BLE001
        logger.debug("tab.activate failed: %s", exc)


async def _prepare_clean_main_tab(browser: uc.Browser) -> uc.Tab:
    """
    Chrome (with a persistent profile) often restores extra tabs (Google homepage, etc.).
    Close everything except the first tab and return that single working tab so the
    user always sees the page we are scraping in the foreground.
    """
    try:
        await browser.wait(0.4)
    except Exception as exc:  # noqa: BLE001
        logger.debug("browser.wait (clean tabs): %s", exc)

    existing: list[uc.Tab] = list(getattr(browser, "tabs", []) or [])
    if not existing:
        return await browser.get("about:blank", new_tab=True)

    main = existing[0]
    for extra in existing[1:]:
        try:
            await extra.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("close extra tab failed: %s", exc)

    try:
        await browser.wait(0.3)
    except Exception:  # noqa: BLE001
        pass

    try:
        await main.get("about:blank")
    except Exception as exc:  # noqa: BLE001
        logger.debug("about:blank reset failed: %s", exc)
    await _try_activate_tab(main)
    return main


async def warm_up_cardmarket_session(
    browser: uc.Browser,
    *,
    debug: bool = False,
    emit: ProgressFn | None = None,
) -> uc.Tab:
    tab = await _prepare_clean_main_tab(browser)
    await asyncio.sleep(0.35 + random.uniform(0, 0.35))
    await tab.get(HOME_POKEMON_URL)
    await tab
    await _try_activate_tab(tab)
    await asyncio.sleep(random.uniform(1.2, 2.8))
    html = await tab.get_content()
    if _html_looks_like_cloudflare_hard_block(html):
        raise CardmarketRateLimitError(
            "Cloudflare bloque déjà sur la page Pokémon (ex. Error 1015). "
            "Attendez plusieurs minutes ou changez de connexion."
        )
    if _html_looks_like_cloudflare_interactive_challenge(html):
        if emit:
            await emit(
                {
                    "type": "cloudflare_wait",
                    "url": HOME_POKEMON_URL,
                    "message": (
                        "Cloudflare demande une vérification sur la page d’accueil — cochez la case "
                        "dans la fenêtre Chrome pour continuer."
                    ),
                }
            )
        await _try_activate_tab(tab)
        ok = await _wait_for_cloudflare_resolution(tab)
        if emit:
            await emit({"type": "cloudflare_resolved" if ok else "cloudflare_timeout", "url": HOME_POKEMON_URL})
        if not ok:
            raise CardmarketRateLimitError(
                "Vérification Cloudflare non résolue dans le délai imparti (warm-up)."
            )
        await asyncio.sleep(random.uniform(0.8, 1.8))
    try:
        from services.cardmarket_session_service import persist_session_from_probe, read_session_from_tab

        profile_dir = default_user_data_dir()
        info = await read_session_from_tab(tab)
        logged_in = persist_session_from_probe(profile_dir, info)
        if logged_in:
            logger.info("Cardmarket warmup: signed in as %s", info.get("username"))
            if emit:
                await emit(
                    {
                        "type": "session_status",
                        "logged_in": True,
                        "username": info.get("username"),
                    }
                )
        else:
            logger.warning(
                "Cardmarket warmup: not signed in — session cache cleared; connect via "
                "Settings → Marketplace."
            )
            if emit:
                await emit(
                    {
                        "type": "session_status",
                        "logged_in": False,
                        "message": (
                            "Compte Cardmarket non détecté — connectez-vous via les paramètres "
                            "marketplace (la session enregistrée a été effacée)."
                        ),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.debug("session status check at warmup: %s", exc)

    if debug:
        logger.debug("Cardmarket session warmed (single tab -> Pokemon FR).")
    return tab


def clean_price(raw_price: str) -> float:
    normalized = (
        raw_price.replace("\u202f", "")
        .replace("\xa0", "")
        .replace("\u20ac", "")
        .replace(" ", "")
        .strip()
    )
    normalized = normalized.replace(",", ".")
    return float(normalized)


def parse_int(value: str) -> int | None:
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return None


def extract_product_name(soup: BeautifulSoup) -> str | None:
    header = soup.select_one("h1.page-title, h1.product-title")
    if header:
        return header.get_text(strip=True)
    return None


def _find_seller_anchor_in_row(row: Tag) -> Tag | None:
    """Seller profile link (path segment ``Users`` varies by locale / rewrites)."""
    for sel in (
        ".seller-name a[href*='Users/']",
        ".seller-name a[href*='users/']",
        ".seller-info a[href*='Users/']",
        ".seller-info a[href*='users/']",
        "a[href*='/Users/']",
    ):
        a = row.select_one(sel)
        if isinstance(a, Tag):
            return a
    return None


def _price_raw_text_from_row(row: Tag) -> str | None:
    """Price cell text: Cardmarket sometimes swaps Bootstrap utility classes."""
    pc = row.select_one(".price-container")
    if not isinstance(pc, Tag):
        return None
    for sel in (
        "span.color-primary",
        "span.text-primary",
        "span.fw-bold",
        ".fw-bold",
        "span.font-weight-bold",
    ):
        el = pc.select_one(sel)
        if not isinstance(el, Tag):
            continue
        t = el.get_text(strip=True)
        if t and any(ch.isdigit() for ch in t):
            return t
    for el in pc.select("span"):
        if not isinstance(el, Tag):
            continue
        t = el.get_text(strip=True)
        if t and any(ch.isdigit() for ch in t):
            return t
    return None


def extract_offers_from_product_page(soup: BeautifulSoup) -> list[CardmarketOffer]:
    offers: list[CardmarketOffer] = []
    rows = soup.select(".article-row")
    skipped_no_seller = 0
    skipped_no_price = 0
    for row in rows:
        if not isinstance(row, Tag):
            continue
        seller_anchor = _find_seller_anchor_in_row(row)
        if not seller_anchor:
            skipped_no_seller += 1
            continue
        seller_name = seller_anchor.get_text(strip=True)

        price_raw = _price_raw_text_from_row(row)
        if not price_raw:
            skipped_no_price += 1
            continue
        try:
            price_eur = clean_price(price_raw)
        except (TypeError, ValueError):
            skipped_no_price += 1
            continue

        quantity_span = row.select_one(".amount-container .item-count")
        quantity = parse_int(quantity_span.get_text()) if quantity_span else None
        if quantity is None:
            quantity = 1

        location_span = row.select_one(".seller-name span[aria-label]")
        seller_location = None
        if location_span and location_span.get("aria-label"):
            seller_location = (
                str(location_span.get("aria-label"))
                .replace("Localisation de l'article: ", "")
                .strip()
            )

        shipping_span = row.select_one(".seller-info .shippingTime-info")
        shipping_time_days = parse_int(shipping_span.get_text()) if shipping_span else None

        comment_span = row.select_one(".product-comments span.text-truncate")
        comments = comment_span.get_text(strip=True) if comment_span else None

        form_hidden = row.select_one("form input[name='idArticle']")
        article_id = form_hidden.get("value") if isinstance(form_hidden, Tag) else None

        offers.append(
            CardmarketOffer(
                seller_name=seller_name,
                price_eur=price_eur,
                quantity=quantity,
                seller_location=seller_location,
                shipping_time_days=shipping_time_days,
                comments=comments,
                article_id=article_id,
            )
        )
    logger.info(
        "Cardmarket parse: rows=%d offers=%d skipped(no_seller)=%d skipped(no_price)=%d",
        len(rows),
        len(offers),
        skipped_no_seller,
        skipped_no_price,
    )
    return offers


def _retry_delay(config: _RetryConfig, attempt: int) -> float:
    base = config.base_sleep if config.base_sleep > 0 else 0.5
    backoff = base * (config.backoff_factor**attempt)
    jitter = random.uniform(config.jitter_min, config.jitter_max)
    return min(config.max_backoff, backoff + jitter)


async def _fetch_page_once(
    tab: uc.Tab,
    full_url: str,
    *,
    timeout: float = REQUEST_TIMEOUT,
    emit: ProgressFn | None = None,
) -> _FetchedPage:
    """
    Initial navigation is bounded by ``timeout``; if Cloudflare shows an interactive
    challenge, we exit that timeout and wait (up to ``CLOUDFLARE_HUMAN_WAIT_MAX_SEC``)
    for the user to solve it manually in the Chrome window.

    Always reuses the supplied ``tab`` so the user keeps seeing the same Chrome view.
    After load, polls the live DOM for ``.article-row``, then **re-fetches** HTML with
    ``get_content()`` so we do not parse a stale snapshot from before rows appeared.
    Optionally merges a longer ``outerHTML`` when CDP returns it successfully.
    """

    async def _initial() -> str:
        await tab.get(full_url)
        await tab
        await _try_activate_tab(tab)
        await asyncio.sleep(random.uniform(0.25, 0.6))
        return await tab.get_content()

    html = await asyncio.wait_for(_initial(), timeout=timeout)

    if _html_looks_like_cloudflare_interactive_challenge(html) and not _html_looks_like_cloudflare_hard_block(html):
        if emit:
            await emit(
                {
                    "type": "cloudflare_wait",
                    "url": full_url,
                    "message": (
                        "Cloudflare demande une vérification — cochez la case dans la fenêtre "
                        "Chrome ouverte par GoupixDex, l’analyse reprend automatiquement."
                    ),
                }
            )
        await _try_activate_tab(tab)
        ok = await _wait_for_cloudflare_resolution(tab)
        if emit:
            await emit({"type": "cloudflare_resolved" if ok else "cloudflare_timeout", "url": full_url})
        if ok:
            await asyncio.sleep(random.uniform(0.6, 1.4))
            try:
                html = await asyncio.wait_for(tab.get_content(), timeout=10.0)
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                pass

    status = await _navigation_http_status(tab)
    final_url = tab.target.url or full_url

    if _html_looks_like_cloudflare_hard_block(html):
        return _FetchedPage(url=final_url, text=html, status_code=429)
    if _html_looks_like_cloudflare_interactive_challenge(html):
        return _FetchedPage(url=final_url, text=html, status_code=429)

    rows_seen = await _wait_for_article_rows(tab, timeout_s=9.0, poll_s=0.4)
    try:
        await tab.evaluate(
            "(() => { try { window.scrollTo(0, document.body.scrollHeight); } catch (e) {} })()",
            return_by_value=True,
        )
    except Exception:  # noqa: BLE001
        pass
    await asyncio.sleep(random.uniform(0.12, 0.38))
    try:
        fresh_html = await asyncio.wait_for(tab.get_content(), timeout=45.0)
        if isinstance(fresh_html, str) and fresh_html.strip():
            html = fresh_html
    except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
        logger.warning("Cardmarket: post-wait get_content failed (%s) url=%s", exc, final_url)

    live_html = await _get_outer_html(tab)
    if live_html and len(live_html) > len(html or ""):
        html = live_html
    if rows_seen == 0:
        logger.warning(
            "Cardmarket: navigation done but 0 .article-row in live DOM (url=%s, html_len=%d).",
            final_url,
            len(html or ""),
        )

    return _FetchedPage(url=final_url, text=html, status_code=status)


async def get_with_retry(
    tab: uc.Tab,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = REQUEST_TIMEOUT,
    config: _RetryConfig | None = None,
    description: str | None = None,
    emit: ProgressFn | None = None,
) -> _FetchedPage:
    if config is None:
        config = _RetryConfig()
    full_url = _merge_url_query(url, params)
    last_exception: Exception | None = None
    attempt = 0
    total_attempts = config.max_retries + 1
    saw_rate_limit = False
    while attempt < total_attempts:
        try:
            page = await _fetch_page_once(tab, full_url, timeout=timeout, emit=emit)
        except asyncio.TimeoutError as exc:
            last_exception = exc
        except Exception as exc:
            last_exception = exc
        else:
            if page.status_code == 429:
                saw_rate_limit = True
                delay = _retry_delay(config, attempt)
                logger.warning("429 on %s — retry in %.1fs", description or full_url, delay)
                await asyncio.sleep(delay)
                attempt += 1
                continue
            if page.status_code >= 400:
                last_exception = CardmarketScrapeError(f"HTTP {page.status_code}")
            else:
                return page

        delay = _retry_delay(config, attempt)
        await asyncio.sleep(delay)
        attempt += 1

    message = f"Failed {description or full_url} after {total_attempts} attempts."
    if saw_rate_limit:
        raise CardmarketRateLimitError(message) from last_exception
    raise CardmarketScrapeError(message) from last_exception


async def fetch_product_page(
    tab: uc.Tab,
    product_url: str,
    *,
    code: str,
    language_id: int | None = None,
    min_condition_id: int | None = None,
    retry_config: _RetryConfig | None = None,
    emit: ProgressFn | None = None,
) -> CardmarketCardResult:
    result = CardmarketCardResult(code=code, product_name=None, product_url=None)
    if retry_config is None:
        retry_config = _RetryConfig()

    params: dict[str, Any] = {"minCondition": min_condition_id or DEFAULT_MIN_CONDITION_ID}
    lang = language_id if language_id is not None else DEFAULT_LANGUAGE_ID
    params["language"] = lang
    if code.endswith("R"):
        params["isReverseHolo"] = "Y"

    product_response = await get_with_retry(
        tab,
        product_url,
        params=params,
        timeout=REQUEST_TIMEOUT,
        description=f"product '{code}'",
        config=retry_config,
        emit=emit,
    )
    if product_response.status_code >= 400:
        result.warnings.append(f"HTTP {product_response.status_code} loading product page.")
        return result

    product_soup = BeautifulSoup(product_response.text, "html.parser")
    result.product_name = extract_product_name(product_soup)
    result.product_url = product_response.url
    result.offers = extract_offers_from_product_page(product_soup)
    if not result.offers:
        result.warnings.append("No offers found for the requested filters.")
        try:
            _maybe_dump_debug_html(default_user_data_dir(), code, product_response.text)
        except Exception as exc:  # noqa: BLE001
            logger.debug("dump on empty offers failed: %s", exc)
    else:
        logger.info(
            "Cardmarket %s: %d offers parsed (cheapest %.2f €)",
            code,
            len(result.offers),
            min(o.price_eur for o in result.offers),
        )
    return result


def default_user_data_dir() -> Path:
    explicit = (os.environ.get("GOUPIX_CARDMARKET_USER_DATA_DIR") or "").strip() or None
    return OsService.resolve_cardmarket_nodriver_user_data_dir(explicit)


ProgressFn = Callable[[dict[str, Any]], Awaitable[None]]
CardDoneFn = Callable[[list[CardmarketCardResult]], Awaitable[None]]


async def scrape_urls_to_card_results(
    urls: list[str],
    *,
    progress: ProgressFn | None = None,
    on_card_done: CardDoneFn | None = None,
    sleep_between_cards: float = DEFAULT_BETWEEN_CARDS_SLEEP,
    between_cards_jitter: tuple[float, float] = BETWEEN_CARDS_JITTER,
) -> list[CardmarketCardResult]:
    """
    Open one browser session, warm up, fetch each product URL, return ``CardmarketCardResult`` rows.

    Retries on rate-limit by restarting the browser (same strategy as the standalone script).
    Calls ``on_card_done(card_results_so_far)`` after each card so callers can stream
    intermediate aggregations to the UI. Pauses for human action when Cloudflare shows
    an interactive challenge.
    """
    profile_dir = default_user_data_dir()
    profile_dir.mkdir(parents=True, exist_ok=True)

    async def emit(ev: dict[str, Any]) -> None:
        if progress:
            await progress(ev)

    retry_cfg = _RetryConfig()

    browser: uc.Browser | None = None
    tab: uc.Tab | None = None
    extra_rate_limit_attempts = EXTRA_RATE_LIMIT_ATTEMPTS
    cooldown_after_rate_limit = RATE_LIMIT_COOLDOWN

    async def _open_browser_and_warm() -> tuple[uc.Browser, uc.Tab]:
        br = await create_browser(headless=DEFAULT_HEADLESS, user_data_dir=profile_dir)
        working_tab = await warm_up_cardmarket_session(br, emit=emit)
        return br, working_tab

    try:
        browser, tab = await _open_browser_and_warm()
    except CardmarketRateLimitError as exc:
        await emit({"type": "error", "message": str(exc)})
        raise

    codes = [label_from_item_url(u) for u in urls]
    card_results: list[CardmarketCardResult] = []

    def _safe_close_browser(br: uc.Browser | None) -> None:
        if br is None:
            return
        try:
            br.stop()
        except Exception as exc:  # noqa: BLE001
            logger.debug("browser.stop: %s", exc)

    try:
        for idx, product_url in enumerate(urls):
            code = codes[idx]
            await emit(
                {
                    "type": "progress",
                    "current": idx + 1,
                    "total": len(urls),
                    "code": code,
                    "product_url": product_url,
                }
            )
            card_result: CardmarketCardResult | None = None
            last_exc: Exception | None = None
            for attempt_round in range(extra_rate_limit_attempts + 1):
                if browser is None or tab is None:
                    try:
                        browser, tab = await _open_browser_and_warm()
                    except CardmarketRateLimitError as warm_exc:
                        last_exc = warm_exc
                        await asyncio.sleep(_retry_delay(retry_cfg, attempt_round))
                        continue
                try:
                    card_result = await fetch_product_page(
                        tab,
                        product_url,
                        code=code,
                        retry_config=retry_cfg,
                        emit=emit,
                    )
                    break
                except CardmarketRateLimitError as exc:
                    last_exc = exc
                    _safe_close_browser(browser)
                    browser = None
                    tab = None
                    pause = max(0.0, cooldown_after_rate_limit)
                    if pause > 0:
                        await asyncio.sleep(pause)
                    if attempt_round == extra_rate_limit_attempts:
                        break
                    try:
                        browser, tab = await _open_browser_and_warm()
                    except CardmarketRateLimitError as warm_exc:
                        last_exc = warm_exc
                        await asyncio.sleep(_retry_delay(retry_cfg, attempt_round))
                        continue
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    break

            if (browser is None or tab is None) and idx < len(urls) - 1:
                try:
                    browser, tab = await _open_browser_and_warm()
                except CardmarketRateLimitError:
                    pass

            if card_result is None:
                card_result = CardmarketCardResult(code=code, product_name=None, product_url=None)
                card_result.warnings.append(
                    f"Fetch failed: {last_exc}" if last_exc else "Unknown fetch error."
                )
            card_results.append(card_result)

            if on_card_done is not None:
                try:
                    await on_card_done(card_results)
                except asyncio.CancelledError:
                    raise
                except Exception as cb_exc:  # noqa: BLE001
                    logger.debug("on_card_done callback failed: %s", cb_exc)

            if idx < len(urls) - 1 and sleep_between_cards > 0:
                jitter_min, jitter_max = between_cards_jitter
                jitter = random.uniform(jitter_min, jitter_max) if jitter_max > jitter_min else 0.0
                await asyncio.sleep(sleep_between_cards + jitter)
    finally:
        if browser is not None and tab is not None:
            try:
                from services.cardmarket_session_service import probe_tab_and_persist_session

                await probe_tab_and_persist_session(tab, profile_dir)
            except Exception as exc:  # noqa: BLE001
                logger.debug("session probe before browser close: %s", exc)
        _safe_close_browser(browser)

    return card_results
