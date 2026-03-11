# tvkit

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Async/Await](https://img.shields.io/badge/async-await-green.svg)](https://docs.python.org/3/library/asyncio.html)
[![Type Safety](https://img.shields.io/badge/typed-pydantic-red.svg)](https://pydantic.dev/)
[![PyPI](https://img.shields.io/pypi/v/tvkit.svg)](https://pypi.org/project/tvkit/)

tvkit — Async Python client for TradingView market data.

Access real-time and historical TradingView data with a modern async Python API.
Designed for quantitative research, trading tools, and data pipelines.

## Features

- Real-time OHLCV streaming via WebSocket with async generators
- **Automatic reconnection** with exponential backoff — transient disconnects recovered transparently
- Historical data retrieval by bar count or explicit date range
- **Automatic segmented fetching** for large historical OHLCV date ranges (TradingView historical depth limits still apply)
- Multi-market scanner: 69 global markets, 101+ financial metrics
- Multi-format data export: Polars DataFrames, JSON, CSV
- Symbol format auto-conversion: `EXCHANGE-SYMBOL` and `EXCHANGE:SYMBOL` both accepted
- Async symbol validation with retry and flexible format support
- Full type safety with Pydantic models throughout
- Python 3.11+ with async/await and context manager patterns

## Installation

Available on PyPI: <https://pypi.org/project/tvkit/>

```bash
uv add tvkit        # recommended
pip install tvkit
```

## Quick Example

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def main() -> None:
    async with OHLCV() as client:
        # Fetch last 10 daily bars for Apple
        bars = await client.get_historical_ohlcv(
            exchange_symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=10,
        )
    for bar in bars:
        print(bar.timestamp, bar.close)
        # 2024-01-10 00:00:00  189.34

asyncio.run(main())
```

See more working examples in [examples/](examples/).

## Automatic Reconnection

Reconnection is on by default — no changes needed to existing call sites:

```python
async with OHLCV() as client:
    # Transient disconnects are recovered automatically (5 attempts, 1s–30s backoff).
    async for bar in client.get_ohlcv("NASDAQ:AAPL", "1D"):
        print(bar.close)
```

Tune it for long-running pipelines:

```python
from tvkit.api.chart import OHLCV, StreamConnectionError

async with OHLCV(max_attempts=10, base_backoff=2.0, max_backoff=60.0) as client:
    try:
        async for bar in client.get_ohlcv("NASDAQ:AAPL", "1D"):
            print(bar.close)
    except StreamConnectionError:
        print("Stream permanently lost after all attempts")
```

## Symbol Format Reference

| Market | Example |
|--------|----------|
| US Equity | `NASDAQ:AAPL` |
| Crypto | `BINANCE:BTCUSDT` |
| Index / Macro | `INDEX:NDFI` |

Canonical format: `EXCHANGE:SYMBOL`. Dash notation (`EXCHANGE-SYMBOL`) is automatically converted.
See [concepts/symbols.md](docs/concepts/symbols.md) for the full reference.

## Documentation

Full documentation index → [docs/index.md](docs/index.md)

### Getting Started

- [Installation](docs/getting-started/installation.md) — Python version, uv, pip, source install, verification
- [Quickstart](docs/getting-started/quickstart.md) — Four self-contained examples in under 15 lines each
- [First Script](docs/getting-started/first-script.md) — Annotated walkthrough from install to first data fetch

### Concepts

- [Symbols](docs/concepts/symbols.md) — Format rules, exchange prefixes, auto-conversion
- [Intervals](docs/concepts/intervals.md) — All supported timeframes and format strings
- [Streaming vs Historical](docs/concepts/streaming-vs-historical.md) — When to use each method
- [Scanner Columns](docs/concepts/scanner-columns.md) — Column sets and when to use each

### Guides

- [Historical Data](docs/guides/historical-data.md) — Bar count mode, date-range mode, Polars integration
- [Real-time Streaming](docs/guides/realtime-streaming.md) — WebSocket streaming, multiple symbols, reconnection
- [Scanner](docs/guides/scanner.md) — 69 global markets, filters, sorting, regional analysis
- [Exporting Data](docs/guides/exporting.md) — DataExporter, CSV, JSON, Polars with metadata
- [Macro Indicators](docs/guides/macro-indicators.md) — INDEX:NDFI, USI:PCC, regime detection

### Reference

- [Chart API](docs/reference/chart/ohlcv.md) — OHLCV client: all methods, parameters, return types
- [Chart Utils](docs/reference/chart/utils.md) — Interval validation, timestamp utilities
- [Scanner API](docs/reference/scanner/scanner.md) — ScannerService interface and filter syntax
- [Markets](docs/reference/scanner/markets.md) — All 69 markets, regions, exchange identifiers
- [Export API](docs/reference/export/exporter.md) — DataExporter interface and export formats
- [Full Reference Index](docs/reference/index.md)

### Architecture

- [System Overview](docs/architecture/system-overview.md) — Four modules, async rationale, module dependencies
- [WebSocket Protocol](docs/architecture/websocket-protocol.md) — TradingView message format, session lifecycle

### Development

- [Release Process](docs/development/release-process.md) — Quality gates, version bump, publish
- [Testing Strategy](docs/development/testing-strategy.md) — Test organisation, mocking, coverage
- [Architecture Decisions](docs/development/architecture-decisions.md) — Key decisions with rationale

### Support

- [FAQ](docs/faq.md) — Symbol formats, bar limits, async requirement, disconnect handling
- [Roadmap](docs/roadmap.md) — Planned features
- [Why tvkit](docs/why-tvkit.md) — Design goals, vs rolling your own WebSocket
- [Limitations](docs/limitations.md) — Bar caps, rate limits, data coverage gaps
- [Data Sources](docs/data-sources.md) — TradingView data origin, real-time vs delayed

### Examples

Working scripts in [examples/](examples/) — clone the repo and run immediately.

## Why tvkit

TradingView provides powerful market data but does not offer an official Python SDK.
tvkit implements the TradingView WebSocket protocol and provides:

- A clean async Python API
- Strong typing via Pydantic
- Structured OHLCV models
- High-level data utilities (export, scanners)

Without needing to reverse-engineer the protocol yourself.
See [docs/why-tvkit.md](docs/why-tvkit.md) for the full rationale.

## Stability

tvkit is under active development. The public API is expected to remain stable within minor versions.
Breaking changes will follow semantic versioning.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development environment setup, quality gate commands, and pull request process.

Quality gates before every commit:

```bash
uv run ruff check .
uv run ruff format .
uv run mypy tvkit/
uv run python -m pytest tests/ -v
```

## License

MIT — see [LICENSE](LICENSE)
