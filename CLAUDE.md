# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing
- Run all tests: `uv run python -m pytest tests/ -v`
- Run specific test file: `uv run python -m pytest tests/test_ohlcv_models.py -v`
- Run with coverage: `uv run python -m pytest tests/ --cov=tvkit`

### Code Quality
- Type checking: `uv run mypy tvkit/`
- Linting: `uv run ruff check .`
- Formatting: `uv run ruff format .`
- All quality checks: `uv run ruff check . && uv run ruff format . && uv run mypy tvkit/`

### Development
- Install dependencies: `uv sync`
- Run example scripts: `uv run python examples/realtime_streaming_example.py`
- Publish: `./scripts/publish.sh`

## Architecture Overview

**tvkit** is a Python library for TradingView's financial data APIs with two main components:

### 1. Scanner API (`tvkit.api.scanner`)
- Provides typed models for TradingView's scanner API
- Key classes: `ScannerRequest`, `ScannerResponse`, `StockData`
- Factory functions: `create_scanner_request()` with presets and column sets
- Used for stock screening, filtering, and fundamental analysis

### 2. Real-Time Chart API (`tvkit.api.chart`)
- Async WebSocket streaming for real-time market data
- Key classes: `OHLCV`, `RealtimeStreamer`
- Supports OHLCV data streaming and quote data
- Built with modern async patterns using `websockets` and `httpx`

## Key Patterns

### Async-First Architecture
- All I/O operations use async/await
- WebSocket streaming with async generators
- HTTP validation with async clients (`httpx`, not `requests`)
- Context managers for resource management

### Type Safety with Pydantic
- All data models inherit from Pydantic BaseModel
- Comprehensive validation and type hints
- Field descriptions and constraints required
- No `Any` types without justification

### Error Handling
- Specific exception types for different error conditions
- Retry mechanisms with exponential backoff
- Graceful degradation for parsing errors
- Structured logging for debugging

## Project Structure
```
tvkit/
├── tvkit/
│   ├── api/
│   │   ├── chart/          # Real-time WebSocket streaming
│   │   │   ├── models/     # Pydantic data models
│   │   │   ├── services/   # WebSocket services
│   │   │   └── ohlcv.py  # Main client
│   │   └── scanner/        # Scanner API models
│   └── core.py
├── tests/                  # Pytest test suite
├── examples/               # Working usage examples
├── docs/                   # Documentation
└── debug/                  # Debug scripts (gitignored)
```

## Development Guidelines

### Mandatory Requirements
1. **Type Safety**: All functions must have complete type annotations
2. **Async Patterns**: Use async/await for all I/O operations  
3. **Pydantic Models**: All data structures must use Pydantic validation
4. **Testing**: All new features must have comprehensive tests
5. **Code Quality**: Must pass `ruff`, `mypy`, and all tests before committing

### Prohibited Actions
- Never use `requests` (use `httpx` for async HTTP)
- Never use `websocket-client` (use `websockets` for async WebSocket)
- Never hardcode credentials or API keys
- Never commit code that doesn't pass all quality checks
- Never use bare `except:` clauses

### Testing Strategy
- Run tests before making changes: `uv run python -m pytest tests/ -v`
- Write tests first (TDD approach preferred)
- Mock external dependencies appropriately
- Maintain 90%+ code coverage

## Key Dependencies
- `pydantic>=2.11.7` - Data validation and settings
- `websockets>=13.0` - Async WebSocket client
- `httpx>=0.28.0` - Async HTTP client
- `polars>=1.0.0` - Data processing and analysis
- `pytest>=8.0.0` + `pytest-asyncio>=0.23.0` - Testing framework

## Important Notes
- Uses `uv` for dependency management (not pip/poetry)
- Python 3.13+ required
- All WebSocket operations are async with proper connection management
- Symbol validation done via async HTTP requests
- Export functionality supports CSV, JSON, and Parquet formats