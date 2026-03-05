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
    async def test_zero_bars_count_requested_documents_behaviour(self) -> None:
        """bars_count=0 documents evaluation order: extend runs before the count check.

        Since extend runs before 'if len >= bars_count: break', the first timescale_update
        batch is always added before the count check fires (5 >= 0 is True). Changing
        evaluation order would break this test — making the refactoring visible.
        """
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=0
            )

        # extend fires first, then 5 >= 0 → break
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_negative_bars_count_documents_behaviour(self) -> None:
        """bars_count=-1 documents the same extend-before-check order as bars_count=0.

        len(bars) >= -1 is always True. The first timescale_update batch is added,
        then the count check fires. Negative bars_count is not validated at the method
        boundary; this test pins the current observable result.
        """
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),
            SERIES_COMPLETED_MSG,
        ]
        client: OHLCV = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            result = await client.get_historical_ohlcv(
                exchange_symbol=SYMBOL, interval="1D", bars_count=-1
            )

        assert len(result) == 5

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
            SYMBOL, "1D", 5
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
