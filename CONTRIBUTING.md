# Contributing to tvkit

Thank you for your interest in contributing. This document explains how to set up a development environment, the standards your changes must meet, and how to submit a pull request.

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

### Setup

```bash
git clone https://github.com/lumduan/tvkit.git
cd tvkit
uv sync
```

This installs all runtime and development dependencies into a managed virtual environment.

## Development Workflow

### Before You Start

Check the [Roadmap](docs/roadmap.md) and open issues to see what is planned or in progress. Open a GitHub issue to discuss your proposed change before writing code — this avoids duplicated effort and ensures the direction fits the project.

### Making Changes

1. Fork the repository and create a branch from `main`
2. Write your changes following the standards below
3. Add or update tests in `tests/`
4. Run the full quality gate (see below)
5. Submit a pull request against `main`

### Quality Gate

All of the following must pass before a PR can be merged:

```bash
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy tvkit/           # type checking
uv run python -m pytest tests/ --cov=tvkit --cov-fail-under=90 -v
```

PRs that fail any check will not be reviewed until they pass.

## Code Standards

### Type Safety

- All functions and methods must have complete type annotations
- All variable declarations that could be ambiguous must have explicit annotations
- No `Any` types without a documented justification
- Code must pass `mypy` in strict mode

### Async Patterns

- All I/O operations must use `async/await`
- Use `httpx` for HTTP (not `requests`)
- Use `websockets` for WebSocket (not `websocket-client`)
- Use context managers for resource management

### Pydantic Models

- All data structures must be Pydantic `BaseModel` subclasses
- Every field must have a description and appropriate constraints

### Prohibited

- `requests` or `websocket-client` (use async equivalents)
- Bare `except:` clauses (always catch specific exceptions)
- Hardcoded credentials or API keys
- Debug `print` statements in library code
- Breaking changes to public APIs without a deprecation path

### Import Order

```python
# 1. Standard library
import asyncio
from typing import Any

# 2. Third-party
import httpx
from pydantic import BaseModel

# 3. Local
from tvkit.api.chart.models import OHLCVBar
```

## Testing

- Add tests for every new public function or model
- Tests must not make live network requests — mock all I/O
- Minimum 90% coverage required
- See [Testing Strategy](docs/development/testing-strategy.md) for patterns and examples

## Documentation

- Update docstrings for any changed public functions
- If adding a new feature, add or update the relevant file in `docs/`
- Example scripts belong in `examples/` and must be fully runnable

## Commit Messages

tvkit uses conventional commit format:

```
type(scope): short description

Longer explanation if needed.
```

Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

Example: `feat(scanner): add pagination support for large result sets`

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Include a clear description of what changed and why
- Reference any related issues with `Closes #N`
- Ensure the branch is up to date with `main` before requesting review

## Questions

Open a [GitHub Discussion](https://github.com/lumduan/tvkit/discussions) for questions, or file an [issue](https://github.com/lumduan/tvkit/issues) for bugs and feature requests.
