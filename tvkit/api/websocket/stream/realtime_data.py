"""Module providing async functions which return async generators containing trades realtime data."""

import asyncio
import json
import logging
import re
import secrets
import signal
import string
import types
from typing import Any, AsyncGenerator, List, Optional

from websockets import ClientConnection
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from tvkit.api.utils import validate_symbols
from tvkit.api.websocket.stream.models.ohlcv import (
    OHLCVBar,
    OHLCVResponse,
    QuoteCompletedMessage,
    QuoteSymbolData,
    TimescaleUpdateResponse,
    WebSocketMessage,
)

# Models for WebSocket connection and request headers
from tvkit.api.websocket.stream.models.realtime import (
    ExtraRequestHeader,
    WebSocketConnection,
)

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class RealTimeData:
    """
    A real-time data streaming client for TradingView WebSocket API.

    This class provides async generators for streaming live market data including
    OHLCV bars, quote data, and trade information from TradingView.
    """

    def __init__(self) -> None:
        """
        Initializes the RealTimeData class, setting up WebSocket connection parameters
        and request headers for TradingView data streaming.
        """
        self.ws_url: str = "wss://data.tradingview.com/socket.io/websocket?from=screener%2F"
        self.ws: ClientConnection

    async def __aenter__(self) -> "RealTimeData":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[types.TracebackType]
    ) -> None:
        """Async context manager exit."""
        if hasattr(self, 'ws') and self.ws:
            await self.ws.close()

    # ========================================
    # PRIVATE METHODS - Internal Implementation
    # ========================================

    async def _connect(self) -> None:
        """
        Establishes the WebSocket connection.

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
                user_agent="Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"
            )

            ws_config: WebSocketConnection = WebSocketConnection(
                uri=self.ws_url,
                additional_headers=request_header,
                compression="deflate",
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )

            self.ws: ClientConnection = await connect(**ws_config.model_dump())

            logging.info("WebSocket connection established successfully")
        except Exception as e:
            logging.error("Failed to establish WebSocket connection: %s", e)
            raise

    async def _initialize_sessions(self, quote_session: str, chart_session: str) -> None:
        """
        Initializes the WebSocket sessions for quotes and charts.

        Args:
            quote_session: The quote session identifier
            chart_session: The chart session identifier
        """
        await self.send_message("set_auth_token", ["unauthorized_user_token"])
        await self.send_message("set_locale", ["en", "US"])
        await self.send_message("chart_create_session", [chart_session, ""])
        await self.send_message("quote_create_session", [quote_session])
        await self.send_message("quote_set_fields", [quote_session, *self._get_quote_fields()])
        await self.send_message("quote_hibernate_all", [quote_session])

    def _get_quote_fields(self) -> list[str]:
        """
        Returns the fields to be set for the quote session.

        Returns:
            A list of fields for the quote session.
        """
        return [
            "ch", "chp", "current_session", "description", "local_description",
            "language", "exchange", "fractional", "is_tradable", "lp",
            "lp_time", "minmov", "minmove2", "original_name", "pricescale",
            "pro_name", "short_name", "type", "update_mode", "volume",
            "currency_code", "rchp", "rtc"
        ]

    async def _add_symbol_to_sessions(
        self,
        quote_session: str,
        chart_session: str,
        exchange_symbol: str
    ) -> None:
        """
        Adds the specified symbol to the quote and chart sessions.

        Args:
            quote_session: The quote session identifier
            chart_session: The chart session identifier
            exchange_symbol: The symbol in 'EXCHANGE:SYMBOL' format
        """
        resolve_symbol: str = json.dumps({"adjustment": "splits", "symbol": exchange_symbol})
        await self.send_message("quote_add_symbols", [quote_session, f"={resolve_symbol}"])
        await self.send_message("resolve_symbol", [chart_session, "sds_sym_1", f"={resolve_symbol}"])
        await self.send_message("create_series", [chart_session, "sds_1", "s1", "sds_sym_1", "1", 10, ""])
        await self.send_message("quote_fast_symbols", [quote_session, exchange_symbol])
        await self.send_message("create_study", [chart_session, "st1", "st1", "sds_1",
                            "Volume@tv-basicstudies-246", {"length": 20, "col_prev_close": "false"}])
        await self.send_message("quote_hibernate_all", [quote_session])

    async def _add_multiple_symbols_to_sessions(
        self,
        quote_session: str,
        exchange_symbols: List[str]
    ) -> None:
        """
        Adds multiple symbols to the quote session.

        Args:
            quote_session: The quote session identifier
            exchange_symbols: List of symbols in 'EXCHANGE:SYMBOL' format
        """
        resolve_symbol: str = json.dumps({
            "adjustment": "splits",
            "currency-id": "USD",
            "session": "regular",
            "symbol": exchange_symbols[0]
        })
        await self.send_message("quote_add_symbols", [quote_session, f"={resolve_symbol}"])
        await self.send_message("quote_fast_symbols", [quote_session, f"={resolve_symbol}"])

        await self.send_message("quote_add_symbols", [quote_session] + exchange_symbols)
        await self.send_message("quote_fast_symbols", [quote_session] + exchange_symbols)

    async def _get_data(self) -> AsyncGenerator[dict[str, Any], None]:
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
                        result = message.decode('utf-8')
                    else:
                        # Handle memoryview and other buffer types
                        result = bytes(message).decode('utf-8')

                    # Check if the result is a heartbeat or actual data
                    if re.match(r"~m~\d+~m~~h~\d+$", result):
                        logging.debug(f"Received heartbeat: {result}")
                        await self.ws.send(result)  # Echo back the heartbeat
                    else:
                        split_result: list[str] = [x for x in re.split(r'~m~\d+~m~', result) if x]
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
            if hasattr(self, 'ws') and self.ws:
                await self.ws.close()

    # ========================================
    # UTILITY METHODS - Message Construction
    # ========================================

    def generate_session(self, prefix: str) -> str:
        """
        Generates a random session identifier.

        Args:
            prefix: The prefix to prepend to the random string.

        Returns:
            A session identifier consisting of the prefix and a random string.
        """
        random_string: str = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(12))
        return prefix + random_string

    def prepend_header(self, message: str) -> str:
        """
        Prepends the message with a header indicating its length.

        Args:
            message: The message to be sent.

        Returns:
            The message prefixed with its length.
        """
        message_length: int = len(message)
        return f"~m~{message_length}~m~{message}"

    def construct_message(self, func: str, param_list: list[Any]) -> str:
        """
        Constructs a message in JSON format.

        Args:
            func: The function name to be called.
            param_list: The list of parameters for the function.

        Returns:
            The constructed JSON message.
        """
        return json.dumps({"m": func, "p": param_list}, separators=(',', ':'))

    def create_message(self, func: str, param_list: list[Any]) -> str:
        """
        Creates a complete message with a header and a JSON body.

        Args:
            func: The function name to be called.
            param_list: The list of parameters for the function.

        Returns:
            The complete message ready to be sent.
        """
        return self.prepend_header(self.construct_message(func, param_list))

    async def send_message(self, func: str, args: list[Any]) -> None:
        """
        Sends a message to the WebSocket server.

        Args:
            func: The function name to be called.
            args: The arguments for the function.

        Raises:
            RuntimeError: If WebSocket connection is not established
            ConnectionClosed: If WebSocket connection is closed
            WebSocketException: If sending fails
        """
        if not self.ws:
            raise RuntimeError("WebSocket connection not established. Call _connect() first.")

        message: str = self.create_message(func, args)
        logging.debug("Sending message: %s", message)

        try:
            await self.ws.send(message)
        except ConnectionClosed as e:
            logging.error("WebSocket connection closed while sending message: %s", e)
            raise
        except WebSocketException as e:
            logging.error("Failed to send message: %s", e)
            raise

    # ========================================
    # PUBLIC API METHODS - Main Interface
    # ========================================

    async def get_ohlcv(self, exchange_symbol: str) -> AsyncGenerator[OHLCVBar, None]:
        """
        Returns an async generator that yields OHLC data for a specified symbol in real-time.

        This is the primary method for streaming structured OHLCV data from TradingView.
        Each yielded bar contains open, high, low, close, volume, and timestamp information.

        Args:
            exchange_symbol: The symbol in the format 'EXCHANGE:SYMBOL' (e.g., 'BINANCE:BTCUSDT').

        Returns:
            An async generator yielding structured OHLCV data as OHLCVBar objects.

        Raises:
            ValueError: If the symbol format is invalid
            WebSocketException: If connection or streaming fails

        Example:
            >>> async with RealTimeData() as client:
            ...     async for bar in client.get_ohlcv("BINANCE:BTCUSDT"):
            ...         print(f"Close: ${bar.close}, Volume: {bar.volume}")
        """
        await validate_symbols(exchange_symbol)
        await self._connect()

        quote_session: str = self.generate_session(prefix="qs_")
        chart_session: str = self.generate_session(prefix="cs_")
        logging.info(f"Quote session generated: {quote_session}, Chart session generated: {chart_session}")

        await self._initialize_sessions(quote_session, chart_session)
        await self._add_symbol_to_sessions(quote_session, chart_session, exchange_symbol)

        async for data in self._get_data():
            # Try to parse different message types
            try:
                # Parse as generic WebSocket message first to check type
                message: WebSocketMessage = WebSocketMessage.model_validate(data)
                message_type: str = message.message_type

                logging.debug(f"Received message type: {message_type}")

                if message_type == "du":
                    # Try to parse as OHLCV data update
                    try:
                        ohlcv_response: OHLCVResponse = OHLCVResponse.model_validate(data)
                        # Yield all OHLCV bars from the response
                        for ohlcv_bar in ohlcv_response.ohlcv_bars:
                            yield ohlcv_bar
                    except Exception as e:
                        logging.debug(f"Failed to parse 'du' message as OHLCV: {e}")
                        continue

                elif message_type == "timescale_update":
                    # Try to parse as timescale update (historical OHLCV data)
                    try:
                        timescale_response: TimescaleUpdateResponse = TimescaleUpdateResponse.model_validate(data)
                        # Yield all OHLCV bars from the response
                        logging.info(f"Received {len(timescale_response.ohlcv_bars)} OHLCV bars from timescale update")
                        for ohlcv_bar in timescale_response.ohlcv_bars:
                            yield ohlcv_bar
                    except Exception as e:
                        logging.debug(f"Failed to parse 'timescale_update' message as OHLCV: {e}")
                        continue

                elif message_type == "qsd":
                    # Quote symbol data - contains current price info
                    try:
                        quote_data: QuoteSymbolData = QuoteSymbolData.model_validate(data)
                        current_price: Optional[float] = quote_data.current_price
                        if current_price is not None:
                            logging.info(f"Quote data for {exchange_symbol}: Current price = ${current_price}")
                        logging.debug(f"Quote symbol data: {quote_data.symbol_info}")
                    except Exception as e:
                        logging.debug(f"Failed to parse 'qsd' message: {e}")
                    continue

                elif message_type == "quote_completed":
                    # Quote setup completed
                    try:
                        quote_completed: QuoteCompletedMessage = QuoteCompletedMessage.model_validate(data)
                        logging.info(f"Quote setup completed for symbol: {quote_completed.symbol}")
                    except Exception as e:
                        logging.debug(f"Failed to parse 'quote_completed' message: {e}")
                    continue

                else:
                    # Other message types (heartbeats, etc.)
                    logging.debug(f"Skipping message type '{message_type}': {data}")
                    continue

            except Exception as e:
                # If we can't parse the message at all, skip it
                logging.debug(f"Skipping unparseable message: {data} - Error: {e}")
                continue

    async def get_quote_data(self, exchange_symbol: str) -> AsyncGenerator[QuoteSymbolData, None]:
        """
        Returns an async generator that yields quote data for a specified symbol in real-time.

        This method is useful for symbols that provide quote data (current price, volume, etc.)
        but may not have OHLCV chart data available. It's ideal for getting real-time price updates.

        Args:
            exchange_symbol: The symbol in the format 'EXCHANGE:SYMBOL' (e.g., 'NASDAQ:AAPL').

        Returns:
            An async generator yielding quote data as QuoteSymbolData objects.

        Raises:
            ValueError: If the symbol format is invalid
            WebSocketException: If connection or streaming fails

        Example:
            >>> async with RealTimeData() as client:
            ...     async for quote in client.get_quote_data("NASDAQ:AAPL"):
            ...         print(f"Price: ${quote.current_price}")
        """
        await validate_symbols(exchange_symbol)
        await self._connect()

        quote_session: str = self.generate_session(prefix="qs_")
        chart_session: str = self.generate_session(prefix="cs_")
        logging.info(f"Quote session generated: {quote_session}, Chart session generated: {chart_session}")

        await self._initialize_sessions(quote_session, chart_session)
        await self._add_symbol_to_sessions(quote_session, chart_session, exchange_symbol)

        async for data in self._get_data():
            try:
                # Parse as generic WebSocket message first to check type
                message: WebSocketMessage = WebSocketMessage.model_validate(data)
                message_type: str = message.message_type

                if message_type == "qsd":
                    # Quote symbol data - contains current price info
                    try:
                        quote_data: QuoteSymbolData = QuoteSymbolData.model_validate(data)
                        yield quote_data
                    except Exception as e:
                        logging.debug(f"Failed to parse 'qsd' message: {e}")
                        continue

                elif message_type == "quote_completed":
                    # Quote setup completed - log but don't yield
                    try:
                        quote_completed: QuoteCompletedMessage = QuoteCompletedMessage.model_validate(data)
                        logging.info(f"Quote setup completed for symbol: {quote_completed.symbol}")
                    except Exception as e:
                        logging.debug(f"Failed to parse 'quote_completed' message: {e}")
                    continue

                else:
                    # Other message types - skip
                    logging.debug(f"Skipping message type '{message_type}' in quote stream")
                    continue

            except Exception as e:
                # If we can't parse the message at all, skip it
                logging.debug(f"Skipping unparseable message in quote stream: {data} - Error: {e}")
                continue

    async def get_ohlcv_raw(self, exchange_symbol: str) -> AsyncGenerator[dict[str, Any], None]:
        """
        Returns an async generator that yields raw OHLC data for a specified symbol in real-time.

        This method provides the raw JSON data from TradingView for debugging purposes.
        Use this when you need to inspect the raw message format or implement custom parsing.

        Args:
            exchange_symbol: The symbol in the format 'EXCHANGE:SYMBOL'.

        Returns:
            An async generator yielding raw OHLC data as JSON dictionary objects.

        Raises:
            ValueError: If the symbol format is invalid
            WebSocketException: If connection or streaming fails

        Example:
            >>> async with RealTimeData() as client:
            ...     async for raw_data in client.get_ohlcv_raw("BINANCE:BTCUSDT"):
            ...         print(f"Raw message: {raw_data}")
        """
        await validate_symbols(exchange_symbol)
        await self._connect()

        quote_session: str = self.generate_session(prefix="qs_")
        chart_session: str = self.generate_session(prefix="cs_")
        logging.info(f"Quote session generated: {quote_session}, Chart session generated: {chart_session}")

        await self._initialize_sessions(quote_session, chart_session)
        await self._add_symbol_to_sessions(quote_session, chart_session, exchange_symbol)

        async for data in self._get_data():
            yield data

    async def get_latest_trade_info(self, exchange_symbol: List[str]) -> AsyncGenerator[dict[str, Any], None]:
        """
        Returns summary information about multiple symbols including last changes,
        change percentage, and last trade time.

        This method allows you to monitor multiple symbols simultaneously and get
        comprehensive trading information for each.

        Args:
            exchange_symbol: A list of symbols in the format 'EXCHANGE:SYMBOL'.

        Returns:
            An async generator yielding summary information as JSON dictionary objects.

        Raises:
            ValueError: If any symbol format is invalid
            WebSocketException: If connection or streaming fails

        Example:
            >>> symbols = ["BINANCE:BTCUSDT", "NASDAQ:AAPL", "FOREX:EURUSD"]
            >>> async with RealTimeData() as client:
            ...     async for trade_info in client.get_latest_trade_info(symbols):
            ...         print(f"Trade info: {trade_info}")
        """
        await validate_symbols(exchange_symbol)
        await self._connect()

        quote_session: str = self.generate_session(prefix="qs_")
        chart_session: str = self.generate_session(prefix="cs_")
        logging.info(f"Session generated: {quote_session}, Chart session generated: {chart_session}")

        await self._initialize_sessions(quote_session, chart_session)
        await self._add_multiple_symbols_to_sessions(quote_session, exchange_symbol)

        async for data in self._get_data():
            yield data


# Signal handler for keyboard interrupt
def signal_handler(sig: int, frame: Optional[types.FrameType]) -> None:
    """
    Handles keyboard interrupt signals to gracefully close the WebSocket connection.

    Args:
        sig: The signal number.
        frame: The current stack frame.
    """
    logging.info("Keyboard interrupt received. Exiting...")
    exit(0)


# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)


# Example Usage
async def main():
    """
    Example usage of the RealTimeData class with async patterns.
    """
    async with RealTimeData() as real_time_data:
        # exchange_symbol = ["BINANCE:ETHUSDT", "FXOPEN:XAUUSD"]
        exchange_symbol = ["TFEX:S50U2025"]

        # Get latest trade info
        # async for packet in real_time_data.get_latest_trade_info(exchange_symbol=exchange_symbol):
        #     print('-' * 50)
        #     print(packet)
        ohlcv_count = 0

        # Try to get structured OHLCV data first
        print("Attempting to get structured OHLCV data...")
        async for ohlcv_bar in real_time_data.get_ohlcv(exchange_symbol=exchange_symbol[0]):
            ohlcv_count += 1
            print('-' * 50)
            print(f"OHLCV Bar #{ohlcv_count}:")
            print(f"Timestamp: {ohlcv_bar.timestamp}")
            print(f"Open: {ohlcv_bar.open}")
            print(f"High: {ohlcv_bar.high}")
            print(f"Low: {ohlcv_bar.low}")
            print(f"Close: {ohlcv_bar.close}")
            print(f"Volume: {ohlcv_bar.volume}")

            # Stop after getting a few bars for demo
            if ohlcv_count >= 3:
                break

        # # If no OHLCV data, try getting quote data instead
        # if ohlcv_count == 0:
        #     print("\nNo OHLCV data received. Trying quote data...")
        #     quote_count = 0
        #     async for quote_data in real_time_data.get_quote_data(exchange_symbol=exchange_symbol[0]):
        #         quote_count += 1
        #         print('-' * 50)
        #         print(f"Quote Data #{quote_count}:")
        #         print(f"Session ID: {quote_data.session_id}")
        #         print(f"Current Price: ${quote_data.current_price}")
        #         print(f"Symbol Info: {quote_data.symbol_info}")

        #         # Stop after getting a few quotes for demo
        #         if quote_count >= 3:
        #             break


if __name__ == "__main__":
    asyncio.run(main())
