"""Semantic triple validation for ArchiMate NEXT connections.

Checks that each (source_type, connection_type, target_type) triple in an
outgoing file is permitted by the active ontology.  Emits E126 for illegal
triples and W126 as realization-quality guidance.
"""

from __future__ import annotations

from src.application.verification.artifact_verifier_parsing import parse_frontmatter_from_path
from src.application.verification.artifact_verifier_registry import ArtifactRegistry
from src.application.verification.artifact_verifier_types import Issue, Severity, VerificationResult
from src.domain.catalogs import ConnectionSemantics, OntologyCatalog


def _entity_type(registry: ArtifactRegistry, entity_id: str) -> str | None:
    path = registry.find_file_by_id(entity_id)
    if path is None:
        return None
    fm = parse_frontmatter_from_path(path)
    if not isinstance(fm, dict):
        return None
    return str(fm.get("artifact-type", "")) or None


def _permitted(
    connections_catalog: ConnectionSemantics,
    source_type: str,
    conn_type: str,
    target_type: str,
) -> tuple[bool, list[str]]:
    """Return (allowed, alternatives)."""
    allowed_set = set(connections_catalog.permissible_connection_types(source_type, target_type))
    if conn_type in allowed_set:
        return True, []
    return False, sorted(allowed_set)


_REALIZATION = "archimate-realization"
_STRUCTURE_CLASSES = frozenset(
    ["active-structure-element", "internal-active-structure-element", "external-active-structure-element",
     "technology-internal-active-structure-element", "passive-structure-element", "composite-element"]
)
_BEHAVIOR_TARGET = frozenset(["service"])


def _is_structure(ontology_catalog: OntologyCatalog, source_type: str) -> bool:
    return any(source_type in ontology_catalog.entity_types_with_class(cls) for cls in _STRUCTURE_CLASSES)


def check_connection_semantics(
    source_id: str,
    connections: list[tuple[str, str]],
    registry: ArtifactRegistry,
    result: VerificationResult,
    loc: str,
    *,
    connections_catalog: ConnectionSemantics | None = None,
    ontology_catalog: OntologyCatalog | None = None,
) -> None:
    """Validate semantic triples; add E126/W126 issues to result.

    When connections_catalog is None the check is skipped (catalog not injected).
    """
    if connections_catalog is None:
        return

    source_type = _entity_type(registry, source_id)
    if source_type is None:
        return

    for conn_type, target_id in connections:
        target_type = _entity_type(registry, target_id)
        if target_type is None:
            continue

        ok, alternatives = _permitted(connections_catalog, source_type, conn_type, target_type)
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

        if (
            ontology_catalog is not None
            and conn_type == _REALIZATION
            and target_type in _BEHAVIOR_TARGET
            and _is_structure(ontology_catalog, source_type)
        ):
            result.issues.append(
                Issue(
                    Severity.WARNING,
                    "W126",
                    f"Realization misuse: '{source_type}' (structure) cannot directly realize "
                    f"'{target_type}' (behavior). Use a function or process as realizer instead.",
                    loc,
                )
            )
