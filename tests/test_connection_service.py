"""Unit tests for ConnectionService protocol message builders and dispatch."""

import inspect
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from tvkit.api.chart.exceptions import AuthError
from tvkit.api.chart.services.connection_service import ConnectionService, ConnectionState

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


class TestAuthTokenParameter:
    """Tests for ConnectionService auth_token constructor parameter and initialize_sessions."""

    def test_default_auth_token_is_anonymous(self) -> None:
        """Default auth_token is the anonymous placeholder string."""
        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        assert svc._auth_token == "unauthorized_user_token"

    def test_custom_auth_token_stored_verbatim(self) -> None:
        """Provided auth_token is stored without modification."""
        token: str = "tv_auth_abc123xyz"
        svc: ConnectionService = ConnectionService(ws_url=WS_URL, auth_token=token)
        assert svc._auth_token == token

    def test_auth_token_parameter_has_correct_default(self) -> None:
        """auth_token parameter default is the anonymous placeholder string."""
        sig = inspect.signature(ConnectionService.__init__)
        param = sig.parameters["auth_token"]
        assert param.default == "unauthorized_user_token"

    @pytest.mark.asyncio
    async def test_initialize_sessions_sends_anonymous_token_by_default(self) -> None:
        """initialize_sessions sends set_auth_token with anonymous token when no auth_token given."""
        sent: list[tuple[str, list[Any]]] = []

        async def mock_send(method: str, args: list[Any]) -> None:
            sent.append((method, args))

        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        await svc.initialize_sessions("qs_test", "cs_test", mock_send)

        auth_calls = [(m, a) for m, a in sent if m == "set_auth_token"]
        assert len(auth_calls) == 1
        assert auth_calls[0][1] == ["unauthorized_user_token"]

    @pytest.mark.asyncio
    async def test_initialize_sessions_sends_provided_auth_token(self) -> None:
        """initialize_sessions sends set_auth_token with the provided auth_token."""
        sent: list[tuple[str, list[Any]]] = []

        async def mock_send(method: str, args: list[Any]) -> None:
            sent.append((method, args))

        token: str = "tv_real_auth_token_12345"
        svc: ConnectionService = ConnectionService(ws_url=WS_URL, auth_token=token)
        await svc.initialize_sessions("qs_test", "cs_test", mock_send)

        auth_calls = [(m, a) for m, a in sent if m == "set_auth_token"]
        assert len(auth_calls) == 1
        assert auth_calls[0][1] == [token]

    @pytest.mark.asyncio
    async def test_initialize_sessions_token_is_first_message(self) -> None:
        """set_auth_token is always the very first message sent by initialize_sessions."""
        sent: list[tuple[str, list[Any]]] = []

        async def mock_send(method: str, args: list[Any]) -> None:
            sent.append((method, args))

        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        await svc.initialize_sessions("qs_test", "cs_test", mock_send)

        assert len(sent) > 0, "initialize_sessions sent no messages"
        assert sent[0][0] == "set_auth_token"

    @pytest.mark.asyncio
    async def test_auth_token_reused_on_reconnect(self) -> None:
        """Calling initialize_sessions a second time (reconnect) reuses the stored token."""
        sent: list[tuple[str, list[Any]]] = []

        async def mock_send(method: str, args: list[Any]) -> None:
            sent.append((method, args))

        token: str = "tv_auth_reconnect_99"
        svc: ConnectionService = ConnectionService(ws_url=WS_URL, auth_token=token)
        await svc.initialize_sessions("qs_1", "cs_1", mock_send)
        await svc.initialize_sessions("qs_2", "cs_2", mock_send)

        auth_calls = [a for m, a in sent if m == "set_auth_token"]
        assert len(auth_calls) == 2
        assert auth_calls[0] == [token]
        assert auth_calls[1] == [token]


class TestAuthErrorDetection:
    """Tests for _is_auth_error() pattern matching and get_data_stream() AuthError propagation."""

    def test_is_auth_error_critical_error_unauthorized_access(self) -> None:
        """critical_error with error_code unauthorized_access is detected as auth error."""
        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        frame: dict[str, object] = {
            "m": "critical_error",
            "p": [{"error_code": "unauthorized_access", "error_message": "Not authorized"}],
        }
        assert svc._is_auth_error(frame) is True

    def test_is_auth_error_set_auth_token_with_error(self) -> None:
        """set_auth_token response with an 'error' field is detected as auth error."""
        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        frame: dict[str, object] = {
            "m": "set_auth_token",
            "p": [{"error": "token_expired"}],
        }
        assert svc._is_auth_error(frame) is True

    def test_is_auth_error_returns_false_for_normal_message(self) -> None:
        """Normal data frames are not classified as auth errors."""
        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        frame: dict[str, object] = {"m": "timescale_update", "p": [{"some": "data"}]}
        assert svc._is_auth_error(frame) is False

    def test_is_auth_error_returns_false_for_critical_error_other_code(self) -> None:
        """critical_error with a different error_code is not an auth error."""
        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        frame: dict[str, object] = {
            "m": "critical_error",
            "p": [{"error_code": "symbol_not_found"}],
        }
        assert svc._is_auth_error(frame) is False

    def test_is_auth_error_returns_false_for_non_list_params(self) -> None:
        """Malformed 'p' field (not a list) does not crash and returns False."""
        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        frame: dict[str, object] = {"m": "critical_error", "p": "not_a_list"}
        assert svc._is_auth_error(frame) is False

    def test_is_auth_error_returns_false_for_empty_params(self) -> None:
        """critical_error with empty params list is not flagged as auth error."""
        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        frame: dict[str, object] = {"m": "critical_error", "p": []}
        assert svc._is_auth_error(frame) is False

    @pytest.mark.asyncio
    async def test_get_data_stream_raises_auth_error_on_auth_frame(self) -> None:
        """AuthError is raised when an auth error frame enters the message queue."""
        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        svc._ws = MagicMock()
        svc._ws.close = AsyncMock()
        svc._state = ConnectionState.STREAMING

        auth_json: str = json.dumps(
            {
                "m": "critical_error",
                "p": [{"error_code": "unauthorized_access"}],
            }
        )
        # _message_queue holds raw TradingView-framed strings (as written by _read_raw_loop)
        framed: str = f"~m~{len(auth_json)}~m~{auth_json}"
        await svc._message_queue.put(framed)

        with pytest.raises(AuthError):
            async for _ in svc.get_data_stream():
                pass  # pragma: no cover

    @pytest.mark.asyncio
    async def test_get_data_stream_closes_connection_on_auth_error(self) -> None:
        """Connection is torn down (state IDLE, ws.close called) after AuthError propagates."""
        svc: ConnectionService = ConnectionService(ws_url=WS_URL)
        ws_mock = MagicMock()
        ws_mock.close = AsyncMock()
        ws_mock.state = MagicMock()
        svc._ws = ws_mock
        svc._state = ConnectionState.STREAMING

        auth_json: str = json.dumps(
            {
                "m": "set_auth_token",
                "p": [{"error": "session_expired"}],
            }
        )
        framed: str = f"~m~{len(auth_json)}~m~{auth_json}"
        await svc._message_queue.put(framed)

        with pytest.raises(AuthError):
            async for _ in svc.get_data_stream():
                pass  # pragma: no cover

        # The finally block in get_data_stream calls close(), which sets state to IDLE
        assert svc._state is ConnectionState.IDLE
        # WebSocket close() was invoked during teardown
        ws_mock.close.assert_called()

    def test_auth_error_is_subclass_of_chart_error(self) -> None:
        """AuthError inherits from ChartError."""
        from tvkit.api.chart.exceptions import ChartError

        assert issubclass(AuthError, ChartError)

    def test_auth_error_importable_from_chart_package(self) -> None:
        """AuthError is accessible from the public tvkit.api.chart surface."""
        from tvkit.api.chart import AuthError as PublicAuthError

        assert PublicAuthError is AuthError
