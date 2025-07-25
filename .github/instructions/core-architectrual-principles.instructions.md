---
applyTo: '**'
---
### 🎯 CORE ARCHITECTURAL PRINCIPLES - NON-NEGOTIABLE


1. **Type Safety is MANDATORY**:

   - ALL functions MUST have complete type annotations
   - ALL data structures MUST use Pydantic models
   - ALL inputs and outputs MUST be validated
   - NO `Any` types without explicit justification
   - NO missing type hints on public APIs
   - ALL variable declarations MUST have explicit type annotations (e.g., `validate_url: str = "..."`)

2. **Async-First Architecture is REQUIRED**:

   - ALL I/O operations MUST use async/await patterns
   - ALL HTTP clients MUST be async (httpx, not requests)
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


### 🚨 MANDATORY PRE-WORK VALIDATION

Before making ANY changes:

1. **ALWAYS** read the current file contents completely before editing
2. **ALWAYS** run existing tests to ensure no regressions: `python -m pytest tests/ -v`
3. **ALWAYS** check git status and current branch before making changes
4. **ALWAYS** validate that your changes align with the project architecture


#### Import Organization (MANDATORY):

```python
# 1. Standard library imports
import asyncio
from typing import Any, Optional

# 2. Third-party imports
import httpx
from pydantic import BaseModel


```