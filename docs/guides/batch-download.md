# Batch Download Guide

`tvkit.batch` provides `batch_download()` — an async function for fetching historical OHLCV data for large symbol sets concurrently. It handles bounded concurrency, per-symbol retry with exponential backoff, and structured partial-failure reporting.

---

## When to use `tvkit.batch`

Use `batch_download()` when you need to fetch historical bars for more than a handful of symbols. The single-symbol `OHLCV.get_historical_ohlcv()` is fine for one to a few symbols; for larger sets, manual `asyncio.gather()` loops overwhelm TradingView's server without a concurrency cap.

`batch_download()` handles:

- **Bounded concurrency** — a semaphore caps in-flight WebSocket connections
- **Per-symbol retry** — transient failures are retried with exponential backoff
- **Partial failure** — failed symbols are collected, not raised (by default)
- **Deduplication** — normalized duplicates are fetched only once

---

## Installation

`tvkit.batch` is included in `tvkit`. No extra dependencies are required.

```bash
uv add tvkit
```

---

## Basic Usage: bars-count mode

Fetch the N most recent bars for each symbol:

```python
import asyncio
from tvkit.batch import batch_download, BatchDownloadRequest

async def main() -> None:
    request = BatchDownloadRequest(
        symbols=["NASDAQ:AAPL", "NASDAQ:MSFT", "NASDAQ:NVDA"],
        interval="1D",
        bars_count=252,   # ~1 year of daily bars
        concurrency=5,
    )
    summary = await batch_download(request)

    for result in summary.results:
        if result.success:
            print(f"{result.symbol}: {len(result.bars)} bars, last close {result.bars[-1].close}")
        else:
            print(f"{result.symbol}: FAILED — {result.error.message}")

    print(f"Done: {summary.success_count}/{summary.total_count} in {summary.elapsed_seconds:.1f}s")

asyncio.run(main())
```

---

## Date-range mode

Fetch bars over a specific date range:

```python
from tvkit.batch import batch_download, BatchDownloadRequest

request = BatchDownloadRequest(
    symbols=symbols,
    interval="1D",
    start="2024-01-01",
    end="2024-12-31",
    concurrency=10,
)
summary = await batch_download(request)
```

- `start` and `end` accept ISO 8601 strings or `datetime` objects.
- Naive `datetime` objects are treated as UTC.
- `end` defaults to the current time if only `start` is provided.

---

## Progress reporting

Pass a sync callback to track progress as symbols complete:

```python
from tvkit.batch import batch_download, BatchDownloadRequest, SymbolResult

def on_progress(result: SymbolResult, completed: int, total: int) -> None:
    status = "OK" if result.success else "FAIL"
    print(f"[{completed}/{total}] {result.symbol} — {status}")

request = BatchDownloadRequest(
    symbols=symbols,
    interval="1D",
    bars_count=252,
    on_progress=on_progress,
)
summary = await batch_download(request)
```

**Callback contract:**
- Called once per symbol, after its terminal result (success or final-attempt failure).
- `completed` is 1-based; `total` is the deduplicated symbol count.
- The callback must be **synchronous** — async callables are rejected at construction.
- Exceptions raised by the callback are logged and swallowed — a bad callback does not abort the batch.

---

## Handling partial failures

By default, `batch_download()` collects failures and always returns a `BatchDownloadSummary`:

```python
summary = await batch_download(request)

# Inspect per-symbol outcomes
for result in summary.results:
    if result.success:
        process(result.symbol, result.bars)
    else:
        logger.error(
            "Symbol failed after %d attempts: %s",
            result.attempts,
            result.error.message,
        )

# Print a concise summary
print(f"Success: {summary.success_count}/{summary.total_count}")
print(f"Failed symbols: {summary.failed_symbols}")
```

### Strict mode — raise on any failure

Set `strict=True` to raise `BatchDownloadError` if any symbol fails:

```python
from tvkit.batch import batch_download, BatchDownloadRequest, BatchDownloadError

try:
    request = BatchDownloadRequest(
        symbols=symbols,
        interval="1D",
        bars_count=252,
        strict=True,
    )
    summary = await batch_download(request)
except BatchDownloadError as exc:
    print(f"Batch failed: {exc.failed_symbols}")
    # Partial results are still available on exc.summary:
    for result in exc.summary.results:
        if result.success:
            process(result)
```

### Deferred error check — `raise_if_failed()`

Inspect the summary first, then raise if needed:

```python
summary = await batch_download(request)

# Export whatever succeeded immediately
for result in summary.results:
    if result.success:
        await exporter.to_csv(result.bars, f"export/{result.symbol.replace(':', '_')}.csv")

# Now assert no failures (raises if any symbol failed)
summary.raise_if_failed()
```

---

## Authenticated batch download

Pass `auth_token` to access premium account limits and extended history:

```python
import os
from tvkit.batch import batch_download, BatchDownloadRequest

request = BatchDownloadRequest(
    symbols=symbols,
    interval="1H",
    bars_count=10_000,
    concurrency=5,
    auth_token=os.environ["TVKIT_AUTH_TOKEN"],  # stored as SecretStr — never logged
)
summary = await batch_download(request)
```

Or use browser cookie extraction:

```python
request = BatchDownloadRequest(
    symbols=symbols,
    interval="1D",
    bars_count=500,
    browser="chrome",  # or "firefox"
)
```

---

## Pre-flight symbol validation

Enable `validate_symbols_before_fetch` to reject clearly invalid symbols before any WebSocket connection is opened:

```python
request = BatchDownloadRequest(
    symbols=symbols,
    interval="1D",
    bars_count=252,
    validate_symbols_before_fetch=True,
)
summary = await batch_download(request)
```

- Symbols confirmed invalid (HTTP 404) become `SymbolResult(success=False, attempts=0)` immediately.
- Validation failures due to transport or server errors **fail open** — the symbol proceeds to the fetch phase unchanged.
- Pre-flight results use `error.attempt=0` to distinguish them from fetch-phase failures.

> **Note**: Each symbol requires one HTTP call before fetching begins. Not recommended for batches > 200 symbols.

---

## Tuning concurrency and retry

```python
request = BatchDownloadRequest(
    symbols=symbols,
    interval="1D",
    bars_count=500,
    concurrency=10,       # up to 10 in-flight connections
    max_attempts=5,       # retry each symbol up to 5 times
    base_backoff=0.5,     # start with 0.5s backoff
    max_backoff=60.0,     # cap backoff at 60s
)
```

**Semaphore behavior**: The semaphore is acquired **per network attempt**, not per retry loop. Backoff sleep is outside the semaphore — other symbols make progress while this one waits.

**Retryable exceptions**: `StreamConnectionError`, `websockets.WebSocketException`, `TimeoutError`

**Non-retryable exceptions**: `ValueError` (bad input), `NoHistoricalDataError` (TradingView confirms no data exists)

---

## Deduplication and normalization

Input symbols are normalized to `EXCHANGE:SYMBOL` format and deduplicated before dispatch. The `BatchDownloadSummary` reflects the deduplicated count.

```python
# These 5 inputs deduplicate to 3 unique symbols
request = BatchDownloadRequest(
    symbols=[
        "NASDAQ:AAPL",
        "nasdaq:aapl",    # case variant → same as NASDAQ:AAPL
        "NASDAQ:MSFT",
        "NASDAQ:MSFT",    # exact duplicate
        "NYSE:JPM",
    ],
    interval="1D",
    bars_count=10,
)
summary = await batch_download(request)
assert summary.total_count == 3
assert len(summary.results) == 3
```

---

## Exporting results

Combine with `tvkit.export.DataExporter` to save results to CSV or JSON:

```python
import asyncio
from tvkit.batch import batch_download, BatchDownloadRequest
from tvkit.export import DataExporter

async def main() -> None:
    request = BatchDownloadRequest(
        symbols=["NASDAQ:AAPL", "NASDAQ:MSFT"],
        interval="1D",
        bars_count=252,
    )
    summary = await batch_download(request)

    exporter = DataExporter()
    for result in summary.results:
        if result.success:
            filename = result.symbol.replace(":", "_")
            await exporter.to_csv(result.bars, f"export/{filename}.csv")
            print(f"Exported {result.symbol} → export/{filename}.csv")

asyncio.run(main())
```

---

## Runnable example

A complete demo script covering all major patterns is available at [examples/batch_sp500_historical.py](../../examples/batch_sp500_historical.py):

```bash
uv run python examples/batch_sp500_historical.py
```

Demos included:
1. Basic batch with rich progress bar
2. Deduplication behavior
3. Partial failure with `strict=False`
4. Strict mode with `BatchDownloadError`

---

## See Also

- [API Reference: tvkit.batch](../reference/batch/downloader.md) — complete parameter tables and model definitions
- [OHLCV Client](../reference/chart/ohlcv.md) — the underlying single-symbol client
- [DataExporter](../reference/export/exporter.md) — export results to CSV, JSON, or Polars
