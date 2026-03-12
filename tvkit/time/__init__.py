"""
tvkit.time — UTC timezone utilities for TradingView OHLCV data.

All timestamps inside tvkit represent UTC Unix epoch seconds. This module provides
utilities for normalizing datetimes to UTC and converting Polars DataFrames or scalar
timestamps to any IANA timezone.

Public API
----------

UTC normalization::

    from tvkit.time import to_utc, ensure_utc

    utc = to_utc(naive_dt)          # assumes UTC, warns once if naive
    utc = ensure_utc(aware_dt)      # converts tz-aware to UTC silently

Scalar conversion::

    from tvkit.time import convert_timestamp

    dt = convert_timestamp(1_700_000_000, "Asia/Bangkok")

DataFrame conversion::

    from tvkit.time import convert_to_timezone, convert_to_exchange_timezone

    df_ny  = convert_to_timezone(df, "America/New_York")
    df_bkk = convert_to_exchange_timezone(df, "SET")        # Asia/Bangkok

Exchange registry::

    from tvkit.time import exchange_timezone, supported_exchanges, exchange_timezone_map
    from tvkit.time import register_exchange, load_exchange_overrides
    from tvkit.time import validate_exchange_registry

    tz = exchange_timezone("NASDAQ")            # "America/New_York"
    register_exchange("MYEX", "Asia/Bangkok")   # runtime extension
"""

import polars as pl

from tvkit.time.conversion import (
    convert_timestamp,
    convert_to_timezone,
    ensure_utc,
    to_utc,
)
from tvkit.time.exchange import (
    exchange_timezone,
    exchange_timezone_map,
    load_exchange_overrides,
    register_exchange,
    supported_exchanges,
    validate_exchange_registry,
)

__all__ = [
    # UTC normalization
    "to_utc",
    "ensure_utc",
    # Scalar conversion
    "convert_timestamp",
    # DataFrame conversion
    "convert_to_timezone",
    "convert_to_exchange_timezone",
    # Exchange registry
    "exchange_timezone",
    "exchange_timezone_map",
    "supported_exchanges",
    "register_exchange",
    "load_exchange_overrides",
    "validate_exchange_registry",
]


def convert_to_exchange_timezone(
    df: pl.DataFrame,
    exchange: str,
    column: str = "timestamp",
    unit: str = "s",
) -> pl.DataFrame:
    """
    Convert the epoch float column to the exchange's local timezone.

    Thin wrapper that resolves the exchange code to an IANA timezone via
    :func:`exchange_timezone`, then delegates to :func:`convert_to_timezone`.

    Args:
        df: Polars DataFrame containing the epoch numeric column.
        exchange: TradingView exchange code (e.g. ``"NASDAQ"``, ``"SET"``, ``"BINANCE"``)
            or full symbol string (e.g. ``"NASDAQ:AAPL"``).
        column: Column name to convert. Default: ``"timestamp"``.
        unit: Time unit of the epoch values — ``"s"`` for seconds (default),
            ``"ms"`` for milliseconds.

    Returns:
        DataFrame with column converted to tz-aware datetime in exchange local time.

    Notes:
        Unknown exchange codes fall back to UTC with a WARNING log.
        Crypto exchanges (e.g. ``"BINANCE"``) map to ``"UTC"`` (24/7 trading, no local session).

    Example:
        >>> from tvkit.time import convert_to_exchange_timezone
        >>> df_ny  = convert_to_exchange_timezone(df, "NASDAQ")   # America/New_York
        >>> df_bkk = convert_to_exchange_timezone(df, "SET")      # Asia/Bangkok
        >>> df_utc = convert_to_exchange_timezone(df, "BINANCE")  # UTC
    """
    tz = exchange_timezone(exchange)
    return convert_to_timezone(df, tz, column=column, unit=unit)  # type: ignore[arg-type]
