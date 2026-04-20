# `tvkit.batch` — Batch Downloader Reference

**Module:** `tvkit.batch`
**Introduced in:** v1.0.0

High-throughput async batch downloader for historical OHLCV data. Fetches multiple symbols concurrently with bounded concurrency, per-symbol retry with exponential backoff, and a structured result summary separating successes from failures.

## Quick Example

```python
import asyncio
from tvkit.batch import batch_download, BatchDownloadRequest

async def main() -> None:
    request = BatchDownloadRequest(
        symbols=["NASDAQ:AAPL", "NASDAQ:MSFT", "NYSE:JPM"],
        interval="1D",
        bars_count=252,
        concurrency=5,
    )
    summary = await batch_download(request)

    for result in summary.results:
        if result.success and result.bars:
            print(f"{result.symbol}: {len(result.bars)} bars, last close {result.bars[-1].close}")
        elif not result.success:
            print(f"{result.symbol}: FAILED — {result.error.message}")

    print(f"Success: {summary.success_count}/{summary.total_count} in {summary.elapsed_seconds:.1f}s")

asyncio.run(main())
```

---

## Import

```python
from tvkit.batch import (
    batch_download,
    BatchDownloadRequest,
    BatchDownloadSummary,
    SymbolResult,
    ErrorInfo,
    BatchDownloadError,
)
```

---

## `batch_download()`

```python
async def batch_download(request: BatchDownloadRequest) -> BatchDownloadSummary:
```

Downloads historical OHLCV bars for multiple symbols concurrently.

All input symbols are normalized and deduplicated (order-preserving) before dispatch. A shared `asyncio.Semaphore` caps the number of in-flight WebSocket connections. Partial failures are collected in the returned `BatchDownloadSummary`; no exception is raised unless `request.strict=True`.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `request` | `BatchDownloadRequest` | Validated request specifying symbols, interval, fetch mode, concurrency, and retry policy |

### Returns

`BatchDownloadSummary` — one `SymbolResult` per deduplicated input symbol, in input order.

### Raises

| Exception | Condition |
|-----------|-----------|
| `BatchDownloadError` | `strict=True` and one or more symbols failed. `exc.summary` always contains the full results, including all partial successes. |

---

## `BatchDownloadRequest`

```python
class BatchDownloadRequest(BaseModel):
```

Validated input parameters for `batch_download()`. Enforces mutual exclusivity between `bars_count` and `start`/`end`, validates all field constraints at construction time, and normalizes `start`/`end` to UTC-aware datetimes.

Invalid parameters raise `pydantic.ValidationError` at construction time.

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `symbols` | `list[str]` | — | TradingView symbols. Normalized and deduplicated before fetch. Minimum 1 symbol required. |
| `interval` | `str` | `"1D"` | Timeframe interval. Valid values: `"1"`, `"5"`, `"15"`, `"30"`, `"60"`, `"1H"`, `"4H"`, `"1D"`, `"1W"`, `"1M"` |
| `bars_count` | `int \| None` | `None` | Number of most-recent bars per symbol. Mutually exclusive with `start`. Must be `> 0`. |
| `start` | `datetime \| None` | `None` | Range start. Accepts ISO 8601 string or `datetime`; normalized to UTC. Mutually exclusive with `bars_count`. `end` without `start` is invalid. |
| `end` | `datetime \| None` | `None` | Range end. Normalized to UTC. Requires `start` — `end` without `start` raises `ValidationError`. Defaults to current UTC time when `start` is set but `end` is omitted. Must be strictly after `start`. |
| `concurrency` | `int` | `5` | Maximum in-flight WebSocket connections at any moment. Must be `≥ 1`. |
| `max_attempts` | `int` | `3` | Per-symbol retry limit including the initial attempt. Must be `≥ 1`. |
| `base_backoff` | `float` | `1.0` | Initial backoff in seconds. Doubles each attempt up to `max_backoff`. Must be `> 0`. |
| `max_backoff` | `float` | `30.0` | Backoff ceiling in seconds. Must be `> 0`. |
| `auth_token` | `SecretStr \| None` | `None` | TradingView auth token. Stored as `SecretStr` — never appears in logs or `repr()`. |
| `browser` | `str \| None` | `None` | Browser for cookie extraction. Accepted values: `"chrome"`, `"firefox"`. |
| `on_progress` | `Callable[[SymbolResult, int, int], None] \| None` | `None` | Sync callback invoked after each symbol resolves. See callback contract below. Async callables raise `ValidationError` at construction. |
| `validate_symbols_before_fetch` | `bool` | `False` | Pre-validate symbols via TradingView HTTP API before fetching. Invalid symbols become `SymbolResult(success=False, attempts=0)`. Not recommended for batches > 200 symbols. |
| `strict` | `bool` | `False` | If `True`, raise `BatchDownloadError` when any symbol fails. |

### Validation rules

Invalid values raise `pydantic.ValidationError` at construction:

| Parameter | Rule |
|-----------|------|
| `symbols` | Non-empty list (`min_length=1`) |
| `bars_count` + `start` | Mutually exclusive — provide one, not both |
| Neither `bars_count` nor `start` | `ValidationError`: at least one fetch mode is required |
| `end` without `start` | `ValidationError`: `end` requires `start` |
| `end` ≤ `start` | `ValidationError`: `end` must be strictly after `start` |
| `interval` | Must be a valid tvkit interval string |
| `browser` | Must be `"chrome"` or `"firefox"` (or `None`) |
| `on_progress` | Must be synchronous — async callables raise `ValidationError` at construction |

### Datetime handling

`start` and `end` accept ISO 8601 strings or `datetime` objects. All are normalized to UTC-aware datetimes at construction time:

- ISO 8601 strings are parsed via `datetime.fromisoformat()`.
- **Naive `datetime` objects are assumed to be UTC** and converted to UTC-aware datetimes.
- Timezone-aware `datetime` objects are converted to UTC.

```python
# All equivalent — all produce the same UTC-aware datetime:
BatchDownloadRequest(symbols=["NASDAQ:AAPL"], interval="1D", start="2024-01-01")
BatchDownloadRequest(symbols=["NASDAQ:AAPL"], interval="1D", start="2024-01-01T00:00:00Z")
BatchDownloadRequest(symbols=["NASDAQ:AAPL"], interval="1D", start=datetime(2024, 1, 1))  # naive → UTC
```

### `on_progress` callback contract

```python
def on_progress(result: SymbolResult, completed: int, total: int) -> None: ...
```

- Called once per symbol after its terminal result (success or final-attempt failure).
- `completed` is 1-based; `total` is the deduplicated symbol count.
- The callback must be **synchronous** — async callables raise `ValidationError` at construction.
- Exceptions raised by the callback are logged at `ERROR` level and swallowed — a misbehaving callback does not abort the batch.
- Retry events (non-terminal failures) do not trigger the callback — only the final outcome does.

---

## `BatchDownloadSummary`

```python
class BatchDownloadSummary(BaseModel):
```

Aggregated result of a `batch_download()` call. `results` preserves deduplicated input order.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `results` | `list[SymbolResult]` | One `SymbolResult` per deduplicated input symbol, in input order |
| `total_count` | `int` | Symbol count after deduplication |
| `success_count` | `int` | Symbols fetched successfully |
| `failure_count` | `int` | Symbols that failed after all retries |
| `elapsed_seconds` | `float` | Total wall-clock seconds for the entire batch |
| `interval` | `str` | Interval used for all fetches |
| `failed_symbols` | `list[str]` | Computed — canonical symbols that failed (empty list on full success) |
| `successful_symbols` | `list[str]` | Computed — canonical symbols that succeeded |

`failed_symbols` and `successful_symbols` are `@computed_field` properties and appear in `model_dump()` output.

### `raise_if_failed()`

```python
def raise_if_failed(self) -> None:
```

Raises `BatchDownloadError` if `failure_count > 0`. Equivalent to having called `batch_download()` with `strict=True`, but callable after the fact — useful for pipelines that inspect the summary before deciding whether failures are fatal.

```python
import asyncio
from tvkit.batch import batch_download, BatchDownloadRequest

async def main() -> None:
    request = BatchDownloadRequest(
        symbols=["NASDAQ:AAPL", "NASDAQ:MSFT"],
        interval="1D",
        bars_count=252,
    )
    summary = await batch_download(request)
    print(f"Successful: {summary.successful_symbols}")
    summary.raise_if_failed()  # raises BatchDownloadError if failure_count > 0

asyncio.run(main())
```

---

## `SymbolResult`

```python
class SymbolResult(BaseModel):
```

Result for a single symbol in a batch download.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Canonical symbol in `EXCHANGE:SYMBOL` format |
| `bars` | `list[OHLCVBar]` | Fetched OHLCV bars, sorted chronologically (oldest first). Always a list — never `None`. Empty on failure, and may be empty on success if the server returned no data for the requested range. |
| `success` | `bool` | `True` if the fetch completed without error |
| `error` | `ErrorInfo \| None` | Structured error detail if `success=False`, else `None` |
| `attempts` | `int` | Number of fetch attempts. `0` = rejected at pre-flight (no fetch made); `1+` = fetch attempt count. |
| `elapsed_seconds` | `float` | Wall-clock seconds across all attempts for this symbol |

### Invariants

Enforced by `@model_validator` — construction raises `ValidationError` if violated:

- `success=True` → `error is None`
- `success=False` → `error is not None` and `bars` is empty

`bars` is always a `list` — never `None`. Callers can iterate `result.bars` without a `None` check, but should guard against an empty list before accessing `result.bars[-1]`.

---

## `ErrorInfo`

```python
class ErrorInfo(BaseModel):
```

Structured error record for a failed symbol fetch.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `message` | `str` | Human-readable error message |
| `exception_type` | `str` | Exception class name (e.g. `"StreamConnectionError"`, `"SymbolValidationError"`) |
| `attempt` | `int` | Attempt number when the error occurred. `0` = pre-flight rejection; `1+` = fetch attempt number. |

### `attempt` values

| `attempt` | Meaning |
|-----------|---------|
| `0` | Symbol rejected at pre-flight validation — no WebSocket connection was opened |
| `1+` | Error occurred during a fetch attempt; value is the attempt number on which it failed |

---

## `BatchDownloadError`

```python
class BatchDownloadError(Exception):
```

Raised by `batch_download()` when `strict=True` and one or more symbols fail, or by `BatchDownloadSummary.raise_if_failed()`.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `summary` | `BatchDownloadSummary` | Full result including both successful and failed symbols. Always populated — partial successes are always accessible even when this exception is raised. |
| `failed_symbols` | `list[str]` | Convenience accessor for `summary.failed_symbols` |

```python
import asyncio
from tvkit.batch import batch_download, BatchDownloadRequest, BatchDownloadError

async def main() -> None:
    request = BatchDownloadRequest(
        symbols=["NASDAQ:AAPL", "NASDAQ:INVALID_XYZ"],
        interval="1D",
        bars_count=10,
        strict=True,
    )
    try:
        summary = await batch_download(request)
    except BatchDownloadError as exc:
        print(f"Failed: {exc.failed_symbols}")
        # Partial successes always available on exc.summary:
        for result in exc.summary.results:
            if result.success and result.bars:
                print(f"{result.symbol}: {len(result.bars)} bars")

asyncio.run(main())
```

---

## Retry and Exception Handling

### Retryable exceptions

These exceptions trigger a retry with exponential backoff. Pre-flight validation failures are **not retried** — they are terminal by design.

| Exception | Source | Rationale |
|-----------|--------|-----------|
| `StreamConnectionError` | `tvkit.api.chart.exceptions` | WebSocket dropped — transient network failure |
| `websockets.exceptions.WebSocketException` | `websockets` | Underlying transport error |
| `TimeoutError` | `asyncio` | Request timed out |

### Non-retryable exceptions

These exceptions stop retry immediately — the symbol is recorded as failed without further attempts:

| Exception | Rationale |
|-----------|-----------|
| `ValueError` | Bad input — programmer error; retrying cannot succeed |
| `NoHistoricalDataError` | TradingView confirms no data exists for this symbol/range — permanent |

Any other unexpected exception is caught by a final broad handler, converted to a failed `SymbolResult`, and logged at `ERROR` with `exc_info=True`. This prevents one symbol's failure from cancelling sibling tasks in `asyncio.gather()`.

### Backoff formula

```
backoff = min(base_backoff * 2 ** (attempt - 1), max_backoff)
```

With defaults (`base_backoff=1.0`, `max_backoff=30.0`): 1.0s → 2.0s → 4.0s → 8.0s → … → 30.0s.

The semaphore is **released before** the backoff sleep — other symbols can start their attempts while this one waits between retries.

---

## Pre-flight Symbol Validation

When `validate_symbols_before_fetch=True`, all deduplicated symbols are validated via the TradingView HTTP API **before** any WebSocket fetch begins. Validation runs **serially** (one HTTP call per symbol, in order).

- Symbols confirmed invalid (HTTP 404) become `SymbolResult(success=False, attempts=0, error=ErrorInfo(attempt=0, exception_type="SymbolValidationError"))`. A `WARNING` is logged per skipped symbol.
- Symbols with indeterminate validation (transport or server failure) **fail open**: they proceed to the fetch phase unchanged. A `WARNING` is logged to indicate validation was unavailable for that symbol.
- A `WARNING` is emitted if the batch exceeds 200 symbols, because validation runs serially and adds one HTTP call per symbol before any fetch begins.

Use `error.attempt == 0` to distinguish pre-flight failures from fetch-phase failures (`error.attempt >= 1`).

> **Performance note**: Not recommended for batches > 200 symbols.

---

## Deduplication Behavior

Input symbols are normalized via `tvkit.symbols.normalize_symbols()` then deduplicated using order-preserving `dict.fromkeys()`. The `BatchDownloadSummary` reflects the deduplicated count.

```python
import asyncio
from tvkit.batch import batch_download, BatchDownloadRequest

async def main() -> None:
    # 5 inputs → 3 unique symbols after normalize + dedup
    request = BatchDownloadRequest(
        symbols=["NASDAQ:AAPL", "nasdaq:aapl", "NASDAQ:MSFT", "NASDAQ:MSFT", "NYSE:JPM"],
        interval="1D",
        bars_count=10,
    )
    summary = await batch_download(request)
    assert summary.total_count == 3
    assert len(summary.results) == 3

asyncio.run(main())
```

---

## See Also

- [Batch Download Guide](../../guides/batch-download.md) — workflow guide with complete patterns
- [Example script](../../../examples/batch_sp500_historical.py) — runnable demos
- [OHLCV Client reference](../chart/ohlcv.md) — the underlying single-symbol client
