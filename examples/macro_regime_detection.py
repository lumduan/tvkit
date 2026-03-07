#!/usr/bin/env python3
"""
Macro Regime Detection — tvkit Example

Fetches INDEX:NDFI (Net Demand For Income) and USI:PCC (Put/Call Ratio),
computes percentile ranks over the trailing year, and classifies the
current market environment as risk-on, neutral, or risk-off.

Run:
    uv run python examples/macro_regime_detection.py
"""

import asyncio

from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.utils import convert_timestamp_to_iso

# Lookback window (trading days)
LOOKBACK = 252


def percentile_rank(values: list[float], current: float) -> float:
    """Return the percentile (0–100) of `current` within `values`."""
    if not values:
        return 50.0
    return sum(1 for v in values if v <= current) / len(values) * 100


def ndfi_regime(pct: float) -> str:
    """Classify NDFI percentile into a liquidity regime label."""
    if pct > 75:
        return "DEFENSIVE  (strong demand for income assets)"
    if pct < 25:
        return "RISK-ON    (investors favour risk assets)"
    return "NEUTRAL"


def pcc_sentiment(pct: float) -> str:
    """Classify PCC percentile into a sentiment label."""
    if pct > 80:
        return "EXTREME FEAR     → contrarian bullish"
    if pct < 20:
        return "COMPLACENCY      → contrarian bearish"
    return "NEUTRAL"


def combined_posture(ndfi_pct: float, pcc_pct: float) -> str:
    """Derive an overall risk posture from NDFI and PCC percentiles."""
    score: float = (ndfi_pct + pcc_pct) / 2
    if score > 70:
        return f"RISK-OFF  (score {score:.1f}) — consider reducing equity exposure"
    if score < 30:
        return f"RISK-ON   (score {score:.1f}) — conditions favour equities"
    return f"NEUTRAL   (score {score:.1f}) — maintain current allocation"


def print_bar_history(bars: list[OHLCVBar], symbol: str, n: int = 5) -> None:
    """Print the most recent `n` daily closes for a symbol."""
    print(f"\n  Last {n} {symbol} closes:")
    for bar in bars[-n:]:
        date: str = convert_timestamp_to_iso(bar.timestamp)[:10]
        print(f"    {date}  {bar.close:.6f}")


async def fetch_indicators() -> tuple[list[OHLCVBar], list[OHLCVBar]]:
    """Fetch NDFI and PCC in a single OHLCV context."""
    # NDFI and PCC update once per trading day; use 1D interval.
    # A single context is used here because both fetches are sequential
    # lookups — no concurrency benefit to opening two sockets.
    async with OHLCV() as client:
        ndfi_bars = await client.get_historical_ohlcv(
            exchange_symbol="INDEX:NDFI",
            interval="1D",
            bars_count=LOOKBACK,
        )

    async with OHLCV() as client:
        pcc_bars = await client.get_historical_ohlcv(
            exchange_symbol="USI:PCC",
            interval="1D",
            bars_count=LOOKBACK,
        )

    return ndfi_bars, pcc_bars


async def liquidity_regime(ndfi_bars: list[OHLCVBar]) -> float:
    """Compute and print the NDFI liquidity regime."""
    values: list[float] = [b.close for b in ndfi_bars]
    current: float = ndfi_bars[-1].close
    pct: float = percentile_rank(values, current)

    print("\nNDFI (Net Demand For Income)")
    print(f"  Current value : {current:.6f}")
    print(f"  Percentile    : {pct:.1f}th  (window = {len(values)} bars)")
    print(f"  Regime        : {ndfi_regime(pct)}")
    print_bar_history(ndfi_bars, "NDFI")

    return pct


async def sentiment_analysis(pcc_bars: list[OHLCVBar]) -> float:
    """Compute and print the PCC sentiment reading."""
    values: list[float] = [b.close for b in pcc_bars]
    current: float = pcc_bars[-1].close
    pct: float = percentile_rank(values, current)

    print("\nPCC (Put/Call Ratio)")
    print(f"  Current value : {current:.4f}")
    print(f"  Percentile    : {pct:.1f}th  (window = {len(values)} bars)")
    print(f"  Sentiment     : {pcc_sentiment(pct)}")
    print_bar_history(pcc_bars, "PCC")

    return pct


async def main() -> None:
    print("Fetching macro indicators (this may take a few seconds)...")

    ndfi_bars, pcc_bars = await fetch_indicators()

    if not ndfi_bars:
        print("No NDFI data returned. Check your connection and try again.")
        return
    if not pcc_bars:
        print("No PCC data returned. Check your connection and try again.")
        return

    ndfi_pct = await liquidity_regime(ndfi_bars)
    pcc_pct = await sentiment_analysis(pcc_bars)

    print(f"\n{'=' * 50}")
    print("  Combined Risk Posture")
    print(f"{'=' * 50}")
    print(f"  NDFI percentile : {ndfi_pct:.1f}")
    print(f"  PCC  percentile : {pcc_pct:.1f}")
    print(f"  {combined_posture(ndfi_pct, pcc_pct)}")


if __name__ == "__main__":
    asyncio.run(main())
