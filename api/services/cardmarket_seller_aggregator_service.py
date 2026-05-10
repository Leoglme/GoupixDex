"""Aggregate Cardmarket offers across cards to rank sellers (pure logic)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from services.cardmarket_product_types import CardmarketCardResult, CardmarketOffer


def aggregate_sellers(
    card_results: list[CardmarketCardResult],
) -> dict[str, dict[str, CardmarketOffer]]:
    """Map seller -> card_code -> cheapest offer from that seller for that card."""
    seller_map: dict[str, dict[str, CardmarketOffer]] = defaultdict(dict)
    for card in card_results:
        for offer in card.offers:
            existing = seller_map[offer.seller_name].get(card.code)
            if existing is None or offer.price_eur < existing.price_eur:
                seller_map[offer.seller_name][card.code] = offer
    return dict(seller_map)


def summarize_sellers_by_coverage(
    sellers: dict[str, dict[str, CardmarketOffer]],
) -> list[dict[str, Any]]:
    """Sort by covered card count desc, then total price asc, then name."""
    rows: list[tuple[str, dict[str, CardmarketOffer], float, int]] = []
    for seller, offers in sellers.items():
        covered = len(offers)
        total_price = sum(o.price_eur for o in offers.values())
        rows.append((seller, offers, total_price, covered))
    rows.sort(key=lambda item: (-item[3], item[2], item[0].lower()))
    out: list[dict[str, Any]] = []
    for seller, offers, total_price, covered in rows:
        out.append(
            {
                "seller_name": seller,
                "covered_cards": covered,
                "total_price_eur": round(total_price, 2),
                "offers_by_code": {code: o.to_json_dict() for code, o in sorted(offers.items())},
            }
        )
    return out


def summarize_sellers_by_value(
    sellers: dict[str, dict[str, CardmarketOffer]],
    cheapest_by_card: dict[str, float | None],
) -> list[dict[str, Any]]:
    """Sort by relative overpay ratio asc, then covered count desc, then name."""
    rows: list[tuple[str, dict[str, CardmarketOffer], float, float, int]] = []
    for seller, offers in sellers.items():
        covered = len(offers)
        total_price = sum(o.price_eur for o in offers.values())
        total_cheapest = 0.0
        for code, offer in offers.items():
            cheapest = cheapest_by_card.get(code)
            if cheapest is not None and cheapest > 0:
                total_cheapest += cheapest
            else:
                total_cheapest += offer.price_eur
        if total_cheapest > 0:
            overpay_ratio = max(0.0, (total_price - total_cheapest) / total_cheapest)
        else:
            overpay_ratio = float("inf") if total_price > 0 else 0.0
        rows.append((seller, offers, total_price, overpay_ratio, covered))
    rows.sort(key=lambda item: (item[3], -item[4], item[0].lower()))
    out: list[dict[str, Any]] = []
    for seller, offers, total_price, overpay_ratio, covered in rows:
        out.append(
            {
                "seller_name": seller,
                "covered_cards": covered,
                "total_price_eur": round(total_price, 2),
                "overpay_ratio": overpay_ratio if overpay_ratio != float("inf") else None,
                "overpay_percent": round(overpay_ratio * 100.0, 4)
                if overpay_ratio != float("inf")
                else None,
                "offers_by_code": {code: o.to_json_dict() for code, o in sorted(offers.items())},
            }
        )
    return out


def build_cheapest_by_card(card_results: list[CardmarketCardResult]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for card in card_results:
        if card.offers:
            out[card.code] = min(o.price_eur for o in card.offers)
        else:
            out[card.code] = None
    return out


def enrich_seller_rows_with_vs_min(
    rows: list[dict[str, Any]],
    cheapest_by_card: dict[str, float | None],
) -> list[dict[str, Any]]:
    """Add per-offer delta vs global min price for UI."""
    enriched: list[dict[str, Any]] = []
    for row in rows:
        offers_by_code = row.get("offers_by_code") or {}
        new_offers: dict[str, Any] = {}
        for code, od in offers_by_code.items():
            cheapest = cheapest_by_card.get(code)
            price = float(od.get("price_eur") or 0)
            delta_eur = None
            delta_percent = None
            is_best = False
            if cheapest is not None and cheapest > 0:
                delta_eur = round(price - cheapest, 4)
                is_best = abs(price - cheapest) < 1e-9
                if not is_best:
                    delta_percent = round((price - cheapest) / cheapest * 100.0, 4)
            new_od = {**od, "delta_vs_min_eur": delta_eur, "delta_vs_min_percent": delta_percent, "is_best_price": is_best}
            new_offers[code] = new_od
        total_cheapest = 0.0
        for code, od in new_offers.items():
            cheapest = cheapest_by_card.get(code)
            p = float(od.get("price_eur") or 0)
            if cheapest is not None and cheapest > 0:
                total_cheapest += cheapest
            else:
                total_cheapest += p
        total_price = float(row.get("total_price_eur") or 0)
        overpay_eur = max(0.0, total_price - total_cheapest) if total_cheapest > 0 else 0.0
        overpay_pct = (overpay_eur / total_cheapest * 100.0) if total_cheapest > 0 else 0.0
        enriched.append(
            {
                **row,
                "offers_by_code": new_offers,
                "overpay_vs_min_total_eur": round(overpay_eur, 4),
                "overpay_vs_min_total_percent": round(overpay_pct, 4),
            }
        )
    return enriched


def build_run_payload(
    card_results: list[CardmarketCardResult],
    *,
    min_cards_for_lists: int = 2,
) -> dict[str, Any]:
    """Full JSON-serializable snapshot for DB + UI."""
    cheapest_by_card = build_cheapest_by_card(card_results)
    seller_map = aggregate_sellers(card_results)
    cov_raw = summarize_sellers_by_coverage(seller_map)
    val_raw = summarize_sellers_by_value(seller_map, cheapest_by_card)
    cov = enrich_seller_rows_with_vs_min(cov_raw, cheapest_by_card)
    val = enrich_seller_rows_with_vs_min(val_raw, cheapest_by_card)
    cov_filtered = [r for r in cov if int(r.get("covered_cards") or 0) >= min_cards_for_lists]
    val_filtered = [r for r in val if int(r.get("covered_cards") or 0) >= min_cards_for_lists]
    max_cov = max((int(r.get("covered_cards") or 0) for r in cov_filtered), default=0)
    return {
        "cards": [c.to_json_dict() for c in card_results],
        "cheapest_by_card": {k: v for k, v in cheapest_by_card.items()},
        "seller_summary_coverage": cov_filtered,
        "seller_summary_value": val_filtered,
        "seller_summary_coverage_all": cov,
        "seller_summary_value_all": val,
        "meta": {
            "min_cards_for_lists": min_cards_for_lists,
            "max_coverage": max_cov,
            "total_cards": len(card_results),
        },
    }
