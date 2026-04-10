"""Core batch download implementation for tvkit.batch."""

from __future__ import annotations

import asyncio
import logging
import time

import websockets.exceptions

from tvkit.api.chart.exceptions import NoHistoricalDataError, StreamConnectionError
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.batch.exceptions import BatchDownloadError
from tvkit.batch.models import (
    BatchDownloadRequest,
    BatchDownloadSummary,
    ErrorInfo,
    SymbolResult,
)
from tvkit.symbols import normalize_symbols

logger: logging.Logger = logging.getLogger(__name__)

# Exceptions that indicate a transient failure — safe to retry.
# Intentionally narrow — only exceptions with a clear transient signal:
#   StreamConnectionError:            WebSocket dropped; retrying opens a fresh connection
#   websockets.exceptions.*:          Underlying protocol error — typically transient
#   TimeoutError (asyncio):           Request timed out — may succeed on next attempt
#
# Intentionally excluded:
#   RuntimeError:                     Too broad; non-transient OHLCV logic failures would
#                                     be silently retried and downgraded to failures
#   ValueError:                       Programmer error / bad input — retrying cannot fix it
#   NoHistoricalDataError(RuntimeError): TradingView confirms data absence — permanent
_RETRYABLE: tuple[type[BaseException], ...] = (
    StreamConnectionError,
    websockets.exceptions.WebSocketException,
    TimeoutError,
)


async def _fetch_one(
    symbol: str,
    semaphore: asyncio.Semaphore,
    request: BatchDownloadRequest,
) -> SymbolResult:
    """Fetch historical OHLCV bars for a single symbol with per-attempt semaphore and retry.

    The semaphore is acquired inside the retry loop (per attempt), not around the loop.
    This ensures backoff sleep never occupies a concurrency slot — other symbols can
    start their attempts while this one sleeps between retries.

    Any exception not matched by the retryable or non-retryable clauses is caught by the
    final broad handler, which converts it into a failed SymbolResult. This prevents
    unexpected exceptions from escaping and aborting sibling tasks in asyncio.gather().

    Args:
        symbol: Canonical symbol in EXCHANGE:SYMBOL format.
        semaphore: Shared asyncio.Semaphore capping in-flight connections.
        request: Validated BatchDownloadRequest with retry and auth config.

    Returns:
        SymbolResult with success=True on any successful attempt, or
        success=False after all attempts are exhausted or a non-retryable exception occurs.
        Never raises — unexpected exceptions are converted to failed SymbolResult entries.
    """
    t0 = time.monotonic()
    last_error: ErrorInfo | None = None
    auth_token = request.auth_token.get_secret_value() if request.auth_token else None
    attempt = 1  # initialised here so it is in scope after the loop

    for attempt in range(1, request.max_attempts + 1):
        try:
            async with semaphore:  # slot acquired per attempt, not per retry loop
                async with OHLCV(auth_token=auth_token, browser=request.browser) as client:
                    if request.bars_count is not None:
                        bars = await client.get_historical_ohlcv(
                            exchange_symbol=symbol,
                            interval=request.interval,
                            bars_count=request.bars_count,
                        )
                    else:
                        bars = await client.get_historical_ohlcv(
                            exchange_symbol=symbol,
                            interval=request.interval,
                            start=request.start,
                            end=request.end,
                        )
            # Slot released; success path
            return SymbolResult(
                symbol=symbol,
                bars=bars,
                success=True,
                error=None,
                attempts=attempt,
                elapsed_seconds=time.monotonic() - t0,
            )

        except (ValueError, NoHistoricalDataError) as exc:
            # Non-retryable: bad input or confirmed data absence.
            # Catch before _RETRYABLE because NoHistoricalDataError is a RuntimeError subclass
            # and could be matched by broad RuntimeError catches if present.
            last_error = ErrorInfo(
                message=str(exc),
                exception_type=type(exc).__qualname__,
                attempt=attempt,
            )
            logger.warning(
                "Symbol fetch failed (non-retryable)",
                extra={
                    "symbol": symbol,
                    "attempt": attempt,
                    "exception_type": last_error.exception_type,
                    "error": last_error.message,
                },
            )
            break  # no retry

        except _RETRYABLE as exc:
            last_error = ErrorInfo(
                message=str(exc),
                exception_type=type(exc).__qualname__,
                attempt=attempt,
            )
            logger.warning(
                "Symbol fetch attempt failed — will retry",
                extra={
                    "symbol": symbol,
                    "attempt": attempt,
                    "max_attempts": request.max_attempts,
                    "exception_type": last_error.exception_type,
                    "error": last_error.message,
                },
            )
            if attempt < request.max_attempts:
                backoff = min(
                    request.base_backoff * (2 ** (attempt - 1)),
                    request.max_backoff,
                )
                await asyncio.sleep(backoff)  # semaphore released during sleep

        except Exception as exc:  # noqa: BLE001
            # Catch-all: unexpected exceptions (internal bugs, unhandled OHLCV conditions).
            # Converted to a failed SymbolResult rather than propagating — prevents one
            # symbol's unexpected failure from cancelling sibling tasks in gather().
            last_error = ErrorInfo(
                message=str(exc),
                exception_type=type(exc).__qualname__,
                attempt=attempt,
            )
            logger.error(
                "Symbol fetch failed with unexpected exception",
                extra={
                    "symbol": symbol,
                    "attempt": attempt,
                    "exception_type": last_error.exception_type,
                    "error": last_error.message,
                },
                exc_info=True,
            )
            break  # no retry for unexpected exceptions

    # All attempts exhausted (or break from non-retryable / unexpected exception)
    return SymbolResult(
        symbol=symbol,
        bars=[],
        success=False,
        error=last_error,
        attempts=attempt,
        elapsed_seconds=time.monotonic() - t0,
    )


async def batch_download(request: BatchDownloadRequest) -> BatchDownloadSummary:
    """Download historical OHLCV bars for multiple symbols concurrently.

    Symbols are normalized and deduplicated (order-preserving) before dispatch.
    All symbols are started concurrently; the semaphore caps the number of
    in-flight WebSocket connections at ``request.concurrency``.

    Partial failures are collected in the returned ``BatchDownloadSummary``.
    If ``request.strict=True``, ``BatchDownloadError`` is raised instead, but
    the full summary (including successful results) is available on the exception.

    Args:
        request: Validated BatchDownloadRequest specifying symbols, interval,
                 fetch mode (bars_count or date range), concurrency, and retry policy.

    Returns:
        BatchDownloadSummary with one SymbolResult per deduplicated input symbol,
        in input order. Failed symbols are collected, not raised (unless strict=True).

    Raises:
        BatchDownloadError: If strict=True and one or more symbols fail.
    """
    # Normalize then deduplicate — order-preserving via dict.fromkeys
    canonical: list[str] = list(dict.fromkeys(normalize_symbols(request.symbols)))
    total = len(canonical)
    semaphore = asyncio.Semaphore(request.concurrency)
    t0_batch = time.monotonic()

    # completed_count is safe without a lock: asyncio tasks run cooperatively on
    # one event loop thread. There is no await between the read and write of
    # completed_count inside _task(), so no other coroutine can interleave.
    completed_count = 0

    async def _task(symbol: str) -> SymbolResult:
        nonlocal completed_count
        result = await _fetch_one(symbol=symbol, semaphore=semaphore, request=request)
        completed_count += 1
        if request.on_progress is not None:
            try:
                request.on_progress(result, completed_count, total)
            except Exception as cb_exc:  # noqa: BLE001
                # Callback failure is logged and swallowed — a bad callback must not
                # abort the batch or cancel successfully-downloaded symbols.
                logger.error(
                    "on_progress callback raised an exception",
                    extra={
                        "symbol": symbol,
                        "completed": completed_count,
                        "total": total,
                        "error": str(cb_exc),
                        "exception_type": type(cb_exc).__qualname__,
                    },
                    exc_info=True,
                )
        log_level = logging.INFO if result.success else logging.WARNING
        logger.log(
            log_level,
            "Symbol batch result",
            extra={
                "symbol": symbol,
                "success": result.success,
                "bars": len(result.bars),
                "attempts": result.attempts,
                "elapsed": result.elapsed_seconds,
            },
        )
        return result

    results: list[SymbolResult] = list(await asyncio.gather(*(_task(s) for s in canonical)))

    success_count = sum(1 for r in results if r.success)
    summary = BatchDownloadSummary(
        results=results,
        total_count=total,
        success_count=success_count,
        failure_count=total - success_count,
        elapsed_seconds=time.monotonic() - t0_batch,
        interval=request.interval,
    )

    logger.info(
        "Batch download complete",
        extra={
            "total": total,
            "success": success_count,
            "failure": total - success_count,
            "elapsed": summary.elapsed_seconds,
        },
    )

    if request.strict and summary.failure_count > 0:
        raise BatchDownloadError(
            f"{summary.failure_count} of {total} symbols failed",
            summary=summary,
        )

    return summary
