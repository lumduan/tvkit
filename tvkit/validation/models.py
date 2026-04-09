"""
Pydantic models for tvkit.validation.

Defines the data types used to represent validation results and violations.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ViolationType(StrEnum):
    """Enumeration of all supported OHLCV validation check types."""

    DUPLICATE_TIMESTAMP = "duplicate_timestamp"
    NON_MONOTONIC_TIMESTAMP = "non_monotonic_timestamp"
    OHLC_INCONSISTENCY = "ohlc_inconsistency"
    NEGATIVE_VOLUME = "negative_volume"
    GAP_DETECTED = "gap_detected"


# Tightly-typed context value — no Any
ContextValue = str | int | float | bool | None
ViolationContext = dict[str, ContextValue]


class Violation(BaseModel):
    """A single data integrity violation found in an OHLCV DataFrame."""

    check: ViolationType = Field(description="The validation check that produced this violation")
    severity: Literal["ERROR", "WARNING"] = Field(description="Severity level of this violation")
    message: str = Field(description="Human-readable description of the violation")
    affected_rows: list[int] = Field(
        default_factory=list,
        description="Row indices (0-based) in the input DataFrame containing the violation",
    )
    context: ViolationContext = Field(
        default_factory=dict,
        description="Structured context values (str, int, float, bool, or None only)",
    )


class ValidationResult(BaseModel):
    """Aggregate result of all validation checks on an OHLCV DataFrame."""

    is_valid: bool = Field(
        description=(
            "True if there are zero ERROR-level violations. "
            "WARNING violations do not affect this flag."
        )
    )
    violations: list[Violation] = Field(
        default_factory=list,
        description=(
            "All violations found, in deterministic order: "
            "sorted by check execution order, then by row index within each check."
        ),
    )
    bars_checked: int = Field(description="Total number of bars examined")
    checks_run: list[ViolationType] = Field(
        description="Ordered list of checks that were executed, in execution order"
    )

    @property
    def errors(self) -> list[Violation]:
        """
        Return only ERROR-severity violations.

        Convenience accessor — not serialized by model_dump().
        """
        return [v for v in self.violations if v.severity == "ERROR"]

    @property
    def warnings(self) -> list[Violation]:
        """
        Return only WARNING-severity violations.

        Convenience accessor — not serialized by model_dump().
        """
        return [v for v in self.violations if v.severity == "WARNING"]
