"""Pydantic models for :mod:`tvkit.api.fundamentals`.

TradingView delivers fundamentals as quote fields (see
``docs/issues/tradingview-financials/findings.md``): scalar and history-array field ids whose
values are **raw** reporting-currency units. History arrays end in ``_h`` and are index-aligned
to the ``fiscal_period_*_h`` label array and the ``fiscal_period_end_*_h`` timestamp array.

``None`` in a :class:`StatementLine` value list means *the API did not report that field for
that period* — never zero. A line the issuer's template omits entirely (e.g. cost of goods for a
bank) is simply absent from :attr:`FinancialStatement.lines`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tvkit.api.fundamentals import catalog

__all__ = [
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
]


class Period(str, Enum):
    """Reporting period type. Selects the field-id suffix used on the wire."""

    FY = "FY"
    """Fiscal year (annual)."""
    FQ = "FQ"
    """Fiscal quarter."""
    FH = "FH"
    """Fiscal half-year."""
    TTM = "TTM"
    """Trailing twelve months (single period)."""


class StatementType(str, Enum):
    """A financial statement family available from :class:`FinancialStatement`."""

    INCOME = "income"
    BALANCE = "balance"
    CASH_FLOW = "cash_flow"
    STATISTICS = "statistics"


def _to_utc(ts: Any) -> datetime | None:
    """Convert a Unix-seconds timestamp to an aware UTC datetime, or None."""
    if not isinstance(ts, (int | float)):
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


class FiscalPeriod(BaseModel):
    """One reporting period a statement's values are aligned to."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(description="Period label, e.g. '2025' (FY) or '2026-Q3' (FQ).")
    period_end: datetime | None = Field(
        default=None, description="Period end as an aware UTC datetime, or None if not delivered."
    )
    period_type: Period = Field(description="The period type this label belongs to.")


class StatementLine(BaseModel):
    """A single statement row and its values across every period (newest-first)."""

    model_config = ConfigDict(extra="forbid")

    field_id: str = Field(description="TradingView field-id base, e.g. 'total_revenue'.")
    label: str = Field(description="Human-readable row label from the field catalog.")
    values: list[float | None] = Field(
        description="Values index-aligned to the statement's periods; None = not reported."
    )


class FinancialStatement(BaseModel):
    """A financial statement: ordered rows × periods, in raw reporting-currency units."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(description="Normalized 'EXCHANGE:TICKER' symbol.")
    statement: StatementType = Field(description="Which statement family this is.")
    period_type: Period = Field(description="Period type of the columns (FY/FQ/TTM/FH).")
    currency: str | None = Field(
        default=None, description="Reporting currency code (e.g. 'THB'), or None if unknown."
    )
    report_template: str | None = Field(
        default=None, description="Issuer template: industrial / banking / insurance / other."
    )
    periods: list[FiscalPeriod] = Field(description="Reporting periods, newest-first.")
    lines: list[StatementLine] = Field(description="Statement rows in display order.")

    def line(self, field_id: str) -> StatementLine | None:
        """Return the row with ``field_id``, or None if the issuer did not report it."""
        return next((ln for ln in self.lines if ln.field_id == field_id), None)


class RevenueSegment(BaseModel):
    """One revenue-segment cell: an issuer-specific label and a raw-currency value."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(description="Segment label as delivered (localized), e.g. 'Airport'.")
    value: float | None = Field(default=None, description="Revenue in raw currency units.")


class SegmentPeriod(BaseModel):
    """Revenue segments for a single fiscal period."""

    model_config = ConfigDict(extra="forbid")

    period: FiscalPeriod = Field(description="The fiscal period.")
    segments: list[RevenueSegment] = Field(description="Segment cells for this period.")


class SegmentReport(BaseModel):
    """Revenue broken down by business source and by geography (P0)."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(description="Normalized 'EXCHANGE:TICKER' symbol.")
    currency: str | None = Field(default=None, description="Reporting currency code.")
    by_business: list[SegmentPeriod] = Field(
        default_factory=list, description="Revenue by business/source, newest-first."
    )
    by_region: list[SegmentPeriod] = Field(
        default_factory=list, description="Revenue by country/region, newest-first."
    )

    @classmethod
    def from_qsd(cls, symbol: str, values: dict[str, Any]) -> SegmentReport:
        """Build a report from a merged ``qsd`` ``v`` dict."""
        return cls(
            symbol=symbol,
            currency=values.get("fundamental_currency_code") or values.get("currency_code"),
            by_business=_parse_segment_series(values.get("revenue_seg_by_business_h")),
            by_region=_parse_segment_series(values.get("revenue_seg_by_region_h")),
        )


class DividendEvent(BaseModel):
    """A single dividend distribution."""

    model_config = ConfigDict(extra="forbid")

    amount: float | None = Field(default=None, description="Dividend per share.")
    ex_date: datetime | None = Field(default=None, description="Ex-dividend date (UTC).")
    payment_date: datetime | None = Field(default=None, description="Payment date (UTC).")
    record_date: datetime | None = Field(default=None, description="Record date (UTC).")
    dividend_type: str | None = Field(default=None, description="e.g. 'Annual', 'Quarterly'.")


class DividendReport(BaseModel):
    """Dividend history plus summary metrics."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(description="Normalized 'EXCHANGE:TICKER' symbol.")
    currency: str | None = Field(default=None, description="Reporting currency code.")
    events: list[DividendEvent] = Field(
        default_factory=list, description="Dividend events, newest-first."
    )
    yield_recent: float | None = Field(default=None, description="Most recent dividend yield (%).")
    payout_ratio_ttm: float | None = Field(default=None, description="Payout ratio, TTM (%).")
    dividends_paid: float | None = Field(
        default=None, description="Total dividends paid (raw currency, most recent period)."
    )

    @classmethod
    def from_qsd(cls, symbol: str, values: dict[str, Any]) -> DividendReport:
        """Build a report from a merged ``qsd`` ``v`` dict."""
        amounts = values.get("dividend_amount_h") or []
        ex = values.get("dividend_ex_date_h") or []
        pay = values.get("dividend_payment_date_h") or []
        rec = values.get("dividend_record_date_h") or []
        types = values.get("dividend_type_h") or []
        events: list[DividendEvent] = []
        for i in range(len(amounts)):
            events.append(
                DividendEvent(
                    amount=_num(amounts[i]),
                    ex_date=_to_utc(ex[i]) if i < len(ex) else None,
                    payment_date=_to_utc(pay[i]) if i < len(pay) else None,
                    record_date=_to_utc(rec[i]) if i < len(rec) else None,
                    dividend_type=types[i] if i < len(types) else None,
                )
            )
        payout_h = values.get("dividend_payout_ratio_fy_h") or []
        return cls(
            symbol=symbol,
            currency=values.get("fundamental_currency_code") or values.get("currency_code"),
            events=events,
            yield_recent=_num(values.get("dividend_yield_recent")),
            payout_ratio_ttm=_num(values.get("dividend_payout_ratio_ttm"))
            or (_num(payout_h[0]) if payout_h else None),
            dividends_paid=_num(values.get("dividends_paid")),
        )


class EarningsPeriod(BaseModel):
    """Reported vs estimated results for one fiscal period."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(description="Fiscal period label, e.g. '2025' or '2026-Q3'.")
    eps_reported: float | None = Field(default=None, description="Reported EPS.")
    eps_estimate: float | None = Field(default=None, description="Consensus EPS estimate.")
    eps_surprise_pct: float | None = Field(
        default=None, description="EPS surprise vs estimate, percent."
    )
    revenue_reported: float | None = Field(default=None, description="Reported revenue (raw).")
    revenue_estimate: float | None = Field(default=None, description="Revenue estimate (raw).")


class EarningsReport(BaseModel):
    """Earnings history: reported vs estimate and surprise, per period."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(description="Normalized 'EXCHANGE:TICKER' symbol.")
    currency: str | None = Field(default=None, description="Reporting currency code.")
    period_type: Period = Field(description="FY or FQ.")
    periods: list[EarningsPeriod] = Field(
        default_factory=list, description="Earnings periods, newest-first."
    )


class FundamentalsSnapshot(BaseModel):
    """Everything for one symbol, fetched in a single WebSocket round-trip."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(description="Normalized 'EXCHANGE:TICKER' symbol.")
    currency: str | None = Field(default=None, description="Reporting currency code.")
    income: FinancialStatement | None = Field(default=None, description="Income statement.")
    balance: FinancialStatement | None = Field(default=None, description="Balance sheet.")
    cash_flow: FinancialStatement | None = Field(default=None, description="Cash-flow statement.")
    statistics: FinancialStatement | None = Field(default=None, description="Statistics/ratios.")
    segments: SegmentReport | None = Field(default=None, description="Revenue segments.")
    dividends: DividendReport | None = Field(default=None, description="Dividend history.")
    earnings: EarningsReport | None = Field(default=None, description="Earnings vs estimates.")
    raw: dict[str, Any] = Field(
        default_factory=dict, repr=False, description="Raw merged qsd field dict (unparsed)."
    )


# --------------------------------------------------------------------------- helpers


def _num(x: Any) -> float | None:
    """Coerce a wire value to float, or None."""
    return float(x) if isinstance(x, (int | float)) else None


def _parse_segment_series(rows: Any) -> list[SegmentPeriod]:
    """Parse a ``revenue_seg_by_*_h`` array into SegmentPeriods (period type FY)."""
    out: list[SegmentPeriod] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        date = row.get("date")
        segs = row.get("segments")
        if not isinstance(segs, list):
            continue
        out.append(
            SegmentPeriod(
                period=FiscalPeriod(label=str(date), period_type=Period.FY),
                segments=[
                    RevenueSegment(label=str(s.get("label")), value=_num(s.get("value")))
                    for s in segs
                    if isinstance(s, dict)
                ],
            )
        )
    return out


def build_fiscal_periods(
    values: dict[str, Any], period: Period, max_periods: int | None
) -> list[FiscalPeriod]:
    """Build the period axis from ``fiscal_period_*_h`` + ``fiscal_period_end_*_h``."""
    label_key, end_key = catalog.PERIOD_FIELDS[period.value]
    labels = values.get(label_key) or []
    ends = values.get(end_key) or []
    periods: list[FiscalPeriod] = []
    for i, label in enumerate(labels):
        periods.append(
            FiscalPeriod(
                label=str(label),
                period_end=_to_utc(ends[i]) if i < len(ends) else None,
                period_type=period,
            )
        )
    if max_periods is not None:
        periods = periods[:max_periods]
    return periods


def build_statement(
    symbol: str,
    statement: StatementType,
    period: Period,
    values: dict[str, Any],
    max_periods: int | None = None,
) -> FinancialStatement:
    """Assemble a :class:`FinancialStatement` from a merged ``qsd`` ``v`` dict.

    Rows are ordered by the issuer's template (``report_type``); a row whose field the server
    did not return is omitted. TTM statements read the scalar ``_ttm`` fields as a single column.
    """
    periods = build_fiscal_periods(values, period, max_periods)
    template = values.get("report_type") or "industrial"
    order = catalog.STATEMENT_ORDER.get(statement.value, {})
    ordered_bases = order.get(template) or order.get("industrial") or []
    # Any reported bases not in the chosen template order get appended (stable).
    known = set(ordered_bases)
    request_bases = catalog.STATEMENT_REQUEST_FIELDS.get(statement.value, [])
    tail = [b for b in request_bases if b not in known]
    suffix = catalog.PERIOD_SUFFIX[period.value]

    lines: list[StatementLine] = []
    for base in [*ordered_bases, *tail]:
        if period is Period.TTM:
            scalar = values.get(f"{base}_ttm")
            if scalar is None:
                continue
            vals: list[float | None] = [_num(scalar)]
        else:
            arr = values.get(f"{base}_{suffix}_h")
            if not isinstance(arr, list):
                continue
            trimmed = arr if max_periods is None else arr[:max_periods]
            vals = [_num(x) for x in trimmed]
        lines.append(
            StatementLine(
                field_id=base,
                label=catalog.FIELD_LABELS.get(base, base),
                values=vals,
            )
        )
    if period is Period.TTM:
        periods = [FiscalPeriod(label="TTM", period_type=Period.TTM)]
    return FinancialStatement(
        symbol=symbol,
        statement=statement,
        period_type=period,
        currency=values.get("fundamental_currency_code") or values.get("currency_code"),
        report_template=values.get("report_type"),
        periods=periods,
        lines=lines,
    )


def build_earnings(
    symbol: str, values: dict[str, Any], period: Period, max_periods: int | None = None
) -> EarningsReport:
    """Assemble an :class:`EarningsReport` from reported/estimate/surprise field arrays."""
    suffix = catalog.PERIOD_SUFFIX[period.value]
    labels = values.get(f"earnings_fiscal_period_{suffix}_h") or []
    reported = values.get(f"earnings_per_share_{suffix}_h") or []
    estimate = (
        values.get(f"earnings_estimate_{suffix}_h")
        or values.get(f"earnings_per_share_forecast_{suffix}_h")
        or []
    )
    rev_rep = values.get(f"revenues_{suffix}_h") or []
    rev_est = values.get(f"revenues_estimate_{suffix}_h") or []

    n = len(labels) if labels else len(reported)
    if max_periods is not None:
        n = min(n, max_periods)
    out: list[EarningsPeriod] = []
    for i in range(n):
        rep = _num(reported[i]) if i < len(reported) else None
        est = _num(estimate[i]) if i < len(estimate) else None
        surprise = None
        if rep is not None and est is not None and est != 0:
            surprise = (rep - est) / abs(est) * 100.0
        out.append(
            EarningsPeriod(
                label=str(labels[i]) if i < len(labels) else str(i),
                eps_reported=rep,
                eps_estimate=est,
                eps_surprise_pct=surprise,
                revenue_reported=_num(rev_rep[i]) if i < len(rev_rep) else None,
                revenue_estimate=_num(rev_est[i]) if i < len(rev_est) else None,
            )
        )
    return EarningsReport(
        symbol=symbol,
        currency=values.get("fundamental_currency_code") or values.get("currency_code"),
        period_type=period,
        periods=out,
    )
