"""Package-level exceptions."""

from __future__ import annotations


class CardmarketDataUnavailableError(RuntimeError):
    """Raised when the price guide can neither be downloaded nor served from cache."""
