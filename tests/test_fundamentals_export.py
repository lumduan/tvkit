"""Tests for exporting fundamentals via DataExporter and the formatters."""

from __future__ import annotations

import csv
import json as jsonlib
from pathlib import Path
from typing import Any

import pytest

from tvkit.api.fundamentals.models import (
    DividendReport,
    Period,
    SegmentReport,
    StatementType,
    build_earnings,
    build_statement,
)
from tvkit.export import DataExporter, ExportFormat, FundamentalsExportData
from tvkit.export.formatters import PolarsFormatter
from tvkit.export.models import ExportConfig

_FIXTURES = Path(__file__).parent / "fixtures" / "fundamentals"


def _aot() -> dict[str, Any]:
    return jsonlib.load(open(_FIXTURES / "aot_v.json"))


@pytest.fixture(scope="module")
def income() -> Any:
    return build_statement("SET:AOT", StatementType.INCOME, Period.FY, _aot())


@pytest.fixture(scope="module")
def segments() -> Any:
    return SegmentReport.from_qsd("SET:AOT", _aot())


class TestConvert:
    @pytest.mark.asyncio
    async def test_statement_rows(self, income: Any) -> None:
        ex = DataExporter()
        rows = ex._convert_fundamentals_data([income])
        assert rows and all(isinstance(r, FundamentalsExportData) for r in rows)
        rev = [r for r in rows if r.dataset == "income" and r.row == "total_revenue"]
        # one row per period
        assert len(rev) == len(income.periods)
        assert rev[0].currency == "THB"
        assert rev[0].value == pytest.approx(66_679_386_770)

    @pytest.mark.asyncio
    async def test_segment_rows(self, segments: Any) -> None:
        ex = DataExporter()
        rows = ex._convert_fundamentals_data([segments])
        datasets = {r.dataset for r in rows}
        assert datasets == {"segment_business", "segment_region"}

    @pytest.mark.asyncio
    async def test_dividend_and_earnings_rows(self) -> None:
        ex = DataExporter()
        div = DividendReport.from_qsd("SET:AOT", _aot())
        earn = build_earnings("SET:AOT", _aot(), Period.FY)
        div_rows = ex._convert_fundamentals_data([div])
        earn_rows = ex._convert_fundamentals_data([earn])
        assert all(r.dataset == "dividend" for r in div_rows)
        assert {r.row for r in earn_rows} >= {"eps_reported", "eps_surprise_pct"}

    @pytest.mark.asyncio
    async def test_snapshot_explodes(self) -> None:
        ex = DataExporter()
        from tvkit.api.fundamentals.models import FundamentalsSnapshot

        snap = FundamentalsSnapshot(
            symbol="SET:AOT",
            income=build_statement("SET:AOT", StatementType.INCOME, Period.FY, _aot()),
            segments=SegmentReport.from_qsd("SET:AOT", _aot()),
        )
        rows = ex._convert_fundamentals_data([snap])
        assert {"income", "segment_business"} <= {r.dataset for r in rows}


class TestExportFormats:
    @pytest.mark.asyncio
    async def test_polars(self, income: Any) -> None:
        ex = DataExporter()
        result = await ex.export_fundamentals_data(income, ExportFormat.POLARS)
        assert result.success
        assert set(result.data.columns) == set(
            ("symbol", "dataset", "row", "label", "period", "period_end", "value", "currency")
        )

    @pytest.mark.asyncio
    async def test_json(self, income: Any, tmp_path: Path) -> None:
        ex = DataExporter()
        out = tmp_path / "f.json"
        result = await ex.export_fundamentals_data(income, ExportFormat.JSON, out)
        assert result.success and out.exists()
        payload = jsonlib.load(open(out))
        assert "data" in payload and payload["data"]

    @pytest.mark.asyncio
    async def test_csv(self, income: Any, tmp_path: Path) -> None:
        ex = DataExporter()
        out = tmp_path / "f.csv"
        result = await ex.export_fundamentals_data(income, ExportFormat.CSV, out)
        assert result.success and out.exists()
        with open(out) as fh:
            rows = list(csv.DictReader(fh))
        assert rows[0]["symbol"] == "SET:AOT"
        assert "value" in rows[0]

    @pytest.mark.asyncio
    async def test_convenience_to_polars(self, segments: Any) -> None:
        ex = DataExporter()
        df = await ex.to_polars([segments])
        assert df.height > 0

    @pytest.mark.asyncio
    async def test_convenience_to_csv(self, income: Any, tmp_path: Path) -> None:
        ex = DataExporter()
        out = await ex.to_csv([income], tmp_path / "c.csv")
        assert Path(out).exists()

    @pytest.mark.asyncio
    async def test_convenience_to_json(self, income: Any, tmp_path: Path) -> None:
        ex = DataExporter()
        out = await ex.to_json([income], tmp_path / "c.json")
        assert Path(out).exists()


class TestBaseFormatterDefault:
    @pytest.mark.asyncio
    async def test_base_export_fundamentals_not_implemented(self) -> None:
        # A formatter that doesn't override export_fundamentals still exists (back-compat):
        class Custom(PolarsFormatter):
            pass

        # PolarsFormatter DOES override it, so build a raw base-like via the ABC default:
        from tvkit.export.formatters.base_formatter import BaseFormatter

        class Bare(BaseFormatter):
            async def export_ohlcv(self, data: Any, file_path: Any = None) -> Any:  # type: ignore[override]
                ...

            async def export_scanner(self, data: Any, file_path: Any = None) -> Any:  # type: ignore[override]
                ...

            def supports_format(self, format_type: str) -> bool:
                return True

        bare = Bare(ExportConfig(format=ExportFormat.CSV))
        with pytest.raises(NotImplementedError):
            await bare.export_fundamentals([])

    @pytest.mark.asyncio
    async def test_empty_data_returns_failure(self) -> None:
        ex = DataExporter()
        result = await ex.export_fundamentals_data([], ExportFormat.POLARS)
        assert not result.success
        assert result.error_message
