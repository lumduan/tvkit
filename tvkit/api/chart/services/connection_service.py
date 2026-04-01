"""Connection service for managing WebSocket connections and sessions."""

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator, Awaitable, Callable
from enum import Enum
from typing import Any

from websockets import ClientConnection
from websockets.asyncio.client import connect
from websockets.connection import State as WebSocketState
from websockets.exceptions import ConnectionClosed, WebSocketException

from tvkit.api.chart.exceptions import AuthError, StreamConnectionError
from tvkit.api.chart.models.realtime import (
    ExtraRequestHeader,
    WebSocketConnection,
)
from tvkit.api.utils.retry import calculate_backoff_delay

logger: logging.Logger = logging.getLogger(__name__)

# Protocol identifier constants for TradingView WebSocket series messages.
# These values appear in both create_series and modify_series parameter lists.
# Centralised here to avoid silent regressions if TradingView updates its protocol.
_SERIES_DATASOURCE_ID: str = "sds_1"
_SERIES_ID: str = "s1"
_SYMBOL_REF_ID: str = "sds_sym_1"

# Precompiled patterns for TradingView WebSocket frame parsing.
_HEARTBEAT_RE: re.Pattern[str] = re.compile(r"~m~\d+~m~~h~\d+$")
_FRAME_SPLIT_RE: re.Pattern[str] = re.compile(r"~m~\d+~m~")


class ConnectionState(Enum):
    """Connection state machine states for ConnectionService."""

    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class ConnectionService:
    """
    Service for managing WebSocket connections and TradingView sessions.

    Manages the low-level WebSocket connection lifecycle including automatic
    reconnection with exponential backoff. A background reader task feeds raw
    messages into an internal queue; ``get_data_stream()`` consumes from the
    queue and handles reconnection transparently.

    Args:
        ws_url: WebSocket URL for TradingView data streaming.
        max_attempts: Total connection attempts before raising ``StreamConnectionError``.
        base_backoff: Base retry delay in seconds (doubles each attempt).
        max_backoff: Maximum retry delay cap in seconds.
        jitter_range: Additive jitter range in seconds (0 = disabled).
        connect_timeout: Seconds to wait for a single ``connect()`` call.
        on_reconnect: Optional async callback invoked after each successful reconnect.
            Use this to restore subscription state (e.g. re-send chart session messages).
    """

    def __init__(
        self,
        ws_url: str,
        max_attempts: int = 5,
        base_backoff: float = 1.0,
        max_backoff: float = 30.0,
        jitter_range: float = 0.0,
        connect_timeout: float = 10.0,
        on_reconnect: Callable[[], Awaitable[None]] | None = None,
        auth_token: str = "unauthorized_user_token",
    ) -> None:
        self.ws_url: str = ws_url
        self._auth_token: str = auth_token
        self._ws: ClientConnection | None = None
        self._state: ConnectionState = ConnectionState.IDLE
        self._closing: bool = False
        self._max_attempts: int = max_attempts
        self._base_backoff: float = base_backoff
        self._max_backoff: float = max_backoff
        self._jitter_range: float = jitter_range
        self._connect_timeout: float = connect_timeout
        self._on_reconnect: Callable[[], Awaitable[None]] | None = on_reconnect
        self._reader_task: asyncio.Task[None] | None = None
        # maxsize=1000 bounds memory when consumer lags; put() blocks on full (backpressure).
        self._message_queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=1000)
        # Lock held for the ENTIRE retry loop to block concurrent reconnect callers.
        self._reconnect_lock: asyncio.Lock = asyncio.Lock()

    @property
    def ws(self) -> ClientConnection | None:
        """WebSocket connection (read-only, backward-compatible accessor)."""
        return self._ws

    # ------------------------------------------------------------------
    # Public connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """
        Establish the WebSocket connection and start the background reader task.

        Raises:
            WebSocketException: If the initial connection fails.
            asyncio.TimeoutError: If the connection exceeds ``connect_timeout``.
        """
        self._state = ConnectionState.CONNECTING
        self._closing = False
        try:
            logger.info("Establishing WebSocket connection to %s", self.ws_url)
            await self._connect()
            self._state = ConnectionState.STREAMING
            self._reader_task = asyncio.create_task(self._read_raw_loop(), name="tvkit-ws-reader")
            logger.info("WebSocket connection established successfully")
        except Exception as exc:
            logger.error("Failed to establish WebSocket connection: %s", exc)
            self._state = ConnectionState.IDLE
            raise

    async def close(self) -> None:
        """Close the WebSocket connection and cancel the reader task."""
        self._closing = True
        if self._ws is not None:
            await self._ws.close()
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        self._state = ConnectionState.IDLE

    # ------------------------------------------------------------------
    # Internal connection helpers
    # ------------------------------------------------------------------

    async def _open_websocket(self) -> None:
        """Open the raw WebSocket connection and assign to ``self._ws``."""
        request_header: ExtraRequestHeader = ExtraRequestHeader(
            accept_encoding="gzip, deflate, br, zstd",
            accept_language="en-US,en;q=0.9,fa;q=0.8",
            cache_control="no-cache",
            origin="https://www.tradingview.com",
            pragma="no-cache",
            user_agent="Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        )
        ws_config: WebSocketConnection = WebSocketConnection(
            uri=self.ws_url,
            additional_headers=request_header,
            compression="deflate",
            ping_interval=20,
            ping_timeout=10,
            close_timeout=10,
            max_size=None,
        )
        self._ws = await connect(**ws_config.model_dump())

    async def _connect(self) -> None:
        """Open WebSocket with a configurable timeout.

        Wraps ``_open_websocket()`` with ``asyncio.wait_for`` so a hung TCP/TLS
        handshake does not freeze the retry loop indefinitely.

        Raises:
            asyncio.TimeoutError: If the connection exceeds ``_connect_timeout``.
            WebSocketException: If the WebSocket handshake fails.
            OSError: If a network-level error occurs.
        """
        await asyncio.wait_for(self._open_websocket(), timeout=self._connect_timeout)

    def _drain_queue(self) -> None:
        """Discard all pending items in the message queue.

        Called inside ``_reset_connection()`` to remove stale data frames and
        any sentinel written by the previous reader task before it was cancelled.
        """
        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _reset_connection(self) -> None:
        """Tear down the current connection state before reconnecting.

        Must be called AFTER ``self._state`` is set to ``RECONNECTING`` so the
        sentinel guard in ``_read_raw_loop()`` fires correctly when the reader is
        cancelled.

        Steps (in order):
            1. Cancel and await the reader task (suppress ``CancelledError``).
            2. Close ``self._ws`` if not already closed (suppress all exceptions).
            3. Reset both references to ``None``.
            4. Drain the message queue to remove stale messages and leftover sentinels.
        """
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        self._reader_task = None

        if self._ws and self._ws.state is WebSocketState.OPEN:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws = None

        self._drain_queue()

    # ------------------------------------------------------------------
    # Background reader
    # ------------------------------------------------------------------

    async def _read_raw_loop(self) -> None:
        """Read raw messages from WebSocket, echo heartbeats, feed data frames to queue.

        Runs as a background task (``_reader_task``). Puts raw message strings into
        ``_message_queue``. The consumer (``get_data_stream``) handles JSON parsing and
        frame splitting.

        The ``None`` sentinel placed in the ``finally`` block signals the consumer that
        the stream has ended. It is suppressed (not placed) when ``_state`` is
        ``RECONNECTING`` to prevent a cancelled reader from injecting a false reconnect
        signal into the queue after ``_drain_queue()`` has already cleared it.

        ``put_nowait`` is used for the sentinel to avoid blocking during shutdown when
        the queue is at capacity. A ``QueueFull`` exception is silently suppressed —
        ``close()`` handles teardown regardless of whether the sentinel is delivered.
        """
        if self._ws is None:
            return
        try:
            async for message in self._ws:
                raw: str
                if isinstance(message, str):
                    raw = message
                elif isinstance(message, bytes):
                    raw = message.decode("utf-8")
                else:
                    raw = bytes(message).decode("utf-8")

                if _HEARTBEAT_RE.match(raw):
                    logger.debug("Received heartbeat: %s", raw)
                    try:
                        await self._ws.send(raw)
                    except ConnectionClosed:
                        logger.debug("Connection closed while echoing heartbeat")
                        break
                else:
                    # Blocks when queue is full — provides backpressure to the reader.
                    await self._message_queue.put(raw)

        except ConnectionClosed as exc:
            if not self._closing:
                logger.warning(
                    "WebSocket closed unexpectedly.",
                    extra={"code": exc.rcvd.code if exc.rcvd else None},
                )
        finally:
            # Sentinel signals end-of-stream to the consumer.
            # Suppressed when _state == RECONNECTING: _reset_connection() has already
            # set state before cancelling this task, so the cancelled reader must not
            # inject a false sentinel into the (now drained) queue.
            if self._state != ConnectionState.RECONNECTING:
                try:
                    self._message_queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass

    # ------------------------------------------------------------------
    # Reconnect loop
    # ------------------------------------------------------------------

    async def _reconnect_with_backoff(self) -> None:
        """Retry WebSocket connection using exponential backoff.

        The reconnect lock is held for the entire retry loop. A second concurrent
        caller blocks at the lock boundary until this loop completes (success or
        exhaustion). This prevents a second caller from returning immediately and
        then waiting indefinitely in ``queue.get()`` if reconnect ultimately fails.

        State is set to ``RECONNECTING`` inside the lock before ``_reset_connection()``
        is called. This ordering is required: the sentinel guard in ``_read_raw_loop()``
        checks ``_state`` on task cancellation, so the state must reflect the new context
        before the reader is cancelled.

        Raises:
            StreamConnectionError: After all ``_max_attempts`` are exhausted.
        """
        async with self._reconnect_lock:
            if self._state == ConnectionState.RECONNECTING:
                logger.debug("Reconnect already in progress. Ignoring duplicate trigger.")
                return
            self._state = ConnectionState.RECONNECTING

            last_error: Exception | None = None
            for attempt in range(1, self._max_attempts + 1):
                await self._reset_connection()
                delay: float = calculate_backoff_delay(
                    attempt, self._base_backoff, self._max_backoff, self._jitter_range
                )
                logger.warning(
                    "WebSocket connection lost. Retrying.",
                    extra={
                        "attempt": attempt,
                        "max_attempts": self._max_attempts,
                        "delay_s": delay,
                    },
                )
                await asyncio.sleep(delay)
                try:
                    await self._connect()
                    self._state = ConnectionState.STREAMING
                    self._reader_task = asyncio.create_task(
                        self._read_raw_loop(), name="tvkit-ws-reader"
                    )
                    logger.info(
                        "WebSocket reconnected successfully.",
                        extra={"attempt": attempt},
                    )
                    if self._on_reconnect:
                        await self._on_reconnect()
                    return
                except (TimeoutError, OSError, WebSocketException) as exc:
                    last_error = exc
                    logger.warning(
                        "Reconnect attempt failed.",
                        extra={"attempt": attempt, "error": str(exc)},
                    )

            self._state = ConnectionState.FAILED
            raise StreamConnectionError(
                f"WebSocket reconnection failed after {self._max_attempts} attempts.",
                attempts=self._max_attempts,
                last_error=last_error,
            )

    # ------------------------------------------------------------------
    # Data stream (consumer)
    # ------------------------------------------------------------------

    def _is_auth_error(self, data: dict[str, object]) -> bool:
        """Return True if the parsed TradingView WebSocket frame indicates auth failure.

        Checks two TradingView auth rejection patterns:

        - ``critical_error`` frame with ``error_code == "unauthorized_access"``
        - ``set_auth_token`` response frame with an ``"error"`` field present

        Args:
            data: A parsed JSON dict from the TradingView WebSocket stream.

        Returns:
            True if the frame signals an authentication failure, False otherwise.
        """
        message_type: object = data.get("m")
        params: object = data.get("p", [])
        if not isinstance(params, list):
            return False

        if message_type == "critical_error":
            for param in params:
                if isinstance(param, dict) and param.get("error_code") == "unauthorized_access":
                    return True

        if message_type == "set_auth_token":
            for param in params:
                if isinstance(param, dict) and "error" in param:
                    return True

        return False

    async def get_data_stream(self) -> AsyncGenerator[dict[str, Any], None]:
        """
        Yield parsed TradingView WebSocket frames.

        Reads from the internal message queue fed by the background reader task.
        Reconnects automatically on unexpected disconnections using exponential
        backoff. Yields parsed JSON dicts; skips malformed frames with a warning.

        Yields:
            Parsed TradingView WebSocket frames as parsed JSON dicts.

        Raises:
            RuntimeError: If the WebSocket connection is not established.
            StreamConnectionError: If reconnection is exhausted after all attempts.
            AuthError: If TradingView rejects the authentication token. The connection
                is closed by the ``finally`` block before this exception propagates.
                Callers must re-enter the OHLCV context manager with fresh credentials.
        """
        if self._ws is None:
            raise RuntimeError("WebSocket connection not established")

        try:
            while True:
                raw: str | None = await self._message_queue.get()

                if raw is None:
                    if self._closing:
                        break
                    # Unexpected disconnect — attempt reconnect.
                    try:
                        await self._reconnect_with_backoff()
                    except StreamConnectionError:
                        raise
                    continue  # new reader is running; resume consuming from queue

                split_result: list[str] = [x for x in _FRAME_SPLIT_RE.split(raw) if x]
                for item in split_result:
                    if item:
                        try:
                            parsed: object = json.loads(item)
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse JSON: %s", item)
                            continue
                        if isinstance(parsed, dict) and self._is_auth_error(parsed):
                            logger.error(
                                "WebSocket authentication error — token rejected by TradingView.",
                                extra={"m": parsed.get("m")},
                            )
                            raise AuthError(
                                "TradingView rejected the authentication token. "
                                "Re-enter the OHLCV context manager with fresh credentials."
                            )
                        yield parsed  # type: ignore[misc]
        finally:
            await self.close()

    # ------------------------------------------------------------------
    # Session management (unchanged from original)
    # ------------------------------------------------------------------

    async def initialize_sessions(
        self,
        quote_session: str,
        chart_session: str,
        send_message_func: Callable[[str, list[Any]], Awaitable[None]],
    ) -> None:
        """
        Initializes the WebSocket sessions for quotes and charts.

        Args:
            quote_session: The quote session identifier
            chart_session: The chart session identifier
            send_message_func: Function to send messages through the WebSocket
        """
        await send_message_func("set_auth_token", [self._auth_token])
        await send_message_func("set_locale", ["en", "US"])
        await send_message_func("chart_create_session", [chart_session, ""])
        await send_message_func("quote_create_session", [quote_session])
        await send_message_func("quote_set_fields", [quote_session, *self._get_quote_fields()])
        await send_message_func("quote_hibernate_all", [quote_session])

    def _get_quote_fields(self) -> list[str]:
        """
        Returns the fields to be set for the quote session.

        Returns:
            A list of fields for the quote session.
        """
        return [
            "ch",
            "chp",
            "current_session",
            "description",
            "local_description",
            "language",
            "exchange",
            "fractional",
            "is_tradable",
            "lp",
            "lp_time",
            "minmov",
            "minmove2",
            "original_name",
            "pricescale",
            "pro_name",
            "short_name",
            "type",
            "update_mode",
            "volume",
            "currency_code",
            "rchp",
            "rtc",
        ]

    def _create_series_args(
        self,
        chart_session: str,
        timeframe: str,
        bars_count: int,
    ) -> list[Any]:
        """
        Build the 7-element parameter list for the create_series WebSocket message.

        The parameter order and count are protocol-critical. The trailing empty string
        must always be present — omitting it silently breaks the TradingView protocol.

        Note: tvkit currently supports a single series per chart session. The series
        identifiers (_SERIES_ID, _SERIES_DATASOURCE_ID, _SYMBOL_REF_ID) are fixed
        constants that match this single-series design.

        Args:
            chart_session: The chart session identifier (e.g. "cs_abcdefghijkl").
            timeframe: The interval string (e.g. "1D", "60", "1H").
            bars_count: Number of bars to request. In range mode this is MAX_BARS_REQUEST
                and is overridden by the subsequent modify_series range constraint.

        Returns:
            List of 7 elements:
            [chart_session, "sds_1", "s1", "sds_sym_1", timeframe, bars_count, ""]

        Example:
            >>> svc._create_series_args("cs_abc123", "1D", 100)
            ["cs_abc123", "sds_1", "s1", "sds_sym_1", "1D", 100, ""]
        """
        return [
            chart_session,
            _SERIES_DATASOURCE_ID,
            _SERIES_ID,
            _SYMBOL_REF_ID,
            timeframe,
            bars_count,
            "",
        ]

    def _modify_series_args(
        self,
        chart_session: str,
        timeframe: str,
        range_param: str,
    ) -> list[Any]:
        """
        Build the 6-element parameter list for the modify_series WebSocket message.

        modify_series is sent in range mode immediately after create_series to apply
        the date range constraint. Unlike create_series, it has exactly 6 elements
        with no trailing empty string.

        The range_param value is transmitted as-is. Callers are responsible for
        producing a valid "r,<from_unix>:<to_unix>" string (e.g. via
        tvkit.api.chart.utils.build_range_param()). Malformed strings are not
        validated here — validation belongs at the OHLCV client layer.

        Args:
            chart_session: The chart session identifier (e.g. "cs_abcdefghijkl").
            timeframe: The interval string (e.g. "1D", "60", "1H").
            range_param: TradingView range string in "r,<from_unix>:<to_unix>" format,
                as produced by tvkit.api.chart.utils.build_range_param().

        Returns:
            List of 6 elements:
            [chart_session, "sds_1", "s1", "sds_sym_1", timeframe, range_param]

        Example:
            >>> svc._modify_series_args("cs_abc123", "1D", "r,1704067200:1735603200")
            ["cs_abc123", "sds_1", "s1", "sds_sym_1", "1D", "r,1704067200:1735603200"]
        """
        return [
            chart_session,
            _SERIES_DATASOURCE_ID,
            _SERIES_ID,
            _SYMBOL_REF_ID,
            timeframe,
            range_param,
        ]

    async def add_symbol_to_sessions(
        self,
        quote_session: str,
        chart_session: str,
        exchange_symbol: str,
        timeframe: str,
        bars_count: int,
        send_message_func: Callable[[str, list[Any]], Awaitable[None]],
        *,
        range_param: str = "",
    ) -> None:
        """
        Adds the specified symbol to the quote and chart sessions.

        In count mode (range_param omitted or ""), only create_series is sent.
        In range mode (range_param non-empty), modify_series is sent immediately
        after create_series to apply the date range constraint before data streams.

        This method is designed to be called once per symbol subscription setup.
        Calling it twice on the same chart_session creates a duplicate series on
        the TradingView side — preventing this is a caller responsibility.

        The range_param value is transmitted as-is to the TradingView protocol.
        Validation of range_param format belongs at the OHLCV client layer, where
        build_range_param() produces a validated string before passing it here.

        Args:
            quote_session: The quote session identifier
            chart_session: The chart session identifier
            exchange_symbol: The symbol in 'EXCHANGE:SYMBOL' format
            timeframe: The timeframe for the chart (default is "1")
            bars_count: Number of bars to fetch for the chart
            send_message_func: Function to send messages through the WebSocket
            range_param: TradingView range string ("r,<from_unix>:<to_unix>") for
                date-range mode. When non-empty, a modify_series message is sent
                immediately after create_series to apply the date constraint.
                Defaults to "" (count mode — modify_series is not sent).
        """
        resolve_symbol: str = json.dumps({"adjustment": "splits", "symbol": exchange_symbol})
        await send_message_func("quote_add_symbols", [quote_session, f"={resolve_symbol}"])
        await send_message_func(
            "resolve_symbol", [chart_session, _SYMBOL_REF_ID, f"={resolve_symbol}"]
        )
        await send_message_func(
            "create_series",
            self._create_series_args(chart_session, timeframe, bars_count),
        )
        if range_param:
            await send_message_func(
                "modify_series",
                self._modify_series_args(chart_session, timeframe, range_param),
            )
        await send_message_func("quote_fast_symbols", [quote_session, exchange_symbol])
        await send_message_func(
            "create_study",
            [
                chart_session,
                "st1",
                "st1",
                _SERIES_DATASOURCE_ID,
                "Volume@tv-basicstudies-246",
                {"length": 20, "col_prev_close": "false"},
            ],
        )
        await send_message_func("quote_hibernate_all", [quote_session])

    async def add_multiple_symbols_to_sessions(
        self,
        quote_session: str,
        exchange_symbols: list[str],
        send_message_func: Callable[[str, list[Any]], Awaitable[None]],
    ) -> None:
        """
        Adds multiple symbols to the quote session.

        Args:
            quote_session: The quote session identifier
            exchange_symbols: List of symbols in 'EXCHANGE:SYMBOL' format
            send_message_func: Function to send messages through the WebSocket
        """
        resolve_symbol: str = json.dumps(
            {
                "adjustment": "splits",
                "currency-id": "USD",
                "session": "regular",
                "symbol": exchange_symbols[0],
            }
        )
        await send_message_func("quote_add_symbols", [quote_session, f"={resolve_symbol}"])
        await send_message_func("quote_fast_symbols", [quote_session, f"={resolve_symbol}"])

        await send_message_func("quote_add_symbols", [quote_session] + exchange_symbols)
        await send_message_func("quote_fast_symbols", [quote_session] + exchange_symbols)
