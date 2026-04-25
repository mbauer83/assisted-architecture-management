"""type_guidance.py — Focused modeling guidelines for entity types.

Returns create_when / never_create_when guidance plus permitted relationships
for a selectable subset of ArchiMate domains or entity types.
"""

from __future__ import annotations

from src.common.connection_ontology import classify_connections
from src.common.ontology_loader import ENTITY_TYPES


def get_type_guidance(
    filter: list[str] | None = None,  # noqa: A002
) -> dict[str, object]:
    """Return focused modeling guidelines for the requested entity types or domains.

    ``filter`` accepts a list of either entity-type names (e.g. ``["requirement",
    "goal"]``) or domain names (e.g. ``["Motivation", "Strategy"]``).  The items
    are resolved unambiguously: if every item matches a known entity-type name the
    filter is treated as an entity-type filter; otherwise it is treated as a domain
    filter.  Omit ``filter`` (or pass ``None``) to return guidance for all types.

    - Entity-type filter → ``archimate_domain`` (domain display name) included per entry.
    - Domain filter → ``archimate_domain`` omitted (it equals the requested domain).
    - No filter → ``archimate_domain`` included (types span all domains).
    """
    all_infos = ENTITY_TYPES

    if filter is None:
        selected = list(all_infos.values())
        include_domain = True
        domain_context: list[str] | None = None
    else:
        # Determine mode: entity-type names or domain names?
        entity_type_hits = [n for n in filter if n in all_infos]
        if len(entity_type_hits) == len(filter):
            # Every name is a known entity type
            selected = [all_infos[n] for n in filter]
            include_domain = True
            domain_context = None
        else:
            # Treat as domain filter (case-insensitive match on domain_dir)
            unknown_types = [n for n in filter if n not in all_infos]
            domain_set = {d.lower() for d in filter}
            selected = [
                info for info in all_infos.values() if info.domain_dir.lower() in domain_set
            ]
            if not selected:
                return {
                    "error": (
                        f"No matches found for filter {filter!r}. "
                        "Provide known entity-type names (e.g. 'requirement') "
                        "or domain names (e.g. 'Motivation')."
                    ),
                    "unknown": unknown_types,
                }
            include_domain = False
            domain_context = filter

    selected = sorted(selected, key=lambda x: (x.domain_dir, x.artifact_type))

    entries: list[dict[str, object]] = []
    for info in selected:
        connections = classify_connections(info.artifact_type)
        entry: dict[str, object] = {
            "name": info.artifact_type,
            "prefix": info.prefix,
        }
        if include_domain:
            entry["archimate_domain"] = info.domain_dir.capitalize()
        entry["element_classes"] = list(info.element_classes)
        entry["create_when"] = info.create_when
        entry["never_create_when"] = info.never_create_when
        entry["permitted_connections"] = connections
        entries.append(entry)

    result: dict[str, object] = {"entity_types": entries, "total": len(entries)}
    if domain_context:
        result["domains"] = domain_context
    return result
