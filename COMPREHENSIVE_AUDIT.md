# Comprehensive Audit — Bug Fixes & Performance Optimization

**Branch:** `claude-optimization-and-bugs`
**Date:** 2026-06-15
**Scope:** Repository-wide review of `tvkit` (≈13.6k LOC) for correctness bugs and
latency/throughput bottlenecks, with a focus on data parsing, network/API error
handling, edge cases in financial data, resource management, and the hot streaming path.

## Result summary

| Metric | Before | After |
| --- | --- | --- |
| Tests passing | 1033 passed, 2 skipped | 1037 passed, 2 skipped |
| New regression tests | — | +4 (`tests/test_indicator_service.py`) |
| `ruff check tvkit/` | clean | clean |
| `mypy` (changed files) | — | clean |
| Behaviour changes | — | 1 intentional correctness fix (export timezone) |

All pre-existing tests continue to pass unchanged; the four new tests cover a bug path
that previously had **zero** coverage.

## Methodology

1. Established a green baseline (`uv run pytest`) before any change.
2. Read every high-risk module: the WebSocket engine (`api/chart/ohlcv.py`), connection &
   message services, segmented fetch, batch downloader, scanner/symbol/indicator HTTP
   clients, the export/serialization layer, models, normalizer, time conversion, and auth.
3. Applied **surgical** fixes only where there was a demonstrable bug or measurable
   overhead — preserving all existing logic and public behaviour.
4. Re-ran the relevant suites after each change and the full suite at the end.

---

## Part 1 — Bugs fixed

### B1. Unhandled `KeyError`/`TypeError` when parsing indicator search results
**File:** `tvkit/api/utils/indicator_service.py` — `fetch_tradingview_indicators()`

**Root cause:** Results from TradingView's public `pubscripts-suggest-json` endpoint were
indexed with hard subscripts (`indicator["scriptName"]`, `indicator["author"]["username"]`,
`indicator["imageUrl"]`, …) while the function only caught `httpx.RequestError`. A single
malformed/partial entry — or `author` not being a dict — raised an **uncaught**
`KeyError`/`TypeError` that aborted the entire search. `response.json()` raising
`json.JSONDecodeError`, and non-2xx responses raising `httpx.HTTPStatusError`, were also
uncaught despite the function's "return `[]` on failure" contract.

**Fix:** Defensive, per-entry parsing: skip non-dict entries, resolve fields with `.get()`
and type guards, construct `IndicatorData` inside a `try` (skipping entries that fail
validation), and broaden the network/JSON exception handling. Valid-data behaviour is
identical (same fields, same filter logic).

**Impact:** One bad record no longer discards every good record; transport/JSON failures
degrade gracefully to `[]`.

### B2. `IndexError`/`KeyError` building the study payload from indicator metadata
**File:** `tvkit/api/utils/indicator_service.py` — `prepare_indicator_metadata()` /
`fetch_indicator_metadata()`

**Root cause:** `metainfo["inputs"][0]["defval"]` assumed a non-empty `inputs` list whose
first element is a dict containing `defval`; the per-input loop indexed `input_item["id"]`,
`["defval"]`, `["type"]` directly. Malformed metadata raised exceptions that the caller's
`except httpx.RequestError` did not catch, violating its documented "return `{}` on error".

**Fix:** Extract the first input and per-input fields defensively (`.get()` + `isinstance`
guards, skipping malformed inputs), guard a non-dict `pine` block, and broaden
`fetch_indicator_metadata`'s exception handling (`HTTPStatusError`, `ValueError`).

### B3. Export silently converted UTC timestamps to the host's local timezone
**File:** `tvkit/export/formatters/base_formatter.py` — `_prepare_timestamp()`

**Root cause:** For `timestamp_format="iso"` (the default) and `"datetime"`, the code used
`datetime.fromtimestamp(timestamp)` **without a timezone**, which interprets the epoch in
the host's local timezone and returns a naive datetime. tvkit's core invariant is that all
OHLCV timestamps are **UTC** Unix-epoch seconds, so any user not running in UTC exported
silently mis-stamped data (e.g. a `00:00:00Z` bar written as `07:00:00` with no offset).

**Fix:** `datetime.fromtimestamp(timestamp, tz=UTC)` for both formats, yielding UTC-aware
output (ISO strings now carry `+00:00`). This makes CSV/JSON/Polars exports timezone-correct
and consistent with the rest of the library. Export tests do not assert on local-time
strings, so no test depended on the buggy behaviour.

### B4. Repository hygiene — stray source backup committed to the package tree
**File (removed):** `tvkit/api/chart/ohlcv.py.backup`

A 30 KB stale copy of the engine sat inside the importable package directory (untracked,
not git-ignored). Removed to prevent confusion and accidental packaging.

---

## Part 2 — Performance & latency optimizations

The streaming/historical OHLCV path is the latency-critical surface for financial data
processing. The following reduce per-message CPU work and memory churn there.

### P1. Eliminated triple re-parsing of OHLCV bars per message (hot path)
**File:** `tvkit/api/chart/ohlcv.py` (`_fetch_single_range`, `_fetch_count_mode`, `get_ohlcv`)

`TimescaleUpdateResponse.ohlcv_bars` and `OHLCVResponse.ohlcv_bars` are **non-cached**
Pydantic `@computed_field` properties — every access re-walks the raw parameter payload and
reconstructs every `OHLCVBar` from scratch. Each historical message accessed the property
**three times** (`len(...)`, a debug loop, then `.extend(...)`). For a premium `prodata`
batch (up to ~20,000 bars in one message) this re-parsed tens of thousands of bars 3×.

**Fix:** Bind the property to a local once (`bars = response.ohlcv_bars`) and reuse it →
**3× → 1×** parse work per message. Applied to both the `timescale_update` and `du` branches.

### P2. Removed eager per-bar debug string construction
**File:** `tvkit/api/chart/ohlcv.py`

`for bar in timescale_response.ohlcv_bars: logger.debug(f"Parsed OHLCV bar: {bar}")` built
an f-string (a full `str()` of a Pydantic model) for **every bar on every fetch even when
debug logging is disabled**, because f-strings are evaluated before `logger.debug` decides
to drop them — and it triggered an extra full re-parse (see P1). Removed; the aggregate
`"Received N bars"` INFO log already conveys the useful signal.

### P3. Made large-payload debug logs lazy
**File:** `tvkit/api/chart/ohlcv.py`

`logger.debug(f"Raw timescale_update data: {data}")` stringified the **entire** raw message
(up to ~2 MB) on every timescale message regardless of log level. Converted these (and the
per-message `"Received message type"` logs) to lazy `%`-style logging
(`logger.debug("... %s", data)`) so the formatting cost is paid only when DEBUG is enabled.

### P4. Removed redundant double Pydantic validation per WebSocket message
**File:** `tvkit/api/chart/ohlcv.py` (all four stream/fetch loops)

Each frame was validated **twice**: once as a generic `WebSocketMessage.model_validate(data)`
purely to read `message_type`, then again with the specific model for the matched branch.
Since the frame is already a parsed `dict`, the type is now read with a cheap
`data.get("m")` (guarded by `isinstance(data, dict)`), removing one full model construction
per message. Behaviour is preserved: missing `"m"` or non-dict frames are skipped exactly as
before. The now-unused `WebSocketMessage` import was dropped (the model itself is retained
and still exported).

### P5. Columnar Polars DataFrame construction for OHLCV export
**File:** `tvkit/export/formatters/polars_formatter.py` — `export_ohlcv()`

Replaced row-oriented construction (`pl.DataFrame([{...}, {...}, …])`, which infers the
schema row-by-row and allocates a dict per bar) with **columnar** construction
(`pl.DataFrame({col: [...]})`). Polars builds each column in a single pass; this is markedly
faster and lighter for large exports (e.g. multi-year minute history from segmented fetch).
Optional `symbol`/`interval` columns are emitted only when present, exactly matching the
previous output.

---

## Testing & verification

```bash
uv run pytest -q                 # 1037 passed, 2 skipped
uv run ruff check tvkit/         # All checks passed
uv run ruff format --check tvkit/
uv run mypy tvkit/api/chart/ohlcv.py tvkit/api/utils/indicator_service.py \
            tvkit/export/formatters/base_formatter.py \
            tvkit/export/formatters/polars_formatter.py   # Success: no issues
```

New file `tests/test_indicator_service.py` adds four regression tests for B1
(valid parse, malformed-entry skip, non-dict payload, JSON decode error). The
malformed-entry test fails against the pre-fix code (`KeyError`).

---

## Deliberately deferred (documented, not changed)

These were identified but intentionally left out to keep the change set focused, correct,
and low-risk. They are recommended follow-ups:

- **Pydantic v2 deprecations (12 warnings):** `class Config` → `model_config = ConfigDict(...)`
  and `json_encoders` in `export/models.py` / `scanner/models/scanner.py`. The `json_encoders`
  replacement (field serializers) alters serialization and these models lack direct coverage,
  so it was not bundled with the bug/perf work.
- **`ScannerService._make_scanner_request`** opens a fresh `httpx.AsyncClient` per retry
  attempt; a single client could be reused across retries. Marginal (helps only on retries),
  and the module has no test coverage, so it was left as-is.
- **`OHLCVResponse.ohlcv_bars` / `series_updates`** could become `functools.cached_property`
  for callers outside the engine; the call-site caching above already covers the hot paths
  without changing the models' serialization surface.
