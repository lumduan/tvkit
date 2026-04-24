# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.11.0] — 2026-04-24

### Added

- **`Adjustment` enum** (`tvkit.api.chart.Adjustment`) with two members:
  - `Adjustment.SPLITS` — split-adjusted prices only (default; identical to all pre-v0.11.0 behaviour)
  - `Adjustment.DIVIDENDS` — dividend-adjusted (total-return) prices; all prior bars are backward-adjusted for cash dividends, producing accurate total-return series for long-term backtesting of dividend-paying stocks
- **`adjustment` keyword parameter on `get_historical_ohlcv()`** — defaults to `Adjustment.SPLITS`; a raw string `"splits"` or `"dividends"` is coerced automatically; an unknown string raises `ValueError` before any network I/O
- **`backadjustment: "default"` added to the historical OHLCV `resolve_symbol` WebSocket payload** — matches TradingView browser behaviour confirmed by HAR capture; applies to `add_symbol_to_sessions()` (historical OHLCV path) only

### Notes

- Existing calls to `get_historical_ohlcv()` without `adjustment` produce the same data as v0.10.0 — fully backwards-compatible
- `Adjustment.NONE` (raw unadjusted prices) is not yet supported — protocol value not confirmed; tracked for a future release
- `add_multiple_symbols_to_sessions()` (quote-data path) and `get_ohlcv()` / `get_ohlcv_raw()` / `get_quote_data()` are unchanged in this release

---

## [0.10.0] — 2026-04-20

### Added

- **`tvkit.batch` module** — high-throughput async batch downloader for historical OHLCV data:
  - `batch_download(request)` — async function that fetches historical OHLCV bars for a list of
    symbols concurrently; returns `BatchDownloadSummary` with one `SymbolResult` per symbol
  - `BatchDownloadRequest` — Pydantic-validated input model; supports bar-count mode
    (`bars_count`) and date-range mode (`start`/`end`); `auth_token` stored as `SecretStr`
  - `BatchDownloadSummary` — aggregated result with `success_count`, `failure_count`,
    `elapsed_seconds`, `interval`, and `@computed_field` properties `failed_symbols` /
    `successful_symbols` (appear in `model_dump()`)
  - `SymbolResult` — per-symbol result with `bars`, `success`, `error`, `attempts`,
    `elapsed_seconds`; invariants enforced by `@model_validator`
  - `ErrorInfo` — structured error record with `message`, `exception_type`, `attempt`
    (`attempt=0` for pre-flight rejections, `1+` for fetch attempts)
  - `BatchDownloadError` — raised in `strict=True` mode or by `raise_if_failed()`; carries
    the full `BatchDownloadSummary` including partial successes on `.summary`
  - `BatchDownloadSummary.raise_if_failed()` — deferred strict-mode check callable after
    the fact; useful for pipelines that inspect before deciding whether failures are fatal
- **Bounded concurrency** — `asyncio.Semaphore` acquired **per network attempt**, not per retry
  loop; backoff sleep never occupies a concurrency slot
- **Per-symbol retry with exponential backoff** — `StreamConnectionError`,
  `websockets.WebSocketException`, `TimeoutError` are retried up to `max_attempts` times;
  `ValueError` and `NoHistoricalDataError` are not retried
- **Partial failure model** — failed symbols are collected in `BatchDownloadSummary` by default;
  no exception raised unless `strict=True`; `raise_if_failed()` provides deferred raise
- **Symbol normalization and deduplication** — all inputs normalized via `tvkit.symbols` and
  deduplicated (order-preserving) before dispatch; `total_count` reflects deduplicated count
- **Opt-in pre-flight symbol validation** — `validate_symbols_before_fetch=True` validates all
  symbols via TradingView HTTP API before any WebSocket fetch; confirmed-invalid symbols become
  `SymbolResult(success=False, attempts=0)` immediately; transport failures fail open
- **Progress callback** — `on_progress: Callable[[SymbolResult, int, int], None]` invoked once
  per symbol after its terminal result; async callables rejected at construction
- **`SymbolValidationOutcome` model** — added to `tvkit.api.utils.symbol_validator` to support
  pre-flight validation; exposes `is_valid`, `is_known_invalid`, and `message` fields
- **`validate_symbol_detailed()`** — new async function in `tvkit.api.utils.symbol_validator`
  returning `SymbolValidationOutcome`; exposed via `tvkit.api.utils`

### Notes

- `tvkit.batch` is a consumer of `tvkit.api.chart.OHLCV` — it instantiates one `OHLCV` client
  per in-flight attempt. WebSocket multiplexing (sharing one connection across subscriptions) is
  listed in `docs/roadmap.md` under **Under Consideration** and is out of scope for this release.
- No breaking changes to existing APIs — `tvkit.api.chart.OHLCV` is unchanged.
- `ErrorInfo.attempt` and `SymbolResult.attempts` minimum is `0` (pre-flight) rather than `1`;
  this is additive and does not affect existing code that only uses non-pre-flight paths.

## [0.9.0] — 2026-04-09

### Added

- **`tvkit.validation` module** — data integrity validation layer for OHLCV Polars DataFrames:
  - `validate_ohlcv(df, *, interval, checks)` — composite validator; runs all applicable checks
    in deterministic order and returns a structured `ValidationResult`
  - `ValidationResult` — Pydantic model with `is_valid`, `violations`, `bars_checked`,
    `checks_run` fields; `.errors` and `.warnings` convenience properties
  - `Violation` — typed Pydantic model per violation: `check`, `severity`, `message`,
    `affected_rows`, `context`
  - `ViolationType` — `StrEnum` for all check types: `DUPLICATE_TIMESTAMP`,
    `NON_MONOTONIC_TIMESTAMP`, `OHLC_INCONSISTENCY`, `NEGATIVE_VOLUME`, `GAP_DETECTED`
  - `DataIntegrityError` — public exception raised by `DataExporter` in strict mode;
    carries the full `ValidationResult` at `.result`
  - `ContextValue`, `ViolationContext` — type aliases for structured violation context dicts
- **Five built-in OHLCV checks** (all pure functions; `list[Violation]` return type):
  - `check_duplicate_timestamps(df)` — detects bars sharing a timestamp (ERROR)
  - `check_monotonic_timestamps(df)` — detects out-of-order timestamp pairs (ERROR)
  - `check_ohlc_consistency(df)` — detects `low > open/close`, `open/close > high`, and NaN in
    price columns (ERROR)
  - `check_volume_non_negative(df)` — detects `volume < 0` or NaN volume (ERROR)
  - `check_gaps(df, interval)` — detects timestamp gaps larger than the expected interval cadence
    (WARNING); raises `ValueError` when called without a valid `interval`
- **`DataExporter` validation integration** — `to_csv()` and `to_json()` now accept three
  keyword-only parameters:
  - `validate: bool = False` — when `True`, runs `validate_ohlcv()` before exporting and logs
    each violation at `WARNING` level; export always proceeds in this mode
  - `strict: bool = False` — when `True` alongside `validate=True`, raises `DataIntegrityError`
    on ERROR violations and does not write the output file; WARNING-only results never raise
  - `interval: str | None = None` — passed through to `validate_ohlcv()` for gap detection

### Notes

- Gap detection in Phase 1 is cadence-only (not calendar-aware). For daily equity bars (`"1D"`),
  weekends and public holidays are reported as `GAP_DETECTED` WARNING violations. This is
  intentional: WARNING violations do not affect `is_valid` and do not block exports. Calendar-aware
  gap detection is planned as a future enhancement.
- Validation is non-destructive — it never mutates the DataFrame. Check functions are pure with
  zero side effects.
- Scanner data passed to `DataExporter` silently skips validation (only `list[OHLCVBar]` input
  triggers the validation path).

## [0.8.0] — 2026-04-08

### Added

- **`tvkit.symbols` module** — synchronous, pure-string symbol normalization layer that
  converts any TradingView instrument reference to canonical `EXCHANGE:SYMBOL` form
  (uppercase, colon-separated) before any network call:
  - `normalize_symbol(symbol, *, config)` — normalize a single symbol; returns `str`
  - `normalize_symbols(symbols, *, config)` — batch normalization; returns `list[str]`,
    preserves input order, raises on first invalid element
  - `normalize_symbol_detailed(symbol, *, config)` — returns `NormalizedSymbol` with
    exchange, ticker, original input, and `NormalizationType` metadata
  - `NormalizedSymbol` — frozen Pydantic model for detailed normalization results
  - `NormalizationType` — enum recording the primary transformation applied
    (`ALREADY_CANONICAL`, `UPPERCASE_ONLY`, `DASH_TO_COLON`, `WHITESPACE_STRIP`,
    `DEFAULT_EXCHANGE`)
  - `NormalizationConfig` — Pydantic Settings model; reads `TVKIT_DEFAULT_EXCHANGE` and
    `TVKIT_STRIP_WHITESPACE` from environment variables
  - `SymbolNormalizationError` — subclass of `ValueError` with `original` and `reason`
    attributes; always raised before any I/O for malformed inputs
- **Bare-ticker resolution** — `normalize_symbol("AAPL", config=NormalizationConfig(default_exchange="NASDAQ"))` returns `"NASDAQ:AAPL"`; also readable via `TVKIT_DEFAULT_EXCHANGE` env var
- **`pydantic-settings>=2.0.0`** — new dependency added to support `NormalizationConfig`
  env var reading

### Changed

- `OHLCV` client methods (`get_historical_ohlcv`, `get_ohlcv`, `get_ohlcv_raw`,
  `get_quote_data`, `get_latest_trade_info`) now normalize symbols via
  `tvkit.symbols.normalize_symbol` before calling `validate_symbols`.
  The new call ordering is: `normalize_symbol(raw)` → `validate_symbols(canonical)`.
  Lowercased symbols (`nasdaq:aapl`), dash-format symbols (`NASDAQ-AAPL`), and
  whitespace-padded inputs are now accepted without errors by all `OHLCV` methods.

### Deprecated

- **`tvkit.api.utils.convert_symbol_format`** — use `tvkit.symbols.normalize_symbol` (single)
  or `tvkit.symbols.normalize_symbols` (batch) instead. A `DeprecationWarning` is emitted on
  every call. Will be removed in the next major version.
- **`tvkit.api.utils.SymbolConversionResult`** — use `tvkit.symbols.NormalizedSymbol` instead.
  Will be removed in the next major version.

See [Migration Guide: Symbol Normalization](docs/development/migration-symbol-normalization.md)
for before/after examples and field mapping.

---

## [0.7.0] — 2026-04-01

### Added

- **Authentication module** (`tvkit.auth`) — authenticate with a TradingView account using browser cookie extraction (Chrome/Firefox) or direct token injection
  - `OHLCV(browser="chrome")` / `OHLCV(browser="firefox")` — extracts session cookies from the user's already-logged-in browser
  - `OHLCV(browser="chrome", browser_profile="Profile 2")` — multi-profile support
  - `OHLCV(cookies={...})` — manual cookie dict injection for headless/CI environments
  - `OHLCV(auth_token=...)` — direct token injection; bypasses all cookie steps
  - `TVKIT_BROWSER` / `TVKIT_AUTH_TOKEN` environment variables as credential source
  - 2FA transparent — browser session is already authenticated; tvkit inherits it
- **Capability detection** — automatic account plan detection and background WebSocket probe
  - Plan-based `max_bars` estimate available immediately after `__aenter__` (~200–500ms)
  - Background probe on a dedicated short-lived connection confirms the actual server limit
  - Adaptive probe: tries `bars_count` 50k → 40k → 20k; symbol fallback chain AAPL → BTCUSDT → SPX
  - `account.max_bars` updated atomically under `asyncio.Lock`
  - `account.probe_status`: `pending` → `success` / `throttled` / `failed`
  - Optional probe result disk cache (`~/.cache/tvkit/capabilities.json`; 24h TTL)
- **Premium WebSocket endpoint** — paid accounts (`tier != "free"`) automatically connect to `prodata.tradingview.com`, which delivers the full account `max_bars` (up to 40,000) in a single large message batch without requiring pagination. Authentication is identical: `set_auth_token` WebSocket message with the JWT.
- **`request_more_data` pagination** — `get_historical_ohlcv()` now correctly fetches all requested bars across multiple server pages. TradingView serves bars in chunks; tvkit sends `request_more_data` after each `series_completed` until the requested count is satisfied or the server is exhausted.
- **`OHLCV.wait_until_ready()`** — blocks until the background capability probe completes; never raises
- **`OHLCV.account`** property — exposes `TradingViewAccount | None` with plan and capability data; `None` for anonymous and direct-token sessions
- **`SegmentedFetchService`** now snapshots `auth_manager.account.max_bars` at each fetch start — stable segment boundaries even if the background probe updates `max_bars` mid-flight; `_needs_segmentation` threshold is also account-aware
- **Typed exceptions**: `BrowserCookieError`, `ProfileFetchError`, `CapabilityProbeError` (all extend `AuthError`)

### Changed

- `ConnectionService.__init__` — new optional `auth_token` parameter (default: `"unauthorized_user_token"` — backward compatible); WebSocket auth errors now raise `AuthError` instead of triggering transparent re-extraction
- `OHLCV.__init__` — new optional credential parameters: `browser`, `browser_profile`, `cookies`, `auth_token` (all default to `None` — backward compatible)
- `WebSocketConnection.max_size` — set to `None` (unlimited) to handle large `prodata.tradingview.com` message batches (~1.9 MB for 20,000 bars)

### Dependencies

- `browser-cookie3>=0.20.1` — added for browser cookie extraction (Chrome/Firefox)

---

## [0.6.0] - 2026-03-12

### Added

- **`tvkit.time` module** — UTC timezone utilities for TradingView OHLCV data:
  - `to_utc(dt)` — normalise any `datetime` to UTC; emits a one-time `UserWarning` for naive inputs
  - `ensure_utc(dt)` — semantic alias for `to_utc`; preferred in validation contexts
  - `convert_timestamp(ts, tz)` — convert a single UTC epoch float to a tz-aware `datetime`
  - `convert_to_timezone(df, tz, column, unit)` — convert a Polars DataFrame epoch column to a tz-aware datetime column
  - `convert_to_exchange_timezone(df, exchange, column, unit)` — exchange-code-aware wrapper for `convert_to_timezone`; resolves exchange codes to IANA timezones automatically
  - `exchange_timezone(exchange)` — look up the IANA timezone for any TradingView exchange code; falls back to `"UTC"` with a WARNING for unknown codes
  - `exchange_timezone_map` — full built-in exchange → IANA timezone dict (all 69 tvkit markets)
  - `supported_exchanges()` — list all exchange codes in the registry
  - `register_exchange(exchange, tz)` — add or override a mapping at runtime
  - `load_exchange_overrides(path)` — load overrides from a YAML file or `TVKIT_EXCHANGE_OVERRIDES` env var
  - `validate_exchange_registry()` — validate all registry entries are valid IANA timezone strings
  - `TimestampUnit` type alias — `Literal["s", "ms"]` for epoch column unit selection
- **`OHLCVBar` UTC invariant** — Pydantic `field_validator` on `OHLCVBar.timestamp` rejects values outside `[0, 7_258_118_400]` (1970-01-01 to 2200-01-01). Catches milliseconds-passed-as-seconds and negative timestamps at model construction time.

### Changed

- `OHLCVBar.timestamp` now has a documented UTC contract. The field type is unchanged (`float`) — no breaking change.
- `ohlcv.py` now calls `ensure_utc()` on `start`/`end` parameters before range computation, ensuring consistent UTC handling for timezone-aware and naive datetime inputs.
- `examples/ohlcv_historical.py` — added `timezone_conversion()` demonstration function showing exchange-aware timestamp conversion for both traditional (NASDAQ) and crypto (BINANCE) exchanges.

---

## [0.5.0] - 2026-03-11

### Added

- **Automatic segmented fetching for large historical OHLCV date ranges** in `get_historical_ohlcv()` range mode. When the requested range exceeds `MAX_BARS_REQUEST` bars, the client automatically splits the range into segments, fetches each sequentially, then merges, deduplicates, and sorts the results. The public API is unchanged — callers receive the same `list[OHLCVBar]` return type.
- **`SegmentedFetchService`** internal orchestrator (`tvkit.api.chart.services.segmented_fetch_service`). Not part of the public API.
- **`segment_time_range(start, end, interval_seconds, max_bars)`** — splits a UTC date range into non-overlapping `TimeSegment` objects sized for at most `max_bars` bars each. Raises `RangeTooLargeError` if segment count exceeds `MAX_SEGMENTS`.
- **`interval_to_seconds(interval)`** — converts a TradingView interval string to seconds. Raises `ValueError` for monthly/weekly intervals (not supported by the segmentation engine).
- **`TimeSegment`** — frozen dataclass (`start: datetime`, `end: datetime`). Hashable and equality-comparable.
- **`MAX_SEGMENTS`** constant (`2000`) — safety guard for `segment_time_range()`.
- **`RangeTooLargeError`** exception (subclass of `ValueError`) — raised when segment count exceeds `MAX_SEGMENTS`.
- **`NoHistoricalDataError`** exception (subclass of `RuntimeError`) — raised by `_fetch_single_range()` for empty segments (weekends, holidays, illiquid periods, or dates outside the accessible history window). Treated as `[]` by `SegmentedFetchService`; never propagated to callers.
- **`SegmentedFetchError`** exception — wraps unexpected segment failures. Carries `segment_index`, `segment_start`, `segment_end`, `total_segments`, `cause`.
- **`_needs_segmentation(start, end, interval)`** private helper on `OHLCV` — returns `True` when the estimated bar count exceeds `MAX_BARS_REQUEST`. Always returns `False` for monthly/weekly intervals.
- **`docs/internals/segmented-fetch.md`** — algorithm, recursion guard rationale, merge/dedup semantics, sequence diagram.

### Changed

- `get_historical_ohlcv()` in range mode now transparently segments large requests. Monthly and weekly intervals continue to use a single request (unchanged behaviour).
- `docs/guides/historical-data.md` — replaced manual segmentation example with automatic segmentation. Added "TradingView Historical Depth Limitation" section with account-tier table and "Why did my request return fewer bars than expected?" troubleshooting section.
- `docs/limitations.md` — added "TradingView Historical Depth Limitation" section with interval × tier depth table.
- `docs/architecture/system-overview.md` — added `SegmentedFetchService` to chart component diagram.

---

## [0.4.0] - 2026-03-10

### Added

- **Automatic WebSocket reconnection** for OHLCV streaming with exponential backoff ([#14](https://github.com/lumduan/tvkit/issues/14)). Transient disconnects are recovered automatically with no changes required to existing call sites.
- **`max_attempts`, `base_backoff`, `max_backoff`** optional constructor parameters on `OHLCV` for tuning retry behaviour. Defaults: `max_attempts=5`, `base_backoff=1.0s`, `max_backoff=30.0s`.
- **`StreamConnectionError`** exception raised when all reconnect attempts are exhausted. Importable from `tvkit.api.chart`. Carries `attempts` (int) and `last_error` (Exception | None) attributes.
- **`ConnectionState` enum** (`IDLE`, `CONNECTING`, `STREAMING`, `RECONNECTING`, `FAILED`) in `tvkit.api.chart.services.connection_service`. Useful for asserting connection state in tests.
- **`calculate_backoff_delay`** pure utility function in `tvkit.api.utils.retry`. Supports base delay, max cap, and optional additive jitter (clamped to `max_backoff`).
- **Structured logging** for every reconnect attempt, outcome, and session restore event.

### Changed

- `ConnectionService` now manages transport reconnect internally via a configurable retry loop and explicit state machine. The public `connect()` / `close()` interface is unchanged.
- `OHLCV._setup_services()` forwards retry config and `on_reconnect=self._restore_session` to `ConnectionService`.

## [0.3.0] - 2026-03-06

### Breaking Changes

- **`get_historical_ohlcv()`**: `bars_count` default changed from `10` to `None`.
  Callers that relied on the implicit default now receive `ValueError` and must pass
  `bars_count` explicitly or switch to the new `start`/`end` range mode.

  **Migration:**

  ```python
  # Before (v0.2.x):
  bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D")  # fetched 10 bars implicitly

  # After (v0.3.0):
  bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=10)
  ```

### Added

- **Date-range mode for `get_historical_ohlcv()`**: New `start` and `end` keyword-only
  parameters (`datetime | str`) for fetching historical bars by explicit date range.
  Both ISO 8601 strings and timezone-aware/naive `datetime` objects are accepted.
  Naive datetimes are treated as UTC.

  ```python
  # Full-year daily bars
  bars = await client.get_historical_ohlcv(
      "NASDAQ:AAPL", "1D", start="2024-01-01", end="2024-12-31"
  )

  # Single-day intraday bars (start == end is valid)
  bars = await client.get_historical_ohlcv(
      "NASDAQ:AAPL", "5", start="2024-06-15", end="2024-06-15"
  )
  ```

- **`tvkit.api.chart.utils.to_unix_timestamp(ts)`** — convert a `datetime` or ISO 8601
  string to a UTC Unix timestamp (integer seconds).
- **`tvkit.api.chart.utils.build_range_param(start, end)`** — build a TradingView
  `r,<from>:<to>` range string from start and end timestamps.
- **`tvkit.api.chart.utils.MAX_BARS_REQUEST`** — sentinel constant (`5000`) passed to
  `create_series` in range mode (TradingView ignores it when `modify_series` is active).

### Changed

- Historical fetch timeout extended from 30s to **180s** in range mode. Count mode
  remains 30s. Range queries may span years of intraday data and require more time.
- **`ConnectionService.add_symbol_to_sessions()`** now accepts an optional `range_param`
  keyword argument (`str = ""`). When non-empty, a `modify_series` message is sent
  immediately after `create_series` to apply the date range constraint.
- **`ConnectionService._create_series_args()`** extracted as a private testable helper
  that returns the strict 7-element `create_series` parameter list (trailing `""` always
  present in count mode).
- **`ConnectionService._modify_series_args()`** extracted as a private testable helper
  that returns the 6-element `modify_series` parameter list with `range_param` last.

---

## [0.2.1] - 2026-03-05

### 🐛 Bug Fixes

#### `get_historical_ohlcv` Early Termination (Issue #7)

- **Fixed freeze on data exhaustion**: `get_historical_ohlcv` now returns immediately when the
  TradingView server signals all available data has been sent (`series_completed`), instead of
  waiting for the full 30-second timeout. Symbols with fewer bars than `bars_count` requested
  now return in ~1–2 seconds.
- **Fixed `series_error` propagation**: `ValueError` raised by the `series_error` handler was
  being swallowed by the outer `except Exception` guard (because `pydantic.ValidationError`
  is a `ValueError` subclass in Pydantic v2). The outer guard now correctly distinguishes
  intentional `ValueError` from parsing-level `ValidationError` and re-raises appropriately.
- **Fixed connection leak in `_setup_services()`**: Opening a new `ConnectionService` now
  closes any existing connection first, preventing WebSocket handle leaks in multi-call scenarios.
- **Fixed `study_completed` handling**: Added unconditional `break` on `study_completed` as a
  protocol-ordering safety net for atypical TradingView message sequences.

### 🔧 Library Hygiene

- **Removed `logging.basicConfig()`**: Replaced with `logger = logging.getLogger(__name__)` —
  library code must not configure root logging (overrides application-level settings).
- **Removed `signal.signal(SIGINT, ...)`**: Library code must not register global signal
  handlers; this is the host application's responsibility.
- **Replaced `asyncio.get_event_loop()`** with `asyncio.get_running_loop()` (Python 3.10+
  preferred API, avoids DeprecationWarning in Python 3.12+).

### ♻️ Refactoring

- **Extracted `_prepare_chart_session()` helper**: Eliminated 4× duplicated session-setup
  boilerplate across `get_ohlcv`, `get_historical_ohlcv`, `get_quote_data`, `get_ohlcv_raw`.
- **Narrowed exception handling**: Inner parsing blocks now catch `ValidationError` instead
  of bare `Exception`, making unintended swallowing of control-flow exceptions impossible.
- **Downgraded session ID logs** from `info` to `debug` to reduce log noise in production.

### 🧪 Testing

- **New `tests/test_historical_ohlcv.py`**: 32 unit tests across 6 classes providing full
  behavioral coverage of `get_historical_ohlcv` with zero real network calls:
  - `TestSeriesCompletedSignal` (6) — Phase 1 regression + `bars_count` threshold tests
  - `TestStudyCompletedSignal` (3) — fallback signal and protocol ordering tests
  - `TestPartialDataScenarios` (6) — partial data, sort order, `du` messages, duplicates
  - `TestErrorHandling` (9) — `series_error`, input validation, malformed frames, edge cases
  - `TestTimeoutBehavior` (4) — timeout safety net with deterministic time mocking
  - `TestSessionLifecycle` (4) — session setup, argument passing, close-on-error contract

---

## [0.2.0] - 2025-09-27

### 🎯 Major Feature: Universal TradingView Indicators Access

#### 📊 Comprehensive Indicator Support

- **Universal Indicator Access**: TVKit now supports fetching any indicators available on TradingView
  - Access to thousands of financial indicators including macro, technical, and custom indicators
  - Seamless integration with TradingView's complete indicator ecosystem
  - Professional-grade data access for institutional and retail analysis

- **Macro and Market Indicators**: Enhanced support for professional analysis including:
  - Market breadth indicators (e.g., INDEX:NDFI for Net Demand For Income analysis)
  - Sentiment indicators (e.g., USI:PCC for Put/Call Ratio analysis)
  - Custom indicators and proprietary TradingView metrics
  - Economic indicators and macro data points

#### 🚀 Enhanced Examples and Documentation

- **Comprehensive Tutorial Integration**: Added Tutorial 5 to `quick_tutorial.py` demonstrating:
  - Universal indicator access patterns and data interpretation
  - Example implementations using popular indicators like NDFI and PCC
  - Integration patterns for quantitative models and analysis frameworks
  - Professional use case scenarios across different indicator types

- **Advanced Quantitative Examples**: Enhanced `historical_and_realtime_data.py` with:
  - `fetch_macro_liquidity_indicators()` - Universal indicator data acquisition function
  - `analyze_macro_indicators_for_quantitative_models()` - Advanced analysis algorithms
  - Risk assessment frameworks supporting any TradingView indicators
  - Signal generation patterns adaptable to various indicator types

- **Interactive Jupyter Integration**: Updated `historical_and_realtime_data.ipynb` with:
  - Interactive cells for real-time indicator analysis across all TradingView metrics
  - Quantitative model integration examples using sample indicators
  - Regime detection and classification algorithms adaptable to any indicators
  - Export capabilities for external analysis tools and indicator data

#### 🔬 Universal Quantitative Analysis Framework

- **Flexible Indicator Analysis**: Professional algorithms adaptable to any TradingView indicators
  - Percentile-based analysis for any indicator type
  - Combined indicator scoring supporting multiple data sources
  - Risk assessment frameworks compatible with diverse indicator sets

- **Systematic Trading Integration**: Code templates and examples for:
  - Algorithmic trading strategy development using any available indicators
  - Portfolio optimization based on custom indicator combinations
  - Risk management parameter adjustment across indicator types
  - Market timing signal generation from various TradingView metrics

#### 📈 Professional Applications

This universal indicator access enables professional research applications critical for:

- **Quantitative Models**: Advanced modeling using any TradingView indicators for market analysis
- **Regime Detection**: Systematic identification of market changes using diverse indicator sets
- **Systematic Trading Strategies**: Integration with algorithmic systems using custom indicator combinations
- **Portfolio Optimization**: Dynamic allocation based on comprehensive indicator analysis
- **Risk Management**: Professional-grade assessment using multiple indicator sources
- **Market Analysis**: Comprehensive analysis using the full TradingView indicator ecosystem

#### 🛠️ Technical Implementation

- **Async-First Architecture**: All indicator functions use modern async/await patterns
- **Type Safety**: Complete Pydantic validation for universal indicator data models
- **Export Integration**: Seamless CSV/JSON export for any indicator data and analysis
- **Error Handling**: Robust error management for production environments across all indicators
- **Documentation**: Comprehensive inline documentation and usage examples for indicator access

#### 📚 Updated Documentation

- **README.md**: Enhanced with universal indicator examples and professional use cases
- **CLAUDE.md**: Comprehensive documentation of indicator access capabilities and integration patterns
- **Code Examples**: Real-world examples demonstrating applications across various indicator types
- **Integration Guides**: Step-by-step guidance for quantitative model integration with any indicators

### 🔧 Quality Assurance

- **Code Quality**: All new code passes ruff linting and mypy type checking
- **Testing**: Comprehensive testing ensuring reliability across all indicator types
- **Performance**: Optimized for high-frequency analysis workflows with any TradingView indicators
- **Compatibility**: Maintains full backward compatibility with existing tvkit functionality

## [0.1.4] - 2025-09-16

- Changed installation method in README from requirements.txt to direct pip install.
- Updated development dependencies in pyproject.toml to newer versions.
- Removed requirements.txt file as it is no longer needed.

## [0.1.3] - 2025-09-08

### 🔧 Compatibility

#### 🐍 Extended Python Version Support

- **Python 3.11+ Support**: Extended compatibility from Python 3.13+ to Python 3.11+
  - Now supports Python 3.11, 3.12, and 3.13 (last 3 stable versions)
  - Maintains full feature compatibility across all supported versions
  - Updated documentation and examples to reflect broader compatibility
  - Reduced deployment barriers for users on slightly older Python versions

## [0.1.2] - 2025-07-31

### 🌍 Enhanced Multi-Market Scanner

#### 🔍 Comprehensive Global Market Coverage

- **69 Global Markets**: Complete coverage across 6 regions with unified API access
  - **North America**: USA (NASDAQ, NYSE, NYSE ARCA, OTC), Canada (TSX, TSXV, CSE, NEO)
  - **Europe**: 30 markets including Germany, France, UK, Netherlands, Switzerland, Italy
  - **Asia Pacific**: 17 markets including Japan, Thailand, Singapore, Korea, Australia, India, China
  - **Middle East & Africa**: 12 markets including UAE, Saudi Arabia, Israel, South Africa
  - **Latin America**: 7 markets including Brazil, Mexico, Argentina, Chile, Colombia

#### 📊 Advanced Financial Data Analysis

- **101+ Financial Columns**: Comprehensive data retrieval with complete TradingView scanner API coverage
- **Predefined Column Sets**: `BASIC`, `FUNDAMENTALS`, `TECHNICAL_INDICATORS`, `PERFORMANCE`, `VALUATION`, `PROFITABILITY`, `FINANCIAL_STRENGTH`, `CASH_FLOW`, `DIVIDENDS`, `COMPREHENSIVE_FULL`
- **Enhanced Data Models**: Complete `StockData` model with all financial metrics including:
  - **Valuation**: P/E ratios, P/B ratios, EV/Revenue, PEG ratios, enterprise value metrics
  - **Profitability**: ROE, ROA, gross/operating/net margins, EBITDA, return on invested capital
  - **Financial Health**: Current/quick ratios, debt-to-equity, total assets/liabilities, cash positions
  - **Dividends**: Current yield, payout ratios, growth rates, continuous dividend tracking
  - **Technical Indicators**: RSI, MACD, Stochastic, CCI, momentum indicators, analyst recommendations

#### 🚀 Regional Market Analysis

- **Market Grouping**: `MarketRegion` enum for regional market analysis and filtering
- **Flexible Market Access**: Support for both `Market` enum and string-based market IDs for dynamic selection
- **Comprehensive Market Information**: Detailed exchange information and market metadata for all supported markets
- **Regional Scanning**: Built-in functions for scanning markets by geographic region

#### 🔧 Enhanced Scanner Service

- **`create_comprehensive_request()`**: New function for accessing all 101+ available columns
- **Error Handling**: Robust error handling with specific exception types and retry mechanisms
- **Async-First Architecture**: Complete async/await pattern implementation with proper resource management
- **Type Safety**: Full Pydantic validation for all scanner requests and responses

#### 📚 Comprehensive Examples

- **Multi-Market Scanner Notebook**: Complete example notebook demonstrating:
  - Basic multi-market scanning (Thailand vs USA comparison)
  - Comprehensive data retrieval with all financial metrics
  - Regional market analysis (Asia Pacific focus)
  - Market scanning by ID strings for dynamic selection
  - Available markets and regional information display
  - Data visualization and pandas integration

#### 🛠️ Technical Enhancements

- **Market Validation**: Built-in market ID validation with helpful error messages
- **Dynamic Column Validation**: Comprehensive column name validation with support for all TradingView fields
- **Response Parsing**: Enhanced API response parsing handling both legacy and new TradingView formats
- **Symbol Extraction**: Improved symbol extraction from TradingView API responses
- **Retry Logic**: Exponential backoff retry mechanism for API reliability

#### 📈 Performance Improvements

- **Efficient Market Scanning**: Optimized scanning performance for multi-market analysis
- **Memory Management**: Efficient data structures for handling large-scale market data
- **Concurrent Scanning**: Support for concurrent market scanning operations
- **Data Processing**: Enhanced data processing with proper null value handling

### 📖 Documentation Updates

- **Enhanced README**: Updated scanner section with multi-market capabilities and comprehensive examples
- **API Documentation**: Complete documentation for all new scanner features and market coverage
- **Usage Examples**: Real-world examples for multi-market analysis and regional scanning
- **Market Coverage Tables**: Detailed tables showing all supported markets and exchanges

### 🔧 Developer Experience

- **Complete Type Hints**: All scanner functions include comprehensive type annotations
- **IDE Support**: Enhanced IntelliSense support with proper type information
- **Error Messages**: Improved error messages with helpful suggestions for market validation
- **Code Organization**: Well-organized module structure with clear separation of concerns

## [0.1.1] - 2025-07-30

### 🔧 Bug Fixes & Improvements

- **Package Publishing**: Improved publishing workflow and version management
- **Documentation**: Enhanced package metadata and publishing process
- **Build System**: Optimized build configuration for better PyPI compatibility

## [0.1.0] - 2025-07-30

### 🎯 First Public Release

#### 📊 Real-Time Chart API (`tvkit.api.chart`)

- **WebSocket streaming** for real-time OHLCV data with async generators
- **Historical data fetching** with configurable intervals and bar counts
- **Multi-symbol support** for stocks, cryptocurrencies, and forex pairs
- **Symbol validation** with automatic retry mechanisms
- **Connection management** with proper cleanup and error handling

#### 🔍 Scanner API (`tvkit.api.scanner`)

- **Typed models** for TradingView's scanner API endpoints
- **Stock screening** and filtering capabilities
- **Fundamental analysis** data structures

#### 💾 Data Export System (`tvkit.export`)

- **Multi-format export** to Polars DataFrames, JSON, CSV, and Parquet
- **Unified DataExporter interface** with comprehensive configuration options
- **Financial analysis integration** with SMA, VWAP, and technical indicators
- **Metadata inclusion** with export timestamps and symbol information
- **Flexible formatting** with customizable timestamp formats and precision

#### 🛠️ Technical Implementation

- **Async-first architecture** using `websockets` and `httpx`
- **Type safety** with comprehensive Pydantic models and validation
- **Error handling** with specific exception types and retry mechanisms
- **Context managers** for proper resource management
- **90%+ test coverage** with pytest and pytest-asyncio

#### 📚 Documentation & Examples

- **Comprehensive sample notebook** demonstrating all major features
- **Real-world usage examples** for stocks, crypto, and forex data
- **Error handling demonstrations** and best practices
- **Multi-asset class examples** with performance comparisons
- **Export format examples** with analysis workflows

#### 🎁 Key Features

- Support for **20+ exchanges** including NASDAQ, NYSE, BINANCE, and forex markets
- **Real-time streaming** with automatic reconnection and error recovery
- **Historical data** with flexible intervals (1m, 5m, 1h, 1D, etc.)
- **Data validation** ensuring data integrity and type safety
- **Export flexibility** supporting multiple output formats and analysis workflows
- **Modern Python** using async/await patterns and type hints

#### 📦 Dependencies

- `pydantic>=2.11.7` - Data validation and settings management
- `websockets>=13.0` - Async WebSocket client for real-time streaming
- `httpx>=0.28.0` - Async HTTP client for API validation
- `polars>=1.0.0` - High-performance data processing and analysis

### 🔧 Development Environment

- **Python 3.11+** support with modern language features
- **UV package manager** for fast dependency resolution
- **Comprehensive tooling** with ruff, mypy, and pytest
- **Quality gates** ensuring code quality and reliability

### 📈 Supported Markets

- **Stocks**: NASDAQ, NYSE, and international exchanges
- **Cryptocurrencies**: Binance, Coinbase, and major crypto exchanges
- **Forex**: Major currency pairs and cross rates
- **Commodities**: Gold, oil, and other tradeable assets
