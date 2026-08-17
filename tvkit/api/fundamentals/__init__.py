"""TradingView financial statements and revenue segments over the WebSocket quote protocol.

``FundamentalsClient`` retrieves income statement, balance sheet, cash-flow statement,
statistics, dividends, earnings, and revenue segments for a symbol — anonymous by default.

Example::

    import asyncio
    from tvkit.api.fundamentals import FundamentalsClient, Period

    async def main() -> None:
        async with FundamentalsClient() as fx:
            segments = await fx.get_segments("SET:AOT")
            income = await fx.get_income_statement("NASDAQ:AAPL", period=Period.FY)
            print(segments.by_business[0].period.label, income.currency)

    asyncio.run(main())
"""

from __future__ import annotations

from tvkit.api.fundamentals.client import FundamentalsClient
from tvkit.api.fundamentals.exceptions import (
    FundamentalsAuthError,
    FundamentalsConnectionError,
    FundamentalsError,
    FundamentalsTimeoutError,
    NoFundamentalDataError,
)
from tvkit.api.fundamentals.models import (
    DividendEvent,
    DividendReport,
    EarningsPeriod,
    EarningsReport,
    FinancialStatement,
    FiscalPeriod,
    FundamentalsSnapshot,
    Period,
    RevenueSegment,
    SegmentPeriod,
    SegmentReport,
    StatementLine,
    StatementType,
)

__all__ = [
    "FundamentalsClient",
    "Period",
    "StatementType",
    "FiscalPeriod",
    "StatementLine",
    "FinancialStatement",
    "RevenueSegment",
    "SegmentPeriod",
    "SegmentReport",
    "DividendEvent",
    "DividendReport",
    "EarningsPeriod",
    "EarningsReport",
    "FundamentalsSnapshot",
    "FundamentalsError",
    "FundamentalsAuthError",
    "FundamentalsConnectionError",
    "FundamentalsTimeoutError",
    "NoFundamentalDataError",
]
