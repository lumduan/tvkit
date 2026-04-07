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
Phase 2 adds bare-ticker resolution via ``NormalizationConfig.default_exchange`` and
``TVKIT_DEFAULT_EXCHANGE`` environment variable support.
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
