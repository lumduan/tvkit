"""
Utility functions and models for the tvkit API.

This package provides essential utilities for TradingView API interactions,
including timestamp conversion, symbol validation, and indicator management.

The package is organized into focused modules:
- models: Pydantic data models for TradingView structures
- timestamp: Timestamp conversion utilities
- symbol_validator: Symbol validation service
- indicator_service: TradingView indicator management

All functions and models are re-exported at package level for backward compatibility.
"""

# Re-export all functions and models for backward compatibility
from .indicator_service import (
    display_and_select_indicator,
    fetch_indicator_metadata,
    fetch_tradingview_indicators,
    prepare_indicator_metadata,
)
from .models import (
    IndicatorData,
    InputValue,
    PineFeatures,
    ProfileConfig,
    StudyPayload,
    SymbolConversionResult,
)
from .symbol_validator import convert_symbol_format, validate_symbols
from .timestamp import convert_timestamp_to_iso

__all__ = [
    # Functions
    "convert_timestamp_to_iso",
    "validate_symbols",
    "convert_symbol_format",
    "fetch_tradingview_indicators",
    "display_and_select_indicator",
    "fetch_indicator_metadata",
    "prepare_indicator_metadata",
    # Models
    "IndicatorData",
    "PineFeatures",
    "ProfileConfig",
    "InputValue",
    "StudyPayload",
    "SymbolConversionResult",
]
