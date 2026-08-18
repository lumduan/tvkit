# Data Validation

[Home](../index.md) > Guides > Data Validation

`tvkit.validation` provides a data integrity layer for OHLCV data. It catches issues that TradingView's WebSocket API can introduce — duplicate bars, out-of-order timestamps, OHLC constraint violations, negative volume, and unexpected gaps — before they silently corrupt exports, backtests, or downstream pipelines.

## Prerequisites

- tvkit installed: see [Installation](../getting-started/installation.md)
- Fetch OHLCV data first: see [Historical Data guide](historical-data.md)

---

## Validation in One Line

The simplest usage is validating a DataFrame you already have:

```python
import polars as pl
from tvkit.validation import validate_ohlcv

result = validate_ohlcv(df)

if result.is_valid:
    print(f"Clean: {result.bars_checked} bars, no errors")
else:
    for v in result.errors:
        print(f"[{v.check}] {v.message} (rows: {v.affected_rows})")
```

**Output** — 365 real AAPL daily bars:

```text
Clean: 365 bars, no errors
```

`df["timestamp"]` must be `Float64`, `Int64`, `Datetime` or `Date`. `DataExporter.to_polars()`
defaults to `timestamp_format="iso"`, which yields a `String` column and raises
`ValueError: Column 'timestamp' has unsupported dtype String`. Build the frame with
`to_polars(bars, timestamp_format="unix")` — see
[Standalone Validation Without Export](#standalone-validation-without-export).

*Example output — live market values will differ.*

---

## Validation Before Export

The most common pattern is gating an export on validation. Pass `validate=True` to `to_csv()` or `to_json()`:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter

async def main() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", interval="1D", bars_count=365)

    exporter = DataExporter()

    # Logging mode: violations are logged at WARNING, export always proceeds
    await exporter.to_csv(bars, "aapl.csv", validate=True, interval="1D")

asyncio.run(main())
```

**Output:**

```text
WARNING  tvkit.export.data_exporter: Gap detected between rows 2 and 3: expected 86400s, got 255600s
WARNING  tvkit.export.data_exporter: Gap detected between rows 7 and 8: expected 86400s, got 259200s
WARNING  tvkit.export.data_exporter: Gap detected between rows 12 and 13: expected 86400s, got 259200s
...
```

# 80 GAP_DETECTED warnings across 365 daily bars — every weekend and market holiday
# the export still proceeds and `to_csv` returns `aapl.csv`

When violations are found, each one is logged at `WARNING` level. A duplicate looks like this:

```text
WARNING  tvkit.export.data_exporter: Duplicate timestamp '1735689600.0' appears 2 time(s) at rows [0, 1]
```

with the structured fields carried on the `Violation` itself:

```text
context={'expected_interval': '1D', 'actual_gap': '255600s',
         'prev_timestamp': '1741357800.0', 'curr_timestamp': '1741613400.0'}
```

---

## Strict Mode — Block Exports on Corrupt Data

Use `strict=True` to treat ERROR violations as a hard failure. The file is **not** written:

```python
from tvkit.validation import DataIntegrityError

try:
    await exporter.to_csv(bars, "aapl.csv", validate=True, strict=True, interval="1D")
except DataIntegrityError as e:
    print(f"Export blocked: {len(e.result.errors)} error(s) found")
    for v in e.result.errors:
        print(f"  [{v.check}] {v.message} (rows {v.affected_rows})")
```

**Output** — with two bars sharing a timestamp:

```text
Export blocked: 2 error(s) found
  [duplicate_timestamp] Duplicate timestamp '1735689600.0' appears 2 time(s) at rows [0, 1]
  [non_monotonic_timestamp] Timestamp at row 1 ('1735689600.0') is not strictly greater than row 0 ('1735689600.0')
```

# one duplicate trips two checks — `aapl.csv` is not written
# `str(exc)` is: OHLCV data integrity check failed: 2 error(s) found. Inspect result.errors for details.
# `v.check` is a StrEnum, so it prints as `duplicate_timestamp`, not `ViolationType.DUPLICATE_TIMESTAMP`

`DataIntegrityError.result` is the full `ValidationResult` — use it for structured logging or retry logic.

---

## Severity Levels

| Severity | `is_valid` | Blocks export (`strict=True`) | When |
|----------|-----------|-------------------------------|------|
| `ERROR` | `False` | Yes | Structural corruption (duplicate bars, OHLC violations, etc.) |
| `WARNING` | `True` | **No** | Expected conditions (calendar gaps in daily equity data) |

WARNING-only results never raise even with `strict=True`:

```python
# Daily equity data will have weekend gaps → GAP_DETECTED WARNING
# strict=True still does NOT block this export
await exporter.to_csv(
    equity_bars, "spy.csv", validate=True, strict=True, interval="1D"
)
```

**Output:**

```text
WARNING  tvkit.export.data_exporter: Gap detected between rows 2 and 3: expected 86400s, got 255600s
...
```

Returns `spy.csv`. 80 warnings, no exception — `is_valid` stays `True` because no violation has
`severity == "ERROR"`.

---

## Gap Detection

Gap detection requires an explicit `interval`. Without it, `GAP_DETECTED` checks are silently skipped:

```python
# No gap check (interval omitted)
result = validate_ohlcv(df)

# Gap check enabled
result = validate_ohlcv(df, interval="1D")
result = validate_ohlcv(df, interval="1H")
result = validate_ohlcv(df, interval="15")   # 15-minute bars
```

### Calendar Gap Limitation

Phase 1 gap detection is **cadence-only** — it flags any pair of consecutive bars where the timestamp difference exceeds one expected interval period. For daily equity bars (`"1D"`):

- Weekends → flagged as `GAP_DETECTED` (WARNING)
- Public holidays → flagged as `GAP_DETECTED` (WARNING)
- Exchange-specific non-trading days → flagged as `GAP_DETECTED` (WARNING)

This is **intentional**. For continuous markets (crypto, forex) and intraday bars, gap detection works without noise. Calendar-aware gap detection is planned as a future enhancement.

To suppress calendar gap noise for equity data, validate without gap detection:

```python
from tvkit.validation import validate_ohlcv, ViolationType

# Run all checks except gap detection
result = validate_ohlcv(
    df,
    checks=[
        ViolationType.DUPLICATE_TIMESTAMP,
        ViolationType.NON_MONOTONIC_TIMESTAMP,
        ViolationType.OHLC_INCONSISTENCY,
        ViolationType.NEGATIVE_VOLUME,
    ],
)
```

---

## Standalone Validation Without Export

`validate_ohlcv()` is a pure function — it does not write files or log. Use it anywhere in your pipeline:

```python
from tvkit.validation import validate_ohlcv, ValidationResult, ViolationType

# After fetching, before caching.
# validate_ohlcv needs a numeric timestamp column, so ask for one — the
# default timestamp_format="iso" yields a String column it rejects.
df = await exporter.to_polars(bars, timestamp_format="unix")
result: ValidationResult = validate_ohlcv(df, interval="1D")

# Log structured violations
for v in result.violations:
    if v.severity == "ERROR":
        logger.error(
            v.message,
            extra={"check": v.check.value, "rows": v.affected_rows, **v.context},
        )
    else:
        logger.warning(
            v.message,
            extra={"check": v.check.value, "rows": v.affected_rows},
        )

# Raise programmatically
if not result.is_valid:
    raise ValueError(f"Data integrity failed: {len(result.errors)} error(s)")
```

**Output** — the `ValidationResult` for 365 clean AAPL daily bars:

| field | value |
|---|---|
| `is_valid` | `True` |
| `bars_checked` | `365` |
| `checks_run` | `['duplicate_timestamp', 'non_monotonic_timestamp', 'ohlc_inconsistency', 'negative_volume', 'gap_detected']` |
| `violations` | 80 entries, all `severity='WARNING'`, all `gap_detected` |

```text
WARNING  Gap detected between rows 2 and 3: expected 86400s, got 255600s
```

# `result.model_dump()` returns only ['is_valid', 'violations', 'bars_checked', 'checks_run'] —
# `.errors` and `.warnings` are plain properties and are not serialized

---

## Selective Checks

Run a specific subset of checks:

```python
from tvkit.validation import validate_ohlcv, ViolationType

# Only check for structural issues (fastest path)
result = validate_ohlcv(df, checks=[ViolationType.DUPLICATE_TIMESTAMP])

# Only check OHLC consistency and volume
result = validate_ohlcv(
    df,
    checks=[ViolationType.OHLC_INCONSISTENCY, ViolationType.NEGATIVE_VOLUME],
)
```

Checks always execute in the deterministic order (`DUPLICATE_TIMESTAMP` → `NON_MONOTONIC_TIMESTAMP` → `OHLC_INCONSISTENCY` → `NEGATIVE_VOLUME` → `GAP_DETECTED`) regardless of the order in the `checks` list.

---

## What Each Check Detects

| Check | What it catches | Severity |
|-------|----------------|----------|
| `DUPLICATE_TIMESTAMP` | Two or more bars with the same timestamp (e.g., reconnect replay) | ERROR |
| `NON_MONOTONIC_TIMESTAMP` | Timestamps not strictly increasing (e.g., late-arriving or reordered bars) | ERROR |
| `OHLC_INCONSISTENCY` | `low > open`, `low > close`, `open > high`, `close > high`, or NaN in any price column | ERROR |
| `NEGATIVE_VOLUME` | `volume < 0` or NaN volume | ERROR |
| `GAP_DETECTED` | Timestamp gap larger than the expected interval cadence | WARNING |

---

## Full API Reference

- [`validate_ohlcv()` — function reference](../reference/validation/index.md)
- [Data models: `ValidationResult`, `Violation`, `ViolationType`, `DataIntegrityError`](../reference/validation/models.md)
- [`DataExporter.to_csv()` / `.to_json()` — updated params](../reference/export/exporter.md)
