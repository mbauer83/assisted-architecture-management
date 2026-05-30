"""type_guidance.py — Focused modeling guidelines for entity types and diagram types.

Returns create_when / never_create_when guidance plus permitted relationships for a
selectable subset of ArchiMate domains or entity types; or when_to_use / when_not_to_use,
diagram_entities_schema, own_entity_types, and optional puml_notes guidance for a
specific diagram type.

Progressive discovery:
  - Pass diagram_type to get authoring guidance for one diagram type.
  - Pass filter to get detailed guidance for specific entity types or domains.
  - Pass both to get diagram type guidance alongside filtered entity type guidance.
  - Pass neither to get guidance for all entity types (large; prefer filtering).
"""

from __future__ import annotations

from functools import lru_cache

from src.domain.connection_ontology import classify_connections
from src.domain.module_types import EntityTypeName
from src.domain.ontology_protocol import DiagramTypeWriteGuidance


@lru_cache(maxsize=1)
def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry()


def get_type_guidance(
    filter: list[str] | None = None,  # noqa: A002
    diagram_type: str | None = None,
) -> dict[str, object]:
    """Return focused modeling guidelines for the requested entity types, domains, or diagram type.

    ``filter`` accepts entity-type names (e.g. ``["requirement", "goal"]``) or domain names
    (e.g. ``["motivation", "strategy"]``).  Resolved unambiguously: if every item matches a
    known entity-type name it is an entity-type filter; otherwise a domain filter.

    ``diagram_type`` selects one diagram type (e.g. ``"archimate-motivation"`` or ``"activity"``).
    When provided, the response includes a ``diagram_type_guidance`` block with when_to_use,
    when_not_to_use, accepted_domains, own entity type guidance, and puml_notes.

    Passing both ``diagram_type`` and ``filter`` returns the diagram type block plus entity type
    guidance for the filtered subset.  Omit both to return guidance for all entity types.
    """
    result: dict[str, object] = {}

    if diagram_type is not None:
        diagram_type_mod = _registry().find_diagram_type(diagram_type)
        if diagram_type_mod is None:
            known = sorted(_registry().all_diagram_types().keys())
            return {
                "error": f"Unknown diagram_type {diagram_type!r}.",
                "known_diagram_types": known,
            }
        result["diagram_type_guidance"] = _serialize_diagram_type_guidance(
            diagram_type, diagram_type_mod.write_guidance()
        )

    if filter is not None or diagram_type is None:
        entity_section = _entity_type_guidance(filter)
        result.update(entity_section)

    return result


def _serialize_diagram_type_guidance(
    name: str,
    g: DiagramTypeWriteGuidance,
) -> dict[str, object]:
    out: dict[str, object] = {
        "name": name,
        "when_to_use": g.when_to_use,
        "when_not_to_use": g.when_not_to_use,
    }
    if g.accepted_domains:
        out["accepted_domains"] = list(g.accepted_domains)
    if g.diagram_entities_schema is not None:
        out["diagram_entities_schema"] = g.diagram_entities_schema
    if g.own_entity_types:
        out["own_entity_types"] = [_serialize_own_entity_type(oe) for oe in g.own_entity_types]
    if g.puml_notes:
        out["puml_notes"] = list(g.puml_notes)
    return out


def _serialize_own_entity_type(oe) -> dict[str, object]:  # type: ignore[no-untyped-def]
    entry: dict[str, object] = {
        "entity_type": oe.entity_type,
        "label": oe.label,
        "min": oe.min,
        "max": oe.max,
        "element_classes": list(oe.element_classes),
        "create_when": oe.create_when,
        "never_create_when": oe.never_create_when,
    }
    if oe.permitted_mappings.has_any():
        mapping_entry: dict[str, object] = {
            "entity_types": list(oe.permitted_mappings.entity_types),
            "entity_classes": list(oe.permitted_mappings.entity_classes),
        }
        if oe.permitted_mappings.sources:
            mapping_entry["sources"] = [
                {
                    "ontology": source.ontology,
                    "entity_type": source.entity_type,
                    "entity_class": source.entity_class,
                    "transparent": source.transparent,
                }
                for source in oe.permitted_mappings.sources
            ]
        entry["permitted_mappings"] = mapping_entry
    managed: dict[str, str] = {"id": "required"}
    if oe.managed_fields is not None:
        managed.update(dict(oe.managed_fields))
    elif oe.permitted_mappings.has_any():
        managed["label"] = "optional — falls back to linked model entity name"
        managed["entity_id"] = "required" if oe.mapping_required else "optional — links to a model entity"
    else:
        managed["label"] = "required"
    entry["managed_fields"] = managed
    if oe.properties:
        entry["domain_properties"] = {p.name: {"required": p.required, **p.schema} for p in oe.properties}
    return entry


def _entity_type_guidance(
    filter: list[str] | None,  # noqa: A002
) -> dict[str, object]:
    all_infos = _registry().all_entity_types()

    if filter is None:
        selected = list(all_infos.values())
        include_domain = True
        domain_context: list[str] | None = None
    else:
        entity_type_hits = [n for n in filter if n in all_infos]
        if len(entity_type_hits) == len(filter):
            selected = [all_infos[EntityTypeName(n)] for n in filter]
            include_domain = True
            domain_context = None
        else:
            unknown_types = [n for n in filter if n not in all_infos]
            domain_set = {d.lower() for d in filter}
            selected = [
                info for info in all_infos.values() if info.hierarchy and info.hierarchy[0].lower() in domain_set
            ]
            if not selected:
                return {
                    "error": (
                        f"No matches found for filter {filter!r}. "
                        "Provide known entity-type names (e.g. 'requirement') "
                        "or domain names (e.g. 'motivation')."
                    ),
                    "unknown": unknown_types,
                }
            include_domain = False
            domain_context = filter

    selected = sorted(
        selected,
        key=lambda x: (x.hierarchy[0] if x.hierarchy else "", x.artifact_type),
    )

    entries: list[dict[str, object]] = []
    for info in selected:
        connections = classify_connections(info.artifact_type)
        entry: dict[str, object] = {
            "name": info.artifact_type,
            "prefix": info.prefix,
        }
        if include_domain:
            entry["domain"] = info.hierarchy[0] if info.hierarchy else ""
        entry["element_classes"] = list(info.element_classes)
        entry["create_when"] = info.create_when
        entry["never_create_when"] = info.never_create_when
        entry["permitted_connections"] = connections
        entries.append(entry)

    out: dict[str, object] = {"entity_types": entries, "total": len(entries)}
    if domain_context:
        out["domains"] = domain_context
    return out
