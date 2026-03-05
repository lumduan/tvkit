# Phase 1: Utility Functions (`utils.py`)

**Feature:** Historical OHLCV Date Range — Phase 1: Utility Functions
**Branch:** `feature/historical-ohlcv-date-range`
**Created:** 2026-03-05
**Status:** Complete
**Completed:** 2026-03-05
**Depends On:** None (standalone utility additions)
**Parent Plan:** `docs/plans/feature-historical-ohlcv-date-range/PLAN.md`

---

## Table of Contents

1. [Overview](#overview)
2. [AI Prompt](#ai-prompt)
3. [Scope](#scope)
4. [Design Decisions](#design-decisions)
5. [Implementation Steps](#implementation-steps)
6. [File Changes](#file-changes)
7. [Success Criteria](#success-criteria)
8. [Completion Notes](#completion-notes)

---

## Overview

### Purpose

Phase 1 adds three items to `tvkit/api/chart/utils.py` that are required by the range-mode feature before any changes to connection or OHLCV layers:

1. **`MAX_BARS_REQUEST: int = 5000`** — sentinel constant passed to `create_series` when TradingView range mode is active. TradingView ignores this value once `modify_series` applies the range, but the parameter slot must be non-empty.

2. **`to_unix_timestamp(ts: datetime | str) -> int`** — converts a timezone-aware `datetime`, naive `datetime` (assigned UTC without conversion), or ISO 8601 string (including `Z` suffix) to an integer Unix timestamp (microseconds truncated).

3. **`build_range_param(start: datetime | str, end: datetime | str) -> str`** — builds the TradingView range parameter string `"r,<from>:<to>"` used in `modify_series` messages.

### Context: Why `MAX_BARS_REQUEST = 5000`

TradingView limits historical intraday bars per account tier:

| Account Plan | Max Intraday Bars |
|---|---|
| Free / Basic | 5,000 |
| Essential / Plus | 10,000 |
| Premium | 20,000 |
| Expert | 25,000 |
| Ultimate | 40,000 |

The base tier (5,000) is used as the sentinel value because:
- `create_series` requires a non-empty `bars_count` slot even in range mode
- TradingView ignores this value when `modify_series` range is active
- Using 5,000 ensures the slot is valid for the lowest common denominator
- Higher-tier users benefit automatically from range mode returning all bars in the window

Source: https://www.tradingview.com/support/solutions/43000480679-historical-intraday-data-bars-and-limits-explained/

---

## AI Prompt

The following prompt was used to generate this phase:

```
Implement plan for Phase 1 — Utility Functions (`utils.py`) to support historical OHLCV date range features in the tvkit library, following all architectural and documentation standards.

Context:
- The tvkit project is a type-safe, async-first Python library for TradingView APIs.
- The feature request is for historical OHLCV data with flexible date range support.
- The plan is documented in `docs/plans/feature-historical-ohlcv-date-range/PLAN.md`, with Phase 1 focused on utility functions in `utils.py`.

Requirements:
- Add MAX_BARS_REQUEST constant, to_unix_timestamp(), and build_range_param() to tvkit/api/chart/utils.py.
- All functions must have complete type annotations and comprehensive docstrings.
- Functions are pure computation (no I/O) — no async required.
- Comprehensive error handling with specific exception types.
- Update planning docs with progress, notes, and any issues encountered.

Special Note on MAX_BARS_REQUEST = 5000:
The length of historical data for any intraday interval is 5000 bars/candles (for Essential and Plus account holders
it is doubled to 10000 bars and for Premium holders it is quadrupled to 20000). Professional plans offer more:
Expert plans have access to 25000 bars, and Ultimate plans can have the maximum of 40000.
From: https://www.tradingview.com/support/solutions/43000480679-historical-intraday-data-bars-and-limits-explained/

Production-hardening requirements (from code review):
- Support "Z" suffix in ISO 8601 strings (replace with "+00:00" before parsing).
- Docstring must explicitly state: "Naive datetimes are assigned UTC timezone without conversion.
  A datetime(2024, 1, 1, 0, 0) passed as local time will be treated as if it were UTC."
- Add TypeError guard for non-(datetime | str) inputs in both functions.
- Add __all__ = ["MAX_BARS_REQUEST", "to_unix_timestamp", "build_range_param", "validate_interval"]
  to utils.py for explicit public API surface.
- Test microsecond truncation explicitly.
```

---

## Scope

### In Scope (Phase 1)

| Component | Description | Status |
|---|---|---|
| `MAX_BARS_REQUEST` constant | Sentinel `int = 5000` for `create_series` in range mode | Complete |
| `to_unix_timestamp()` | Convert `datetime` or ISO 8601 string (incl. `Z`) to Unix int | Complete |
| `build_range_param()` | Build TradingView `"r,<from>:<to>"` string with type guard | Complete |
| `__all__` declaration | Explicit public API surface for `utils.py` | Complete |
| Unit tests | 11 test cases covering all edge cases | Complete |
| Plan document | This document | Complete |

### Out of Scope (Future Phases)

- `ConnectionService` changes (`_create_series_args`, `_modify_series_args`, `modify_series` dispatch) — Phase 2
- OHLCV client `get_historical_ohlcv()` signature changes — Phase 3
- Integration tests with live or mocked WebSocket — Phase 4

---

## Design Decisions

### 1. `to_unix_timestamp` accepts both `datetime` and `str`

Using a union type `datetime | str` allows callers to pass either convenience strings (`"2024-01-01"`) or explicit `datetime` objects. Python 3.11+ `datetime.fromisoformat()` fully supports ISO 8601, including date-only strings and timezone-aware strings.

### 2. `Z` suffix normalization before `fromisoformat`

`datetime.fromisoformat()` in Python 3.10 and below does not support the `"Z"` UTC designator; Python 3.11 added support. Since trading systems, REST APIs, and JSON feeds commonly emit `"2024-01-01T00:00:00Z"`, we normalize this unconditionally:

```python
if isinstance(ts, str) and ts.endswith("Z"):
    ts = ts[:-1] + "+00:00"
```

This is safe and adds zero cost for strings without `Z`.

### 3. Naive datetimes assigned UTC (not converted) — no exception

Raising on naive datetimes would be too strict. The chosen behavior assigns UTC timezone using `replace(tzinfo=timezone.utc)` — this is an **assignment, not a conversion**. The docstring makes this explicit: a `datetime` representing Bangkok local time will be silently misinterpreted as UTC. Callers who care must supply timezone-aware datetimes. A debug log is emitted.

### 4. `TypeError` guard for non-`datetime | str` inputs

If a caller passes an integer or any other type, the resulting error from `fromisoformat` or `.timestamp()` would be cryptic. A single `isinstance` check at the top of `to_unix_timestamp` produces a clear `TypeError` with a useful message. `build_range_param` inherits this guard by delegating to `to_unix_timestamp`.

### 5. Microsecond truncation via `int(dt.timestamp())`

TradingView uses integer seconds. `int()` truncates (rounds down) sub-second precision, consistent with floor behavior. This is explicitly tested.

### 6. No `async` — pure computation

`to_unix_timestamp` and `build_range_param` perform no I/O. Making them async would add unnecessary overhead and `await` noise at every call site.

### 7. `__all__` declaration for explicit public API surface

Declaring `__all__` in `utils.py` makes the public contract explicit for Phase 2/3 imports and prevents accidental re-export of internal symbols.

### 8. Logger side-effect accepted for naive datetime warning

The project's architecture allows logging in utility functions. The debug-level log for naive datetimes is a low-cost diagnostic that aids debugging without polluting normal output. Pure-function advocates could remove it, but the tradeoff favors observability for a financial data library.

---

## Implementation Steps

### Step 1: Add `__all__` and imports

```python
import logging
import re
from datetime import datetime, timezone

logger: logging.Logger = logging.getLogger(__name__)

__all__ = [
    "MAX_BARS_REQUEST",
    "to_unix_timestamp",
    "build_range_param",
    "validate_interval",
]
```

### Step 2: Add `MAX_BARS_REQUEST` constant

```python
# Sentinel bars_count sent in create_series during range mode.
# TradingView ignores this value when modify_series range is active,
# but the parameter slot must be filled. Using 5000 (free tier base limit)
# as the conservative sentinel — safe for all account tiers.
#
# Account tier bar limits (intraday intervals):
#   Free / Basic:     5,000
#   Essential / Plus: 10,000
#   Premium:          20,000
#   Expert:           25,000
#   Ultimate:         40,000
#
# Source: https://www.tradingview.com/support/solutions/43000480679
MAX_BARS_REQUEST: int = 5000
```

### Step 3: Implement `to_unix_timestamp`

Key behaviors:
- Normalize `"Z"` suffix before `fromisoformat`
- Raise `TypeError` for non-`datetime | str` inputs
- Assign UTC to naive datetimes (with debug log); do not raise
- Truncate microseconds via `int()`

```python
def to_unix_timestamp(ts: datetime | str) -> int:
    if not isinstance(ts, (datetime, str)):
        raise TypeError(
            f"ts must be a datetime or ISO 8601 string, got {type(ts).__name__!r}"
        )
    if isinstance(ts, str):
        # Normalize "Z" UTC designator — fromisoformat requires "+00:00"
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt: datetime = datetime.fromisoformat(ts)
    else:
        dt = ts

    if dt.tzinfo is None:
        logger.debug(
            "to_unix_timestamp received naive datetime %s — "
            "assigning UTC (no timezone conversion applied)", dt
        )
        dt = dt.replace(tzinfo=timezone.utc)

    return int(dt.timestamp())
```

### Step 4: Implement `build_range_param`

```python
def build_range_param(start: datetime | str, end: datetime | str) -> str:
    from_ts: int = to_unix_timestamp(start)  # TypeError propagates from here
    to_ts: int = to_unix_timestamp(end)

    if from_ts > to_ts:
        raise ValueError(
            f"start ({start!r}) must not be after end ({end!r}). "
            f"Converted timestamps: start={from_ts}, end={to_ts}"
        )

    return f"r,{from_ts}:{to_ts}"
```

### Step 4b: Refactor `validate_interval` in `utils.py`

The existing implementation uses a list of string-literal regexes compiled per-call with scattered validation logic. The refactor:

1. **Adds `isinstance` type guard** — raises `TypeError` for non-string inputs (consistent with `to_unix_timestamp`)
2. **Replaces per-call `re.match` with a single precompiled regex** — `_INTERVAL_RE` at module level
3. **Separates parsing from validation** — one `fullmatch`, then clean unit dispatch

```python
# Precompiled once at module load — covers all TradingView interval formats:
#   Minutes: "1", "15", "1440"
#   Seconds: "1S", "30S"
#   Hours:   "1H", "12H"
#   Days:    "D", "1D", "3D"
#   Weeks:   "W", "1W", "4W"
#   Months:  "M", "1M", "12M"
_INTERVAL_RE: re.Pattern[str] = re.compile(r"^(\d+)([SMHDWM])?$|^([DWM])$")
```

Validation limits remain unchanged (minutes 1–1440, seconds 1–60, hours 1–168, etc.). A note is added to the docstring clarifying these are client-side safety limits, not server-enforced TradingView restrictions.

### Step 5: Write unit tests in `test_utils.py`

Eleven test cases:

```
TestToUnixTimestamp:
  test_to_unix_timestamp_datetime_utc
  test_to_unix_timestamp_naive_datetime_treated_as_utc_no_raise
  test_to_unix_timestamp_iso_string_date_only
  test_to_unix_timestamp_iso_string_with_time_and_tz
  test_to_unix_timestamp_iso_string_z_suffix
  test_to_unix_timestamp_microsecond_truncation
  test_to_unix_timestamp_invalid_string_raises_value_error
  test_to_unix_timestamp_invalid_type_raises_type_error

TestBuildRangeParam:
  test_build_range_param_valid_returns_r_prefix_string
  test_build_range_param_same_day_is_valid
  test_build_range_param_start_after_end_raises
  test_build_range_param_datetime_inputs
  test_build_range_param_mixed_datetime_and_string_inputs
```

---

## File Changes

| File | Action | Description |
|---|---|---|
| `tvkit/api/chart/utils.py` | MODIFY | Add `__all__`, `MAX_BARS_REQUEST`, `to_unix_timestamp()`, `build_range_param()` |
| `tests/test_utils.py` | MODIFY | Add `TestToUnixTimestamp` and `TestBuildRangeParam` test classes |
| `docs/plans/feature-historical-ohlcv-date-range/phase1-util-functions.md` | CREATE | This plan document |
| `docs/plans/feature-historical-ohlcv-date-range/PLAN.md` | MODIFY | Phase 1 completion notes |

---

## Success Criteria

- [x] `MAX_BARS_REQUEST: int = 5000` defined with inline comment explaining the constant and account tier table
- [x] `to_unix_timestamp(ts: datetime | str) -> int` implemented with full type annotations
- [x] `"Z"` suffix normalized to `"+00:00"` before `fromisoformat` parsing
- [x] `TypeError` raised for non-`datetime | str` inputs
- [x] Naive datetime assigned UTC with `replace(tzinfo=timezone.utc)` and debug log
- [x] Docstring explicitly states: "assigned, not converted"
- [x] `build_range_param(start, end) -> str` implemented, validates `start <= end`
- [x] `__all__` declared in `utils.py`
- [x] All 13 unit tests written and passing
- [x] `ruff check .` — no errors
- [x] `ruff format .` — no changes
- [x] `mypy tvkit/` — no errors
- [x] `pytest tests/ -v` — all pass

---

## Completion Notes

### Summary

Phase 1 utility functions implemented and verified. All production-hardening points from code review incorporated:
- `Z` suffix support
- Explicit naive-datetime docstring
- `TypeError` guards
- Microsecond truncation test
- `__all__` export declaration

### Issues Encountered

None.

---

**Document Version:** 1.1
**Author:** AI Agent
**Status:** Complete
**Completed:** 2026-03-05
