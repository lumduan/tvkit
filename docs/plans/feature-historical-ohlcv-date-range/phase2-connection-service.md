# Phase 2: Connection Service (`connection_service.py`)

**Feature:** Historical OHLCV Date Range — Phase 2: Connection Service
**Branch:** `feature/historical-ohlcv-date-range`
**Created:** 2026-03-05
**Status:** Planned
**Depends On:** Phase 1 — Utility Functions (Complete)
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

---

## Overview

### Purpose

Phase 2 extends `tvkit/api/chart/services/connection_service.py` to support the TradingView `modify_series` protocol message required for date-range-based historical OHLCV queries.

The connection service is the component responsible for building and dispatching the `create_series` and (new) `modify_series` WebSocket messages. Currently, `add_symbol_to_sessions()` sends `create_series` inline with hardcoded argument construction. This phase:

1. **Adds module-level constants** for the three hardcoded TradingView identifier strings (`"sds_1"`, `"s1"`, `"sds_sym_1"`) that appear in both message builders — a single source of truth that guards against future protocol regressions.
2. **Extracts `_create_series_args()`** — a private helper that builds the 7-element `create_series` parameter list, making the argument structure explicitly testable without mocking the WebSocket.
3. **Adds `_modify_series_args()`** — a private helper that builds the 6-element `modify_series` parameter list for range mode.
4. **Updates `add_symbol_to_sessions()`** — adds a keyword-only `range_param: str = ""` parameter; dispatches `modify_series` only when `range_param` is non-empty. All existing callers omit this parameter and continue to work without change.

### Context: Why `modify_series`?

TradingView's WebSocket protocol applies a date range constraint via a two-step sequence:

1. `create_series` — initializes the series subscription (same as count mode; always required)
2. `modify_series` — immediately follows `create_series` in range mode to apply the `"r,<from>:<to>"` constraint

The server ignores the `bars_count` value in `create_series` once `modify_series` is received; it streams only bars within the specified date window, terminating with `series_completed`.

This phase implements the connection-layer half of that protocol. The OHLCV client dispatch and public API changes are Phase 3.

---

## AI Prompt

The following prompt should be used to generate this implementation:

```
Implement Phase 2 — Connection Service changes for the Historical OHLCV Date Range feature
in the tvkit library, following all architectural and documentation standards.

Context:
- The tvkit project is a type-safe, async-first Python library for TradingView APIs.
- Phase 1 (utility functions) is complete: MAX_BARS_REQUEST, to_unix_timestamp(), and
  build_range_param() are available in tvkit/api/chart/utils.py.
- The feature plan is documented in docs/plans/feature-historical-ohlcv-date-range/PLAN.md,
  Phase 2 section.
- The target file is tvkit/api/chart/services/connection_service.py.

Read these files before making any changes:
- docs/plans/feature-historical-ohlcv-date-range/PLAN.md (Phase 2 section)
- docs/plans/feature-historical-ohlcv-date-range/phase2-connection-service.md (this document)
- tvkit/api/chart/services/connection_service.py (current implementation)
- tvkit/api/chart/utils.py (Phase 1 deliverables already in place)
- tests/test_ohlcv_models.py (existing test patterns to follow)

Requirements — implement all of the following in order:

1. Add module-level protocol identifier constants to connection_service.py
   (place at module level, after imports, before the class definition):

   _SERIES_DATASOURCE_ID: str = "sds_1"
   _SERIES_ID: str = "s1"
   _SYMBOL_REF_ID: str = "sds_sym_1"

   These replace all inline string literals "sds_1", "s1", "sds_sym_1" in the file.
   Rationale: single source of truth for protocol identifiers — if TradingView ever
   changes these, only one location needs updating and existing tests immediately catch
   any regression.

2. Extract _create_series_args() private helper method on ConnectionService:
   - Signature:
     def _create_series_args(
         self,
         chart_session: str,
         timeframe: str,
         bars_count: int,
     ) -> list[Any]:
   - Returns exactly:
     [chart_session, _SERIES_DATASOURCE_ID, _SERIES_ID, _SYMBOL_REF_ID, timeframe, bars_count, ""]
   - The trailing "" (empty string) MUST always be present — protocol-critical for count mode.
   - Full docstring required (see Implementation Steps for template).
   - Add comment: "# tvkit currently supports a single series per chart session."

3. Add _modify_series_args() private helper method on ConnectionService:
   - Signature:
     def _modify_series_args(
         self,
         chart_session: str,
         timeframe: str,
         range_param: str,
     ) -> list[Any]:
   - Returns exactly:
     [chart_session, _SERIES_DATASOURCE_ID, _SERIES_ID, _SYMBOL_REF_ID, timeframe, range_param]
   - 6 elements — no trailing empty string (modify_series protocol differs from create_series).
   - Full docstring required.

4. Update add_symbol_to_sessions() signature and body:

   New signature (keyword-only range_param, backward-compatible):
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

   Body changes:
   a. Replace the inline create_series argument list with:
        self._create_series_args(chart_session, timeframe, bars_count)
   b. Immediately after the create_series call, add:
        if range_param:
            await send_message_func(
                "modify_series",
                self._modify_series_args(chart_session, timeframe, range_param),
            )
   c. Update docstring to document range_param (see Implementation Steps for template).
   d. All other message sends (resolve_symbol, quote_add_symbols, quote_fast_symbols,
      create_study, quote_hibernate_all) remain unchanged.

   Note on double-call safety: add_symbol_to_sessions() is called once per symbol
   subscription setup. Calling it twice for the same session would create a duplicate
   series on the TradingView side — this is a caller responsibility, not something
   the connection service guards against. Document this in the docstring.

   Note on range_param validation: malformed range_param strings (e.g. wrong format,
   timestamps out of order) are the caller's responsibility. The connection service
   transmits the value as-is. Validation belongs at the OHLCV client layer (Phase 3)
   where build_range_param() produces the validated string before it reaches here.
   Document this layering in the docstring.

5. Create tests/test_connection_service.py (new file — do NOT add to test_ohlcv_models.py):

   These tests cover the connection-layer protocol contract, not OHLCV end-to-end flow.
   Separating them keeps test_ohlcv_models.py focused on the client layer.

   Test class: TestConnectionServiceSeriesArgs

   Test 1 — _create_series_args structure:
     def test_create_series_args_structure():
       svc = ConnectionService(ws_url="wss://...")
       args = svc._create_series_args("cs_abc", "1D", 100)
       assert args == ["cs_abc", "sds_1", "s1", "sds_sym_1", "1D", 100, ""]
       assert len(args) == 7
       assert args[-1] == ""  # trailing empty string is protocol-critical

   Test 2 — _modify_series_args structure:
     def test_modify_series_args_structure():
       svc = ConnectionService(ws_url="wss://...")
       range_str = "r,1704067200:1735603200"
       args = svc._modify_series_args("cs_abc", "1D", range_str)
       assert args == ["cs_abc", "sds_1", "s1", "sds_sym_1", "1D", range_str]
       assert len(args) == 6
       assert args[-1] == range_str

   Test 3 — count mode does NOT send modify_series:
     @pytest.mark.asyncio
     async def test_add_symbol_count_mode_no_modify_series():
       sent_messages: list[tuple[str, list]] = []
       async def mock_send(method: str, args: list) -> None:
           sent_messages.append((method, args))
       svc = ConnectionService(ws_url="wss://...")
       await svc.add_symbol_to_sessions(
           "qs_test", "cs_test", "NASDAQ:AAPL", "1D", 100, mock_send
       )
       methods = [m[0] for m in sent_messages]
       assert "modify_series" not in methods

   Test 4 — range mode sends modify_series immediately after create_series:
     @pytest.mark.asyncio
     async def test_add_symbol_range_mode_sends_modify_series_in_order():
       sent_messages: list[tuple[str, list]] = []
       async def mock_send(method: str, args: list) -> None:
           sent_messages.append((method, args))
       svc = ConnectionService(ws_url="wss://...")
       range_str = "r,1704067200:1735603200"
       await svc.add_symbol_to_sessions(
           "qs_test", "cs_test", "NASDAQ:AAPL", "1D", 5000, mock_send,
           range_param=range_str,
       )
       methods = [m[0] for m in sent_messages]
       assert "modify_series" in methods
       create_index = methods.index("create_series")
       # modify_series MUST appear directly after create_series — protocol ordering
       assert methods[create_index + 1] == "modify_series"
       # Confirm range_param is the last element of modify_series args
       modify_args = next(args for method, args in sent_messages if method == "modify_series")
       assert modify_args[-1] == range_str

   Test 5 — range_param keyword parameter defaults to empty string:
     def test_add_symbol_range_param_default_empty_string():
       import inspect
       sig = inspect.signature(ConnectionService.add_symbol_to_sessions)
       assert sig.parameters["range_param"].default == ""

Architectural requirements:
- ALL variable declarations MUST have explicit type annotations.
- Named parameters in all function calls.
- No Any types without justification (Any is already imported and used in this file).
- Follow the existing import organization in connection_service.py.
- All WebSocket operations remain async.
- No debug print statements.
- All existing public API compatibility maintained.

Quality gates (run and verify all pass before updating plan docs):
  uv run ruff check .
  uv run ruff format .
  uv run mypy tvkit/
  uv run python -m pytest tests/ -v

After implementation:
- Update docs/plans/feature-historical-ohlcv-date-range/PLAN.md:
  - Check off all Phase 2 checklist items under "Connection Service (connection_service.py)"
  - Add a Phase 2 entry under "Phase Completion Log" with date, test count, and any issues
- Update docs/plans/feature-historical-ohlcv-date-range/phase2-connection-service.md:
  - Change "Status: Planned" to "Status: Complete"
  - Set "Completed:" to today's date
  - Add a Completion Notes section (summary, test count, issues encountered, quality gate results)

Files for reference:
- docs/plans/feature-historical-ohlcv-date-range/PLAN.md
- docs/plans/feature-historical-ohlcv-date-range/phase2-connection-service.md
- tvkit/api/chart/services/connection_service.py
- tvkit/api/chart/utils.py
- tests/test_ohlcv_models.py
```

---

## Scope

### In Scope (Phase 2)

| Component | Description | Status |
|---|---|---|
| Module-level protocol constants | `_SERIES_DATASOURCE_ID`, `_SERIES_ID`, `_SYMBOL_REF_ID` | Planned |
| `_create_series_args()` | Extract 7-element `create_series` arg builder as private helper | Planned |
| `_modify_series_args()` | Add 6-element `modify_series` arg builder as private helper | Planned |
| `add_symbol_to_sessions()` signature | Add keyword-only `range_param: str = ""` parameter | Planned |
| `modify_series` dispatch | Conditional send immediately after `create_series` when `range_param` non-empty | Planned |
| `tests/test_connection_service.py` | New test file with 5 test cases for arg structure and dispatch behaviour | Planned |
| Plan document | This document | Complete |

### Out of Scope (Future Phases)

- OHLCV client `get_historical_ohlcv()` signature changes and dispatch logic — Phase 3
- Timeout adjustment (30s count mode / 120s range mode) — Phase 3
- `bars_count` default change from `10` to `None` — Phase 3
- Full integration tests with mocked WebSocket message sequences — Phase 4

---

## Design Decisions

### 1. Module-level constants for protocol identifier strings

The strings `"sds_1"`, `"s1"`, and `"sds_sym_1"` appear in both `_create_series_args()` and `_modify_series_args()`. Duplicating string literals across two methods creates a regression risk: if TradingView ever changes an identifier, tests would fail only at integration level rather than at the unit level where the constant is defined.

```python
_SERIES_DATASOURCE_ID: str = "sds_1"
_SERIES_ID: str = "s1"
_SYMBOL_REF_ID: str = "sds_sym_1"
```

This gives a **single source of truth**: one place to update, and the structure tests immediately catch any regression in element order or value.

### 2. Keyword-only `range_param` for strict backward compatibility

The `range_param` parameter is placed after `*` (keyword-only). All existing callers pass `bars_count` as the last positional argument; the keyword-only boundary makes this safe without any code changes at existing call sites.

```python
# Existing callers — unaffected (range_param defaults to "")
await connection_service.add_symbol_to_sessions(
    quote_session, chart_session, symbol, timeframe, bars_count, send_fn
)

# Range-mode caller — explicit keyword argument
await connection_service.add_symbol_to_sessions(
    quote_session, chart_session, symbol, timeframe, bars_count, send_fn,
    range_param="r,1704067200:1735603200",
)
```

### 3. Extract helpers for testability, not just readability

The primary motivation for extracting `_create_series_args()` and `_modify_series_args()` is **unit testability**. The argument lists are protocol-critical — a wrong element count or wrong position breaks the TradingView WebSocket protocol silently. Extracting them as pure methods that return lists allows direct structural testing without spinning up a WebSocket:

```python
args = svc._create_series_args("cs_abc", "1D", 100)
assert args == ["cs_abc", "sds_1", "s1", "sds_sym_1", "1D", 100, ""]
assert len(args) == 7
assert args[-1] == ""  # protocol-critical trailing empty string
```

### 4. `modify_series` sent immediately after `create_series`, before other messages

Per the protocol specification, `modify_series` must arrive immediately after `create_series` before the data loop begins. Within `add_symbol_to_sessions()`, the conditional `modify_series` dispatch is placed on the lines directly following the `create_series` send, before `quote_fast_symbols` and `create_study`. The test asserts strict ordering (`methods[create_index + 1] == "modify_series"`), not just presence.

### 5. Conditional on non-empty string — no separate mode flag

The dispatch condition is `if range_param:` rather than introducing a `mode: str` or `use_range: bool` parameter. The range param carries its own presence signal: an empty string means "count mode, no `modify_series`"; a non-empty string means "range mode, send `modify_series`".

### 6. What happens if `modify_series` is called twice?

`add_symbol_to_sessions()` is designed to be called once per symbol subscription setup. Calling it twice for the same session would create a duplicate series on the TradingView side, which is a caller responsibility. The connection service transmits protocol messages faithfully; it does not track session state or guard against duplicate calls. This is documented in the method's docstring.

### 7. Where is malformed `range_param` detected?

Malformed range strings (e.g. wrong prefix, reversed timestamps, invalid format) are **not validated** in the connection service. The connection service transmits whatever value it receives as-is. Validation belongs at the OHLCV client layer (Phase 3), where `build_range_param()` from `utils.py` produces a validated string before passing it down to `add_symbol_to_sessions()`. This maintains clean layer separation: the connection service is a protocol messenger, not a validator.

### 8. How will protocol regressions be detected?

The module-level constants and structural unit tests in `tests/test_connection_service.py` form a regression detection net:
- If the constants are changed, `test_create_series_args_structure` and `test_modify_series_args_structure` immediately fail
- If element counts change, `assert len(args) == 7` / `== 6` catch it
- If ordering changes, `assert methods[create_index + 1] == "modify_series"` catches it
- If the trailing `""` is removed from `_create_series_args`, `assert args[-1] == ""` catches it

### 9. New test file `tests/test_connection_service.py` — not `test_ohlcv_models.py`

These tests cover the **connection-layer protocol contract** — argument structure and message dispatch order. Adding them to `test_ohlcv_models.py` would mix two different concerns (protocol builder correctness vs. OHLCV client end-to-end flow). A dedicated file gives:
- Clearer test responsibility boundaries
- Easier coverage reporting per layer
- Room for Phase 3 connection tests without cluttering the models file

### 10. Single-series comment for future contributors

The helpers hardcode `_SERIES_ID = "s1"` — a single series per chart session. A comment is added to `_create_series_args()` to signal this design constraint to future contributors who might attempt multi-series support.

---

## Implementation Steps

### Step 1: Read current `connection_service.py`

Before writing any code, read the file to confirm:
- The exact current signature of `add_symbol_to_sessions()`
- The inline `create_series` argument list (currently at lines ~155–158)
- The import block (to confirm `Any` is already imported from `typing`)

### Step 2: Add module-level protocol constants

Insert at module level, after imports, before the `ConnectionService` class definition:

```python
# Protocol identifier constants for TradingView WebSocket series messages.
# These values appear in both create_series and modify_series parameter lists.
# Centralised here to avoid silent regressions if TradingView updates its protocol.
_SERIES_DATASOURCE_ID: str = "sds_1"
_SERIES_ID: str = "s1"
_SYMBOL_REF_ID: str = "sds_sym_1"
```

### Step 3: Add `_create_series_args()` private helper

Insert after `_get_quote_fields()` and before `add_symbol_to_sessions()`:

```python
def _create_series_args(
    self,
    chart_session: str,
    timeframe: str,
    bars_count: int,
) -> list[Any]:
    """
    Build the 7-element parameter list for the create_series WebSocket message.

    The parameter order and count are protocol-critical. The trailing empty string
    must always be present — omitting it silently breaks the TradingView protocol.

    Note: tvkit currently supports a single series per chart session. The series
    identifiers (_SERIES_ID, _SERIES_DATASOURCE_ID, _SYMBOL_REF_ID) are fixed
    constants that match this single-series design.

    Args:
        chart_session: The chart session identifier (e.g. "cs_abcdefghijkl").
        timeframe: The interval string (e.g. "1D", "60", "1H").
        bars_count: Number of bars to request. In range mode this is MAX_BARS_REQUEST
            and is ignored by TradingView once modify_series applies the range.

    Returns:
        List of 7 elements:
        [chart_session, "sds_1", "s1", "sds_sym_1", timeframe, bars_count, ""]

    Example:
        >>> svc._create_series_args("cs_abc123", "1D", 100)
        ["cs_abc123", "sds_1", "s1", "sds_sym_1", "1D", 100, ""]
    """
    return [
        chart_session,
        _SERIES_DATASOURCE_ID,
        _SERIES_ID,
        _SYMBOL_REF_ID,
        timeframe,
        bars_count,
        "",
    ]
```

### Step 4: Add `_modify_series_args()` private helper

Insert immediately after `_create_series_args()`:

```python
def _modify_series_args(
    self,
    chart_session: str,
    timeframe: str,
    range_param: str,
) -> list[Any]:
    """
    Build the 6-element parameter list for the modify_series WebSocket message.

    modify_series is sent in range mode immediately after create_series to apply
    the date range constraint. Unlike create_series, it has exactly 6 elements
    with no trailing empty string.

    The range_param value is transmitted as-is. Callers are responsible for
    producing a valid "r,<from_unix>:<to_unix>" string (e.g. via
    tvkit.api.chart.utils.build_range_param()). Malformed strings are not
    validated here — validation belongs at the OHLCV client layer.

    Args:
        chart_session: The chart session identifier (e.g. "cs_abcdefghijkl").
        timeframe: The interval string (e.g. "1D", "60", "1H").
        range_param: TradingView range string in "r,<from_unix>:<to_unix>" format,
            as produced by tvkit.api.chart.utils.build_range_param().

    Returns:
        List of 6 elements:
        [chart_session, "sds_1", "s1", "sds_sym_1", timeframe, range_param]

    Example:
        >>> svc._modify_series_args("cs_abc123", "1D", "r,1704067200:1735603200")
        ["cs_abc123", "sds_1", "s1", "sds_sym_1", "1D", "r,1704067200:1735603200"]
    """
    return [
        chart_session,
        _SERIES_DATASOURCE_ID,
        _SERIES_ID,
        _SYMBOL_REF_ID,
        timeframe,
        range_param,
    ]
```

### Step 5: Update `add_symbol_to_sessions()` signature and body

**Signature** — add keyword-only `range_param`:

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

**Docstring** — add `range_param` to the Args block:

```
range_param: TradingView range string ("r,<from_unix>:<to_unix>") for
    date-range mode. When non-empty, a modify_series message is sent
    immediately after create_series to apply the date constraint.
    Defaults to "" (count mode — modify_series is not sent).
    This method is designed to be called once per symbol subscription;
    calling it twice on the same chart_session creates a duplicate series.
```

**Body** — replace inline list, add conditional `modify_series`:

```python
# Before:
await send_message_func(
    "create_series",
    [chart_session, "sds_1", "s1", "sds_sym_1", timeframe, bars_count, ""],
)

# After:
await send_message_func(
    "create_series",
    self._create_series_args(chart_session, timeframe, bars_count),
)
if range_param:
    await send_message_func(
        "modify_series",
        self._modify_series_args(chart_session, timeframe, range_param),
    )
```

### Step 6: Create `tests/test_connection_service.py`

```python
"""Unit tests for ConnectionService protocol message builders and dispatch."""

import inspect
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock

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
        create_index: int = methods.index("create_series")
        # Protocol requirement: modify_series MUST be the very next message
        assert methods[create_index + 1] == "modify_series"
        # Confirm range_param is the last element of the modify_series args
        modify_args: list[Any] = next(
            args for method, args in sent_messages if method == "modify_series"
        )
        assert modify_args[-1] == range_str

    def test_add_symbol_range_param_default_empty_string(self) -> None:
        """range_param keyword argument defaults to empty string."""
        sig = inspect.signature(ConnectionService.add_symbol_to_sessions)
        assert sig.parameters["range_param"].default == ""
```

### Step 7: Run quality gates

```bash
uv run ruff check .
uv run ruff format .
uv run mypy tvkit/
uv run python -m pytest tests/ -v
```

All must pass before updating the plan files.

### Step 8: Update plan documents

- Update `docs/plans/feature-historical-ohlcv-date-range/phase2-connection-service.md`:
  - Change `Status: Planned` to `Status: Complete`
  - Set `Completed:` to today's date
  - Add Completion Notes section (summary, test count, issues, quality gate results)
- Update `docs/plans/feature-historical-ohlcv-date-range/PLAN.md`:
  - Check off all Phase 2 checklist items under "Connection Service"
  - Add a Phase 2 entry under Phase Completion Log

---

## File Changes

| File | Action | Description |
|---|---|---|
| `tvkit/api/chart/services/connection_service.py` | MODIFY | Add module-level constants; extract `_create_series_args()`; add `_modify_series_args()`; update `add_symbol_to_sessions()` with `range_param` |
| `tests/test_connection_service.py` | CREATE | 5 test cases covering arg structure and dispatch behaviour (new file — not added to `test_ohlcv_models.py`) |
| `docs/plans/feature-historical-ohlcv-date-range/phase2-connection-service.md` | CREATE | This plan document |
| `docs/plans/feature-historical-ohlcv-date-range/PLAN.md` | MODIFY | Note Phase 2 as planned; mark checklist after completion |

---

## Success Criteria

- [ ] Module-level constants `_SERIES_DATASOURCE_ID`, `_SERIES_ID`, `_SYMBOL_REF_ID` defined before the class
- [ ] `_create_series_args()` extracted — returns exactly 7 elements, trailing `""` present
- [ ] `_modify_series_args()` added — returns exactly 6 elements, `range_param` is last
- [ ] Both helpers use module-level constants (no inline string literals for `"sds_1"`, `"s1"`, `"sds_sym_1"`)
- [ ] `add_symbol_to_sessions()` updated — accepts keyword-only `range_param: str = ""`
- [ ] `modify_series` sent only when `range_param` is non-empty
- [ ] `modify_series` sent as the message immediately following `create_series` (strict ordering)
- [ ] All existing callers of `add_symbol_to_sessions()` unaffected (backward-compatible default)
- [ ] Docstrings updated with `range_param`, double-call note, and validation-layer note
- [ ] `tests/test_connection_service.py` created — 5 tests, all passing
- [ ] `test_create_series_args_structure` — 7 elements, trailing `""`
- [ ] `test_modify_series_args_structure` — 6 elements, range string last
- [ ] `test_add_symbol_count_mode_no_modify_series` — `modify_series` NOT in sent methods
- [ ] `test_add_symbol_range_mode_sends_modify_series_in_order` — ordering and arg content correct
- [ ] `test_add_symbol_range_param_default_empty_string` — default is `""`
- [ ] `uv run ruff check .` — no errors
- [ ] `uv run ruff format .` — no changes
- [ ] `uv run mypy tvkit/` — no errors
- [ ] `uv run python -m pytest tests/ -v` — all pass

---

**Document Version:** 1.0
**Author:** AI Agent
**Status:** Planned
