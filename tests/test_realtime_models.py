"""
Tests for real-time WebSocket streaming models.

This module provides comprehensive tests for all Pydantic models used in
real-time streaming operations including validation, serialization, and error handling.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from typing import List

from tvkit.api.chart.models import (
    OHLCVData,
    TradeData,
    IndicatorData,
    SymbolInfo,
    SessionInfo,
    WebSocketMessage,
    ExportConfig,
    StreamConfig,
    StreamerResponse,
    RealtimeStreamData,
)


class TestOHLCVData:
    """Test cases for OHLCVData model."""

    def test_valid_ohlcv_creation(self):
        """Test creating valid OHLCV data."""
        ohlcv = OHLCVData(
            index=1,
            timestamp=1642694400,  # 2022-01-20 12:00:00 UTC
            open=Decimal("50000.50"),
            high=Decimal("51000.75"),
            low=Decimal("49500.25"),
            close=Decimal("50500.00"),
            volume=Decimal("1250.5"),
        )

        assert ohlcv.index == 1
        assert ohlcv.timestamp == 1642694400
        assert ohlcv.open == Decimal("50000.50")
        assert ohlcv.high == Decimal("51000.75")
        assert ohlcv.low == Decimal("49500.25")
        assert ohlcv.close == Decimal("50500.00")
        assert ohlcv.volume == Decimal("1250.5")

    def test_datetime_property(self):
        """Test datetime property conversion."""
        ohlcv = OHLCVData(
            index=1,
            timestamp=1642694400,
            open=Decimal("50000"),
            high=Decimal("51000"),
            low=Decimal("49500"),
            close=Decimal("50500"),
            volume=Decimal("1250"),
        )

        dt = ohlcv.datetime
        assert isinstance(dt, datetime)
        assert dt.year == 2022
        assert dt.month == 1
        assert dt.day == 20

    def test_to_dict_method(self):
        """Test dictionary conversion method."""
        ohlcv = OHLCVData(
            index=1,
            timestamp=1642694400,
            open=Decimal("50000.50"),
            high=Decimal("51000.75"),
            low=Decimal("49500.25"),
            close=Decimal("50500.00"),
            volume=Decimal("1250.5"),
        )

        result = ohlcv.to_dict()

        assert isinstance(result, dict)
        assert result["index"] == 1
        assert result["timestamp"] == 1642694400
        assert "datetime" in result
        assert result["open"] == "50000.50"
        assert result["high"] == "51000.75"
        assert result["low"] == "49500.25"
        assert result["close"] == "50500.00"
        assert result["volume"] == "1250.5"

    def test_negative_values_validation(self):
        """Test validation of negative values."""
        with pytest.raises(ValueError):
            OHLCVData(
                index=1,
                timestamp=1642694400,
                open=Decimal("-50000"),  # Negative price should fail
                high=Decimal("51000"),
                low=Decimal("49500"),
                close=Decimal("50500"),
                volume=Decimal("1250"),
            )

    def test_zero_timestamp_validation(self):
        """Test validation of zero timestamp."""
        with pytest.raises(ValueError):
            OHLCVData(
                index=1,
                timestamp=0,  # Zero timestamp should fail
                open=Decimal("50000"),
                high=Decimal("51000"),
                low=Decimal("49500"),
                close=Decimal("50500"),
                volume=Decimal("1250"),
            )


class TestTradeData:
    """Test cases for TradeData model."""

    def test_valid_trade_creation(self):
        """Test creating valid trade data."""
        trade = TradeData(
            symbol="BINANCE:BTCUSDT",
            price=Decimal("50000.50"),
            volume=Decimal("0.125"),
            timestamp=1642694400,
            side="buy",
        )

        assert trade.symbol == "BINANCE:BTCUSDT"
        assert trade.price == Decimal("50000.50")
        assert trade.volume == Decimal("0.125")
        assert trade.timestamp == 1642694400
        assert trade.side == "buy"

    def test_trade_without_side(self):
        """Test creating trade data without side information."""
        trade = TradeData(
            symbol="BINANCE:BTCUSDT",
            price=Decimal("50000.50"),
            volume=Decimal("0.125"),
            timestamp=1642694400,
            side=None,  # Explicitly set to None
        )

        assert trade.side is None

    def test_datetime_property(self):
        """Test datetime property conversion."""
        trade = TradeData(
            symbol="BINANCE:BTCUSDT",
            price=Decimal("50000"),
            volume=Decimal("0.125"),
            timestamp=1642694400,
            side=None,
        )

        dt = trade.datetime
        assert isinstance(dt, datetime)


class TestIndicatorData:
    """Test cases for IndicatorData model."""

    def test_valid_indicator_creation(self):
        """Test creating valid indicator data."""
        indicator = IndicatorData(
            indicator_id="RSI",
            indicator_version="1.0",
            timestamp=1642694400,
            values={"rsi": Decimal("65.5"), "signal": Decimal("1")},
            metadata={"period": 14},
        )

        assert indicator.indicator_id == "RSI"
        assert indicator.indicator_version == "1.0"
        assert indicator.values["rsi"] == Decimal("65.5")
        assert indicator.metadata is not None
        assert indicator.metadata["period"] == 14


class TestSymbolInfo:
    """Test cases for SymbolInfo model."""

    def test_valid_symbol_creation(self):
        """Test creating valid symbol info."""
        symbol_info = SymbolInfo(
            exchange="BINANCE",
            symbol="BTCUSDT",
            full_symbol="BINANCE:BTCUSDT",
            market="crypto",
            is_valid=True,
        )

        assert symbol_info.exchange == "BINANCE"
        assert symbol_info.symbol == "BTCUSDT"
        assert symbol_info.full_symbol == "BINANCE:BTCUSDT"
        assert symbol_info.is_valid is True


class TestSessionInfo:
    """Test cases for SessionInfo model."""

    def test_valid_session_creation(self):
        """Test creating valid session info."""
        session = SessionInfo(
            quote_session="qs_12345",
            chart_session="cs_67890",
            jwt_token="test_token",
            connection_id="conn_123",
        )

        assert session.quote_session == "qs_12345"
        assert session.chart_session == "cs_67890"
        assert session.jwt_token == "test_token"
        assert session.connection_id == "conn_123"
        assert isinstance(session.created_at, datetime)


class TestWebSocketMessage:
    """Test cases for WebSocketMessage model."""

    def test_valid_message_creation(self):
        """Test creating valid WebSocket message."""
        message = WebSocketMessage(
            method="quote_add_symbols",
            params=["session_123", "BINANCE:BTCUSDT"],
            message_id="msg_001",
        )

        assert message.method == "quote_add_symbols"
        assert message.params == ["session_123", "BINANCE:BTCUSDT"]
        assert message.message_id == "msg_001"

    def test_format_message_method(self):
        """Test message formatting method."""
        message = WebSocketMessage(
            method="test_method", params=["param1", "param2"], message_id="msg_002"
        )

        formatted = message.format_message()
        assert isinstance(formatted, str)
        assert "test_method" in formatted
        assert "param1" in formatted
        assert "param2" in formatted


class TestExportConfig:
    """Test cases for ExportConfig model."""

    def test_default_export_config(self):
        """Test default export configuration."""
        config = ExportConfig(
            enabled=False,
            format="json",
            directory="/export",
            filename_prefix=None,
            include_timestamp=True,
            auto_export_interval=None,
        )

        assert config.enabled is False
        assert config.format == "json"
        assert config.directory == "/export"
        assert config.include_timestamp is True

    def test_custom_export_config(self):
        """Test custom export configuration."""
        config = ExportConfig(
            enabled=True,
            format="csv",
            directory="/custom/path",
            filename_prefix="data",
            include_timestamp=False,
            auto_export_interval=60,
        )

        assert config.enabled is True
        assert config.format == "csv"
        assert config.directory == "/custom/path"
        assert config.filename_prefix == "data"
        assert config.include_timestamp is False
        assert config.auto_export_interval == 60


class TestStreamConfig:
    """Test cases for StreamConfig model."""

    def test_valid_stream_config(self):
        """Test creating valid stream configuration."""
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT", "NASDAQ:AAPL"],
            timeframe="1m",
            num_candles=50,
            include_indicators=False,
            indicator_id=None,
            indicator_version=None,
            export_config=None,
        )

        assert len(config.symbols) == 2
        assert "BINANCE:BTCUSDT" in config.symbols
        assert config.timeframe == "1m"
        assert config.num_candles == 50
        assert config.include_indicators is False

    def test_symbol_validation(self):
        """Test symbol format validation."""
        with pytest.raises(ValueError, match="Invalid symbol format"):
            StreamConfig(
                symbols=["INVALID_SYMBOL"],  # Missing colon
                timeframe="1m",
                num_candles=10,
                include_indicators=False,
                indicator_id=None,
                indicator_version=None,
                export_config=None,
            )

    def test_timeframe_validation(self):
        """Test timeframe validation."""
        with pytest.raises(ValueError, match="Invalid timeframe"):
            StreamConfig(
                symbols=["BINANCE:BTCUSDT"],
                timeframe="invalid_tf",  # Invalid timeframe
                num_candles=10,
                include_indicators=False,
                indicator_id=None,
                indicator_version=None,
                export_config=None,
            )

    def test_valid_timeframes(self):
        """Test all valid timeframes."""
        valid_timeframes = [
            "1m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "1d",
            "1w",
            "1M",
        ]

        for tf in valid_timeframes:
            config = StreamConfig(
                symbols=["BINANCE:BTCUSDT"],
                timeframe=tf,
                num_candles=10,
                include_indicators=False,
                indicator_id=None,
                indicator_version=None,
                export_config=None,
            )
            assert config.timeframe == tf


class TestStreamerResponse:
    """Test cases for StreamerResponse model."""

    def test_ohlcv_response(self):
        """Test creating OHLCV response."""
        ohlcv_data = [
            OHLCVData(
                index=1,
                timestamp=1642694400,
                open=Decimal("50000"),
                high=Decimal("51000"),
                low=Decimal("49500"),
                close=Decimal("50500"),
                volume=Decimal("1250"),
            )
        ]

        response = StreamerResponse(
            symbol="BINANCE:BTCUSDT",
            data_type="ohlcv",
            ohlcv_data=ohlcv_data,
            trade_data=None,
            indicator_data=None,
            metadata={},
        )

        assert response.symbol == "BINANCE:BTCUSDT"
        assert response.data_type == "ohlcv"
        assert response.ohlcv_data is not None
        assert len(response.ohlcv_data) == 1
        assert response.trade_data is None
        assert response.indicator_data is None

    def test_trade_response(self):
        """Test creating trade response."""
        trade_data = TradeData(
            symbol="BINANCE:BTCUSDT",
            price=Decimal("50000"),
            volume=Decimal("0.125"),
            timestamp=1642694400,
            side=None,
        )

        response = StreamerResponse(
            symbol="BINANCE:BTCUSDT",
            data_type="trade",
            ohlcv_data=None,
            trade_data=trade_data,
            indicator_data=None,
            metadata={},
        )

        assert response.data_type == "trade"
        assert response.trade_data is not None
        assert response.ohlcv_data is None


class TestRealtimeStreamData:
    """Test cases for RealtimeStreamData model."""

    def test_valid_stream_data_creation(self):
        """Test creating valid stream data."""
        session_info = SessionInfo(
            quote_session="qs_123",
            chart_session="cs_456",
            jwt_token="token",
            connection_id="conn_789",
        )

        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=10,
            include_indicators=False,
            indicator_id=None,
            indicator_version=None,
            export_config=None,
        )

        stream_data = RealtimeStreamData(
            session_info=session_info,
            config=config,
            connection_status="disconnected",
            error_message=None,
        )

        assert stream_data.session_info.quote_session == "qs_123"
        assert stream_data.config.timeframe == "1m"
        assert stream_data.connection_status == "disconnected"
        assert len(stream_data.responses) == 0

    def test_add_response(self):
        """Test adding responses to stream data."""
        session_info = SessionInfo(
            quote_session="qs_123",
            chart_session="cs_456",
            jwt_token="token",
            connection_id="conn_789",
        )

        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=10,
            include_indicators=False,
            indicator_id=None,
            indicator_version=None,
            export_config=None,
        )

        stream_data = RealtimeStreamData(
            session_info=session_info,
            config=config,
            connection_status="connected",
            error_message=None,
        )

        response = StreamerResponse(
            symbol="BINANCE:BTCUSDT",
            data_type="trade",
            ohlcv_data=None,
            trade_data=TradeData(
                symbol="BINANCE:BTCUSDT",
                price=Decimal("50000"),
                volume=Decimal("0.125"),
                timestamp=1642694400,
                side=None,
            ),
            indicator_data=None,
            metadata={},
        )

        stream_data.add_response(response)

        assert len(stream_data.responses) == 1
        assert stream_data.responses[0].symbol == "BINANCE:BTCUSDT"

    def test_get_statistics(self):
        """Test getting stream statistics."""
        session_info = SessionInfo(
            quote_session="qs_123",
            chart_session="cs_456",
            jwt_token="token",
            connection_id="conn_789",
        )

        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=10,
            include_indicators=False,
            indicator_id=None,
            indicator_version=None,
            export_config=None,
        )

        stream_data = RealtimeStreamData(
            session_info=session_info,
            config=config,
            connection_status="disconnected",
            error_message=None,
        )

        stats = stream_data.get_statistics()

        assert isinstance(stats, dict)
        assert "total_responses" in stats
        assert "connection_status" in stats
        assert stats["total_responses"] == 0
        assert stats["connection_status"] == "disconnected"


@pytest.fixture
def sample_ohlcv_data() -> List[OHLCVData]:
    """Fixture providing sample OHLCV data for testing."""
    return [
        OHLCVData(
            index=i,
            timestamp=1642694400 + i * 60,  # 1 minute intervals
            open=Decimal(f"{50000 + i * 10}"),
            high=Decimal(f"{50100 + i * 10}"),
            low=Decimal(f"{49900 + i * 10}"),
            close=Decimal(f"{50050 + i * 10}"),
            volume=Decimal(f"{1000 + i * 50}"),
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_stream_config() -> StreamConfig:
    """Fixture providing sample stream configuration for testing."""
    return StreamConfig(
        symbols=["BINANCE:BTCUSDT", "NASDAQ:AAPL"],
        timeframe="1m",
        num_candles=50,
        include_indicators=False,
        indicator_id=None,
        indicator_version=None,
        export_config=ExportConfig(
            enabled=True,
            format="json",
            directory="/tmp/test_export",
            filename_prefix=None,
            include_timestamp=True,
            auto_export_interval=None,
        ),
    )


class TestIntegration:
    """Integration tests for model interactions."""

    def test_complete_streaming_workflow(
        self, sample_stream_config: StreamConfig, sample_ohlcv_data: List[OHLCVData]
    ):
        """Test complete streaming workflow with all models."""
        # Create session
        session_info = SessionInfo(
            quote_session="qs_integration_test",
            chart_session="cs_integration_test",
            jwt_token="integration_token",
            connection_id="conn_integration",
        )

        # Create stream data container
        stream_data = RealtimeStreamData(
            session_info=session_info,
            config=sample_stream_config,
            connection_status="connected",
            error_message=None,
        )

        # Add OHLCV response
        ohlcv_response = StreamerResponse(
            symbol="BINANCE:BTCUSDT",
            data_type="ohlcv",
            ohlcv_data=sample_ohlcv_data,
            trade_data=None,
            indicator_data=None,
            metadata={},
        )

        stream_data.add_response(ohlcv_response)

        # Add trade response
        trade_response = StreamerResponse(
            symbol="BINANCE:BTCUSDT",
            data_type="trade",
            ohlcv_data=None,
            trade_data=TradeData(
                symbol="BINANCE:BTCUSDT",
                price=Decimal("50125.75"),
                volume=Decimal("0.5"),
                timestamp=1642694700,
                side="buy",
            ),
            indicator_data=None,
            metadata={},
        )

        stream_data.add_response(trade_response)

        # Verify statistics
        stats = stream_data.get_statistics()
        assert stats["total_responses"] == 2
        assert stats["ohlcv_count"] == 1
        assert stats["trade_count"] == 1
        assert stats["unique_symbols"] == 1

        # Verify latest OHLCV data
        latest_ohlcv = stream_data.get_latest_ohlcv("BINANCE:BTCUSDT")
        assert latest_ohlcv is not None
        assert len(latest_ohlcv) == 5

    def test_model_serialization(self, sample_ohlcv_data: List[OHLCVData]):
        """Test model serialization for JSON export."""
        ohlcv = sample_ohlcv_data[0]

        # Test to_dict method
        dict_data = ohlcv.to_dict()
        assert isinstance(dict_data, dict)
        assert all(isinstance(v, (str, int, float)) for v in dict_data.values())

        # Verify data integrity
        assert dict_data["index"] == ohlcv.index
        assert dict_data["timestamp"] == ohlcv.timestamp
        assert dict_data["open"] == str(ohlcv.open)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
