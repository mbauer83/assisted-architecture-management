"""Connection-type guidance: specialization enumeration plus, when a repo root is known,
the EFFECTIVE merged metadata schema each (connection-type, specialization) pair authors
against.

Entities get their effective schema from ``GET /api/entity-schemata``; connections have no
such endpoint, so the authoring-guidance payload carries theirs. Both transports (REST and
MCP) call the same builder, so neither can offer a shape the other lacks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.application.artifact_schema import (
    attribute_descriptors,
    compute_effective_connection_metadata_schema,
    schema_all_properties,
    schema_required_properties,
)
from src.domain.profile_registry import ProfileRegistry
from src.domain.specializations import SpecializationCatalog, SpecializationInfo


def serialize_specialization(info: SpecializationInfo) -> dict[str, object]:
    entry: dict[str, object] = {
        "slug": info.slug,
        "name": info.name,
        "description": info.description,
        "create_when": info.create_when,
        "never_create_when": info.never_create_when,
    }
    if info.notation.icon or info.notation.color:
        notation = {k: v for k, v in (("icon", info.notation.icon), ("color", info.notation.color)) if v}
        entry["notation"] = notation
    return entry


def connection_type_guidance(
    specialization_catalog: SpecializationCatalog,
    *,
    profile_registry: ProfileRegistry = ProfileRegistry.empty(),
    repo_root: Path | None = None,
    connection_type_names: tuple[str, ...],
) -> list[dict[str, object]]:
    """Per-connection-type specialization enumeration, restricted to types that have any.

    Unlike entity types (each already gets its own guidance entry, so an empty
    ``specializations`` list costs nothing extra), connection types have no other guidance
    entry here; listing every known connection type regardless of specialization would add a
    long, mostly-empty block to every guidance response.

    With ``repo_root``, each entry also carries the effective metadata schema: the
    type-level one under ``metadata_schema``, and each specialization's merged schema under
    its own ``metadata_schema``, alongside ``quarantined`` — the same derived read of the
    same conflicts channel the entity schema endpoint exposes, so an authoring surface can
    disable a pair it must not write.
    """
    entries: list[dict[str, object]] = []
    for name in connection_type_names:
        specializations = specialization_catalog.for_type("connection", name)
        if not specializations:
            continue
        entry: dict[str, object] = {
            "name": name,
            "specializations": [
                _specialization_entry(info, name, specialization_catalog, profile_registry, repo_root)
                for info in specializations
            ],
        }
        if repo_root is not None:
            entry["metadata_schema"] = _schema_block(
                repo_root, name, "", specialization_catalog, profile_registry
            )
        entries.append(entry)
    return entries


def _specialization_entry(
    info: SpecializationInfo,
    connection_type: str,
    specialization_catalog: SpecializationCatalog,
    profile_registry: ProfileRegistry,
    repo_root: Path | None,
) -> dict[str, object]:
    entry = serialize_specialization(info)
    if repo_root is not None:
        entry["metadata_schema"] = _schema_block(
            repo_root, connection_type, info.slug, specialization_catalog, profile_registry
        )
    return entry


def _schema_block(
    repo_root: Path,
    connection_type: str,
    specialization_slug: str,
    specialization_catalog: SpecializationCatalog,
    profile_registry: ProfileRegistry,
) -> dict[str, Any]:
    schema, conflicts = compute_effective_connection_metadata_schema(
        repo_root,
        connection_type,
        [specialization_slug],
        specialization_catalog=specialization_catalog,
        profile_registry=profile_registry,
    )
    return {
        "schema": schema,
        "properties": schema_all_properties(schema) if schema else [],
        "required": schema_required_properties(schema) if schema else [],
        "descriptors": attribute_descriptors(schema) if schema else {},
        "conflicts": conflicts,
        # Derived from the SAME conflicts channel, never a parallel one: true means the
        # write boundary refuses this pair.
        "quarantined": bool(conflicts),
    }
