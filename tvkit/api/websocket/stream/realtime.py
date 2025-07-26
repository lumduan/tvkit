"""
Real-time data streaming module for TradingView WebSocket connections.

This module provides a comprehensive async-first implementation for streaming
real-time market data from TradingView, including OHLCV data, trade information,
and technical indicators with export capabilities.
"""

# Standard library imports
import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, AsyncGenerator, Dict, List, Optional, cast

# Third-party imports
import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

# Local imports
from tvkit.api.websocket.stream.exceptions import (
    ConfigurationError,
    ConnectionError,
    DataParsingError,
    SessionError,
    StreamingError,
    SymbolValidationError,
)
from tvkit.api.websocket.stream.models import (
    ExportConfig,
    IndicatorData,
    OHLCVData,
    RealtimeStreamData,
    SessionInfo,
    StreamConfig,
    StreamerResponse,
    TradeData,
    WebSocketMessage,
)
from tvkit.api.websocket.stream.utils import (
    OHLCVConverter,
    export_data,
    generate_session_id,
    validate_symbols_async,
)

# Configure logging
logger: logging.Logger = logging.getLogger(__name__)


class RealtimeStreamer:
    """
    Async-first real-time data streamer for TradingView WebSocket connections.

    This class provides comprehensive functionality for streaming real-time market data
    including OHLCV data, trade information, and technical indicators with built-in
    export capabilities and error handling.

    Example:
        >>> config = StreamConfig(
        ...     symbols=["BINANCE:BTCUSDT", "NASDAQ:AAPL"],
        ...     timeframe="1m",
        ...     num_candles=50
        ... )
        >>> async with RealtimeStreamer(config) as streamer:
        ...     async for data in streamer.stream():
        ...         print(f"Received: {data}")
    """

    def __init__(
        self,
        config: StreamConfig,
        websocket_url: str = "wss://data.tradingview.com/socket.io/websocket?from=chart%2FVEPYsueI%2F&type=chart",
        jwt_token: str = "unauthorized_user_token",
    ):
        """
        Initialize the real-time streamer.

        Args:
            config: Stream configuration including symbols, timeframe, and export settings.
            websocket_url: WebSocket endpoint URL for TradingView data.
            jwt_token: JWT token for authentication (defaults to unauthorized).

        Raises:
            ConfigurationError: If configuration is invalid.
        """
        self.config: StreamConfig = config
        self.websocket_url: str = websocket_url
        self.jwt_token: str = jwt_token

        # WebSocket connection
        self.ws: Optional[Any] = None
        self.is_connected: bool = False

        # Session management
        self.session_info: Optional[SessionInfo] = None
        self.stream_data: Optional[RealtimeStreamData] = None

        # HTTP client for symbol validation
        self.http_client: Optional[httpx.AsyncClient] = None

        # Request headers for WebSocket connection
        self.request_headers: Dict[str, str] = {
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
            "Cache-Control": "no-cache",
            "Origin": "https://www.tradingview.com",
            "Pragma": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"
        }

        # Symbol validation URL
        self.validate_url: str = (
            "https://scanner.tradingview.com/symbol?"
            "symbol={exchange}%3A{symbol}&fields=market&no_404=false"
        )

        # Internal state
        self._ohlcv_converter: Optional[OHLCVConverter] = None
        self._last_export_time: Optional[datetime] = None

        # Validate configuration
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """
        Validate the stream configuration.

        Raises:
            ConfigurationError: If configuration is invalid.
        """
        try:
            # Validate symbols format
            for symbol in self.config.symbols:
                if ':' not in symbol:
                    raise ConfigurationError(
                        f"Invalid symbol format '{symbol}'. Must be like 'BINANCE:BTCUSDT'",
                        config_field="symbols"
                    )

            # Initialize OHLCV converter if needed
            if self.config.timeframe:
                self._ohlcv_converter = OHLCVConverter(self.config.timeframe)

        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Configuration validation failed: {e}")

    async def __aenter__(self) -> 'RealtimeStreamer':
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """
        Establish WebSocket connection and initialize session.

        Raises:
            ConnectionError: If connection fails.
            SymbolValidationError: If symbol validation fails.
            SessionError: If session initialization fails.
        """
        try:
            # Initialize HTTP client for symbol validation
            self.http_client = httpx.AsyncClient(timeout=30.0)

            # Validate symbols
            logger.info(f"Validating {len(self.config.symbols)} symbols...")
            valid_symbols: List[str] = await validate_symbols_async(
                self.config.symbols,
                self.validate_url
            )

            if not valid_symbols:
                raise SymbolValidationError(
                    "No valid symbols found",
                    message="All provided symbols failed validation"
                )

            if len(valid_symbols) < len(self.config.symbols):
                invalid_symbols: List[str] = list(set(self.config.symbols) - set(valid_symbols))
                logger.warning(f"Invalid symbols ignored: {invalid_symbols}")
                # Update config with only valid symbols
                self.config.symbols = valid_symbols

            # Establish WebSocket connection
            logger.info("Establishing WebSocket connection...")
            self.ws = await connect(
                uri=self.websocket_url,
                additional_headers=self.request_headers,
                compression="deflate",
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )

            # Initialize session
            await self._initialize_session()

            self.is_connected = True
            logger.info("WebSocket connection established successfully")

        except WebSocketException as e:
            raise ConnectionError(f"WebSocket connection failed: {e}")
        except httpx.RequestError as e:
            raise ConnectionError(f"Symbol validation failed: {e}")
        except Exception as e:
            if isinstance(e, (ConnectionError, SymbolValidationError, SessionError)):
                raise
            raise ConnectionError(f"Connection setup failed: {e}")

    async def disconnect(self) -> None:
        """
        Close WebSocket connection and cleanup resources.
        """
        self.is_connected = False

        if self.ws:
            try:
                await self.ws.close()
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")
            finally:
                self.ws = None

        if self.http_client:
            try:
                await self.http_client.aclose()
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {e}")
            finally:
                self.http_client = None

    async def _initialize_session(self) -> None:
        """
        Initialize WebSocket session with TradingView.

        Raises:
            SessionError: If session initialization fails.
        """
        try:
            # Generate session identifiers
            quote_session: str = f"qs_{generate_session_id()}"
            chart_session: str = f"cs_{generate_session_id()}"

            # Create session info
            self.session_info = SessionInfo(
                quote_session=quote_session,
                chart_session=chart_session,
                jwt_token=self.jwt_token,
                connection_id=generate_session_id(16)
            )

            # Initialize stream data container
            self.stream_data = RealtimeStreamData(
                session_info=self.session_info,
                config=self.config,
                connection_status='connected',
                error_message=None
            )

            # Send session initialization messages
            await self._send_session_messages()

            logger.info(f"Session initialized: {quote_session}, {chart_session}")

        except Exception as e:
            raise SessionError(f"Session initialization failed: {e}")

    async def _send_session_messages(self) -> None:
        """
        Send session initialization messages to TradingView WebSocket.

        Raises:
            SessionError: If message sending fails.
        """
        if not self.session_info or not self.ws:
            raise SessionError("Session not initialized or WebSocket not connected")

        try:
            # Initialize sessions
            await self._send_message("set_auth_token", [self.jwt_token])
            await self._send_message("chart_create_session", [self.session_info.chart_session, ""])
            await self._send_message("quote_create_session", [self.session_info.quote_session])

            # Add symbols to sessions
            for symbol in self.config.symbols:
                await self._add_symbol_to_session(symbol)

            # Add indicators if configured
            if self.config.include_indicators and self.config.indicator_id:
                await self._add_indicator_study()

        except Exception as e:
            raise SessionError(f"Failed to send session messages: {e}")

    async def _send_message(self, method: str, params: List[Any]) -> None:
        """
        Send a formatted message to the WebSocket.

        Args:
            method: WebSocket method name.
            params: Method parameters.

        Raises:
            SessionError: If message sending fails.
        """
        if not self.ws:
            raise SessionError("WebSocket not connected")

        try:
            message: WebSocketMessage = WebSocketMessage(
                method=method,
                params=params,
                message_id=None
            )
            formatted_message: str = message.format_message()

            await self.ws.send(formatted_message)
            logger.debug(f"Sent message: {method} with params: {params}")

        except Exception as e:
            raise SessionError(f"Failed to send message {method}: {e}")

    async def _add_symbol_to_session(self, symbol: str) -> None:
        """
        Add a symbol to the WebSocket session for data streaming.

        Args:
            symbol: Symbol in 'EXCHANGE:SYMBOL' format.

        Raises:
            SessionError: If symbol addition fails.
        """
        if not self.session_info:
            raise SessionError("Session not initialized")

        try:
            resolve_symbol: str = json.dumps({"adjustment": "splits", "symbol": symbol})

            # Add symbol to quote session
            await self._send_message("quote_add_symbols", [
                self.session_info.quote_session,
                f"={resolve_symbol}"
            ])

            # Add symbol to chart session
            await self._send_message("resolve_symbol", [
                self.session_info.chart_session,
                "sds_sym_1",
                f"={resolve_symbol}"
            ])

            # Create series for OHLCV data
            await self._send_message("create_series", [
                self.session_info.chart_session,
                "sds_1",
                "s1",
                "sds_sym_1",
                self.config.timeframe,
                self.config.num_candles,
                ""
            ])

            # Enable fast symbols for real-time updates
            await self._send_message("quote_fast_symbols", [
                self.session_info.quote_session,
                symbol
            ])

            logger.debug(f"Added symbol {symbol} to session")

        except Exception as e:
            raise SessionError(f"Failed to add symbol {symbol}: {e}")

    async def _add_indicator_study(self) -> None:
        """
        Add indicator study to the session if configured.

        Raises:
            SessionError: If indicator addition fails.
        """
        if not self.config.indicator_id or not self.session_info:
            return

        try:
            # Create indicator study parameters
            study_params: List[Any] = [
                self.session_info.chart_session,
                "sds_2",
                "st1",
                "sds_sym_1",
                self.config.indicator_id,
                self.config.indicator_version or "1",
                {}  # indicator inputs
            ]

            await self._send_message("create_study", study_params)
            await self._send_message("quote_hibernate_all", [self.session_info.quote_session])

            logger.debug(f"Added indicator {self.config.indicator_id}")

        except Exception as e:
            raise SessionError(f"Failed to add indicator: {e}")

    async def stream(self) -> AsyncGenerator[StreamerResponse, None]:
        """
        Stream real-time data from TradingView WebSocket.

        Yields:
            StreamerResponse: Parsed streaming data responses.

        Raises:
            ConnectionError: If connection is lost.
            DataParsingError: If data parsing fails.
            TimeoutError: If no data received within timeout.
        """
        if not self.is_connected or not self.ws:
            raise ConnectionError("Not connected to WebSocket")

        try:
            async for message in self.ws:
                try:
                    # Parse WebSocket message
                    response: Optional[StreamerResponse] = await self._parse_message(message)

                    if response:
                        # Add to stream data
                        if self.stream_data:
                            self.stream_data.add_response(response)

                        # Handle export if configured
                        await self._handle_export(response)

                        yield response

                except DataParsingError as e:
                    logger.warning(f"Data parsing error: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error processing message: {e}")
                    continue

        except ConnectionClosed as e:
            self.is_connected = False
            raise ConnectionError(f"WebSocket connection closed: {e}")
        except WebSocketException as e:
            self.is_connected = False
            raise ConnectionError(f"WebSocket error: {e}")
        except Exception as e:
            raise StreamingError(f"Streaming error: {e}")

    async def _parse_message(self, message: str) -> Optional[StreamerResponse]:
        """
        Parse WebSocket message and extract data.

        Args:
            message: Raw WebSocket message.

        Returns:
            Parsed streamer response or None if no data found.

        Raises:
            DataParsingError: If message parsing fails.
        """
        try:
            # TradingView uses a specific message format
            if not message.startswith('~m~'):
                return None

            # Extract JSON part from TradingView message format
            parts: List[str] = message.split('~m~')
            if len(parts) < 3:
                return None

            json_data: str = parts[2]
            if not json_data:
                return None

            data: Dict[str, Any] = json.loads(json_data)

            # Check for different message types
            if 'p' in data:
                return await self._parse_data_message(data)

            return None

        except json.JSONDecodeError as e:
            raise DataParsingError(f"JSON decode error: {e}", message)
        except Exception as e:
            raise DataParsingError(f"Message parsing error: {e}", message)

    async def _parse_data_message(self, data: Dict[str, Any]) -> Optional[StreamerResponse]:
        """
        Parse data message and extract OHLCV or trade information.

        Args:
            data: Parsed message data.

        Returns:
            Parsed streamer response or None.

        Raises:
            DataParsingError: If data parsing fails.
        """
        try:
            message_params: List[Any] = data.get('p', [])
            if len(message_params) < 2:
                return None

            # Check for OHLCV data
            if 'sds_1' in str(message_params):
                return await self._parse_ohlcv_data(message_params)

            # Check for indicator data
            if 'sds_2' in str(message_params) and self.config.include_indicators:
                return await self._parse_indicator_data(message_params)

            # Check for trade data
            if isinstance(message_params[1], dict):
                return await self._parse_trade_data(message_params)

            return None

        except Exception as e:
            raise DataParsingError(f"Data message parsing error: {e}", data)

    async def _parse_ohlcv_data(self, params: List[Any]) -> Optional[StreamerResponse]:
        """
        Parse OHLCV data from message parameters.

        Args:
            params: Message parameters containing OHLCV data.

        Returns:
            StreamerResponse with OHLCV data or None.
        """
        try:
            if len(params) < 2 or not isinstance(params[1], dict):
                return None

            # Type-safe extraction with explicit casting
            param_data: Dict[str, Any] = cast(Dict[str, Any], params[1])
            series_data_raw: Any = param_data.get('sds_1', {})

            # Validate that series_data is a dictionary
            if not isinstance(series_data_raw, dict):
                return None

            # Cast to proper type after validation
            series_data: Dict[str, Any] = cast(Dict[str, Any], series_data_raw)
            if 's' not in series_data:
                return None

            # Validate that 's' contains a list
            series_list_raw: Any = series_data['s']
            if not isinstance(series_list_raw, list):
                return None

            # Cast to list after validation
            series_list: List[Any] = cast(List[Any], series_list_raw)
            ohlcv_list: List[OHLCVData] = []

            for entry_raw in series_list:
                # Type guard for entry
                if not isinstance(entry_raw, dict):
                    continue

                # Cast to proper type after validation
                entry: Dict[str, Any] = cast(Dict[str, Any], entry_raw)

                # Validate entry structure
                if 'v' not in entry:
                    continue

                values_raw: Any = entry['v']
                if not isinstance(values_raw, list) or len(cast(list[Any], values_raw)) < 6:
                    continue

                # Cast to list after validation
                values: List[Any] = cast(List[Any], values_raw)

                try:
                    # Extract index with type safety
                    index_raw: Any = entry.get('i', 0)
                    index: int = int(index_raw) if isinstance(index_raw, (int, float, str)) else 0

                    ohlcv: OHLCVData = OHLCVData(
                        index=index,
                        timestamp=int(values[0]),
                        open=Decimal(str(values[1])),
                        high=Decimal(str(values[2])),
                        low=Decimal(str(values[3])),
                        close=Decimal(str(values[4])),
                        volume=Decimal(str(values[5]))
                    )
                    ohlcv_list.append(ohlcv)

                except (ValueError, TypeError, IndexError) as e:
                    logger.warning(f"Error parsing OHLCV entry: {e}")
                    continue

            if not ohlcv_list:
                return None

            # Determine symbol from config (simplified approach)
            symbol: str = self.config.symbols[0] if self.config.symbols else "UNKNOWN"

            return StreamerResponse(
                symbol=symbol,
                data_type='ohlcv',
                ohlcv_data=ohlcv_list,
                trade_data=None,
                indicator_data=None,
                metadata={'raw_params': params}
            )

        except Exception as e:
            logger.warning(f"OHLCV parsing error: {e}")
            return None

    async def _parse_indicator_data(self, params: List[Any]) -> Optional[StreamerResponse]:
        """
        Parse technical indicator data from message parameters.

        Args:
            params: Message parameters containing indicator data.

        Returns:
            StreamerResponse with indicator data or None.
        """
        try:
            if len(params) < 2 or not isinstance(params[1], dict):
                return None

            # Type-safe extraction with casting
            param_data: Dict[str, Any] = cast(Dict[str, Any], params[1])
            indicator_data_raw: Any = param_data.get('sds_2', {})

            # Validate that indicator_data is a dictionary
            if not isinstance(indicator_data_raw, dict):
                return None

            indicator_data: Dict[str, Any] = cast(Dict[str, Any], indicator_data_raw)
            if 'st' not in indicator_data:
                return None

            # Validate that 'st' contains a dictionary
            st_data_raw: Any = indicator_data['st']
            if not isinstance(st_data_raw, dict):
                return None

            # Parse indicator values
            st_data: Dict[str, Any] = cast(Dict[str, Any], st_data_raw)
            values: Dict[str, Decimal] = {}

            for key, value in st_data.items():
                try:
                    # Cast key and value to proper types
                    str_key: str = str(key)
                    values[str_key] = Decimal(str(value))
                except (ValueError, TypeError):
                    continue

            if not values:
                return None

            indicator: IndicatorData = IndicatorData(
                indicator_id=self.config.indicator_id or "unknown",
                indicator_version=self.config.indicator_version or "1",
                timestamp=int(datetime.now().timestamp()),
                values=values,
                metadata={'raw_params': params}
            )

            symbol: str = self.config.symbols[0] if self.config.symbols else "UNKNOWN"

            return StreamerResponse(
                symbol=symbol,
                data_type='indicator',
                ohlcv_data=None,
                trade_data=None,
                indicator_data=indicator,
                metadata={'raw_params': params}
            )

        except Exception as e:
            logger.warning(f"Indicator parsing error: {e}")
            return None

    async def _parse_trade_data(self, params: List[Any]) -> Optional[StreamerResponse]:
        """
        Parse trade data from message parameters.

        Args:
            params: Message parameters containing trade data.

        Returns:
            StreamerResponse with trade data or None.
        """
        try:
            if len(params) < 2 or not isinstance(params[1], dict):
                return None

            # Type-safe extraction with casting
            trade_info: Dict[str, Any] = cast(Dict[str, Any], params[1])

            # Extract trade information (format may vary)
            price: Optional[float] = trade_info.get('lp')  # last price
            volume: Optional[float] = trade_info.get('volume')

            if price is None:
                return None

            trade: TradeData = TradeData(
                symbol=self.config.symbols[0] if self.config.symbols else "UNKNOWN",
                price=Decimal(str(price)),
                volume=Decimal(str(volume or 0)),
                timestamp=int(datetime.now().timestamp()),
                side=None
            )

            return StreamerResponse(
                symbol=trade.symbol,
                data_type='trade',
                ohlcv_data=None,
                trade_data=trade,
                indicator_data=None,
                metadata={'raw_params': params}
            )

        except Exception as e:
            logger.warning(f"Trade parsing error: {e}")
            return None

    async def _handle_export(self, response: StreamerResponse) -> None:
        """
        Handle data export based on configuration.

        Args:
            response: Streamer response to potentially export.
        """
        if not self.config.export_config or not self.config.export_config.enabled:
            return

        try:
            # Check if it's time for auto-export
            export_config: ExportConfig = self.config.export_config

            if export_config.auto_export_interval:
                now: datetime = datetime.now()
                if (self._last_export_time and
                    (now - self._last_export_time).total_seconds() < export_config.auto_export_interval):
                    return
                self._last_export_time = now

            # Export OHLCV data
            if response.data_type == 'ohlcv' and response.ohlcv_data:
                await export_data(
                    response.ohlcv_data,
                    export_config,
                    response.symbol,
                    self.config.timeframe
                )

        except Exception as e:
            logger.warning(f"Export error: {e}")

    def get_stream_statistics(self) -> Optional[Dict[str, Any]]:
        """
        Get current streaming statistics.

        Returns:
            Dictionary containing streaming statistics or None if not available.
        """
        if self.stream_data:
            return self.stream_data.get_statistics()
        return None

    def get_latest_ohlcv(self, symbol: Optional[str] = None) -> Optional[List[OHLCVData]]:
        """
        Get the latest OHLCV data for a symbol.

        Args:
            symbol: Symbol to get data for, or None for all symbols.

        Returns:
            List of latest OHLCV data or None if not available.
        """
        if self.stream_data:
            return self.stream_data.get_latest_ohlcv(symbol)
        return None

if __name__ == "__main__":
    # Configure logging for demonstration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def demo_basic_streaming():
        """
        Demonstrate basic real-time streaming with OHLCV data.
        """
        print("\n🚀 Demo 1: Basic OHLCV Streaming")
        print("=" * 50)

        config: StreamConfig = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=20,
            include_indicators=False,
            indicator_id=None,
            indicator_version=None,
            export_config=None
        )

        try:
            async with RealtimeStreamer(config) as streamer:
                print(f"✅ Connected to TradingView WebSocket")
                print(f"📈 Streaming: {', '.join(config.symbols)}")
                print(f"⏰ Timeframe: {config.timeframe}")
                print(f"📊 Historical candles: {config.num_candles}")

                # Stream for a limited time to demonstrate
                count: int = 0
                max_responses: int = 5

                async for response in streamer.stream():
                    count += 1
                    print(f"\n📦 Response {count}: {response.data_type.upper()}")
                    print(f"🎯 Symbol: {response.symbol}")
                    print(f"⏰ Timestamp: {response.timestamp}")

                    if response.ohlcv_data:
                        for ohlcv in response.ohlcv_data:
                            print(f"💰 OHLCV: Open={ohlcv.open}, High={ohlcv.high}, "
                                  f"Low={ohlcv.low}, Close={ohlcv.close}, Volume={ohlcv.volume}")

                    # Get stream statistics
                    stats: Optional[Dict[str, Any]] = streamer.get_stream_statistics()
                    if stats:
                        print(f"📊 Stats: {stats['total_responses']} responses, "
                              f"{stats['session_duration']:.1f}s session duration")

                    if count >= max_responses:
                        print(f"\n✅ Demo complete after {count} responses")
                        break

        except Exception as e:
            print(f"❌ Error in basic streaming demo: {e}")

    async def demo_multiple_symbols():
        """
        Demonstrate streaming multiple symbols simultaneously.
        """
        print("\n🌐 Demo 2: Multiple Symbol Streaming")
        print("=" * 50)

        config: StreamConfig = StreamConfig(
            symbols=["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "NASDAQ:AAPL"],
            timeframe="5m",
            num_candles=10,
            include_indicators=False,
            indicator_id=None,
            indicator_version=None,
            export_config=None
        )

        try:
            async with RealtimeStreamer(config) as streamer:
                print(f"✅ Streaming {len(config.symbols)} symbols:")
                for symbol in config.symbols:
                    print(f"  📈 {symbol}")

                # Collect data for each symbol
                symbol_data: Dict[str, int] = {}
                count: int = 0
                max_responses: int = 10

                async for response in streamer.stream():
                    count += 1
                    symbol_data[response.symbol] = symbol_data.get(response.symbol, 0) + 1

                    print(f"\n📦 Response {count}: {response.symbol} - {response.data_type}")

                    # Get latest OHLCV for specific symbols
                    latest_btc: Optional[List[OHLCVData]] = streamer.get_latest_ohlcv("BINANCE:BTCUSDT")
                    latest_eth: Optional[List[OHLCVData]] = streamer.get_latest_ohlcv("BINANCE:ETHUSDT")

                    if latest_btc:
                        print(f"₿ Latest BTC: {latest_btc[-1].close} USDT")
                    if latest_eth:
                        print(f"🔷 Latest ETH: {latest_eth[-1].close} USDT")

                    if count >= max_responses:
                        print(f"\n📊 Symbol distribution: {symbol_data}")
                        break

        except Exception as e:
            print(f"❌ Error in multiple symbols demo: {e}")

    async def demo_with_indicators():
        """
        Demonstrate streaming with technical indicators.
        """
        print("\n📊 Demo 3: Streaming with Technical Indicators")
        print("=" * 50)

        config: StreamConfig = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50,
            include_indicators=True,
            indicator_id="STD;SMA",  # Simple Moving Average
            indicator_version="1",
            export_config=None
        )

        try:
            async with RealtimeStreamer(config) as streamer:
                print(f"✅ Streaming with indicators enabled")
                print(f"📈 Symbol: {config.symbols[0]}")
                print(f"📊 Indicator: {config.indicator_id}")

                count: int = 0
                max_responses: int = 8

                async for response in streamer.stream():
                    count += 1
                    print(f"\n📦 Response {count}: {response.data_type.upper()}")

                    if response.indicator_data:
                        print(f"📊 Indicator: {response.indicator_data.indicator_id}")
                        print(f"💹 Values: {dict(list(response.indicator_data.values.items())[:3])}")

                    if response.ohlcv_data:
                        latest_ohlcv: OHLCVData = response.ohlcv_data[-1]
                        print(f"💰 Latest Price: {latest_ohlcv.close}")

                    if count >= max_responses:
                        break

        except Exception as e:
            print(f"❌ Error in indicators demo: {e}")

    async def demo_with_export():
        """
        Demonstrate streaming with data export capabilities.
        """
        print("\n💾 Demo 4: Streaming with Data Export")
        print("=" * 50)

        export_config: ExportConfig = ExportConfig(
            enabled=True,
            format='json',
            directory='./export',
            filename_prefix='demo_stream',
            include_timestamp=True,
            auto_export_interval=30  # Export every 30 seconds
        )

        config: StreamConfig = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=15,
            include_indicators=False,
            indicator_id=None,
            indicator_version=None,
            export_config=export_config
        )

        try:
            async with RealtimeStreamer(config) as streamer:
                print(f"✅ Export enabled: {export_config.format} format")
                print(f"📁 Directory: {export_config.directory}")
                print(f"⏰ Auto-export interval: {export_config.auto_export_interval}s")

                count: int = 0
                max_responses: int = 6

                async for response in streamer.stream():
                    count += 1
                    print(f"\n📦 Response {count}: Data exported to {export_config.directory}")

                    if response.ohlcv_data:
                        print(f"💰 Price data: {len(response.ohlcv_data)} candles")

                    # Show statistics
                    stats: Optional[Dict[str, Any]] = streamer.get_stream_statistics()
                    if stats:
                        print(f"📊 Total responses: {stats['total_responses']}")

                    if count >= max_responses:
                        print(f"\n✅ Check {export_config.directory} for exported files")
                        break

        except Exception as e:
            print(f"❌ Error in export demo: {e}")

    async def demo_error_handling():
        """
        Demonstrate error handling and connection recovery.
        """
        print("\n⚠️ Demo 5: Error Handling and Recovery")
        print("=" * 50)

        # Test with invalid symbol format
        try:
            config_invalid: StreamConfig = StreamConfig(
                symbols=["INVALID_SYMBOL"],  # Missing exchange prefix
                timeframe="1m",
                num_candles=10,
                include_indicators=False,
                indicator_id=None,
                indicator_version=None,
                export_config=None
            )
            # Use the config to trigger validation
            print(f"❌ This should fail with invalid symbol format: {config_invalid.symbols}")
        except Exception as e:
            print(f"✅ Caught expected validation error: {e}")

        # Test with invalid timeframe
        try:
            StreamConfig(
                symbols=["BINANCE:BTCUSDT"],
                timeframe="30s",  # Invalid timeframe
                num_candles=10,
                include_indicators=False,
                indicator_id=None,
                indicator_version=None,
                export_config=None
            )
            print("❌ This should fail with invalid timeframe")
        except Exception as e:
            print(f"✅ Caught expected timeframe error: {e}")

        # Test connection with proper configuration but limited time
        print("\n🔄 Testing connection handling...")
        try:
            config_valid: StreamConfig = StreamConfig(
                symbols=["BINANCE:BTCUSDT"],
                timeframe="1m",
                num_candles=5,
                include_indicators=False,
                indicator_id=None,
                indicator_version=None,
                export_config=None
            )

            async with RealtimeStreamer(config_valid) as streamer:
                print("✅ Connection established successfully")

                # Test method calls on connected streamer
                stats: Optional[Dict[str, Any]] = streamer.get_stream_statistics()
                if stats:
                    print(f"📊 Connection status: {stats['connection_status']}")

                # Get latest OHLCV (might be None initially)
                latest: Optional[List[OHLCVData]] = streamer.get_latest_ohlcv()
                print(f"📈 Latest OHLCV available: {latest is not None}")

                # Stream for a very short time
                count: int = 0
                async for _ in streamer.stream():
                    count += 1
                    print(f"📦 Received response {count}")
                    if count >= 2:
                        break

            print("✅ Connection closed cleanly")

        except Exception as e:
            print(f"⚠️ Expected network error (WebSocket connection): {e}")

    async def demo_configuration_options():
        """
        Demonstrate various configuration options and their effects.
        """
        print("\n⚙️ Demo 6: Configuration Options")
        print("=" * 50)

        configs: List[tuple[str, StreamConfig]] = [
            ("Crypto High Frequency", StreamConfig(
                symbols=["BINANCE:BTCUSDT", "BINANCE:ETHUSDT"],
                timeframe="1m",
                num_candles=100,
                include_indicators=False,
                indicator_id=None,
                indicator_version=None,
                export_config=None
            )),
            ("Stock with Indicators", StreamConfig(
                symbols=["NASDAQ:AAPL"],
                timeframe="5m",
                num_candles=50,
                include_indicators=True,
                indicator_id="STD;RSI",
                indicator_version="1",
                export_config=None
            )),
            ("Multi-Asset Portfolio", StreamConfig(
                symbols=["BINANCE:BTCUSDT", "NASDAQ:AAPL", "BINANCE:ETHUSDT"],
                timeframe="15m",
                num_candles=20,
                include_indicators=False,
                indicator_id=None,
                indicator_version=None,
                export_config=ExportConfig(
                    enabled=True,
                    format='csv',
                    directory='./export',
                    filename_prefix='portfolio',
                    include_timestamp=True,
                    auto_export_interval=None
                )
            ))
        ]

        for desc, config in configs:
            print(f"\n📋 Configuration: {desc}")
            print(f"  📈 Symbols: {len(config.symbols)} ({', '.join(config.symbols[:2])}{'...' if len(config.symbols) > 2 else ''})")
            print(f"  ⏰ Timeframe: {config.timeframe}")
            print(f"  📊 Candles: {config.num_candles}")
            print(f"  🧮 Indicators: {'✅' if config.include_indicators else '❌'}")
            print(f"  💾 Export: {'✅' if config.export_config and config.export_config.enabled else '❌'}")

            try:
                # Test configuration validation without connecting
                _ = RealtimeStreamer(config)
                print(f"  ✅ Configuration valid")
            except Exception as e:
                print(f"  ❌ Configuration error: {e}")

    async def main():
        """
        Run comprehensive demonstration of all RealtimeStreamer functionality.

        This function demonstrates:
        1. Basic OHLCV streaming
        2. Multiple symbol streaming
        3. Technical indicators integration
        4. Data export capabilities
        5. Error handling and recovery
        6. Configuration options and validation
        """
        print("🎯 TradingView Real-time Streamer - Comprehensive Demo")
        print("=" * 60)
        print("⚠️  Note: This demo requires internet connection to TradingView")
        print("⚠️  Some demos may fail due to network restrictions")
        print("=" * 60)

        # List of all demos to run
        demos: List[tuple[str, Any]] = [
            ("Configuration Options (Safe)", demo_configuration_options),
            ("Error Handling (Safe)", demo_error_handling),
            ("Basic OHLCV Streaming", demo_basic_streaming),
            ("Multiple Symbols", demo_multiple_symbols),
            ("Technical Indicators", demo_with_indicators),
            ("Data Export", demo_with_export),
        ]

        for i, (demo_name, demo_func) in enumerate(demos, 1):
            try:
                print(f"\n🎬 Running Demo {i}/{len(demos)}: {demo_name}")
                await demo_func()
                print(f"✅ Demo {i} completed successfully")
            except Exception as e:
                print(f"❌ Demo {i} failed: {e}")
                print(f"   This is expected for network-dependent demos")

            # Small delay between demos
            await asyncio.sleep(1)

        print(f"\n🎉 All demonstrations completed!")
        print("=" * 60)
        print("📖 Key Methods Demonstrated:")
        print("   • RealtimeStreamer.__init__(config)")
        print("   • async with RealtimeStreamer(config) as streamer:")
        print("   • async for response in streamer.stream():")
        print("   • streamer.get_stream_statistics()")
        print("   • streamer.get_latest_ohlcv(symbol)")
        print("   • StreamConfig validation and configuration")
        print("   • Error handling and connection management")
        print("=" * 60)

    asyncio.run(main())
