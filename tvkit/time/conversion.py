"""
UTC normalization and timezone conversion utilities.

All functions in this module treat timestamps as UTC-origin values.
The library's UTC invariant: every OHLCVBar.timestamp is a Unix epoch float in UTC.
"""

import logging
import warnings
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

import polars as pl

logger = logging.getLogger(__name__)


def to_utc(dt: datetime) -> datetime:
    """
    Convert any datetime to UTC.

    Naive datetimes are assumed to represent UTC and a one-time warning is emitted
    via ``warnings.warn()`` — not ``logger.warning()`` — to avoid log spam in loops.
    Tz-aware datetimes are silently converted to UTC via ``.astimezone(timezone.utc)``.

    Args:
        dt: Any ``datetime`` object, naive or tz-aware.

    Returns:
        UTC tz-aware ``datetime``.

    Raises:
        TypeError: If ``dt`` is not a ``datetime`` instance.

    Example:
        >>> from datetime import datetime
        >>> from tvkit.time import to_utc
        >>> utc = to_utc(datetime(2024, 1, 1, 9, 30))
        UserWarning: Naive datetime 2024-01-01 09:30:00 assumed UTC. ...
        >>> print(utc)
        2024-01-01 09:30:00+00:00
    """
    if not isinstance(dt, datetime):
        raise TypeError(f"Expected datetime, got {type(dt).__name__!r}")

    if dt.tzinfo is None:
        warnings.warn(
            f"Naive datetime {dt!s} assumed UTC. "
            "Attach tzinfo=timezone.utc to suppress this warning.",
            UserWarning,
            stacklevel=2,
        )
        return dt.replace(tzinfo=UTC)

    offset = dt.utcoffset()
    if dt.tzinfo is UTC or (offset is not None and offset.total_seconds() == 0):
        return dt

    converted = dt.astimezone(UTC)
    logger.debug(
        "Converted tz-aware datetime to UTC",
        extra={"original": str(dt), "utc": str(converted)},
    )
    return converted


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure a datetime is UTC-aware. Semantic alias for :func:`to_utc`.

    Preferred in validation contexts where the intent is "this must be UTC"
    rather than "convert to UTC."

    Args:
        dt: Any ``datetime`` object, naive or tz-aware.

    Returns:
        UTC tz-aware ``datetime``.

    Raises:
        TypeError: If ``dt`` is not a ``datetime`` instance.
    """
    return to_utc(dt)


def convert_timestamp(ts: float, tz: str) -> datetime:
    """
    Convert a UTC Unix epoch float to a tz-aware datetime in the target timezone.

    Useful for single-value conversion outside a DataFrame context.

    The conversion chain is UTC-first: ``epoch → UTC datetime → target timezone``.
    This makes the UTC-origin semantics explicit regardless of the platform locale.

    Args:
        ts: UTC Unix epoch seconds (float).
        tz: IANA timezone string (e.g. ``"Asia/Bangkok"``, ``"America/New_York"``).

    Returns:
        Tz-aware ``datetime`` in the specified timezone.

    Raises:
        ZoneInfoNotFoundError: If ``tz`` is not a valid IANA timezone string.

    Example:
        >>> from tvkit.time import convert_timestamp
        >>> dt = convert_timestamp(1_700_000_000, "Asia/Bangkok")
        >>> print(dt)
        2023-11-15 06:13:20+07:00
    """
    target = ZoneInfo(tz)
    return datetime.fromtimestamp(ts, tz=UTC).astimezone(target)


def convert_to_timezone(
    df: pl.DataFrame,
    tz: str,
    column: str = "timestamp",
    unit: Literal["s", "ms"] = "s",
) -> pl.DataFrame:
    """
    Convert an epoch numeric column in a Polars DataFrame to a tz-aware datetime column.

    The conversion chain is:

    .. code-block:: text

        epoch numeric  →  naive datetime column  →  attach UTC  →  convert to target tz
        from_epoch()      (intermediate)             replace_time_zone("UTC")  convert_time_zone(tz)

    ``replace_time_zone("UTC")`` **must** be called before ``convert_time_zone(tz)``.
    Without it, Polars treats the intermediate datetime column as naive and raises an error
    on ``convert_time_zone()``.

    Args:
        df: Polars DataFrame containing the epoch numeric column.
        tz: IANA timezone string (e.g. ``"Asia/Bangkok"``, ``"America/New_York"``).
        column: Column name to convert. Default: ``"timestamp"``.
        unit: Time unit of the epoch values — ``"s"`` for seconds (default),
            ``"ms"`` for milliseconds. TradingView OHLCV timestamps are seconds.
            Use ``"ms"`` for REST API or third-party data sources that use milliseconds.

    Returns:
        DataFrame with the named column replaced by a tz-aware datetime column.

    Raises:
        ZoneInfoNotFoundError: If ``tz`` is not a valid IANA timezone string.
        ColumnNotFoundError: If ``column`` is not present in ``df``.

    Example:
        >>> from tvkit.time import convert_to_timezone
        >>> df_bkk = convert_to_timezone(df, "Asia/Bangkok")
        >>> df_ms  = convert_to_timezone(df_ms, "UTC", unit="ms")
    """
    return df.with_columns(
        pl.from_epoch(pl.col(column), time_unit=unit)
        .dt.replace_time_zone("UTC")
        .dt.convert_time_zone(tz)
        .alias(column)
    )
