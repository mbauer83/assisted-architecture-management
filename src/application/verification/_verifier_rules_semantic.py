"""Semantic triple validation for ArchiMate NEXT connections.

Checks that each (source_type, connection_type, target_type) triple in an
outgoing file is permitted by the active ontology.  Emits E126 for illegal
triples and W126 as realization-quality guidance.
"""

from __future__ import annotations

from src.application.verification.artifact_verifier_parsing import parse_frontmatter_from_path
from src.application.verification.artifact_verifier_registry import ArtifactRegistry
from src.application.verification.artifact_verifier_types import Issue, Severity, VerificationResult


def _entity_type(registry: ArtifactRegistry, entity_id: str) -> str | None:
    path = registry.find_file_by_id(entity_id)
    if path is None:
        return None
    fm = parse_frontmatter_from_path(path)
    if not isinstance(fm, dict):
        return None
    return str(fm.get("artifact-type", "")) or None


def _permitted(source_type: str, conn_type: str, target_type: str) -> tuple[bool, list[str]]:
    """Return (allowed, alternatives).  Handles symmetric connections."""
    from src.infrastructure.app_bootstrap import build_runtime_catalogs, get_module_registry  # noqa: PLC0415

    allowed_set = set(
        build_runtime_catalogs(get_module_registry()).connections.permissible_connection_types(
            source_type, target_type
        )
    )
    if conn_type in allowed_set:
        return True, []
    return False, sorted(allowed_set)


_REALIZATION = "archimate-realization"
_STRUCTURE_CLASSES = frozenset(
    ["active-structure-element", "internal-active-structure-element", "external-active-structure-element",
     "technology-internal-active-structure-element", "passive-structure-element", "composite-element"]
)
_BEHAVIOR_TARGET = frozenset(["service"])


def _is_structure(source_type: str) -> bool:
    from src.domain.module_types import ElementClassName, EntityTypeName  # noqa: PLC0415
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    reg = get_module_registry()
    for cls in _STRUCTURE_CLASSES:
        if EntityTypeName(source_type) in reg.entity_types_with_class(ElementClassName(cls)):
            return True
    return False


def check_connection_semantics(
    source_id: str,
    connections: list[tuple[str, str]],
    registry: ArtifactRegistry,
    result: VerificationResult,
    loc: str,
) -> None:
    """Validate semantic triples; add E126/W126 issues to result."""
    source_type = _entity_type(registry, source_id)
    if source_type is None:
        return

    for conn_type, target_id in connections:
        target_type = _entity_type(registry, target_id)
        if target_type is None:
            continue

        ok, alternatives = _permitted(source_type, conn_type, target_type)
        if ok:
            continue

        alt_str = ", ".join(alternatives) if alternatives else "none"
        result.issues.append(
            Issue(
                Severity.ERROR,
                "E126",
                f"Relationship '{conn_type}' is not permitted from "
                f"'{source_type}' to '{target_type}'. "
                f"Permitted alternatives: {alt_str}.",
                loc,
            )
        )

        if conn_type == _REALIZATION and target_type in _BEHAVIOR_TARGET and _is_structure(source_type):
            result.issues.append(
                Issue(
                    Severity.WARNING,
                    "W126",
                    f"Realization misuse: '{source_type}' (structure) cannot directly realize "
                    f"'{target_type}' (behavior). Use a function or process as realizer instead.",
                    loc,
                )
            )
