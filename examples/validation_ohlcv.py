"""
OHLCV Data Integrity Validation

Primary example: fetch → validate → export workflow using tvkit.validation.

This script uses synthetic continuous-market data (hourly bars, no calendar gaps)
to demonstrate the full validation pipeline cleanly. For a comprehensive multi-demo
walkthrough including strict mode, programmatic handling, and selective checks, see
examples/validation_ohlcv_example.py.

Run:
    uv run python examples/validation_ohlcv.py
"""

import asyncio
import logging
import tempfile
from pathlib import Path

import polars as pl

from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.export import DataExporter
from tvkit.validation import DataIntegrityError, validate_ohlcv

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# 2024-01-01 00:00:00 UTC in epoch seconds
_BASE_TS = 1_704_067_200.0
_ONE_HOUR = 3_600.0


def make_hourly_bars(n: int = 24) -> list[OHLCVBar]:
    """Generate n clean hourly bars (continuous market — no calendar gaps)."""
    return [
        OHLCVBar(
            timestamp=_BASE_TS + i * _ONE_HOUR,
            open=100.0 + i * 0.5,
            high=102.0 + i * 0.5,
            low=99.0 + i * 0.5,
            close=101.0 + i * 0.5,
            volume=50_000.0 + i * 500,
        )
        for i in range(n)
    ]


async def main() -> None:
    bars = make_hourly_bars(n=24)
    exporter = DataExporter()

    # ------------------------------------------------------------------
    # 1. Standalone validation — inspect the result before exporting
    # ------------------------------------------------------------------
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
    result = validate_ohlcv(df, interval="1H")
    logger.info(
        "Validation result: is_valid=%s, bars_checked=%d, violations=%d",
        result.is_valid,
        result.bars_checked,
        len(result.violations),
    )

    if not result.is_valid:
        for v in result.errors:
            logger.error(v.message, extra={"check": v.check.value, "rows": v.affected_rows})
        return

    # ------------------------------------------------------------------
    # 2. Export with validation gate (strict mode — blocks on ERROR violations)
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "ohlcv_1h.csv"
        try:
            written = await exporter.to_csv(
                bars,
                out,
                validate=True,
                strict=True,
                interval="1H",
            )
            logger.info("Exported clean data to: %s", written.name)
        except DataIntegrityError as e:
            logger.error(
                "Export blocked: %d error(s) found in %d bars",
                len(e.result.errors),
                e.result.bars_checked,
            )
            for v in e.result.errors:
                logger.error("  [%s] %s — rows: %s", v.check.value, v.message, v.affected_rows)


if __name__ == "__main__":
    asyncio.run(main())
