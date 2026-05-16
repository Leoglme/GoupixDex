"""Synchronise Cardmarket purchases (Sent orders) on the desktop worker.

Opens the persistent Cardmarket Chromium profile, lists ``Orders/Purchases/Sent``,
skips orders already imported in GoupixDex (matched by ``external_order_id``),
downloads the printable invoice PDF for each remaining order via the in-page
print form, and uploads it to the remote API at ``POST /orders/import``.

Same UX patterns as the basket scraper:
- single ``asyncio.Task`` lock per user (prevents concurrent runs);
- progress emitted as JSON events to subscribers;
- handles Cloudflare interactive challenges by waiting for the user;
- closes the browser cleanly so cookies are flushed.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from nodriver.cdp import runtime as cdp_runtime

from services.cardmarket_scraper_service import (
    CardmarketRateLimitError,
    CardmarketScrapeError,
    HOME_POKEMON_URL,
    _html_looks_like_cloudflare_hard_block,
    _html_looks_like_cloudflare_interactive_challenge,
    _try_activate_tab,
    _wait_for_cloudflare_resolution,
    create_browser,
    default_user_data_dir,
    warm_up_cardmarket_session,
)

logger = logging.getLogger(__name__)

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]

ORDERS_BASE_URL = "https://www.cardmarket.com/fr/Pokemon/Orders/Purchases/Sent"
ORDER_DETAIL_URL_PREFIX = "https://www.cardmarket.com"
PRINT_ENDPOINT_URL = "https://www.cardmarket.com/fr/Pokemon/PostGetAction/Shipment_PrintShipmentPage"

# Hard cap; users typically have <50 pages but we don't want a runaway loop.
MAX_ORDER_PAGES = 60
MAX_ORDERS_PER_RUN = 500
PER_ORDER_DELAY_SEC = 0.8
PDF_TRANSFER_TIMEOUT_SEC = 90.0

# Read order rows from ``Orders/Purchases/Sent``: each row is a div with
# ``data-url="/fr/Pokemon/Orders/<id>"`` inside ``#StatusTable .table-body``.
_LIST_PARSE_JS = """
(() => {
  const out = { rows: [], total_pages: null, page_label: null };
  const rows = document.querySelectorAll('#StatusTable .table-body > div[data-url]');
  rows.forEach((row) => {
    const dataUrl = row.getAttribute('data-url') || '';
    const m = dataUrl.match(/\\/Orders\\/(\\d+)/i);
    if (!m) return;
    const idText = (row.querySelector('.col-longNumber a, .col-longNumber') || {}).textContent || '';
    const dateText = (row.querySelector('.col-datetime') || {}).textContent || '';
    const totalText = (row.querySelector('.col-price') || {}).textContent || '';
    const sellerText = (row.querySelector('.col-username .seller-name') || {}).textContent || '';
    out.rows.push({
      external_order_id: m[1],
      detail_path: dataUrl,
      id_text: idText.trim(),
      date_text: dateText.replace(/\\s+/g, ' ').trim(),
      total_text: totalText.replace(/\\s+/g, ' ').trim(),
      seller_text: sellerText.replace(/\\s+/g, ' ').trim(),
    });
  });
  // Detect the pagination label "Page X sur Y" so we know how many pages exist.
  const pageLabel = document.querySelector('.pagination .mx-1');
  if (pageLabel) {
    out.page_label = (pageLabel.textContent || '').trim();
    const pm = out.page_label.match(/(\\d+)\\D+(\\d+)/);
    if (pm) out.total_pages = parseInt(pm[2], 10);
  }
  return JSON.stringify(out);
})()
"""

# Scroll to the print block and expand the Bootstrap collapse (form is inside ``#collapsiblePrintShipment``).
_PREPARE_PRINT_UI_JS = """
(() => {
  const out = { scrolled: false, expanded: false, has_form: false };
  try {
    window.scrollTo(0, document.body.scrollHeight);
  } catch (e) { /* ignore */ }
  const label = document.querySelector('#labelPrintShipment');
  const collapse = document.querySelector('#collapsiblePrintShipment');
  const anchor = label || collapse || document.querySelector('form[action*="Shipment_PrintShipmentPage"]');
  if (anchor) {
    anchor.scrollIntoView({ behavior: 'instant', block: 'center' });
    out.scrolled = true;
  }
  if (collapse && !collapse.classList.contains('show')) {
    const toggle =
      document.querySelector('#labelPrintShipment button[data-bs-toggle="collapse"]') ||
      document.querySelector('#labelPrintShipment button');
    if (toggle) {
      toggle.click();
      out.expanded = true;
    }
  } else if (collapse) {
    out.expanded = true;
  }
  const form =
    document.querySelector('form[action*="Shipment_PrintShipmentPage"]') ||
    (collapse && collapse.querySelector('form[action*="Shipment_PrintShipmentPage"]'));
  out.has_form = !!form;
  return JSON.stringify(out);
})()
"""

# In-page fetch the printable PDF using the print form's hidden ``__cmtkn`` token.
# Must be evaluated with ``await_promise=True`` (async IIFE).
_FETCH_PDF_JS_TEMPLATE = """
(async () => {
  try {
    let form = document.querySelector('form[action*="Shipment_PrintShipmentPage"]');
    const collapse = document.querySelector('#collapsiblePrintShipment');
    if (!form && collapse) {
      form = collapse.querySelector('form[action*="Shipment_PrintShipmentPage"]');
    }
    if (!form) return JSON.stringify({ ok: false, error: 'print_form_missing' });
    const action = form.getAttribute('action') || %s;
    const tokenInput = form.querySelector('input[name="__cmtkn"]');
    const idInput = form.querySelector('input[name="idShipment"]');
    if (!tokenInput || !idInput) return JSON.stringify({ ok: false, error: 'print_form_inputs_missing' });
    const fd = new FormData();
    fd.append('__cmtkn', tokenInput.value || '');
    fd.append('idShipment', idInput.value || '');
    const url = action.startsWith('http') ? action : (location.origin + action);
    const r = await fetch(url, { method: 'POST', body: fd, credentials: 'include' });
    if (!r.ok) return JSON.stringify({ ok: false, error: 'http_' + r.status });
    const ct = (r.headers.get('content-type') || '').toLowerCase();
    const buf = await r.arrayBuffer();
    if (!buf || !buf.byteLength) return JSON.stringify({ ok: false, error: 'empty_pdf' });
    const u8 = new Uint8Array(buf);
    const isPdf = u8.length >= 4 && u8[0] === 0x25 && u8[1] === 0x50 && u8[2] === 0x44 && u8[3] === 0x46;
    if (!isPdf && !ct.includes('pdf')) {
      return JSON.stringify({ ok: false, error: 'not_pdf', content_type: ct, length: u8.length });
    }
    let bin = '';
    const chunk = 0x8000;
    for (let i = 0; i < u8.length; i += chunk) {
      bin += String.fromCharCode.apply(null, u8.subarray(i, Math.min(i + chunk, u8.length)));
    }
    return JSON.stringify({ ok: true, b64: btoa(bin), content_type: ct, length: u8.length });
  } catch (e) {
    return JSON.stringify({ ok: false, error: 'js_exc:' + (e && e.message ? e.message : String(e)) });
  }
})()
"""


def _print_endpoint_js_literal() -> str:
    return json.dumps(PRINT_ENDPOINT_URL)


async def _eval_json(
    tab: Any,
    js: str,
    *,
    timeout_s: float = 30.0,
    await_promise: bool = False,
) -> Any:
    """Run ``js`` in the page and JSON-decode its return value (or raise)."""
    raw = await asyncio.wait_for(
        tab.evaluate(js, return_by_value=True, await_promise=await_promise),
        timeout=timeout_s,
    )
    if isinstance(raw, cdp_runtime.ExceptionDetails):
        raise CardmarketScrapeError(f"JS exception: {raw}")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CardmarketScrapeError(f"JS returned non-JSON: {raw[:200]}") from exc
    if isinstance(raw, dict):
        return raw
    raise CardmarketScrapeError(f"Unexpected evaluate result type: {type(raw).__name__}")


async def _prepare_print_section(tab: Any) -> dict[str, Any]:
    """Scroll to the print block and expand the collapse menu."""
    prep = await _eval_json(tab, _PREPARE_PRINT_UI_JS, timeout_s=15.0)
    if not isinstance(prep, dict):
        return {"has_form": False}
    if not prep.get("has_form"):
        await asyncio.sleep(0.45)
        prep2 = await _eval_json(tab, _PREPARE_PRINT_UI_JS, timeout_s=15.0)
        if isinstance(prep2, dict):
            prep = prep2
    return prep if isinstance(prep, dict) else {"has_form": False}


async def _ensure_not_cloudflare(tab: Any, *, emit: EmitFn) -> None:
    """If the current tab is on a Cloudflare interactive challenge, wait for the human."""
    try:
        html = await asyncio.wait_for(tab.get_content(), timeout=8.0)
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        return
    if _html_looks_like_cloudflare_hard_block(html):
        raise CardmarketRateLimitError(
            "Cloudflare bloque la page (Error 1015 / 1020). Réessayez plus tard."
        )
    if _html_looks_like_cloudflare_interactive_challenge(html):
        await emit(
            {
                "type": "cloudflare_wait",
                "message": (
                    "Cloudflare demande une vérification — cochez la case dans la fenêtre Chrome ouverte."
                ),
            }
        )
        await _try_activate_tab(tab)
        ok = await _wait_for_cloudflare_resolution(tab)
        await emit({"type": "cloudflare_resolved" if ok else "cloudflare_timeout"})
        if not ok:
            raise CardmarketRateLimitError("Vérification Cloudflare non résolue dans le délai imparti.")


def _page_url(page: int) -> str:
    if page <= 1:
        return ORDERS_BASE_URL
    return f"{ORDERS_BASE_URL}?site={page}"


async def _fetch_imported_external_ids(remote_base: str, token: str) -> set[str]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        r = await client.get(f"{remote_base}/orders/external-ids", headers=headers)
        r.raise_for_status()
        data = r.json()
    return {str(x).strip() for x in data if str(x).strip()}


async def _upload_pdf(remote_base: str, token: str, external_id: str, pdf_bytes: bytes) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    files = {"file": (f"cardmarket-{external_id}.pdf", pdf_bytes, "application/pdf")}
    async with httpx.AsyncClient(timeout=PDF_TRANSFER_TIMEOUT_SEC, follow_redirects=True) as client:
        r = await client.post(f"{remote_base}/orders/import", headers=headers, files=files)
    if r.status_code == 409:
        return {"status": "already_imported"}
    r.raise_for_status()
    return {"status": "imported", "data": r.json()}


async def _download_order_pdf(tab: Any, external_id: str, *, emit: EmitFn) -> bytes:
    detail_url = f"{ORDER_DETAIL_URL_PREFIX}/fr/Pokemon/Orders/{external_id}"
    await tab.get(detail_url)
    await tab
    await _try_activate_tab(tab)
    await asyncio.sleep(1.0)
    await _ensure_not_cloudflare(tab, emit=emit)

    prep = await _prepare_print_section(tab)
    if not prep.get("has_form"):
        await asyncio.sleep(0.8)
        prep = await _prepare_print_section(tab)

    await asyncio.sleep(0.5)

    js = _FETCH_PDF_JS_TEMPLATE % _print_endpoint_js_literal()
    payload = await _eval_json(tab, js, timeout_s=PDF_TRANSFER_TIMEOUT_SEC, await_promise=True)
    if not isinstance(payload, dict) or not payload.get("ok"):
        err = str(payload.get("error") if isinstance(payload, dict) else "invalid_response")
        extra = ""
        if isinstance(payload, dict) and payload.get("content_type"):
            extra = f" (type={payload.get('content_type')}, len={payload.get('length')})"
        raise CardmarketScrapeError(f"PDF download failed for {external_id}: {err}{extra}")
    b64 = str(payload.get("b64") or "")
    try:
        pdf_bytes = base64.b64decode(b64, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise CardmarketScrapeError(f"PDF base64 decode failed for {external_id}: {exc}") from exc
    if not pdf_bytes.startswith(b"%PDF"):
        raise CardmarketScrapeError(
            f"PDF download failed for {external_id}: response is not a PDF ({len(pdf_bytes)} bytes)"
        )
    return pdf_bytes


async def _list_orders_for_page(tab: Any, page: int, *, emit: EmitFn) -> dict[str, Any]:
    await tab.get(_page_url(page))
    await tab
    await _try_activate_tab(tab)
    await asyncio.sleep(0.5)
    await _ensure_not_cloudflare(tab, emit=emit)
    parsed = await _eval_json(tab, _LIST_PARSE_JS, timeout_s=20.0)
    if not isinstance(parsed, dict):
        return {"rows": [], "total_pages": None}
    rows = parsed.get("rows") if isinstance(parsed.get("rows"), list) else []
    total_pages = parsed.get("total_pages") if isinstance(parsed.get("total_pages"), int) else None
    return {"rows": rows, "total_pages": total_pages, "page_label": parsed.get("page_label")}


async def run_cardmarket_orders_sync_job(
    user_id: int,
    token: str,
    remote_base: str,
    emit: EmitFn,
) -> None:
    """Top-level coroutine spawned by ``POST /cardmarket/orders/sync``."""
    profile_dir = default_user_data_dir()
    profile_dir.mkdir(parents=True, exist_ok=True)

    try:
        await emit({"type": "log", "message": "Récupération des commandes déjà importées…"})
        already = await _fetch_imported_external_ids(remote_base, token)
        await emit({"type": "log", "message": f"{len(already)} commande(s) déjà présente(s) dans GoupixDex."})
    except httpx.HTTPError as exc:
        logger.exception("orders sync: cannot list imported ids")
        await emit({"type": "error", "message": f"API distante : {exc}"})
        return

    browser: Any = None
    tab: Any = None
    try:
        browser = await create_browser(headless=False, user_data_dir=profile_dir)
        tab = await warm_up_cardmarket_session(browser, emit=emit)
    except CardmarketRateLimitError as exc:
        await emit({"type": "error", "message": str(exc)})
        if browser is not None and tab is not None:
            try:
                from services.cardmarket_session_service import probe_tab_and_persist_session

                await probe_tab_and_persist_session(tab, profile_dir)
            except Exception:  # noqa: BLE001
                pass
        if browser is not None:
            try:
                browser.stop()
            except Exception:  # noqa: BLE001
                pass
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("orders sync: browser warmup failed")
        await emit({"type": "error", "message": f"Impossible d'ouvrir Chrome : {exc}"})
        if browser is not None and tab is not None:
            try:
                from services.cardmarket_session_service import probe_tab_and_persist_session

                await probe_tab_and_persist_session(tab, profile_dir)
            except Exception:  # noqa: BLE001
                pass
        if browser is not None:
            try:
                browser.stop()
            except Exception:  # noqa: BLE001
                pass
        return

    counts = {"discovered": 0, "skipped": 0, "imported": 0, "failed": 0}
    try:
        await tab.get(HOME_POKEMON_URL)
        await tab
        await _try_activate_tab(tab)

        page = 1
        total_pages: int | None = None
        seen_in_run: set[str] = set()

        while page <= MAX_ORDER_PAGES:
            await emit({"type": "log", "message": f"Lecture de la page {page} des commandes…"})
            try:
                page_data = await _list_orders_for_page(tab, page, emit=emit)
            except CardmarketRateLimitError as exc:
                await emit({"type": "error", "message": str(exc)})
                break
            except Exception as exc:  # noqa: BLE001
                logger.exception("orders sync: list page %s failed", page)
                await emit({"type": "error", "message": f"Échec lecture de la page {page} : {exc}"})
                break

            rows: list[dict[str, Any]] = list(page_data.get("rows") or [])
            if total_pages is None and isinstance(page_data.get("total_pages"), int):
                total_pages = int(page_data["total_pages"])

            if not rows:
                await emit({"type": "log", "message": f"Aucune commande sur la page {page}, arrêt de la pagination."})
                break

            counts["discovered"] += len(rows)
            await emit(
                {
                    "type": "page",
                    "page": page,
                    "total_pages": total_pages,
                    "rows_on_page": len(rows),
                }
            )

            for row in rows:
                ext_id = str(row.get("external_order_id") or "").strip()
                if not ext_id or ext_id in seen_in_run:
                    continue
                seen_in_run.add(ext_id)
                if ext_id in already:
                    counts["skipped"] += 1
                    await emit(
                        {
                            "type": "skip",
                            "external_order_id": ext_id,
                            "message": f"Commande #{ext_id} déjà importée — ignorée.",
                            "totals": dict(counts),
                        }
                    )
                    continue

                if counts["imported"] + counts["failed"] >= MAX_ORDERS_PER_RUN:
                    await emit(
                        {
                            "type": "log",
                            "message": (
                                f"Limite de {MAX_ORDERS_PER_RUN} commandes par exécution atteinte — arrêt."
                            ),
                        }
                    )
                    break

                await emit(
                    {
                        "type": "order_start",
                        "external_order_id": ext_id,
                        "seller": row.get("seller_text"),
                        "date_text": row.get("date_text"),
                        "total_text": row.get("total_text"),
                    }
                )

                try:
                    pdf_bytes = await _download_order_pdf(tab, ext_id, emit=emit)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    counts["failed"] += 1
                    logger.exception("orders sync: pdf failed for %s", ext_id)
                    await emit(
                        {
                            "type": "order_failed",
                            "external_order_id": ext_id,
                            "message": f"Téléchargement PDF impossible : {exc}",
                            "totals": dict(counts),
                        }
                    )
                    await asyncio.sleep(PER_ORDER_DELAY_SEC)
                    continue

                try:
                    upload = await _upload_pdf(remote_base, token, ext_id, pdf_bytes)
                except httpx.HTTPStatusError as exc:
                    counts["failed"] += 1
                    detail = exc.response.text[:300] if exc.response is not None else str(exc)
                    logger.exception("orders sync: upload failed for %s", ext_id)
                    await emit(
                        {
                            "type": "order_failed",
                            "external_order_id": ext_id,
                            "message": f"Import API échoué ({exc.response.status_code if exc.response else '?'}): {detail}",
                            "totals": dict(counts),
                        }
                    )
                    await asyncio.sleep(PER_ORDER_DELAY_SEC)
                    continue
                except Exception as exc:  # noqa: BLE001
                    counts["failed"] += 1
                    logger.exception("orders sync: upload error for %s", ext_id)
                    await emit(
                        {
                            "type": "order_failed",
                            "external_order_id": ext_id,
                            "message": f"Erreur upload : {exc}",
                            "totals": dict(counts),
                        }
                    )
                    await asyncio.sleep(PER_ORDER_DELAY_SEC)
                    continue

                if upload.get("status") == "already_imported":
                    counts["skipped"] += 1
                    already.add(ext_id)
                    await emit(
                        {
                            "type": "skip",
                            "external_order_id": ext_id,
                            "message": f"Commande #{ext_id} déjà importée (côté API) — ignorée.",
                            "totals": dict(counts),
                        }
                    )
                else:
                    counts["imported"] += 1
                    already.add(ext_id)
                    await emit(
                        {
                            "type": "order_imported",
                            "external_order_id": ext_id,
                            "order": upload.get("data"),
                            "totals": dict(counts),
                        }
                    )

                await asyncio.sleep(PER_ORDER_DELAY_SEC)

            if counts["imported"] + counts["failed"] >= MAX_ORDERS_PER_RUN:
                break

            if total_pages is not None and page >= total_pages:
                break
            page += 1

        await emit(
            {
                "type": "done",
                "summary": {
                    "discovered": counts["discovered"],
                    "imported": counts["imported"],
                    "skipped": counts["skipped"],
                    "failed": counts["failed"],
                },
            }
        )
    except asyncio.CancelledError:
        await emit({"type": "cancelled", "message": "Synchronisation arrêtée par l’utilisateur.", "totals": dict(counts)})
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("orders sync: fatal error")
        await emit({"type": "error", "message": str(exc) or "Erreur inconnue."})
    finally:
        if browser is not None and tab is not None:
            try:
                from services.cardmarket_session_service import probe_tab_and_persist_session

                await probe_tab_and_persist_session(tab, profile_dir)
            except Exception as exc:  # noqa: BLE001
                logger.debug("orders sync session probe before close: %s", exc)
        if browser is not None:
            try:
                browser.stop()
            except Exception as exc:  # noqa: BLE001
                logger.debug("orders sync: browser.stop: %s", exc)
