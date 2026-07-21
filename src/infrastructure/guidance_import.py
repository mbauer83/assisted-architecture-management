"""Fetch, validate, and filter a guidance-cache source document for arch-import-guidance
(D2/D3/D3a). Pure validation/filtering here; network+file I/O and CLI wiring live in
``src/infrastructure/cli/arch_import_guidance.py``.
"""

from __future__ import annotations

import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from src.domain.guidance import ConceptKind
from src.domain.guidance_hierarchy_source import resolve_guidance_hierarchy
from src.domain.module_registry import ModuleRegistry
from src.domain.ontology_protocol import OntologyModule
from src.infrastructure.app_bootstrap import resolve_meta_ontology_module

_MAX_SOURCE_BYTES = 5_000_000
_FETCH_TIMEOUT_S = 10.0
# Only the latest format is imported. An older cache is migrated offline by
# ``arch-repair upgrade`` (guidance_cache target), never read as-is.
_SUPPORTED_GUIDANCE_FORMAT = 2
_V1_SLOT_KEYS = ("entity_types", "connection_types")


class GuidanceImportError(Exception):
    """Raised for any fetch, schema, or (in --strict mode) key-validation failure."""


@dataclass(frozen=True)
class GuidanceImportSummary:
    """One meta-ontology alias's outcome, in the shape written to the provenance sidecar."""

    alias: str
    matched_keys: tuple[str, ...] = ()
    unmatched_keys: tuple[str, ...] = field(default_factory=tuple)
    filtered_document: dict[str, object] = field(default_factory=dict)


def fetch_source(source: str, *, allow_http: bool) -> bytes:
    """Fetch ``source`` (an https/http URL or local path). HTTPS-only unless ``allow_http``.

    Enforces a timeout and a size cap; never trusts a Content-Length header alone.
    """
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        if parsed.scheme == "http" and not allow_http:
            raise GuidanceImportError(f"refusing plain-HTTP source {source!r} — pass --allow-http to override")
        req = urllib.request.Request(source, headers={"User-Agent": "arch-import-guidance/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT_S) as resp:  # noqa: S310
                data = resp.read(_MAX_SOURCE_BYTES + 1)
        except OSError as exc:
            raise GuidanceImportError(f"failed to fetch {source!r}: {exc}") from exc
    else:
        path = Path(source)
        if not path.is_file():
            raise GuidanceImportError(f"source file not found: {source}")
        data = path.read_bytes()

    if len(data) > _MAX_SOURCE_BYTES:
        raise GuidanceImportError(f"source {source!r} exceeds the {_MAX_SOURCE_BYTES}-byte size cap")
    return data


def validate_schema(data: object) -> dict[str, object]:
    """Validate the top-level v1 guidance-cache shape; raise on anything else."""
    if not isinstance(data, dict):
        raise GuidanceImportError("guidance document must be a YAML mapping")
    fmt = data.get("guidance_format")
    if fmt != _SUPPORTED_GUIDANCE_FORMAT:
        raise GuidanceImportError(
            f"unsupported guidance_format {fmt!r} (expected {_SUPPORTED_GUIDANCE_FORMAT}). "
            "Only the latest format is imported; migrate an already-imported older cache with "
            "`arch-repair upgrade`."
        )
    meta_ontologies = data.get("meta_ontologies")
    if not isinstance(meta_ontologies, dict):
        raise GuidanceImportError("guidance document is missing a 'meta_ontologies' mapping")
    return data


def select_aliases(data: dict[str, object], module: str | None) -> dict[str, object]:
    """Return the requested alias's data, or every alias present when ``module`` is omitted.

    ``data`` must already have passed :func:`validate_schema`, which guarantees
    ``meta_ontologies`` is a mapping.
    """
    meta_ontologies = cast(dict[str, object], data["meta_ontologies"])
    if module is None:
        return meta_ontologies
    if module not in meta_ontologies:
        raise GuidanceImportError(f"module alias {module!r} not present in source document")
    return {module: meta_ontologies[module]}


_SECTION_CONCEPT_KINDS: dict[str, ConceptKind] = {"entity_types": "entity", "connection_types": "connection"}


def _known_type_names(om: OntologyModule, section: str) -> frozenset[str]:
    return frozenset(str(t) for t in (om.entity_types if section == "entity_types" else om.connection_types))


def _known_specialization_slugs(om: OntologyModule, section: str, type_name: str) -> frozenset[str]:
    kind = _SECTION_CONCEPT_KINDS[section]
    return frozenset(spec.slug for spec in om.specialization_catalog.for_type(kind, type_name))


def _filter_type_entry(
    om: OntologyModule, section: str, type_name: str, type_data: Mapping[str, object], *, key_prefix: str
) -> tuple[dict[str, object], list[str], list[str]]:
    """Filter one type's guidance entry, validating its optional ``specializations`` slugs
    against the target module's SpecializationCatalog when present."""
    matched = [key_prefix]
    unmatched: list[str] = []
    filtered: dict[str, object] = {k: v for k, v in type_data.items() if k != "specializations"}

    specializations = type_data.get("specializations")
    if isinstance(specializations, Mapping):
        known_slugs = _known_specialization_slugs(om, section, type_name)
        filtered_specializations: dict[str, object] = {}
        for slug, slug_data in specializations.items():
            slug_key = f"{key_prefix}.specializations.{slug}"
            if slug in known_slugs:
                matched.append(slug_key)
                filtered_specializations[str(slug)] = slug_data
            else:
                unmatched.append(slug_key)
        if filtered_specializations:
            filtered["specializations"] = filtered_specializations

    return filtered, matched, unmatched


def _filter_context_levels(
    om: OntologyModule, alias_data: Mapping[str, object]
) -> tuple[dict[str, object], list[str], list[str]]:
    """Validate broader-level context maps (e.g. ``domain:``) against the module's derived
    guidance hierarchy: the top-level key must be a declared level and each node id a declared
    node at that level. The v1 type slots are validated separately; anything else is a level
    map. Returns the filtered sections plus matched/unmatched key lists (``<level>.<node>``).
    """
    hierarchy = resolve_guidance_hierarchy(om)
    matched: list[str] = []
    unmatched: list[str] = []
    filtered: dict[str, object] = {}
    for level_id, section in alias_data.items():
        if not isinstance(level_id, str) or level_id in _V1_SLOT_KEYS or not isinstance(section, Mapping):
            continue
        if not hierarchy.is_declared_level(level_id):
            unmatched.append(f"{level_id} (undeclared guidance level)")
            continue
        valid_nodes = {node.node_id for node in hierarchy.nodes if node.level_id == level_id}
        filtered_section: dict[str, object] = {}
        for node_id, node_data in section.items():
            key = f"{level_id}.{node_id}"
            if node_id in valid_nodes:
                matched.append(key)
                filtered_section[str(node_id)] = node_data
            else:
                unmatched.append(key)
        if filtered_section:
            filtered[level_id] = filtered_section
    return filtered, matched, unmatched


def filter_alias_document(
    alias: str, alias_data: object, registry: ModuleRegistry, *, strict: bool
) -> GuidanceImportSummary:
    """Validate one alias's entity/connection type keys — and, for each type, its optional
    per-specialization guidance slugs — against the active registry's module (including its
    SpecializationCatalog when the module carries one). Unknown keys are listed; they are
    dropped from the filtered document unless ``strict`` is set, in which case any unknown
    key aborts the whole import.
    """
    om = resolve_meta_ontology_module(alias, registry)
    if om is None:
        raise GuidanceImportError(f"module alias {alias!r} is not a registered, active ontology")
    if not isinstance(alias_data, dict):
        raise GuidanceImportError(f"guidance entry for {alias!r} must be a mapping")

    matched: list[str] = []
    unmatched: list[str] = []
    filtered: dict[str, object] = {}
    for section in ("entity_types", "connection_types"):
        section_data = alias_data.get(section)
        if not isinstance(section_data, dict):
            continue
        known = _known_type_names(om, section)
        filtered_section: dict[str, object] = {}
        for type_name, type_data in section_data.items():
            key = f"{section}.{type_name}"
            if type_name not in known:
                unmatched.append(key)
                continue
            if not isinstance(type_data, Mapping):
                matched.append(key)
                filtered_section[type_name] = type_data
                continue
            filtered_entry, entry_matched, entry_unmatched = _filter_type_entry(
                om, section, type_name, type_data, key_prefix=key
            )
            matched.extend(entry_matched)
            unmatched.extend(entry_unmatched)
            filtered_section[type_name] = filtered_entry
        if filtered_section:
            filtered[section] = filtered_section

    context_filtered, context_matched, context_unmatched = _filter_context_levels(om, alias_data)
    matched.extend(context_matched)
    unmatched.extend(context_unmatched)
    filtered.update(context_filtered)

    if unmatched and strict:
        raise GuidanceImportError(f"unknown guidance keys for {alias!r} (--strict): {sorted(unmatched)}")

    return GuidanceImportSummary(
        alias=alias,
        matched_keys=tuple(matched),
        unmatched_keys=tuple(unmatched),
        filtered_document={"guidance_format": _SUPPORTED_GUIDANCE_FORMAT, "meta_ontologies": {alias: filtered}},
    )
