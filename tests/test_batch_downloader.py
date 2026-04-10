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
"""

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
