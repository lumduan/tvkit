"""
WebSocket stream API for real-time data streaming.

This module provides comprehensive functionality for streaming real-time market data
from TradingView, including OHLCV data, trade information, and technical indicators.
"""

from .realtime import RealtimeStreamer
from .models import (
    OHLCVData,
    TradeData,
    IndicatorData,
    StreamConfig,
    SessionInfo,
    WebSocketMessage,
    StreamerResponse,
    RealtimeStreamData,
    ExportConfig,
    SymbolInfo,
)
from .exceptions import (
    StreamingError,
    ConnectionError,
    SymbolValidationError,
    DataParsingError,
    SessionError,
    ExportError,
    RateLimitError,
    ConfigurationError,
    DataNotFoundError,
    TimeoutError,
    AuthenticationError,
    ValidationError,
)
from .utils import (
    export_data,
    generate_session_id,
    validate_symbols_async,
    OHLCVConverter,
    save_json_file,
    save_csv_file,
    save_parquet_file,
    ensure_export_directory,
    generate_export_filepath,
)

__all__ = [
    # Main streamer class
    "RealtimeStreamer",

    # Data models
    "OHLCVData",
    "TradeData",
    "IndicatorData",
    "StreamConfig",
    "SessionInfo",
    "WebSocketMessage",
    "StreamerResponse",
    "RealtimeStreamData",
    "ExportConfig",
    "SymbolInfo",

    # Exceptions
    "StreamingError",
    "ConnectionError",
    "SymbolValidationError",
    "DataParsingError",
    "SessionError",
    "ExportError",
    "RateLimitError",
    "ConfigurationError",
    "DataNotFoundError",
    "TimeoutError",
    "AuthenticationError",
    "ValidationError",

    # Utilities
    "export_data",
    "generate_session_id",
    "validate_symbols_async",
    "OHLCVConverter",
    "save_json_file",
    "save_csv_file",
    "save_parquet_file",
    "ensure_export_directory",
    "generate_export_filepath",
]
