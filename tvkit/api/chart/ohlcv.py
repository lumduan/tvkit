"""Module providing async functions which return async generators containing trades realtime data."""

import asyncio
import logging
import math
import types
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from tvkit.api.chart.exceptions import NoHistoricalDataError
from tvkit.api.chart.models.ohlcv import (
    OHLCVBar,
    OHLCVResponse,
    QuoteCompletedMessage,
    QuoteSymbolData,
    TimescaleUpdateResponse,
    WebSocketMessage,
)
from tvkit.api.chart.services import ConnectionService, MessageService
from tvkit.api.chart.services.segmented_fetch_service import SegmentedFetchService
from tvkit.api.chart.utils import (
    MAX_BARS_REQUEST,
    _to_utc_datetime,
    build_range_param,
    end_of_day_timestamp,
    interval_to_seconds,
    to_unix_timestamp,
    validate_interval,
)
from tvkit.api.utils import convert_symbol_format, validate_symbols
from tvkit.time import ensure_utc

logger: logging.Logger = logging.getLogger(__name__)


def _normalize_input(dt: datetime | str) -> datetime:
    """Normalize a start/end input to a UTC-aware datetime (integer-second precision).

    - ``datetime`` objects run through :func:`tvkit.time.ensure_utc` first, which
      attaches UTC and emits a one-time ``UserWarning`` for naive datetimes, then
      delegates to :func:`_to_utc_datetime` for integer-second truncation.
    - ``str`` values are parsed directly by :func:`_to_utc_datetime` (ISO 8601,
      including the ``Z`` suffix).

    Args:
        dt: UTC-aware datetime, naive datetime, or ISO 8601 string.

    Returns:
        UTC-aware ``datetime`` truncated to integer seconds.
    """
    if isinstance(dt, datetime):
        dt = ensure_utc(dt)
    return _to_utc_datetime(dt)


# Intervals that bypass segmentation. Monthly/weekly intervals never accumulate enough
# bars to require segmentation, and variable-length durations make segment sizing
# unreliable. Keep in sync with _UNSUPPORTED_INTERVALS in utils.py.
# Uses an explicit set — NOT endswith("M") — to avoid matching "15M" as monthly.
_MONTHLY_WEEKLY_INTERVALS: frozenset[str] = frozenset(
    {"M", "1M", "2M", "3M", "6M", "W", "1W", "2W", "3W"}
)


@dataclass(frozen=True)
class _StreamingSession:
    """Immutable session snapshot used to restore streaming after reconnect.

    Stored after each successful call to ``_prepare_chart_session``. Used by
    ``_restore_session`` to re-initialize the chart session and re-subscribe to
    the symbol after a WebSocket reconnect. Never exposed in the public API.

    Attributes:
        symbol: TradingView symbol in EXCHANGE:SYMBOL format.
        interval: Chart interval string (e.g. "1D", "60").
        bars_count: Number of bars requested.
        quote_session: Quote session identifier (e.g. "qs_abc123").
        chart_session: Chart session identifier (e.g. "cs_abc123").
        range_param: TradingView range string if range mode, else "".
    """

    symbol: str
    interval: str
    bars_count: int
    quote_session: str
    chart_session: str
    range_param: str = ""


# Timeout constants for get_historical_ohlcv().
# Range mode uses a longer timeout — multi-year intraday streams can be slow.
_HISTORICAL_TIMEOUT_SECONDS: int = 30
_HISTORICAL_RANGE_TIMEOUT_SECONDS: int = 180


class OHLCV:
    """
    A real-time data streaming client for TradingView WebSocket API.

    This class provides async generators for streaming live market data including
    OHLCV bars, quote data, and trade information from TradingView.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        base_backoff: float = 1.0,
        max_backoff: float = 30.0,
    ) -> None:
        """
        Initializes the OHLCV client with WebSocket connection parameters.

        All retry parameters are optional with safe defaults. Existing call sites
        require no changes — ``OHLCV()`` works identically to before.

        Args:
            max_attempts: Total WebSocket connection attempts before raising
                ``StreamConnectionError`` (default: 5). Counts initial attempt
                plus all retries.
            base_backoff: Base retry delay in seconds. Doubles each attempt
                (default: 1.0).
            max_backoff: Maximum retry delay cap in seconds. Applied before and
                after jitter (default: 30.0).
        """
        self.ws_url: str = "wss://data.tradingview.com/socket.io/websocket?from=chart%2F"
        self.connection_service: ConnectionService | None = None
        self.message_service: MessageService | None = None
        self._max_attempts: int = max_attempts
        self._base_backoff: float = base_backoff
        self._max_backoff: float = max_backoff
        self._session: _StreamingSession | None = None

    async def __aenter__(self) -> "OHLCV":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        self._session = None
        if self.connection_service:
            await self.connection_service.close()

    async def _setup_services(self) -> None:
        """Initialize and connect the services, closing any existing connection first."""
        if self.connection_service is not None:
            await self.connection_service.close()
        self.connection_service = ConnectionService(
            self.ws_url,
            max_attempts=self._max_attempts,
            base_backoff=self._base_backoff,
            max_backoff=self._max_backoff,
            on_reconnect=self._restore_session,
        )
        await self.connection_service.connect()
        if self.connection_service.ws is None:
            raise RuntimeError("WebSocket connection not established after connect()")
        self.message_service = MessageService(self.connection_service.ws)

    async def _restore_session(self) -> None:
        """Re-establish the chart session after a WebSocket reconnect.

        Called by ``ConnectionService`` immediately after a successful reconnect
        and before the message processing loop resumes. Recreates the
        ``MessageService`` with the new WebSocket reference and re-sends all
        session initialization and symbol subscription messages.

        This method is idempotent: calling it multiple times (e.g. across
        consecutive reconnects) produces the same final state — a clean session
        with the original subscription active.

        If no session has been established yet or there is no active connection
        service, this method returns without action.

        Raises:
            Exception: Any exception from session initialization is logged then
                re-raised so ``ConnectionService`` can decide whether to continue
                the retry loop.
        """
        # Snapshot before the first await to guard against concurrent __aexit__
        # setting self._session = None while this coroutine is suspended.
        session = self._session
        if session is None or self.connection_service is None:
            return
        logger.info(
            "Restoring streaming session after reconnect.",
            extra={
                "symbol": session.symbol,
                "interval": session.interval,
                "chart_session": session.chart_session,
            },
        )
        try:
            if self.connection_service.ws is None:
                raise RuntimeError("WebSocket connection not established after reconnect")
            self.message_service = MessageService(self.connection_service.ws)
            send_message_func = self.message_service.get_send_message_callable()
            await self.connection_service.initialize_sessions(
                session.quote_session,
                session.chart_session,
                send_message_func,
            )
            await self.connection_service.add_symbol_to_sessions(
                session.quote_session,
                session.chart_session,
                session.symbol,
                session.interval,
                session.bars_count,
                send_message_func,
                range_param=session.range_param,
            )
        except Exception:
            logger.exception(
                "Failed to restore streaming session after reconnect.",
                extra={"symbol": session.symbol, "interval": session.interval},
            )
            raise
        logger.info(
            "Session restored successfully.",
            extra={"symbol": session.symbol, "interval": session.interval},
        )

    async def _prepare_chart_session(
        self,
        converted_symbol: str,
        interval: str,
        bars_count: int,
        *,
        range_param: str = "",
    ) -> None:
        """
        Set up services and subscribe the chart session to symbol data.

        Calls _setup_services (closes any existing connection first), generates
        unique session IDs, initializes sessions, and subscribes to symbol data.

        Args:
            converted_symbol: Symbol in EXCHANGE:SYMBOL format.
            interval: Chart interval (e.g. "1", "5", "1D").
            bars_count: Number of bars to request.
            range_param: TradingView range string (e.g. "r,<from>:<to>"). If non-empty,
                a modify_series message is sent immediately after create_series to apply
                the date range constraint. Empty string means count mode (default).

        Raises:
            RuntimeError: If services fail to initialize.
        """
        await self._setup_services()
        if self.connection_service is None or self.message_service is None:
            raise RuntimeError("Services not properly initialized")

        quote_session: str = self.message_service.generate_session(prefix="qs_")
        chart_session: str = self.message_service.generate_session(prefix="cs_")
        logger.debug(f"Sessions: quote={quote_session}, chart={chart_session}")

        send_message_func = self.message_service.get_send_message_callable()
        await self.connection_service.initialize_sessions(
            quote_session, chart_session, send_message_func
        )
        await self.connection_service.add_symbol_to_sessions(
            quote_session,
            chart_session,
            converted_symbol,
            interval,
            bars_count,
            send_message_func,
            range_param=range_param,
        )
        self._session = _StreamingSession(
            symbol=converted_symbol,
            interval=interval,
            bars_count=bars_count,
            quote_session=quote_session,
            chart_session=chart_session,
            range_param=range_param,
        )

    def _validate_range(self, start: datetime, end: datetime) -> tuple[datetime, datetime]:
        """
        Validate a date range and clamp future end dates.

        ``start == end`` is valid — it fetches bars for a single period (e.g., one
        minute, one day). Only a strict ``start > end`` (after optional clamping)
        raises ``ValueError``.

        Args:
            start: Inclusive start (UTC-aware datetime).
            end:   Inclusive end (UTC-aware datetime).

        Returns:
            Tuple of (start, end) — end may be clamped to the current UTC time if
            it was in the future.

        Raises:
            ValueError: If start > end after optional future-date clamping.
        """
        now: datetime = datetime.now(tz=UTC)
        if end > now:
            logger.debug(
                "end is in the future — clamping to current UTC time.",
                extra={"original_end": end.isoformat(), "clamped_to": now.isoformat()},
            )
            end = now
        if start > end:
            raise ValueError(
                f"start ({start.isoformat()!r}) must not be after end ({end.isoformat()!r})."
            )
        return start, end

    def _needs_segmentation(self, start: datetime, end: datetime, interval: str) -> bool:
        """
        Return True if the estimated bar count for the range exceeds MAX_BARS_REQUEST.

        Monthly and weekly intervals always return False — they never accumulate enough
        bars to require segmentation, and variable-length durations complicate segment
        sizing. Invalid intervals also return False — validation is handled downstream
        by ``_fetch_single_range()``.

        Overflow protection (e.g. 1-second interval over 50 years) is handled upstream
        by ``segment_time_range()`` via ``RangeTooLargeError`` when the estimated segment
        count exceeds ``MAX_SEGMENTS = 2000``.

        Args:
            start:    Inclusive start (UTC-aware datetime).
            end:      Inclusive end (UTC-aware datetime).
            interval: TradingView interval string.

        Returns:
            True if segmentation is required; False otherwise.
        """
        if interval in _MONTHLY_WEEKLY_INTERVALS:
            return False
        try:
            interval_secs: int = interval_to_seconds(interval)
        except (TypeError, ValueError):
            return False  # invalid interval handled downstream by validate_interval()
        if interval_secs <= 0:
            return False  # defensive guard — interval_to_seconds() should never return 0
        range_secs: int = int(end.timestamp()) - int(start.timestamp())
        if range_secs <= 0:
            return False  # start == end or start > end — zero or negative bars, no segmentation
        estimated_bars: int = math.ceil(range_secs / interval_secs)
        return estimated_bars > MAX_BARS_REQUEST

    async def _fetch_single_range(
        self,
        exchange_symbol: str,
        interval: str,
        *,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar]:
        """
        Perform a single-request historical fetch using range mode.

        This is the private implementation used by both ``get_historical_ohlcv()``
        (for small ranges) and ``SegmentedFetchService`` (for individual segments).

        It does NOT check ``_needs_segmentation()`` — callers that need segmentation
        must use ``get_historical_ohlcv()`` instead. Calling this directly from
        ``SegmentedFetchService`` is intentional and avoids infinite recursion.

        Both ``start`` and ``end`` must be UTC-aware ``datetime`` objects. Normalization
        from strings or naive datetimes is the caller's responsibility
        (``get_historical_ohlcv()`` via ``_to_utc_datetime()``; ``SegmentedFetchService``
        enforces the same contract). This enforces a clear layer boundary.

        Args:
            exchange_symbol: TradingView symbol in EXCHANGE:SYMBOL format.
            interval:        TradingView interval string.
            start:           Inclusive start of the range (UTC-aware datetime, keyword-only).
            end:             Inclusive end of the range (UTC-aware datetime, keyword-only).

        Returns:
            List of OHLCVBar objects, sorted ascending by timestamp.

        Raises:
            NoHistoricalDataError: If no bars are received from TradingView for the
                requested range. Expected for segments covering weekends, holidays,
                or illiquid periods — ``SegmentedFetchService`` catches this and treats
                it as an empty result, not a failure.
            ValueError: If the symbol or interval is invalid.
        """
        await validate_symbols(exchange_symbol)
        symbol_result = convert_symbol_format(exchange_symbol)
        converted_symbol: str = symbol_result.converted_symbol  # type: ignore
        validate_interval(interval)

        range_param: str = build_range_param(start, end)
        await self._prepare_chart_session(
            converted_symbol, interval, MAX_BARS_REQUEST, range_param=range_param
        )

        if self.connection_service is None:
            raise RuntimeError("Services not properly initialized")

        historical_bars: list[OHLCVBar] = []
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        start_time: float = loop.time()
        series_completed_received: bool = False

        async for data in self.connection_service.get_data_stream():
            if loop.time() - start_time > _HISTORICAL_RANGE_TIMEOUT_SECONDS:
                logger.warning(
                    "Historical data fetch timed out after %d seconds",
                    _HISTORICAL_RANGE_TIMEOUT_SECONDS,
                )
                break

            try:
                message: WebSocketMessage = WebSocketMessage.model_validate(data)
                message_type: str = message.message_type

                logger.debug(f"Received message type: {message_type}")

                if message_type == "timescale_update":
                    try:
                        logger.debug(f"Raw timescale_update data: {data}")
                        timescale_response: TimescaleUpdateResponse = (
                            TimescaleUpdateResponse.model_validate(data)
                        )
                        logger.info(
                            "Received %d historical OHLCV bars",
                            len(timescale_response.ohlcv_bars),
                        )
                        for bar in timescale_response.ohlcv_bars:
                            logger.debug(f"Parsed OHLCV bar: {bar}")
                        historical_bars.extend(timescale_response.ohlcv_bars)
                    except ValidationError as e:
                        logger.warning(f"Failed to parse 'timescale_update' message: {e}")
                        logger.debug(f"Raw message that failed to parse: {data}")
                        continue

                elif message_type == "du":
                    try:
                        ohlcv_response: OHLCVResponse = OHLCVResponse.model_validate(data)
                        if ohlcv_response.ohlcv_bars:
                            logger.info(
                                "Received %d OHLCV bars from data update",
                                len(ohlcv_response.ohlcv_bars),
                            )
                            historical_bars.extend(ohlcv_response.ohlcv_bars)
                    except ValidationError as e:
                        logger.debug(f"Failed to parse 'du' message as OHLCV: {e}")
                        continue

                elif message_type == "quote_completed":
                    try:
                        quote_completed: QuoteCompletedMessage = (
                            QuoteCompletedMessage.model_validate(data)
                        )
                        logger.debug(f"Quote setup completed for symbol: {quote_completed.symbol}")
                    except ValidationError as e:
                        logger.debug(f"Failed to parse 'quote_completed' message: {e}")
                    continue

                elif message_type in ("series_loading", "study_loading"):
                    logger.debug(f"{message_type} for historical data fetch")
                    continue

                elif message_type == "series_completed":
                    series_completed_received = True
                    logger.info(
                        "Series completed — received %d historical bars", len(historical_bars)
                    )
                    break

                elif message_type == "study_completed":
                    # In TradingView historical flow, `study_completed` is emitted only after
                    # all `timescale_update` bars have been transmitted. Breaking here is safe.
                    # In practice, `series_completed` fires first (the branch above exits before
                    # this is reached), so this serves as a safety net for atypical ordering.
                    logger.info("Study completed — terminating historical fetch")
                    break

                elif message_type == "series_error":
                    logger.error(
                        "Series error received from TradingView during historical data fetch"
                    )
                    logger.error(f"Error details: {data}")
                    logger.error(
                        "Please check the interval - this timeframe may not be supported for the symbol"
                    )
                    logger.error("Also verify that bars_count is within valid range")
                    if self.connection_service:
                        await self.connection_service.close()
                    raise ValueError(
                        "TradingView series error: Invalid interval or bars count. "
                        "Please check that the timeframe is supported for this symbol "
                        "and that bars_count is within valid range."
                    )

                else:
                    logger.debug(f"Skipping message type '{message_type}' in historical data fetch")
                    continue

            except Exception as e:
                # Re-raise intentional ValueErrors (e.g. from series_error handler).
                # pydantic.ValidationError is a subclass of ValueError in pydantic v2,
                # so exclude it explicitly — invalid message structures are skipped, not
                # propagated.  Other ValueErrors (raised deliberately by this method)
                # must propagate to the caller.
                if isinstance(e, ValueError) and not isinstance(e, ValidationError):
                    raise
                logger.debug(
                    f"Skipping unparseable message in historical fetch: {data} - Error: {e}"
                )
                continue

        if not series_completed_received:
            logger.warning(
                "Stream ended without series_completed for %s (%s) — "
                "data may be incomplete. Received %d bars.",
                converted_symbol,
                interval,
                len(historical_bars),
            )

        # Sort bars by timestamp for chronological order.
        historical_bars.sort(key=lambda bar: bar.timestamp)

        # Client-side range filter: TradingView's modify_series range constraint is
        # applied server-side but does not guarantee strict boundary adherence — bars
        # beyond the requested end date (e.g., the live/current period) may bleed
        # through. This O(n) filter removes any such out-of-range bars.
        from_ts: int = to_unix_timestamp(start)
        to_ts_inclusive: int = end_of_day_timestamp(end)
        pre_filter_count: int = len(historical_bars)
        historical_bars = [
            bar for bar in historical_bars if from_ts <= bar.timestamp <= to_ts_inclusive
        ]
        removed: int = pre_filter_count - len(historical_bars)
        if removed > 0:
            logger.debug(
                "Range post-filter removed %d out-of-range bar(s) "
                "(from_ts=%d, to_ts=%d, remaining=%d)",
                removed,
                from_ts,
                to_ts_inclusive,
                len(historical_bars),
            )

        if not historical_bars:
            logger.warning(f"No historical bars received for symbol {converted_symbol}")
            raise NoHistoricalDataError(
                f"No historical data received for symbol {converted_symbol}"
            )

        logger.info(
            "Successfully fetched %d historical OHLCV bars for %s",
            len(historical_bars),
            converted_symbol,
        )
        return historical_bars

    async def _fetch_count_mode(
        self,
        exchange_symbol: str,
        interval: str,
        *,
        bars_count: int,
    ) -> list[OHLCVBar]:
        """
        Perform a count-based historical fetch (most recent N bars).

        Private implementation for count mode in ``get_historical_ohlcv()``.
        Should not be called directly — use ``get_historical_ohlcv()`` with
        ``bars_count`` instead.

        Args:
            exchange_symbol: TradingView symbol in EXCHANGE:SYMBOL format.
            interval:        TradingView interval string.
            bars_count:      Number of bars to fetch (keyword-only). Must be > 0.

        Returns:
            List of OHLCVBar objects, sorted ascending by timestamp.
            May contain fewer bars than requested if the symbol has limited history.

        Raises:
            RuntimeError: If no bars are received from TradingView.
            ValueError:   If the symbol or interval is invalid.
        """
        await validate_symbols(exchange_symbol)
        symbol_result = convert_symbol_format(exchange_symbol)
        converted_symbol: str = symbol_result.converted_symbol  # type: ignore
        validate_interval(interval)

        await self._prepare_chart_session(converted_symbol, interval, bars_count, range_param="")

        if self.connection_service is None:
            raise RuntimeError("Services not properly initialized")

        historical_bars: list[OHLCVBar] = []
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        start_time: float = loop.time()
        series_completed_received: bool = False

        async for data in self.connection_service.get_data_stream():
            if loop.time() - start_time > _HISTORICAL_TIMEOUT_SECONDS:
                logger.warning(
                    "Historical data fetch timed out after %d seconds", _HISTORICAL_TIMEOUT_SECONDS
                )
                break

            try:
                message: WebSocketMessage = WebSocketMessage.model_validate(data)
                message_type: str = message.message_type

                logger.debug(f"Received message type: {message_type}")

                if message_type == "timescale_update":
                    try:
                        logger.debug(f"Raw timescale_update data: {data}")
                        timescale_response: TimescaleUpdateResponse = (
                            TimescaleUpdateResponse.model_validate(data)
                        )
                        logger.info(
                            "Received %d historical OHLCV bars",
                            len(timescale_response.ohlcv_bars),
                        )
                        for bar in timescale_response.ohlcv_bars:
                            logger.debug(f"Parsed OHLCV bar: {bar}")
                        historical_bars.extend(timescale_response.ohlcv_bars)
                        # In count mode, break early once enough bars are accumulated.
                        if len(historical_bars) >= bars_count:
                            break
                    except ValidationError as e:
                        logger.warning(f"Failed to parse 'timescale_update' message: {e}")
                        logger.debug(f"Raw message that failed to parse: {data}")
                        continue

                elif message_type == "du":
                    try:
                        ohlcv_response: OHLCVResponse = OHLCVResponse.model_validate(data)
                        if ohlcv_response.ohlcv_bars:
                            logger.info(
                                "Received %d OHLCV bars from data update",
                                len(ohlcv_response.ohlcv_bars),
                            )
                            historical_bars.extend(ohlcv_response.ohlcv_bars)
                    except ValidationError as e:
                        logger.debug(f"Failed to parse 'du' message as OHLCV: {e}")
                        continue

                elif message_type == "quote_completed":
                    try:
                        quote_completed: QuoteCompletedMessage = (
                            QuoteCompletedMessage.model_validate(data)
                        )
                        logger.debug(f"Quote setup completed for symbol: {quote_completed.symbol}")
                    except ValidationError as e:
                        logger.debug(f"Failed to parse 'quote_completed' message: {e}")
                    continue

                elif message_type in ("series_loading", "study_loading"):
                    logger.debug(f"{message_type} for historical data fetch")
                    continue

                elif message_type == "series_completed":
                    series_completed_received = True
                    logger.info(
                        "Series completed — received %d historical bars", len(historical_bars)
                    )
                    break

                elif message_type == "study_completed":
                    logger.info("Study completed — terminating historical fetch")
                    break

                elif message_type == "series_error":
                    logger.error(
                        "Series error received from TradingView during historical data fetch"
                    )
                    logger.error(f"Error details: {data}")
                    logger.error(
                        "Please check the interval - this timeframe may not be supported for the symbol"
                    )
                    logger.error("Also verify that bars_count is within valid range")
                    if self.connection_service:
                        await self.connection_service.close()
                    raise ValueError(
                        "TradingView series error: Invalid interval or bars count. "
                        "Please check that the timeframe is supported for this symbol "
                        "and that bars_count is within valid range."
                    )

                else:
                    logger.debug(f"Skipping message type '{message_type}' in historical data fetch")
                    continue

            except Exception as e:
                # Re-raise intentional ValueErrors (e.g. from series_error handler).
                # pydantic.ValidationError is a subclass of ValueError in pydantic v2,
                # so exclude it explicitly.
                if isinstance(e, ValueError) and not isinstance(e, ValidationError):
                    raise
                logger.debug(
                    f"Skipping unparseable message in historical fetch: {data} - Error: {e}"
                )
                continue

        if not series_completed_received:
            logger.warning(
                "Stream ended without series_completed for %s (%s) — "
                "data may be incomplete. Received %d bars.",
                converted_symbol,
                interval,
                len(historical_bars),
            )

        # Sort bars by timestamp for chronological order.
        historical_bars.sort(key=lambda bar: bar.timestamp)

        if not historical_bars:
            logger.warning(f"No historical bars received for symbol {converted_symbol}")
            raise RuntimeError(f"No historical data received for symbol {converted_symbol}")

        if len(historical_bars) < bars_count:
            logger.info(
                "Partial data: received %d bars (requested %d) — "
                "symbol may have less available history",
                len(historical_bars),
                bars_count,
            )

        logger.info(
            "Successfully fetched %d historical OHLCV bars for %s",
            len(historical_bars),
            converted_symbol,
        )
        return historical_bars

    async def get_ohlcv(
        self, exchange_symbol: str, interval: str = "1", bars_count: int = 10
    ) -> AsyncGenerator[OHLCVBar, None]:
        """
        Returns an async generator that yields OHLC data for a specified symbol in real-time.

        This is the primary method for streaming structured OHLCV data from TradingView.
        Each yielded bar contains open, high, low, close, volume, and timestamp information.
        Symbols are automatically converted from EXCHANGE-SYMBOL to EXCHANGE:SYMBOL format.

        Args:
            exchange_symbol: The symbol in 'EXCHANGE:SYMBOL' or 'EXCHANGE-SYMBOL' format (e.g., 'BINANCE:BTCUSDT' or 'USI-PCC').
            interval: The interval for the chart (default is "1" for 1 minute).
            bars_count: The number of bars to fetch (default is 10).

        Returns:
            An async generator yielding structured OHLCV data as OHLCVBar objects.

        Raises:
            ValueError: If the symbol format is invalid
            WebSocketException: If connection or streaming fails

        Example:
            >>> async with OHLCV() as client:
            ...     async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="5"):
            ...         print(f"Close: ${bar.close}, Volume: {bar.volume}")
        """
        await validate_symbols(exchange_symbol)
        symbol_result = convert_symbol_format(exchange_symbol)
        converted_symbol: str = symbol_result.converted_symbol  # type: ignore
        validate_interval(interval)
        await self._prepare_chart_session(converted_symbol, interval, bars_count)

        if self.connection_service is None:
            raise RuntimeError("Services not properly initialized")

        async for data in self.connection_service.get_data_stream():
            try:
                message: WebSocketMessage = WebSocketMessage.model_validate(data)
                message_type: str = message.message_type

                logger.debug(f"Received message type: {message_type}")

                if message_type == "du":
                    try:
                        ohlcv_response: OHLCVResponse = OHLCVResponse.model_validate(data)
                        for ohlcv_bar in ohlcv_response.ohlcv_bars:
                            yield ohlcv_bar
                    except ValidationError as e:
                        logger.debug(f"Failed to parse 'du' message as OHLCV: {e}")
                        continue

                elif message_type == "timescale_update":
                    try:
                        timescale_response: TimescaleUpdateResponse = (
                            TimescaleUpdateResponse.model_validate(data)
                        )
                        logger.info(
                            f"Received {len(timescale_response.ohlcv_bars)} OHLCV bars from timescale update"
                        )
                        for ohlcv_bar in timescale_response.ohlcv_bars:
                            yield ohlcv_bar
                    except ValidationError as e:
                        logger.debug(f"Failed to parse 'timescale_update' message as OHLCV: {e}")
                        continue

                elif message_type == "qsd":
                    try:
                        quote_data: QuoteSymbolData = QuoteSymbolData.model_validate(data)
                        current_price: float | None = quote_data.current_price
                        if current_price is not None:
                            logger.info(
                                f"Quote data for {converted_symbol}: Current price = ${current_price}"
                            )
                        logger.debug(f"Quote symbol data: {quote_data.symbol_info}")
                    except ValidationError as e:
                        logger.debug(f"Failed to parse 'qsd' message: {e}")
                    continue

                elif message_type == "quote_completed":
                    try:
                        quote_completed: QuoteCompletedMessage = (
                            QuoteCompletedMessage.model_validate(data)
                        )
                        logger.info(f"Quote setup completed for symbol: {quote_completed.symbol}")
                    except ValidationError as e:
                        logger.debug(f"Failed to parse 'quote_completed' message: {e}")
                    continue

                elif message_type in ("series_loading", "study_loading"):
                    logger.debug(f"{message_type} for real-time data stream")
                    continue

                elif message_type in ("series_completed", "study_completed"):
                    logger.debug(f"{message_type} for real-time data stream")
                    continue

                elif message_type == "series_error":
                    logger.error("Series error received from TradingView")
                    logger.error(f"Error details: {data}")
                    logger.error(
                        "Please check the interval - this timeframe may not be supported for the symbol"
                    )
                    logger.error("Also verify that bars_count is within valid range")
                    if self.connection_service:
                        await self.connection_service.close()
                    raise ValueError(
                        "TradingView series error: Invalid interval or bars count. "
                        "Please check that the timeframe is supported for this symbol "
                        "and that bars_count is within valid range."
                    )

                else:
                    logger.debug(f"Skipping message type '{message_type}': {data}")
                    continue

            except Exception as e:
                # Outer guard: skip unparseable messages (e.g. malformed WebSocket frames)
                logger.debug(f"Skipping unparseable message: {data} - Error: {e}")
                continue

    async def get_historical_ohlcv(
        self,
        exchange_symbol: str,
        interval: str = "1",
        bars_count: int | None = None,
        *,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
    ) -> list[OHLCVBar]:
        """
        Returns a list of historical OHLCV data for a specified symbol.

        Supports two mutually exclusive modes:

        **Count mode** — fetch the most recent N bars:

            bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=100)

        **Range mode** — fetch all bars within an explicit date window:

            bars = await client.get_historical_ohlcv(
                "NASDAQ:AAPL", "1D", start="2024-01-01", end="2024-12-31"
            )

        For large date ranges in range mode, this method automatically splits the request
        into segments and merges the results transparently. No change to the call site is
        required — segmentation is an internal implementation detail.

        Symbols are automatically converted from EXCHANGE-SYMBOL to EXCHANGE:SYMBOL format.

        Args:
            exchange_symbol: The symbol in 'EXCHANGE:SYMBOL' or 'EXCHANGE-SYMBOL' format
                (e.g., 'BINANCE:BTCUSDT' or 'USI-PCC').
            interval: The chart interval (default "1" for 1 minute).
            bars_count: Number of most-recent bars to fetch. Mutually exclusive with
                start/end. Must be a positive integer. No default — must be provided
                explicitly when using count mode.
            start: Start of the date range (inclusive). Accepts a timezone-aware datetime,
                naive datetime (assigned UTC), or ISO 8601 string. Keyword-only.
                Must be provided together with end.
            end: End of the date range (inclusive). Same accepted types as start.
                Keyword-only. Must be provided together with start. Future end dates
                are automatically clamped to the current UTC time.

        Returns:
            A list of OHLCVBar objects sorted by timestamp in ascending order.

        Raises:
            ValueError: If neither bars_count nor start/end is provided; if both are
                provided; if only one of start/end is provided; if bars_count <= 0;
                if start > end; or if the symbol/interval is invalid.
            RangeTooLargeError: If the date range requires more than MAX_SEGMENTS (2000)
                fetch operations. Narrow the range or use a wider interval.
            RuntimeError: If no bars are received from TradingView (count mode).
            NoHistoricalDataError: If no bars are received from TradingView (range mode).
                This is a RuntimeError subclass — existing except RuntimeError callers
                are unaffected.
        """
        # --- Mode dispatch (fail fast before WebSocket) ---
        has_range: bool = start is not None or end is not None
        has_count: bool = bars_count is not None

        if has_range and has_count:
            raise ValueError(
                "Cannot specify both bars_count and start/end. "
                "Use bars_count for count-based queries or start/end for range-based queries."
            )

        if has_count:
            assert bars_count is not None  # mypy narrowing — has_count guarantees non-None
            if bars_count <= 0:
                raise ValueError("bars_count must be a positive integer.")

        if has_range:
            if start is None or end is None:
                raise ValueError("Both start and end must be provided for range-based queries.")

            # Normalize to UTC-aware datetimes (truncated to integer seconds).
            # _normalize_input() calls ensure_utc() for datetime objects (warns if
            # naive) then _to_utc_datetime() for string parsing and second truncation.
            start_dt: datetime = _normalize_input(start)
            end_dt: datetime = _normalize_input(end)

            # Validate range: clamp future end, check start <= end.
            start_dt, end_dt = self._validate_range(start_dt, end_dt)

            if self._needs_segmentation(start_dt, end_dt, interval):
                logger.info(
                    "Range exceeds single-request limit — switching to segmented fetch.",
                    extra={
                        "interval": interval,
                        "start": start_dt.isoformat(),
                        "end": end_dt.isoformat(),
                    },
                )
                service = SegmentedFetchService(
                    client=self,
                    max_bars_per_segment=MAX_BARS_REQUEST,
                )
                return await service.fetch_all(exchange_symbol, interval, start_dt, end_dt)

            # Small range — use single-request path (existing behavior, unchanged).
            return await self._fetch_single_range(
                exchange_symbol, interval, start=start_dt, end=end_dt
            )

        elif has_count:
            assert bars_count is not None  # mypy narrowing
            return await self._fetch_count_mode(exchange_symbol, interval, bars_count=bars_count)

        else:
            raise ValueError("Either bars_count or both start and end must be provided.")

    async def get_quote_data(
        self, exchange_symbol: str, interval: str = "1", bars_count: int = 10
    ) -> AsyncGenerator[QuoteSymbolData, None]:
        """
        Returns an async generator that yields quote data for a specified symbol in real-time.

        This method is useful for symbols that provide quote data (current price, volume, etc.)
        but may not have OHLCV chart data available. It's ideal for getting real-time price updates.
        Symbols are automatically converted from EXCHANGE-SYMBOL to EXCHANGE:SYMBOL format.

        Args:
            exchange_symbol: The symbol in 'EXCHANGE:SYMBOL' or 'EXCHANGE-SYMBOL' format (e.g., 'NASDAQ:AAPL' or 'USI-PCC').
            interval: The interval for the chart (default is "1" for 1 minute).
            bars_count: The number of bars to fetch (default is 10).

        Returns:
            An async generator yielding quote data as QuoteSymbolData objects.

        Raises:
            ValueError: If the symbol format is invalid
            WebSocketException: If connection or streaming fails

        Example:
            >>> async with OHLCV() as client:
            ...     async for quote in client.get_quote_data("NASDAQ:AAPL", interval="5"):
            ...         print(f"Price: ${quote.current_price}")
        """
        await validate_symbols(exchange_symbol)
        symbol_result = convert_symbol_format(exchange_symbol)
        converted_symbol: str = symbol_result.converted_symbol  # type: ignore
        validate_interval(interval)
        await self._prepare_chart_session(converted_symbol, interval, bars_count)

        if self.connection_service is None:
            raise RuntimeError("Services not properly initialized")

        async for data in self.connection_service.get_data_stream():
            try:
                message: WebSocketMessage = WebSocketMessage.model_validate(data)
                message_type: str = message.message_type

                if message_type == "qsd":
                    try:
                        quote_data: QuoteSymbolData = QuoteSymbolData.model_validate(data)
                        yield quote_data
                    except ValidationError as e:
                        logger.debug(f"Failed to parse 'qsd' message: {e}")
                        continue

                elif message_type == "quote_completed":
                    try:
                        quote_completed: QuoteCompletedMessage = (
                            QuoteCompletedMessage.model_validate(data)
                        )
                        logger.info(f"Quote setup completed for symbol: {quote_completed.symbol}")
                    except ValidationError as e:
                        logger.debug(f"Failed to parse 'quote_completed' message: {e}")
                    continue

                elif message_type in (
                    "series_loading",
                    "study_loading",
                    "series_completed",
                    "study_completed",
                ):
                    logger.debug(f"{message_type} for quote data stream")
                    continue

                elif message_type == "series_error":
                    logger.error("Series error received from TradingView during quote data stream")
                    logger.error(f"Error details: {data}")
                    logger.error(
                        "Please check the interval - this timeframe may not be supported for the symbol"
                    )
                    logger.error("Also verify that bars_count is within valid range")
                    if self.connection_service:
                        await self.connection_service.close()
                    raise ValueError(
                        "TradingView series error: Invalid interval or bars count. "
                        "Please check that the timeframe is supported for this symbol "
                        "and that bars_count is within valid range."
                    )

                else:
                    logger.debug(f"Skipping message type '{message_type}' in quote stream")
                    continue

            except Exception as e:
                # Outer guard: skip unparseable messages (e.g. malformed WebSocket frames)
                logger.debug(f"Skipping unparseable message in quote stream: {data} - Error: {e}")
                continue

    async def get_ohlcv_raw(
        self, exchange_symbol: str, interval: str = "1", bars_count: int = 10
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Returns an async generator that yields raw OHLC data for a specified symbol in real-time.

        This method provides the raw JSON data from TradingView for debugging purposes.
        Use this when you need to inspect the raw message format or implement custom parsing.
        Symbols are automatically converted from EXCHANGE-SYMBOL to EXCHANGE:SYMBOL format.

        Args:
            exchange_symbol: The symbol in 'EXCHANGE:SYMBOL' or 'EXCHANGE-SYMBOL' format.
            interval: The interval for the chart (default is "1" for 1 minute).
            bars_count: The number of bars to fetch (default is 10).

        Returns:
            An async generator yielding raw OHLC data as JSON dictionary objects.

        Raises:
            ValueError: If the symbol format is invalid
            WebSocketException: If connection or streaming fails

        Example:
            >>> async with OHLCV() as client:
            ...     async for raw_data in client.get_ohlcv_raw("BINANCE:BTCUSDT", interval="5"):
            ...         print(f"Raw message: {raw_data}")
        """
        await validate_symbols(exchange_symbol)
        symbol_result = convert_symbol_format(exchange_symbol)
        converted_symbol: str = symbol_result.converted_symbol  # type: ignore
        validate_interval(interval)
        await self._prepare_chart_session(converted_symbol, interval, bars_count)

        if self.connection_service is None:
            raise RuntimeError("Services not properly initialized")

        async for data in self.connection_service.get_data_stream():
            yield data

    async def get_latest_trade_info(
        self, exchange_symbol: list[str]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Returns summary information about multiple symbols including last changes,
        change percentage, and last trade time.

        This method allows you to monitor multiple symbols simultaneously and get
        comprehensive trading information for each. All symbols are automatically
        converted from EXCHANGE-SYMBOL to EXCHANGE:SYMBOL format.

        Args:
            exchange_symbol: A list of symbols in 'EXCHANGE:SYMBOL' or 'EXCHANGE-SYMBOL' format.

        Returns:
            An async generator yielding summary information as JSON dictionary objects.

        Raises:
            ValueError: If any symbol format is invalid
            WebSocketException: If connection or streaming fails

        Example:
            >>> symbols = ["BINANCE:BTCUSDT", "NASDAQ:AAPL", "FOREX:EURUSD"]
            >>> async with OHLCV() as client:
            ...     async for trade_info in client.get_latest_trade_info(symbols):
            ...         print(f"Trade info: {trade_info}")
        """
        await validate_symbols(exchange_symbol)
        symbol_results = convert_symbol_format(exchange_symbol)
        converted_symbols = [result.converted_symbol for result in symbol_results]  # type: ignore
        await self._setup_services()

        if not self.connection_service or not self.message_service:
            raise RuntimeError("Services not properly initialized")

        quote_session: str = self.message_service.generate_session(prefix="qs_")
        chart_session: str = self.message_service.generate_session(prefix="cs_")
        logger.debug(f"Sessions: quote={quote_session}, chart={chart_session}")

        send_message_func = self.message_service.get_send_message_callable()
        await self.connection_service.initialize_sessions(
            quote_session, chart_session, send_message_func
        )
        await self.connection_service.add_multiple_symbols_to_sessions(
            quote_session, converted_symbols, send_message_func
        )

        async for data in self.connection_service.get_data_stream():
            yield data
