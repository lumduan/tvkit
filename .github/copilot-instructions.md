```instructions
<SYSTEM>
You are an AI programming assistant that is specialized in applying code changes to an existing document.
Follow Microsoft content policies.
Avoid content that violates copyrights.
If you are asked to generate content that is harmful, hateful, racist, sexist, lewd, violent, or completely irrelevant to software engineering, only respond with "Sorry, I can't assist with that."
Keep your answers short and impersonal.
The user has a code block that represents a suggestion for a code change and a instructions file opened in a code editor.
Rewrite the existing document to fully incorporate the code changes in the provided code block.
For the response, always follow these instructions:
1. Analyse the code block and the existing document to decide if the code block should replace existing code or should be inserted.
2. If necessary, break up the code block in multiple parts and insert each part at the appropriate location.
3. Preserve whitespace and newlines right after the parts of the file that you modify.
4. The final result must be syntactically valid, properly formatted, and correctly indented. It should not contain any ...existing code... comments.
5. Finally, provide the fully rewritten file. You must output the complete file.
</SYSTEM>
```

# 🤖 AI Agent Context

## Project Overview

**tvkit** is a Python library for interacting with TradingView's financial data APIs, specifically focused on the scanner API for retrieving stock market data and analysis.

## 🎯 Core Purpose

This library provides a type-safe, async-first Python interface to TradingView's scanner API, enabling developers to:

- Query stock market data with flexible filtering and sorting
- Retrieve fundamental and technical analysis data
- Access real-time market information
- Perform stock screening and analysis

## 🏗️ Architecture & Tech Stack

### Core Framework

- **Python 3.13+**: Modern Python with full type hint support
- **Pydantic V2**: Data validation and settings management with strict type enforcement
- **Async/Await**: Non-blocking I/O operations for optimal performance

### Dependencies & Package Management

**Dependency Management & Python Execution:**

- All Python dependencies MUST be managed using [uv](https://github.com/astral-sh/uv).
- Install dependencies with `uv pip install -r requirements.txt` or `uv pip install <package>`.
- Add/remove dependencies with `uv pip add <package>` or `uv pip remove <package>`.
- Lock dependencies with `uv pip freeze > requirements.txt` and ensure `uv.lock` is up to date.
- Run Python scripts and modules using `uv pip run python <script.py>` or `uv pip run python -m <module>`.
- Do NOT use pip, poetry, or conda for dependency management or Python execution.

### Design Principles

## 📁 Project Structure

```
tvkit/
├── tvkit/
│   ├── __init__.py              # Main library exports
│   ├── api/
│   │   ├── __init__.py          # API module exports
│   │   ├── stock.py             # Individual stock data API
│   │   ├── stocks.py            # Multiple stocks API
│   │   └── scanner/
│   │       ├── __init__.py      # Scanner module exports
│   │       └── model.py         # TradingView scanner API models
│   └── stock/
│       └── stream/
│           ├── stream_handler.py # Base WebSocket stream handler
│           └── price.py         # Real-time price streaming API
├── tests/
│   ├── __init__.py
│   └── test_scanner_model.py    # Tests for scanner models
├── docs/                        # Documentation
├── debug/                       # Debug scripts (gitignored)
├── scripts/                     # Utility scripts
│   └── publish.sh              # Publishing automation
├── pyproject.toml              # Project configuration and dependencies
├── uv.lock                     # Locked dependencies
└── README.md                   # User documentation
```

## 🔧 Environment Configuration

### Required Environment Variables

```bash
# Set all required environment variables in your shell or .env file before running any scripts.
```

### Configuration Loading

## 🚀 Core Modules

### TradingView Scanner API (`tvkit.api.scanner`)

The core module providing comprehensive data models for interacting with TradingView's scanner API:

#### **Key Components:**

- **`ScannerRequest`**: Pydantic model for API request configuration

  - Validates column names, range limits, and sorting options
  - Supports all major TradingView scanner presets
  - Type-safe field validation with comprehensive error messages

- **`ScannerResponse`**: Structured response parsing from TradingView API

  - Converts raw API arrays into typed `StockData` objects
  - Handles pagination and total count metadata
  - Error-tolerant parsing with graceful degradation

- **`StockData`**: Complete stock information model
  - 20+ financial fields including fundamentals and technical indicators
  - Price data (close, high, low, open, change)
  - Volume and market cap information
  - Earnings, P/E ratios, and dividend yields
  - Sector classification and analyst recommendations

#### **Utility Classes:**

- **`ScannerPresets`**: Common scanner configurations (ALL_STOCKS, TOP_GAINERS, etc.)
- **`ColumnSets`**: Predefined column groups (BASIC, DETAILED, FUNDAMENTALS, TECHNICAL)
- **`create_scanner_request()`**: Factory function with sensible defaults

#### **Example Usage:**

```python
from tvkit.api.scanner import create_scanner_request, ColumnSets

# Create a request for top gainers with basic columns
request = create_scanner_request(
    columns=ColumnSets.BASIC,
    preset="top_gainers",
    sort_by="change",
    sort_order="desc",
    range_end=50
)

# All models provide comprehensive validation and type safety
print(f"Requesting {len(request.columns)} columns")
print(f"Range: {request.range[0]}-{request.range[1]}")
```

### TradingView Real-Time Streaming API (`tvkit.stock.stream`)

Modern async-first WebSocket streaming implementation for real-time market data:

#### **Key Components:**

- **`RealTimeData`**: Async WebSocket client for TradingView real-time data

  - Full async/await patterns using `websockets` library
  - Automatic connection management with context manager support
  - Built-in compression and keepalive functionality
  - Type-safe async generators for data streaming

- **`StreamHandler`**: Base WebSocket connection handler

  - Session management for quote and chart data streams
  - Message construction and protocol handling
  - Error recovery and connection state management

#### **WebSocket Architecture:**

- **Modern Library**: Uses `websockets>=13.0` (not `websocket-client`)
- **Async HTTP**: Uses `httpx` for symbol validation (not `requests`)
- **Type Safety**: Full type annotations with `AsyncGenerator` patterns
- **Error Handling**: Specific exception types (`ConnectionClosed`, `WebSocketException`)
- **Performance**: Built-in WebSocket compression (RFC 7692) and connection pooling

#### **Example Usage:**

```python
from tvkit.stock.stream.price import RealTimeData
import asyncio

# Single symbol OHLCV streaming
async def stream_ohlcv():
    async with RealTimeData() as client:
        async for data in client.get_ohlcv("BINANCE:BTCUSDT"):
            print(f"OHLCV: {data}")

# Multiple symbols trade info
async def stream_multiple():
    symbols = ["BINANCE:ETHUSDT", "NASDAQ:AAPL", "FXOPEN:XAUUSD"]
    async with RealTimeData() as client:
        async for data in client.get_latest_trade_info(symbols):
            print(f"Trade data: {data}")

# Run the async functions
asyncio.run(stream_ohlcv())
```

#### **WebSocket Features:**

- **Async Context Manager**: Automatic connection lifecycle management
- **Symbol Validation**: Async HTTP validation with retry logic
- **Session Management**: Automatic quote/chart session handling
- **Heartbeat Handling**: Built-in ping/pong keepalive
- **Message Protocol**: TradingView-specific message formatting
- **Error Recovery**: Graceful connection handling and reconnection

## 🧪 Testing Strategy

### Test Infrastructure

- **`test_scanner_model.py`**: Comprehensive test suite for all scanner models
  - Tests for model validation, field constraints, and error handling
  - Factory function testing with various parameter combinations
  - Response parsing validation with realistic TradingView API data
  - Edge case testing for malformed data and boundary conditions

## ⚠️ AI Agent File Deletion Limitation

When using AI models such as GPT-4.1, GPT-4o, or any model that cannot directly delete files, be aware of the following workflow limitation:

- **File Deletion Restriction**: The AI model cannot perform destructive actions like deleting files from the filesystem. Its capabilities are limited to editing file contents only.
- **User Action Required**: If you need to remove a file, the AI will provide the appropriate terminal command (e.g., `rm /path/to/file.py`) for you to run manually.
- **Safety Rationale**: This restriction is in place to prevent accidental or unauthorized file deletion and to ensure user control over destructive actions.
- **Workflow Guidance**: Always confirm file removal by running the suggested command in your terminal or file manager.

## 🤖 AI Agent Instructions - STRICT COMPLIANCE REQUIRED

**CRITICAL**: All AI agents working on this project MUST follow these instructions precisely. Deviation from these guidelines is not permitted.

### 🚨 MANDATORY PRE-WORK VALIDATION

Before making ANY changes:

1. **ALWAYS** read the current file contents completely before editing
2. **ALWAYS** run existing tests to ensure no regressions: `python -m pytest tests/ -v`
3. **ALWAYS** check git status and current branch before making changes
4. **ALWAYS** validate that your changes align with the project architecture

### 🎯 CORE ARCHITECTURAL PRINCIPLES - NON-NEGOTIABLE

1. **Type Safety is MANDATORY**:

   - ALL functions MUST have complete type annotations
   - ALL data structures MUST use Pydantic models
   - ALL inputs and outputs MUST be validated
   - NO `Any` types without explicit justification
   - NO missing type hints on public APIs
   - ALL variable declarations MUST have explicit type annotations (e.g., `validate_url: str = "..."`)

## 📝 Module Variable Type Annotations

All variable declarations in the module now have explicit type annotations as requested. The code is more readable and type-safe, following the preferred style.

**Example:**
```python
# ✅ Correct - with explicit type annotation
validate_url: str = (
    "https://scanner.tradingview.com/symbol?"
    "symbol={exchange}%3A{symbol}&fields=market&no_404=false"
)

# ❌ Incorrect - without type annotation
validate_url = (
    "https://scanner.tradingview.com/symbol?"
    "symbol={exchange}%3A{symbol}&fields=market&no_404=false"
)
```

2. **Async-First Architecture is REQUIRED**:

   - ALL I/O operations MUST use async/await patterns
   - ALL HTTP clients MUST be async (httpx, not requests)
   - ALL WebSocket operations MUST be async (websockets, not websocket-client)
   - ALL database operations MUST be async
   - Context managers MUST be used for resource management

3. **Pydantic Integration is MANDATORY**:

   - ALL configuration MUST use Pydantic Settings
   - ALL API request/response models MUST use Pydantic
   - ALL validation MUST use Pydantic validators
   - Field descriptions and constraints are REQUIRED

4. **Error Handling Must Be Comprehensive**:
   - ALL exceptions MUST be typed and specific
   - ALL external API calls MUST have retry mechanisms
   - ALL errors MUST be logged with structured data
   - User-facing error messages MUST be helpful and actionable

### 📁 FILE ORGANIZATION - STRICT RULES

#### Directory Structure Requirements:

- `/tests/`: ALL pytest tests, comprehensive coverage required
- `/examples/`: ONLY real-world usage examples, fully functional
- `/docs/`: ALL documentation, including moved WEBHOOK_SETUP.md
- `/debug/`: Temporary debug scripts ONLY (gitignored)
- `/scripts/`: Utility scripts for development and CI/CD

#### File Naming Conventions:

- Snake_case for all Python files
- Clear, descriptive names indicating purpose
- Test files MUST match pattern `test_*.py`
- Example files MUST match pattern `*_example.py`

#### Import Organization (MANDATORY):

```python
```python
# 1. Standard library imports
import asyncio
from typing import Any, Optional, AsyncGenerator

# 2. Third-party imports
import httpx
from pydantic import BaseModel
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException
```


```

### 🧪 TESTING REQUIREMENTS - NO EXCEPTIONS

1. **ALL new features MUST have tests**:

   - Unit tests for all functions
   - Integration tests for API interactions
   - Async test patterns using pytest-asyncio
   - Mock external dependencies appropriately

2. **Test Coverage Standards**:

   - Minimum 90% code coverage
   - 100% coverage for public APIs
   - Edge cases and error conditions MUST be tested

3. **Test Quality Requirements**:
   - Clear test names describing what is being tested
   - Arrange-Act-Assert pattern
   - No test interdependencies
   - Fast execution (no real API calls in unit tests)

### 📝 DOCUMENTATION STANDARDS - MANDATORY

1. **Docstring Requirements**:

   - ALL public functions MUST have comprehensive docstrings
   - Include parameter descriptions with types
   - Include return value descriptions
   - Include usage examples for complex functions
   - Include exception documentation

2. **Example Format**:

```python
async def multicast_message(
    self,
    user_ids: list[str],
    messages: list[Any],
    notification_disabled: Optional[bool] = None,
) -> bool:
    """
    Send multicast message to multiple users.

    Efficiently sends the same message to multiple user IDs. Cannot send
    messages to group chats or multi-person chats.

    Args:
        user_ids: List of user IDs (max 500)
        messages: List of message objects (max 5)
        notification_disabled: Whether to disable push notifications

    Returns:
        True if successful

    Raises:
        LineMessageError: If message sending fails
        LineRateLimitError: If rate limit exceeded

    Example:
        >>> async with LineMessagingClient(config) as client:
        ...     success = await client.multicast_message(
        ...         user_ids=["user1", "user2"],
        ...         messages=[TextMessage.create("Hello!")],
        ...     )
    """
```

### 🔧 CODE QUALITY - STRICT ENFORCEMENT

1. **Linting and Formatting**:

   - MUST run `ruff format .` before committing
   - MUST run `ruff check .` and fix all issues
   - MUST run `mypy tvkit/` and resolve all type errors
   - NO disabled linting rules without justification
   - **ACHIEVED**: 100% mypy strict mode compliance across all modules

2. **Code Style Requirements**:

   - NO wildcard imports (`from module import *`)
   - NO unused imports or variables
   - Consistent naming conventions throughout
   - Use modern type annotations (`dict`/`list` not `Dict`/`List`)

3. **Performance Requirements**:
   - Use async patterns for ALL I/O operations
   - Implement proper connection pooling
   - Cache responses when appropriate
   - Monitor memory usage for large operations

### 🛡️ SECURITY REQUIREMENTS - NON-NEGOTIABLE

1. **Credential Management**:
   - NO hardcoded secrets or tokens
   - ALL credentials MUST use environment variables
   - Pydantic SecretStr for sensitive data
   - Secure defaults for all configuration

### 🔄 DEVELOPMENT WORKFLOW - MANDATORY STEPS

#### Before Starting ANY Task:

1. Create feature branch: `git checkout -b feature/description`
2. Read ALL relevant existing code
3. Check current tests: `uv pip run python -m pytest tests/ -v`
4. Understand the current implementation completely

#### During Development:

1. Write tests FIRST (TDD approach preferred)
2. Implement with full type hints
3. Add comprehensive docstrings
4. Run tests frequently: `uv pip run python -m pytest tests/test_specific.py -v`

#### Before Committing:

1. Run ALL tests: `uv pip run python -m pytest tests/ -v`
2. Run type checking: `uv pip run mypy tvkit/`
3. Run linting: `uv pip run ruff check . && uv pip run ruff format .`
4. Verify examples still work
5. Update documentation if needed


### ❌ PROHIBITED ACTIONS

1. **NEVER** use bare `except:` clauses
2. **NEVER** ignore type checker warnings without justification
3. **NEVER** hardcode credentials or secrets
4. **NEVER** commit debug print statements
5. **NEVER** break existing public APIs without deprecation
6. **NEVER** add dependencies without updating pyproject.toml
7. **NEVER** commit code that doesn't pass all tests
8. **NEVER** use synchronous I/O for external API calls
9. **NEVER** use `websocket-client` library (use `websockets` for async patterns)
10. **NEVER** use `requests` library (use `httpx` for async HTTP)

### 🏆 QUALITY GATES - ALL MUST PASS

Before any code is considered complete:

- [ ] All tests pass: `python -m pytest tests/ -v`
- [ ] Type checking passes: `mypy tvkit/`
- [ ] Linting passes: `ruff check .`
- [ ] Code is formatted: `ruff format .`
- [ ] Documentation is updated
- [ ] Examples work correctly
- [ ] Performance is acceptable
- [ ] Security review completed

### 🚨 VIOLATION CONSEQUENCES

Failure to follow these guidelines will result in:

1. Immediate rejection of changes
2. Required rework with full compliance
3. Additional review requirements for future changes

**These guidelines are not suggestions - they are requirements for maintaining the quality and reliability of this production-grade TradingView stock data integration library.**

### Development Guidelines

#### Adding New Features

1. **Plan the API**: Design the public interface first
2. **Write Tests**: Start with test cases for the new feature
3. **Implement**: Create the implementation with full type hints
4. **Document**: Add comprehensive docstrings and examples
5. **Integration**: Update the main API classes if needed
6. **Validate**: Run all tests and type checking

#### Code Organization Rules

- **Clean Imports**: All imports at the top of files
- **Debug Scripts**: All debug/investigation scripts MUST go in `/debug` folder (gitignored)
- **Tests**: All pytest tests MUST go in `/tests` folder
- **Examples**: Real-world examples in `/examples` folder
- **Documentation**: API docs and guides in `/docs` folder

#### Error Handling Patterns

```python
from tvkit.stock.stream.price import RealTimeData
from websockets.exceptions import ConnectionClosed, WebSocketException
import asyncio
import logging

# Proper WebSocket streaming with error handling
async def stream_with_retry(symbols: list[str]) -> None:
    """Stream real-time data with connection retry."""
    max_retries = 3
    base_delay = 1.0

    for attempt in range(max_retries + 1):
        try:
            async with RealTimeData() as client:
                async for data in client.get_latest_trade_info(symbols):
                    print(f"Received: {data}")
        except ConnectionClosed as e:
            logging.warning(f"WebSocket connection closed: {e}")
            if attempt == max_retries:
                raise

            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)
            continue
        except WebSocketException as e:
            logging.error(f"WebSocket error: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            raise

# Async HTTP validation with retry
async def validate_symbols_with_retry(symbols: list[str]) -> bool:
    """Validate symbols with exponential backoff retry."""
    import httpx

    async with httpx.AsyncClient() as client:
        for symbol in symbols:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = await client.get(f"https://api.example.com/validate/{symbol}")
                    response.raise_for_status()
                    break
                except httpx.RequestError as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1.0 * (2 ** attempt))
                    else:
                        raise ValueError(f"Failed to validate {symbol}") from e
    return True
```

### Production Considerations

- **Rate Limiting**: Implement proper rate limiting for all API calls
- **Error Recovery**: Retry mechanisms with exponential backoff
- **Logging**: Structured logging for debugging and monitoring
- **Security**: Secure credential management and validation
- **Performance**: Async operations and connection pooling
- **Monitoring**: Health checks and metrics collection
- **WebSocket Management**: Proper connection lifecycle and heartbeat handling
- **Symbol Validation**: Async HTTP validation with retry logic

```


### Key Files for AI Understanding

- **README.md**: User-facing documentation and usage examples
- **pyproject.toml**: Dependencies and project configuration
- **Module `__init__.py` files**: Public API exports and module structure
- **Test files**: Examples of proper usage and expected behavior
- **Integration guides**: Patterns for using shared tools in services

```
