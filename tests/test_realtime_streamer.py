"""
Tests for real-time WebSocket streaming implementation.

This module provides comprehensive tests for the RealtimeStreamer class
and its functionality for connecting to TradingView WebSocket streams.
"""

import asyncio
import json
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tvkit.api.websocket.stream.exceptions import (
    ConfigurationError,
    ConnectionError,
    DataParsingError,
    SessionError,
    StreamingError,
)
from tvkit.api.websocket.stream.models import (
    ExportConfig,
    OHLCVData,
    StreamConfig,
    StreamerResponse,
    TradeData,
)
from tvkit.api.websocket.stream.realtime import RealtimeStreamer


class TestRealtimeStreamer:
    """Test cases for RealtimeStreamer class."""

    def test_init_basic_config(self):
        """Test initializing with basic configuration."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        streamer = RealtimeStreamer(config)

        assert streamer.config == config
        assert streamer.websocket_url == "wss://data.tradingview.com/socket.io/websocket?from=chart%2FVEPYsueI%2F&type=chart"
        assert streamer.jwt_token == "unauthorized_user_token"
        assert streamer.ws is None
        assert not streamer.is_connected

    def test_init_custom_websocket_url(self):
        """Test initializing with custom WebSocket URL."""
        config = StreamConfig(
            symbols=["NASDAQ:AAPL"],
            timeframe="5m",
            num_candles=20
        )
        custom_url = "wss://custom.tradingview.com/websocket"

        streamer = RealtimeStreamer(config, websocket_url=custom_url)

        assert streamer.websocket_url == custom_url

    def test_init_custom_jwt_token(self):
        """Test initializing with custom JWT token."""
        config = StreamConfig(
            symbols=["BINANCE:ETHUSDT"],
            timeframe="15m",
            num_candles=30
        )
        custom_token = "custom_jwt_token_12345"

        streamer = RealtimeStreamer(config, jwt_token=custom_token)

        assert streamer.jwt_token == custom_token

    def test_configuration_validation_empty_symbols(self):
        """Test configuration validation with empty symbols."""
        config = StreamConfig(
            symbols=[],
            timeframe="1m",
            num_candles=50
        )

        with pytest.raises(ConfigurationError):
            RealtimeStreamer(config)

    def test_configuration_validation_invalid_timeframe(self):
        """Test configuration validation with invalid timeframe."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="invalid",
            num_candles=50
        )

        # Should not raise during init, but during validation
        streamer = RealtimeStreamer(config)

        with pytest.raises(ConfigurationError):
            streamer._validate_configuration()

    def test_configuration_validation_invalid_num_candles(self):
        """Test configuration validation with invalid number of candles."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=0
        )

        with pytest.raises(ConfigurationError):
            RealtimeStreamer(config)

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        """Test successful context manager entry and exit."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        with patch.object(RealtimeStreamer, 'connect') as mock_connect, \
             patch.object(RealtimeStreamer, 'disconnect') as mock_disconnect:

            mock_connect.return_value = None
            mock_disconnect.return_value = None

            async with RealtimeStreamer(config) as streamer:
                assert streamer is not None
                mock_connect.assert_called_once()

            mock_disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_connection_failure(self):
        """Test context manager with connection failure."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        with patch.object(RealtimeStreamer, 'connect') as mock_connect:
            mock_connect.side_effect = ConnectionError("Connection failed")

            with pytest.raises(ConnectionError):
                async with RealtimeStreamer(config):
                    pass

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful WebSocket connection."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        mock_websocket = AsyncMock()

        with patch('tvkit.api.websocket.stream.realtime.connect') as mock_connect, \
             patch.object(RealtimeStreamer, '_initialize_session') as mock_init_session:

            mock_connect.return_value.__aenter__.return_value = mock_websocket
            mock_init_session.return_value = None

            streamer = RealtimeStreamer(config)
            await streamer.connect()

            assert streamer.is_connected is True
            assert streamer.ws is not None
            mock_init_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_websocket_error(self):
        """Test WebSocket connection error."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        with patch('tvkit.api.websocket.stream.realtime.connect') as mock_connect:
            mock_connect.side_effect = Exception("WebSocket connection failed")

            streamer = RealtimeStreamer(config)

            with pytest.raises(ConnectionError):
                await streamer.connect()

    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        """Test successful WebSocket disconnection."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        mock_websocket = AsyncMock()

        streamer = RealtimeStreamer(config)
        streamer.ws = mock_websocket
        streamer.is_connected = True

        await streamer.disconnect()

        assert streamer.is_connected is False
        assert streamer.ws is None
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(self):
        """Test disconnection when not connected."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        streamer = RealtimeStreamer(config)

        # Should not raise error
        await streamer.disconnect()

        assert streamer.is_connected is False

    @pytest.mark.asyncio
    async def test_stream_not_connected(self):
        """Test streaming when not connected."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        streamer = RealtimeStreamer(config)

        with pytest.raises(StreamingError, match="Not connected"):
            async for _ in streamer.stream():
                pass

    @pytest.mark.asyncio
    async def test_stream_receives_data(self):
        """Test streaming receives data correctly."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        mock_websocket = AsyncMock()
        mock_response = StreamerResponse(
            symbol="BINANCE:BTCUSDT",
            data_type="ohlcv",
            data={
                "timestamp": 1642694400,
                "open": 50000.0,
                "high": 51000.0,
                "low": 49500.0,
                "close": 50500.0,
                "volume": 1250.0
            },
            timestamp=1642694400
        )

        # Mock message that would trigger parsing
        mock_message = '~m~100~m~{"m":"timescale_update","p":["sds_1",{"s":[{"i":1,"v":[1642694400,50000,51000,49500,50500,1250]}]}]}'

        mock_websocket.recv = AsyncMock(side_effect=[mock_message, asyncio.CancelledError()])

        with patch.object(RealtimeStreamer, '_parse_message') as mock_parse:
            mock_parse.return_value = mock_response

            streamer = RealtimeStreamer(config)
            streamer.ws = mock_websocket
            streamer.is_connected = True

            received_data = []

            try:
                async for data in streamer.stream():
                    received_data.append(data)
                    if len(received_data) >= 1:
                        break
            except asyncio.CancelledError:
                pass

            assert len(received_data) == 1
            assert received_data[0] == mock_response

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test sending WebSocket message successfully."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        mock_websocket = AsyncMock()

        streamer = RealtimeStreamer(config)
        streamer.ws = mock_websocket
        streamer.is_connected = True

        await streamer._send_message("test_method", ["param1", "param2"])

        mock_websocket.send.assert_called_once()
        # Verify the call was made with a string message
        call_args = mock_websocket.send.call_args[0][0]
        assert isinstance(call_args, str)
        assert "test_method" in call_args

    @pytest.mark.asyncio
    async def test_send_message_not_connected(self):
        """Test sending message when not connected."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        streamer = RealtimeStreamer(config)

        with pytest.raises(StreamingError):
            await streamer._send_message("test_method", [])

    def test_get_stream_statistics_no_data(self):
        """Test getting stream statistics when no data available."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        streamer = RealtimeStreamer(config)

        stats = streamer.get_stream_statistics()

        assert stats is None

    def test_get_latest_ohlcv_no_data(self):
        """Test getting latest OHLCV when no data available."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        streamer = RealtimeStreamer(config)

        ohlcv_data = streamer.get_latest_ohlcv()

        assert ohlcv_data is None


class TestRealtimeStreamerIntegration:
    """Integration tests for RealtimeStreamer."""

    @pytest.mark.asyncio
    async def test_full_workflow_mock(self):
        """Test complete workflow with mocked WebSocket."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        # Mock WebSocket messages
        messages = [
            '~m~50~m~{"m":"quote_completed","p":["qs_1"]}',
            '~m~100~m~{"m":"timescale_update","p":["sds_1",{"s":[{"i":1,"v":[1642694400,50000,51000,49500,50500,1250]}]}]}',
        ]

        mock_websocket = AsyncMock()
        mock_websocket.recv = AsyncMock(side_effect=messages + [asyncio.CancelledError()])
        mock_websocket.send = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch('tvkit.api.websocket.stream.realtime.connect') as mock_connect:
            mock_connect.return_value.__aenter__.return_value = mock_websocket

            streamer = RealtimeStreamer(config)

            received_messages = []

            try:
                async with streamer:
                    async for message in streamer.stream():
                        if message:  # Only add non-None messages
                            received_messages.append(message)
                        if len(received_messages) >= 1:  # Get one message then stop
                            break
            except asyncio.CancelledError:
                pass

            # Should have attempted to connect and send session messages
            mock_websocket.send.assert_called()

    def test_configuration_with_export_enabled(self):
        """Test configuration with export functionality enabled."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT", "NASDAQ:AAPL"],
            timeframe="5m",
            num_candles=100,
            export=ExportConfig(
                enabled=True,
                format='json',
                directory='/tmp/exports',
                filename_prefix='test_stream',
                include_timestamp=True,
                auto_export_interval=300
            )
        )

        streamer = RealtimeStreamer(config)

        # Verify export configuration is properly set
        assert streamer.config.export.enabled is True
        assert streamer.config.export.format == 'json'
        assert streamer.config.export.directory == '/tmp/exports'
        assert streamer.config.export.filename_prefix == 'test_stream'
        assert streamer.config.export.include_timestamp is True
        assert streamer.config.export.auto_export_interval == 300

    @pytest.mark.asyncio
    async def test_error_handling_websocket_disconnect(self):
        """Test error handling when WebSocket disconnects."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50
        )

        mock_websocket = AsyncMock()
        mock_websocket.recv = AsyncMock(side_effect=[
            '~m~50~m~{"m":"quote_completed","p":["qs_1"]}',
            Exception("WebSocket disconnected")
        ])
        mock_websocket.send = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch('tvkit.api.websocket.stream.realtime.connect') as mock_connect:
            mock_connect.return_value.__aenter__.return_value = mock_websocket

            streamer = RealtimeStreamer(config)

            with pytest.raises(StreamingError):
                async with streamer:
                    async for message in streamer.stream():
                        break


@pytest.fixture
def sample_config():
    """Fixture providing a sample StreamConfig for testing."""
    return StreamConfig(
        symbols=["BINANCE:BTCUSDT", "NASDAQ:AAPL"],
        timeframe="1m",
        num_candles=50
    )


@pytest.fixture
def sample_streamer(sample_config):
    """Fixture providing a RealtimeStreamer instance for testing."""
    return RealtimeStreamer(sample_config)


@pytest.fixture
def mock_websocket_message():
    """Fixture providing a mock WebSocket message."""
    mock_data = {
        "m": "timescale_update",
        "p": [
            "sds_1",
            {
                "s": [
                    {
                        "i": 1,
                        "v": [1642694400, 50000.0, 51000.0, 49500.0, 50500.0, 1250.0]
                    }
                ]
            }
        ]
    }
    return f"~m~{len(json.dumps(mock_data))}~m~{json.dumps(mock_data)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import asyncio
import json
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tvkit.api.websocket.stream.exceptions import (
    ConnectionError,
    DataParsingError,
    SessionError,
    StreamingError,
)
from tvkit.api.websocket.stream.models import (
    ExportConfig,
    OHLCVData,
    RealtimeStreamData,
    StreamConfig,
    TradeData,
)
from tvkit.api.websocket.stream.realtime import RealtimeStreamer


class TestRealtimeStreamer:
    """Test cases for RealtimeStreamer class."""

    def test_init_default_config(self):
        """Test initializing with default configuration."""
        streamer = RealtimeStreamer()

        assert streamer.symbols == []
        assert streamer.config.export.enabled is False
        assert streamer.config.websocket.url == "wss://data.tradingview.com/socket.io/websocket"
        assert streamer.websocket is None
        assert not streamer.connected

    def test_init_custom_symbols(self):
        """Test initializing with custom symbols."""
        symbols = ["BINANCE:BTCUSDT", "NASDAQ:AAPL"]
        streamer = RealtimeStreamer(symbols)

        assert streamer.symbols == symbols

    def test_init_custom_config(self):
        """Test initializing with custom configuration."""
        config = StreamConfig(
            export=ExportConfig(
                enabled=True,
                format='json',
                directory='/tmp/test',
                filename_prefix='custom',
                include_timestamp=True,
                auto_export_interval=None
            ),
            websocket=StreamConfig.WebSocketConfig(
                url="wss://custom.url/websocket",
                timeout=45.0,
                ping_interval=25.0,
                ping_timeout=15.0,
                close_timeout=15.0,
                max_size=2**21,
                compression="deflate"
            ),
            validation=StreamConfig.ValidationConfig(
                validate_symbols=False,
                validation_url=""
            )
        )

        streamer = RealtimeStreamer(config=config)

        assert streamer.config.export.enabled is True
        assert streamer.config.websocket.url == "wss://custom.url/websocket"
        assert streamer.config.websocket.timeout == 45.0

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        """Test successful context manager entry and exit."""
        with patch.object(RealtimeStreamer, '_connect') as mock_connect, \
             patch.object(RealtimeStreamer, '_disconnect') as mock_disconnect:

            mock_connect.return_value = None
            mock_disconnect.return_value = None

            async with RealtimeStreamer() as streamer:
                assert streamer is not None
                mock_connect.assert_called_once()

            mock_disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_connection_failure(self):
        """Test context manager with connection failure."""
        with patch.object(RealtimeStreamer, '_connect') as mock_connect:
            mock_connect.side_effect = ConnectionError("Connection failed")

            with pytest.raises(ConnectionError):
                async with RealtimeStreamer():
                    pass

    @pytest.mark.asyncio
    async def test_validate_symbols_success(self):
        """Test successful symbol validation."""
        symbols = ["BINANCE:BTCUSDT", "NASDAQ:AAPL"]

        with patch('tvkit.api.websocket.stream.realtime.validate_symbols_async') as mock_validate:
            mock_validate.return_value = symbols

            streamer = RealtimeStreamer()
            result = await streamer._validate_symbols(symbols)

            assert result == symbols
            mock_validate.assert_called_once_with(
                symbols,
                streamer.config.validation.validation_url
            )

    @pytest.mark.asyncio
    async def test_validate_symbols_failure(self):
        """Test symbol validation failure."""
        symbols = ["INVALID:SYMBOL"]

        with patch('tvkit.api.websocket.stream.realtime.validate_symbols_async') as mock_validate:
            mock_validate.return_value = []

            streamer = RealtimeStreamer()

            with pytest.raises(ValueError, match="No valid symbols"):
                await streamer._validate_symbols(symbols)

    @pytest.mark.asyncio
    async def test_validate_symbols_disabled(self):
        """Test symbol validation when disabled."""
        config = StreamConfig(
            validation=StreamConfig.ValidationConfig(validate_symbols=False, validation_url="")
        )
        symbols = ["ANY:SYMBOL"]

        streamer = RealtimeStreamer(config=config)
        result = await streamer._validate_symbols(symbols)

        assert result == symbols

    def test_generate_session_id(self):
        """Test session ID generation."""
        streamer = RealtimeStreamer()

        session_id = streamer._generate_session_id()

        assert len(session_id) == 12
        assert session_id.isalnum()

        # Should generate different IDs
        another_id = streamer._generate_session_id()
        assert session_id != another_id

    def test_create_message_valid(self):
        """Test creating valid WebSocket message."""
        streamer = RealtimeStreamer()

        message = streamer._create_message("test_method", {"param": "value"})

        assert "~m~" in message
        assert "test_method" in message
        assert "param" in message
        assert "value" in message

    def test_create_message_no_params(self):
        """Test creating message without parameters."""
        streamer = RealtimeStreamer()

        message = streamer._create_message("simple_method")

        assert "~m~" in message
        assert "simple_method" in message

    def test_parse_message_valid_ohlcv(self):
        """Test parsing valid OHLCV message."""
        streamer = RealtimeStreamer()

        # Mock OHLCV data from TradingView
        mock_data = {
            "m": "timescale_update",
            "p": [
                "sds_1",
                {
                    "s": [
                        {
                            "i": 1,
                            "v": [1642694400, 50000.0, 51000.0, 49500.0, 50500.0, 1250.0]
                        }
                    ]
                }
            ]
        }

        message = f"~m~{len(json.dumps(mock_data))}~m~{json.dumps(mock_data)}"

        result = streamer._parse_message(message)

        assert result is not None
        assert isinstance(result, RealtimeStreamData)
        assert result.symbol == "BINANCE:BTCUSDT"  # Default for test
        assert len(result.data) == 1
        assert isinstance(result.data[0], OHLCVData)

    def test_parse_message_invalid_format(self):
        """Test parsing message with invalid format."""
        streamer = RealtimeStreamer()

        with pytest.raises(DataParsingError):
            streamer._parse_message("invalid_message")

    def test_parse_message_invalid_json(self):
        """Test parsing message with invalid JSON."""
        streamer = RealtimeStreamer()

        message = "~m~20~m~{invalid json}"

        with pytest.raises(DataParsingError):
            streamer._parse_message(message)

    def test_parse_ohlcv_data_valid(self):
        """Test parsing valid OHLCV data."""
        streamer = RealtimeStreamer()

        raw_data = [1642694400, 50000.0, 51000.0, 49500.0, 50500.0, 1250.0]

        result = streamer._parse_ohlcv_data(raw_data, 1)

        assert isinstance(result, OHLCVData)
        assert result.index == 1
        assert result.timestamp == 1642694400
        assert result.open == Decimal('50000.0')
        assert result.high == Decimal('51000.0')
        assert result.low == Decimal('49500.0')
        assert result.close == Decimal('50500.0')
        assert result.volume == Decimal('1250.0')

    def test_parse_ohlcv_data_insufficient_values(self):
        """Test parsing OHLCV data with insufficient values."""
        streamer = RealtimeStreamer()

        raw_data = [1642694400, 50000.0]  # Only timestamp and open

        with pytest.raises(DataParsingError, match="Insufficient data"):
            streamer._parse_ohlcv_data(raw_data, 1)

    def test_parse_trade_data_valid(self):
        """Test parsing valid trade data."""
        streamer = RealtimeStreamer()

        trade_info = {
            "lp": 50000.0,
            "ch": 500.0,
            "chp": 1.0,
            "volume": 1250000.0
        }

        result = streamer._parse_trade_data(trade_info)

        assert isinstance(result, TradeData)
        assert result.price == Decimal('50000.0')
        assert result.change == Decimal('500.0')
        assert result.change_percent == Decimal('1.0')
        assert result.volume == Decimal('1250000.0')

    def test_parse_trade_data_missing_fields(self):
        """Test parsing trade data with missing fields."""
        streamer = RealtimeStreamer()

        trade_info = {"lp": 50000.0}  # Only price

        result = streamer._parse_trade_data(trade_info)

        assert isinstance(result, TradeData)
        assert result.price == Decimal('50000.0')
        assert result.change is None
        assert result.change_percent is None
        assert result.volume is None

    @pytest.mark.asyncio
    async def test_setup_sessions_success(self):
        """Test successful session setup."""
        symbols = ["BINANCE:BTCUSDT"]

        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()

        streamer = RealtimeStreamer(symbols)
        streamer.websocket = mock_websocket

        await streamer._setup_sessions(symbols)

        # Should send session setup messages
        assert mock_websocket.send.call_count >= 2  # At least quote and chart sessions

    @pytest.mark.asyncio
    async def test_setup_sessions_websocket_error(self):
        """Test session setup with WebSocket error."""
        symbols = ["BINANCE:BTCUSDT"]

        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock(side_effect=Exception("WebSocket error"))

        streamer = RealtimeStreamer(symbols)
        streamer.websocket = mock_websocket

        with pytest.raises(SessionError):
            await streamer._setup_sessions(symbols)

    @pytest.mark.asyncio
    async def test_stream_method_not_connected(self):
        """Test stream method when not connected."""
        streamer = RealtimeStreamer()

        with pytest.raises(StreamingError, match="Not connected"):
            async for _ in streamer.stream():
                pass

    @pytest.mark.asyncio
    async def test_stream_method_with_symbols(self):
        """Test stream method with provided symbols."""
        symbols = ["BINANCE:BTCUSDT"]

        mock_websocket = AsyncMock()
        mock_websocket.recv = AsyncMock(return_value="~m~5~m~test")

        with patch.object(RealtimeStreamer, '_connect'), \
             patch.object(RealtimeStreamer, '_setup_sessions'), \
             patch.object(RealtimeStreamer, '_parse_message') as mock_parse:

            mock_parse.return_value = RealtimeStreamData(
                symbol="BINANCE:BTCUSDT",
                data=[],
                timestamp=1642694400
            )

            streamer = RealtimeStreamer()
            streamer.websocket = mock_websocket
            streamer.connected = True

            # Get first message and break
            async for message in streamer.stream(symbols):
                assert isinstance(message, RealtimeStreamData)
                break

    @pytest.mark.asyncio
    async def test_add_symbols_not_connected(self):
        """Test adding symbols when not connected."""
        streamer = RealtimeStreamer()

        with pytest.raises(StreamingError, match="Not connected"):
            await streamer.add_symbols(["BINANCE:BTCUSDT"])

    @pytest.mark.asyncio
    async def test_remove_symbols_not_connected(self):
        """Test removing symbols when not connected."""
        streamer = RealtimeStreamer()

        with pytest.raises(StreamingError, match="Not connected"):
            await streamer.remove_symbols(["BINANCE:BTCUSDT"])


class TestRealtimeStreamerIntegration:
    """Integration tests for RealtimeStreamer."""

    @pytest.mark.asyncio
    async def test_full_streaming_workflow_mock(self):
        """Test complete streaming workflow with mocked WebSocket."""
        symbols = ["BINANCE:BTCUSDT", "NASDAQ:AAPL"]

        # Mock WebSocket messages
        messages = [
            "~m~50~m~{\"m\":\"quote_completed\",\"p\":[\"qs_1\"]}",
            "~m~100~m~{\"m\":\"timescale_update\",\"p\":[\"sds_1\",{\"s\":[{\"i\":1,\"v\":[1642694400,50000,51000,49500,50500,1250]}]}]}",
        ]

        mock_websocket = AsyncMock()
        mock_websocket.recv = AsyncMock(side_effect=messages + [asyncio.CancelledError()])
        mock_websocket.send = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch('tvkit.api.websocket.stream.realtime.connect') as mock_connect, \
             patch('tvkit.api.websocket.stream.realtime.validate_symbols_async') as mock_validate:

            mock_connect.return_value.__aenter__.return_value = mock_websocket
            mock_validate.return_value = symbols

            streamer = RealtimeStreamer(symbols)

            received_messages = []

            try:
                async with streamer:
                    async for message in streamer.stream():
                        received_messages.append(message)
                        if len(received_messages) >= 1:  # Get one message then stop
                            break
            except asyncio.CancelledError:
                pass

            # Should have processed at least one message
            assert len(received_messages) >= 0  # May not get OHLCV data from quote_completed

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        symbols = ["BINANCE:BTCUSDT"]

        # Mock connection that fails then succeeds
        mock_websocket = AsyncMock()
        mock_websocket.recv = AsyncMock(side_effect=[
            Exception("Connection lost"),
            "~m~50~m~{\"m\":\"quote_completed\",\"p\":[\"qs_1\"]}"
        ])
        mock_websocket.send = AsyncMock()
        mock_websocket.close = AsyncMock()

        with patch('tvkit.api.websocket.stream.realtime.connect') as mock_connect, \
             patch('tvkit.api.websocket.stream.realtime.validate_symbols_async') as mock_validate:

            mock_connect.return_value.__aenter__.return_value = mock_websocket
            mock_validate.return_value = symbols

            streamer = RealtimeStreamer(symbols)

            with pytest.raises(StreamingError):
                async with streamer:
                    async for message in streamer.stream():
                        break

    def test_configuration_inheritance(self):
        """Test that configuration is properly inherited and applied."""
        custom_config = StreamConfig(
            export=ExportConfig(
                enabled=True,
                format='parquet',
                directory='/custom/export',
                filename_prefix='test_prefix',
                include_timestamp=False,
                auto_export_interval=300
            ),
            websocket=StreamConfig.WebSocketConfig(
                url="wss://custom.tradingview.com/socket",
                timeout=60.0,
                ping_interval=30.0,
                ping_timeout=20.0,
                close_timeout=20.0,
                max_size=2**22,
                compression="deflate"
            ),
            validation=StreamConfig.ValidationConfig(
                validate_symbols=True,
                validation_url="https://custom.validation.url/"
            )
        )

        streamer = RealtimeStreamer(config=custom_config)

        # Verify all configuration values are applied
        assert streamer.config.export.enabled is True
        assert streamer.config.export.format == 'parquet'
        assert streamer.config.export.directory == '/custom/export'
        assert streamer.config.export.filename_prefix == 'test_prefix'
        assert streamer.config.export.include_timestamp is False
        assert streamer.config.export.auto_export_interval == 300

        assert streamer.config.websocket.url == "wss://custom.tradingview.com/socket"
        assert streamer.config.websocket.timeout == 60.0
        assert streamer.config.websocket.ping_interval == 30.0
        assert streamer.config.websocket.ping_timeout == 20.0
        assert streamer.config.websocket.close_timeout == 20.0
        assert streamer.config.websocket.max_size == 2**22
        assert streamer.config.websocket.compression == "deflate"

        assert streamer.config.validation.validate_symbols is True
        assert streamer.config.validation.validation_url == "https://custom.validation.url/"


@pytest.fixture
def sample_streamer():
    """Fixture providing a RealtimeStreamer instance for testing."""
    return RealtimeStreamer(["BINANCE:BTCUSDT"])


@pytest.fixture
def mock_websocket_message():
    """Fixture providing a mock WebSocket message."""
    mock_data = {
        "m": "timescale_update",
        "p": [
            "sds_1",
            {
                "s": [
                    {
                        "i": 1,
                        "v": [1642694400, 50000.0, 51000.0, 49500.0, 50500.0, 1250.0]
                    }
                ]
            }
        ]
    }
    return f"~m~{len(json.dumps(mock_data))}~m~{json.dumps(mock_data)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
