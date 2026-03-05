# Historical OHLCV Date Range Feature Implementation Plan

**Feature:** Retrieve historical OHLCV data by start/end date range
**Branch:** `feature/historical-ohlcv-date-range`
**Created:** 2026-03-05
**Status:** In Progress (Phase 1 Complete)
**Positioning:** Extends `get_historical_ohlcv()` to support range-based queries alongside existing `bars_count` mode

---

## Table of Contents

1. [Overview](#overview)
2. [Background & Motivation](#background--motivation)
3. [Architecture](#architecture)
4. [Protocol Research](#protocol-research)
5. [Message Flow Sequence](#message-flow-sequence)
6. [Implementation Phases](#implementation-phases)
7. [Data Models](#data-models)
8. [API Design](#api-design)
9. [Error Handling Strategy](#error-handling-strategy)
10. [Testing Strategy](#testing-strategy)
11. [Breaking Change Guide](#breaking-change-guide)
12. [Implementation Checklist](#implementation-checklist)
13. [Success Criteria](#success-criteria)
14. [Future Enhancements](#future-enhancements)

---

## Overview

### Purpose

This feature extends the existing `get_historical_ohlcv()` method to support fetching historical OHLCV bars by an explicit **start/end date range**, in addition to the current count-based approach (`bars_count`). The TradingView WebSocket protocol supports a range parameter format (`r,<from_unix>:<to_unix>`) via the `modify_series` message. This feature exposes that capability in a type-safe, async-first manner consistent with the rest of tvkit.

### Design Rationale

Currently, callers must guess how many bars to request (`bars_count`) and then filter the results by date client-side — an imprecise and wasteful approach for use cases like:
- **Backtesting**: Fetch a precise training window for Zipline, Backtrader, or custom engines without over-fetching
- **Analytics pipelines**: Export clean date-ranged slices to CSV/JSON via `DataExporter`
- **Technical analysis**: Calculate indicators over fixed windows (e.g., "last 52 weeks of daily bars")
- **Data science**: Build reproducible datasets aligned to known date boundaries

---

## Background & Motivation

### Current Behavior

```python
async def get_historical_ohlcv(
    self, exchange_symbol: str, interval: str = "1", bars_count: int = 10
) -> list[OHLCVBar]:
```

- Only `bars_count` supported; callers over-fetch and filter post-hoc
- No way to specify a date range directly
- Default of `10` is implicit and fragile as a sentinel for mode detection

### TradingView Protocol

TradingView uses a two-step approach for range-based data:

1. **`create_series`** initializes the subscription (same as count mode)
2. **`modify_series`** applies the date range constraint to the already-created series

The `modify_series` message carries the range string as its last parameter:
```
"r,<from_unix_timestamp>:<to_unix_timestamp>"
```

Example: `"r,1704067200:1735689600"` (Jan 1 2024 → Dec 31 2024 UTC, inclusive)

---

## Architecture

### Affected Files

| File | Change Type | Reason |
|------|-------------|--------|
| `tvkit/api/chart/ohlcv.py` | Modify | New method signature + range dispatch logic |
| `tvkit/api/chart/utils.py` | Add | `to_unix_timestamp()`, `build_range_param()`, `MAX_BARS_REQUEST` constant |
| `tvkit/api/chart/services/connection_service.py` | Modify | Add `modify_series` call; extract `_create_series_args()` / `_modify_series_args()` helpers |
| `tvkit/api/chart/models/ohlcv.py` | No change | Existing `OHLCVBar` sufficient; no new metadata model needed |
| `tests/test_ohlcv_models.py` | Modify | Add range-mode test cases |
| `tests/test_utils.py` | Modify | Add timestamp conversion and range param tests |

### No New Model Required

The feature returns the same `list[OHLCVBar]` type. A metadata wrapper model is deferred to a future enhancement (see [Future Enhancements](#future-enhancements)).

---

## Protocol Research

### `create_series` vs `modify_series`

| Action | Message | When |
|--------|---------|------|
| First subscription | `create_series` | Initial session setup (same as today) |
| Apply date range | `modify_series` | Immediately after `create_series`, range mode only |

Range mode does **not** replace `create_series`; it sends `modify_series` immediately after to apply the range constraint. Count mode does not send `modify_series` at all.

### Parameter Type Reference

The strict 7-element `create_series` signature and 6-element `modify_series` signature:

```
CreateSeriesArgs = [
    chart_session,  # str  — chart session ID (e.g. "cs_abcdefghijkl")
    sds_id,         # str  — series data source ID (always "sds_1")
    series_id,      # str  — series ID (always "s1")
    sds_sym_id,     # str  — symbol reference ID (always "sds_sym_1")
    timeframe,      # str  — interval string (e.g. "1D", "60", "1H")
    bars_count,     # int  — number of bars (ignored by server in range mode)
    range_string,   # str  — "" for count mode; MUST NOT be omitted
]

ModifySeriesArgs = [
    chart_session,  # str  — same chart session ID
    sds_id,         # str  — "sds_1"
    series_id,      # str  — "s1"
    sds_sym_id,     # str  — "sds_sym_1"
    timeframe,      # str  — same interval string
    range_param,    # str  — "r,<from_unix>:<to_unix>"
]
```

**Key rules:**
- Parameter positions are **strict** — swapping any element breaks the protocol
- `create_series` trailing `""` **must always be present** in count mode
- `modify_series` has exactly 6 elements — no trailing empty string

---

## Message Flow Sequence

### Count Mode (existing — no change)

```
client → resolve_symbol
client → quote_add_symbols / quote_fast_symbols
client → create_series   [..., bars_count, ""]
server ← series_loading
server ← timescale_update × N
server ← series_completed        ← break loop
```

### Range Mode (new)

```
client → resolve_symbol
client → quote_add_symbols / quote_fast_symbols
client → create_series   [..., MAX_BARS_REQUEST, ""]
client → modify_series   [..., "r,<from>:<to>"]     ← new step
server ← series_loading
server ← timescale_update × N
server ← series_completed                           ← break loop
```

`modify_series` is sent immediately after `create_series`, before the data loop begins. TradingView then applies the range constraint and streams only bars within the window.

---

## Implementation Phases

### Phase 1 — Utility Functions (`utils.py`) ✅ Complete (2026-03-05)

**Goal:** Provide `to_unix_timestamp()`, `build_range_param()`, and `MAX_BARS_REQUEST` constant.

**New constant:**

```python
# Sentinel bars_count sent in create_series during range mode.
# TradingView ignores this value when modify_series range is active,
# but the parameter slot must be filled.
MAX_BARS_REQUEST: int = 5000
```

**New functions:**

```python
from datetime import datetime, timezone


def to_unix_timestamp(ts: datetime | str) -> int:
    """
    Convert a datetime or ISO 8601 string to a UTC Unix timestamp (integer seconds).

    Args:
        ts: A timezone-aware datetime, or an ISO 8601 string.
            Naive datetimes are assumed to be UTC (debug log emitted).

    Returns:
        Unix timestamp as integer seconds since epoch.

    Raises:
        ValueError: If the string cannot be parsed as ISO 8601.

    Example:
        >>> to_unix_timestamp("2024-01-01")
        1704067200
        >>> to_unix_timestamp(datetime(2024, 1, 1, tzinfo=timezone.utc))
        1704067200
    """


def build_range_param(start: datetime | str, end: datetime | str) -> str:
    """
    Build a TradingView range parameter string from start and end timestamps.

    Args:
        start: Start of the range (inclusive).
        end: End of the range (inclusive).

    Returns:
        Range string in format "r,<from>:<to>".

    Raises:
        ValueError: If start > end after conversion.
            start == end is valid (e.g. single-day intraday fetch).

    Example:
        >>> build_range_param("2024-01-01", "2024-12-31")
        "r,1704067200:1735603200"
        >>> build_range_param("2024-01-01", "2024-01-01")  # single-day: valid
        "r,1704067200:1704067200"
    """
```

**Implementation notes:**
- Use `datetime.fromisoformat()` for string parsing (Python 3.11+ accepts full ISO 8601)
- Naive datetimes treated as UTC; emit `logger.debug()` — do not raise
- `start > end` raises `ValueError` (fail fast before WebSocket)
- `start == end` is **valid** — allows fetching a single day's bars on intraday intervals

---

### Phase 2 — Connection Service (`connection_service.py`) 📋 Planned (2026-03-05)

**Goal:** Add `modify_series` support and extract private builder helpers for testability.

**New private helper methods:**

```python
def _create_series_args(
    self,
    chart_session: str,
    timeframe: str,
    bars_count: int,
) -> list[Any]:
    """
    Build the 7-element parameter list for create_series.

    Returns:
        [chart_session, "sds_1", "s1", "sds_sym_1", timeframe, bars_count, ""]
    """
    return [chart_session, "sds_1", "s1", "sds_sym_1", timeframe, bars_count, ""]


def _modify_series_args(
    self,
    chart_session: str,
    timeframe: str,
    range_param: str,
) -> list[Any]:
    """
    Build the 6-element parameter list for modify_series (range mode).

    Returns:
        [chart_session, "sds_1", "s1", "sds_sym_1", timeframe, range_param]
    """
    return [chart_session, "sds_1", "s1", "sds_sym_1", timeframe, range_param]
```

Extracting these as private methods makes them directly unit-testable without mocking the WebSocket.

**Updated `add_symbol_to_sessions()` signature (backward-compatible):**

```python
async def add_symbol_to_sessions(
    self,
    quote_session: str,
    chart_session: str,
    exchange_symbol: str,
    timeframe: str,
    bars_count: int,
    send_message_func: Callable[[str, list[Any]], Awaitable[None]],
    *,
    range_param: str = "",
) -> None:
```

**Updated body — range dispatch:**

```python
await send_message_func("create_series", self._create_series_args(chart_session, timeframe, bars_count))

if range_param:
    await send_message_func("modify_series", self._modify_series_args(chart_session, timeframe, range_param))
```

Existing callers omit `range_param` and receive `""` — count mode, `modify_series` is never sent.

---

### Phase 3 — OHLCV Client (`ohlcv.py`)

**Goal:** Update public API and internal dispatch. Eliminate implicit `bars_count` sentinel.

**Revised `bars_count` default — `None` instead of `10`:**

Using `None` as the default removes fragile sentinel comparisons. Mode is determined solely by which parameters are provided:

```python
async def get_historical_ohlcv(
    self,
    exchange_symbol: str,
    interval: str = "1",
    bars_count: int | None = None,
    *,
    start: datetime | str | None = None,
    end: datetime | str | None = None,
) -> list[OHLCVBar]:
```

**Dispatch logic (explicit, no sentinel):**

```python
has_range: bool = start is not None or end is not None
has_count: bool = bars_count is not None

if has_range and has_count:
    raise ValueError(
        "Cannot specify both bars_count and start/end. "
        "Use bars_count for count-based queries or start/end for range-based queries."
    )

if has_range:
    if start is None or end is None:
        raise ValueError("Both start and end must be provided for range-based queries.")
    range_param: str = build_range_param(start, end)
    effective_bars_count: int = MAX_BARS_REQUEST  # ignored by TradingView in range mode
elif has_count:
    range_param = ""
    effective_bars_count = bars_count
else:
    raise ValueError(
        "Either bars_count or both start and end must be provided."
    )
```

**Updated `_prepare_chart_session()`:**

```python
async def _prepare_chart_session(
    self,
    converted_symbol: str,
    interval: str,
    bars_count: int,
    *,
    range_param: str = "",
) -> None:
```

Passes `range_param` through to `add_symbol_to_sessions()`.

**Timeout adjustment for range mode:**

```python
# Range queries may cover years of intraday data; extend timeout accordingly.
# CHANGELOG: timeout increased from 30s (count mode) to 120s (range mode).
timeout_seconds: int = 120 if range_param else 30
```

**Remove `bars_count` completion check in range mode:**

```python
# Only break early on count in count mode — range terminates on series_completed
if not range_param and len(historical_bars) >= effective_bars_count:
    break
```

**Track `series_completed` for incomplete-stream warning:**

```python
series_completed_received: bool = False

# ... in loop ...
elif message_type == "series_completed":
    series_completed_received = True
    logger.info("Series completed — all available historical bars received")
    break

# ... after loop ...
if not series_completed_received:
    logger.warning(
        "WebSocket stream ended without series_completed signal — "
        "data may be incomplete. Consider increasing timeout or checking "
        "network stability."
    )
```

---

### Phase 4 — Tests

**Files to update:**
- `tests/test_utils.py` — new tests for `to_unix_timestamp()` and `build_range_param()`
- `tests/test_ohlcv_models.py` — integration-style tests for range mode using mocked WebSocket

#### `test_utils.py` — new test cases

```
- test_to_unix_timestamp_datetime_utc
- test_to_unix_timestamp_naive_datetime_treated_as_utc_no_raise
- test_to_unix_timestamp_iso_string_date_only
- test_to_unix_timestamp_iso_string_with_time_and_tz
- test_to_unix_timestamp_invalid_string_raises_value_error
- test_build_range_param_valid_returns_r_prefix_string
- test_build_range_param_same_day_is_valid          ← start == end is allowed
- test_build_range_param_start_after_end_raises      ← start > end raises
- test_build_range_param_string_inputs
- test_build_range_param_mixed_datetime_and_string_inputs
```

#### `test_ohlcv_models.py` — new test cases

Mock sequence for range mode must include:
1. `series_loading`
2. `timescale_update` × N (with bars inside window)
3. `series_completed`

And assert `modify_series` is called on the send function:

```
- test_get_historical_ohlcv_count_mode_unchanged
- test_get_historical_ohlcv_range_mode_basic
- test_get_historical_ohlcv_range_mode_partial_result_ok    ← fewer bars is not an error
- test_get_historical_ohlcv_range_mode_no_bars_raises       ← zero bars → RuntimeError
- test_get_historical_ohlcv_both_bars_count_and_range_raises
- test_get_historical_ohlcv_only_start_raises
- test_get_historical_ohlcv_only_end_raises
- test_get_historical_ohlcv_start_after_end_raises
- test_get_historical_ohlcv_no_params_raises
- test_get_historical_ohlcv_range_mode_sends_modify_series  ← assert modify_series called
- test_get_historical_ohlcv_websocket_closes_before_series_completed_warns
- test_get_historical_ohlcv_range_mode_timeout_is_120s      ← assert timeout value
- test_create_series_args_structure                         ← 7-element list, trailing ""
- test_modify_series_args_structure                         ← 6-element list, range string
```

**Note on partial results:** TradingView may return fewer bars than the range spans (weekends, holidays, limited history). This is **not** an error. Tests should assert that returned bars fall within the requested range, not that a specific count was returned.

**Timeout test:** Mock `get_data_stream()` to yield messages slowly (or yield nothing after `series_loading`) and assert that the timeout triggers without hanging indefinitely.

---

## Data Models

### No New Models Needed

The existing `OHLCVBar` model is sufficient for range-mode responses. The same `timescale_update` → `series_completed` protocol flow is used.

### Deferred: `HistoricalRangeResult`

A future enhancement may wrap the result with metadata:

```python
class HistoricalRangeResult(BaseModel):
    bars: list[OHLCVBar]
    requested_start: int   # Unix timestamp
    requested_end: int     # Unix timestamp
    actual_start: int      # First bar timestamp
    actual_end: int        # Last bar timestamp
    symbol: str
    interval: str
    bar_count: int
```

This is intentionally deferred — returning `list[OHLCVBar]` keeps the API consistent with the existing count-based method.

---

## API Design

### Public Interface

```python
# Count mode (bars_count now required explicitly — no implicit default)
bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=100)

# Range mode — datetime objects
from datetime import datetime, timezone
bars = await client.get_historical_ohlcv(
    "NASDAQ:AAPL",
    "1D",
    start=datetime(2024, 1, 1, tzinfo=timezone.utc),
    end=datetime(2024, 12, 31, tzinfo=timezone.utc),
)

# Range mode — ISO 8601 strings (convenience)
bars = await client.get_historical_ohlcv(
    "NASDAQ:AAPL",
    "1D",
    start="2024-01-01",
    end="2024-12-31",
)

# Single-day intraday fetch (start == end is valid)
bars = await client.get_historical_ohlcv(
    "NASDAQ:AAPL",
    "5",
    start="2024-06-15",
    end="2024-06-15",
)

# Backtesting integration example (Backtrader / Zipline pipeline)
import polars as pl
from tvkit.export import DataExporter

bars = await client.get_historical_ohlcv("BINANCE:BTCUSDT", "1D", start="2023-01-01", end="2023-12-31")
df = pl.DataFrame([bar.model_dump() for bar in bars])
```

### Validation Rules

| Condition | Behaviour |
|-----------|-----------|
| Only `bars_count` provided | Count mode (existing) |
| Both `start` and `end` provided | Range mode |
| Only `start` OR only `end` | `ValueError` immediately |
| Both `bars_count` AND `start`/`end` | `ValueError` immediately |
| Neither `bars_count` nor `start`/`end` | `ValueError` immediately |
| `start > end` | `ValueError` from `build_range_param()` |
| `start == end` | Valid — single time-point range (e.g., intraday bars for one day) |
| Naive `datetime` | Treated as UTC, `logger.debug()` emitted, no exception |
| Invalid ISO string | `ValueError` with descriptive message |

---

## Error Handling Strategy

### Fail Fast (Before WebSocket)

All validation that does not require network I/O is performed before `_prepare_chart_session()` is called:
- Mode mutual exclusivity (`bars_count` vs `start`/`end`)
- Both `start` and `end` required when range mode is intended
- `start > end` check
- ISO string parse errors

### WebSocket-Level Errors

**Early disconnect before `series_completed`:**

If the WebSocket closes before `series_completed` is received, `ConnectionClosed` from `get_data_stream()` propagates naturally. The loop exits, a warning is logged, and the caller receives whatever bars were collected (or `RuntimeError` if none).

**`series_error` during range fetch:**

Existing handler already raises `ValueError`. No changes needed.

**Timeout:**

```
# Count mode: 30 seconds (unchanged)
# Range mode: 120 seconds (documented in CHANGELOG)
```

This is configurable via an optional `timeout` parameter in a future enhancement.

### Partial Range Results

TradingView may return fewer bars than the range implies (market closed, holidays, limited history). This is expected and not an error. The existing partial-data log warning covers this case.

---

## Breaking Change Guide

### What Changed

`bars_count` default changes from `10` to `None`. Callers that previously relied on the default to fetch 10 bars now receive a `ValueError` unless they explicitly pass `bars_count=10`.

### Migration

**Before:**
```python
bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D")
# → fetched 10 bars (implicit default)
```

**After:**
```python
bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=10)
# → fetches 10 bars (explicit)
```

### CHANGELOG Entry Template

```markdown
## [next version] — YYYY-MM-DD

### Breaking Changes
- `get_historical_ohlcv()`: `bars_count` default changed from `10` to `None`.
  Callers must now explicitly pass `bars_count` or provide `start`/`end` range.

### Added
- `get_historical_ohlcv()` now accepts `start` and `end` parameters for
  date-range-based historical data retrieval.
- `tvkit.api.chart.utils.to_unix_timestamp()` — convert datetime/ISO string to Unix timestamp.
- `tvkit.api.chart.utils.build_range_param()` — build TradingView range string.
- `tvkit.api.chart.utils.MAX_BARS_REQUEST` — sentinel constant for range mode.

### Changed
- Historical fetch timeout extended to 120s in range mode (was 30s).
```

---

## Implementation Checklist

Use this checklist before opening a PR:

### Utilities (`utils.py`)
- [ ] `to_unix_timestamp(ts: datetime | str) -> int` implemented and exported
- [ ] `build_range_param(start, end) -> str` implemented and exported
- [ ] `MAX_BARS_REQUEST: int = 5000` constant defined and exported
- [ ] All edge cases handled: naive datetime, ISO date-only, ISO datetime with tz
- [ ] Unit tests written and passing

### Connection Service (`connection_service.py`)
- [ ] `_create_series_args()` extracted (7-element, trailing `""`)
- [ ] `_modify_series_args()` extracted (6-element, range string last)
- [ ] `add_symbol_to_sessions()` accepts `range_param: str = ""`
- [ ] `modify_series` sent only when `range_param` is non-empty
- [ ] Existing count-mode callers unaffected (no `modify_series` sent)

### OHLCV Client (`ohlcv.py`)
- [ ] `bars_count` default changed to `None`
- [ ] `start` / `end` keyword-only parameters added
- [ ] Dispatch logic implemented with explicit mode detection (no sentinel comparison)
- [ ] `_prepare_chart_session()` passes `range_param` through
- [ ] Timeout set to `120s` for range mode, `30s` for count mode
- [ ] `bars_count` early-exit check disabled in range mode
- [ ] `series_completed_received` flag tracks termination signal
- [ ] Incomplete-stream warning logged if `series_completed` not received

### Tests
- [ ] `test_utils.py` — all 10 utility test cases pass
- [ ] Range mode basic test (bars returned, `modify_series` called)
- [ ] Partial result test (fewer bars than range spans — not an error)
- [ ] Empty result test (zero bars → `RuntimeError`)
- [ ] All invalid-input `ValueError` cases covered
- [ ] Timeout test (slow stream → warning, no hang)
- [ ] `_create_series_args` structure test (7 elements, trailing `""`)
- [ ] `_modify_series_args` structure test (6 elements, range string)
- [ ] Coverage ≥ 90%

### Quality Gates
- [ ] `uv run ruff check .` — no errors
- [ ] `uv run ruff format .` — no changes
- [ ] `uv run mypy tvkit/` — no errors
- [ ] `uv run python -m pytest tests/ -v` — all pass

---

## Success Criteria

- [ ] `get_historical_ohlcv()` accepts `start`/`end` parameters without breaking existing `bars_count` callers (when explicit)
- [ ] `bars_count` default changed to `None`; explicit mode selection enforced
- [ ] `modify_series` is sent after `create_series` when range mode is active
- [ ] `create_series` trailing empty string preserved correctly in count mode
- [ ] Timezone-aware and naive datetimes both handled correctly
- [ ] ISO 8601 date strings accepted as convenience input
- [ ] `start == end` is valid (single-day intraday fetch)
- [ ] `start > end` raises `ValueError` before any WebSocket connection is opened
- [ ] All other invalid inputs raise `ValueError` before WebSocket
- [ ] Range-mode timeout extended to 120 seconds
- [ ] Incomplete stream (no `series_completed`) emits warning log
- [ ] `_create_series_args()` and `_modify_series_args()` extracted as testable private helpers
- [ ] `MAX_BARS_REQUEST` constant defined and documented
- [ ] All new code passes `ruff`, `mypy`, and `pytest` with ≥90% coverage
- [ ] Breaking change documented in CHANGELOG with migration guide

---

## Phase Completion Log

### Phase 1 — Utility Functions (`utils.py`) — Complete (2026-03-05)

**Deliverables:**
- `MAX_BARS_REQUEST: int = 5000` — constant with inline account-tier table and TradingView source link
- `to_unix_timestamp(ts: datetime | str) -> int` — supports timezone-aware datetime, naive datetime (assigned UTC with debug log), ISO 8601 date-only strings, full ISO strings, and `"Z"` suffix normalization; `TypeError` guard for non-datetime/str inputs; microseconds truncated
- `build_range_param(start, end) -> str` — builds `"r,<from>:<to>"` string; validates `start <= end`; delegates type-checking to `to_unix_timestamp`
- `__all__` declaration added to `utils.py`
- `validate_interval` refactored: single precompiled `_INTERVAL_RE` regex, `TypeError` guard for non-string inputs, separated parsing from validation
- 13 new test cases in `tests/test_utils.py` (`TestToUnixTimestamp`, `TestBuildRangeParam`)
- `test_non_string_raises_type_error` added to `tests/test_interval_validation.py`
- Phase plan document: `docs/plans/feature-historical-ohlcv-date-range/phase1-util-functions.md`

**Quality gates:** `ruff check`, `ruff format`, `mypy`, `pytest` — all pass (123 tests)

**Issues / Notes:**
- `validate_interval` already had comprehensive coverage in `test_interval_validation.py`; added only the `TypeError` test there rather than duplicating
- Ruff enforces `datetime.UTC` alias and `X | Y` union syntax in `isinstance` — both applied

---

## Future Enhancements

1. **`HistoricalRangeResult` wrapper model** — return metadata (actual date range covered, bar count) alongside bars
2. **`get_historical_ohlcv_range()` convenience alias** — positional `start`/`end` shorthand for callers who always use range mode
3. **Configurable timeout** — expose `timeout: int` parameter to override the 30s/120s defaults
4. **Pagination support** — for very long intraday ranges, auto-paginate using multiple WebSocket requests
5. **`get_ohlcv()` range mode** — extend the real-time streaming method to accept a start anchor
6. **Relative range shortcuts** — e.g., `start="ytd"`, `start="-90d"` convenience strings
7. **DataExporter integration** — pass range result directly to `DataExporter` with auto-generated filename from date range
8. **HTTP fallback client** — if a REST endpoint for historical data becomes available, add as alternative transport with shared `OHLCVBar` model
