#!/usr/bin/env python3
"""
Dividend-Adjusted OHLCV — tvkit Example
========================================

Demonstrates how to request dividend-adjusted (total-return) prices using the
``Adjustment`` enum, and compares them side-by-side with the default split-adjusted
prices.

Modes:
- Interactive menu: choose symbol, interval, and fetch mode
- Default demo: runs a preset comparison for SET:ADVANC

Run:
    uv run python examples/ohlcv_dividend_adjusted.py
"""

import asyncio
import logging

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from tvkit.api.chart import OHLCV, Adjustment
from tvkit.api.chart.exceptions import NoHistoricalDataError
from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.api.utils import convert_timestamp_to_iso

console: Console = Console()

# Suppress tvkit internal logs so rich output stays clean in this demo.
logging.getLogger("tvkit").setLevel(logging.CRITICAL)

# Default symbol for the preset demo
DEFAULT_SYMBOL: str = "SET:ADVANC"
DEFAULT_INTERVAL: str = "1D"
DEFAULT_COUNT_BARS: int = 300


# ── Output helpers ────────────────────────────────────────────────────────────


def _section(title: str, subtitle: str = "") -> None:
    header = Text()
    header.append(title, style="bold cyan")
    if subtitle:
        header.append(f"\n{subtitle}", style="dim")
    console.print(Panel(header, box=box.ROUNDED, border_style="cyan", padding=(0, 2)))


def _add_row(table: Table, s: OHLCVBar, d: OHLCVBar) -> None:
    date = convert_timestamp_to_iso(s.timestamp)[:10]
    ratio = d.close / s.close if s.close else 0.0
    delta = d.close - s.close
    ratio_style = "green" if ratio >= 1.0 else "red"
    table.add_row(
        date,
        f"{s.close:.3f}",
        f"{d.close:.5f}",
        Text(f"{ratio:.4f}", style=ratio_style),
        Text(f"{delta:+.3f}", style=ratio_style),
    )


def _render_comparison(
    splits_bars: list[OHLCVBar],
    div_bars: list[OHLCVBar],
    *,
    head: int = 5,
    tail: int = 5,
) -> None:
    """Render a Rich table comparing split-adjusted vs dividend-adjusted closes."""
    table = Table(box=box.SIMPLE_HEAD, show_edge=False, padding=(0, 1))
    table.add_column("Date", style="bold", min_width=12)
    table.add_column("Splits-Adj", justify="right", min_width=12)
    table.add_column("Dividend-Adj", justify="right", min_width=14)
    table.add_column("Ratio", justify="right", min_width=8)
    table.add_column("Delta", justify="right", min_width=10)

    paired = list(zip(splits_bars, div_bars, strict=False))
    total = len(paired)
    cutoff = head + tail

    rows_to_show = paired[:head] if total > cutoff else paired
    for s, d in rows_to_show:
        _add_row(table, s, d)

    if total > cutoff:
        table.add_row(Text(f"  … {total - cutoff} bars omitted …", style="dim"), "", "", "", "")
        for s, d in paired[-tail:]:
            _add_row(table, s, d)

    console.print(table)


def _print_count_summary(splits_bars: list[OHLCVBar], div_bars: list[OHLCVBar]) -> None:
    first_s, first_d = splits_bars[0].close, div_bars[0].close
    last_s, last_d = splits_bars[-1].close, div_bars[-1].close
    first_ratio = first_d / first_s if first_s else 0.0
    last_ratio = last_d / last_s if last_s else 0.0

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="dim")
    summary.add_column()
    summary.add_row("Oldest bar ratio (div-adj / splits):", f"{first_ratio:.4f}")
    summary.add_row("Newest bar ratio (div-adj / splits):", f"{last_ratio:.4f}")
    summary.add_row(
        "Interpretation:",
        "Ratio < 1.0 means historical prices are lower in the dividend-adjusted "
        "series (dividends deducted backward).",
    )
    console.print()
    console.print(summary)


# ── Demo functions ────────────────────────────────────────────────────────────


async def run_count_mode(symbol: str, interval: str, bars_count: int) -> None:
    """Fetch and compare bars_count most-recent bars in both adjustment modes."""
    _section(
        "Count Mode Comparison",
        f"{bars_count} most-recent {interval} bars · {symbol} · splits vs dividend-adjusted",
    )

    async with OHLCV() as client:
        splits_bars = await client.get_historical_ohlcv(
            exchange_symbol=symbol,
            interval=interval,
            bars_count=bars_count,
            adjustment=Adjustment.SPLITS,
        )
        div_bars = await client.get_historical_ohlcv(
            exchange_symbol=symbol,
            interval=interval,
            bars_count=bars_count,
            adjustment=Adjustment.DIVIDENDS,
        )

    if not splits_bars or not div_bars:
        console.print("  [yellow]⚠[/yellow]  No bars returned — check the symbol and interval.")
        return

    _render_comparison(splits_bars, div_bars, head=5, tail=5)
    _print_count_summary(splits_bars, div_bars)


async def run_range_mode(symbol: str, interval: str, start: str, end: str) -> None:
    """Fetch dividend-adjusted bars for a specific date window."""
    _section(
        "Range Mode — Dividend-Adjusted",
        f"{symbol} · {start} → {end} · {interval} bars",
    )

    try:
        async with OHLCV() as client:
            div_bars = await client.get_historical_ohlcv(
                exchange_symbol=symbol,
                interval=interval,
                start=start,
                end=end,
                adjustment=Adjustment.DIVIDENDS,
            )
    except NoHistoricalDataError:
        console.print(
            "  [yellow]⚠[/yellow]  No historical data for this range in anonymous mode. "
            "Authenticate with an account to access older data."
        )
        return

    if not div_bars:
        console.print("  [yellow]⚠[/yellow]  No bars returned.")
        return

    first_date = convert_timestamp_to_iso(div_bars[0].timestamp)[:10]
    last_date = convert_timestamp_to_iso(div_bars[-1].timestamp)[:10]

    info = Table.grid(padding=(0, 2))
    info.add_column(style="dim")
    info.add_column()
    info.add_row("Bars received:", str(len(div_bars)))
    info.add_row("Date range:", f"{first_date} → {last_date}")
    info.add_row("First bar close (div-adj):", f"{div_bars[0].close:.5f}")
    info.add_row("Last bar close  (div-adj):", f"{div_bars[-1].close:.5f}")
    console.print(info)


def show_adjustment_reference() -> None:
    """Display the Adjustment enum members and their protocol values."""
    _section(
        "Adjustment Enum Reference",
        "Protocol values sent in the TradingView WebSocket resolve_symbol message",
    )

    table = Table(box=box.SIMPLE_HEAD, show_edge=False, padding=(0, 1))
    table.add_column("Enum member", style="bold cyan", min_width=24)
    table.add_column("Protocol value", min_width=14)
    table.add_column("Description", min_width=50)

    table.add_row(
        "Adjustment.SPLITS",
        Text('"splits"', style="dim"),
        "Split-adjusted only — default, backwards-compatible with all pre-v0.11.0 calls",
    )
    table.add_row(
        "Adjustment.DIVIDENDS",
        Text('"dividends"', style="dim"),
        "Dividend-adjusted (total-return) — prior prices backward-adjusted for cash dividends",
    )

    console.print(table)
    console.print()
    note = Table.grid(padding=(0, 1))
    note.add_column(style="dim")
    note.add_column()
    note.add_row(
        "Note:",
        "Adjustment.NONE (raw unadjusted prices) is not yet supported — "
        "protocol value not confirmed; tracked for a future release.",
    )
    console.print(note)


# ── Menu helpers ──────────────────────────────────────────────────────────────


def _prompt_symbol() -> str:
    return (
        Prompt.ask(
            "  [bold]Symbol[/bold] [dim](e.g. NASDAQ:AAPL, SET:ADVANC)[/dim]",
            default=DEFAULT_SYMBOL,
        )
        .strip()
        .upper()
    )


def _prompt_interval() -> str:
    return Prompt.ask(
        "  [bold]Interval[/bold] [dim](1, 5, 15, 60, 1H, 1D, 1W, 1M)[/dim]",
        default=DEFAULT_INTERVAL,
    ).strip()


def _print_menu() -> None:
    menu = Table.grid(padding=(0, 2))
    menu.add_column(style="bold cyan", min_width=4)
    menu.add_column()
    menu.add_row("1", "Preset demo — SET:ADVANC 1D · 300 bars · splits vs dividend-adjusted")
    menu.add_row("2", "Custom symbol — count mode (N most-recent bars)")
    menu.add_row("3", "Custom symbol — range mode (date window, dividend-adjusted)")
    menu.add_row("4", "Show Adjustment enum reference")
    menu.add_row("5", "Exit")
    console.print(menu)


# ── Main ──────────────────────────────────────────────────────────────────────


async def main() -> None:
    console.print()
    console.print(
        Panel(
            "[bold white]Dividend-Adjusted OHLCV — tvkit[/bold white]\n"
            "[dim]Compare split-adjusted vs total-return prices using the Adjustment enum[/dim]",
            box=box.DOUBLE_EDGE,
            border_style="bright_blue",
            padding=(1, 4),
        )
    )

    while True:
        console.print()
        _print_menu()
        console.print()
        choice = Prompt.ask(
            "  [bold]Select[/bold]",
            choices=["1", "2", "3", "4", "5"],
            default="1",
        )
        console.print()

        if choice == "1":
            await run_count_mode(
                symbol=DEFAULT_SYMBOL,
                interval=DEFAULT_INTERVAL,
                bars_count=DEFAULT_COUNT_BARS,
            )

        elif choice == "2":
            symbol = _prompt_symbol()
            interval = _prompt_interval()
            bars_count = IntPrompt.ask(
                "  [bold]Bars count[/bold]",
                default=DEFAULT_COUNT_BARS,
            )
            console.print()
            await run_count_mode(symbol=symbol, interval=interval, bars_count=bars_count)

        elif choice == "3":
            symbol = _prompt_symbol()
            interval = _prompt_interval()
            start = Prompt.ask(
                "  [bold]Start date[/bold] [dim](YYYY-MM-DD)[/dim]",
                default="2025-01-01",
            ).strip()
            end = Prompt.ask(
                "  [bold]End date[/bold]   [dim](YYYY-MM-DD)[/dim]",
                default="2025-12-31",
            ).strip()
            console.print()
            await run_range_mode(symbol=symbol, interval=interval, start=start, end=end)

        elif choice == "4":
            show_adjustment_reference()

        elif choice == "5":
            console.print("[bold green]Goodbye.[/bold green]")
            break


if __name__ == "__main__":
    asyncio.run(main())
