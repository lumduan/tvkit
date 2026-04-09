# validate_ohlcv Reference

**Module:** `tvkit.validation`
**Introduced in:** v0.9.0

Validates the structural and logical integrity of an OHLCV Polars DataFrame. Returns a structured `ValidationResult` describing any violations found. All checks are pure functions with no side effects.

## Quick Example

```python
from tvkit.validation import validate_ohlcv, ViolationType

result = validate_ohlcv(df, interval="1D")

if result.is_valid:
    await exporter.to_csv(bars, "output.csv")
else:
    for v in result.errors:
        logger.error(v.message, extra={"check": v.check, "rows": v.affected_rows})
```

---

## Import

```python
from tvkit.validation import (
    validate_ohlcv,
    ValidationResult,
    Violation,
    ViolationType,
    DataIntegrityError,
    ContextValue,
    ViolationContext,
)
```

---

## `validate_ohlcv()`

```python
def validate_ohlcv(
    df: pl.DataFrame,
    *,
    interval: str | None = None,
    checks: list[ViolationType] | None = None,
) -> ValidationResult:
```

Validates the integrity of an OHLCV Polars DataFrame.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `df` | `pl.DataFrame` | — | DataFrame with required columns: `timestamp`, `open`, `high`, `low`, `close`, `volume` |
| `interval` | `str \| None` | `None` | Interval string for gap detection (e.g. `"1D"`, `"1H"`, `"15"`). Required for `GAP_DETECTED` check. Silently skips gap detection if `None` and `GAP_DETECTED` is not in `checks`. |
| `checks` | `list[ViolationType] \| None` | `None` | Subset of checks to run. If `None`, all applicable checks run. Execution always follows deterministic order regardless of list order. |

### Returns

`ValidationResult` — see [models reference](models.md).

### Raises

| Exception | Condition |
|-----------|-----------|
| `ValueError` | Required column missing or unsupported dtype |
| `ValueError` | `ViolationType.GAP_DETECTED` in `checks` but `interval` is `None` |
| `ValueError` | Unknown value in `checks` |

---

## Required Schema

`validate_ohlcv()` raises `ValueError` if the DataFrame does not meet the schema before any check runs.

| Column | Accepted Polars Dtypes | Nullable |
|--------|------------------------|----------|
| `timestamp` | `Float64`, `Int64`, `Datetime(...)`, `Date` | No |
| `open` | `Float64`, `Float32` | No |
| `high` | `Float64`, `Float32` | No |
| `low` | `Float64`, `Float32` | No |
| `close` | `Float64`, `Float32` | No |
| `volume` | `Float64`, `Float32`, `Int64` | No |

**`Float64` timestamp note:** tvkit's `PolarsFormatter` produces `Float64` epoch-seconds timestamps. This is the canonical timestamp format for tvkit DataFrames.

**`Int64` timestamp note:** Interpreted as epoch milliseconds (Polars convention). No conversion is performed — the caller is responsible for correct units.

Empty DataFrames (0 rows) pass schema validation. All checks return empty violation lists.

---

## Deterministic Check Order

When `checks=None`, all applicable checks run in this fixed order:

| # | `ViolationType` | Severity | Condition |
|---|-----------------|----------|-----------|
| 1 | `DUPLICATE_TIMESTAMP` | ERROR | Any timestamp appears more than once |
| 2 | `NON_MONOTONIC_TIMESTAMP` | ERROR | Any consecutive pair where `ts[i] >= ts[i+1]` |
| 3 | `OHLC_INCONSISTENCY` | ERROR | Any bar where `low > open`, `low > close`, `open > high`, or `close > high`, or any NaN in OHLC columns |
| 4 | `NEGATIVE_VOLUME` | ERROR | Any bar with `volume < 0` or NaN volume |
| 5 | `GAP_DETECTED` | WARNING | Any consecutive pair where timestamp difference exceeds the expected interval |

Violations are sorted by this check order, then by row index within each check. This ordering is stable across releases.

---

## Gap Detection Behavior

| `interval` | `checks` | Behavior |
|---|---|---|
| `None` | `None` (all checks) | Gap detection silently skipped |
| `"1D"` | `None` (all checks) | Gap detection runs |
| `None` | `[ViolationType.GAP_DETECTED]` | Raises `ValueError` immediately |
| `"1H"` | `[ViolationType.GAP_DETECTED]` | Gap detection runs |

### Supported Interval Strings

| String | Duration |
|--------|----------|
| `"1"` | 1 minute |
| `"5"` | 5 minutes |
| `"15"` | 15 minutes |
| `"30"` | 30 minutes |
| `"60"` / `"1H"` | 1 hour |
| `"240"` / `"4H"` | 4 hours |
| `"1D"` | 1 day |
| `"1W"` | 1 week |
| `"1M"` | 1 month (30 days) |

### Phase 1 Calendar Limitation

Gap detection in Phase 1 is **cadence-only and not calendar-aware**. For daily equity bars (`"1D"`), weekends and public holidays appear as `GAP_DETECTED` WARNING violations. These are expected and should be filtered by the caller if needed. Calendar-aware gap detection is planned as a future enhancement.

---

## Selective Checks

Run only a specific subset of checks:

```python
from tvkit.validation import validate_ohlcv, ViolationType

# Only check for duplicates and OHLC inconsistencies
result = validate_ohlcv(
    df,
    checks=[ViolationType.DUPLICATE_TIMESTAMP, ViolationType.OHLC_INCONSISTENCY],
)

# Only gap detection (interval required)
result = validate_ohlcv(
    df,
    interval="1H",
    checks=[ViolationType.GAP_DETECTED],
)
```

Checks always execute in `_CHECK_ORDER` regardless of the order in the `checks` list.

---

## DataExporter Integration

`DataExporter.to_csv()` and `DataExporter.to_json()` accept opt-in validation via keyword-only parameters:

```python
exporter = DataExporter()

# Logging mode: violations logged at WARNING, export always proceeds
await exporter.to_csv(bars, "output.csv", validate=True, interval="1D")

# Strict mode: DataIntegrityError raised on ERROR violations, file not written
await exporter.to_csv(bars, "output.csv", validate=True, strict=True, interval="1D")
```

See [DataExporter reference](../export/exporter.md) and the [data validation guide](../../guides/data-validation.md) for full details.
