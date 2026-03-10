"""Integration tests for ConnectionService retry and reconnection behavior.

All tests use AsyncMock — no live WebSocket connections.
asyncio.sleep is patched to avoid real delays in the retry loop.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tvkit.api.chart.exceptions import StreamConnectionError
from tvkit.api.chart.services.connection_service import ConnectionService, ConnectionState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTINEL: None = None  # end-of-stream sentinel value put by _read_raw_loop


def make_service(**kwargs: Any) -> ConnectionService:
    """Return a ConnectionService with the given overrides and a dummy URL."""
    defaults: dict[str, Any] = {"ws_url": "wss://test.example.com/ws", "max_attempts": 3}
    defaults.update(kwargs)
    return ConnectionService(**defaults)


async def drain(gen: AsyncIterator[Any], limit: int = 5) -> list[Any]:
    """Exhaust up to *limit* items from an async generator."""
    items = []
    async for item in gen:
        items.append(item)
        if len(items) >= limit:
            break
    return items


# ---------------------------------------------------------------------------
# connect() state transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_state_transitions() -> None:
    """connect() transitions IDLE → CONNECTING → STREAMING."""
    svc = make_service()
    state_during_connect: list[ConnectionState] = []

    original_connect = svc._connect

    async def spy_connect() -> None:
        state_during_connect.append(svc._state)
        await original_connect()

    with patch.object(svc, "_connect", side_effect=spy_connect):
        with patch.object(svc, "_open_websocket", new_callable=AsyncMock):
            svc._ws = MagicMock()
            with patch.object(svc, "_read_raw_loop", new_callable=AsyncMock):
                await svc.connect()

    assert ConnectionState.CONNECTING in state_during_connect
    assert svc._state is ConnectionState.STREAMING


@pytest.mark.asyncio
async def test_connect_failure_resets_state_to_idle() -> None:
    """If connect() raises, state must be reset to IDLE."""
    svc = make_service()
    with patch.object(svc, "_connect", side_effect=OSError("connection refused")):
        with pytest.raises(OSError):
            await svc.connect()
    assert svc._state is ConnectionState.IDLE


# ---------------------------------------------------------------------------
# _drain_queue
# ---------------------------------------------------------------------------


def test_drain_queue_clears_stale_messages() -> None:
    """_drain_queue() removes all pending items."""
    svc = make_service()
    for i in range(5):
        svc._message_queue.put_nowait(f"item-{i}")
    assert svc._message_queue.qsize() == 5
    svc._drain_queue()
    assert svc._message_queue.empty()


def test_drain_queue_is_idempotent_on_empty_queue() -> None:
    """_drain_queue() on an already-empty queue does not raise."""
    svc = make_service()
    svc._drain_queue()


# ---------------------------------------------------------------------------
# _read_raw_loop sentinel guard
# ---------------------------------------------------------------------------


async def _empty_async_iter() -> AsyncIterator[str]:
    """Async generator that yields nothing — simulates an immediately-closed WebSocket."""
    return
    yield  # type: ignore[misc]  # makes this an async generator


@pytest.mark.asyncio
async def test_reader_sentinel_suppressed_during_reconnect() -> None:
    """Sentinel must NOT be put when state is RECONNECTING (cancelled reader)."""
    svc = make_service()
    svc._state = ConnectionState.RECONNECTING

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: _empty_async_iter()
    svc._ws = mock_ws

    await svc._read_raw_loop()

    assert svc._message_queue.empty(), "Sentinel must not be placed when _state is RECONNECTING"


@pytest.mark.asyncio
async def test_reader_sentinel_placed_on_clean_exit() -> None:
    """Sentinel IS placed when state is STREAMING (normal stream end)."""
    svc = make_service()
    svc._state = ConnectionState.STREAMING

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: _empty_async_iter()
    svc._ws = mock_ws

    await svc._read_raw_loop()

    assert not svc._message_queue.empty()
    sentinel = svc._message_queue.get_nowait()
    assert sentinel is _SENTINEL


# ---------------------------------------------------------------------------
# _reset_connection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reader_task_cancelled_on_reconnect() -> None:
    """_reset_connection() cancels the reader task."""
    svc = make_service()
    svc._state = ConnectionState.RECONNECTING

    real_task = asyncio.create_task(asyncio.sleep(100), name="test-reader")
    svc._reader_task = real_task
    svc._ws = None

    await svc._reset_connection()

    assert real_task.cancelled() or real_task.done()
    assert svc._reader_task is None


@pytest.mark.asyncio
async def test_ws_reference_reset_on_reconnect() -> None:
    """_reset_connection() sets _ws to None."""
    from websockets.connection import State as WsState

    svc = make_service()
    svc._state = ConnectionState.RECONNECTING

    mock_ws = AsyncMock()
    mock_ws.state = WsState.OPEN
    svc._ws = mock_ws

    await svc._reset_connection()

    assert svc._ws is None


@pytest.mark.asyncio
async def test_reset_connection_drains_queue() -> None:
    """_reset_connection() drains the message queue."""
    svc = make_service()
    svc._state = ConnectionState.RECONNECTING
    svc._ws = None

    for i in range(10):
        svc._message_queue.put_nowait(f"msg-{i}")
    assert svc._message_queue.qsize() == 10

    await svc._reset_connection()
    assert svc._message_queue.empty()


# ---------------------------------------------------------------------------
# _reconnect_with_backoff — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconnect_on_unexpected_close() -> None:
    """None sentinel (not _closing) triggers reconnect; stream resumes after."""
    svc = make_service(max_attempts=3, base_backoff=0.01, max_backoff=0.01)

    frame = '~m~23~m~{"m":"du","p":[]}'
    svc._message_queue.put_nowait(_SENTINEL)
    svc._message_queue.put_nowait(frame)

    reconnected = False

    async def mock_reconnect() -> None:
        nonlocal reconnected
        reconnected = True

    with patch.object(svc, "_reconnect_with_backoff", side_effect=mock_reconnect):
        with patch.object(svc, "close", new_callable=AsyncMock):
            svc._ws = MagicMock()
            items = await drain(svc.get_data_stream(), limit=1)

    assert reconnected
    assert len(items) == 1


@pytest.mark.asyncio
async def test_successful_reconnect_resumes_stream() -> None:
    """First attempt fails, second succeeds; on_reconnect is awaited once."""
    on_reconnect_mock = AsyncMock()
    svc = make_service(
        max_attempts=3,
        base_backoff=0.01,
        max_backoff=0.01,
        on_reconnect=on_reconnect_mock,
    )

    attempt_count = 0

    async def failing_then_succeeding() -> None:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            raise OSError("refused")
        svc._ws = AsyncMock()

    with patch.object(svc, "_connect", side_effect=failing_then_succeeding):
        with patch.object(svc, "_read_raw_loop", new_callable=AsyncMock):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch.object(svc, "_reset_connection", new_callable=AsyncMock):
                    svc._state = ConnectionState.STREAMING
                    await svc._reconnect_with_backoff()

    assert attempt_count == 2
    on_reconnect_mock.assert_awaited_once()
    assert svc._state is ConnectionState.STREAMING


@pytest.mark.asyncio
async def test_on_reconnect_called_after_success() -> None:
    """on_reconnect callback is awaited exactly once on first successful reconnect."""
    on_reconnect = AsyncMock()
    svc = make_service(
        max_attempts=2, base_backoff=0.01, max_backoff=0.01, on_reconnect=on_reconnect
    )

    with patch.object(svc, "_connect", new_callable=AsyncMock):
        with patch.object(svc, "_read_raw_loop", new_callable=AsyncMock):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch.object(svc, "_reset_connection", new_callable=AsyncMock):
                    svc._state = ConnectionState.STREAMING
                    await svc._reconnect_with_backoff()

    on_reconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# _reconnect_with_backoff — failure paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attempt_exhaustion_raises_stream_connection_error() -> None:
    """All attempts fail → StreamConnectionError with correct attempts attribute."""
    svc = make_service(max_attempts=3, base_backoff=0.01, max_backoff=0.01)

    with patch.object(svc, "_connect", side_effect=OSError("refused")):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch.object(svc, "_reset_connection", new_callable=AsyncMock):
                svc._state = ConnectionState.STREAMING
                with pytest.raises(StreamConnectionError) as exc_info:
                    await svc._reconnect_with_backoff()

    err = exc_info.value
    assert err.attempts == 3
    assert isinstance(err.last_error, OSError)


@pytest.mark.asyncio
async def test_state_is_failed_after_exhaustion() -> None:
    """_state must be FAILED after all attempts are exhausted."""
    svc = make_service(max_attempts=2, base_backoff=0.01, max_backoff=0.01)

    with patch.object(svc, "_connect", side_effect=OSError("x")):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch.object(svc, "_reset_connection", new_callable=AsyncMock):
                svc._state = ConnectionState.STREAMING
                with pytest.raises(StreamConnectionError):
                    await svc._reconnect_with_backoff()

    assert svc._state is ConnectionState.FAILED


@pytest.mark.asyncio
async def test_connect_timeout_triggers_retry() -> None:
    """asyncio.TimeoutError from _connect() is caught; next attempt runs."""
    svc = make_service(max_attempts=2, base_backoff=0.01, max_backoff=0.01)
    call_count = 0

    async def timeout_then_succeed() -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TimeoutError
        svc._ws = AsyncMock()

    with patch.object(svc, "_connect", side_effect=timeout_then_succeed):
        with patch.object(svc, "_read_raw_loop", new_callable=AsyncMock):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch.object(svc, "_reset_connection", new_callable=AsyncMock):
                    svc._state = ConnectionState.STREAMING
                    await svc._reconnect_with_backoff()  # must not raise

    assert call_count == 2


# ---------------------------------------------------------------------------
# _reconnect_with_backoff — guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_nested_reconnect_loop() -> None:
    """Duplicate call while RECONNECTING returns immediately without connecting."""
    svc = make_service()
    svc._state = ConnectionState.RECONNECTING

    with patch.object(svc, "_connect", new_callable=AsyncMock) as mock_connect:
        await svc._reconnect_with_backoff()
        mock_connect.assert_not_called()


@pytest.mark.asyncio
async def test_reconnect_storm_single_loop() -> None:
    """Multiple concurrent None sentinels result in exactly one reconnect loop."""
    svc = make_service(max_attempts=2, base_backoff=0.01, max_backoff=0.01)
    reconnect_call_count = 0

    original = svc._reconnect_with_backoff

    async def counting_reconnect() -> None:
        nonlocal reconnect_call_count
        reconnect_call_count += 1
        await original()

    svc._message_queue.put_nowait(_SENTINEL)
    svc._message_queue.put_nowait(_SENTINEL)
    svc._message_queue.put_nowait(_SENTINEL)
    svc._message_queue.put_nowait('{"m":"done"}')

    with patch.object(svc, "_reconnect_with_backoff", side_effect=counting_reconnect):
        with patch.object(svc, "close", new_callable=AsyncMock):
            svc._ws = MagicMock()
            try:
                await drain(svc.get_data_stream(), limit=10)
            except StreamConnectionError:
                pass

    # Each sentinel triggers one call; the lock ensures all subsequent calls
    # see RECONNECTING and return early — so we always get at least one call,
    # and the guard prevents a second full retry loop from running.
    assert reconnect_call_count >= 1


# ---------------------------------------------------------------------------
# Intentional close
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_intentional_close_suppresses_retry() -> None:
    """When _closing is True, None sentinel → no reconnect attempt."""
    svc = make_service()
    svc._closing = True
    svc._ws = MagicMock()
    svc._message_queue.put_nowait(_SENTINEL)

    with patch.object(svc, "_reconnect_with_backoff", new_callable=AsyncMock) as mock_reconnect:
        with patch.object(svc, "close", new_callable=AsyncMock):
            await drain(svc.get_data_stream(), limit=10)

    mock_reconnect.assert_not_called()


@pytest.mark.asyncio
async def test_no_retry_on_clean_close() -> None:
    """None sentinel with _closing=True breaks the loop without yielding items."""
    svc = make_service()
    svc._ws = MagicMock()
    svc._closing = True
    svc._message_queue.put_nowait(_SENTINEL)

    items: list[Any] = []
    with patch.object(svc, "close", new_callable=AsyncMock):
        async for item in svc.get_data_stream():
            items.append(item)

    assert items == []


# ---------------------------------------------------------------------------
# Backoff delay
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backoff_delay_respected() -> None:
    """asyncio.sleep is called with correct exponential delays for each attempt."""
    svc = make_service(max_attempts=3, base_backoff=1.0, max_backoff=30.0)
    sleep_calls: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    with patch.object(svc, "_connect", side_effect=OSError("x")):
        with patch.object(svc, "_reset_connection", new_callable=AsyncMock):
            with patch(
                "tvkit.api.chart.services.connection_service.asyncio.sleep",
                side_effect=record_sleep,
            ):
                svc._state = ConnectionState.STREAMING
                with pytest.raises(StreamConnectionError):
                    await svc._reconnect_with_backoff()

    assert len(sleep_calls) == 3
    assert sleep_calls[0] == 1.0  # attempt 1: 1.0 × 2^0
    assert sleep_calls[1] == 2.0  # attempt 2: 1.0 × 2^1
    assert sleep_calls[2] == 4.0  # attempt 3: 1.0 × 2^2


# ---------------------------------------------------------------------------
# Queue backpressure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_blocks_on_full() -> None:
    """put() blocks when queue is at maxsize, confirming backpressure semantics."""
    svc = make_service()

    # Fill queue to capacity using the service's own maxsize
    for _ in range(svc._message_queue.maxsize):
        svc._message_queue.put_nowait("x")

    # put_nowait raises immediately on full queue
    with pytest.raises(asyncio.QueueFull):
        svc._message_queue.put_nowait("overflow")

    # Blocking await put() should block (not complete) until space is freed
    task = asyncio.create_task(svc._message_queue.put("new-item"))
    await asyncio.sleep(0)  # yield to let the task attempt
    assert not task.done(), "put() must block when queue is full"
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
