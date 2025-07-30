"""
Tests for the tvkit export module.

This module contains comprehensive tests for the export functionality
including data exporters, formatters, and configuration models.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest

from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.api.scanner.models import StockData
from tvkit.export import (
    DataExporter,
    ExportConfig,
    ExportFormat,
    ExportResult,
    OHLCVExportData,
    ScannerExportData,
)
from tvkit.export.formatters import CSVFormatter, JSONFormatter


class TestExportModels:
    """Test export model classes."""

    def test_export_config_creation(self) -> None:
        """Test ExportConfig model creation and validation."""
        config: ExportConfig = ExportConfig(format=ExportFormat.JSON)
        assert config.format == ExportFormat.JSON
        assert config.timestamp_format == "iso"
        assert config.include_metadata is True
        assert config.options == {}

    def test_export_config_invalid_timestamp_format(self) -> None:
        """Test ExportConfig with invalid timestamp format."""
        with pytest.raises(ValueError, match="timestamp_format must be one of"):
            ExportConfig(format=ExportFormat.JSON, timestamp_format="invalid")

    def test_ohlcv_export_data_creation(self) -> None:
        """Test OHLCVExportData model creation."""
        data: OHLCVExportData = OHLCVExportData(
            timestamp=1672531200.0,
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1000.0,
            symbol="AAPL",
            interval="1m",
        )

        assert data.timestamp == 1672531200.0
        assert data.open == 100.0
        assert data.symbol == "AAPL"
        assert data.interval == "1m"

    def test_scanner_export_data_creation(self) -> None:
        """Test ScannerExportData model creation."""
        data: ScannerExportData = ScannerExportData(
            name="AAPL", data={"close": 150.0, "volume": 1000000}
        )

        assert data.name == "AAPL"
        assert data.data["close"] == 150.0
        assert isinstance(data.export_timestamp, datetime)


class TestJSONFormatter:
    """Test JSON export formatter."""

    @pytest.fixture
    def sample_ohlcv_data(self) -> List[OHLCVExportData]:
        """Create sample OHLCV data for testing."""
        return [
            OHLCVExportData(
                timestamp=1672531200.0,
                open=100.0,
                high=105.0,
                low=95.0,
                close=102.0,
                volume=1000.0,
                symbol="AAPL",
            ),
            OHLCVExportData(
                timestamp=1672531260.0,
                open=102.0,
                high=107.0,
                low=101.0,
                close=105.0,
                volume=1200.0,
                symbol="AAPL",
            ),
        ]

    @pytest.fixture
    def sample_scanner_data(self) -> List[ScannerExportData]:
        """Create sample scanner data for testing."""
        return [
            ScannerExportData(
                name="AAPL",
                data={"close": 150.0, "volume": 1000000, "market": "NASDAQ"},
            ),
            ScannerExportData(
                name="GOOGL",
                data={"close": 2500.0, "volume": 500000, "market": "NASDAQ"},
            ),
        ]

    @pytest.mark.asyncio
    async def test_json_export_ohlcv(
        self, sample_ohlcv_data: List[OHLCVExportData]
    ) -> None:
        """Test JSON export of OHLCV data."""
        config: ExportConfig = ExportConfig(format=ExportFormat.JSON)
        formatter: JSONFormatter = JSONFormatter(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path: Path = Path(temp_dir) / "test_ohlcv.json"

            result: ExportResult = await formatter.export_ohlcv(
                sample_ohlcv_data, file_path
            )

            assert result.success is True
            assert result.file_path == file_path
            assert result.metadata.record_count == 2
            assert result.metadata.format == ExportFormat.JSON

            # Verify file contents
            assert file_path.exists()
            with open(file_path, "r") as f:
                data: Dict[str, Any] = json.load(f)

            assert "data" in data
            assert len(data["data"]) == 2
            assert data["data"][0]["symbol"] == "AAPL"
            assert data["data"][0]["open"] == 100.0

    @pytest.mark.asyncio
    async def test_json_export_scanner(
        self, sample_scanner_data: List[ScannerExportData]
    ) -> None:
        """Test JSON export of scanner data."""
        config: ExportConfig = ExportConfig(format=ExportFormat.JSON)
        formatter: JSONFormatter = JSONFormatter(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path: Path = Path(temp_dir) / "test_scanner.json"

            result: ExportResult = await formatter.export_scanner(
                sample_scanner_data, file_path
            )

            assert result.success is True
            assert result.file_path == file_path
            assert result.metadata.record_count == 2

            # Verify file contents
            with open(file_path, "r") as f:
                data: Dict[str, Any] = json.load(f)

            assert len(data["data"]) == 2
            assert data["data"][0]["name"] == "AAPL"
            assert data["data"][0]["market"] == "NASDAQ"


class TestCSVFormatter:
    """Test CSV export formatter."""

    @pytest.fixture
    def sample_ohlcv_data(self) -> List[OHLCVExportData]:
        """Create sample OHLCV data for testing."""
        return [
            OHLCVExportData(
                timestamp=1672531200.0,
                open=100.0,
                high=105.0,
                low=95.0,
                close=102.0,
                volume=1000.0,
            )
        ]

    @pytest.mark.asyncio
    async def test_csv_export_ohlcv(
        self, sample_ohlcv_data: List[OHLCVExportData]
    ) -> None:
        """Test CSV export of OHLCV data."""
        config: ExportConfig = ExportConfig(format=ExportFormat.CSV)
        formatter: CSVFormatter = CSVFormatter(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path: Path = Path(temp_dir) / "test_ohlcv.csv"

            result: ExportResult = await formatter.export_ohlcv(
                sample_ohlcv_data, file_path
            )

            assert result.success is True
            assert result.file_path == file_path

            # Verify file contents
            assert file_path.exists()
            content: str = file_path.read_text()

            # Check CSV header and data
            lines: List[str] = content.strip().split("\n")
            assert len(lines) == 2  # Header + 1 data row
            assert "timestamp,open,high,low,close,volume" in lines[0]
            # Timestamp is converted to ISO format by default
            assert (
                lines[1].startswith("2023-01-01T07:00:00") or "1672531200.0" in lines[1]
            )


class TestDataExporter:
    """Test main DataExporter class."""

    @pytest.fixture
    def sample_ohlcv_bars(self) -> List[OHLCVBar]:
        """Create sample OHLCV bars for testing."""
        return [
            OHLCVBar(
                timestamp=1672531200.0,
                open=100.0,
                high=105.0,
                low=95.0,
                close=102.0,
                volume=1000.0,
            ),
            OHLCVBar(
                timestamp=1672531260.0,
                open=102.0,
                high=107.0,
                low=101.0,
                close=105.0,
                volume=1200.0,
            ),
        ]

    @pytest.fixture
    def sample_stock_data(self) -> List[StockData]:
        """Create sample StockData for testing."""
        return [
            StockData(name="AAPL", close=150.0, volume=1000000, currency="USD"),
            StockData(name="GOOGL", close=2500.0, volume=500000, currency="USD"),
        ]

    def test_data_exporter_initialization(self) -> None:
        """Test DataExporter initialization."""
        exporter: DataExporter = DataExporter()

        supported_formats: List[ExportFormat] = exporter.get_supported_formats()
        assert ExportFormat.JSON in supported_formats
        assert ExportFormat.CSV in supported_formats
        assert ExportFormat.POLARS in supported_formats

    @pytest.mark.asyncio
    async def test_export_ohlcv_to_json(
        self, sample_ohlcv_bars: List[OHLCVBar]
    ) -> None:
        """Test exporting OHLCV data to JSON."""
        exporter: DataExporter = DataExporter()

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path: Path = Path(temp_dir) / "test_export.json"

            result_path: Path = await exporter.to_json(sample_ohlcv_bars, file_path)

            assert result_path == file_path
            assert file_path.exists()

            # Verify JSON content
            with open(file_path, "r") as f:
                data: Dict[str, Any] = json.load(f)

            assert "data" in data
            assert len(data["data"]) == 2
            assert data["data"][0]["open"] == 100.0

    @pytest.mark.asyncio
    async def test_export_ohlcv_to_csv(self, sample_ohlcv_bars: List[OHLCVBar]) -> None:
        """Test exporting OHLCV data to CSV."""
        exporter: DataExporter = DataExporter()

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path: Path = Path(temp_dir) / "test_export.csv"

            result_path: Path = await exporter.to_csv(sample_ohlcv_bars, file_path)

            assert result_path == file_path
            assert file_path.exists()

            # Verify CSV content
            content: str = file_path.read_text()
            lines: List[str] = content.strip().split("\n")
            assert len(lines) == 3  # Header + 2 data rows


@pytest.mark.skipif(
    not pytest.importorskip("polars", minversion=None), reason="Polars not available"
)
class TestPolarsIntegration:
    """Test Polars DataFrame integration."""

    @pytest.fixture
    def sample_ohlcv_bars(self) -> List[OHLCVBar]:
        """Create sample OHLCV bars for testing."""
        return [
            OHLCVBar(
                timestamp=1672531200.0,
                open=100.0,
                high=105.0,
                low=95.0,
                close=102.0,
                volume=1000.0,
            )
        ]

    @pytest.mark.asyncio
    async def test_export_to_polars(self, sample_ohlcv_bars: List[OHLCVBar]) -> None:
        """Test exporting to Polars DataFrame."""
        try:
            import polars as pl
        except ImportError:
            pytest.skip("Polars not available")

        exporter: DataExporter = DataExporter()

        df: pl.DataFrame = await exporter.to_polars(sample_ohlcv_bars)

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 1
        assert "timestamp" in df.columns
        assert "open" in df.columns
        assert "close" in df.columns

        # Check data values
        row: Dict[str, Any] = df.row(0, named=True)
        assert row["open"] == 100.0
        assert row["close"] == 102.0

    @pytest.mark.asyncio
    async def test_export_to_polars_with_analysis(
        self, sample_ohlcv_bars: List[OHLCVBar]
    ) -> None:
        """Test exporting to Polars DataFrame with financial analysis."""
        try:
            import polars as pl
        except ImportError:
            pytest.skip("Polars not available")

        # Create more data for analysis
        bars: List[OHLCVBar] = [
            OHLCVBar(
                timestamp=1672531200.0 + i * 60,
                open=100.0 + i,
                high=105.0 + i,
                low=95.0 + i,
                close=102.0 + i,
                volume=1000.0 + i * 100,
            )
            for i in range(10)
        ]

        exporter: DataExporter = DataExporter()

        df: pl.DataFrame = await exporter.to_polars(bars, add_analysis=True)

        assert isinstance(df, pl.DataFrame)
        assert len(df) == 10

        # Check for analysis columns
        analysis_columns: List[str] = ["return_pct", "typical_price", "sma_5", "vwap"]
        for col in analysis_columns:
            assert col in df.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
