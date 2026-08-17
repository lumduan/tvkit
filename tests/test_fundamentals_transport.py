"""Tests for QuoteSnapshotTransport — with a fake ConnectionService/MessageService.

Verifies the quote-verb sequence, qsd merge, session filtering, and completion handling
without any real WebSocket (patches the chart primitives at the transport import site).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from tvkit.api.chart.exceptions import AuthError, StreamConnectionError
from tvkit.api.fundamentals import transport as transport_mod
from tvkit.api.fundamentals.exceptions import (
    FundamentalsAuthError,
    FundamentalsConnectionError,
    FundamentalsTimeoutError,
)
from tvkit.api.fundamentals.transport import QuoteSnapshotTransport

_FIXTURES = Path(__file__).parent / "fixtures" / "fundamentals"


def _qsd(session: str, symbol: str, values: dict[str, Any]) -> dict[str, Any]:
    return {"m": "qsd", "p": [session, {"n": symbol, "s": "ok", "v": values}]}


def _completed(session: str, symbol: str) -> dict[str, Any]:
    return {"m": "quote_completed", "p": [session, symbol]}


class FakeWS:
    async def send(self, message: str) -> None:  # MessageService.send_message calls this
        return None


class FakeMessageService:
    def __init__(self, ws: Any) -> None:
        self.ws = ws
        self.sent: list[tuple[str, list[Any]]] = []

    def generate_session(self, prefix: str) -> str:
        return prefix + "test"

    def get_send_message_callable(self) -> Any:
        async def _send(func: str, args: list[Any]) -> None:
            self.sent.append((func, args))

        return _send


class FakeConnectionService:
    """Configurable fake — yields the frames it is given from get_data_stream()."""

    frames: list[dict[str, Any]] = []
    connect_error: Exception | None = None
    stream_error: Exception | None = None
    block_after: bool = False

    def __init__(self, ws_url: str, auth_token: str, on_reconnect: Any = None) -> None:
        self.ws_url = ws_url
        self.auth_token = auth_token
        self._ws: FakeWS | None = None

    async def connect(self) -> None:
        if FakeConnectionService.connect_error is not None:
            raise FakeConnectionService.connect_error
        self._ws = FakeWS()

    @property
    def ws(self) -> FakeWS | None:
        return self._ws

    async def close(self) -> None:
        return None

    async def get_data_stream(self) -> AsyncIterator[dict[str, Any]]:
        import asyncio

        if FakeConnectionService.stream_error is not None:
            raise FakeConnectionService.stream_error
        for frame in FakeConnectionService.frames:
            yield frame
        if FakeConnectionService.block_after:
            await asyncio.sleep(10)  # simulate a live socket that blocks for more frames


def _install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transport_mod, "ConnectionService", FakeConnectionService)
    monkeypatch.setattr(transport_mod, "MessageService", FakeMessageService)
    FakeConnectionService.frames = []
    FakeConnectionService.connect_error = None
    FakeConnectionService.stream_error = None
    FakeConnectionService.block_after = False


class TestSnapshot:
    @pytest.mark.asyncio
    async def test_verb_sequence_and_merge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(monkeypatch)
        FakeConnectionService.frames = [
            _qsd("qs_test", "SET:AOT", {"a": 1}),
            _qsd("qs_test", "SET:AOT", {"b": 2}),
            _completed("qs_test", "SET:AOT"),
        ]
        t = QuoteSnapshotTransport()
        await t.connect()
        result = await t.snapshot(["SET:AOT"], ["a", "b"])
        assert result["SET:AOT"] == {"a": 1, "b": 2}
        verbs = [f for f, _ in t._message.sent]  # type: ignore[union-attr]
        assert verbs == [
            "set_auth_token",
            "set_locale",
            "quote_create_session",
            "quote_set_fields",
            "quote_add_symbols",
            "quote_fast_symbols",
        ]

    @pytest.mark.asyncio
    async def test_ignores_other_session_frames(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(monkeypatch)
        FakeConnectionService.frames = [
            _qsd("qs_OTHER", "SET:AOT", {"stale": 9}),
            _completed("qs_OTHER", "SET:AOT"),  # must NOT complete our snapshot
            _qsd("qs_test", "SET:AOT", {"fresh": 1}),
            _completed("qs_test", "SET:AOT"),
        ]
        t = QuoteSnapshotTransport()
        await t.connect()
        result = await t.snapshot(["SET:AOT"], ["x"])
        assert result["SET:AOT"] == {"fresh": 1}

    @pytest.mark.asyncio
    async def test_snapshot_without_connect_raises(self) -> None:
        t = QuoteSnapshotTransport()
        with pytest.raises(FundamentalsConnectionError):
            await t.snapshot(["SET:AOT"], ["x"])

    @pytest.mark.asyncio
    async def test_connect_error_wrapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(monkeypatch)
        FakeConnectionService.connect_error = StreamConnectionError("boom")
        t = QuoteSnapshotTransport()
        with pytest.raises(FundamentalsConnectionError):
            await t.connect()

    @pytest.mark.asyncio
    async def test_auth_error_wrapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(monkeypatch)
        FakeConnectionService.stream_error = AuthError("bad token")
        t = QuoteSnapshotTransport()
        await t.connect()
        with pytest.raises(FundamentalsAuthError):
            await t.snapshot(["SET:AOT"], ["x"])

    @pytest.mark.asyncio
    async def test_stream_connection_error_wrapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(monkeypatch)
        FakeConnectionService.stream_error = StreamConnectionError("drop")
        t = QuoteSnapshotTransport()
        await t.connect()
        with pytest.raises(FundamentalsConnectionError):
            await t.snapshot(["SET:AOT"], ["x"])

    @pytest.mark.asyncio
    async def test_timeout_without_data_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(monkeypatch)
        FakeConnectionService.frames = []
        FakeConnectionService.block_after = True  # blocks, never completes
        t = QuoteSnapshotTransport(timeout=0.05)
        await t.connect()
        with pytest.raises(FundamentalsTimeoutError):
            await t.snapshot(["SET:AOT"], ["x"])

    @pytest.mark.asyncio
    async def test_timeout_with_data_returns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Data arrived but quote_completed never did → return what we have, no raise.
        _install(monkeypatch)
        FakeConnectionService.frames = [_qsd("qs_test", "SET:AOT", {"a": 1})]
        FakeConnectionService.block_after = True
        t = QuoteSnapshotTransport(timeout=0.05)
        await t.connect()
        result = await t.snapshot(["SET:AOT"], ["a"])
        assert result["SET:AOT"] == {"a": 1}

    @pytest.mark.asyncio
    async def test_close_is_safe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(monkeypatch)
        t = QuoteSnapshotTransport()
        await t.connect()
        await t.close()
        await t.close()  # idempotent
