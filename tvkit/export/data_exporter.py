"""
Main data exporter class for tvkit export functionality.

This module provides the primary interface for exporting financial data
from tvkit APIs to various formats including Polars DataFrames, JSON, and CSV.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union, overload, cast

from .models import (
    ExportConfig,
    ExportFormat,
    ExportResult,
    OHLCVExportData,
    ScannerExportData,
)
from .formatters import BaseFormatter, PolarsFormatter, JSONFormatter, CSVFormatter
from ..api.chart.models.ohlcv import OHLCVBar
from ..api.scanner.models import StockData

logger = logging.getLogger(__name__)


class DataExporter:
    """
    Main data exporter for tvkit financial data.

    This class provides a unified interface for exporting data from tvkit APIs
    to various formats. It handles format selection, data conversion, and
    export configuration automatically.
    """

    def __init__(self) -> None:
        """Initialize the DataExporter with available formatters."""
        self._formatters: Dict[ExportFormat, Type[BaseFormatter]] = {
            ExportFormat.POLARS: PolarsFormatter,
            ExportFormat.JSON: JSONFormatter,
            ExportFormat.CSV: CSVFormatter,
        }

    async def export_ohlcv_data(
        self,
        data: List[OHLCVBar],
        format: ExportFormat,
        file_path: Optional[Union[Path, str]] = None,
        config: Optional[ExportConfig] = None,
    ) -> ExportResult:
        """
        Export OHLCV data to the specified format.

        Args:
            data: List of OHLCV bars from tvkit
            format: Export format to use
            file_path: Optional file path for file-based exports
            config: Optional export configuration

        Returns:
            ExportResult with operation details and exported data

        Raises:
            ValueError: If format is not supported or data is invalid

        Example:
            >>> from tvkit.export import DataExporter, ExportFormat
            >>> from tvkit.api.chart.ohlcv import OHLCV
            >>>
            >>> async with OHLCV() as client:
            ...     bars = await client.get_historical_ohlcv("BINANCE:BTCUSDT", "1m", 100)
            ...
            ...     exporter = DataExporter()
            ...
            ...     # Export to Polars DataFrame
            ...     result = await exporter.export_ohlcv_data(bars, ExportFormat.POLARS)
            ...     df = result.data  # Access the DataFrame
            ...
            ...     # Export to JSON file
            ...     result = await exporter.export_ohlcv_data(
            ...         bars,
            ...         ExportFormat.JSON,
            ...         file_path="btc_data.json"
            ...     )
        """
        try:
            # Convert tvkit OHLCV data to export format
            export_data: List[OHLCVExportData] = self._convert_ohlcv_bars(data)

            # Create configuration if not provided
            if config is None:
                config = ExportConfig(format=format)

            # Get and initialize formatter
            formatter: BaseFormatter = self._get_formatter(format, config)

            # Export data
            result: ExportResult = await formatter.export_ohlcv(export_data, file_path)

            logger.info(
                f"Successfully exported {len(data)} OHLCV records to {format.value} format"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to export OHLCV data: {e}")
            raise

    async def export_scanner_data(
        self,
        data: List[StockData],
        format: ExportFormat,
        file_path: Optional[Union[Path, str]] = None,
        config: Optional[ExportConfig] = None,
    ) -> ExportResult:
        """
        Export scanner data to the specified format.

        Args:
            data: List of scanner StockData from tvkit
            format: Export format to use
            file_path: Optional file path for file-based exports
            config: Optional export configuration

        Returns:
            ExportResult with operation details and exported data

        Example:
            >>> from tvkit.export import DataExporter, ExportFormat
            >>> from tvkit.api.scanner import ScannerAPI
            >>>
            >>> scanner = ScannerAPI()
            >>> stocks = await scanner.get_stocks(preset="all_stocks", limit=100)
            >>>
            >>> exporter = DataExporter()
            >>> result = await exporter.export_scanner_data(stocks, ExportFormat.CSV)
        """
        try:
            # Convert tvkit scanner data to export format
            export_data: List[ScannerExportData] = self._convert_scanner_data(data)

            # Create configuration if not provided
            if config is None:
                config = ExportConfig(format=format)

            # Get and initialize formatter
            formatter: BaseFormatter = self._get_formatter(format, config)

            # Export data
            result: ExportResult = await formatter.export_scanner(
                export_data, file_path
            )

            logger.info(
                f"Successfully exported {len(data)} scanner records to {format.value} format"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to export scanner data: {e}")
            raise

    @overload
    async def to_polars(
        self, data: List[OHLCVBar], add_analysis: bool = False
    ) -> Any: ...

    @overload
    async def to_polars(
        self, data: List[StockData], add_analysis: bool = False
    ) -> Any: ...

    async def to_polars(
        self, data: Union[List[OHLCVBar], List[StockData]], add_analysis: bool = False
    ) -> Any:
        """
        Convenience method to export data directly to Polars DataFrame.

        Args:
            data: OHLCV bars or scanner data
            add_analysis: Whether to add financial analysis columns (OHLCV only)

        Returns:
            Polars DataFrame with the exported data

        Example:
            >>> exporter = DataExporter()
            >>> df = await exporter.to_polars(ohlcv_bars, add_analysis=True)
            >>> print(df.head())
        """
        config: ExportConfig = ExportConfig(
            format=ExportFormat.POLARS, options={"add_analysis": add_analysis}
        )

        if data and isinstance(data[0], OHLCVBar):
            result: ExportResult = await self.export_ohlcv_data(
                cast(List[OHLCVBar], data),
                ExportFormat.POLARS,
                config=config,
            )
        else:
            result = await self.export_scanner_data(
                cast(List[StockData], data),
                ExportFormat.POLARS,
                config=config,
            )

        if not result.success:
            raise RuntimeError(f"Export failed: {result.error_message}")

        return result.data

    async def to_json(
        self,
        data: Union[List[OHLCVBar], List[StockData]],
        file_path: Union[Path, str],
        include_metadata: bool = True,
        **json_options: Any,
    ) -> Path:
        """
        Convenience method to export data to JSON file.

        Args:
            data: OHLCV bars or scanner data
            file_path: Output file path
            include_metadata: Whether to include metadata in JSON
            **json_options: Additional JSON formatting options

        Returns:
            Path to the created JSON file

        Example:
            >>> exporter = DataExporter()
            >>> json_file = await exporter.to_json(
            ...     ohlcv_bars,
            ...     "btc_data.json",
            ...     indent=4
            ... )
        """
        config: ExportConfig = ExportConfig(
            format=ExportFormat.JSON,
            include_metadata=include_metadata,
            options=json_options,
        )

        if data and isinstance(data[0], OHLCVBar):
            result: ExportResult = await self.export_ohlcv_data(
                cast(List[OHLCVBar], data),
                ExportFormat.JSON,
                file_path,
                config,
            )
        else:
            result = await self.export_scanner_data(
                cast(List[StockData], data),
                ExportFormat.JSON,
                file_path,
                config,
            )

        if not result.success:
            raise RuntimeError(f"Export failed: {result.error_message}")

        if result.file_path is None:
            raise RuntimeError("Export did not produce a file path")

        return result.file_path

    async def to_csv(
        self,
        data: Union[List[OHLCVBar], List[StockData]],
        file_path: Union[Path, str],
        include_metadata: bool = True,
        **csv_options: Any,
    ) -> Path:
        """
        Convenience method to export data to CSV file.

        Args:
            data: OHLCV bars or scanner data
            file_path: Output file path
            include_metadata: Whether to include metadata file
            **csv_options: Additional CSV formatting options

        Returns:
            Path to the created CSV file

        Example:
            >>> exporter = DataExporter()
            >>> csv_file = await exporter.to_csv(
            ...     ohlcv_bars,
            ...     "btc_data.csv",
            ...     delimiter=";",
            ...     timestamp_format="iso"
            ... )
        """
        config: ExportConfig = ExportConfig(
            format=ExportFormat.CSV,
            include_metadata=include_metadata,
            options=csv_options,
        )

        if data and isinstance(data[0], OHLCVBar):
            result: ExportResult = await self.export_ohlcv_data(
                cast(List[OHLCVBar], data),
                ExportFormat.CSV,
                file_path,
                config,
            )
        else:
            result = await self.export_scanner_data(
                cast(List[StockData], data),
                ExportFormat.CSV,
                file_path,
                config,
            )

        if not result.success:
            raise RuntimeError(f"Export failed: {result.error_message}")

        if result.file_path is None:
            raise RuntimeError("Export did not produce a file path")

        return result.file_path

    def add_formatter(
        self, format_type: ExportFormat, formatter_class: Type[BaseFormatter]
    ) -> None:
        """
        Add or replace a formatter for a specific format.

        Args:
            format_type: Export format type
            formatter_class: Formatter class that extends BaseFormatter

        Example:
            >>> class ParquetFormatter(BaseFormatter):
            ...     # Implementation
            ...     pass
            >>>
            >>> exporter = DataExporter()
            >>> exporter.add_formatter(ExportFormat.PARQUET, ParquetFormatter)
        """
        self._formatters[format_type] = formatter_class
        logger.info(f"Added formatter for {format_type.value} format")

    def get_supported_formats(self) -> List[ExportFormat]:
        """
        Get list of supported export formats.

        Returns:
            List of supported ExportFormat values
        """
        return list(self._formatters.keys())

    def _get_formatter(
        self, format: ExportFormat, config: ExportConfig
    ) -> BaseFormatter:
        """
        Get and initialize a formatter for the specified format.

        Args:
            format: Export format
            config: Export configuration

        Returns:
            Initialized formatter instance

        Raises:
            ValueError: If format is not supported
        """
        if format not in self._formatters:
            supported: List[str] = [f.value for f in self._formatters.keys()]
            raise ValueError(
                f"Unsupported export format: {format.value}. "
                f"Supported formats: {', '.join(supported)}"
            )

        formatter_class: Type[BaseFormatter] = self._formatters[format]
        return formatter_class(config)

    def _convert_ohlcv_bars(self, bars: List[OHLCVBar]) -> List[OHLCVExportData]:
        """
        Convert tvkit OHLCV bars to export data format.

        Args:
            bars: List of OHLCV bars from tvkit

        Returns:
            List of export-ready OHLCV data
        """
        export_data: List[OHLCVExportData] = []

        for bar in bars:
            export_item: OHLCVExportData = OHLCVExportData(
                timestamp=bar.timestamp,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
            )
            export_data.append(export_item)

        return export_data

    def _convert_scanner_data(self, stocks: List[StockData]) -> List[ScannerExportData]:
        """
        Convert tvkit scanner data to export data format.

        Args:
            stocks: List of StockData from tvkit scanner

        Returns:
            List of export-ready scanner data
        """
        export_data: List[ScannerExportData] = []

        for stock in stocks:
            # Convert StockData to dictionary, excluding None values
            stock_dict: Dict[str, Any] = stock.model_dump(exclude_none=True)
            name: str = stock_dict.pop("name", "unknown")

            export_item: ScannerExportData = ScannerExportData(
                name=name, data=stock_dict
            )
            export_data.append(export_item)

        return export_data
