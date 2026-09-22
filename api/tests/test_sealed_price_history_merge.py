from services.sealed_price_history_service import merge_price_points


def test_secondary_fills_missing_dates_and_result_is_sorted() -> None:
    real = [{"date": "2026-09-22", "price_eur": 155.72}]
    catalog = [{"date": "2026-09-20", "price_eur": 162.0}, {"date": "2026-09-21", "price_eur": 158.9}]
    merged = merge_price_points(real, catalog)
    assert [p["date"] for p in merged] == ["2026-09-20", "2026-09-21", "2026-09-22"]


def test_primary_wins_on_same_date() -> None:
    real = [{"date": "2026-09-22", "price_eur": 150.0}]
    catalog = [{"date": "2026-09-22", "price_eur": 155.72}]
    merged = merge_price_points(real, catalog)
    assert merged == [{"date": "2026-09-22", "price_eur": 150.0}]


def test_empty_inputs() -> None:
    assert merge_price_points([], []) == []
    only = [{"date": "2026-09-22", "price_eur": 1.0}]
    assert merge_price_points([], only) == only
    assert merge_price_points(only, []) == only
