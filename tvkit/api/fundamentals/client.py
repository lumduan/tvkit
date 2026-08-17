"""Async client for TradingView financial statements and revenue segments.

``FundamentalsClient`` opens one WebSocket for the lifetime of its ``async with`` block and runs
a one-shot quote snapshot per ``get_*`` call. Anonymous by default; pass
:class:`tvkit.auth.TradingViewCredentials` for an authenticated session.

Example::

    from tvkit.api.fundamentals import FundamentalsClient, Period

    async with FundamentalsClient() as fx:
        segments = await fx.get_segments("SET:AOT")
        income = await fx.get_income_statement("SET:AOT", period=Period.FY)
        snapshot = await fx.get_financials("NASDAQ:AAPL")
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

from tvkit.api.fundamentals import catalog, models
from tvkit.api.fundamentals.exceptions import FundamentalsError, NoFundamentalDataError
from tvkit.api.fundamentals.models import (
    DividendReport,
    EarningsReport,
    FinancialStatement,
    FundamentalsSnapshot,
    Period,
    SegmentReport,
    StatementType,
)
from tvkit.api.fundamentals.transport import STANDARD_WS_URL, QuoteSnapshotTransport
from tvkit.auth import AuthManager, TradingViewCredentials
from tvkit.symbols import normalize_symbol

__all__ = ["FundamentalsClient"]


class FundamentalsClient:
    """Async context-managed client for per-symbol fundamentals over the TradingView WebSocket.

    Args:
        credentials: Authentication credentials. Defaults to anonymous, which is sufficient for
            fundamentals (see ``findings.md`` §6).
        language: Locale for ``set_locale`` — controls segment-label localization (default 'en').
        timeout: Seconds to wait for a snapshot to complete.
        ws_url: Override the WebSocket endpoint (advanced/testing).
    """

    def __init__(
        self,
        credentials: TradingViewCredentials | None = None,
        language: str = "en",
        timeout: float = 30.0,
        ws_url: str = STANDARD_WS_URL,
    ) -> None:
        self._credentials = credentials
        self._language = language
        self._timeout = timeout
        self._ws_url = ws_url
        self._auth: AuthManager | None = None

    # -- lifecycle ---------------------------------------------------------

    async def __aenter__(self) -> FundamentalsClient:
        # Authenticate once; the WebSocket itself is opened fresh per call, because the
        # TradingView server closes a quote-only socket after delivering one snapshot.
        self._auth = AuthManager(self._credentials)
        await self._auth.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._auth is not None:
            await self._auth.__aexit__(exc_type, exc_val, exc_tb)
            self._auth = None

    def _make_transport(self, auth_token: str) -> QuoteSnapshotTransport:
        """Build a transport. Overridable seam for tests (inject a fake)."""
        return QuoteSnapshotTransport(
            auth_token=auth_token,
            language=self._language,
            ws_url=self._ws_url,
            timeout=self._timeout,
        )

    async def _fetch(self, symbol: str, fields: list[str]) -> tuple[str, dict[str, Any]]:
        """Normalize the symbol, run one snapshot on a fresh socket, return (symbol, values)."""
        if self._auth is None:
            raise FundamentalsError(
                "FundamentalsClient is not open — use 'async with FundamentalsClient() as fx'."
            )
        canonical = normalize_symbol(symbol)
        transport = self._make_transport(self._auth.auth_token)
        await transport.connect()
        try:
            result = await transport.snapshot([canonical], fields)
        finally:
            await transport.close()
        values = result.get(canonical, {})
        if not values:
            raise NoFundamentalDataError(f"No fundamental data returned for {canonical!r}.")
        return canonical, values

    # -- field-set builders ------------------------------------------------

    @staticmethod
    def _statement_fields(statement: StatementType, period: Period) -> list[str]:
        suffix = catalog.PERIOD_SUFFIX[period.value]
        bases = catalog.STATEMENT_REQUEST_FIELDS.get(statement.value, [])
        if period is Period.TTM:
            value_fields = [f"{b}_ttm" for b in bases]
        else:
            value_fields = [f"{b}_{suffix}_h" for b in bases]
        return [*value_fields, *catalog.PERIOD_FIELDS[period.value], *catalog.META_FIELDS]

    # -- public API --------------------------------------------------------

    async def get_segments(self, symbol: str) -> SegmentReport:
        """Return revenue broken down by business source and by geography (annual)."""
        fields = [*catalog.SEGMENT_FIELDS, *catalog.META_FIELDS]
        canonical, values = await self._fetch(symbol, fields)
        return SegmentReport.from_qsd(canonical, values)

    async def _get_statement(
        self,
        symbol: str,
        statement: StatementType,
        period: Period,
        max_periods: int | None,
    ) -> FinancialStatement:
        canonical, values = await self._fetch(symbol, self._statement_fields(statement, period))
        return models.build_statement(canonical, statement, period, values, max_periods)

    async def get_income_statement(
        self, symbol: str, period: Period = Period.FY, max_periods: int | None = None
    ) -> FinancialStatement:
        """Return the income statement."""
        return await self._get_statement(symbol, StatementType.INCOME, period, max_periods)

    async def get_balance_sheet(
        self, symbol: str, period: Period = Period.FY, max_periods: int | None = None
    ) -> FinancialStatement:
        """Return the balance sheet."""
        return await self._get_statement(symbol, StatementType.BALANCE, period, max_periods)

    async def get_cash_flow(
        self, symbol: str, period: Period = Period.FY, max_periods: int | None = None
    ) -> FinancialStatement:
        """Return the cash-flow statement."""
        return await self._get_statement(symbol, StatementType.CASH_FLOW, period, max_periods)

    async def get_statistics(
        self, symbol: str, period: Period = Period.FY, max_periods: int | None = None
    ) -> FinancialStatement:
        """Return statistics / valuation ratios."""
        return await self._get_statement(symbol, StatementType.STATISTICS, period, max_periods)

    async def get_dividends(self, symbol: str) -> DividendReport:
        """Return dividend history and summary metrics."""
        fields = [
            *catalog.DIVIDEND_EVENT_FIELDS,
            *catalog.DIVIDEND_SUMMARY_FIELDS,
            *catalog.META_FIELDS,
        ]
        canonical, values = await self._fetch(symbol, fields)
        return DividendReport.from_qsd(canonical, values)

    async def get_earnings(
        self, symbol: str, period: Period = Period.FY, max_periods: int | None = None
    ) -> EarningsReport:
        """Return earnings: reported vs estimate and surprise, per period."""
        if period not in (Period.FY, Period.FQ):
            raise ValueError("Earnings support only Period.FY or Period.FQ.")
        fields = [*catalog.EARNINGS_FIELDS[period.value], *catalog.META_FIELDS]
        canonical, values = await self._fetch(symbol, fields)
        return models.build_earnings(canonical, values, period, max_periods)

    async def get_financials(
        self, symbol: str, period: Period = Period.FY, max_periods: int | None = None
    ) -> FundamentalsSnapshot:
        """Return income, balance, cash-flow, statistics, segments, dividends and earnings.

        Fetched in a single WebSocket round-trip (the union of every field set).
        """
        fields: list[str] = []
        for statement in StatementType:
            fields.extend(self._statement_fields(statement, period))
        fields.extend(catalog.SEGMENT_FIELDS)
        fields.extend(catalog.DIVIDEND_EVENT_FIELDS)
        fields.extend(catalog.DIVIDEND_SUMMARY_FIELDS)
        if period in (Period.FY, Period.FQ):
            fields.extend(catalog.EARNINGS_FIELDS[period.value])
        fields = list(dict.fromkeys(fields))  # dedupe, preserve order

        canonical, values = await self._fetch(symbol, fields)
        earnings = (
            models.build_earnings(canonical, values, period, max_periods)
            if period in (Period.FY, Period.FQ)
            else None
        )
        return FundamentalsSnapshot(
            symbol=canonical,
            currency=values.get("fundamental_currency_code") or values.get("currency_code"),
            income=models.build_statement(
                canonical, StatementType.INCOME, period, values, max_periods
            ),
            balance=models.build_statement(
                canonical, StatementType.BALANCE, period, values, max_periods
            ),
            cash_flow=models.build_statement(
                canonical, StatementType.CASH_FLOW, period, values, max_periods
            ),
            statistics=models.build_statement(
                canonical, StatementType.STATISTICS, period, values, max_periods
            ),
            segments=SegmentReport.from_qsd(canonical, values),
            dividends=DividendReport.from_qsd(canonical, values),
            earnings=earnings,
            raw=values,
        )
