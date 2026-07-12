"""Viewpoint enumeration + scope summary for ``artifact_authoring_guidance`` (WU-E6).

Split out of ``type_guidance.py`` to keep that file within the LoC policy — this is a
self-contained concern (purely descriptive viewpoint metadata, companion plan §8) with no
call-graph coupling to the entity/diagram-type guidance functions it lives alongside there.
"""

from __future__ import annotations

from src.domain.concept_scope import ConceptScope
from src.domain.viewpoints import ViewpointCatalog, ViewpointDefinition


def summarize_scope(scope: ConceptScope) -> dict[str, object]:
    """Compact scope summary for guidance/enumeration surfaces — not the full serialized
    ``ConceptScope`` grammar (class/hierarchy predicates, endpoint rules), just enough for an
    agent to judge applicability at a glance: whether the viewpoint is unrestricted, and if not,
    which entity/connection types it admits."""
    if scope == ConceptScope.unrestricted():
        return {"unrestricted": True}
    summary: dict[str, object] = {"unrestricted": False}
    if scope.entity_types is not None:
        summary["entity_types"] = sorted(str(t) for t in scope.entity_types)
    if scope.connection_types is not None:
        summary["connection_types"] = sorted(str(t) for t in scope.connection_types)
    return summary


def _serialize_viewpoint(v: ViewpointDefinition) -> dict[str, object]:
    return {
        "slug": v.slug,
        "version": v.version,
        "name": v.name,
        "description": v.description,
        "purpose": list(v.purpose),
        "content": list(v.content),
        "scope": summarize_scope(v.scope),
    }


def viewpoint_guidance(catalog: ViewpointCatalog) -> list[dict[str, object]]:
    """Enumerate the effective merged viewpoint catalog so an agent can discover applicable
    viewpoints from the same guidance call it already makes for entity/diagram-type guidance —
    purely descriptive metadata (companion plan §8) plus a scope summary; query/presentation
    content is not surfaced here (that is WU-E7a's `artifact_query_viewpoint list` job, once a
    definition actually carries a query)."""
    return [_serialize_viewpoint(v) for v in sorted(catalog.entries, key=lambda v: v.slug)]
