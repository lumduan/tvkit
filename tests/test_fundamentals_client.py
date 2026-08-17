"""Tests for FundamentalsClient — with a fake WS transport (no network)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tvkit.api.fundamentals import (
    FundamentalsClient,
    NoFundamentalDataError,
    Period,
)
from tvkit.api.fundamentals.exceptions import FundamentalsError

_FIXTURES = Path(__file__).parent / "fixtures" / "fundamentals"


def _load(name: str) -> dict[str, Any]:
    return json.load(open(_FIXTURES / name))


class FakeTransport:
    """Stands in for QuoteSnapshotTransport — returns fixture values, records fields."""

    def __init__(self, values_by_symbol: dict[str, dict[str, Any]]) -> None:
        self._values = values_by_symbol
        self.connected = False
        self.closed = False
        self.last_fields: list[str] = []
        self.snapshots = 0

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.closed = True

    async def snapshot(self, symbols: list[str], fields: list[str]) -> dict[str, dict[str, Any]]:
        self.snapshots += 1
        self.last_fields = fields
        return {s: self._values.get(s, {}) for s in symbols}


def _client_with(values: dict[str, dict[str, Any]]) -> tuple[FundamentalsClient, FakeTransport]:
    fake = FakeTransport(values)
    client = FundamentalsClient()
    client._make_transport = lambda token: fake  # type: ignore[method-assign]
    return client, fake


@pytest.fixture(scope="module")
def aot() -> dict[str, Any]:
    return _load("aot_v.json")


@pytest.fixture(scope="module")
def kbank() -> dict[str, Any]:
    return _load("kbank_v.json")


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_context_manager_opens_and_closes(self, aot: dict[str, Any]) -> None:
        client, fake = _client_with({"SET:AOT": aot})
        async with client as fx:
            await fx.get_segments("SET:AOT")
        assert fake.connected and fake.closed

    @pytest.mark.asyncio
    async def test_use_before_open_raises(self) -> None:
        client, _ = _client_with({})
        with pytest.raises(FundamentalsError):
            await client.get_segments("SET:AOT")


class TestGetters:
    @pytest.mark.asyncio
    async def test_get_segments(self, aot: dict[str, Any]) -> None:
        client, _ = _client_with({"SET:AOT": aot})
        async with client as fx:
            report = await fx.get_segments("SET:AOT")
        assert report.symbol == "SET:AOT"
        assert report.by_business

    @pytest.mark.asyncio
    async def test_symbol_normalized(self, aot: dict[str, Any]) -> None:
        # Dash notation is normalized to colon before the snapshot.
        client, _ = _client_with({"SET:AOT": aot})
        async with client as fx:
            report = await fx.get_segments("SET-AOT")
        assert report.symbol == "SET:AOT"

    @pytest.mark.asyncio
    async def test_income_balance_cashflow_statistics(self, aot: dict[str, Any]) -> None:
        client, _ = _client_with({"SET:AOT": aot})
        async with client as fx:
            assert (await fx.get_income_statement("SET:AOT")).lines
            assert (await fx.get_balance_sheet("SET:AOT")).lines
            assert (await fx.get_cash_flow("SET:AOT")).lines
            assert (await fx.get_statistics("SET:AOT")).lines

    @pytest.mark.asyncio
    async def test_income_fields_requested(self, aot: dict[str, Any]) -> None:
        client, fake = _client_with({"SET:AOT": aot})
        async with client as fx:
            await fx.get_income_statement("SET:AOT", period=Period.FY)
        assert "total_revenue_fy_h" in fake.last_fields
        assert "fiscal_period_fy_h" in fake.last_fields

    @pytest.mark.asyncio
    async def test_dividends(self, aot: dict[str, Any]) -> None:
        client, _ = _client_with({"SET:AOT": aot})
        async with client as fx:
            report = await fx.get_dividends("SET:AOT")
        assert report.events

    @pytest.mark.asyncio
    async def test_earnings(self, aot: dict[str, Any]) -> None:
        client, _ = _client_with({"SET:AOT": aot})
        async with client as fx:
            report = await fx.get_earnings("SET:AOT")
        assert report.periods

    @pytest.mark.asyncio
    async def test_earnings_rejects_ttm(self, aot: dict[str, Any]) -> None:
        client, _ = _client_with({"SET:AOT": aot})
        async with client as fx:
            with pytest.raises(ValueError):
                await fx.get_earnings("SET:AOT", period=Period.TTM)

    @pytest.mark.asyncio
    async def test_get_financials_bundle_single_snapshot(self, aot: dict[str, Any]) -> None:
        client, fake = _client_with({"SET:AOT": aot})
        async with client as fx:
            snap = await fx.get_financials("SET:AOT")
        assert fake.snapshots == 1  # one WS round-trip
        assert snap.income and snap.balance and snap.cash_flow and snap.statistics
        assert snap.segments and snap.dividends and snap.earnings
        assert snap.raw  # raw carrier populated

    @pytest.mark.asyncio
    async def test_get_financials_fq_has_earnings(self, aot: dict[str, Any]) -> None:
        client, _ = _client_with({"SET:AOT": aot})
        async with client as fx:
            snap = await fx.get_financials("SET:AOT", period=Period.FQ)
        assert snap.earnings is not None

    @pytest.mark.asyncio
    async def test_get_financials_ttm_no_earnings(self, aot: dict[str, Any]) -> None:
        client, _ = _client_with({"SET:AOT": aot})
        async with client as fx:
            snap = await fx.get_financials("SET:AOT", period=Period.TTM)
        assert snap.earnings is None

    @pytest.mark.asyncio
    async def test_no_data_raises(self) -> None:
        client, _ = _client_with({"SET:AOT": {}})
        async with client as fx:
            with pytest.raises(NoFundamentalDataError):
                await fx.get_segments("NASDAQ:AAPL")  # not in fixture map


class TestBankTemplate:
    @pytest.mark.asyncio
    async def test_bank_income(self, kbank: dict[str, Any]) -> None:
        client, _ = _client_with({"SET:KBANK": kbank})
        async with client as fx:
            stmt = await fx.get_income_statement("SET:KBANK")
        assert stmt.report_template == "banking"
        assert stmt.line("cost_of_goods") is None
