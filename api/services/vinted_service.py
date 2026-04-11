"""Vinted UI automation using nodriver (Chrome DevTools Protocol)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Optional

import nodriver as uc
from nodriver import Element

from app_types.payload import ItemPayload
from app_types.vinted import VintedPackageSize
from services.os_service import get_project_root
from services.timer_service import TimerService

if TYPE_CHECKING:
    from nodriver import Browser, Tab

logger = logging.getLogger(__name__)

# Auth entry (same path as header "S'inscrire | Se connecter"); Vinted may not redirect from home anymore.
VINTED_MEMBER_AUTH_URL = "https://www.vinted.fr/member/signup/select_type?ref_url=%2F"

# URL substrings that mean the user is still in the login / signup flow (not "connected").
_AUTH_FLOW_URL_MARKERS: tuple[str, ...] = (
    "select_type",
    "/member/signup",
    "/member/session",
    "/member/login",
)

_DEFAULT_BROWSER_ARGS: list[str] = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--start-maximized",
]


class VintedService:
    """
    Static-style service mirroring the previous TypeScript class: one browser, one tab.

    Launches Chrome via nodriver, navigates Vinted, fills listing fields, uploads photos,
    and can publish listings.
    """

    _browser: Optional[Browser] = None
    _tab: Optional[Tab] = None
    _VINTED_TIMEOUT_MS: int = 500

    @classmethod
    async def init_browser(cls) -> None:
        """
        Start the Chromium-based browser with flags aimed at fewer automation signals.

        Returns:
            None

        Raises:
            RuntimeError: If the browser failed to start.
        """
        cls._browser = await uc.start(
            headless=False,
            browser_args=list(_DEFAULT_BROWSER_ARGS),
            sandbox=False,
        )
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
    async def select_category(cls, category_path: list[str]) -> None:
        """
        Walk the category dropdown using the given label path.

        Args:
            category_path: Ordered list of category titles as shown in the Vinted UI.

        Returns:
            None

        Raises:
            RuntimeError: If a label in the path cannot be resolved.
        """
        tab = cls._require_tab()
        catalog = await tab.select('[data-testid="catalog-select-dropdown-input"]')
        await catalog.click()
        await tab.select('[data-testid="catalog-select-dropdown-content"]', timeout=10)

        for category in category_path:
            expr = f"""
            (() => {{
                const label = {json.dumps(category)};
                const items = Array.from(document.querySelectorAll('.web_ui__Cell__cell'));
                const target = items.find(
                    (item) =>
                        item.querySelector('.web_ui__Cell__title')?.textContent?.trim() === label
                );
                return target ? target.id : null;
            }})()
            """
            category_id = await tab.evaluate(expr, return_by_value=True)
            if not category_id:
                raise RuntimeError(f"Category {category!r} not found")
            logger.info("clicking on category %s", category)
            el = await tab.select(f"#{category_id}")
            await el.click()
            await TimerService.wait(500)

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
        status = await tab.select("#status_id")
        await status.click()
        await tab.select(".input-dropdown", timeout=10)
        selector = ".web_ui__Cell__cell[role='button'] .web_ui__Cell__title"
        await tab.select(selector, timeout=10)

        expr = f"""
        (() => {{
            const conditionName = {json.dumps(condition_name)};
            const sel = {json.dumps(selector)};
            const options = document.querySelectorAll(sel);
            const target = Array.from(options).find((opt) =>
                (opt.textContent || '').includes(conditionName)
            );
            if (target) {{
                target.click();
                return true;
            }}
            return false;
        }})()
        """
        ok = await tab.evaluate(expr, return_by_value=True)
        if not ok:
            raise RuntimeError(f"Condition {condition_name!r} not found")
        logger.info("Condition selected successfully.")

    @classmethod
    async def select_package_size(cls, package_size: VintedPackageSize) -> None:
        """
        Click the shipping package size cell (small / medium / large).

        Args:
            package_size: One of ``small``, ``medium``, ``large``.

        Returns:
            None
        """
        tab = cls._require_tab()
        base = '[data-testid$="-package-size--cell"]'
        await tab.select(base, timeout=15)
        cell = await tab.select(f'[data-testid="{package_size}-package-size--cell"]')
        await cell.click()
        logger.info("Package size %r selected successfully.", package_size)

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
    ) -> None:
        """
        Fill category, brand, condition, package size, photos, title, optional description, and price.

        Args:
            vinted_item: Parsed row from ``items.json``.
            category_path: Category breadcrumb labels.
            brand: Brand to select.
            package_size: Parcel size for the listing.

        Returns:
            None
        """
        await TimerService.wait(1000)
        try:
            await cls.select_category(category_path)
            await TimerService.wait(cls._VINTED_TIMEOUT_MS)
            await cls.select_brand(brand)
            await TimerService.wait(cls._VINTED_TIMEOUT_MS)
            await cls.select_condition(vinted_item["condition"])
            await TimerService.wait(cls._VINTED_TIMEOUT_MS)
            await cls.select_package_size(package_size)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error selecting category, brand, condition, or package size: %s", exc)

        await TimerService.wait(cls._VINTED_TIMEOUT_MS)

        try:
            await cls.add_photos_to_item(vinted_item["images"])
        except Exception as exc:  # noqa: BLE001
            logger.error("Error adding photos: %s", exc)

        await TimerService.wait(cls._VINTED_TIMEOUT_MS)
        logger.info("Filling in the remaining item details")

        await cls._fill_item_field("#title", vinted_item["title"])
        await TimerService.wait(cls._VINTED_TIMEOUT_MS)

        if vinted_item.get("description"):
            await cls._fill_item_field(
                "#description",
                "Prix négociable si achat de plusieurs articles.",
            )
            await TimerService.wait(cls._VINTED_TIMEOUT_MS)

        price = vinted_item["price"]
        await cls._fill_item_field("#price", str(int(price)) if price == int(price) else str(price))

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
        btn = await tab.select('[data-testid="upload-form-save-button"]', timeout=15)
        if btn is None:
            raise RuntimeError("upload-form-save-button not found")
        await btn.click()
        logger.info("Item listed for sale successfully.")
