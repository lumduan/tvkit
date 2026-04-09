"""
Public exceptions for tvkit.validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tvkit.validation.models import ValidationResult


class DataIntegrityError(Exception):
    """
    Raised when OHLCV data fails validation and strict mode is enabled.

    Attributes:
        result: The full ValidationResult containing all violations found.
    """

    def __init__(self, result: ValidationResult) -> None:
        error_count = len(result.errors)
        super().__init__(
            f"OHLCV data integrity check failed: {error_count} error(s) found. "
            f"Inspect result.errors for details."
        )
        self.result = result
