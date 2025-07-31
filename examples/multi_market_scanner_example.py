"""
Multi-Market Scanner Example.

This example demonstrates how to use the scanner service
to retrieve market data from various global markets using TradingView's scanner API.
Includes specific examples for Thailand, USA, and other markets.
"""

import asyncio

from tvkit.api.scanner.services import ScannerService, create_comprehensive_request
from tvkit.api.scanner.models import ColumnSets, create_scanner_request, StockData
from tvkit.api.scanner.markets import Market, MarketRegion, get_markets_by_region


async def basic_market_scan() -> None:
    """Perform a basic scan of multiple markets."""
    print("🌍 Multi-Market Scanner - Basic Example")
    print("=" * 50)

    try:
        # Create scanner service
        service = ScannerService()

        # Create a basic request
        request = create_scanner_request(
            columns=ColumnSets.BASIC,
            sort_by="volume",
            sort_order="desc",
            range_end=10,  # Get top 10 by volume
        )

        print("Scanning markets for top 10 stocks by volume...")
        print(f"Columns: {', '.join(request.columns)}")

        # Scan Thailand market
        print("\n🇹🇭 Scanning Thailand market...")
        response = await service.scan_market(Market.THAILAND, request)

        print(f"✅ Found {len(response.data)} Thai stocks")
        if response.total_count:
            print(f"Total Thai stocks available: {response.total_count}")

        # Also scan USA market for comparison
        print("\n🇺🇸 Scanning USA market...")
        usa_response = await service.scan_market(Market.AMERICA, request)

        print(f"✅ Found {len(usa_response.data)} US stocks")
        if usa_response.total_count:
            print(f"Total US stocks available: {usa_response.total_count}")

        # Display Thailand results
        print("\n📊 Top Thai Stocks by Volume:")
        print("-" * 80)
        print(
            f"{'Symbol':<12} {'Price':<10} {'Currency':<8} {'Change':<10} {'Volume':<15}"
        )
        print("-" * 80)

        for stock in response.data[:5]:  # Show top 5
            price_thai: str = f"{stock.close:.2f}" if stock.close else "N/A"
            change_thai: str = f"{stock.change:.2f}" if stock.change else "N/A"
            volume_thai: str = f"{stock.volume:,}" if stock.volume else "N/A"
            currency_thai: str = stock.currency or "N/A"

            print(
                f"{stock.name:<12} {price_thai:<10} {currency_thai:<8} {change_thai:<10} {volume_thai:<15}"
            )

        # Display USA results
        print("\n📊 Top US Stocks by Volume:")
        print("-" * 80)
        print(
            f"{'Symbol':<12} {'Price':<10} {'Currency':<8} {'Change':<10} {'Volume':<15}"
        )
        print("-" * 80)

        for stock in usa_response.data[:5]:  # Show top 5
            price_usa: str = f"{stock.close:.2f}" if stock.close else "N/A"
            change_usa: str = f"{stock.change:.2f}" if stock.change else "N/A"
            volume_usa: str = f"{stock.volume:,}" if stock.volume else "N/A"
            currency_usa: str = stock.currency or "N/A"

            print(
                f"{stock.name:<12} {price_usa:<10} {currency_usa:<8} {change_usa:<10} {volume_usa:<15}"
            )

    except Exception as e:
        print(f"❌ Error: {e}")


async def comprehensive_market_scan() -> None:
    """Perform a comprehensive scan with all available data."""
    print("\n\n🌏 Multi-Market Scanner - Comprehensive Example")
    print("=" * 60)

    try:
        service = ScannerService()

        # Use the comprehensive request
        request = create_comprehensive_request(
            sort_by="market_cap_basic", sort_order="desc", range_end=10
        )

        print(f"Using {len(request.columns)} columns for comprehensive analysis...")

        markets_to_scan = [Market.THAILAND, Market.JAPAN, Market.SINGAPORE]

        for market in markets_to_scan:
            market_name = market.value.title()
            print(f"\n🔍 Scanning {market_name} market...")

            response = await service.scan_market(market, request)

            print(f"✅ Found {len(response.data)} stocks in {market_name}")

            if response.data:
                print(f"\n📈 Top {market_name} Stock by Market Cap:")
                stock = response.data[0]
                print(f"   Name: {stock.name}")
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

    except Exception as e:
        print(f"❌ Error: {e}")


async def regional_market_scan() -> None:
    """Demonstrate scanning multiple markets by region."""
    print("\n\n🌍 Regional Market Scanner - Asia Pacific")
    print("=" * 50)

    try:
        service = ScannerService()

        # Get Asia Pacific markets
        asia_markets = get_markets_by_region(MarketRegion.ASIA_PACIFIC)
        selected_markets = [
            Market.THAILAND,
            Market.SINGAPORE,
            Market.JAPAN,
            Market.KOREA,
        ]

        # Create request focused on basic metrics
        request = create_scanner_request(
            columns=ColumnSets.BASIC + ["market_cap_basic", "sector"],
            sort_by="market_cap_basic",
            sort_order="desc",
            range_end=5,  # Top 5 from each market
        )

        print(f"Scanning {len(selected_markets)} Asia Pacific markets...")

        all_results: dict[str, list[StockData]] = {}

        for market in selected_markets:
            if market in asia_markets:
                print(f"\n📊 Scanning {market.value.title()}...")
                response = await service.scan_market(market, request)
                all_results[market.value] = response.data
                print(f"   Found {len(response.data)} top stocks")

        # Display results by market
        print("\n🏆 Top Stocks by Market Cap (Asia Pacific):")
        print("=" * 70)

        for market_id, stocks in all_results.items():
            market_name = market_id.title()
            print(f"\n{market_name}:")
            print("-" * 30)

            for i, stock in enumerate(stocks[:3], 1):  # Top 3 per market
                market_cap = (
                    f"{stock.market_cap_basic:,}" if stock.market_cap_basic else "N/A"
                )
                print(
                    f"  {i}. {stock.name} - {stock.close} {stock.currency} (Cap: {market_cap})"
                )

    except Exception as e:
        print(f"❌ Error: {e}")


async def market_by_id_example() -> None:
    """Demonstrate using market by ID string."""
    print("\n\n🔤 Market Scanner - By ID Example")
    print("=" * 50)

    try:
        service = ScannerService()

        request = create_scanner_request(columns=ColumnSets.BASIC, range_end=3)

        # Using market ID strings
        market_ids = ["thailand", "brazil", "germany"]

        for market_id in market_ids:
            print(f"\n🌐 Scanning '{market_id}' market...")
            response = await service.scan_market_by_id(market_id, request)

            print(f"✅ Found {len(response.data)} stocks")
            if response.data:
                top_stock = response.data[0]
                print(
                    f"   Top stock: {top_stock.name} - {top_stock.close} {top_stock.currency}"
                )

    except Exception as e:
        print(f"❌ Error: {e}")


async def available_markets_info() -> None:
    """Display information about available markets."""
    print("\n\n🗺️  Available Markets Information")
    print("=" * 50)

    try:
        from tvkit.api.scanner.markets import get_all_markets, MARKET_INFO

        all_markets = get_all_markets()
        print(f"Total available markets: {len(all_markets)}")

        # Group by region
        regions = {
            MarketRegion.NORTH_AMERICA: "🇺🇸 North America",
            MarketRegion.EUROPE: "🇪🇺 Europe",
            MarketRegion.ASIA_PACIFIC: "🌏 Asia Pacific",
            MarketRegion.MIDDLE_EAST_AFRICA: "🕌 Middle East & Africa",
            MarketRegion.MEXICO_SOUTH_AMERICA: "🌎 Mexico & South America",
        }

        for region, region_name in regions.items():
            markets = get_markets_by_region(region)
            print(f"\n{region_name}: {len(markets)} markets")

            # Show a few examples
            example_markets = markets[:5]  # First 5
            for market in example_markets:
                info = MARKET_INFO.get(market)
                if info:
                    exchanges = ", ".join(info.exchanges[:2])  # Show first 2 exchanges
                    if len(info.exchanges) > 2:
                        exchanges += f" (+{len(info.exchanges) - 2} more)"
                    print(f"  • {info.name} ({market.value}): {exchanges}")

            if len(markets) > 5:
                print(f"  ... and {len(markets) - 5} more")

    except Exception as e:
        print(f"❌ Error: {e}")


async def main() -> None:
    """Run all examples."""
    print("Multi-Market Scanner Examples")
    print("=" * 60)
    print("This example demonstrates various ways to use the market")
    print("scanner service with TradingView's API across different global markets.")
    print()

    # Run examples
    await basic_market_scan()
    await comprehensive_market_scan()
    await regional_market_scan()
    await market_by_id_example()
    await available_markets_info()

    print("\n" + "=" * 60)
    print("🎉 All examples completed!")
    print("\nNote: This service requires an internet connection")
    print("and access to TradingView's scanner API.")
    print(
        f"\nSupported markets: {len(Market)} markets across {len(MarketRegion)} regions"
    )
    print("Use Market enum for type-safe market selection.")


if __name__ == "__main__":
    asyncio.run(main())
