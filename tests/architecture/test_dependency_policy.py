"""AST-based dependency policy test.

Walks every *.py under src/, collects all Import/ImportFrom nodes including
lazy (function-nested) ones, classifies each module's package role, and
asserts the matrix from docs/architecture/dependency-policy.md.

Runs in baseline mode: architecture_baseline.json lists current known
violations; the test fails only on *new* violations not present there.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_BASELINE_PATH = Path(__file__).parent / "architecture_baseline.json"
_SRC_ROOT = _PROJECT_ROOT / "src"

# Entry-point modules that wire the full object graph; allowed to import from any package.
_COMPOSITION_ROOTS: frozenset[str] = frozenset(
    {
        "src/infrastructure/app_bootstrap.py",
        "src/infrastructure/cli/artifact_query_cli.py",
        "src/infrastructure/cli/arch_assurance.py",
        "src/infrastructure/cli/_assurance_commands.py",
        "src/infrastructure/cli/_security_commands.py",
        "src/infrastructure/mcp/arch_mcp_stdio.py",
        "src/infrastructure/mcp/arch_mcp_stdio_write.py",
        "src/infrastructure/mcp/arch_mcp_stdio_assurance.py",
        "src/infrastructure/mcp/mcp_artifact_server.py",
        "src/infrastructure/mcp/mcp_assurance_server.py",
        "src/infrastructure/gui/gui_server.py",
        "src/infrastructure/backend/arch_backend.py",
        "src/infrastructure/backend/arch_backend_app.py",
    }
)

# Allowed import-target roles per source role.
# Intra-package imports (a file importing a sibling/child in the same package) are
# always permitted and are represented by including the package's own role.
_ALLOWED: dict[str, frozenset[str]] = {
    "domain": frozenset({"domain"}),
    "application": frozenset({"domain", "application"}),
    "config": frozenset({"config", "domain"}),
    "ontologies": frozenset({"domain", "ontologies"}),
    "diagram_types": frozenset({"domain", "infrastructure", "diagram_types"}),
    "infrastructure": frozenset(
        {"application", "domain", "ontologies", "diagram_types", "config", "infrastructure"}
    ),
    "composition": frozenset(
        {
            "domain",
            "application",
            "config",
            "ontologies",
            "diagram_types",
            "infrastructure",
            "composition",
        }
    ),
}


def _file_role(rel_path: str) -> str:
    if rel_path in _COMPOSITION_ROOTS:
        return "composition"
    parts = Path(rel_path).parts
    if len(parts) < 2 or parts[0] != "src":
        return "unknown"
    return parts[1]  # 'domain', 'application', 'config', …


def _import_role(module: str) -> str | None:
    """Return the src-package role of an imported module, or None for stdlib/third-party."""
    if not module.startswith("src."):
        return None
    parts = module.split(".", 2)
    return parts[1] if len(parts) >= 2 else None


def _collect_imports(tree: ast.AST) -> list[str]:
    """Return deduplicated list of imported module names, including lazy ones."""
    seen: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            seen.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                seen.add(alias.name)
    return sorted(seen)


def _load_baseline() -> set[str]:
    if not _BASELINE_PATH.exists():
        return set()
    return set(json.loads(_BASELINE_PATH.read_text()))


def test_dependency_policy() -> None:
    baseline = _load_baseline()
    new_violations: list[str] = []

    for py_file in sorted(_SRC_ROOT.rglob("*.py")):
        rel = py_file.relative_to(_PROJECT_ROOT).as_posix()
        source_role = _file_role(rel)
        if source_role == "unknown":
            continue
        allowed = _ALLOWED.get(source_role, frozenset())

        try:
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
        except SyntaxError:
            continue

        for module in _collect_imports(tree):
            target_role = _import_role(module)
            if target_role is None:
                continue  # stdlib or third-party — always allowed
            if target_role not in allowed:
                key = f"{rel}::{module}"
                if key not in baseline:
                    new_violations.append(key)

    if new_violations:
        formatted = "\n".join(f"  {v}" for v in sorted(new_violations))
        raise AssertionError(
            f"New dependency-policy violations (add to baseline to acknowledge):\n{formatted}"
        )
