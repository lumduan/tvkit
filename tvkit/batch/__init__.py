"""tvkit.batch — High-throughput async batch downloader for historical OHLCV data.

Provides ``batch_download()``: an async function that fetches historical OHLCV bars
for large symbol sets concurrently, with bounded concurrency, per-symbol retry with
exponential backoff, and a structured ``BatchDownloadSummary`` separating successes
from failures.

Example::

    from tvkit.batch import batch_download, BatchDownloadRequest

    request = BatchDownloadRequest(
        symbols=["NASDAQ:AAPL", "NASDAQ:MSFT", "NYSE:JPM"],
        interval="1D",
        bars_count=252,
        concurrency=5,
    )
    summary = await batch_download(request)

    for result in summary.results:
        if result.success:
            print(f"{result.symbol}: {len(result.bars)} bars")
        else:
            print(f"{result.symbol}: FAILED — {result.error.message}")

    print(f"Success: {summary.success_count}/{summary.total_count}")
"""

from tvkit.batch.downloader import batch_download
from tvkit.batch.exceptions import BatchDownloadError
from tvkit.batch.models import (
    BatchDownloadRequest,
    BatchDownloadSummary,
    ErrorInfo,
    SymbolResult,
)

__all__ = [
    "BatchDownloadError",
    "BatchDownloadRequest",
    "BatchDownloadSummary",
    "ErrorInfo",
    "SymbolResult",
    "batch_download",
]
