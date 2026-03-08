#!/usr/bin/env python3
"""
validate-examples.py — Syntax-check and optionally run all example scripts.

Usage:
    uv run python scripts/validate-examples.py              # syntax check + skip [INTEGRATION]
    uv run python scripts/validate-examples.py --dry-run    # syntax check only
    uv run python scripts/validate-examples.py --verbose    # print subprocess output per example

Flags:
    --dry-run      Syntax-check every example; skip execution of integration examples.
                   Safe to run without a network connection or TradingView API access.
    --verbose      Print stdout/stderr captured from each subprocess.
    --timeout N    Per-example timeout in seconds for run mode (default: 30).

Integration examples:
    Examples tagged with a `# [INTEGRATION]` comment in their first 30 lines are
    integration tests. If no tag is present, examples that import `websockets`,
    `httpx`, or `ScannerService` are auto-detected as integration tests.
    Integration examples are always skipped (not executed) — remove the early-return
    block in run_all() if you want to run them in a credentialled CI environment.

Exit codes:
    0 — all checks passed (failures = 0)
    1 — one or more checks failed
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

SCRIPTS_DIR: Path = Path(__file__).parent.resolve()
REPO_ROOT: Path = SCRIPTS_DIR.parent
EXAMPLES_DIR: Path = REPO_ROOT / "examples"

# Keywords that indicate a live-network dependency.
# `OHLCV` is excluded — a future offline OHLCV example is plausible.
INTEGRATION_KEYWORDS: tuple[str, ...] = ("websockets", "httpx", "ScannerService")

# ANSI colour codes — disabled when stdout is not a TTY
_USE_COLOR: bool = sys.stdout.isatty()


def _color(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


PASS_LABEL = _color("32", "[PASS]")
SKIP_LABEL = _color("33", "[SKIP]")
FAIL_LABEL = _color("31", "[FAIL]")

# ── Helpers ───────────────────────────────────────────────────────────────────


def is_integration(path: Path) -> bool:
    """Return True if the example requires live network access.

    Reads the file exactly once:
    1. Checks the first 30 lines for an explicit `# [INTEGRATION]` comment.
    2. Scans all import lines for INTEGRATION_KEYWORDS as a heuristic fallback.
    """
    explicit_tag_found = False
    all_lines: list[str] = []

    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            all_lines.append(line)
            # Explicit tag search (first 30 lines)
            if i < 30 and "# [INTEGRATION]" in line:
                explicit_tag_found = True

    if explicit_tag_found:
        return True

    # Heuristic: scan all import lines for network-dependent keywords
    for line in all_lines:
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            if any(kw in stripped for kw in INTEGRATION_KEYWORDS):
                return True

    return False


def run_subprocess(
    cmd: list[str],
    *,
    timeout: int,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"Timed out after {timeout}s"
    except Exception as exc:
        return 1, "", str(exc)


def syntax_check(path: Path, *, timeout: int, verbose: bool) -> tuple[bool, str]:
    """Syntax-check a Python file using py_compile. Returns (ok, error_message)."""
    code, stdout, stderr = run_subprocess(
        [sys.executable, "-m", "py_compile", str(path)],
        timeout=timeout,
    )
    if verbose and (stdout.strip() or stderr.strip()):
        _print_output(stdout, stderr)
    if code != 0:
        return False, stderr.strip() or stdout.strip() or "py_compile failed"
    return True, ""


def run_example(
    path: Path,
    *,
    timeout: int,
    verbose: bool,
) -> tuple[bool, str]:
    """Run an example in an isolated subprocess with PYTHONPATH set to the repo root."""
    env: dict[str, str] = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    code, stdout, stderr = run_subprocess(
        [sys.executable, str(path)],
        timeout=timeout,
        env=env,
    )
    if verbose:
        _print_output(stdout, stderr)
    if code != 0:
        return False, stderr.strip() or stdout.strip() or f"exited with code {code}"
    return True, ""


def _print_output(stdout: str, stderr: str) -> None:
    if stdout.strip():
        print(f"    stdout:\n{_indent(stdout)}")
    if stderr.strip():
        print(f"    stderr:\n{_indent(stderr)}")


def _indent(text: str, prefix: str = "      ") -> str:
    return "\n".join(prefix + line for line in text.rstrip().splitlines())


# ── Main ──────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Syntax-check and optionally run all tvkit example scripts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Syntax-check only; skip execution of all integration examples.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print stdout/stderr from each subprocess.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        metavar="N",
        help="Per-example timeout in seconds for run mode (default: 30).",
    )
    return parser.parse_args()


def run_all(args: argparse.Namespace) -> int:
    if not EXAMPLES_DIR.is_dir():
        print(f"Error: examples directory not found: {EXAMPLES_DIR}", file=sys.stderr)
        return 1

    # rglob captures examples in subdirectories as well
    examples: list[Path] = sorted(EXAMPLES_DIR.rglob("*.py"))
    if not examples:
        print("No .py files found in examples/")
        return 0

    mode_label = "dry-run (syntax only)" if args.dry_run else f"full run (timeout={args.timeout}s)"
    print(f"tvkit example validator  [{mode_label}]")
    print(f"Examples: {EXAMPLES_DIR}")
    print()

    passed = skipped = failed = 0

    for path in examples:
        rel = path.relative_to(REPO_ROOT)
        integration = is_integration(path)

        # ── Syntax check ──────────────────────────────────────────────────────
        ok, err = syntax_check(path, timeout=args.timeout, verbose=args.verbose)
        if not ok:
            print(f"{FAIL_LABEL}  {rel}  — SyntaxError: {err}")
            failed += 1
            continue

        # ── Skip integration examples ─────────────────────────────────────────
        # Integration examples require live TradingView API access.
        # Remove this block and add --run-integration logic if you need to
        # run them in a credentialled CI environment.
        if integration:
            print(f"{SKIP_LABEL}  {rel}  [INTEGRATION]")
            skipped += 1
            continue

        # ── Skip non-integration execution in dry-run mode ────────────────────
        if args.dry_run:
            print(f"{PASS_LABEL}  {rel}  (syntax OK)")
            passed += 1
            continue

        # ── Run example ───────────────────────────────────────────────────────
        ok, err = run_example(path, timeout=args.timeout, verbose=args.verbose)
        if ok:
            print(f"{PASS_LABEL}  {rel}")
            passed += 1
        else:
            print(f"{FAIL_LABEL}  {rel}  — {err}")
            failed += 1

    print()
    parts: list[str] = []
    if passed:
        parts.append(f"{passed} passed")
    if skipped:
        parts.append(f"{skipped} skipped")
    if failed:
        parts.append(_color("31", f"{failed} failed"))
    print("  ".join(parts) if parts else "No examples checked")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run_all(parse_args()))
