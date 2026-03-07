# Testing Strategy

tvkit's test suite covers model validation, protocol correctness, and service behavior. All tests run without a live TradingView connection — network calls are always mocked.

## Running Tests

```bash
# Full suite
uv run python -m pytest tests/ -v

# Single file
uv run python -m pytest tests/test_ohlcv_models.py -v

# With coverage
uv run python -m pytest tests/ --cov=tvkit

# With coverage enforcement
uv run python -m pytest tests/ --cov=tvkit --cov-fail-under=90
```

Minimum required coverage: **90%**. Coverage is measured across `tvkit/` only — test files and examples are excluded. The `--cov-fail-under=90` flag causes the test run to fail if coverage drops below this threshold, which is the same check used in CI.

## Test Files

| File | What it covers |
|------|---------------|
| `test_ohlcv_models.py` | `OHLCVBar`, `OHLCVResponse`, `SeriesData`, `NamespaceData` — Pydantic validation |
| `test_realtime_models.py` | Real-time streaming models — `QuoteData`, `TradeInfo` |
| `test_interval_validation.py` | `validate_interval()` — all valid and invalid interval strings |
| `test_connection_service.py` | `ConnectionService` protocol message builders — no socket required |
| `test_historical_ohlcv.py` | `get_historical_ohlcv()` — date-range and count-mode behavior |
| `test_ohlcv_range_filter.py` | Client-side post-filter logic for date-range responses |
| `test_export_module.py` | `DataExporter`, `PolarsFormatter`, `JSONFormatter`, `CSVFormatter` |
| `test_utils.py` | `convert_timestamp_to_iso()`, `validate_symbols()`, `convert_symbol_format()` |

## What Gets Mocked

All external I/O is mocked. Tests never open a real WebSocket or make HTTP requests:

- **WebSocket connections**: replaced with `AsyncMock` capturing outgoing messages
- **HTTP requests** (`httpx`): patched at the `httpx.AsyncClient` level
- **`send_message_func`**: replaced with a recording callable that captures `(method, args)` tuples

Example pattern from `test_connection_service.py`:

```python
sent_messages: list[tuple[str, list[Any]]] = []

async def mock_send(method: str, args: list[Any]) -> None:
    sent_messages.append((method, args))

await service.add_symbol_to_sessions(
    "qs_abc", "cs_abc", "NASDAQ:AAPL", "1D", 100, mock_send
)

methods = [m for m, _ in sent_messages]
assert "create_series" in methods
assert "modify_series" not in methods  # count mode — no range
```

## Async Tests

tvkit is async-first. Tests for async code use `pytest-asyncio` (included in dev dependencies) in strict mode:

```toml
[tool.pytest.ini_options]
asyncio_mode = "strict"
```

Decorate async test methods with `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_something_async() -> None:
    result = await some_async_function()
    assert result is not None
```

## Protocol Correctness Tests

The most important tests verify that outgoing protocol messages have the correct structure. The TradingView WebSocket protocol is position-sensitive — a wrong argument at position 4 fails silently. These assertions prevent subtle protocol regressions.

Key assertions to include when testing message builders:

- Exact element count (`len(args) == 7` for `create_series`, `6` for `modify_series`)
- Trailing empty string present in `create_series` (`args[-1] == ""`)
- Range string format (`args[-1].startswith("r,")`) in `modify_series`
- `modify_series` absent in count mode, present in range mode

## Pydantic Model Tests

Model tests validate both happy-path construction and rejection of invalid data:

```python
def test_ohlcv_bar_rejects_missing_field() -> None:
    with pytest.raises(ValidationError):
        OHLCVBar(timestamp=1720000000.0, open=100.0)  # missing high/low/close/volume
```

Use `pytest.raises(ValidationError)` for all expected Pydantic failures.

## Adding Tests for New Features

When adding a new public method or model:

1. Create a test class in the appropriate `test_*.py` file
2. Cover the happy path, at least one edge case, and invalid input rejection
3. Mock all I/O — no live network calls in tests
4. Run `uv run python -m pytest tests/ --cov=tvkit --cov-fail-under=90` and confirm coverage stays above 90%

## See Also

- [Release Process](release-process.md) — quality gates required before publishing
- [Architecture Decisions](architecture-decisions.md) — why the async-first design affects test structure
