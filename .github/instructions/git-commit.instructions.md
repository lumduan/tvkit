---
applyTo: '**'
---
### Commit Message Instructions

1. **Use clear section headers** (e.g., 🎯 New Features, 🛠️ Technical Implementation, 📁 Files Added/Modified, ✅ Benefits, 🧪 Tested)
2. **Summarize the purpose and impact** of the change in the first line
3. **List all new and modified files** with brief descriptions
4. **Highlight user and technical benefits** clearly
5. **Note any testing or validation** performed
6. **Use bullet points** (•) for better readability
7. **Include relevant emojis** for visual organization
8. **Keep descriptions concise** but informative

### ❌ PROHIBITED ACTIONS

1. **NEVER** use bare `except:` clauses
2. **NEVER** ignore type checker warnings without justification
3. **NEVER** hardcode credentials or secrets
4. **NEVER** commit debug print statements
5. **NEVER** break existing public APIs without deprecation
6. **NEVER** add dependencies without updating pyproject.toml
7. **NEVER** commit code that doesn't pass all tests
8. **NEVER** use synchronous I/O for external API calls