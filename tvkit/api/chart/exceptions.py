"""Exception types for the tvkit.api.chart package."""

from datetime import datetime

__all__ = [
    "ChartError",
    "NoHistoricalDataError",
    "RangeTooLargeError",
    "SegmentedFetchError",
    "StreamConnectionError",
]


class ChartError(Exception):
    """Base exception for all chart-related errors in tvkit."""


class NoHistoricalDataError(RuntimeError):
    """
    Raised by ``_fetch_single_range()`` when TradingView returns no bars for the
    requested range.

    Used as a typed signal by ``SegmentedFetchService`` to distinguish an empty
    segment (expected for weekends, holidays, or illiquid periods) from a genuine
    fetch failure. Inherits from ``RuntimeError`` for backward compatibility with
    callers that currently catch ``RuntimeError`` from ``get_historical_ohlcv()``.

    Phase 4 contract: ``_fetch_single_range()`` MUST raise this exception instead of
    the bare ``RuntimeError("No historical data received…")`` so that
    ``SegmentedFetchService`` can catch it without fragile string-match heuristics.

    Example:
        >>> try:
        ...     bars = await client._fetch_single_range("NASDAQ:AAPL", "1D", start, end)
        ... except NoHistoricalDataError:
        ...     bars = []  # expected — no trading activity in this window
    """


class RangeTooLargeError(ValueError):
    """
    Raised when a requested date range requires more segments than MAX_SEGMENTS.

    This exception signals that the combination of date range and interval
    would require more than MAX_SEGMENTS (2000) fetch operations — a guard
    against accidental requests that would produce hundreds of millions of
    bars and exhaust memory.

    Inherits from ValueError so existing callers catching ValueError will
    continue to catch this exception without any code changes (backwards
    compatible).

    Typical causes:
        - Sub-minute intervals (e.g., ``"1S"``) over multi-year ranges
        - Typos in start/end dates (e.g., year 2000 instead of 2020)

    Resolution:
        - Narrow the date range
        - Use a wider interval (e.g., ``"1H"`` instead of ``"1"``)

    Example:
        >>> try:
        ...     segs = segment_time_range(start, end, interval_seconds=1, max_bars=5000)
        ... except RangeTooLargeError as exc:
        ...     print(f"Range too large: {exc}")
    """


class StreamConnectionError(ChartError):
    """
    Raised when WebSocket reconnection fails after exhausting all attempts.

    This exception is raised by ``ConnectionService`` when all retry attempts are
    exhausted and the WebSocket connection cannot be re-established. Callers should
    treat this as a terminal failure for the current streaming session. A new
    streaming session may be started if desired.

    Attributes:
        attempts: Total number of connection attempts made before giving up.
        last_error: The last exception that caused a retry attempt to fail,
            or ``None`` if no individual attempt error was captured.

    Example:
        >>> try:
        ...     async with OHLCV(max_attempts=3) as client:
        ...         async for bar in client.get_ohlcv("NASDAQ:AAPL"):
        ...             process(bar)
        ... except StreamConnectionError as exc:
        ...     print(f"Stream lost after {exc.attempts} attempts: {exc}")
        ...     # Optionally inspect the root cause:
        ...     if exc.last_error:
        ...         print(f"Last error: {exc.last_error}")
    """

    def __init__(
        self,
        message: str,
        attempts: int | None = None,
        last_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.attempts: int | None = attempts
        self.last_error: Exception | None = last_error


class SegmentedFetchError(Exception):
    """
    Raised when a segment fetch fails during a segmented historical OHLCV fetch.

    ``SegmentedFetchService`` wraps any exception from ``_fetch_single_range()``
    (other than ``NoHistoricalDataError``) in this typed exception so that callers
    receive full context about which segment failed and why.

    Attributes:
        segment_index:  1-based index of the failed segment.
        segment_start:  Inclusive start of the failed segment (UTC-aware datetime).
        segment_end:    Inclusive end of the failed segment (UTC-aware datetime).
        total_segments: Total number of segments planned for this operation.
        cause:          The original exception that triggered the failure.

    Example:
        >>> try:
        ...     bars = await client.get_historical_ohlcv(
        ...         "BINANCE:BTCUSDT", "1", start="2020-01-01", end="2024-12-31"
        ...     )
        ... except SegmentedFetchError as exc:
        ...     print(f"Segment {exc.segment_index}/{exc.total_segments} failed")
        ...     print(f"  Range: {exc.segment_start} → {exc.segment_end}")
        ...     print(f"  Cause: {exc.cause}")
    """

    def __init__(
        self,
        segment_index: int,
        segment_start: datetime,
        segment_end: datetime,
        total_segments: int,
        cause: Exception,
    ) -> None:
        super().__init__(
            f"Segment {segment_index}/{total_segments} failed "
            f"({segment_start.isoformat()} \u2192 {segment_end.isoformat()}): {cause}"
        )
        self.segment_index: int = segment_index
        self.segment_start: datetime = segment_start
        self.segment_end: datetime = segment_end
        self.total_segments: int = total_segments
        self.cause: Exception = cause
