#!/usr/bin/env python3
"""
Multi-Market Scanner Example Script

This comprehensive script demonstrates how to use the tvkit scanner service to 
retrieve market data from various global markets using TradingView's scanner API.

What you'll learn:
- Basic market scanning across different countries
- Comprehensive data retrieval with all available columns
- Regional market analysis (Asia Pacific focus)
- Market scanning by ID strings
- Available markets and regional information
- Data visualization and analysis techniques

Prerequisites:
- Internet connection for TradingView API access
- Python 3.13+ with asyncio support
- tvkit library installed

Usage:
    uv run python examples/multi_market_scanner_example.py
"""

import asyncio
import pandas as pd
from typing import Dict, List

# Import tvkit scanner components
from tvkit.api.scanner.services import ScannerService, create_comprehensive_request
from tvkit.api.scanner.models import ColumnSets, create_scanner_request, StockData
from tvkit.api.scanner.markets import (
    Market, 
    MarketRegion, 
    get_markets_by_region, 
    get_all_markets, 
    MARKET_INFO
)


def display_available_regions() -> None:
    """Display available market regions and sample markets."""
    print("🌍 Available Market Regions:")
    print("=" * 50)

    regions = {
        MarketRegion.NORTH_AMERICA: "🇺🇸 North America",
        MarketRegion.EUROPE: "🇪🇺 Europe", 
        MarketRegion.ASIA_PACIFIC: "🌏 Asia Pacific",
        MarketRegion.MIDDLE_EAST_AFRICA: "🕌 Middle East & Africa",
        MarketRegion.MEXICO_SOUTH_AMERICA: "🌎 Mexico & South America",
    }

    for region, region_name in regions.items():
        markets = get_markets_by_region(region)
        print(f"{region_name}: {len(markets)} markets")

        # Show first 3 examples
        for market in markets[:3]:
            info = MARKET_INFO.get(market)
            if info:
                print(f"  • {info.name} ({market.value})")

        if len(markets) > 3:
            print(f"  ... and {len(markets) - 3} more")
        print()


async def basic_market_scan_demo() -> tuple[List[StockData] | None, List[StockData] | None]:
    """Perform a basic scan of multiple markets."""
    print("🌍 Multi-Market Scanner - Basic Example")
    print("=" * 50)

    try:
        # Create scanner service
        service = ScannerService()

        # Create a basic request for top volume stocks
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
        thailand_response = await service.scan_market(Market.THAILAND, request)

        print(f"✅ Found {len(thailand_response.data)} Thai stocks")
        if thailand_response.total_count:
            print(f"Total Thai stocks available: {thailand_response.total_count:,}")

        # Scan USA market for comparison
        print("\n🇺🇸 Scanning USA market...")
        usa_response = await service.scan_market(Market.AMERICA, request)

        print(f"✅ Found {len(usa_response.data)} US stocks")
        if usa_response.total_count:
            print(f"Total US stocks available: {usa_response.total_count:,}")

        # Convert to DataFrames for better display
        def stocks_to_df(stocks: List[StockData], market_name: str) -> pd.DataFrame:
            data = []
            for stock in stocks:
                data.append({
                    'Market': market_name,
                    'Symbol': stock.name,
                    'Price': stock.close if stock.close else 0,
                    'Currency': stock.currency or 'N/A',
                    'Change': stock.change if stock.change else 0,
                    'Volume': stock.volume if stock.volume else 0,
                    'Change %': round(stock.change / stock.close * 100, 2) if stock.change and stock.close else 0
                })
            return pd.DataFrame(data)

        # Create comparison DataFrame
        thailand_df = stocks_to_df(thailand_response.data[:5], "Thailand")
        usa_df = stocks_to_df(usa_response.data[:5], "USA")

        combined_df = pd.concat([thailand_df, usa_df], ignore_index=True)

        print("\n📊 Top 5 Stocks by Volume - Market Comparison:")
        print(combined_df.to_string(index=False))

        return thailand_response.data, usa_response.data

    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None


async def comprehensive_market_scan_demo() -> Dict[str, List[StockData]]:
    """Perform a comprehensive scan with all available data."""
    print("🌏 Multi-Market Scanner - Comprehensive Example")
    print("=" * 60)

    try:
        service = ScannerService()

        # Use the comprehensive request with all available columns
        request = create_comprehensive_request(
            sort_by="market_cap_basic",
            sort_order="desc",
            range_end=5  # Top 5 by market cap
        )

        print(f"Using {len(request.columns)} columns for comprehensive analysis...")
        print(f"Sample columns: {', '.join(request.columns[:10])}...")

        markets_to_scan = [Market.THAILAND, Market.JAPAN, Market.SINGAPORE, Market.KOREA]
        comprehensive_results = {}

        for market in markets_to_scan:
            market_name = market.value.title()
            print(f"\n🔍 Scanning {market_name} market...")

            response = await service.scan_market(market, request)
            comprehensive_results[market_name] = response.data

            print(f"✅ Found {len(response.data)} stocks in {market_name}")

            if response.data:
                stock = response.data[0]  # Top stock by market cap
                print(f"\n📈 Top {market_name} Stock by Market Cap:")
                print(f"   Name: {stock.name}")
                print(f"   Price: {stock.close} {stock.currency}")

                if stock.market_cap_basic:
                    print(f"   Market Cap: ${stock.market_cap_basic:,.0f}")
                else:
                    print("   Market Cap: N/A")

                print(f"   Sector: {stock.sector or 'N/A'}")

                if stock.price_earnings_ttm:
                    print(f"   P/E Ratio: {stock.price_earnings_ttm:.2f}")
                else:
                    print("   P/E Ratio: N/A")

                if stock.dividends_yield_current:
                    print(f"   Dividend Yield: {stock.dividends_yield_current:.2f}%")

                if stock.return_on_equity_fq:
                    print(f"   ROE: {stock.return_on_equity_fq:.2f}%")

        # Create comprehensive comparison DataFrame
        comparison_data = []
        for market_name, stocks in comprehensive_results.items():
            if stocks:
                stock = stocks[0]  # Top stock
                comparison_data.append({
                    'Market': market_name,
                    'Symbol': stock.name,
                    'Price': f"{stock.close:.2f} {stock.currency}" if stock.close else "N/A",
                    'Market Cap (USD)': f"${stock.market_cap_basic:,.0f}" if stock.market_cap_basic else "N/A",
                    'P/E Ratio': f"{stock.price_earnings_ttm:.2f}" if stock.price_earnings_ttm else "N/A",
                    'Sector': stock.sector or "N/A",
                    'Dividend Yield': f"{stock.dividends_yield_current:.2f}%" if stock.dividends_yield_current else "N/A"
                })

        comparison_df = pd.DataFrame(comparison_data)
        print("\n🏆 Market Leaders Comparison:")
        print("=" * 100)
        print(comparison_df.to_string(index=False))

        return comprehensive_results

    except Exception as e:
        print(f"❌ Error: {e}")
        return {}


async def regional_market_scan_demo() -> Dict[str, List[StockData]]:
    """Demonstrate scanning multiple markets by region."""
    print("🌍 Regional Market Scanner - Asia Pacific")
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
            Market.AUSTRALIA,
            Market.INDIA
        ]

        # Create request focused on key metrics
        request = create_scanner_request(
            columns=ColumnSets.BASIC + ["market_cap_basic", "sector", "price_earnings_ttm"],
            sort_by="market_cap_basic",
            sort_order="desc",
            range_end=3,  # Top 3 from each market
        )

        print(f"Scanning {len(selected_markets)} Asia Pacific markets...")
        print("Looking for top 3 stocks by market cap in each market")

        all_results: Dict[str, List[StockData]] = {}

        for market in selected_markets:
            if market in asia_markets:
                market_name = market.value.title()
                print(f"\n📊 Scanning {market_name}...")

                response = await service.scan_market(market, request)
                all_results[market.value] = response.data
                print(f"   Found {len(response.data)} top stocks")

        # Create detailed results DataFrame
        regional_data = []
        for market_id, stocks in all_results.items():
            market_name = market_id.title()
            for i, stock in enumerate(stocks, 1):
                regional_data.append({
                    'Market': market_name,
                    'Rank': i,
                    'Symbol': stock.name,
                    'Price': f"{stock.close:.2f}" if stock.close else "N/A",
                    'Currency': stock.currency or "N/A",
                    'Market Cap': f"{stock.market_cap_basic:,.0f}" if stock.market_cap_basic else "N/A",
                    'P/E': f"{stock.price_earnings_ttm:.2f}" if stock.price_earnings_ttm else "N/A",
                    'Sector': stock.sector or "N/A"
                })

        regional_df = pd.DataFrame(regional_data)

        print("\n🏆 Top Stocks by Market Cap (Asia Pacific):")
        print("=" * 120)

        # Display by market
        for market_name in regional_df['Market'].unique():
            market_stocks = regional_df[regional_df['Market'] == market_name]
            print(f"\n{market_name}:")
            print(market_stocks[['Rank', 'Symbol', 'Price', 'Currency', 'Market Cap', 'Sector']].to_string(index=False))

        return all_results

    except Exception as e:
        print(f"❌ Error: {e}")
        return {}


async def market_by_id_demo() -> List[Dict[str, str]]:
    """Demonstrate using market by ID string."""
    print("🔤 Market Scanner - By ID Example")
    print("=" * 50)

    try:
        service = ScannerService()

        request = create_scanner_request(
            columns=ColumnSets.BASIC + ["market_cap_basic", "sector"],
            sort_by="market_cap_basic",
            sort_order="desc",
            range_end=5
        )

        # Using market ID strings - useful for dynamic market selection
        market_ids = ["thailand", "brazil", "germany", "france", "canada"]

        market_id_results = []

        for market_id in market_ids:
            print(f"\n🌐 Scanning '{market_id}' market...")

            try:
                response = await service.scan_market_by_id(market_id, request)

                print(f"✅ Found {len(response.data)} stocks")

                if response.data:
                    for i, stock in enumerate(response.data[:3], 1):  # Top 3
                        market_id_results.append({
                            'Market': market_id.title(),
                            'Rank': str(i),
                            'Symbol': stock.name,
                            'Price': f"{stock.close:.2f} {stock.currency}" if stock.close else "N/A",
                            'Market Cap': f"{stock.market_cap_basic:,.0f}" if stock.market_cap_basic else "N/A",
                            'Sector': stock.sector or "N/A"
                        })

                    top_stock = response.data[0]
                    print(f"   Top stock: {top_stock.name} - {top_stock.close} {top_stock.currency}")
                    if top_stock.market_cap_basic:
                        print(f"   Market Cap: ${top_stock.market_cap_basic:,.0f}")

            except ValueError as e:
                print(f"   ❌ Invalid market ID: {e}")
            except Exception as e:
                print(f"   ❌ Error scanning {market_id}: {e}")

        # Display results in a nice table
        if market_id_results:
            results_df = pd.DataFrame(market_id_results)
            print("\n📊 Market Leaders by ID:")
            print("=" * 100)
            print(results_df.to_string(index=False))

        return market_id_results

    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def display_available_markets_info() -> pd.DataFrame:
    """Display comprehensive information about available markets."""
    print("🗺️  Available Markets Information")
    print("=" * 50)

    try:
        all_markets = get_all_markets()
        print(f"Total available markets: {len(all_markets)}")

        # Group by region with detailed info
        regions = {
            MarketRegion.NORTH_AMERICA: "🇺🇸 North America",
            MarketRegion.EUROPE: "🇪🇺 Europe",
            MarketRegion.ASIA_PACIFIC: "🌏 Asia Pacific",
            MarketRegion.MIDDLE_EAST_AFRICA: "🕌 Middle East & Africa",
            MarketRegion.MEXICO_SOUTH_AMERICA: "🌎 Mexico & South America",
        }

        market_summary = []

        for region, region_name in regions.items():
            markets = get_markets_by_region(region)
            print(f"\n{region_name}: {len(markets)} markets")

            region_markets = []
            for market in markets:
                info = MARKET_INFO.get(market)
                if info:
                    exchanges = ", ".join(info.exchanges[:2])  # Show first 2 exchanges
                    if len(info.exchanges) > 2:
                        exchanges += f" (+{len(info.exchanges) - 2} more)"

                    region_markets.append({
                        'Region': region_name,
                        'Market': info.name,  
                        'ID': market.value,
                        'Exchanges': exchanges,
                        'Total Exchanges': len(info.exchanges)
                    })

                    print(f"  • {info.name} ({market.value}): {exchanges}")

            market_summary.extend(region_markets[:5])  # Top 5 per region for summary

        # Create summary DataFrame
        summary_df = pd.DataFrame(market_summary)

        print("\n📊 Market Summary (Top 5 per Region):")
        print("=" * 120)
        print(summary_df.to_string(index=False))

        # Regional statistics
        print("\n📈 Regional Statistics:")
        for region, region_name in regions.items():
            markets = get_markets_by_region(region)
            total_exchanges = sum(
                len(MARKET_INFO.get(m, type('obj', (object,), {'exchanges': []})).exchanges) 
                for m in markets
            )
            print(f"  {region_name}: {len(markets)} markets, {total_exchanges} total exchanges")

        return summary_df

    except Exception as e:
        print(f"❌ Error: {e}")
        return pd.DataFrame()


async def run_all_scanner_examples() -> Dict[str, any]:
    """Run all scanner examples in sequence."""
    print("Multi-Market Scanner Examples - Complete Demo")
    print("=" * 60)
    print("This comprehensive demo showcases the tvkit scanner service")
    print("capabilities across global markets using TradingView's API.")
    print()

    # Track all results
    demo_results = {
        'basic_scan': None,
        'comprehensive_scan': None,
        'regional_scan': None,
        'id_scan': None
    }

    try:
        # 1. Basic Market Scan
        print("\n" + "="*60)
        print("1️⃣  BASIC MARKET SCAN")
        print("="*60)
        thailand_data, usa_data = await basic_market_scan_demo()
        demo_results['basic_scan'] = {'thailand': thailand_data, 'usa': usa_data}

        # 2. Comprehensive Market Scan
        print("\n" + "="*60)
        print("2️⃣  COMPREHENSIVE MARKET SCAN")
        print("="*60)
        comprehensive_data = await comprehensive_market_scan_demo()
        demo_results['comprehensive_scan'] = comprehensive_data

        # 3. Regional Market Scan
        print("\n" + "="*60)
        print("3️⃣  REGIONAL MARKET SCAN")
        print("="*60)
        regional_data = await regional_market_scan_demo()
        demo_results['regional_scan'] = regional_data

        # 4. Market by ID Scan
        print("\n" + "="*60)
        print("4️⃣  MARKET BY ID SCAN")
        print("="*60)
        market_id_data = await market_by_id_demo()
        demo_results['id_scan'] = market_id_data

        # 5. Available Markets Info
        print("\n" + "="*60)
        print("5️⃣  AVAILABLE MARKETS INFO")
        print("="*60)
        display_available_markets_info()

        # Final Summary
        print("\n" + "="*60)
        print("🎉 ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("="*60)

        print("\n📊 Demo Summary:")
        basic_count = len(demo_results['basic_scan']['thailand']) if demo_results['basic_scan'] and demo_results['basic_scan']['thailand'] else 0
        comp_count = sum(len(stocks) for stocks in demo_results['comprehensive_scan'].values()) if demo_results['comprehensive_scan'] else 0
        regional_count = sum(len(stocks) for stocks in demo_results['regional_scan'].values()) if demo_results['regional_scan'] else 0
        id_count = len(demo_results['id_scan']) if demo_results['id_scan'] else 0

        print(f"  • Basic scan: {basic_count} Thailand stocks + USA comparison")
        print(f"  • Comprehensive scan: {comp_count} stocks across 4 Asian markets")
        print(f"  • Regional scan: {regional_count} stocks across Asia Pacific")
        print(f"  • ID-based scan: {id_count} results across 5 global markets")
        print(f"  • Market info: {len(Market)} total markets across {len(MarketRegion)} regions")

        print("\n🔗 Key Features Demonstrated:")
        print("  ✅ Multi-market scanning with Market enum")
        print("  ✅ Comprehensive data retrieval (101+ columns)")
        print("  ✅ Regional market analysis and filtering")
        print("  ✅ Dynamic market selection by ID strings")
        print("  ✅ Error handling and retry mechanisms")
        print("  ✅ Data formatting and pandas integration")

        print("\n📝 Notes:")
        print("  • All examples require internet connection")
        print("  • TradingView scanner API access needed")
        print("  • Market data updates in real-time")
        print("  • Service includes automatic retry logic")
        print("  • Supports 101+ financial data columns")

        return demo_results

    except Exception as e:
        print(f"\n❌ Demo Error: {e}")
        print("\n🔧 Troubleshooting Tips:")
        print("  • Check internet connection")
        print("  • Verify TradingView API accessibility")
        print("  • Try reducing request range (range_end parameter)")
        print("  • Check for API rate limiting")
        return demo_results


async def main() -> None:
    """Main function that runs all scanner examples."""
    print("🚀 Multi-Market Scanner Example Script")
    print("=" * 50)
    print(f"📊 Available markets: {len(Market)} markets across {len(MarketRegion)} regions")
    print()

    # Display available regions first
    display_available_regions()

    # Run all examples
    await run_all_scanner_examples()

    print("\n### Service Requirements:")
    print("- **Internet Connection**: Required for TradingView API access")
    print("- **Python 3.13+**: Async/await support needed")
    print("- **Dependencies**: `tvkit`, `pandas`, `httpx`, `websockets`")

    print("\n### Key Features:")
    print("- **101+ Data Columns**: Comprehensive financial metrics")
    print("- **Global Coverage**: 69+ markets across 6 regions")
    print("- **Real-time Data**: Live market information")
    print("- **Type Safety**: Pydantic models with full validation")
    print("- **Error Handling**: Automatic retries with exponential backoff")
    print("- **Flexible Queries**: Sort, filter, and paginate results")

    print("\n### Supported Markets:")
    print("- **North America**: USA, Canada")
    print("- **Europe**: Germany, France, UK, Netherlands, etc.")
    print("- **Asia Pacific**: Thailand, Japan, Singapore, Korea, Australia, India")
    print("- **Middle East & Africa**: UAE, Saudi Arabia, South Africa")
    print("- **Latin America**: Brazil, Mexico, Argentina")

    print("\n### Usage Tips:")
    print("1. Use `Market` enum for type-safe market selection")
    print("2. Start with `ColumnSets.BASIC` for simple queries")
    print("3. Use `create_comprehensive_request()` for full analysis")
    print("4. Implement proper error handling for production use")
    print("5. Consider API rate limits for high-frequency requests")

    print("\n### Next Steps:")
    print("- Explore specific market analysis use cases")
    print("- Integrate with data visualization libraries")
    print("- Build custom screening strategies")
    print("- Export data for further analysis")
    print("- Set up automated market monitoring")


if __name__ == "__main__":
    asyncio.run(main())