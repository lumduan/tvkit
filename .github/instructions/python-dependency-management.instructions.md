---
applyTo: '**'
---
**Dependency Management & Python Execution:**

- All Python dependencies MUST be managed using [uv](https://github.com/astral-sh/uv).
- Install dependencies with `uv pip install -r requirements.txt` or `uv pip install <package>`.
- Add/remove dependencies with `uv pip add <package>` or `uv pip remove <package>`.
- Lock dependencies with `uv pip freeze > requirements.txt` and ensure `uv.lock` is up to date.
- Run Python scripts and modules using `uv pip run python <script.py>` or `uv pip run python -m <module>`.
- Do NOT use pip, poetry, or conda for dependency management or Python execution.

