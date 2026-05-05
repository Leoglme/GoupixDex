"""
Best-effort scrape of eBay **sold / completed** listing search (HTML).

No Marketplace Insights API — uses the public search URL like a browser.
**Fragile:** eBay often returns **403** for datacenter IPs.

Uses ``curl_cffi`` with Chrome TLS/JA3 impersonation to defeat fingerprint-based
blocks (eBay's edge fingerprints datacenter clients via JA3, not just IP). A
warm-up GET on ``ebay.fr`` first collects session cookies, mirroring a real
browser flow. An optional ``EBAY_SOLD_SCRAPE_PROXY`` is still honored as a
last-resort fallback when impersonation alone is not enough.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from config import AppSettings, get_settings

logger = logging.getLogger(__name__)

EBAY_FR_HOME = "https://www.ebay.fr/"
EBAY_FR_SOLD_BASE = "https://www.ebay.fr/sch/i.html"

#: Default impersonation profiles tried in order when no browser cookie source
#: drives the choice (Chrome JA3 first, Safari JA3 fallback).
_IMPERSONATE_PROFILES: tuple[str, ...] = ("chrome", "safari17_0")

#: When we inject cookies harvested from a specific browser, we want the TLS /
#: HTTP/2 fingerprint to *match* that browser — otherwise eBay's edge sees
#: « cookies issued to Firefox JA3, presented over Chrome JA3 » and trips the
#: anti-bot challenge. ``curl_cffi`` 0.7+ ships these named profiles.
_PROFILES_BY_BROWSER: dict[str, tuple[str, ...]] = {
    "firefox": ("firefox133", "firefox110", "chrome"),
    "chrome": ("chrome", "safari17_0"),
    "chromium": ("chrome", "safari17_0"),
    "brave": ("chrome", "safari17_0"),
    "edge": ("chrome", "safari17_0"),
    "safari": ("safari17_0", "chrome"),
}

#: Extra headers on top of those auto-set by impersonation. We only force the
#: language: Chrome defaults to ``en-US`` which is suspicious for ebay.fr.
_EXTRA_HEADERS: dict[str, str] = {
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


class EbayScrapeError(Exception):
    """Raised when the eBay HTML fetch fails (HTTP >= 400 or transport error)."""

    def __init__(self, *, status_code: int | None, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class ScrapedSoldRow:
    title: str
    price_eur: float | None
    listing_url: str
    image_url: str | None
    item_id: str | None
    sold_caption: str | None
    approx_hours_ago: float | None


def ebay_fr_sold_search_url(*, q: str, page_size: int = 50) -> str:
    """Human-readable same search as the scraper (for opening in a browser)."""
    params = {
        "_nkw": q.strip(),
        "LH_Sold": "1",
        "LH_Complete": "1",
        "_sop": "13",
        "_ipg": str(min(max(page_size, 10), 60)),
        "rt": "nc",
    }
    return f"{EBAY_FR_SOLD_BASE}?{urlencode(params)}"


def _extract_item_id(url: str) -> str | None:
    m = re.search(r"/itm/(\d{6,20})", url)
    return m.group(1) if m else None


def _parse_eur_price(raw: str) -> float | None:
    t = (raw or "").replace("EUR", " ").replace("€", " ").strip()
    if not t:
        return None
    m = re.search(r"(\d[\d\s]*[,.]\d{2})\s*$", t.replace(" ", ""))
    if not m:
        m = re.search(r"(\d[\d\s]{0,12})", t.replace(" ", ""))
    if not m:
        return None
    num = m.group(1).replace(" ", "").replace(".", "").replace(",", ".", 1)
    try:
        v = float(num)
    except ValueError:
        return None
    return round(v, 2) if v > 0 else None


_RELATIVE_FR = (
    (re.compile(r"il y a\s+(\d+)\s*heure", re.I), lambda n: float(n)),
    (re.compile(r"il y a\s+(\d+)\s*jour", re.I), lambda n: float(n) * 24.0),
    (re.compile(r"il y a\s+(\d+)\s*minute", re.I), lambda n: float(n) / 60.0),
)

#: French month tokens normalized to ASCII (no accent, trailing dot stripped).
_FR_MONTHS: dict[str, int] = {
    "janv": 1, "janvier": 1, "jan": 1,
    "fevr": 2, "fev": 2, "fevrier": 2,
    "mars": 3, "mar": 3,
    "avr": 4, "avril": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7, "juillet": 7,
    "aout": 8,
    "sept": 9, "sep": 9, "septembre": 9,
    "oct": 10, "octobre": 10,
    "nov": 11, "novembre": 11,
    "dec": 12, "decembre": 12,
}

#: Matches a French short or long month name (with or without accent) in a caption.
_FR_DATE_RX = re.compile(
    r"(?P<day>\d{1,2})\s*"
    r"(?P<month>janv\.?|janvier|jan\.?|f[eé]vr?\.?|f[eé]vrier|mars|mar\.?|"
    r"avr\.?|avril|mai|juin|juil\.?|juillet|ao[uû]t|sept\.?|sep\.?|septembre|"
    r"oct\.?|octobre|nov\.?|novembre|d[eé]c\.?|d[eé]cembre)"
    r"\.?\s*(?P<year>\d{4})?",
    re.IGNORECASE,
)


def _normalize_month_token(token: str) -> str:
    t = token.lower().rstrip(".")
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("û", "u"), ("ù", "u")):
        t = t.replace(a, b)
    return t


def _approx_hours_from_caption(caption: str, *, now: datetime | None = None) -> float | None:
    s = (caption or "").strip()
    if not s:
        return None
    for rx, fn in _RELATIVE_FR:
        m = rx.search(s)
        if m:
            try:
                return fn(float(m.group(1)))
            except (TypeError, ValueError):
                continue
    m = _FR_DATE_RX.search(s)
    if not m:
        return None
    month = _FR_MONTHS.get(_normalize_month_token(m.group("month")))
    if month is None:
        return None
    try:
        day = int(m.group("day"))
    except (TypeError, ValueError):
        return None
    current = now or datetime.now(timezone.utc)
    if m.group("year"):
        year = int(m.group("year"))
    else:
        year = current.year
        try:
            candidate = datetime(year, month, day, 12, 0, tzinfo=timezone.utc)
        except ValueError:
            return None
        if candidate > current:
            year -= 1
    try:
        sold = datetime(year, month, day, 12, 0, tzinfo=timezone.utc)
    except ValueError:
        return None
    delta_hours = (current - sold).total_seconds() / 3600.0
    return max(delta_hours, 0.0)


#: Trailing screen-reader text appended to titles in the new ``s-card`` layout.
_SR_ONLY_TITLE_RX = re.compile(r"\s*La page s['’]ouvre.*$", re.I)


def _clean_title(text: str) -> str:
    return _SR_ONLY_TITLE_RX.sub("", text or "").strip()


def _parse_sold_rows(html: str) -> list[ScrapedSoldRow]:
    soup = BeautifulSoup(html, "html.parser")
    # New layout (2025+): ``<li class="s-card …" data-listingid="…">``.
    lis = soup.select("li.s-card")
    if not lis:
        lis = soup.select("li.s-item")  # legacy fallback

    rows: list[ScrapedSoldRow] = []
    for li in lis:
        li_classes = " ".join(li.get("class") or [])
        if "s-item--watch-at-corner" in li_classes:
            continue

        title_el = (
            li.select_one(".s-card__title")
            or li.select_one(".s-item__title span")
            or li.select_one(".s-item__title")
        )
        title = _clean_title(title_el.get_text(" ", strip=True) if title_el else "")
        if not title or title.lower().startswith("montrez-vous") or "sponsoris" in title.lower():
            continue

        # Prefer ``data-listingid`` (canonical, present on every s-card LI). The
        # visible ``a.su-link`` in the new layout points to a *search results*
        # URL, not to the listing — so reconstruct the listing URL ourselves.
        item_id = (li.get("data-listingid") or "").strip() or None
        listing_url = ""
        if item_id and item_id.isdigit():
            listing_url = f"https://www.ebay.fr/itm/{item_id}"
        else:
            link_el = li.select_one("a[href*='/itm/']") or li.select_one("a.s-item__link")
            href = str(link_el.get("href") or "").strip() if link_el else ""
            if href.startswith("http"):
                listing_url = href.split("?")[0]
                item_id = item_id or _extract_item_id(href)
        if not listing_url:
            continue

        price_el = li.select_one(".s-card__price") or li.select_one(".s-item__price")
        price_txt = price_el.get_text(" ", strip=True) if price_el else ""
        price = _parse_eur_price(price_txt)

        img_el = (
            li.select_one(".s-card__image img")
            or li.select_one(".image-treatment img")
            or li.select_one("img.s-item__image-img")
            or li.select_one(".s-item__image-img")
        )
        img_src = ""
        if img_el is not None:
            img_src = str(img_el.get("src") or "").strip() or str(img_el.get("data-src") or "").strip()
        img_url = img_src if img_src.startswith("http") else None

        cap_el = (
            li.select_one(".s-card__caption")
            or li.select_one(".s-item__subtitle")
            or li.select_one(".s-item__caption--signal")
        )
        cap_txt = cap_el.get_text(" ", strip=True) if cap_el else ""
        approx = _approx_hours_from_caption(cap_txt)

        rows.append(
            ScrapedSoldRow(
                title=title,
                price_eur=price,
                listing_url=listing_url,
                image_url=img_url,
                item_id=item_id,
                sold_caption=cap_txt or None,
                approx_hours_ago=approx,
            ),
        )
    return rows


#: Substrings present on eBay's anti-bot interstitial (« Nous sommes désolés / Vérification de
#: votre navigateur avant d'accéder à eBay »). The page is also dramatically smaller than a real SRP.
_BOT_CHALLENGE_TOKENS: tuple[str, ...] = (
    "vérification de votre navigateur",
    "verification de votre navigateur",
    "nous sommes désolés",
    "nous sommes desoles",
    "access denied",
    "security measure",
    "pardon our interruption",
)


def _looks_like_bot_challenge(html: str) -> bool:
    """Heuristic: very short HTML *and* a known interstitial phrase appears in it."""
    if len(html) >= 200_000:
        return False
    head = html[:8000].lower()
    return any(tok in head for tok in _BOT_CHALLENGE_TOKENS)


def _filter_window(rows: list[ScrapedSoldRow], *, window_hours: float) -> list[ScrapedSoldRow]:
    """Keep rows whose relative sold time could be parsed and fits the window."""
    out: list[ScrapedSoldRow] = []
    for r in rows:
        if r.approx_hours_ago is None:
            continue
        if r.approx_hours_ago <= window_hours + 0.5:
            out.append(r)
    return out


#: Cached eBay cookies from the local user's browser. Refreshed every 5 min so
#: that re-authentication / challenge resolution in the browser is picked up
#: without restarting the API. Empty dict on platforms / setups where no
#: browser cookie store is reachable (e.g. headless VPS).
_BROWSER_COOKIE_CACHE: dict[str, Any] = {"loaded_at": 0.0, "value": {}}
_BROWSER_COOKIE_TTL_SECONDS = 300.0
#: Shorter TTL when no cookies were found, so a freshly-loaded browser is picked
#: up quickly instead of being masked by a 5-minute miss-cache.
_BROWSER_COOKIE_TTL_EMPTY = 30.0


def _read_browser_cookies() -> tuple[dict[str, str], str | None]:
    """
    Best-effort: read ebay.fr / ebay.com cookies from the local user's browser
    so that a human-passed challenge cookie can flow into our automated request.

    Returns ``({}, None)`` when no browser cookie store is accessible (typical
    on a headless server). The second tuple element identifies the source
    browser (e.g. ``"firefox"``) so the caller can pick a matching TLS profile.
    Cached for 5 min on success / 30 s on miss.
    """
    now = time.time()
    cached_value: dict[str, str] = dict(_BROWSER_COOKIE_CACHE["value"])
    cached_source: str | None = _BROWSER_COOKIE_CACHE.get("source")  # type: ignore[assignment]
    age = now - float(_BROWSER_COOKIE_CACHE["loaded_at"])
    ttl = _BROWSER_COOKIE_TTL_SECONDS if cached_value else _BROWSER_COOKIE_TTL_EMPTY
    if age < ttl:
        return cached_value, cached_source

    cookies: dict[str, str] = {}
    source: str | None = None
    try:
        import browser_cookie3  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("browser_cookie3 not installed — install via `pip install browser-cookie3`")
        _BROWSER_COOKIE_CACHE["loaded_at"] = now
        _BROWSER_COOKIE_CACHE["value"] = cookies
        _BROWSER_COOKIE_CACHE["source"] = source
        return cookies, source

    attempts: list[str] = []
    # Probe order favors browsers we have a matching impersonation profile for.
    for name in ("chrome", "safari", "firefox", "edge", "brave", "chromium"):
        loader = getattr(browser_cookie3, name, None)
        if not callable(loader):
            continue
        try:
            jar = loader(domain_name="ebay")
        except Exception as exc:
            attempts.append(f"{name}=err({type(exc).__name__})")
            continue
        bucket: dict[str, str] = {}
        for c in jar:
            domain = (c.domain or "").lstrip(".")
            if domain.endswith("ebay.fr") or domain.endswith("ebay.com"):
                bucket[c.name] = c.value
        attempts.append(f"{name}={len(bucket)}")
        if bucket and not cookies:
            cookies = bucket
            source = name
            logger.info("Loaded %d eBay cookie(s) from browser=%s", len(cookies), name)

    if not cookies:
        logger.warning("No eBay cookies found in any browser. Probes: %s", ", ".join(attempts) or "none")

    _BROWSER_COOKIE_CACHE["loaded_at"] = now
    _BROWSER_COOKIE_CACHE["value"] = cookies
    _BROWSER_COOKIE_CACHE["source"] = source
    return cookies, source


async def _fetch_with_profile(
    *,
    url: str,
    profile: str,
    proxies: dict[str, str] | None,
    cookies: dict[str, str],
) -> str:
    """One attempt: warm-up GET on the eBay home, then the search URL."""
    async with AsyncSession(impersonate=profile, timeout=45, proxies=proxies) as session:
        try:
            await session.get(
                EBAY_FR_HOME,
                headers=_EXTRA_HEADERS,
                cookies=cookies or None,
                allow_redirects=True,
            )
        except Exception as exc:
            logger.debug("eBay warm-up GET failed (%s): %s", profile, exc)

        try:
            resp = await session.get(
                url,
                headers=_EXTRA_HEADERS,
                cookies=cookies or None,
                allow_redirects=True,
            )
        except Exception as exc:
            raise EbayScrapeError(status_code=None, message=str(exc)) from exc

    if resp.status_code >= 400:
        logger.warning(
            "eBay sold HTML fetch failed (%s) status=%s len=%s",
            profile, resp.status_code, len(resp.text),
        )
        raise EbayScrapeError(status_code=resp.status_code, message=f"HTTP {resp.status_code}")
    return resp.text


async def fetch_sold_listings_html(*, q: str, page_size: int = 50, app: AppSettings | None = None) -> str:
    """
    Fetch the sold-listings HTML, trying each impersonation profile in turn.

    If the primary profile yields a bot-challenge interstitial, retries once with
    the fallback profile after a brief pause. Returns the last HTML we obtained;
    the caller detects the challenge to surface a clean error to the user.
    """
    s = app or get_settings()
    url = ebay_fr_sold_search_url(q=q, page_size=page_size)
    proxy = (s.ebay_sold_scrape_proxy or "").strip() or None
    proxies = {"http": proxy, "https": proxy} if proxy else None

    cookies, cookie_source = _read_browser_cookies()
    profiles = _PROFILES_BY_BROWSER.get(cookie_source or "", _IMPERSONATE_PROFILES)
    if cookie_source:
        logger.info("Using impersonation profiles=%s to match cookie source=%s", profiles, cookie_source)

    last_html = ""
    last_err: EbayScrapeError | None = None
    for idx, profile in enumerate(profiles):
        if idx > 0:
            await asyncio.sleep(1.5)  # brief pause before profile rotation
        try:
            html = await _fetch_with_profile(
                url=url, profile=profile, proxies=proxies, cookies=cookies,
            )
        except EbayScrapeError as exc:
            last_err = exc
            continue
        except Exception as exc:
            # curl_cffi raises if an impersonation profile string is unknown to
            # the bundled libcurl-impersonate (e.g. ``firefox133`` on an older
            # build). Skip to the next profile rather than 500-ing.
            logger.warning("Impersonation profile %s unavailable: %s", profile, exc)
            continue
        last_html = html
        if not _looks_like_bot_challenge(html):
            return html
        logger.info("eBay challenge with profile=%s — trying next", profile)

    if last_html:
        return last_html  # caller will detect the challenge
    if last_err:
        raise last_err
    raise EbayScrapeError(status_code=None, message="no impersonation profile succeeded")


async def scrape_sold_listings(
    *,
    q: str,
    window_hours: float,
    limit: int = 50,
    app: AppSettings | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Return ``(items_as_dicts, error_message_or_none)``.

    On success ``error_message_or_none`` is ``None``.
    """
    try:
        html = await fetch_sold_listings_html(q=q, page_size=min(60, max(limit, 10)), app=app)
    except EbayScrapeError as exc:
        if exc.status_code is None:
            logger.warning("eBay sold scrape transport error: %s", exc)
            return [], f"Erreur réseau lors du téléchargement de la page eBay : {exc}"
        return (
            [],
            f"eBay a refusé la page HTML (HTTP {exc.status_code}). "
            f"Réessayez plus tard ou ouvrez la recherche « vendus » dans le navigateur.",
        )

    if _looks_like_bot_challenge(html):
        logger.warning("eBay served bot-challenge page (len=%d)", len(html))
        return (
            [],
            "eBay a affiché une page de vérification anti-bot. "
            "Ouvrez ebay.fr dans Safari ou Chrome sur cette machine, laissez la page se charger "
            "(le challenge se résout tout seul), puis réessayez : l'API réutilisera vos cookies "
            "de navigateur. À défaut, attendez 30–60 min et utilisez le lien manuel ci-dessous.",
        )

    all_rows = _parse_sold_rows(html)
    in_window = _filter_window(all_rows, window_hours=window_hours)
    rows = in_window[:limit]
    if not rows:
        logger.info(
            "eBay sold scrape empty: q=%r window=%sh parsed=%d in_window=%d html_len=%d",
            q, window_hours, len(all_rows), len(in_window), len(html),
        )

    items: list[dict[str, Any]] = []
    for r in rows:
        items.append(
            {
                "title": r.title,
                "price_eur": r.price_eur,
                "listing_url": r.listing_url,
                "image_url": r.image_url,
                "item_id": r.item_id,
                "sold_caption": r.sold_caption,
                "approx_hours_ago": r.approx_hours_ago,
            },
        )
    return items, None
