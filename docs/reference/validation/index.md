# Validation Reference

**Module:** `tvkit.validation`
**Introduced in:** v0.9.0

`tvkit.validation` provides a data integrity layer for OHLCV data. It catches structural and logical issues in financial bar data before they silently corrupt exports, backtests, or downstream pipelines.

---

## Reference Pages

| Page | Contents |
|------|----------|
| [`validate_ohlcv`](validate_ohlcv.md) | Function signature, parameters, schema contract, check order, gap detection behavior, selective checks |
| [`Models`](models.md) | `ValidationResult`, `Violation`, `ViolationType`, `DataIntegrityError`, `ContextValue`, `ViolationContext` |

---

## Quick Import

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

## See Also

- [Data Validation guide](../../guides/data-validation.md) — workflow examples and common patterns
- [Data Integrity concepts](../../concepts/data-integrity.md) — why validation matters and design rationale
- [DataExporter reference](../export/exporter.md) — `validate`, `strict`, `interval` parameters
