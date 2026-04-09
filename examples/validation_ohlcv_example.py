"""
OHLCV Data Integrity Validation Example

Comprehensive walkthrough of every tvkit.validation feature:

  1. Clean data  — all checks pass, zero violations
  2. Duplicate timestamps  — ERROR: reconnect-replay scenario
  3. Non-monotonic timestamps  — ERROR: out-of-order bars
  4. OHLC inconsistency  — ERROR: open > high / close < low
  5. Negative volume  — ERROR: corrupt volume field
  6. Gap detection  — WARNING: missing bars (is_valid stays True)
  7. DataExporter logging mode  — validate=True, strict=False
  8. DataExporter strict mode  — validate=True, strict=True (blocks on ERROR)
  9. Selective checks  — run a specific subset

Note on OHLCVBar construction:
  OHLCVBar does NOT enforce OHLC constraints at construction time.
  Structural integrity is the responsibility of tvkit.validation.

Run:
    uv run python examples/validation_ohlcv_example.py
"""

import asyncio
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.export import DataExporter
from tvkit.validation import (
    DataIntegrityError,
    ValidationResult,
    ViolationType,
    validate_ohlcv,
)

console: Console = Console()

_BASE_TS: float = 1_672_531_200.0  # 2023-01-01 00:00:00 UTC
_ONE_DAY: float = 86_400.0
_ONE_HOUR: float = 3_600.0


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _section(number: int, title: str, subtitle: str = "") -> None:
    """Print a rich panel header for each demo section."""
    header: Text = Text()
    header.append(f"Demo {number}  ", style="bold cyan")
    header.append(title, style="bold white")
    if subtitle:
        header.append(f"\n{subtitle}", style="dim")
    console.print(Panel(header, box=box.ROUNDED, border_style="cyan", padding=(0, 2)))


def _print_result(result: ValidationResult, label: str = "") -> None:
    """Render a ValidationResult as a rich table."""
    status_text: Text = (
        Text("✔  VALID", style="bold green")
        if result.is_valid
        else Text("✘  INVALID", style="bold red")
    )

    summary: Table = Table(box=box.SIMPLE_HEAD, show_header=False, padding=(0, 1))
    summary.add_column(style="dim")
    summary.add_column()
    if label:
        summary.add_row("Dataset", label)
    summary.add_row("Status", status_text)
    summary.add_row("Bars checked", str(result.bars_checked))
    summary.add_row("Errors", Text(str(len(result.errors)), style="bold red"))
    summary.add_row("Warnings", Text(str(len(result.warnings)), style="bold yellow"))
    summary.add_row(
        "Checks run",
        ", ".join(c.value for c in result.checks_run),
    )
    console.print(summary)

    if result.violations:
        vtable: Table = Table(
            "Severity",
            "Check",
            "Message",
            "Affected rows",
            box=box.MINIMAL_DOUBLE_HEAD,
            border_style="dim",
            show_lines=False,
        )
        for v in result.violations:
            sev_style: str = "bold red" if v.severity == "ERROR" else "bold yellow"
            vtable.add_row(
                Text(v.severity, style=sev_style),
                v.check.value,
                v.message,
                str(v.affected_rows),
            )
        console.print(vtable)
    console.print()


def _bars_to_df(bars: list[OHLCVBar]) -> pl.DataFrame:
    """Convert a list of OHLCVBars to a Polars DataFrame."""
    return pl.DataFrame(
        {
            "timestamp": [b.timestamp for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }
    )


# ---------------------------------------------------------------------------
# Bar factories
# ---------------------------------------------------------------------------


def _make_clean_bars(n: int = 10) -> list[OHLCVBar]:
    """Valid bars: monotonic timestamps, valid OHLC, positive volume."""
    return [
        OHLCVBar(
            timestamp=_BASE_TS + i * _ONE_DAY,
            open=100.0 + i,
            high=110.0 + i,
            low=90.0 + i,
            close=105.0 + i,
            volume=10_000.0 + i * 100,
        )
        for i in range(n)
    ]


def _make_duplicate_ts_bars() -> list[OHLCVBar]:
    """Bars where bar 4 repeats bar 3's timestamp (WebSocket reconnect replay)."""
    bars: list[OHLCVBar] = _make_clean_bars(8)
    bars[4] = OHLCVBar(
        timestamp=_BASE_TS + 3 * _ONE_DAY,  # duplicate of bar 3
        open=104.0,
        high=114.0,
        low=94.0,
        close=109.0,
        volume=10_400.0,
    )
    return bars


def _make_nonmonotonic_bars() -> list[OHLCVBar]:
    """Bars where bar 5 has a timestamp earlier than bar 4 (out-of-order arrival)."""
    bars: list[OHLCVBar] = _make_clean_bars(8)
    bars[5] = OHLCVBar(
        timestamp=_BASE_TS + 2 * _ONE_DAY,  # older than bar 4
        open=105.0,
        high=115.0,
        low=95.0,
        close=110.0,
        volume=10_500.0,
    )
    return bars


def _make_ohlc_error_bars() -> list[OHLCVBar]:
    """Bars where open > high on two rows — OHLC_INCONSISTENCY ERROR."""
    bars: list[OHLCVBar] = _make_clean_bars(10)
    bars[2] = OHLCVBar(
        timestamp=_BASE_TS + 2 * _ONE_DAY,
        open=130.0,  # exceeds high=112.0
        high=112.0,
        low=92.0,
        close=107.0,
        volume=10_200.0,
    )
    bars[7] = OHLCVBar(
        timestamp=_BASE_TS + 7 * _ONE_DAY,
        open=130.0,  # exceeds high=117.0
        high=117.0,
        low=97.0,
        close=112.0,
        volume=10_700.0,
    )
    return bars


def _make_negative_volume_bars() -> list[OHLCVBar]:
    """Bars where bar 3 has volume = -500 — NEGATIVE_VOLUME ERROR."""
    bars: list[OHLCVBar] = _make_clean_bars(8)
    bars[3] = OHLCVBar(
        timestamp=_BASE_TS + 3 * _ONE_DAY,
        open=103.0,
        high=113.0,
        low=93.0,
        close=108.0,
        volume=-500.0,  # invalid
    )
    return bars


def _make_gapped_bars() -> list[OHLCVBar]:
    """Daily bars with a 3-day gap between bar 2 and bar 3 — GAP_DETECTED WARNING."""
    timestamps: list[float] = [
        _BASE_TS + 0 * _ONE_DAY,
        _BASE_TS + 1 * _ONE_DAY,
        _BASE_TS + 2 * _ONE_DAY,
        _BASE_TS + 5 * _ONE_DAY,  # 3-day jump
        _BASE_TS + 6 * _ONE_DAY,
    ]
    return [
        OHLCVBar(
            timestamp=ts,
            open=100.0 + i,
            high=110.0 + i,
            low=90.0 + i,
            close=105.0 + i,
            volume=10_000.0 + i * 100,
        )
        for i, ts in enumerate(timestamps)
    ]


# ---------------------------------------------------------------------------
# Demo 1 — Clean data
# ---------------------------------------------------------------------------


def demo_clean_data() -> None:
    _section(1, "Clean data", "All checks pass — zero violations expected")
    bars: list[OHLCVBar] = _make_clean_bars(10)
    result: ValidationResult = validate_ohlcv(_bars_to_df(bars), interval="1D")
    _print_result(result, label="10 clean daily bars")
    assert result.is_valid
    assert result.violations == []


# ---------------------------------------------------------------------------
# Demo 2 — Duplicate timestamps
# ---------------------------------------------------------------------------


def demo_duplicate_timestamps() -> None:
    _section(
        2,
        "Duplicate timestamps",
        "Bar 4 repeats bar 3's timestamp (WebSocket reconnect replay scenario)",
    )
    bars: list[OHLCVBar] = _make_duplicate_ts_bars()
    result: ValidationResult = validate_ohlcv(_bars_to_df(bars))
    _print_result(result, label="8 bars — 1 duplicate timestamp injected")
    assert not result.is_valid
    assert any(v.check == ViolationType.DUPLICATE_TIMESTAMP for v in result.errors)


# ---------------------------------------------------------------------------
# Demo 3 — Non-monotonic timestamps
# ---------------------------------------------------------------------------


def demo_nonmonotonic_timestamps() -> None:
    _section(
        3,
        "Non-monotonic timestamps",
        "Bar 5 has an earlier timestamp than bar 4 (late-arriving WebSocket frame)",
    )
    bars: list[OHLCVBar] = _make_nonmonotonic_bars()
    result: ValidationResult = validate_ohlcv(_bars_to_df(bars))
    _print_result(result, label="8 bars — 1 out-of-order timestamp injected")
    assert not result.is_valid
    assert any(v.check == ViolationType.NON_MONOTONIC_TIMESTAMP for v in result.errors)


# ---------------------------------------------------------------------------
# Demo 4 — OHLC inconsistency
# ---------------------------------------------------------------------------


def demo_ohlc_inconsistency() -> None:
    _section(
        4,
        "OHLC inconsistency",
        "Bars 2 and 7 have open > high — violates low ≤ open/close ≤ high",
    )
    bars: list[OHLCVBar] = _make_ohlc_error_bars()
    result: ValidationResult = validate_ohlcv(_bars_to_df(bars))
    _print_result(result, label="10 bars — open > high on rows 2 and 7")
    assert not result.is_valid
    error_rows: set[int] = {row for v in result.errors for row in v.affected_rows}
    assert 2 in error_rows
    assert 7 in error_rows


# ---------------------------------------------------------------------------
# Demo 5 — Negative volume
# ---------------------------------------------------------------------------


def demo_negative_volume() -> None:
    _section(5, "Negative volume", "Bar 3 has volume = -500 — corrupt data from API")
    bars: list[OHLCVBar] = _make_negative_volume_bars()
    result: ValidationResult = validate_ohlcv(_bars_to_df(bars))
    _print_result(result, label="8 bars — negative volume on row 3")
    assert not result.is_valid
    assert any(v.check == ViolationType.NEGATIVE_VOLUME for v in result.errors)


# ---------------------------------------------------------------------------
# Demo 6 — Gap detection
# ---------------------------------------------------------------------------


def demo_gap_detection() -> None:
    _section(
        6,
        "Gap detection  (WARNING — is_valid stays True)",
        "3-day jump between bar 2→3; interval='1D' enables cadence check",
    )
    bars: list[OHLCVBar] = _make_gapped_bars()
    result: ValidationResult = validate_ohlcv(_bars_to_df(bars), interval="1D")
    _print_result(result, label="5 daily bars — 3-day gap injected")
    assert result.is_valid  # WARNING does not affect is_valid
    assert any(v.check == ViolationType.GAP_DETECTED for v in result.warnings)

    console.print(
        "[dim]Note: daily equity data will also trigger GAP_DETECTED on weekends/holidays "
        "— this is intentional (Phase 1 is cadence-only, not calendar-aware).[/dim]\n"
    )


# ---------------------------------------------------------------------------
# Demo 7 — DataExporter logging mode (strict=False)
# ---------------------------------------------------------------------------


async def demo_export_logging_mode() -> None:
    _section(
        7,
        "DataExporter — logging mode  (validate=True, strict=False)",
        "Violations are logged at WARNING; export always proceeds",
    )
    bars: list[OHLCVBar] = _make_ohlc_error_bars()
    exporter: DataExporter = DataExporter()

    with tempfile.TemporaryDirectory() as tmpdir:
        out: Path = await exporter.to_csv(
            bars,
            Path(tmpdir) / "ohlc_errors.csv",
            validate=True,
            strict=False,
        )
        assert out.exists()
        console.print(
            f"  [green]✔[/green]  File written despite ERROR violations: [bold]{out.name}[/bold]"
        )
        console.print("  [dim]Violations were logged at WARNING level above.[/dim]\n")


# ---------------------------------------------------------------------------
# Demo 8 — DataExporter strict mode (strict=True)
# ---------------------------------------------------------------------------


async def demo_export_strict_mode() -> None:
    _section(
        8,
        "DataExporter — strict mode  (validate=True, strict=True)",
        "DataIntegrityError raised on ERROR violations; file is NOT written",
    )
    bars: list[OHLCVBar] = _make_ohlc_error_bars()
    exporter: DataExporter = DataExporter()

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path: Path = Path(tmpdir) / "should_not_exist.csv"
        try:
            await exporter.to_csv(bars, out_path, validate=True, strict=True)
            raise AssertionError("Expected DataIntegrityError")
        except DataIntegrityError as exc:
            r: ValidationResult = exc.result
            blocked_table: Table = Table(
                "Field", "Value", box=box.SIMPLE_HEAD, show_header=False, padding=(0, 1)
            )
            blocked_table.add_row("Export blocked", Text("Yes", style="bold red"))
            blocked_table.add_row("Errors found", str(len(r.errors)))
            blocked_table.add_row("Bars checked", str(r.bars_checked))
            console.print(blocked_table)

            vtable: Table = Table("Check", "Message", "Rows", box=box.MINIMAL, border_style="red")
            for v in r.errors:
                vtable.add_row(v.check.value, v.message, str(v.affected_rows))
            console.print(vtable)

            assert not out_path.exists()
            console.print(
                "\n  [green]✔[/green]  Confirmed: output file was [bold]NOT[/bold] written.\n"
            )


# ---------------------------------------------------------------------------
# Demo 9 — Selective checks
# ---------------------------------------------------------------------------


def demo_selective_checks() -> None:
    _section(
        9,
        "Selective checks",
        "Run only DUPLICATE_TIMESTAMP + OHLC_INCONSISTENCY + NEGATIVE_VOLUME",
    )
    bars: list[OHLCVBar] = _make_ohlc_error_bars()
    result: ValidationResult = validate_ohlcv(
        _bars_to_df(bars),
        checks=[
            ViolationType.DUPLICATE_TIMESTAMP,
            ViolationType.OHLC_INCONSISTENCY,
            ViolationType.NEGATIVE_VOLUME,
        ],
    )
    _print_result(result, label="10 bars — subset of checks only")

    # model_dump() does NOT include .errors / .warnings (@property — not serialised)
    dump: dict[str, object] = result.model_dump()
    skipped_table: Table = Table(
        "Key", "Included in model_dump()", box=box.SIMPLE_HEAD, show_header=False, padding=(0, 1)
    )
    for key in ("violations", "bars_checked", "checks_run"):
        skipped_table.add_row(key, Text("✔", style="green"))
    for key in ("errors", "warnings"):
        present: bool = key in dump
        skipped_table.add_row(
            key,
            Text(
                "✔" if present else "✘  (computed @property — not serialised)",
                style="green" if present else "dim",
            ),
        )
    console.print(skipped_table)
    assert "errors" not in dump
    assert "warnings" not in dump
    console.print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    started_at: datetime = datetime.now(tz=UTC)

    console.print(
        Panel(
            Text.assemble(
                ("tvkit.validation", "bold magenta"),
                (" — OHLCV Data Integrity Validation\n", "bold white"),
                ("Covers all 5 checks · DataExporter integration · selective checks", "dim"),
            ),
            box=box.DOUBLE_EDGE,
            border_style="magenta",
            padding=(1, 4),
        )
    )

    demo_clean_data()
    demo_duplicate_timestamps()
    demo_nonmonotonic_timestamps()
    demo_ohlc_inconsistency()
    demo_negative_volume()
    demo_gap_detection()
    await demo_export_logging_mode()
    await demo_export_strict_mode()
    demo_selective_checks()

    elapsed: float = (datetime.now(tz=UTC) - started_at).total_seconds()
    console.print(
        Panel(
            Text.assemble(
                ("✔  All 9 demos completed", "bold green"),
                (f"  ·  {elapsed:.2f}s", "dim"),
            ),
            box=box.ROUNDED,
            border_style="green",
            padding=(0, 2),
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
