"""Connection service for managing WebSocket connections and sessions."""

import json
import logging
import re
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

from websockets import ClientConnection
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from tvkit.api.chart.models.realtime import (
    ExtraRequestHeader,
    WebSocketConnection,
)

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


class ConnectionService:
    """
    Service for managing WebSocket connections and TradingView sessions.

    This service handles the low-level WebSocket connection management,
    session initialization, and symbol subscription for TradingView data streams.
    """

    def __init__(self, ws_url: str) -> None:
        """
        Initialize the connection service.

        Args:
            ws_url: The WebSocket URL for TradingView data streaming
        """
        self.ws_url: str = ws_url
        self.ws: ClientConnection | None = None

    async def connect(self) -> None:
        """
        Establishes the WebSocket connection to TradingView.

        Raises:
            WebSocketException: If connection fails
        """
        try:
            logger.info("Establishing WebSocket connection to %s", self.ws_url)

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
            )

            self.ws = await connect(**ws_config.model_dump())

            logger.info("WebSocket connection established successfully")
        except Exception as e:
            logger.error("Failed to establish WebSocket connection: %s", e)
            raise

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self.ws is not None:
            await self.ws.close()

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
        await send_message_func("set_auth_token", ["unauthorized_user_token"])
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
                and is ignored by TradingView once modify_series applies the range.

        Returns:
            List of 7 elements:
            [chart_session, "sds_1", "s1", "sds_sym_1", timeframe, bars_count, ""]

        Example:
            >>> svc._create_series_args("cs_abc123", "1D", 100)
            ["cs_abc123", "sds_1", "s1", "sds_sym_1", "1D", 100, ""]
        """
        # tvkit currently supports a single series per chart session.
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

    async def get_data_stream(self) -> AsyncGenerator[dict[str, Any], None]:
        """
        Continuously receives data from the TradingView server via the WebSocket connection.

        Yields:
            Parsed JSON data received from the server.

        Raises:
            RuntimeError: If WebSocket connection is not established
        """
        if self.ws is None:
            raise RuntimeError("WebSocket connection not established")

        try:
            async for message in self.ws:
                try:
                    # Convert message to string - WebSocket messages can be str, bytes, or memoryview
                    if isinstance(message, str):
                        result: str = message
                    elif isinstance(message, bytes):
                        result = message.decode("utf-8")
                    else:
                        # Handle memoryview and other buffer types
                        result = bytes(message).decode("utf-8")

                    if _HEARTBEAT_RE.match(result):
                        logger.debug("Received heartbeat: %s", result)
                        try:
                            await self.ws.send(result)  # Echo back the heartbeat
                        except ConnectionClosed:
                            logger.debug("Connection closed while echoing heartbeat")
                            break
                    else:
                        split_result: list[str] = [x for x in _FRAME_SPLIT_RE.split(result) if x]
                        for item in split_result:
                            if item:
                                try:
                                    yield json.loads(item)  # Yield parsed JSON data
                                except json.JSONDecodeError:
                                    logger.warning("Failed to parse JSON: %s", item)
                                    continue

                except ConnectionClosed:
                    logger.error("WebSocket connection closed.")
                    break
                except WebSocketException as e:
                    logger.error("WebSocket error occurred: %s", e)
                    break
                except Exception as e:
                    logger.error("An unexpected error occurred: %s", e)
                    break
        finally:
            await self.close()
