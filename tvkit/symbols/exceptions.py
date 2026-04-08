"""
Exception types for the tvkit symbol normalization layer.
"""


class SymbolNormalizationError(ValueError):
    """
    Raised when a symbol string cannot be normalized to canonical EXCHANGE:SYMBOL form.

    Attributes:
        original: The original symbol string that failed normalization.
        reason: Human-readable explanation of why normalization failed.

    Example:
        >>> try:
        ...     normalize_symbol("AAPL")
        ... except SymbolNormalizationError as exc:
        ...     print(exc.original)  # "AAPL"
        ...     print(exc.reason)    # "no exchange prefix"
        ...     print(exc)           # "Cannot normalize 'AAPL': no exchange prefix"
    """

    def __init__(self, original: str, reason: str) -> None:
        self.original = original
        self.reason = reason
        super().__init__(f"Cannot normalize '{original}': {reason}")
