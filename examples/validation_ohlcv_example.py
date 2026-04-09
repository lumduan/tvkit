"""
Data Integrity Validation Example

Demonstrates tvkit.validation usage patterns:
  1. Standalone validate_ohlcv() — inspect violations directly
  2. DataExporter.to_csv(validate=True, strict=False) — logging mode: violations logged,
     export proceeds even when ERROR violations are found
  3. DataExporter.to_csv(validate=True, strict=True) — strict mode: errors block export,
     file is not written
  4. Programmatic violation handling

Note on OHLCVBar and OHLC validation:
  OHLCVBar validates only the timestamp field at construction time. It does NOT enforce
  OHLC constraints (low <= open/close <= high). These structural checks are the
  responsibility of tvkit.validation, which is why they are caught at the DataExporter
  level rather than during bar construction.

Prerequisites:
  uv run python examples/validation_ohlcv_example.py
"""

import asyncio
import logging
import tempfile
from pathlib import Path

import polars as pl

from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.export import DataExporter
from tvkit.validation import (
    DataIntegrityError,
    ValidationResult,
    ViolationType,
    validate_ohlcv,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_TS = 1_672_531_200.0  # 2023-01-01 UTC


# ---------------------------------------------------------------------------
# Shared bar factories
# ---------------------------------------------------------------------------


def make_clean_bars(n: int = 10) -> list[OHLCVBar]:
    """Valid OHLCV bars: monotonic timestamps, valid OHLC, positive volume."""
    return [
        OHLCVBar(
            timestamp=BASE_TS + i * 86_400.0,
            open=100.0 + i,
            high=110.0 + i,
            low=90.0 + i,
            close=105.0 + i,
            volume=10_000.0 + i * 100,
        )
        for i in range(n)
    ]


def make_ohlc_error_bars(n: int = 10) -> list[OHLCVBar]:
    """
    OHLCV bars where some bars have open > high (OHLC_INCONSISTENCY ERROR).

    OHLCVBar does not enforce OHLC constraints at construction time — that is
    the job of tvkit.validation. These bars are created without error here.
    """
    bars = make_clean_bars(n)
    # Inject violations: open > high on bars 2 and 7
    bars[2] = OHLCVBar(
        timestamp=BASE_TS + 2 * 86_400.0,
        open=130.0,  # exceeds high=112.0 → OHLC ERROR
        high=112.0,
        low=92.0,
        close=107.0,
        volume=10_200.0,
    )
    bars[7] = OHLCVBar(
        timestamp=BASE_TS + 7 * 86_400.0,
        open=130.0,  # exceeds high=117.0 → OHLC ERROR
        high=117.0,
        low=97.0,
        close=112.0,
        volume=10_700.0,
    )
    return bars


def make_gapped_bars() -> list[OHLCVBar]:
    """
    OHLCV bars with a 3-day gap between bar 3 and bar 4.
    Produces GAP_DETECTED WARNING (not ERROR). is_valid stays True.
    """
    return [
        OHLCVBar(
            timestamp=BASE_TS + 0 * 86_400.0,
            open=100.0,
            high=110.0,
            low=90.0,
            close=105.0,
            volume=10_000.0,
        ),
        OHLCVBar(
            timestamp=BASE_TS + 1 * 86_400.0,
            open=101.0,
            high=111.0,
            low=91.0,
            close=106.0,
            volume=10_100.0,
        ),
        OHLCVBar(
            timestamp=BASE_TS + 2 * 86_400.0,
            open=102.0,
            high=112.0,
            low=92.0,
            close=107.0,
            volume=10_200.0,
        ),
        # 3-day gap here → GAP_DETECTED WARNING
        OHLCVBar(
            timestamp=BASE_TS + 5 * 86_400.0,
            open=105.0,
            high=115.0,
            low=95.0,
            close=110.0,
            volume=10_500.0,
        ),
        OHLCVBar(
            timestamp=BASE_TS + 6 * 86_400.0,
            open=106.0,
            high=116.0,
            low=96.0,
            close=111.0,
            volume=10_600.0,
        ),
    ]


# ---------------------------------------------------------------------------
# 1. Standalone validate_ohlcv()
# ---------------------------------------------------------------------------


def demo_standalone_validation() -> None:
    """Demonstrate using validate_ohlcv() directly on a Polars DataFrame."""
    logger.info("=" * 60)
    logger.info("DEMO 1: Standalone validate_ohlcv()")
    logger.info("=" * 60)

    # --- Clean data ---
    bars = make_clean_bars()
    df = pl.DataFrame(
        {
            "timestamp": [b.timestamp for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }
    )
    result: ValidationResult = validate_ohlcv(df, interval="1D")
    logger.info(
        "Clean DataFrame: is_valid=%s, bars_checked=%d, violations=%d",
        result.is_valid,
        result.bars_checked,
        len(result.violations),
    )
    assert result.is_valid
    assert result.violations == []

    # --- OHLC error data ---
    bars = make_ohlc_error_bars()
    df = pl.DataFrame(
        {
            "timestamp": [b.timestamp for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }
    )
    result = validate_ohlcv(df)
    logger.info(
        "OHLC-error DataFrame: is_valid=%s, errors=%d",
        result.is_valid,
        len(result.errors),
    )
    for v in result.errors:
        logger.info(
            "  [%s] %s — rows: %s, context: %s",
            v.check.value,
            v.message,
            v.affected_rows,
            v.context,
        )
    assert not result.is_valid
    # Bars 2 and 7 are affected — check by row index, not by count (count is implementation detail)
    error_rows = {row for v in result.errors for row in v.affected_rows}
    assert 2 in error_rows, f"Expected row 2 in error rows, got {error_rows}"
    assert 7 in error_rows, f"Expected row 7 in error rows, got {error_rows}"
    assert any(v.check == ViolationType.OHLC_INCONSISTENCY for v in result.errors)

    # --- Gap warning (WARNING-only, is_valid stays True) ---
    bars = make_gapped_bars()
    df = pl.DataFrame(
        {
            "timestamp": [b.timestamp for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }
    )
    result = validate_ohlcv(df, interval="1D")
    logger.info(
        "Gapped DataFrame: is_valid=%s, warnings=%d",
        result.is_valid,
        len(result.warnings),
    )
    assert result.is_valid  # WARNING does not affect is_valid
    assert any(v.check == ViolationType.GAP_DETECTED for v in result.warnings)

    logger.info("Demo 1 complete.\n")


# ---------------------------------------------------------------------------
# 2. DataExporter.to_csv(validate=True, strict=False) — logging mode
# ---------------------------------------------------------------------------


async def demo_export_logging_mode() -> None:
    """
    validate=True, strict=False (default):
    Violations are logged at WARNING level, but the export always proceeds.
    Even ERROR violations do not block the file write.
    """
    logger.info("=" * 60)
    logger.info("DEMO 2: to_csv(validate=True, strict=False) — logging mode")
    logger.info("=" * 60)

    # Use bars WITH OHLC errors — violations will be logged, but file is written anyway
    bars = make_ohlc_error_bars()
    exporter = DataExporter()

    with tempfile.TemporaryDirectory() as tmpdir:
        out = await exporter.to_csv(
            bars,
            Path(tmpdir) / "ohlc_errors.csv",
            validate=True,
            strict=False,  # violations logged, export proceeds
        )
        # File is written despite ERROR violations
        assert out.exists(), "File must be written in non-strict mode"
        logger.info(
            "Export succeeded (strict=False): %s — violations logged above as WARNING",
            out.name,
        )

    logger.info("Demo 2 complete.\n")


# ---------------------------------------------------------------------------
# 3. DataExporter.to_csv(validate=True, strict=True) — strict mode
# ---------------------------------------------------------------------------


async def demo_export_strict_mode() -> None:
    """
    validate=True, strict=True:
    DataIntegrityError is raised on ERROR violations. The file is NOT written.
    """
    logger.info("=" * 60)
    logger.info("DEMO 3: to_csv(validate=True, strict=True) — strict mode")
    logger.info("=" * 60)

    # OHLCVBar does not validate OHLC constraints at construction time.
    # These bars are created successfully; OHLC errors are caught by validate_ohlcv().
    bars = make_ohlc_error_bars()
    exporter = DataExporter()

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "should_not_exist.csv"
        try:
            await exporter.to_csv(
                bars,
                out_path,
                validate=True,
                strict=True,
            )
            raise AssertionError("Expected DataIntegrityError — should not reach here")
        except DataIntegrityError as e:
            logger.info(
                "Export blocked (strict=True): %d error(s) in %d bars",
                len(e.result.errors),
                e.result.bars_checked,
            )
            for v in e.result.errors:
                logger.info(
                    "  [%s] %s — rows: %s",
                    v.check.value,
                    v.message,
                    v.affected_rows,
                )
            assert not out_path.exists(), (
                "File must NOT be written when DataIntegrityError is raised"
            )
            logger.info("Confirmed: output file was NOT written.")

    logger.info("Demo 3 complete.\n")


# ---------------------------------------------------------------------------
# 4. Programmatic violation handling
# ---------------------------------------------------------------------------


def demo_programmatic_handling() -> None:
    """
    Use validate_ohlcv() directly for custom handling:
    - Separate errors from warnings
    - Extract affected row indices for downstream repair
    - Check specific violation types
    - Inspect serialized form (model_dump excludes .errors / .warnings properties)
    """
    logger.info("=" * 60)
    logger.info("DEMO 4: Programmatic violation handling")
    logger.info("=" * 60)

    bars = make_ohlc_error_bars()
    df = pl.DataFrame(
        {
            "timestamp": [b.timestamp for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }
    )
    result = validate_ohlcv(
        df,
        checks=[
            ViolationType.DUPLICATE_TIMESTAMP,
            ViolationType.OHLC_INCONSISTENCY,
            ViolationType.NEGATIVE_VOLUME,
        ],
    )

    # Separate by severity
    logger.info("Errors: %d, Warnings: %d", len(result.errors), len(result.warnings))

    # Collect all affected rows across all ERROR violations
    error_rows = sorted({row for v in result.errors for row in v.affected_rows})
    logger.info("Rows with errors: %s", error_rows)

    # Check for a specific violation type
    has_ohlc_errors = any(v.check == ViolationType.OHLC_INCONSISTENCY for v in result.errors)
    logger.info("OHLC violations present: %s", has_ohlc_errors)
    assert has_ohlc_errors

    # model_dump() for serialization — .errors and .warnings are @property, not serialized
    dump = result.model_dump()
    logger.info("Serialized keys: %s", list(dump.keys()))
    assert "errors" not in dump, "errors must not appear in model_dump()"
    assert "warnings" not in dump, "warnings must not appear in model_dump()"

    # Checks run are in deterministic order (subset of _CHECK_ORDER)
    logger.info("Checks run: %s", [c.value for c in result.checks_run])

    logger.info("Demo 4 complete.\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    demo_standalone_validation()
    await demo_export_logging_mode()
    await demo_export_strict_mode()
    demo_programmatic_handling()
    logger.info("All demos complete.")


if __name__ == "__main__":
    asyncio.run(main())
