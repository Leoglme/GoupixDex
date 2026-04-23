"""TCGdex REST API v2 response shapes (https://tcgdex.dev/)."""

from typing import Any, NotRequired, TypedDict


class TcgdexCardCount(TypedDict, total=False):
    """Card counts inside a set or nested ``set`` on a card."""

    total: int
    official: int
    firstEd: int
    holo: int
    normal: int
    reverse: int


class TcgdexSetBrief(TypedDict, total=False):
    """Row from ``GET /v2/{locale}/sets`` (may omit optional fields)."""

    id: str
    name: str
    logo: str
    symbol: str
    cardCount: TcgdexCardCount


class TcgdexAbbreviation(TypedDict, total=False):
    """Official / internal product codes when present."""

    official: str


class TcgdexSerieRef(TypedDict, total=False):
    """Parent series reference on a set."""

    id: str
    name: str


class TcgdexSeriesBrief(TypedDict, total=False):
    """Row from ``GET /v2/{locale}/series``."""

    id: str
    name: str
    logo: str


class TcgdexSeriesDetail(TypedDict, total=False):
    """Full series from ``GET /v2/{locale}/series/{seriesId}`` (includes nested sets)."""

    id: str
    name: str
    logo: str
    releaseDate: str
    firstSet: TcgdexSetBrief
    lastSet: TcgdexSetBrief
    sets: list[TcgdexSetBrief]


class TcgdexSetLegal(TypedDict, total=False):
    """Play format flags."""

    standard: bool
    expanded: bool


class TcgdexCardInSetBrief(TypedDict, total=False):
    """Card stub embedded in a full set payload."""

    id: str
    localId: str
    name: str
    image: str


class TcgdexSetDetail(TypedDict, total=False):
    """Full set from ``GET /v2/{locale}/sets/{setId}`` (superset of TcgdexSetBrief)."""

    id: str
    name: str
    logo: str
    symbol: str
    cardCount: TcgdexCardCount
    cards: list[TcgdexCardInSetBrief]
    releaseDate: str
    serie: TcgdexSerieRef
    tcgOnline: str
    abbreviation: TcgdexAbbreviation
    legal: TcgdexSetLegal


class TcgdexSetNestedOnCard(TypedDict, total=False):
    """``set`` object on a single-card response (subset of set fields)."""

    id: str
    name: str
    logo: str
    symbol: str
    cardCount: TcgdexCardCount


class TcgdexCardDetail(TypedDict, total=False):
    """Single card from ``GET /v2/{locale}/cards/{cardId}``."""

    id: str
    localId: str
    name: str
    image: str
    rarity: str
    category: str
    set: TcgdexSetNestedOnCard
    pricing: dict[str, Any]
