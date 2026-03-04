#!/usr/bin/env python3
"""
TVKit Command Line Interface

Provides a simple CLI for testing TVKit functionality without writing code.
Perfect for quick testing and verification.

Usage:
    python -m tvkit price NASDAQ:AAPL
    python -m tvkit compare NASDAQ:AAPL NASDAQ:GOOGL NASDAQ:MSFT
    python -m tvkit crypto
    python -m tvkit help
"""

import argparse
import asyncio

from tvkit.helpers import create_user_friendly_error, get_help_message
from tvkit.quickstart import (
    MAJOR_CRYPTOS,
    POPULAR_STOCKS,
    compare_stocks,
    get_crypto_prices,
    get_stock_price,
)


async def cmd_price(symbol: str):
    """Get price for a single symbol."""
    try:
        price_info = await get_stock_price(symbol)
        print(f"📈 {symbol}")
        print(f"   Price: ${price_info['price']:.2f}")
        print(f"   Range: ${price_info['low']:.2f} - ${price_info['high']:.2f}")
        print(f"   Volume: {price_info['volume']:,.0f}")
        print(f"   Date: {price_info['date']}")
    except Exception as e:
        print(f"❌ Error getting price for {symbol}")
        print(f"   {create_user_friendly_error(e)}")
        print("\n💡 Try: python -m tvkit price NASDAQ:AAPL")


async def cmd_compare(symbols: list[str], days: int = 30):
    """Compare multiple symbols."""
    try:
        print(f"📊 Comparing {len(symbols)} symbols over {days} days...")
        comparison = await compare_stocks(symbols, days)

        print(f"\n{'Symbol':<15} {'Price':<10} {'Change':<10} {'Status'}")
        print("-" * 50)

        for symbol, metrics in comparison.items():
            if "error" in metrics:
                print(f"{symbol:<15} {'--':<10} {'--':<10} ❌ Error")
            else:
                price = metrics["current_price"]
                change = metrics["change_percent"]
                status = "📈" if change > 0 else "📉"
                print(f"{symbol:<15} ${price:<9.2f} {change:+6.2f}% {status}")

    except Exception as e:
        print("❌ Error comparing symbols")
        print(f"   {create_user_friendly_error(e)}")


async def cmd_crypto(limit: int = 5):
    """Get cryptocurrency prices."""
    try:
        print(f"💰 Top {limit} Cryptocurrency Prices:")
        crypto_prices = await get_crypto_prices(limit)

        print(f"\n{'Crypto':<10} {'Price':<15}")
        print("-" * 30)

        for crypto, price in crypto_prices.items():
            print(f"{crypto:<10} ${price:>12,.2f}")

    except Exception as e:
        print("❌ Error getting crypto prices")
        print(f"   {create_user_friendly_error(e)}")


def cmd_help():
    """Show help information."""
    print(get_help_message())
    print("\n🔧 CLI Commands:")
    print("   python -m tvkit price SYMBOL        Get price for a symbol")
    print("   python -m tvkit compare SYM1 SYM2   Compare symbols")
    print("   python -m tvkit crypto [limit]      Get crypto prices")
    print("   python -m tvkit examples            Show example commands")
    print("   python -m tvkit help                Show this help")


def cmd_examples():
    """Show example commands."""
    print("🎯 TVKit CLI Examples:\n")

    print("📈 Stock Prices:")
    print("   python -m tvkit price NASDAQ:AAPL")
    print("   python -m tvkit price NYSE:JPM")
    print("   python -m tvkit price BINANCE:BTCUSDT")

    print("\n📊 Stock Comparison:")
    print("   python -m tvkit compare NASDAQ:AAPL NASDAQ:GOOGL")
    print("   python -m tvkit compare NASDAQ:TSLA NYSE:F NYSE:GM")

    print("\n💰 Cryptocurrency:")
    print("   python -m tvkit crypto")
    print("   python -m tvkit crypto 3")

    print("\n🌍 International Stocks:")
    print("   python -m tvkit price TSE:7203        # Toyota (Japan)")
    print("   python -m tvkit price LSE:SHEL        # Shell (London)")
    print("   python -m tvkit price FRA:SAP         # SAP (Frankfurt)")

    print("\n📋 Popular Symbols:")
    print(f"   Stocks: {', '.join(POPULAR_STOCKS[:5])}")
    print(f"   Crypto: {', '.join(MAJOR_CRYPTOS[:3])}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="TVKit CLI - Quick financial data access",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tvkit price NASDAQ:AAPL
  python -m tvkit compare NASDAQ:AAPL NASDAQ:GOOGL NASDAQ:MSFT
  python -m tvkit crypto 5
  python -m tvkit help
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Price command
    price_parser = subparsers.add_parser("price", help="Get price for a symbol")
    price_parser.add_argument("symbol", help="Trading symbol (e.g., NASDAQ:AAPL)")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare multiple symbols")
    compare_parser.add_argument("symbols", nargs="+", help="Symbols to compare")
    compare_parser.add_argument(
        "--days", type=int, default=30, help="Days to compare (default: 30)"
    )

    # Crypto command
    crypto_parser = subparsers.add_parser("crypto", help="Get cryptocurrency prices")
    crypto_parser.add_argument(
        "limit", nargs="?", type=int, default=5, help="Number of cryptos (default: 5)"
    )

    # Help and examples
    subparsers.add_parser("help", help="Show detailed help")
    subparsers.add_parser("examples", help="Show example commands")

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Execute commands
    try:
        if args.command == "price":
            asyncio.run(cmd_price(args.symbol))
        elif args.command == "compare":
            asyncio.run(cmd_compare(args.symbols, args.days))
        elif args.command == "crypto":
            asyncio.run(cmd_crypto(args.limit))
        elif args.command == "help":
            cmd_help()
        elif args.command == "examples":
            cmd_examples()

    except KeyboardInterrupt:
        print("\n👋 Cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("\n💡 Try: python -m tvkit help")


if __name__ == "__main__":
    main()
