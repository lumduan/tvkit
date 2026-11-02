"""
Guard against Markdown that renders at the wrong size on GitHub and PyPI.

This exists because of a real defect. The docs style guide told writers to annotate
output with a comment line such as ``# 250 rows total, showing 5``. That is correct
inside a fenced ``text`` block. Under a Markdown table, or after the closing fence of an
output block, the same line is an ATX level-1 heading, so every such note rendered in the
page's largest type. It had spread to 42 note runs across 21 files, including the
README that PyPI shows on the project page.

The check is structural: a page has at most one level-1 heading (its title). Every other
``# `` line outside a fence is almost certainly a stray note. Notes outside a fence
belong in a ``-`` bullet list (``docs/reference/_style.md``, Style Rule 11).
"""

from __future__ import annotations

import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

PAGES: list[pathlib.Path] = sorted(
    [REPO_ROOT / "README.md", *(REPO_ROOT / "docs").rglob("*.md")],
)

# An ATX level-1 heading: up to three spaces of indent, one '#', then a space or end of line.
_ATX_H1 = re.compile(r"^ {0,3}#(?:[ \t]|$)")
# A setext level-1 underline: up to three spaces of indent, then only '=' characters.
_SETEXT_H1 = re.compile(r"^ {0,3}=+[ \t]*$")
# An opening or closing code fence: three or more backticks or tildes.
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def _level_one_headings(text: str) -> list[tuple[int, str]]:
    """Return ``(line_number, line)`` for every level-1 heading outside a code fence."""
    found: list[tuple[int, str]] = []
    fence: str | None = None
    previous = ""
    for number, line in enumerate(text.splitlines(), start=1):
        match = _FENCE.match(line)
        if fence is None and match:
            fence = match.group(1)
        elif fence is not None:
            # A fence closes on a run of the same character at least as long as the opener.
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                fence = None
        elif _ATX_H1.match(line):
            found.append((number, line))
        elif _SETEXT_H1.match(line) and previous.strip() and not previous.lstrip().startswith("|"):
            found.append((number - 1, previous))
        previous = line if fence is None else ""
    return found


def test_pages_are_found() -> None:
    """The glob must see the README and the docs tree, or the check below is vacuous."""
    names = {p.relative_to(REPO_ROOT).as_posix() for p in PAGES}
    assert "README.md" in names
    assert "docs/index.md" in names
    assert len(PAGES) > 30


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_at_most_one_level_one_heading(page: pathlib.Path) -> None:
    headings = _level_one_headings(page.read_text(encoding="utf-8"))
    extra = headings[1:]
    assert not extra, (
        f"{page.relative_to(REPO_ROOT)} has {len(headings)} level-1 headings; only the title "
        "may be one. A note line starting with '# ' outside a code fence renders as a "
        "giant heading — write it as a '- ' bullet instead (docs/reference/_style.md, Rule 11).\n"
        + "\n".join(f"  line {n}: {line}" for n, line in extra)
    )


def test_detector_catches_a_stray_note_after_a_table() -> None:
    """The detector itself must flag the exact shape that shipped, and ignore fenced comments."""
    page = (
        "# Title\n\n"
        "```python\n# a comment inside a fence is fine\n```\n\n"
        "| a | b |\n|---|---|\n| 1 | 2 |\n\n"
        "# 10 rows total, showing 5\n"
    )
    assert _level_one_headings(page) == [(1, "# Title"), (11, "# 10 rows total, showing 5")]
