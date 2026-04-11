"""PokéWallet API response shapes (https://api.pokewallet.io)."""

from typing import NotRequired, TypedDict


class PokeWalletSearchMetadata(TypedDict):
    """Metadata returned alongside search results, summarising source coverage."""

    total_count: int
    tcg: int
    cardmarket: int
    tcg_only: int
    cardmarket_only: int
    both_sources: int


class PokeWalletPagination(TypedDict):
    """Pagination envelope for the search endpoint."""

    page: int
    limit: int
    total: int
    total_pages: int


class PokeWalletSearchOptions(TypedDict, total=False):
    """Optional query flags for ``GET /search`` (page default 1, limit default 20, max 100)."""

    page: int
    limit: int
    pokemonName: str


class PokeWalletGetCardOptions(TypedDict, total=False):
    """Optional query flags for ``GET /cards/:id`` (disambiguation)."""

    setCode: str


class PokeWalletCardInfo(TypedDict, total=False):
    """Core card attributes as returned by the API (fields may be omitted on partial matches)."""

    name: str
    clean_name: str
    set_name: str
    set_code: str
    set_id: str
    card_number: str
    rarity: str
    card_type: str
    hp: str
    stage: str
    card_text: str | None
    attacks: list[str]
    weakness: str
    resistance: str | None
    retreat_cost: str


class PokeWalletTcgPlayerPriceRow(TypedDict):
    """A single TCGPlayer price row for a product sub-type (e.g. Holofoil)."""

    low_price: float
    mid_price: float
    high_price: float
    updated_at: str
    market_price: float
    direct_low_price: float | None
    sub_type_name: str


class PokeWalletTcgPlayerBlock(TypedDict):
    """TCGPlayer listing block; may be absent when the card is not listed there."""

    prices: list[PokeWalletTcgPlayerPriceRow]
    url: str


class PokeWalletCardmarketPriceRow(TypedDict, total=False):
    """
    Cardmarket price snapshot for a variant (normal / holo, etc.).
    Some rows omit fields (API returns partial objects for certain products).
    """

    avg: float | None
    low: float | None
    avg1: float | None
    avg7: float | None
    avg30: float | None
    trend: float | None
    updated_at: str
    variant_type: str


class PokeWalletCardmarketBlock(TypedDict):
    """Cardmarket listing block; absent when the card is TCG-only."""

    product_name: str
    prices: list[PokeWalletCardmarketPriceRow]
    product_url: str


class PokeWalletCard(TypedDict):
    """
    One card hit from search, or the full payload from GET /cards/:id.
    ``id`` may be ``pk_…`` (TCG) or a hex hash (CardMarket-only).
    """

    id: str
    card_info: PokeWalletCardInfo
    tcgplayer: PokeWalletTcgPlayerBlock | None
    cardmarket: PokeWalletCardmarketBlock | None


class PokeWalletSearchResponse(TypedDict):
    """Response body from GET /search."""

    query: str
    results: list[PokeWalletCard]
    pagination: PokeWalletPagination
    metadata: PokeWalletSearchMetadata
