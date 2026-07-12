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


@dataclass(frozen=True)
class GuidanceKey:
    """Identifies one guidance slot: a module's entity/connection type, optionally a specialization."""

    module_alias: str
    concept_kind: ConceptKind
    type_name: str
    specialization: str | None = None


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

    def is_empty(self) -> bool:
        return not self.entries

    def get(self, key: GuidanceKey) -> GuidanceEntry | None:
        return self.entries.get(key)


_CONCEPT_SECTIONS: dict[str, ConceptKind] = {"entity_types": "entity", "connection_types": "connection"}


def guidance_overlay_from_mapping(data: Mapping[str, object]) -> GuidanceOverlay:
    """Parse one already-YAML-loaded guidance-cache file (v1 schema) into an overlay.

    Schema: ``meta_ontologies.<alias>.{entity_types,connection_types}.<type>`` carrying
    ``create_when``/``never_create_when`` at the base level and, optionally, the same pair
    per entry under ``specializations.<slug>``. A type entry with only a ``specializations``
    block and no base ``create_when``/``never_create_when`` (the reserved, not-yet-populated
    connection-type base case per D3) does not produce a base-level key — an absent base key
    means "fall back to module-inline text", not "override with empty text". Malformed or
    missing structure is tolerated by omission; schema/key validation against the registry is
    the import CLI's job (WU-B4), not this pure parser's.
    """
    entries: dict[GuidanceKey, GuidanceEntry] = {}
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
    return GuidanceOverlay(entries)


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
