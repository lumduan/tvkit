# tvkit Documentation

tvkit is an async Python library for TradingView's financial data APIs. This index links every section of the documentation so you can find what you need regardless of where you start.

```python
from tvkit import OHLCV

# Fetch the latest 5 daily bars for Apple
async with OHLCV() as client:
    bars = await client.get_historical_ohlcv(
        "NASDAQ:AAPL", interval="1D", bars_count=5
    )
    for bar in bars:
        print(f"{bar.timestamp}  close={bar.close}  volume={bar.volume}")
```

---

## Recommended Learning Paths

**New to tvkit?** Follow this path to get up and running quickly:

1. [Installation](getting-started/installation.md) — install the package
2. [Quickstart](getting-started/quickstart.md) — four working examples in under 5 minutes
3. [First Script](getting-started/first-script.md) — annotated walkthrough of your first tvkit script
4. [Historical Data](guides/historical-data.md) — fetch real OHLCV bars from TradingView

**Already familiar with async Python?** Jump directly to:

1. [Concepts](concepts/symbols.md) — tvkit-specific terminology and format rules
2. [Scanner Guide](guides/scanner.md) — screen global markets with hundreds of financial metrics
3. [Exporting Data](guides/exporting.md) — CSV, JSON, and Polars DataFrame export

---

## Getting Started 🚀

*Minimal steps to run your first tvkit code.*

- [Installation](getting-started/installation.md)
- [Quickstart](getting-started/quickstart.md)
- [First Script](getting-started/first-script.md)

---

## Why tvkit? 🤔

*Context and constraints that help you decide if tvkit is the right tool.*

- [Why tvkit](why-tvkit.md)
- [Limitations](limitations.md)
- [Data Sources](data-sources.md)

---

## Concepts 🧠

*Key terminology used throughout tvkit — read before the guides.*

- [Symbols](concepts/symbols.md)
- [Intervals](concepts/intervals.md)
- [Streaming vs Historical](concepts/streaming-vs-historical.md)
- [Scanner Columns](concepts/scanner-columns.md)
- [Timezones](concepts/timezones.md) — UTC internal model; how to convert OHLCV timestamps to exchange or local time
- [Account Capabilities](concepts/capabilities.md) — TradingView plan tiers, bar limits, and capability detection

---

## Guides 📘

*Task-oriented tutorials with complete, runnable examples. Assumes concepts are understood.*

- [Historical Data](guides/historical-data.md)
- [Real-time Streaming](guides/realtime-streaming.md)
- [Authenticated Sessions](guides/authenticated-sessions.md) — browser cookies, token injection, capability detection
- [Google Colab / Hosted Notebooks](guides/notebook-colab.md) — export cookies from host and use in remote environments
- [Scanner](guides/scanner.md)
- [Exporting Data](guides/exporting.md)
- [Macro Indicators](guides/macro-indicators.md)

---

## Reference 📚

*Complete API specifications — method signatures, parameters, return types, and exceptions.*

- [Chart API — OHLCV Client](reference/chart/ohlcv.md)
- [Authentication — tvkit.auth](reference/auth/index.md)
- [Scanner API](reference/scanner/scanner.md)
- [Export API](reference/export/exporter.md)
- [Timezone Utilities — tvkit.time](reference/time/index.md)
- [Full Reference Index](reference/index.md)

---

## Architecture 🏗️

*High-level design documents explaining how the system works.*

- [System Overview](architecture/system-overview.md)
- [WebSocket Protocol](architecture/websocket-protocol.md)

---

## Internals 🔬

*Implementation detail for contributors and curious readers.*

- [Connection Service](internals/connection-service.md)
- [Message Service](internals/message-service.md)

---

## Development 🛠️

*Contributor workflows for releasing, testing, and recording architectural decisions.*

- [Release Process](development/release-process.md)
- [Testing Strategy](development/testing-strategy.md)
- [Architecture Decisions](development/architecture-decisions.md)

---

## Community 🌍

- [FAQ](faq.md)
- [Roadmap](roadmap.md)
- [Changelog](../CHANGELOG.md)
- [Contributing](../CONTRIBUTING.md)
- [Code of Conduct](../CODE_OF_CONDUCT.md)
- [Security](../SECURITY.md)

---

## Need Help?

- [Open a GitHub issue](https://github.com/lumduan/tvkit/issues) — bug reports and feature requests
- [Start a Discussion](https://github.com/lumduan/tvkit/discussions) — questions and community support
