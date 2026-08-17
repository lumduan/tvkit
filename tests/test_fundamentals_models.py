"""Tests for tvkit.api.fundamentals models — parsing and period alignment.

Uses recorded anonymous payloads under tests/fixtures/fundamentals/ (no network).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tvkit.api.fundamentals.models import (
    DividendReport,
    EarningsReport,
    FinancialStatement,
    FiscalPeriod,
    Period,
    RevenueSegment,
    SegmentReport,
    StatementLine,
    StatementType,
    build_earnings,
    build_fiscal_periods,
    build_statement,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "fundamentals"


def _load(name: str) -> dict[str, Any]:
    return json.load(open(_FIXTURES / name))


@pytest.fixture(scope="module")
def aot() -> dict[str, Any]:
    return _load("aot_v.json")


@pytest.fixture(scope="module")
def kbank() -> dict[str, Any]:
    return _load("kbank_v.json")


# --------------------------------------------------------------------------- models


class TestFiscalPeriod:
    def test_period_end_optional(self) -> None:
        p = FiscalPeriod(label="2025", period_type=Period.FY)
        assert p.period_end is None

    def test_rejects_extra(self) -> None:
        with pytest.raises(ValidationError):
            FiscalPeriod(label="2025", period_type=Period.FY, bogus=1)  # type: ignore[call-arg]


class TestStatementLine:
    def test_values_can_be_none(self) -> None:
        line = StatementLine(field_id="x", label="X", values=[1.0, None, 3.0])
        assert line.values[1] is None


class TestSegmentReport:
    def test_by_business_matches_oracle(self, aot: dict[str, Any]) -> None:
        report = SegmentReport.from_qsd("SET:AOT", aot)
        assert report.currency == "THB"
        by_year = {
            sp.period.label: {s.label: s.value for s in sp.segments} for sp in report.by_business
        }
        # Oracle values (raw THB) from the screenshots.
        assert by_year["2025"]["Airport"] == pytest.approx(62_432_730_000)
        assert by_year["2025"]["Hotel"] == pytest.approx(671_470_000)
        assert by_year["2021"]["Security"] == pytest.approx(40_000)

    def test_by_region_thailand(self, aot: dict[str, Any]) -> None:
        report = SegmentReport.from_qsd("SET:AOT", aot)
        by_year = {
            sp.period.label: {s.label: s.value for s in sp.segments} for sp in report.by_region
        }
        assert by_year["2021"]["Thailand"] == pytest.approx(7_078_880_000)

    def test_legacy_label_union(self, aot: dict[str, Any]) -> None:
        # "Airport and Hotel" only appears in the oldest periods (2006-2013).
        report = SegmentReport.from_qsd("SET:AOT", aot)
        labels_2013 = {
            s.label for sp in report.by_business if sp.period.label == "2013" for s in sp.segments
        }
        assert "Airport and Hotel" in labels_2013

    def test_missing_segments_yield_empty(self) -> None:
        report = SegmentReport.from_qsd("X:Y", {})
        assert report.by_business == []
        assert report.by_region == []

    def test_malformed_rows_skipped(self) -> None:
        report = SegmentReport.from_qsd(
            "X:Y",
            {"revenue_seg_by_business_h": ["bad", {"date": 2025, "segments": "nope"}, 5]},
        )
        assert report.by_business == []


class TestBuildStatement:
    def test_income_matches_oracle(self, aot: dict[str, Any]) -> None:
        stmt = build_statement("SET:AOT", StatementType.INCOME, Period.FY, aot)
        assert stmt.currency == "THB"
        assert stmt.report_template == "industrial"
        assert stmt.period_type is Period.FY
        idx = {p.label: i for i, p in enumerate(stmt.periods)}
        rev = stmt.line("total_revenue")
        assert rev is not None
        assert rev.values[idx["2025"]] == pytest.approx(66_679_386_770)
        # The tricky duplicate-id rows resolve correctly.
        assert stmt.line("total_non_oper_income").values[idx["2025"]] == pytest.approx(
            -4_903_775_320, rel=1e-3
        )  # noqa: E501
        assert stmt.line("minority_interest_exp").values[idx["2025"]] == pytest.approx(
            -428_740_000, rel=1e-3
        )  # noqa: E501

    def test_period_end_is_utc_sep30(self, aot: dict[str, Any]) -> None:
        stmt = build_statement("SET:AOT", StatementType.INCOME, Period.FY, aot)
        end = stmt.periods[0].period_end
        assert end == datetime(2025, 9, 30, tzinfo=UTC)

    def test_bank_template_omits_cogs(self, kbank: dict[str, Any]) -> None:
        stmt = build_statement("SET:KBANK", StatementType.INCOME, Period.FY, kbank)
        assert stmt.report_template == "banking"
        assert stmt.line("cost_of_goods") is None  # bank has no COGS
        assert stmt.line("net_revenue") is not None  # bank-specific line present

    def test_max_periods_trims(self, aot: dict[str, Any]) -> None:
        stmt = build_statement("SET:AOT", StatementType.INCOME, Period.FY, aot, max_periods=3)
        assert len(stmt.periods) == 3
        assert all(len(line.values) == 3 for line in stmt.lines)

    def test_ttm_single_period(self, aot: dict[str, Any]) -> None:
        stmt = build_statement("SET:AOT", StatementType.INCOME, Period.TTM, aot)
        assert len(stmt.periods) == 1
        assert stmt.periods[0].label == "TTM"
        rev = stmt.line("total_revenue")
        assert rev is not None and len(rev.values) == 1

    def test_missing_report_type_defaults_industrial(self, aot: dict[str, Any]) -> None:
        payload = dict(aot)
        payload.pop("report_type", None)
        stmt = build_statement("SET:AOT", StatementType.INCOME, Period.FY, payload)
        # Falls back to the industrial ordering; still finds total_revenue.
        assert stmt.line("total_revenue") is not None


class TestBuildFiscalPeriods:
    def test_labels_and_ends_aligned(self, aot: dict[str, Any]) -> None:
        periods = build_fiscal_periods(aot, Period.FY, None)
        assert periods[0].label == "2025"
        assert periods[0].period_end == datetime(2025, 9, 30, tzinfo=UTC)

    def test_empty_when_no_period_fields(self) -> None:
        assert build_fiscal_periods({}, Period.FY, None) == []


class TestBuildEarnings:
    def test_reported_and_surprise_match_oracle(self, aot: dict[str, Any]) -> None:
        report = build_earnings("SET:AOT", aot, Period.FY)
        by_label = {ep.label: ep for ep in report.periods}
        assert by_label["2025"].eps_reported == pytest.approx(1.27, abs=0.01)
        assert by_label["2021"].eps_reported == pytest.approx(-1.14, abs=0.01)
        # Surprise sign/magnitude from screenshot #6.
        assert by_label["2023"].eps_surprise_pct == pytest.approx(-9.58, abs=0.2)

    def test_surprise_none_when_estimate_zero(self) -> None:
        report = build_earnings(
            "X:Y",
            {
                "earnings_fiscal_period_fy_h": ["2025"],
                "earnings_per_share_fy_h": [1.0],
                "earnings_estimate_fy_h": [0],
            },
            Period.FY,
        )
        assert report.periods[0].eps_surprise_pct is None


class TestDividendReport:
    def test_events_and_summary(self, aot: dict[str, Any]) -> None:
        report = DividendReport.from_qsd("SET:AOT", aot)
        assert report.events
        assert report.events[0].amount == pytest.approx(0.81, abs=0.01)
        assert report.events[0].ex_date is not None
        assert report.events[0].ex_date.date().isoformat() == "2025-12-11"
        assert report.yield_recent == pytest.approx(1.25, abs=0.01)

    def test_empty_payload(self) -> None:
        report = DividendReport.from_qsd("X:Y", {})
        assert report.events == []
        assert report.dividends_paid is None


class TestEnums:
    def test_period_and_statement_values(self) -> None:
        assert Period.FY.value == "FY"
        assert StatementType.CASH_FLOW.value == "cash_flow"

    def test_revenue_segment_defaults(self) -> None:
        seg = RevenueSegment(label="Airport")
        assert seg.value is None


def test_earnings_report_is_pydantic() -> None:
    report = EarningsReport(symbol="X:Y", period_type=Period.FY)
    assert isinstance(report, EarningsReport)
    assert report.periods == []


def test_financial_statement_line_lookup_miss(aot: dict[str, Any]) -> None:
    stmt = build_statement("SET:AOT", StatementType.INCOME, Period.FY, aot)
    assert stmt.line("does_not_exist") is None
    assert isinstance(stmt, FinancialStatement)
