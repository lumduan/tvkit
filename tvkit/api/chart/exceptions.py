"""Exception types for the tvkit.api.chart package."""

__all__ = ["ChartError", "RangeTooLargeError", "StreamConnectionError"]


class ChartError(Exception):
    """Base exception for all chart-related errors in tvkit."""


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
