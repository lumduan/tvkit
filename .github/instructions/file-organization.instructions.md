---
applyTo: '**'
---
## ⚠️ AI Agent File Deletion Limitation

When using AI models such as GPT-4.1, GPT-4o, or any model that cannot directly delete files, be aware of the following workflow limitation:

- **File Deletion Restriction**: The AI model cannot perform destructive actions like deleting files from the filesystem. Its capabilities are limited to editing file contents only.
- **User Action Required**: If you need to remove a file, the AI will provide the appropriate terminal command (e.g., `rm /path/to/file.py`) for you to run manually.
- **Safety Rationale**: This restriction is in place to prevent accidental or unauthorized file deletion and to ensure user control over destructive actions.
- **Workflow Guidance**: Always confirm file removal by running the suggested command in your terminal or file manager.

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

