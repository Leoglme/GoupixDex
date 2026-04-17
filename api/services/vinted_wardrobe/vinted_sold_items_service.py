"""
Vinted sync — seller-side sold rows from ``my_orders`` and ``transactions/{id}``.

This module defines a single class, ``VintedSoldItemsService``.
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from services.vinted_wardrobe.vinted_catalog_service import VintedCatalogService
from services.vinted_wardrobe.vinted_http_service import VintedHttpService


class VintedSoldItemsService:
    """@description Fetches seller transactions and emits one JSON row per sold line item."""

    @staticmethod
    def _absolute_item_url(raw: object, item_id: object, base: str) -> str:
        """@description Builds ``https://…/items/{id}`` when the API omits scheme or path."""
        if isinstance(raw, str) and raw.strip():
            u = VintedCatalogService.normalize_item_url(raw.strip(), base)
            if u:
                return u
        try:
            iid = int(item_id)
        except (TypeError, ValueError):
            return ""
        return f"{base.rstrip('/')}/items/{iid}"

    def __init__(self, catalog: VintedCatalogService | None = None) -> None:
        """
        Args:
            catalog: Shared ``VintedCatalogService`` for photos / money helpers.
        """
        self._catalog: VintedCatalogService = catalog or VintedCatalogService()

    @staticmethod
    def _float_amount(m: dict[str, Any] | None) -> float:
        if not isinstance(m, dict):
            return 0.0
        try:
            return float(m.get("amount") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _alloc_weights(items: list[dict[str, Any]]) -> list[float]:
        sums: float = sum(VintedSoldItemsService._float_amount(i.get("price")) for i in items)
        if sums <= 0 and items:
            n: float = float(len(items))
            return [1.0 / n] * len(items)
        if sums <= 0:
            return []
        return [VintedSoldItemsService._float_amount(i.get("price")) / sums for i in items]

    @staticmethod
    def _fmt_money(amount: float, currency: str | None) -> dict[str, Any]:
        cur: str = currency or "EUR"
        if amount <= 0 and currency is None:
            return {"amount": None, "currency_code": None}
        return {"amount": f"{amount:.2f}", "currency_code": cur}

    @staticmethod
    def _transaction_included_by_status(tx: dict[str, Any]) -> bool:
        """
        @description Filters by ``VINTED_SOLD_TRANSACTION_STATUSES`` (default ``450``).

        Use ``all`` to disable status filtering.
        """
        raw: str = os.environ.get(
            "VINTED_SOLD_TRANSACTION_STATUSES", "450"
        ).strip().lower()
        if raw == "all":
            return True
        allowed: set[int] = set()
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                allowed.add(int(part))
            except ValueError:
                continue
        if not allowed:
            return True
        st = tx.get("status")
        try:
            return int(st) in allowed
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _sold_row_sort_key(r: dict[str, Any]) -> str:
        return str(r.get("transaction_debit_processed_at") or "")

    def fetch_sold_rows_as_seller(
        self,
        base_url: str,
        user_id: int,
        cookie_header: str,
        session: requests.Session | None = None,
        per_page: int = 100,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """
        @description Paginates ``my_orders`` and expands each seller transaction.

        Returns:
            ``(sold_rows, warning_messages)``.
        """
        sess: requests.Session = session or requests.Session()
        hdr: dict[str, str] = VintedHttpService.build_json_request_headers(
            base_url, cookie_header
        )
        base: str = base_url.rstrip("/")
        errors: list[str] = []
        rows: list[dict[str, Any]] = []
        page: int = 1

        while True:
            r: requests.Response = sess.get(
                f"{base}/api/v2/my_orders",
                params={"page": page, "per_page": per_page},
                headers=hdr,
                timeout=45,
            )
            if r.status_code != 200:
                errors.append(f"my_orders HTTP {r.status_code} page={page}")
                break
            try:
                js: dict[str, Any] = r.json()
            except (json.JSONDecodeError, ValueError) as exc:
                errors.append(f"my_orders JSON page={page}: {exc}")
                break

            orders: list[Any] = js.get("my_orders") or []
            pag: dict[str, Any] = js.get("pagination") or {}

            for o in orders:
                if not isinstance(o, dict):
                    continue
                tid = o.get("transaction_id")
                if tid is None:
                    continue

                tr: requests.Response = sess.get(
                    f"{base}/api/v2/transactions/{tid}",
                    headers=hdr,
                    timeout=45,
                )
                if tr.status_code != 200:
                    errors.append(f"transactions/{tid} HTTP {tr.status_code}")
                    continue
                try:
                    tj: dict[str, Any] = tr.json()
                except (json.JSONDecodeError, ValueError) as exc:
                    errors.append(f"transactions/{tid} JSON: {exc}")
                    continue

                tx = tj.get("transaction")
                if not isinstance(tx, dict):
                    continue
                if int(tx.get("seller_id") or 0) != int(user_id):
                    continue
                if not self._transaction_included_by_status(tx):
                    continue

                order = tx.get("order") or {}
                if not isinstance(order, dict):
                    continue
                items: list[Any] = order.get("items") or []

                offer_p = tx.get("offer") or {}
                offer_price = offer_p.get("price") if isinstance(offer_p, dict) else None
                fee_block = tx.get("service_fee")
                total_wotax = tx.get("total_amount_without_tax")
                cur: str | None = None
                if isinstance(offer_price, dict):
                    cur = str(offer_price.get("currency_code") or "") or None
                if not cur and isinstance(fee_block, dict):
                    cur = str(fee_block.get("currency_code") or "") or None

                buyer_total: float = self._float_amount(
                    total_wotax if isinstance(total_wotax, dict) else None
                )
                if buyer_total <= 0:
                    buyer_total = self._float_amount(
                        offer_price if isinstance(offer_price, dict) else None
                    ) + self._float_amount(fee_block if isinstance(fee_block, dict) else None)

                fee_total: float = self._float_amount(
                    fee_block if isinstance(fee_block, dict) else None
                )
                offer_amt: float = self._float_amount(
                    offer_price if isinstance(offer_price, dict) else None
                )

                trans_meta: dict[str, Any] = {
                    "transaction_id": tid,
                    "transaction_status": tx.get("status"),
                    "transaction_status_title": tx.get("status_title"),
                    "transaction_debit_processed_at": tx.get("debit_processed_at"),
                    "transaction_offer_total": self._catalog.normalize_money(
                        offer_price if isinstance(offer_price, dict) else None
                    ),
                    "transaction_service_fee_total": self._catalog.normalize_money(
                        fee_block if isinstance(fee_block, dict) else None
                    ),
                    "transaction_total_amount_without_tax": self._catalog.normalize_money(
                        total_wotax if isinstance(total_wotax, dict) else None
                    ),
                }

                if not items:
                    self._append_fallback_rows(
                        base=base,
                        tx=tx,
                        order=order,
                        rows=rows,
                        trans_meta=trans_meta,
                        buyer_total=buyer_total,
                        fee_total=fee_total,
                        offer_amt=offer_amt,
                        cur=cur,
                    )
                    continue

                weights: list[float] = self._alloc_weights(items)
                for idx, it in enumerate(items):
                    if not isinstance(it, dict):
                        continue
                    line: dict[str, Any] = it
                    w: float = weights[idx] if idx < len(weights) else 0.0
                    alloc_buyer: float = buyer_total * w
                    alloc_fee: float = fee_total * w
                    photos_d, photo_urls = self._catalog.collect_photos_from_api(
                        line.get("photos") if isinstance(line.get("photos"), list) else None,
                        None,
                    )
                    price = line.get("price") or {}
                    item_url = self._absolute_item_url(line.get("url"), line.get("id"), base)
                    rows.append(
                        {
                            "id": line.get("id"),
                            "title": line.get("title"),
                            "url": item_url or line.get("url"),
                            "price": self._catalog.normalize_money(
                                price if isinstance(price, dict) else None
                            ),
                            "total_item_price": self._fmt_money(alloc_buyer, cur),
                            "service_fee": self._fmt_money(alloc_fee, cur),
                            "photo_urls": photo_urls,
                            "photos": photos_d,
                            "brand_title": line.get("brand_title"),
                            "size_title": line.get("size_title"),
                            "status": line.get("status"),
                            "is_sold": True,
                            "sold_row_source": "order_items",
                            **trans_meta,
                        }
                    )

            tpages = pag.get("total_pages")
            cpage = pag.get("current_page", page)
            if tpages is not None and cpage >= tpages:
                break
            if not orders:
                break
            page += 1
            if page > 200:
                errors.append("my_orders: safety stop page>200")
                break

        rows.sort(key=self._sold_row_sort_key, reverse=True)
        return rows, errors

    def _append_fallback_rows(
        self,
        *,
        base: str,
        tx: dict[str, Any],
        order: dict[str, Any],
        rows: list[dict[str, Any]],
        trans_meta: dict[str, Any],
        buyer_total: float,
        fee_total: float,
        offer_amt: float,
        cur: str | None,
    ) -> None:
        """@description Synthetic rows when ``order.items`` is empty but ``item_ids`` exist."""
        raw_ids = order.get("item_ids") or []
        id_list: list[int] = []
        for x in raw_ids:
            try:
                id_list.append(int(x))
            except (TypeError, ValueError):
                continue
        if not id_list and tx.get("item_id") is not None:
            try:
                id_list.append(int(tx["item_id"]))
            except (TypeError, ValueError):
                pass
        if not id_list:
            return
        n: int = len(id_list)
        lot_title: str = (
            str(tx.get("item_title") or "")
            or str(tx.get("removed_item_title") or "")
            or str(order.get("title") or "")
        )
        per_buyer: float = buyer_total / n
        per_fee: float = fee_total / n
        per_offer: float = offer_amt / n if offer_amt > 0 else 0.0
        for iid in id_list:
            title_one: str = lot_title
            if n > 1:
                title_one = f"{lot_title} · #{iid}"
            rows.append(
                {
                    "id": iid,
                    "title": title_one,
                    "url": f"{base}/items/{iid}",
                    "price": self._fmt_money(per_offer, cur)
                    if per_offer > 0
                    else self._catalog.normalize_money(None),
                    "total_item_price": self._fmt_money(per_buyer, cur),
                    "service_fee": self._fmt_money(per_fee, cur),
                    "photo_urls": [],
                    "photos": [],
                    "brand_title": None,
                    "size_title": "",
                    "status": None,
                    "is_sold": True,
                    "sold_row_source": "transaction_item_ids_fallback",
                    **trans_meta,
                }
            )
