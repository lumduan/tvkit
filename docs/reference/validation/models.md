# Validation Models Reference

**Module:** `tvkit.validation`
**Introduced in:** v0.9.0

Data models, enums, and exceptions used by the `tvkit.validation` module.

---

## `ViolationType`

```python
from tvkit.validation import ViolationType
```

`StrEnum` identifying the check that produced a violation. The string value is used in structured logging and serialization.

```python
class ViolationType(StrEnum):
    DUPLICATE_TIMESTAMP = "duplicate_timestamp"
    NON_MONOTONIC_TIMESTAMP = "non_monotonic_timestamp"
    OHLC_INCONSISTENCY = "ohlc_inconsistency"
    NEGATIVE_VOLUME = "negative_volume"
    GAP_DETECTED = "gap_detected"
```

---

## `Violation`

```python
from tvkit.validation import Violation
```

A single data integrity violation found in an OHLCV DataFrame.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `check` | `ViolationType` | The validation check that produced this violation |
| `severity` | `Literal["ERROR", "WARNING"]` | Severity level |
| `message` | `str` | Human-readable description |
| `affected_rows` | `list[int]` | 0-based row indices in the input DataFrame |
| `context` | `ViolationContext` | Structured context values (`str`, `int`, `float`, `bool`, or `None`) |

### Severity Semantics

| Severity | Effect on `ValidationResult.is_valid` | Meaning |
|----------|--------------------------------------|---------|
| `ERROR` | Sets `is_valid=False` | Structural data corruption — downstream pipelines cannot safely use this data |
| `WARNING` | No effect (`is_valid` stays `True`) | Potentially expected condition — caller should acknowledge and decide |

Currently, only `GAP_DETECTED` produces `WARNING` violations. All other checks produce `ERROR`.

---

## `ValidationResult`

```python
from tvkit.validation import ValidationResult
```

Aggregate result of all validation checks on an OHLCV DataFrame.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_valid` | `bool` | `True` iff zero ERROR violations. WARNING violations do not affect this flag. |
| `violations` | `list[Violation]` | All violations in deterministic order (check order, then row index) |
| `bars_checked` | `int` | Total number of bars examined |
| `checks_run` | `list[ViolationType]` | Ordered list of checks executed |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `.errors` | `list[Violation]` | Only ERROR-severity violations. Not serialized by `model_dump()`. |
| `.warnings` | `list[Violation]` | Only WARNING-severity violations. Not serialized by `model_dump()`. |

### Example

```python
result = validate_ohlcv(df, interval="1D")

print(result.is_valid)           # True or False
print(result.bars_checked)       # e.g. 252
print(result.checks_run)         # [ViolationType.DUPLICATE_TIMESTAMP, ...]

for v in result.errors:
    logger.error(v.message, extra={"check": v.check.value, "rows": v.affected_rows})

for v in result.warnings:
    logger.warning(v.message, extra={"check": v.check.value, "rows": v.affected_rows})
```

---

## `DataIntegrityError`

```python
from tvkit.validation import DataIntegrityError
```

Raised by `DataExporter` when `strict=True` and ERROR-level violations are found. Carries the full `ValidationResult` for structured error handling.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `result` | `ValidationResult` | The full validation result with all violations |

### Example

```python
try:
    await exporter.to_csv(bars, "output.csv", validate=True, strict=True)
except DataIntegrityError as e:
    print(f"Found {len(e.result.errors)} error(s)")
    for v in e.result.errors:
        print(f"  [{v.check}] {v.message} (rows: {v.affected_rows})")
```

---

## Type Aliases

### `ContextValue`

```python
ContextValue = str | int | float | bool | None
```

A single value in a `Violation.context` dictionary. Restricted to JSON-serializable primitives.

### `ViolationContext`

```python
ViolationContext = dict[str, ContextValue]
```

The type of `Violation.context`. Keys are strings; values are `ContextValue` (no nested dicts, no lists).
