"""
Pydantic models for real-time WebSocket streaming data.

This module provides type-safe data models for all real-time streaming
operations including OHLCV data, trade information, and WebSocket messages.
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OHLCVData(BaseModel):
    """
    Model for OHLCV (Open, High, Low, Close, Volume) market data.

    Represents a single candlestick/bar of market data with timestamp,
    price information, and trading volume.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=True,
    )

    index: int = Field(..., description="Data point index")
    timestamp: int = Field(..., description="Unix timestamp in seconds", gt=0)
    open: Decimal = Field(..., description="Opening price", ge=0)
    high: Decimal = Field(..., description="Highest price", ge=0)
    low: Decimal = Field(..., description="Lowest price", ge=0)
    close: Decimal = Field(..., description="Closing price", ge=0)
    volume: Decimal = Field(..., description="Trading volume", ge=0)

    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime object."""
        return datetime.fromtimestamp(self.timestamp)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with string values for JSON serialization."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "datetime": self.datetime.isoformat(),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": str(self.volume),
        }


class TradeData(BaseModel):
    """
    Model for individual trade information.

    Represents a single trade execution with price, volume, and timing data.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=True,
    )

    symbol: str = Field(..., description="Trading symbol (e.g., BINANCE:BTCUSDT)")
    price: Decimal = Field(..., description="Trade execution price", ge=0)
    volume: Decimal = Field(..., description="Trade volume", ge=0)
    timestamp: int = Field(..., description="Trade timestamp", gt=0)
    side: Optional[Literal["buy", "sell"]] = Field(None, description="Trade side")

    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime object."""
        return datetime.fromtimestamp(self.timestamp)


class IndicatorData(BaseModel):
    """
    Model for technical indicator data.

    Represents calculated technical indicator values with metadata.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=True,
    )

    indicator_id: str = Field(..., description="Unique indicator identifier")
    indicator_version: str = Field(..., description="Indicator version")
    timestamp: int = Field(..., description="Calculation timestamp", gt=0)
    values: Dict[str, Decimal] = Field(..., description="Indicator output values")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime object."""
        return datetime.fromtimestamp(self.timestamp)


class SymbolInfo(BaseModel):
    """
    Model for symbol validation and information.

    Contains validated symbol data and market information.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=True,
    )

    exchange: str = Field(..., description="Exchange name (e.g., BINANCE)")
    symbol: str = Field(..., description="Symbol name (e.g., BTCUSDT)")
    full_symbol: str = Field(..., description="Full symbol (e.g., BINANCE:BTCUSDT)")
    market: Optional[str] = Field(None, description="Market category")
    is_valid: bool = Field(..., description="Symbol validation status")


class SessionInfo(BaseModel):
    """
    Model for WebSocket session information.

    Contains session identifiers and connection metadata.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    quote_session: str = Field(..., description="Quote session identifier")
    chart_session: str = Field(..., description="Chart session identifier")
    jwt_token: str = Field(..., description="JWT authentication token")
    connection_id: Optional[str] = Field(None, description="Connection identifier")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Session creation time"
    )


class WebSocketMessage(BaseModel):
    """
    Model for WebSocket message structure.

    Represents formatted messages for TradingView WebSocket protocol.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    method: str = Field(..., description="WebSocket method name")
    params: List[Any] = Field(..., description="Method parameters")
    message_id: Optional[str] = Field(None, description="Message identifier")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Message timestamp"
    )

    def format_message(self) -> str:
        """Format message for WebSocket transmission."""
        # Properly serialize the entire message as JSON
        message_data = {"m": self.method, "p": self.params}
        message_json = json.dumps(message_data, separators=(",", ":"))
        message_length = len(message_json)
        return f"~m~{message_length}~m~{message_json}"


class ExportConfig(BaseModel):
    """
    Model for data export configuration.

    Defines export settings including format, destination, and options.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    enabled: bool = Field(False, description="Whether export is enabled")
    format: Literal["json", "csv", "parquet"] = Field(
        "json", description="Export format"
    )
    directory: str = Field("/export", description="Export directory path")
    filename_prefix: Optional[str] = Field(None, description="Filename prefix")
    include_timestamp: bool = Field(True, description="Include timestamp in filename")
    auto_export_interval: Optional[int] = Field(
        None, description="Auto-export interval in seconds"
    )


class StreamConfig(BaseModel):
    """
    Model for real-time stream configuration.

    Contains all settings for WebSocket streaming operations.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    symbols: List[str] = Field(
        ..., description="List of symbols to stream", min_length=1
    )
    timeframe: str = Field("1m", description="Data timeframe (e.g., 1m, 5m, 1h)")
    num_candles: int = Field(
        10, description="Number of historical candles", ge=1, le=1000
    )
    include_indicators: bool = Field(False, description="Whether to include indicators")
    indicator_id: Optional[str] = Field(None, description="Indicator ID if enabled")
    indicator_version: Optional[str] = Field(
        None, description="Indicator version if enabled"
    )
    export_config: Optional[ExportConfig] = Field(None, description="Export settings")

    @field_validator("symbols")
    @classmethod
    def validate_symbol_format(cls, v: List[str]) -> List[str]:
        """Validate symbol format for all symbols."""
        for symbol in v:
            if ":" not in symbol:
                raise ValueError(
                    f"Invalid symbol format '{symbol}'. Must be like 'BINANCE:BTCUSDT'"
                )
            if len(symbol.split(":")) != 2:
                raise ValueError(
                    f"Invalid symbol format '{symbol}'. Must have exactly one ':' separator"
                )
        return v

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Validate timeframe format."""
        valid_timeframes: List[str] = [
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
        if v not in valid_timeframes:
            raise ValueError(
                f"Invalid timeframe '{v}'. Must be one of: {valid_timeframes}"
            )
        return v


class StreamerResponse(BaseModel):
    """
    Model for streamer response data.

    Contains processed streaming data ready for consumption.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    symbol: str = Field(..., description="Source symbol")
    data_type: Literal["ohlcv", "trade", "indicator"] = Field(
        ..., description="Type of data"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp"
    )
    ohlcv_data: Optional[List[OHLCVData]] = Field(
        None, description="OHLCV data if applicable"
    )
    trade_data: Optional[TradeData] = Field(
        None, description="Trade data if applicable"
    )
    indicator_data: Optional[IndicatorData] = Field(
        None, description="Indicator data if applicable"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional response metadata"
    )


class RealtimeStreamData(BaseModel):
    """
    Model for complete real-time stream data package.

    Aggregates all streaming information in a single response object.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    session_info: SessionInfo = Field(..., description="Session information")
    config: StreamConfig = Field(..., description="Stream configuration")
    responses: List[StreamerResponse] = Field(
        default_factory=list, description="Stream responses"
    )
    connection_status: Literal["connected", "disconnected", "error"] = Field(
        "disconnected", description="Connection status"
    )
    error_message: Optional[str] = Field(None, description="Error message if any")
    last_update: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )

    def add_response(self, response: StreamerResponse) -> None:
        """Add a new response to the stream data."""
        self.responses.append(response)
        self.last_update = datetime.now()

    def get_latest_ohlcv(
        self, symbol: Optional[str] = None
    ) -> Optional[List[OHLCVData]]:
        """Get the latest OHLCV data for a symbol or all symbols."""
        ohlcv_responses: List[StreamerResponse] = [
            r
            for r in self.responses
            if r.data_type == "ohlcv" and (symbol is None or r.symbol == symbol)
        ]

        if not ohlcv_responses:
            return None

        latest_response: StreamerResponse = max(
            ohlcv_responses, key=lambda x: x.timestamp
        )
        return latest_response.ohlcv_data

    def get_statistics(self) -> Dict[str, Any]:
        """Get streaming statistics."""
        return {
            "total_responses": len(self.responses),
            "ohlcv_count": len([r for r in self.responses if r.data_type == "ohlcv"]),
            "trade_count": len([r for r in self.responses if r.data_type == "trade"]),
            "indicator_count": len(
                [r for r in self.responses if r.data_type == "indicator"]
            ),
            "unique_symbols": len(set(r.symbol for r in self.responses)),
            "session_duration": (
                self.last_update - self.session_info.created_at
            ).total_seconds(),
            "connection_status": self.connection_status,
        }
