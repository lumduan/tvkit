"""
Thailand Market Scanner Example.

This example demonstrates how to use the Thailand scanner service
to retrieve market data using TradingView's scanner API.
"""

import asyncio

from tvkit.api.scanner.services import ScannerService
from tvkit.api.scanner.services.scanner_service import create_default_thailand_request
from tvkit.api.scanner.models import ColumnSets, create_scanner_request


async def basic_thailand_scan() -> None:
    """Perform a basic scan of the Thailand market."""
    print("🇹🇭 Thailand Market Scanner - Basic Example")
    print("=" * 50)

    try:
        # Create scanner service
        service = ScannerService()

        # Create a basic request
        request = create_scanner_request(
            columns=ColumnSets.BASIC,
            sort_by="volume",
            sort_order="desc",
            range_end=20,  # Get top 20 by volume
        )

        print("Scanning Thailand market for top 20 stocks by volume...")
        print(f"Columns: {', '.join(request.columns)}")

        # Make the request
        response = await service.scan_thailand_market(request)

        print(f"\n✅ Found {len(response.data)} stocks")
        if response.total_count:
            print(f"Total stocks available: {response.total_count}")

        # Display results
        print("\n📊 Top Stocks by Volume:")
        print("-" * 80)
        print(
            f"{'Symbol':<12} {'Price':<10} {'Currency':<8} {'Change':<10} {'Volume':<15}"
        )
        print("-" * 80)

        for stock in response.data[:10]:  # Show top 10
            price: str = f"{stock.close:.2f}" if stock.close else "N/A"
            change: str = f"{stock.change:.2f}" if stock.change else "N/A"
            volume: str = f"{stock.volume:,}" if stock.volume else "N/A"
            currency: str = stock.currency or "N/A"

            print(
                f"{stock.name:<12} {price:<10} {currency:<8} {change:<10} {volume:<15}"
            )

    except Exception as e:
        print(f"❌ Error: {e}")


async def comprehensive_thailand_scan() -> None:
    """Perform a comprehensive scan with all available data."""
    print("\n\n🇹🇭 Thailand Market Scanner - Comprehensive Example")
    print("=" * 60)

    try:
        service = ScannerService()

        # Use the default comprehensive request
        request = create_default_thailand_request()

        # Limit to top 10 for demo
        request.range = (0, 10)
        request.sort.sort_by = "market_cap_basic"
        request.sort.sort_order = "desc"

        print(f"Scanning with {len(request.columns)} columns...")
        print("Getting top 10 stocks by market cap")

        response = await service.scan_thailand_market(request)

        print(f"\n✅ Found {len(response.data)} stocks")

        # Display detailed results
        print("\n📈 Top Stocks by Market Cap (Detailed):")
        print("=" * 100)

        for i, stock in enumerate(response.data, 1):
            print(f"\n{i}. {stock.name}")
            print(f"   Price: {stock.close} {stock.currency}")
            print(
                f"   Market Cap: {stock.market_cap_basic:,}"
                if stock.market_cap_basic
                else "   Market Cap: N/A"
            )
            print(f"   Sector: {stock.sector}")
            print(
                f"   P/E Ratio: {stock.price_earnings_ttm}"
                if stock.price_earnings_ttm
                else "   P/E Ratio: N/A"
            )
            print(
                f"   Dividend Yield: {stock.dividends_yield_current}%"
                if stock.dividends_yield_current
                else "   Dividend Yield: N/A"
            )

    except Exception as e:
        print(f"❌ Error: {e}")


async def filtered_sector_scan() -> None:
    """Demonstrate scanning with specific sector focus."""
    print("\n\n🏭 Thailand Market Scanner - Sector Analysis")
    print("=" * 50)

    try:
        service = ScannerService()

        # Create request focused on financial metrics
        request = create_scanner_request(
            columns=ColumnSets.FUNDAMENTALS
            + ["sector", "market", "volume", "gross_margin_ttm", "return_on_equity_fq"],
            sort_by="return_on_equity_fq",
            sort_order="desc",
            range_end=50,
        )

        print("Analyzing fundamentals across sectors...")

        response = await service.scan_thailand_market(request)

        print(f"\n✅ Found {len(response.data)} stocks")

        # Group by sector
        sectors: dict[str, list] = {}
        for stock in response.data:
            sector = stock.sector or "Unknown"
            if sector not in sectors:
                sectors[sector] = []
            sectors[sector].append(stock)

        print(f"\n📊 Stocks by Sector ({len(sectors)} sectors found):")
        print("-" * 60)

        for sector, stocks in list(sectors.items())[:5]:  # Show top 5 sectors
            print(f"\n{sector}: {len(stocks)} stocks")

            # Show top stock in this sector
            if stocks:
                top_stock = stocks[0]
                print(f"  Top: {top_stock.name}")
                print(f"       Price: {top_stock.close} {top_stock.currency}")
                print(
                    f"       P/E: {top_stock.price_earnings_ttm}"
                    if top_stock.price_earnings_ttm
                    else "       P/E: N/A"
                )

    except Exception as e:
        print(f"❌ Error: {e}")


async def main() -> None:
    """Run all examples."""
    print("Thailand Market Scanner Examples")
    print("=" * 60)
    print("This example demonstrates various ways to use the Thailand")
    print("market scanner service with TradingView's API.")
    print()

    # Run examples
    await basic_thailand_scan()
    await comprehensive_thailand_scan()
    await filtered_sector_scan()

    print("\n" + "=" * 60)
    print("🎉 All examples completed!")
    print("\nNote: This service requires an internet connection")
    print("and access to TradingView's scanner API.")


if __name__ == "__main__":
    asyncio.run(main())
