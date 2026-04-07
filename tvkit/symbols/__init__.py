"""
tvkit.symbols — canonical symbol normalization layer.

Provides synchronous, pure-string normalization of TradingView instrument references
to the canonical ``EXCHANGE:SYMBOL`` form (uppercase, colon-separated).

Public API::

    from tvkit.symbols import (
        normalize_symbol,
        normalize_symbols,
        normalize_symbol_detailed,
        NormalizedSymbol,
        NormalizationConfig,
        NormalizationType,
        SymbolNormalizationError,
    )

Phase 1 handles exchange-aware symbol variants (colon, dash, lowercase, whitespace).
Bare-ticker resolution and env-var config support are Phase 2 features.
"""

from .exceptions import SymbolNormalizationError
from .models import NormalizationConfig, NormalizationType, NormalizedSymbol
from .normalizer import normalize_symbol, normalize_symbol_detailed, normalize_symbols

__all__: list[str] = [
    "normalize_symbol",
    "normalize_symbols",
    "normalize_symbol_detailed",
    "NormalizedSymbol",
    "NormalizationConfig",
    "NormalizationType",
    "SymbolNormalizationError",
]
