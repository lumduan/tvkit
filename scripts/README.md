# scripts/

This directory contains development and maintenance scripts for the tvkit project.

## Maintenance Scripts

| Script | Purpose | Command |
| --- | --- | --- |
| [`check-docs.sh`](check-docs.sh) | Check all `docs/` markdown files for broken internal links | `./scripts/check-docs.sh` |
| [`check_docs.py`](check_docs.py) | Python version of the link checker (supports `--tool` flag) | `uv run python scripts/check_docs.py` |
| [`validate_examples.py`](validate_examples.py) | Syntax-check and optionally run all `examples/` scripts | `uv run python scripts/validate_examples.py --dry-run` |

### `check-docs.sh`

Checks every internal link in every markdown file under `docs/` and reports broken links with
file name and line number. Exits non-zero on any broken link.

**When to run:** After renaming or moving any docs file, or before a release.

**Tool detection order:**

1. `lychee` — fastest; install from <https://github.com/lycheeverse/lychee>
2. `markdown-link-check` — Node.js; `npm install -g markdown-link-check`
3. Python built-in — always available; no extra dependencies

```bash
./scripts/check-docs.sh
```

### `check_docs.py`

Python port of `check-docs.sh`. Identical tool detection order, but written in pure Python with
an additional `--tool` flag to force a specific checker. Use this script when you prefer Python
tooling or need to control which tool is used in CI.

**Built-in Python checker features:**

- Code-block-aware: links inside fenced code blocks are ignored
- Anchor validation: `page.md#section` checks that `## Section` heading exists
- Parallel scanning via `ThreadPoolExecutor` for speed on large doc sets

```bash
uv run python scripts/check_docs.py              # auto-detect tool
uv run python scripts/check_docs.py --tool python # force built-in checker
uv run python scripts/check_docs.py --help        # show all options
```

### `validate_examples.py`

Syntax-checks every `.py` file in `examples/`. Examples that require a live TradingView
connection are tagged `[INTEGRATION]` and skipped unless running in full mode.

**When to run:** Before committing any change to `examples/`, or as part of documentation QA.

```bash
# Syntax check only — safe without network access
uv run python scripts/validate_examples.py --dry-run

# Full output (print stdout/stderr per example)
uv run python scripts/validate_examples.py --dry-run --verbose

# Help
uv run python scripts/validate_examples.py --help
```

---

## Publishing

| Script | Purpose | Command |
| --- | --- | --- |
| [`publish.sh`](publish.sh) | Build and publish tvkit to PyPI | `./scripts/publish.sh` |

### `publish.sh`

Builds the distribution package and uploads it to PyPI using `twine`. Requires PyPI credentials
configured in `~/.pypirc` or via environment variables. See
[`docs/development/release-process.md`](../docs/development/release-process.md) for the full
release workflow.

---

## Diagnostics

| Script | Purpose | Command |
| --- | --- | --- |
| [`quick_network_test.py`](quick_network_test.py) | Verify TradingView WebSocket connectivity | `uv run python scripts/quick_network_test.py` |

### `quick_network_test.py`

Performs a minimal WebSocket connection to TradingView to confirm network connectivity and
API availability. Useful for diagnosing connection issues in development or CI environments.
