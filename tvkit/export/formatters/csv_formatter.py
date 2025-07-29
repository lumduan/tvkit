"""
CSV formatter for data export operations.

This module provides CSV export functionality with configurable
formatting options and metadata handling.
"""

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Union, Sequence, Set, Literal, cast

from .base_formatter import BaseFormatter
from ..models import (
    ExportResult,
    ExportMetadata,
    ExportFormat,
    OHLCVExportData,
    ScannerExportData,
)

logger = logging.getLogger(__name__)


class CSVFormatter(BaseFormatter):
    """CSV export formatter with configurable options."""

    def supports_format(self, format_type: str) -> bool:
        """Check if this formatter supports the given format."""
        return format_type.lower() == ExportFormat.CSV.value

    async def export_ohlcv(
        self, data: List[OHLCVExportData], file_path: Union[Path, str, None] = None
    ) -> ExportResult:
        """
        Export OHLCV data to CSV format.

        Args:
            data: List of OHLCV data records
            file_path: Optional override for output file path

        Returns:
            ExportResult with operation details
        """
        try:
            self._validate_data(data)

            # Determine output path
            if file_path is None:
                symbol: str = data[0].symbol if data and data[0].symbol else "data"
                file_path = self._generate_file_path("ohlcv", symbol, "csv")
            else:
                file_path = Path(file_path)

            # Define CSV columns
            columns: List[str] = ["timestamp", "open", "high", "low", "close", "volume"]

            # Add optional columns if present in data
            if any(item.symbol for item in data):
                columns.append("symbol")
            if any(item.interval for item in data):
                columns.append("interval")

            # Convert data to rows
            rows: List[Dict[str, Any]] = []
            for item in data:
                row: Dict[str, Any] = {
                    "timestamp": self._prepare_timestamp(item.timestamp),
                    "open": float(item.open),
                    "high": float(item.high),
                    "low": float(item.low),
                    "close": float(item.close),
                    "volume": float(item.volume),
                }

                # Add optional fields if present
                if "symbol" in columns:
                    row["symbol"] = item.symbol or ""
                if "interval" in columns:
                    row["interval"] = item.interval or ""

                rows.append(row)

            # Write CSV file
            await self._write_csv_file(rows, columns, file_path)

            # Write metadata file if configured
            if self.config.include_metadata:
                await self._write_metadata_file(data, file_path, "ohlcv")

            # Create successful result
            symbol = data[0].symbol if data and data[0].symbol else "unknown"
            metadata: ExportMetadata = ExportMetadata(
                source="ohlcv",
                symbol=symbol,
                interval=data[0].interval if data and data[0].interval else None,
                record_count=len(data),
                format=ExportFormat.CSV,
                file_path=str(file_path),
            )

            return ExportResult(success=True, metadata=metadata, file_path=file_path)

        except Exception as e:
            logger.error(f"Failed to export OHLCV data to CSV: {e}")

            metadata = ExportMetadata(
                source="ohlcv",
                record_count=len(data) if data else 0,
                format=ExportFormat.CSV,
                file_path=str(file_path) if file_path else None,
            )

            return ExportResult(success=False, metadata=metadata, error_message=str(e))

    async def export_scanner(
        self, data: List[ScannerExportData], file_path: Union[Path, str, None] = None
    ) -> ExportResult:
        """
        Export scanner data to CSV format.

        Args:
            data: List of scanner data records
            file_path: Optional override for output file path

        Returns:
            ExportResult with operation details
        """
        try:
            self._validate_data(data)

            # Determine output path
            if file_path is None:
                file_path = self._generate_file_path("scanner", "data", "csv")
            else:
                file_path = Path(file_path)

            # Collect all unique columns from scanner data
            all_columns: Set[str] = {"name"}
            for item in data:
                all_columns.update(item.data.keys())

            # Add export timestamp if metadata is included
            if self.config.include_metadata:
                all_columns.add("export_timestamp")

            # Sort columns for consistent output
            columns: List[str] = sorted(all_columns)

            # Convert data to rows
            rows: List[Dict[str, Any]] = []
            for item in data:
                row: Dict[str, Any] = {"name": item.name}

                # Add all data fields
                for col in columns:
                    if col == "name":
                        continue
                    elif col == "export_timestamp" and self.config.include_metadata:
                        row[col] = item.export_timestamp.isoformat()
                    else:
                        row[col] = item.data.get(col, "")

                rows.append(row)

            # Write CSV file
            await self._write_csv_file(rows, columns, file_path)

            # Write metadata file if configured
            if self.config.include_metadata:
                await self._write_metadata_file(data, file_path, "scanner")

            # Create successful result
            metadata: ExportMetadata = ExportMetadata(
                source="scanner",
                record_count=len(data),
                format=ExportFormat.CSV,
                file_path=str(file_path),
            )

            return ExportResult(success=True, metadata=metadata, file_path=file_path)

        except Exception as e:
            logger.error(f"Failed to export scanner data to CSV: {e}")

            metadata = ExportMetadata(
                source="scanner",
                record_count=len(data) if data else 0,
                format=ExportFormat.CSV,
                file_path=str(file_path) if file_path else None,
            )

            return ExportResult(success=False, metadata=metadata, error_message=str(e))

    async def _write_csv_file(
        self, rows: List[Dict[str, Any]], columns: List[str], file_path: Path
    ) -> None:
        """
        Write CSV data to file.

        Args:
            rows: Data rows to write
            columns: Column names in order
            file_path: Output file path

        Raises:
            IOError: If file write fails
        """
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Get CSV options
        delimiter: str = self.config.options.get("delimiter", ",")
        quoting: Literal[0, 1, 2, 3, 4, 5] = cast(
            Literal[0, 1, 2, 3, 4, 5],
            self.config.options.get("quoting", csv.QUOTE_MINIMAL),
        )
        line_terminator: str = self.config.options.get("line_terminator", "\n")

        # Write CSV file
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=columns,
                delimiter=delimiter,
                quoting=quoting,
                lineterminator=line_terminator,
            )

            # Write header
            writer.writeheader()

            # Write data rows
            writer.writerows(rows)

        logger.info(f"Successfully exported CSV data to {file_path}")

    async def _write_metadata_file(
        self,
        data: Sequence[Union[OHLCVExportData, ScannerExportData]],
        csv_file_path: Path,
        data_type: str,
    ) -> None:
        """
        Write metadata file alongside CSV export.

        Args:
            data: Source data for metadata generation
            csv_file_path: Path to the CSV file
            data_type: Type of data being exported
        """
        try:
            # Create metadata file path
            metadata_path: Path = csv_file_path.with_suffix(".metadata.txt")

            # Generate metadata content
            if data_type == "ohlcv":
                symbol = (
                    data[0].symbol
                    if data and hasattr(data[0], "symbol") and data[0].symbol
                    else "unknown"
                )
                interval = (
                    data[0].interval
                    if data and hasattr(data[0], "interval") and data[0].interval
                    else None
                )
                from datetime import datetime

                content = f"""CSV Export Metadata
==================
Export Time: {datetime.now().isoformat()}
Source: {data_type}
Symbol: {symbol}
Interval: {interval}
Record Count: {len(data)}
CSV File: {csv_file_path.name}
Format: CSV

Column Descriptions:
- timestamp: Price timestamp ({self.config.timestamp_format} format)
- open: Opening price
- high: Highest price in period
- low: Lowest price in period  
- close: Closing price
- volume: Trading volume
"""
                if symbol != "unknown":
                    content += f"- symbol: Trading symbol ({symbol})\n"
                if interval:
                    content += f"- interval: Time interval ({interval})\n"

            else:  # scanner data
                from datetime import datetime

                content = f"""CSV Export Metadata
==================
Export Time: {datetime.now().isoformat()}
Source: {data_type}
Record Count: {len(data)}
CSV File: {csv_file_path.name}
Format: CSV

Note: Scanner data contains variable columns based on requested fields.
Each row represents one symbol with its associated data fields.
"""

            # Write metadata file
            with open(metadata_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Metadata written to {metadata_path}")

        except Exception as e:
            logger.warning(f"Failed to write metadata file: {e}")

    def get_default_options(self) -> Dict[str, Any]:
        """
        Get default CSV formatting options.

        Returns:
            Default options dictionary
        """
        return {"delimiter": ",", "quoting": csv.QUOTE_MINIMAL, "line_terminator": "\n"}
