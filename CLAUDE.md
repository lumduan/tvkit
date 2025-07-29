# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing
- Run all tests: `uv run python -m pytest tests/ -v`
- Run specific test file: 
  - `uv run python -m pytest tests/test_ohlcv_models.py -v`
  - `uv run python -m pytest tests/test_realtime_models.py -v`
  - `uv run python -m pytest tests/test_interval_validation.py -v`
  - `uv run python -m pytest tests/test_utils.py -v`
- Run with coverage: `uv run python -m pytest tests/ --cov=tvkit`

### Code Quality
- Type checking: `uv run mypy tvkit/`
- Linting: `uv run ruff check .`
- Formatting: `uv run ruff format .`
- All quality checks: `uv run ruff check . && uv run ruff format . && uv run mypy tvkit/`

### Development
- Install dependencies: `uv sync`
- **Execute Python**: Use `uv run python <script.py>` or `uv run python -m <module>` (NEVER use pip, poetry, or conda)
- Run example scripts: 
  - `uv run python examples/realtime_streaming_example.py`
  - `uv run python examples/polars_financial_analysis.py`
- Publish: `./scripts/publish.sh`

### Git Workflow
- Pre-commit checks: `uv run ruff check . && uv run ruff format . && uv run mypy tvkit/ && uv run python -m pytest tests/ -v`
- Stage changes: `git add [files]`
- **IMPORTANT**: Request commit review from Claude before committing: "Please review these staged changes and create a commit if appropriate"
- Push to remote: `git push origin main`

## Architecture Overview

**tvkit** is a Python library for TradingView's financial data APIs with two main components:

### 1. Scanner API (`tvkit.api.scanner`)
- Provides typed models for TradingView's scanner API
- Key classes: Located in `model.py`
- Used for stock screening, filtering, and fundamental analysis

### 2. Real-Time Chart API (`tvkit.api.chart`)
- Async WebSocket streaming for real-time market data
- Key classes: `OHLCV` models, real-time streaming models
- Main client: `ohlcv.py` with streaming functionality
- Services: `connection_service.py`, `message_service.py`
- Models: `ohlcv.py`, `realtime.py`, `stream_models.py`
- Utilities: `utils.py` for helper functions
- Built with modern async patterns using `websockets` and `httpx`

## Key Patterns

### Async-First Architecture
- All I/O operations use async/await
- WebSocket streaming with async generators
- HTTP validation with async clients (`httpx`, not `requests`)
- Context managers for resource management

### Type Safety with Pydantic
- All data models inherit from Pydantic BaseModel
- Comprehensive validation and type hints
- Field descriptions and constraints required
- No `Any` types without justification

### Error Handling
- Specific exception types for different error conditions
- Retry mechanisms with exponential backoff
- Graceful degradation for parsing errors
- Structured logging for debugging

## Project Structure
```
tvkit/
├── tvkit/
│   ├── api/
│   │   ├── chart/              # Real-time WebSocket streaming
│   │   │   ├── models/         # Pydantic data models
│   │   │   │   ├── ohlcv.py    # OHLCV data models
│   │   │   │   ├── realtime.py # Real-time streaming models
│   │   │   │   └── stream_models.py # Stream-specific models
│   │   │   ├── services/       # WebSocket services
│   │   │   │   ├── connection_service.py # Connection management
│   │   │   │   └── message_service.py    # Message handling
│   │   │   ├── ohlcv.py        # Main OHLCV client
│   │   │   └── utils.py        # Chart utilities
│   │   ├── scanner/            # Scanner API models
│   │   │   └── model.py        # Scanner data models
│   │   └── utils.py            # General API utilities
│   ├── core.py                 # Core functionality
│   └── py.typed                # Type declarations marker
├── tests/                      # Pytest test suite
├── examples/                   # Working usage examples
├── docs/                       # Documentation
├── debug/                      # Debug scripts (gitignored)
├── export/                     # Export output directory
└── scripts/                    # Utility scripts
```

## Development Guidelines

### Mandatory Requirements
1. **Type Safety**: All functions must have complete type annotations
   - ALL variable declarations MUST have explicit type annotations (e.g., `validate_url: str = "..."`)
   - Named Parameters in All Function Calls
   - NO `Any` types without explicit justification
2. **Async Patterns**: Use async/await for all I/O operations  
   - ALL HTTP clients MUST be async (httpx, not requests)
   - ALL WebSocket operations MUST be async (websockets, not websocket-client)
   - Context managers MUST be used for resource management
3. **Pydantic Models**: All data structures must use Pydantic validation
   - Field descriptions and constraints are REQUIRED
4. **Testing**: All new features must have comprehensive tests
   - Minimum 90% code coverage required
5. **Code Quality**: Must pass `ruff`, `mypy`, and all tests before committing

### Prohibited Actions
- Never use `requests` (use `httpx` for async HTTP)
- Never use `websocket-client` (use `websockets` for async WebSocket)
- Never hardcode credentials or API keys
- Never commit code that doesn't pass all quality checks
- Never use bare `except:` clauses
- Never commit debug print statements
- Never break existing public APIs without deprecation
- Never add dependencies without updating pyproject.toml
- Never use synchronous I/O for external API calls
- Never commit without using Claude's git-commit-reviewer agent (except for trivial documentation changes)

### Git Commit Guidelines

#### When to Use Git-Commit-Reviewer (MANDATORY)
- **Refactoring changes** (class/method/variable renames)
- **API changes** affecting public interfaces
- **Breaking changes** or architectural updates
- **Multiple file modifications** (3+ files)
- **Dependencies or configuration changes**
- **Performance or security modifications**
- **Data model or schema changes**

#### Commit Review Process
1. **Pre-commit validation**: All quality checks must pass
2. **Stage changes**: `git add` relevant files
3. **Request review**: Ask Claude to "review these staged changes and create a commit if appropriate"
4. **Claude will assess**:
   - Code quality and CI/CD pipeline impact
   - Breaking changes and deployment risks
   - Test coverage and production readiness
   - Commit message structure and clarity

#### Commit Message Standards
- Use conventional commit format with emojis for visual organization
- Include clear section headers (🎯 New Features, 🛠️ Technical Implementation, etc.)
- List all modified files with brief descriptions
- Highlight user and technical benefits
- Note testing performed and validation steps
- Use bullet points (•) for better readability
- Keep descriptions concise but informative
- All commits include Claude co-authoring attribution

### Testing Strategy
- Run tests before making changes: `uv run python -m pytest tests/ -v`
- Write tests first (TDD approach preferred)
- Mock external dependencies appropriately
- Maintain 90%+ code coverage

## Key Dependencies
- `pydantic>=2.11.7` - Data validation and settings
- `websockets>=13.0` - Async WebSocket client
- `httpx>=0.28.0` - Async HTTP client
- `polars>=1.0.0` - Data processing and analysis
- `pytest>=8.0.0` + `pytest-asyncio>=0.23.0` - Testing framework
- `ruff>=0.12.4` - Code linting and formatting
- `mypy>=1.17.0` - Static type checking (dev dependency)

## Important Notes
- Uses `uv` for dependency management (not pip/poetry)
- Python 3.13+ required (specified in pyproject.toml)
- All WebSocket operations are async with proper connection management
- Symbol validation done via async HTTP requests
- Export functionality supports CSV, JSON, and Parquet formats
- Includes `py.typed` marker file for type information distribution
- Build system uses setuptools with wheel support

## File Organization Standards

### Directory Structure Requirements
- `/tests/`: ALL pytest tests, comprehensive coverage required
- `/examples/`: ONLY real-world usage examples, fully functional
- `/docs/`: ALL documentation files (includes POLARS_INTEGRATION.md, realtime_streaming.md)
- `/debug/`: Temporary debug scripts ONLY (gitignored)
- `/scripts/`: Utility scripts for development and CI/CD
- `/export/`: Output directory for exported data (CSV, JSON, Parquet)
- `/dist/`: Build artifacts and distribution files

### File Naming Conventions
- Snake_case for all Python files
- Clear, descriptive names indicating purpose
- Test files MUST match pattern `test_*.py`
- Example files MUST match pattern `*_example.py`

### Import Organization (MANDATORY)
```python
# 1. Standard library imports
import asyncio
from typing import Any, Optional

# 2. Third-party imports
import httpx
import polars as pl
from pydantic import BaseModel

# 3. Local imports
from tvkit.api.chart.models import OHLCV
```

## Documentation Standards

### Docstring Requirements
- ALL public functions MUST have comprehensive docstrings
- Include parameter descriptions with types
- Include return value descriptions
- Include usage examples for complex functions
- Include exception documentation

### Example Format
```python
async def example_function(
    param1: str,
    param2: Optional[bool] = None,
) -> bool:
    """
    Brief description of what the function does.

    More detailed explanation if needed. Cannot send
    messages to certain types of chats.

    Args:
        param1: Description of parameter
        param2: Optional parameter description

    Returns:
        True if successful

    Raises:
        CustomError: When specific error occurs

    Example:
        >>> result = await example_function("test")
        >>> print(result)
        True
    """
```

## Specialized Agent Workflows

This project uses specialized Claude agents for specific development tasks to ensure consistency and expertise:

### Git Commit Reviewer Agent (`@git-commit-reviewer`)

**Purpose**: Ensures commit quality, message standards, and repository hygiene

**Invoke when**:
- Creating any git commit (mandatory)
- Reviewing pull requests
- Analyzing commit history or git workflow issues
- Setting up git hooks or automation

**Responsibilities**:
- Validate commit message format and clarity
- Review staged changes for completeness
- Ensure no sensitive data or debug code is committed
- Verify all quality checks pass before commit
- Follow conventional commit format when appropriate
- Check that related tests and documentation are included

**Workflow Integration**:
```bash
# Before any commit, the agent will:
1. Run: git status && git diff --staged && git log --oneline -5
2. Analyze changes for quality and completeness
3. Draft appropriate commit message following project conventions
4. Execute: git commit -m "message" && git status
```

### Python Architect Agent (`@python-architect`)

**Purpose**: Provides architectural guidance and ensures code quality standards

**Invoke when**:
- Designing new features or major refactoring
- Making architectural decisions (async patterns, error handling, etc.)
- Evaluating dependencies or technology choices
- Establishing coding standards or patterns
- Reviewing complex code changes
- Planning module structure or API design

**Responsibilities**:
- Ensure compliance with async-first architecture
- Validate Pydantic model design and type safety
- Review error handling and logging strategies
- Assess performance and scalability implications
- Maintain consistency with existing patterns
- Guide testing strategy and coverage requirements

**Domain Expertise**:
- WebSocket streaming architectures
- Async/await patterns and context management
- Pydantic validation and data modeling
- Financial data processing best practices
- API design for real-time data systems

### Documentation Specialist Agent (`@documentation-specialist`)

**Purpose**: Ensures comprehensive documentation standards and maintains consistency

**Invoke when**:
- Writing or updating public API documentation
- Creating comprehensive docstrings for complex functions
- Establishing documentation standards across modules
- Reviewing documentation for completeness and clarity
- Creating usage examples and integration guides

**Responsibilities**:
- Validate docstring format and completeness
- Ensure parameter descriptions include types and constraints
- Add usage examples for complex functions
- Document exceptions and error conditions
- Maintain consistency in documentation style across modules
- Review and improve existing documentation

**Domain Expertise**:
- Python docstring conventions and best practices
- API documentation standards
- Technical writing for developer audiences
- Code example creation and validation

### Dependency Manager Agent (`@dependency-manager`)

**Purpose**: Manages Python dependencies and execution environment using uv package manager

**Invoke when**:
- Adding or removing project dependencies
- Updating package versions
- Setting up development environment
- Troubleshooting dependency conflicts
- Validating environment reproducibility
- Preparing for project releases

**Responsibilities**:
- Manage all Python dependencies using `uv` (NEVER pip, poetry, or conda)
- Execute Python scripts using `uv run python <script.py>`
- Update `pyproject.toml` for all dependency changes
- Maintain `uv.lock` file consistency
- Monitor dependency versions for security updates
- Ensure Python 3.13+ compatibility

**Domain Expertise**:
- uv package manager best practices
- Python dependency resolution and conflicts
- Virtual environment management
- Package security and vulnerability assessment
- Modern Python packaging standards (PEP 517, 518, 621)

### Agent Coordination Protocol

**Sequential Invocation Pattern**:
1. `@python-architect` for design and implementation
2. `@git-commit-reviewer` for commit preparation
3. Quality gates: tests, linting, type checking must pass

**Decision Matrix**:
| Task Type | Primary Agent | Secondary Agent | Quality Gates |
|-----------|---------------|-----------------|---------------|
| New Feature Design | `@python-architect` | `@git-commit-reviewer` | All |
| Bug Fix | General Claude | `@git-commit-reviewer` | Tests + Lint |
| Refactoring | `@python-architect` | `@git-commit-reviewer` | All |
| Documentation | `@documentation-specialist` | `@git-commit-reviewer` | Lint only |
| Configuration | `@python-architect` | `@git-commit-reviewer` | Tests |
| API Documentation | `@documentation-specialist` | `@python-architect` | All |
| Dependencies | `@dependency-manager` | `@git-commit-reviewer` | Tests |
| Environment Setup | `@dependency-manager` | `@python-architect` | Tests |

### Quality Gates Integration

All agent workflows must enforce these quality gates:

```bash
# Mandatory before any commit
uv run ruff check . && uv run ruff format . && uv run mypy tvkit/
uv run python -m pytest tests/ -v

# Architecture reviews must consider:
- Async pattern compliance
- Type safety with mypy validation
- Pydantic model correctness
- Test coverage maintenance
- Performance implications
```