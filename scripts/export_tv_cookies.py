"""
export_tv_cookies.py
====================

Interactive script to extract TradingView session cookies from your local
Chrome or Firefox browser and export them for use in remote environments
(Google Colab, CI, Docker, remote servers) where browser access is unavailable.

Prerequisites:
    - Log in to TradingView in Chrome or Firefox before running.
    - Dependencies are already installed: uv sync

Usage::

    uv run python scripts/export_tv_cookies.py

Security:
    The exported JSON contains your TradingView session credentials.
    Treat it like a password — do not commit it to git or share it publicly.
"""

import json
import sys
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

from tvkit.auth.cookie_provider import CookieProvider
from tvkit.auth.exceptions import BrowserCookieError

console = Console()

# Cookies that must be present for TradingView authentication.
_REQUIRED_COOKIES: set[str] = {"sessionid"}
# Cookies that are useful but not strictly required.
_OPTIONAL_COOKIES: set[str] = {"csrftoken", "device_t", "tv_ecuid", "sessionid_sign"}


def _select_browser() -> str:
    """Prompt the user to select a browser."""
    console.print()
    console.print("[bold]Which browser are you logged in to TradingView with?[/bold]")
    console.print("  [cyan]1[/cyan]  Chrome (default)")
    console.print("  [cyan]2[/cyan]  Firefox")
    console.print()

    choice = Prompt.ask("Enter choice", choices=["1", "2"], default="1")
    return "chrome" if choice == "1" else "firefox"


def _extract_cookies(browser: str) -> dict[str, str]:
    """Extract TradingView cookies using tvkit's CookieProvider."""
    with console.status(
        f"[dim]Extracting cookies from [bold]{browser}[/bold]…[/dim]",
        spinner="dots",
    ):
        provider = CookieProvider()
        return provider.extract(browser=browser)


def _print_cookie_summary(cookies: dict[str, str], browser: str) -> None:
    """Print a summary table of the cookies found (names only, no values)."""
    table = Table(
        title=f"Cookies found in {browser.capitalize()}",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Cookie name", style="bold")
    table.add_column("Status")

    all_known = _REQUIRED_COOKIES | _OPTIONAL_COOKIES
    for name in sorted(all_known):
        if name in cookies:
            status = "[green]✓ present[/green]"
        elif name in _REQUIRED_COOKIES:
            status = "[red]✗ missing (required)[/red]"
        else:
            status = "[dim]– not found[/dim]"
        table.add_row(name, status)

    extra = [k for k in cookies if k not in all_known]
    for name in sorted(extra):
        table.add_row(name, "[dim]present (extra)[/dim]")

    console.print()
    console.print(table)
    console.print(f"\n[bold green]✓[/bold green] Extracted [bold]{len(cookies)}[/bold] cookie(s).")


def _export_to_file(cookies: dict[str, str]) -> None:
    """Prompt for a file path and write the cookies JSON there."""
    default_path = "tv_cookies.json"
    path_str = Prompt.ask("\nSave to file", default=default_path)
    dest = Path(path_str)
    dest.write_text(json.dumps(cookies, indent=2))
    console.print(f"\n[bold green]✓[/bold green] Saved to [cyan]{dest.resolve()}[/cyan]")
    console.print(
        "\n[yellow]⚠[/yellow]  Add [bold]tv_cookies.json[/bold] to [bold].gitignore[/bold] "
        "— it contains your session credentials."
    )


def _print_colab_instructions(json_str: str) -> None:
    """Print step-by-step instructions for using the cookies in Colab."""
    console.print()
    console.print(
        Panel(
            "[bold]How to use these cookies in Google Colab[/bold]\n\n"
            "1. Open your Colab notebook.\n"
            "2. Click the [bold]key icon[/bold] (🔑) in the left sidebar "
            "→ [bold]Add new secret[/bold].\n"
            "3. Set [bold]Name[/bold] to [cyan]TV_COOKIES[/cyan].\n"
            "4. Paste [bold]only the JSON line[/bold] between the dashed lines as the [bold]Value[/bold].\n"
            "   (The JSON is a single line starting with { and ending with })\n"
            "5. Enable [bold]Notebook access[/bold] for the secret.",
            title="Colab setup",
            border_style="cyan",
        )
    )

    code = """\
import asyncio, json
from google.colab import userdata
from tvkit.api.chart.ohlcv import OHLCV

cookies = json.loads(userdata.get("TV_COOKIES"))

async def fetch():
    async with OHLCV(cookies=cookies) as client:
        account = client.account
        if account:
            print(f"Logged in: {account.username}  |  plan: {account.plan}  |  max_bars: {account.max_bars}")
        bars = await client.get_historical_ohlcv(
            exchange_symbol="BINANCE:BTCUSDT",
            interval="1H",
            bars_count=10_000,
        )
        print(f"Fetched {len(bars):,} bars")
        return bars

bars = asyncio.run(fetch())
"""
    console.print()
    console.print("[bold]Colab cell — paste after setting the secret:[/bold]")
    console.print(Syntax(code, "python", theme="monokai", line_numbers=False))


def main() -> None:
    console.print(
        Panel(
            "[bold]TradingView Cookie Exporter[/bold]\n\n"
            "Extracts your TradingView session cookies from a local browser so you can\n"
            "authenticate tvkit in remote environments (Google Colab, CI, servers).\n\n"
            "[yellow]Prerequisites:[/yellow] log in to TradingView in Chrome or Firefox first.",
            border_style="bright_blue",
        )
    )

    # ── Step 1: Select browser ──────────────────────────────────────────
    browser = _select_browser()

    # ── Step 2: Extract cookies ─────────────────────────────────────────
    try:
        cookies = _extract_cookies(browser)
    except BrowserCookieError as e:
        console.print(f"\n[bold red]Cookie extraction failed:[/bold red] {e}")
        console.print(
            f"[dim]Fix: log in to TradingView in {browser.capitalize()}, "
            "then run this script again.[/dim]"
        )
        sys.exit(1)

    _print_cookie_summary(cookies, browser)

    # ── Step 3: Export ──────────────────────────────────────────────────
    console.print()
    console.print("[bold]Export options:[/bold]")
    console.print("  [cyan]1[/cyan]  Print JSON to terminal (copy-paste into Colab Secrets)")
    console.print("  [cyan]2[/cyan]  Save JSON to a local file")
    console.print("  [cyan]3[/cyan]  Both")
    console.print()

    export_choice = Prompt.ask("Choose export option", choices=["1", "2", "3"], default="1")

    # Filter to auth-essential cookies only.  The full cookie jar contains
    # analytics, consent, and tracking cookies that are not needed and make
    # the JSON too large for Colab Secrets to store reliably.
    essential_keys = _REQUIRED_COOKIES | _OPTIONAL_COOKIES
    export_cookies = {k: v for k, v in cookies.items() if k in essential_keys}
    json_str = json.dumps(export_cookies)

    if export_choice in ("1", "3"):
        console.print()
        console.print(
            "[bold]JSON output[/bold] — select all text between the lines below "
            "and paste into [cyan]TV_COOKIES[/cyan]:\n"
            "[dim](do not copy the dashed lines themselves)[/dim]"
        )
        console.print("[dim]" + "-" * 60 + "[/dim]")
        # Print raw to stdout so copy-paste captures the exact string without
        # any Rich markup, borders, or line wrapping artefacts.
        print(json_str)
        console.print("[dim]" + "-" * 60 + "[/dim]")
        console.print(
            f"\n[dim]Exported [bold]{len(export_cookies)}[/bold] essential cookie(s) "
            f"({len(json_str)} chars — safe for Colab Secrets).[/dim]"
        )

    if export_choice in ("2", "3"):
        _export_to_file(export_cookies)

    # ── Step 4: Show Colab instructions ─────────────────────────────────
    if Confirm.ask("\nShow instructions for using these cookies in Google Colab?", default=True):
        _print_colab_instructions(json_str)

    console.print(
        "\n[bold green]Done.[/bold green]  "
        "Remember: re-run this script if TradingView shows a login error in Colab.\n"
    )


if __name__ == "__main__":
    main()
