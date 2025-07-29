"""
JSON formatter for data export operations.

This module provides JSON export functionality with configurable
formatting and metadata inclusion options.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Union

from .base_formatter import BaseFormatter
from ..models import (
    ExportResult,
    ExportMetadata,
    ExportFormat,
    OHLCVExportData,
    ScannerExportData,
)

logger = logging.getLogger(__name__)


class JSONFormatter(BaseFormatter):
    """JSON export formatter with configurable options."""

    def supports_format(self, format_type: str) -> bool:
        """Check if this formatter supports the given format."""
        return format_type.lower() == ExportFormat.JSON.value

    async def export_ohlcv(
        self, data: List[OHLCVExportData], file_path: Union[Path, str, None] = None
    ) -> ExportResult:
        """
        Export OHLCV data to JSON format.

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
                file_path = self._generate_file_path("ohlcv", symbol, "json")
            else:
                file_path = Path(file_path)

            # Convert data to JSON-serializable format
            json_data: Dict[str, Any] = {
                "data": [self._convert_ohlcv_to_dict(item) for item in data]
            }

            # Add metadata if configured
            if self.config.include_metadata:
                symbol = data[0].symbol if data and data[0].symbol else "unknown"
                metadata: ExportMetadata = ExportMetadata(
                    source="ohlcv",
                    symbol=symbol,
                    interval=data[0].interval if data and data[0].interval else None,
                    record_count=len(data),
                    format=ExportFormat.JSON,
                    file_path=str(file_path),
                )
                json_data["metadata"] = metadata.model_dump()

            # Write to file
            await self._write_json_file(json_data, file_path)

            # Create successful result
            metadata = ExportMetadata(
                source="ohlcv",
                symbol=data[0].symbol if data and data[0].symbol else "unknown",
                interval=data[0].interval if data and data[0].interval else None,
                record_count=len(data),
                format=ExportFormat.JSON,
                file_path=str(file_path),
            )

            return ExportResult(success=True, metadata=metadata, file_path=file_path)

        except Exception as e:
            logger.error(f"Failed to export OHLCV data to JSON: {e}")

            metadata = ExportMetadata(
                source="ohlcv",
                record_count=len(data) if data else 0,
                format=ExportFormat.JSON,
                file_path=str(file_path) if file_path else None,
            )

            return ExportResult(success=False, metadata=metadata, error_message=str(e))

    async def export_scanner(
        self, data: List[ScannerExportData], file_path: Union[Path, str, None] = None
    ) -> ExportResult:
        """
        Export scanner data to JSON format.

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
                file_path = self._generate_file_path("scanner", "data", "json")
            else:
                file_path = Path(file_path)

            # Convert data to JSON-serializable format
            json_data: Dict[str, Any] = {
                "data": [self._convert_scanner_to_dict(item) for item in data]
            }

            # Add metadata if configured
            if self.config.include_metadata:
                metadata: ExportMetadata = ExportMetadata(
                    source="scanner",
                    record_count=len(data),
                    format=ExportFormat.JSON,
                    file_path=str(file_path),
                )
                json_data["metadata"] = metadata.model_dump()

            # Write to file
            await self._write_json_file(json_data, file_path)

            # Create successful result
            metadata = ExportMetadata(
                source="scanner",
                record_count=len(data),
                format=ExportFormat.JSON,
                file_path=str(file_path),
            )

            return ExportResult(success=True, metadata=metadata, file_path=file_path)

        except Exception as e:
            logger.error(f"Failed to export scanner data to JSON: {e}")

            metadata = ExportMetadata(
                source="scanner",
                record_count=len(data) if data else 0,
                format=ExportFormat.JSON,
                file_path=str(file_path) if file_path else None,
            )

            return ExportResult(success=False, metadata=metadata, error_message=str(e))

    def _convert_ohlcv_to_dict(self, item: OHLCVExportData) -> Dict[str, Any]:
        """
        Convert OHLCV data item to dictionary.

        Args:
            item: OHLCV data item

        Returns:
            Dictionary representation
        """
        result: Dict[str, Any] = {
            "timestamp": self._prepare_timestamp(item.timestamp),
            "open": float(item.open),
            "high": float(item.high),
            "low": float(item.low),
            "close": float(item.close),
            "volume": float(item.volume),
        }

        # Add optional fields if present
        if item.symbol:
            result["symbol"] = item.symbol
        if item.interval:
            result["interval"] = item.interval

        return result

    def _convert_scanner_to_dict(self, item: ScannerExportData) -> Dict[str, Any]:
        """
        Convert scanner data item to dictionary.

        Args:
            item: Scanner data item

        Returns:
            Dictionary representation
        """
        result: Dict[str, Any] = {
            "name": item.name,
            **item.data,  # Flatten the data dictionary
        }

        # Add export timestamp if metadata is included
        if self.config.include_metadata:
            result["export_timestamp"] = item.export_timestamp.isoformat()

        return result

    async def _write_json_file(self, data: Dict[str, Any], file_path: Path) -> None:
        """
        Write JSON data to file with proper formatting.

        Args:
            data: Data to write
            file_path: Output file path

        Raises:
            IOError: If file write fails
        """
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Get formatting options
        indent: Union[int, None] = self.config.options.get("indent", 2)
        ensure_ascii: bool = self.config.options.get("ensure_ascii", False)
        sort_keys: bool = self.config.options.get("sort_keys", True)

        # Write to file
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=indent,
                ensure_ascii=ensure_ascii,
                sort_keys=sort_keys,
                default=str,  # Handle any non-serializable objects
            )

        logger.info(f"Successfully exported JSON data to {file_path}")

    def get_default_options(self) -> Dict[str, Any]:
        """
        Get default JSON formatting options.

        Returns:
            Default options dictionary
        """
        return {"indent": 2, "ensure_ascii": False, "sort_keys": True}
