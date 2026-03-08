# Reference Layer Style Guide

This file defines the structure and writing rules for all pages in `docs/reference/`.

**Audience:** tvkit contributors writing or reviewing reference documentation.

---

## The Reference Layer Rule

> Reference = specification only. No tutorial prose.

The reference layer answers: **"What exactly does this method accept and return?"**

It does **not** answer: "How do I accomplish X?" (that belongs in `docs/guides/`).

| Layer | Answers | Prose style |
|-------|---------|-------------|
| `guides/` | How do I accomplish X? | Step-by-step, explanation-heavy |
| `concepts/` | What does this term mean? | Short explanation |
| `reference/` | What exactly does method Y accept? | Tables, signatures, no narration |

---

## Page Template

Every reference page must follow this structure in this order:

```markdown
# <Module or Class Name> Reference

**Module:** `tvkit.<module.path>`
**Available since:** vX.Y.Z

One sentence describing what this module or class does. No tutorial prose.

---

## Import

\`\`\`python
from tvkit.<module.path> import <ClassName>
\`\`\`

---

## `ClassName`

Brief one-line description.

### Signature

\`\`\`python
class ClassName:
    def __init__(self, param1: Type = default, ...) -> None: ...
\`\`\`

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `param1`  | `str` | `"value"` | What it controls |

---

## Methods

### `method_name()`

\`\`\`python
async def method_name(self, param: Type, ...) -> ReturnType: ...
\`\`\`

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `param`   | `str` | required | Description |

#### Returns

`ReturnType` — Description of return value and its structure.

#### Raises

| Exception | When |
|-----------|------|
| `ValueError` | When param is out of range |
| `RuntimeError` | When connection fails |

#### Example

\`\`\`python
async with ClassName() as obj:
    result = await obj.method_name(...)
\`\`\`

---

## Type Definitions

### `SomePydanticModel`

\`\`\`python
from tvkit.<module.path> import SomePydanticModel
\`\`\`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `field1` | `str` | required | Description |
| `field2` | `int \| None` | `None` | Description |

---

## See Also

- [Related Guide](../../guides/related-guide.md)
- [Concepts: Related Concept](../../concepts/related-concept.md)
- [Other Reference Page](../other/page.md)
```

---

## Style Rules

### 1. Import block — required

Every page starts with a working import. Users must be able to copy-paste the import immediately.

```python
# Correct — full import path
from tvkit.api.chart.ohlcv import OHLCV

# Correct — multiple exports
from tvkit.export import DataExporter, ExportFormat
```

### 2. Parameter tables — required for ≥2 parameters

Use a Markdown table. Do not document parameters only in prose.

| Column | Content |
|--------|---------|
| Parameter | Backtick-quoted name |
| Type | Full Python type annotation |
| Default | `required` if no default; otherwise the exact default value |
| Description | One sentence max |

### 3. Return values — required

State the exact return type and what the caller should do with it.

```
#### Returns

`list[OHLCVBar]` — Bars sorted by timestamp ascending. Empty list is never returned;
RuntimeError is raised instead.
```

### 4. Raises table — required

Document every exception the method intentionally raises. Do not document internal implementation exceptions or third-party library exceptions unless they propagate to the caller.

### 5. Minimal example — required

6–10 lines maximum. No explanation prose inside the example block. The example must be complete (includes imports if non-obvious).

```python
# Good — complete, minimal, no prose
async with OHLCV() as client:
    bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=10)
print(bars[0].close)
```

### 6. Type definitions — required for public Pydantic models

Include a fields table for every Pydantic model that appears in a public method signature. Users need to know what fields to access on returned objects.

### 7. "See also" — required

Link to at least one related guide or concept page. Reference pages do not stand alone — they assume the user has read the relevant guide first.

### 8. "Available since" — required

State the version when the class or method was introduced. Use `v0.3.0` format.

### 9. No tutorial prose

These phrases do not belong in reference pages:
- "In this section, we will..."
- "Let's explore..."
- "You can use this method to..."
- "This is useful when..."

Replace with direct specification language:
- "Returns X."
- "Raises ValueError if Y."
- "Equivalent to calling Z."

### 10. No deep-linking into internal implementation

Reference pages document the public API only. Do not reference private methods, internal constants, or implementation details unless they affect the caller (e.g., timeout values that the caller needs to know about).

---

## Checklist for New Reference Pages

Before submitting a reference page, verify:

- [ ] H1 title matches the class or module name exactly
- [ ] `Module:` and `Available since:` metadata present
- [ ] Import block present and correct
- [ ] Every public method documented
- [ ] Every method has: signature, parameter table, returns, raises table, example
- [ ] All Pydantic models in public method signatures have a fields table
- [ ] "See also" section present with at least one link
- [ ] No `<!-- TODO -->` placeholders
- [ ] No tutorial prose
- [ ] All values verified against current source code (not from memory or other docs)
