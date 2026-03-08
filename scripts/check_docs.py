#!/usr/bin/env python3
"""
check_docs.py — Python port of scripts/check-docs.sh

Checks all markdown files in docs/ for broken internal links.
Uses lychee or markdown-link-check if available; falls back to a built-in
Python checker that requires no extra dependencies.

Usage:
    uv run python scripts/check_docs.py                  # auto-detect tool
    uv run python scripts/check_docs.py --tool python    # force built-in checker
    uv run python scripts/check_docs.py --tool lychee    # force lychee
    uv run python scripts/check_docs.py --tool mlc       # force markdown-link-check
    ./scripts/check_docs.py                              # direct execution (needs chmod +x)

Exit codes:
    0 — no broken links found
    1 — one or more broken links, or requested tool not available
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT: Path = Path(__file__).resolve().parents[1]
DOCS_DIR: Path = REPO_ROOT / "docs"

# ── Tool detection ────────────────────────────────────────────────────────────


def has_cmd(cmd: str) -> bool:
    """Return True if cmd is available on PATH."""
    return shutil.which(cmd) is not None


def _run(cmd: list[str]) -> int:
    """Run a command, stream output to the terminal, and return its exit code."""
    print("+", " ".join(cmd))
    return subprocess.run(cmd).returncode


# ── External tool runners ─────────────────────────────────────────────────────


def run_lychee(docs_dir: Path) -> int:
    """Run lychee in offline mode against the docs directory."""
    rc = _run(["lychee", "--offline", "--no-progress", str(docs_dir)])
    print(f"\nChecked: {docs_dir}")
    return rc


def run_mlc(docs_dir: Path) -> int:
    """Run markdown-link-check against every .md file under docs_dir."""
    mlc_config = {
        "ignorePatterns": [
            {"pattern": "^https?://"},
            {"pattern": "^mailto:"},
        ],
        "retryOn429": False,
        "timeout": "5s",
    }

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        prefix="mlc-config-",
        delete=False,
    ) as tmp:
        json.dump(mlc_config, tmp)
        config_path = tmp.name

    md_files = sorted(docs_dir.rglob("*.md"))
    failed = False
    try:
        for md_file in md_files:
            rc = subprocess.run(
                ["markdown-link-check", "--config", config_path, "--quiet", str(md_file)]
            ).returncode
            if rc != 0:
                failed = True
    finally:
        Path(config_path).unlink(missing_ok=True)

    print(f"\nChecked {len(md_files)} markdown file(s) in {docs_dir}")
    return 1 if failed else 0


# ── Built-in Python link checker ──────────────────────────────────────────────
#
# Features:
# - Code-block-aware: links inside fenced code blocks are ignored
# - Anchor validation: page.md#section checks that ## Section heading exists
# - Parallel scanning via ThreadPoolExecutor (max_workers=8, IO-bound)
# - Anchor caching: each target file's headings are parsed at most once
#
# Limitation:
# - Parses only inline links [text](path) — reference-style links ([text][ref])
#   are not supported. All tvkit docs use inline link syntax.

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)")
CODE_FENCE_RE = re.compile(r"^\s*```")


def _slugify(text: str) -> str:
    """Convert a Markdown heading to a GitHub-style anchor slug."""
    slug = text.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    return slug


def _extract_headings(md_file: Path) -> frozenset[str]:
    """Return the set of anchor slugs defined by headings in md_file."""
    anchors: list[str] = []
    in_code = False
    with md_file.open(encoding="utf-8") as fh:
        for line in fh:
            if CODE_FENCE_RE.match(line):
                in_code = not in_code
                continue
            if in_code:
                continue
            m = HEADING_RE.match(line)
            if m:
                anchors.append(_slugify(m.group(1)))
    return frozenset(anchors)


def _parse_links(md_file: Path) -> list[tuple[int, str, str, str | None]]:
    """Extract (lineno, raw_link, path, anchor_or_None) from md_file.

    Links inside fenced code blocks are skipped.
    Only inline links [text](path) are parsed; reference-style links are not.
    """
    results: list[tuple[int, str, str, str | None]] = []
    in_code = False
    with md_file.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if CODE_FENCE_RE.match(line):
                in_code = not in_code
                continue
            if in_code:
                continue
            for _text, raw_link in LINK_RE.findall(line):
                link = raw_link.strip()

                # Strip inline title: path "title" -> path
                if '"' in link:
                    link = link.split('"')[0].strip()

                # Skip empty, HTTP, anchor-only, and mailto links
                if not link:
                    continue
                if link.startswith(("http://", "https://", "mailto:", "#")):
                    continue

                # Split anchor fragment
                anchor: str | None = None
                if "#" in link:
                    link, anchor = link.split("#", 1)
                if not link or link.endswith("/"):
                    continue

                results.append((lineno, raw_link.strip(), link, anchor))
    return results


def _check_file(
    md_file: Path,
    anchors_cache: dict[Path, frozenset[str]],
    cache_lock: threading.Lock,
) -> list[tuple[Path, int, str]]:
    """Check a single markdown file. Returns list of (file, lineno, raw_link) failures."""
    broken: list[tuple[Path, int, str]] = []

    for lineno, raw_link, link, anchor in _parse_links(md_file):
        target = md_file.parent.joinpath(link)

        if not target.exists():
            broken.append((md_file, lineno, raw_link))
            continue

        if anchor is not None:
            with cache_lock:
                cached = anchors_cache.get(target)
            if cached is None:
                cached = _extract_headings(target)
                with cache_lock:
                    anchors_cache[target] = cached
            if _slugify(anchor) not in cached:
                broken.append((md_file, lineno, raw_link))

    return broken


def run_python_checker(docs_dir: Path) -> int:
    """Run the built-in Python link checker. Returns 0 if all OK, 1 on any broken link."""
    md_files = sorted(docs_dir.rglob("*.md"))
    if not md_files:
        print(f"No markdown files found under {docs_dir}")
        return 0

    anchors_cache: dict[Path, frozenset[str]] = {}
    cache_lock = threading.Lock()
    all_broken: list[tuple[Path, int, str]] = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_check_file, f, anchors_cache, cache_lock): f for f in md_files}
        for future in as_completed(futures):
            all_broken.extend(future.result())

    all_broken.sort(key=lambda x: (str(x[0]), x[1]))

    if all_broken:
        print(f"Found {len(all_broken)} broken link(s):\n")
        for file_path, lineno, link in all_broken:
            rel = file_path.relative_to(docs_dir.parent)
            print(f"  {rel}:{lineno}  ->  {link}")
        print()
        print(f"Checked {len(md_files)} markdown file(s) in {docs_dir}")
        return 1

    print(f"All links OK  ({len(md_files)} files checked in {docs_dir})")
    return 0


# ── Argument parsing ──────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check docs/ markdown files for broken internal links.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
tool detection order (when --tool is not specified):
  1. lychee              fastest; install from https://github.com/lycheeverse/lychee
  2. markdown-link-check Node.js;  npm install -g markdown-link-check
  3. python              always available; no extra dependencies
        """,
    )
    parser.add_argument(
        "--tool",
        choices=["lychee", "mlc", "python"],
        default=None,
        help=(
            "Force a specific tool. "
            "'lychee' = lychee binary, "
            "'mlc' = markdown-link-check, "
            "'python' = built-in checker (default: auto-detect)."
        ),
    )
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    args = parse_args()

    print("tvkit docs link checker")
    print(f"Checking: {DOCS_DIR}")
    print()

    if not DOCS_DIR.is_dir():
        print(f"Error: docs directory not found: {DOCS_DIR}", file=sys.stderr)
        return 1

    # Force a specific tool if requested
    if args.tool == "lychee":
        if not has_cmd("lychee"):
            print("Error: lychee not found on PATH", file=sys.stderr)
            return 1
        print("Using: lychee")
        return run_lychee(DOCS_DIR)

    if args.tool == "mlc":
        if not has_cmd("markdown-link-check"):
            print("Error: markdown-link-check not found on PATH", file=sys.stderr)
            return 1
        print("Using: markdown-link-check")
        return run_mlc(DOCS_DIR)

    if args.tool == "python":
        print("Using: Python built-in checker")
        return run_python_checker(DOCS_DIR)

    # Auto-detect
    if has_cmd("lychee"):
        print("Using: lychee")
        return run_lychee(DOCS_DIR)

    if has_cmd("markdown-link-check"):
        print("Using: markdown-link-check")
        return run_mlc(DOCS_DIR)

    print("Using: Python built-in checker (install lychee or markdown-link-check for speed)")
    print()
    return run_python_checker(DOCS_DIR)


if __name__ == "__main__":
    sys.exit(main())
