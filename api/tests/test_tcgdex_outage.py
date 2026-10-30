import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

from services import catalog_browse_service as browse
from services import tcgdex_client_service as tcgdex
from services.tcgdex_client_service import TcgdexClientService, TcgdexUnavailableError

INDEX_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "build_catalog_browse_index.py"
NO_AVAILABLE_SERVER = httpx.Response(503, text="no available server")


def _load_index_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_catalog_browse_index", INDEX_SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


index_script = _load_index_script()


def fake_tcgdex(monkeypatch: pytest.MonkeyPatch, answers: list[httpx.Response | Exception]) -> list[str]:
    calls: list[str] = []

    def answer_next(url: str, **_kwargs: Any) -> httpx.Response:
        calls.append(url)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(tcgdex.httpx, "get", answer_next)
    monkeypatch.setattr(tcgdex.time, "sleep", lambda _seconds: None)
    return calls


class FailingSetDetailsClient:
    """Client TCGdex dont toutes les fiches d'extension échouent avec la même erreur."""

    def __init__(self, error: RuntimeError) -> None:
        self.error = error

    def get_set(self, _locale: str, _set_id: str) -> dict[str, Any]:
        raise self.error


def test_tcgdex_restart_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_tcgdex(
        monkeypatch,
        [NO_AVAILABLE_SERVER, httpx.ConnectError("refused"), httpx.Response(200, json=[{"id": "SV"}])],
    )

    assert TcgdexClientService().list_series("ja") == [{"id": "SV"}]
    assert len(calls) == 3


def test_missing_resource_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_tcgdex(monkeypatch, [httpx.Response(404, text="not found")])

    with pytest.raises(RuntimeError) as raised:
        TcgdexClientService().get_set("ja", "XYZ")
    assert not isinstance(raised.value, TcgdexUnavailableError)
    assert len(calls) == 1


def test_tcgdex_still_down_after_the_last_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_tcgdex(monkeypatch, [NO_AVAILABLE_SERVER] * 3)

    with pytest.raises(TcgdexUnavailableError, match="503 Service Unavailable"):
        TcgdexClientService().list_series("ja")
    assert len(calls) == 3


def test_release_facts_tolerate_a_missing_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browse, "_client", lambda: FailingSetDetailsClient(RuntimeError("TCGdex request failed (404)")))

    assert browse._set_release_facts("ja", ["CS1a"]) == {"CS1a": (None, -1)}


def test_release_facts_fail_while_tcgdex_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browse, "_client", lambda: FailingSetDetailsClient(TcgdexUnavailableError("503")))

    with pytest.raises(TcgdexUnavailableError):
        browse._set_release_facts("ja", ["CS1a", "SV1"])


def test_browse_tree_does_not_drop_a_series_while_tcgdex_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    def series_while_down(_locale: str, _series_id: str) -> dict[str, Any]:
        raise TcgdexUnavailableError("503")

    monkeypatch.setattr(browse, "list_series_for_ui", lambda _locale, _name: [{"id": "sv", "name": "Écarlate et Violet"}])
    monkeypatch.setattr(browse, "get_series_for_ui", series_while_down)
    browse._cache._store.clear()

    with pytest.raises(TcgdexUnavailableError):
        browse.browse_catalog_for_ui("fr")


def test_locale_is_rebuilt_once_tcgdex_is_back(monkeypatch: pytest.MonkeyPatch) -> None:
    answers: list[list[dict[str, Any]] | Exception] = [TcgdexUnavailableError("503"), [{"id": "SV", "sets": []}]]
    pauses: list[float] = []

    def browse_after_restart(_locale: str) -> list[dict[str, Any]]:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(browse, "browse_catalog_for_ui", browse_after_restart)
    monkeypatch.setattr(index_script.time, "sleep", pauses.append)

    assert index_script.build_locale_payload("ja") == [{"id": "SV", "name": None, "sets": []}]
    assert pauses == [60.0]


def test_published_index_is_untouched_when_tcgdex_stays_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def browse_down_in_japanese(locale: str) -> list[dict[str, Any]]:
        if locale == "ja":
            raise TcgdexUnavailableError("503")
        return [{"id": "sv", "sets": []}]

    monkeypatch.setattr(browse, "browse_catalog_for_ui", browse_down_in_japanese)
    monkeypatch.setattr(index_script.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(index_script, "OUT_DIR", tmp_path)

    assert index_script.main() == 1
    assert list(tmp_path.iterdir()) == []
