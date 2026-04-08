"""
Individual OHLCV validation check functions.

Each function is pure: no side effects, no logging, no mutation of input.
All functions return list[Violation]. An empty list means no violations found.

These functions assume the DataFrame schema has already been validated by
_require_ohlcv_schema() in validator.py. They do not re-validate column
existence or dtypes.

check_gaps() is the only function that raises — it raises ValueError when
called with an empty or unrecognised interval. All other functions never raise.
"""

import math
from typing import Any

import polars as pl

from tvkit.validation.models import Violation, ViolationContext, ViolationType


def _safe_float(value: Any) -> float | None:
    """Return value as float, or None if it is NaN or null."""
    if value is None:
        return None
    f = float(value)
    return None if math.isnan(f) else f


def _timestamp_diff_seconds(
    a: Any,
    b: Any,
    dtype: pl.PolarsDataType,
) -> int:
    """
    Return the difference (b - a) in whole seconds.

    Handles four timestamp representations, all following tvkit's epoch-seconds convention:
    - Float64: epoch seconds (default tvkit export — OHLCVBar.timestamp is a float in UTC seconds)
    - Int64:   epoch seconds (tvkit integer timestamps; multiply by 1 to get seconds)
    - Date:    Python datetime.date objects from .to_list() (days × 86400)
    - Datetime: Python datetime.datetime objects from .to_list() (timedelta.total_seconds)

    Note: Int64 timestamps in tvkit DataFrames are UTC epoch seconds, not milliseconds.
    This is consistent with OHLCVBar.timestamp (float seconds), tvkit.time documentation,
    and the PolarsFormatter which converts seconds→ms only on cast to Datetime.
    """
    import datetime

    if dtype in (pl.Float64, pl.Float32, pl.Int64):
        # epoch seconds — direct arithmetic
        return round(float(b) - float(a))

    # pl.Date and pl.Datetime both produce Python temporal objects via .to_list()
    delta: datetime.timedelta = b - a  # type: ignore[operator]
    return int(delta.total_seconds())


def check_duplicate_timestamps(df: pl.DataFrame) -> list[Violation]:
    """
    Identify bars with duplicate timestamps.

    Args:
        df: Polars DataFrame with a validated OHLCV schema.

    Returns:
        One Violation per group of duplicate timestamps, sorted by the first
        affected row index. Empty list if no duplicates are found.
    """
    if len(df) == 0:
        return []

    groups = (
        df.with_row_index("_row_idx")
        .group_by("timestamp")
        .agg(
            pl.col("_row_idx").alias("_indices"),
            pl.len().alias("_count"),
        )
        .filter(pl.col("_count") > 1)
    )

    violations: list[Violation] = []
    for row in groups.iter_rows(named=True):
        affected: list[int] = sorted(row["_indices"])
        ts_str = str(row["timestamp"])
        count: int = int(row["_count"])
        violations.append(
            Violation(
                check=ViolationType.DUPLICATE_TIMESTAMP,
                severity="ERROR",
                message=(
                    f"Duplicate timestamp {ts_str!r} appears {count} time(s) at rows {affected}"
                ),
                affected_rows=affected,
                context={"duplicate_timestamp": ts_str, "count": count},
            )
        )

    violations.sort(key=lambda v: v.affected_rows[0] if v.affected_rows else 0)
    return violations


def check_monotonic_timestamps(df: pl.DataFrame) -> list[Violation]:
    """
    Detect out-of-order timestamps.

    Checks that each bar's timestamp is strictly greater than the previous bar's
    timestamp. Should be run after check_duplicate_timestamps so that equal-value
    pairs are reported as duplicates before being reported here.

    Args:
        df: Polars DataFrame with a validated OHLCV schema.

    Returns:
        One Violation per out-of-order consecutive pair. Empty list if all
        timestamps are strictly increasing.
    """
    if len(df) <= 1:
        return []

    ts_list = df["timestamp"].to_list()
    violations: list[Violation] = []

    for i in range(len(ts_list) - 1):
        curr_val = ts_list[i]
        next_val = ts_list[i + 1]
        if next_val <= curr_val:
            violations.append(
                Violation(
                    check=ViolationType.NON_MONOTONIC_TIMESTAMP,
                    severity="ERROR",
                    message=(
                        f"Timestamp at row {i + 1} ({str(next_val)!r}) is not strictly "
                        f"greater than row {i} ({str(curr_val)!r})"
                    ),
                    affected_rows=[i, i + 1],
                    context={
                        "prev_timestamp": str(curr_val),
                        "curr_timestamp": str(next_val),
                    },
                )
            )

    return violations


def check_ohlc_consistency(df: pl.DataFrame) -> list[Violation]:
    """
    Enforce OHLC price constraints for every bar.

    For each bar checks:
    - low <= open <= high
    - low <= close <= high
    - No NaN or null values in open, high, low, close

    Args:
        df: Polars DataFrame with a validated OHLCV schema.

    Returns:
        One Violation per bar that fails any constraint. Empty list if all bars
        pass. NaN and null values are treated as violations.
    """
    if len(df) == 0:
        return []

    opens = df["open"].to_list()
    highs = df["high"].to_list()
    lows = df["low"].to_list()
    closes = df["close"].to_list()

    violations: list[Violation] = []

    for i, (o, h, low_val, c) in enumerate(zip(opens, highs, lows, closes, strict=False)):
        violated: str | None = None

        has_null_or_nan = any(
            v is None or (isinstance(v, float) and math.isnan(v)) for v in (o, h, low_val, c)
        )

        if has_null_or_nan:
            violated = "NaN or null value in OHLC column"
        elif not (low_val <= o <= h):  # type: ignore[operator]
            violated = f"low ({low_val}) \u2264 open ({o}) \u2264 high ({h}) violated"
        elif not (low_val <= c <= h):  # type: ignore[operator]
            violated = f"low ({low_val}) \u2264 close ({c}) \u2264 high ({h}) violated"

        if violated is not None:
            ctx: ViolationContext = {
                "open": _safe_float(o),
                "high": _safe_float(h),
                "low": _safe_float(low_val),
                "close": _safe_float(c),
                "violated_constraint": violated,
            }
            violations.append(
                Violation(
                    check=ViolationType.OHLC_INCONSISTENCY,
                    severity="ERROR",
                    message=f"OHLC constraint violated at row {i}: {violated}",
                    affected_rows=[i],
                    context=ctx,
                )
            )

    return violations


def check_volume_non_negative(df: pl.DataFrame) -> list[Violation]:
    """
    Detect bars with negative or NaN volume.

    Args:
        df: Polars DataFrame with a validated OHLCV schema.

    Returns:
        One Violation per bar with volume < 0 or NaN/null volume. Empty list
        if all volume values are valid non-negative numbers.
    """
    if len(df) == 0:
        return []

    volumes = df["volume"].to_list()
    violations: list[Violation] = []

    for i, v in enumerate(volumes):
        is_null_or_nan = v is None or (isinstance(v, float) and math.isnan(v))

        if is_null_or_nan:
            violations.append(
                Violation(
                    check=ViolationType.NEGATIVE_VOLUME,
                    severity="ERROR",
                    message=f"Null or NaN volume at row {i}",
                    affected_rows=[i],
                    context={"volume": None},
                )
            )
        elif v < 0:
            violations.append(
                Violation(
                    check=ViolationType.NEGATIVE_VOLUME,
                    severity="ERROR",
                    message=f"Negative volume {v} at row {i}",
                    affected_rows=[i],
                    context={"volume": float(v)},
                )
            )

    return violations


def check_gaps(df: pl.DataFrame, interval: str) -> list[Violation]:
    """
    Find missing bars given the expected interval cadence.

    Uses validate_interval() and interval_to_seconds() from tvkit.api.chart.utils
    to validate the interval string and compute the expected gap duration.

    Phase 1 limitation: cadence-only, not calendar-aware. For daily equity data,
    weekends and public holidays are reported as WARNING violations. The caller is
    responsible for filtering expected calendar gaps.

    Args:
        df: Polars DataFrame with a validated OHLCV schema.
        interval: Expected interval string (e.g., "1D", "1H", "15", "5S").
                  Must be a non-empty, recognised TradingView interval with a
                  fixed cadence (seconds, minutes, hours, or days).

    Returns:
        One WARNING Violation per gap found, with affected_rows pointing to the
        bar immediately after the gap. Empty list if no gaps are found.

    Raises:
        ValueError: If interval is empty, unrecognised, or a variable-cadence
                    monthly/weekly interval that cannot be converted to seconds.
        TypeError:  If interval is not a string (propagated from validate_interval).
    """
    from tvkit.api.chart.utils import interval_to_seconds, validate_interval

    validate_interval(interval)  # raises ValueError / TypeError for invalid format

    try:
        expected_seconds = interval_to_seconds(interval)
    except ValueError as exc:
        raise ValueError(
            f"Gap detection requires a fixed-cadence interval (seconds, minutes, "
            f"hours, or days). Monthly and weekly intervals have variable-length "
            f"durations and cannot be used for cadence-based gap detection. "
            f"Got {interval!r}."
        ) from exc

    if len(df) <= 1:
        return []

    ts_list = df["timestamp"].to_list()
    dtype = df["timestamp"].dtype
    violations: list[Violation] = []

    for i in range(len(ts_list) - 1):
        actual_seconds = _timestamp_diff_seconds(ts_list[i], ts_list[i + 1], dtype)
        if actual_seconds != expected_seconds:
            violations.append(
                Violation(
                    check=ViolationType.GAP_DETECTED,
                    severity="WARNING",
                    message=(
                        f"Gap detected between rows {i} and {i + 1}: "
                        f"expected {expected_seconds}s, got {actual_seconds}s"
                    ),
                    affected_rows=[i + 1],
                    context={
                        "expected_interval": interval,
                        "actual_gap": f"{actual_seconds}s",
                        "prev_timestamp": str(ts_list[i]),
                        "curr_timestamp": str(ts_list[i + 1]),
                    },
                )
            )

    return violations
