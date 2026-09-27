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
    click_request_invite_async,
    close_browser_sync,
    export_cookies_requests_format,
    fetch_html_via_tab,
    fetch_product_page_via_tab,
    login_to_amazon as nodriver_login_session,
    prime_session_and_export_cookies_async,
    run_browser,
    session_state_via_browser_async,
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


def _status_from_visible_state(state: Dict) -> Optional[str]:
    """Statut d'invitation d'après ce que Chrome affiche réellement ; ``None`` si l'état n'est pas lisible."""
    if not state:
        return None
    if state.get("signedIn") == "false":
        return "needs_login"
    if state.get("cart"):
        return "accepted"
    if state.get("inviteButton") or state.get("inviteText"):
        return "not_requested"
    if state.get("requestedBlock") or state.get("requestedText"):
        return "requested"
    return None


def _apply_visible_state(item: Dict, state: Dict) -> Dict:
    """Aligne un item parsé sur l'état visible du widget (autorité quand la fiche est lue dans Chrome)."""
    st = _status_from_visible_state(state)
    if st:
        item["invitation_status"] = st
        item["invitation_requested"] = st in ("accepted", "requested")
        item["can_order"] = st == "accepted"
    return item


# Mots qui ne départagent aucun produit : la recherche vise déjà le JCC Pokémon.
_GENERIC_QUERY_WORDS = frozenset(
    {
        "pokemon", "jcc", "tcg", "jeu", "jeux", "carte", "cartes", "collectionner",
        "de", "du", "des", "la", "le", "les", "et", "en", "au", "aux", "un", "une",
        "pour", "avec", "sur", "the", "of", "and",
    }
)
# Ordinal collé au nombre : « 30e », « 30eme », « 1er », « 1re », « 30th »…
_ORDINAL_NUMBER_RE = re.compile(r"^(\d+)(?:e|eme|er|ere|re|th|st|nd|rd)$")


def _split_search_words(text: str) -> List[str]:
    """
    Découpe un titre ou une requête en mots sans accents ni majuscules, « 30ᵉ » et « 30e » lus « 30 ».

    Args:
        text: Titre produit ou requête saisie.

    Returns:
        Les mots, dans l'ordre du texte.
    """
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char)).lower()
    normalized = normalized.replace("œ", "oe").replace("æ", "ae")
    words: List[str] = []
    for word in re.split(r"[^0-9a-z]+", normalized):
        if word:
            ordinal = _ORDINAL_NUMBER_RE.match(word)
            words.append(ordinal.group(1) if ordinal else word)
    return words


def _significant_query_words(query: str) -> List[str]:
    """
    Mots de la requête capables de départager des titres (sans doublons ni mots génériques).

    Args:
        query: Requête envoyée à Amazon.

    Returns:
        Les mots retenus, dans l'ordre de saisie.
    """
    significant_words: List[str] = []
    for word in _split_search_words(query):
        if word in _GENERIC_QUERY_WORDS or (len(word) < 2 and not word.isdigit()):
            continue
        if word not in significant_words:
            significant_words.append(word)
    return significant_words


def _title_contains_query_word(title_words: List[str], query_word: str) -> bool:
    """
    Un nombre doit figurer tel quel ; un mot peut être le début d'un mot du titre (« pika » trouve « pikachu »).

    Args:
        title_words: Mots du titre.
        query_word: Mot de la requête.

    Returns:
        ``True`` si le titre contient ce mot.
    """
    if query_word.isdigit():
        return query_word in title_words
    prefixes = {query_word}
    if len(query_word) > 3 and query_word[-1] in "sx":
        prefixes.add(query_word[:-1])  # pluriel : « boites » trouve « boite »
    return any(title_word.startswith(prefix) for title_word in title_words for prefix in prefixes)


def _select_best_title_matches(rows: List[Dict], query: str) -> List[Dict]:
    """
    Garde, dans l'ordre Amazon, les produits dont le titre reprend le plus de mots de la requête (tous si aucun titre ne correspond).

    Args:
        rows: Produits sur invitation, dans l'ordre des résultats Amazon.
        query: Requête envoyée à Amazon.

    Returns:
        Les produits retenus, ordre Amazon conservé.
    """
    query_words = _significant_query_words(query)
    if not query_words:
        return list(rows)
    scored_rows: List[tuple[int, Dict]] = []
    for row in rows:
        title_words = _split_search_words(str(row.get("title") or ""))
        score = sum(1 for word in query_words if _title_contains_query_word(title_words, word))
        scored_rows.append((score, row))
    best_score = max((score for score, _ in scored_rows), default=0)
    if best_score == 0:
        return list(rows)
    return [row for score, row in scored_rows if score == best_score]


class AmazonScraper:
    def __init__(self, debug_mode=False, chromedriver_path=None, prefer_browser: bool = False):
        self.base_url = AMAZON_BASE_URL
        self.is_logged_in = False
        self.debug_mode = debug_mode
        self._http_client: Optional[httpx.Client] = None
        self._http_lock = threading.Lock()
        # Lit chaque page via l'onglet Chrome du profil lié : compte toujours connecté, aucun cookie à extraire.
        self.prefer_browser = prefer_browser
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
        if self.prefer_browser:
            return run_browser(fetch_html_via_tab(url))
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

    def _build_invite_search_url(self, amazon_query: str, page: int) -> str:
        """
        URL d'une page de résultats Amazon.fr limitée aux produits vendus par Amazon.

        Args:
            amazon_query: Requête envoyée à Amazon.
            page: Numéro de page de résultats (1 = première).

        Returns:
            L'URL de la page de résultats.
        """
        # Tri pertinence comme dans le navigateur : « Nouveautés » (s=date-desc-rank) masque une partie des produits sur invitation.
        url = (
            f"{self.base_url}/s?k={quote_plus(amazon_query)}"
            f"&__mk_fr_FR=%C3%85M%C3%85%C5%BD%C3%95%C3%91"
            f"&rh={AMAZON_FR_SELLER_RH}"
        )
        return url if page == 1 else f"{url}&page={page}"

    def _scan_search_pages_for_invites(
        self,
        amazon_query: str,
        max_pages: int,
        item_cap: int | None,
        progress_callback,
    ) -> List[Dict]:
        """
        Lit les pages de résultats et garde les produits sur invitation qui correspondent le mieux à la requête.

        Args:
            amazon_query: Requête envoyée à Amazon.
            max_pages: Nombre maximum de pages de résultats à lire.
            item_cap: Nombre maximum de produits à renvoyer (``None`` = pas de limite).
            progress_callback: Rappel de progression du worker (optionnel).

        Returns:
            Les produits retenus, dans l'ordre Amazon.
        """
        invite_rows: List[Dict] = []
        seen_asins: set[str] = set()
        streamed_asins: set[str] = set()
        matching_rows: List[Dict] = []
        pages_without_new_invites = 0

        for page in range(1, max_pages + 1):
            print(f"[page] {page}/{max_pages}...")

            if progress_callback:
                progress_callback(
                    current_page=page,
                    total_pages=max_pages,
                    items_found=len(matching_rows),
                    status="searching",
                    message=f"Searching page {page}/{max_pages}...",
                )
                time.sleep(0.1)

            full_url = self._build_invite_search_url(amazon_query, page)
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

                new_invite_count = 0
                for row in page_items:
                    asin = str(row.get("asin") or "").strip().upper()
                    if not asin or asin in seen_asins:
                        continue
                    seen_asins.add(asin)
                    invite_rows.append(row)
                    new_invite_count += 1

                matching_rows = _select_best_title_matches(invite_rows, amazon_query)
                if item_cap is not None:
                    matching_rows = matching_rows[:item_cap]

                if progress_callback:
                    progress_callback(
                        current_page=page,
                        total_pages=max_pages,
                        items_found=len(matching_rows),
                        status="page_done",
                        message=(
                            f"Page {page}/{max_pages}: +{new_invite_count} invite-only on this page, "
                            f"{len(matching_rows)} matching the search"
                        ),
                    )
                    for row in matching_rows:
                        asin = str(row.get("asin") or "").strip().upper()
                        if asin in streamed_asins:
                            continue
                        streamed_asins.add(asin)
                        progress_callback(
                            current_page=page,
                            total_pages=max_pages,
                            items_found=len(matching_rows),
                            status="item_found",
                            message=f"Trouvé : {row.get('title', '')[:120]}",
                            item_data=dict(row),
                        )

                if item_cap is not None and len(matching_rows) >= item_cap:
                    break
                if not soup.find_all("div", {"data-component-type": "s-search-result"}):
                    print("   [warn] No result blocks - stopping")
                    break
                pages_without_new_invites = 0 if new_invite_count else pages_without_new_invites + 1
                # En tri pertinence, les produits sur invitation arrivent en tête des résultats.
                if pages_without_new_invites >= (1 if invite_rows else 2):
                    print("   No new invite-only items - stopping")
                    break

                if page < max_pages:
                    time.sleep(1)

            except Exception as e:
                print(f"   [err] Page {page} error: {e}")
                import traceback

                traceback.print_exc()
                break

        return matching_rows

    def search_invitation_items(
        self,
        query: str,
        max_pages: int = 10,
        progress_callback=None,
        max_items: int | None = None,
    ) -> List[Dict]:
        amazon_q = _effective_invite_search_query(query)
        item_cap: int | None = None
        if max_items is not None and int(max_items) > 0:
            item_cap = min(500, int(max_items))

        print(f"\n{'='*60}")
        cap_note = f", max {item_cap} items" if item_cap else ""
        print(
            f"[search] '{amazon_q}' - up to {max_pages} pages{cap_note} "
            f"(HTTP + nodriver if needed)"
        )
        print(f"{'='*60}\n")

        if progress_callback:
            progress_callback(
                current_page=0,
                total_pages=max_pages,
                items_found=0,
                status="starting",
                message=f"Recherche Amazon « {amazon_q} » (jusqu’à {max_pages} pages)…",
            )

        # La requête part telle quelle sur Amazon : lui seul sait que « 30 ans » désigne les titres « 30ᵉ Anniversaire ».
        all_items = self._scan_search_pages_for_invites(
            amazon_q, max_pages, item_cap, progress_callback
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
                visible_state: Dict = {}
                if self.prefer_browser:
                    fetched = run_browser(fetch_product_page_via_tab(url))
                    page_source = str(fetched.get("html") or "")
                    visible_state = dict(fetched.get("state") or {})
                else:
                    page_source = self._fetch_html(url)

                item_data = parse_product_page(page_source, asin, self.base_url)
                if item_data is None:
                    print("   [warn] Item skipped (not invite sale / filtered out)")
                    continue
                item_data = _apply_visible_state(item_data, visible_state)

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
        if st == "needs_login":
            return {
                "success": False,
                "message": "Ce compte n'est pas connecté à Amazon sur ce PC. Reconnectez-le puis réessayez.",
            }
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
        if item2 is not None and item2.get("invitation_status") == "needs_login":
            return {
                "success": False,
                "message": "Session Amazon perdue pendant la demande. Reconnectez ce compte puis réessayez.",
            }
        if item2 is None or item2.get("invitation_status") == "unknown":
            # Amazon a accepté le POST mais la relecture de la fiche ne le confirme pas :
            # on ne fabrique pas « demandée », on laisse le statut à revérifier.
            item2 = dict(preview)
            item2["invitation_status"] = "unknown"
            item2["invitation_requested"] = False
            return {
                "success": True,
                "message": "Demande envoyée, statut à revérifier (fiche non confirmée).",
                "item": item2,
            }

        return {
            "success": True,
            "message": "Invitation requested.",
            "item": item2,
        }

    def session_state_via_browser(self) -> str:
        """« ready » / « needs_login » d'après le message d'accueil, lu dans le Chrome du profil lié."""
        return run_browser(session_state_via_browser_async(), timeout=120)

    def request_invitation_via_browser(self, asin: str) -> Dict:
        """Demande l'invitation en cliquant le bouton dans le Chrome du profil lié (compte connecté requis)."""
        t = (asin or "").strip().upper()
        if not re.match(r"^[A-Z0-9]{10}$", t):
            return {"success": False, "message": "Invalid ASIN."}
        dp_url = f"{self.base_url}/dp/{t}"
        try:
            res = run_browser(click_request_invite_async(dp_url), timeout=180)
        except Exception as e:
            return {"success": False, "message": f"Chrome : {e}"}

        before = parse_product_page(str(res.get("html_before") or ""), t, self.base_url)
        if before is not None:
            before = _apply_visible_state(before, dict(res.get("state_before") or {}))
        st_before = _status_from_visible_state(dict(res.get("state_before") or {})) or (
            before.get("invitation_status") if before else None
        )
        if st_before == "accepted":
            return {
                "success": False,
                "message": "This product is already orderable; no invitation to request.",
            }
        if st_before == "requested":
            return {"success": False, "message": "Invitation already recorded or status changed."}
        if st_before == "needs_login":
            return {
                "success": False,
                "message": "Ce compte n'est pas connecté à Amazon dans Chrome. Reconnectez-le puis réessayez.",
            }
        if not res.get("clicked"):
            return {
                "success": False,
                "message": "Invitation button not found (Amazon may have changed the page).",
            }

        state_after = dict(res.get("state_after") or {})
        after = parse_product_page(str(res.get("html_after") or ""), t, self.base_url)
        # Confirmation : bloc « demandée » visible après le clic (même si le bouton reste affiché un instant).
        confirmed = bool(state_after.get("requestedBlock") or state_after.get("requestedText")) or (
            after is not None and after.get("invitation_status") == "requested"
        )
        if confirmed:
            item = dict(after or before or {"asin": t, "title": "Product", "url": dp_url})
            item["invitation_status"] = "requested"
            item["invitation_requested"] = True
            return {"success": True, "message": "Invitation requested.", "item": item}
        item = dict(after or before or {"asin": t, "title": "Product", "url": dp_url})
        item["invitation_status"] = "unknown"
        item["invitation_requested"] = False
        return {
            "success": True,
            "message": "Bouton cliqué, statut à revérifier (fiche non confirmée).",
            "item": item,
        }
