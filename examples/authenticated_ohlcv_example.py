"""
Authenticated OHLCV Example
============================

Demonstrates how to use tvkit with a TradingView account to access
larger historical data windows beyond the anonymous 5,000-bar limit.

Prerequisites:
- Log in to TradingView in Chrome or Firefox before running this script.
- Install tvkit with its dependencies: uv sync

Usage:
    uv run python examples/authenticated_ohlcv_example.py           # Chrome (default)
    uv run python examples/authenticated_ohlcv_example.py firefox   # Firefox
"""

import asyncio
import logging
import sys

from tvkit.api.chart.ohlcv import OHLCV
from tvkit.auth import AuthError, BrowserCookieError, ProfileFetchError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main(browser: str) -> None:
    """Authenticate with browser cookies and fetch historical bars."""
    logger.info("Starting authenticated OHLCV example (browser=%r)", browser)

    try:
        async with OHLCV(browser=browser) as client:
            # ----------------------------------------------------------------
            # 1. Inspect account capabilities (available immediately)
            # ----------------------------------------------------------------
            account = client.account
            if account is None:
                # This should not happen in browser mode after a successful __aenter__,
                # but guard defensively.
                logger.warning(
                    "No account profile returned — check that you are logged in "
                    "to TradingView in %r.",
                    browser,
                )
            else:
                logger.info(
                    "Authenticated — plan=%r tier=%r max_bars=%d (source=%r)",
                    account.plan,
                    account.tier,
                    account.max_bars,
                    account.max_bars_source,
                )

            # ----------------------------------------------------------------
            # 2. Wait for the background probe to confirm max_bars.
            #    Skip this step for faster startup if the estimate is enough.
            # ----------------------------------------------------------------
            logger.info("Waiting for background capability probe...")
            await client.wait_until_ready()

            # Re-read account reference after the probe updates max_bars in-place.
            account = client.account
            if account is not None:
                logger.info(
                    "Probe complete — max_bars=%d source=%r status=%r confirmed=%s",
                    account.max_bars,
                    account.max_bars_source,
                    account.probe_status,
                    account.probe_confirmed,
                )

            # ----------------------------------------------------------------
            # 3. Fetch historical OHLCV bars.
            #    The segmented fetch service uses max_bars automatically.
            # ----------------------------------------------------------------
            symbol = "NASDAQ:AAPL"
            interval = "1D"
            bars_count = 1_000

            logger.info("Fetching %d bars for %s (%s)...", bars_count, symbol, interval)
            bars = await client.get_historical_ohlcv(
                exchange_symbol=symbol,
                interval=interval,
                bars_count=bars_count,
            )

            logger.info("Received %d bars", len(bars))
            if bars:
                latest = bars[-1]
                logger.info(
                    "Latest bar — timestamp=%.0f open=%s high=%s low=%s close=%s volume=%s",
                    latest.timestamp,
                    latest.open,
                    latest.high,
                    latest.low,
                    latest.close,
                    latest.volume,
                )

    except BrowserCookieError as e:
        logger.error(
            "Could not extract TradingView session cookies from %r: %s\n"
            "Fix: Log in to TradingView in %s, then run this script again.",
            browser,
            e,
            browser,
        )
    except ProfileFetchError as e:
        logger.error(
            "Could not fetch TradingView user profile: %s\n"
            "Fix: Your browser session may have expired. "
            "Log out and back in to TradingView, then run again.",
            e,
        )
    except AuthError as e:
        logger.error("Authentication error: %s", e)


if __name__ == "__main__":
    browser_arg = sys.argv[1] if len(sys.argv) > 1 else "chrome"
    asyncio.run(main(browser=browser_arg))
