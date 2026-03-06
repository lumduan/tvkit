"""Unit tests for ConnectionService protocol message builders and dispatch."""

import inspect
from typing import Any

import pytest

from tvkit.api.chart.services.connection_service import ConnectionService

WS_URL: str = "wss://data.tradingview.com/socket.io/websocket"


class TestConnectionServiceSeriesArgs:
    """Tests for _create_series_args, _modify_series_args, and add_symbol_to_sessions."""

    def test_create_series_args_structure(self) -> None:
        """_create_series_args returns 7-element list with trailing empty string."""
        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        args: list[Any] = svc._create_series_args("cs_abc", "1D", 100)
        assert args == ["cs_abc", "sds_1", "s1", "sds_sym_1", "1D", 100, ""]
        assert len(args) == 7
        assert args[-1] == ""  # trailing empty string is protocol-critical

    def test_modify_series_args_structure(self) -> None:
        """_modify_series_args returns 6-element list with range_param as last element."""
        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        range_str: str = "r,1704067200:1735603200"
        args: list[Any] = svc._modify_series_args("cs_abc", "1D", range_str)
        assert args == ["cs_abc", "sds_1", "s1", "sds_sym_1", "1D", range_str]
        assert len(args) == 6
        assert args[-1] == range_str

    @pytest.mark.asyncio
    async def test_add_symbol_count_mode_no_modify_series(self) -> None:
        """modify_series must NOT be sent when range_param is omitted (count mode)."""
        sent_messages: list[tuple[str, list[Any]]] = []

        async def mock_send(method: str, args: list[Any]) -> None:
            sent_messages.append((method, args))

        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        await svc.add_symbol_to_sessions(
            quote_session="qs_test",
            chart_session="cs_test",
            exchange_symbol="NASDAQ:AAPL",
            timeframe="1D",
            bars_count=100,
            send_message_func=mock_send,
        )
        methods: list[str] = [m[0] for m in sent_messages]
        assert "modify_series" not in methods

    @pytest.mark.asyncio
    async def test_add_symbol_range_mode_sends_modify_series_in_order(self) -> None:
        """modify_series IS sent immediately after create_series when range_param is set."""
        sent_messages: list[tuple[str, list[Any]]] = []

        async def mock_send(method: str, args: list[Any]) -> None:
            sent_messages.append((method, args))

        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        range_str: str = "r,1704067200:1735603200"
        await svc.add_symbol_to_sessions(
            quote_session="qs_test",
            chart_session="cs_test",
            exchange_symbol="NASDAQ:AAPL",
            timeframe="1D",
            bars_count=5000,
            send_message_func=mock_send,
            range_param=range_str,
        )
        methods: list[str] = [m[0] for m in sent_messages]
        assert "modify_series" in methods
        # Protocol ordering: resolve_symbol must precede create_series
        assert methods.index("resolve_symbol") < methods.index("create_series")
        create_index: int = methods.index("create_series")
        # Protocol requirement: modify_series MUST be the very next message
        assert methods[create_index + 1] == "modify_series"
        # Only one modify_series must be sent — no accidental double-dispatch
        assert methods.count("modify_series") == 1
        # Confirm range_param is the last element of the modify_series args
        modify_args: list[Any] = next(
            args for method, args in sent_messages if method == "modify_series"
        )
        assert modify_args[-1] == range_str

    def test_add_symbol_range_param_default_empty_string(self) -> None:
        """range_param keyword argument defaults to empty string."""
        sig = inspect.signature(ConnectionService.add_symbol_to_sessions)
        assert sig.parameters["range_param"].default == ""


class TestAddMultipleSymbolsToSessions:
    """Tests for add_multiple_symbols_to_sessions dispatch behaviour."""

    @pytest.mark.asyncio
    async def test_sends_quote_add_and_fast_symbols_for_all(self) -> None:
        """Both quote_add_symbols and quote_fast_symbols are sent for all symbols."""
        sent_messages: list[tuple[str, list[Any]]] = []

        async def mock_send(method: str, args: list[Any]) -> None:
            sent_messages.append((method, args))

        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        symbols: list[str] = ["NASDAQ:AAPL", "NASDAQ:MSFT", "NYSE:TSLA"]
        await svc.add_multiple_symbols_to_sessions(
            quote_session="qs_test",
            exchange_symbols=symbols,
            send_message_func=mock_send,
        )
        methods: list[str] = [m[0] for m in sent_messages]
        assert methods.count("quote_add_symbols") == 2
        assert methods.count("quote_fast_symbols") == 2

    @pytest.mark.asyncio
    async def test_all_symbols_included_in_second_add(self) -> None:
        """Second quote_add_symbols call includes all symbols as raw strings."""
        sent_messages: list[tuple[str, list[Any]]] = []

        async def mock_send(method: str, args: list[Any]) -> None:
            sent_messages.append((method, args))

        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        symbols: list[str] = ["NASDAQ:AAPL", "NASDAQ:MSFT"]
        await svc.add_multiple_symbols_to_sessions(
            quote_session="qs_test",
            exchange_symbols=symbols,
            send_message_func=mock_send,
        )
        # The second quote_add_symbols call carries the raw symbol list
        add_calls: list[list[Any]] = [
            args for method, args in sent_messages if method == "quote_add_symbols"
        ]
        second_call_args: list[Any] = add_calls[1]
        for symbol in symbols:
            assert symbol in second_call_args
