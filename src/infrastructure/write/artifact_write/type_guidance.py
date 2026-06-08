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

from src.domain.allowed_bindings import serialize_allowed_bindings
from src.domain.module_types import EntityTypeName
from src.domain.ontology_protocol import DiagramTypeWriteGuidance


def pair_connection_guidance(source_type: str, target_type: str) -> dict[str, object]:
    """Return directional pair-legality for (source_type, target_type).

    Derives direction cleanly from ``classify_connections(source_type)`` so that
    outgoing/incoming/symmetric are unambiguous.  Returns a dict with keys:
    ``source``, ``target``, ``outgoing``, ``incoming``, ``symmetric``.
    ``error`` is set when either type is unknown.
    """
    all_types = _registry().all_entity_types()
    unknown = [t for t in (source_type, target_type) if t not in all_types]
    if unknown:
        return {
            "error": f"Unknown entity type(s): {unknown!r}. Provide concrete type names.",
            "known_types": sorted(all_types.keys()),
        }
    c = _classify_connections(source_type)
    return {
        "source": source_type,
        "target": target_type,
        "outgoing": sorted(c["outgoing"].get(target_type, [])),
        "incoming": sorted(c["incoming"].get(target_type, [])),
        "symmetric": sorted(c["symmetric"].get(target_type, [])),
    }


@lru_cache(maxsize=1)
def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry()


def _classify_connections(source_type: str) -> dict[str, dict[str, list[str]]]:
    """Classify permissible connections into outgoing/incoming/symmetric."""
    from src.domain.module_types import ConnectionTypeName  # noqa: PLC0415

    prs = _registry().aggregated_permitted_relationships()
    src = EntityTypeName(source_type)
    outgoing: dict[str, list[str]] = {}
    incoming: dict[str, list[str]] = {}
    symmetric: dict[str, list[str]] = {}

    for tgt, ct in prs.by_source().get(src, []):
        ct_info = _registry().find_connection_type(ConnectionTypeName(str(ct)))
        if ct_info is not None and ct_info.symmetric:
            symmetric.setdefault(str(tgt), []).append(str(ct))
        else:
            outgoing.setdefault(str(tgt), []).append(str(ct))

    for src2, ct in prs.by_target().get(src, []):
        ct_info = _registry().find_connection_type(ConnectionTypeName(str(ct)))
        if ct_info is not None and ct_info.symmetric:
            if str(src2) not in symmetric:
                symmetric.setdefault(str(src2), []).append(str(ct))
        else:
            incoming.setdefault(str(src2), []).append(str(ct))

    return {"outgoing": outgoing, "incoming": incoming, "symmetric": symmetric}


def get_type_guidance(
    filter: list[str] | None = None,  # noqa: A002
    diagram_type: str | None = None,
    target: str | None = None,
) -> dict[str, object]:
    """Return focused modeling guidelines for the requested entity types, domains, or diagram type.

    ``filter`` accepts entity-type names (e.g. ``["requirement", "goal"]``) or domain names
    (e.g. ``["motivation", "strategy"]``).  Resolved unambiguously: if every item matches a
    known entity-type name it is an entity-type filter; otherwise a domain filter.

    ``diagram_type`` selects one diagram type (e.g. ``"archimate-motivation"`` or ``"activity"``).
    When provided, the response includes a ``diagram_type_guidance`` block with when_to_use,
    when_not_to_use, accepted_domains, own entity type guidance, and puml_notes.

    ``target`` enables pair-legality guidance: when set, ``filter`` must contain exactly one
    concrete entity-type name (the source).  The response gains a ``pair_guidance`` block with
    outgoing/incoming/symmetric connection types for the (source, target) pair.  A domain
    filter, multiple source types, or ``target`` without ``filter`` is a validation error.

    Passing both ``diagram_type`` and ``filter`` returns the diagram type block plus entity type
    guidance for the filtered subset.  Omit both to return guidance for all entity types.
    """
    result: dict[str, object] = {}

    if target is not None:
        if filter is None:
            return {"error": "target requires filter to contain exactly one concrete entity type name."}
        all_types = _registry().all_entity_types()
        concrete = [t for t in filter if t in all_types]
        if len(concrete) != 1 or len(filter) != 1:
            return {
                "error": (
                    "target requires filter with exactly one concrete entity type (e.g. ['requirement']). "
                    "Domain filters and multiple types are not allowed."
                ),
                "filter_received": filter,
            }
        result["pair_guidance"] = pair_connection_guidance(concrete[0], target)

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
    if g.allowed_bindings is not None:
        out["allowed_bindings"] = serialize_allowed_bindings(g.allowed_bindings)
    return out


def _serialize_own_entity_type(oe) -> dict[str, object]:  # type: ignore[no-untyped-def]
    entry: dict[str, object] = {
        "entity_type": oe.entity_type,
        "label": oe.label,
        "min": oe.min,
        "max": oe.max,
        "classes": list(oe.classes),
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
        connections = _classify_connections(info.artifact_type)
        entry: dict[str, object] = {
            "name": info.artifact_type,
            "prefix": info.prefix,
        }
        if include_domain:
            entry["domain"] = info.hierarchy[0] if info.hierarchy else ""
        entry["classes"] = list(info.classes)
        entry["create_when"] = info.create_when
        entry["never_create_when"] = info.never_create_when
        entry["permitted_connections"] = connections
        entries.append(entry)

    out: dict[str, object] = {"entity_types": entries, "total": len(entries)}
    if domain_context:
        out["domains"] = domain_context
    return out
