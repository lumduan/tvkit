#!/usr/bin/env python3
"""
TVKit Comprehensive Example Script

This script demonstrates the comprehensive capabilities of TVKit:
- OHLCV Data Fetching (Historical and real-time financial data)
- Data Export System (Multiple formats: Polars DataFrame, JSON, CSV)
- Financial Analysis (Technical indicators and data analysis)
- Real-time Streaming (Live market data updates)
- Multi-symbol Operations (Working with multiple financial instruments)

Prerequisites:
    pip install tvkit polars matplotlib seaborn

Usage:
    uv run python examples/historical_and_realtime_data.py
"""

import asyncio
import logging
import warnings
from typing import List, Dict

# TVKit imports
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.export import DataExporter, ExportFormat
from tvkit.api.utils import convert_timestamp_to_iso

# Optional: Data analysis and visualization
try:
    import polars as pl
    import matplotlib.pyplot as plt
    import seaborn as sns

    analysis_available = True
    print("✅ Analysis libraries loaded successfully")
    # Use the imports to avoid F401 warnings
    _ = pl, plt, sns
except ImportError as e:
    analysis_available = False
    print(f"⚠️  Analysis libraries not available: {e}")


def configure_logging() -> None:
    """Configure logging to suppress debug messages for clean output."""
    # Set logging levels to reduce verbosity
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)

    # Optionally suppress warnings
    warnings.filterwarnings("ignore")

    print("🔇 Debug logging disabled - clean output mode enabled")


async def fetch_historical_ohlcv_data() -> List[OHLCVBar]:
    """Fetch historical OHLCV data for Apple stock."""
    async with OHLCV() as ohlcv:
        # Fetch last 100 daily bars for Apple
        ohlcv_data = await ohlcv.get_historical_ohlcv(
            exchange_symbol="NASDAQ:AAPL",
            interval="1D",  # Daily intervals
            bars_count=100,
        )

    # Display basic information
    print(f"📊 Fetched {len(ohlcv_data)} OHLCV bars")
    print(
        f"📅 Date range: {convert_timestamp_to_iso(ohlcv_data[0].timestamp)} to {convert_timestamp_to_iso(ohlcv_data[-1].timestamp)}"
    )

    # Show first few bars
    print("\n🔍 First 3 bars:")
    for i, bar in enumerate(ohlcv_data[:3]):
        print(
            f"  Bar {i + 1}: {convert_timestamp_to_iso(bar.timestamp)[:10]} - Close: ${bar.close:.2f}, Volume: {bar.volume:,.0f}"
        )

    return ohlcv_data


async def demonstrate_data_export(apple_data: List[OHLCVBar]):
    """Demonstrate different data export formats."""
    exporter = DataExporter()

    # 1. Export to Polars DataFrame
    print("📈 Exporting to Polars DataFrame ...")
    df = await exporter.to_polars(apple_data, add_analysis=False)

    print(f"DataFrame shape: {df.shape}")
    print(f"Columns: {df.columns}")
    print("\n📋 First 5 rows:")
    print(df.head())

    # 2. Export to JSON file
    print("\n💾 Exporting to JSON file...")
    json_path = await exporter.to_json(
        apple_data,
        "./export/apple_ohlcv_data.json",
        include_metadata=True,
        indent=2,
    )
    print(f"JSON exported to: {json_path}")

    # 3. Export to CSV file
    print("\n📊 Exporting to CSV file...")
    csv_path = await exporter.to_csv(
        apple_data,
        "./export/apple_ohlcv_data.csv",
        include_metadata=True,
        timestamp_format="iso",
    )
    print(f"CSV exported to: {csv_path}")

    return df


async def compare_multiple_symbols() -> Dict[str, List[OHLCVBar]]:
    """Fetch and compare data for multiple symbols."""
    symbols = [
        "NASDAQ:AAPL",  # Apple
        "NASDAQ:GOOGL",  # Google
        "NASDAQ:MSFT",  # Microsoft
        "NASDAQ:TSLA",  # Tesla
    ]

    symbol_data = {}

    print("🔄 Fetching data for multiple symbols...")

    async with OHLCV() as ohlcv:
        for symbol in symbols:
            try:
                print(f"  📥 Fetching {symbol}...")
                data = await ohlcv.get_historical_ohlcv(
                    exchange_symbol=symbol,
                    interval="1D",
                    bars_count=30,  # Last 30 days
                )
                symbol_data[symbol] = data
                print(f"    ✅ Got {len(data)} bars")
            except Exception as e:
                print(f"    ❌ Failed to fetch {symbol}: {e}")

    # Calculate performance metrics
    print("\n📊 Performance Summary (30-day period):")
    print("-" * 60)

    for symbol, data in symbol_data.items():
        if len(data) >= 2:
            first_close = data[0].close
            last_close = data[-1].close
            change_pct = ((last_close - first_close) / first_close) * 100

            avg_volume = sum(bar.volume for bar in data) / len(data)
            max_high = max(bar.high for bar in data)
            min_low = min(bar.low for bar in data)

            print(
                f"{symbol:12} | Change: {change_pct:+6.2f}% | "
                f"Range: ${min_low:.2f}-${max_high:.2f} | "
                f"Avg Vol: {avg_volume:,.0f}"
            )

    return symbol_data


async def fetch_crypto_and_forex_data() -> Dict[str, Dict[str, List[OHLCVBar]]]:
    """Demonstrate fetching cryptocurrency and forex data."""

    # Different asset classes
    symbols = {
        "Cryptocurrency": [
            "BINANCE:BTCUSDT",  # Bitcoin
            "BINANCE:ETHUSDT",  # Ethereum
            "BINANCE:ADAUSDT",  # Cardano
        ],
        "Forex": [
            "FX_IDC:EURUSD",  # EUR/USD
            "FX_IDC:GBPUSD",  # GBP/USD
            "FX_IDC:USDJPY",  # USD/JPY
        ],
    }

    all_data = {}

    async with OHLCV() as ohlcv:
        for category, symbol_list in symbols.items():
            print(f"\n📊 Fetching {category} Data:")
            print("-" * 40)

            category_data = {}

            for symbol in symbol_list:
                try:
                    print(f"  📥 {symbol}...")
                    data = await ohlcv.get_historical_ohlcv(
                        exchange_symbol=symbol,
                        interval="240",  # 4-hour intervals
                        bars_count=50,
                    )
                    category_data[symbol] = data

                    # Show latest price
                    latest = data[-1]
                    print(
                        f"    ✅ Latest: ${latest.close:.6f} (Vol: {latest.volume:,.0f})"
                    )

                except Exception as e:
                    print(f"    ❌ Failed: {e}")

            all_data[category] = category_data

    # Calculate volatility for each asset
    print("\n📈 Volatility Analysis (4-hour intervals, last 50 bars):")
    print("-" * 60)

    for category, category_data in all_data.items():
        print(f"\n{category}:")
        for symbol, data in category_data.items():
            if len(data) > 1:
                # Calculate price volatility (standard deviation of returns)
                returns = []
                for i in range(1, len(data)):
                    ret = (data[i].close - data[i - 1].close) / data[i - 1].close
                    returns.append(ret)

                if returns:
                    volatility = (
                        sum((r - sum(returns) / len(returns)) ** 2 for r in returns)
                        / len(returns)
                    ) ** 0.5
                    volatility_pct = volatility * 100

                    print(
                        f"  {symbol:20} | Volatility: {volatility_pct:.3f}% | Latest: ${data[-1].close:.6f}"
                    )

    return all_data


async def limited_realtime_demo() -> None:
    """Demonstrate real-time streaming with a time limit."""

    print("🚀 Starting limited real-time data stream (30 seconds)...")
    print("Symbol: BINANCE:BTCUSDT (Bitcoin)")
    print("-" * 50)

    start_time = asyncio.get_event_loop().time()
    timeout_seconds = 30  # Limit to 30 seconds
    bar_count = 0

    try:
        async with OHLCV() as ohlcv:
            async for bar in ohlcv.get_ohlcv("BINANCE:BTCUSDT", interval="1"):
                # Check timeout
                if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                    print(f"\n⏰ Demo timeout reached ({timeout_seconds}s)")
                    break

                bar_count += 1
                timestamp_str = convert_timestamp_to_iso(bar.timestamp)

                print(
                    f"📊 Bar {bar_count}: {timestamp_str} | "
                    f"Close: ${bar.close:,.2f} | "
                    f"Volume: {bar.volume:,.0f}"
                )

                # Also limit by number of bars
                if bar_count >= 10:
                    print(f"\n📈 Received {bar_count} bars, stopping demo")
                    break

    except Exception as e:
        print(f"❌ Streaming error: {e}")

    print(f"\n✅ Real-time demo completed. Received {bar_count} bars.")


async def demonstrate_error_handling(apple_data: List[OHLCVBar]) -> None:
    """Show proper error handling techniques with TVKit."""

    print("🛡️  Error Handling and Best Practices")
    print("=" * 45)

    # 1. Handle invalid symbols gracefully
    print("\n1️⃣  Invalid Symbol Handling:")
    invalid_symbols = ["INVALID:SYMBOL", "BADEXCHANGE:BADSTOCK"]

    async with OHLCV() as ohlcv:
        for symbol in invalid_symbols:
            try:
                print(f"  📥 Attempting to fetch {symbol}...")
                data = await ohlcv.get_historical_ohlcv(
                    exchange_symbol=symbol, interval="1D", bars_count=10
                )
                print(f"    ✅ Success: Got {len(data)} bars")
            except Exception as e:
                print(f"    ❌ Expected error: {type(e).__name__}: {e}")

    # 2. Handle network timeouts and connection issues
    print("\n2️⃣  Connection Resilience:")

    try:
        async with OHLCV() as ohlcv:
            # This should work normally
            data = await ohlcv.get_historical_ohlcv(
                exchange_symbol="NASDAQ:AAPL", interval="1D", bars_count=5
            )
            print(f"    ✅ Successfully fetched {len(data)} bars")
    except Exception as e:
        print(f"    ❌ Connection error: {e}")

    # 3. Export error handling
    print("\n3️⃣  Export Error Handling:")

    try:
        exporter = DataExporter()

        # Try to export to an invalid path
        result = await exporter.export_ohlcv_data(
            apple_data[:5],  # Use small subset
            ExportFormat.JSON,
            file_path="/invalid/path/cannot_write_here.json",
        )

        if result.success:
            print("    ✅ Export successful")
        else:
            print(f"    ❌ Export failed: {result.error_message}")

    except Exception as e:
        print(f"    ❌ Export exception: {type(e).__name__}: {e}")

    # 4. Best practices summary
    print("\n💡 Best Practices Summary:")
    print("   • Always use async context managers (async with)")
    print("   • Handle symbol validation errors gracefully")
    print("   • Set appropriate timeouts for real-time streams")
    print("   • Check export results for success status")
    print("   • Use try-except blocks for robust error handling")
    print("   • Validate data before processing")


async def main() -> None:
    """Main function that runs all examples."""
    print("🚀 TVKit Comprehensive Sample Script")
    print("=" * 50)
    print("This script demonstrates TVKit's comprehensive capabilities:")
    print("- OHLCV Data Fetching")
    print("- Data Export System")
    print("- Financial Analysis")
    print("- Real-time Streaming")
    print("- Multi-symbol Operations")
    print()

    # Configure logging for clean output
    configure_logging()

    try:
        # Basic OHLCV Data Fetching
        print("\n" + "=" * 50)
        print("📊 Basic OHLCV Data Fetching")
        print("=" * 50)
        apple_data = await fetch_historical_ohlcv_data()

        # Data Export to Different Formats
        print("\n" + "=" * 50)
        print("💾 Data Export to Different Formats")
        print("=" * 50)
        await demonstrate_data_export(apple_data)

        # Multi-Symbol Data Comparison
        print("\n" + "=" * 50)
        print("📈 Multi-Symbol Data Comparison")
        print("=" * 50)
        await compare_multiple_symbols()

        # Cryptocurrency and Forex Data
        print("\n" + "=" * 50)
        print("🪙 Cryptocurrency and Forex Data")
        print("=" * 50)
        await fetch_crypto_and_forex_data()

        # Real-time Data Streaming (Limited Demo)
        print("\n" + "=" * 50)
        print("📡 Real-time Data Streaming (Limited Demo)")
        print("=" * 50)
        print("⚠️ Note: Real-time streaming is demonstrated with a limited time window")
        await limited_realtime_demo()

        # Error Handling and Best Practices
        print("\n" + "=" * 50)
        print("🛡️  Error Handling and Best Practices")
        print("=" * 50)
        await demonstrate_error_handling(apple_data)

        # Summary
        print("\n" + "=" * 50)
        print("✅ Summary")
        print("=" * 50)
        print("This script has demonstrated the comprehensive capabilities of TVKit:")
        print()
        print("### ✅ Completed Examples")
        print(
            "- Basic OHLCV Data Fetching - Retrieved historical market data for Apple stock"
        )
        print(
            "- Multi-format Data Export - Exported to Polars DataFrame, JSON, and CSV formats"
        )
        print("- Multi-symbol Operations - Compared performance across multiple stocks")
        print(
            "- Cryptocurrency & Forex - Demonstrated support for various asset classes"
        )
        print("- Real-time Streaming - Limited demo of live data streaming")
        print("- Error Handling - Best practices for robust applications")
        print()
        print("### 🔧 Key Features Highlighted")
        print("- Async Architecture - All operations use modern async/await patterns")
        print("- Type Safety - Comprehensive Pydantic models for data validation")
        print("- Multiple Asset Classes - Stocks, crypto, forex, and more")
        print(
            "- Flexible Export System - Support for Polars, JSON, CSV with custom options"
        )
        print("- Real-time Capabilities - WebSocket streaming for live market data")
        print("- Error Resilience - Robust error handling and validation")
        print()
        print("### 📚 Next Steps")
        print("- Explore the full TVKit documentation")
        print("- Check out additional examples in the examples/ directory")
        print("- Review the API reference for advanced features")
        print("- Consider integrating TVKit into your financial analysis workflows")
        print()
        print("Happy Trading! 📈")

    except Exception as e:
        print(f"❌ Script error: {e}")
        print("\n🔧 Troubleshooting Tips:")
        print("  • Check internet connection")
        print("  • Verify TradingView API accessibility")
        print("  • Ensure all dependencies are installed")
        print("  • Check for API rate limiting")


if __name__ == "__main__":
    asyncio.run(main())
