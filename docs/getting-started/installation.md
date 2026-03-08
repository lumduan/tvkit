# Installation

tvkit requires **Python 3.11 or later** and can be installed using a Python package manager such as **uv** (recommended) or **pip**.

## Runtime Requirements

tvkit depends on several core libraries that are installed automatically:

- **pydantic** — data validation
- **websockets** — async WebSocket client
- **httpx** — async HTTP client
- **polars** — high-performance DataFrame processing

---

## Using uv (Recommended)

[uv](https://docs.astral.sh/uv/) is a fast Python package manager. It is the preferred method for tvkit projects.

Install uv if needed:

```bash
pip install uv
```

Then add tvkit to your project:

```bash
uv add tvkit
```

To start a new project from scratch:

```bash
uv init my-trading-project
cd my-trading-project
uv add tvkit
```

---

## Using pip

```bash
pip install --upgrade tvkit
```

With development tools (testing, linting, type checking):

```bash
pip install --upgrade 'tvkit[dev]'
```

---

## Installing from Source

Requires **git** to be installed.

```bash
git clone https://github.com/lumduan/tvkit.git
cd tvkit
pip install -e .
```

For development with all tools:

```bash
pip install -e '.[dev]'
```

This installs testing (pytest), linting (ruff), and type checking (mypy) dependencies.

---

## Verify Installation

### Python

```python
import tvkit
print(tvkit.__version__)
```

### Terminal

```bash
# With pip
python -c "import tvkit; print('tvkit installed')"

# With uv
uv run python -c "import tvkit; print('tvkit installed')"
```

---

## Next Steps

Continue with the **Quickstart** to run your first examples in under 5 minutes:

[Quickstart →](quickstart.md)
