# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
