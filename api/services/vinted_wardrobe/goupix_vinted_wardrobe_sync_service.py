"""
Vinted wardrobe sync (active listings + sold + HTML descriptions).

Same logic as the former standalone module, integrated under ``api/services/vinted_wardrobe/``.
Environment variables: ``VINTED_FETCH_ACTIVE_DESCRIPTIONS``, ``VINTED_FETCH_SOLD_DESCRIPTIONS``,
``VINTED_DESCRIPTION_WORKERS``, etc. (see ``VintedSoldItemsService``).
"""

from __future__ import annotations

import html as html_module
import json
import logging
import os
import random
import re
import threading
import time
from datetime import datetime, timezone
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, ClassVar, Optional

import requests

from services.vinted_wardrobe.vinted_catalog_service import VintedCatalogService
from services.vinted_wardrobe.vinted_http_service import COOKIE_LOAD_ERRORS, VintedHttpService
from services.vinted_wardrobe.vinted_sold_items_service import VintedSoldItemsService

logger = logging.getLogger(__name__)


class GoupixVintedWardrobeSyncService:
    """Runs catalog + seller sales + description scraping; returns a JSON document."""

    _SESSION_HELP_EN: ClassVar[str] = (
        "No seller session cookie is available. Open Vinted in your browser while logged in, "
        "refresh the page, then run this sync again. Alternatively, set the VINTED_COOKIE "
        "environment variable to your Cookie header value (from the browser developer tools)."
    )

    _ITEM_PAGE_UA: ClassVar[str] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0"
    )
    _RE_ITEM_DESC: ClassVar[re.Pattern[str]] = re.compile(
        r'"description"\s*:\s*"((?:\\.|[^"\\])*)"', re.DOTALL
    )
    _RE_ITEM_META: ClassVar[re.Pattern[str]] = re.compile(
        r'<meta\s+name="description"\s+content="([^"]*)"',
        re.IGNORECASE,
    )

    @staticmethod
    def _decode_json_string_fragment(raw: str) -> str:
        try:
            return str(json.loads(f'"{raw}"'))
        except json.JSONDecodeError:
            return (
                raw.replace("\\n", "\n")
                .replace("\\r", "")
                .replace('\\"', '"')
                .replace("\\\\", "\\")
            )

    @staticmethod
    def _score_description_candidate(text: str) -> tuple[int, int]:
        bonus: int = 0
        if "Langue" in text or "Nom :" in text or "Série" in text:
            bonus += 10_000
        if "État" in text or "Gradation" in text:
            bonus += 1_000
        return (bonus, len(text))

    @classmethod
    def _is_vinted_boilerplate_description(cls, text: str) -> bool:
        """Vinted marketing blurb sometimes shown instead of the real listing description."""
        t = text.strip().lower()
        if len(t) < 20:
            return False
        needles = (
            "une communauté",
            "milliers de marques",
            "prêt à te lancer",
            "découvre comment ça marche",
        )
        return any(n in t for n in needles)

    @classmethod
    def _extract_description_from_item_html(cls, page_html: str) -> str | None:
        candidates: list[str] = []
        for match in cls._RE_ITEM_DESC.finditer(page_html):
            decoded: str = cls._decode_json_string_fragment(match.group(1))
            if len(decoded.strip()) < 5:
                continue
            if cls._is_vinted_boilerplate_description(decoded):
                continue
            candidates.append(decoded)
        if not candidates:
            return None
        candidates.sort(key=cls._score_description_candidate, reverse=True)
        return candidates[0]

    @classmethod
    def _extract_meta_description(cls, page_html: str) -> str | None:
        match = cls._RE_ITEM_META.search(page_html)
        if not match:
            return None
        text: str = html_module.unescape(match.group(1).replace("&quot;", '"'))
        text = cls._decode_json_string_fragment(text) if "\\n" in text else text
        stripped: str = text.strip()
        return stripped or None

    @classmethod
    def _fetch_listing_description_from_public_page(
        cls,
        item_url: str,
        *,
        timeout: float = 90.0,
        retries: int = 4,
    ) -> str | None:
        """@description HTTP GET with retries; prefers embedded JSON description over meta tag."""
        headers: dict[str, str] = {
            "User-Agent": cls._ITEM_PAGE_UA,
            "Accept-Language": "fr-FR,fr;q=0.9",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        }
        last_html: str = ""
        for attempt in range(retries):
            try:
                response: requests.Response = requests.get(
                    item_url, headers=headers, timeout=timeout
                )
                if response.status_code != 200:
                    time.sleep(0.8 * (attempt + 1))
                    continue
                last_html = response.text
                desc = cls._extract_description_from_item_html(last_html)
                if desc and not cls._is_vinted_boilerplate_description(desc):
                    return desc
                meta = cls._extract_meta_description(last_html)
                if (
                    meta
                    and len(meta) > 15
                    and not cls._is_vinted_boilerplate_description(meta)
                ):
                    return meta
            except (requests.RequestException, OSError):
                time.sleep(1.0 * (attempt + 1))
        if last_html:
            desc2 = cls._extract_description_from_item_html(last_html)
            if desc2 and not cls._is_vinted_boilerplate_description(desc2):
                return desc2
            meta2 = cls._extract_meta_description(last_html)
            if meta2 and not cls._is_vinted_boilerplate_description(meta2):
                return meta2
        return None

    @staticmethod
    def _listing_id_set(rows: list[dict[str, Any]]) -> set[int]:
        out: set[int] = set()
        for row in rows:
            raw = row.get("id")
            if raw is None:
                continue
            try:
                out.add(int(raw))
            except (TypeError, ValueError):
                continue
        return out

    @classmethod
    def _drop_sold_rows_still_in_catalog(
        cls,
        sold_rows: list[dict[str, Any]],
        active_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Legacy optional filter: drop sold rows whose listing id still appears in ``active_rows``.

        Off by default: Vinted may reuse the same listing id after a relist, so a past sale
        and a current listing can legitimately share one id — dropping those sold rows loses
        history.
        """
        active_ids = cls._listing_id_set(active_rows)
        if not active_ids:
            return sold_rows
        kept: list[dict[str, Any]] = []
        for row in sold_rows:
            raw = row.get("id")
            if raw is None:
                kept.append(row)
                continue
            try:
                iid = int(raw)
            except (TypeError, ValueError):
                kept.append(row)
                continue
            if iid in active_ids:
                continue
            kept.append(row)
        return kept

    def __init__(
        self,
        base_url: str,
        user_id: int,
        *,
        catalog: VintedCatalogService | None = None,
        sold: VintedSoldItemsService | None = None,
        cookie_header_fn: Callable[[str], tuple[Optional[str], str]] | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        self._base_url: str = base_url
        self._user_id: int = user_id
        self._catalog: VintedCatalogService = catalog or VintedCatalogService()
        self._sold: VintedSoldItemsService = sold or VintedSoldItemsService(self._catalog)
        self._cookie_header_fn: Callable[[str], tuple[Optional[str], str]] = (
            cookie_header_fn or VintedHttpService.preferred_session_cookie_header
        )
        self._on_progress: Callable[[str], None] | None = on_progress

    def _emit_progress(self, message: str) -> None:
        """User-facing log (e.g. wardrobe SSE) + server logs."""
        logger.info(message)
        if self._on_progress:
            try:
                self._on_progress(message)
            except Exception:
                logger.debug("on_progress failed", exc_info=True)

    @staticmethod
    def _description_worker_count() -> int:
        raw: str = os.environ.get("VINTED_DESCRIPTION_WORKERS", "4").strip()
        try:
            n: int = int(raw)
        except ValueError:
            n = 4
        return max(1, min(16, n))

    def _attach_descriptions(
        self, rows: list[dict[str, Any]], delay: float, label: str
    ) -> None:
        total = len(rows)
        step = max(1, min(80, total // 12)) if total else 1
        for i, row in enumerate(rows, start=1):
            url: str = str(row.get("url") or "")
            if not url:
                row["description"] = ""
                row["description_source"] = None
            else:
                desc = self._fetch_listing_description_from_public_page(item_url=url)
                row["description"] = desc or ""
                row["description_source"] = "public_item_page_html" if desc else None
            if total and (i % step == 0 or i == total):
                self._emit_progress(f"Descriptions ({label}) : {i}/{total}…")
            time.sleep(delay + random.uniform(0, 0.35))

    def _attach_descriptions_parallel(
        self, rows: list[dict[str, Any]], workers: int, label: str
    ) -> None:
        """@description Same as ``_attach_descriptions`` without per-request sleep (workers cap concurrency)."""
        total = len(rows)
        step = max(1, min(80, total // 12)) if total else 1
        lock = threading.Lock()
        done_ct = 0

        def one(row: dict[str, Any]) -> None:
            nonlocal done_ct
            url = str(row.get("url") or "")
            if not url:
                row["description"] = ""
                row["description_source"] = None
            else:
                desc = self._fetch_listing_description_from_public_page(item_url=url)
                row["description"] = desc or ""
                row["description_source"] = "public_item_page_html" if desc else None
            with lock:
                done_ct += 1
                d = done_ct
            if total and (d % step == 0 or d == total):
                self._emit_progress(f"Descriptions ({label}) : {d}/{total}…")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(one, rows))

    def _retry_empty_descriptions(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            if str(row.get("description") or "").strip():
                continue
            u: str = str(row.get("url") or "")
            if not u:
                continue
            desc2 = self._fetch_listing_description_from_public_page(
                item_url=u, timeout=120.0, retries=6
            )
            if desc2:
                row["description"] = desc2
                row["description_source"] = "public_item_page_html_retry"
            time.sleep(1.0 + random.uniform(0, 0.5))

    def _retry_empty_descriptions_parallel(
        self, rows: list[dict[str, Any]], workers: int
    ) -> None:
        need: list[dict[str, Any]] = [
            row
            for row in rows
            if not str(row.get("description") or "").strip() and str(row.get("url") or "")
        ]
        if not need:
            return

        def retry_one(row: dict[str, Any]) -> None:
            u = str(row.get("url") or "")
            desc2 = self._fetch_listing_description_from_public_page(
                item_url=u, timeout=120.0, retries=6
            )
            if desc2:
                row["description"] = desc2
                row["description_source"] = "public_item_page_html_retry"

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(retry_one, need))

    def _resolve_bare_sold_item_urls(self, sold: list[dict[str, Any]]) -> int:
        """
        @description Expands ``/items/123`` to canonical slug URLs so slug-based photo merge works.

        ``my_orders`` often returns bare URLs; Vinted redirects to ``/items/123-slug``.
        """
        try:
            cap = int(os.environ.get("VINTED_RESOLVE_BARE_SOLD_ITEM_URLS_MAX", "80").strip())
        except ValueError:
            cap = 80
        cap = max(0, min(300, cap))
        if cap == 0 or not sold:
            return 0
        candidates: list[dict[str, Any]] = [
            r
            for r in sold
            if not self._catalog.serialized_row_has_photos(r)
            and self._catalog.is_bare_vinted_item_url(
                str(r.get("url") or ""), self._base_url.rstrip("/")
            )
        ][:cap]
        if not candidates:
            return 0
        verbose: bool = os.environ.get("VINTED_VERBOSE_SYNC", "0").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if verbose:
            logger.info(
                "Resolving %s bare sold item URL(s) (HEAD→GET redirect)…",
                len(candidates),
            )
        try:
            rw = int(os.environ.get("VINTED_BARE_SOLD_URL_RESOLVE_WORKERS", "6").strip())
        except ValueError:
            rw = 6
        rw = max(1, min(16, rw))
        try:
            bare_to = float(os.environ.get("VINTED_BARE_SOLD_URL_TIMEOUT", "10").strip())
        except ValueError:
            bare_to = 10.0
        bare_to = max(4.0, min(25.0, bare_to))
        prefer_head: bool = os.environ.get(
            "VINTED_BARE_SOLD_URL_HEAD_FIRST", "1"
        ).strip().lower() not in ("0", "false", "no")

        def resolve_one(row: dict[str, Any]) -> int:
            u0 = str(row.get("url") or "")
            u1 = self._catalog.resolve_item_url_follow_redirect(
                u0,
                timeout=bare_to,
                user_agent=self._ITEM_PAGE_UA,
                base_url=self._base_url.rstrip("/"),
                prefer_head=prefer_head,
            )
            if u1 and u1 != u0:
                row["url"] = u1
                return 1
            return 0

        if rw <= 1:
            return sum(resolve_one(r) for r in candidates)
        with ThreadPoolExecutor(max_workers=rw) as pool:
            parts: list[int] = list(pool.map(resolve_one, candidates))
        return sum(parts)

    def _fill_descriptions(
        self,
        rows: list[dict[str, Any]],
        delay: float,
        workers: int,
        *,
        label: str,
    ) -> None:
        if workers <= 1:
            self._attach_descriptions(rows, delay, label)
            n_empty = sum(
                1
                for r in rows
                if str(r.get("url") or "").strip() and not str(r.get("description") or "").strip()
            )
            if n_empty:
                self._emit_progress(
                    f"Nouvelle tentative pour les descriptions encore vides ({label}, ~{n_empty})…",
                )
            self._retry_empty_descriptions(rows)
        else:
            self._attach_descriptions_parallel(rows, workers, label)
            need = sum(
                1
                for r in rows
                if str(r.get("url") or "").strip() and not str(r.get("description") or "").strip()
            )
            if need:
                self._emit_progress(
                    f"Nouvelle tentative pour les descriptions encore vides ({label}, ~{need})…",
                )
            self._retry_empty_descriptions_parallel(rows, workers)

    def run_to_dict(self) -> dict[str, Any]:
        """Run the full sync and return the document (no file write)."""
        active_excluded_no_photo: int = 0
        sold_excluded_no_photo: int = 0
        sold_photos_enriched_from_active: int = 0
        sold_bare_urls_resolved: int = 0
        max_fetch: int = int(os.environ.get("VINTED_MAX_DESCRIPTION_FETCH", "0"))
        delay: float = float(os.environ.get("VINTED_PAGE_FETCH_DELAY", "0.25"))
        workers: int = self._description_worker_count()
        fetch_active_desc: bool = os.environ.get(
            "VINTED_FETCH_ACTIVE_DESCRIPTIONS", "1"
        ).strip().lower() not in ("0", "false", "no")
        fetch_sold_desc: bool = os.environ.get(
            "VINTED_FETCH_SOLD_DESCRIPTIONS", "1"
        ).strip().lower() not in ("0", "false", "no")

        self._emit_progress("Preparing Vinted API calls (catalog, session)…")

        cookie_resolution_note: str | None = None
        try:
            header, cookie_src = self._cookie_header_fn(self._base_url)
        except COOKIE_LOAD_ERRORS as exc:
            header, cookie_src = None, "none"
            cookie_resolution_note = str(exc)

        session_help_en: str | None = (
            self._SESSION_HELP_EN if not header else None
        )

        client: object = VintedCatalogService.create_scraper_client(self._base_url)
        active: list[dict[str, Any]] = []
        pagination: dict[str, Any] | None = None
        cat_err: str | None = None
        try:
            self._emit_progress(
                "Downloading catalog (all pages of active listings)…",
            )
            raw, pagination = self._catalog.fetch_all_raw_items(client, self._user_id)
            active = [self._catalog.serialize_catalog_item(x) for x in raw]
            include_no_photo: bool = os.environ.get(
                "VINTED_INCLUDE_ITEMS_WITHOUT_PHOTOS", "0"
            ).strip().lower() in ("1", "true", "yes")
            if not include_no_photo:
                active, active_excluded_no_photo = (
                    self._catalog.exclude_rows_without_photos(active)
                )
                if active_excluded_no_photo:
                    logger.info(
                        "Excluded %s active listing(s) without photos.",
                        active_excluded_no_photo,
                    )
            if os.environ.get("VINTED_ACTIVE_ITEMS_SORT", "display").strip().lower() != "api":
                self._catalog.apply_active_items_display_order(active)
            logger.info("Catalog active listings: %s", len(active))
            self._emit_progress(f"Catalog: {len(active)} active listing(s) fetched.")
        except Exception as exc:
            cat_err = str(exc)
            logger.warning("Catalog error: %s", cat_err)
            self._emit_progress(f"Catalog error: {cat_err[:180]}")
        finally:
            closer = getattr(client, "__exit__", None)
            if callable(closer):
                try:
                    closer(None, None, None)
                except Exception:
                    pass

        sold: list[dict[str, Any]] = []
        sold_errors: list[str] = []
        if header:
            self._emit_progress(
                "Fetching sales history (seller / orders view)…",
            )
            sold, sold_errors = self._sold.fetch_sold_rows_as_seller(
                self._base_url, self._user_id, header
            )
            logger.info("Sold rows (seller): %s", len(sold))
            self._emit_progress(f"Sales: {len(sold)} row(s) fetched.")
            if sold_errors:
                logger.warning("Sold fetch warnings: %s", sold_errors[:5])
                self._emit_progress(f"Sales warning: {sold_errors[0][:160]}…")
        else:
            logger.warning(
                "No seller session cookie — sold_items skipped. %s",
                self._SESSION_HELP_EN,
            )
            self._emit_progress(
                "No seller session — sales history skipped (catalog only).",
            )

        drop_sold_if_same_id_active: bool = os.environ.get(
            "VINTED_DROP_SOLD_WHEN_LISTING_STILL_ACTIVE", "0"
        ).strip().lower() in ("1", "true", "yes")
        if drop_sold_if_same_id_active:
            before = len(sold)
            sold = self._drop_sold_rows_still_in_catalog(sold, active)
            dropped = before - len(sold)
            if dropped:
                logger.info(
                    "Dropped %s sold row(s) still in catalog (VINTED_DROP_SOLD_WHEN_LISTING_STILL_ACTIVE).",
                    dropped,
                )

        if sold and active:
            self._emit_progress(
                "Matching photos and links between active listings and sold items…",
            )
            origin: str = self._base_url.rstrip("/")
            # Cheap merge first (id / title); HTTP redirect only for rows still bare + no photos.
            n_enrich_pre: int = self._catalog.enrich_sold_photos_from_active_catalog(
                sold, active, origin
            )
            sold_bare_urls_resolved = self._resolve_bare_sold_item_urls(sold)
            n_enrich_post: int = self._catalog.enrich_sold_photos_from_active_catalog(
                sold, active, origin
            )
            sold_photos_enriched_from_active = n_enrich_pre + n_enrich_post
            if sold_bare_urls_resolved or sold_photos_enriched_from_active:
                logger.info(
                    "Sold photos: +%s before redirects, %s bare URLs, +%s after.",
                    n_enrich_pre,
                    sold_bare_urls_resolved,
                    n_enrich_post,
                )

        include_no_photo = os.environ.get(
            "VINTED_INCLUDE_ITEMS_WITHOUT_PHOTOS", "0"
        ).strip().lower() in ("1", "true", "yes")
        if not include_no_photo and sold:
            log_excl = os.environ.get(
                "VINTED_LOG_EXCLUDED_SOLD_NO_PHOTO", "1"
            ).strip().lower() not in ("0", "false", "no")
            if log_excl:
                missing = [
                    r
                    for r in sold
                    if not self._catalog.serialized_row_has_photos(r)
                ]
                if missing:
                    try:
                        lim = int(
                            os.environ.get(
                                "VINTED_LOG_EXCLUDED_SOLD_NO_PHOTO_MAX", "150"
                            ).strip()
                        )
                    except ValueError:
                        lim = 150
                    lim = max(1, min(500, lim))
                    logger.debug(
                        "Sold rows still without photos before filter (%s)",
                        len(missing),
                    )
                    if len(missing) > lim:
                        logger.debug(
                            "... and %s more (raise VINTED_LOG_EXCLUDED_SOLD_NO_PHOTO_MAX)",
                            len(missing) - lim,
                        )
            sold, sold_excluded_no_photo = self._catalog.exclude_rows_without_photos(sold)
            if sold_excluded_no_photo:
                logger.info(
                    "Excluded %s sold row(s) without photos.",
                    sold_excluded_no_photo,
                )

        sold_tx_ids: set[Any] = {
            r.get("transaction_id")
            for r in sold
            if r.get("transaction_id") is not None
        }
        sold_distinct_transactions: int = len(sold_tx_ids)

        # Descriptions: only rows that remain after optional sold/active id dedupe + photo filter.
        to_desc_active: list[dict[str, Any]] = active if fetch_active_desc else []
        to_desc_sold: list[dict[str, Any]] = sold if fetch_sold_desc else []
        if max_fetch > 0:
            to_desc_active = to_desc_active[:max_fetch]
            to_desc_sold = to_desc_sold[:max_fetch]

        if to_desc_active or to_desc_sold:
            mode_en = "parallel" if workers > 1 else f"sequential (delay={delay}s)"
            logger.info(
                "HTML descriptions [%s, workers=%s]: %s active, %s sold",
                mode_en,
                workers,
                len(to_desc_active),
                len(to_desc_sold),
            )
            self._emit_progress(
                f"Fetching descriptions from public pages ({mode_en}, "
                f"{len(to_desc_active)} active, {len(to_desc_sold)} sold) — slowest step…",
            )
            if to_desc_active:
                self._fill_descriptions(
                    to_desc_active, delay, workers, label="active listings"
                )
            if to_desc_sold:
                self._fill_descriptions(
                    to_desc_sold, delay, workers, label="sold items"
                )
        elif fetch_active_desc or fetch_sold_desc:
            self._emit_progress(
                "Description step: nothing to process (empty list after filters).",
            )

        for row in active:
            if "description" not in row:
                row["description"] = ""
                row["description_source"] = None
        for row in sold:
            if "description" not in row:
                row["description"] = ""
                row["description_source"] = None

        self._emit_progress("Finalizing result (counts, metadata)…")

        ok: bool = cat_err is None and len(active) > 0
        sync_payload: dict[str, Any] = {
            "ok": ok,
            "error": cat_err,
            "user_id": self._user_id,
            "cookie_source_catalog": "vinted_scraper_anonymous_access_token_web",
            "cookie_source_sold": cookie_src if header else "none",
            "pagination_catalog": pagination,
            "active_count": len(active),
            "active_excluded_no_photo_count": active_excluded_no_photo,
            "sold_count": len(sold),
            "sold_excluded_no_photo_count": sold_excluded_no_photo,
            "sold_photos_enriched_from_active_count": sold_photos_enriched_from_active,
            "sold_bare_item_urls_resolved_count": sold_bare_urls_resolved,
            "sold_distinct_transactions": sold_distinct_transactions,
            "sold_fetch_warnings": sold_errors,
            "active_items": active,
            "sold_items": sold,
            "note": (
                "active_items order: newest first (listed_at_ts desc, then id desc). "
                "Rows without photos are excluded by default (see "
                "VINTED_INCLUDE_ITEMS_WITHOUT_PHOTOS). Sold photo merge: cheap match first, then "
                "bare /items/{id} URLs expanded (HEAD then GET if needed; "
                "sold_bare_item_urls_resolved_count), then slug/id/title merge again "
                "(sold_photos_enriched_from_active_count). sold_count is one row per sold line "
                "item; sold_distinct_transactions counts unique orders. Sold HTML "
                "descriptions on by default (after no-photo filter; set "
                "VINTED_FETCH_SOLD_DESCRIPTIONS=0 to skip). Sold rows are never dropped for "
                "matching active listing ids unless VINTED_DROP_SOLD_WHEN_LISTING_STILL_ACTIVE=1 "
                "(relist can reuse the same id). Session cookie required for sold; status 450 "
                "by default."
            ),
        }
        if session_help_en is not None:
            sync_payload["session_help_en"] = session_help_en
        if cookie_resolution_note is not None:
            sync_payload["cookie_resolution_note"] = cookie_resolution_note
        sync_payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
        return sync_payload
