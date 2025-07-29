"""
Export configuration models and data structures.

This module provides Pydantic models for configuring data exports
and standardizing export operations across different formats.
"""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ExportFormat(str, Enum):
    """Supported export formats."""

    POLARS = "polars"
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"


class ExportConfig(BaseModel):
    """Configuration for data export operations."""

    format: ExportFormat = Field(description="Export format to use")
    file_path: Optional[Path] = Field(
        default=None, description="Output file path (auto-generated if not provided)"
    )
    timestamp_format: str = Field(
        default="iso", description="Timestamp format: 'iso', 'unix', or 'datetime'"
    )
    include_metadata: bool = Field(
        default=True, description="Whether to include metadata in export"
    )
    options: Dict[str, Any] = Field(
        default_factory=dict, description="Format-specific export options"
    )

    @field_validator("timestamp_format")
    @classmethod
    def validate_timestamp_format(cls, v: str) -> str:
        """Validate timestamp format."""
        allowed_formats: List[str] = ["iso", "unix", "datetime"]
        if v not in allowed_formats:
            raise ValueError(f"timestamp_format must be one of {allowed_formats}")
        return v


class ExportMetadata(BaseModel):
    """Metadata for exported data."""

    export_timestamp: datetime = Field(
        default_factory=datetime.now, description="When the export was created"
    )
    source: str = Field(description="Data source (e.g., 'ohlcv', 'scanner')")
    symbol: Optional[str] = Field(default=None, description="Symbol if applicable")
    interval: Optional[str] = Field(default=None, description="Interval if applicable")
    record_count: int = Field(description="Number of records exported")
    format: ExportFormat = Field(description="Export format used")
    file_path: Optional[str] = Field(default=None, description="Output file path")

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat(), Path: str}


class ExportResult(BaseModel):
    """Result of an export operation."""

    success: bool = Field(description="Whether export was successful")
    metadata: ExportMetadata = Field(description="Export metadata")
    file_path: Optional[Path] = Field(default=None, description="Output file path")
    error_message: Optional[str] = Field(
        default=None, description="Error message if failed"
    )
    data: Optional[Any] = Field(
        default=None, description="Exported data (for in-memory formats)"
    )

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
        json_encoders = {Path: str}


class OHLCVExportData(BaseModel):
    """Standardized OHLCV data structure for export."""

    timestamp: Union[float, str, datetime] = Field(description="Timestamp")
    open: float = Field(description="Opening price")
    high: float = Field(description="High price")
    low: float = Field(description="Low price")
    close: float = Field(description="Closing price")
    volume: float = Field(description="Trading volume")
    symbol: Optional[str] = Field(default=None, description="Trading symbol")
    interval: Optional[str] = Field(default=None, description="Time interval")

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class ScannerExportData(BaseModel):
    """Standardized scanner data structure for export."""

    name: str = Field(description="Symbol name")
    data: Dict[str, Any] = Field(description="Scanner data fields")
    export_timestamp: datetime = Field(
        default_factory=datetime.now, description="When data was exported"
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}
