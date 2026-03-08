#!/usr/bin/env bash
# check-docs.sh — Check all markdown files in docs/ for broken internal links.
#
# Usage:
#   ./scripts/check-docs.sh
#
# Exits 0 if no broken links are found, 1 otherwise.
#
# Tool priority:
#   1. lychee              (install: https://github.com/lycheeverse/lychee)
#   2. markdown-link-check (install: npm install -g markdown-link-check)
#   3. Python fallback     (always available via uv run python)
#
# Only internal (relative) links are checked. HTTP links, anchor-only links
# (#section), and mailto: links are skipped.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCS_DIR="$REPO_ROOT/docs"

echo "tvkit docs link checker"
echo "Checking: $DOCS_DIR"
echo ""

if [[ ! -d "$DOCS_DIR" ]]; then
    echo "Error: docs directory not found: $DOCS_DIR" >&2
    exit 1
fi

# ── Tool: lychee ──────────────────────────────────────────────────────────────
if command -v lychee &>/dev/null; then
    echo "Using: lychee"
    lychee \
        --offline \
        --no-progress \
        "$DOCS_DIR"
    exit $?
fi

# ── Tool: markdown-link-check ─────────────────────────────────────────────────
if command -v markdown-link-check &>/dev/null; then
    echo "Using: markdown-link-check"

    # Temporary config that skips HTTP links
    TMP_CONFIG="$(mktemp /tmp/mlc-config.XXXXXX.json)"
    trap 'rm -f "$TMP_CONFIG"' EXIT
    cat > "$TMP_CONFIG" <<'JSON'
{
  "ignorePatterns": [
    { "pattern": "^https?://" },
    { "pattern": "^mailto:" }
  ],
  "retryOn429": false,
  "timeout": "5s"
}
JSON

    FAILED=0
    while IFS= read -r -d '' md_file; do
        markdown-link-check \
            --config "$TMP_CONFIG" \
            --quiet \
            "$md_file" || FAILED=1
    done < <(find "$DOCS_DIR" -name '*.md' -print0)

    exit $FAILED
fi

# ── Fallback: pure Python ─────────────────────────────────────────────────────
echo "Using: Python fallback (install lychee or markdown-link-check for faster checks)"
echo ""

uv run python - "$DOCS_DIR" <<'PYEOF'
"""
Pure-Python internal link checker — v2.

Features:
- Code-block-aware parsing: links inside fenced code blocks are ignored
- Anchor validation: page.md#section checks that ## Section heading exists
- Parallel scanning via ThreadPoolExecutor for speed on large doc sets
- Anchor caching: each target file's headings are parsed at most once

Intentionally simple inline link parser:
- Parses only inline Markdown links: [text](path) or [text](path "title")
- Reference-style links ([text][ref]) are NOT parsed — all tvkit docs use inline syntax
- Directory links (path/to/dir/) are skipped
- HTTP links, anchor-only links, and mailto: links are skipped
"""
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Matches inline links: [text](path) or [text](path "title")
# Intentionally does not match reference-style links.
LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
HEADING_RE = re.compile(r'^#{1,6}\s+(.*)')
CODE_FENCE_RE = re.compile(r'^\s*```')


def slugify(text: str) -> str:
    """Convert a Markdown heading to a GitHub-style anchor slug."""
    slug = text.strip().lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    return slug


def extract_headings(md_file: Path) -> frozenset[str]:
    """Return all anchor slugs defined by headings in a markdown file."""
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
                anchors.append(slugify(m.group(1)))
    return frozenset(anchors)


def parse_links(md_file: Path) -> list[tuple[int, str, str, str | None]]:
    """Extract (lineno, raw_link, path, anchor_or_None) from a markdown file.

    Skips links inside fenced code blocks.
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
                if not link:
                    continue

                # Skip directory links
                if link.endswith("/"):
                    continue

                results.append((lineno, raw_link.strip(), link, anchor))
    return results


def check_file(
    md_file: Path,
    docs_root: Path,
    anchors_cache: dict[Path, frozenset[str]],
    cache_lock: threading.Lock,
) -> list[tuple[Path, int, str]]:
    """Check a single markdown file for broken links. Returns list of failures."""
    broken: list[tuple[Path, int, str]] = []

    for lineno, raw_link, link, anchor in parse_links(md_file):
        target = md_file.parent.joinpath(link)

        if not target.exists():
            broken.append((md_file, lineno, raw_link))
            continue

        if anchor is not None:
            with cache_lock:
                cached = anchors_cache.get(target)
            if cached is None:
                cached = extract_headings(target)
                with cache_lock:
                    anchors_cache[target] = cached
            if slugify(anchor) not in cached:
                broken.append((md_file, lineno, raw_link))

    return broken


def check_docs(docs_dir: Path) -> int:
    """Check all .md files under docs_dir for broken internal links.

    Returns the number of broken links found.
    """
    md_files = sorted(docs_dir.rglob("*.md"))
    anchors_cache: dict[Path, frozenset[str]] = {}
    cache_lock = threading.Lock()
    all_broken: list[tuple[Path, int, str]] = []

    with ThreadPoolExecutor() as pool:
        futures = {
            pool.submit(check_file, f, docs_dir, anchors_cache, cache_lock): f
            for f in md_files
        }
        for future in as_completed(futures):
            all_broken.extend(future.result())

    # Sort for deterministic output
    all_broken.sort(key=lambda x: (str(x[0]), x[1]))

    if all_broken:
        print(f"Found {len(all_broken)} broken link(s):\n")
        for file_path, lineno, link in all_broken:
            rel = file_path.relative_to(docs_dir.parent)
            print(f"  {rel}:{lineno}  ->  {link}")
        print()
        return len(all_broken)

    print(f"All links OK  ({len(md_files)} files checked)")
    return 0


if __name__ == "__main__":
    docs_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs")
    if not docs_path.is_dir():
        print(f"Error: directory not found: {docs_path}", file=sys.stderr)
        sys.exit(1)
    broken_count = check_docs(docs_path)
    sys.exit(1 if broken_count > 0 else 0)
PYEOF
