"""
Tests for how tvkit reports TradingView's refusals of a chart-series request (issue #59).

TradingView refuses a series with a ``symbol_error`` and/or a ``series_error`` frame.
These tests pin how those frames become ``SeriesError`` / ``EntitlementError`` in every
message loop: count mode, range mode, ``get_ohlcv()`` and ``get_quote_data()``.

The frame payloads are the ones TradingView sent to an anonymous session on 2026-09-24,
with server ids replaced. No real network calls — all I/O is mocked.
"""

import copy
import logging
import pickle
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import tvkit.api.chart as chart_api
from tvkit.api.chart import exceptions as chart_exceptions
from tvkit.api.chart.exceptions import ChartError, EntitlementError, SeriesError
from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.api.chart.ohlcv import (
    OHLCV,
    _is_entitlement_reason,
    _series_refusal,
    _StreamingSession,
)

SYMBOL: str = "ECONOMICS:USM2"
SERVER: str = "srv-1@srv-1"
ENTITLEMENT_SUFFIX: str = (
    ". The session is not entitled to this data; retrying the same request will not help."
)

# ── Frames TradingView sent on 2026-09-24 (anonymous session) ───────────────────────

SERIES_LOADING: dict[str, Any] = {"m": "series_loading", "p": ["cs_test", "sds_1", "s1"]}
SYMBOL_ERROR_PERMISSION: dict[str, Any] = {
    "m": "symbol_error",
    "p": ["cs_test", "sds_sym_1", "permission denied", "group", "economics_paid"],
}
SERIES_ERROR_RESOLVE: dict[str, Any] = {
    "m": "series_error",
    "p": ["cs_test", "sds_1", "s1", "resolve error", SERVER],
}
QSD_PERMISSION_DENIED: dict[str, Any] = {
    "m": "qsd",
    "p": [
        "qs_test",
        {
            "n": '={"adjustment":"splits","backadjustment":"default","symbol":"ECONOMICS:USM2"}',
            "s": "permission_denied",
            "errmsg": "Permission denied",
            "v": {"alternative": "economics_paid"},
        },
    ],
}
QUOTE_COMPLETED: dict[str, Any] = {
    "m": "quote_completed",
    "p": [
        "qs_test",
        '={"adjustment":"splits","backadjustment":"default","symbol":"ECONOMICS:USM2"}',
    ],
}
STUDY_ERROR: dict[str, Any] = {
    "m": "study_error",
    "p": ["cs_test", "st1", "s1_st1", "check study unexpected error", SERVER],
}
SERIES_COMPLETED: dict[str, Any] = {
    "m": "series_completed",
    "p": ["cs_test", "sds_1", "streaming", "s1", {"rt_update_period": 5}],
}

# What TradingView sent for ECONOMICS:USM2 (and FRED:M2SL), in arrival order.
ISSUE_59_BATCH: list[dict[str, Any]] = [
    SERIES_LOADING,
    SYMBOL_ERROR_PERMISSION,
    SERIES_ERROR_RESOLVE,
    QSD_PERMISSION_DENIED,
    QUOTE_COMPLETED,
    STUDY_ERROR,
]

SYMBOL_ERROR_INVALID: dict[str, Any] = {
    "m": "symbol_error",
    "p": ["cs_test", "sds_sym_1", "invalid symbol"],
}
SERIES_ERROR_SECONDS: dict[str, Any] = {
    "m": "series_error",
    "p": ["cs_test", "sds_1", "s1", "seconds_not_entitled", "undefined"],
}
SERIES_ERROR_UNSUPPORTED: dict[str, Any] = {
    "m": "series_error",
    "p": ["cs_test", "sds_1", "s1", "unsupported resolution: INDEX:NDFI, 5", SERVER],
}
SERIES_ERROR_CUSTOM: dict[str, Any] = {
    "m": "series_error",
    "p": ["cs_test", "sds_1", "s1", "custom_resolution", "undefined"],
}


# ── Helpers ────────────────────────────────────────────────────────────────────────


def make_timescale_update(bars_count: int, base_ts: float = 1_704_067_200.0) -> dict[str, Any]:
    """Build a timescale_update carrying ``bars_count`` daily bars."""
    series: list[dict[str, Any]] = [
        {"i": i, "v": [base_ts + i * 86_400, 100.0, 105.0, 95.0, 102.0, 1_000.0]}
        for i in range(bars_count)
    ]
    return {"m": "timescale_update", "p": ["cs_test", {"sds_1": {"s": series}}]}


async def fake_stream(messages: list[dict[str, Any]]) -> AsyncGenerator[dict[str, Any], None]:
    """Yield a fixed sequence of parsed frames."""
    for message in messages:
        yield message


def make_client(messages: list[dict[str, Any]]) -> OHLCV:
    """Return an OHLCV client whose connection yields ``messages``; services are mocked."""
    client: OHLCV = OHLCV()
    client._prepare_chart_session = AsyncMock()  # type: ignore[method-assign]
    client._session = _StreamingSession(
        symbol=SYMBOL,
        interval="1D",
        bars_count=100,
        quote_session="qs_test",
        chart_session="cs_test",
    )
    client.connection_service = MagicMock()
    client.connection_service.get_data_stream = lambda: fake_stream(messages)
    client.connection_service.close = AsyncMock()
    client.message_service = MagicMock()
    client.message_service.send_message = AsyncMock()
    return client


def make_patches(symbol: str = SYMBOL) -> dict[str, Any]:
    """Mocks for the module-level validation helpers used before the stream starts."""
    return {
        "validate_symbols": AsyncMock(return_value=True),
        "normalize_symbol": MagicMock(return_value=symbol),
        "validate_interval": MagicMock(),
    }


# ─────────────────────────────────────────────────────────────────────────────────────
# _series_refusal / _is_entitlement_reason
# ─────────────────────────────────────────────────────────────────────────────────────


class TestSeriesRefusal:
    """Frame → exception mapping, message wording and payload robustness."""

    def test_permission_denied_is_an_entitlement_error(self) -> None:
        """The #59 frame names TradingView's reason instead of blaming the interval."""
        error = _series_refusal(SYMBOL_ERROR_PERMISSION, symbol=SYMBOL, interval="1D")

        assert type(error) is EntitlementError
        assert str(error) == (
            "TradingView could not resolve symbol 'ECONOMICS:USM2': "
            "permission denied (group economics_paid)" + ENTITLEMENT_SUFFIX
        )
        assert error.symbol == SYMBOL
        assert error.interval == "1D"
        assert error.message_type == "symbol_error"
        assert error.reason == "permission denied"
        assert error.details == ("group", "economics_paid")
        assert "Invalid interval" not in str(error)
        assert "bars" not in str(error)

    def test_invalid_symbol_is_a_plain_series_error(self) -> None:
        error = _series_refusal(
            SYMBOL_ERROR_INVALID, symbol="NASDAQ:INVALID_FAKE_XYZ", interval="1D"
        )

        assert type(error) is SeriesError
        assert str(error) == (
            "TradingView could not resolve symbol 'NASDAQ:INVALID_FAKE_XYZ': invalid symbol"
        )
        assert error.reason == "invalid symbol"
        assert error.details == ()

    @pytest.mark.parametrize("reason", ["seconds_not_entitled", "ticks_not_entitled"])
    def test_not_entitled_series_errors_are_entitlement_errors(self, reason: str) -> None:
        frame: dict[str, Any] = {
            "m": "series_error",
            "p": ["cs_test", "sds_1", "s1", reason, "undefined"],
        }
        error = _series_refusal(frame, symbol="NASDAQ:AAPL", interval="1S")

        assert type(error) is EntitlementError
        assert str(error) == (
            f"TradingView series error for 'NASDAQ:AAPL' (interval '1S'): {reason}"
            + ENTITLEMENT_SUFFIX
        )
        assert error.message_type == "series_error"
        assert error.details == ("undefined",)

    def test_unsupported_resolution_names_the_interval_problem(self) -> None:
        error = _series_refusal(SERIES_ERROR_UNSUPPORTED, symbol="INDEX:NDFI", interval="5")

        assert type(error) is SeriesError
        assert str(error) == (
            "TradingView series error for 'INDEX:NDFI' (interval '5'): "
            "unsupported resolution: INDEX:NDFI, 5 "
            "(the interval is not supported for this symbol)"
        )

    def test_custom_resolution_is_not_an_entitlement_error(self) -> None:
        error = _series_refusal(SERIES_ERROR_CUSTOM, symbol="NASDAQ:AAPL", interval="2D")

        assert type(error) is SeriesError
        assert str(error) == (
            "TradingView series error for 'NASDAQ:AAPL' (interval '2D'): "
            "custom_resolution (TradingView refused this custom interval)"
        )

    def test_resolve_error_alone_says_the_symbol_could_not_be_resolved(self) -> None:
        error = _series_refusal(SERIES_ERROR_RESOLVE, symbol=SYMBOL, interval="1D")

        assert type(error) is SeriesError
        assert str(error) == (
            "TradingView series error for 'ECONOMICS:USM2' (interval '1D'): "
            "resolve error (the symbol could not be resolved)"
        )

    def test_unknown_reason_is_reported_verbatim(self) -> None:
        frame: dict[str, Any] = {
            "m": "series_error",
            "p": ["cs_test", "sds_1", "s1", "something new", SERVER],
        }
        error = _series_refusal(frame, symbol="NASDAQ:AAPL", interval="1D")

        assert type(error) is SeriesError
        assert str(error) == (
            "TradingView series error for 'NASDAQ:AAPL' (interval '1D'): something new"
        )

    def test_series_error_server_id_is_kept_in_details_not_in_message(self) -> None:
        error = _series_refusal(SERIES_ERROR_RESOLVE, symbol=SYMBOL, interval="1D")

        assert SERVER not in str(error)
        assert error.details == (SERVER,)

    @pytest.mark.parametrize(
        "frame",
        [
            {"m": "series_error"},
            {"m": "series_error", "p": None},
            {"m": "series_error", "p": "not a list"},
            {"m": "series_error", "p": []},
            {"m": "series_error", "p": ["cs_test", "sds_1", "s1"]},
            {"m": "symbol_error", "p": ["cs_test", "sds_sym_1"]},
            {"m": "series_error", "p": ["cs_test", "sds_1", "s1", "   "]},
        ],
        ids=["no-p", "p-none", "p-str", "p-empty", "series-short", "symbol-short", "blank"],
    )
    def test_malformed_frames_fall_back_instead_of_raising(self, frame: dict[str, Any]) -> None:
        """An unusable payload still yields an exception to raise — never an IndexError."""
        error = _series_refusal(frame, symbol="NASDAQ:AAPL", interval="1D")

        assert type(error) is SeriesError
        assert error.reason == "no reason given"
        assert str(error).endswith(": no reason given")

    def test_non_string_payload_items_are_stringified(self) -> None:
        frame: dict[str, Any] = {"m": "symbol_error", "p": [None, 7, {"k": "v"}, ["x"], 3.5]}
        error = _series_refusal(frame, symbol="NASDAQ:AAPL", interval="1D")

        assert error.reason == "{'k': 'v'}"
        assert error.details == ("['x']", "3.5")

    @pytest.mark.parametrize(
        ("reason", "expected"),
        [
            ("permission denied", True),
            ("Permission Denied", True),
            ("permission_denied", True),
            ("seconds_not_entitled", True),
            ("ticks_not_entitled", True),
            ("invalid symbol", False),
            ("resolve error", False),
            ("custom_resolution", False),
            ("unsupported resolution: INDEX:NDFI, 5", False),
            ("", False),
        ],
    )
    def test_is_entitlement_reason(self, reason: str, expected: bool) -> None:
        assert _is_entitlement_reason(reason) is expected


# ─────────────────────────────────────────────────────────────────────────────────────
# Exception classes
# ─────────────────────────────────────────────────────────────────────────────────────


class TestExceptionClasses:
    """Hierarchy, serialization and public exports of the new exceptions."""

    def test_hierarchy(self) -> None:
        """ValueError keeps old ``except ValueError`` callers and tvkit.batch non-retryable."""
        assert issubclass(EntitlementError, SeriesError)
        assert issubclass(SeriesError, ValueError)
        assert not issubclass(SeriesError, ChartError)
        assert not issubclass(EntitlementError, OSError)  # PermissionError is an OSError

    def test_pickle_and_copy_round_trip(self) -> None:
        error = _series_refusal(SYMBOL_ERROR_PERMISSION, symbol=SYMBOL, interval="1D")

        for clone in (pickle.loads(pickle.dumps(error)), copy.copy(error), copy.deepcopy(error)):
            assert type(clone) is EntitlementError
            assert str(clone) == str(error)
            assert clone.symbol == SYMBOL
            assert clone.interval == "1D"
            assert clone.message_type == "symbol_error"
            assert clone.reason == "permission denied"
            assert clone.details == ("group", "economics_paid")

    def test_public_exports(self) -> None:
        assert chart_api.SeriesError is SeriesError
        assert chart_api.EntitlementError is EntitlementError
        assert {"SeriesError", "EntitlementError"} <= set(chart_api.__all__)
        assert {"SeriesError", "EntitlementError"} <= set(chart_exceptions.__all__)


# ─────────────────────────────────────────────────────────────────────────────────────
# get_historical_ohlcv — count mode and range mode
# ─────────────────────────────────────────────────────────────────────────────────────


class TestHistoricalFetch:
    """Refusals in the count-mode and range-mode message loops."""

    @pytest.mark.asyncio
    async def test_count_mode_issue_59_batch_raises_entitlement_error(self) -> None:
        client: OHLCV = make_client(ISSUE_59_BATCH)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(EntitlementError) as exc_info:
                await client.get_historical_ohlcv(SYMBOL, "1D", bars_count=2000)

        error = exc_info.value
        assert error.message_type == "symbol_error"
        assert error.reason == "permission denied"
        assert error.details == ("group", "economics_paid")
        assert "Invalid interval" not in str(error)
        client.connection_service.close.assert_awaited_once()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_range_mode_issue_59_batch_raises_entitlement_error(self) -> None:
        client: OHLCV = make_client(ISSUE_59_BATCH)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(EntitlementError) as exc_info:
                await client.get_historical_ohlcv(
                    SYMBOL, "1D", start="2024-01-01", end="2024-06-30"
                )

        assert exc_info.value.reason == "permission denied"
        client.connection_service.close.assert_awaited_once()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_series_error_arriving_first_still_raises(self) -> None:
        """If the frames ever arrive reversed, the series_error alone still names the cause."""
        client: OHLCV = make_client([SERIES_ERROR_RESOLVE, SYMBOL_ERROR_PERMISSION])

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(SeriesError) as exc_info:
                await client.get_historical_ohlcv(SYMBOL, "1D", bars_count=100)

        assert type(exc_info.value) is SeriesError
        assert exc_info.value.reason == "resolve error"
        assert "the symbol could not be resolved" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_study_error_is_not_fatal(self) -> None:
        """study_error also arrives on successful fetches — the bars are still returned."""
        client: OHLCV = make_client([make_timescale_update(5), SERIES_COMPLETED, STUDY_ERROR])

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            bars: list[OHLCVBar] = await client.get_historical_ohlcv(SYMBOL, "1D", bars_count=100)

        assert len(bars) == 5
        client.connection_service.close.assert_not_called()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_malformed_refusal_frame_still_raises(self) -> None:
        """A refusal with an unusable payload is raised, never skipped.

        If it were skipped, the five bars that follow would satisfy ``bars_count=5``
        and the call would return normally.
        """
        client: OHLCV = make_client(
            [{"m": "symbol_error"}, make_timescale_update(5), SERIES_COMPLETED]
        )

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(SeriesError) as exc_info:
                await client.get_historical_ohlcv(SYMBOL, "1D", bars_count=5)

        assert exc_info.value.reason == "no reason given"

    @pytest.mark.asyncio
    async def test_close_failure_does_not_mask_the_refusal(self) -> None:
        client: OHLCV = make_client(ISSUE_59_BATCH)
        client.connection_service.close = AsyncMock(  # type: ignore[union-attr]
            side_effect=RuntimeError("socket already gone")
        )

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(EntitlementError):
                await client.get_historical_ohlcv(SYMBOL, "1D", bars_count=100)

        client.connection_service.close.assert_awaited_once()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_refusal_is_logged_once_at_error_level(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        client: OHLCV = make_client(ISSUE_59_BATCH)

        with caplog.at_level(logging.ERROR, logger="tvkit.api.chart.ohlcv"):
            with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
                with pytest.raises(EntitlementError):
                    await client.get_historical_ohlcv(SYMBOL, "1D", bars_count=100)

        errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
        assert len(errors) == 1
        assert "permission denied (group economics_paid)" in errors[0].getMessage()

    @pytest.mark.asyncio
    async def test_abort_without_connection_service_still_returns_the_error(self) -> None:
        """With no connection to close, the refusal is still built and returned."""
        client: OHLCV = OHLCV()
        assert client.connection_service is None

        error = await client._abort_series_refusal(
            SERIES_ERROR_UNSUPPORTED, symbol="INDEX:NDFI", interval="5"
        )

        assert type(error) is SeriesError
        assert error.reason == "unsupported resolution: INDEX:NDFI, 5"


# ─────────────────────────────────────────────────────────────────────────────────────
# get_ohlcv / get_quote_data — streaming
# ─────────────────────────────────────────────────────────────────────────────────────


class TestStreaming:
    """Refusals in the streaming loops, which used to swallow the error and end silently."""

    @pytest.mark.asyncio
    async def test_get_ohlcv_raises_entitlement_error(self) -> None:
        client: OHLCV = make_client(ISSUE_59_BATCH)

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(EntitlementError):
                async for _ in client.get_ohlcv(SYMBOL, "1D"):
                    pass

        client.connection_service.close.assert_awaited_once()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_get_ohlcv_yields_bars_then_raises(self) -> None:
        client: OHLCV = make_client([make_timescale_update(3), SERIES_ERROR_SECONDS])
        received: list[OHLCVBar] = []

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches("NASDAQ:AAPL")):
            with pytest.raises(EntitlementError) as exc_info:
                async for bar in client.get_ohlcv("NASDAQ:AAPL", "1S"):
                    received.append(bar)

        assert len(received) == 3
        assert exc_info.value.reason == "seconds_not_entitled"
        assert exc_info.value.interval == "1S"

    @pytest.mark.asyncio
    async def test_get_quote_data_raises_before_the_denied_quote(self) -> None:
        client: OHLCV = make_client(ISSUE_59_BATCH)
        received: list[Any] = []

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            with pytest.raises(EntitlementError):
                async for quote in client.get_quote_data(SYMBOL, "1D"):
                    received.append(quote)

        assert received == []
        client.connection_service.close.assert_awaited_once()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_streams_still_skip_malformed_frames(self) -> None:
        """Re-raising refusals must not stop the streams from skipping bad frames."""
        client: OHLCV = make_client(
            [
                {"m": "du", "p": ["cs_test", "not_a_dict"]},
                {"no_m_key": True},
                make_timescale_update(2),
            ]
        )

        with patch.multiple("tvkit.api.chart.ohlcv", **make_patches()):
            bars: list[OHLCVBar] = [bar async for bar in client.get_ohlcv(SYMBOL, "1D")]

        assert len(bars) == 2
