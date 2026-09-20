"""
Amazon scraper: nodriver (Chrome / CDP, persistent profile) + httpx for HTML.
"""
from __future__ import annotations

import os
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

import amazon_config
from amazon_config import AMAZON_BASE_URL
from amazon_http import (
    DEFAULT_HEADERS,
    cookies_from_chromium_profile,
    cookies_from_legacy_json_export,
    fetch_html_http,
    looks_like_blocked_or_bot,
    nodriver_cookies_to_client,
    post_hdp_request_invite,
)
from services.amazon_profile_session_service import detect_amazon_session_from_profile
from amazon_nodriver import (
    close_browser_sync,
    export_cookies_requests_format,
    fetch_html_via_tab,
    login_to_amazon as nodriver_login_session,
    prime_session_and_export_cookies_async,
    run_browser,
)
from amazon_parse import (
    parse_hdp_invite_api_fields,
    parse_product_page,
    parse_search_page,
)

# When the UI leaves the Amazon-side query empty: generic « pokemon » rarely shows the
# « Disponible sur invitation » badge in result cards; TCG-oriented wording works reliably.
DEFAULT_INVITE_SEARCH_QUERY = "pokemon cartes"
# Sold-by-Amazon.fr (invite-only Pokémon TCG is mostly on this seller).
AMAZON_FR_SELLER_RH = "p_6%3AA1X6FK5RDHNB96"


def _normalize_amazon_search_query(q: str) -> str:
    """Lowercase, strip accents, normalize spaces (same logic as the frontend)."""
    t = (q or "").strip()
    if not t:
        return ""
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _query_already_pokemon_scoped(n: str) -> bool:
    """True when the user already included Pokémon / cartes — do not prefix again."""
    return "pokemon" in n or "carte" in n


def _effective_invite_search_query(q: str) -> str:
    """
    Build the Amazon search string from the toolbar input.

    - Empty → default TCG browse query.
    - ``30`` → ``pokemon 30`` (not a longer auto-query).
    - ``pokemon 30`` → unchanged (never ``pokemon pokemon 30``).
    - Other text without Pokémon/cartes → single ``pokemon …`` prefix.
    """
    n = _normalize_amazon_search_query(q)
    if not n:
        return DEFAULT_INVITE_SEARCH_QUERY
    if _query_already_pokemon_scoped(n):
        return n
    return f"pokemon {n}"


def _title_matches_user_filter(title: str, user_q: str) -> bool:
    """Match UI search intent on product titles (e.g. ``30`` → 30e / anniversaire)."""
    u = _normalize_amazon_search_query(user_q)
    if not u:
        return True
    hay = _normalize_amazon_search_query(title)
    if u in ("30", "30e", "30eme") or u == "30":
        return "30" in hay or "anniversaire" in hay
    if u.isdigit():
        return u in hay
    if u in hay:
        return True
    parts = [p for p in u.split() if len(p) >= 2]
    return bool(parts) and all(p in hay for p in parts)


class AmazonScraper:
    def __init__(self, debug_mode=False, chromedriver_path=None):
        self.base_url = AMAZON_BASE_URL
        self.is_logged_in = False
        self.debug_mode = debug_mode
        self._http_client: Optional[httpx.Client] = None
        self._http_lock = threading.Lock()
        # Legacy Selenium chromedriver arg — ignored by nodriver; use AMAZON_CHROME_EXECUTABLE
        _ = chromedriver_path

    def _profile_dir(self) -> str:
        return amazon_config.AMAZON_USER_DATA_DIR

    def _cookies_path(self) -> str:
        return amazon_config.AMAZON_COOKIES_EXPORT_FILE

    def close_selenium(self):
        """Backward compat: close the browser."""
        self.close_browser()

    def close_browser(self):
        with self._http_lock:
            if self._http_client is not None:
                try:
                    self._http_client.close()
                except Exception:
                    pass
                self._http_client = None
        close_browser_sync()

    def _chromium_cookie_db_exists(self) -> bool:
        p1 = os.path.join(self._profile_dir(), "Default", "Network", "Cookies")
        p2 = os.path.join(self._profile_dir(), "Default", "Cookies")
        return os.path.isfile(p1) or os.path.isfile(p2)

    def _has_persisted_amazon_cookies(self) -> bool:
        cookies_path = self._cookies_path()
        if os.path.isfile(cookies_path):
            try:
                if os.path.getsize(cookies_path) > 30:
                    return True
            except OSError:
                pass
        return self._chromium_cookie_db_exists()

    def _invalidate_http(self) -> None:
        with self._http_lock:
            if self._http_client is not None:
                try:
                    self._http_client.close()
                except Exception:
                    pass
                self._http_client = None

    def _build_fresh_http_client(self) -> httpx.Client:
        c = cookies_from_legacy_json_export(self._cookies_path())
        if c is not None:
            print("   [http] Session: JSON cookie file")
            return c

        c = cookies_from_chromium_profile(self._profile_dir())
        if c is not None:
            print("   [http] Session: Chromium profile cookies (SQLite)")
            return c

        det = detect_amazon_session_from_profile(Path(self._profile_dir()))
        if det != "ready":
            print(
                "   [http] Profil non connecté — pas d'export CDP (connexion auto / manuelle requise)"
            )
            return httpx.Client(
                headers=DEFAULT_HEADERS,
                follow_redirects=True,
                timeout=30.0,
            )

        print("   [http] Session: nodriver CDP export (Chrome may open)...")
        try:
            ck = run_browser(export_cookies_requests_format())
            return nodriver_cookies_to_client(ck)
        except Exception as e:
            print(f"   [warn] Direct CDP export: {e}")

        ck = run_browser(prime_session_and_export_cookies_async())
        return nodriver_cookies_to_client(ck)

    def _get_http_client(self) -> httpx.Client:
        with self._http_lock:
            if self._http_client is None:
                self._http_client = self._build_fresh_http_client()
            return self._http_client

    def _fetch_html(self, url: str) -> str:
        client = self._get_http_client()
        try:
            html = fetch_html_http(client, url)
            if not looks_like_blocked_or_bot(html):
                return html
            print("   [warn] Suspicious HTTP response (bot / short page) - browser fallback")
        except Exception as e:
            print(f"   [warn] HTTP: {e} - browser fallback")

        return run_browser(fetch_html_via_tab(url))

    def login_to_amazon(self) -> Dict:
        try:
            self._invalidate_http()
            result = nodriver_login_session()
            self._invalidate_http()
            if result.get("success"):
                self.is_logged_in = True
            else:
                self.is_logged_in = False
            return result
        except Exception as e:
            return {"success": False, "message": str(e)}

    def check_login_status(self) -> Dict:
        cookies_exist = (
            os.path.exists(self._cookies_path()) or self._chromium_cookie_db_exists()
        )
        cookie_json_ok = False
        cookies_path = self._cookies_path()
        if os.path.isfile(cookies_path):
            try:
                cookie_json_ok = os.path.getsize(cookies_path) > 30
            except OSError:
                cookie_json_ok = False

        if self.is_logged_in and not cookies_exist:
            self.is_logged_in = False

        # JSON exported by nodriver after login: reflects state even if the flag was lost (reload, etc.)
        if cookie_json_ok:
            self.is_logged_in = True

        return {
            "is_logged_in": self.is_logged_in,
            "cookies_exist": cookies_exist,
            "user_data_dir": self._profile_dir(),
        }

    def logout_amazon(self) -> Dict:
        """Ferme Chrome, supprime cookies export JSON + SQLite du profil Chromium."""
        self.is_logged_in = False
        self._invalidate_http()
        close_browser_sync()

        removed_json = False
        try:
            cookies_path = self._cookies_path()
            if os.path.isfile(cookies_path):
                os.remove(cookies_path)
                removed_json = True
        except OSError as e:
            print(f"   [warn] Could not remove cookies export: {e}")

        for rel in ("Default/Network/Cookies", "Default/Cookies"):
            p = os.path.join(self._profile_dir(), rel)
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except OSError as e:
                print(f"   [warn] SQLite cookie delete {p}: {e}")

        return {
            "success": True,
            "message": "Signed out.",
            "removed_json": removed_json,
        }

    def _scan_search_pages_for_invites(
        self,
        amazon_query: str,
        max_pages: int,
        item_cap: int | None,
        title_filter: str,
        progress_callback,
        into: List[Dict],
        seen_asins: set[str],
    ) -> None:
        for page in range(1, max_pages + 1):
            if item_cap is not None and len(into) >= item_cap:
                return

            print(f"[page] {page}/{max_pages}...")

            if progress_callback:
                progress_callback(
                    current_page=page,
                    total_pages=max_pages,
                    items_found=len(into),
                    status="searching",
                    message=f"Searching page {page}/{max_pages}...",
                )
                time.sleep(0.1)

            k_enc = quote_plus(amazon_query)
            if page == 1:
                full_url = (
                    f"{self.base_url}/s?k={k_enc}"
                    f"&__mk_fr_FR=%C3%85M%C3%85%C5%BD%C3%95%C3%91"
                    f"&rh={AMAZON_FR_SELLER_RH}&s=date-desc-rank"
                )
            else:
                full_url = (
                    f"{self.base_url}/s?k={k_enc}"
                    f"&__mk_fr_FR=%C3%85M%C3%85%C5%BD%C3%95%C3%91"
                    f"&rh={AMAZON_FR_SELLER_RH}&s=date-desc-rank&page={page}"
                )

            print(f"   URL: {full_url}")

            try:
                page_source = self._fetch_html(full_url)

                if self.debug_mode:
                    debug_file = f"debug_page_{page}.html"
                    with open(debug_file, "w", encoding="utf-8") as f:
                        f.write(page_source)
                    print(f"   [debug] HTML -> {debug_file}")

                soup = BeautifulSoup(page_source, "html.parser")
                page_items = parse_search_page(soup, self.base_url)
                print(f"   {len(page_items)} invite-only items on this page")

                if not page_items and not soup.find_all(
                    "div", {"data-component-type": "s-search-result"}
                ):
                    print(f"   [warn] No result blocks - stopping")
                    break

                added: List[Dict] = []
                for row in page_items:
                    if item_cap is not None and len(into) >= item_cap:
                        break
                    title = str(row.get("title") or "")
                    if title_filter and not _title_matches_user_filter(title, title_filter):
                        continue
                    asin = str(row.get("asin") or "").strip().upper()
                    if not asin or asin in seen_asins:
                        continue
                    seen_asins.add(asin)
                    into.append(row)
                    added.append(row)

                if progress_callback:
                    progress_callback(
                        current_page=page,
                        total_pages=max_pages,
                        items_found=len(into),
                        status="page_done",
                        message=(
                            f"Page {page}/{max_pages}: +{len(added)} invite-only on this page "
                            f"(total {len(into)})"
                        ),
                    )
                    for row in added:
                        progress_callback(
                            current_page=page,
                            total_pages=max_pages,
                            items_found=len(into),
                            status="item_found",
                            message=f"Trouvé : {row.get('title', '')[:120]}",
                            item_data=dict(row),
                        )

                if item_cap is not None and len(into) >= item_cap:
                    return

                if page < max_pages:
                    time.sleep(1)

            except Exception as e:
                print(f"   [err] Page {page} error: {e}")
                import traceback

                traceback.print_exc()
                break

    def search_invitation_items(
        self,
        query: str,
        max_pages: int = 10,
        progress_callback=None,
        max_items: int | None = None,
    ) -> List[Dict]:
        all_items: List[Dict] = []
        seen_asins: set[str] = set()

        user_filter = _normalize_amazon_search_query(query)
        amazon_q = _effective_invite_search_query(query)
        item_cap: int | None = None
        if max_items is not None and int(max_items) > 0:
            item_cap = min(500, int(max_items))

        print(f"\n{'='*60}")
        cap_note = f", max {item_cap} items" if item_cap else ""
        print(f"[search] '{amazon_q}' - up to {max_pages} pages{cap_note} (HTTP + nodriver if needed)")
        if user_filter:
            print(f"[search] title filter: '{user_filter}'")
        print(f"{'='*60}\n")

        if progress_callback:
            progress_callback(
                current_page=0,
                total_pages=max_pages,
                items_found=0,
                status="starting",
                message=f"Starting search for '{amazon_q}' (up to {max_pages} pages)...",
            )

        self._scan_search_pages_for_invites(
            amazon_q, max_pages, item_cap, "", progress_callback, all_items, seen_asins
        )

        if user_filter and (not all_items or (item_cap is not None and len(all_items) < item_cap)):
            print(
                f"[search] Fallback '{DEFAULT_INVITE_SEARCH_QUERY}' + title filter '{user_filter}'"
            )
            if progress_callback:
                progress_callback(
                    current_page=0,
                    total_pages=max_pages,
                    items_found=len(all_items),
                    status="starting",
                    message=f"Recherche élargie + filtre « {user_filter} »…",
                )
            self._scan_search_pages_for_invites(
                DEFAULT_INVITE_SEARCH_QUERY,
                max_pages,
                item_cap,
                user_filter,
                progress_callback,
                all_items,
                seen_asins,
            )

        print(f"\n{'='*60}")
        print(f"[result] {len(all_items)} invite-only items")
        print(f"{'='*60}\n")

        if progress_callback:
            progress_callback(
                current_page=max_pages,
                total_pages=max_pages,
                items_found=len(all_items),
                status="search_done",
                message=f"Search finished: {len(all_items)} invite-only product(s).",
            )

        return all_items

    def check_invitation_status(
        self, asins: List[str], progress_callback=None
    ) -> List[Dict]:
        results: List[Dict] = []

        print(f"\n{'='*60}")
        print(f"[check] {len(asins)} ASIN(s) (HTTP preferred)")
        print(f"{'='*60}\n")

        for i, asin in enumerate(asins):
            print(f"[item] {i+1}/{len(asins)}: {asin}")

            if progress_callback:
                progress_callback(
                    current_page=i + 1,
                    total_pages=len(asins),
                    items_found=len(results),
                    status="checking",
                    message=f"Checking item {i+1}/{len(asins)}...",
                )

            try:
                url = f"{self.base_url}/dp/{asin}"
                page_source = self._fetch_html(url)

                item_data = parse_product_page(page_source, asin, self.base_url)
                if item_data is None:
                    print("   [warn] Item skipped (not invite sale / filtered out)")
                    continue

                results.append(item_data)

                st = item_data.get("invitation_status")
                can = item_data.get("can_order")
                print(f"   Status: {st} | Cart: {'yes' if can else 'no'}")

                if progress_callback:
                    progress_callback(
                        current_page=i + 1,
                        total_pages=len(asins),
                        items_found=len(results),
                        status="checking",
                        message=f"Checking item {i+1}/{len(asins)}...",
                        item_data=item_data,
                    )

                if i < len(asins) - 1:
                    time.sleep(0.2)

            except Exception as e:
                print(f"   [err] Error: {e}")
                import traceback

                traceback.print_exc()
                continue

        commandable = [x for x in results if x.get("can_order")]
        print(f"\n{'='*60}")
        print(f"[total] {len(results)} - Orderable: {len(commandable)}")
        print(f"{'='*60}\n")
        return results

    def request_invitation_for_asin(self, asin: str) -> Dict:
        """
        Using the Amazon session (cookies): load /dp, POST ``request-invite`` like the
        « Request invitation » button on Amazon.
        """
        t = (asin or "").strip().upper()
        if not re.match(r"^[A-Z0-9]{10}$", t):
            return {"success": False, "message": "Invalid ASIN."}

        if not self._has_persisted_amazon_cookies():
            return {
                "success": False,
                "message": "No Amazon session. Sign in via the app first.",
            }

        dp_url = f"{self.base_url}/dp/{t}"
        try:
            page_source = self._fetch_html(dp_url)
        except Exception as e:
            return {"success": False, "message": f"Could not load product page: {e}"}

        preview = parse_product_page(page_source, t, self.base_url)
        if preview is None:
            return {
                "success": False,
                "message": "Product not eligible or page not recognized.",
            }
        if preview.get("can_order"):
            return {
                "success": False,
                "message": "This product is already orderable; no invitation to request.",
            }
        st = preview.get("invitation_status")
        if st != "not_requested":
            return {
                "success": False,
                "message": "Invitation already recorded or status changed.",
            }

        fields = parse_hdp_invite_api_fields(page_source)
        if not fields:
            return {
                "success": False,
                "message": "Invitation button not found (Amazon may have changed the page).",
            }
        if fields.get("signed_in_flag") is False:
            return {
                "success": False,
                "message": "Amazon reports you are not signed in. Sign in again.",
            }

        client = self._get_http_client()
        try:
            r = post_hdp_request_invite(
                client,
                post_url=fields["post_url"],
                csrf_token=fields["csrf"],
                slate_token=fields.get("slate_token"),
                referer_dp_url=dp_url,
                origin_base=self.base_url,
            )
        except Exception as e:
            return {"success": False, "message": str(e)}

        if r.status_code >= 400:
            detail = (r.text or "")[:500]
            return {
                "success": False,
                "message": f"Amazon refused (HTTP {r.status_code}). {detail}",
            }

        try:
            page2 = self._fetch_html(dp_url)
            item2 = parse_product_page(page2, t, self.base_url)
        except Exception:
            item2 = None
        if item2 is None:
            item2 = dict(preview)
            item2["invitation_status"] = "requested"
            item2["invitation_requested"] = True

        return {
            "success": True,
            "message": "Invitation requested.",
            "item": item2,
        }
