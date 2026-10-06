"""Types des échanges avec le worker Leboncoin du PC."""

from __future__ import annotations

from typing import TypedDict


class LeboncoinListingRemovalOutcome(TypedDict):
    article_id: int
    delisted: bool
    detail: str | None


class LeboncoinListingRemovalJob(TypedDict):
    user_id: int
    is_finished: bool
    outcomes: list[LeboncoinListingRemovalOutcome]
