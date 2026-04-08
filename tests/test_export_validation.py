"""
Integration tests for DataExporter validation integration (Phase 3).

Tests for:
- to_csv(validate=False) skips validation
- to_csv(validate=True) logs violations
- to_csv(validate=True, strict=False) exports despite ERROR violations
- to_csv(validate=True, strict=True) raises DataIntegrityError on ERROR violations
- to_csv(validate=True, strict=True) does NOT raise on WARNING-only results
- DataIntegrityError.result carries the full ValidationResult
- strict=True does not write the file on ERROR violations
"""
