---
name: Bug Report
about: Report a reproducible bug in tvkit
title: "[Bug] <short description — e.g. OHLCV returns empty candles for NASDAQ:AAPL 1D>"
labels: bug
assignees: ''
---

## Environment

| Field | Value |
|-------|-------|
| **tvkit version** | <!-- e.g. 0.3.0 — run `uv run python -c "import tvkit; print(tvkit.__version__)"` --> |
| **Python version** | <!-- e.g. 3.13.1 — run `python --version` --> |
| **Operating system** | <!-- e.g. macOS 15.3, Ubuntu 24.04, Windows 11 --> |
| **Installation method** | <!-- pip install tvkit / uv add tvkit / source install --> |

---

## Symbol(s) affected

<!-- The exact symbol string(s) you passed to tvkit. If not symbol-specific, write "N/A". -->

```
# Replace with your symbol(s)
NASDAQ:AAPL
```

## Interval

<!-- The interval string you passed. Common values: 1D (daily), 60 (60-min), 15 (15-min), 1 (1-min), 1W (weekly). If not applicable, write "N/A". -->

```
# Replace with the interval you used
1D
```

---

## Steps to reproduce (if applicable)

<!-- If the bug requires a sequence of actions or timing (e.g. waiting, reconnecting), list them here. -->
<!-- If a single code block is enough to reproduce the bug, write "See reproduction code below." -->

1.
2.
3.

---

## Minimal reproduction code

<!-- The smallest possible script that triggers the bug. Remove all business logic. -->
<!-- Please ensure the code runs as a standalone script — maintainers should be able to copy, paste, and run it immediately. -->

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def main():
    async with OHLCV() as client:
        # paste the call that fails here

asyncio.run(main())
```

---

## Expected behaviour

<!-- What did you expect tvkit to do? -->

---

## Actual behaviour

<!-- What did tvkit actually do? Describe the observable outcome. -->

---

## Full traceback

<!-- Paste the complete Python traceback here. Do not truncate it. -->
<!-- If there is no traceback, write "No traceback — see Actual behaviour above." -->

```text
<traceback here>
```

---

## Debug logs (if available)

<!--
For WebSocket or connection issues, re-run your script with DEBUG logging enabled:

    import logging
    logging.basicConfig(level=logging.DEBUG)

Then paste the relevant log output below.
If no additional logs appeared, write "No additional debug output."
-->

```text
<debug log output here>
```

---

## Additional context

<!-- Any other information that might help: network environment, proxy, VPN, TradingView account tier, etc. -->
