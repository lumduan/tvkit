"""
Tests for OHLCV models in real-time streaming.

This module tests the parsing and validation of OHLCV data structures
received from TradingView's WebSocket API.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from tvkit.api.chart.models.ohlcv import (
    LastBarStatus,
    NamespaceData,
    OHLCVBar,
    OHLCVResponse,
    SeriesData,
)


class TestOHLCVBar:
    """Test cases for OHLCVBar model."""

    def test_ohlcv_bar_creation(self):
        """Test creating an OHLCVBar with valid data."""
        bar = OHLCVBar(
            timestamp=1753692060.0,
            open=118881.76,
            high=118881.76,
            low=118881.75,
            close=118881.75,
            volume=0.95897,
        )

        assert bar.timestamp == 1753692060.0
        assert bar.open == 118881.76
        assert bar.high == 118881.76
        assert bar.low == 118881.75
        assert bar.close == 118881.75
        assert bar.volume == 0.95897

    def test_ohlcv_bar_from_array(self):
        """Test creating an OHLCVBar from array format."""
        data = [1753692060.0, 118881.76, 118881.76, 118881.75, 118881.75, 0.95897]
        bar = OHLCVBar.from_array(data)

        assert bar.timestamp == 1753692060.0
        assert bar.open == 118881.76
        assert bar.high == 118881.76
        assert bar.low == 118881.75
        assert bar.close == 118881.75
        assert bar.volume == 0.95897

    def test_ohlcv_bar_from_array_invalid_length(self):
        """Test that from_array raises error with invalid array length."""
        with pytest.raises(ValueError, match="Expected 6 elements"):
            OHLCVBar.from_array([1, 2, 3, 4, 5])  # Only 5 elements

    def test_ohlcv_bar_validation(self) -> None:
        """Test OHLCVBar field validation."""
        # Test with negative volume (business logic validation could be added)
        bar = OHLCVBar(
            timestamp=1753692060.0,
            open=100.0,
            high=110.0,
            low=90.0,
            close=105.0,
            volume=-1000.0,  # Negative volume
        )
        # This should work - the model doesn't enforce business rules
        assert bar.volume == -1000.0


class TestSeriesData:
    """Test cases for SeriesData model."""

    def test_series_data_creation(self):
        """Test creating SeriesData with valid data."""
        data = SeriesData(
            i=9, v=[1753692060.0, 118881.76, 118881.76, 118881.75, 118881.75, 0.95897]
        )

        assert data.index == 9
        assert len(data.values) == 6
        assert data.ohlcv_bar.timestamp == 1753692060.0
        assert data.ohlcv_bar.open == 118881.76

    def test_series_data_alias_parsing(self):
        """Test SeriesData parsing with field aliases."""
        raw_data: dict[str, Any] = {
            "i": 9,
            "v": [1753692060.0, 118881.76, 118881.76, 118881.75, 118881.75, 0.95897],
        }

        data = SeriesData.model_validate(raw_data)
        assert data.index == 9
        assert data.ohlcv_bar.close == 118881.75


class TestOHLCVResponse:
    """Test cases for complete OHLCV response parsing."""

    @pytest.fixture
    def sample_response_data(self) -> dict[str, Any]:
        """Sample response data from TradingView."""
        return {
            "m": "du",
            "p": [
                "cs_wrouuzfexqom",
                {
                    "sds_1": {
                        "s": [
                            {
                                "i": 9,
                                "v": [
                                    1753692060.0,
                                    118881.76,
                                    118881.76,
                                    118881.75,
                                    118881.75,
                                    0.95897,
                                ],
                            }
                        ],
                        "ns": {"d": "", "indexes": "nochange"},
                        "t": "s1",
                        "lbs": {"bar_close_time": 1753692120},
                    }
                },
            ],
        }

    def test_ohlcv_response_parsing(self, sample_response_data: dict[str, Any]) -> None:
        """Test parsing complete OHLCV response."""
        response = OHLCVResponse.model_validate(sample_response_data)

        assert response.message_type == "du"
        assert response.session_id == "cs_wrouuzfexqom"
        assert len(response.series_updates) == 1
        assert "sds_1" in response.series_updates

        series_update = response.series_updates["sds_1"]
        assert len(series_update.series_data) == 1
        assert series_update.series_data[0].index == 9
        assert series_update.last_bar_status.bar_close_time == 1753692120

    def test_ohlcv_bars_extraction(self, sample_response_data: dict[str, Any]) -> None:
        """Test extracting OHLCV bars from response."""
        response = OHLCVResponse.model_validate(sample_response_data)
        ohlcv_bars = response.ohlcv_bars

        assert len(ohlcv_bars) == 1
        bar = ohlcv_bars[0]
        assert bar.timestamp == 1753692060.0
        assert bar.open == 118881.76
        assert bar.high == 118881.76
        assert bar.low == 118881.75
        assert bar.close == 118881.75
        assert bar.volume == 0.95897

    def test_invalid_message_type(self):
        """Test validation of message type."""
        with pytest.raises(ValidationError, match="Expected message type 'du'"):
            OHLCVResponse.model_validate({"m": "invalid", "p": ["session", {}]})

    def test_insufficient_parameters(self):
        """Test validation of parameters length."""
        with pytest.raises(ValidationError, match="Parameters must contain at least"):
            OHLCVResponse.model_validate({"m": "du", "p": ["session_only"]})

    def test_partial_parsing_resilience(self):
        """Test that partial parsing works when some series data is invalid."""
        data: dict[str, Any] = {
            "m": "du",
            "p": [
                "session_id",
                {
                    "valid_series": {
                        "s": [{"i": 1, "v": [1, 2, 3, 4, 5, 6]}],
                        "ns": {"d": ""},
                        "t": "s1",
                        "lbs": {"bar_close_time": 123},
                    },
                    "invalid_series": {
                        # Missing required fields
                        "s": []
                    },
                },
            ],
        }

        response = OHLCVResponse.model_validate(data)
        # Should parse the valid series and skip the invalid one
        assert len(response.series_updates) == 1
        assert "valid_series" in response.series_updates
        assert "invalid_series" not in response.series_updates


class TestNamespaceData:
    """Test cases for NamespaceData model."""

    def test_namespace_data_creation(self):
        """Test creating NamespaceData."""
        ns = NamespaceData(d="test description", indexes="change")
        assert ns.description == "test description"
        assert ns.indexes == "change"

    def test_namespace_data_defaults(self):
        """Test NamespaceData with default values."""
        ns = NamespaceData()
        assert ns.description == ""
        assert ns.indexes == "nochange"


class TestLastBarStatus:
    """Test cases for LastBarStatus model."""

    def test_last_bar_status_creation(self):
        """Test creating LastBarStatus."""
        lbs = LastBarStatus(bar_close_time=1753692120.0)
        assert lbs.bar_close_time == 1753692120.0

    def test_last_bar_status_validation(self) -> None:
        """Test LastBarStatus field validation."""
        # Test with valid data
        lbs = LastBarStatus(bar_close_time=1753692120.0)
        assert lbs.bar_close_time == 1753692120.0
