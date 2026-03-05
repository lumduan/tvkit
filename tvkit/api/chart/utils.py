"""Utility functions for chart API operations."""

import logging
import re
from datetime import UTC, datetime

logger: logging.Logger = logging.getLogger(__name__)

__all__ = [
    "MAX_BARS_REQUEST",
    "to_unix_timestamp",
    "build_range_param",
    "validate_interval",
]

# Precompiled regex for TradingView interval format validation.
# Matches:
#   Minutes: "1", "15", "1440"    (digits only, no unit)
#   Seconds: "1S", "30S"          (digits + S)
#   Hours:   "1H", "12H"          (digits + H)
#   Days:    "D", "1D", "3D"      (optional digits + D)
#   Weeks:   "W", "1W", "4W"      (optional digits + W)
#   Months:  "M", "1M", "12M"     (optional digits + M)
_INTERVAL_RE: re.Pattern[str] = re.compile(r"^(\d+)([SHDWM])?$|^([DWM])$")

# Sentinel bars_count sent in create_series during range mode.
# TradingView ignores this value when modify_series range is active,
# but the parameter slot must be filled. Using 5000 (free tier base limit)
# as the conservative sentinel — safe for all account tiers.
#
# Account tier bar limits (intraday intervals):
#   Free / Basic:     5,000
#   Essential / Plus: 10,000
#   Premium:          20,000
#   Expert:           25,000
#   Ultimate:         40,000
#
# Source: https://www.tradingview.com/support/solutions/43000480679-historical-intraday-data-bars-and-limits-explained/
MAX_BARS_REQUEST: int = 5000


def to_unix_timestamp(ts: datetime | str) -> int:
    """
    Convert a datetime or ISO 8601 string to a UTC Unix timestamp (integer seconds).

    Microseconds are truncated (not rounded) — TradingView uses integer seconds.

    Args:
        ts: A timezone-aware datetime, a naive datetime (see note), or an ISO 8601
            string. Strings with a "Z" UTC designator are supported and normalized
            to "+00:00" before parsing.

    Returns:
        Unix timestamp as integer seconds since epoch. Sub-second precision is
        truncated (e.g., datetime(..., microsecond=999999) yields the same result
        as datetime(..., microsecond=0)).

    Raises:
        TypeError: If ts is not a datetime or str.
        ValueError: If the string cannot be parsed as ISO 8601.

    Note — naive datetimes:
        Naive datetimes (no tzinfo) are **assigned** UTC timezone without any
        conversion. A datetime that represents a local time in another timezone
        will be silently misinterpreted as UTC. Callers who care about correctness
        must supply timezone-aware datetimes.

    Example:
        >>> to_unix_timestamp("2024-01-01")
        1704067200
        >>> to_unix_timestamp("2024-01-01T00:00:00Z")
        1704067200
        >>> to_unix_timestamp(datetime(2024, 1, 1, tzinfo=UTC))
        1704067200
    """
    if not isinstance(ts, datetime | str):
        raise TypeError(f"ts must be a datetime or ISO 8601 string, got {type(ts).__name__!r}")

    if isinstance(ts, str):
        # Normalize "Z" UTC designator — fromisoformat requires "+00:00" not "Z"
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt: datetime = datetime.fromisoformat(ts)
    else:
        dt = ts

    if dt.tzinfo is None:
        logger.debug(
            "to_unix_timestamp received naive datetime %s — "
            "assigning UTC timezone (no conversion applied)",
            dt,
        )
        dt = dt.replace(tzinfo=UTC)

    return int(dt.timestamp())


def build_range_param(start: datetime | str, end: datetime | str) -> str:
    """
    Build a TradingView range parameter string from start and end timestamps.

    This string is passed as the last argument of a modify_series WebSocket message
    to constrain the historical data window. TradingView applies the range server-side
    and streams only bars within the window.

    Args:
        start: Start of the range (inclusive). Accepts a timezone-aware datetime,
            naive datetime (assigned UTC without conversion), or ISO 8601 string
            (including "Z" suffix).
        end: End of the range (inclusive). Same accepted types as start.

    Returns:
        Range string in the format "r,<from_unix>:<to_unix>".

    Raises:
        TypeError: If start or end is not a datetime or str.
        ValueError: If start or end is not a valid ISO 8601 string, or if start > end.
            start == end is valid — allows fetching a single day's intraday bars.

    Example:
        >>> build_range_param("2024-01-01", "2024-12-31")
        'r,1704067200:1735603200'
        >>> build_range_param("2024-06-15", "2024-06-15")  # single day — valid
        'r,1718409600:1718409600'
    """
    from_ts: int = to_unix_timestamp(start)
    to_ts: int = to_unix_timestamp(end)

    if from_ts > to_ts:
        raise ValueError(
            f"start ({start!r}) must not be after end ({end!r}). "
            f"Converted timestamps: start={from_ts}, end={to_ts}"
        )

    return f"r,{from_ts}:{to_ts}"


def validate_interval(interval: str) -> None:
    """
    Validates TradingView interval format.

    Supports TradingView interval formats:

    - Minutes: "1", "5", "15", "30", "45" (number only, 1–1440)
    - Seconds: "1S", "5S", "15S", "30S" (number + S, 1–60)
    - Hours: "1H", "2H", "3H", "4H", "6H", "8H", "12H" (number + H, 1–168)
    - Days: "D", "1D", "2D", "3D" (D or number + D, 1–365)
    - Weeks: "W", "1W", "2W", "3W" (W or number + W, 1–52)
    - Months: "M", "1M", "2M", "3M", "6M" (M or number + M, 1–12)

    Note:
        Range limits (e.g., minutes 1–1440, months 1–12) are client-side safety
        guards. TradingView may accept different ranges server-side. If you need an
        interval outside these bounds, validate against the TradingView UI directly.

    Args:
        interval: The interval string to validate.

    Raises:
        TypeError: If interval is not a string.
        ValueError: If interval is empty or does not match a supported format.

    Example:
        >>> validate_interval("5")        # 5 minutes - valid
        >>> validate_interval("1H")       # 1 hour - valid
        >>> validate_interval("D")        # Daily - valid
        >>> validate_interval("15S")      # 15 seconds - valid
        >>> validate_interval("2W")       # 2 weeks - valid
        >>> validate_interval("invalid")  # Raises ValueError
    """
    if not isinstance(interval, str):
        raise TypeError(f"interval must be a string, got {type(interval).__name__!r}")

    interval = interval.strip()

    if not interval:
        raise ValueError("Interval must be a non-empty string")

    match: re.Match[str] | None = _INTERVAL_RE.fullmatch(interval)
    if not match:
        raise ValueError(
            f"Invalid interval format: '{interval}'. "
            f"Expected formats: minutes (1, 5, 15), seconds (15S), hours (1H), "
            f"days (D, 1D), weeks (W, 1W), months (M, 1M)"
        )

    # Groups: (digits, unit) from first alternative, or (bare_unit,) from second
    digits_str: str | None = match.group(1)
    unit: str | None = match.group(2) or match.group(3)

    # Bare unit with no number (e.g. "D", "W", "M") — always valid
    if digits_str is None:
        return

    value: int = int(digits_str)

    if unit is None:
        # Minutes: digits only
        if value <= 0 or value > 1440:
            raise ValueError(
                f"Invalid minute interval: {interval}. Must be between 1 and 1440 minutes"
            )
    elif unit == "S":
        if value <= 0 or value > 60:
            raise ValueError(f"Invalid second interval: {interval}. Must be between 1S and 60S")
    elif unit == "H":
        if value <= 0 or value > 168:
            raise ValueError(f"Invalid hour interval: {interval}. Must be between 1H and 168H")
    elif unit == "D":
        if value <= 0 or value > 365:
            raise ValueError(f"Invalid day interval: {interval}. Must be between 1D and 365D")
    elif unit == "W":
        if value <= 0 or value > 52:
            raise ValueError(f"Invalid week interval: {interval}. Must be between 1W and 52W")
    elif unit == "M":
        if value <= 0 or value > 12:
            raise ValueError(f"Invalid month interval: {interval}. Must be between 1M and 12M")
