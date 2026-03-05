"""Module providing async functions which return async generators containing trades realtime data."""

import asyncio
import logging
import types
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import ValidationError

from tvkit.api.chart.models.ohlcv import (
    OHLCVBar,
    OHLCVResponse,
    QuoteCompletedMessage,
    QuoteSymbolData,
    TimescaleUpdateResponse,
    WebSocketMessage,
)
from tvkit.api.chart.services import ConnectionService, MessageService
from tvkit.api.chart.utils import validate_interval
from tvkit.api.utils import convert_symbol_format, validate_symbols

logger: logging.Logger = logging.getLogger(__name__)


class OHLCV:
    """
    A real-time data streaming client for TradingView WebSocket API.

    This class provides async generators for streaming live market data including
    OHLCV bars, quote data, and trade information from TradingView.
    """

    def __init__(self) -> None:
        """
        Initializes the OHLCV class, setting up WebSocket connection parameters
        and request headers for TradingView data streaming.
        """
        self.ws_url: str = "wss://data.tradingview.com/socket.io/websocket?from=chart%2F"
        self.connection_service: ConnectionService | None = None
        self.message_service: MessageService | None = None

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
        if self.connection_service:
            await self.connection_service.close()

    async def _setup_services(self) -> None:
        """Initialize and connect the services, closing any existing connection first."""
        if self.connection_service is not None:
            await self.connection_service.close()
        self.connection_service = ConnectionService(self.ws_url)
        await self.connection_service.connect()
        self.message_service = MessageService(self.connection_service.ws)

    async def _prepare_chart_session(
        self,
        converted_symbol: str,
        interval: str,
        bars_count: int,
    ) -> None:
        """
        Set up services and subscribe the chart session to symbol data.

        Calls _setup_services (closes any existing connection first), generates
        unique session IDs, initializes sessions, and subscribes to symbol data.

        Args:
            converted_symbol: Symbol in EXCHANGE:SYMBOL format.
            interval: Chart interval (e.g. "1", "5", "1D").
            bars_count: Number of bars to request.

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
        )

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
        self, exchange_symbol: str, interval: str = "1", bars_count: int = 10
    ) -> list[OHLCVBar]:
        """
        Returns a list of historical OHLCV data for a specified symbol.

        This method fetches historical OHLCV data from TradingView and returns it as a list of OHLCVBar objects.
        Symbols are automatically converted from EXCHANGE-SYMBOL to EXCHANGE:SYMBOL format.

        Args:
            exchange_symbol: The symbol in 'EXCHANGE:SYMBOL' or 'EXCHANGE-SYMBOL' format (e.g., 'BINANCE:BTCUSDT' or 'USI-PCC').
            interval: The interval for the chart (default is "1" for 1 minute).
            bars_count: The number of bars to fetch (default is 10).

        Returns:
            A list of OHLCVBar objects containing historical OHLCV data.

        Raises:
            ValueError: If the symbol format is invalid
            WebSocketException: If connection or streaming fails
        """
        await validate_symbols(exchange_symbol)
        symbol_result = convert_symbol_format(exchange_symbol)
        converted_symbol: str = symbol_result.converted_symbol  # type: ignore
        validate_interval(interval)
        await self._prepare_chart_session(converted_symbol, interval, bars_count)

        if self.connection_service is None:
            raise RuntimeError("Services not properly initialized")

        historical_bars: list[OHLCVBar] = []
        timeout_seconds: int = 30
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        start_time: float = loop.time()

        async for data in self.connection_service.get_data_stream():
            # Check for timeout between messages (safety net for network stalls)
            if loop.time() - start_time > timeout_seconds:
                logger.warning(f"Historical data fetch timed out after {timeout_seconds} seconds")
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
                            f"Received {len(timescale_response.ohlcv_bars)} historical OHLCV bars"
                        )
                        for bar in timescale_response.ohlcv_bars:
                            logger.debug(f"Parsed OHLCV bar: {bar}")
                        historical_bars.extend(timescale_response.ohlcv_bars)
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
                                f"Received {len(ohlcv_response.ohlcv_bars)} OHLCV bars from data update"
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
                    logger.info("Series completed — all available historical bars received")
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

        # Sort bars by timestamp for chronological order.
        # TradingView generally sends bars in order, but this guarantees correctness
        # if messages arrive out of sequence due to network conditions.
        historical_bars.sort(key=lambda bar: bar.timestamp)

        if not historical_bars:
            logger.warning(f"No historical bars received for symbol {converted_symbol}")
            raise RuntimeError(f"No historical data received for symbol {converted_symbol}")

        if len(historical_bars) < bars_count:
            logger.info(
                f"Partial data: received {len(historical_bars)} bars "
                f"(requested {bars_count}) — symbol may have less available history"
            )

        logger.info(
            f"Successfully fetched {len(historical_bars)} historical OHLCV bars for {converted_symbol}"
        )
        return historical_bars

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
