"""
Quick Start utilities for TVKit users.

This module provides simple functions to get started with TVKit quickly,
especially for Python 3.11+ users who want immediate results.
"""

import asyncio
from typing import Any, Coroutine, Dict, List

from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.utils import convert_timestamp_to_iso
from tvkit.export import DataExporter


async def get_stock_price(symbol: str) -> Dict[str, Any]:
    """
    Get the latest stock price for a symbol.

    Args:
        symbol: Trading symbol (e.g., "NASDAQ:AAPL", "BINANCE:BTCUSDT")

    Returns:
        Dictionary with latest price information

    Example:
        >>> import asyncio
        >>> from tvkit.quickstart import get_stock_price
        >>> price_info = asyncio.run(get_stock_price("NASDAQ:AAPL"))
        >>> print(f"Apple: ${price_info['price']}")
    """
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(symbol, "1D", 1)
        if not bars:
            raise ValueError(f"No data found for symbol: {symbol}")

        latest = bars[0]
        return {
            "symbol": symbol,
            "price": latest.close,
            "open": latest.open,
            "high": latest.high,
            "low": latest.low,
            "volume": latest.volume,
            "timestamp": convert_timestamp_to_iso(latest.timestamp),
            "date": convert_timestamp_to_iso(latest.timestamp)[:10],
        }


async def compare_stocks(
    symbols: List[str], days: int = 30
) -> Dict[str, Dict[str, Any]]:
    """
    Compare performance of multiple stocks over a period.

    Args:
        symbols: List of trading symbols
        days: Number of days to analyze (default: 30)

    Returns:
        Dictionary with performance metrics for each symbol

    Example:
        >>> symbols = ["NASDAQ:AAPL", "NASDAQ:GOOGL", "NASDAQ:MSFT"]
        >>> comparison = asyncio.run(compare_stocks(symbols, 30))
        >>> for symbol, metrics in comparison.items():
        ...     print(f"{symbol}: {metrics['change_percent']:.2f}%")
    """
    results: dict[str, dict[str, Any]] = {}

    async with OHLCV() as client:
        for symbol in symbols:
            try:
                bars = await client.get_historical_ohlcv(symbol, "1D", days)
                if len(bars) < 2:
                    continue

                first_price = bars[0].close
                last_price = bars[-1].close
                change_percent = ((last_price - first_price) / first_price) * 100

                avg_volume = sum(bar.volume for bar in bars) / len(bars)
                high_price = max(bar.high for bar in bars)
                low_price = min(bar.low for bar in bars)

                results[symbol] = {
                    "current_price": last_price,
                    "change_percent": change_percent,
                    "change_absolute": last_price - first_price,
                    "high": high_price,
                    "low": low_price,
                    "average_volume": avg_volume,
                    "period_days": len(bars),
                }
            except Exception as e:
                results[symbol] = {"error": str(e)}

    return results


async def get_crypto_prices(limit: int = 5) -> Dict[str, float]:
    """
    Get current prices for major cryptocurrencies.

    Args:
        limit: Number of cryptos to fetch (default: 5)

    Returns:
        Dictionary mapping crypto symbols to prices

    Example:
        >>> crypto_prices = asyncio.run(get_crypto_prices(3))
        >>> for crypto, price in crypto_prices.items():
        ...     print(f"{crypto}: ${price:,.2f}")
    """
    crypto_symbols = [
        "BINANCE:BTCUSDT",  # Bitcoin
        "BINANCE:ETHUSDT",  # Ethereum
        "BINANCE:ADAUSDT",  # Cardano
        "BINANCE:SOLUSDT",  # Solana
        "BINANCE:DOTUSDT",  # Polkadot
        "BINANCE:LINKUSDT",  # Chainlink
        "BINANCE:LTCUSDT",  # Litecoin
        "BINANCE:XRPUSDT",  # Ripple
    ]

    prices: dict[str, float] = {}
    async with OHLCV() as client:
        for symbol in crypto_symbols[:limit]:
            try:
                bars = await client.get_historical_ohlcv(symbol, "1D", 1)
                if bars:
                    crypto_name = symbol.split(":")[1].replace("USDT", "")
                    price = bars[0].close
                    prices[crypto_name] = float(price)
            except Exception:
                continue

    return prices


def quick_export_to_csv(bars: List[OHLCVBar], filename: str = "stock_data.csv") -> str:
    """
    Synchronous wrapper for exporting data to CSV.

    Args:
        bars: List of OHLCV bars
        filename: Output filename

    Returns:
        Path to the exported file

    Example:
        >>> bars = asyncio.run(get_historical_data("NASDAQ:AAPL", 10))
        >>> csv_path = quick_export_to_csv(bars, "apple_data.csv")
        >>> print(f"Data exported to: {csv_path}")
    """

    async def _export():
        exporter = DataExporter()
        return await exporter.to_csv(bars, f"./export/{filename}")

    result = asyncio.run(_export())
    return str(result)


async def get_historical_data(symbol: str, days: int) -> List[OHLCVBar]:
    """
    Simple function to get historical data.

    Args:
        symbol: Trading symbol
        days: Number of days of data

    Returns:
        List of OHLCV bars

    Example:
        >>> data = asyncio.run(get_historical_data("NASDAQ:AAPL", 30))
        >>> print(f"Got {len(data)} days of Apple data")
    """
    async with OHLCV() as client:
        return await client.get_historical_ohlcv(symbol, "1D", days)


# Convenience functions for common use cases
def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Helper to run async functions for users not familiar with asyncio.

    Args:
        coro: Coroutine to run

    Returns:
        Result of the coroutine

    Example:
        >>> from tvkit.quickstart import get_stock_price, run_async
        >>> price_info = run_async(get_stock_price("NASDAQ:AAPL"))
        >>> print(price_info)
    """
    return asyncio.run(coro)


# Pre-defined symbol lists for easy access
POPULAR_STOCKS = [
    "NASDAQ:AAPL",  # Apple
    "NASDAQ:GOOGL",  # Google
    "NASDAQ:MSFT",  # Microsoft
    "NASDAQ:AMZN",  # Amazon
    "NASDAQ:TSLA",  # Tesla
    "NASDAQ:NVDA",  # NVIDIA
    "NASDAQ:META",  # Meta
    "NYSE:JPM",  # JPMorgan
    "NYSE:JNJ",  # Johnson & Johnson
    "NYSE:V",  # Visa
]

MAJOR_CRYPTOS = [
    "BINANCE:BTCUSDT",  # Bitcoin
    "BINANCE:ETHUSDT",  # Ethereum
    "BINANCE:ADAUSDT",  # Cardano
    "BINANCE:SOLUSDT",  # Solana
    "BINANCE:DOTUSDT",  # Polkadot
]

FOREX_PAIRS = [
    "FX_IDC:EURUSD",  # EUR/USD
    "FX_IDC:GBPUSD",  # GBP/USD
    "FX_IDC:USDJPY",  # USD/JPY
    "FX_IDC:USDCHF",  # USD/CHF
    "FX_IDC:AUDUSD",  # AUD/USD
]
