"""
Timestamp utilities for TradingView data processing.

This module provides functions for converting between Unix timestamps and ISO 8601 format,
specifically designed for handling TradingView's timestamp format.
"""

from datetime import datetime, timezone


def convert_timestamp_to_iso(timestamp: float) -> str:
    """
    Convert a Unix timestamp to ISO 8601 format string.

    This function converts TradingView timestamps (Unix epoch seconds)
    to human-readable ISO 8601 format with UTC timezone.

    Args:
        timestamp: Unix timestamp as a float (seconds since epoch).

    Returns:
        ISO 8601 formatted datetime string with UTC timezone.

    Example:
        >>> convert_timestamp_to_iso(1753436820.0)
        '2025-07-28T12:13:40+00:00'
        >>> convert_timestamp_to_iso(1640995200.0)
        '2022-01-01T00:00:00+00:00'
    """
    dt: datetime = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.isoformat()
