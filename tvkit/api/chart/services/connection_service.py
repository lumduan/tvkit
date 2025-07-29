"""Connection service for managing WebSocket connections and sessions."""

import json
import logging
from typing import Any, AsyncGenerator, Awaitable, Callable, List

from websockets import ClientConnection
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from tvkit.api.chart.models.realtime import (
    ExtraRequestHeader,
    WebSocketConnection,
)


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
        self.ws: ClientConnection

    async def connect(self) -> None:
        """
        Establishes the WebSocket connection to TradingView.

        Raises:
            WebSocketException: If connection fails
        """
        try:
            logging.info("Establishing WebSocket connection to %s", self.ws_url)

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

            logging.info("WebSocket connection established successfully")
        except Exception as e:
            logging.error("Failed to establish WebSocket connection: %s", e)
            raise

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if hasattr(self, "ws") and self.ws:
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
        await send_message_func(
            "quote_set_fields", [quote_session, *self._get_quote_fields()]
        )
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

    async def add_symbol_to_sessions(
        self,
        quote_session: str,
        chart_session: str,
        exchange_symbol: str,
        timeframe: str,
        bars_count: int,
        send_message_func: Callable[[str, list[Any]], Awaitable[None]],
    ) -> None:
        """
        Adds the specified symbol to the quote and chart sessions.

        Args:
            quote_session: The quote session identifier
            chart_session: The chart session identifier
            exchange_symbol: The symbol in 'EXCHANGE:SYMBOL' format
            timeframe: The timeframe for the chart (default is "1")
            bars_count: Number of bars to fetch for the chart
            send_message_func: Function to send messages through the WebSocket
        """
        resolve_symbol: str = json.dumps(
            {"adjustment": "splits", "symbol": exchange_symbol}
        )
        await send_message_func(
            "quote_add_symbols", [quote_session, f"={resolve_symbol}"]
        )
        await send_message_func(
            "resolve_symbol", [chart_session, "sds_sym_1", f"={resolve_symbol}"]
        )
        await send_message_func(
            "create_series",
            [chart_session, "sds_1", "s1", "sds_sym_1", timeframe, bars_count, ""],
        )
        await send_message_func("quote_fast_symbols", [quote_session, exchange_symbol])
        await send_message_func(
            "create_study",
            [
                chart_session,
                "st1",
                "st1",
                "sds_1",
                "Volume@tv-basicstudies-246",
                {"length": 20, "col_prev_close": "false"},
            ],
        )
        await send_message_func("quote_hibernate_all", [quote_session])

    async def add_multiple_symbols_to_sessions(
        self,
        quote_session: str,
        exchange_symbols: List[str],
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
        await send_message_func(
            "quote_add_symbols", [quote_session, f"={resolve_symbol}"]
        )
        await send_message_func(
            "quote_fast_symbols", [quote_session, f"={resolve_symbol}"]
        )

        await send_message_func("quote_add_symbols", [quote_session] + exchange_symbols)
        await send_message_func(
            "quote_fast_symbols", [quote_session] + exchange_symbols
        )

    async def get_data_stream(self) -> AsyncGenerator[dict[str, Any], None]:
        """
        Continuously receives data from the TradingView server via the WebSocket connection.

        Yields:
            Parsed JSON data received from the server.

        Raises:
            RuntimeError: If WebSocket connection is not established
        """
        if not self.ws:
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

                    # Check if the result is a heartbeat or actual data
                    import re

                    if re.match(r"~m~\d+~m~~h~\d+$", result):
                        logging.debug(f"Received heartbeat: {result}")
                        await self.ws.send(result)  # Echo back the heartbeat
                    else:
                        split_result: list[str] = [
                            x for x in re.split(r"~m~\d+~m~", result) if x
                        ]
                        for item in split_result:
                            if item:
                                try:
                                    yield json.loads(item)  # Yield parsed JSON data
                                except json.JSONDecodeError:
                                    logging.warning(f"Failed to parse JSON: {item}")
                                    continue

                except ConnectionClosed:
                    logging.error("WebSocket connection closed.")
                    break
                except WebSocketException as e:
                    logging.error(f"WebSocket error occurred: {e}")
                    break
                except Exception as e:
                    logging.error(f"An unexpected error occurred: {e}")
                    break
        finally:
            await self.close()
