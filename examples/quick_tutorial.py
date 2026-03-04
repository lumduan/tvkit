#!/usr/bin/env python3
"""
TVKit Quick Tutorial - Get Started in 5 Minutes
===========================================

This tutorial shows you how to use TVKit for common financial data tasks.
Perfect for Python 3.11+ users who want to get started quickly.

Run this file to see TVKit in action:
    uv run python examples/quick_tutorial.py
"""

import asyncio

from tvkit import (
    MAJOR_CRYPTOS,
    POPULAR_STOCKS,
    compare_stocks,
    get_crypto_prices,
    get_stock_price,
    run_async,
)


def print_section(title: str):
    """Helper to print section headers."""
    print(f"\n{'=' * 50}")
    print(f"🚀 {title}")
    print("=" * 50)


async def tutorial_1_single_stock():
    """Tutorial 1: Get a single stock price."""
    print_section("Tutorial 1: Get Apple Stock Price")

    # Get Apple's current price
    apple_info = await get_stock_price("NASDAQ:AAPL")

    print("📈 Apple Inc. (AAPL)")
    print(f"   Current Price: ${apple_info['price']:.2f}")
    print(f"   Today's Range: ${apple_info['low']:.2f} - ${apple_info['high']:.2f}")
    print(f"   Volume: {apple_info['volume']:,.0f}")
    print(f"   Date: {apple_info['date']}")


async def tutorial_2_compare_stocks():
    """Tutorial 2: Compare multiple stocks."""
    print_section("Tutorial 2: Compare Tech Giants")

    # Compare tech stocks performance over 30 days
    tech_stocks = ["NASDAQ:AAPL", "NASDAQ:GOOGL", "NASDAQ:MSFT", "NASDAQ:TSLA"]
    comparison = await compare_stocks(tech_stocks, days=30)

    print("📊 30-Day Performance Comparison:")
    print(f"{'Stock':<15} {'Price':<10} {'Change':<10} {'Range':<20}")
    print("-" * 60)

    for symbol, metrics in comparison.items():
        if "error" in metrics:
            print(f"{symbol:<15} ❌ Error: {metrics['error']}")
            continue

        stock_name = symbol.split(":")[1]
        price = metrics["current_price"]
        change = metrics["change_percent"]
        range_str = f"${metrics['low']:.2f}-${metrics['high']:.2f}"

        change_icon = "📈" if change > 0 else "📉"
        print(f"{stock_name:<15} ${price:<9.2f} {change_icon}{change:+6.2f}% {range_str:<20}")


async def tutorial_3_crypto_prices():
    """Tutorial 3: Get cryptocurrency prices."""
    print_section("Tutorial 3: Crypto Market Overview")

    # Get current crypto prices
    crypto_prices = await get_crypto_prices(limit=5)

    print("💰 Top Cryptocurrency Prices:")
    print(f"{'Crypto':<10} {'Price':<15}")
    print("-" * 30)

    for crypto, price in crypto_prices.items():
        print(f"{crypto:<10} ${price:>12,.2f}")


async def tutorial_4_predefined_lists():
    """Tutorial 4: Using predefined symbol lists."""
    print_section("Tutorial 4: Quick Market Overview")

    print("📋 Available Pre-defined Lists:")
    print(f"   POPULAR_STOCKS: {len(POPULAR_STOCKS)} stocks")
    print(f"   MAJOR_CRYPTOS: {len(MAJOR_CRYPTOS)} cryptocurrencies")
    print(f"   Examples: {POPULAR_STOCKS[:3]}")

    # Compare top 3 popular stocks
    top_3_comparison = await compare_stocks(POPULAR_STOCKS[:3], days=7)

    print("\n📈 Weekly Performance (Top 3 Stocks):")
    for symbol, metrics in top_3_comparison.items():
        if "error" not in metrics:
            stock_name = symbol.split(":")[1]
            change = metrics["change_percent"]
            icon = "📈" if change > 0 else "📉"
            print(f"   {stock_name}: {icon} {change:+.2f}%")


async def tutorial_5_macro_indicators():
    """Tutorial 5: Macro liquidity and market breadth indicators."""
    from tvkit.api.chart.ohlcv import OHLCV
    from tvkit.api.utils import convert_timestamp_to_iso

    print_section("Tutorial 5: Macro Liquidity Indicators")

    print("🎯 Accessing Macro Indicators for Quantitative Analysis")
    print("These indicators are essential for:")
    print("   • Liquidity regime detection")
    print("   • Market breadth analysis")
    print("   • Systematic trading strategies")
    print("   • Risk management")
    print()

    # Define key macro indicators
    macro_symbols = {
        "INDEX:NDFI": "Net Demand For Income (Market Breadth)",
        "USI:PCC": "Put/Call Ratio (Sentiment & Liquidity)",
    }

    async with OHLCV() as ohlcv:
        for symbol, description in macro_symbols.items():
            try:
                print(f"📊 Fetching {symbol} - {description}")

                # Get recent data for analysis
                data = await ohlcv.get_historical_ohlcv(
                    exchange_symbol=symbol,
                    interval="1D",
                    bars_count=30,  # Last 30 days
                )

                if data:
                    latest = data[-1]
                    earliest = data[0]

                    # Calculate basic statistics
                    values = [bar.close for bar in data]
                    avg_value = sum(values) / len(values)
                    current_value = latest.close

                    # Simple percentile calculation
                    sorted_values = sorted(values)
                    percentile = (
                        sum(1 for v in sorted_values if v <= current_value) / len(sorted_values)
                    ) * 100

                    print(
                        f"   📅 Period: {convert_timestamp_to_iso(earliest.timestamp)[:10]} to {convert_timestamp_to_iso(latest.timestamp)[:10]}"
                    )
                    print(f"   📈 Current Value: {current_value:.6f}")
                    print(f"   📊 30-day Average: {avg_value:.6f}")
                    print(f"   📊 Current Percentile: {percentile:.1f}%")

                    # Basic interpretation
                    if symbol == "INDEX:NDFI":
                        if percentile > 75:
                            signal = "🟢 High income demand - Market strength signal"
                        elif percentile < 25:
                            signal = "🔴 Low income demand - Potential weakness"
                        else:
                            signal = "🟡 Neutral income demand"
                        print(f"   🎯 Signal: {signal}")

                    elif symbol == "USI:PCC":
                        if percentile > 75:
                            signal = "🟠 High fear - Potential contrarian opportunity"
                        elif percentile < 25:
                            signal = "🔵 Low fear - Potential complacency"
                        else:
                            signal = "🟡 Neutral sentiment"
                        print(f"   🎯 Signal: {signal}")

                else:
                    print("   ❌ No data available")

            except Exception as e:
                print(f"   ❌ Error: {e}")

            print()  # Add spacing between indicators

    print("💡 Integration Tips:")
    print("   • Use NDFI for liquidity regime detection")
    print("   • Use PCC for contrarian sentiment signals")
    print("   • Combine both for comprehensive market analysis")
    print("   • Export data for systematic trading models")


def tutorial_6_sync_wrapper():
    """Tutorial 6: Using the sync wrapper for non-async code."""
    print_section("Tutorial 6: Synchronous Wrapper")

    print("🔄 For users not familiar with async/await:")
    print("   Use the run_async() helper function")
    print()

    # Example: Get Bitcoin price without async/await
    bitcoin_info = run_async(get_stock_price("BINANCE:BTCUSDT"))

    print("💰 Bitcoin Price (using sync wrapper):")
    print(f"   Price: ${bitcoin_info['price']:,.2f}")
    print(f"   Volume: {bitcoin_info['volume']:,.0f}")


async def main():
    """Run all tutorials."""
    print("🎓 TVKit Quick Tutorial")
    print("Learn TVKit in 5 minutes with practical examples!")

    try:
        # Run tutorials
        await tutorial_1_single_stock()
        await tutorial_2_compare_stocks()
        await tutorial_3_crypto_prices()
        await tutorial_4_predefined_lists()
        await tutorial_5_macro_indicators()
        tutorial_6_sync_wrapper()

        # Final tips
        print_section("🎉 Congratulations!")
        print("You've completed the TVKit quick tutorial!")
        print()
        print("📚 Next Steps:")
        print("   1. Explore the full documentation")
        print("   2. Try the comprehensive examples:")
        print("      • uv run python examples/historical_and_realtime_data.py")
        print("      • uv run python examples/multi_market_scanner_example.py")
        print("   3. Check out real-time streaming capabilities")
        print("   4. Experiment with data export features")
        print("   5. Explore macro indicators for quantitative analysis")
        print()
        print("🚀 Happy Trading with TVKit!")

    except Exception as e:
        print(f"❌ Tutorial Error: {e}")
        print()
        print("💡 Troubleshooting:")
        print("   • Check your internet connection")
        print("   • Verify TradingView API accessibility")
        print("   • Try running individual functions")


if __name__ == "__main__":
    asyncio.run(main())
