"""
Base formatter interface for data export operations.

This module provides the abstract base class that all export formatters
must implement, ensuring consistent interfaces across different formats.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Union

from ..models import ExportConfig, ExportResult, OHLCVExportData, ScannerExportData


class BaseFormatter(ABC):
    """Abstract base class for all data export formatters."""

    def __init__(self, config: ExportConfig) -> None:
        """
        Initialize the formatter with configuration.

        Args:
            config: Export configuration settings
        """
        self.config: ExportConfig = config

    @abstractmethod
    async def export_ohlcv(
        self, data: List[OHLCVExportData], file_path: Union[Path, str, None] = None
    ) -> ExportResult:
        """
        Export OHLCV data to the specified format.

        Args:
            data: List of OHLCV data records
            file_path: Optional override for output file path

        Returns:
            ExportResult with operation details

        Raises:
            ValueError: If data is invalid
            IOError: If file operations fail
        """
        pass

    @abstractmethod
    async def export_scanner(
        self, data: List[ScannerExportData], file_path: Union[Path, str, None] = None
    ) -> ExportResult:
        """
        Export scanner data to the specified format.

        Args:
            data: List of scanner data records
            file_path: Optional override for output file path

        Returns:
            ExportResult with operation details

        Raises:
            ValueError: If data is invalid
            IOError: If file operations fail
        """
        pass

    @abstractmethod
    def supports_format(self, format_type: str) -> bool:
        """
        Check if this formatter supports the given format.

        Args:
            format_type: Format type to check

        Returns:
            True if format is supported
        """
        pass

    def _generate_file_path(
        self, data_type: str, symbol: str = "data", extension: str = "txt"
    ) -> Path:
        """
        Generate a default file path for export.

        Args:
            data_type: Type of data being exported (e.g., 'ohlcv', 'scanner')
            symbol: Symbol or identifier for the data
            extension: File extension to use

        Returns:
            Generated file path
        """
        from datetime import datetime

        timestamp: str = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename: str = f"{data_type}_{symbol}_{timestamp}.{extension}"

        # Use export directory if it exists, otherwise current directory
        export_dir: Path = Path("export")
        if export_dir.exists():
            return export_dir / filename
        return Path(filename)

    def _validate_data(self, data: List[Any]) -> None:
        """
        Validate input data before export.

        Args:
            data: Data to validate

        Raises:
            ValueError: If data is invalid
        """
        if not data:
            raise ValueError("Cannot export empty data")

        if not isinstance(data, list):
            raise ValueError("Data must be a list")

    def _prepare_timestamp(self, timestamp: Union[float, str, Any]) -> Any:
        """
        Prepare timestamp based on configuration.

        Args:
            timestamp: Raw timestamp value

        Returns:
            Formatted timestamp based on config
        """
        from datetime import datetime

        if self.config.timestamp_format == "unix":
            if isinstance(timestamp, (int, float)):
                return timestamp
            elif hasattr(timestamp, "timestamp"):
                return timestamp.timestamp()
            else:
                return float(timestamp)

        elif self.config.timestamp_format == "iso":
            if isinstance(timestamp, (int, float)):
                return datetime.fromtimestamp(timestamp).isoformat()
            elif hasattr(timestamp, "isoformat"):
                return timestamp.isoformat()
            else:
                return str(timestamp)

        elif self.config.timestamp_format == "datetime":
            if isinstance(timestamp, (int, float)):
                return datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, str):
                # Try to parse ISO format
                try:
                    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    return datetime.fromtimestamp(float(timestamp))
            else:
                return timestamp

        return timestamp
