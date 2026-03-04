# Fix Issue #7 — Historical OHLCV Freezes When Requested Bars Exceed Available Data

**Feature:** Early Termination for `get_historical_ohlcv` on Data Exhaustion
**Branch:** `fix/issue-7-historical-ohlcv-early-termination`
**Created:** 2026-03-04
**Status:** Planning
**Issue:** [#7 — get_historical_ohlcv freezes until timeout when bars_count > available data](https://github.com/lumduan/tvkit/issues/7)

---

## Table of Contents

1. [Overview](#overview)
2. [Root Cause Analysis](#root-cause-analysis)
3. [Architecture Context](#architecture-context)
4. [Fix Strategy](#fix-strategy)
5. [Implementation Phases](#implementation-phases)
6. [Testing Strategy](#testing-strategy)
7. [CI/CD Improvements](#cicd-improvements)
8. [Development Standards](#development-standards)
9. [File Changes](#file-changes)
10. [Success Criteria](#success-criteria)
11. [Roadmap & Priorities](#roadmap--priorities)

---

## Overview

### Problem Statement

When a caller requests more historical OHLCV bars than a symbol actually has available, `get_historical_ohlcv` **freezes for the full 30-second timeout** before returning any data, instead of returning the available partial data immediately.

```python
# Example: BINANCE:BTCUSDT has 403 daily bars total
bars = await client.get_historical_ohlcv("BINANCE:BTCUSDT", interval="1D", bars_count=500)
# ↑ Currently blocks for 30 seconds before returning 403 bars
# ↑ Should return 403 bars in ~1–2 seconds once TradingView signals completion
```

### User Impact

| Scenario | Current Behavior | Expected Behavior |
|---|---|---|
| `bars_count` ≤ available | Returns fast (~1–2 s) ✅ | No change |
| `bars_count` > available | Freezes for 30 s ❌ | Returns partial data in ~1–2 s ✅ |
| Server closes connection | Freezes for 30 s, then RuntimeError ❌ | Returns collected data immediately ✅ |
| Symbol with no data | Freezes for 30 s, then RuntimeError ❌ | Raises faster with clear message ✅ |

### Design Rationale

The TradingView WebSocket protocol already sends a `series_completed` message to signal that all available data for a requested series has been transmitted. The fix does **not** change any network protocol — it simply honours a signal that the server is already sending.

---

## Root Cause Analysis

### Protocol Flow (Normal — `bars_count` ≤ Available)

```
Client → create_series(cs_xxx, 10 bars)
Server → series_loading
Server → timescale_update  { 10 bars }   ← historical bars
Server → series_completed                ← "all done"
Server → du  { latest bar }             ← real-time update
```

### Protocol Flow (Broken — `bars_count` > Available)

```
Client → create_series(cs_xxx, 500 bars)
Server → series_loading
Server → timescale_update  { 403 bars }  ← all available bars
Server → series_completed                ← "all done" ← BUG: ignored here
         ... silence ...
         ... silence ...
         ... 30 s elapses ...
Client → timeout break                   ← finally exits
```

### Code Location

**File:** `tvkit/api/chart/ohlcv.py` — `get_historical_ohlcv` method, ~line 355

```python
# CURRENT (BROKEN) — series_completed is silently continued past
elif message_type == "series_completed":
    # Series completed message - continue waiting for data
    logging.debug("Series completed for historical data fetch")
    continue   # ← BUG: should break when we have bars, not keep waiting
```

### Why `continue` Is Wrong Here

`series_completed` means the server has finished sending all bars for the registered series (`sds_1`). Any subsequent messages on this stream will be **real-time ticks** (`du`), not historical bars. The function is called `get_historical_ohlcv` — it should stop as soon as historical transmission ends.

### Secondary Issue — `study_completed` Never Triggers Early Exit

The `study_completed` message (sent after `create_study` with the Volume study) is also handled with `continue`. After `series_completed` + `study_completed`, no further historical-relevant messages will arrive.

### Related Code Paths that Have the Same Pattern

| Method | Message | Current | Should Be |
|---|---|---|---|
| `get_historical_ohlcv` | `series_completed` | `continue` | `break` (if bars exist) |
| `get_historical_ohlcv` | `study_completed` | `continue` | `break` (if `series_completed` seen) |

Methods `get_ohlcv`, `get_quote_data`, `get_ohlcv_raw`, and `get_latest_trade_info` use streaming generators and **do not** need this fix — they are designed to run indefinitely.

---

## Architecture Context

### Relevant Files

```
tvkit/api/chart/
├── ohlcv.py                          ← PRIMARY: fix series_completed handler
│   └── get_historical_ohlcv()        ← ~lines 229–410
├── services/
│   ├── connection_service.py         ← get_data_stream() — yields parsed JSON messages
│   └── message_service.py            ← constructs and sends WebSocket messages
└── models/
    └── ohlcv.py                      ← OHLCVBar, TimescaleUpdateResponse, WebSocketMessage
```

### Data Flow

```
get_historical_ohlcv()
  │
  ├─ validate_symbols()           [async HTTP validation]
  ├─ convert_symbol_format()      [EXCHANGE-SYMBOL → EXCHANGE:SYMBOL]
  ├─ validate_interval()
  ├─ _setup_services()            [creates ConnectionService + MessageService]
  ├─ connection_service.initialize_sessions()
  ├─ connection_service.add_symbol_to_sessions()  [sends create_series]
  │
  └─ async for data in connection_service.get_data_stream():
         │
         ├─ timescale_update → extend historical_bars
         ├─ du               → extend historical_bars (partial updates)
         ├─ series_completed → [CURRENTLY: continue] [FIX: break]
         ├─ series_loading   → continue
         ├─ quote_completed  → continue
         ├─ study_completed  → [CURRENTLY: continue] [FIX: break if series_completed seen]
         ├─ series_error     → raise ValueError
         └─ timeout check    → break after 30 s [KEEP as safety net]
```

---

## Fix Strategy

### Minimal, Targeted Change

The fix is **small and surgical**. No refactoring of the WebSocket protocol layer or `ConnectionService` is needed.

#### Change 1 — Track `series_completed` State

Add a boolean flag inside `get_historical_ohlcv` to record when `series_completed` has been received:

```python
series_completed_received: bool = False
```

#### Change 2 — Break on `series_completed`

```python
elif message_type == "series_completed":
    logging.info("Series completed — all available historical bars received")
    series_completed_received = True
    break  # Exit loop: server has sent all available data
```

#### Change 3 — Break on `study_completed` After `series_completed`

Because `study_completed` (Volume study) can arrive slightly after `series_completed`, the most robust approach is to break on `series_completed` directly (Change 2). This is the primary terminal signal.

However, as a belt-and-suspenders addition, guard `study_completed` too:

```python
elif message_type == "study_completed":
    if series_completed_received:
        logging.info("Study completed after series — terminating historical fetch")
        break
    logging.debug("Study completed for historical data fetch")
    continue
```

#### Change 4 — Guard Against Empty Result

The existing guard already covers this case, but add a log message to distinguish partial vs. zero data:

```python
if not historical_bars:
    raise RuntimeError(f"No historical data received for symbol {converted_symbol}")

if len(historical_bars) < bars_count:
    logging.info(
        f"Partial data: received {len(historical_bars)} bars "
        f"(requested {bars_count}) — symbol may have less available history"
    )
```

### Timeout Remains as Safety Net

The 30-second timeout **is kept**. It now serves only as a safety net for unexpected network stalls or malformed server responses — not as the primary exit condition for data-exhausted streams.

### No Changes to `ConnectionService`

`get_data_stream()` in `connection_service.py` correctly yields all parsed messages from the WebSocket stream. No changes needed there.

---

## Implementation Phases

### Phase 1 — Core Bug Fix (Priority 1)

**Goal:** Stop the freeze. Return partial data immediately when the server signals completion.

**Files to change:**

- `tvkit/api/chart/ohlcv.py` — `get_historical_ohlcv` method (~lines 345–362)

**Steps:**

1. Add `series_completed_received: bool = False` flag before the stream loop
2. Change `series_completed` handler from `continue` to `break` + set flag
3. Update `study_completed` handler to break if flag is set
4. Add informational log message for partial result case
5. Run existing tests: `uv run python -m pytest tests/ -v`
6. Run type check: `uv run mypy tvkit/`
7. Run linter: `uv run ruff check . && uv run ruff format .`

**Estimated effort:** 0.5 day

---

### Phase 2 — New Test Coverage (Priority 2)

**Goal:** Prevent regression and cover all edge cases for historical data retrieval.

**Files to create:**

- `tests/test_historical_ohlcv.py` — comprehensive test suite for `get_historical_ohlcv`

**Test categories and cases:**

#### 2.1 Unit Tests — `series_completed` Signal Handling

These tests mock `connection_service.get_data_stream()` to emit controlled message sequences.

| Test Name | Scenario | Expected Outcome |
|---|---|---|
| `test_returns_partial_bars_on_series_completed` | 403 bars returned, then `series_completed` | Returns 403 bars immediately |
| `test_returns_exact_bars_when_count_matches` | Exactly 10 bars, then `series_completed` | Returns 10 bars |
| `test_returns_bars_before_timeout` | `series_completed` at 0.1 s, timeout at 30 s | Returns in < 1 s (not 30 s) |
| `test_does_not_stop_before_series_completed` | 5 bars, no `series_completed` yet | Continues receiving until signal |
| `test_study_completed_after_series_breaks_loop` | `series_completed` then `study_completed` | Breaks at `study_completed` |
| `test_study_completed_without_series_continues` | `study_completed` before `series_completed` | Continues (does not break early) |

#### 2.2 Unit Tests — Partial Data Scenarios

| Test Name | Scenario | Expected Outcome |
|---|---|---|
| `test_partial_result_logged_as_info` | 50/100 bars available | Log message mentions partial result |
| `test_zero_bars_raises_runtime_error` | `series_completed` received with no bars | `RuntimeError` raised |
| `test_bars_sorted_chronologically` | Bars arrive out of order | Result sorted by timestamp |

#### 2.3 Unit Tests — Error and Timeout Cases

| Test Name | Scenario | Expected Outcome |
|---|---|---|
| `test_series_error_raises_value_error` | `series_error` message received | `ValueError` raised |
| `test_timeout_returns_partial_bars` | 30 s elapses with partial data | Returns collected bars, logs warning |
| `test_connection_closed_mid_stream` | WebSocket closes after 5 bars | Returns 5 bars collected so far |

#### 2.4 Integration Tests — Mock WebSocket Server

Use a lightweight in-process mock WebSocket server (or direct mock of `get_data_stream`) to simulate end-to-end flows:

| Test Name | Scenario | Expected Outcome |
|---|---|---|
| `test_integration_partial_data_end_to_end` | Mock server sends 50 bars + `series_completed` | Client returns 50 bars without timeout |
| `test_integration_symbol_validation_failure` | Invalid symbol format | `ValueError` from `validate_symbols` |

#### 2.5 Fixtures and Test Utilities

```python
# Helper: build a fake timescale_update message with N bars
def make_timescale_update(bars_count: int) -> dict[str, Any]: ...

# Helper: series_completed message dict
SERIES_COMPLETED_MSG: dict[str, Any] = {"m": "series_completed", "p": ["cs_xxx", "sds_1"]}

# Helper: series_loading message dict
SERIES_LOADING_MSG: dict[str, Any] = {"m": "series_loading", "p": ["cs_xxx", "sds_1"]}
```

**Estimated effort:** 2 days

---

### Phase 3 — CI/CD Pipeline (Priority 3)

**Goal:** Ensure all future pull requests are validated automatically.

**Files to create:**

- `.github/workflows/ci.yml`

**Pipeline steps:**

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: uv sync
      - name: Lint
        run: uv run ruff check .
      - name: Format check
        run: uv run ruff format --check .
      - name: Type check
        run: uv run mypy tvkit/
      - name: Tests with coverage
        run: uv run python -m pytest tests/ -v --cov=tvkit --cov-report=xml --cov-fail-under=80
      - uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
```

**Estimated effort:** 1 day

---

### Phase 4 — Coverage Reporting and Standards (Priority 4)

**Goal:** Enforce a minimum coverage gate and document testing conventions.

**Steps:**

1. Add `pytest-cov` to `pyproject.toml` dev dependencies
2. Add `[tool.pytest.ini_options]` to `pyproject.toml`:

   ```toml
   [tool.pytest.ini_options]
   asyncio_mode = "auto"
   addopts = "--cov=tvkit --cov-fail-under=80"
   ```

3. Update `CLAUDE.md` to document new test file `tests/test_historical_ohlcv.py`
4. Document mock fixture pattern for WebSocket testing

**Estimated effort:** 0.5 day

---

## Testing Strategy

### Mocking Approach

`get_historical_ohlcv` is hard to test with live TradingView connections. All unit tests mock `connection_service.get_data_stream()` to return a controllable async generator:

```python
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tvkit.api.chart.ohlcv import OHLCV


async def fake_stream(messages: list[dict[str, Any]]) -> AsyncGenerator[dict[str, Any], None]:
    """Fake data stream that yields a predefined sequence of messages."""
    for msg in messages:
        yield msg


@pytest.mark.asyncio
async def test_returns_partial_bars_on_series_completed() -> None:
    """When series_completed arrives before bars_count is reached, return collected bars."""
    bars_payload: list[dict[str, Any]] = make_timescale_update(bars_count=403)
    messages: list[dict[str, Any]] = [
        {"m": "series_loading", "p": ["cs_1", "sds_1"]},
        bars_payload,
        {"m": "series_completed", "p": ["cs_1", "sds_1", "sds_sym_1", "ok"]},
    ]

    with patch.multiple(
        "tvkit.api.chart.ohlcv",
        validate_symbols=AsyncMock(return_value=True),
        convert_symbol_format=MagicMock(return_value=MagicMock(converted_symbol="BINANCE:BTCUSDT")),
        validate_interval=MagicMock(),
    ):
        client = OHLCV()
        client.connection_service = MagicMock()
        client.connection_service.get_data_stream = lambda: fake_stream(messages)
        client.connection_service.initialize_sessions = AsyncMock()
        client.connection_service.add_symbol_to_sessions = AsyncMock()
        client.message_service = MagicMock()
        client.message_service.generate_session = MagicMock(side_effect=["qs_1", "cs_1"])
        client.message_service.get_send_message_callable = MagicMock(return_value=AsyncMock())

        result = await client.get_historical_ohlcv("BINANCE:BTCUSDT", interval="1D", bars_count=500)

    assert len(result) == 403
```

### Test Pyramid

```
                      ┌─────────────────────┐
                      │   Integration (2)   │  End-to-end mock server flows
                      ├─────────────────────┤
                      │   Functional (8)    │  Full method flows with mocked stream
                      ├─────────────────────┤
                      │   Unit (11)         │  Model parsing, individual message handling
                      └─────────────────────┘
```

### Async Test Requirements

All async tests use `pytest-asyncio` with `asyncio_mode = "auto"` in `pyproject.toml`. No per-test `@pytest.mark.asyncio` decorators needed when running in auto mode.

---

## CI/CD Improvements

### Current State

No automated CI pipeline is configured (no `.github/workflows/` folder).

### Proposed GitHub Actions Workflow

| Step | Tool | Fail Threshold |
|---|---|---|
| Lint | `ruff check .` | Any error |
| Format | `ruff format --check .` | Any diff |
| Type check | `mypy tvkit/` | Any type error |
| Tests | `pytest tests/ -v` | Any failure |
| Coverage | `pytest --cov=tvkit --cov-fail-under=80` | < 80% |

### Branch Protection Rules (Recommended)

In GitHub repository settings, require the `CI` workflow to pass before merging any pull request to `main`. This prevents any regression from being merged silently.

---

## Development Standards

### New Test File Naming

- `tests/test_historical_ohlcv.py` — test file for `get_historical_ohlcv` and related behavior

### Docstring for New Tests

Each test class and function must include a one-line docstring explaining:

- What is being tested
- What the expected outcome is

### Mock Pattern for WebSocket Streams

Always mock `connection_service.get_data_stream` as an async generator factory, not as an `AsyncMock` returning a list. This accurately represents the streaming nature of the real implementation.

```python
# ✅ Correct — async generator
client.connection_service.get_data_stream = lambda: fake_stream(messages)

# ❌ Incorrect — AsyncMock is not an async generator
client.connection_service.get_data_stream = AsyncMock(return_value=messages)
```

### Type Annotations

All new code must include explicit type annotations on every variable and function. No implicit `Any` unless justified and documented.

---

## File Changes

### Files Modified

| File | Change | Phase |
|---|---|---|
| `tvkit/api/chart/ohlcv.py` | Add `series_completed_received` flag; change `continue` → `break` for `series_completed`; conditional `break` for `study_completed` after flag is set; add partial-data log message | Phase 1 |
| `pyproject.toml` | Add `pytest-cov` to dev dependencies | Phase 4 |
| `CLAUDE.md` | Document new test file and mock fixture pattern | Phase 4 |

### Files Created

| File | Purpose | Phase |
|---|---|---|
| `tests/test_historical_ohlcv.py` | Comprehensive unit + integration tests for `get_historical_ohlcv` | Phase 2 |
| `.github/workflows/ci.yml` | GitHub Actions CI pipeline | Phase 3 |
| `docs/plans/fix-issue-7-historical-ohlcv-timeout/PLAN.md` | This document | Now |
| `docs/plans/fix-issue-7-historical-ohlcv-timeout/phase1-core-fix.md` | Phase 1 implementation details | Phase 1 |
| `docs/plans/fix-issue-7-historical-ohlcv-timeout/phase2-test-coverage.md` | Phase 2 testing details | Phase 2 |
| `docs/plans/fix-issue-7-historical-ohlcv-timeout/phase3-ci-pipeline.md` | Phase 3 CI/CD details | Phase 3 |

---

## Success Criteria

### Phase 1 — Core Fix

- [ ] `get_historical_ohlcv("BINANCE:BTCUSDT", interval="1D", bars_count=500)` returns in < 5 seconds (not 30 s)
- [ ] Returned list contains all available bars (e.g., 403), not an empty list
- [ ] Log output includes: `"Series completed — all available historical bars received"`
- [ ] Log output includes partial data notice when `len(result) < bars_count`
- [ ] All existing tests pass: `uv run python -m pytest tests/ -v`
- [ ] Type check passes: `uv run mypy tvkit/`
- [ ] Linting passes: `uv run ruff check . && uv run ruff format .`

### Phase 2 — Test Coverage

- [ ] `tests/test_historical_ohlcv.py` exists and all tests pass
- [ ] At least 21 new test cases covering the scenarios in [Phase 2](#phase-2--new-test-coverage-priority-2)
- [ ] Coverage for `tvkit/api/chart/ohlcv.py` ≥ 85%
- [ ] No real network calls in any test (all external I/O mocked)

### Phase 3 — CI/CD

- [ ] `.github/workflows/ci.yml` exists and triggers on PRs to `main`
- [ ] Pipeline runs lint, format check, mypy, and pytest
- [ ] Coverage gate set at 80% minimum
- [ ] Pipeline passes on a clean push to `main`

### Phase 4 — Standards

- [ ] `pytest-cov` listed in `pyproject.toml` dev dependencies
- [ ] `CLAUDE.md` updated with new test file reference
- [ ] Mock fixture pattern documented in `CLAUDE.md`

---

## Roadmap & Priorities

| Priority | Phase | Task | Effort |
|---|---|---|---|
| 1 | Phase 1 | Fix `series_completed` handler → break instead of continue | 0.5 day |
| 2 | Phase 2 | Write `tests/test_historical_ohlcv.py` with 21+ test cases | 2 days |
| 3 | Phase 3 | Create `.github/workflows/ci.yml` pipeline | 1 day |
| 4 | Phase 4 | Add coverage config + update docs | 0.5 day |
| | **Total** | | **~4 days** |

### Delivery Sequence

```
Phase 1 (fix) ──► Phase 2 (tests) ──► Phase 3 (CI) ──► Phase 4 (standards)
     │                  │                  │                   │
  0.5 day            2 days             1 day              0.5 day
```

Phase 1 can be deployed immediately as a patch release (`v0.x.1`). Phases 2–4 can be batched into a single pull request since they are non-breaking.

---

## Appendix — TradingView `series_completed` Protocol Reference

The `series_completed` message has the following structure on the wire:

```json
{
  "m": "series_completed",
  "p": ["cs_<session_id>", "sds_1", "sds_sym_1", "ok"]
}
```

After `series_completed`, the server transitions the series to **real-time update mode** and will only send `du` (data update) messages for new bars. Historical transmission is permanently finished at this point. There is no subsequent signal that would re-trigger historical data for the same session.

This is why `get_historical_ohlcv` — which specifically requests a snapshot of past bars — must exit the message loop when it receives `series_completed`. Continuing to wait will never produce additional historical bars.
