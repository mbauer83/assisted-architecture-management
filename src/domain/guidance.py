"""Guidance overlay domain types (D2/D3): imported authoring help, never a governance tier.

Guidance text (``create_when``/``never_create_when``) ships empty in ontology modules for
license reasons and is optionally restored at bootstrap from one deployment-level,
out-of-repo cache (never per engagement/enterprise repo). This module only defines the
overlay shape and parsing; loading the cache and threading the result into
``EntityTypeInfo`` is application/infrastructure wiring (WU-B2+). Guidance authored directly
in committed declarations (e.g. specialization guidance in ``.arch-repo/specializations.yaml``)
does not flow through ``GuidanceOverlay`` at all, so it is never at risk of being overridden
by an imported cache.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

ConceptKind = Literal["entity", "connection"]

# v1 slot keys, reserved: a broader guidance level whose id happened to match one of these
# would be read as a v1 type slot, not a context map. Level ids are singular level names
# (``domain``), so this only guards against an accidental collision.
_V1_SLOT_KEYS = frozenset({"entity_types", "connection_types"})


@dataclass(frozen=True)
class GuidanceKey:
    """Identifies one guidance slot: a module's entity/connection type, optionally a specialization."""

    module_alias: str
    concept_kind: ConceptKind
    type_name: str
    specialization: str | None = None


@dataclass(frozen=True)
class GuidanceContextKey:
    """Identifies one broader-level context slot: a module's guidance level and a node in it
    (e.g. the ``domain`` level's ``motivation`` node). Leaf-level guidance uses :class:`GuidanceKey`.
    """

    module_alias: str
    level_id: str
    node_id: str


@dataclass(frozen=True)
class GuidanceEntry:
    """One resolved guidance text pair."""

    create_when: str
    never_create_when: str


@dataclass(frozen=True)
class GuidanceOverlay:
    """Immutable guidance lookup, keyed by :class:`GuidanceKey`.

    An empty overlay is a no-op: every lookup misses, so callers keep whatever text the
    ontology module shipped inline. Keys absent from a given layer pass through unchanged;
    they are not errors.
    """

    entries: Mapping[GuidanceKey, GuidanceEntry] = field(default_factory=dict)
    context_entries: Mapping[GuidanceContextKey, str] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.entries and not self.context_entries

    def get(self, key: GuidanceKey) -> GuidanceEntry | None:
        return self.entries.get(key)

    def context_for(self, key: GuidanceContextKey) -> str | None:
        return self.context_entries.get(key)


_CONCEPT_SECTIONS: dict[str, ConceptKind] = {"entity_types": "entity", "connection_types": "connection"}


def guidance_overlay_from_mapping(data: Mapping[str, object]) -> GuidanceOverlay:
    """Parse one already-YAML-loaded guidance-cache file into an overlay.

    Two kinds of content under ``meta_ontologies.<alias>``:

    * **Type slots** — ``{entity_types,connection_types}.<type>`` carrying ``create_when``/
      ``never_create_when`` at the base level and, optionally, the same pair per
      ``specializations.<slug>``. An absent base key means "fall back to module-inline text",
      not "override with empty text".
    * **Broader-level context** — every *other* top-level map (e.g. ``domain:``) is a guidance
      level keyed by its own id, holding ``<node>: {context: ...}``. The level/node keys were
      already validated against the module's hierarchy at import (``--strict``), so the runtime
      cache is clean; this parser reads them without needing the hierarchy (which is derived
      from the very module being built — a cycle it must not depend on). Composition along the
      ancestry path happens later, at serving time.

    Malformed/missing structure is tolerated by omission.
    """
    entries: dict[GuidanceKey, GuidanceEntry] = {}
    context_entries: dict[GuidanceContextKey, str] = {}
    meta_ontologies = data.get("meta_ontologies")
    if not isinstance(meta_ontologies, Mapping):
        return GuidanceOverlay()
    for alias, module_data in meta_ontologies.items():
        if not isinstance(alias, str) or not isinstance(module_data, Mapping):
            continue
        for section, kind in _CONCEPT_SECTIONS.items():
            concept_map = module_data.get(section)
            if not isinstance(concept_map, Mapping):
                continue
            for type_name, type_data in concept_map.items():
                if not isinstance(type_name, str) or not isinstance(type_data, Mapping):
                    continue
                entries.update(_entries_for_type(alias, kind, type_name, type_data))
        context_entries.update(_context_entries_for_alias(alias, module_data))
    return GuidanceOverlay(entries, context_entries)


def _context_entries_for_alias(alias: str, module_data: Mapping[str, object]) -> dict[GuidanceContextKey, str]:
    """Read every broader-level ``<node>: {context: ...}`` map (any top-level key that is not a
    type slot) from one alias's document. The key is the guidance level id."""
    out: dict[GuidanceContextKey, str] = {}
    for level_id, section in module_data.items():
        if not isinstance(level_id, str) or level_id in _V1_SLOT_KEYS or not isinstance(section, Mapping):
            continue
        for node_id, node_data in section.items():
            if not isinstance(node_id, str) or not isinstance(node_data, Mapping):
                continue
            context = node_data.get("context")
            if isinstance(context, str) and context.strip():
                out[GuidanceContextKey(alias, level_id, node_id)] = context.strip()
    return out


def _entry_from_mapping(data: Mapping[str, object]) -> GuidanceEntry:
    return GuidanceEntry(
        create_when=str(data.get("create_when", "")),
        never_create_when=str(data.get("never_create_when", "")),
    )


def _entries_for_type(
    alias: str, kind: ConceptKind, type_name: str, data: Mapping[str, object]
) -> dict[GuidanceKey, GuidanceEntry]:
    out: dict[GuidanceKey, GuidanceEntry] = {}
    if "create_when" in data or "never_create_when" in data:
        out[GuidanceKey(alias, kind, type_name)] = _entry_from_mapping(data)
    specializations = data.get("specializations")
    if isinstance(specializations, Mapping):
        for slug, spec_data in specializations.items():
            if isinstance(slug, str) and isinstance(spec_data, Mapping):
                out[GuidanceKey(alias, kind, type_name, slug)] = _entry_from_mapping(spec_data)
    return out
