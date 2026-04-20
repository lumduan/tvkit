#!/usr/bin/env python3
"""
Async Batch Downloader — tvkit Example
=======================================

Demonstrates high-throughput concurrent historical OHLCV fetching for a set
of well-known large-cap symbols using ``tvkit.batch``.

What you'll learn:
- Fetching OHLCV data for many symbols concurrently (bounded concurrency)
- Real-time progress reporting with a live progress bar
- Handling partial failures gracefully (strict=False default)
- Deduplication and symbol normalization behaviour
- Pre-flight symbol validation (opt-in)
- Summary reporting: success/failure counts, per-symbol elapsed time
- Raising on any failure with strict=True / raise_if_failed()

Run:
    uv run python examples/batch_sp500_historical.py
"""

import asyncio
import logging
import traceback

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from tvkit.api.utils import convert_timestamp_to_iso
from tvkit.batch import BatchDownloadRequest, BatchDownloadSummary, SymbolResult, batch_download
from tvkit.batch.exceptions import BatchDownloadError

console = Console()

# Suppress tvkit internal logs so rich output stays clean in this demo.
logging.getLogger("tvkit").setLevel(logging.CRITICAL)

# ── Sample symbol sets ────────────────────────────────────────────────────────

_MEGA_CAPS: list[str] = [
    "NASDAQ:AAPL",
    "NASDAQ:MSFT",
    "NASDAQ:NVDA",
    "NASDAQ:GOOGL",
    "NASDAQ:AMZN",
    "NYSE:BRK.B",
    "NYSE:JPM",
    "NYSE:V",
    "NYSE:UNH",
    "NYSE:XOM",
]

# Intentional duplicates and case variation — batch_download deduplicates these.
_SYMBOLS_WITH_DUPES: list[str] = [
    "NASDAQ:AAPL",
    "nasdaq:aapl",  # duplicate, different case
    "NASDAQ:MSFT",
    "NASDAQ:MSFT",  # exact duplicate
    "NYSE:JPM",
]


# ── Output helpers ────────────────────────────────────────────────────────────


def _section(title: str, subtitle: str = "") -> None:
    header = Text()
    header.append(title, style="bold cyan")
    if subtitle:
        header.append(f"\n{subtitle}", style="dim")
    console.print(Panel(header, box=box.ROUNDED, border_style="cyan", padding=(0, 2)))


def _print_summary(summary: BatchDownloadSummary) -> None:
    """Render a BatchDownloadSummary as a rich table."""
    # Header counts
    header = Table.grid(padding=(0, 2))
    header.add_column(style="bold")
    header.add_column()
    header.add_row(
        "Symbols",
        f"{summary.total_count} requested  ·  "
        f"[green]{summary.success_count} succeeded[/green]  ·  "
        f"[red]{summary.failure_count} failed[/red]",
    )
    header.add_row("Interval", summary.interval)
    header.add_row("Wall time", f"{summary.elapsed_seconds:.2f}s")
    console.print(header)
    console.print()

    # Per-symbol results
    table = Table(box=box.SIMPLE_HEAD, show_edge=False, padding=(0, 1))
    table.add_column("Symbol", style="bold", min_width=16, max_width=18, no_wrap=True)
    table.add_column("Status", justify="center", min_width=9)
    table.add_column("Bars", justify="right", min_width=5)
    table.add_column("Atts", justify="right", min_width=4)
    table.add_column("Elapsed", justify="right", min_width=7)
    table.add_column("Close", justify="right", min_width=8)
    table.add_column("Last Bar", justify="right", min_width=10)

    for result in summary.results:
        if result.success:
            status = Text("✔  OK", style="bold green")
            bars_col = str(len(result.bars))
            last_close = f"${result.bars[-1].close:,.2f}" if result.bars else "—"
            last_date = (
                convert_timestamp_to_iso(result.bars[-1].timestamp)[:10] if result.bars else "—"
            )
            last_bar_col = Text(last_date, style="dim")
        else:
            status = Text("✘  FAIL", style="bold red")
            bars_col = "—"
            last_close = "—"
            last_bar_col = Text("—", style="dim")

        table.add_row(
            result.symbol,
            status,
            bars_col,
            str(result.attempts),
            f"{result.elapsed_seconds:.2f}s",
            last_close,
            last_bar_col,
        )

    console.print(table)

    # Print failure details below the table (error type + message)
    failures = [r for r in summary.results if not r.success]
    if failures:
        console.print()
        for r in failures:
            exc_type = (r.error.exception_type if r.error else "?").split(".")[-1]
            error_msg = (r.error.message if r.error else "unknown").replace("\n", " ")[:60]
            console.print(
                f"  [red]✘[/red]  [bold]{r.symbol}[/bold]  [dim][{exc_type}][/dim] {error_msg}",
            )


# ── Demo sections ─────────────────────────────────────────────────────────────


async def demo_basic_batch() -> None:
    """Fetch 252 daily bars for 10 mega-cap symbols with a live progress bar."""
    _section(
        "Demo 1 — Basic Batch Download",
        "252 daily bars · 10 symbols · concurrency=5 · bars_count mode",
    )

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("·  [cyan]{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )

    task_id: TaskID | None = None

    def on_progress(result: SymbolResult, completed: int, total: int) -> None:
        nonlocal task_id
        if task_id is None:
            return
        symbol_short = result.symbol.split(":")[1]
        status = "✔" if result.success else "✘"
        progress.update(
            task_id,
            advance=1,
            description=f"[bold blue]Batch download  {status} {symbol_short:<6}",
        )

    with progress:
        task_id = progress.add_task("Batch download  …      ", total=len(_MEGA_CAPS))
        request = BatchDownloadRequest(
            symbols=_MEGA_CAPS,
            interval="1D",
            bars_count=252,
            concurrency=5,
            on_progress=on_progress,
        )
        summary = await batch_download(request)

    console.print()
    _print_summary(summary)


async def demo_deduplication() -> None:
    """Show that duplicate and case-variant symbols are silently deduplicated."""
    _section(
        "Demo 2 — Deduplication",
        "5 input symbols → 3 unique after normalization + dedup",
    )

    console.print(f"  Input symbols ({len(_SYMBOLS_WITH_DUPES)}):", style="dim")
    for s in _SYMBOLS_WITH_DUPES:
        console.print(f"    [dim]•[/dim] {s}")
    console.print()

    request = BatchDownloadRequest(
        symbols=_SYMBOLS_WITH_DUPES,
        interval="1D",
        bars_count=10,
        concurrency=3,
    )
    summary = await batch_download(request)

    console.print(
        f"  After dedup: [bold cyan]{summary.total_count}[/bold cyan] unique symbols fetched"
    )
    console.print()
    _print_summary(summary)


async def demo_partial_failure() -> None:
    """Show strict=False partial failure — real and fake symbols mixed."""
    _section(
        "Demo 3 — Partial Failure (strict=False)",
        "Mix of real symbols and invalid symbols — failures collected, not raised",
    )

    mixed_symbols = ["NASDAQ:AAPL", "NASDAQ:INVALID_FAKE_XYZ", "NASDAQ:MSFT"]
    request = BatchDownloadRequest(
        symbols=mixed_symbols,
        interval="1D",
        bars_count=10,
        concurrency=3,
        max_attempts=1,  # fail fast for demo
        strict=False,
    )
    summary = await batch_download(request)
    _print_summary(summary)

    if summary.failure_count > 0:
        console.print(
            f"  [yellow]⚠[/yellow]  {summary.failure_count} symbol(s) failed — "
            "inspect summary.failed_symbols for details"
        )
        console.print(f"  Failed: {summary.failed_symbols}")


async def demo_strict_mode() -> None:
    """Show strict=True — BatchDownloadError raised with partial results attached."""
    _section(
        "Demo 4 — Strict Mode (strict=True)",
        "BatchDownloadError raised if any symbol fails; partial results on exc.summary",
    )

    mixed_symbols = ["NASDAQ:AAPL", "NASDAQ:INVALID_FAKE_XYZ"]
    request = BatchDownloadRequest(
        symbols=mixed_symbols,
        interval="1D",
        bars_count=10,
        concurrency=2,
        max_attempts=1,
        strict=True,
    )

    try:
        await batch_download(request)
        console.print("  All symbols succeeded — no exception raised.", style="green")
    except BatchDownloadError as exc:
        console.print(
            f"  [bold red]BatchDownloadError[/bold red]: {exc}",
        )
        console.print(
            f"  [dim]Partial results on exc.summary:[/dim]  "
            f"[green]{exc.summary.success_count} ok[/green]  ·  "
            f"[red]{exc.summary.failure_count} failed[/red]"
        )
        console.print(f"  Failed symbols: [red]{exc.failed_symbols}[/red]")
        console.print()
        console.print("  [dim]Successful results still accessible via exc.summary.results:[/dim]")
        for result in exc.summary.results:
            if result.success:
                console.print(
                    f"    [green]✔[/green]  {result.symbol}  "
                    f"→ {len(result.bars)} bars, "
                    f"last close ${result.bars[-1].close:,.2f}"
                )


async def main() -> None:
    console.print()
    console.print(
        Panel(
            "[bold white]tvkit.batch — Async Batch Downloader[/bold white]\n"
            "[dim]High-throughput concurrent OHLCV fetching with bounded concurrency, "
            "retry, and partial-failure support[/dim]",
            box=box.DOUBLE_EDGE,
            border_style="bright_blue",
            padding=(1, 4),
        )
    )
    console.print()

    try:
        await demo_basic_batch()
        console.print()
        await demo_deduplication()
        console.print()
        await demo_partial_failure()
        console.print()
        await demo_strict_mode()
        console.print()
        console.print("[bold green]All demos complete.[/bold green]")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
