# Claude Code — Project Instructions

## Architectural discipline

**Always choose the principled solution, never a workaround.**

When something is missing from a class or interface, add it at the correct layer. Do not route around the gap using a different, less appropriate API.

Examples of workarounds to reject:
- A facade is missing a delegation method → do not reach through to the underlying store using a different, less efficient call; add the delegation.
- A protocol/port declares a method the implementing class lacks → implement it; don't call an alternative that happens to return equivalent data.
- A test setup is brittle because the production code has an incomplete contract → fix the contract, then write the test against it.

After every such fix: add a unit test verifying the delegation, and a regression test reproducing the original failure scenario.

## Quality gates (every change)

Run in order before committing:
1. `python -m pytest --tb=short -q` — must be 0 failures
2. `ruff check src/ tests/` — must be 0 errors (including E501)
3. `uv run zuban check` — must pass

## Model authoring

All model writes go through MCP tools (`artifact_create_entity`, `artifact_add_connection`, etc.). Never edit model files by hand. If a tool is wrong, fix the tool.
