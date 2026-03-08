#!/usr/bin/env python3
"""
Large-Cap US Equities Scanner — tvkit Example

Demonstrates scanning the US market for large-cap stocks using
fundamental and technical filters, then exporting results to CSV.

Run:
    uv run python examples/scanner_sp500.py
"""

import asyncio

from tvkit.api.scanner.markets import Market
from tvkit.api.scanner.models import ColumnSets, StockData, create_scanner_request
from tvkit.api.scanner.services import ScannerService
from tvkit.api.scanner.services.scanner_service import (
    ScannerAPIError,
    ScannerConnectionError,
)
from tvkit.export import DataExporter, ExportFormat


def format_market_cap(value: int | None) -> str:
    """Format market cap in billions."""
    if value is None:
        return "N/A"
    billions: float = value / 1_000_000_000
    return f"${billions:.1f}B"


def format_pe(value: float | None) -> str:
    """Format P/E ratio."""
    if value is None:
        return "N/A"
    return f"{value:.1f}x"


def format_change(value: float | None) -> str:
    """Format price change percentage."""
    if value is None:
        return "N/A"
    sign: str = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def print_results_table(stocks: list[StockData], title: str) -> None:
    """Print a formatted table of scanner results."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")
    print(f"{'Symbol':<12} {'Price':>8} {'Chg%':>8} {'Mkt Cap':>12} {'P/E':>8} {'Sector':<20}")
    print("-" * 70)
    for stock in stocks:
        price: str = f"${stock.close:.2f}" if stock.close is not None else "N/A"
        sector: str = (stock.sector or "")[:19]
        print(
            f"{stock.name:<12} {price:>8} {format_change(stock.change):>8} "
            f"{format_market_cap(stock.market_cap_basic):>12} "
            f"{format_pe(stock.price_earnings_ttm):>8} {sector:<20}"
        )
    print(f"\n  Total: {len(stocks)} stocks")


async def scan_large_caps() -> list[StockData]:
    """Scan the US market for large-cap stocks, sorted by market cap."""
    print("Scanning US market for large-cap stocks...")

    request = create_scanner_request(
        columns=ColumnSets.FUNDAMENTALS,
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=50,
    )

    service = ScannerService()
    response = await service.scan_market(market=Market.AMERICA, request=request)

    # Keep only stocks with a market cap above $10B
    large_caps: list[StockData] = [
        s
        for s in response.data
        if s.market_cap_basic is not None and s.market_cap_basic >= 10_000_000_000
    ]
    return large_caps


async def scan_by_sector() -> None:
    """Print a breakdown of large-cap counts by sector."""
    stocks = await scan_large_caps()

    sector_counts: dict[str, int] = {}
    for stock in stocks:
        key: str = stock.sector or "Unknown"
        sector_counts[key] = sector_counts.get(key, 0) + 1

    print("\n--- Large-Cap Stocks by Sector ---")
    for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {sector:<30} {count:>3} stocks")


async def scan_value_stocks() -> None:
    """Find large-cap stocks with low P/E ratios (potential value plays)."""
    print("\nLooking for large-cap value stocks (low P/E)...")

    # Sort by market cap to get large-caps first, then filter by P/E
    request = create_scanner_request(
        columns=ColumnSets.VALUATION,
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=200,
    )

    service = ScannerService()
    response = await service.scan_market(market=Market.AMERICA, request=request)

    # Filter: has a positive P/E below 20 and market cap above $10B
    value_stocks: list[StockData] = [
        s
        for s in response.data
        if s.price_earnings_ttm is not None
        and 0 < s.price_earnings_ttm < 20
        and s.market_cap_basic is not None
        and s.market_cap_basic >= 10_000_000_000
    ]

    print_results_table(value_stocks[:20], "Large-Cap Value Stocks (P/E < 20)")


async def scan_top_performers() -> None:
    """Find large-cap stocks with the best year-to-date performance."""
    print("\nScanning for top YTD performers...")

    columns: list[str] = [
        "name",
        "close",
        "currency",
        "change",
        "market_cap_basic",
        "sector",
        "Perf.YTD",
        "Perf.1M",
        "Perf.3M",
    ]

    # Fetch large-caps first, then sort the results by Perf.YTD in Python
    request = create_scanner_request(
        columns=columns,
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=200,
    )

    service = ScannerService()
    response = await service.scan_market(market=Market.AMERICA, request=request)

    # Keep large-caps with YTD data, sort by Perf.YTD descending
    large_caps_with_perf: list[StockData] = [
        s
        for s in response.data
        if s.market_cap_basic is not None and s.market_cap_basic >= 10_000_000_000
    ]

    print_results_table(large_caps_with_perf[:20], "Top YTD Performers (Large-Cap)")


async def export_large_caps_to_csv() -> None:
    """Scan large-cap stocks and export results to CSV."""
    print("\nFetching large-cap data for CSV export...")

    request = create_scanner_request(
        columns=ColumnSets.COMPREHENSIVE,
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=100,
    )

    service = ScannerService()
    response = await service.scan_market(market=Market.AMERICA, request=request)

    large_caps: list[StockData] = [
        s
        for s in response.data
        if s.market_cap_basic is not None and s.market_cap_basic >= 5_000_000_000
    ]

    if not large_caps:
        print("No results to export.")
        return

    exporter = DataExporter()
    result = await exporter.export_scanner_data(
        data=large_caps,
        format=ExportFormat.CSV,
        file_path="export/large_cap_us_stocks.csv",
    )
    print(f"Exported {len(large_caps)} stocks to {result.file_path}")


async def main() -> None:
    try:
        stocks = await scan_large_caps()
        print_results_table(stocks[:20], "Top 20 US Large-Cap Stocks by Market Cap")

        await scan_by_sector()
        await scan_value_stocks()
        await scan_top_performers()
        await export_large_caps_to_csv()

    except ScannerConnectionError as exc:
        print(f"Connection error: {exc}")
    except ScannerAPIError as exc:
        print(f"API error: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
