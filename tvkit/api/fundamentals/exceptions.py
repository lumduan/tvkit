"""Exceptions for :mod:`tvkit.api.fundamentals`.

Mirrors the chart package's single-base hierarchy. The fundamentals client reuses the chart
WebSocket transport, so it may catch :class:`tvkit.api.chart.exceptions.AuthError` /
``StreamConnectionError`` internally and re-wrap them as the fundamentals equivalents below.
"""

from __future__ import annotations

__all__ = [
    "FundamentalsError",
    "FundamentalsAuthError",
    "FundamentalsConnectionError",
    "FundamentalsTimeoutError",
    "NoFundamentalDataError",
]


class FundamentalsError(Exception):
    """Base class for all fundamentals errors."""


class FundamentalsAuthError(FundamentalsError):
    """Raised when the TradingView WebSocket rejects the auth token."""


class FundamentalsConnectionError(FundamentalsError):
    """Raised when the WebSocket connection fails or drops mid-snapshot."""


class FundamentalsTimeoutError(FundamentalsError):
    """Raised when a symbol's ``quote_completed`` is not received before the deadline."""


class NoFundamentalDataError(FundamentalsError):
    """Raised when the server returns no fundamental fields for a symbol.

    Typically an invalid symbol, or an instrument type without financial statements
    (e.g. an index, a currency pair, or an unlisted ticker).
    """
