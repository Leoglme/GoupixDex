"""Vinted UI automation using nodriver (Chrome DevTools Protocol)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Optional

import nodriver as uc
from nodriver import Element

from app_types.payload import ItemPayload
from app_types.vinted import VintedPackageSize
from config import get_settings
from services.os_service import get_project_root
from services.timer_service import TimerService

if TYPE_CHECKING:
    from nodriver import Browser, Tab

logger = logging.getLogger(__name__)

# Callback SSE : dict avec au moins ``type``, ``message`` ; champs optionnels ``form_step``, ``detail``.
FormProgressFn = Callable[[dict[str, Any]], Awaitable[None]]


def _parse_eval_dict_result(raw: Any, *, context: str = "") -> dict[str, Any]:
    """
    nodriver renvoie souvent un ``RemoteObject`` pour les objets JS au lieu d'un dict.
    Préférer ``return JSON.stringify({...})`` côté page ; ce helper accepte dict, str JSON,
    ou une reconstruction minimale depuis ``RemoteObject.deep_serialized_value``.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        raise TypeError(f"JSON root is not an object (context={context})")
    ds = getattr(raw, "deep_serialized_value", None)
    val = getattr(ds, "value", None) if ds is not None else None
    if isinstance(val, list):
        try:
            return _remote_deep_value_to_dict(val)
        except Exception:  # noqa: BLE001
            pass
    logger.error("Évaluation JS inutilisable (%s): %r", context, raw)
    raise TypeError(f"Unexpected evaluate result: {type(raw).__name__}")


def _remote_deep_value_to_dict(val: Any) -> dict[str, Any]:
    """Reconstruit un dict depuis la structure ``DeepSerializedValue.value`` (liste de paires)."""
    if isinstance(val, dict):
        return val
    if not isinstance(val, list):
        raise TypeError("expected list of pairs")
    out: dict[str, Any] = {}
    for pair in val:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        key, typed = pair[0], pair[1]
        if not isinstance(typed, dict) or "value" not in typed:
            continue
        out[str(key)] = typed["value"]
    return out

# Auth entry (same path as header "S'inscrire | Se connecter"); Vinted may not redirect from home anymore.
VINTED_MEMBER_AUTH_URL = "https://www.vinted.fr/member/signup/select_type?ref_url=%2F"

# URL substrings that mean the user is still in the login / signup flow (not "connected").
_AUTH_FLOW_URL_MARKERS: tuple[str, ...] = (
    "select_type",
    "/member/signup",
    "/member/session",
    "/member/login",
)

def _normalize_vinted_label(text: str) -> str:
    """Aligne apostrophes typographiques / ASCII pour matcher le DOM Vinted."""
    return (
        (text or "")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("`", "'")
        .strip()
    )


def _build_browser_args(*, headless: bool) -> list[str]:
    """Flags communs ; en headless (prod VPS) on évite --start-maximized et on renforce la stabilité serveur."""
    base: list[str] = [
        "--no-sandbox",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
    ]
    if headless:
        base.extend(
            [
                "--window-size=1920,1080",
                "--disable-dev-shm-usage",
            ]
        )
    else:
        base.append("--start-maximized")
    return base


class VintedService:
    """
    Static-style service mirroring the previous TypeScript class: one browser, one tab.

    Launches Chrome via nodriver, navigates Vinted, fills listing fields, uploads photos,
    and can publish listings.
    """

    _browser: Optional[Browser] = None
    _tab: Optional[Tab] = None
    _VINTED_TIMEOUT_MS: int = 350

    @classmethod
    async def init_browser(cls) -> None:
        """
        Start the Chromium-based browser with flags aimed at fewer automation signals.

        Returns:
            None

        Raises:
            RuntimeError: If the browser failed to start.
        """
        settings = get_settings()
        headless = settings.vinted_browser_headless
        start_kw: dict[str, Any] = {
            "headless": headless,
            "browser_args": _build_browser_args(headless=headless),
            "sandbox": False,
        }
        if settings.vinted_chrome_executable:
            start_kw["browser_executable_path"] = settings.vinted_chrome_executable.strip()
        cls._browser = await uc.start(**start_kw)
        if cls._browser is None:
            raise RuntimeError("nodriver.start() returned no browser instance")

    @classmethod
    async def init_page(cls) -> None:
        """
        Attach the main tab (first ``page`` target) and open a blank document.

        Returns:
            None

        Raises:
            RuntimeError: If ``init_browser`` was not called first.
        """
        if cls._browser is None:
            raise RuntimeError("Call init_browser() before init_page()")
        cls._tab = await cls._browser.get("about:blank")

    @classmethod
    def close_browser(cls) -> None:
        """
        Ferme le processus Chrome lancé par ``init_browser`` et réinitialise l'état du service.

        À appeler en ``finally`` après une session d'automation (succès ou erreur).
        """
        if cls._browser is None:
            return
        try:
            cls._browser.stop()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fermeture du navigateur Vinted : %s", exc)
        finally:
            cls._browser = None
            cls._tab = None

    @classmethod
    def _require_tab(cls) -> Tab:
        if cls._tab is None:
            raise RuntimeError("Tab is not initialized; call init_page() first")
        return cls._tab

    @classmethod
    def _url_is_auth_flow(cls, url: str) -> bool:
        """Return True if the location is still a Vinted login/sign-up route."""
        u = (url or "").lower()
        return any(marker in u for marker in _AUTH_FLOW_URL_MARKERS)

    @classmethod
    async def _header_guest_login_button_visible(cls, tab: Tab) -> bool:
        """True when the main header still shows S'inscrire | Se connecter (guest)."""
        val = await tab.evaluate(
            """
            (() => {
                const b = document.querySelector('[data-testid="header--login-button"]');
                if (!b) return false;
                const cs = window.getComputedStyle(b);
                if (cs.display === 'none' || cs.visibility === 'hidden') return false;
                const r = b.getBoundingClientRect();
                return r.width > 2 && r.height > 2;
            })()
            """,
            return_by_value=True,
        )
        return val is True

    @classmethod
    async def _scroll_page_top(cls, tab: Tab) -> None:
        """Scroll the document to the top (auth redirects often land scrolled down)."""
        await tab.evaluate(
            "window.scrollTo({ top: 0, left: 0, behavior: 'instant' })",
            return_by_value=False,
        )
        await tab.evaluate(
            "document.documentElement.scrollTop = 0; document.body && (document.body.scrollTop = 0);",
            return_by_value=False,
        )
        await tab.sleep(0.05)

    @classmethod
    async def _scroll_selector_into_view(cls, css_selector: str) -> None:
        """Centre le formulaire sur un champ pour limiter les clics hors cible après reflow."""
        tab = cls._require_tab()
        await tab
        sel_json = json.dumps(css_selector)
        await tab.evaluate(
            f"""
            (() => {{
                const el = document.querySelector({sel_json});
                if (el) {{
                    el.scrollIntoView({{ block: 'center', behavior: 'instant' }});
                }}
            }})()
            """,
            return_by_value=False,
        )
        await tab.sleep(0.12)

    @classmethod
    async def _catalog_debug_probe(cls) -> None:
        """Logs JSON décrivant le DOM catalogue (panneaux, titres, URL) pour diagnostiquer les échecs."""
        tab = cls._require_tab()
        await tab
        probe = await tab.evaluate(
            """
            (() => {
                const mark = (p) => {
                    let s = 0;
                    if (p.querySelector('#catalog-search-input')) s += 25;
                    s += p.querySelectorAll('[id^="catalog-"]').length * 2;
                    if (p.querySelector('[data-testid="catalog-navigation"]')) s += 8;
                    s += p.querySelectorAll('li.web_ui__Item__item').length;
                    return s;
                };
                const panels = Array.from(document.querySelectorAll('.input-dropdown__content'));
                const panelInfo = panels.map((p, i) => {
                    const r = p.getBoundingClientRect();
                    return {
                        index: i,
                        mark: mark(p),
                        w: Math.round(r.width),
                        h: Math.round(r.height),
                        titles: Array.from(p.querySelectorAll('li .web_ui__Cell__title'))
                            .slice(0, 12)
                            .map((e) => (e.textContent || '').trim()),
                    };
                });
                const inp = document.querySelector('[data-testid="catalog-select-dropdown-input"]');
                let inputRect = null;
                if (inp) {
                    const r = inp.getBoundingClientRect();
                    inputRect = { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top) };
                }
                const chevron = document.querySelector('[data-testid="catalog-select-dropdown-chevron-down"]');
                return JSON.stringify({
                    href: String(location.href || ''),
                    inputDropdownContentCount: panels.length,
                    panels: panelInfo,
                    catalogInputFound: !!inp,
                    catalogInputRect: inputRect,
                    chevronFound: !!chevron,
                    legacyContent: !!document.querySelector('[data-testid="catalog-select-dropdown-content"]'),
                });
            })()
            """,
            return_by_value=True,
        )
        try:
            parsed = _parse_eval_dict_result(probe, context="catalog_probe")
            logger.warning("Vinted catalog DOM probe: %s", json.dumps(parsed, ensure_ascii=False, default=str))
        except (TypeError, json.JSONDecodeError) as exc:
            logger.warning("Vinted catalog DOM probe (raw): %r err=%s", probe, exc)

    @classmethod
    async def _ensure_catalog_dropdown_open(cls) -> bool:
        """
        Ouvre le sélecteur catégorie (input puis chevron si besoin).
        Retourne True si un panneau catalogue plausible est détecté.
        """
        tab = cls._require_tab()
        await tab
        await cls._scroll_selector_into_view('[data-testid="catalog-select-dropdown-input"]')
        inp = await tab.select('[data-testid="catalog-select-dropdown-input"]', timeout=15)
        if inp is None:
            logger.error("catalog-select-dropdown-input introuvable.")
            return False
        try:
            await inp.click()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Clic input catégorie: %s", exc)
        await tab.sleep(0.35)

        def _panel_ready_js() -> str:
            return """
            (() => {
                const mark = (p) => {
                    let s = 0;
                    if (p.querySelector('#catalog-search-input')) s += 25;
                    s += p.querySelectorAll('[id^="catalog-"]').length * 2;
                    if (p.querySelector('[data-testid="catalog-navigation"]')) s += 8;
                    s += p.querySelectorAll('li.web_ui__Item__item').length;
                    return s;
                };
                const panels = Array.from(document.querySelectorAll('.input-dropdown__content'));
                for (const p of panels) {
                    if (mark(p) <= 0) continue;
                    const n = p.querySelectorAll(
                        'li.web_ui__Item__item .web_ui__Cell__title, [id^="catalog-"] .web_ui__Cell__title'
                    ).length;
                    if (n > 0) return true;
                }
                const legacy = document.querySelector('[data-testid="catalog-select-dropdown-content"]');
                return !!(legacy && legacy.querySelector('li.web_ui__Item__item .web_ui__Cell__title'));
            })()
            """

        for _ in range(120):
            await tab
            ready = await tab.evaluate(_panel_ready_js(), return_by_value=True)
            if ready is True:
                return True
            await asyncio.sleep(0.08)

        logger.info("Panneau catégorie pas prêt après clic input — tentative chevron.")
        clicked = await tab.evaluate(
            """
            (() => {
                const sp = document.querySelector('[data-testid="catalog-select-dropdown-chevron-down"]');
                if (!sp) return false;
                const btn = sp.closest('[role="button"]') || sp.closest('.c-input__icon') || sp.parentElement;
                if (btn && typeof btn.click === 'function') {
                    btn.click();
                    return true;
                }
                return false;
            })()
            """,
            return_by_value=True,
        )
        if clicked is True:
            await tab.sleep(0.4)
            for _ in range(80):
                await tab
                ready = await tab.evaluate(_panel_ready_js(), return_by_value=True)
                if ready is True:
                    return True
                await asyncio.sleep(0.08)

        return False

    @classmethod
    async def _set_input_value_for_react(cls, tab: Tab, css_selector: str, value: str) -> bool:
        """
        Set a controlled input value and dispatch events so React picks it up.

        Args:
            tab: Active tab.
            css_selector: A ``document.querySelector`` selector (e.g. ``input#username``).
            value: Text to set.

        Returns:
            True if an element was found and updated.
        """
        sel_json = json.dumps(css_selector)
        val_json = json.dumps(value)
        ok = await tab.evaluate(
            f"""
            (() => {{
                const sel = {sel_json};
                const el = document.querySelector(sel);
                if (!el) return false;
                el.focus();
                const val = {val_json};
                const proto = Object.getPrototypeOf(el);
                const desc = Object.getOwnPropertyDescriptor(proto, 'value')
                    || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
                if (desc && desc.set) {{
                    desc.set.call(el, val);
                }} else {{
                    el.value = val;
                }}
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }})()
            """,
            return_by_value=True,
        )
        return ok is True

    @classmethod
    async def _accept_onetrust_cookies(cls, tab: Tab, total_timeout_sec: float = 15.0) -> None:
        """
        Click the OneTrust "Accept all" button as soon as it appears.

        Vinted may redirect to login quickly; a long sleep before this call lets the
        banner disappear or the DOM navigate away, so this runs immediately after
        ``get()`` with a tight poll loop.

        Args:
            tab: Active Vinted tab.
            total_timeout_sec: Max time to wait for ``#onetrust-accept-btn-handler``.

        Returns:
            None
        """
        deadline = time.monotonic() + total_timeout_sec
        while time.monotonic() < deadline:
            await tab
            try:
                found = await tab.query_selector("#onetrust-accept-btn-handler")
            except Exception as exc:  # noqa: BLE001
                logger.debug("query_selector cookie button: %s", exc)
                found = None
            if isinstance(found, Element):
                btn = found
                try:
                    await btn.scroll_into_view()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    await btn.click()
                    logger.info("Accepted OneTrust cookies (#onetrust-accept-btn-handler).")
                    await tab.sleep(0.1)
                    return
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Cookie accept click failed, retrying: %s", exc)
            await asyncio.sleep(0.1)

        logger.warning(
            "OneTrust cookie button not found within %ss; continuing without clicking it.",
            total_timeout_sec,
        )

    @classmethod
    async def _try_click_header_login_button(cls, tab: Tab) -> bool:
        """
        Click the header CTA ``S'inscrire | Se connecter`` (same destination as ``VINTED_MEMBER_AUTH_URL``).

        Args:
            tab: Tab showing the Vinted chrome (typically home).

        Returns:
            True if the element was found and clicked.
        """
        await tab
        el = await tab.query_selector('[data-testid="header--login-button"]')
        if not isinstance(el, Element):
            return False
        try:
            await el.scroll_into_view()
            await tab.sleep(0.08)
            await el.click()
            logger.info("Clicked header login button (header--login-button).")
            await tab.sleep(0.25)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Header login click failed: %s", exc)
            return False

    @classmethod
    async def _go_to_member_auth_entry(cls, tab: Tab) -> None:
        """
        Open the member auth flow. Prefer a direct URL; if still on plain home, click the header CTA.

        Args:
            tab: Active tab (already on ``vinted.fr`` after home + cookies is fine).

        Returns:
            None
        """
        await tab.get(VINTED_MEMBER_AUTH_URL)
        await tab
        await tab.sleep(0.15)
        url = (tab.target.url or "").lower()
        if "/member/" in url:
            logger.info("Opened member auth via direct URL.")
            return

        logger.warning(
            "Direct auth URL did not land on /member/ (got %s); trying header button.",
            (tab.target.url or "")[:100],
        )
        await tab.get("https://www.vinted.fr")
        await tab
        if await cls._try_click_header_login_button(tab):
            await tab
            if "/member/" in (tab.target.url or "").lower():
                return

        await tab.get(VINTED_MEMBER_AUTH_URL)
        logger.info("Second navigation to member auth URL.")

    @classmethod
    async def _login_username_field_is_visible(cls, tab: Tab) -> bool:
        """
        True only when the username input is actually shown (not merely in a hidden signup branch).

        Vinted keeps both flows in the DOM; ``query_selector('input[name="username"]')`` alone is not enough.
        """
        val = await tab.evaluate(
            """
            (() => {
                const u = document.querySelector('input[name="username"]');
                if (!u) return false;
                const cs = window.getComputedStyle(u);
                if (cs.display === 'none' || cs.visibility === 'hidden') return false;
                const rect = u.getBoundingClientRect();
                return rect.width > 2 && rect.height > 2;
            })()
            """,
            return_by_value=True,
        )
        return val is True

    @classmethod
    async def _activate_auth_testid_span(cls, tab: Tab, el: Element, testid: str) -> None:
        """Click helpers for ``span[role=button][data-testid=…]`` auth controls."""
        await el.scroll_into_view()
        await tab.sleep(0.03)
        try:
            await el.click()
        except Exception as exc:  # noqa: BLE001
            logger.debug("click %s: %s", testid, exc)
        await tab.sleep(0.03)
        await tab.evaluate(
            f"""
            (() => {{
                const el = document.querySelector('[data-testid="{testid}"]');
                if (!el) return;
                el.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window }}));
            }})()
            """,
            return_by_value=False,
        )
        await tab.sleep(0.02)
        try:
            await el.apply("(e) => { e.focus(); }")
            await el.send_keys(" ")
        except Exception as exc:  # noqa: BLE001
            logger.debug("keyboard %s: %s", testid, exc)

    @classmethod
    async def _activate_se_connecter_switch(cls, tab: Tab, el: Element) -> None:
        """Activate the Se connecter tab switch (same as other auth testid spans)."""
        await cls._activate_auth_testid_span(tab, el, "auth-select-type--register-switch")

    @classmethod
    async def _click_auth_se_connecter_switch(cls, tab: Tab, total_timeout_sec: float = 45.0) -> None:
        """
        On the auth screen, click "Se connecter" to switch from the sign-up panel to the login panel.

        Targets ``span[role=button][data-testid="auth-select-type--register-switch"]``.

        Skips only when the username field is **visible** (login step already active).

        Args:
            tab: Active tab (often already on a ``/member/...`` login URL).
            total_timeout_sec: Max time to wait for the control and for the login panel to appear.

        Returns:
            None
        """
        selector = '[data-testid="auth-select-type--register-switch"]'
        await tab

        if await cls._login_username_field_is_visible(tab):
            logger.info("Login panel already visible; skipping %s.", selector)
            return

        wait_timeout = min(5.0, max(1.2, min(total_timeout_sec, 8.0)))
        el = await tab.select(selector, timeout=wait_timeout)
        if el is None:
            deadline = time.monotonic() + min(total_timeout_sec, 10.0)
            while time.monotonic() < deadline:
                await tab
                el = await tab.query_selector(selector)
                if isinstance(el, Element):
                    break
                await asyncio.sleep(0.05)
            if not isinstance(el, Element):
                logger.warning(
                    "Element %s not found within %ss.",
                    selector,
                    total_timeout_sec,
                )
                return

        await cls._activate_se_connecter_switch(tab, el)
        logger.info("Activated Se connecter (%s).", selector)
        await cls._scroll_page_top(tab)

        settle_deadline = time.monotonic() + 1.5
        while time.monotonic() < settle_deadline:
            await tab
            if await cls._login_username_field_is_visible(tab):
                logger.info("Login username field is now visible.")
                return
            await asyncio.sleep(0.05)

        if not await cls._login_username_field_is_visible(tab):
            logger.warning(
                "Se connecter was activated but username field did not become visible within 1.5s.",
            )

    @classmethod
    async def _click_auth_login_email_option(cls, tab: Tab, total_timeout_sec: float = 12.0) -> None:
        """
        After "Se connecter", choose login with e-mail (``auth-select-type--login-email``).
        """
        testid = "auth-select-type--login-email"
        selector = f'[data-testid="{testid}"]'
        await tab
        if await cls._login_username_field_is_visible(tab):
            logger.info("Username field already visible; skipping e-mail login method picker.")
            return

        wait_timeout = min(5.0, max(1.0, min(total_timeout_sec, 8.0)))
        el = await tab.select(selector, timeout=wait_timeout)
        if el is None:
            deadline = time.monotonic() + min(total_timeout_sec, 10.0)
            while time.monotonic() < deadline:
                await tab
                el = await tab.query_selector(selector)
                if isinstance(el, Element):
                    break
                await asyncio.sleep(0.05)
            if not isinstance(el, Element):
                logger.warning("Login e-mail option %s not found within %ss.", selector, total_timeout_sec)
                return

        await cls._activate_auth_testid_span(tab, el, testid)
        logger.info("Clicked login via e-mail (%s).", selector)
        await cls._scroll_page_top(tab)
        await tab.sleep(0.05)

    @classmethod
    async def _fill_and_submit_credentials(cls, tab: Tab, email: str, password: str) -> None:
        """
        Fill username/password and submit the member login form (Continuer).

        Uses JS value setter + input/change events so React-controlled fields update.
        """
        await tab
        await cls._scroll_page_top(tab)
        form_deadline = time.monotonic() + 12.0
        while time.monotonic() < form_deadline:
            await tab
            if await cls._login_username_field_is_visible(tab):
                break
            await asyncio.sleep(0.06)
        else:
            logger.warning("Username field did not become visible before credential fill.")

        await cls._scroll_page_top(tab)
        if not await cls._set_input_value_for_react(tab, "input#username", email):
            await cls._set_input_value_for_react(tab, 'input[name="username"]', email)
        await tab.sleep(0.05)
        if not await cls._set_input_value_for_react(tab, "input#password", password):
            await cls._set_input_value_for_react(tab, 'input[name="password"]', password)
        await tab.sleep(0.06)
        await cls._scroll_page_top(tab)

        submit = await tab.select('button[type="submit"]', timeout=5)
        if isinstance(submit, Element):
            try:
                await submit.scroll_into_view()
                await tab.sleep(0.04)
                await submit.click()
                logger.info("Clicked login submit (button[type=submit]).")
            except Exception as exc:  # noqa: BLE001
                logger.debug("Submit click: %s", exc)
                await tab.evaluate(
                    """
                    (() => {
                        const btn = document.querySelector('button[type="submit"]');
                        if (btn) { btn.click(); return true; }
                        return false;
                    })()
                    """,
                    return_by_value=True,
                )
        else:
            await tab.evaluate(
                """
                (() => {
                    const buttons = Array.from(document.querySelectorAll('button[type="submit"]'));
                    const btn = buttons.find(b => /Continuer/i.test((b.innerText || '').trim())) || buttons[0];
                    if (btn) { btn.click(); return true; }
                    return false;
                })()
                """,
                return_by_value=True,
            )
            logger.info("Submitted login via JS (Continuer / first submit).")
        await tab.sleep(0.6)
        await tab

    @classmethod
    async def is_connected(cls) -> bool:
        """
        Rough check that the user is **not** on an auth entry URL and the guest header CTA is gone.

        This avoids logging "connected" while still on ``select_type`` or when the header still shows
        "S'inscrire | Se connecter".

        Returns:
            True if URL is Vinted FR, not an auth-flow path, and the guest login header button is absent/hidden.
        """
        tab = cls._require_tab()
        await tab
        current = (tab.target.url or "").strip()
        if not current.lower().startswith("https://www.vinted.fr"):
            return False
        if cls._url_is_auth_flow(current):
            return False
        if await cls._header_guest_login_button_visible(tab):
            return False
        return True

    @classmethod
    async def ensure_sign_in(cls, email: str, password: str) -> None:
        """
        Attempt sign-in up to five times using :meth:`sign_in_vinted`.

        Args:
            email: Vinted username or email (unused if login UI steps are disabled).
            password: Account password (unused if login UI steps are disabled).

        Returns:
            None

        Raises:
            RuntimeError: If sign-in is still considered unsuccessful after all attempts.
        """
        max_attempts = 5
        await cls.sign_in_vinted(email, password, from_home=True)
        await cls._require_tab().sleep(1.8)
        if await cls.is_connected():
            logger.info(
                "Session looks logged in (past auth URL and no visible guest header login button).",
            )
            return

        for attempt in range(1, max_attempts):
            logger.info(
                "Retry %s/%s: member auth only (no reload of vinted.fr home — avoids losing the form).",
                attempt,
                max_attempts - 1,
            )
            await cls.sign_in_vinted(email, password, from_home=False)
            await cls._require_tab().sleep(1.5)
            if await cls.is_connected():
                logger.info(
                    "Session looks logged in (past auth URL and no visible guest header login button).",
                )
                return

        raise RuntimeError("Failed to sign in after multiple attempts")

    @classmethod
    async def sign_in_vinted(cls, email: str, password: str, *, from_home: bool = True) -> None:
        """
        Navigate to auth, click Se connecter → e-mail, fill credentials, submit.

        Args:
            email: Vinted login or email.
            password: Account password.
            from_home: If True, start from ``https://www.vinted.fr`` then member auth. If False, open
                member auth URL directly (used on retries so the home page does not wipe the login flow).

        Returns:
            None
        """
        tab = cls._require_tab()
        if from_home:
            await tab.get("https://www.vinted.fr")
            await cls._accept_onetrust_cookies(tab)
            await TimerService.wait(40)
            await cls._go_to_member_auth_entry(tab)
        else:
            await tab.get(VINTED_MEMBER_AUTH_URL)
            await tab
            await tab.sleep(0.08)

        await cls._accept_onetrust_cookies(tab, total_timeout_sec=4.0)
        await TimerService.wait(30)
        await cls._scroll_page_top(tab)
        await cls._click_auth_se_connecter_switch(tab, total_timeout_sec=12.0)
        await tab.sleep(0.04)
        await cls._click_auth_login_email_option(tab, total_timeout_sec=8.0)
        await cls._fill_and_submit_credentials(tab, email, password)

    @classmethod
    async def open_sell_item_page(cls) -> None:
        """
        Navigate to the “new item” listing page.

        Returns:
            None
        """
        tab = cls._require_tab()
        await tab.get("https://www.vinted.fr/items/new")
        await cls._accept_onetrust_cookies(tab)

    @classmethod
    async def wait_for_listing_form(cls, timeout_sec: float = 25.0) -> None:
        """Attend que le formulaire d'annonce (upload photos / catalogue) soit prêt."""
        tab = cls._require_tab()
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            await tab
            ok = await tab.evaluate(
                """
                (() => {
                    return !!(
                        document.querySelector('[data-testid="add-photos-input"]')
                        || document.querySelector('[data-testid="catalog-select-dropdown-input"]')
                    );
                })()
                """,
                return_by_value=True,
            )
            if ok is True:
                return
            await asyncio.sleep(0.04)
        logger.warning("Formulaire vendre : timeout après %ss (photos/catalogue).", timeout_sec)

    @classmethod
    async def add_photos_to_item(cls, photo_names: list[str]) -> None:
        """
        Upload local image files to the listing photo input.

        Args:
            photo_names: Basenames under the project ``images/`` directory.

        Returns:
            None

        Raises:
            RuntimeError: If the file input is missing or upload does not complete.
        """
        tab = cls._require_tab()
        root = get_project_root()
        photo_paths = [str(root / "images" / name) for name in photo_names]

        input_el = await tab.select('[data-testid="add-photos-input"]', timeout=15)
        if input_el is None:
            logger.error("Failed to find the file input on the page.")
            raise RuntimeError("add-photos-input not found")

        await input_el.send_file(*photo_paths)
        logger.info("Photos added successfully.")

        expected = len(photo_paths)
        for _ in range(120):
            count = await tab.evaluate(
                "document.querySelectorAll('.photo-box').length",
                return_by_value=True,
            )
            if isinstance(count, int) and count >= expected:
                return
            await asyncio.sleep(0.25)
        raise RuntimeError("Timeout waiting for photo thumbnails to match upload count")

    @classmethod
    async def select_category(
        cls,
        category_path: list[str],
        *,
        form_progress: FormProgressFn | None = None,
    ) -> None:
        """
        Walk the category dropdown using the given label path.

        Feuilles (ex. « Cartes à collectionner à l'unité ») peuvent exposer un ``radio`` :
        on clique le radio pour éviter les erreurs CDP sur le conteneur.

        Args:
            category_path: Ordered list of category titles as shown in the Vinted UI.
            form_progress: Journalisation optionnelle (SSE) pour chaque sous-étape.

        Returns:
            None

        Raises:
            RuntimeError: If a label in the path cannot be resolved.
        """
        tab = cls._require_tab()
        await tab
        if form_progress:
            await form_progress(
                {
                    "type": "log",
                    "step": "vinted_form",
                    "form_step": "category_open",
                    "message": "Ouverture du sélecteur de catégorie…",
                }
            )
        opened = await cls._ensure_catalog_dropdown_open()
        if not opened:
            logger.error("Impossible d'ouvrir le panneau catalogue (input + chevron).")
            await cls._catalog_debug_probe()
            raise RuntimeError("Catalog dropdown did not open or has no category rows")
        await TimerService.wait(180)

        for category in category_path:
            want = _normalize_vinted_label(category)
            if form_progress:
                await form_progress(
                    {
                        "type": "log",
                        "step": "vinted_form",
                        "form_step": "category_segment",
                        "message": f'Recherche du niveau catalogue : « {want} »',
                        "detail": want,
                    }
                )
            want_js = json.dumps(want)
            expr = f"""
            (() => {{
                try {{
                const wantRaw = {want_js};
                const norm = (s) => (String(s || "")
                    .replace(/\\u2019/g, "'")
                    .replace(/\\u2018/g, "'")
                    .trim());
                const looseKey = (s) => {{
                    let t = norm(s).toLowerCase().replace(/&/g, ' et ');
                    return t.split(/\\s+/).join(' ').trim();
                }};
                const wantLoose = looseKey(wantRaw);
                const wantN = norm(wantRaw);
                const matches = (text) => {{
                    const t = norm(text);
                    return t === wantN || looseKey(t) === wantLoose;
                }};

                const resolveCatalogPanel = () => {{
                    const mark = (p) => {{
                        let s = 0;
                        if (p.querySelector('#catalog-search-input')) s += 25;
                        s += p.querySelectorAll('[id^="catalog-"]').length * 2;
                        if (p.querySelector('[data-testid="catalog-navigation"]')) s += 8;
                        s += p.querySelectorAll('li.web_ui__Item__item').length;
                        return s;
                    }};
                    const panels = Array.from(document.querySelectorAll('.input-dropdown__content'));
                    let best = null;
                    let bestM = -1;
                    for (const p of panels) {{
                        const m = mark(p);
                        if (m > bestM) {{
                            bestM = m;
                            best = p;
                        }}
                    }}
                    if (best != null && bestM > 0) return best;
                    const seed = document.querySelector('[id^="catalog-"].web_ui__Cell__cell, li [id^="catalog-"]');
                    if (seed) {{
                        const c = seed.closest('.input-dropdown__content');
                        if (c) return c;
                    }}
                    return document.querySelector('[data-testid="catalog-select-dropdown-content"]');
                }};

                const content = resolveCatalogPanel();
                if (!content) {{
                    return JSON.stringify({{ ok: false, titles: [], err: 'no_catalog_panel' }});
                }}

                const allTitleEls = Array.from(content.querySelectorAll('.web_ui__Cell__title'));
                const inList = (el) => !!el.closest('li.web_ui__Item__item');
                const listTitleEls = allTitleEls.filter(inList);
                const navTitleEls = allTitleEls.filter((el) => !inList(el));

                const listTitles = listTitleEls.map((el) => norm(el.textContent)).filter(Boolean);
                const navTitles = navTitleEls.map((el) => norm(el.textContent)).filter(Boolean);

                for (const titleEl of listTitleEls) {{
                    if (!matches(titleEl.textContent)) continue;
                    let target = titleEl.closest('[id^="catalog-"]');
                    if (!target) target = titleEl.closest('div[role="button"]');
                    if (!target) target = titleEl.closest('.web_ui__Cell__cell');
                    if (!target) continue;
                    try {{
                        target.scrollIntoView({{ block: 'center', behavior: 'instant' }});
                    }} catch (e) {{}}
                    const radio = target.querySelector('input[type="radio"]');
                    if (radio) {{
                        radio.click();
                    }} else {{
                        target.click();
                    }}
                    return JSON.stringify({{ ok: true, id: target.id || '', skipped: false }});
                }}

                const navBody = content.querySelector('[data-testid="catalog-navigation--body"]');
                if (navBody && matches(navBody.textContent || '')) {{
                    return JSON.stringify({{ ok: true, id: 'already_in_panel', skipped: true }});
                }}

                for (const titleEl of navTitleEls) {{
                    if (matches(titleEl.textContent)) {{
                        return JSON.stringify({{ ok: true, id: 'already_in_panel', skipped: true }});
                    }}
                }}

                const backBtn = Array.from(content.querySelectorAll('button')).find((b) => {{
                    const a = (b.getAttribute('aria-label') || '').toLowerCase();
                    return a.includes('retour') || a.includes('back') || a.includes('précédent')
                        || a.includes('arrière') || a.includes('revenir');
                }});
                if (backBtn) {{
                    let sib = backBtn.nextElementSibling;
                    for (let i = 0; i < 4 && sib; i++) {{
                        const lines = (sib.textContent || '')
                            .split('\\n')
                            .map((x) => norm(x.trim()))
                            .filter(Boolean);
                        if (lines.some((line) => matches(line))) {{
                            return JSON.stringify({{ ok: true, id: 'already_in_panel', skipped: true }});
                        }}
                        sib = sib.nextElementSibling;
                    }}
                }}

                const navBodyText = navBody ? norm(navBody.textContent || '') : '';
                const debugTitles = [...new Set([...listTitles, ...navTitles, navBodyText].filter(Boolean))].slice(0, 40);
                return JSON.stringify({{ ok: false, titles: debugTitles }});
                }} catch (e) {{
                    return JSON.stringify({{ ok: false, titles: [], err: String(e) }});
                }}
            }})()
            """
            raw = await tab.evaluate(expr, return_by_value=True)
            try:
                result = _parse_eval_dict_result(raw, context=f"catalog:{want}")
            except (TypeError, json.JSONDecodeError) as exc:
                logger.error(
                    "Catalog evaluate inutilisable pour %r: %s raw=%r",
                    want,
                    exc,
                    raw,
                )
                await cls._catalog_debug_probe()
                raise RuntimeError(f"Category {want!r}: invalid evaluate result") from exc
            if not result.get("ok"):
                titles = result.get("titles")
                err = result.get("err")
                logger.error(
                    "Catalog: %r introuvable. Titres visibles (extrait): %s err=%s brut=%s",
                    want,
                    titles,
                    err,
                    json.dumps(result, ensure_ascii=False, default=str),
                )
                await cls._catalog_debug_probe()
                raise RuntimeError(f"Category {want!r} not found in Vinted catalog UI")
            if result.get("skipped"):
                logger.info("Catalog step %r → déjà dans ce niveau (en-tête)", want)
                if form_progress:
                    await form_progress(
                        {
                            "type": "log",
                            "step": "vinted_form",
                            "form_step": "category_skip",
                            "message": f'Déjà au bon niveau : « {want} »',
                            "detail": want,
                        }
                    )
            else:
                logger.info("Catalog step %r → %s", want, result.get("id"))
                if form_progress:
                    await form_progress(
                        {
                            "type": "log",
                            "step": "vinted_form",
                            "form_step": "category_ok",
                            "message": f'Niveau sélectionné : « {want} »',
                            "detail": want,
                        }
                    )
            await TimerService.wait(450)

    @classmethod
    async def select_brand(cls, brand_name: str) -> None:
        """
        Open the brand dropdown, type the brand, and pick the matching option.

        Args:
            brand_name: Exact brand label (used in ``aria-label`` on the result row).

        Returns:
            None
        """
        tab = cls._require_tab()
        brand_input = await tab.select('[data-testid="brand-select-dropdown-input"]')
        await brand_input.click()
        await tab.select('[data-testid="brand-select-dropdown-content"]', timeout=10)
        await brand_input.send_keys(brand_name)
        await TimerService.wait(500)
        option = await tab.select(f'[aria-label="{brand_name}"]', timeout=10)
        await option.click()
        logger.info("Brand selected successfully.")

    @classmethod
    async def select_condition(cls, condition_name: str) -> None:
        """
        Open the item condition dropdown and select the row containing ``condition_name``.

        Args:
            condition_name: Vinted condition string (French UI).

        Returns:
            None

        Raises:
            RuntimeError: If the condition text is not found in the menu.
        """
        tab = cls._require_tab()
        await tab

        trigger_selectors = (
            '[data-testid="category-condition-single-list-input"]',
            "#condition",
            'input[name="condition"]',
            '[data-testid="status-select-dropdown-input"]',
            "#status_id",
            'input#status_id',
        )
        trigger = None
        used_sel = ""
        for sel in trigger_selectors:
            try:
                trigger = await tab.select(sel, timeout=3)
            except Exception:  # noqa: BLE001
                trigger = None
            if trigger is not None:
                used_sel = sel
                break

        if trigger is None:
            trigger = await cls._find_condition_trigger_via_js()
            used_sel = "js_resolve"

        if trigger is None:
            raise RuntimeError(
                "Champ « état » introuvable (attendu: "
                "[data-testid=category-condition-single-list-input] ou #condition).",
            )

        if isinstance(trigger, str):
            await cls._scroll_selector_into_view(trigger)
            open_ok = await tab.evaluate(
                f"""
                (() => {{
                    const el = document.querySelector({json.dumps(trigger)});
                    if (!el) return false;
                    el.scrollIntoView({{ block: 'center', behavior: 'instant' }});
                    el.click();
                    return true;
                }})()
                """,
                return_by_value=True,
            )
            if open_ok is not True:
                raise RuntimeError("Clic sur le sélecteur d'état (JS) sans effet")
        else:
            if used_sel and used_sel != "js_resolve":
                await cls._scroll_selector_into_view(used_sel)
            await trigger.click()

        await tab.sleep(0.25)
        menu_ok = await tab.evaluate(
            """
            (() => !!document.querySelector(
                '[data-testid="category-condition-single-list-content"] .web_ui__Cell__title'
            ))()
            """,
            return_by_value=True,
        )
        if menu_ok is not True:
            await tab.evaluate(
                """
                (() => {
                    const sp = document.querySelector('[data-testid="category-condition-single-list-chevron-down"]');
                    if (!sp) return false;
                    const btn = sp.closest('[role="button"]') || sp.closest('.c-input__icon') || sp.parentElement;
                    if (btn && typeof btn.click === 'function') {
                        btn.click();
                        return true;
                    }
                    return false;
                })()
                """,
                return_by_value=True,
            )
            await tab.sleep(0.35)

        await TimerService.wait(350)

        expr = f"""
        (() => {{
            const conditionName = {json.dumps(condition_name)};
            const norm = (s) => (String(s || '')
                .replace(/\\u2019/g, "'")
                .replace(/\\u2018/g, "'")
                .trim());
            const wrap = document.querySelector('[data-testid="category-condition-single-list-content"]');
            const inner = wrap && wrap.querySelector('.input-dropdown__content');
            const roots = [];
            if (inner) roots.push(inner);
            if (wrap && !inner) roots.push(wrap);
            const panels = Array.from(document.querySelectorAll('.input-dropdown__content'));
            const visible = panels.filter((p) => {{
                const r = p.getBoundingClientRect();
                return r.width > 30 && r.height > 30;
            }});
            for (const p of (visible.length ? visible : panels)) {{
                if (p.querySelector('[data-testid^="condition-"]') && !roots.includes(p)) {{
                    roots.push(p);
                }}
            }}
            if (!roots.length) roots.push(document.body);
            let best = null;
            for (const root of roots) {{
                const titles = root.querySelectorAll('.web_ui__Cell__title');
                for (const el of titles) {{
                    const t = norm(el.textContent || '');
                    const want = norm(conditionName);
                    if (t.includes(want) || want.includes(t)) {{
                        best = el;
                        break;
                    }}
                }}
                if (best) break;
            }}
            if (!best) return JSON.stringify({{ ok: false }});
            const cell =
                best.closest('[data-testid^="condition-"]') ||
                best.closest('[role="button"]') ||
                best.closest('.web_ui__Cell__cell');
            try {{
                cell && cell.scrollIntoView({{ block: 'center', behavior: 'instant' }});
            }} catch (e) {{}}
            const radio = cell && cell.querySelector('input[type="radio"]');
            if (radio) {{
                radio.click();
            }} else if (cell && typeof cell.click === 'function') {{
                cell.click();
            }} else {{
                best.click();
            }}
            return JSON.stringify({{ ok: true }});
        }})()
        """
        raw = await tab.evaluate(expr, return_by_value=True)
        try:
            parsed = _parse_eval_dict_result(raw, context="select_condition")
            ok = parsed.get("ok") is True
        except (TypeError, json.JSONDecodeError):
            ok = raw is True

        if not ok:
            raise RuntimeError(f"Condition {condition_name!r} not found in dropdown")
        logger.info("Condition selected successfully (%s).", condition_name)

    @classmethod
    async def _find_condition_trigger_via_js(cls) -> Any:
        """Dernier recours : champ État Vinted (#condition / category-condition-single-list-input)."""
        tab = cls._require_tab()
        sel = await tab.evaluate(
            """
            (() => {
                const esc = (id) => (typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(id) : id.replace(/([#.:,[\\]])/g, '\\\\$1'));
                const direct = document.querySelector('[data-testid="category-condition-single-list-input"]');
                if (direct && direct.id) return '#' + esc(direct.id);
                const cond = document.querySelector('#condition[name="condition"]') || document.querySelector('#condition');
                if (cond) return '#condition';
                const norm = (s) => (String(s || '').toLowerCase().normalize('NFD').replace(/\\u0300-\\u036f/g, ''));
                const labels = Array.from(document.querySelectorAll('label.c-input__title, label'));
                for (const lb of labels) {
                    const tx = norm(lb.textContent || '');
                    if (!tx.includes('etat') && !tx.includes('condition')) continue;
                    const wrap = lb.closest('.c-input, li') || lb.parentElement;
                    if (!wrap) continue;
                    const inp = wrap.querySelector(
                        'input[readonly].c-input__value, [data-testid="category-condition-single-list-input"]'
                    );
                    if (!inp || !inp.id) continue;
                    return '#' + esc(inp.id);
                }
                return null;
            })()
            """,
            return_by_value=True,
        )
        return sel if isinstance(sel, str) else None

    @classmethod
    async def select_package_size(cls, package_size: VintedPackageSize) -> None:
        """
        Click the shipping package size cell (small / medium / large).

        Vinted change parfois les ``data-testid`` (ordre des segments, suffixes). On essaie
        plusieurs sélecteurs, puis un clic par index sur la rangée de 3 cellules, puis un
        repli sur le libellé (FR/EN).

        Args:
            package_size: One of ``small``, ``medium``, ``large``.

        Returns:
            None
        """
        tab = cls._require_tab()
        await tab
        size_json = json.dumps(package_size)
        expr = f"""
        (() => {{
            const size = {size_json};
            const idx = ({{ small: 0, medium: 1, large: 2 }}[size] ?? 0);
            const clickEl = (el) => {{
                if (!el) return false;
                el.scrollIntoView({{ block: 'center', behavior: 'instant' }});
                el.click();
                return true;
            }};
            const directSels = [
                `[data-testid="${{size}}-package-size--cell"]`,
                `[data-testid="package-size-${{size}}--cell"]`,
                `[data-testid="${{size}}-parcel-size--cell"]`,
                `[data-testid="parcel-size-${{size}}--cell"]`,
            ];
            for (const sel of directSels) {{
                const el = document.querySelector(sel);
                if (el && clickEl(el)) return JSON.stringify({{ ok: true, method: 'direct', sel }});
            }}
            let row = Array.from(document.querySelectorAll('[data-testid$="-package-size--cell"]'));
            if (row.length < 2) {{
                row = Array.from(
                    document.querySelectorAll('[data-testid*="package-size"][data-testid*="cell"]')
                );
            }}
            if (row.length < 2) {{
                row = Array.from(
                    document.querySelectorAll('[data-testid*="parcel"][data-testid*="cell"]')
                );
            }}
            if (row[idx] && row.length >= 2) {{
                if (clickEl(row[idx]))
                    return JSON.stringify({{ ok: true, method: 'indexed', idx, n: row.length }});
            }}
            const norm = (s) =>
                String(s || '')
                    .toLowerCase()
                    .normalize('NFD')
                    .replace(/\\u0300-\\u036f/g, '');
            const pat = {{
                small: /\\bpetit\\b|\\bsmall\\b/,
                medium: /\\bmoyen\\b|\\bmedium\\b/,
                large: /\\bgrand\\b|\\blarge\\b/,
            }};
            const re = pat[size];
            if (re) {{
                const nodes = document.querySelectorAll(
                    '[data-testid*="package"], [data-testid*="parcel"], [class*="Cell"]'
                );
                for (const el of nodes) {{
                    const t = norm(el.textContent || '');
                    if (!re.test(t)) continue;
                    const target =
                        el.closest('[data-testid*="cell"],[role="button"],button') || el;
                    if (clickEl(target)) return JSON.stringify({{ ok: true, method: 'text' }});
                }}
            }}
            const sample = Array.from(document.querySelectorAll('[data-testid]'))
                .map((e) => e.getAttribute('data-testid'))
                .filter((t) => t && (t.includes('package') || t.includes('parcel') || t.includes('colis')))
                .slice(0, 30);
            return JSON.stringify({{ ok: false, sample }});
        }})()
        """
        raw = await tab.evaluate(expr, return_by_value=True)
        try:
            parsed = _parse_eval_dict_result(raw, context="select_package_size")
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Sélection colis : réponse JS invalide ({raw!r})") from exc
        if not parsed.get("ok"):
            raise RuntimeError(
                f"Impossible de sélectionner la taille de colis ({package_size!r}). "
                f"Exemples data-testid (package/parcel/colis) : {parsed.get('sample')}"
            )
        await tab.sleep(0.15)
        logger.info(
            "Package size %r selected (%s).",
            package_size,
            parsed.get("method"),
        )

    @classmethod
    async def _fill_item_field(cls, selector: str, value: str) -> None:
        tab = cls._require_tab()
        el = await tab.select(selector, timeout=15)
        if el is None:
            logger.error("Failed to find input for selector: %s", selector)
            return
        await el.click()
        await el.clear_input()
        await el.send_keys(value)

    @classmethod
    async def fill_item_details(
        cls,
        vinted_item: ItemPayload,
        category_path: list[str],
        brand: str,
        package_size: VintedPackageSize = "small",
        progress: FormProgressFn | None = None,
    ) -> None:
        """
        Ordre aligné sur le formulaire Vinted : photos → titre → description → catégorie →
        marque → état → prix → colis.

        Args:
            vinted_item: Parsed row from ``items.json``.
            category_path: Category breadcrumb labels.
            brand: Brand to select.
            package_size: Parcel size for the listing.
            progress: Callback optionnel (dict SSE : ``form_step``, ``message``, etc.).

        Returns:
            None
        """
        async def emit_step(form_step: str, message: str, **extra: Any) -> None:
            if not progress:
                return
            ev: dict[str, Any] = {
                "type": "log",
                "step": "vinted_form",
                "form_step": form_step,
                "message": message,
            }
            ev.update(extra)
            await progress(ev)

        await emit_step("form_ready", "Synchronisation avec le formulaire Vinted…")
        await cls.wait_for_listing_form()
        await emit_step("form_ready", "Formulaire prêt — début du remplissage.")

        try:
            await emit_step("photos", "Envoi des photos…")
            await cls.add_photos_to_item(vinted_item["images"])
            await emit_step("photos_ok", "Photos importées.")
        except Exception as exc:  # noqa: BLE001
            logger.error("Error adding photos: %s", exc)

        await TimerService.wait(cls._VINTED_TIMEOUT_MS)

        await cls._scroll_selector_into_view("#title")
        await emit_step("title", "Saisie du titre…")
        await cls._fill_item_field("#title", vinted_item["title"])
        await emit_step("title_ok", "Titre renseigné.")
        await TimerService.wait(cls._VINTED_TIMEOUT_MS)

        desc = (vinted_item.get("description") or "").strip()
        if desc:
            await cls._scroll_selector_into_view("#description")
            await emit_step("description", "Saisie de la description…")
            await cls._fill_item_field("#description", desc)
            await emit_step("description_ok", "Description renseignée.")
            await TimerService.wait(cls._VINTED_TIMEOUT_MS)

        await cls._scroll_selector_into_view('[data-testid="catalog-select-dropdown-input"]')
        await TimerService.wait(400)

        try:
            await emit_step("category", "Sélection de la catégorie (plusieurs niveaux)…")
            await cls.select_category(category_path, form_progress=progress)
            await emit_step("category_done", "Catégorie validée.")
            await TimerService.wait(cls._VINTED_TIMEOUT_MS)

            await cls._scroll_selector_into_view('[data-testid="brand-select-dropdown-input"]')
            await emit_step("brand", "Sélection de la marque…")
            await cls.select_brand(brand)
            await emit_step("brand_ok", f'Marque « {brand} » sélectionnée.')
            await TimerService.wait(cls._VINTED_TIMEOUT_MS)

            await cls._scroll_selector_into_view("#status_id")
            await emit_step("condition", "Sélection de l'état…")
            await cls.select_condition(vinted_item["condition"])
            await emit_step("condition_ok", "État sélectionné.")
            await TimerService.wait(cls._VINTED_TIMEOUT_MS)

            await cls._scroll_selector_into_view("#price")
            price = vinted_item["price"]
            price_str = str(int(price)) if price == int(price) else str(price)
            await emit_step("price", "Saisie du prix…")
            await cls._fill_item_field("#price", price_str)
            await emit_step("price_ok", f"Prix : {price_str} €.")
            await TimerService.wait(cls._VINTED_TIMEOUT_MS)

            await cls._scroll_selector_into_view('[data-testid$="-package-size--cell"]')
            await emit_step("package", "Choix de la taille du colis…")
            await cls.select_package_size(package_size)
            await emit_step("package_ok", f"Colis : {package_size}.")
        except Exception as exc:  # noqa: BLE001
            logger.error("Error during Vinted form (category → colis): %s", exc)
            await emit_step("form_error", f"Échec sur le formulaire : {exc}", detail=str(exc))
            raise

        logger.info("Filling in the remaining item details — done")

    @classmethod
    async def publish(cls) -> None:
        """
        Click the Vinted upload/save button to publish the listing.

        Returns:
            None

        Raises:
            RuntimeError: If the button is not clickable in time.
        """
        tab = cls._require_tab()
        await cls._scroll_selector_into_view('[data-testid="upload-form-save-button"]')
        btn = await tab.select('[data-testid="upload-form-save-button"]', timeout=15)
        if btn is None:
            raise RuntimeError("upload-form-save-button not found")
        await btn.click()
        logger.info("Item listed for sale successfully.")
