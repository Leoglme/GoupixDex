"""Leboncoin « déposer une annonce » automation (nodriver / CDP)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urlparse

import nodriver as uc
from nodriver import Element
from nodriver.cdp import input_ as cdp_input

from config import get_settings
from services.os_service import get_project_root, resolve_leboncoin_nodriver_user_data_dir
from services.timer_service import TimerService
from services.vinted_service import _build_browser_args

if TYPE_CHECKING:
    from nodriver import Browser, Tab

logger = logging.getLogger(__name__)

FormProgressFn = Callable[[dict[str, Any]], Awaitable[None]]

BASE_URL = "https://www.leboncoin.fr"
DEPOSIT_URL = f"{BASE_URL}/deposer-une-annonce"
ACCOUNT_URL = f"{BASE_URL}/mes-annonces"
MY_ADS_URL = f"{BASE_URL}/compte/part/mes-annonces"
LOGIN_URL = f"{BASE_URL}/compte/connexion-securite"
# Pages accessibles uniquement avec une session membre (Leboncoin redirige souvent vers /favorites).
_MEMBER_AREA_PATH_RE = re.compile(
    r"/(mes-annonces|favorites|mon-compte|account/|deposer-une-annonce)",
    re.I,
)
LOGIN_URL_PATTERN = re.compile(
    r"(auth\.leboncoin\.fr|/(compte/connexion|connexion-securite|login|authentification|account/login))",
    re.I,
)
PUBLISHED_URL_PATTERNS = (
    re.compile(r"/ad/[^/]+/(\d{4,})"),
    re.compile(r"/(\d{6,})\.htm"),
    re.compile(r"[?&]listing_id=(\d+)"),
)
CONFIRMED_URL_PATTERNS = (
    re.compile(r"/deposer-une-annonce/(confirmation|merci|success)", re.I),
    re.compile(r"/ad/"),
)

# Autocomplete label for Pokémon singles (Loisirs → Collection).
DEFAULT_CATEGORY_LABEL = os.environ.get("LEBONCOIN_CATEGORY", "Collection")
# Optional wizard clicks before the category autocomplete (comma-separated labels).
_CATEGORY_WIZARD_LABELS = tuple(
    x.strip()
    for x in os.environ.get(
        "LEBONCOIN_CATEGORY_WIZARD",
        "Loisirs,Collection",
    ).split(",")
    if x.strip()
)

_CATEGORY_INPUT_SELECTORS = (
    'input[name="category"]',
    'input[data-qa-id="adsubject_category"]',
    'input[placeholder*="catégorie" i]',
    '[data-qa-id="category"] input',
)
_TITLE_SELECTORS = (
    'input[aria-label*="titre" i]',
    'input[placeholder*="titre" i]',
    'input[name="subject"]',
    'input[data-qa-id="input_subject"]',
    "input#subject",
)
_DESC_SELECTORS = (
    'textarea[aria-label*="description" i]',
    'textarea[placeholder*="description" i]',
    'textarea[name="body"]',
    'textarea[data-qa-id="textarea_body"]',
    "textarea#body",
)
_PRICE_SELECTORS = (
    'input[name="price_cents"]',
    "input#price_cents",
    'input[aria-label*="prix" i]',
    'input[placeholder*="prix" i]',
    'input[name="price"]',
    'input[data-qa-id="input_price"]',
    "input#price",
)
_ZIP_SELECTORS = (
    'input[name="zipcode"]',
    'input[data-qa-id="input_location"]',
    'input[placeholder*="code postal" i]',
)
_ADDRESS_LBC_SELECTORS = (
    'div[data-rhf-name="location"] input[data-spark-component="combobox-input"]',
    'input[data-spark-component="combobox-input"][name="location"]',
    'input[name="location"][role="combobox"]',
    'input[placeholder*="Adresse" i]',
    'input[aria-label*="adresse" i]',
    'input[aria-label*="Adresse" i]',
)
_SUGGESTION_SELECTORS = (
    '[role="option"]',
    'li[data-qa-id*="suggestion"]',
    'ul[role="listbox"] li',
    '[data-qa-id="suggestion"]',
)
_FILE_INPUT_SELECTORS = ('input[type="file"][accept*="image"]', 'input[type="file"]')
_PUBLISH_BUTTON_CSS = ('button[type="submit"]', 'button[data-qa-id="adsubmit"]')
_PUBLISH_BUTTON_TEXT = (
    "Déposer mon annonce",
    "Déposer l'annonce",
    "Publier mon annonce",
    "Publier",
    "Valider",
)
_SKIP_BOOST_BUTTON_TEXT = (
    "Déposer sans booster mon annonce",
    "Déposer sans booster",
)

_SESSION_RECONNECT_MSG = (
    "Session Leboncoin expirée ou incomplète pour déposer une annonce. "
    "Paramètres → Session Leboncoin → Ouvrir Chrome, connectez-vous, "
    "attendez la fermeture automatique de Chrome, puis relancez la publication."
)
# « Mes annonces » est rechargée à cet intervalle le temps que Leboncoin valide l'annonce déposée.
_MY_ADS_RELOAD_SEC = 8.0
_DELETE_SESSION_RECONNECT_MSG = (
    "Session Leboncoin expirée : Paramètres → Session Leboncoin → Ouvrir Chrome, connectez-vous, "
    "attendez la fermeture automatique de Chrome, puis relancez le retrait."
)
_MY_ADS_LIST_TIMEOUT_SEC = 25.0
_MY_ADS_MAX_SCROLL_LOADS = 12
_DELETE_DIALOG_TIMEOUT_SEC = 10.0
_DELETE_OUTCOME_TIMEOUT_SEC = 30.0
_DELETE_TRIGGER_MARKER = "data-goupix-delete-trigger"
_DELETE_CONFIRM_CSS = '[data-qa-id="delete-ad-modal-confirm"]'
_DELETE_ACCEPTED_CSS = '[data-qa-id="delete-ad-modal-reason-submit"]'
_ALREADY_BEING_DELETED_ERROR = re.compile(r"d[ée]j[àa] en cours de suppression", re.I)


def format_leboncoin_price(price_eur: float) -> str:
    """Prix tel qu'on le tape dans Leboncoin : « 3 » ou « 2,50 »."""
    return str(int(price_eur)) if price_eur == int(price_eur) else f"{price_eur:.2f}".replace(".", ",")


def parse_leboncoin_price(shown_price: str) -> float | None:
    """Prix affiché par le champ Leboncoin (« 2,50 », « 5 € »), ou None quand il est vide ou illisible."""
    digits = re.sub(r"[^\d,.]", "", shown_price).replace(",", ".")
    try:
        return round(float(digits), 2) if digits else None
    except ValueError:
        return None


class LeboncoinService:
    """One browser session per publish job (mirrors VintedService lifecycle)."""

    _browser: Optional[Browser] = None
    _tab: Optional[Tab] = None
    browser_job_lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def _require_tab(cls) -> Tab:
        if cls._tab is None:
            raise RuntimeError("Leboncoin tab not initialized")
        return cls._tab

    @classmethod
    async def init_browser(cls) -> None:
        settings = get_settings()
        headless = settings.vinted_browser_headless
        discreet = bool(settings.vinted_browser_discreet) and not headless
        start_kw: dict[str, Any] = {
            "headless": headless,
            "browser_args": _build_browser_args(headless=headless, discreet=discreet),
            "sandbox": False,
        }
        if settings.vinted_chrome_executable:
            start_kw["browser_executable_path"] = settings.vinted_chrome_executable.strip()
        uds = resolve_leboncoin_nodriver_user_data_dir(os.environ.get("LEBONCOIN_USER_DATA_DIR"))
        uds.mkdir(parents=True, exist_ok=True)
        start_kw["user_data_dir"] = str(uds)
        logger.info("Leboncoin browser: persistent profile %s", uds)
        cls._browser = await uc.start(**start_kw)
        if cls._browser is None:
            raise RuntimeError("nodriver.start() returned no browser instance")

    @classmethod
    async def init_page(cls, url: str = DEPOSIT_URL) -> None:
        cls._tab = await cls._browser.get(url)  # type: ignore[union-attr]
        await cls._require_tab().sleep(0.6)

    @classmethod
    def close_browser(cls) -> None:
        try:
            if cls._browser is not None:
                cls._browser.stop()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Leboncoin browser stop: %s", exc)
        cls._browser = None
        cls._tab = None

    @classmethod
    async def ping_browser(cls) -> bool:
        """False if CDP is gone (Chrome closed/crashed) — clears stale handles."""
        if cls._browser is None or cls._tab is None:
            return False
        try:
            await asyncio.wait_for(cls._tab.evaluate("1+1", return_by_value=True), timeout=3.0)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.info("Leboncoin CDP unreachable, clearing browser handle: %s", exc)
            cls.close_browser()
            return False

    @classmethod
    async def _set_input_value(cls, tab: Tab, css_selector: str, value: str) -> bool:
        sel_json = json.dumps(css_selector)
        val_json = json.dumps(value)
        ok = await tab.evaluate(
            f"""
            (() => {{
                const el = document.querySelector({sel_json});
                if (!el) return false;
                el.focus();
                const val = {val_json};
                const proto = Object.getPrototypeOf(el);
                const desc = Object.getOwnPropertyDescriptor(proto, 'value')
                    || Object.getOwnPropertyDescriptor(
                        el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype,
                        'value'
                    );
                if (desc && desc.set) desc.set.call(el, val);
                else el.value = val;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }})()
            """,
            return_by_value=True,
        )
        return ok is True

    @classmethod
    async def _first_matching_selector(cls, tab: Tab, selectors: tuple[str, ...]) -> str | None:
        for sel in selectors:
            found = await tab.evaluate(
                f"!!document.querySelector({json.dumps(sel)})",
                return_by_value=True,
            )
            if found is True:
                return sel
        return None

    @classmethod
    async def _pick_suggestion(cls, tab: Tab, needle: str) -> None:
        needle_low = needle.lower()
        await tab.evaluate(
            f"""
            (() => {{
                const needle = {json.dumps(needle_low)};
                const sels = {json.dumps(list(_SUGGESTION_SELECTORS))};
                for (const sel of sels) {{
                    for (const el of document.querySelectorAll(sel)) {{
                        const t = (el.textContent || '').trim().toLowerCase();
                        if (t && (t.includes(needle) || needle.includes(t.slice(0, 12)))) {{
                            el.click();
                            return true;
                        }}
                    }}
                }}
                const first = document.querySelector('[role="option"]');
                if (first) {{ first.click(); return true; }}
                return false;
            }})()
            """,
            return_by_value=True,
        )
        await tab.sleep(0.35)

    @classmethod
    async def _click_button_containing(cls, tab: Tab, needle: str) -> bool:
        needle_json = json.dumps(needle.lower())
        clicked = await tab.evaluate(
            f"""
            (() => {{
                const needle = {needle_json};
                for (const el of document.querySelectorAll('button, a, [role="button"]')) {{
                    const t = (el.textContent || '').trim().toLowerCase();
                    if (t && (t === needle || t.includes(needle))) {{
                        el.click();
                        return true;
                    }}
                }}
                return false;
            }})()
            """,
            return_by_value=True,
        )
        if clicked is True:
            await tab.sleep(0.55)
        return clicked is True

    @classmethod
    async def _try_category_wizard(cls, tab: Tab) -> None:
        if await cls._first_matching_selector(tab, _CATEGORY_INPUT_SELECTORS):
            return
        for label in _CATEGORY_WIZARD_LABELS:
            if await cls._click_button_containing(tab, label):
                logger.info("Leboncoin wizard click: %s", label)
                await tab.sleep(0.4)

    @classmethod
    async def _fill_first(cls, tab: Tab, selectors: tuple[str, ...], value: str, *, pick_suggestion: bool = False) -> bool:
        sel = await cls._first_matching_selector(tab, selectors)
        if not sel:
            return False
        if not await cls._set_input_value(tab, sel, value):
            return False
        if pick_suggestion:
            await cls._pick_suggestion(tab, value)
            await tab.sleep(1.2)
        return True

    @classmethod
    async def _shown_price(cls, tab: Tab, css_selector: str) -> float | None:
        """Prix affiché par le champ prix de la page."""
        shown_price = await tab.evaluate(
            f"(document.querySelector({json.dumps(css_selector)}) || {{}}).value || ''",
            return_by_value=True,
        )
        return parse_leboncoin_price(str(shown_price or ""))

    @classmethod
    async def _fill_price(cls, tab: Tab, price_eur: float) -> bool | None:
        """
        Saisit le prix de l'article et vérifie que le champ le garde : Leboncoin y préremplit son propre prix suggéré.

        Returns:
            True quand le champ affiche le prix de l'article, False s'il ne le garde pas, None si la page n'a pas de champ prix.
        """
        css_selector = await cls._first_matching_selector(tab, _PRICE_SELECTORS)
        if css_selector is None:
            return None
        expected_price = round(price_eur, 2)
        for _attempt in range(3):
            if await cls._shown_price(tab, css_selector) == expected_price:
                return True
            await cls._set_input_value(tab, css_selector, format_leboncoin_price(price_eur))
            await tab.sleep(0.6)
        return await cls._shown_price(tab, css_selector) == expected_price

    @classmethod
    async def _click_continue(cls, tab: Tab) -> bool:
        return await cls._click_button_containing(tab, "Continuer")

    @classmethod
    async def _wait_for_combobox_options(cls, tab: Tab, *, timeout_sec: float = 6.0) -> bool:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            found = await tab.evaluate(
                """
                (() => {
                  const sels = [
                    '[role="listbox"] [role="option"]',
                    '[role="option"]',
                    '[data-spark-component="combobox-item"]',
                  ];
                  for (const sel of sels) {
                    for (const el of document.querySelectorAll(sel)) {
                      const r = el.getBoundingClientRect();
                      if (r.width > 2 && r.height > 2) return true;
                    }
                  }
                  return false;
                })()
                """,
                return_by_value=True,
            )
            if found is True:
                return True
            await tab.sleep(0.25)
        return False

    @classmethod
    async def _select_combobox_option(cls, tab: Tab, label_fragment: str, option_text: str) -> bool:
        label_json = json.dumps(label_fragment)
        option_json = json.dumps(option_text)
        ok = await tab.evaluate(
            f"""
            (() => {{
                const norm = (s) => String(s || '')
                  .normalize('NFD').replace(/\\p{{M}}/gu, '')
                  .replace(/[''´`]/g, "'")
                  .toLowerCase()
                  .trim();
                const labelFrag = norm({label_json});
                const want = norm({option_json});

                const findCombo = () => {{
                  for (const lab of document.querySelectorAll('label, legend, p, span')) {{
                    const t = norm(lab.textContent || '');
                    if (!t || (!t.startsWith(labelFrag) && t !== labelFrag)) continue;
                    const root = lab.closest('div, fieldset, section') || lab.parentElement;
                    if (!root) continue;
                    const cb = root.querySelector(
                      '[role="combobox"], button[data-spark-component*="combobox"], input[data-spark-component="combobox-input"]'
                    );
                    if (cb) return cb;
                  }}
                  for (const c of document.querySelectorAll('[role="combobox"]')) {{
                    const al = norm(c.getAttribute('aria-label') || c.getAttribute('name') || '');
                    if (al.includes(labelFrag)) return c;
                  }}
                  return null;
                }};

                const combo = findCombo();
                if (!combo) return false;
                combo.scrollIntoView({{ block: 'center', behavior: 'instant' }});
                combo.click();
                combo.focus?.();

                const pickOption = () => {{
                  const opts = [
                    ...document.querySelectorAll('[role="listbox"] [role="option"]'),
                    ...document.querySelectorAll('[role="option"]'),
                    ...document.querySelectorAll('[data-spark-component="combobox-item"]'),
                  ];
                  for (const opt of opts) {{
                    const t = norm(opt.textContent || '');
                    if (!t) continue;
                    if (t === want || t.includes(want) || want.includes(t)) {{
                      opt.click();
                      return true;
                    }}
                  }}
                  return false;
                }};
                if (pickOption()) return true;
                return false;
            }})()
            """,
            return_by_value=True,
        )
        if ok is not True:
            await tab.sleep(0.35)
            await cls._wait_for_combobox_options(tab, timeout_sec=4.0)
            ok = await tab.evaluate(
                f"""
                (() => {{
                  const norm = (s) => String(s || '')
                    .normalize('NFD').replace(/\\p{{M}}/gu, '')
                    .replace(/[''´`]/g, "'")
                    .toLowerCase()
                    .trim();
                  const want = norm({option_json});
                  for (const opt of document.querySelectorAll('[role="option"], [data-spark-component="combobox-item"]')) {{
                    const t = norm(opt.textContent || '');
                    if (t && (t === want || t.includes(want) || want.includes(t))) {{
                      opt.click();
                      return true;
                    }}
                  }}
                  return false;
                }})()
                """,
                return_by_value=True,
            )
        if ok is True:
            await tab.sleep(0.45)
            return True
        logger.warning("Leboncoin combobox « %s » → « %s » non sélectionné.", label_fragment, option_text)
        return False

    @classmethod
    async def _click_category_suggestion(cls, tab: Tab, keyword: str) -> bool:
        needle = json.dumps(keyword.lower())
        clicked = await tab.evaluate(
            f"""
            (() => {{
                const needle = {needle};
                for (const el of document.querySelectorAll('button, [role="button"]')) {{
                    const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                    if (aria.includes('catégorie') && aria.includes(needle)) {{
                        el.click();
                        return true;
                    }}
                }}
                for (const el of document.querySelectorAll('button, [role="button"]')) {{
                    const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                    const text = (el.textContent || '').trim().toLowerCase();
                    if (aria.includes('choix') && aria.includes(needle)) {{
                        el.click();
                        return true;
                    }}
                    if (text.includes(needle) && (text.includes('loisirs') || text.includes('collection'))) {{
                        el.click();
                        return true;
                    }}
                }}
                return false;
            }})()
            """,
            return_by_value=True,
        )
        if clicked is True:
            await tab.sleep(0.55)
        return clicked is True

    @classmethod
    async def _continue_button_visible(cls, tab: Tab) -> bool:
        raw = await tab.evaluate(
            """
            (() => {
              for (const b of document.querySelectorAll('button')) {
                const t = (b.textContent || '').trim().toLowerCase();
                if (t === 'continuer' && !b.disabled) return true;
              }
              return false;
            })()
            """,
            return_by_value=True,
        )
        return raw is True

    @classmethod
    async def _wait_for_wizard_step(cls, tab: Tab, *, timeout_sec: float = 45.0) -> bool:
        """
        Attend que l'étape courante de l'assistant soit affichée : après les photos, Leboncoin analyse l'article (« On admire votre article »).

        Returns:
            Vrai quand un champ ou un bouton de l'étape est là, faux si l'analyse dure au-delà du délai.
        """
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            is_step_shown = await tab.evaluate(
                """
                (() => {
                  if (/On admire votre article|Juste un instant/i.test(document.body.innerText || '')) return false;
                  if (document.querySelector('textarea[name="body"], input[name="price_cents"]')) return true;
                  return [...document.querySelectorAll('button')].some((button) => {
                    const label = (button.textContent || '').trim().toLowerCase();
                    return label === 'continuer' || label.includes('déposer');
                  });
                })()
                """,
                return_by_value=True,
            )
            if is_step_shown is True:
                return True
            await tab.sleep(0.5)
        return False

    @classmethod
    async def _fill_title_and_trigger_suggestions(cls, tab: Tab, title: str) -> None:
        if not await cls._fill_first(tab, _TITLE_SELECTORS, title[:200]):
            raise RuntimeError("Champ titre introuvable (assistant Leboncoin).")
        await tab.evaluate(
            """
            (() => {
              const sels = [
                'input[aria-label*="titre" i]',
                'input[placeholder*="titre" i]',
                'input[name="subject"]',
              ];
              let el = null;
              for (const s of sels) {
                el = document.querySelector(s);
                if (el) break;
              }
              if (!el) return false;
              el.focus();
              el.dispatchEvent(new Event('input', { bubbles: true }));
              el.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            })()
            """,
            return_by_value=True,
        )
        await tab.sleep(2.0)

    @classmethod
    async def _category_is_collection(cls, tab: Tab) -> bool:
        raw = await tab.evaluate(
            """
            (() => {
              const nodes = [
                document.querySelector('[data-qa-id="category"]'),
                document.querySelector('input[name="category"]'),
                ...document.querySelectorAll('button, [role="button"], nav, [class*="breadcrumb" i]'),
              ].filter(Boolean);
              const text = nodes.map((el) => (el.textContent || el.value || '')).join(' ').toLowerCase();
              return text.includes('collection') && !text.includes('jeux & jouets');
            })()
            """,
            return_by_value=True,
        )
        return raw is True

    @classmethod
    async def _wizard_step_title_and_category(cls, tab: Tab, title: str, category_keyword: str) -> None:
        await cls._fill_title_and_trigger_suggestions(tab, title)
        picked = await cls._click_category_suggestion(tab, category_keyword)
        if not picked:
            picked = await cls._click_category_suggestion(tab, "collection")
        if not picked:
            await cls._try_category_wizard(tab)
            picked = await cls._click_category_suggestion(tab, "collection")
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            if await cls._continue_button_visible(tab) and (
                picked or await cls._category_is_collection(tab)
            ):
                break
            if not picked:
                picked = await cls._click_category_suggestion(tab, category_keyword) or await cls._click_category_suggestion(
                    tab, "collection"
                )
            await asyncio.sleep(0.45)
        else:
            raise RuntimeError("Catégorie Collection ou bouton « Continuer » introuvable après le titre.")
        if not picked and not await cls._category_is_collection(tab):
            raise RuntimeError(
                "Catégorie « Collection » non sélectionnée — dépôt annulé pour éviter un refus Leboncoin."
            )
        if not await cls._click_continue(tab):
            raise RuntimeError("Bouton « Continuer » introuvable après le titre.")

    @classmethod
    async def _wizard_fill_structured_attributes(
        cls,
        tab: Tab,
        *,
        produit: str,
        etat: str,
        conditionnement: str,
        epoque: str | None,
    ) -> None:
        current_produit = await tab.evaluate(
            """
            (() => {
              const c = [...document.querySelectorAll('[role="combobox"]')]
                .find(x => (x.getAttribute('aria-label')||'').toLowerCase().includes('produit'));
              return c ? (c.value || c.textContent || '').trim() : '';
            })()
            """,
            return_by_value=True,
        )
        prod_str = str(current_produit or "")
        if produit.lower() not in prod_str.lower():
            await cls._select_combobox_option(tab, "produit", produit)
        for label_frag, value in (
            ("état", etat),
            ("conditionnement", conditionnement),
        ):
            for _ in range(2):
                if await cls._select_combobox_option(tab, label_frag, value):
                    break
                await tab.sleep(0.5)
        if epoque:
            for _ in range(2):
                if await cls._select_combobox_option(tab, "époque", epoque):
                    break
                await tab.sleep(0.5)

    @classmethod
    async def _page_has_final_submit(cls, tab: Tab) -> bool:
        for label in _PUBLISH_BUTTON_TEXT:
            found = await tab.evaluate(
                f"""
                (() => {{
                    const needle = {json.dumps(label.lower())};
                    for (const b of document.querySelectorAll('button')) {{
                        const t = (b.textContent || '').trim().toLowerCase();
                        if (t === needle || t.includes(needle)) return true;
                    }}
                    return false;
                }})()
                """,
                return_by_value=True,
            )
            if found is True:
                return True
        return False

    @classmethod
    async def _cdp_tap_key(cls, tab: Tab, *, key: str, code: str, modifiers: int = 0) -> None:
        for type_ in ("keyDown", "keyUp"):
            await tab.send(
                cdp_input.dispatch_key_event(
                    type_=type_,
                    key=key,
                    code=code,
                    modifiers=modifiers,
                )
            )
        await tab.sleep(0.08)

    @classmethod
    async def _pick_address_suggestion(cls, tab: Tab, postal_code: str, city: str) -> bool:
        pc_json = json.dumps(postal_code.strip())
        city_json = json.dumps(city.strip().lower())
        picked = await tab.evaluate(
            f"""
            (() => {{
                const pc = {pc_json};
                const cityNeedle = {city_json};
                const collect = (root) => {{
                  const optionSelectors = [
                    '[role="option"]',
                    '[role="listbox"] [role="option"]',
                    '[data-spark-component="combobox-item"]',
                    'li[data-spark-component="combobox-item"]',
                  ];
                  const options = [];
                  for (const sel of optionSelectors) {{
                    for (const opt of root.querySelectorAll(sel)) {{
                      if (!options.includes(opt)) options.push(opt);
                    }}
                  }}
                  return options;
                }};
                let options = collect(document);
                for (const wrap of document.querySelectorAll('[data-radix-popper-content-wrapper]')) {{
                  for (const opt of collect(wrap)) {{
                    if (!options.includes(opt)) options.push(opt);
                  }}
                }}
                for (const opt of options) {{
                    const t = (opt.textContent || '').trim().toLowerCase();
                    if (!t) continue;
                    const r = opt.getBoundingClientRect();
                    if (r.width < 4 || r.height < 4) continue;
                    if (pc && t.includes(pc) && (!cityNeedle || t.includes(cityNeedle))) {{
                        opt.click();
                        return true;
                    }}
                }}
                for (const opt of options) {{
                    const r = opt.getBoundingClientRect();
                    if (r.width > 4 && r.height > 4) {{
                        opt.click();
                        return true;
                    }}
                }}
                return false;
            }})()
            """,
            return_by_value=True,
        )
        if picked is True:
            await tab.sleep(0.5)
            return True
        await cls._cdp_tap_key(tab, key="ArrowDown", code="ArrowDown")
        await tab.sleep(0.25)
        await cls._cdp_tap_key(tab, key="Enter", code="Enter")
        await tab.sleep(0.45)
        return await cls._location_field_looks_valid(tab)

    @classmethod
    def _normalize_address_token(cls, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    @classmethod
    async def _read_lbc_location_value(cls, tab: Tab) -> str:
        raw = await tab.evaluate(
            """
            (() => {
              const el =
                document.querySelector('div[data-rhf-name="location"] input[name="location"]')
                || document.querySelector('input[data-spark-component="combobox-input"][name="location"]')
                || document.querySelector('input[name="location"][role="combobox"]');
              return el ? String(el.value || '').trim() : '';
            })()
            """,
            return_by_value=True,
        )
        return str(raw or "").strip()

    @classmethod
    def _location_value_looks_duplicated(cls, value: str, postal_code: str) -> bool:
        pc = postal_code.strip()
        if not value or not pc:
            return False
        if value.count(pc) >= 2:
            return True
        low = value.lower()
        # Même numéro de voie répété deux fois (cache LBC + resaisie).
        m = re.search(r"^(\d+\s+\S+)", value.strip(), re.I)
        if m:
            token = m.group(1).lower()
            if low.count(token) >= 2:
                return True
        return False

    @classmethod
    async def _location_keep_leboncoin_prefill(cls, tab: Tab, postal_code: str = "") -> bool:
        """
        Leboncoin préremplit souvent l’adresse (cache compte).
        Si le champ contient déjà une adresse non dupliquée, on ne la touche pas.
        """
        value = await cls._read_lbc_location_value(tab)
        if len(value) < 5:
            return False
        pc = postal_code.strip()
        if pc and cls._location_value_looks_duplicated(value, pc):
            return False
        return True

    @classmethod
    async def _clear_lbc_location_input(cls, tab: Tab, el: Element, css_selector: str) -> None:
        sel_json = json.dumps(css_selector)
        await tab.evaluate(
            f"""
            (() => {{
              const el = document.querySelector({sel_json});
              if (!el) return false;
              el.focus();
              el.click();
              const proto = Object.getPrototypeOf(el);
              const desc = Object.getOwnPropertyDescriptor(proto, 'value')
                || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
              if (desc && desc.set) desc.set.call(el, '');
              else el.value = '';
              el.dispatchEvent(new Event('input', {{ bubbles: true }}));
              el.dispatchEvent(new Event('change', {{ bubbles: true }}));
              return true;
            }})()
            """,
            return_by_value=True,
        )
        await el.click()
        await cls._cdp_tap_key(tab, key="a", code="KeyA", modifiers=2)
        await cls._cdp_tap_key(tab, key="Backspace", code="Backspace")
        try:
            await el.clear_input()
        except Exception:
            pass
        await tab.sleep(0.15)

    @classmethod
    async def _location_field_looks_valid(cls, tab: Tab) -> bool:
        raw = await tab.evaluate(
            """
            (() => {
              const el =
                document.querySelector('div[data-rhf-name="location"] input[name="location"]')
                || document.querySelector('input[data-spark-component="combobox-input"][name="location"]')
                || document.querySelector('input[name="location"][role="combobox"]');
              if (!el) return false;
              const v = (el.value || '').trim();
              if (v.length < 5) return false;
              return el.getAttribute('aria-invalid') !== 'true';
            })()
            """,
            return_by_value=True,
        )
        return raw is True

    @classmethod
    async def _type_lbc_location_combobox(cls, tab: Tab, text: str) -> bool:
        pc_in_query = re.search(r"\b(\d{5})\b", text)
        pc = pc_in_query.group(1) if pc_in_query else ""
        if await cls._location_keep_leboncoin_prefill(tab, pc):
            logger.info("Leboncoin: adresse préremplie conservée (pas de saisie)")
            return True
        for sel in _ADDRESS_LBC_SELECTORS:
            el: Element | None = None
            try:
                el = await tab.select(sel, timeout=2.5)
            except Exception:
                el = None
            if el is None:
                continue
            try:
                await el.scroll_into_view()
                await tab.sleep(0.25)
                current = await cls._read_lbc_location_value(tab)
                if current and cls._location_value_looks_duplicated(current, pc):
                    await cls._clear_lbc_location_input(tab, el, sel)
                elif current and len(current) >= 5:
                    logger.info("Leboncoin: adresse déjà dans le champ, pas d’effacement")
                    return True
                await el.click()
                await tab.sleep(0.15)
                await el.send_keys(text)
                await tab.sleep(0.45)
                if await cls._input_value_matches(tab, sel, text):
                    logger.info("Leboncoin adresse saisie (send_keys) via %s", sel)
                    return True
                await el.click()
                await tab.send(cdp_input.insert_text(text))
                await tab.sleep(0.35)
                if await cls._input_value_matches(tab, sel, text):
                    logger.info("Leboncoin adresse saisie (CDP insertText) via %s", sel)
                    return True
            except Exception as exc:
                logger.debug("Leboncoin saisie adresse %s: %s", sel, exc)
        return False

    @classmethod
    async def _input_value_matches(cls, tab: Tab, css_selector: str, expected: str) -> bool:
        sel_json = json.dumps(css_selector)
        exp_json = json.dumps(expected.strip())
        raw = await tab.evaluate(
            f"""
            (() => {{
              const el = document.querySelector({sel_json});
              if (!el) return false;
              const v = (el.value || '').trim();
              const exp = {exp_json};
              return v.length >= 4 && (v === exp || v.includes(exp.slice(0, 12)));
            }})()
            """,
            return_by_value=True,
        )
        return raw is True

    @classmethod
    async def _wait_for_address_suggestions(cls, tab: Tab, *, timeout_sec: float = 8.0) -> bool:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            found = await tab.evaluate(
                """
                (() => {
                  const sels = [
                    '[role="option"]',
                    '[role="listbox"] [role="option"]',
                    '[data-spark-component="combobox-item"]',
                  ];
                  for (const sel of sels) {
                    const el = document.querySelector(sel);
                    if (el) {
                      const r = el.getBoundingClientRect();
                      if (r.width > 4 && r.height > 4) return true;
                    }
                  }
                  return false;
                })()
                """,
                return_by_value=True,
            )
            if found is True:
                return True
            await tab.sleep(0.35)
        return False

    @classmethod
    async def _fill_leboncoin_pickup_address(
        cls,
        tab: Tab,
        *,
        address_line1: str,
        postal_code: str,
        city: str,
        progress: FormProgressFn | None,
    ) -> bool:
        line = address_line1.strip()
        pc = postal_code.strip()
        town = city.strip()
        if not line or not pc or not town:
            return False
        query = f"{line}, {pc} {town}"
        if await cls._location_keep_leboncoin_prefill(tab, pc):
            existing = await cls._read_lbc_location_value(tab)
            if progress:
                await progress(
                    {
                        "type": "log",
                        "step": "form",
                        "message": f"Adresse de remise (Leboncoin) : {existing[:80]}",
                        "form_step": "pickup_address",
                    }
                )
            return True
        typed = await cls._type_lbc_location_combobox(tab, query)
        if not typed:
            sel = await cls._first_matching_selector(tab, _ADDRESS_LBC_SELECTORS)
            if sel:
                typed = await cls._set_input_value(tab, sel, query)
        if not typed:
            logger.warning("Leboncoin: impossible de saisir l’adresse de remise (%s).", query)
            if progress:
                await progress(
                    {
                        "type": "log",
                        "step": "form",
                        "message": "Adresse de remise : saisie automatique échouée.",
                        "form_step": "pickup_address",
                    }
                )
            return False
        await tab.sleep(1.0)
        await cls._wait_for_address_suggestions(tab, timeout_sec=10.0)
        picked = await cls._pick_address_suggestion(tab, pc, town)
        if not picked:
            await tab.sleep(0.8)
            picked = await cls._pick_address_suggestion(tab, pc, town)
        valid = picked or await cls._location_field_looks_valid(tab)
        if progress:
            await progress(
                {
                    "type": "log",
                    "step": "form",
                    "message": f"Adresse de remise : {line}, {pc} {town}"
                    + (" (validée)" if valid else " (suggestion requise)"),
                    "form_step": "pickup_address",
                }
            )
        return valid

    @classmethod
    async def _select_leboncoin_parcel_size_small(cls, tab: Tab) -> bool:
        """Carte Pokémon → « Colis petit » (≤ 100 g), pas « Colis moyen »."""
        raw = await tab.evaluate(
            """
            (() => {
              const norm = (s) => String(s || '')
                .normalize('NFD').replace(/\\p{M}/gu, '')
                .replace(/[''´`]/g, "'")
                .toLowerCase();

              const body = norm(document.body.innerText || '');
              const looksSmall =
                body.includes('colis petit') ||
                (body.includes('jusqu') && body.includes('100 g') && !body.includes('250 g'));
              if (looksSmall && !body.includes('colis moyen')) {
                return 'already';
              }

              const clickEl = (el) => {
                if (!el) return false;
                el.scrollIntoView({ block: 'center', behavior: 'instant' });
                el.click();
                return true;
              };

              for (const el of document.querySelectorAll('button, [role="button"], [role="radio"], label, li, div')) {
                const t = norm(el.textContent || '');
                if (!t || t.length > 120) continue;
                if (
                  t.includes('colis petit') ||
                  (t.includes('petit') && t.includes('colis') && t.includes('100'))
                ) {
                  if (clickEl(el.closest('button, [role="radio"], label') || el)) {
                    return 'picked';
                  }
                }
              }

              for (const el of document.querySelectorAll('button, [role="button"], div, span')) {
                const t = norm(el.textContent || '');
                if (t.includes('colis moyen') && t.length < 90) {
                  clickEl(el.closest('button, [role="button"]') || el);
                  break;
                }
              }

              for (const btn of document.querySelectorAll('button[aria-label*="colis" i], button[aria-label*="Colis" i]')) {
                if (clickEl(btn)) break;
              }

              for (const el of document.querySelectorAll('[role="radio"], [role="option"], button, label')) {
                const t = norm(el.textContent || '');
                if (!t || t.length > 100) continue;
                if (t.includes('colis petit') || (t.includes('petit') && t.includes('100'))) {
                  if (clickEl(el)) return 'picked';
                }
              }
              return 'miss';
            })()
            """,
            return_by_value=True,
        )
        if raw in ("already", "picked"):
            await tab.sleep(0.5)
            return True
        return False

    @classmethod
    async def _wizard_fill_late_steps(
        cls,
        tab: Tab,
        *,
        description: str,
        price_eur: float,
        postal_code: str,
        address_line1: str,
        city: str,
        progress: FormProgressFn | None,
    ) -> bool:
        """
        Remplit les étapes description, prix, localisation et livraison jusqu'au bouton de dépôt.

        Returns:
            Vrai quand le champ prix a gardé le prix de l'article.
        """
        zip_clean = postal_code.strip()
        has_confirmed_price = False
        for step in range(12):
            await cls._wait_for_wizard_step(tab)
            if await cls._page_has_final_submit(tab):
                break
            if not await cls._location_keep_leboncoin_prefill(tab, postal_code.strip()):
                await cls._fill_leboncoin_pickup_address(
                    tab,
                    address_line1=address_line1,
                    postal_code=postal_code,
                    city=city,
                    progress=progress,
                )
            if description and await cls._fill_first(tab, _DESC_SELECTORS, description[:4000]):
                if progress:
                    await progress(
                        {
                            "type": "log",
                            "step": "form",
                            "message": "Description renseignée.",
                            "form_step": "description",
                        }
                    )
            is_article_price_shown = await cls._fill_price(tab, price_eur)
            if is_article_price_shown is not None:
                if is_article_price_shown and not has_confirmed_price and progress:
                    await progress(
                        {
                            "type": "log",
                            "step": "form",
                            "message": f"Prix {format_leboncoin_price(price_eur)} € renseigné.",
                            "form_step": "price",
                        }
                    )
                has_confirmed_price = is_article_price_shown
            if zip_clean and await cls._fill_first(tab, _ZIP_SELECTORS, zip_clean, pick_suggestion=True):
                if progress:
                    await progress(
                        {
                            "type": "log",
                            "step": "form",
                            "message": f"Localisation {zip_clean}.",
                            "form_step": "location",
                        }
                    )
            if await cls._select_leboncoin_parcel_size_small(tab):
                if progress:
                    await progress(
                        {
                            "type": "log",
                            "step": "form",
                            "message": "Livraison : colis petit (≤ 100 g).",
                            "form_step": "parcel_small",
                        }
                    )
            if await cls._page_has_final_submit(tab):
                break
            if not await cls._click_continue(tab):
                await tab.sleep(0.6)
                if await cls._page_has_final_submit(tab):
                    break
                logger.debug("Leboncoin wizard: pas de « Continuer » (étape %s).", step)
                break
            await tab.sleep(0.75)
        return has_confirmed_price

    @classmethod
    async def _current_url(cls, tab: Tab) -> str:
        raw = await tab.evaluate("location.href", return_by_value=True)
        return str(raw or "")

    @classmethod
    async def _accept_didomi_cookies(cls, tab: Tab, timeout_sec: float = 12.0) -> None:
        """Didomi consent banner (blocks form interaction until dismissed)."""
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            await tab
            clicked = await tab.evaluate(
                """
                (() => {
                  const ids = ['#didomi-agree-to-all', '#didomi-notice-agree-button'];
                  for (const id of ids) {
                    const el = document.querySelector(id);
                    if (el && typeof el.click === 'function') { el.click(); return 'id'; }
                  }
                  const qa = document.querySelector('[data-qa-id="didomi_cta_accept_cookies"]');
                  if (qa && typeof qa.click === 'function') { qa.click(); return 'qa'; }
                  const btns = [...document.querySelectorAll('button')];
                  for (const b of btns) {
                    const t = (b.textContent || '').toLowerCase();
                    if (t.includes('accepter') && t.includes('fermer')) {
                      b.click();
                      return 'text';
                    }
                  }
                  for (const a of document.querySelectorAll('a, button, [role="button"]')) {
                    const t = (a.textContent || '').trim().toLowerCase();
                    if (t.includes('continuer sans accepter')) {
                      a.click();
                      return 'skip';
                    }
                  }
                  return '';
                })()
                """,
                return_by_value=True,
            )
            if clicked:
                logger.info("Leboncoin Didomi dismissed (%s)", clicked)
                await tab.sleep(0.45)
                return
            await asyncio.sleep(0.15)
        logger.debug("Leboncoin Didomi banner not found (may already be accepted).")

    @classmethod
    async def read_login_state_from_tab(cls, tab: Tab) -> dict[str, Any]:
        """Best-effort DOM probe (used while the login helper Chrome is open)."""
        await cls._accept_didomi_cookies(tab)
        raw = await tab.evaluate(
            """
            JSON.stringify((() => {
              const url = location.href || '';
              if (/auth\\.leboncoin\\.fr/i.test(url)) {
                return { logged_in: false, reason: 'auth_host' };
              }
              const body = (document.body && document.body.innerText) || '';
              if (/\\bse déconnecter\\b/i.test(body)) {
                return { logged_in: true, reason: 'logout_link' };
              }
              const header =
                document.querySelector('header') ||
                document.querySelector('[role="banner"]') ||
                document.querySelector('[data-test-id="header"]');
              let headerLogin = false;
              if (header) {
                for (const el of header.querySelectorAll('a, button, [role="button"]')) {
                  const t = (el.textContent || '').trim().toLowerCase();
                  if (t === 'se connecter' || t === 'me connecter') {
                    headerLogin = true;
                    break;
                  }
                }
              }
              const hasMessages = !!document.querySelector(
                'a[href*="/messages"], a[href*="messages.leboncoin"]'
              );
              const hasDeposit = !!document.querySelector('a[href*="deposer-une-annonce"]');
              const hasAccountNav = !!document.querySelector(
                'a[href*="/account/"], a[href*="/compte/"], a[href*="mon-compte"]'
              );
              if ((hasMessages || hasDeposit) && !headerLogin) {
                return { logged_in: true, reason: 'nav_logged_in' };
              }
              if (hasDeposit && !headerLogin) {
                return { logged_in: true, reason: 'deposit_nav' };
              }
              if (/mes-annonces/i.test(url) && !headerLogin) {
                return { logged_in: true, reason: 'mes_annonces' };
              }
              if (/\\/favorites/i.test(url) && !headerLogin) {
                return { logged_in: true, reason: 'favorites' };
              }
              if (
                (/\\/account\\//i.test(url) || /mon-compte/i.test(url)) &&
                (hasAccountNav || hasMessages) &&
                !headerLogin
              ) {
                return { logged_in: true, reason: 'account_area' };
              }
              return { logged_in: false, reason: headerLogin ? 'login_header' : 'unknown' };
            })())
            """,
            return_by_value=True,
        )
        try:
            data = json.loads(str(raw or "{}"))
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        return {"logged_in": bool(data.get("logged_in")), "reason": data.get("reason")}

    @classmethod
    def _url_is_member_area(cls, url: str) -> bool:
        low = (url or "").lower()
        if "auth.leboncoin.fr" in low:
            return False
        return bool(_MEMBER_AREA_PATH_RE.search(low))

    @classmethod
    async def _cdp_has_auth_cookie(cls) -> bool:
        browser = cls._browser
        if browser is None:
            return False
        conn = getattr(browser, "connection", None)
        if conn is None:
            return False
        try:
            import nodriver.cdp.storage as cdp_storage  # type: ignore

            cookies = await asyncio.wait_for(conn.send(cdp_storage.get_cookies()), timeout=10.0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Leboncoin CDP get_cookies: %s", exc)
            return False
        for item in cookies or []:
            name = getattr(item, "name", None)
            domain = getattr(item, "domain", None)
            value = getattr(item, "value", None)
            if name is None and isinstance(item, dict):
                name = item.get("name")
                domain = item.get("domain")
                value = item.get("value")
            from services.leboncoin_profile_session_service import is_signed_in_leboncoin_cookie

            if is_signed_in_leboncoin_cookie(str(name or ""), str(domain or ""), value):
                return True
        return False

    @classmethod
    async def confirm_session_ready(cls, tab: Tab) -> bool:
        """
        Validate a real session: « Mes annonces » must load without auth redirect.
        Prefer an auth cookie via CDP when available (HttpOnly).
        """
        await tab.get(ACCOUNT_URL)
        await tab.sleep(1.4)
        await cls._accept_didomi_cookies(tab)
        url = await cls._current_url(tab)
        if "auth.leboncoin.fr" in url.lower():
            return False
        if LOGIN_URL_PATTERN.search(url):
            return False
        if await cls._page_shows_login_gate(tab):
            return False
        dom = await cls.read_login_state_from_tab(tab)
        if not dom.get("logged_in"):
            return False
        if await cls._cdp_has_auth_cookie():
            return True
        return cls._url_is_member_area(url)

    @classmethod
    async def try_confirm_session_on_current_page(cls, tab: Tab) -> bool:
        """Validate session without forcing navigation (current tab may already be /favorites)."""
        await cls._accept_didomi_cookies(tab)
        url = await cls._current_url(tab)
        if "auth.leboncoin.fr" in url.lower() or LOGIN_URL_PATTERN.search(url):
            return False
        if await cls._page_shows_login_gate(tab):
            return False
        dom = await cls.read_login_state_from_tab(tab)
        if not dom.get("logged_in"):
            return False
        if await cls._cdp_has_auth_cookie():
            return True
        return cls._url_is_member_area(url)

    @classmethod
    async def safe_close_browser_graceful(cls) -> None:
        """CDP Browser.close so Chromium flushes cookies to the profile (Cardmarket pattern)."""
        browser = cls._browser
        tab = cls._tab
        if browser is None:
            return
        if tab is not None:
            try:
                await asyncio.wait_for(tab.get("about:blank"), timeout=5.0)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Leboncoin pre-close about:blank: %s", exc)
        try:
            import nodriver.cdp.browser as cdp_browser  # type: ignore

            connection = getattr(browser, "connection", None)
            if connection is not None:
                try:
                    await asyncio.wait_for(connection.send(cdp_browser.close()), timeout=5.0)
                    logger.info("Leboncoin browser: graceful CDP Browser.close sent")
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Leboncoin CDP Browser.close: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Leboncoin CDP import: %s", exc)
        try:
            await asyncio.sleep(2.5)
        except asyncio.CancelledError:
            pass
        cls.close_browser()

    @classmethod
    async def _page_shows_login_gate(cls, tab: Tab) -> bool:
        """True only on auth URLs or a visible header « Se connecter » (not footer/marketing links)."""
        raw = await tab.evaluate(
            """
            JSON.stringify((() => {
              const url = location.href || '';
              if (/auth\\.leboncoin\\.fr/i.test(url)) return true;
              if (/(compte\\/connexion|connexion-securite|login|authentification)/i.test(url)) return true;
              const header =
                document.querySelector('header') ||
                document.querySelector('[role="banner"]') ||
                document.querySelector('[data-test-id="header"]');
              if (!header) return false;
              for (const el of header.querySelectorAll('a, button, [role="button"]')) {
                const t = (el.textContent || '').trim().toLowerCase();
                if (t === 'se connecter' || t === 'me connecter') return true;
              }
              return false;
            })())
            """,
            return_by_value=True,
        )
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() == "true"

    @classmethod
    async def open_login_browser(cls) -> dict[str, Any]:
        """Open Chromium on « Mes annonces » (redirect login si besoin). Browser stays open."""
        await cls.init_browser()
        tab = await cls._browser.get(ACCOUNT_URL)  # type: ignore[union-attr]
        cls._tab = tab
        await tab.sleep(0.8)
        await cls._accept_didomi_cookies(tab)
        return {"opened": True, "url": await cls._current_url(tab)}

    @classmethod
    async def _clear_stale_session_marker(cls) -> None:
        from services.leboncoin_profile_session_service import clear_leboncoin_session_info

        profile = resolve_leboncoin_nodriver_user_data_dir(os.environ.get("LEBONCOIN_USER_DATA_DIR"))
        clear_leboncoin_session_info(profile)

    @classmethod
    async def _deposit_page_is_login_wall(cls, tab: Tab) -> bool:
        """True when /deposer-une-annonce shows « Me connecter » instead of the wizard."""
        url = await cls._current_url(tab)
        if "auth.leboncoin.fr" in url.lower() or LOGIN_URL_PATTERN.search(url):
            return True
        raw = await tab.evaluate(
            """
            JSON.stringify((() => {
              const hasTitle = !!document.querySelector(
                'input[aria-label*="titre" i], input[placeholder*="titre" i], input[name="subject"]'
              );
              if (hasTitle) return false;
              const body = (document.body && document.body.innerText) || '';
              if (/connectez-vous ou créez un compte/i.test(body)) return true;
              if (/me connecter/i.test(body) && /créer un compte/i.test(body)) return true;
              for (const b of document.querySelectorAll('button')) {
                const t = (b.textContent || '').trim().toLowerCase();
                if (t === 'me connecter') return true;
              }
              return false;
            })())
            """,
            return_by_value=True,
        )
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() == "true"

    @classmethod
    async def ensure_logged_in(cls, progress: FormProgressFn | None = None) -> None:
        """Vérifie la session sur la page de dépôt (pas seulement le JSON local)."""
        await cls.open_deposit_form(progress)

    @classmethod
    async def open_deposit_form(cls, progress: FormProgressFn | None = None) -> None:
        tab = cls._require_tab()
        await tab.get(DEPOSIT_URL)
        await tab.sleep(0.9)
        await cls._accept_didomi_cookies(tab)
        if await cls._deposit_page_is_login_wall(tab):
            await cls._clear_stale_session_marker()
            raise RuntimeError(_SESSION_RECONNECT_MSG)
        if not await cls._first_matching_selector(tab, _TITLE_SELECTORS):
            await cls._clear_stale_session_marker()
            raise RuntimeError(_SESSION_RECONNECT_MSG)
        if progress:
            await progress({"type": "log", "step": "auth", "message": "Session Leboncoin OK.", "form_step": "auth_ok"})
            await progress(
                {
                    "type": "log",
                    "step": "page",
                    "message": "Formulaire « Déposer une annonce » ouvert.",
                    "form_step": "deposit_page",
                }
            )

    @classmethod
    async def run_deposit_wizard(
        cls,
        *,
        title: str,
        description: str,
        price_eur: float,
        postal_code: str,
        address_line1: str,
        city: str,
        photo_basenames: list[str],
        listing_fields: Any,
        progress: FormProgressFn | None = None,
        submit_final: bool = True,
    ) -> dict[str, Any]:
        """Assistant Leboncoin (2025+) : titre → détails → prix / description → envoi ou brouillon."""
        tab = cls._require_tab()
        category_kw = getattr(listing_fields, "category_suggestion", DEFAULT_CATEGORY_LABEL) or "Collection"

        if progress:
            await progress(
                {
                    "type": "log",
                    "step": "form",
                    "message": "Étape 1 — titre et catégorie…",
                    "form_step": "wizard_title",
                }
            )
        await cls._wizard_step_title_and_category(tab, title, str(category_kw))

        if progress:
            await progress(
                {
                    "type": "log",
                    "step": "form",
                    "message": "Étape 2 — photos et attributs carte…",
                    "form_step": "wizard_details",
                }
            )
        await cls.upload_photos(photo_basenames, progress)
        await tab.sleep(0.8)
        await cls._wizard_fill_structured_attributes(
            tab,
            produit=getattr(listing_fields, "produit", "Jeux de cartes"),
            etat=getattr(listing_fields, "etat", "Très bon état"),
            conditionnement=getattr(listing_fields, "conditionnement", "Sans emballage"),
            epoque=getattr(listing_fields, "epoque", None),
        )
        if not await cls._click_continue(tab):
            raise RuntimeError("Bouton « Continuer » introuvable après les photos / attributs.")

        if progress:
            await progress(
                {
                    "type": "log",
                    "step": "form",
                    "message": "Étape 3 — description, prix, localisation…",
                    "form_step": "wizard_late",
                }
            )
        has_confirmed_price = await cls._wizard_fill_late_steps(
            tab,
            description=description,
            price_eur=price_eur,
            postal_code=postal_code,
            address_line1=address_line1,
            city=city,
            progress=progress,
        )
        is_article_price_shown_on_final_page = await cls._fill_price(tab, price_eur)
        if is_article_price_shown_on_final_page is not None:
            has_confirmed_price = is_article_price_shown_on_final_page

        if not submit_final:
            url = await cls._current_url(tab)
            if progress:
                await progress(
                    {
                        "type": "log",
                        "step": "dry_run",
                        "message": "Brouillon prêt — envoi final désactivé (vérifiez dans Chrome).",
                        "form_step": "dry_run_ready",
                    }
                )
            return {"published": False, "dry_run": True, "url": url}

        if not has_confirmed_price:
            raise RuntimeError(
                f"Le prix {format_leboncoin_price(price_eur)} € n'a pas pu être saisi : annonce non déposée, "
                "pour ne pas la publier au prix suggéré par Leboncoin."
            )
        return await cls.submit_and_wait(progress)

    @classmethod
    async def upload_photos(cls, photo_basenames: list[str], progress: FormProgressFn | None = None) -> None:
        tab = cls._require_tab()
        root = get_project_root()
        paths = [str(root / "images" / name) for name in photo_basenames]
        for p in paths:
            if not Path(p).is_file():
                raise RuntimeError(f"Photo introuvable pour Leboncoin : {p}")

        file_sel = await cls._first_matching_selector(tab, _FILE_INPUT_SELECTORS)
        if not file_sel:
            await cls._click_button_containing(tab, "photo")
            await tab.sleep(0.8)
            file_sel = await cls._first_matching_selector(tab, _FILE_INPUT_SELECTORS)
        if not file_sel:
            raise RuntimeError("Input fichier photo introuvable sur Leboncoin.")
        input_el = await tab.select(file_sel, timeout=20)
        if not isinstance(input_el, Element):
            raise RuntimeError("Input photo Leboncoin non interactif.")
        await input_el.send_file(*paths)
        if progress:
            await progress(
                {
                    "type": "log",
                    "step": "images",
                    "message": f"{len(paths)} photo(s) envoyée(s).",
                    "form_step": "photos_ok",
                }
            )
        await tab.sleep(1.2)

    @classmethod
    async def _on_boost_options_page(cls, tab: Tab) -> bool:
        url = (await cls._current_url(tab)).lower()
        return "/deposer-une-annonce/options" in url

    @classmethod
    async def _click_skip_boost(cls, tab: Tab) -> bool:
        """Page « Boostez votre annonce » — sticky bar en bas."""
        clicked = await tab.evaluate(
            """
            (() => {
              const bar = document.querySelector('[data-qa-id="stickyBarElement"]');
              if (bar) {
                bar.scrollIntoView({ block: 'end', behavior: 'instant' });
                const btn = bar.querySelector('button');
                if (btn) {
                  btn.click();
                  return true;
                }
              }
              for (const b of document.querySelectorAll('button')) {
                const t = (b.textContent || '').trim().toLowerCase();
                if (t.includes('sans booster')) {
                  b.scrollIntoView({ block: 'center', behavior: 'instant' });
                  b.click();
                  return true;
                }
              }
              return false;
            })()
            """,
            return_by_value=True,
        )
        if clicked is True:
            await tab.sleep(0.55)
            return True
        for label in _SKIP_BOOST_BUTTON_TEXT:
            if await cls._click_button_containing(tab, label):
                return True
        return False

    @classmethod
    async def _click_publish(cls, tab: Tab) -> bool:
        if await cls._on_boost_options_page(tab):
            return await cls._click_skip_boost(tab)
        for css in _PUBLISH_BUTTON_CSS:
            btn = await tab.select(css, timeout=4)
            if isinstance(btn, Element):
                await btn.click()
                return True
        for label in _PUBLISH_BUTTON_TEXT:
            clicked = await tab.evaluate(
                f"""
                (() => {{
                    const needle = {json.dumps(label.lower())};
                    for (const b of document.querySelectorAll('button')) {{
                        const t = (b.textContent || '').trim().toLowerCase();
                        if (t === needle || t.includes(needle)) {{
                            b.click();
                            return true;
                        }}
                    }}
                    return false;
                }})()
                """,
                return_by_value=True,
            )
            if clicked is True:
                return True
        return False

    @staticmethod
    def _extract_listing_id(url: str) -> str | None:
        for pat in PUBLISHED_URL_PATTERNS:
            m = pat.search(url)
            if m:
                return m.group(1)
        return None

    @classmethod
    async def _newest_listing_id_with_title(cls, tab: Tab, title: str) -> str | None:
        """Identifiant de l'annonce la plus récente de « Mes annonces » dont le lien porte ce titre."""
        listing_id = await tab.evaluate(
            f"""
            (() => {{
              const normalize = (text) => (text || '')
                .normalize('NFKD').replace(/[\\u0300-\\u036f]/g, '')
                .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
              const wantedTitle = normalize({json.dumps(title)});
              let newestListingId = null;
              for (const anchor of document.querySelectorAll('a[href*="/ad/"]')) {{
                const match = (anchor.getAttribute('href') || '').match(/\\/ad\\/[^/?#]+\\/(\\d{{4,}})/);
                if (!match || !normalize(anchor.textContent).includes(wantedTitle)) continue;
                if (newestListingId === null || Number(match[1]) > Number(newestListingId)) newestListingId = match[1];
              }}
              return newestListingId;
            }})()
            """,
            return_by_value=True,
        )
        return str(listing_id) if isinstance(listing_id, str) and listing_id else None

    @classmethod
    async def find_listing_id_in_my_ads(cls, title: str, *, timeout_sec: float = 60.0) -> str | None:
        """
        Retrouve l'annonce déposée dans « Mes annonces », où Leboncoin l'affiche une fois validée (15 à 25 s après le dépôt).

        Returns:
            L'identifiant de l'annonce, ou None si elle n'y apparaît pas avant la fin du délai.
        """
        tab = cls._require_tab()
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            await tab.get(MY_ADS_URL)
            reload_at = min(deadline, time.monotonic() + _MY_ADS_RELOAD_SEC)
            while time.monotonic() < reload_at:
                await tab.sleep(1.0)
                listing_id = await cls._newest_listing_id_with_title(tab, title)
                if listing_id:
                    return listing_id
        return None

    @classmethod
    async def _read_my_ads_list_state(cls, tab: Tab) -> dict[str, int] | None:
        """
        Compte les annonces affichées dans « Mes annonces » et le total en ligne annoncé par l'onglet.

        Returns:
            ``{"shown": n, "online": total}``, ou None tant que l'onglet « En ligne » n'est pas affiché.
        """
        raw = await tab.evaluate(
            """
            (() => {
              const onlineTab = document.querySelector('[data-qa-id="online_ads_tab"]');
              if (!onlineTab) return null;
              const total = ((onlineTab.textContent || '').match(/\\((\\d+)\\)/) || [])[1];
              return JSON.stringify({
                shown: document.querySelectorAll('li[data-qa-id="ad_item_container"]').length,
                online: total === undefined ? -1 : Number(total),
              });
            })()
            """,
            return_by_value=True,
        )
        if not isinstance(raw, str):
            return None
        state = json.loads(raw)
        return {"shown": int(state["shown"]), "online": int(state["online"])}

    @classmethod
    async def _wait_for_my_ads_list(cls, tab: Tab) -> dict[str, int]:
        """
        Attend que « Mes annonces » affiche ses annonces (ou un compte vide).

        Raises:
            RuntimeError: session expirée, ou liste jamais affichée.
        """
        deadline = time.monotonic() + _MY_ADS_LIST_TIMEOUT_SEC
        while time.monotonic() < deadline:
            if await cls._page_shows_login_gate(tab):
                await cls._clear_stale_session_marker()
                raise RuntimeError(_DELETE_SESSION_RECONNECT_MSG)
            state = await cls._read_my_ads_list_state(tab)
            if state is not None and (state["shown"] > 0 or state["online"] == 0):
                return state
            await tab.sleep(0.8)
        raise RuntimeError("« Mes annonces » ne s’est pas affiché sur Leboncoin.")

    @classmethod
    async def _mark_delete_trigger_of_listing(cls, tab: Tab, listing_id: str | None, title: str) -> int:
        """
        Pose le marqueur sur la corbeille de l'annonce visée : par son identifiant, sinon par son titre exact.

        Returns:
            Le nombre d'annonces affichées qui correspondent (0 : absente, plus de 1 : ambiguë, rien n'est marqué).
        """
        raw = await tab.evaluate(
            f"""
            (() => {{
              const listingId = {json.dumps(listing_id or "")};
              const normalize = (text) => (text || '')
                .normalize('NFKD').replace(/[\\u0300-\\u036f]/g, '')
                .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
              const wantedTitle = normalize({json.dumps(title)});
              const marker = {json.dumps(_DELETE_TRIGGER_MARKER)};
              document.querySelectorAll('[' + marker + ']').forEach((el) => el.removeAttribute(marker));
              const listingHref = new RegExp('/(?:ad/[^/]+|annonce)/' + listingId + '(?:[/?#]|$)');
              const matches = [...document.querySelectorAll('li[data-qa-id="ad_item_container"]')].filter((card) => {{
                if (listingId) {{
                  return [...card.querySelectorAll('a[href]')].some((a) => listingHref.test(a.getAttribute('href') || ''));
                }}
                const shownTitle = card.querySelector('a[href*="/ad/"] p[title]');
                return !!shownTitle && normalize(shownTitle.getAttribute('title')) === wantedTitle;
              }});
              if (matches.length !== 1) return JSON.stringify({{ matchCount: matches.length, isMarked: false }});
              const trigger = [...matches[0].querySelectorAll('button[aria-haspopup="dialog"][title="Supprimer"]')]
                .find((button) => button.getClientRects().length > 0);
              if (trigger) trigger.setAttribute(marker, '1');
              return JSON.stringify({{ matchCount: 1, isMarked: !!trigger }});
            }})()
            """,
            return_by_value=True,
        )
        # nodriver renvoie l'erreur JS au lieu de la lever : sans réponse lisible, ne jamais conclure à une absence.
        if not isinstance(raw, str):
            raise RuntimeError("Lecture de « Mes annonces » impossible sur Leboncoin.")
        search = json.loads(raw)
        if search["matchCount"] == 1 and not search["isMarked"]:
            raise RuntimeError("Bouton « Supprimer » introuvable sur l’annonce dans « Mes annonces ».")
        return int(search["matchCount"])

    @classmethod
    async def _find_listing_delete_trigger(cls, tab: Tab, listing_id: str | None, title: str) -> bool:
        """
        Cherche l'annonce dans « Mes annonces », en faisant défiler la liste tant que Leboncoin en charge d'autres.

        Returns:
            True quand la corbeille de l'annonce est marquée, False quand toute la liste est chargée sans elle.

        Raises:
            RuntimeError: plusieurs annonces portent ce titre, ou la liste n'a pas pu être chargée en entier
                (l'annonce n'est alors jamais déclarée absente à tort).
        """
        state = await cls._wait_for_my_ads_list(tab)
        for _ in range(_MY_ADS_MAX_SCROLL_LOADS):
            match_count = await cls._mark_delete_trigger_of_listing(tab, listing_id, title)
            if match_count == 1:
                return True
            if match_count > 1:
                raise RuntimeError(
                    f"{match_count} annonces Leboncoin portent ce titre : supprimez la bonne depuis « Mes annonces »."
                )
            if 0 <= state["online"] <= state["shown"]:
                return False
            shown_before = state["shown"]
            await tab.evaluate("(() => { window.scrollTo(0, document.body.scrollHeight); return true; })()")
            await tab.sleep(2.5)
            state = await cls._wait_for_my_ads_list(tab)
            if state["shown"] <= shown_before:
                break
        raise RuntimeError("« Mes annonces » n’a pas chargé toutes vos annonces : l’annonce n’a pas été trouvée.")

    @classmethod
    async def _click_in_page(cls, tab: Tab, css_selector: str, *, timeout_sec: float) -> bool:
        """
        Clique un élément dès que React y a branché ses gestionnaires (un clic plus tôt serait perdu).

        Returns:
            True si l'élément a été cliqué avant la fin du délai.
        """
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            clicked = await tab.evaluate(
                f"""
                (() => {{
                  const el = document.querySelector({json.dumps(css_selector)});
                  if (!el || el.disabled || !Object.keys(el).some((key) => key.startsWith('__reactProps'))) return false;
                  el.scrollIntoView({{ block: 'center' }});
                  el.click();
                  return true;
                }})()
                """,
                return_by_value=True,
            )
            if clicked is True:
                return True
            await tab.sleep(0.4)
        return False

    @classmethod
    async def _wait_for_delete_outcome(cls, tab: Tab) -> None:
        """
        Attend la réponse de Leboncoin après « Valider » : le questionnaire de suppression s'affiche quand elle est acceptée.

        Raises:
            RuntimeError: Leboncoin affiche une erreur, ou ne répond pas dans le délai.
        """
        deadline = time.monotonic() + _DELETE_OUTCOME_TIMEOUT_SEC
        while time.monotonic() < deadline:
            raw = await tab.evaluate(
                f"""
                (() => {{
                  if (document.querySelector({json.dumps(_DELETE_ACCEPTED_CSS)})) return JSON.stringify({{ accepted: true }});
                  const confirm = document.querySelector({json.dumps(_DELETE_CONFIRM_CSS)});
                  const dialog = confirm && confirm.closest('[role="dialog"]');
                  const error = dialog && dialog.querySelector('.text-error');
                  return JSON.stringify({{
                    accepted: false,
                    error: error ? (error.textContent || '').trim() : '',
                  }});
                }})()
                """,
                return_by_value=True,
            )
            outcome = json.loads(raw) if isinstance(raw, str) else {}
            if outcome.get("accepted"):
                return
            error = str(outcome.get("error") or "")
            if _ALREADY_BEING_DELETED_ERROR.search(error):
                return
            if error:
                raise RuntimeError(f"Leboncoin a refusé la suppression : {error}")
            await tab.sleep(0.5)
        raise RuntimeError("Leboncoin n’a pas confirmé la suppression de l’annonce.")

    @classmethod
    async def delete_listing(cls, listing_id: str | None, title: str) -> bool:
        """
        Supprime une annonce comme à la main : « Mes annonces », corbeille, puis « Valider » (retrait du site sous 45 min).

        Args:
            listing_id: Identifiant Leboncoin de l'annonce, quand GoupixDex l'a relevé au dépôt.
            title: Titre exact de l'annonce, utilisé seulement sans identifiant.

        Returns:
            True si Leboncoin a accepté la suppression, False si l'annonce n'est déjà plus en ligne.

        Raises:
            RuntimeError: session expirée, annonce ambiguë, ou suppression refusée par Leboncoin.
        """
        tab = cls._require_tab()
        await tab.get(MY_ADS_URL)
        await cls._accept_didomi_cookies(tab, timeout_sec=4.0)
        numeric_listing_id = re.sub(r"\D", "", listing_id or "") or None
        if not await cls._find_listing_delete_trigger(tab, numeric_listing_id, title):
            return False
        trigger_css = f"[{_DELETE_TRIGGER_MARKER}]"
        if not await cls._click_in_page(tab, trigger_css, timeout_sec=_DELETE_DIALOG_TIMEOUT_SEC):
            raise RuntimeError("Impossible d’ouvrir la fenêtre « Supprimer l’annonce » de Leboncoin.")
        if not await cls._click_in_page(tab, _DELETE_CONFIRM_CSS, timeout_sec=_DELETE_DIALOG_TIMEOUT_SEC):
            raise RuntimeError("Bouton « Valider » introuvable dans la fenêtre de suppression Leboncoin.")
        await cls._wait_for_delete_outcome(tab)
        return True

    @classmethod
    async def submit_and_wait(
        cls,
        progress: FormProgressFn | None = None,
        *,
        timeout_sec: float = 180.0,
    ) -> dict[str, Any]:
        tab = cls._require_tab()
        if progress:
            await progress(
                {
                    "type": "log",
                    "step": "publish",
                    "message": "Envoi de l’annonce… (captcha DataDome : validez dans la fenêtre Chrome si besoin).",
                    "form_step": "publish_click",
                }
            )
        if not await cls._click_publish(tab):
            raise RuntimeError(
                "Bouton « Déposer mon annonce » introuvable — complétez le formulaire manuellement dans Chrome."
            )

        deadline = time.monotonic() + timeout_sec
        last_url = ""
        while time.monotonic() < deadline:
            await tab.sleep(0.5)
            url = await cls._current_url(tab)
            last_url = url
            if any(p.search(url) for p in CONFIRMED_URL_PATTERNS):
                listing_id = cls._extract_listing_id(url)
                return {"published": True, "listing_id": listing_id, "url": url}
            if re.search(r"/mes-annonces|/compte/part/mes-annonces", url, re.I):
                return {"published": True, "listing_id": cls._extract_listing_id(url), "url": url}
            if await cls._on_boost_options_page(tab):
                if progress:
                    await progress(
                        {
                            "type": "log",
                            "step": "publish",
                            "message": "Options de boost — clic « Déposer sans booster »…",
                            "form_step": "skip_boost",
                        }
                    )
                await cls._click_skip_boost(tab)
            elif await cls._page_has_final_submit(tab):
                await cls._click_publish(tab)
            if "datadome" in url.lower() and progress:
                await progress(
                    {
                        "type": "log",
                        "step": "captcha",
                        "message": "DataDome — résolvez le captcha dans Chrome…",
                        "form_step": "datadome",
                    }
                )
        raise RuntimeError(
            f"Publication Leboncoin non confirmée avant timeout (dernière URL : {urlparse(last_url).path or last_url})."
        )

    @classmethod
    async def publish_pokemon_listing(
        cls,
        *,
        title: str,
        description: str,
        price_eur: float,
        postal_code: str,
        address_line1: str,
        city: str,
        photo_basenames: list[str],
        listing_fields: Any,
        progress: FormProgressFn | None = None,
        submit_final: bool = True,
    ) -> dict[str, Any]:
        """Session → assistant dépôt → (optionnel) envoi final."""
        await cls.open_deposit_form(progress)
        return await cls.run_deposit_wizard(
            title=title,
            description=description,
            price_eur=price_eur,
            postal_code=postal_code,
            address_line1=address_line1,
            city=city,
            photo_basenames=photo_basenames,
            listing_fields=listing_fields,
            progress=progress,
            submit_final=submit_final,
        )
