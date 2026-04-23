"""Tests for OHLCV session tracking and reconnect restoration (Phase 3)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tvkit.api.chart.ohlcv import OHLCV, _StreamingSession


class TestStreamingSession:
    """Tests for _StreamingSession frozen dataclass."""

    def test_fields_stored(self) -> None:
        session = _StreamingSession(
            symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=100,
            quote_session="qs_abc",
            chart_session="cs_abc",
        )
        assert session.symbol == "NASDAQ:AAPL"
        assert session.interval == "1D"
        assert session.bars_count == 100
        assert session.quote_session == "qs_abc"
        assert session.chart_session == "cs_abc"
        assert session.range_param == ""

    def test_range_param_stored(self) -> None:
        session = _StreamingSession(
            symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=5000,
            quote_session="qs_abc",
            chart_session="cs_abc",
            range_param="r,1704067200:1735603200",
        )
        assert session.range_param == "r,1704067200:1735603200"

    def test_frozen_raises_on_mutation(self) -> None:
        session = _StreamingSession(
            symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=100,
            quote_session="qs_abc",
            chart_session="cs_abc",
        )
        with pytest.raises(FrozenInstanceError):
            session.symbol = "BINANCE:BTCUSDT"  # type: ignore[attr-defined]


class TestOHLCVInit:
    """Tests for OHLCV constructor retry parameter exposure."""

    def test_default_parameters(self) -> None:
        client = OHLCV()
        assert client._max_attempts == 5
        assert client._base_backoff == 1.0
        assert client._max_backoff == 30.0
        assert client._session is None

    def test_custom_parameters(self) -> None:
        client = OHLCV(max_attempts=3, base_backoff=2.0, max_backoff=60.0)
        assert client._max_attempts == 3
        assert client._base_backoff == 2.0
        assert client._max_backoff == 60.0

    def test_no_connection_initially(self) -> None:
        client = OHLCV()
        assert client.connection_service is None
        assert client.message_service is None


class TestRestoreSession:
    """Tests for _restore_session callback."""

    @pytest.mark.asyncio
    async def test_returns_when_session_none(self) -> None:
        """_restore_session returns immediately if no session stored."""
        client = OHLCV()
        mock_cs = AsyncMock()
        mock_cs.initialize_sessions = AsyncMock()  # explicit mock — no dynamic attribute creation
        client.connection_service = mock_cs
        await client._restore_session()
        mock_cs.initialize_sessions.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_when_no_connection_service(self) -> None:
        """_restore_session returns immediately if connection_service is None."""
        client = OHLCV()
        client._session = _StreamingSession(
            symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=100,
            quote_session="qs_abc",
            chart_session="cs_abc",
        )
        # connection_service is None — must not raise
        await client._restore_session()

    @pytest.mark.asyncio
    async def test_sends_correct_messages(self) -> None:
        """_restore_session re-initializes session, re-subscribes, and updates message_service."""
        client = OHLCV()
        client._session = _StreamingSession(
            symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=100,
            quote_session="qs_abc",
            chart_session="cs_abc",
        )

        mock_ws = MagicMock()
        mock_cs = AsyncMock()
        mock_cs.ws = mock_ws

        mock_ms = MagicMock()
        mock_send = AsyncMock()
        mock_ms.get_send_message_callable.return_value = mock_send

        client.connection_service = mock_cs

        with patch("tvkit.api.chart.ohlcv.MessageService", return_value=mock_ms) as mock_ms_cls:
            await client._restore_session()

        mock_ms_cls.assert_called_once_with(mock_ws)
        assert client.message_service is mock_ms  # assignment happened
        mock_cs.initialize_sessions.assert_called_once_with("qs_abc", "cs_abc", mock_send)
        from tvkit.api.chart.models.adjustment import Adjustment

        mock_cs.add_symbol_to_sessions.assert_called_once_with(
            "qs_abc",
            "cs_abc",
            "NASDAQ:AAPL",
            "1D",
            100,
            mock_send,
            range_param="",
            adjustment=Adjustment.SPLITS,
        )

    @pytest.mark.asyncio
    async def test_range_param_passed(self) -> None:
        """_restore_session passes range_param from stored session."""
        client = OHLCV()
        client._session = _StreamingSession(
            symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=5000,
            quote_session="qs_abc",
            chart_session="cs_abc",
            range_param="r,1704067200:1735603200",
        )

        mock_ws = MagicMock()
        mock_cs = AsyncMock()
        mock_cs.ws = mock_ws

        mock_ms = MagicMock()
        mock_send = AsyncMock()
        mock_ms.get_send_message_callable.return_value = mock_send
        client.connection_service = mock_cs

        with patch("tvkit.api.chart.ohlcv.MessageService", return_value=mock_ms):
            await client._restore_session()

        from tvkit.api.chart.models.adjustment import Adjustment

        mock_cs.add_symbol_to_sessions.assert_called_once_with(
            "qs_abc",
            "cs_abc",
            "NASDAQ:AAPL",
            "1D",
            5000,
            mock_send,
            range_param="r,1704067200:1735603200",
            adjustment=Adjustment.SPLITS,
        )

    @pytest.mark.asyncio
    async def test_propagates_exception(self) -> None:
        """_restore_session re-raises exceptions so ConnectionService retry loop can react."""
        client = OHLCV()
        client._session = _StreamingSession(
            symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=100,
            quote_session="qs_abc",
            chart_session="cs_abc",
        )

        mock_ws = MagicMock()
        mock_cs = AsyncMock()
        mock_cs.ws = mock_ws
        mock_cs.initialize_sessions.side_effect = OSError("Network error")

        mock_ms = MagicMock()
        mock_ms.get_send_message_callable.return_value = AsyncMock()
        client.connection_service = mock_cs

        with patch("tvkit.api.chart.ohlcv.MessageService", return_value=mock_ms):
            with pytest.raises(OSError, match="Network error"):
                await client._restore_session()


class TestSetupServices:
    """Tests for _setup_services forwarding retry config to ConnectionService."""

    @pytest.mark.asyncio
    async def test_retry_config_forwarded(self) -> None:
        """_setup_services passes all retry params and on_reconnect to ConnectionService."""
        client = OHLCV(max_attempts=3, base_backoff=2.0, max_backoff=60.0)

        mock_ws = MagicMock()
        mock_cs = MagicMock()
        mock_cs.ws = mock_ws
        mock_cs.connect = AsyncMock()
        mock_cs.close = AsyncMock()

        with (
            patch("tvkit.api.chart.ohlcv.ConnectionService", return_value=mock_cs) as mock_cs_cls,
            patch("tvkit.api.chart.ohlcv.MessageService"),
        ):
            await client._setup_services()

        mock_cs_cls.assert_called_once_with(
            client.ws_url,
            auth_token="unauthorized_user_token",
            max_attempts=3,
            base_backoff=2.0,
            max_backoff=60.0,
            on_reconnect=client._restore_session,
        )
        mock_cs.connect.assert_awaited_once()  # connect() must be called

    @pytest.mark.asyncio
    async def test_on_reconnect_is_restore_session(self) -> None:
        """_setup_services passes on_reconnect=self._restore_session."""
        client = OHLCV()

        mock_ws = MagicMock()
        mock_cs = MagicMock()
        mock_cs.ws = mock_ws
        mock_cs.connect = AsyncMock()
        mock_cs.close = AsyncMock()

        with (
            patch("tvkit.api.chart.ohlcv.ConnectionService", return_value=mock_cs) as mock_cs_cls,
            patch("tvkit.api.chart.ohlcv.MessageService"),
        ):
            await client._setup_services()

        call_kwargs = mock_cs_cls.call_args[1]
        # Bound methods are created fresh on each attribute access, so `is` identity
        # fails. Verify the callback is the correct bound method via __func__ + __self__.
        callback = call_kwargs["on_reconnect"]
        assert callback.__func__ is OHLCV._restore_session
        assert callback.__self__ is client


class TestSessionTracking:
    """Tests for _prepare_chart_session storing session state."""

    @pytest.mark.asyncio
    async def test_session_stored_after_prepare(self) -> None:
        """_prepare_chart_session stores _session with correct values after successful setup."""
        client = OHLCV()

        mock_ws = MagicMock()
        mock_cs = AsyncMock()
        mock_cs.ws = mock_ws
        mock_cs.close = AsyncMock()

        mock_ms = MagicMock()
        mock_ms.generate_session.side_effect = ["qs_test123", "cs_test456"]
        mock_ms.get_send_message_callable.return_value = AsyncMock()

        with (
            patch("tvkit.api.chart.ohlcv.ConnectionService", return_value=mock_cs),
            patch("tvkit.api.chart.ohlcv.MessageService", return_value=mock_ms),
        ):
            await client._prepare_chart_session("NASDAQ:AAPL", "1D", 100)

        assert client._session is not None
        assert client._session.symbol == "NASDAQ:AAPL"
        assert client._session.interval == "1D"
        assert client._session.bars_count == 100
        assert client._session.quote_session == "qs_test123"
        assert client._session.chart_session == "cs_test456"
        assert client._session.range_param == ""

    @pytest.mark.asyncio
    async def test_session_range_param_stored(self) -> None:
        """_prepare_chart_session stores range_param when provided."""
        client = OHLCV()

        mock_ws = MagicMock()
        mock_cs = AsyncMock()
        mock_cs.ws = mock_ws
        mock_cs.close = AsyncMock()

        mock_ms = MagicMock()
        mock_ms.generate_session.side_effect = ["qs_test123", "cs_test456"]
        mock_ms.get_send_message_callable.return_value = AsyncMock()

        with (
            patch("tvkit.api.chart.ohlcv.ConnectionService", return_value=mock_cs),
            patch("tvkit.api.chart.ohlcv.MessageService", return_value=mock_ms),
        ):
            await client._prepare_chart_session(
                "NASDAQ:AAPL", "1D", 5000, range_param="r,1704067200:1735603200"
            )

        assert client._session is not None
        assert client._session.range_param == "r,1704067200:1735603200"

    @pytest.mark.asyncio
    async def test_session_cleared_on_aexit(self) -> None:
        """__aexit__ clears _session and calls close() on the connection service."""
        client = OHLCV()
        client._session = _StreamingSession(
            symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=100,
            quote_session="qs_abc",
            chart_session="cs_abc",
        )
        mock_cs = AsyncMock()
        client.connection_service = mock_cs

        await client.__aexit__(None, None, None)

        assert client._session is None
        mock_cs.close.assert_awaited_once()  # resource cleanup triggered
