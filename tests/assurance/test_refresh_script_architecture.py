"""Architecture/dependency contract for the refresh script: it submits typed
bundles through the RefreshSecuritySignals command and NEVER imports a signals
connector (the legacy import_bom/import_vulnerabilities adapters) — the run
lifecycle has exactly one owner."""

from __future__ import annotations

import ast
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "refresh_security_signals.py"

_FORBIDDEN_MODULES = (
    "src.infrastructure.assurance._collocated_signals_connector",
    "src.infrastructure.assurance._security_connector",
)
_FORBIDDEN_NAMES = (
    "SecuritySignalConnector",
    "CollocatedSQLCipherSignalsConnector",
    "SQLiteSecurityConnector",
    "import_bom",
    "import_vulnerabilities",
)


def _all_imports(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def test_script_imports_no_signals_connector() -> None:
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    imports = _all_imports(tree)
    offenders = {
        name for name in imports
        if any(name.startswith(forbidden) for forbidden in _FORBIDDEN_MODULES)
        or any(name.endswith(f".{forbidden}") for forbidden in _FORBIDDEN_NAMES)
    }
    assert offenders == set(), f"the refresh script must not touch connectors: {offenders}"


def test_script_never_references_connector_apis_even_lazily() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    offenders = [name for name in _FORBIDDEN_NAMES if name in source]
    assert offenders == [], f"connector API references found in the script: {offenders}"


_LIFECYCLE_TRANSITIONS = (
    "create_staging_run",
    "populate_run",
    "complete_run",
    "activate_run",
    "fail_run",
)


def test_script_submits_through_the_shared_ingest_boundary() -> None:
    """The script assembles a typed bundle and submits it; the command (reached via
    submit_bundle) owns the lifecycle, so run-id policy and the single-writer
    boundary are not re-invented per surface."""
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "submit_bundle" in source
    assert "assemble_bundle" in source
    assert "RefreshBundle" in source


def test_script_never_drives_lifecycle_transitions_itself() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    offenders = [name for name in _LIFECYCLE_TRANSITIONS if name in source]
    assert offenders == [], f"the script must not drive the run lifecycle: {offenders}"
