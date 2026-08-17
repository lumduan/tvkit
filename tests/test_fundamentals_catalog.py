"""Tests for the generated fundamentals field catalog."""

from __future__ import annotations

from tvkit.api.fundamentals import catalog


class TestCatalogStructure:
    def test_statements_present(self) -> None:
        for stmt in ("income", "balance", "cash_flow", "statistics"):
            assert stmt in catalog.STATEMENT_REQUEST_FIELDS
            assert stmt in catalog.STATEMENT_ORDER
            assert catalog.STATEMENT_REQUEST_FIELDS[stmt]  # non-empty

    def test_income_templates(self) -> None:
        assert set(catalog.STATEMENT_ORDER["income"]) >= {"industrial", "banking"}

    def test_income_industrial_order_matches_oracle_ids(self) -> None:
        order = catalog.STATEMENT_ORDER["income"]["industrial"]
        # The exact field ids the recon oracle verified (duplicate-id resolution).
        for fid in (
            "total_revenue",
            "cost_of_goods",
            "gross_profit",
            "oper_income",
            "total_non_oper_income",
            "pretax_income",
            "income_tax",
            "minority_interest_exp",
            "net_income",
        ):
            assert fid in order
        # total_revenue leads the statement.
        assert order[0] == "total_revenue"

    def test_banking_income_has_net_revenue(self) -> None:
        assert "net_revenue" in catalog.STATEMENT_ORDER["income"]["banking"]

    def test_labels_resolve_industrial_over_banking(self) -> None:
        # oper_income = "Operating income" (industrial), not "Net operating profit" (banking).
        assert catalog.FIELD_LABELS["oper_income"] == "Operating income"
        assert catalog.FIELD_LABELS["income_tax"] == "Taxes"
        assert catalog.FIELD_LABELS["total_revenue"] == "Total revenue"

    def test_period_suffix_and_fields(self) -> None:
        assert catalog.PERIOD_SUFFIX["FY"] == "fy"
        assert catalog.PERIOD_FIELDS["FY"] == ["fiscal_period_fy_h", "fiscal_period_end_fy_h"]
        assert "fundamental_currency_code" in catalog.META_FIELDS
        assert "report_type" in catalog.META_FIELDS

    def test_segment_dividend_earnings_fields(self) -> None:
        assert "revenue_seg_by_business_h" in catalog.SEGMENT_FIELDS
        assert "revenue_seg_by_region_h" in catalog.SEGMENT_FIELDS
        assert "dividend_amount_h" in catalog.DIVIDEND_EVENT_FIELDS
        assert "FY" in catalog.EARNINGS_FIELDS and "FQ" in catalog.EARNINGS_FIELDS
        assert "earnings_per_share_fy_h" in catalog.EARNINGS_FIELDS["FY"]

    def test_request_fields_are_unique(self) -> None:
        for bases in catalog.STATEMENT_REQUEST_FIELDS.values():
            assert len(bases) == len(set(bases))
