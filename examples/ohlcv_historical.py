#!/usr/bin/env python3
"""
Historical OHLCV Data — tvkit Example
======================================

Demonstrates fetching historical bar data in both count mode and date-range
mode, concurrent multi-symbol fetching, and exporting results to CSV.

What you'll learn:
- Fetching N most-recent bars (count mode)
- Fetching bars within a date range (date-range mode)
- Concurrent multi-symbol fetching with asyncio.gather()
- Exporting results to CSV with DataExporter

Prerequisites:
- Internet connection for TradingView API access
- Python 3.11+ with asyncio support
- tvkit library installed

Usage:
    uv run python examples/ohlcv_historical.py
"""

import asyncio
import traceback

from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.utils import convert_timestamp_to_iso
from tvkit.export import DataExporter, ExportFormat


def print_bars(bars: list[OHLCVBar], title: str) -> None:
    """Print a compact table of the last 10 OHLCV bars."""
    print(f"\n{title}")
    print(f"{'Date':<12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>14}")
    print("-" * 70)
    for bar in bars[-10:]:
        dt = convert_timestamp_to_iso(bar.timestamp)[:10]
        print(
            f"{dt:<12} {bar.open:>10.2f} {bar.high:>10.2f} "
            f"{bar.low:>10.2f} {bar.close:>10.2f} {bar.volume:>14,.0f}"
        )
    if len(bars) > 10:
        print(f"  ... ({len(bars) - 10} earlier bars not shown)")


async def fetch_count_mode() -> None:
    """Fetch the 100 most recent daily bars for NASDAQ:AAPL."""
    print("\n=== Count Mode: 100 most recent daily bars ===")
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(
            exchange_symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=100,
        )
    print(f"Received {len(bars)} bars")
    print_bars(bars, "NASDAQ:AAPL — Daily (last 10 shown)")


async def fetch_date_range_mode() -> None:
    """Fetch daily bars for BINANCE:BTCUSDT over a specific date range."""
    print("\n=== Date-Range Mode: BTC/USDT Jan–Mar 2024 ===")
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(
            exchange_symbol="BINANCE:BTCUSDT",
            interval="1D",
            start="2024-01-01",
            end="2024-03-31",
        )
    print(f"Received {len(bars)} bars")
    print_bars(bars, "BINANCE:BTCUSDT — Daily Jan–Mar 2024 (last 10 shown)")


async def fetch_concurrent() -> None:
    """Fetch 30 daily bars for multiple symbols concurrently.

    Each symbol uses its own OHLCV context — the protocol requires
    a separate WebSocket session per chart data series.
    """
    print("\n=== Concurrent Fetch: 3 symbols in parallel ===")
    symbols = ["NASDAQ:AAPL", "NASDAQ:MSFT", "NASDAQ:GOOGL"]

    async def fetch(symbol: str) -> list[OHLCVBar]:
        async with OHLCV() as client:
            return await client.get_historical_ohlcv(
                exchange_symbol=symbol,
                interval="1D",
                bars_count=30,
            )

    results = await asyncio.gather(*(fetch(s) for s in symbols))
    for symbol, bars in zip(symbols, results, strict=False):
        last_close = bars[-1].close if bars else None
        print(f"  {symbol}: {len(bars)} bars, last close = {last_close}")


async def export_to_csv() -> None:
    """Fetch hourly bars and export to CSV."""
    print("\n=== Export: NASDAQ:AAPL daily bars → CSV ===")
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(
            exchange_symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=50,
        )
    exporter = DataExporter()
    result = await exporter.export_ohlcv_data(
        data=bars,
        format=ExportFormat.CSV,
        file_path="export/aapl_daily.csv",
    )
    print(f"Exported {len(bars)} bars → {result.file_path}")


async def main() -> None:
    try:
        await fetch_count_mode()
        await fetch_date_range_mode()
        await fetch_concurrent()
        await export_to_csv()
        print("\nDone.")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
