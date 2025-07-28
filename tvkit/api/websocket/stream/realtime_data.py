"""Module providing async functions which return async generators containing trades realtime data."""

import asyncio
import json
import logging
import re
import secrets
import signal
import string
import time
from typing import AsyncGenerator, List, Optional, Union

import httpx  # Modern async HTTP client
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from tvkit.api import websocket
from tvkit.api.websocket.stream.models.realtime import (
    ExtraRequestHeader,
    WebSocketConnection,
)

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class RealTimeData:
    def __init__(self):
        """
        Initializes the RealTimeData class, setting up WebSocket connection parameters
        and request headers for TradingView data streaming.
        """

        self.ws_url: str = "wss://data.tradingview.com/socket.io/websocket?from=screener%2F"
        self.validate_url: str = "https://scanner.tradingview.com/symbol?symbol={exchange}%3A{symbol}&fields=market&no_404=false" # URL to validate symbols
        self.ws: Optional[object] = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.ws:
            await self.ws.close()

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
                user_agent="Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/
            )

            ws_config: WebSocketConnection = WebSocketConnection(
                uri=self.ws_url,
                extra_headers=request_header,
                compression="deflate",
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )

            self.ws = await connect(**ws_config.model_dump())

            logging.info("WebSocket connection established successfully")
        except Exception as e:
            logging.error("Failed to establish WebSocket connection: %s", e)
            raise

    async def validate_symbols(self, exchange_symbol: Union[str, List[str]]) -> bool:
        """
        Validates the provided exchange symbols using async HTTP requests.

        Args:
            exchange_symbol (str or list): A single symbol or a list of symbols
                                            in the format 'EXCHANGE:SYMBOL'.

        Raises:
            ValueError: If the symbol format is invalid or if the symbol is not valid.

        Returns:
            bool: True if all symbols are valid.
        """
        if not exchange_symbol:
            raise ValueError("exchange_symbol could not be empty")

        if isinstance(exchange_symbol, str):
            exchange_symbol = [exchange_symbol]

        async with httpx.AsyncClient() as client:
            for item in exchange_symbol:
                if len(item.split(':')) != 2:
                    raise ValueError(f"Invalid symbol format '{item}'. Must be like 'BINANCE:BTCUSDT'")

                exchange, symbol = item.split(':')
                retries = 3
                for attempt in range(retries):
                    try:
                        response = await client.get(
                            self.validate_url.format(exchange=exchange, symbol=symbol),
                            timeout=5.0
                        )
                        response.raise_for_status()
                        break  # Exit the retry loop on success

                    except httpx.RequestError as e:
                        logging.warning("Attempt %d failed to validate exchange:symbol '%s': %s",
                                      attempt + 1, item, e)

                        if attempt < retries - 1:
                            await asyncio.sleep(1)  # Wait before retrying
                        else:
                            raise ValueError(f"Invalid exchange:symbol '{item}' after {retries} attempts") from e

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 404:
                            raise ValueError(f"Invalid exchange:symbol '{item}' - symbol not found") from e

                        logging.warning("HTTP error %d for exchange:symbol '%s': %s",
                                      e.response.status_code, item, e)

                        if attempt < retries - 1:
                            await asyncio.sleep(1)
                        else:
                            raise ValueError(f"Invalid exchange:symbol '{item}' after {retries} attempts") from e
        return True


    def generate_session(self, prefix: str) -> str:
        """
        Generates a random session identifier.

        Args:
            prefix (str): The prefix to prepend to the random string.

        Returns:
            str: A session identifier consisting of the prefix and a random string.
        """
        random_string = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(12))
        return prefix + random_string


    def prepend_header(self, message: str) -> str:
        """
        Prepends the message with a header indicating its length.

        Args:
            message (str): The message to be sent.

        Returns:
            str: The message prefixed with its length.
        """
        message_length = len(message)
        return f"~m~{message_length}~m~{message}"


    def construct_message(self, func: str, param_list: list) -> str:
        """
        Constructs a message in JSON format.

        Args:
            func (str): The function name to be called.
            param_list (list): The list of parameters for the function.

        Returns:
            str: The constructed JSON message.
        """
        return json.dumps({"m": func, "p": param_list}, separators=(',', ':'))

    def create_message(self, func: str, param_list: list) -> str:
        """
        Creates a complete message with a header and a JSON body.

        Args:
            func (str): The function name to be called.
            param_list (list): The list of parameters for the function.

        Returns:
            str: The complete message ready to be sent.
        """
        return self.prepend_header(self.construct_message(func, param_list))

    async def send_message(self, func: str, args: list) -> None:
        """
        Sends a message to the WebSocket server.

        Args:
            func (str): The function name to be called.
            args (list): The arguments for the function.

        Raises:
            ConnectionClosed: If WebSocket connection is closed
            WebSocketException: If sending fails
        """
        if not self.ws:
            raise RuntimeError("WebSocket connection not established. Call _connect() first.")

        message = self.create_message(func, args)
        logging.debug("Sending message: %s", message)

        try:
            await self.ws.send(message)
        except ConnectionClosed as e:
            logging.error("WebSocket connection closed while sending message: %s", e)
            raise
        except WebSocketException as e:
            logging.error("Failed to send message: %s", e)
            raise


    async def get_ohlcv(self, exchange_symbol: str) -> AsyncGenerator[dict, None]:
        """
        Returns an async generator that yields OHLC data for a specified symbol in real-time.

        Args:
            exchange_symbol (str): The symbol in the format 'EXCHANGE:SYMBOL'.

        Returns:
            AsyncGenerator[dict, None]: An async generator yielding OHLC data as JSON objects.
        """
        await self.validate_symbols(exchange_symbol)
        await self._connect()

        quote_session = self.generate_session(prefix="qs_")
        chart_session = self.generate_session(prefix="cs_")
        logging.info(f"Quote session generated: {quote_session}, Chart session generated: {chart_session}")

        await self._initialize_sessions(quote_session, chart_session)
        await self._add_symbol_to_sessions(quote_session, chart_session, exchange_symbol)

        async for data in self._get_data():
            yield data

    async def _initialize_sessions(self, quote_session: str, chart_session: str) -> None:
        """
        Initializes the WebSocket sessions for quotes and charts.
        """
        await self.send_message("set_auth_token", ["unauthorized_user_token"])
        await self.send_message("set_locale", ["en", "US"])
        await self.send_message("chart_create_session", [chart_session, ""])
        await self.send_message("quote_create_session", [quote_session])
        await self.send_message("quote_set_fields", [quote_session, *self._get_quote_fields()])
        await self.send_message("quote_hibernate_all", [quote_session])

    def _get_quote_fields(self):
        """
        Returns the fields to be set for the quote session.

        Returns:
            list: A list of fields for the quote session.
        """
        return ["ch", "chp", "current_session", "description", "local_description",
                "language", "exchange", "fractional", "is_tradable", "lp",
                "lp_time", "minmov", "minmove2", "original_name", "pricescale",
                "pro_name", "short_name", "type", "update_mode", "volume",
                "currency_code", "rchp", "rtc"]

    async def _add_symbol_to_sessions(self, quote_session: str, chart_session: str, exchange_symbol: str) -> None:
        """
        Adds the specified symbol to the quote and chart sessions.
        """
        resolve_symbol = json.dumps({"adjustment": "splits", "symbol": exchange_symbol})
        await self.send_message("quote_add_symbols", [quote_session, f"={resolve_symbol}"])
        await self.send_message("resolve_symbol", [chart_session, "sds_sym_1", f"={resolve_symbol}"])
        await self.send_message("create_series", [chart_session, "sds_1", "s1", "sds_sym_1", "1", 10, ""])
        await self.send_message("quote_fast_symbols", [quote_session, exchange_symbol])
        await self.send_message("create_study", [chart_session, "st1", "st1", "sds_1",
                            "Volume@tv-basicstudies-246", {"length": 20, "col_prev_close": "false"}])
        await self.send_message("quote_hibernate_all", [quote_session])


    async def get_latest_trade_info(self, exchange_symbol: List[str]) -> AsyncGenerator[dict, None]:
        """
        Returns summary information about multiple symbols including last changes,
        change percentage, and last trade time.

        Args:
            exchange_symbol (List[str]): A list of symbols in the format 'EXCHANGE:SYMBOL'.

        Returns:
            AsyncGenerator[dict, None]: An async generator yielding summary information as JSON objects.
        """
        await self.validate_symbols(exchange_symbol)
        await self._connect()

        quote_session = self.generate_session(prefix="qs_")
        chart_session = self.generate_session(prefix="cs_")
        logging.info(f"Session generated: {quote_session}, Chart session generated: {chart_session}")

        await self._initialize_sessions(quote_session, chart_session)
        await self._add_multiple_symbols_to_sessions(quote_session, exchange_symbol)

        async for data in self._get_data():
            yield data

    async def _add_multiple_symbols_to_sessions(self, quote_session: str, exchange_symbols: List[str]) -> None:
        """
        Adds multiple symbols to the quote session.
        """
        resolve_symbol = json.dumps({"adjustment": "splits", "currency-id": "USD", "session": "regular", "symbol": exchange_symbols[0]})
        await self.send_message("quote_add_symbols", [quote_session, f"={resolve_symbol}"])
        await self.send_message("quote_fast_symbols", [quote_session, f"={resolve_symbol}"])

        await self.send_message("quote_add_symbols", [quote_session]+exchange_symbols)
        await self.send_message("quote_fast_symbols", [quote_session]+exchange_symbols)


    async def _get_data(self) -> AsyncGenerator[dict, None]:
        """
        Continuously receives data from the TradingView server via the WebSocket connection.

        Yields:
            dict: Parsed JSON data received from the server.
        """
        if not self.ws:
            raise RuntimeError("WebSocket connection not established")

        try:
            async for message in self.ws:
                try:
                    result = message
                    # Check if the result is a heartbeat or actual data
                    if re.match(r"~m~\d+~m~~h~\d+$", result):
                        logging.debug(f"Received heartbeat: {result}")
                        await self.ws.send(result)  # Echo back the heartbeat
                    else:
                        split_result = [x for x in re.split(r'~m~\d+~m~', result) if x]
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
            if self.ws:
                await self.ws.close()


# Signal handler for keyboard interrupt
def signal_handler(sig: int, frame) -> None:
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
        # exchange_symbol = ["SET:AOT", "BINANCE:ETHUSDT", "FXOPEN:XAUUSD"]
        exchange_symbol = ["TFEX:S50U2025"]

        # Get latest trade info
        # async for packet in real_time_data.get_latest_trade_info(exchange_symbol=exchange_symbol):
        #     print('-' * 50)
        #     print(packet)

        # Alternative: Get OHLCV data for a single symbol
        async for packet in real_time_data.get_ohlcv(exchange_symbol=exchange_symbol[0]):
            print('-' * 50)
            print(packet)


if __name__ == "__main__":
    asyncio.run(main())
