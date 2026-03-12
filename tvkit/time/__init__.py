"""
tvkit.time — UTC timezone utilities for TradingView OHLCV data.

All timestamps inside tvkit represent UTC Unix epoch seconds. This module provides
utilities for normalizing datetimes to UTC and converting Polars DataFrames or scalar
timestamps to any IANA timezone.

Public API
----------

Type alias::

    from tvkit.time import TimestampUnit   # Literal["s", "ms"]

UTC normalization::

    from tvkit.time import to_utc, ensure_utc

    utc = to_utc(naive_dt)          # assumes UTC, warns once if naive
    utc = ensure_utc(aware_dt)      # converts tz-aware to UTC silently

Scalar conversion::

    from tvkit.time import convert_timestamp

    dt = convert_timestamp(1_700_000_000, "Asia/Bangkok")   # UTC epoch seconds → tz-aware

DataFrame conversion (returns a new DataFrame — input is never mutated)::

    from tvkit.time import convert_to_timezone, convert_to_exchange_timezone

    df_ny  = convert_to_timezone(df, "America/New_York")
    df_bkk = convert_to_exchange_timezone(df, "SET")        # Asia/Bangkok
    df_utc = convert_to_exchange_timezone(df, "BINANCE")    # UTC (24/7 trading, no local session)

Exchange registry::

    from tvkit.time import exchange_timezone, supported_exchanges, exchange_timezone_map
    from tvkit.time import register_exchange, load_exchange_overrides
    from tvkit.time import validate_exchange_registry

    tz = exchange_timezone("NASDAQ")            # "America/New_York"
    register_exchange("MYEX", "Asia/Bangkok")   # runtime extension

Stability
---------

The symbols in ``__all__`` below are the stable public API. Internal modules
(``tvkit.time.conversion``, ``tvkit.time.exchange``) are implementation details
and may change without notice.
"""

import polars as pl

from tvkit.time.conversion import (
    TimestampUnit,
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
    # Type alias
    "TimestampUnit",
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
    unit: TimestampUnit = "s",
) -> pl.DataFrame:
    """
    Convert the epoch column to the exchange's local timezone.

    Thin wrapper that resolves the exchange code to an IANA timezone via
    :func:`exchange_timezone`, then delegates to :func:`convert_to_timezone`.

    Args:
        df: Polars DataFrame containing the epoch numeric column.
        exchange: TradingView exchange code (e.g. ``"NASDAQ"``, ``"SET"``, ``"BINANCE"``)
            or full symbol string (e.g. ``"NASDAQ:AAPL"``). Case-insensitive.
        column: Column name to convert. Default: ``"timestamp"``.
        unit: Time unit of the epoch values — ``"s"`` for seconds (default;
            TradingView OHLCV timestamps), ``"ms"`` for milliseconds.

    Returns:
        New DataFrame with the named column replaced by a tz-aware datetime column
        in the exchange's local timezone. The original DataFrame is not mutated
        (Polars ``with_columns`` immutability).

    Notes:
        Unknown exchange codes fall back to UTC with a WARNING log (logged once per
        unique unknown code). Crypto exchanges (e.g. ``"BINANCE"``, ``"COINBASE"``)
        map to ``"UTC"`` — they operate 24/7 with no market open/close session and no
        concept of exchange-local time.

    Example:
        >>> from tvkit.time import convert_to_exchange_timezone
        >>> df_ny  = convert_to_exchange_timezone(df, "NASDAQ")   # America/New_York
        >>> df_bkk = convert_to_exchange_timezone(df, "SET")      # Asia/Bangkok
        >>> df_utc = convert_to_exchange_timezone(df, "BINANCE")  # UTC (24/7, no local session)
    """
    tz = exchange_timezone(exchange)
    return convert_to_timezone(df, tz, column=column, unit=unit)
