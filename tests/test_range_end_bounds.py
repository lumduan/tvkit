"""
Tests for the v0.16.0 range-mode contract: where the ``end`` bound is resolved, what the
merged create_series/modify_series result looks like, and that segment seams are exact.

- ``end="YYYY-MM-DD"`` (a date-only string) means the whole calendar day: the range sent
  to TradingView and the client-side filter both end at 23:59:59 UTC, so
  ``start == end`` returns that day's full intraday set.
- ``end=datetime(..., 0, 0)`` — naive or tz-aware — is an exact midnight boundary.
- In-range create_series bars are merged with the modify_series response. When a
  timestamp is received more than once, the LAST received copy wins.
- A range that produces several segments has no gap and no duplicate at any seam.

No live WebSocket connections — all external I/O is mocked. The seam tests drive the
public ``get_historical_ohlcv()`` through the real ``_fetch_single_range()`` against a
fake server that honours the ``r,<from>:<to>`` range it is sent.
"""

from __future__ import annotations

import re
import warnings
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta, tzinfo
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tvkit.api.chart.exceptions import NoHistoricalDataError
from tvkit.api.chart.ohlcv import OHLCV, _StreamingSession
from tvkit.api.chart.utils import MAX_BARS_REQUEST, end_of_day_timestamp, to_unix_timestamp

SYMBOL: str = "SSE:000001"

SERIES_COMPLETED_MSG: dict[str, Any] = {
    "m": "series_completed",
    "p": ["cs_xxx", "sds_1", "sds_sym_1", "ok"],
}


# ---------------------------------------------------------------------------
# Wire messages and fixtures
# ---------------------------------------------------------------------------


def make_timescale_update(
    stamps: list[int] | list[float], close: float = 1.5, volume: float = 100.0
) -> dict[str, Any]:
    """Build a fake timescale_update carrying one bar per timestamp in ``stamps``."""
    series: list[dict[str, Any]] = [
        {"i": i, "v": [float(ts), 1.0, 2.0, 0.5, close, volume]} for i, ts in enumerate(stamps)
    ]
    return {"m": "timescale_update", "p": ["cs_xxx", {"sds_1": {"s": series}}]}


def make_du_update(ts: float, close: float, volume: float) -> dict[str, Any]:
    """Build a fake 'du' data-update frame for the live bar at ``ts``."""
    return {
        "m": "du",
        "p": [
            "cs_xxx",
            {
                "sds_1": {
                    "s": [{"i": 0, "v": [float(ts), 1.0, 2.0, 0.5, close, volume]}],
                    "ns": {"d": "", "indexes": "nochange"},
                    "t": "s1",
                    "lbs": {"bar_close_time": int(ts + 60)},
                }
            },
        ],
    }


def sse_session_stamps(day: str) -> list[int]:
    """The 240 one-minute bar stamps of an SSE session (01:30–03:29 and 05:00–06:59 UTC)."""
    midnight: int = to_unix_timestamp(day)
    morning: list[int] = [midnight + 90 * 60 + i * 60 for i in range(120)]
    afternoon: list[int] = [midnight + 300 * 60 + i * 60 for i in range(120)]
    return morning + afternoon


async def fake_stream(messages: list[dict[str, Any]]) -> AsyncGenerator[dict[str, Any], None]:
    for msg in messages:
        yield msg


def _make_client(messages: list[dict[str, Any]] | None = None) -> OHLCV:
    """Return an OHLCV client wired for range-mode tests with mocked services."""
    client = OHLCV()
    client._prepare_chart_session = AsyncMock()  # type: ignore[method-assign]
    client._session = _StreamingSession(  # type: ignore[assignment]
        symbol=SYMBOL,
        interval="1",
        bars_count=MAX_BARS_REQUEST,
        quote_session="qs_test",
        chart_session="cs_test",
    )
    client.connection_service = MagicMock()
    if messages is not None:
        client.connection_service.get_data_stream = lambda: fake_stream(messages)
    client.connection_service.close = AsyncMock()
    client.message_service = MagicMock()  # type: ignore[assignment]
    return client


def _make_patches() -> dict[str, Any]:
    return {
        "validate_symbols": AsyncMock(return_value=True),
        "normalize_symbol": MagicMock(return_value=SYMBOL),
        "validate_interval": MagicMock(),
    }


def _range_param_bounds(client: OHLCV) -> tuple[int, int]:
    """(from, to) of the range_param passed to the latest _prepare_chart_session call."""
    call = client._prepare_chart_session.call_args  # type: ignore[attr-defined]
    assert call is not None, "_prepare_chart_session was not called"
    match = re.fullmatch(r"r,(\d+):(\d+)", call.kwargs["range_param"])
    assert match is not None, call.kwargs["range_param"]
    return int(match.group(1)), int(match.group(2))


# ===========================================================================
# A date-only end string means the whole calendar day
# ===========================================================================


class TestDateOnlyEndMeansWholeDay:
    """The whole-day intent is resolved once, at the API boundary, and applied to both
    the range sent to TradingView and the client-side filter."""

    @pytest.mark.asyncio
    async def test_same_day_date_only_range_returns_the_full_session(self) -> None:
        """start == end == "YYYY-MM-DD" → the day's 240 bars; server range ends 23:59:59.

        The day sits inside the create_series window, so modify_series returns nothing
        — the live shape of SSE:000001 on a recent day. v0.15.0 returned 19 bars for
        this input (or nothing) because the end was cut back to midnight.
        """
        day = "2026-09-04"
        stamps = sse_session_stamps(day)
        messages = [make_timescale_update(stamps), SERIES_COMPLETED_MSG, SERIES_COMPLETED_MSG]
        client = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            bars = await client.get_historical_ohlcv(SYMBOL, "1", start=day, end=day)

        assert len(bars) == 240
        assert [b.timestamp for b in bars] == stamps
        assert _range_param_bounds(client) == (to_unix_timestamp(day), end_of_day_timestamp(day))

    @pytest.mark.asyncio
    async def test_start_with_time_on_the_end_date_is_valid(self) -> None:
        """start="…T05:00Z", end="<same date>" → 05:00 to 23:59:59 (v0.15.0 raised)."""
        day = "2026-09-04"
        stamps = sse_session_stamps(day)
        messages = [SERIES_COMPLETED_MSG, make_timescale_update(stamps), SERIES_COMPLETED_MSG]
        client = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            bars = await client.get_historical_ohlcv(SYMBOL, "1", start=f"{day}T05:00:00Z", end=day)

        assert len(bars) == 120  # the afternoon session only
        assert bars[0].timestamp == to_unix_timestamp(f"{day}T05:00:00Z")
        assert _range_param_bounds(client) == (
            to_unix_timestamp(f"{day}T05:00:00Z"),
            end_of_day_timestamp(day),
        )

    @pytest.mark.asyncio
    async def test_string_end_with_time_is_exact(self) -> None:
        """end="YYYY-MM-DD HH:MM" is an exact, inclusive bound — no expansion."""
        day = "2026-09-04"
        end = f"{day} 03:00"
        stamps = sse_session_stamps(day)
        messages = [SERIES_COMPLETED_MSG, make_timescale_update(stamps), SERIES_COMPLETED_MSG]
        client = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            bars = await client.get_historical_ohlcv(SYMBOL, "1", start=day, end=end)

        assert len(bars) == 91  # 01:30 … 03:00 inclusive
        assert bars[-1].timestamp == to_unix_timestamp(end)
        assert _range_param_bounds(client)[1] == to_unix_timestamp(end)


# ===========================================================================
# A midnight datetime is an exact instant
# ===========================================================================


class TestMidnightDatetimeEndIsExact:
    """The leak reported in #55: an overnight window ending at an exact midnight used to
    return the whole following day through the create_series fallback."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tz", [UTC, None], ids=["aware", "naive"])
    async def test_overnight_window_ending_at_midnight_does_not_leak_next_day(
        self, tz: tzinfo | None
    ) -> None:
        """Window 08:00 → next day 00:00 with no bars inside → NoHistoricalDataError.

        create_series holds the next day's full session (240 bars); v0.15.0 returned all
        of them. Both bounds must reach the server range unchanged.
        """
        next_day_stamps = sse_session_stamps("2026-09-04")
        messages = [
            make_timescale_update(next_day_stamps),
            SERIES_COMPLETED_MSG,
            SERIES_COMPLETED_MSG,  # modify_series: nothing in the window
        ]
        client = _make_client(messages)
        start = datetime(2026, 9, 3, 8, 0, tzinfo=tz)
        end = datetime(2026, 9, 4, 0, 0, tzinfo=tz)

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", UserWarning)  # naive datetimes warn once
            with pytest.raises(NoHistoricalDataError):
                await client.get_historical_ohlcv(SYMBOL, "1", start=start, end=end)

        assert _range_param_bounds(client) == (
            to_unix_timestamp(datetime(2026, 9, 3, 8, 0, tzinfo=UTC)),
            to_unix_timestamp(datetime(2026, 9, 4, 0, 0, tzinfo=UTC)),
        )

    @pytest.mark.asyncio
    async def test_bar_at_exactly_midnight_is_kept_and_later_bars_are_not(self) -> None:
        """The midnight bound is inclusive: the 00:00 bar stays, the 00:01 bar goes."""
        midnight = to_unix_timestamp("2026-09-04")
        messages = [
            SERIES_COMPLETED_MSG,
            make_timescale_update([midnight - 60, midnight, midnight + 60]),
            SERIES_COMPLETED_MSG,
        ]
        client = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            bars = await client.get_historical_ohlcv(
                SYMBOL,
                "1",
                start=datetime(2026, 9, 3, 23, 0, tzinfo=UTC),
                end=datetime(2026, 9, 4, 0, 0, tzinfo=UTC),
            )

        assert [b.timestamp for b in bars] == [midnight - 60, midnight]


# ===========================================================================
# Merge of create_series and modify_series; last received wins
# ===========================================================================


class TestMergeAndDedup:
    @pytest.mark.asyncio
    async def test_straddling_range_merges_recent_and_older_slices(self) -> None:
        """create_series: the recent 220 bars; modify_series: the older 19 → 239.

        TradingView does not re-send bars it already delivered in the create_series
        response, so each slice arrives exactly once. Result is ascending and unique.
        """
        stamps = sse_session_stamps("2026-08-07")[:239]  # the live session had 239 bars
        older, recent = stamps[:19], stamps[19:]  # 19 + 220
        messages = [
            make_timescale_update(recent),  # create_series: most recent bars
            SERIES_COMPLETED_MSG,
            make_timescale_update(older),  # modify_series: only what was not sent yet
            SERIES_COMPLETED_MSG,
        ]
        client = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            bars = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2026-08-07", end="2026-08-07"
            )

        timestamps = [b.timestamp for b in bars]
        assert len(bars) == 239
        assert timestamps == stamps  # ascending, no duplicates, nothing lost

    @pytest.mark.asyncio
    async def test_modify_series_bar_supersedes_create_series_bar(self) -> None:
        """Same timestamp from both responses → the modify_series (later) copy survives."""
        ts = to_unix_timestamp("2026-08-07T01:30:00Z")
        messages = [
            make_timescale_update([ts], close=1.0, volume=10.0),  # create_series snapshot
            SERIES_COMPLETED_MSG,
            make_timescale_update([ts], close=3.0, volume=30.0),  # modify_series copy
            SERIES_COMPLETED_MSG,
        ]
        client = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            bars = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2026-08-07", end="2026-08-07"
            )

        assert len(bars) == 1
        assert (bars[0].close, bars[0].volume) == (3.0, 30.0)

    @pytest.mark.asyncio
    async def test_du_update_supersedes_timescale_bar_in_the_same_phase(self) -> None:
        """A 'du' update after the modify_series snapshot wins; one bar, not two."""
        ts = to_unix_timestamp("2026-08-07T01:30:00Z")
        messages = [
            SERIES_COMPLETED_MSG,
            make_timescale_update([ts], close=3.0, volume=30.0),
            make_du_update(ts, close=4.0, volume=40.0),
            SERIES_COMPLETED_MSG,
        ]
        client = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            bars = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2026-08-07", end="2026-08-07"
            )

        assert len(bars) == 1
        assert (bars[0].close, bars[0].volume) == (4.0, 40.0)

    @pytest.mark.asyncio
    async def test_du_update_supersedes_create_series_snapshot(self) -> None:
        """A 'du' update in the modify phase beats the create_series snapshot of the live bar."""
        ts = to_unix_timestamp("2026-08-07T06:59:00Z")
        messages = [
            make_timescale_update([ts], close=1.0, volume=10.0),  # create_series snapshot
            SERIES_COMPLETED_MSG,
            make_du_update(ts, close=4.0, volume=40.0),  # later update, same bar
            SERIES_COMPLETED_MSG,
        ]
        client = _make_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            bars = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2026-08-07", end="2026-08-07"
            )

        assert len(bars) == 1
        assert (bars[0].close, bars[0].volume) == (4.0, 40.0)


# ===========================================================================
# Segment seams
# ===========================================================================


class TestSegmentSeams:
    """Real _fetch_single_range per segment against a fake server that honours the
    r,<from>:<to> it is sent. Segmentation is forced through the public API by a fake
    authenticated account with a tiny max_bars (read by _needs_segmentation and
    SegmentedFetchService._resolve_max_bars)."""

    @staticmethod
    def _client_with_max_bars(max_bars: int) -> OHLCV:
        client = _make_client()
        client._auth_manager = SimpleNamespace(  # type: ignore[assignment]
            account=SimpleNamespace(max_bars=max_bars, max_bars_source="test")
        )
        return client

    @staticmethod
    def _install_server(
        client: OHLCV, stamps: list[int], *, recent_window: int, resend_recent: bool
    ) -> None:
        """Fake TradingView: create_series returns the newest ``recent_window`` bars
        regardless of the range; modify_series returns the bars inside [from, to] —
        all of them, or only those create_series did not already send."""
        recent = stamps[-recent_window:]

        async def stream() -> AsyncGenerator[dict[str, Any], None]:
            lo, hi = _range_param_bounds(client)
            in_range = [ts for ts in stamps if lo <= ts <= hi]
            modify = in_range if resend_recent else [ts for ts in in_range if ts not in recent]
            yield make_timescale_update(recent)
            yield SERIES_COMPLETED_MSG
            if modify:
                yield make_timescale_update(modify)
            yield SERIES_COMPLETED_MSG

        client.connection_service.get_data_stream = stream  # type: ignore[union-attr]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "resend_recent", [True, False], ids=["server-resends", "server-omits-create-bars"]
    )
    async def test_three_hourly_segments_have_no_gap_and_no_duplicate(
        self, resend_recent: bool
    ) -> None:
        """12 hourly bars, max_bars=4 → 3 segments [00–03], [04–07], [08–11]: exact grid."""
        t0 = datetime(2024, 1, 1, tzinfo=UTC)
        grid = [int((t0 + timedelta(hours=h)).timestamp()) for h in range(12)]
        client = self._client_with_max_bars(4)
        self._install_server(client, grid, recent_window=6, resend_recent=resend_recent)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            bars = await client.get_historical_ohlcv(
                SYMBOL, "1H", start=t0, end=t0 + timedelta(hours=11)
            )

        assert client._prepare_chart_session.await_count == 3  # type: ignore[attr-defined]
        timestamps = [b.timestamp for b in bars]
        assert timestamps == grid  # exact count, strictly increasing, no duplicates

    @pytest.mark.asyncio
    async def test_daily_segments_with_midnight_seams_and_date_only_end(self) -> None:
        """25 daily bars, max_bars=10 → 3 segments with exact-midnight seams.

        The date-only end expands to 23:59:59, so the last segment covers the whole
        final day; the seams (01-10|01-11, 01-20|01-21) lose nothing and double nothing.
        """
        t0 = datetime(2024, 1, 1, tzinfo=UTC)
        grid = [int((t0 + timedelta(days=d)).timestamp()) for d in range(25)]
        client = self._client_with_max_bars(10)
        self._install_server(client, grid, recent_window=8, resend_recent=False)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            bars = await client.get_historical_ohlcv(
                SYMBOL, "1D", start="2024-01-01", end="2024-01-25"
            )

        assert client._prepare_chart_session.await_count == 3  # type: ignore[attr-defined]
        assert [b.timestamp for b in bars] == grid
        assert _range_param_bounds(client)[1] == end_of_day_timestamp("2024-01-25")

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Known limitation, unchanged by v0.16.0: segment_time_range() leaves a "
            "one-interval hole between seg.end and next.start, so a bar stamped off the "
            "interval grid on a seam day (e.g. a session-open daily bar at 14:30 UTC) is "
            "requested by no segment. Follow-up: contiguous segment windows."
        ),
    )
    async def test_off_grid_daily_stamps_survive_midnight_seams(self) -> None:
        t0 = datetime(2024, 1, 1, 14, 30, tzinfo=UTC)  # session-open stamps
        grid = [int((t0 + timedelta(days=d)).timestamp()) for d in range(25)]
        client = self._client_with_max_bars(10)
        self._install_server(client, grid, recent_window=8, resend_recent=False)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            bars = await client.get_historical_ohlcv(
                SYMBOL, "1D", start="2024-01-01", end="2024-01-25"
            )

        assert [b.timestamp for b in bars] == grid
