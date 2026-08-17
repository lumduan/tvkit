"""
Main data exporter class for tvkit export functionality.

This module provides the primary interface for exporting financial data
from tvkit APIs to various formats including Polars DataFrames, JSON, and CSV.
"""

import logging
from pathlib import Path
from typing import Any, cast, overload

import polars as pl

from ..api.chart.models.ohlcv import OHLCVBar
from ..api.fundamentals.models import (
    DividendReport,
    EarningsReport,
    FinancialStatement,
    FundamentalsSnapshot,
    SegmentReport,
)
from ..api.scanner.models import StockData
from ..validation import DataIntegrityError, ValidationResult, validate_ohlcv
from .formatters import BaseFormatter, CSVFormatter, JSONFormatter, PolarsFormatter
from .models import (
    ExportConfig,
    ExportFormat,
    ExportResult,
    FundamentalsExportData,
    OHLCVExportData,
    ScannerExportData,
)

# Report types that ``export_fundamentals_data`` / the convenience wrappers accept.
FundamentalsInput = (
    FinancialStatement | SegmentReport | DividendReport | EarningsReport | FundamentalsSnapshot
)
_FUNDAMENTALS_TYPES: tuple[type, ...] = (
    FinancialStatement,
    SegmentReport,
    DividendReport,
    EarningsReport,
    FundamentalsSnapshot,
)

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
        self._formatters: dict[ExportFormat, type[BaseFormatter]] = {
            ExportFormat.POLARS: PolarsFormatter,
            ExportFormat.JSON: JSONFormatter,
            ExportFormat.CSV: CSVFormatter,
        }

    async def export_ohlcv_data(
        self,
        data: list[OHLCVBar],
        format: ExportFormat,
        file_path: Path | str | None = None,
        config: ExportConfig | None = None,
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
            export_data: list[OHLCVExportData] = self._convert_ohlcv_bars(data)

            # Create configuration if not provided
            if config is None:
                config = ExportConfig(format=format)

            # Get and initialize formatter
            formatter: BaseFormatter = self._get_formatter(format, config)

            # Export data
            result: ExportResult = await formatter.export_ohlcv(export_data, file_path)

            logger.info(f"Successfully exported {len(data)} OHLCV records to {format.value} format")

            return result

        except Exception as e:
            logger.error(f"Failed to export OHLCV data: {e}")
            raise

    async def export_scanner_data(
        self,
        data: list[StockData],
        format: ExportFormat,
        file_path: Path | str | None = None,
        config: ExportConfig | None = None,
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
            export_data: list[ScannerExportData] = self._convert_scanner_data(data)

            # Create configuration if not provided
            if config is None:
                config = ExportConfig(format=format)

            # Get and initialize formatter
            formatter: BaseFormatter = self._get_formatter(format, config)

            # Export data
            result: ExportResult = await formatter.export_scanner(export_data, file_path)

            logger.info(
                f"Successfully exported {len(data)} scanner records to {format.value} format"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to export scanner data: {e}")
            raise

    async def export_fundamentals_data(
        self,
        data: FundamentalsInput | list[FundamentalsInput],
        format: ExportFormat,
        file_path: Path | str | None = None,
        config: ExportConfig | None = None,
    ) -> ExportResult:
        """
        Export financial statements / revenue segments / dividends / earnings.

        Accepts a single report (or a list of reports) from
        :class:`tvkit.api.fundamentals.FundamentalsClient` and emits tidy/long rows.

        Args:
            data: A report or list of reports (statement, segments, dividends, earnings, snapshot)
            format: Export format to use
            file_path: Optional file path for file-based exports
            config: Optional export configuration

        Returns:
            ExportResult with operation details and exported data

        Example:
            >>> from tvkit.export import DataExporter, ExportFormat
            >>> from tvkit.api.fundamentals import FundamentalsClient
            >>>
            >>> async with FundamentalsClient() as fx:
            ...     income = await fx.get_income_statement("NASDAQ:AAPL")
            ...     exporter = DataExporter()
            ...     df = await exporter.export_fundamentals_data(income, ExportFormat.POLARS)
        """
        try:
            reports = data if isinstance(data, list) else [data]
            export_data: list[FundamentalsExportData] = self._convert_fundamentals_data(reports)

            if config is None:
                config = ExportConfig(format=format)
            formatter: BaseFormatter = self._get_formatter(format, config)
            result: ExportResult = await formatter.export_fundamentals(export_data, file_path)

            logger.info(
                f"Successfully exported {len(export_data)} fundamentals rows to {format.value}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to export fundamentals data: {e}")
            raise

    def _convert_fundamentals_data(
        self, reports: list[FundamentalsInput]
    ) -> list[FundamentalsExportData]:
        """Flatten reports into tidy/long :class:`FundamentalsExportData` rows."""
        rows: list[FundamentalsExportData] = []
        for report in reports:
            if isinstance(report, FundamentalsSnapshot):
                for sub in (
                    report.income,
                    report.balance,
                    report.cash_flow,
                    report.statistics,
                    report.segments,
                    report.dividends,
                    report.earnings,
                ):
                    if sub is not None:
                        rows.extend(self._convert_fundamentals_data([sub]))
            elif isinstance(report, FinancialStatement):
                for line in report.lines:
                    for i, period in enumerate(report.periods):
                        rows.append(
                            FundamentalsExportData(
                                symbol=report.symbol,
                                dataset=report.statement.value,
                                row=line.field_id,
                                label=line.label,
                                period=period.label,
                                period_end=period.period_end,
                                value=line.values[i] if i < len(line.values) else None,
                                currency=report.currency,
                            )
                        )
            elif isinstance(report, SegmentReport):
                for dataset, series in (
                    ("segment_business", report.by_business),
                    ("segment_region", report.by_region),
                ):
                    for sp in series:
                        for seg in sp.segments:
                            rows.append(
                                FundamentalsExportData(
                                    symbol=report.symbol,
                                    dataset=dataset,
                                    row=seg.label,
                                    label=seg.label,
                                    period=sp.period.label,
                                    period_end=sp.period.period_end,
                                    value=seg.value,
                                    currency=report.currency,
                                )
                            )
            elif isinstance(report, DividendReport):
                for ev in report.events:
                    ex_label = ev.ex_date.date().isoformat() if ev.ex_date else ""
                    rows.append(
                        FundamentalsExportData(
                            symbol=report.symbol,
                            dataset="dividend",
                            row="amount",
                            label=ev.dividend_type or "Dividend",
                            period=ex_label,
                            period_end=ev.ex_date,
                            value=ev.amount,
                            currency=report.currency,
                        )
                    )
            elif isinstance(report, EarningsReport):
                for ep in report.periods:
                    for row_id, label, value in (
                        ("eps_reported", "Reported EPS", ep.eps_reported),
                        ("eps_estimate", "Estimated EPS", ep.eps_estimate),
                        ("eps_surprise_pct", "EPS surprise %", ep.eps_surprise_pct),
                        ("revenue_reported", "Reported revenue", ep.revenue_reported),
                        ("revenue_estimate", "Estimated revenue", ep.revenue_estimate),
                    ):
                        rows.append(
                            FundamentalsExportData(
                                symbol=report.symbol,
                                dataset="earnings",
                                row=row_id,
                                label=label,
                                period=ep.label,
                                value=value,
                                currency=report.currency,
                            )
                        )
        return rows

    @overload
    async def to_polars(self, data: list[OHLCVBar], add_analysis: bool = False) -> Any: ...

    @overload
    async def to_polars(self, data: list[StockData], add_analysis: bool = False) -> Any: ...

    @overload
    async def to_polars(self, data: list[FundamentalsInput], add_analysis: bool = False) -> Any: ...

    async def to_polars(
        self,
        data: list[OHLCVBar] | list[StockData] | list[FundamentalsInput],
        add_analysis: bool = False,
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
                cast(list[OHLCVBar], data),
                ExportFormat.POLARS,
                config=config,
            )
        elif data and isinstance(data[0], _FUNDAMENTALS_TYPES):
            result = await self.export_fundamentals_data(
                cast(list[FundamentalsInput], data),
                ExportFormat.POLARS,
                config=config,
            )
        else:
            result = await self.export_scanner_data(
                cast(list[StockData], data),
                ExportFormat.POLARS,
                config=config,
            )

        if not result.success:
            raise RuntimeError(f"Export failed: {result.error_message}")

        return result.data

    async def to_json(
        self,
        data: list[OHLCVBar] | list[StockData] | list[FundamentalsInput],
        file_path: Path | str,
        include_metadata: bool = True,
        *,
        validate: bool = False,
        strict: bool = False,
        interval: str | None = None,
        **json_options: Any,
    ) -> Path:
        """
        Convenience method to export data to JSON file.

        Args:
            data: OHLCV bars or scanner data
            file_path: Output file path
            include_metadata: Whether to include metadata in JSON
            validate: If True, run validate_ohlcv() before writing.
                Violations are logged at WARNING level. Does not affect
                export behavior unless strict=True. Only applies to OHLCV
                data; scanner data silently skips validation.
            strict: If True and validate=True, raise DataIntegrityError if
                any ERROR-level violations are found. The file is NOT written.
                WARNING-only results do not raise.
            interval: Passed to validate_ohlcv() for gap detection.
                Only relevant when validate=True.
            **json_options: Additional JSON formatting options

        Returns:
            Path to the created JSON file

        Raises:
            DataIntegrityError: If validate=True, strict=True, and ERROR
                violations are found.
            RuntimeError: If the export fails or produces no file path.

        Example:
            >>> exporter = DataExporter()
            >>> json_file = await exporter.to_json(
            ...     ohlcv_bars,
            ...     "btc_data.json",
            ...     indent=4
            ... )
        """
        if validate:
            self._run_ohlcv_validation(data, strict=strict, interval=interval)

        config: ExportConfig = ExportConfig(
            format=ExportFormat.JSON,
            include_metadata=include_metadata,
            options=json_options,
        )

        if data and isinstance(data[0], OHLCVBar):
            result: ExportResult = await self.export_ohlcv_data(
                cast(list[OHLCVBar], data),
                ExportFormat.JSON,
                file_path,
                config,
            )
        elif data and isinstance(data[0], _FUNDAMENTALS_TYPES):
            result = await self.export_fundamentals_data(
                cast(list[FundamentalsInput], data),
                ExportFormat.JSON,
                file_path,
                config,
            )
        else:
            result = await self.export_scanner_data(
                cast(list[StockData], data),
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
        data: list[OHLCVBar] | list[StockData] | list[FundamentalsInput],
        file_path: Path | str,
        include_metadata: bool = True,
        *,
        validate: bool = False,
        strict: bool = False,
        interval: str | None = None,
        **csv_options: Any,
    ) -> Path:
        """
        Convenience method to export data to CSV file.

        Args:
            data: OHLCV bars or scanner data
            file_path: Output file path
            include_metadata: Whether to include metadata file
            validate: If True, run validate_ohlcv() before writing.
                Violations are logged at WARNING level. Does not affect
                export behavior unless strict=True. Only applies to OHLCV
                data; scanner data silently skips validation.
            strict: If True and validate=True, raise DataIntegrityError if
                any ERROR-level violations are found. The file is NOT written.
                WARNING-only results do not raise.
            interval: Passed to validate_ohlcv() for gap detection.
                Only relevant when validate=True.
            **csv_options: Additional CSV formatting options

        Returns:
            Path to the created CSV file

        Raises:
            DataIntegrityError: If validate=True, strict=True, and ERROR
                violations are found.
            RuntimeError: If the export fails or produces no file path.

        Example:
            >>> exporter = DataExporter()
            >>> csv_file = await exporter.to_csv(
            ...     ohlcv_bars,
            ...     "btc_data.csv",
            ...     delimiter=";",
            ...     timestamp_format="iso"
            ... )
        """
        if validate:
            self._run_ohlcv_validation(data, strict=strict, interval=interval)

        config: ExportConfig = ExportConfig(
            format=ExportFormat.CSV,
            include_metadata=include_metadata,
            options=csv_options,
        )

        if data and isinstance(data[0], OHLCVBar):
            result: ExportResult = await self.export_ohlcv_data(
                cast(list[OHLCVBar], data),
                ExportFormat.CSV,
                file_path,
                config,
            )
        elif data and isinstance(data[0], _FUNDAMENTALS_TYPES):
            result = await self.export_fundamentals_data(
                cast(list[FundamentalsInput], data),
                ExportFormat.CSV,
                file_path,
                config,
            )
        else:
            result = await self.export_scanner_data(
                cast(list[StockData], data),
                ExportFormat.CSV,
                file_path,
                config,
            )

        if not result.success:
            raise RuntimeError(f"Export failed: {result.error_message}")

        if result.file_path is None:
            raise RuntimeError("Export did not produce a file path")

        return result.file_path

    def _run_ohlcv_validation(
        self,
        data: list[OHLCVBar] | list[StockData] | list[FundamentalsInput],
        *,
        strict: bool,
        interval: str | None,
    ) -> None:
        """
        Run OHLCV data integrity validation if data contains OHLCV bars.

        Silently skips validation for scanner (StockData) inputs and empty lists.
        Logs all violations at WARNING level using structured extra fields.
        Raises DataIntegrityError only when strict=True and ERROR-level violations
        are found. WARNING-only results never raise.

        Args:
            data: OHLCV bars or scanner data. Validation applies to OHLCVBar only.
            strict: If True, raise DataIntegrityError on ERROR violations.
            interval: Passed to validate_ohlcv() for gap detection.

        Raises:
            DataIntegrityError: If strict=True and ERROR-level violations are found.
        """
        if not data or not isinstance(data[0], OHLCVBar):
            return

        ohlcv_bars: list[OHLCVBar] = cast(list[OHLCVBar], data)
        df: pl.DataFrame = pl.DataFrame(
            {
                "timestamp": [bar.timestamp for bar in ohlcv_bars],
                "open": [bar.open for bar in ohlcv_bars],
                "high": [bar.high for bar in ohlcv_bars],
                "low": [bar.low for bar in ohlcv_bars],
                "close": [bar.close for bar in ohlcv_bars],
                "volume": [bar.volume for bar in ohlcv_bars],
            }
        )

        result: ValidationResult = validate_ohlcv(df, interval=interval)

        for violation in result.violations:
            logger.warning(
                violation.message,
                extra={"check": violation.check.value, "rows": violation.affected_rows},
            )

        if strict and result.errors:
            raise DataIntegrityError(result)

    def add_formatter(
        self, format_type: ExportFormat, formatter_class: type[BaseFormatter]
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

    def get_supported_formats(self) -> list[ExportFormat]:
        """
        Get list of supported export formats.

        Returns:
            List of supported ExportFormat values
        """
        return list(self._formatters.keys())

    def _get_formatter(self, format: ExportFormat, config: ExportConfig) -> BaseFormatter:
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
            supported: list[str] = [f.value for f in self._formatters.keys()]
            raise ValueError(
                f"Unsupported export format: {format.value}. "
                f"Supported formats: {', '.join(supported)}"
            )

        formatter_class: type[BaseFormatter] = self._formatters[format]
        return formatter_class(config)

    def _convert_ohlcv_bars(self, bars: list[OHLCVBar]) -> list[OHLCVExportData]:
        """
        Convert tvkit OHLCV bars to export data format.

        Args:
            bars: List of OHLCV bars from tvkit

        Returns:
            List of export-ready OHLCV data
        """
        export_data: list[OHLCVExportData] = []

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

    def _convert_scanner_data(self, stocks: list[StockData]) -> list[ScannerExportData]:
        """
        Convert tvkit scanner data to export data format.

        Args:
            stocks: List of StockData from tvkit scanner

        Returns:
            List of export-ready scanner data
        """
        export_data: list[ScannerExportData] = []

        for stock in stocks:
            # Convert StockData to dictionary, excluding None values
            stock_dict: dict[str, Any] = stock.model_dump(exclude_none=True)
            name: str = stock_dict.pop("name", "unknown")

            export_item: ScannerExportData = ScannerExportData(name=name, data=stock_dict)
            export_data.append(export_item)

        return export_data
