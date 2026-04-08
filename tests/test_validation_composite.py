"""
Integration tests for tvkit.validation.validate_ohlcv() composite validator.

Tests for:
- validate_ohlcv() orchestration and deterministic check ordering
- Schema validation (_require_ohlcv_schema)
- selective checks via the checks= parameter
- Gap detection skip/raise behaviour based on interval and checks arguments
- ValidationResult.is_valid flag, errors, warnings properties
"""
