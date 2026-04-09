"""
Integration tests for DataExporter validation integration (Phase 3).

Tests for:
- to_csv(validate=False) skips validation
- to_csv(validate=True) logs violations
- to_csv(validate=True, strict=False) exports despite ERROR violations
- to_csv(validate=True, strict=True) raises DataIntegrityError on ERROR violations
- to_csv(validate=True, strict=True) does NOT raise on WARNING-only results
- DataIntegrityError.result carries the full ValidationResult
- strict=True does not write the file on ERROR violations
- scanner data silently skips validation
- interval is forwarded to validate_ohlcv
- violations are logged at WARNING with structured extra fields
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.api.scanner.models import StockData
from tvkit.export import DataExporter
from tvkit.validation import DataIntegrityError, ValidationResult, Violation, ViolationType

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_ohlcv_bars() -> list[OHLCVBar]:
    """Valid OHLCV bars: monotonic timestamps, valid OHLC, positive volume."""
    base_ts = 1_672_531_200.0  # 2023-01-01 UTC
    return [
        OHLCVBar(
            timestamp=base_ts + i * 86_400.0,
            open=100.0 + i,
            high=110.0 + i,
            low=90.0 + i,
            close=105.0 + i,
            volume=1_000.0 + i,
        )
        for i in range(5)
    ]


@pytest.fixture
def ohlcv_bars_with_error() -> list[OHLCVBar]:
    """OHLCV bars with one OHLC ERROR violation (open > high on bar 1)."""
    base_ts = 1_672_531_200.0
    bars = [
        OHLCVBar(
            timestamp=base_ts + i * 86_400.0,
            open=100.0 + i,
            high=110.0 + i,
            low=90.0 + i,
            close=105.0 + i,
            volume=1_000.0 + i,
        )
        for i in range(5)
    ]
    # Inject OHLC violation on bar 1: open > high
    bars[1] = OHLCVBar(
        timestamp=base_ts + 86_400.0,
        open=120.0,  # open > high → ERROR
        high=110.0,
        low=90.0,
        close=105.0,
        volume=1_000.0,
    )
    return bars


@pytest.fixture
def ohlcv_bars_with_gap_warning() -> list[OHLCVBar]:
    """
    OHLCV bars with a timestamp gap — produces GAP_DETECTED (WARNING) only.

    The gap is 3 days between bar 2 and bar 3 when cadence is 1D.
    """
    base_ts = 1_672_531_200.0
    return [
        OHLCVBar(
            timestamp=base_ts + 0 * 86_400.0,
            open=100.0,
            high=110.0,
            low=90.0,
            close=105.0,
            volume=1_000.0,
        ),
        OHLCVBar(
            timestamp=base_ts + 1 * 86_400.0,
            open=101.0,
            high=111.0,
            low=91.0,
            close=106.0,
            volume=1_001.0,
        ),
        OHLCVBar(
            # 3-day gap (2 missing bars) → GAP_DETECTED WARNING
            timestamp=base_ts + 4 * 86_400.0,
            open=104.0,
            high=114.0,
            low=94.0,
            close=109.0,
            volume=1_004.0,
        ),
        OHLCVBar(
            timestamp=base_ts + 5 * 86_400.0,
            open=105.0,
            high=115.0,
            low=95.0,
            close=110.0,
            volume=1_005.0,
        ),
    ]


@pytest.fixture
def scanner_stocks() -> list[StockData]:
    """Minimal scanner data for testing validation skip."""
    return [StockData(name="AAPL"), StockData(name="MSFT")]


# ---------------------------------------------------------------------------
# Helper: build a ValidationResult with violations of given severities
# ---------------------------------------------------------------------------


def _make_validation_result(*, errors: int = 0, warnings: int = 0) -> ValidationResult:
    """Build a ValidationResult with the requested number of violations."""
    violations: list[Violation] = []
    for i in range(errors):
        violations.append(
            Violation(
                check=ViolationType.OHLC_INCONSISTENCY,
                severity="ERROR",
                message=f"OHLC error #{i}",
                affected_rows=[i],
                context={},
            )
        )
    for i in range(warnings):
        violations.append(
            Violation(
                check=ViolationType.GAP_DETECTED,
                severity="WARNING",
                message=f"Gap warning #{i}",
                affected_rows=[i],
                context={},
            )
        )
    return ValidationResult(
        is_valid=errors == 0,
        violations=violations,
        bars_checked=10,
        checks_run=[ViolationType.OHLC_INCONSISTENCY],
    )


# ===========================================================================
# Tests: DataExporter.to_csv() validation integration
# ===========================================================================


class TestDataExporterValidationToCsv:
    """Integration tests for DataExporter.to_csv() validation parameters."""

    @pytest.mark.asyncio
    async def test_validate_false_skips_validation(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """validate=False (default) does not call validate_ohlcv."""
        exporter = DataExporter()
        with patch("tvkit.export.data_exporter.validate_ohlcv") as mock_validate:
            await exporter.to_csv(clean_ohlcv_bars, tmp_path / "out.csv")
        mock_validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_false_explicit_skips_validation(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """Explicitly passing validate=False does not call validate_ohlcv."""
        exporter = DataExporter()
        with patch("tvkit.export.data_exporter.validate_ohlcv") as mock_validate:
            await exporter.to_csv(clean_ohlcv_bars, tmp_path / "out.csv", validate=False)
        mock_validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_true_calls_validate_ohlcv(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """validate=True calls validate_ohlcv exactly once before export."""
        exporter = DataExporter()
        mock_result = _make_validation_result()
        with patch(
            "tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result
        ) as mock_validate:
            await exporter.to_csv(clean_ohlcv_bars, tmp_path / "out.csv", validate=True)
        mock_validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_true_clean_data_exports(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """Clean data: validate=True passes validation and file is written."""
        exporter = DataExporter()
        out = await exporter.to_csv(clean_ohlcv_bars, tmp_path / "out.csv", validate=True)
        assert out.exists()

    @pytest.mark.asyncio
    async def test_validate_strict_false_exports_despite_errors(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """validate=True, strict=False: ERROR violations are logged but file is written."""
        exporter = DataExporter()
        mock_result = _make_validation_result(errors=1)
        with patch("tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result):
            out = await exporter.to_csv(
                clean_ohlcv_bars,
                tmp_path / "out.csv",
                validate=True,
                strict=False,
            )
        assert out.exists()

    @pytest.mark.asyncio
    async def test_validate_strict_true_raises_on_errors(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """validate=True, strict=True: DataIntegrityError raised on ERROR violations."""
        exporter = DataExporter()
        mock_result = _make_validation_result(errors=2)
        with patch("tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result):
            with pytest.raises(DataIntegrityError):
                await exporter.to_csv(
                    clean_ohlcv_bars,
                    tmp_path / "out.csv",
                    validate=True,
                    strict=True,
                )

    @pytest.mark.asyncio
    async def test_validate_strict_true_no_raise_on_warnings_only(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """validate=True, strict=True: WARNING-only result does NOT raise; file written."""
        exporter = DataExporter()
        mock_result = _make_validation_result(warnings=3)
        with patch("tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result):
            out = await exporter.to_csv(
                clean_ohlcv_bars,
                tmp_path / "out.csv",
                validate=True,
                strict=True,
            )
        assert out.exists()

    @pytest.mark.asyncio
    async def test_data_integrity_error_carries_result(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """DataIntegrityError.result holds the full ValidationResult."""
        exporter = DataExporter()
        mock_result = _make_validation_result(errors=1)
        with patch("tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result):
            with pytest.raises(DataIntegrityError) as exc_info:
                await exporter.to_csv(
                    clean_ohlcv_bars,
                    tmp_path / "out.csv",
                    validate=True,
                    strict=True,
                )
        assert exc_info.value.result is mock_result
        assert len(exc_info.value.result.errors) == 1

    @pytest.mark.asyncio
    async def test_strict_true_does_not_write_file_on_errors(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """When strict=True and errors found, file is NOT written."""
        exporter = DataExporter()
        out_path = tmp_path / "should_not_exist.csv"
        mock_result = _make_validation_result(errors=1)
        with patch("tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result):
            with pytest.raises(DataIntegrityError):
                await exporter.to_csv(clean_ohlcv_bars, out_path, validate=True, strict=True)
        assert not out_path.exists()

    @pytest.mark.asyncio
    async def test_validate_with_interval_passed_through(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """interval is forwarded to validate_ohlcv for gap detection."""
        exporter = DataExporter()
        mock_result = _make_validation_result()
        with patch(
            "tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result
        ) as mock_validate:
            await exporter.to_csv(
                clean_ohlcv_bars,
                tmp_path / "out.csv",
                validate=True,
                interval="1D",
            )
        _, kwargs = mock_validate.call_args
        assert kwargs.get("interval") == "1D"

    @pytest.mark.asyncio
    async def test_scanner_data_skips_validation(
        self, scanner_stocks: list[StockData], tmp_path: Path
    ) -> None:
        """validate=True with scanner data silently skips validation."""
        exporter = DataExporter()
        with patch("tvkit.export.data_exporter.validate_ohlcv") as mock_validate:
            await exporter.to_csv(
                scanner_stocks,  # type: ignore[arg-type]
                tmp_path / "out.csv",
                validate=True,
            )
        mock_validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_list_skips_validation(self, tmp_path: Path) -> None:
        """validate=True with an empty list silently skips validation."""
        exporter = DataExporter()
        with patch("tvkit.export.data_exporter.validate_ohlcv") as mock_validate:
            # Empty list export may fail (no formatter output), but validation should not run
            try:
                await exporter.to_csv(
                    [],  # type: ignore[arg-type]
                    tmp_path / "out.csv",
                    validate=True,
                )
            except (RuntimeError, Exception):
                pass  # Export itself may fail on empty input — that is expected
        mock_validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_violations_logged_at_warning_with_extra_fields(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """Violations are logged at WARNING level with check (str) and rows extra fields."""
        exporter = DataExporter()
        violation = Violation(
            check=ViolationType.OHLC_INCONSISTENCY,
            severity="ERROR",
            message="open exceeds high",
            affected_rows=[1],
            context={},
        )
        mock_result = ValidationResult(
            is_valid=False,
            violations=[violation],
            bars_checked=5,
            checks_run=[ViolationType.OHLC_INCONSISTENCY],
        )
        with patch("tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result):
            with patch("tvkit.export.data_exporter.logger") as mock_logger:
                with pytest.raises(DataIntegrityError):
                    await exporter.to_csv(
                        clean_ohlcv_bars,
                        tmp_path / "out.csv",
                        validate=True,
                        strict=True,
                    )

        mock_logger.warning.assert_called_once_with(
            "open exceeds high",
            extra={
                "check": ViolationType.OHLC_INCONSISTENCY.value,
                "rows": [1],
            },
        )

    @pytest.mark.asyncio
    async def test_check_value_in_log_is_string(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """The 'check' field in the log extra is a plain string, not an enum object."""
        exporter = DataExporter()
        violation = Violation(
            check=ViolationType.DUPLICATE_TIMESTAMP,
            severity="ERROR",
            message="duplicate",
            affected_rows=[0],
            context={},
        )
        mock_result = ValidationResult(
            is_valid=False,
            violations=[violation],
            bars_checked=5,
            checks_run=[ViolationType.DUPLICATE_TIMESTAMP],
        )
        logged_calls: list[dict] = []

        def capture_warning(msg: str, **kwargs: object) -> None:
            extra = kwargs.get("extra", {})
            logged_calls.append({"msg": msg, "extra": extra})

        with patch("tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result):
            with patch("tvkit.export.data_exporter.logger") as mock_logger:
                mock_logger.warning.side_effect = capture_warning
                with pytest.raises(DataIntegrityError):
                    await exporter.to_csv(
                        clean_ohlcv_bars,
                        tmp_path / "out.csv",
                        validate=True,
                        strict=True,
                    )

        assert len(logged_calls) == 1
        check_val = logged_calls[0]["extra"]["check"]
        assert isinstance(check_val, str)
        assert check_val == "duplicate_timestamp"

    @pytest.mark.asyncio
    async def test_real_ohlcv_error_raises_on_strict(
        self, ohlcv_bars_with_error: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """End-to-end: real OHLC error bars + strict=True raises DataIntegrityError."""
        exporter = DataExporter()
        with pytest.raises(DataIntegrityError) as exc_info:
            await exporter.to_csv(
                ohlcv_bars_with_error,
                tmp_path / "out.csv",
                validate=True,
                strict=True,
            )
        assert not exc_info.value.result.is_valid
        assert len(exc_info.value.result.errors) >= 1

    @pytest.mark.asyncio
    async def test_real_gap_warning_does_not_raise_on_strict(
        self, ohlcv_bars_with_gap_warning: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """End-to-end: gap warning + strict=True does NOT raise; file is written."""
        exporter = DataExporter()
        out = await exporter.to_csv(
            ohlcv_bars_with_gap_warning,
            tmp_path / "out.csv",
            validate=True,
            strict=True,
            interval="1D",
        )
        assert out.exists()

    @pytest.mark.asyncio
    async def test_multiple_violations_each_logged(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """Each violation generates one logger.warning call."""
        exporter = DataExporter()
        mock_result = _make_validation_result(errors=3)
        with patch("tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result):
            with patch("tvkit.export.data_exporter.logger") as mock_logger:
                with pytest.raises(DataIntegrityError):
                    await exporter.to_csv(
                        clean_ohlcv_bars,
                        tmp_path / "out.csv",
                        validate=True,
                        strict=True,
                    )
        assert mock_logger.warning.call_count == 3

    @pytest.mark.asyncio
    async def test_validate_no_interval_skips_gap_detection(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """validate=True without interval: gap detection silently skipped in validate_ohlcv."""
        exporter = DataExporter()
        mock_result = _make_validation_result()
        with patch(
            "tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result
        ) as mock_validate:
            await exporter.to_csv(clean_ohlcv_bars, tmp_path / "out.csv", validate=True)
        _, kwargs = mock_validate.call_args
        assert kwargs.get("interval") is None


# ===========================================================================
# Tests: DataExporter.to_json() validation integration
# ===========================================================================


class TestDataExporterValidationToJson:
    """Integration tests for DataExporter.to_json() validation parameters."""

    @pytest.mark.asyncio
    async def test_validate_false_skips_validation(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """validate=False (default) does not call validate_ohlcv."""
        exporter = DataExporter()
        with patch("tvkit.export.data_exporter.validate_ohlcv") as mock_validate:
            await exporter.to_json(clean_ohlcv_bars, tmp_path / "out.json")
        mock_validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_strict_true_raises_on_errors(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """validate=True, strict=True: DataIntegrityError raised on ERROR violations."""
        exporter = DataExporter()
        mock_result = _make_validation_result(errors=1)
        with patch("tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result):
            with pytest.raises(DataIntegrityError):
                await exporter.to_json(
                    clean_ohlcv_bars,
                    tmp_path / "out.json",
                    validate=True,
                    strict=True,
                )

    @pytest.mark.asyncio
    async def test_validate_strict_true_no_raise_on_warnings_only(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """validate=True, strict=True: WARNING-only does not raise; file written."""
        exporter = DataExporter()
        mock_result = _make_validation_result(warnings=2)
        with patch("tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result):
            out = await exporter.to_json(
                clean_ohlcv_bars,
                tmp_path / "out.json",
                validate=True,
                strict=True,
            )
        assert out.exists()

    @pytest.mark.asyncio
    async def test_strict_true_does_not_write_file_on_errors(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """When strict=True and errors found, JSON file is NOT written."""
        exporter = DataExporter()
        out_path = tmp_path / "should_not_exist.json"
        mock_result = _make_validation_result(errors=1)
        with patch("tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result):
            with pytest.raises(DataIntegrityError):
                await exporter.to_json(clean_ohlcv_bars, out_path, validate=True, strict=True)
        assert not out_path.exists()

    @pytest.mark.asyncio
    async def test_validate_with_interval_passed_through(
        self, clean_ohlcv_bars: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """interval is forwarded to validate_ohlcv for gap detection."""
        exporter = DataExporter()
        mock_result = _make_validation_result()
        with patch(
            "tvkit.export.data_exporter.validate_ohlcv", return_value=mock_result
        ) as mock_validate:
            await exporter.to_json(
                clean_ohlcv_bars,
                tmp_path / "out.json",
                validate=True,
                interval="1H",
            )
        _, kwargs = mock_validate.call_args
        assert kwargs.get("interval") == "1H"

    @pytest.mark.asyncio
    async def test_real_ohlcv_error_raises_on_strict(
        self, ohlcv_bars_with_error: list[OHLCVBar], tmp_path: Path
    ) -> None:
        """End-to-end: real OHLC error bars + strict=True raises DataIntegrityError."""
        exporter = DataExporter()
        with pytest.raises(DataIntegrityError) as exc_info:
            await exporter.to_json(
                ohlcv_bars_with_error,
                tmp_path / "out.json",
                validate=True,
                strict=True,
            )
        assert len(exc_info.value.result.errors) >= 1
