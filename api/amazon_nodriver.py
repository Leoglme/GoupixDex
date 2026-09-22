"""
nodriver: start Chrome (persistent profile), sign-in, CDP cookie export, tab-based HTML fallback.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, Tuple

import nodriver as uc
from nodriver.cdp import input_ as cdp_input
from nodriver.core.connection import Connection
from nodriver.core.tab import Tab

import amazon_config
from amazon_config import AMAZON_BASE_URL, AMAZON_CHROME_EXECUTABLE
from amazon_http import write_amazon_cookies_json_from_profile
from nodriver_executor import DedicatedAsyncLoop

_browser_holder: dict[str, Any] = {"browser": None}


def _profile_dir() -> str:
    return amazon_config.AMAZON_USER_DATA_DIR


def _cookies_export_file() -> str:
    return amazon_config.AMAZON_COOKIES_EXPORT_FILE


def _register_log(msg: str) -> None:
    """Stdout + journal profil + copie globale (LocalAppData/GoupixDex)."""
    line = f"[amazon-register] {msg}"
    print(line, flush=True)
    paths = [os.path.join(_profile_dir(), "amazon-register.log")]
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        paths.append(os.path.join(local, "GoupixDex", "amazon-register-latest.log"))
    for path in paths:
        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def _js_run(expression: str) -> str:
    """
    nodriver ``evaluate(..., return_by_value=True)`` must receive an *expression*.
    ``() => {{ ... }}`` alone yields a Function ``RemoteObject`` — wrap as IIFE.
    """
    expr = expression.strip()
    if expr.startswith("() =>"):
        return f"({expr})()"
    return expr


def _ensure_profile_dir() -> None:
    os.makedirs(_profile_dir(), exist_ok=True)


async def _ensure_browser_async():
    _ensure_profile_dir()
    b = _browser_holder["browser"]
    if b is not None and not b.stopped:
        return b
    kwargs: dict[str, Any] = {
        "user_data_dir": _profile_dir(),
        "headless": False,
        "sandbox": False,
        "browser_args": [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
            "--disable-dev-shm-usage",
        ],
    }
    if AMAZON_CHROME_EXECUTABLE:
        kwargs["browser_executable_path"] = AMAZON_CHROME_EXECUTABLE
    browser = await uc.start(**kwargs)
    _browser_holder["browser"] = browser
    return browser


def _schedule_close_browser_after_login() -> None:
    """Close Chrome without blocking the end of ``login_to_amazon_async``: otherwise the HTTP
    POST /api/login response would only leave after ``browser.stop()`` (can hang on Windows)."""

    async def _runner() -> None:
        try:
            await close_browser_async()
        except Exception as e:
            print(f"[nodriver] browser close after login (background): {e!r}")

    try:
        asyncio.get_running_loop().create_task(_runner())
    except RuntimeError:
        try:
            close_browser_sync()
        except Exception as e:
            print(f"[nodriver] synchronous close after login: {e!r}")


def _force_kill_browser_process(b: Any) -> None:
    """Last resort if ``Browser.stop()`` hangs (nodriver + Chrome on Windows)."""
    proc = getattr(b, "_process", None)
    pid = getattr(b, "_process_pid", None)
    if proc is not None:
        for action in ("terminate", "kill"):
            fn = getattr(proc, action, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
    if not pid:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=15,
                text=True,
            )
        except Exception as e:
            print(f"[nodriver] taskkill PID {pid}: {e!r}")
    else:
        try:
            os.kill(int(pid), 15)
        except Exception:
            try:
                os.kill(int(pid), 9)
            except Exception:
                pass


async def close_browser_async() -> None:
    """Close Chrome with timeout: if the window was closed manually, stop() may hang forever."""
    b = _browser_holder["browser"]
    if b is None:
        return

    def _sync_stop() -> None:
        try:
            if not getattr(b, "stopped", True):
                b.stop()
        except Exception:
            pass

    try:
        await asyncio.wait_for(asyncio.to_thread(_sync_stop), timeout=25.0)
    except asyncio.TimeoutError:
        print("[nodriver] browser.stop() timeout - attempting taskkill", flush=True)
        _force_kill_browser_process(b)
    except Exception as e:
        print(f"[nodriver] browser.stop(): {e}", flush=True)
    finally:
        _browser_holder["browser"] = None


def run_browser(coro, timeout: float = 600):
    return DedicatedAsyncLoop.instance().run(coro, timeout=timeout)


def close_browser_sync() -> None:
    """Same logic as close_browser_async (timeout on stop, holder cleared)."""
    try:
        DedicatedAsyncLoop.instance().run(close_browser_async(), timeout=90)
    except Exception as e:
        print(f"[nodriver] close_browser_sync: {e}")
    finally:
        _browser_holder["browser"] = None


async def export_cookies_requests_format():
    browser = await _ensure_browser_async()
    tab = await browser.get(AMAZON_BASE_URL)
    await browser.sleep(1.5)
    await _accept_amazon_cookie_consent(tab, browser)
    await browser.sleep(0.5)
    return await browser.cookies.get_all(requests_cookie_format=True)


async def prime_session_and_export_cookies_async():
    """Open the homepage then return cookies (CDP) for httpx."""
    browser = await _ensure_browser_async()
    tab = await browser.get(AMAZON_BASE_URL)
    await browser.sleep(2)
    await _accept_amazon_cookie_consent(tab, browser)
    await browser.sleep(0.8)
    return await browser.cookies.get_all(requests_cookie_format=True)


async def _accept_amazon_cookie_consent(tab: Any, browser: Any, timeout_sec: float = 14.0) -> bool:
    """Amazon.fr GDPR banner (``#sp-cc-accept`` / « Accepter »)."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        await tab
        for sel in (
            "#sp-cc-accept",
            "input#sp-cc-accept",
            "button#sp-cc-accept",
            '[data-action="sp-cc-accept"]',
        ):
            try:
                el = await tab.select(sel, timeout=1)
                if el:
                    await el.click()
                    await browser.sleep(0.35)
                    return True
            except Exception:
                continue
        try:
            clicked = await _tab_eval_value(
                tab,
                """
                () => {
                  const direct = document.querySelector('#sp-cc-accept');
                  if (direct) { direct.click(); return true; }
                  const nodes = document.querySelectorAll('button, input[type="submit"], a, span[role="button"]');
                  for (const el of nodes) {
                    const t = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
                    if (/^accepter$/i.test(t) || /^accept$/i.test(t)) {
                      el.click();
                      return true;
                    }
                  }
                  return false;
                }
                """,
            )
            if clicked is True:
                await browser.sleep(0.35)
                return True
        except Exception:
            pass
        await asyncio.sleep(0.2)
    return False


async def fetch_html_via_tab(url: str) -> str:
    browser = await _ensure_browser_async()
    tab = await browser.get(url)
    await browser.sleep(1.5)
    if await _accept_amazon_cookie_consent(tab, browser):
        tab = await browser.get(url)
        await browser.sleep(1.2)
    await tab
    return await tab.get_content()


_GREETING_JS = (
    "(() => { const el = document.querySelector('#nav-link-accountList-nav-line-1');"
    " return el && el.textContent ? el.textContent.trim() : ''; })()"
)
_SIGNED_OUT_GREETING_MARKERS = ("identifiez", "s'identifier", "s’identifier", "sign in", "connectez")


async def session_state_via_browser_async() -> str:
    """« ready » si le message d'accueil Amazon nomme un compte, « needs_login » sinon (profil lié)."""
    browser = await _ensure_browser_async()
    tab = await browser.get(AMAZON_BASE_URL)
    await browser.sleep(2)
    await _accept_amazon_cookie_consent(tab, browser)
    await tab
    try:
        greeting = await asyncio.wait_for(tab.evaluate(_GREETING_JS), timeout=8)
    except Exception:
        return "needs_login"
    text = str(greeting or "").strip()
    if not text:
        return "needs_login"
    lowered = text.casefold()
    if any(marker in lowered for marker in _SIGNED_OUT_GREETING_MARKERS):
        return "needs_login"
    return "ready"


_INVITE_BUTTON_SELECTORS = (
    'input[name="submit.inviteButton"]',
    "#hdp-invite-button input",
    "#hdp-invite-button",
)


async def click_request_invite_async(dp_url: str) -> Dict[str, Any]:
    """Ouvre la fiche, clique « Demander une invitation » comme l'utilisateur, renvoie le HTML avant/après."""
    browser = await _ensure_browser_async()
    tab = await browser.get(dp_url)
    await browser.sleep(2)
    if await _accept_amazon_cookie_consent(tab, browser):
        tab = await browser.get(dp_url)
        await browser.sleep(1.5)
    await tab
    before = await tab.get_content()

    clicked = False
    for selector in _INVITE_BUTTON_SELECTORS:
        try:
            btn = await tab.select(selector, timeout=4)
        except Exception:
            btn = None
        if btn:
            await btn.click()
            clicked = True
            break
    if not clicked:
        return {"clicked": False, "html_before": before, "html_after": before}

    await browser.sleep(3)
    tab = await browser.get(dp_url)
    await browser.sleep(2)
    await tab
    after = await tab.get_content()
    return {"clicked": True, "html_before": before, "html_after": after}


async def _input_value_matches(tab: Any, selector: str, expected: str) -> bool:
    sel = json.dumps(selector)
    exp = json.dumps(expected)
    try:
        ok = await _tab_eval_value(
            tab,
            f"""
            (() => {{
              const el = document.querySelector({sel});
              if (!el) return false;
              return String(el.value || '').trim() === {exp}.trim();
            }})()
            """,
        )
        return bool(ok)
    except Exception:
        return False


async def _set_input_value_native(tab: Any, selector: str, value: str) -> bool:
    """React / Amazon auth inputs often ignore plain ``el.value = …``."""
    escaped = json.dumps(value)
    sel = json.dumps(selector)
    script = f"""
    (() => {{
      const el = document.querySelector({sel});
      if (!el) return false;
      el.focus();
      const proto = window.HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
      if (setter) {{
        setter.call(el, {escaped});
      }} else {{
        el.value = {escaped};
      }}
      el.dispatchEvent(new Event('input', {{ bubbles: true }}));
      el.dispatchEvent(new Event('change', {{ bubbles: true }}));
      return true;
    }})()
    """
    try:
        ok = await _tab_eval_value(tab, script)
        return bool(ok)
    except Exception:
        return False


async def _amazon_insert_text_cdp(tab: Any, text: str) -> None:
    await tab.send(cdp_input.insert_text(text))


async def _amazon_type_in_input(tab: Any, selector: str, value: str, timeout: float = 6) -> bool:
    try:
        el = await tab.select(selector, timeout=timeout)
        if el is None:
            return False
        await el.scroll_into_view()
        await el.click()
        await asyncio.sleep(0.25)
        await el.apply(
            """(element) => {
              element.focus();
              if ('select' in element) element.select();
              element.value = '';
            }"""
        )
        await asyncio.sleep(0.1)
        await _amazon_insert_text_cdp(tab, value)
        await asyncio.sleep(0.25)
        return True
    except Exception as exc:
        _register_log(f"type_in_input {selector!r}: {exc!r}")
        return False


async def _fill_amazon_field(tab: Any, selector: str, value: str, timeout: float = 6) -> bool:
    if await _amazon_type_in_input(tab, selector, value, timeout=timeout):
        if await _input_value_matches(tab, selector, value):
            return True
    if await _set_input_value_native(tab, selector, value):
        return await _input_value_matches(tab, selector, value)
    return False


async def _set_input_value(tab: Any, selector: str, value: str) -> bool:
    return await _fill_amazon_field(tab, selector, value)


def _is_cdp_transport_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    msg = str(exc).lower()
    return (
        "ConnectionRefused" in name
        or "connection" in msg
        or "websocket" in msg
        or "closed" in msg
        or "disconnect" in msg
    )


def _is_nodriver_tab(obj: Any) -> bool:
    """``browser.tabs`` / ``main_tab`` can expose ``Connection`` or ``TargetInfo`` — only ``Tab`` is usable."""
    return isinstance(obj, Tab)


def _normalize_eval_result(raw: Any) -> Any:
    """nodriver renvoie parfois un ``RemoteObject`` alors que le JS a bien réussi (objets / booléens)."""
    if raw is None or isinstance(raw, (bool, str, int, float, dict, list)):
        return raw
    val = getattr(raw, "value", None)
    if isinstance(val, (dict, list, bool, str, int, float)):
        return val
    dsv = getattr(raw, "deep_serialized_value", None)
    if dsv is not None:
        inner = getattr(dsv, "value", None)
        if isinstance(inner, dict):
            return inner
        if isinstance(inner, list):
            if inner and isinstance(inner[0], (list, tuple)) and len(inner[0]) >= 2:
                out: dict[str, Any] = {}
                for item in inner:
                    if not isinstance(item, (list, tuple)) or len(item) < 2:
                        continue
                    key, payload = item[0], item[1]
                    if isinstance(payload, dict) and "value" in payload:
                        out[str(key)] = payload["value"]
                    else:
                        out[str(key)] = payload
                if out:
                    return out
            return inner
    return raw


async def _tab_eval_value(tab: Any, expression: str) -> Any:
    raw = await tab.evaluate(_js_run(expression), return_by_value=True)
    return _normalize_eval_result(raw)


def _coerce_connection_to_tab(browser: Any, obj: Any) -> Tab | None:
    """``update_targets()`` peut remplacer les ``Tab`` par des ``Connection`` sans ``evaluate``."""
    if obj is None:
        return None
    if isinstance(obj, Tab):
        return obj
    if isinstance(obj, Connection):
        try:
            return Tab(obj.websocket_url, obj.target, browser)
        except Exception:
            return None
    return None


async def _tab_cdp_ping(tab: Any) -> bool:
    if not _is_nodriver_tab(tab):
        return False
    try:
        return (await _tab_eval_value(tab, "() => true")) is True
    except Exception:
        return False


async def _tab_url(tab: Any) -> str:
    try:
        if _is_nodriver_tab(tab):
            return (tab.target.url or "") if tab.target else ""
        url = getattr(tab, "url", None)
        return str(url or "")
    except Exception:
        return ""


async def _first_live_tab(browser: Any, url_hint: str = "") -> Tab | None:
    try:
        await browser.update_targets()
    except Exception:
        pass
    hint = (url_hint or "").lower()
    candidates: list[Any] = list(getattr(browser, "targets", []) or [])
    candidates.extend(getattr(browser, "tabs", []) or [])
    seen: set[int] = set()
    ordered: list[Any] = []
    for raw in candidates:
        t = _coerce_connection_to_tab(browser, raw)
        if t is None:
            continue
        tid = id(t)
        if tid in seen:
            continue
        seen.add(tid)
        ordered.append(t)
    if hint:
        for t in ordered:
            u = await _tab_url(t)
            if hint in u.lower() and await _tab_cdp_ping(t):
                return t
    for t in reversed(ordered):
        u = await _tab_url(t)
        if "/ap/" in u.lower() and await _tab_cdp_ping(t):
            return t
    for t in reversed(ordered):
        if await _tab_cdp_ping(t):
            return t
    return None


async def _ensure_nodriver_tab(browser: Any, tab: Any) -> Tab:
    coerced = _coerce_connection_to_tab(browser, tab)
    if coerced is not None:
        tab = coerced
    if _is_nodriver_tab(tab) and await _tab_cdp_ping(tab):
        await _try_activate_tab(tab)
        return tab
    hint = await _tab_url(tab)
    found = await _first_live_tab(browser, hint)
    if found is not None:
        await _try_activate_tab(found)
        return found
    if _is_nodriver_tab(tab):
        return tab
    raise RuntimeError("Aucun onglet Chrome nodriver utilisable (Tab CDP)")


async def _try_activate_tab(tab: Any) -> None:
    try:
        await tab.activate()
    except Exception:
        pass


async def _refresh_amazon_tab(browser: Any, fallback: Any) -> Tab:
    try:
        return await _ensure_nodriver_tab(browser, fallback)
    except RuntimeError:
        _register_log("CDP inactif — recherche d’un onglet Tab…")
        found = await _first_live_tab(browser, await _tab_url(fallback))
        if found is None:
            raise
        return found


def _html_is_amazon_soft_404(html: str) -> bool:
    low = (html or "").lower()
    return "ne correspond à aucune page" in low or "vous recherchez quelque chose" in low


async def _open_amazon_auth_for_register(browser: Any, base_url: str) -> Tab:
    """
    Accueil Amazon → clic « Identifiez-vous » (ne pas ouvrir /ap/signin dans la barre d’adresse :
    Amazon renvoie souvent une fausse 404).
    """
    last_exc: Exception | None = None
    tab: Tab | None = None
    for attempt in range(2):
        _register_log(f"Ouverture connexion Amazon (tentative {attempt + 1}/2)…")
        try:
            if tab is None:
                tab = await browser.get(base_url)
            else:
                cur = await _tab_url(tab)
                if "/ap/" not in cur:
                    tab = await browser.get(base_url)
            tab = _coerce_connection_to_tab(browser, tab) or tab
            await browser.sleep(1.6 if attempt == 0 else 1.2)
            await _accept_amazon_cookie_consent(tab, browser, timeout_sec=4 if attempt == 0 else 3)
            cur = await _tab_url(tab)
            if "/ap/" in cur:
                tab = await _ensure_nodriver_tab(browser, tab)
                return tab
            btn = await tab.select('a[data-nav-role="signin"]', timeout=8)
            if btn is None:
                raise RuntimeError("Lien « Identifiez-vous » introuvable sur l’accueil.")
            await btn.mouse_click()
            try:
                await tab
            except StopIteration as exc:
                raise RuntimeError("Onglet Chrome perdu après le clic connexion.") from exc
            except Exception:
                pass
            await browser.sleep(2.0)
            await _try_activate_tab(tab)
            try:
                html = await tab.get_content()
            except Exception as exc:
                _register_log(f"Lecture HTML: {exc!r}")
                html = ""
            if _html_is_amazon_soft_404(html):
                _register_log("Page erreur Amazon après clic — nouvel essai depuis l’accueil.")
                tab = None
                continue
            if await _wait_for_amazon_auth_page(tab, browser, timeout_sec=6):
                tab = await _ensure_nodriver_tab(browser, tab)
                return tab
            _register_log("Pas de page /ap/ après clic — nouvel essai.")
            tab = None
        except Exception as exc:
            last_exc = exc if isinstance(exc, Exception) else RuntimeError(str(exc))
            _register_log(f"Échec tentative {attempt + 1}: {last_exc!r}")
            await browser.sleep(0.8)
    raise RuntimeError(
        "Impossible d’ouvrir la page de connexion Amazon. "
        f"Dernière erreur: {last_exc or 'inconnue'}"
    )


async def _fill_amazon_email_one_shot(browser: Any, tab: Any, email: str) -> Tuple[bool, Any]:
    """Remplit l’e-mail dans la page via un seul ``evaluate`` (moins de allers-retours CDP)."""
    email_lit = json.dumps(email)
    script = f"""
    () => {{
      const email = {email_lit};
      const isVisible = (el) => {{
        if (!el || el.disabled || el.type === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 8 && r.height > 8;
      }};
      const applyValue = (el) => {{
        el.focus();
        el.click();
        const setter = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype,
          'value',
        )?.set;
        if (setter) setter.call(el, email);
        else el.value = email;
        try {{
          el.dispatchEvent(new InputEvent('input', {{
            bubbles: true,
            inputType: 'insertFromPaste',
            data: email,
          }}));
        }} catch (_e) {{
          el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        }}
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        return String(el.value || '').trim() === email.trim();
      }};
      let el = null;
      for (const lab of document.querySelectorAll('label')) {{
        const t = (lab.textContent || '').toLowerCase();
        if (!/adresse|mail|e-mail|email|mobile|téléphone|telephone/.test(t)) continue;
        const id = lab.getAttribute('for');
        if (id) el = document.getElementById(id);
        if (!isVisible(el)) el = lab.querySelector('input');
        if (isVisible(el)) break;
        el = null;
      }}
      if (!isVisible(el)) {{
        for (const s of [
          '#ap_email_login',
          '#ap_email',
          'input[name="email"]',
          'input[type="email"]',
          '#auth-email-input',
        ]) {{
          el = document.querySelector(s);
          if (isVisible(el)) break;
          el = null;
        }}
      }}
      if (!isVisible(el)) {{
        return {{ ok: false, reason: 'no_visible_email_input' }};
      }}
      const ok = applyValue(el);
      return {{
        ok,
        id: el.id || null,
        name: el.name || null,
        len: (el.value || '').length,
      }};
    }}
    """
    tab = _coerce_connection_to_tab(browser, tab) or tab
    await _try_activate_tab(tab)
    try:
        result = await _tab_eval_value(tab, script)
        if isinstance(result, dict) and result.get("ok"):
            _register_log(
                f"E-mail saisi (#{result.get('id') or result.get('name')}, len={result.get('len')})"
            )
            return True, tab
        if result is not True:
            _register_log(f"Saisie e-mail refusée (JS): {result!r}")
    except Exception as exc:
        _register_log(f"Saisie e-mail JS: {exc!r}")
    sel = await _find_visible_amazon_email_selector(tab)
    if sel:
        try:
            el = await tab.select(sel, timeout=0.8)
            if el is not None:
                await el.mouse_click()
                await el.apply("(e) => { e.focus(); if (e.select) e.select(); e.value=''; }")
                await _amazon_insert_text_cdp(tab, email)
                if await _input_value_matches(tab, sel, email):
                    _register_log(f"E-mail saisi (insertText {sel})")
                    return True, tab
        except Exception as exc:
            _register_log(f"insertText ({sel}): {exc!r}")
    await _debug_dump_auth_inputs(tab)
    return False, tab


async def _wait_for_amazon_auth_page(tab: Any, browser: Any, timeout_sec: float = 22) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            url = (tab.target.url or "") if tab.target else ""
        except Exception:
            url = ""
        if "/ap/" in url:
            _register_log(f"Page auth détectée: {url[:140]}")
            return True
        await tab
        await browser.sleep(0.12)
    _register_log("Timeout en attente de la page /ap/ (connexion Amazon)")
    return False


async def _debug_dump_auth_inputs(tab: Any) -> None:
    try:
        info = await _tab_eval_value(
            tab,
            """
            () => {
              const vis = (el) => {
                if (!el || el.disabled) return false;
                const r = el.getBoundingClientRect();
                return r.width > 4 && r.height > 4;
              };
              return [...document.querySelectorAll('input')].map((el) => ({
                id: el.id || null,
                name: el.name || null,
                type: el.type || null,
                visible: vis(el),
                valueLen: (el.value || '').length,
                aria: el.getAttribute('aria-label'),
                placeholder: el.placeholder || null,
              }));
            }
            """,
        )
        _register_log(f"Inputs auth page: {json.dumps(info, ensure_ascii=False)[:900]}")
    except Exception as exc:
        _register_log(f"debug inputs failed: {exc!r}")


async def _focus_amazon_email_input(tab: Any) -> bool:
    try:
        ok = await _tab_eval_value(
            tab,
            """
            () => {
              const isVisible = (el) => {
                if (!el || el.disabled || el.type === 'hidden') return false;
                const r = el.getBoundingClientRect();
                return r.width > 8 && r.height > 8;
              };
              const focusEl = (el) => {
                if (!isVisible(el)) return false;
                el.focus();
                el.click();
                if ('select' in el) el.select();
                return true;
              };
              for (const lab of document.querySelectorAll('label')) {
                const t = (lab.textContent || '').toLowerCase();
                if (!/mail|e-mail|email|mobile|téléphone|telephone/.test(t)) continue;
                const id = lab.getAttribute('for');
                if (id && focusEl(document.getElementById(id))) return true;
                const inner = lab.querySelector('input');
                if (focusEl(inner)) return true;
              }
              for (const s of [
                '#ap_email_login',
                '#ap_email',
                'input[name="email"]',
                'input[type="email"]',
                '#auth-email-input',
              ]) {
                if (focusEl(document.querySelector(s))) return true;
              }
              const inputs = [...document.querySelectorAll('input')].filter(isVisible);
              const mailish = inputs.find((i) =>
                /mail|email|phone|mobile/i.test(
                  `${i.name}${i.id}${i.autocomplete}${i.placeholder}${i.getAttribute('aria-label') || ''}`,
                ),
              );
              return Boolean(mailish && focusEl(mailish));
            }
            """,
        )
        return bool(ok)
    except Exception as exc:
        _register_log(f"focus email: {exc!r}")
        return False


async def _fill_amazon_identifier_email_cdp(tab: Any, email: str) -> bool:
    if not await _focus_amazon_email_input(tab):
        return False
    await asyncio.sleep(0.35)
    try:
        await _amazon_insert_text_cdp(tab, email)
    except Exception as exc:
        _register_log(f"insertText: {exc!r}")
        return False
    await asyncio.sleep(0.25)
    exp = json.dumps(email)
    ok = await _tab_eval_value(
        tab,
        f"""
        () => {{
          const el = document.activeElement;
          if (!el || !('value' in el)) return false;
          return String(el.value || '').trim() === {exp}.trim();
        }}
        """,
    )
    if ok:
        _register_log("E-mail saisi (CDP insertText + focus libellé)")
        return True
    await _tab_eval_value(
        tab,
        f"""
        () => {{
          const el = document.activeElement;
          if (!el) return false;
          const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype,
            'value',
          )?.set;
          if (setter) setter.call(el, {exp});
          else el.value = {exp};
          el.dispatchEvent(new Event('input', {{ bubbles: true }}));
          el.dispatchEvent(new Event('change', {{ bubbles: true }}));
          return true;
        }}
        """,
    )
    ok2 = await _tab_eval_value(
        tab,
        f"""
        () => {{
          const el = document.activeElement;
          return el && String(el.value || '').trim() === {exp}.trim();
        }}
        """,
    )
    if ok2:
        _register_log("E-mail saisi (setter natif sur activeElement)")
    return bool(ok2)


async def _find_visible_amazon_email_selector(tab: Any) -> str | None:
    try:
        sel = await _tab_eval_value(
            tab,
            """
            () => {
              const candidates = [
                '#ap_email_login',
                '#ap_email',
                'input[name="email"]',
                'input[type="email"]',
                '#auth-email-input',
              ];
              for (const s of candidates) {
                const el = document.querySelector(s);
                if (!el || el.disabled || el.type === 'hidden') continue;
                const r = el.getBoundingClientRect();
                if (r.width < 8 || r.height < 8) continue;
                return s;
              }
              return null;
            }
            """,
        )
        return str(sel) if sel else None
    except Exception:
        return None


async def _try_submit_amazon_signin(tab: Any) -> None:
    for sel in ('#signInSubmit', 'input#signInSubmit', 'input[type="submit"]'):
        try:
            btn = await tab.select(sel, timeout=3)
            if btn:
                await btn.click()
                return
        except Exception:
            continue


async def _navigate_to_amazon_signin(tab: Any, browser: Any, base_url: str) -> None:
    """Homepage → « Identifiez-vous » (évite une ouverture directe /ap/signin souvent en erreur)."""
    await tab.get(base_url)
    await browser.sleep(3)
    await _accept_amazon_cookie_consent(tab, browser)
    try:
        btn = await tab.select('a[data-nav-role="signin"]', timeout=12)
        if btn:
            await btn.click()
            await browser.sleep(2)
            await _wait_for_amazon_auth_page(tab, browser)
            return
    except Exception as exc:
        _register_log(f"Clic Identifiez-vous: {exc!r}")
    login_url = f"{base_url}/ap/signin?openid.return_to={base_url}/"
    await tab.get(login_url)
    await browser.sleep(2)
    await _wait_for_amazon_auth_page(tab, browser)


async def _fill_amazon_identifier_email(
    tab: Any, email: str, browser: Any | None = None
) -> bool:
    """Champ « e-mail ou mobile » (page unifiée avant mot de passe / création)."""
    if browser is not None:
        ok, tab_ref = await _fill_amazon_email_one_shot(browser, tab, email)
        if ok:
            return True
        tab = tab_ref
    if await _fill_amazon_identifier_email_cdp(tab, email):
        return True
    visible = await _find_visible_amazon_email_selector(tab)
    if visible and await _fill_amazon_field(tab, visible, email):
        _register_log(f"E-mail saisi ({visible})")
        return True
    for sel in (
        "#ap_email_login",
        "#ap_email",
        'input[name="email"]',
        'input[type="email"]',
        "#auth-email-input",
    ):
        if await _fill_amazon_field(tab, sel, email, timeout=4):
            _register_log(f"E-mail saisi ({sel})")
            return True
    await _debug_dump_auth_inputs(tab)
    return False


async def _wait_and_fill_amazon_identifier_email(
    tab: Any, browser: Any, email: str, attempts: int = 1
) -> bool:
    ok, _tab = await _fill_amazon_email_one_shot(browser, tab, email)
    return ok


async def _click_amazon_auth_continue(tab: Any) -> bool:
    """Bouton « Continuer » sur les pages /ap/* (étape e-mail / mobile)."""
    browser = getattr(tab, "browser", None)
    if browser is not None:
        tab = _coerce_connection_to_tab(browser, tab) or tab
    for sel in (
        "#continue",
        "input#continue",
        "#auth-continue",
        "#auth-signin-button",
        'input[name="continue"]',
        'button[name="continue"]',
        "#intention-submit-button",
        "span#continue input",
        ".a-button-primary input",
    ):
        try:
            btn = await tab.select(sel, timeout=1.2)
            if btn:
                await btn.mouse_click()
                _register_log(f"Clic Continuer ({sel})")
                return True
        except Exception:
            continue
    try:
        clicked = await _tab_eval_value(
            tab,
            """
            () => {
              const isVisible = (el) => {
                if (!el || el.disabled) return false;
                const r = el.getBoundingClientRect();
                return r.width > 4 && r.height > 4;
              };
              const tryClick = (el) => {
                if (!isVisible(el)) return false;
                el.focus();
                el.click();
                return true;
              };
              for (const id of ['continue', 'auth-continue']) {
                const el = document.getElementById(id);
                if (tryClick(el)) return true;
              }
              for (const el of document.querySelectorAll(
                'input[type="submit"], button[type="submit"], input.a-button-input, .a-button-input'
              )) {
                const t = (el.value || el.innerText || el.getAttribute('aria-label') || '').trim();
                if (/continuer|^continue$/i.test(t) && tryClick(el)) return true;
              }
              const form = document.querySelector('#ap_login_form, form[action*="signin"]');
              if (form) {
                const sub = form.querySelector('input[type="submit"], .a-button-primary input');
                if (tryClick(sub)) return true;
              }
              return false;
            }
            """,
        )
        if clicked:
            _register_log("Clic Continuer (JS)")
        else:
            _register_log("Bouton Continuer introuvable sur la page")
        return bool(clicked)
    except Exception as exc:
        _register_log(f"Clic Continuer: {exc!r}")
        return False


async def _click_amazon_new_email_create_account(tab: Any, browser: Any) -> bool:
    """Page « Cet e-mail est nouveau pour nous » → bouton « Créer votre compte »."""
    b = getattr(tab, "browser", None) or browser
    if b is not None:
        tab = _coerce_connection_to_tab(b, tab) or tab
    for sel in (
        "#intention-submit-button",
        "#auth-register-create-account",
        "input#createAccountSubmit",
        "#createAccountSubmit",
        'input[name="createAccountSubmit"]',
        "form input.a-button-input",
        "#continue",
    ):
        try:
            el = await tab.select(sel, timeout=0.9)
            if el:
                await el.mouse_click()
                _register_log(f"Clic « Créer votre compte » ({sel})")
                return True
        except Exception:
            continue
    try:
        clicked = await _tab_eval_value(
            tab,
            """
            () => {
              const isVisible = (el) => {
                if (!el || el.disabled) return false;
                const r = el.getBoundingClientRect();
                return r.width > 4 && r.height > 4;
              };
              const label = (el) =>
                (el.value || el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim();
              for (const el of document.querySelectorAll(
                'input[type=submit], button, .a-button-input, span.a-button-inner input'
              )) {
                if (!isVisible(el)) continue;
                if (/cr[eé]er votre compte|create your account/i.test(label(el))) {
                  el.click();
                  return true;
                }
              }
              const body = (document.body.innerText || '').toLowerCase();
              if (body.includes('nouveau pour nous') || body.includes('new to us')) {
                const btn = document.querySelector('.a-button-primary input, input[type=submit]');
                if (isVisible(btn)) {
                  btn.click();
                  return true;
                }
              }
              return false;
            }
            """,
        )
        if clicked:
            _register_log("Clic « Créer votre compte » (JS)")
        return bool(clicked)
    except Exception as exc:
        _register_log(f"Clic « Créer votre compte »: {exc!r}")
        return False


async def _advance_to_amazon_registration_form(tab: Any, browser: Any) -> bool:
    """Après « Continuer » : interstitiel nouvel e-mail puis formulaire inscription."""
    deadline = time.time() + 10.0
    while time.time() < deadline:
        tab = await _ensure_nodriver_tab(browser, tab)
        if await _page_has_registration_name_field(tab):
            return True
        await _click_amazon_new_email_create_account(tab, browser)
        await browser.sleep(0.8)
        if await _page_has_registration_name_field(tab):
            return True
        await browser.sleep(0.2)
    return await _page_has_registration_name_field(tab)


async def _click_amazon_create_account_links(tab: Any, browser: Any) -> bool:
    """Liens « Créer un compte » / bascule inscription."""
    for sel in (
        "#createAccountSubmit",
        "a#createAccountSubmit",
        'a[data-action="switch-to-register"]',
        "#auth-create-account-link",
        "#auth-switch-to-register",
        'a[href*="/ap/register"]',
    ):
        try:
            link = await tab.select(sel, timeout=3)
            if link:
                await link.click()
                await browser.sleep(2)
                return True
        except Exception:
            continue
    try:
        clicked = await _tab_eval_value(
            tab,
            """
            () => {
              const nodes = document.querySelectorAll('a, button, span[role="button"]');
              for (const el of nodes) {
                const t = (el.innerText || '').trim();
                if (/cr[eé]er (un |votre )?compte/i.test(t) && !/professionnel/i.test(t)) {
                  el.click();
                  return true;
                }
              }
              return false;
            }
            """,
        )
        if clicked:
            await browser.sleep(2)
        return bool(clicked)
    except Exception:
        return False


async def _set_registration_input(tab: Any, selector: str, value: str) -> bool:
    """Inscription Amazon : setter natif d'abord (évite insertText CDP sur mauvais focus)."""
    if await _set_input_value_native(tab, selector, value):
        if await _input_value_matches(tab, selector, value):
            return True
    return await _fill_amazon_field(tab, selector, value, timeout=2.5)


async def _fill_amazon_registration_fields(
    tab: Any, email: str, password: str, customer_name: str
) -> None:
    del email  # déjà fixé par l'étape e-mail ; retoucher #ap_email append dans « Votre nom ».
    if not await _set_registration_input(tab, "#ap_customer_name", customer_name):
        await _set_registration_input(tab, 'input[name="customerName"]', customer_name)
    await _set_registration_input(tab, "#ap_password", password) or await _set_registration_input(
        tab, 'input[name="password"]', password
    )
    await _set_registration_input(tab, "#ap_password_check", password) or await _set_registration_input(
        tab, 'input[name="passwordCheck"]', password
    )


async def _click_amazon_registration_continue(tab: Any) -> bool:
    """Bouton jaune « Continuer » sur « Créer un compte » (#ap_register_form)."""
    browser = getattr(tab, "browser", None)
    if browser is not None:
        tab = _coerce_connection_to_tab(browser, tab) or tab
    for sel in (
        "#ap_register_form input#continue",
        "#ap_register_form #continue",
        "form[name='register'] input#continue",
        "#continue",
        "input#continue",
        'input[name="continue"]',
        "#auth-continue",
        ".a-button-primary input.a-button-input",
    ):
        try:
            btn = await tab.select(sel, timeout=1.2)
            if btn:
                await btn.mouse_click()
                _register_log(f"Clic Continuer inscription ({sel})")
                return True
        except Exception:
            continue
    try:
        clicked = await _tab_eval_value(
            tab,
            """
            () => {
              const isVisible = (el) => {
                if (!el || el.disabled) return false;
                const r = el.getBoundingClientRect();
                return r.width > 4 && r.height > 4;
              };
              const tryClick = (el) => {
                if (!isVisible(el)) return false;
                el.focus();
                el.click();
                return true;
              };
              const form = document.querySelector('#ap_register_form, form[name="register"]');
              if (form) {
                for (const el of form.querySelectorAll(
                  'input[type="submit"], button[type="submit"], .a-button-input, input.a-button-input'
                )) {
                  const t = (el.value || el.innerText || el.getAttribute('aria-label') || '').trim();
                  if (/continuer|^continue$/i.test(t) && tryClick(el)) return true;
                }
                const primary = form.querySelector('.a-button-primary input, #continue');
                if (tryClick(primary)) return true;
              }
              for (const el of document.querySelectorAll(
                'input[type="submit"], button[type="submit"], input.a-button-input, .a-button-input'
              )) {
                const t = (el.value || el.innerText || el.getAttribute('aria-label') || '').trim();
                if (/continuer|^continue$/i.test(t) && tryClick(el)) return true;
              }
              return false;
            }
            """,
        )
        if clicked:
            _register_log("Clic Continuer inscription (JS)")
        return bool(clicked)
    except Exception:
        return False


async def _amazon_auth_page_kind(tab: Any) -> str:
    """``identifier`` (e-mail/mobile), ``register`` (nom client), or ``unknown``."""
    try:
        kind = await _tab_eval_value(
            tab,
            """
            () => {
              const isVisible = (el) => {
                if (!el || el.disabled || el.type === 'hidden') return false;
                const r = el.getBoundingClientRect();
                return r.width > 8 && r.height > 8;
              };
              const nameEl = document.querySelector('#ap_customer_name')
                || document.querySelector('input[name="customerName"]');
              if (isVisible(nameEl)) return 'register';
              if (isVisible(document.querySelector('#ap_email_login'))) return 'identifier';
              const path = (location.pathname || '').toLowerCase();
              if (path.includes('/register')) return 'register';
              if (path.includes('/signin')) return 'identifier';
              for (const s of [
                '#ap_email', 'input[name="email"]', 'input[type="email"]', '#auth-email-input',
              ]) {
                if (isVisible(document.querySelector(s))) return 'identifier';
              }
              return 'unknown';
            }
            """,
        )
        if isinstance(kind, str):
            return kind
        return "unknown"
    except Exception:
        return "unknown"


async def _page_has_registration_name_field(tab: Any) -> bool:
    return (await _amazon_auth_page_kind(tab)) == "register"


async def _maybe_fill_amazon_credentials(tab: Any, email: str, password: str) -> bool:
    filled = False
    if await _set_input_value(tab, "#ap_email", email) or await _set_input_value(
        tab, 'input[name="email"]', email
    ):
        filled = True
    await asyncio.sleep(0.4)
    if await _set_input_value(tab, "#ap_password", password) or await _set_input_value(
        tab, 'input[name="password"]', password
    ):
        filled = True
    if filled:
        await asyncio.sleep(0.3)
        await _try_submit_amazon_signin(tab)
    return filled


async def login_to_amazon_async(
    email: str | None = None,
    password: str | None = None,
) -> Dict[str, Any]:
    """Sign-in (manual or auto-fill when ``email``/``password`` are set); cookies exported at the end."""
    # Reset a zombie session (Chrome closed manually, or stop() stuck).
    await close_browser_async()
    await asyncio.sleep(0.6)

    base_url = AMAZON_BASE_URL
    browser = await _ensure_browser_async()
    tab = await browser.get(base_url)
    await browser.sleep(3)
    await _accept_amazon_cookie_consent(tab, browser)

    try:
        btn = await tab.select('a[data-nav-role="signin"]', timeout=12)
        if btn:
            await btn.click()
            await browser.sleep(3)
    except Exception:
        login_url = f"{base_url}/ap/signin?openid.return_to={base_url}/"
        await tab.get(login_url)
        await browser.sleep(2)

    max_wait = 600
    start_time = time.time()
    error_redirect_count = 0
    max_error_redirects = 3
    last_status_time = time.time()
    logged_in_ready = False
    auto_creds = (email or "").strip(), (password or "").strip()
    credentials_attempted = False

    try:
        while time.time() - start_time < max_wait:
            await tab
            page_source = await tab.get_content()
            current_url = (tab.target.url or "") if tab.target else ""
            page_title = ""
            try:
                page_title = await tab.evaluate("document.title")
            except Exception:
                pass

            if time.time() - last_status_time > 10:
                elapsed = int(time.time() - start_time)
                remaining = int(max_wait - elapsed)
                print(f"   [time] Elapsed: {elapsed}s | Remaining: {remaining}s")
                print(f"   Current URL: {current_url[:80]}...")
                print(f"   Title: {str(page_title)[:50]}...")
                last_status_time = time.time()

            is_error_page = (
                "ne correspond à aucune page active" in page_source
                or "Vous recherchez quelque chose" in page_source
                or "ap_error_page" in page_source
                or ("404" in str(page_title) if page_title else False)
            )

            if is_error_page and error_redirect_count < max_error_redirects:
                print("   [warn] Error page detected, redirecting to homepage...")
                await tab.get(base_url)
                error_redirect_count += 1
                await browser.sleep(3)
                continue

            if error_redirect_count >= max_error_redirects and is_error_page:
                raise RuntimeError("Too many error pages after authentication")

            is_on_amazon_page = (
                "amazon.fr" in current_url
                and "/ap/" not in current_url
                and not is_error_page
            )

            has_amazon_elements = any(
                x in page_source
                for x in (
                    "nav-link-accountList",
                    "nav-cart",
                    "Bonjour,",
                    "Retours et Commandes",
                )
            )

            if is_on_amazon_page and has_amazon_elements:
                logged_in_ready = True
                print(f"   [ok] Sign-in success! Amazon page detected: {current_url}")
                break

            auth_url_keywords = [
                "/ap/signin",
                "/ap/cvf",
                "/ap/mfa",
                "/ap/register",
                "/ap/challenge",
                "/ap/dcq",
            ]
            is_auth_url = any(k in current_url for k in auth_url_keywords)
            has_auth_form = any(
                x in page_source
                for x in (
                    "ap_signin_form",
                    "ap_password",
                    "auth-mfa-form",
                    "cvf-widget-form",
                )
            )

            if is_auth_url or has_auth_form:
                if (
                    auto_creds[0]
                    and auto_creds[1]
                    and not credentials_attempted
                    and "ap_password" in page_source
                ):
                    credentials_attempted = True
                    print("   [auto] Filling Amazon email/password…")
                    await _maybe_fill_amazon_credentials(tab, auto_creds[0], auto_creds[1])
                    await browser.sleep(4)
                    continue
                if "qr" in page_source.lower() and "scan" in page_source.lower():
                    print("   [qr] QR code detected - scan with your phone...")
                elif "cvf" in current_url or "mfa" in current_url:
                    print("   [mfa] Two-factor authentication in progress...")
                else:
                    print("   Sign-in page - enter your credentials...")
                await browser.sleep(5)
                continue

            print(f"   Waiting for redirect... (URL: {current_url[:50]}...)")
            await browser.sleep(5)
        else:
            raise TimeoutError("Wait time exceeded (10 minutes)")

        if not logged_in_ready:
            raise RuntimeError("Inconsistent login state after wait loop")

        # Do not call CDP ``Storage.getCookies``: with nodriver it can hang forever and never
        # finish POST /api/login (GoupixDex: close Chrome then read SQLite from profile).
        print(
            "[nodriver] Short pause then close Chrome -> export cookies from on-disk SQLite...",
            flush=True,
        )
        await asyncio.sleep(1.0)

        print("[nodriver] Closing browser (unlock Cookies SQLite file)...", flush=True)
        await close_browser_async()
        await asyncio.sleep(0.6)

        ok_file = await asyncio.to_thread(
            write_amazon_cookies_json_from_profile,
            _profile_dir(),
            _cookies_export_file(),
        )
        if ok_file:
            print(
                f"\nSIGN-IN OK - cookies written from profile -> {_cookies_export_file()}",
                flush=True,
            )
            return {
                "success": True,
                "message": "Sign-in successful. Cookies saved.",
            }

        print(
            "\nSIGN-IN OK - JSON export failed; session still in Chromium profile "
            f"({_profile_dir()}).",
            flush=True,
        )
        return {
            "success": True,
            "message": (
                "Sign-in successful. JSON file could not be generated; "
                "HTTP session will use the Chrome profile (SQLite) if needed."
            ),
        }

    except Exception as wait_error:
        print(f"\nTIMEOUT or ERROR: {wait_error}")
        return {"success": False, "message": str(wait_error)}
    finally:
        _schedule_close_browser_after_login()


def login_to_amazon(email: str | None = None, password: str | None = None) -> Dict[str, Any]:
    return run_browser(login_to_amazon_async(email, password), timeout=620)


async def register_to_amazon_async(
    email: str,
    password: str,
    customer_name: str = "GoupixDex",
) -> Dict[str, Any]:
    """Open Amazon.fr registration and pre-fill email/password (SMS/CAPTCHA left to the user)."""
    log_path = os.path.join(_profile_dir(), "amazon-register.log")
    _register_log(f"Démarrage inscription pour {email[:6]}… (log: {log_path})")

    try:
        await close_browser_async()
        await asyncio.sleep(0.25)

        base_url = AMAZON_BASE_URL
        browser = await _ensure_browser_async()
        tab = await _open_amazon_auth_for_register(browser, base_url)

        auth_url = (await _tab_url(tab)).lower()
        if "/signin" in auth_url or "/register" in auth_url:
            page_kind = "register" if "/register" in auth_url else "identifier"
        else:
            page_kind = await _amazon_auth_page_kind(tab)
        _register_log(f"Type page auth: {page_kind} ({auth_url[:100]})")

        email_ok = False
        if page_kind in ("identifier", "unknown"):
            _register_log("Page identifiant — saisie e-mail + Continuer")
            email_ok = await _wait_and_fill_amazon_identifier_email(tab, browser, email)
            if email_ok:
                tab = await _ensure_nodriver_tab(browser, tab)
                await asyncio.sleep(0.15)
                if not await _click_amazon_auth_continue(tab):
                    await asyncio.sleep(0.35)
                    await _click_amazon_auth_continue(tab)
                tab = await _ensure_nodriver_tab(browser, tab)
                await _advance_to_amazon_registration_form(tab, browser)
            else:
                _register_log(f"Échec saisie e-mail — détails: {log_path}")
                if "/signin" in auth_url or page_kind == "identifier":
                    return {
                        "success": False,
                        "message": (
                            "Impossible de préremplir l’e-mail sur Amazon. "
                            f"Aucun compte enregistré. Journal: {log_path}"
                        ),
                        "url": auth_url,
                        "email_prefilled": False,
                        "register_log": log_path,
                    }

        tab = await _refresh_amazon_tab(browser, tab)
        if not await _page_has_registration_name_field(tab):
            await _click_amazon_create_account_links(tab, browser)
            await browser.sleep(1.5)
            tab = await _refresh_amazon_tab(browser, tab)
            if not await _page_has_registration_name_field(tab) and not email_ok:
                if await _fill_amazon_identifier_email(tab, email, browser):
                    await _click_amazon_auth_continue(tab)
                    await browser.sleep(2.5)

        tab = await _refresh_amazon_tab(browser, tab)
        if not email_ok and not await _page_has_registration_name_field(tab):
            return {
                "success": False,
                "message": (
                    "Impossible de préremplir l’e-mail sur Amazon. "
                    f"Aucun compte enregistré. Journal: {log_path}"
                ),
                "url": await _tab_url(tab),
                "email_prefilled": False,
                "register_log": log_path,
            }
        _register_log("Préremplissage formulaire inscription")
        await _fill_amazon_registration_fields(tab, email, password, customer_name)
        tab = await _ensure_nodriver_tab(browser, tab)
        await asyncio.sleep(0.35)
        if not await _click_amazon_registration_continue(tab):
            await asyncio.sleep(0.4)
            tab = await _ensure_nodriver_tab(browser, tab)
            await _click_amazon_registration_continue(tab)
        await browser.sleep(1.2)

        current_url = ""
        try:
            tab = await _refresh_amazon_tab(browser, tab)
            current_url = (tab.target.url or "") if tab.target else ""
        except Exception:
            pass

        if email_ok:
            msg = (
                "Chrome ouvert — e-mail prérempli, terminez l’inscription sur Amazon "
                "(SMS / CAPTCHA)."
            )
            ok = True
        else:
            msg = (
                "Chrome ouvert — saisie auto de l’e-mail impossible. "
                f"Collez {email} manuellement. Journal: {log_path}"
            )
            ok = False
        return {
            "success": ok,
            "message": msg,
            "url": current_url,
            "email_prefilled": email_ok,
            "register_log": log_path,
        }
    except Exception as exc:
        _register_log(f"Inscription interrompue: {exc!r}")
        try:
            await close_browser_async()
        except Exception:
            pass
        return {
            "success": False,
            "message": str(exc),
            "email_prefilled": False,
            "register_log": log_path,
        }


def register_to_amazon(email: str, password: str, customer_name: str = "GoupixDex") -> Dict[str, Any]:
    return run_browser(register_to_amazon_async(email, password, customer_name), timeout=120)


_EMAIL_VERIFY_CODE_SELECTORS: tuple[str, ...] = (
    "#cvf_input_code",
    'input[name="code"]',
    'input[name="otpCode"]',
    'input[autocomplete="one-time-code"]',
    "#auth-mfa-otpcode",
    'input[type="tel"][maxlength="6"]',
    'input[type="text"][maxlength="6"]',
)


async def _click_amazon_email_verify_submit(tab: Any) -> bool:
    """Bouton jaune « Vérifier » OTP (#cvf-submit-otp-button) — le submit n'a pas de value textuelle."""
    browser = getattr(tab, "browser", None)
    if browser is not None:
        tab = _coerce_connection_to_tab(browser, tab) or tab
    for sel in (
        "#cvf-submit-otp-button input.a-button-input",
        "#cvf-submit-otp-button input[type='submit']",
        "#cvf-submit-otp-button",
        "span.cvf-widget-btn-verify input.a-button-input",
        'input.a-button-input[aria-label*="Vérifier"]',
        'input.a-button-input[aria-label*="Verifier"]',
    ):
        try:
            btn = await tab.select(sel, timeout=1.5)
            if btn:
                await btn.mouse_click()
                _register_log(f"Clic Vérifier OTP ({sel})")
                return True
        except Exception:
            continue
    try:
        clicked = await _tab_eval_value(
            tab,
            """
            () => {
              const isVisible = (el) => {
                if (!el || el.disabled) return false;
                const r = el.getBoundingClientRect();
                return r.width > 4 && r.height > 4;
              };
              const tryClick = (el) => {
                if (!isVisible(el)) return false;
                el.focus();
                el.click();
                return true;
              };
              const root = document.querySelector('#cvf-submit-otp-button, .cvf-widget-btn-verify');
              if (root) {
                const input = root.querySelector('input.a-button-input, input[type="submit"]');
                if (input && tryClick(input)) return true;
                if (tryClick(root)) return true;
              }
              for (const el of document.querySelectorAll('input.a-button-input[type="submit"]')) {
                const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                if (aria.includes('vérifier') || aria.includes('verifier') || aria.includes('otp')) {
                  if (tryClick(el)) return true;
                }
              }
              const createLabels = ['créez votre compte', 'creer votre compte', 'create your account'];
              for (const root of document.querySelectorAll('.a-button-primary, .cvf-widget-btn-primary')) {
                const text = (root.textContent || '').trim().toLowerCase();
                if (!createLabels.some((l) => text.includes(l))) continue;
                const input = root.querySelector('input.a-button-input, input[type="submit"]');
                if (input && tryClick(input)) return true;
              }
              return false;
            }
            """,
        )
        if clicked:
            _register_log("Clic Vérifier OTP (JS cvf-submit)")
            return True
    except Exception:
        pass
    return False


async def fill_amazon_email_verification_code_async(code: str) -> Dict[str, Any]:
    """Saisie du code e-mail Amazon (page « Vérifiez l'adresse e-mail ») sur Chrome déjà ouvert."""
    cleaned = "".join(ch for ch in (code or "").strip() if ch.isdigit())
    if len(cleaned) < 4:
        return {"success": False, "message": "Code invalide."}
    browser = _browser_holder.get("browser")
    if browser is None:
        return {"success": False, "message": "Chrome Amazon non ouvert."}
    seed = await _first_live_tab(browser, "")
    tab = await _refresh_amazon_tab(browser, await _ensure_nodriver_tab(browser, seed))
    filled = False
    for sel in _EMAIL_VERIFY_CODE_SELECTORS:
        if await _set_registration_input(tab, sel, cleaned):
            filled = True
            break
    if not filled:
        js = f"""
        (() => {{
          const code = {json.dumps(cleaned)};
          const inputs = document.querySelectorAll('input');
          for (const el of inputs) {{
            const label = (el.labels && el.labels[0] && el.labels[0].textContent) || '';
            const aria = el.getAttribute('aria-label') || '';
            const hint = `${{label}} ${{aria}}`.toLowerCase();
            if (!/code|sécurité|securite|verification|vérification/.test(hint)) continue;
            if (el.offsetParent === null) continue;
            el.focus();
            el.value = code;
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
          }}
          return false;
        }})()
        """
        try:
            filled = bool(await tab.evaluate(js))
        except Exception:
            filled = False
    if not filled:
        return {"success": False, "message": "Champ code introuvable sur la page Amazon."}
    await asyncio.sleep(0.2)
    clicked = False
    for attempt in range(4):
        if await _click_amazon_email_verify_submit(tab):
            clicked = True
            break
        await asyncio.sleep(0.35)
    if not clicked:
        return {
            "success": True,
            "message": "Code saisi — cliquez « Vérifier » si la page ne bouge pas.",
        }
    return {"success": True, "message": "Code saisi et Vérifier cliqué dans Chrome."}


def fill_amazon_email_verification_code(code: str) -> Dict[str, Any]:
    return run_browser(fill_amazon_email_verification_code_async(code), timeout=45)


def amazon_cvf_phone_parts(phone_e164: str | None) -> tuple[str, str] | None:
    """
    Chiffres locaux pour le champ Amazon + indicatif pays du select (FR/BE/CA/US…).

    Amazon FR (+33) attend en général **9 chiffres sans 0** (642193812), pas 0642…
    (sinon affichage +330642… et rejet « numéro invalide »).
    """
    raw = (phone_e164 or "").strip()
    if not raw:
        return None
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 11 and digits.startswith("33"):
        return ("FR", digits[2:11])
    if len(digits) == 10 and digits.startswith("0") and digits[1] in "67":
        return ("FR", digits[1:])
    if len(digits) == 9 and digits[0] in "67":
        return ("FR", digits)
    if len(digits) == 11 and digits.startswith("32"):
        return ("BE", digits[2:])
    if len(digits) == 10 and digits.startswith("0"):
        return ("BE", digits[1:])
    if len(digits) == 11 and digits.startswith("1"):
        return ("CA", digits[1:])
    if len(digits) == 10:
        return ("CA", digits)
    return None


async def _set_amazon_cvf_country(tab: Any, country_iso: str) -> None:
    iso = (country_iso or "FR").upper()
    dial = {"FR": "+33", "BE": "+32", "CA": "+1", "US": "+1"}.get(iso, "+33")
    script = f"""
    (() => {{
      const iso = {json.dumps(iso)};
      const dial = {json.dumps(dial)};
      for (const sel of document.querySelectorAll('select')) {{
        const opts = [...sel.options];
        const hit = opts.find((o) => (o.value || '').toUpperCase() === iso)
          || opts.find((o) => (o.textContent || '').includes(dial));
        if (!hit) continue;
        sel.value = hit.value;
        sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
        return true;
      }}
      return false;
    }})()
    """
    try:
        await tab.evaluate(script)
    except Exception:
        pass


_PHONE_CVF_INPUT_SELECTORS = (
    "#cvfPhoneNumber",
    'input[name="cvfPhoneNumber"]',
    'input[name="phoneNumber"]',
    'input[type="tel"]',
    "#ap_phone_number",
    'input[id*="PhoneNumber"]',
    'input[id*="phone"]',
)


async def _click_amazon_cvf_add_phone_submit(tab: Any) -> bool:
    browser = getattr(tab, "browser", None)
    if browser is not None:
        tab = _coerce_connection_to_tab(browser, tab) or tab
    for sel in (
        "#cvf-submit-otp-button input.a-button-input",
        "#cvf-submit-otp-button",
        'input[aria-label*="Ajouter un numéro de téléphone"]',
        'input[aria-label*="Ajouter un numero de telephone"]',
        'input[aria-label*="Ajouter un numéro"]',
        'input[aria-label*="Ajouter un numero"]',
        "span.cvf-widget-btn-primary input.a-button-input",
        ".cvf-widget-btn-primary input.a-button-input",
        ".a-button-primary input.a-button-input",
    ):
        try:
            btn = await tab.select(sel, timeout=1.2)
            if btn:
                await btn.mouse_click()
                _register_log(f"Clic ajout téléphone CVF ({sel})")
                return True
        except Exception:
            continue
    try:
        clicked = await _tab_eval_value(
            tab,
            """
            () => {
              const isVisible = (el) => {
                if (!el || el.disabled) return false;
                const r = el.getBoundingClientRect();
                return r.width > 4 && r.height > 4;
              };
              const tryClick = (el) => {
                if (!isVisible(el)) return false;
                el.focus();
                el.click();
                return true;
              };
              const labels = ['ajouter un numéro', 'ajouter un numero', 'add mobile'];
              for (const root of document.querySelectorAll('.cvf-widget-btn-primary, .a-button-primary')) {
                const text = (root.textContent || '').trim().toLowerCase();
                if (!labels.some((l) => text.includes(l))) continue;
                const input = root.querySelector('input.a-button-input, input[type="submit"]');
                if (input && tryClick(input)) return true;
                if (tryClick(root)) return true;
              }
              return false;
            }
            """,
        )
        if clicked:
            _register_log("Clic ajout téléphone CVF (JS)")
            return True
    except Exception:
        pass
    return False


async def _page_is_amazon_cvf_add_phone(tab: Any) -> bool:
    try:
        kind = await _tab_eval_value(
            tab,
            """
            () => {
              const body = (document.body && document.body.innerText) || '';
              const t = body.toLowerCase();
              if (t.includes('ajouter un numéro de téléphone') || t.includes('ajouter un numero de telephone')) {
                return true;
              }
              if (t.includes('numéro de téléphone portable') && !t.includes('whatsapp')) {
                return true;
              }
              return false;
            }
            """,
        )
        return bool(kind)
    except Exception:
        return False


async def _click_amazon_cvf_send_sms_instead(tab: Any) -> bool:
    try:
        clicked = await _tab_eval_value(
            tab,
            """
            () => {
              const labels = ['envoyer le code par sms', 'send code by sms'];
              for (const el of document.querySelectorAll('a, button, input[type="submit"], span.a-button-text')) {
                const t = (el.textContent || el.value || '').trim().toLowerCase();
                if (!labels.some((l) => t.includes(l))) continue;
                el.click();
                return true;
              }
              return false;
            }
            """,
        )
        if clicked:
            _register_log("Clic « Envoyer le code par SMS »")
            return True
    except Exception:
        pass
    return False


async def fill_amazon_cvf_phone_async(phone_e164: str) -> Dict[str, Any]:
    """Étape « Ajouter un numéro de téléphone portable » (CVF) — sans saisie WhatsApp/SMS."""
    parts = amazon_cvf_phone_parts(phone_e164)
    if not parts:
        return {"success": False, "message": "Numéro mobile invalide (FR/BE/CA/+1…)."}
    country_iso, national = parts
    browser = _browser_holder.get("browser")
    if browser is None:
        return {"success": False, "message": "Chrome Amazon non ouvert."}
    seed = await _first_live_tab(browser, "")
    tab = await _refresh_amazon_tab(browser, await _ensure_nodriver_tab(browser, seed))
    if not await _page_is_amazon_cvf_add_phone(tab):
        return {"success": False, "message": "Page « Ajouter un téléphone » introuvable."}
    await _set_amazon_cvf_country(tab, country_iso)
    await asyncio.sleep(0.15)
    filled = False
    for sel in _PHONE_CVF_INPUT_SELECTORS:
        if await _fill_amazon_field(tab, sel, national, timeout=2):
            if await _input_value_matches(tab, sel, national):
                filled = True
                _register_log(f"Téléphone saisi ({sel})")
                break
    if not filled:
        js = f"""
        (() => {{
          const national = {json.dumps(national)};
          for (const el of document.querySelectorAll('input[type="tel"], input[name*="phone" i], input[id*="phone" i]')) {{
            if (el.offsetParent === null) continue;
            el.focus();
            const proto = window.HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
            if (setter) setter.call(el, national);
            else el.value = national;
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
          }}
          return false;
        }})()
        """
        try:
            filled = bool(await tab.evaluate(js))
        except Exception:
            filled = False
    if not filled:
        return {"success": False, "message": "Champ téléphone introuvable sur la page Amazon."}
    await asyncio.sleep(0.25)
    clicked = False
    for _ in range(6):
        if await _click_amazon_cvf_add_phone_submit(tab):
            clicked = True
            break
        await asyncio.sleep(0.35)
    if clicked:
        await asyncio.sleep(1.2)
        await _click_amazon_cvf_send_sms_instead(tab)
    if not clicked:
        return {
            "success": True,
            "message": "Numéro saisi — cliquez « Ajouter un numéro » si la page ne bouge pas.",
        }
    return {"success": True, "message": "Numéro saisi et validation cliquée dans Chrome."}


def fill_amazon_cvf_phone(phone_e164: str) -> Dict[str, Any]:
    return run_browser(fill_amazon_cvf_phone_async(phone_e164), timeout=45)
