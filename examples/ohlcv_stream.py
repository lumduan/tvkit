#!/usr/bin/env python3
"""
Real-Time OHLCV Streaming — tvkit Example
==========================================

Demonstrates real-time bar streaming using the OHLCV client, including
a limited-bar stream, multi-symbol trade monitoring, and basic error handling
with retry logic.

What you'll learn:
- Streaming real-time OHLCV bars with get_ohlcv()
- Stopping the stream after N bars
- Monitoring multiple symbols with get_latest_trade_info()
- Handling ConnectionClosed with retry/backoff

Prerequisites:
- Internet connection for TradingView API access
- Python 3.11+ with asyncio support
- tvkit library installed

Usage:
    uv run python examples/ohlcv_stream.py
"""

import asyncio
import traceback
from typing import Any

from websockets.exceptions import ConnectionClosed

from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.utils import convert_timestamp_to_iso


async def stream_limited(symbol: str = "NASDAQ:AAPL", max_bars: int = 5) -> None:
    """Stream real-time bars and stop after receiving max_bars updates."""
    print(f"\n=== Real-Time Stream: {symbol} (first {max_bars} bar updates) ===")
    print(f"{'Date/Time':<22} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>14}")
    print("-" * 80)

    count = 0
    async with OHLCV() as client:
        async for bar in client.get_ohlcv(symbol, interval="1"):
            dt = convert_timestamp_to_iso(bar.timestamp)
            print(
                f"{dt:<22} {bar.open:>10.4f} {bar.high:>10.4f} "
                f"{bar.low:>10.4f} {bar.close:>10.4f} {bar.volume:>14,.0f}"
            )
            count += 1
            if count >= max_bars:
                break

    print(f"Stopped after {count} bar(s).")


async def monitor_quotes(
    symbols: list[str] | None = None,
    duration_seconds: int = 10,
) -> None:
    """Monitor real-time quote updates for multiple symbols."""
    if symbols is None:
        symbols = ["NASDAQ:AAPL", "NASDAQ:MSFT", "BINANCE:BTCUSDT"]

    print(f"\n=== Multi-Symbol Quote Monitor ({duration_seconds}s) ===")
    print(f"Watching: {', '.join(symbols)}")
    print()

    async def _run() -> None:
        async with OHLCV() as client:
            async for msg in client.get_latest_trade_info(exchange_symbol=symbols):
                # Protocol message format: {"m": "qsd", "p": [session, {"n": symbol, "v": {...}}]}
                if msg.get("m") != "qsd":
                    continue
                payload = msg.get("p", [])
                if len(payload) < 2:
                    continue
                data: dict[str, Any] = payload[1]
                sym: str = data.get("n", "?")
                vals: dict[str, Any] = data.get("v", {})
                price: Any = vals.get("lp", "?")
                change_pct: Any = vals.get("chp", 0.0)
                direction = "+" if isinstance(change_pct, int | float) and change_pct >= 0 else ""
                print(f"  {sym:<20} price={price}  change={direction}{change_pct}%")

    try:
        await asyncio.wait_for(_run(), timeout=duration_seconds)
    except TimeoutError:
        print(f"\nStopped after {duration_seconds}s.")


async def stream_with_retry(symbol: str = "NASDAQ:AAPL", max_retries: int = 3) -> None:
    """Stream bars with exponential backoff on connection failure."""
    print(f"\n=== Retry-Enabled Stream: {symbol} ===")
    delay = 1.0

    for attempt in range(1, max_retries + 1):
        try:
            print(f"Attempt {attempt}/{max_retries} ...")
            async with OHLCV() as client:
                bar_count = 0
                async for bar in client.get_ohlcv(symbol, interval="1"):
                    print(f"  Bar: close={bar.close:.4f}")
                    bar_count += 1
                    if bar_count >= 2:
                        break
            print("Stream complete.")
            return
        except ConnectionClosed as e:
            print(f"  Connection closed: {e}")
            if attempt < max_retries:
                print(f"  Retrying in {delay:.0f}s ...")
                await asyncio.sleep(delay)
                delay *= 2
            else:
                print("  Max retries reached.")
                raise


async def main() -> None:
    try:
        await stream_limited(symbol="NASDAQ:AAPL", max_bars=5)
        await monitor_quotes(duration_seconds=10)
        await stream_with_retry(symbol="NASDAQ:AAPL")
        print("\nDone.")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
