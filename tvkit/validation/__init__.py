"""
tvkit.validation — OHLCV data integrity validation.

Provides utilities to verify the structural and logical consistency of OHLCV
bar data before it is cached, exported, or consumed by downstream pipelines.

Public API:
    validate_ohlcv(df, *, interval, checks) -> ValidationResult
    ValidationResult
    Violation
    ViolationType
    DataIntegrityError
    ContextValue
    ViolationContext

Example::

    from tvkit.validation import validate_ohlcv

    result = validate_ohlcv(df, interval="1D")
    if result.is_valid:
        await exporter.to_csv("output.csv")
    else:
        for v in result.violations:
            logger.warning(v.message, extra={"check": v.check, "rows": v.affected_rows})
"""

from tvkit.validation.exceptions import DataIntegrityError
from tvkit.validation.models import (
    ContextValue,
    ValidationResult,
    Violation,
    ViolationContext,
    ViolationType,
)
from tvkit.validation.validator import validate_ohlcv

__all__ = [
    "validate_ohlcv",
    "ValidationResult",
    "Violation",
    "ViolationType",
    "DataIntegrityError",
    "ContextValue",
    "ViolationContext",
]
