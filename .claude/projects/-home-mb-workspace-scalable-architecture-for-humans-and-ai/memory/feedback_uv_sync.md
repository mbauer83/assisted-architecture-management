---
name: Use uv sync for Python deps
description: Use `uv sync` instead of pip install for Python dependency management
type: feedback
---

Use `uv sync` instead of `pip install` for Python dependency management in this project.

**Why:** Project uses uv as its Python package manager.
**How to apply:** When Python imports fail due to missing modules, run `uv sync` to install all project dependencies.
