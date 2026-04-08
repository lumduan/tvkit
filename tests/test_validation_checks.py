"""
Unit tests for tvkit.validation individual check functions.

Tests for:
- check_duplicate_timestamps
- check_monotonic_timestamps
- check_ohlc_consistency
- check_volume_non_negative
- check_gaps

Gap detection note: check_gaps() raises ValueError for weekly ("W", "1W") and
monthly ("M", "1M") intervals because interval_to_seconds() does not support
variable-cadence intervals. This is intentional — cadence-based gap detection
has no meaningful interpretation for intervals with variable durations.
"""

from datetime import UTC, date, datetime, timedelta

import polars as pl
import pytest

from tvkit.validation.checks import (
    check_duplicate_timestamps,
    check_gaps,
    check_monotonic_timestamps,
    check_ohlc_consistency,
    check_volume_non_negative,
)
from tvkit.validation.models import ViolationType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_TS = 1_700_000_000.0  # 2023-11-14 22:13:20 UTC (Float64 epoch seconds)
_DAY = 86_400


def _make_df(
    timestamps: list[float],
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    closes: list[float] | None = None,
    volumes: list[float] | None = None,
) -> pl.DataFrame:
    """Build a minimal valid OHLCV DataFrame with Float64 epoch-second timestamps."""
    n = len(timestamps)
    return pl.DataFrame(
        {
            "timestamp": pl.Series(timestamps, dtype=pl.Float64),
            "open": pl.Series(opens if opens is not None else [100.0] * n, dtype=pl.Float64),
            "high": pl.Series(highs if highs is not None else [110.0] * n, dtype=pl.Float64),
            "low": pl.Series(lows if lows is not None else [90.0] * n, dtype=pl.Float64),
            "close": pl.Series(closes if closes is not None else [105.0] * n, dtype=pl.Float64),
            "volume": pl.Series(volumes if volumes is not None else [1000.0] * n, dtype=pl.Float64),
        }
    )


# ===========================================================================
# check_duplicate_timestamps
# ===========================================================================


class TestCheckDuplicateTimestamps:
    def test_clean_dataframe_returns_empty(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS + _DAY, _BASE_TS + 2 * _DAY])
        assert check_duplicate_timestamps(df) == []

    def test_empty_dataframe_returns_empty(self) -> None:
        df = _make_df([])
        assert check_duplicate_timestamps(df) == []

    def test_single_row_returns_empty(self) -> None:
        df = _make_df([_BASE_TS])
        assert check_duplicate_timestamps(df) == []

    def test_single_duplicate_pair(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS, _BASE_TS + _DAY])
        violations = check_duplicate_timestamps(df)
        assert len(violations) == 1
        v = violations[0]
        assert v.check == ViolationType.DUPLICATE_TIMESTAMP
        assert v.severity == "ERROR"
        assert sorted(v.affected_rows) == [0, 1]
        assert v.context["count"] == 2

    def test_two_duplicate_groups(self) -> None:
        ts_a = _BASE_TS
        ts_b = _BASE_TS + _DAY
        ts_c = _BASE_TS + 2 * _DAY
        df = _make_df([ts_a, ts_a, ts_b, ts_b, ts_c])
        violations = check_duplicate_timestamps(df)
        assert len(violations) == 2
        # sorted by first affected row
        assert violations[0].affected_rows[0] < violations[1].affected_rows[0]

    def test_triple_duplicate(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS, _BASE_TS, _BASE_TS + _DAY])
        violations = check_duplicate_timestamps(df)
        assert len(violations) == 1
        assert violations[0].context["count"] == 3
        assert len(violations[0].affected_rows) == 3

    def test_violation_context_has_required_keys(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS])
        v = check_duplicate_timestamps(df)[0]
        assert "duplicate_timestamp" in v.context
        assert "count" in v.context

    def test_violations_sorted_by_first_affected_row(self) -> None:
        # group at rows 2,3 should come after group at rows 0,1
        df = _make_df([_BASE_TS, _BASE_TS, _BASE_TS + _DAY, _BASE_TS + _DAY])
        violations = check_duplicate_timestamps(df)
        assert len(violations) == 2
        assert violations[0].affected_rows[0] == 0
        assert violations[1].affected_rows[0] == 2


# ===========================================================================
# check_monotonic_timestamps
# ===========================================================================


class TestCheckMonotonicTimestamps:
    def test_strictly_increasing_returns_empty(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS + _DAY, _BASE_TS + 2 * _DAY])
        assert check_monotonic_timestamps(df) == []

    def test_empty_dataframe_returns_empty(self) -> None:
        assert check_monotonic_timestamps(_make_df([])) == []

    def test_single_row_returns_empty(self) -> None:
        assert check_monotonic_timestamps(_make_df([_BASE_TS])) == []

    def test_two_equal_timestamps(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS])
        violations = check_monotonic_timestamps(df)
        assert len(violations) == 1
        v = violations[0]
        assert v.check == ViolationType.NON_MONOTONIC_TIMESTAMP
        assert v.severity == "ERROR"
        assert v.affected_rows == [0, 1]

    def test_out_of_order_pair(self) -> None:
        df = _make_df([_BASE_TS + _DAY, _BASE_TS])
        violations = check_monotonic_timestamps(df)
        assert len(violations) == 1
        assert violations[0].affected_rows == [0, 1]

    def test_multiple_out_of_order_pairs(self) -> None:
        # timestamps go: 3, 2, 1 — two violations
        df = _make_df([_BASE_TS + 2 * _DAY, _BASE_TS + _DAY, _BASE_TS])
        violations = check_monotonic_timestamps(df)
        assert len(violations) == 2

    def test_violation_context_keys(self) -> None:
        df = _make_df([_BASE_TS + _DAY, _BASE_TS])
        v = check_monotonic_timestamps(df)[0]
        assert "prev_timestamp" in v.context
        assert "curr_timestamp" in v.context

    def test_middle_out_of_order(self) -> None:
        # valid, invalid, valid
        df = _make_df([_BASE_TS, _BASE_TS + _DAY, _BASE_TS])
        violations = check_monotonic_timestamps(df)
        assert len(violations) == 1
        assert violations[0].affected_rows == [1, 2]


# ===========================================================================
# check_ohlc_consistency
# ===========================================================================


class TestCheckOhlcConsistency:
    def test_valid_bars_returns_empty(self) -> None:
        df = _make_df(
            timestamps=[_BASE_TS, _BASE_TS + _DAY],
            opens=[100.0, 200.0],
            highs=[110.0, 210.0],
            lows=[90.0, 190.0],
            closes=[105.0, 205.0],
        )
        assert check_ohlc_consistency(df) == []

    def test_empty_dataframe_returns_empty(self) -> None:
        assert check_ohlc_consistency(_make_df([])) == []

    def test_open_above_high(self) -> None:
        df = _make_df(
            timestamps=[_BASE_TS],
            opens=[120.0],
            highs=[110.0],
            lows=[90.0],
            closes=[105.0],
        )
        violations = check_ohlc_consistency(df)
        assert len(violations) == 1
        v = violations[0]
        assert v.check == ViolationType.OHLC_INCONSISTENCY
        assert v.severity == "ERROR"
        assert v.affected_rows == [0]
        assert "violated_constraint" in v.context

    def test_open_below_low(self) -> None:
        df = _make_df(
            timestamps=[_BASE_TS],
            opens=[80.0],
            highs=[110.0],
            lows=[90.0],
            closes=[105.0],
        )
        violations = check_ohlc_consistency(df)
        assert len(violations) == 1

    def test_close_above_high(self) -> None:
        df = _make_df(
            timestamps=[_BASE_TS],
            opens=[100.0],
            highs=[110.0],
            lows=[90.0],
            closes=[120.0],
        )
        violations = check_ohlc_consistency(df)
        assert len(violations) == 1

    def test_close_below_low(self) -> None:
        df = _make_df(
            timestamps=[_BASE_TS],
            opens=[100.0],
            highs=[110.0],
            lows=[90.0],
            closes=[80.0],
        )
        violations = check_ohlc_consistency(df)
        assert len(violations) == 1

    def test_nan_in_open(self) -> None:
        df = _make_df(
            timestamps=[_BASE_TS],
            opens=[float("nan")],
            highs=[110.0],
            lows=[90.0],
            closes=[105.0],
        )
        violations = check_ohlc_consistency(df)
        assert len(violations) == 1
        constraint = violations[0].context.get("violated_constraint")
        assert isinstance(constraint, str)
        assert "NaN or null" in constraint

    def test_multiple_bad_bars(self) -> None:
        df = _make_df(
            timestamps=[_BASE_TS, _BASE_TS + _DAY, _BASE_TS + 2 * _DAY],
            opens=[120.0, 100.0, 120.0],
            highs=[110.0, 110.0, 110.0],
            lows=[90.0, 90.0, 90.0],
            closes=[105.0, 105.0, 105.0],
        )
        violations = check_ohlc_consistency(df)
        assert len(violations) == 2
        assert violations[0].affected_rows == [0]
        assert violations[1].affected_rows == [2]

    def test_violation_context_has_ohlc_keys(self) -> None:
        df = _make_df(
            timestamps=[_BASE_TS],
            opens=[120.0],
            highs=[110.0],
            lows=[90.0],
            closes=[105.0],
        )
        ctx = check_ohlc_consistency(df)[0].context
        assert "open" in ctx
        assert "high" in ctx
        assert "low" in ctx
        assert "close" in ctx
        assert "violated_constraint" in ctx

    def test_doji_candle_all_equal_is_valid(self) -> None:
        # open == close == high == low — valid
        df = _make_df(
            timestamps=[_BASE_TS],
            opens=[100.0],
            highs=[100.0],
            lows=[100.0],
            closes=[100.0],
        )
        assert check_ohlc_consistency(df) == []


# ===========================================================================
# check_volume_non_negative
# ===========================================================================


class TestCheckVolumeNonNegative:
    def test_valid_volumes_returns_empty(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS + _DAY], volumes=[1000.0, 2000.0])
        assert check_volume_non_negative(df) == []

    def test_zero_volume_is_valid(self) -> None:
        df = _make_df([_BASE_TS], volumes=[0.0])
        assert check_volume_non_negative(df) == []

    def test_empty_dataframe_returns_empty(self) -> None:
        assert check_volume_non_negative(_make_df([])) == []

    def test_negative_volume(self) -> None:
        df = _make_df([_BASE_TS], volumes=[-1.0])
        violations = check_volume_non_negative(df)
        assert len(violations) == 1
        v = violations[0]
        assert v.check == ViolationType.NEGATIVE_VOLUME
        assert v.severity == "ERROR"
        assert v.affected_rows == [0]
        assert v.context["volume"] == -1.0

    def test_nan_volume_context_is_none(self) -> None:
        df = _make_df([_BASE_TS], volumes=[float("nan")])
        violations = check_volume_non_negative(df)
        assert len(violations) == 1
        assert violations[0].context["volume"] is None

    def test_multiple_negative_volumes(self) -> None:
        df = _make_df(
            [_BASE_TS, _BASE_TS + _DAY, _BASE_TS + 2 * _DAY],
            volumes=[-5.0, 1000.0, -10.0],
        )
        violations = check_volume_non_negative(df)
        assert len(violations) == 2
        assert violations[0].affected_rows == [0]
        assert violations[1].affected_rows == [2]

    def test_mixed_nan_and_negative(self) -> None:
        df = _make_df(
            [_BASE_TS, _BASE_TS + _DAY, _BASE_TS + 2 * _DAY],
            volumes=[float("nan"), 1000.0, -1.0],
        )
        violations = check_volume_non_negative(df)
        assert len(violations) == 2


# ===========================================================================
# check_gaps
# ===========================================================================


class TestCheckGaps:
    # -----------------------------------------------------------------------
    # Happy path — no gaps
    # -----------------------------------------------------------------------

    def test_exact_cadence_1d_returns_empty(self) -> None:
        ts = [_BASE_TS + i * _DAY for i in range(5)]
        df = _make_df(ts)
        assert check_gaps(df, "1D") == []

    def test_exact_cadence_1h_returns_empty(self) -> None:
        hour = 3600
        ts = [_BASE_TS + i * hour for i in range(10)]
        df = _make_df(ts)
        assert check_gaps(df, "1H") == []

    def test_exact_cadence_1min_returns_empty(self) -> None:
        ts = [_BASE_TS + i * 60 for i in range(10)]
        df = _make_df(ts)
        assert check_gaps(df, "1") == []

    def test_exact_cadence_15s_returns_empty(self) -> None:
        ts = [_BASE_TS + i * 15 for i in range(10)]
        df = _make_df(ts)
        assert check_gaps(df, "15S") == []

    # -----------------------------------------------------------------------
    # Edge cases — 0 or 1 rows
    # -----------------------------------------------------------------------

    def test_empty_dataframe_returns_empty(self) -> None:
        assert check_gaps(_make_df([]), "1D") == []

    def test_single_row_returns_empty(self) -> None:
        assert check_gaps(_make_df([_BASE_TS]), "1D") == []

    def test_two_rows_exact_cadence_returns_empty(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS + _DAY])
        assert check_gaps(df, "1D") == []

    # -----------------------------------------------------------------------
    # Single gap
    # -----------------------------------------------------------------------

    def test_single_gap_detected(self) -> None:
        ts = [_BASE_TS, _BASE_TS + 2 * _DAY]  # missing one day
        df = _make_df(ts)
        violations = check_gaps(df, "1D")
        assert len(violations) == 1
        v = violations[0]
        assert v.check == ViolationType.GAP_DETECTED
        assert v.severity == "WARNING"
        assert v.affected_rows == [1]

    def test_single_gap_in_middle(self) -> None:
        ts = [
            _BASE_TS,
            _BASE_TS + _DAY,
            _BASE_TS + 3 * _DAY,  # gap here
            _BASE_TS + 4 * _DAY,
        ]
        df = _make_df(ts)
        violations = check_gaps(df, "1D")
        assert len(violations) == 1
        assert violations[0].affected_rows == [2]

    # -----------------------------------------------------------------------
    # Multiple gaps
    # -----------------------------------------------------------------------

    def test_multiple_gaps(self) -> None:
        ts = [
            _BASE_TS,
            _BASE_TS + 2 * _DAY,  # gap → row 1
            _BASE_TS + 3 * _DAY,
            _BASE_TS + 5 * _DAY,  # gap → row 3
        ]
        df = _make_df(ts)
        violations = check_gaps(df, "1D")
        assert len(violations) == 2
        assert violations[0].affected_rows == [1]
        assert violations[1].affected_rows == [3]

    # -----------------------------------------------------------------------
    # Sub-interval spacing: actual < expected — must NOT be flagged
    # (gap detection only flags missing bars, not closer-than-expected spacing)
    # -----------------------------------------------------------------------

    def test_sub_interval_spacing_no_violation(self) -> None:
        ts = [_BASE_TS, _BASE_TS + 3600]  # 1 hour apart, interval is 1D
        df = _make_df(ts)
        # actual (3600s) < expected (86400s) — not a gap
        assert check_gaps(df, "1D") == []

    def test_sub_interval_5min_interval_3min_apart(self) -> None:
        ts = [_BASE_TS, _BASE_TS + 180]  # 3 min < 5 min expected
        df = _make_df(ts)
        assert check_gaps(df, "5") == []

    # -----------------------------------------------------------------------
    # Violation context
    # -----------------------------------------------------------------------

    def test_violation_context_keys(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS + 2 * _DAY])
        v = check_gaps(df, "1D")[0]
        assert v.context["expected_interval"] == "1D"
        assert v.context["actual_gap"] == f"{2 * _DAY}s"
        assert "prev_timestamp" in v.context
        assert "curr_timestamp" in v.context

    def test_violation_message_includes_seconds(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS + 2 * _DAY])
        v = check_gaps(df, "1D")[0]
        assert f"expected {_DAY}s" in v.message
        assert f"got {2 * _DAY}s" in v.message

    # -----------------------------------------------------------------------
    # Calendar gap (weekend) — still flagged as WARNING (cadence-only)
    # -----------------------------------------------------------------------

    def test_weekend_gap_flagged_for_daily_interval(self) -> None:
        """Friday → Monday produces a 3-day gap; cadence-only, no calendar awareness."""
        friday_ts = 1700179200.0  # 2023-11-17 00:00:00 UTC (Friday)
        monday_ts = friday_ts + 3 * _DAY
        df = _make_df([friday_ts, monday_ts])
        violations = check_gaps(df, "1D")
        assert len(violations) == 1
        assert violations[0].severity == "WARNING"
        assert violations[0].context["actual_gap"] == f"{3 * _DAY}s"

    def test_two_day_gap_flagged(self) -> None:
        ts = [_BASE_TS, _BASE_TS + 2 * _DAY]
        df = _make_df(ts)
        violations = check_gaps(df, "1D")
        assert len(violations) == 1

    # -----------------------------------------------------------------------
    # Multiple interval types
    # -----------------------------------------------------------------------

    def test_1h_interval_gap(self) -> None:
        hour = 3600
        ts = [_BASE_TS, _BASE_TS + 2 * hour]  # 2 hours, expected 1
        df = _make_df(ts)
        violations = check_gaps(df, "1H")
        assert len(violations) == 1
        assert violations[0].context["actual_gap"] == f"{2 * hour}s"

    def test_15_minute_interval_gap(self) -> None:
        ts = [_BASE_TS, _BASE_TS + 1800]  # 30 min, expected 15 min
        df = _make_df(ts)
        violations = check_gaps(df, "15")
        assert len(violations) == 1

    def test_1s_interval_gap(self) -> None:
        ts = [_BASE_TS, _BASE_TS + 5]  # 5 sec, expected 1 sec
        df = _make_df(ts)
        violations = check_gaps(df, "1S")
        assert len(violations) == 1

    def test_3d_interval_exact_cadence(self) -> None:
        ts = [_BASE_TS + i * 3 * _DAY for i in range(4)]
        df = _make_df(ts)
        assert check_gaps(df, "3D") == []

    # -----------------------------------------------------------------------
    # Timestamp dtype support
    # -----------------------------------------------------------------------

    def test_int64_epoch_seconds_exact_cadence(self) -> None:
        ts_int = [int(_BASE_TS) + i * _DAY for i in range(3)]
        df = pl.DataFrame(
            {
                "timestamp": pl.Series(ts_int, dtype=pl.Int64),
                "open": [100.0, 100.0, 100.0],
                "high": [110.0, 110.0, 110.0],
                "low": [90.0, 90.0, 90.0],
                "close": [105.0, 105.0, 105.0],
                "volume": [1000.0, 1000.0, 1000.0],
            }
        )
        assert check_gaps(df, "1D") == []

    def test_int64_epoch_seconds_gap_detected(self) -> None:
        ts_int = [int(_BASE_TS), int(_BASE_TS) + 2 * _DAY]
        df = pl.DataFrame(
            {
                "timestamp": pl.Series(ts_int, dtype=pl.Int64),
                "open": [100.0, 100.0],
                "high": [110.0, 110.0],
                "low": [90.0, 90.0],
                "close": [105.0, 105.0],
                "volume": [1000.0, 1000.0],
            }
        )
        violations = check_gaps(df, "1D")
        assert len(violations) == 1

    def test_date_dtype_exact_cadence(self) -> None:
        dates = [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]
        df = pl.DataFrame(
            {
                "timestamp": pl.Series(dates, dtype=pl.Date),
                "open": [100.0, 100.0, 100.0],
                "high": [110.0, 110.0, 110.0],
                "low": [90.0, 90.0, 90.0],
                "close": [105.0, 105.0, 105.0],
                "volume": [1000.0, 1000.0, 1000.0],
            }
        )
        assert check_gaps(df, "1D") == []

    def test_date_dtype_gap_detected(self) -> None:
        dates = [date(2024, 1, 1), date(2024, 1, 3)]  # missing Jan 2
        df = pl.DataFrame(
            {
                "timestamp": pl.Series(dates, dtype=pl.Date),
                "open": [100.0, 100.0],
                "high": [110.0, 110.0],
                "low": [90.0, 90.0],
                "close": [105.0, 105.0],
                "volume": [1000.0, 1000.0],
            }
        )
        violations = check_gaps(df, "1D")
        assert len(violations) == 1

    def test_datetime_dtype_exact_cadence(self) -> None:
        base = datetime(2024, 1, 1, tzinfo=UTC)
        dts = [base + timedelta(days=i) for i in range(4)]
        df = pl.DataFrame(
            {
                "timestamp": pl.Series(dts),
                "open": [100.0] * 4,
                "high": [110.0] * 4,
                "low": [90.0] * 4,
                "close": [105.0] * 4,
                "volume": [1000.0] * 4,
            }
        )
        assert check_gaps(df, "1D") == []

    def test_datetime_dtype_gap_detected(self) -> None:
        base = datetime(2024, 1, 1, tzinfo=UTC)
        dts = [base, base + timedelta(days=2)]  # 1-day gap
        df = pl.DataFrame(
            {
                "timestamp": pl.Series(dts),
                "open": [100.0, 100.0],
                "high": [110.0, 110.0],
                "low": [90.0, 90.0],
                "close": [105.0, 105.0],
                "volume": [1000.0, 1000.0],
            }
        )
        violations = check_gaps(df, "1D")
        assert len(violations) == 1

    # -----------------------------------------------------------------------
    # Error conditions
    #
    # Weekly and monthly intervals raise ValueError because interval_to_seconds()
    # does not support variable-cadence intervals. This is by design — a
    # cadence-based gap check has no meaningful interpretation for intervals
    # whose duration varies (e.g., February vs March for monthly).
    # -----------------------------------------------------------------------

    def test_invalid_interval_raises_value_error(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS + _DAY])
        with pytest.raises(ValueError):
            check_gaps(df, "invalid_interval")

    def test_empty_interval_raises_value_error(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS + _DAY])
        with pytest.raises(ValueError):
            check_gaps(df, "")

    def test_weekly_interval_raises_value_error(self) -> None:
        """Weekly intervals have variable durations and cannot be used for cadence gaps."""
        df = _make_df([_BASE_TS, _BASE_TS + 7 * _DAY])
        with pytest.raises(ValueError):
            check_gaps(df, "1W")

    def test_bare_weekly_interval_raises_value_error(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS + 7 * _DAY])
        with pytest.raises(ValueError):
            check_gaps(df, "W")

    def test_monthly_interval_raises_value_error(self) -> None:
        """Monthly intervals have variable durations and cannot be used for cadence gaps."""
        df = _make_df([_BASE_TS, _BASE_TS + 30 * _DAY])
        with pytest.raises(ValueError):
            check_gaps(df, "1M")

    def test_bare_monthly_interval_raises_value_error(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS + 30 * _DAY])
        with pytest.raises(ValueError):
            check_gaps(df, "M")

    def test_non_string_interval_raises_type_error(self) -> None:
        df = _make_df([_BASE_TS, _BASE_TS + _DAY])
        with pytest.raises(TypeError):
            check_gaps(df, 86400)  # type: ignore[arg-type]

    # -----------------------------------------------------------------------
    # Determinism — violations in row order
    # -----------------------------------------------------------------------

    def test_violations_in_row_order(self) -> None:
        ts = [
            _BASE_TS,
            _BASE_TS + 3 * _DAY,  # gap at row 1
            _BASE_TS + 4 * _DAY,
            _BASE_TS + 6 * _DAY,  # gap at row 3
            _BASE_TS + 7 * _DAY,
        ]
        df = _make_df(ts)
        violations = check_gaps(df, "1D")
        assert len(violations) == 2
        assert violations[0].affected_rows == [1]
        assert violations[1].affected_rows == [3]

    # -----------------------------------------------------------------------
    # Non-destructive — input DataFrame is not mutated
    # -----------------------------------------------------------------------

    def test_input_dataframe_not_mutated(self) -> None:
        ts = [_BASE_TS, _BASE_TS + 2 * _DAY]
        df = _make_df(ts)
        original_shape = df.shape
        original_first_ts = df["timestamp"][0]
        check_gaps(df, "1D")
        assert df.shape == original_shape
        assert df["timestamp"][0] == original_first_ts
