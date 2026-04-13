"""Tests for tvkit.batch — async batch downloader.

Covers:
- Single-symbol success
- Strict-mode failure escalation
- Partial failure (strict=False)
- Symbol deduplication (order-preserving, multi-symbol)
- Retry then success (transient failure on attempt 1)
- Retry exhaustion (all attempts fail)
- Non-retryable ValueError (no retry)
- Non-retryable NoHistoricalDataError (no retry)
- on_progress callback behavior
- BatchDownloadRequest mutual-exclusivity validation
Phase 2 additions:
- Full BatchDownloadRequest validation (interval, browser, concurrency, max_attempts,
  date-range order, invalid ISO 8601, empty symbols)
- auth_token SecretStr: repr() and log non-disclosure
- ErrorInfo.exception_type and ErrorInfo.attempt correctness (non-retryable, exhaustion,
  catch-all paths)
- Structured logging LogRecord field assertions (WARNING per-attempt, WARNING non-retryable,
  ERROR catch-all with exc_info, INFO batch-complete)
- catch-all handler converts unexpected exception to SymbolResult failure
Phase 3 additions:
- raise_if_failed(): raises BatchDownloadError on partial failure; no-op on full success
- raise_if_failed(): error message contains counts; exc.summary identity; exc.failed_symbols
- on_progress multi-symbol: invocation count == symbol count; completed counter 1-based
- on_progress invoked for failed symbols (not just successes)
- failed_symbols computed field: empty on full success
- successful_symbols computed field: empty on full failure
- model_dump() includes both computed fields
"""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from tvkit.api.chart.exceptions import NoHistoricalDataError, StreamConnectionError
from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.batch import BatchDownloadRequest, batch_download
from tvkit.batch.exceptions import BatchDownloadError

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_bars() -> list[OHLCVBar]:
    return [
        OHLCVBar(
            timestamp=1700000000.0,
            open=100.0,
            high=105.0,
            low=99.0,
            close=104.0,
            volume=1_000_000.0,
        )
    ]


def _make_mock_client(bars: list[OHLCVBar]) -> AsyncMock:
    """Return an AsyncMock OHLCV context manager that returns bars on get_historical_ohlcv."""
    client = AsyncMock()
    client.get_historical_ohlcv.return_value = bars
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _make_failing_client(exc: Exception) -> AsyncMock:
    """Return an AsyncMock OHLCV context manager that raises exc on get_historical_ohlcv."""
    client = AsyncMock()
    client.get_historical_ohlcv.side_effect = exc
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_success(mock_bars: list[OHLCVBar]) -> None:
    """Single symbol fetched successfully — summary counts and result contents correct."""
    with patch("tvkit.batch.downloader.OHLCV", return_value=_make_mock_client(mock_bars)):
        summary = await batch_download(
            BatchDownloadRequest(symbols=["NASDAQ:AAPL"], interval="1D", bars_count=1)
        )

    assert summary.success_count == 1
    assert summary.failure_count == 0
    assert summary.total_count == 1
    assert summary.results[0].symbol == "NASDAQ:AAPL"
    assert summary.results[0].success is True
    assert summary.results[0].bars == mock_bars
    assert summary.results[0].error is None
    assert summary.results[0].attempts == 1


# ---------------------------------------------------------------------------
# Strict mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strict_raises_on_failure() -> None:
    """strict=True raises BatchDownloadError when any symbol fails; summary is attached."""
    with patch(
        "tvkit.batch.downloader.OHLCV",
        return_value=_make_failing_client(StreamConnectionError("network down")),
    ):
        with pytest.raises(BatchDownloadError) as exc_info:
            await batch_download(
                BatchDownloadRequest(
                    symbols=["NASDAQ:AAPL"],
                    interval="1D",
                    bars_count=1,
                    max_attempts=1,
                    strict=True,
                )
            )

    err = exc_info.value
    assert err.summary.failure_count == 1
    assert err.summary.success_count == 0
    assert "NASDAQ:AAPL" in err.failed_symbols


# ---------------------------------------------------------------------------
# Partial failure (strict=False)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strict_false_partial_failure(mock_bars: list[OHLCVBar]) -> None:
    """strict=False collects failures without raising; success and failure both present."""
    good_client = _make_mock_client(mock_bars)
    bad_client = _make_failing_client(StreamConnectionError("timeout"))

    call_count = 0

    def client_factory(*args: object, **kwargs: object) -> AsyncMock:
        nonlocal call_count
        call_count += 1
        return good_client if call_count == 1 else bad_client

    with patch("tvkit.batch.downloader.OHLCV", side_effect=client_factory):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL", "NASDAQ:MSFT"],
                interval="1D",
                bars_count=1,
                max_attempts=1,
                strict=False,
            )
        )

    assert summary.total_count == 2
    assert summary.success_count == 1
    assert summary.failure_count == 1
    assert "NASDAQ:MSFT" in summary.failed_symbols
    assert "NASDAQ:AAPL" in summary.successful_symbols


# ---------------------------------------------------------------------------
# Symbol deduplication
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_symbol_deduplication_order_preserved(mock_bars: list[OHLCVBar]) -> None:
    """Duplicates are removed (first-seen wins); order of distinct symbols is preserved.

    Input:  ["NASDAQ:MSFT", "NASDAQ:AAPL", "nasdaq:msft"]
    After normalization + dedup:  ["NASDAQ:MSFT", "NASDAQ:AAPL"]
    Expected result order:  MSFT first, AAPL second.
    """
    mock_client = _make_mock_client(mock_bars)

    with patch("tvkit.batch.downloader.OHLCV", return_value=mock_client) as mock_ohlcv:
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:MSFT", "NASDAQ:AAPL", "nasdaq:msft"],
                interval="1D",
                bars_count=1,
            )
        )

    assert summary.total_count == 2
    assert summary.success_count == 2
    assert summary.results[0].symbol == "NASDAQ:MSFT"
    assert summary.results[1].symbol == "NASDAQ:AAPL"
    # Two distinct symbols → two OHLCV constructions
    assert mock_ohlcv.call_count == 2


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_then_success(mock_bars: list[OHLCVBar]) -> None:
    """Symbol fails on attempt 1 (transient) then succeeds on attempt 2; attempts == 2."""
    fail_client = _make_failing_client(StreamConnectionError("dropped"))
    ok_client = _make_mock_client(mock_bars)

    call_count = 0

    def client_factory(*args: object, **kwargs: object) -> AsyncMock:
        nonlocal call_count
        call_count += 1
        return fail_client if call_count == 1 else ok_client

    with patch("tvkit.batch.downloader.OHLCV", side_effect=client_factory):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
                max_attempts=3,
                base_backoff=0.0001,  # near-zero backoff to keep the test fast
            )
        )

    result = summary.results[0]
    assert result.success is True
    assert result.attempts == 2
    assert result.bars == mock_bars


@pytest.mark.asyncio
async def test_retry_exhaustion() -> None:
    """All attempts fail; result is failure with attempts == max_attempts."""
    with patch(
        "tvkit.batch.downloader.OHLCV",
        return_value=_make_failing_client(StreamConnectionError("down")),
    ):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
                max_attempts=3,
                base_backoff=0.0001,
            )
        )

    result = summary.results[0]
    assert result.success is False
    assert result.attempts == 3
    assert result.error is not None
    assert result.bars == []


# ---------------------------------------------------------------------------
# Non-retryable exceptions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_retryable_value_error() -> None:
    """ValueError is not retried; result is failure with attempts == 1."""
    with patch(
        "tvkit.batch.downloader.OHLCV",
        return_value=_make_failing_client(ValueError("bad symbol")),
    ):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
                max_attempts=3,
            )
        )

    result = summary.results[0]
    assert result.success is False
    assert result.attempts == 1
    assert result.error is not None
    assert "ValueError" in result.error.exception_type


@pytest.mark.asyncio
async def test_non_retryable_no_historical_data() -> None:
    """NoHistoricalDataError is not retried despite being a RuntimeError subclass."""
    with patch(
        "tvkit.batch.downloader.OHLCV",
        return_value=_make_failing_client(NoHistoricalDataError("no data")),
    ):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
                max_attempts=3,
            )
        )

    result = summary.results[0]
    assert result.success is False
    assert result.attempts == 1
    assert result.error is not None
    assert "NoHistoricalDataError" in result.error.exception_type


# ---------------------------------------------------------------------------
# on_progress callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_progress_callback(mock_bars: list[OHLCVBar]) -> None:
    """on_progress is called once per symbol with correct (result, completed, total) args."""
    calls: list[tuple[object, int, int]] = []

    def progress(result: object, completed: int, total: int) -> None:
        calls.append((result, completed, total))

    with patch("tvkit.batch.downloader.OHLCV", return_value=_make_mock_client(mock_bars)):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
                on_progress=progress,
            )
        )

    assert len(calls) == 1
    result_arg, completed_arg, total_arg = calls[0]
    assert result_arg is summary.results[0]
    assert completed_arg == 1  # 1-based
    assert total_arg == 1


# ---------------------------------------------------------------------------
# BatchDownloadRequest validation
# ---------------------------------------------------------------------------


def test_request_validation_mutual_exclusivity() -> None:
    """Providing both bars_count and start raises ValidationError."""
    with pytest.raises(ValidationError):
        BatchDownloadRequest(
            symbols=["NASDAQ:AAPL"],
            interval="1D",
            bars_count=10,
            start="2024-01-01",
        )


def test_request_validation_neither_provided() -> None:
    """Providing neither bars_count nor start raises ValidationError."""
    with pytest.raises(ValidationError):
        BatchDownloadRequest(
            symbols=["NASDAQ:AAPL"],
            interval="1D",
        )


def test_request_validation_async_callback_rejected() -> None:
    """Async callable passed as on_progress raises ValidationError at construction."""

    async def async_cb(result: object, completed: int, total: int) -> None:
        pass  # pragma: no cover

    with pytest.raises(ValidationError, match="synchronous callable"):
        BatchDownloadRequest(
            symbols=["NASDAQ:AAPL"],
            interval="1D",
            bars_count=1,
            on_progress=async_cb,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_on_progress_callback_exception_swallowed(mock_bars: list[OHLCVBar]) -> None:
    """A callback that raises does not abort the batch; summary is still returned."""

    def bad_callback(result: object, completed: int, total: int) -> None:
        raise RuntimeError("callback bug")

    with patch("tvkit.batch.downloader.OHLCV", return_value=_make_mock_client(mock_bars)):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
                on_progress=bad_callback,
            )
        )

    # Batch completes successfully despite the callback raising
    assert summary.success_count == 1
    assert summary.failure_count == 0


# ---------------------------------------------------------------------------
# Phase 2: BatchDownloadRequest validation
# ---------------------------------------------------------------------------


def test_empty_symbols_raises() -> None:
    """Empty symbols list raises ValidationError (min_length=1 on symbols field)."""
    with pytest.raises(ValidationError):
        BatchDownloadRequest(symbols=[], interval="1D", bars_count=1)


def test_invalid_interval_raises() -> None:
    """Unrecognised interval string raises ValidationError."""
    with pytest.raises(ValidationError, match="[Ii]nterval"):
        BatchDownloadRequest(symbols=["NASDAQ:AAPL"], interval="INVALID", bars_count=1)


def test_invalid_browser_raises() -> None:
    """Unsupported browser string raises ValidationError."""
    with pytest.raises(ValidationError, match="[Bb]rowser"):
        BatchDownloadRequest(
            symbols=["NASDAQ:AAPL"],
            interval="1D",
            bars_count=1,
            browser="safari",
        )


def test_invalid_concurrency_zero_raises() -> None:
    """concurrency=0 raises ValidationError (ge=1)."""
    with pytest.raises(ValidationError):
        BatchDownloadRequest(
            symbols=["NASDAQ:AAPL"],
            interval="1D",
            bars_count=1,
            concurrency=0,
        )


def test_invalid_max_attempts_zero_raises() -> None:
    """max_attempts=0 raises ValidationError (ge=1)."""
    with pytest.raises(ValidationError):
        BatchDownloadRequest(
            symbols=["NASDAQ:AAPL"],
            interval="1D",
            bars_count=1,
            max_attempts=0,
        )


def test_end_before_start_raises() -> None:
    """end <= start raises ValidationError from validate_fetch_mode."""
    with pytest.raises(ValidationError, match="[Ee]nd"):
        BatchDownloadRequest(
            symbols=["NASDAQ:AAPL"],
            interval="1D",
            start="2024-06-01",
            end="2024-01-01",
        )


def test_invalid_iso_datetime_raises() -> None:
    """Unparseable start string raises ValidationError."""
    with pytest.raises(ValidationError):
        BatchDownloadRequest(
            symbols=["NASDAQ:AAPL"],
            interval="1D",
            start="not-a-date",
        )


# ---------------------------------------------------------------------------
# Phase 2: auth_token SecretStr non-disclosure
# ---------------------------------------------------------------------------


def test_auth_token_secret_str_repr() -> None:
    """repr() of a BatchDownloadRequest never exposes the raw auth_token value."""
    secret = "super_secret_token_12345"
    request = BatchDownloadRequest(
        symbols=["NASDAQ:AAPL"],
        interval="1D",
        bars_count=1,
        auth_token=secret,
    )
    assert secret not in repr(request)


@pytest.mark.asyncio
async def test_auth_token_not_in_logs(
    mock_bars: list[OHLCVBar],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The raw auth_token value never appears in any log record after a batch run."""
    secret = "super_secret_token_67890"
    request = BatchDownloadRequest(
        symbols=["NASDAQ:AAPL"],
        interval="1D",
        bars_count=1,
        auth_token=secret,
    )
    with caplog.at_level(logging.DEBUG, logger="tvkit.batch.downloader"):
        with patch("tvkit.batch.downloader.OHLCV", return_value=_make_mock_client(mock_bars)):
            await batch_download(request)

    all_log_text = " ".join(r.getMessage() for r in caplog.records)
    assert secret not in all_log_text


# ---------------------------------------------------------------------------
# Phase 2: ErrorInfo correctness (exception_type + attempt)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_info_on_non_retryable_exception_type() -> None:
    """Non-retryable ValueError: error.exception_type contains 'ValueError', attempt==1."""
    with patch(
        "tvkit.batch.downloader.OHLCV",
        return_value=_make_failing_client(ValueError("bad input")),
    ):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
                max_attempts=3,
            )
        )

    result = summary.results[0]
    assert result.success is False
    assert result.error is not None
    assert "ValueError" in result.error.exception_type
    assert result.error.attempt == 1  # no retries


@pytest.mark.asyncio
async def test_error_info_on_retry_exhaustion_exception_type() -> None:
    """Retry exhaustion: error.exception_type contains 'StreamConnectionError', attempt==max_attempts."""
    max_attempts = 3
    with patch(
        "tvkit.batch.downloader.OHLCV",
        return_value=_make_failing_client(StreamConnectionError("dropped")),
    ):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
                max_attempts=max_attempts,
                base_backoff=0.0001,
            )
        )

    result = summary.results[0]
    assert result.success is False
    assert result.error is not None
    assert "StreamConnectionError" in result.error.exception_type
    assert result.error.attempt == max_attempts


@pytest.mark.asyncio
async def test_error_info_on_catch_all_exception_type() -> None:
    """Unexpected KeyError: caught by broad handler → error.exception_type contains 'KeyError'."""
    with patch(
        "tvkit.batch.downloader.OHLCV",
        return_value=_make_failing_client(KeyError("unexpected")),
    ):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
                max_attempts=2,
            )
        )

    result = summary.results[0]
    assert result.success is False
    assert result.error is not None
    assert "KeyError" in result.error.exception_type
    assert result.error.attempt >= 1


# ---------------------------------------------------------------------------
# Phase 2: Structured logging — LogRecord field assertions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retryable_warning_log_fields(caplog: pytest.LogCaptureFixture) -> None:
    """WARNING log on retryable failure includes symbol, attempt, max_attempts, exception_type."""
    with caplog.at_level(logging.WARNING, logger="tvkit.batch.downloader"):
        with patch(
            "tvkit.batch.downloader.OHLCV",
            return_value=_make_failing_client(StreamConnectionError("dropped")),
        ):
            await batch_download(
                BatchDownloadRequest(
                    symbols=["NASDAQ:AAPL"],
                    interval="1D",
                    bars_count=1,
                    max_attempts=2,
                    base_backoff=0.0001,
                )
            )

    # Find a WARNING record from the retryable path
    retry_records = [
        r for r in caplog.records if r.levelno == logging.WARNING and "will retry" in r.getMessage()
    ]
    assert retry_records, "Expected at least one WARNING with 'will retry'"
    rec = retry_records[0]
    assert rec.symbol == "NASDAQ:AAPL"  # type: ignore[attr-defined]
    assert rec.attempt == 1  # type: ignore[attr-defined]
    assert rec.max_attempts == 2  # type: ignore[attr-defined]
    assert "StreamConnectionError" in rec.exception_type  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_non_retryable_warning_log_fields(caplog: pytest.LogCaptureFixture) -> None:
    """WARNING log on non-retryable failure includes symbol, attempt, exception_type."""
    with caplog.at_level(logging.WARNING, logger="tvkit.batch.downloader"):
        with patch(
            "tvkit.batch.downloader.OHLCV",
            return_value=_make_failing_client(ValueError("bad")),
        ):
            await batch_download(
                BatchDownloadRequest(
                    symbols=["NASDAQ:AAPL"],
                    interval="1D",
                    bars_count=1,
                    max_attempts=3,
                )
            )

    non_retryable_records = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "non-retryable" in r.getMessage()
    ]
    assert non_retryable_records, "Expected at least one WARNING with 'non-retryable'"
    rec = non_retryable_records[0]
    assert rec.symbol == "NASDAQ:AAPL"  # type: ignore[attr-defined]
    assert rec.attempt == 1  # type: ignore[attr-defined]
    assert "ValueError" in rec.exception_type  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unexpected_exception_error_log(caplog: pytest.LogCaptureFixture) -> None:
    """Unexpected exception is logged at ERROR level with exc_info and correct fields."""
    with caplog.at_level(logging.ERROR, logger="tvkit.batch.downloader"):
        with patch(
            "tvkit.batch.downloader.OHLCV",
            return_value=_make_failing_client(KeyError("unexpected")),
        ):
            summary = await batch_download(
                BatchDownloadRequest(
                    symbols=["NASDAQ:AAPL"],
                    interval="1D",
                    bars_count=1,
                    max_attempts=1,
                )
            )

    # Batch still returns a summary — exception was absorbed
    assert summary.failure_count == 1

    error_records = [
        r
        for r in caplog.records
        if r.levelno == logging.ERROR and "unexpected" in r.getMessage().lower()
    ]
    assert error_records, "Expected at least one ERROR log for unexpected exception"
    rec = error_records[0]
    assert rec.exc_info is not None  # exc_info=True was passed
    assert rec.symbol == "NASDAQ:AAPL"  # type: ignore[attr-defined]
    assert "KeyError" in rec.exception_type  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_batch_complete_info_log_fields(
    mock_bars: list[OHLCVBar],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """INFO 'Batch download complete' log includes total, success, failure, elapsed fields."""
    with caplog.at_level(logging.INFO, logger="tvkit.batch.downloader"):
        with patch("tvkit.batch.downloader.OHLCV", return_value=_make_mock_client(mock_bars)):
            summary = await batch_download(
                BatchDownloadRequest(
                    symbols=["NASDAQ:AAPL", "NASDAQ:MSFT"],
                    interval="1D",
                    bars_count=1,
                )
            )

    complete_records = [
        r
        for r in caplog.records
        if r.levelno == logging.INFO and "complete" in r.getMessage().lower()
    ]
    assert complete_records, "Expected at least one INFO log with 'complete'"
    rec = complete_records[0]
    assert rec.total == summary.total_count  # type: ignore[attr-defined]
    assert rec.success == summary.success_count  # type: ignore[attr-defined]
    assert rec.failure == summary.failure_count  # type: ignore[attr-defined]
    assert rec.elapsed >= 0.0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Phase 2: catch-all handler converts unexpected exception to failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unexpected_exception_converted_to_failure() -> None:
    """KeyError from inside OHLCV is caught by the broad handler → SymbolResult failure."""
    with patch(
        "tvkit.batch.downloader.OHLCV",
        return_value=_make_failing_client(KeyError("internal oops")),
    ):
        # batch_download must NOT raise — the exception is absorbed
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
                max_attempts=1,
            )
        )

    assert summary.failure_count == 1
    assert summary.success_count == 0
    result = summary.results[0]
    assert result.success is False
    assert result.bars == []
    assert result.error is not None


# ---------------------------------------------------------------------------
# Phase 3: raise_if_failed()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raise_if_failed_raises_on_partial_failure() -> None:
    """raise_if_failed() raises BatchDownloadError when failure_count > 0."""
    with patch(
        "tvkit.batch.downloader.OHLCV",
        return_value=_make_failing_client(StreamConnectionError("down")),
    ):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
                max_attempts=1,
            )
        )

    assert summary.failure_count == 1
    with pytest.raises(BatchDownloadError):
        summary.raise_if_failed()


@pytest.mark.asyncio
async def test_raise_if_failed_noop_on_full_success(mock_bars: list[OHLCVBar]) -> None:
    """raise_if_failed() does not raise when all symbols succeed."""
    with patch("tvkit.batch.downloader.OHLCV", return_value=_make_mock_client(mock_bars)):
        summary = await batch_download(
            BatchDownloadRequest(symbols=["NASDAQ:AAPL"], interval="1D", bars_count=1)
        )

    assert summary.failure_count == 0
    summary.raise_if_failed()  # must not raise


@pytest.mark.asyncio
async def test_raise_if_failed_attaches_summary_and_failed_symbols() -> None:
    """raise_if_failed() attaches the exact same summary object; exc.failed_symbols matches."""
    with patch(
        "tvkit.batch.downloader.OHLCV",
        return_value=_make_failing_client(StreamConnectionError("down")),
    ):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
                max_attempts=1,
            )
        )

    with pytest.raises(BatchDownloadError) as exc_info:
        summary.raise_if_failed()

    exc = exc_info.value
    assert exc.summary is summary  # identity — same object, not a copy
    assert exc.failed_symbols == ["NASDAQ:AAPL"]


@pytest.mark.asyncio
async def test_raise_if_failed_error_message_includes_counts() -> None:
    """raise_if_failed() error message contains failure count and total count."""
    with patch(
        "tvkit.batch.downloader.OHLCV",
        return_value=_make_failing_client(StreamConnectionError("down")),
    ):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL", "NASDAQ:MSFT"],
                interval="1D",
                bars_count=1,
                max_attempts=1,
            )
        )

    with pytest.raises(BatchDownloadError) as exc_info:
        summary.raise_if_failed()

    message = str(exc_info.value)
    # Message must be actionable: both failure count and total are present
    assert "2" in message  # 2 failures
    assert "2" in message  # 2 total (also 2 in this case)


# ---------------------------------------------------------------------------
# Phase 3: on_progress multi-symbol behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_progress_multi_symbol_invocation_count(mock_bars: list[OHLCVBar]) -> None:
    """on_progress is called exactly once per symbol for a 3-symbol batch."""
    call_count = 0

    def progress(result: object, completed: int, total: int) -> None:
        nonlocal call_count
        call_count += 1

    with patch("tvkit.batch.downloader.OHLCV", return_value=_make_mock_client(mock_bars)):
        await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL", "NASDAQ:MSFT", "NYSE:JPM"],
                interval="1D",
                bars_count=1,
                on_progress=progress,
            )
        )

    assert call_count == 3


@pytest.mark.asyncio
async def test_on_progress_completed_counter_reaches_total(mock_bars: list[OHLCVBar]) -> None:
    """completed counter is 1-based and every value from 1 to total appears exactly once."""
    completed_values: list[int] = []
    total_values: list[int] = []

    def progress(result: object, completed: int, total: int) -> None:
        completed_values.append(completed)
        total_values.append(total)

    with patch("tvkit.batch.downloader.OHLCV", return_value=_make_mock_client(mock_bars)):
        await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL", "NASDAQ:MSFT", "NYSE:JPM"],
                interval="1D",
                bars_count=1,
                on_progress=progress,
            )
        )

    # Every value from 1 to 3 must appear exactly once (order not guaranteed in async)
    assert sorted(completed_values) == [1, 2, 3]
    # total is always the deduplicated symbol count
    assert all(t == 3 for t in total_values)


@pytest.mark.asyncio
async def test_on_progress_invoked_on_failure(mock_bars: list[OHLCVBar]) -> None:
    """on_progress is invoked for failed symbols as well as successful ones."""
    received_results: list[object] = []

    def progress(result: object, completed: int, total: int) -> None:
        received_results.append(result)

    good_client = _make_mock_client(mock_bars)
    bad_client = _make_failing_client(StreamConnectionError("down"))

    call_count = 0

    def client_factory(*args: object, **kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        return good_client if call_count == 1 else bad_client

    with patch("tvkit.batch.downloader.OHLCV", side_effect=client_factory):
        await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL", "NASDAQ:MSFT"],
                interval="1D",
                bars_count=1,
                max_attempts=1,
                on_progress=progress,
            )
        )

    # Callback must have been called for both symbols (one success, one failure)
    assert len(received_results) == 2
    successes = [r for r in received_results if getattr(r, "success", None) is True]
    failures = [r for r in received_results if getattr(r, "success", None) is False]
    assert len(successes) == 1
    assert len(failures) == 1


# ---------------------------------------------------------------------------
# Phase 3: computed fields — failed_symbols and successful_symbols
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_symbols_is_empty_on_full_success(mock_bars: list[OHLCVBar]) -> None:
    """failed_symbols is an empty list when all symbols succeed."""
    with patch("tvkit.batch.downloader.OHLCV", return_value=_make_mock_client(mock_bars)):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL", "NASDAQ:MSFT"],
                interval="1D",
                bars_count=1,
            )
        )

    assert summary.failed_symbols == []
    assert summary.successful_symbols == ["NASDAQ:AAPL", "NASDAQ:MSFT"]


@pytest.mark.asyncio
async def test_successful_symbols_is_empty_on_full_failure() -> None:
    """successful_symbols is an empty list when all symbols fail."""
    with patch(
        "tvkit.batch.downloader.OHLCV",
        return_value=_make_failing_client(StreamConnectionError("down")),
    ):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL", "NASDAQ:MSFT"],
                interval="1D",
                bars_count=1,
                max_attempts=1,
            )
        )

    assert summary.successful_symbols == []
    assert set(summary.failed_symbols) == {"NASDAQ:AAPL", "NASDAQ:MSFT"}


@pytest.mark.asyncio
async def test_summary_model_dump_includes_computed_fields(mock_bars: list[OHLCVBar]) -> None:
    """model_dump() output includes failed_symbols and successful_symbols computed fields."""
    with patch("tvkit.batch.downloader.OHLCV", return_value=_make_mock_client(mock_bars)):
        summary = await batch_download(
            BatchDownloadRequest(
                symbols=["NASDAQ:AAPL"],
                interval="1D",
                bars_count=1,
            )
        )

    dumped = summary.model_dump()
    assert "failed_symbols" in dumped
    assert "successful_symbols" in dumped
    assert dumped["failed_symbols"] == []
    assert dumped["successful_symbols"] == ["NASDAQ:AAPL"]
