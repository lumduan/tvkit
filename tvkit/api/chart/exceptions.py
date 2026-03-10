"""Exception types for the tvkit.api.chart package."""

__all__ = ["ChartError", "StreamConnectionError"]


class ChartError(Exception):
    """Base exception for all chart-related errors in tvkit."""


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
