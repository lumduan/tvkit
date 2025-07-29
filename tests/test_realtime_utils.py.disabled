"""
Tests for real-time WebSocket streaming utilities.

This module provides comprehensive tests for utility functions used in
real-time streaming operations including export, validation, and data conversion.
"""

import pytest
import os
import json
import tempfile
from decimal import Decimal
from typing import List, Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock

from tvkit.api.chart.utils import (
    ensure_export_directory,
    generate_export_filepath,
    save_json_file,
    save_csv_file,
    save_parquet_file,
    export_data,
    OHLCVConverter,
    generate_session_id,
    validate_symbols_async,
)
from tvkit.api.chart.models import OHLCVData, ExportConfig


class TestDirectoryOperations:
    """Test cases for directory operations."""

    def test_ensure_export_directory_creation(self):
        """Test creating export directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = os.path.join(temp_dir, "new_export_dir")

            # Directory should not exist initially
            assert not os.path.exists(test_path)

            # Create directory
            ensure_export_directory(test_path)

            # Directory should now exist
            assert os.path.exists(test_path)
            assert os.path.isdir(test_path)

    def test_ensure_export_directory_existing(self):
        """Test with existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Directory already exists
            ensure_export_directory(temp_dir)

            # Should not raise error and directory should still exist
            assert os.path.exists(temp_dir)

    def test_generate_export_filepath(self):
        """Test export filepath generation."""
        symbol = "BINANCE:BTCUSDT"
        data_category = "ohlcv"
        timeframe = "1m"
        file_extension = ".json"

        filepath = generate_export_filepath(
            symbol, data_category, timeframe, file_extension
        )

        # Check format
        assert filepath.startswith("/export/")
        assert "ohlcv" in filepath
        assert "binancebtcusdt" in filepath  # Symbol should be cleaned
        assert "1m" in filepath
        assert filepath.endswith(".json")
        assert (
            len(filepath.split("_")) >= 4
        )  # Should have multiple underscore-separated parts


class TestFileOperations:
    """Test cases for file operations."""

    @pytest.mark.asyncio
    async def test_save_json_file(self):
        """Test saving JSON file."""
        test_data: List[Dict[str, Any]] = [
            {"timestamp": 1642694400, "price": "50000.50"},
            {"timestamp": 1642694460, "price": "50100.25"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = os.path.join(temp_dir, "test_data.json")

            result = await save_json_file(test_data, filepath)

            assert result is True
            assert os.path.exists(filepath)

            # Verify content
            with open(filepath, "r") as f:
                loaded_data = json.load(f)

            assert loaded_data == test_data

    @pytest.mark.asyncio
    async def test_save_csv_file(self):
        """Test saving CSV file."""
        test_data: List[Dict[str, Any]] = [
            {"timestamp": 1642694400, "price": "50000.50", "volume": "1.25"},
            {"timestamp": 1642694460, "price": "50100.25", "volume": "2.15"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = os.path.join(temp_dir, "test_data.csv")

            result = await save_csv_file(test_data, filepath)

            assert result is True
            assert os.path.exists(filepath)

            # Check that file is not empty
            assert os.path.getsize(filepath) > 0

    @pytest.mark.asyncio
    async def test_save_parquet_file(self):
        """Test saving Parquet file."""
        test_data: List[Dict[str, Any]] = [
            {"timestamp": 1642694400, "price": 50000.50, "volume": 1.25},
            {"timestamp": 1642694460, "price": 50100.25, "volume": 2.15},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = os.path.join(temp_dir, "test_data.parquet")

            result = await save_parquet_file(test_data, filepath)

            assert result is True
            assert os.path.exists(filepath)

            # Check that file is not empty
            assert os.path.getsize(filepath) > 0

    @pytest.mark.asyncio
    async def test_export_data_disabled(self):
        """Test export when disabled."""
        config = ExportConfig(
            enabled=False,
            format="json",
            directory="/tmp",
            filename_prefix=None,
            include_timestamp=True,
            auto_export_interval=None,
        )

        ohlcv_data = [
            OHLCVData(
                index=1,
                timestamp=1642694400,
                open=Decimal("50000"),
                high=Decimal("51000"),
                low=Decimal("49500"),
                close=Decimal("50500"),
                volume=Decimal("1250"),
            )
        ]

        result = await export_data(ohlcv_data, config, "BINANCE:BTCUSDT", "1m")

        assert result is False

    @pytest.mark.asyncio
    async def test_export_data_enabled_json(self):
        """Test export when enabled with JSON format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ExportConfig(
                enabled=True,
                format="json",
                directory=temp_dir,
                filename_prefix="test",
                include_timestamp=True,
                auto_export_interval=None,
            )

            ohlcv_data = [
                OHLCVData(
                    index=1,
                    timestamp=1642694400,
                    open=Decimal("50000"),
                    high=Decimal("51000"),
                    low=Decimal("49500"),
                    close=Decimal("50500"),
                    volume=Decimal("1250"),
                )
            ]

            result = await export_data(ohlcv_data, config, "BINANCE:BTCUSDT", "1m")

            assert result is True

            # Check that a file was created
            files = os.listdir(temp_dir)
            assert len(files) == 1
            assert files[0].endswith(".json")


class TestOHLCVConverter:
    """Test cases for OHLCV converter."""

    def test_valid_converter_creation(self):
        """Test creating valid OHLCV converter."""
        converter = OHLCVConverter("1h")

        assert converter.target_timeframe == "1h"
        assert converter.target_interval == 60  # 1 hour = 60 minutes

    def test_invalid_timeframe(self):
        """Test creating converter with invalid timeframe."""
        with pytest.raises(ValueError, match="Invalid timeframe"):
            OHLCVConverter("invalid_tf")

    def test_timeframe_to_minutes_conversion(self):
        """Test timeframe to minutes conversion."""
        test_cases = [
            ("1m", 1),
            ("5m", 5),
            ("15m", 15),
            ("30m", 30),
            ("1h", 60),
            ("2h", 120),
            ("4h", 240),
            ("1d", 1440),
            ("1w", 10080),
            ("1M", 302400),
        ]

        for timeframe, expected_minutes in test_cases:
            converter = OHLCVConverter(timeframe)
            assert converter.target_interval == expected_minutes

    def test_convert_ohlcv_data_empty(self):
        """Test converting empty OHLCV data."""
        converter = OHLCVConverter("1h")

        with pytest.raises(ValueError, match="Cannot convert empty data"):
            converter.convert_ohlcv_data([])

    def test_convert_ohlcv_data_same_timeframe(self):
        """Test converting OHLCV data to same timeframe."""
        converter = OHLCVConverter("1m")

        # Create 1-minute data
        data = [
            OHLCVData(
                index=i,
                timestamp=1642694400 + i * 60,  # 1 minute intervals
                open=Decimal(f"{50000 + i * 10}"),
                high=Decimal(f"{50100 + i * 10}"),
                low=Decimal(f"{49900 + i * 10}"),
                close=Decimal(f"{50050 + i * 10}"),
                volume=Decimal(f"{1000 + i * 50}"),
            )
            for i in range(5)
        ]

        converted = converter.convert_ohlcv_data(data)

        # Should have same number of data points for same timeframe
        assert len(converted) == 5

        # First point should match
        assert converted[0].open == data[0].open
        assert converted[0].close == data[0].close

    def test_convert_ohlcv_data_aggregation(self):
        """Test converting OHLCV data with aggregation."""
        converter = OHLCVConverter("5m")

        # Create 1-minute data (5 points = 1 five-minute candle)
        base_timestamp = 1642694400  # Round timestamp
        data = [
            OHLCVData(
                index=i,
                timestamp=base_timestamp + i * 60,  # 1 minute intervals
                open=Decimal(f"{50000 + i * 10}"),
                high=Decimal(f"{50100 + i * 10}"),
                low=Decimal(f"{49900 + i * 10}"),
                close=Decimal(f"{50050 + i * 10}"),
                volume=Decimal(f"{1000}"),  # Same volume for easy calculation
            )
            for i in range(5)
        ]

        converted = converter.convert_ohlcv_data(data)

        # Should aggregate into fewer data points
        assert len(converted) >= 1

        # Check aggregation logic
        if len(converted) == 1:
            aggregated = converted[0]
            assert aggregated.open == data[0].open  # First open
            assert aggregated.close == data[-1].close  # Last close
            assert aggregated.volume == Decimal("5000")  # Sum of volumes


class TestUtilityFunctions:
    """Test cases for utility functions."""

    def test_generate_session_id_default_length(self):
        """Test generating session ID with default length."""
        session_id = generate_session_id()

        assert len(session_id) == 12
        assert session_id.isalnum()

    def test_generate_session_id_custom_length(self):
        """Test generating session ID with custom length."""
        session_id = generate_session_id(20)

        assert len(session_id) == 20
        assert session_id.isalnum()

    def test_generate_session_id_uniqueness(self):
        """Test that generated session IDs are unique."""
        ids = [generate_session_id() for _ in range(100)]

        # All IDs should be unique
        assert len(set(ids)) == 100

    @pytest.mark.asyncio
    async def test_validate_symbols_async_valid(self):
        """Test validating valid symbols."""
        symbols = ["BINANCE:BTCUSDT", "NASDAQ:AAPL"]
        validation_url = "https://example.com/validate?symbol={exchange}%3A{symbol}"

        # Mock httpx.AsyncClient
        with patch("tvkit.api.chart.utils.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            result = await validate_symbols_async(symbols, validation_url)

            assert len(result) == 2
            assert "BINANCE:BTCUSDT" in result
            assert "NASDAQ:AAPL" in result

    @pytest.mark.asyncio
    async def test_validate_symbols_async_invalid_format(self):
        """Test validating symbols with invalid format."""
        symbols = ["INVALID_SYMBOL"]  # Missing colon
        validation_url = "https://example.com/validate?symbol={exchange}%3A{symbol}"

        with pytest.raises(ValueError, match="Invalid symbol format"):
            await validate_symbols_async(symbols, validation_url)

    @pytest.mark.asyncio
    async def test_validate_symbols_async_http_error(self):
        """Test validating symbols with HTTP errors."""
        symbols = ["BINANCE:BTCUSDT"]
        validation_url = "https://example.com/validate?symbol={exchange}%3A{symbol}"

        # Mock httpx.AsyncClient to raise HTTP error
        with patch("tvkit.api.chart.utils.httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("HTTP Error")
            )
            mock_client.return_value = mock_context

            result = await validate_symbols_async(symbols, validation_url)

            # Should return empty list if all symbols fail validation
            assert result == []


@pytest.fixture
def sample_ohlcv_data() -> List[OHLCVData]:
    """Fixture providing sample OHLCV data for testing."""
    return [
        OHLCVData(
            index=i,
            timestamp=1642694400 + i * 60,  # 1 minute intervals
            open=Decimal(f"{50000 + i * 10}"),
            high=Decimal(f"{50100 + i * 10}"),
            low=Decimal(f"{49900 + i * 10}"),
            close=Decimal(f"{50050 + i * 10}"),
            volume=Decimal(f"{1000 + i * 50}"),
        )
        for i in range(10)
    ]


class TestIntegration:
    """Integration tests for utility functions."""

    @pytest.mark.asyncio
    async def test_complete_export_workflow(self, sample_ohlcv_data: List[OHLCVData]):
        """Test complete export workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test all export formats
            export_formats = ["json", "csv", "parquet"]
            for export_format in export_formats:
                config = ExportConfig(
                    enabled=True,
                    format=export_format,  # type: ignore
                    directory=temp_dir,
                    filename_prefix=f"test_{export_format}",
                    include_timestamp=True,
                    auto_export_interval=None,
                )

                result = await export_data(
                    sample_ohlcv_data[:3],  # Use subset for faster testing
                    config,
                    "BINANCE:BTCUSDT",
                    "1m",
                )

                assert result is True

                # Check that file was created
                files = [
                    f
                    for f in os.listdir(temp_dir)
                    if f.startswith(f"test_{export_format}")
                ]
                assert len(files) >= 1
                assert files[0].endswith(f".{export_format}")

    def test_ohlcv_converter_integration(self, sample_ohlcv_data: List[OHLCVData]):
        """Test OHLCV converter with realistic data."""
        # Test converting 1m data to 5m
        converter = OHLCVConverter("5m")

        # Ensure we have enough data points
        assert len(sample_ohlcv_data) >= 5

        converted = converter.convert_ohlcv_data(sample_ohlcv_data)

        # Should have fewer data points after aggregation
        assert len(converted) <= len(sample_ohlcv_data)

        # Each converted point should be valid OHLCV data
        for point in converted:
            assert isinstance(point, OHLCVData)
            assert point.high >= point.low
            assert point.open >= point.low
            assert point.close >= point.low
            assert point.open <= point.high
            assert point.close <= point.high


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
