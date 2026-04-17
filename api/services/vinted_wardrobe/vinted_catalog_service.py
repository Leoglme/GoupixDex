"""
Vinted sync — member catalog: scraper client, pagination, item serialization.

This module defines a single class, ``VintedCatalogService``. JSON payloads are typed as
``dict[str, Any]`` (no module-level type alias).
"""

from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


class VintedCatalogService:
    """@description Paginates catalog API and serializes rows for the sync document."""

    _ITEM_ID_IN_PATH: re.Pattern[str] = re.compile(r"/items/(\d+)")
    _ITEM_SLUG_IN_PATH: re.Pattern[str] = re.compile(
        r"/items/\d+-([^/?#]+)", re.IGNORECASE
    )
    @staticmethod
    def normalize_item_url(url: str | None, base_url: str) -> str:
        """Absolute URL: ``//…`` → ``https:…``; root-relative ``/items/…`` → origin + path."""
        if not url or not isinstance(url, str):
            return ""
        u = url.strip().rstrip("/").split("?")[0].split("#")[0]
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return base_url.rstrip("/") + u
        return u

    @staticmethod
    def is_bare_vinted_item_url(url: str | None, base_url: str = "") -> bool:
        """
        True when the path is ``/items/{digits}`` only (no ``-slug``), as in many ``my_orders`` URLs.

        ``base_url`` is used only to normalize ``//host`` or ``/items/…`` shapes before checking.
        """
        if not url or not isinstance(url, str):
            return False
        u = VintedCatalogService.normalize_item_url(url, base_url or "https://www.vinted.fr")
        u = u.rstrip("/")
        return bool(re.search(r"/items/\d+$", u, re.IGNORECASE))

    @staticmethod
    def resolve_item_url_follow_redirect(
        url: str,
        *,
        timeout: float = 10.0,
        user_agent: str | None = None,
        base_url: str = "",
        prefer_head: bool = True,
    ) -> str:
        """
        Follows redirects so ``/items/6184120335`` becomes the canonical slug URL.

        Uses **HEAD** first (lighter than GET on Vinted), then **GET** if the URL did not change.
        """
        try:
            import requests
        except ImportError:
            return url
        ua: str = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) "
            "Gecko/20100101 Firefox/131.0"
        )
        hdrs: dict[str, str] = {
            "User-Agent": ua,
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        }
        u0 = VintedCatalogService.normalize_item_url(url, base_url or "https://www.vinted.fr")
        if not u0:
            return url
        origin = base_url or "https://www.vinted.fr"
        try:
            if prefer_head:
                try:
                    rh = requests.head(
                        u0,
                        timeout=timeout,
                        allow_redirects=True,
                        headers=hdrs,
                    )
                    head_url: str = (rh.url or "").strip()
                    if head_url and head_url != u0:
                        return head_url
                    if head_url == u0 and VintedCatalogService.is_bare_vinted_item_url(
                        head_url, origin
                    ):
                        return u0
                except requests.RequestException:
                    pass
            r = requests.get(
                u0,
                timeout=timeout,
                allow_redirects=True,
                headers=hdrs,
            )
        except (OSError, requests.RequestException):
            return url
        final: str = (r.url or "").strip()
        return final if final else url

    @staticmethod
    def listing_slug_from_item_url(
        url: str | None, site_origin: str = "https://www.vinted.fr"
    ) -> str | None:
        """
        URL path segment after ``/items/{id}-`` (same for a relist with a new numeric id).

        Example: ``…/items/6184120335-pikachu-ex-sv8-033106-pokemon-japonais`` and
        ``…/items/8380085584-pikachu-ex-sv8-033106-pokemon-japonais`` share slug
        ``pikachu-ex-sv8-033106-pokemon-japonais``.
        """
        if not url or not isinstance(url, str):
            return None
        u = VintedCatalogService.normalize_item_url(url, site_origin)
        if not u:
            return None
        m = VintedCatalogService._ITEM_SLUG_IN_PATH.search(u)
        if not m:
            return None
        s = m.group(1).strip().lower()
        return s or None

    @staticmethod
    def parse_listing_id_from_item_url(
        url: str | None, site_origin: str = "https://www.vinted.fr"
    ) -> int | None:
        """Numeric id from a Vinted item URL path (``/items/6184126659-…``)."""
        if not url or not isinstance(url, str):
            return None
        u = VintedCatalogService.normalize_item_url(url, site_origin)
        if not u:
            return None
        m = VintedCatalogService._ITEM_ID_IN_PATH.search(u)
        if not m:
            return None
        try:
            return int(m.group(1))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def normalized_listing_title(row: dict[str, Any]) -> str:
        """Lowercase single-spaced title for cross-matching sold vs active."""
        t = str(row.get("title") or "").strip().lower()
        return " ".join(t.split())

    @classmethod
    def debug_line_row_without_photos(
        cls, row: dict[str, Any], site_origin: str = "https://www.vinted.fr"
    ) -> str:
        """One-line debug summary for a row missing images (sold diagnostics)."""
        u = str(row.get("url") or "")
        slug_id = cls.parse_listing_id_from_item_url(u, site_origin)
        slug_part = f" url_path_id={slug_id}" if slug_id is not None else ""
        path_slug = cls.listing_slug_from_item_url(u, site_origin)
        slug_dbg = f" path_slug={path_slug!r}" if path_slug else ""
        title = str(row.get("title") or "")[:140]
        return (
            f"  id={row.get('id')} tx={row.get('transaction_id')}{slug_part}{slug_dbg} "
            f"title={title!r} url={row.get('url')!r}"
        )

    @staticmethod
    def create_scraper_client(base_url: str, retries: int = 6, sleep_base: float = 2.0) -> Any:
        """@description Builds ``VintedWrapper`` with backoff on ``RuntimeError``."""
        from vinted_scraper import VintedWrapper

        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                return VintedWrapper(baseurl=base_url)
            except RuntimeError as exc:
                last_err = exc
                time.sleep(sleep_base * (1 + attempt * 0.5))
        if last_err is not None:
            raise last_err
        raise RuntimeError("VintedWrapper: retries is 0 or no attempt completed")

    @staticmethod
    def _response_as_dict(data: object) -> dict[str, Any]:
        if isinstance(data, dict):
            return data
        jd = getattr(data, "json_data", None)
        if isinstance(jd, dict):
            return jd
        return {}

    def fetch_all_raw_items(
        self,
        client: object,
        user_id: int,
        per_page: int | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """@description Paginates ``/api/v2/catalog/items`` preserving API order."""
        curl = getattr(client, "curl", None)
        if not callable(curl):
            raise TypeError("client must expose a callable curl(path, params)")

        uid: str = str(user_id)
        per: int = int(per_page or os.environ.get("VINTED_CATALOG_PER_PAGE", "96"))
        order: str = os.environ.get("VINTED_CATALOG_ORDER", "newest_first")
        page: int = 1
        flat: list[dict[str, Any]] = []
        last_pag: dict[str, Any] | None = None

        while True:
            raw: object = curl(
                "/api/v2/catalog/items",
                {"user_ids": uid, "per_page": per, "page": page, "order": order},
            )
            data: dict[str, Any] = self._response_as_dict(raw)
            batch: list[Any] = data.get("items") or []
            last_pag = data.get("pagination") or last_pag
            for row in batch:
                if isinstance(row, dict):
                    flat.append(row)
            pag: dict[str, Any] = data.get("pagination") or {}
            tpages = pag.get("total_pages")
            cur = pag.get("current_page", page)
            total = pag.get("total_entries")
            if not batch:
                break
            if tpages is not None and cur >= tpages:
                break
            if total is not None and len(flat) >= int(total):
                break
            page += 1
            if page > 100:
                break

        return flat, last_pag

    @staticmethod
    def photo_listing_timestamp(item: dict[str, Any]) -> int:
        photo: dict[str, Any] = item.get("photo") or {}
        hr: dict[str, Any] = photo.get("high_resolution") or {}
        try:
            return int(hr.get("timestamp") or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _photo_entry(photo: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": photo.get("id"),
            "url": photo.get("url"),
            "full_size_url": photo.get("full_size_url"),
            "is_main": photo.get("is_main"),
            "width": photo.get("width"),
            "height": photo.get("height"),
        }

    @classmethod
    def collect_photos_from_api(
        cls,
        photos: list[Any] | None,
        fallback_photo: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        photos_detailed: list[dict[str, Any]] = []
        photo_urls: list[str] = []

        for p in photos or []:
            if not isinstance(p, dict):
                continue
            photos_detailed.append(cls._photo_entry(p))
            u = p.get("url")
            if isinstance(u, str) and u:
                photo_urls.append(u)

        if not photos_detailed and isinstance(fallback_photo, dict):
            photos_detailed.append(cls._photo_entry(fallback_photo))
            u = fallback_photo.get("url")
            if isinstance(u, str) and u:
                photo_urls.append(u)

        return photos_detailed, photo_urls

    @staticmethod
    def normalize_money(src: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(src, dict):
            return {"amount": None, "currency_code": None}
        return {
            "amount": src.get("amount"),
            "currency_code": src.get("currency_code"),
        }

    @classmethod
    def serialize_catalog_item(cls, item: dict[str, Any]) -> dict[str, Any]:
        price: dict[str, Any] = item.get("price") or {}
        total_item_price: dict[str, Any] = item.get("total_item_price") or {}
        service_fee: dict[str, Any] = item.get("service_fee") or {}
        ts: int = cls.photo_listing_timestamp(item)
        listed_utc: str | None = None
        if ts > 0:
            listed_utc = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        photos_list = item.get("photos") if isinstance(item.get("photos"), list) else None
        fb = item.get("photo") if isinstance(item.get("photo"), dict) else None
        photos_detailed, photo_urls = cls.collect_photos_from_api(photos_list, fb)

        return {
            "id": item.get("id"),
            "title": item.get("title"),
            "url": item.get("url"),
            "price": {
                "amount": price.get("amount"),
                "currency_code": price.get("currency_code"),
            },
            "total_item_price": cls.normalize_money(total_item_price),
            "service_fee": cls.normalize_money(service_fee),
            "listed_at_ts": ts if ts else None,
            "listed_at_utc": listed_utc,
            "photo_urls": photo_urls,
            "photos": photos_detailed,
            "brand_title": item.get("brand_title"),
            "size_title": item.get("size_title"),
            "status": item.get("status"),
            "is_sold": False,
        }

    @staticmethod
    def serialized_row_has_photos(row: dict[str, Any]) -> bool:
        """@description True if the row has at least one usable image URL (active or sold shape)."""
        urls = row.get("photo_urls")
        if isinstance(urls, list) and any(
            isinstance(u, str) and u.strip() for u in urls
        ):
            return True
        photos = row.get("photos")
        if isinstance(photos, list):
            for p in photos:
                if isinstance(p, dict) and isinstance(p.get("url"), str) and p["url"].strip():
                    return True
        return False

    @classmethod
    def _copy_photo_fields_into(cls, dest: dict[str, Any], src: dict[str, Any]) -> None:
        urls = src.get("photo_urls")
        photos = src.get("photos")
        if isinstance(urls, list) and urls:
            dest["photo_urls"] = [
                u for u in urls if isinstance(u, str) and u.strip()
            ]
        if isinstance(photos, list) and photos:
            dest["photos"] = [
                dict(p) if isinstance(p, dict) else p for p in photos
            ]

    @classmethod
    def enrich_sold_photos_from_active_catalog(
        cls,
        sold_rows: list[dict[str, Any]],
        active_rows: list[dict[str, Any]],
        site_origin: str = "https://www.vinted.fr",
    ) -> int:
        """
        @description Copies photos from active rows onto sold rows when a link is unambiguous.

        Tries in order: same numeric ``id`` as active; id parsed from sold ``url`` path
        (``/items/123-slug``); **slug** after ``/items/{id}-`` (matches relists with new ids);
        then **unique** normalized title among actives that have photos (skips ambiguous titles).
        """
        origin: str = site_origin.strip().rstrip("/") or "https://www.vinted.fr"
        by_id: dict[int, dict[str, Any]] = {}
        by_slug: dict[str, dict[str, Any]] = {}
        for row in active_rows:
            raw = row.get("id")
            try:
                iid = int(raw)
            except (TypeError, ValueError):
                continue
            if cls.serialized_row_has_photos(row):
                by_id[iid] = row
                sk = cls.listing_slug_from_item_url(str(row.get("url") or ""), origin)
                if sk and sk not in by_slug:
                    by_slug[sk] = row

        title_groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in active_rows:
            if not cls.serialized_row_has_photos(row):
                continue
            t = cls.normalized_listing_title(row)
            if t:
                title_groups[t].append(row)
        unique_title_src: dict[str, dict[str, Any]] = {
            t: g[0] for t, g in title_groups.items() if len(g) == 1
        }

        n: int = 0
        for srow in sold_rows:
            if cls.serialized_row_has_photos(srow):
                continue
            had = False
            ids_to_try: list[int] = []
            raw = srow.get("id")
            try:
                ids_to_try.append(int(raw))
            except (TypeError, ValueError):
                pass
            alt = cls.parse_listing_id_from_item_url(str(srow.get("url") or ""), origin)
            if alt is not None and alt not in ids_to_try:
                ids_to_try.append(alt)
            for iid in ids_to_try:
                src = by_id.get(iid)
                if src:
                    cls._copy_photo_fields_into(srow, src)
                    if cls.serialized_row_has_photos(srow):
                        had = True
                        break
            if not had:
                sk = cls.listing_slug_from_item_url(str(srow.get("url") or ""), origin)
                if sk:
                    src_slug = by_slug.get(sk)
                    if src_slug:
                        cls._copy_photo_fields_into(srow, src_slug)
                        if cls.serialized_row_has_photos(srow):
                            had = True
            if not had:
                tkey = cls.normalized_listing_title(srow)
                src2 = unique_title_src.get(tkey)
                if src2:
                    cls._copy_photo_fields_into(srow, src2)
            if cls.serialized_row_has_photos(srow):
                n += 1
        return n

    @classmethod
    def exclude_rows_without_photos(
        cls, rows: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], int]:
        """@description Drops rows with no photos; returns ``(kept, excluded_count)``."""
        kept: list[dict[str, Any]] = []
        excluded: int = 0
        for row in rows:
            if cls.serialized_row_has_photos(row):
                kept.append(row)
            else:
                excluded += 1
        return kept, excluded

    @staticmethod
    def apply_active_items_display_order(rows: list[dict[str, Any]]) -> None:
        """
        @description Reorders ``active_items`` in place to match the profile « Actifs » order.

        Newest listings first (descending ``listed_at_ts``), then descending ``id`` when
        timestamps tie (same second uploads).
        """
        rows.sort(
            key=lambda r: (
                -(int(r.get("listed_at_ts") or 0)),
                -(int(r.get("id") or 0)),
            )
        )
