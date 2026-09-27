import asyncio
from typing import Any

import pytest

from services import leboncoin_service
from services.leboncoin_service import LeboncoinService


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now


class FakeWizardTab:
    """Onglet du dépôt dont l'étape s'affiche une fois l'analyse de l'article terminée."""

    def __init__(self, clock: FakeClock, is_step_shown_by_poll: list[bool]) -> None:
        self.clock = clock
        self.is_step_shown_by_poll = is_step_shown_by_poll

    async def evaluate(self, _script: str, **_options: object) -> Any:
        return (
            self.is_step_shown_by_poll.pop(0) if self.is_step_shown_by_poll else False
        )

    async def sleep(self, seconds: float) -> None:
        self.clock.now += seconds


def use_wizard_tab(
    monkeypatch: pytest.MonkeyPatch, is_step_shown_by_poll: list[bool]
) -> FakeWizardTab:
    clock = FakeClock()
    monkeypatch.setattr(leboncoin_service.time, "monotonic", clock.monotonic)
    return FakeWizardTab(clock, is_step_shown_by_poll)


def test_step_is_filled_once_leboncoin_has_analysed_the_article(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = use_wizard_tab(monkeypatch, [False, False, True])

    assert asyncio.run(LeboncoinService._wait_for_wizard_step(tab)) is True
    assert tab.clock.now == 1.0


def test_wait_gives_up_when_the_analysis_never_ends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = use_wizard_tab(monkeypatch, [])

    assert (
        asyncio.run(LeboncoinService._wait_for_wizard_step(tab, timeout_sec=5.0))
        is False
    )
