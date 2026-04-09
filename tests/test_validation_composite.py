"""
Integration tests for tvkit.validation.validate_ohlcv() composite validator.

Tests for:
- validate_ohlcv() orchestration and deterministic check ordering
- Schema validation (_require_ohlcv_schema via validate_ohlcv)
- Selective checks via the checks= parameter
- Gap detection skip/raise behaviour based on interval and checks arguments
- ValidationResult.is_valid flag, errors, warnings properties
"""

from datetime import UTC, date, datetime

import polars as pl
import pytest

from tvkit.validation import (
    ValidationResult,
    Violation,
    ViolationType,
    validate_ohlcv,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_TS = 1_700_000_000.0  # 2023-11-14 22:13:20 UTC (Float64 epoch seconds)
_DAY = 86_400.0
_HOUR = 3_600.0


def _make_df(
    timestamps: list[float] | None = None,
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    closes: list[float] | None = None,
    volumes: list[float] | None = None,
    n: int = 3,
    ts_dtype: pl.DataType = pl.Float64,
) -> pl.DataFrame:
    """Build a valid OHLCV DataFrame with clean data by default."""
    if timestamps is None:
        timestamps = [_BASE_TS + i * _DAY for i in range(n)]
    n = len(timestamps)
    return pl.DataFrame(
        {
            "timestamp": pl.Series(timestamps, dtype=ts_dtype),
            "open": pl.Series(opens if opens is not None else [100.0] * n, dtype=pl.Float64),
            "high": pl.Series(highs if highs is not None else [110.0] * n, dtype=pl.Float64),
            "low": pl.Series(lows if lows is not None else [90.0] * n, dtype=pl.Float64),
            "close": pl.Series(closes if closes is not None else [105.0] * n, dtype=pl.Float64),
            "volume": pl.Series(volumes if volumes is not None else [1000.0] * n, dtype=pl.Float64),
        }
    )


def _make_datetime_df(n: int = 3) -> pl.DataFrame:
    """Build a valid OHLCV DataFrame with Datetime timestamps."""
    base = datetime(2023, 11, 14, tzinfo=UTC)
    from datetime import timedelta

    timestamps = [base + timedelta(days=i) for i in range(n)]
    return pl.DataFrame(
        {
            "timestamp": pl.Series(timestamps).cast(pl.Datetime("us", "UTC")),
            "open": pl.Series([100.0] * n, dtype=pl.Float64),
            "high": pl.Series([110.0] * n, dtype=pl.Float64),
            "low": pl.Series([90.0] * n, dtype=pl.Float64),
            "close": pl.Series([105.0] * n, dtype=pl.Float64),
            "volume": pl.Series([1000.0] * n, dtype=pl.Float64),
        }
    )


def _make_date_df(n: int = 3) -> pl.DataFrame:
    """Build a valid OHLCV DataFrame with Date timestamps."""
    from datetime import timedelta

    base = date(2023, 11, 14)
    timestamps = [base + timedelta(days=i) for i in range(n)]
    return pl.DataFrame(
        {
            "timestamp": pl.Series(timestamps, dtype=pl.Date),
            "open": pl.Series([100.0] * n, dtype=pl.Float64),
            "high": pl.Series([110.0] * n, dtype=pl.Float64),
            "low": pl.Series([90.0] * n, dtype=pl.Float64),
            "close": pl.Series([105.0] * n, dtype=pl.Float64),
            "volume": pl.Series([1000.0] * n, dtype=pl.Float64),
        }
    )


# ===========================================================================
# Schema Validation Tests
# ===========================================================================


class TestSchemaValidation:
    def test_missing_timestamp_raises(self) -> None:
        df = pl.DataFrame(
            {
                "open": [100.0],
                "high": [110.0],
                "low": [90.0],
                "close": [105.0],
                "volume": [1000.0],
            }
        )
        with pytest.raises(ValueError, match="timestamp"):
            validate_ohlcv(df)

    def test_missing_open_raises(self) -> None:
        df = _make_df()
        df = df.drop("open")
        with pytest.raises(ValueError, match="open"):
            validate_ohlcv(df)

    def test_missing_high_raises(self) -> None:
        df = _make_df()
        df = df.drop("high")
        with pytest.raises(ValueError, match="high"):
            validate_ohlcv(df)

    def test_missing_low_raises(self) -> None:
        df = _make_df()
        df = df.drop("low")
        with pytest.raises(ValueError, match="low"):
            validate_ohlcv(df)

    def test_missing_close_raises(self) -> None:
        df = _make_df()
        df = df.drop("close")
        with pytest.raises(ValueError, match="close"):
            validate_ohlcv(df)

    def test_missing_volume_raises(self) -> None:
        df = _make_df()
        df = df.drop("volume")
        with pytest.raises(ValueError, match="volume"):
            validate_ohlcv(df)

    def test_wrong_dtype_on_open_raises(self) -> None:
        df = _make_df()
        df = df.with_columns(pl.col("open").cast(pl.Utf8))
        with pytest.raises(ValueError, match="open"):
            validate_ohlcv(df)

    def test_wrong_dtype_on_volume_raises(self) -> None:
        df = _make_df()
        df = df.with_columns(pl.col("volume").cast(pl.Utf8))
        with pytest.raises(ValueError, match="volume"):
            validate_ohlcv(df)

    def test_wrong_dtype_on_timestamp_raises(self) -> None:
        df = _make_df()
        df = df.with_columns(pl.col("timestamp").cast(pl.Utf8))
        with pytest.raises(ValueError, match="timestamp"):
            validate_ohlcv(df)

    def test_empty_dataframe_passes_schema(self) -> None:
        df = _make_df(n=0)
        result = validate_ohlcv(df)
        assert result.is_valid is True
        assert result.violations == []
        assert result.bars_checked == 0

    def test_float64_timestamp_accepted(self) -> None:
        df = _make_df(ts_dtype=pl.Float64)
        result = validate_ohlcv(df)
        assert result.is_valid is True

    def test_int64_timestamp_accepted(self) -> None:
        base_int = int(_BASE_TS)
        df = _make_df(
            timestamps=[float(base_int + i * int(_DAY)) for i in range(3)],
            ts_dtype=pl.Float64,
        )
        df = df.with_columns(pl.col("timestamp").cast(pl.Int64))
        result = validate_ohlcv(df)
        assert result.is_valid is True

    def test_datetime_timestamp_accepted(self) -> None:
        df = _make_datetime_df()
        result = validate_ohlcv(df)
        assert result.is_valid is True

    def test_date_timestamp_accepted(self) -> None:
        df = _make_date_df()
        result = validate_ohlcv(df)
        assert result.is_valid is True

    def test_float32_prices_accepted(self) -> None:
        df = _make_df()
        df = df.with_columns(
            pl.col("open").cast(pl.Float32),
            pl.col("high").cast(pl.Float32),
            pl.col("low").cast(pl.Float32),
            pl.col("close").cast(pl.Float32),
        )
        result = validate_ohlcv(df)
        assert result.is_valid is True

    def test_int64_volume_accepted(self) -> None:
        df = _make_df()
        df = df.with_columns(pl.col("volume").cast(pl.Int64))
        result = validate_ohlcv(df)
        assert result.is_valid is True


# ===========================================================================
# Core Orchestration Tests
# ===========================================================================


class TestValidateOhlcvOrchestration:
    def test_clean_data_is_valid(self) -> None:
        df = _make_df()
        result = validate_ohlcv(df)
        assert result.is_valid is True
        assert result.violations == []

    def test_bars_checked_equals_row_count(self) -> None:
        df = _make_df(n=5)
        result = validate_ohlcv(df)
        assert result.bars_checked == 5

    def test_bars_checked_zero_for_empty_df(self) -> None:
        df = _make_df(n=0)
        result = validate_ohlcv(df)
        assert result.bars_checked == 0

    def test_checks_run_without_interval_excludes_gap(self) -> None:
        df = _make_df()
        result = validate_ohlcv(df)
        assert ViolationType.GAP_DETECTED not in result.checks_run
        assert ViolationType.DUPLICATE_TIMESTAMP in result.checks_run
        assert ViolationType.NON_MONOTONIC_TIMESTAMP in result.checks_run
        assert ViolationType.OHLC_INCONSISTENCY in result.checks_run
        assert ViolationType.NEGATIVE_VOLUME in result.checks_run

    def test_checks_run_with_interval_includes_gap(self) -> None:
        df = _make_df()
        result = validate_ohlcv(df, interval="1D")
        assert ViolationType.GAP_DETECTED in result.checks_run

    def test_checks_run_order_is_deterministic(self) -> None:
        df = _make_df()
        result = validate_ohlcv(df, interval="1D")
        expected_order = [
            ViolationType.DUPLICATE_TIMESTAMP,
            ViolationType.NON_MONOTONIC_TIMESTAMP,
            ViolationType.OHLC_INCONSISTENCY,
            ViolationType.NEGATIVE_VOLUME,
            ViolationType.GAP_DETECTED,
        ]
        assert result.checks_run == expected_order

    def test_error_violation_sets_is_valid_false(self) -> None:
        # Duplicate timestamps cause ERROR violation
        ts = _BASE_TS
        df = _make_df(timestamps=[ts, ts, ts + _DAY])
        result = validate_ohlcv(df)
        assert result.is_valid is False

    def test_warning_violation_leaves_is_valid_true(self) -> None:
        # Weekend gap for daily interval: Friday → Monday (3-day span > 1-day expected)
        friday = _BASE_TS
        monday = friday + 3 * _DAY  # skip weekend
        df = _make_df(timestamps=[friday, monday])
        result = validate_ohlcv(df, interval="1D")
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert result.warnings[0].check == ViolationType.GAP_DETECTED

    def test_mixed_error_and_warning_is_valid_false(self) -> None:
        # Duplicate timestamps (ERROR) + gap (WARNING)
        ts = _BASE_TS
        friday = ts + 10 * _DAY
        monday = friday + 3 * _DAY  # gap
        # Duplicate appears before the gap data
        df = _make_df(timestamps=[ts, ts, ts + _DAY, friday, monday])
        result = validate_ohlcv(df, interval="1D")
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert len(result.warnings) >= 1

    def test_returns_validation_result_type(self) -> None:
        df = _make_df()
        result = validate_ohlcv(df)
        assert isinstance(result, ValidationResult)

    def test_violations_are_violation_instances(self) -> None:
        ts = _BASE_TS
        df = _make_df(timestamps=[ts, ts])
        result = validate_ohlcv(df)
        assert all(isinstance(v, Violation) for v in result.violations)


# ===========================================================================
# Gap Detection Behavior Tests
# ===========================================================================


class TestValidateOhlcvGapDetection:
    def test_no_interval_gap_detection_silently_skipped(self) -> None:
        # Even with obvious gaps, no gap violations without interval
        df = _make_df(timestamps=[_BASE_TS, _BASE_TS + 100 * _DAY])
        result = validate_ohlcv(df)
        gap_violations = [v for v in result.violations if v.check == ViolationType.GAP_DETECTED]
        assert gap_violations == []
        assert ViolationType.GAP_DETECTED not in result.checks_run

    def test_with_interval_gap_violations_reported(self) -> None:
        friday = _BASE_TS
        monday = friday + 3 * _DAY
        df = _make_df(timestamps=[friday, monday])
        result = validate_ohlcv(df, interval="1D")
        gap_violations = [v for v in result.violations if v.check == ViolationType.GAP_DETECTED]
        assert len(gap_violations) == 1
        assert gap_violations[0].severity == "WARNING"

    def test_explicit_gap_detected_without_interval_raises(self) -> None:
        df = _make_df()
        with pytest.raises(ValueError, match="interval"):
            validate_ohlcv(df, checks=[ViolationType.GAP_DETECTED])

    def test_explicit_gap_detected_with_interval_runs(self) -> None:
        df = _make_df(timestamps=[_BASE_TS, _BASE_TS + _DAY, _BASE_TS + 2 * _DAY])
        result = validate_ohlcv(df, interval="1D", checks=[ViolationType.GAP_DETECTED])
        assert ViolationType.GAP_DETECTED in result.checks_run
        assert result.violations == []  # exact cadence, no gaps

    def test_gap_detection_exact_cadence_no_violations(self) -> None:
        df = _make_df(
            timestamps=[_BASE_TS + i * _HOUR for i in range(5)],
        )
        result = validate_ohlcv(df, interval="1H")
        gap_violations = [v for v in result.violations if v.check == ViolationType.GAP_DETECTED]
        assert gap_violations == []

    def test_gap_detection_sub_interval_spacing_no_violation(self) -> None:
        # Bars closer than expected — not a gap
        df = _make_df(
            timestamps=[_BASE_TS, _BASE_TS + _HOUR / 2],
        )
        result = validate_ohlcv(df, interval="1H")
        gap_violations = [v for v in result.violations if v.check == ViolationType.GAP_DETECTED]
        assert gap_violations == []


# ===========================================================================
# Selective Checks Tests
# ===========================================================================


class TestValidateOhlcvSelectiveChecks:
    def test_single_check_requested_only_that_runs(self) -> None:
        df = _make_df()
        result = validate_ohlcv(df, checks=[ViolationType.DUPLICATE_TIMESTAMP])
        assert result.checks_run == [ViolationType.DUPLICATE_TIMESTAMP]

    def test_single_check_does_not_report_other_violations(self) -> None:
        # OHLC violation present — but we only request duplicate check
        df = _make_df(opens=[200.0, 100.0, 100.0])  # open > high (110) — OHLC error
        result = validate_ohlcv(df, checks=[ViolationType.DUPLICATE_TIMESTAMP])
        # No OHLC violation reported since OHLC check not requested
        ohlc_violations = [
            v for v in result.violations if v.check == ViolationType.OHLC_INCONSISTENCY
        ]
        assert ohlc_violations == []
        # Result should be valid (no duplicate timestamps)
        assert result.is_valid is True

    def test_multiple_checks_run_in_deterministic_order(self) -> None:
        df = _make_df()
        # Request in reversed order
        checks = [ViolationType.NEGATIVE_VOLUME, ViolationType.DUPLICATE_TIMESTAMP]
        result = validate_ohlcv(df, checks=checks)
        # Execution order must follow _CHECK_ORDER regardless of request order
        assert result.checks_run == [
            ViolationType.DUPLICATE_TIMESTAMP,
            ViolationType.NEGATIVE_VOLUME,
        ]

    def test_unknown_check_type_raises(self) -> None:
        df = _make_df()
        with pytest.raises(ValueError, match="Unknown check type"):
            validate_ohlcv(df, checks=["not_a_real_check"])  # type: ignore[list-item]

    def test_empty_checks_list_returns_no_violations(self) -> None:
        df = _make_df(timestamps=[_BASE_TS, _BASE_TS])  # would cause duplicate error
        result = validate_ohlcv(df, checks=[])
        assert result.violations == []
        assert result.checks_run == []
        assert result.is_valid is True

    def test_all_checks_explicitly_run_with_interval(self) -> None:
        df = _make_df()
        all_checks = list(ViolationType)
        result = validate_ohlcv(df, interval="1D", checks=all_checks)
        assert set(result.checks_run) == set(ViolationType)

    def test_selective_gap_check_with_interval_returns_violations(self) -> None:
        friday = _BASE_TS
        monday = friday + 3 * _DAY
        df = _make_df(timestamps=[friday, monday])
        result = validate_ohlcv(
            df,
            interval="1D",
            checks=[ViolationType.GAP_DETECTED],
        )
        assert len(result.violations) == 1
        assert result.violations[0].check == ViolationType.GAP_DETECTED


# ===========================================================================
# Deterministic Ordering Tests
# ===========================================================================


class TestViolationOrdering:
    def test_violations_ordered_by_check_type_then_row(self) -> None:
        # Create a DataFrame with both a DUPLICATE_TIMESTAMP violation (row 0,1)
        # and an OHLC violation (row 2)
        ts = _BASE_TS
        df = pl.DataFrame(
            {
                "timestamp": pl.Series([ts, ts, ts + _DAY, ts + 2 * _DAY], dtype=pl.Float64),
                "open": pl.Series(
                    [100.0, 100.0, 200.0, 100.0], dtype=pl.Float64
                ),  # row 2: open > high
                "high": pl.Series([110.0, 110.0, 110.0, 110.0], dtype=pl.Float64),
                "low": pl.Series([90.0, 90.0, 90.0, 90.0], dtype=pl.Float64),
                "close": pl.Series([105.0, 105.0, 105.0, 105.0], dtype=pl.Float64),
                "volume": pl.Series([1000.0, 1000.0, 1000.0, 1000.0], dtype=pl.Float64),
            }
        )
        result = validate_ohlcv(df)

        # Violations must be sorted: DUPLICATE_TIMESTAMP before OHLC_INCONSISTENCY
        checks_in_order = [v.check for v in result.violations]
        duplicate_idx = next(
            i for i, c in enumerate(checks_in_order) if c == ViolationType.DUPLICATE_TIMESTAMP
        )
        ohlc_idx = next(
            i for i, c in enumerate(checks_in_order) if c == ViolationType.OHLC_INCONSISTENCY
        )
        assert duplicate_idx < ohlc_idx

    def test_violations_from_same_check_ordered_by_row(self) -> None:
        # Two OHLC violations at rows 0 and 2 — must appear in row order
        df = pl.DataFrame(
            {
                "timestamp": pl.Series(
                    [_BASE_TS, _BASE_TS + _DAY, _BASE_TS + 2 * _DAY], dtype=pl.Float64
                ),
                "open": pl.Series(
                    [200.0, 100.0, 200.0], dtype=pl.Float64
                ),  # rows 0, 2: open > high
                "high": pl.Series([110.0, 110.0, 110.0], dtype=pl.Float64),
                "low": pl.Series([90.0, 90.0, 90.0], dtype=pl.Float64),
                "close": pl.Series([105.0, 105.0, 105.0], dtype=pl.Float64),
                "volume": pl.Series([1000.0, 1000.0, 1000.0], dtype=pl.Float64),
            }
        )
        result = validate_ohlcv(df)
        ohlc_violations = [
            v for v in result.violations if v.check == ViolationType.OHLC_INCONSISTENCY
        ]
        assert len(ohlc_violations) == 2
        assert ohlc_violations[0].affected_rows[0] < ohlc_violations[1].affected_rows[0]


# ===========================================================================
# ValidationResult Property Tests
# ===========================================================================


class TestValidationResultProperties:
    def test_errors_returns_only_error_violations(self) -> None:
        # Duplicate → ERROR; gap → WARNING
        ts = _BASE_TS
        friday = ts + 10 * _DAY
        monday = friday + 3 * _DAY
        df = _make_df(timestamps=[ts, ts, ts + _DAY, friday, monday])
        result = validate_ohlcv(df, interval="1D")
        for v in result.errors:
            assert v.severity == "ERROR"

    def test_warnings_returns_only_warning_violations(self) -> None:
        friday = _BASE_TS
        monday = friday + 3 * _DAY
        df = _make_df(timestamps=[friday, monday])
        result = validate_ohlcv(df, interval="1D")
        for v in result.warnings:
            assert v.severity == "WARNING"

    def test_errors_empty_when_no_error_violations(self) -> None:
        friday = _BASE_TS
        monday = friday + 3 * _DAY
        df = _make_df(timestamps=[friday, monday])
        result = validate_ohlcv(df, interval="1D")
        assert result.errors == []

    def test_warnings_empty_when_no_warning_violations(self) -> None:
        ts = _BASE_TS
        df = _make_df(timestamps=[ts, ts])  # duplicate — ERROR only
        result = validate_ohlcv(df)
        assert result.warnings == []

    def test_model_dump_excludes_errors_and_warnings(self) -> None:
        df = _make_df()
        result = validate_ohlcv(df)
        dumped = result.model_dump()
        assert "errors" not in dumped
        assert "warnings" not in dumped

    def test_model_dump_includes_expected_keys(self) -> None:
        df = _make_df()
        result = validate_ohlcv(df)
        dumped = result.model_dump()
        assert set(dumped.keys()) == {"is_valid", "violations", "bars_checked", "checks_run"}

    def test_errors_count_matches_is_valid_false(self) -> None:
        ts = _BASE_TS
        df = _make_df(timestamps=[ts, ts])
        result = validate_ohlcv(df)
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_is_valid_true_when_only_warnings(self) -> None:
        friday = _BASE_TS
        monday = friday + 3 * _DAY
        df = _make_df(timestamps=[friday, monday])
        result = validate_ohlcv(df, interval="1D")
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert len(result.errors) == 0
