# Data Integrity for OHLCV Data

[Home](../index.md) > Concepts > Data Integrity

This page explains why OHLCV data integrity matters, what failure modes occur in practice, and how `tvkit.validation` is designed to address them.

---

## The Problem

tvkit retrieves OHLCV data over TradingView's WebSocket API — a persistent, real-time connection that delivers bars as they are produced by the exchange. This delivery mechanism introduces failure modes that are not present in static file-based data sources:

| Failure Mode | How It Happens |
|---|---|
| **Duplicate bars** | WebSocket reconnects replay bars already received — the same timestamp appears more than once |
| **Out-of-order timestamps** | Late-arriving or reordered messages cause bars to appear non-chronologically |
| **OHLC constraint violations** | Encoding bugs or gap-fill edge cases produce bars where `low > open`, `open > high`, or similar |
| **Negative or NaN volume** | Edge cases in the TradingView data protocol produce invalid volume values |
| **Unexpected gaps** | Connection loss or exchange interruptions leave missing bars for a given interval |

Without a validation layer, these issues are silently passed to downstream pipelines — corrupting exports, breaking backtests, and introducing subtle, hard-to-debug data quality bugs.

---

## Why Silent Corruption Is Dangerous

The failure modes above do not produce exceptions. A DataFrame with a duplicate timestamp row, an OHLC inversion, or a missing bar looks structurally identical to clean data. Downstream code — whether a moving average calculation, a backtest, or a CSV export — will consume corrupt data without any indication of a problem.

The resulting bugs surface far from the data source:
- A backtest gives different results on different days because cached bars contain duplicates that change which rows are processed
- A strategy fires spurious signals because OHLC constraints are violated on specific bars
- Aggregated statistics are subtly wrong because gaps in the data are not accounted for

Validation at the boundary — before the data enters any pipeline — is the only reliable defense.

---

## tvkit.validation Design Philosophy

`tvkit.validation` is built around six principles:

| Principle | Decision |
|---|---|
| **Non-destructive** | Validation reports problems but never mutates the DataFrame. The caller decides what to do. |
| **Composable** | Individual checks are independently callable — use only what you need. |
| **Structured results** | All violations are typed Pydantic models, not raw strings or log messages. |
| **Pure functions** | Check functions have zero side effects — no logging, no I/O, no mutation. |
| **Explicit errors** | Missing required arguments raise `ValueError` immediately, not silently skipped. |
| **Deterministic** | Checks run in a fixed order. Violations are sorted by check order, then row index. The same DataFrame always produces the same result. |

---

## Severity Levels

Not all violations are equally serious. `tvkit.validation` uses two severity levels:

### ERROR

Structural data corruption. The data cannot be safely used by downstream pipelines.

`ValidationResult.is_valid` is `False` when any ERROR violation is present.

| Check | What it catches |
|---|---|
| `DUPLICATE_TIMESTAMP` | Two or more bars share the same timestamp |
| `NON_MONOTONIC_TIMESTAMP` | Timestamps are not strictly increasing |
| `OHLC_INCONSISTENCY` | `low > open`, `low > close`, `open > high`, `close > high`, or NaN in any price column |
| `NEGATIVE_VOLUME` | `volume < 0` or NaN volume |

### WARNING

Potentially expected conditions that the caller should acknowledge. `ValidationResult.is_valid` stays `True` even when WARNING violations exist.

| Check | What it catches |
|---|---|
| `GAP_DETECTED` | Consecutive bars with a timestamp gap larger than the expected interval |

WARNING-only results do not block `DataExporter` even with `strict=True`. The caller is responsible for deciding whether gaps are acceptable.

---

## The Gap Detection Limitation (Phase 1)

Gap detection in Phase 1 is **cadence-only and not calendar-aware**.

For a given interval, the check flags any consecutive pair of bars where the timestamp difference exceeds one expected interval period. This works correctly for:

- **Continuous markets** — crypto, forex: bars are produced 24/7, so any gap is unexpected
- **Intraday bars** — `"1H"`, `"15"` within a single trading session

For **daily equity bars** (`"1D"`), however, the market does not trade every calendar day. Weekends, public holidays, and exchange-specific non-trading days all produce gaps in the bar sequence that are completely expected. Phase 1 reports these as `GAP_DETECTED` WARNING violations.

**This is intentional.** The WARNING severity means `is_valid` stays `True` and exports are not blocked. Calendar-aware gap detection (which would suppress expected non-trading-day gaps) is planned as a future enhancement.

To suppress gap warnings for equity daily data, either omit `interval` or run checks selectively:

```python
from tvkit.validation import validate_ohlcv, ViolationType

# Option 1: omit interval (gap detection silently skipped)
result = validate_ohlcv(df)

# Option 2: run all structural checks explicitly, excluding GAP_DETECTED
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

## Validation at the Export Boundary

The primary integration point is `DataExporter`. Validation is opt-in and non-breaking:

```python
from tvkit.export import DataExporter
from tvkit.validation import DataIntegrityError

exporter = DataExporter()

# validate=True: violations are logged at WARNING, export always proceeds
await exporter.to_csv(bars, "output.csv", validate=True, interval="1D")

# strict=True: DataIntegrityError raised on ERROR violations, file is NOT written
try:
    await exporter.to_csv(bars, "output.csv", validate=True, strict=True, interval="1D")
except DataIntegrityError as e:
    for v in e.result.errors:
        logger.error(v.message, extra={"check": v.check.value, "rows": v.affected_rows})
```

`DataIntegrityError.result` carries the full `ValidationResult`, so structured error handling and retry logic have access to every violation detail.

---

## Further Reading

- [Data Validation guide](../guides/data-validation.md) — workflow examples and common patterns
- [`validate_ohlcv` reference](../reference/validation/validate_ohlcv.md) — full function signature and schema contract
- [Validation models reference](../reference/validation/models.md) — `ValidationResult`, `Violation`, `ViolationType`, `DataIntegrityError`
