"""
Composite OHLCV validator.

Provides validate_ohlcv() — the single public entry point that orchestrates
all check functions in deterministic order — and the private schema helper
_require_ohlcv_schema().
"""

import polars as pl

from tvkit.validation.checks import (
    check_duplicate_timestamps,
    check_gaps,
    check_monotonic_timestamps,
    check_ohlc_consistency,
    check_volume_non_negative,
)
from tvkit.validation.models import ValidationResult, Violation, ViolationType

# Required columns and their accepted Polars dtypes.
#
# Notes:
# - pl.Float64 is included for timestamp because tvkit's PolarsFormatter produces
#   Float64 timestamp columns (UTC epoch seconds from OHLCVBar.timestamp: float).
# - pl.Int64 is included for timestamp because callers may cast Float64 → Int64;
#   the convention is epoch seconds in both cases.
# - pl.Datetime entries are handled via isinstance() in _require_ohlcv_schema because
#   Datetime is parameterised (time_unit, time_zone) and equality against the bare
#   class always returns False for instantiated variants like Datetime('us', None).
_REQUIRED_COLUMNS: dict[str, tuple[type[pl.DataType], ...]] = {
    "timestamp": (pl.Float64, pl.Int64, pl.Date),  # Datetime handled via isinstance
    "open": (pl.Float64, pl.Float32),
    "high": (pl.Float64, pl.Float32),
    "low": (pl.Float64, pl.Float32),
    "close": (pl.Float64, pl.Float32),
    "volume": (pl.Float64, pl.Float32, pl.Int64),
}

# Deterministic execution order — part of the public contract.
_CHECK_ORDER: list[ViolationType] = [
    ViolationType.DUPLICATE_TIMESTAMP,
    ViolationType.NON_MONOTONIC_TIMESTAMP,
    ViolationType.OHLC_INCONSISTENCY,
    ViolationType.NEGATIVE_VOLUME,
    ViolationType.GAP_DETECTED,
]

_ALL_CHECK_TYPES: frozenset[ViolationType] = frozenset(ViolationType)


def _require_ohlcv_schema(df: pl.DataFrame) -> None:
    """
    Verify that df has all required OHLCV columns with acceptable dtypes.

    Called at the start of validate_ohlcv() before any check executes.
    Empty DataFrames (zero rows) pass without error.

    Args:
        df: Polars DataFrame to inspect.

    Raises:
        ValueError: If any required column is missing or has an unsupported dtype.
    """
    for col, accepted in _REQUIRED_COLUMNS.items():
        if col not in df.columns:
            raise ValueError(
                f"Required column {col!r} is missing from the DataFrame. "
                f"Expected columns: {list(_REQUIRED_COLUMNS)}"
            )
        dtype = df[col].dtype
        is_datetime = col == "timestamp" and isinstance(dtype, pl.Datetime)
        if not is_datetime and dtype not in accepted:
            if col == "timestamp":
                accepted_names = "Float64, Int64, Datetime, Date"
            else:
                accepted_names = ", ".join(str(d) for d in accepted)
            raise ValueError(
                f"Column {col!r} has unsupported dtype {dtype!r}. Accepted: {accepted_names}"
            )


def validate_ohlcv(
    df: pl.DataFrame,
    *,
    interval: str | None = None,
    checks: list[ViolationType] | None = None,
) -> ValidationResult:
    """
    Validate the integrity of an OHLCV Polars DataFrame.

    Runs checks in deterministic order:
    1. DUPLICATE_TIMESTAMP
    2. NON_MONOTONIC_TIMESTAMP
    3. OHLC_INCONSISTENCY
    4. NEGATIVE_VOLUME
    5. GAP_DETECTED (only when interval is provided, or explicitly requested)

    Args:
        df: Polars DataFrame with required columns: timestamp, open, high,
            low, close, volume.
        interval: Optional interval string (e.g., "1D", "1H") required for
                  gap detection. If None and GAP_DETECTED is not explicitly in
                  checks, gap detection is silently skipped. If None and
                  ViolationType.GAP_DETECTED is explicitly in checks, raises
                  ValueError.
        checks: Optional subset of checks to run. If None, all applicable
                checks are run in the fixed deterministic order (GAP_DETECTED
                only if interval is provided). All items must be valid
                ViolationType members — unknown values raise ValueError.

    Returns:
        ValidationResult with:
        - is_valid: False if and only if at least one ERROR-level violation exists
        - violations: sorted by check execution order, then by row index
        - bars_checked: total rows examined
        - checks_run: ordered list of executed check types

    Raises:
        ValueError: If df is missing required columns, any column has an
                    unsupported dtype, checks contains an unknown ViolationType,
                    or GAP_DETECTED is explicitly requested without interval.

    Example::

        >>> result = validate_ohlcv(df, interval="1D")
        >>> if not result.is_valid:
        ...     for v in result.errors:
        ...         logger.error(v.message, extra={"rows": v.affected_rows})
    """
    _require_ohlcv_schema(df)

    if checks is None:
        # Default: run all checks; silently skip GAP_DETECTED when no interval given.
        checks_to_run = [
            c for c in _CHECK_ORDER if c != ViolationType.GAP_DETECTED or interval is not None
        ]
    else:
        # Reject unknown check types up front — a typo or wrong value must be an
        # immediate error, not a silent no-op that returns is_valid=True.
        unknown = [c for c in checks if c not in _ALL_CHECK_TYPES]
        if unknown:
            raise ValueError(
                f"Unknown check type(s): {unknown!r}. "
                f"Valid values: {[v.value for v in ViolationType]}"
            )

        # Guard: explicit GAP_DETECTED requires interval.
        if ViolationType.GAP_DETECTED in checks and interval is None:
            raise ValueError(
                "interval is required when ViolationType.GAP_DETECTED is included "
                "in checks. Provide interval='1D' (or the appropriate interval), "
                "or omit GAP_DETECTED from checks."
            )
        checks_to_run = list(checks)

    all_violations: list[Violation] = []

    # Execute in the fixed deterministic order, filtered to the requested checks.
    for check_type in _CHECK_ORDER:
        if check_type not in checks_to_run:
            continue

        if check_type == ViolationType.DUPLICATE_TIMESTAMP:
            all_violations.extend(check_duplicate_timestamps(df))
        elif check_type == ViolationType.NON_MONOTONIC_TIMESTAMP:
            all_violations.extend(check_monotonic_timestamps(df))
        elif check_type == ViolationType.OHLC_INCONSISTENCY:
            all_violations.extend(check_ohlc_consistency(df))
        elif check_type == ViolationType.NEGATIVE_VOLUME:
            all_violations.extend(check_volume_non_negative(df))
        elif check_type == ViolationType.GAP_DETECTED and interval is not None:
            all_violations.extend(check_gaps(df, interval))

    has_errors = any(v.severity == "ERROR" for v in all_violations)
    executed = [c for c in _CHECK_ORDER if c in checks_to_run]

    return ValidationResult(
        is_valid=not has_errors,
        violations=all_violations,
        bars_checked=len(df),
        checks_run=executed,
    )
