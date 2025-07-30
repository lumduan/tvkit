# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Python 3.13+** support with modern language features
- **UV package manager** for fast dependency resolution
- **Comprehensive tooling** with ruff, mypy, and pytest
- **Quality gates** ensuring code quality and reliability

### 📈 Supported Markets
- **Stocks**: NASDAQ, NYSE, and international exchanges
- **Cryptocurrencies**: Binance, Coinbase, and major crypto exchanges  
- **Forex**: Major currency pairs and cross rates
- **Commodities**: Gold, oil, and other tradeable assets
