"""Tests for ``DataExporter.to_polars(timestamp_format=...)`` and its consumers.

``to_polars()`` used to hard-code the default ``ExportConfig``, whose ``timestamp_format`` is
``"iso"`` — a ``String`` column that both :func:`tvkit.validation.validate_ohlcv` and
:func:`tvkit.time.convert_to_timezone` reject. There was no way to ask ``to_polars()`` for a
numeric column, so tvkit's own documented pipeline did not compose.
"""

from datetime import UTC, datetime

import polars as pl
import pytest

from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.export import DataExporter
from tvkit.time import convert_to_exchange_timezone, convert_to_timezone
from tvkit.validation import validate_ohlcv

# Three consecutive daily bars, 2026-01-01..03 UTC. Synthetic — no network.
BARS: list[OHLCVBar] = [
    OHLCVBar(timestamp=1767225600.0, open=100.0, high=101.0, low=99.0, close=100.5, volume=1000.0),
    OHLCVBar(timestamp=1767312000.0, open=100.5, high=102.0, low=100.0, close=101.5, volume=1200.0),
    OHLCVBar(timestamp=1767398400.0, open=101.5, high=103.0, low=101.0, close=102.5, volume=1100.0),
]


@pytest.fixture
def exporter() -> DataExporter:
    return DataExporter()


@pytest.mark.asyncio
async def test_default_is_unchanged(exporter: DataExporter) -> None:
    """Omitting the argument must behave exactly as before — a String column."""
    df = await exporter.to_polars(BARS)

    assert df["timestamp"].dtype == pl.String
    assert df["timestamp"][0] == "2026-01-01T00:00:00+00:00"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fmt", "expected"),
    [
        ("iso", pl.String),
        ("unix", pl.Float64),
        ("datetime", pl.Datetime(time_unit="us", time_zone="UTC")),
    ],
)
async def test_timestamp_format_selects_the_dtype(
    exporter: DataExporter, fmt: str, expected: pl.DataType
) -> None:
    """Each accepted value produces the documented dtype."""
    df = await exporter.to_polars(BARS, timestamp_format=fmt)  # type: ignore[arg-type]

    assert df["timestamp"].dtype == expected


@pytest.mark.asyncio
async def test_timestamp_format_is_keyword_only(exporter: DataExporter) -> None:
    """It must not be passable positionally, where it would collide with add_analysis."""
    with pytest.raises(TypeError):
        await exporter.to_polars(BARS, False, "unix")  # type: ignore[misc]


@pytest.mark.asyncio
async def test_invalid_timestamp_format_is_rejected(exporter: DataExporter) -> None:
    """ExportConfig validates the value, so a typo fails loudly."""
    with pytest.raises(ValueError, match="timestamp_format"):
        await exporter.to_polars(BARS, timestamp_format="epoch")  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["unix", "datetime"])
async def test_numeric_and_temporal_frames_validate(exporter: DataExporter, fmt: str) -> None:
    """The whole point: the frame chains straight into validate_ohlcv()."""
    df = await exporter.to_polars(BARS, timestamp_format=fmt)  # type: ignore[arg-type]

    result = validate_ohlcv(df, interval="1D")

    assert result.is_valid
    assert result.bars_checked == len(BARS)


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["unix", "datetime"])
async def test_numeric_and_temporal_frames_convert_timezone(
    exporter: DataExporter, fmt: str
) -> None:
    """...and straight into a timezone conversion."""
    df = await exporter.to_polars(BARS, timestamp_format=fmt)  # type: ignore[arg-type]

    local = convert_to_exchange_timezone(df, "NASDAQ")

    assert local["timestamp"].dtype == pl.Datetime(time_unit="us", time_zone="America/New_York")
    # The instant is preserved, only its rendering changes: 2026-01-01T00:00Z is 19:00 on
    # 2025-12-31 in New York (UTC-5).
    assert local["timestamp"][0] == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert (local["timestamp"][0].hour, local["timestamp"][0].day) == (19, 31)
    # The source frame is never mutated.
    assert df["timestamp"].dtype != pl.Datetime(time_unit="us", time_zone="America/New_York")


@pytest.mark.asyncio
async def test_iso_frame_names_the_fix_in_the_validation_error(exporter: DataExporter) -> None:
    """The default still fails — but the message says what to pass instead."""
    df = await exporter.to_polars(BARS, timestamp_format="iso")

    with pytest.raises(ValueError, match=r'timestamp_format="unix"'):
        validate_ohlcv(df, interval="1D")


@pytest.mark.asyncio
async def test_iso_frame_names_the_fix_in_the_conversion_error(exporter: DataExporter) -> None:
    """Previously an opaque polars 'arithmetic on string and numeric' error."""
    df = await exporter.to_polars(BARS, timestamp_format="iso")

    with pytest.raises(ValueError, match=r'timestamp_format="unix"'):
        convert_to_timezone(df, "Asia/Bangkok")


@pytest.mark.asyncio
async def test_scanner_input_ignores_timestamp_format(exporter: DataExporter) -> None:
    """Scanner frames have no epoch column; export_timestamp stays an ISO string."""
    from tvkit.api.scanner.models import StockData

    rows = [StockData(name="AAPL", close=305.59, currency="USD")]

    df = await exporter.to_polars(rows, timestamp_format="unix")  # type: ignore[arg-type]

    assert df["export_timestamp"].dtype == pl.String
