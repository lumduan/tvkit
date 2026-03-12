#!/usr/bin/env python3
"""
Historical OHLCV Data — tvkit Example
======================================

Demonstrates fetching historical bar data in both count mode and date-range
mode, concurrent multi-symbol fetching, exporting results to CSV, and
converting UTC timestamps to exchange or local timezones.

What you'll learn:
- Fetching N most-recent bars (count mode)
- Fetching bars within a date range (date-range mode)
- Concurrent multi-symbol fetching with asyncio.gather()
- Exporting results to CSV with DataExporter
- Converting UTC timestamps to exchange local time with tvkit.time

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
from tvkit.time import convert_to_exchange_timezone, convert_to_timezone


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


async def timezone_conversion() -> None:
    """Demonstrate UTC timestamp conversion using tvkit.time.

    All OHLCVBar.timestamp values are UTC epoch floats. Use tvkit.time to
    convert for display or analysis — never for backtesting or ML features.
    """
    print("\n=== Timezone Conversion: UTC epoch → local time ===")

    # --- Traditional exchange: NASDAQ → America/New_York ---
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(
            exchange_symbol="NASDAQ:AAPL",
            interval="60",
            bars_count=5,
        )

    exporter = DataExporter()
    df = await exporter.to_polars(bars)

    print("\nNASDAQ:AAPL — raw UTC epoch timestamps:")
    print(df.select(["timestamp", "close"]).head(3))

    # Convert using exchange code — resolves to America/New_York automatically
    df_ny = convert_to_exchange_timezone(df, "NASDAQ")
    print("\nNASDAQ:AAPL — converted to America/New_York (exchange local time):")
    print(df_ny.select(["timestamp", "close"]).head(3))

    # --- Crypto exchange: BINANCE stays UTC (24/7, no local session) ---
    async with OHLCV() as client:
        btc_bars = await client.get_historical_ohlcv(
            exchange_symbol="BINANCE:BTCUSDT",
            interval="60",
            bars_count=5,
        )

    df_btc = await exporter.to_polars(btc_bars)

    # BINANCE maps to "UTC" — crypto has no exchange-local time concept
    df_btc_utc = convert_to_exchange_timezone(df_btc, "BINANCE")
    print("\nBINANCE:BTCUSDT — UTC (crypto = 24/7, no local session):")
    print(df_btc_utc.select(["timestamp", "close"]).head(3))

    # --- Arbitrary IANA timezone ---
    df_bkk = convert_to_timezone(df_ny, "Asia/Bangkok")
    print("\nNASDAQ:AAPL — converted to Asia/Bangkok (arbitrary IANA tz):")
    print(df_bkk.select(["timestamp", "close"]).head(3))


async def main() -> None:
    try:
        await fetch_count_mode()
        await fetch_date_range_mode()
        await fetch_concurrent()
        await export_to_csv()
        await timezone_conversion()
        print("\nDone.")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
