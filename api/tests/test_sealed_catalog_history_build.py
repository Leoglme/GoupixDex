import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "build_sealed_catalog.py"


def _load_build_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_sealed_catalog", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = _load_build_script()


def test_append_history_point_replaces_same_day_and_sorts() -> None:
    series = [["2026-09-20", 10.0], ["2026-09-22", 12.0]]
    result = build.append_history_point(series, "2026-09-21", 11.0)
    assert result == [["2026-09-20", 10.0], ["2026-09-21", 11.0], ["2026-09-22", 12.0]]
    replaced = build.append_history_point(result, "2026-09-22", 12.5)
    assert replaced[-1] == ["2026-09-22", 12.5]
    assert len(replaced) == 3


def test_append_history_point_caps_length() -> None:
    series = [[f"2020-01-{day:02d}", float(day)] for day in range(1, 29)]
    build.HISTORY_MAX_DAYS = 5
    try:
        result = build.append_history_point(series, "2026-09-22", 99.0)
    finally:
        build.HISTORY_MAX_DAYS = 730
    assert len(result) == 5
    assert result[-1] == ["2026-09-22", 99.0]


def test_history_shard_is_stable_and_bounded() -> None:
    assert build.history_shard(672401) == 672401 % build.HISTORY_SHARDS
    assert 0 <= build.history_shard(12345) < build.HISTORY_SHARDS


def test_update_price_history_writes_shards_and_accumulates(tmp_path: Path) -> None:
    payload = {
        "series": [
            {
                "expansions": [
                    {
                        "products": [
                            {"tp": 64, "price": 10.0},
                            {"tp": 65, "price": None},
                            {"tp": 128, "price": 20.0},
                        ]
                    }
                ]
            }
        ]
    }
    assert build.update_price_history(payload, "2026-09-22", tmp_path) == 2
    shard = json.loads((tmp_path / "0.json").read_text(encoding="utf-8"))
    assert shard["products"] == {"64": [["2026-09-22", 10.0]], "128": [["2026-09-22", 20.0]]}

    payload["series"][0]["expansions"][0]["products"][0]["price"] = 11.0
    assert build.update_price_history(payload, "2026-09-23", tmp_path) == 2
    shard = json.loads((tmp_path / "0.json").read_text(encoding="utf-8"))
    assert shard["products"]["64"] == [["2026-09-22", 10.0], ["2026-09-23", 11.0]]
    assert "65" not in shard["products"]


def test_merge_history_points_keeps_existing_and_adds_missing_dates() -> None:
    existing = [["2026-09-22", 10.0]]
    incoming = [["2026-09-20", 9.0], ["2026-09-22", 99.0], ["2026-09-21", 9.5]]
    merged = build.merge_history_points(existing, incoming)
    assert merged == [["2026-09-20", 9.0], ["2026-09-21", 9.5], ["2026-09-22", 10.0]]


def test_load_tcgcsv_groups_retries_groups_that_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    groups = [{"groupId": 1, "name": "Base Set"}, {"groupId": 2, "name": "Jungle"}]
    failures_left = {2: 1}

    def fake_fetch_json(url: str, **_kwargs: object) -> dict:
        if url.endswith("/groups"):
            return {"results": groups}
        group_id = int(url.split("/")[-2])
        if url.endswith("/products") and failures_left.get(group_id):
            failures_left[group_id] -= 1
            raise SystemExit("TCGCSV limite les requêtes")
        if url.endswith("/products"):
            return {"results": [{"productId": group_id, "name": "Booster Box", "extendedData": []}]}
        return {"results": []}

    monkeypatch.setattr(build, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(build.time, "sleep", lambda _seconds: None)

    loaded, abandoned = build.load_tcgcsv_groups()

    assert [group["name"] for group in loaded] == ["Base Set", "Jungle"]
    assert abandoned == []


def test_load_tcgcsv_groups_reports_groups_refused_at_every_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    groups = [{"groupId": 1406, "name": "Platinum"}]

    def fake_fetch_json(url: str, **_kwargs: object) -> dict:
        if url.endswith("/groups"):
            return {"results": groups}
        raise SystemExit("TCGCSV limite les requêtes")

    monkeypatch.setattr(build, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(build.time, "sleep", lambda _seconds: None)

    loaded, abandoned = build.load_tcgcsv_groups()

    assert loaded == []
    assert abandoned == groups


def test_previous_expansions_are_indexed_by_tcgplayer_group(tmp_path: Path) -> None:
    catalog = tmp_path / "sealed-v2.json"
    catalog.write_text(
        json.dumps(
            {
                "series": [
                    {"name": "Platine", "expansions": [{"id": "PL", "group_id": 1406, "name": "Platine"}]},
                    {"name": "Autres", "expansions": [{"id": "PR", "name": "Sans groupe"}]},
                ]
            }
        ),
        encoding="utf-8",
    )

    previous = build.previous_expansions_by_group(catalog)

    assert previous == {1406: ("Platine", {"id": "PL", "group_id": 1406, "name": "Platine"})}
    assert build.previous_expansions_by_group(tmp_path / "absent.json") == {}


def test_print_run_groups_keep_distinct_names() -> None:
    assert build.PRINT_RUN_RE.search(build.norm("Base Set (Shadowless)")).group(1) == "shadowless"
    assert build.PRINT_RUN_RE.search(build.norm("Base Set")) is None
    assert "base set" in build.set_keys("Base Set (Shadowless)")


def test_embedded_group_logo_points_to_the_bundled_file() -> None:
    assert build.embedded_group_logo({"group_id": 24831}) == "/set-logos/fr/tp-24831.webp"
    assert build.embedded_group_logo({"group_id": 1}) is None
