"""
TVKit - TradingView API Integration Library

A comprehensive Python library for interacting with TradingView's financial data APIs,
providing real-time streaming, historical data, and multi-market scanning capabilities.

Quick Start:
    >>> import asyncio
    >>> from tvkit import OHLCV
    >>>
    >>> async def get_apple_data():
    ...     async with OHLCV() as client:
    ...         bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", 5)
    ...         return bars
    >>>
    >>> data = asyncio.run(get_apple_data())
"""

__version__ = "0.1.4"
__author__ = "lumduan"
__license__ = "MIT"

# Core API exports for easy importing
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.utils import convert_timestamp_to_iso, validate_symbols
from tvkit.export import DataExporter, ExportConfig, ExportFormat

# Quick start utilities for easy access
from tvkit.quickstart import (
    FOREX_PAIRS,
    MAJOR_CRYPTOS,
    POPULAR_STOCKS,
    compare_stocks,
    get_crypto_prices,
    get_historical_data,
    get_stock_price,
    quick_export_to_csv,
    run_async,
)

# Scanner API exports
try:
    from tvkit.api.scanner import Market, MarketRegion, ScannerService  # noqa: F401
    from tvkit.api.scanner.markets import get_markets_by_region  # noqa: F401
    from tvkit.api.scanner.models.scanner import (  # noqa: F401
        ColumnSets,
        ScannerRequest,
        ScannerResponse,
    )

    scanner_available = True
except ImportError:
    scanner_available = False

__all__ = [
    # Core exports
    "__version__",
    "__author__",
    "__license__",
    # Main API classes
    "OHLCV",
    "DataExporter",
    "ExportFormat",
    "ExportConfig",
    # Utility functions
    "convert_timestamp_to_iso",
    "validate_symbols",
    # Quick start functions
    "get_stock_price",
    "compare_stocks",
    "get_crypto_prices",
    "get_historical_data",
    "quick_export_to_csv",
    "run_async",
    # Pre-defined symbol lists
    "POPULAR_STOCKS",
    "MAJOR_CRYPTOS",
    "FOREX_PAIRS",
]

# Add scanner exports if available
if scanner_available:
    __all__.extend(
        [
            "ScannerService",
            "Market",
            "MarketRegion",
            "ScannerRequest",
            "ScannerResponse",
            "ColumnSets",
            "get_markets_by_region",
        ]
    )
