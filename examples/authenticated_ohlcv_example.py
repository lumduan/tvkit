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
from datetime import UTC, datetime

from rich import box
from rich.console import Console
from rich.table import Table

from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.auth import AuthError, BrowserCookieError, ProfileFetchError

# Suppress noisy internal library logs — only show WARNING and above from third-parties.
logging.basicConfig(level=logging.WARNING)
# Keep our own logger at INFO so intentional messages still appear.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console = Console()


def _print_account_table(
    user_id: int,
    username: str,
    plan: str,
    tier: str,
    max_bars: int,
    max_bars_source: str,
    probe_status: str,
    probe_confirmed: bool,
) -> None:
    """Render account identity and capabilities as a two-column rich table."""
    table = Table(
        title="TradingView Account",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Field", style="bold")
    table.add_column("Value")

    # Identity rows — confirm you are logged in to the correct account.
    table.add_row("User ID", str(user_id))
    table.add_row("Username", f"[bold]{username}[/bold]")
    table.add_row("Plan", plan)
    table.add_row("Tier", tier)
    table.add_row("Max Bars", str(max_bars))
    table.add_row("Max Bars Source", max_bars_source)
    table.add_row("Probe Status", probe_status)
    table.add_row(
        "Probe Confirmed", "[green]Yes[/green]" if probe_confirmed else "[yellow]No[/yellow]"
    )

    console.print(table)


def _print_bars_table(bars: list[OHLCVBar], symbol: str, interval: str) -> None:
    """Render the first 5 and last 5 OHLCV bars as a rich table.

    A separator row is inserted between the head and tail sections
    when there are more than 10 bars in total.
    """
    table = Table(
        title=f"OHLCV Bars  {symbol} [{interval}]  — {len(bars):,} bars total (showing first 5 & last 5)",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold magenta",
    )

    # Define columns
    for col, justify in [
        ("Timestamp (UTC)", "left"),
        ("Open", "right"),
        ("High", "right"),
        ("Low", "right"),
        ("Close", "right"),
        ("Volume", "right"),
    ]:
        table.add_column(col, justify=justify)  # type: ignore[arg-type]

    def _row(bar: OHLCVBar) -> tuple[str, str, str, str, str, str]:
        """Format a single bar into display strings."""
        dt: str = datetime.fromtimestamp(bar.timestamp, tz=UTC).strftime("%Y-%m-%d %H:%M")
        return (
            dt,
            f"{bar.open:.4f}",
            f"{bar.high:.4f}",
            f"{bar.low:.4f}",
            f"{bar.close:.4f}",
            f"{bar.volume:,.0f}",
        )

    head: list[OHLCVBar] = bars[:5]
    tail: list[OHLCVBar] = bars[-5:] if len(bars) > 5 else []

    for bar in head:
        table.add_row(*_row(bar))

    # Show a visual gap when the head and tail do not overlap.
    if len(bars) > 10:
        table.add_row("…", "…", "…", "…", "…", "…", style="dim")

    for bar in tail:
        table.add_row(*_row(bar))

    console.print(table)


async def main(browser: str) -> None:
    """Authenticate with browser cookies and fetch historical bars."""
    console.print(
        f"\n[bold]Starting authenticated OHLCV example[/bold]  (browser=[cyan]{browser!r}[/cyan])\n"
    )

    try:
        async with OHLCV(browser=browser) as client:
            # ----------------------------------------------------------------
            # 1. Inspect account capabilities available immediately after login.
            # ----------------------------------------------------------------
            account = client.account
            if account is None:
                # Guard: should not happen in browser mode, but be defensive.
                console.print(
                    f"[yellow]Warning:[/yellow] No account profile returned. "
                    f"Check that you are logged in to TradingView in {browser!r}."
                )
            else:
                _print_account_table(
                    user_id=account.user_id,
                    username=account.username,
                    plan=account.plan,
                    tier=account.tier,
                    max_bars=account.max_bars,
                    max_bars_source=account.max_bars_source,
                    probe_status=account.probe_status,
                    probe_confirmed=account.probe_confirmed,
                )

            # ----------------------------------------------------------------
            # 2. Wait for the background probe to confirm max_bars.
            #    Skip for faster startup when the estimate is sufficient.
            # ----------------------------------------------------------------
            console.print("[dim]Waiting for background capability probe…[/dim]")
            await client.wait_until_ready()

            # Re-read account reference after probe may update max_bars in-place.
            account = client.account
            if account is not None:
                # Re-render the table with the final confirmed values.
                _print_account_table(
                    user_id=account.user_id,
                    username=account.username,
                    plan=account.plan,
                    tier=account.tier,
                    max_bars=account.max_bars,
                    max_bars_source=account.max_bars_source,
                    probe_status=account.probe_status,
                    probe_confirmed=account.probe_confirmed,
                )

            # ----------------------------------------------------------------
            # 3. Fetch historical OHLCV bars.
            #    The segmented fetch service respects max_bars automatically.
            # ----------------------------------------------------------------
            # BINANCE:BTCUSDT trades 24/7 — ideal for verifying data retrieval at any time.
            symbol: str = "BINANCE:BTCUSDT"
            interval: str = "1H"
            bars_count: int = 20000

            console.print(
                f"\n[bold]Fetching[/bold] [cyan]{bars_count:,}[/cyan] bars for "
                f"[green]{symbol}[/green] ([yellow]{interval}[/yellow])…\n"
            )
            bars = await client.get_historical_ohlcv(
                exchange_symbol=symbol,
                interval=interval,
                bars_count=bars_count,
            )

            # Display a summary table with head + tail rows for quick inspection.
            _print_bars_table(bars=bars, symbol=symbol, interval=interval)

    except BrowserCookieError as e:
        console.print(
            f"[bold red]Cookie Error:[/bold red] Could not extract TradingView session cookies "
            f"from {browser!r}.\n{e}\n"
            f"[dim]Fix: Log in to TradingView in {browser}, then run this script again.[/dim]"
        )
    except ProfileFetchError as e:
        console.print(
            f"[bold red]Profile Error:[/bold red] Could not fetch TradingView user profile.\n{e}\n"
            "[dim]Fix: Your browser session may have expired. "
            "Log out and back in to TradingView, then run again.[/dim]"
        )
    except AuthError as e:
        console.print(f"[bold red]Auth Error:[/bold red] {e}")


if __name__ == "__main__":
    browser_arg: str = sys.argv[1] if len(sys.argv) > 1 else "chrome"
    asyncio.run(main(browser=browser_arg))
