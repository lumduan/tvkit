"""
tvkit export module for financial data export functionality.

This module provides a unified interface for exporting financial data
from tvkit APIs to various formats including Polars DataFrames, JSON, CSV,
and more. It supports both OHLCV chart data and scanner market data.

Main Components:
- DataExporter: Primary export interface
- ExportFormat: Supported export formats
- ExportConfig: Configuration options for exports
- Various formatters for different output formats

Example Usage:
    >>> from tvkit.export import DataExporter, ExportFormat
    >>> from tvkit.api.chart.ohlcv import OHLCV
    >>>
    >>> # Get OHLCV data
    >>> async with OHLCV() as client:
    ...     bars = await client.get_historical_ohlcv("BINANCE:BTCUSDT", "1m", 100)
    ...
    ...     # Initialize exporter
    ...     exporter = DataExporter()
    ...
    ...     # Export to different formats
    ...     df = await exporter.to_polars(bars, add_analysis=True)
    ...     json_file = await exporter.to_json(bars, "btc_data.json")
    ...     csv_file = await exporter.to_csv(bars, "btc_data.csv")
"""

from .data_exporter import DataExporter
from .models import (
    ExportFormat,
    ExportConfig,
    ExportResult,
    ExportMetadata,
    OHLCVExportData,
    ScannerExportData,
)
from .formatters import BaseFormatter, PolarsFormatter, JSONFormatter, CSVFormatter

__all__ = [
    # Main exporter
    "DataExporter",
    # Models and enums
    "ExportFormat",
    "ExportConfig",
    "ExportResult",
    "ExportMetadata",
    "OHLCVExportData",
    "ScannerExportData",
    # Formatters
    "BaseFormatter",
    "PolarsFormatter",
    "JSONFormatter",
    "CSVFormatter",
]

# Version info
__version__ = "1.0.0"
