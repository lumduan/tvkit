"""
Tests for get_historical_ohlcv in the OHLCV client.

Covers all message-loop exit paths: series_completed signal, study_completed fallback,
bars_count threshold, timeout safety net, error conditions, and session lifecycle.
No real network calls — all external I/O is mocked.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tvkit.api.chart.ohlcv import OHLCV

SYMBOL: str = "BINANCE:BTCUSDT"

SERIES_COMPLETED_MSG: dict[str, Any] = {
    "m": "series_completed",
    "p": ["cs_xxx", "sds_1", "sds_sym_1", "ok"],
}
STUDY_COMPLETED_MSG: dict[str, Any] = {
    "m": "study_completed",
    "p": ["cs_xxx", "st1"],
}
SERIES_LOADING_MSG: dict[str, Any] = {
    "m": "series_loading",
    "p": ["cs_xxx", "sds_1"],
}
SERIES_ERROR_MSG: dict[str, Any] = {
    "m": "series_error",
    "p": ["cs_xxx", "sds_1", "series_error", "SeriesErrorType"],
}


def make_timescale_update(
    bars_count: int,
    base_ts: float = 1_000_000.0,
) -> dict[str, Any]:
    """Build a fake timescale_update message containing `bars_count` bars."""
    series: list[dict[str, Any]] = [
        {"i": i, "v": [base_ts + i * 60, 100.0, 105.0, 95.0, 102.0, float(i + 1)]}
        for i in range(bars_count)
    ]
    return {"m": "timescale_update", "p": ["cs_xxx", {"sds_1": {"s": series}}]}


def make_du_update(
    bars_count: int = 1,
    base_ts: float = 2_000_000.0,
) -> dict[str, Any]:
    """Build a fake 'du' data-update message containing `bars_count` bars."""
    series: list[dict[str, Any]] = [
        {"i": i, "v": [base_ts + i * 60, 110.0, 115.0, 108.0, 112.0, float(i + 1)]}
        for i in range(bars_count)
    ]
    return {
        "m": "du",
        "p": [
            "cs_xxx",
            {
                "sds_1": {
                    "s": series,
                    "ns": {"d": "", "indexes": "nochange"},
                    "t": "s1",
                    "lbs": {"bar_close_time": int(base_ts + bars_count * 60)},
                }
            },
        ],
    }


async def fake_stream(
    messages: list[dict[str, Any]],
) -> AsyncGenerator[dict[str, Any], None]:
    """Async generator that yields a pre-defined sequence of messages."""
    for msg in messages:
        yield msg


async def broken_stream(
    messages: list[dict[str, Any]],
    error: Exception,
) -> AsyncGenerator[dict[str, Any], None]:
    """Async generator that yields messages then raises an unexpected exception."""
    for msg in messages:
        yield msg
    raise error


def make_patches() -> dict[str, Any]:
    """Return fresh mock instances for module-level dependencies (per-test isolation)."""
    return {
        "validate_symbols": AsyncMock(return_value=True),
        "convert_symbol_format": MagicMock(return_value=MagicMock(converted_symbol=SYMBOL)),
        "validate_interval": MagicMock(),
    }


def _make_client(messages: list[dict[str, Any]]) -> OHLCV:
    """Return an OHLCV client wired to a fake data stream with services mocked."""
    client: OHLCV = OHLCV()
    client._prepare_chart_session = AsyncMock()  # type: ignore[method-assign]
    client.connection_service = MagicMock()
    client.connection_service.get_data_stream = lambda: fake_stream(messages)
    client.connection_service.close = AsyncMock()
    return client


# ─────────────────────────────────────────────────────────────────────────────
# Class 1: series_completed signal — Phase 1 regression tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSeriesCompletedSignal:
    """Regression tests: series_completed must break the message loop (Phase 1 fix)."""

    @pytest.mark.asyncio
    async def test_returns_partial_bars_on_series_completed(self) -> None:
        """When series_completed arrives before bars_count is reached, return all collected bars."""
        messages: list[dict[str, Any]] = [
            SERIES_LOADING_MSG,
            make_timescale_update(bars_count=403),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=500
            )

        assert len(result) == 403

    @pytest.mark.asyncio
    async def test_returns_exact_bars_when_count_matches(self) -> None:
        """When bars_count exactly equals available bars, all bars are returned."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=10),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=10
            )

        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_series_completed_with_zero_bars_raises_runtime_error(self) -> None:
        """series_completed with no bars collected raises RuntimeError."""
        messages: list[dict[str, Any]] = [
            SERIES_LOADING_MSG,
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(RuntimeError, match="No historical data received"):
                await client.get_historical_ohlcv(
                    exchange_symbol=SYMBOL, interval="1D", bars_count=100
                )

    @pytest.mark.asyncio
    async def test_multiple_timescale_updates_before_series_completed(self) -> None:
        """Bars accumulate correctly across multiple timescale_update messages."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5, base_ts=1_000_000.0),
            make_timescale_update(bars_count=5, base_ts=1_001_000.0),
            make_timescale_update(bars_count=5, base_ts=1_002_000.0),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=100
            )

        assert len(result) == 15

    @pytest.mark.asyncio
    async def test_series_completed_stops_before_timeout(self) -> None:
        """Loop exits via series_completed signal, not 30-second timeout."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=10),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        # asyncio.wait_for enforces a strict 5 s ceiling — hangs here means the fix regressed
        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await asyncio.wait_for(
                client.get_historical_ohlcv(exchange_symbol=SYMBOL, interval="1D", bars_count=500),
                timeout=5.0,
            )

        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_breaks_when_bars_count_reached_before_series_completed(self) -> None:
        """Loop exits on bars_count threshold; series_completed signal is never awaited."""
        # Stream has exactly bars_count bars and no series_completed.
        # The loop must break on the count check, not wait for a signal.
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=10),
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=10
            )

        assert len(result) == 10


# ─────────────────────────────────────────────────────────────────────────────
# Class 2: study_completed fallback signal
# ─────────────────────────────────────────────────────────────────────────────


class TestStudyCompletedSignal:
    """study_completed is a fallback exit signal for atypical TradingView message ordering."""

    @pytest.mark.asyncio
    async def test_study_completed_alone_breaks_loop_and_raises_on_no_bars(self) -> None:
        """study_completed with no bars raises RuntimeError (zero bars = error)."""
        messages: list[dict[str, Any]] = [
            STUDY_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(RuntimeError, match="No historical data received"):
                await client.get_historical_ohlcv(
                    exchange_symbol=SYMBOL, interval="1D", bars_count=100
                )

    @pytest.mark.asyncio
    async def test_study_completed_after_bars_returns_bars(self) -> None:
        """study_completed after bars (no series_completed) breaks the loop and returns bars."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),
            STUDY_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=100
            )

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_series_completed_exits_before_study_completed_reached(self) -> None:
        """Loop exits at series_completed; study_completed message is never processed."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),
            SERIES_COMPLETED_MSG,
            STUDY_COMPLETED_MSG,  # stream continues, but loop already exited
            make_timescale_update(bars_count=100),  # should never be processed
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=500
            )

        # Only the 5 bars before series_completed are returned
        assert len(result) == 5


# ─────────────────────────────────────────────────────────────────────────────
# Class 3: partial data, sorting, du messages, duplicates, unknown types
# ─────────────────────────────────────────────────────────────────────────────


class TestPartialDataScenarios:
    """Partial data, chronological sorting, du processing, duplicates, unknown messages."""

    @pytest.mark.asyncio
    async def test_partial_result_when_fewer_bars_than_requested(self) -> None:
        """Fewer bars than requested returns successfully without error."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=50),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=100
            )

        assert len(result) == 50

    @pytest.mark.asyncio
    async def test_no_partial_condition_when_bars_count_exactly_met(self) -> None:
        """Exactly bars_count bars returns successfully (no partial condition)."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=10),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=10
            )

        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_bars_sorted_chronologically_on_out_of_order_arrival(self) -> None:
        """Bars are sorted ascending by timestamp regardless of arrival order."""
        # Two batches: second batch has earlier timestamps than the first
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=3, base_ts=2_000_000.0),  # later timestamps
            make_timescale_update(bars_count=3, base_ts=1_000_000.0),  # earlier timestamps
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=100
            )

        assert len(result) == 6
        timestamps: list[float] = [bar.timestamp for bar in result]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_du_message_bars_also_collected(self) -> None:
        """'du' data-update bars are collected alongside timescale_update bars."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=3),
            make_du_update(bars_count=1),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=100
            )

        assert len(result) == 4

    @pytest.mark.asyncio
    async def test_duplicate_bars_appended_without_deduplication(self) -> None:
        """Duplicate timescale_update messages result in duplicate bars (no deduplication).

        This documents the current append-only behaviour. If deduplication is added,
        this test will fail — making the behaviour change visible and deliberate.
        Two separate make_timescale_update() calls are used (not the same object reference)
        to avoid any possible mutation-sharing side effects.
        """
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),  # first call
            make_timescale_update(bars_count=5),  # second call — identical content
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=100
            )

        assert len(result) == 10  # 5 + 5, no deduplication

    @pytest.mark.asyncio
    async def test_unknown_message_type_skipped_gracefully(self) -> None:
        """Unknown message types are silently skipped; bars collection continues."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),
            {"m": "some_future_event", "p": ["cs_xxx", "payload"]},
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=100
            )

        assert len(result) == 5


# ─────────────────────────────────────────────────────────────────────────────
# Class 4: error handling — series_error, invalid input, malformed messages
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Error propagation, malformed message recovery, and input-validation boundaries."""

    @pytest.mark.asyncio
    async def test_series_error_clean_raises_value_error(self) -> None:
        """series_error as the first message raises ValueError immediately."""
        messages: list[dict[str, Any]] = [SERIES_ERROR_MSG]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(ValueError, match="TradingView series error"):
                await client.get_historical_ohlcv(
                    exchange_symbol=SYMBOL, interval="1D", bars_count=100
                )

    @pytest.mark.asyncio
    async def test_series_error_after_partial_bars_raises_value_error(self) -> None:
        """series_error is always fatal — ValueError raised even when bars were collected."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),
            SERIES_ERROR_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(ValueError, match="TradingView series error"):
                await client.get_historical_ohlcv(
                    exchange_symbol=SYMBOL, interval="1D", bars_count=100
                )

    @pytest.mark.asyncio
    async def test_invalid_symbol_raises_value_error(self) -> None:
        """validate_symbols failure propagates before stream starts."""
        messages: list[dict[str, Any]] = []
        client: OHLCV = _make_client(messages)

        patches: dict[str, Any] = {
            **make_patches(),
            "validate_symbols": AsyncMock(side_effect=ValueError("Invalid symbol")),
        }
        with patch.multiple("tvkit.api.chart.ohlcv", **patches):
            with pytest.raises(ValueError, match="Invalid symbol"):
                await client.get_historical_ohlcv(
                    exchange_symbol="INVALID:SYM", interval="1D", bars_count=10
                )

    @pytest.mark.asyncio
    async def test_convert_symbol_format_raises_propagated(self) -> None:
        """convert_symbol_format failure propagates before stream starts."""
        messages: list[dict[str, Any]] = []
        client: OHLCV = _make_client(messages)

        patches: dict[str, Any] = {
            **make_patches(),
            "convert_symbol_format": MagicMock(side_effect=ValueError("Bad symbol format")),
        }
        with patch.multiple("tvkit.api.chart.ohlcv", **patches):
            with pytest.raises(ValueError, match="Bad symbol format"):
                await client.get_historical_ohlcv(
                    exchange_symbol="BAD-FORMAT", interval="1D", bars_count=10
                )

    @pytest.mark.asyncio
    async def test_malformed_timescale_update_skipped_gracefully(self) -> None:
        """Malformed timescale_update (inner ValidationError) is skipped, not crashed."""
        messages: list[dict[str, Any]] = [
            {"m": "timescale_update", "p": ["cs_xxx", "not_a_dict"]},
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(RuntimeError, match="No historical data received"):
                await client.get_historical_ohlcv(
                    exchange_symbol=SYMBOL, interval="1D", bars_count=100
                )

    @pytest.mark.asyncio
    async def test_malformed_websocket_frame_skipped_gracefully(self) -> None:
        """Message missing 'm' key (outer except Exception) is skipped, not crashed."""
        messages: list[dict[str, Any]] = [
            {"no_m_key": True, "p": []},
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(RuntimeError, match="No historical data received"):
                await client.get_historical_ohlcv(
                    exchange_symbol=SYMBOL, interval="1D", bars_count=100
                )

    @pytest.mark.asyncio
    async def test_zero_bars_count_raises_value_error(self) -> None:
        """bars_count=0 raises ValueError before opening the WebSocket."""
        client: OHLCV = OHLCV()
        client._prepare_chart_session = AsyncMock()  # type: ignore[method-assign]

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            pytest.raises(ValueError, match="bars_count must be a positive integer"),
        ):
            await client.get_historical_ohlcv(exchange_symbol=SYMBOL, interval="1D", bars_count=0)

        client._prepare_chart_session.assert_not_called()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_negative_bars_count_raises_value_error(self) -> None:
        """bars_count=-1 raises ValueError before opening the WebSocket."""
        client: OHLCV = OHLCV()
        client._prepare_chart_session = AsyncMock()  # type: ignore[method-assign]

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            pytest.raises(ValueError, match="bars_count must be a positive integer"),
        ):
            await client.get_historical_ohlcv(exchange_symbol=SYMBOL, interval="1D", bars_count=-1)

        client._prepare_chart_session.assert_not_called()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_unexpected_exception_in_stream_propagates(self) -> None:
        """RuntimeError raised by the stream generator propagates out of the method.

        An exception raised by get_data_stream() during iteration fires outside the inner
        try/except block (which only wraps message processing). It propagates to the caller.
        """
        stream_error: RuntimeError = RuntimeError("connection dropped unexpectedly")
        client: OHLCV = OHLCV()
        client._prepare_chart_session = AsyncMock()  # type: ignore[method-assign]
        client.connection_service = MagicMock()
        client.connection_service.get_data_stream = lambda: broken_stream(
            messages=[make_timescale_update(bars_count=3)],
            error=stream_error,
        )
        client.connection_service.close = AsyncMock()

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(RuntimeError, match="connection dropped unexpectedly"):
                await client.get_historical_ohlcv(
                    exchange_symbol=SYMBOL, interval="1D", bars_count=100
                )


# ─────────────────────────────────────────────────────────────────────────────
# Class 5: timeout safety-net path
# ─────────────────────────────────────────────────────────────────────────────


class TestTimeoutBehavior:
    """Timeout is a safety net for network stalls — collected bars are returned normally."""

    @pytest.mark.asyncio
    async def test_timeout_returns_collected_bars(self) -> None:
        """When timeout fires mid-stream, already-collected bars are returned without error."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),
            SERIES_LOADING_MSG,  # second message: timeout check fires here
        ]
        client: OHLCV = _make_client(messages)

        mock_loop: MagicMock = MagicMock()
        # start=0.0, iteration-1 check=0.5 (no timeout), iteration-2 check=31.0 → timeout
        mock_loop.time.side_effect = [0.0, 0.5, 31.0]

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            patch("asyncio.get_running_loop", return_value=mock_loop),
        ):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=100
            )

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_timeout_with_no_bars_raises_runtime_error(self) -> None:
        """Timeout with zero bars collected raises RuntimeError."""
        messages: list[dict[str, Any]] = [
            SERIES_LOADING_MSG,
            SERIES_LOADING_MSG,  # second message: timeout check fires here
        ]
        client: OHLCV = _make_client(messages)

        mock_loop: MagicMock = MagicMock()
        # start=0.0, iteration-1 check=0.5 (no timeout), iteration-2 check=31.0 → timeout
        mock_loop.time.side_effect = [0.0, 0.5, 31.0]

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            patch("asyncio.get_running_loop", return_value=mock_loop),
        ):
            with pytest.raises(RuntimeError, match="No historical data received"):
                await client.get_historical_ohlcv(
                    exchange_symbol=SYMBOL, interval="1D", bars_count=100
                )

    @pytest.mark.asyncio
    async def test_timeout_does_not_explicitly_call_close(self) -> None:
        """On timeout, connection_service.close() is NOT called by get_historical_ohlcv.

        Cleanup is the caller's responsibility via 'async with OHLCV() as client:'.
        If a finally: close() is ever added to the method, this test fails — making
        the behaviour change visible and deliberate.
        """
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=3),
            SERIES_LOADING_MSG,  # second message: timeout check fires here
        ]
        client: OHLCV = _make_client(messages)

        mock_loop: MagicMock = MagicMock()
        # start=0.0, iteration-1 check=0.5 (no timeout), iteration-2 check=31.0 → timeout
        mock_loop.time.side_effect = [0.0, 0.5, 31.0]

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            patch("asyncio.get_running_loop", return_value=mock_loop),
        ):
            await client.get_historical_ohlcv(exchange_symbol=SYMBOL, interval="1D", bars_count=100)

        client.connection_service.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_stream_exhaustion_without_signals_returns_bars(self) -> None:
        """When the stream generator exhausts naturally (no signals), collected bars returned."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=3),
            # No series_completed, no study_completed — stream just ends
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=100
            )

        assert len(result) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Class 6: session lifecycle — setup, argument passing, close assertions
# ─────────────────────────────────────────────────────────────────────────────


class TestSessionLifecycle:
    """Session setup, argument passing, and resource cleanup assertions."""

    @pytest.mark.asyncio
    async def test_prepare_chart_session_called_with_correct_args(self) -> None:
        """_prepare_chart_session is called once with (converted_symbol, interval, bars_count)."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            await client.get_historical_ohlcv(exchange_symbol=SYMBOL, interval="1D", bars_count=5)

        client._prepare_chart_session.assert_called_once_with(  # type: ignore[union-attr]
            SYMBOL, "1D", 5, range_param=""
        )

    @pytest.mark.asyncio
    async def test_validate_symbols_called_with_original_symbol(self) -> None:
        """validate_symbols is called with the original (unconverted) exchange_symbol."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        validate_symbols_mock: AsyncMock = AsyncMock(return_value=True)
        patches: dict[str, Any] = {
            **make_patches(),
            "validate_symbols": validate_symbols_mock,
        }
        original_symbol: str = "BINANCE:BTCUSDT"

        with patch.multiple("tvkit.api.chart.ohlcv", **patches):
            await client.get_historical_ohlcv(
                exchange_symbol=original_symbol, interval="1D", bars_count=5
            )

        validate_symbols_mock.assert_called_once_with(original_symbol)

    @pytest.mark.asyncio
    async def test_connection_service_close_called_on_series_error(self) -> None:
        """series_error triggers connection_service.close() before raising ValueError."""
        messages: list[dict[str, Any]] = [SERIES_ERROR_MSG]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(ValueError):
                await client.get_historical_ohlcv(
                    exchange_symbol=SYMBOL, interval="1D", bars_count=10
                )

        client.connection_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_series_completed_success_does_not_call_close(self) -> None:
        """Normal success path (series_completed) does NOT call connection_service.close().

        Cleanup is the caller's responsibility via 'async with OHLCV() as client:'.
        If close() is accidentally added to the success path, this test catches it.
        """
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            await client.get_historical_ohlcv(exchange_symbol=SYMBOL, interval="1D", bars_count=100)

        client.connection_service.close.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Class 7: Range mode — start/end date range queries
# ─────────────────────────────────────────────────────────────────────────────


class TestRangeMode:
    """Tests for get_historical_ohlcv() range mode (start/end parameters)."""

    @pytest.mark.asyncio
    async def test_range_mode_returns_all_bars_until_series_completed(self) -> None:
        """Range mode collects all bars and terminates on series_completed."""
        messages: list[dict[str, Any]] = [
            SERIES_LOADING_MSG,
            make_timescale_update(bars_count=10),
            make_timescale_update(bars_count=5),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", start="2024-01-01", end="2024-12-31"
            )

        assert len(result) == 15

    @pytest.mark.asyncio
    async def test_range_mode_passes_range_param_to_prepare_chart_session(self) -> None:
        """Range mode passes a non-empty range_param to _prepare_chart_session."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=3),
            SERIES_COMPLETED_MSG,
        ]
        prepare_mock: AsyncMock = AsyncMock()
        client: OHLCV = OHLCV()
        client._prepare_chart_session = prepare_mock  # type: ignore[method-assign]
        client.connection_service = MagicMock()
        client.connection_service.get_data_stream = lambda: fake_stream(messages)
        client.connection_service.close = AsyncMock()

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", start="2024-01-01", end="2024-12-31"
            )

        call_kwargs = prepare_mock.call_args
        assert call_kwargs is not None
        range_param_value: str = call_kwargs.kwargs["range_param"]
        assert range_param_value.startswith("r,")
        assert ":" in range_param_value

    @pytest.mark.asyncio
    async def test_range_mode_uses_max_bars_request_for_create_series(self) -> None:
        """Range mode passes MAX_BARS_REQUEST as bars_count to _prepare_chart_session."""
        from tvkit.api.chart.utils import MAX_BARS_REQUEST

        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=3),
            SERIES_COMPLETED_MSG,
        ]
        prepare_mock: AsyncMock = AsyncMock()
        client: OHLCV = OHLCV()
        client._prepare_chart_session = prepare_mock  # type: ignore[method-assign]
        client.connection_service = MagicMock()
        client.connection_service.get_data_stream = lambda: fake_stream(messages)
        client.connection_service.close = AsyncMock()

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", start="2024-01-01", end="2024-12-31"
            )

        call_args = prepare_mock.call_args
        assert call_args is not None
        effective_bars_count: int = call_args.args[2]
        assert effective_bars_count == MAX_BARS_REQUEST

    @pytest.mark.asyncio
    async def test_range_mode_does_not_break_early_on_bar_count(self) -> None:
        """Range mode does not break early when bar count exceeds MAX_BARS_REQUEST.

        Even if more bars arrive than MAX_BARS_REQUEST, range mode must wait
        for series_completed — the count-based early exit must not fire.
        """
        from tvkit.api.chart.utils import MAX_BARS_REQUEST

        # Produce more bars than MAX_BARS_REQUEST in a single batch
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=MAX_BARS_REQUEST + 1),
            make_timescale_update(bars_count=2),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", start="2024-01-01", end="2024-12-31"
            )

        # All bars from both batches should be returned
        assert len(result) == MAX_BARS_REQUEST + 3

    @pytest.mark.asyncio
    async def test_range_mode_start_after_end_raises_value_error(self) -> None:
        """start > end raises ValueError before the WebSocket is opened."""
        prepare_mock: AsyncMock = AsyncMock()
        client: OHLCV = OHLCV()
        client._prepare_chart_session = prepare_mock  # type: ignore[method-assign]

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            pytest.raises(ValueError),
        ):
            await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", start="2024-12-31", end="2024-01-01"
            )

        prepare_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_range_mode_only_start_raises_value_error(self) -> None:
        """Providing only start (without end) raises ValueError before the WebSocket."""
        prepare_mock: AsyncMock = AsyncMock()
        client: OHLCV = OHLCV()
        client._prepare_chart_session = prepare_mock  # type: ignore[method-assign]

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            pytest.raises(ValueError, match="Both start and end must be provided"),
        ):
            await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", start="2024-01-01"
            )

        prepare_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_range_mode_only_end_raises_value_error(self) -> None:
        """Providing only end (without start) raises ValueError before the WebSocket."""
        prepare_mock: AsyncMock = AsyncMock()
        client: OHLCV = OHLCV()
        client._prepare_chart_session = prepare_mock  # type: ignore[method-assign]

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            pytest.raises(ValueError, match="Both start and end must be provided"),
        ):
            await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", end="2024-12-31"
            )

        prepare_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_range_and_bars_count_together_raises_value_error(self) -> None:
        """Specifying both bars_count and start/end raises ValueError."""
        prepare_mock: AsyncMock = AsyncMock()
        client: OHLCV = OHLCV()
        client._prepare_chart_session = prepare_mock  # type: ignore[method-assign]

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            pytest.raises(ValueError, match="Cannot specify both bars_count and start/end"),
        ):
            await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL,
                interval="1D",
                bars_count=100,
                start="2024-01-01",
                end="2024-12-31",
            )

        prepare_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_params_raises_value_error(self) -> None:
        """Providing neither bars_count nor start/end raises ValueError."""
        prepare_mock: AsyncMock = AsyncMock()
        client: OHLCV = OHLCV()
        client._prepare_chart_session = prepare_mock  # type: ignore[method-assign]

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            pytest.raises(ValueError, match="Either bars_count or both start and end"),
        ):
            await client.get_historical_ohlcv(exchange_symbol=SYMBOL, interval="1D")

        prepare_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_range_mode_partial_bars_is_not_an_error(self) -> None:
        """Range mode with fewer bars than the window spans is not an error (weekends, holidays).

        Unlike count mode, range mode does not log a partial-data warning when fewer bars
        are returned than the window could theoretically contain.
        """
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=2),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", start="2024-01-01", end="2024-12-31"
            )

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_range_mode_zero_bars_raises_runtime_error(self) -> None:
        """Range mode with no bars returned raises RuntimeError (same as count mode)."""
        messages: list[dict[str, Any]] = [SERIES_COMPLETED_MSG]
        client: OHLCV = _make_client(messages)

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            pytest.raises(RuntimeError, match="No historical data received"),
        ):
            await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", start="2024-01-01", end="2024-12-31"
            )

    @pytest.mark.asyncio
    async def test_range_mode_does_not_timeout_at_31s(self) -> None:
        """Range mode (180s) is NOT terminated at 31s — count mode (30s) would have fired here."""
        from tvkit.api.chart.ohlcv import _HISTORICAL_RANGE_TIMEOUT_SECONDS

        assert _HISTORICAL_RANGE_TIMEOUT_SECONDS == 180

        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=3),
            SERIES_LOADING_MSG,  # 2nd iteration: time check → 31.0 s (no timeout)
            SERIES_COMPLETED_MSG,  # 3rd iteration: clean exit via series_completed
        ]
        client: OHLCV = _make_client(messages)

        mock_loop: MagicMock = MagicMock()
        # start=0.0, check at msg-1=31.0 (31>180? NO), check at msg-2=32.0 (32>180? NO),
        # check at msg-3=33.0 → series_completed breaks before timeout fires.
        # Extra value pads against StopIteration if a future impl adds a loop.time() call.
        mock_loop.time.side_effect = [0.0, 31.0, 32.0, 33.0, 34.0]

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            patch("asyncio.get_running_loop", return_value=mock_loop),
        ):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", start="2024-01-01", end="2024-12-31"
            )

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_range_mode_timeout_triggers_at_181s(self) -> None:
        """Range mode (180s) IS terminated at 181s; collected bars are returned without error."""
        from tvkit.api.chart.ohlcv import _HISTORICAL_RANGE_TIMEOUT_SECONDS

        assert _HISTORICAL_RANGE_TIMEOUT_SECONDS == 180

        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=3),
            SERIES_LOADING_MSG,  # 2nd: 31.0 s — no timeout
            SERIES_LOADING_MSG,  # 3rd: 100.0 s — no timeout
            SERIES_LOADING_MSG,  # 4th: 181.0 s — TIMEOUT fires; loop breaks
        ]
        client: OHLCV = _make_client(messages)

        mock_loop: MagicMock = MagicMock()
        # start=0.0, check-1=31.0 (NO), check-2=100.0 (NO), check-3=181.0 (YES → break).
        # Extra value pads against StopIteration if a future impl adds a loop.time() call.
        mock_loop.time.side_effect = [0.0, 31.0, 100.0, 181.0, 182.0]

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            patch("asyncio.get_running_loop", return_value=mock_loop),
        ):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", start="2024-01-01", end="2024-12-31"
            )

        # Bars collected before timeout are returned without raising
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_stream_ends_without_series_completed_emits_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When range-mode stream ends without series_completed, a WARNING is logged."""
        import logging

        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),
            # No series_completed — stream ends naturally
        ]
        client: OHLCV = _make_client(messages)

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            caplog.at_level(logging.WARNING, logger="tvkit.api.chart.ohlcv"),
        ):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", start="2024-01-01", end="2024-12-31"
            )

        assert len(result) == 5
        assert any(
            r.levelname == "WARNING" and "series_completed" in r.getMessage()
            for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_range_mode_empty_stream_raises_runtime_error(self) -> None:
        """Range mode with an empty stream (no messages at all) raises RuntimeError.

        Unlike zero-bars-after-series_completed, an empty stream never enters the loop.
        The incomplete-stream warning is also emitted (no series_completed received).
        """
        messages: list[dict[str, Any]] = []
        client: OHLCV = _make_client(messages)

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **make_patches()),
            pytest.raises(RuntimeError, match="No historical data received"),
        ):
            await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", start="2024-01-01", end="2024-12-31"
            )
