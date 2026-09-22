import importlib.util
import json
from pathlib import Path
from types import ModuleType

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
