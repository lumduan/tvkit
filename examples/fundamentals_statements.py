#!/usr/bin/env python3
"""Financial Statements & Revenue Segments — tvkit Example

# [INTEGRATION] — opens a live TradingView WebSocket; skipped by the example validator.

Retrieve revenue segments, the income statement, and a full financials snapshot for a symbol
using ``tvkit.api.fundamentals.FundamentalsClient`` (anonymous — no login required), then export
the tidy/long records to a Polars DataFrame.

What you'll learn:
- Fetch revenue segments (by business and by geography)
- Fetch the income statement with fiscal-period alignment
- Fetch everything at once with ``get_financials()``
- Export fundamentals to Polars / CSV / JSON

Run:
    uv run python examples/fundamentals_statements.py
"""

from __future__ import annotations

import asyncio

from tvkit.api.fundamentals import FundamentalsClient, Period
from tvkit.export import DataExporter, ExportFormat


def _abbrev(value: float | None) -> str:
    """Abbreviate a raw currency value the way the TradingView UI does (K/M/B)."""
    if value is None:
        return "—"
    magnitude = abs(value)
    sign = "-" if value < 0 else ""
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if magnitude >= divisor:
            return f"{sign}{magnitude / divisor:.2f}{suffix}"
    return f"{sign}{magnitude:.2f}"


async def main() -> None:
    symbol = "SET:AOT"  # Airports of Thailand — reports in THB, fiscal year ends September

    async with FundamentalsClient() as fx:
        # 1. Revenue segments (the highest-value dataset).
        segments = await fx.get_segments(symbol)
        print(f"\nRevenue by business — {segments.symbol} ({segments.currency})")
        for period in segments.by_business[:5]:
            cells = ", ".join(f"{s.label}={_abbrev(s.value)}" for s in period.segments)
            print(f"  {period.period.label}: {cells}")

        # 2. Income statement (annual), aligned to fiscal periods.
        income = await fx.get_income_statement(symbol, period=Period.FY, max_periods=5)
        years = [p.label for p in income.periods]
        print(
            f"\nIncome statement — {income.currency}, FY ends "
            f"{income.periods[0].period_end:%B}  columns={years}"
        )
        for field_id in ("total_revenue", "gross_profit", "net_income"):
            line = income.line(field_id)
            if line is not None:
                print(f"  {line.label:16}: {' '.join(_abbrev(v) for v in line.values)}")

        # 3. Everything in one round-trip.
        snapshot = await fx.get_financials(symbol)
        print(
            f"\nSnapshot: income={bool(snapshot.income)} balance={bool(snapshot.balance)} "
            f"cash_flow={bool(snapshot.cash_flow)} statistics={bool(snapshot.statistics)} "
            f"segments={bool(snapshot.segments)} dividends={bool(snapshot.dividends)} "
            f"earnings={bool(snapshot.earnings)}"
        )

        # 4. Export the tidy/long records.
        exporter = DataExporter()
        df = await exporter.export_fundamentals_data(snapshot, ExportFormat.POLARS)
        print(f"\nExported {df.data.height} tidy rows to a Polars DataFrame:")
        print(df.data.head())


if __name__ == "__main__":
    asyncio.run(main())
