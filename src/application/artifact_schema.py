"""Configurable JSON Schema loading for frontmatter and attribute validation.

Schema files are stored in ``.arch-repo/schemata/`` within a repository root.

File conventions
----------------
- ``frontmatter.{file-type}.schema.json``  — entity, outgoing, diagram
- ``attributes.{artifact-type}.schema.json`` — per entity-type base attribute schema
- ``attributes.{artifact-type}.{specialization-slug}.schema.json`` — schema attached to one
  specialization of that entity type (D13); merges into the base schema for entities
  carrying that specialization; orphaned (no matching declared specialization) is a
  verifier warning, never silently ignored.
- ``connection-metadata.{connection-type}.schema.json`` — per connection-type metadata

Default behaviour: when no schema file exists for a given scope/type,
validation is skipped (free schema).
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import jsonschema  # type: ignore[import-untyped]

from src.domain.profiles import (
    compile_profile_schema,
    merge_property_schemas,
    profile_from_inline_attributes,
)
from src.domain.specializations import SpecializationCatalog

SCHEMATA_DIR = ".arch-repo/schemata"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_frontmatter_schema(repo_root: Path, file_type: str) -> dict[str, Any] | None:
    """Load the frontmatter JSON Schema for *file_type* (entity, outgoing, diagram).

    Returns ``None`` when no schema file exists (free schema — skip validation).
    """
    return _load_schema_file(repo_root, f"frontmatter.{file_type}.schema.json")


def load_attribute_schema(repo_root: Path, artifact_type: str) -> dict[str, Any] | None:
    """Load the attribute JSON Schema for an entity's *artifact_type*.

    Returns ``None`` when no schema file exists (free schema — skip validation).
    """
    return _load_schema_file(repo_root, f"attributes.{artifact_type}.schema.json")


def load_connection_metadata_schema(repo_root: Path, connection_type: str) -> dict[str, Any] | None:
    """Load the metadata JSON Schema for *connection_type*.

    Returns ``None`` when no schema file exists (free schema — skip validation).
    """
    return _load_schema_file(repo_root, f"connection-metadata.{connection_type}.schema.json")


def load_specialization_attachment_schema(
    repo_root: Path, artifact_type: str, specialization_slug: str
) -> dict[str, Any] | None:
    """Load the `attributes.{artifact_type}.{specialization_slug}.schema.json` attachment file.

    Returns ``None`` when no such file exists (free schema — skip validation).
    """
    return _load_schema_file(repo_root, f"attributes.{artifact_type}.{specialization_slug}.schema.json")


SchemaFileKind = Literal[
    "entity-attributes", "specialization-attachment", "connection-metadata", "frontmatter", "unrecognized"
]


@dataclass(frozen=True)
class SchemaFileRef:
    """One classified ``.arch-repo/schemata/`` file, parsed per this module's filename
    conventions. The inventory is the single place that understands those conventions —
    consumers (startup validation, orphan detection, schema policy) filter typed records
    instead of re-parsing filenames."""

    filename: str
    kind: SchemaFileKind
    subject: str = ""  # entity type / connection type / frontmatter file-type
    specialization_slug: str = ""  # kind == "specialization-attachment" only


def _classify_schema_filename(filename: str) -> SchemaFileRef:
    suffix = ".schema.json"
    if filename.startswith("attributes.") and filename.endswith(suffix):
        parts = filename[len("attributes.") : -len(suffix)].split(".")
        if len(parts) == 1 and parts[0]:
            return SchemaFileRef(filename=filename, kind="entity-attributes", subject=parts[0])
        if len(parts) == 2 and all(parts):
            return SchemaFileRef(
                filename=filename, kind="specialization-attachment",
                subject=parts[0], specialization_slug=parts[1],
            )
        return SchemaFileRef(filename=filename, kind="unrecognized")
    if filename.startswith("connection-metadata.") and filename.endswith(suffix):
        subject = filename[len("connection-metadata.") : -len(suffix)]
        if subject:
            return SchemaFileRef(filename=filename, kind="connection-metadata", subject=subject)
        return SchemaFileRef(filename=filename, kind="unrecognized")
    if filename.startswith("frontmatter.") and filename.endswith(suffix):
        subject = filename[len("frontmatter.") : -len(suffix)]
        if subject:
            return SchemaFileRef(filename=filename, kind="frontmatter", subject=subject)
    return SchemaFileRef(filename=filename, kind="unrecognized")


def list_schema_files(repo_root: Path) -> tuple[SchemaFileRef, ...]:
    """Classified inventory of one repo's ``.arch-repo/schemata/`` directory, sorted by
    filename. Empty when the directory does not exist."""
    schemata_dir = repo_root / SCHEMATA_DIR
    if not schemata_dir.is_dir():
        return ()
    return tuple(
        _classify_schema_filename(path.name) for path in sorted(schemata_dir.glob("*.schema.json"))
    )


def compute_effective_attribute_schema(
    repo_root: Path,
    artifact_type: str,
    specialization_slug: str,
    *,
    specialization_catalog: SpecializationCatalog,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Merge the base-type attribute schema with an entity's own specialization's profile.

    An entity carries at most one specialization (D6), so this is base ⊕ (at most) one
    specialization-contributed fragment. A specialization's profile is one-to-one with it —
    never a separately reusable, named registry entry — sourced from inline `attributes:`
    and/or its dedicated `attributes.{artifact_type}.{slug}.schema.json` attachment file,
    both already scoped to that one specialization by construction. Returns
    ``(merged_schema, conflict_messages)`` — ``merged_schema`` is ``None`` only when there is
    no base schema, no specialization, and no attachment file (free schema).
    """
    fragments: list[dict[str, Any]] = []
    base = load_attribute_schema(repo_root, artifact_type)
    if base is not None:
        fragments.append(base)

    if specialization_slug:
        spec_info = specialization_catalog.get("entity", artifact_type, specialization_slug)
        if spec_info is not None and spec_info.attributes:
            inline = profile_from_inline_attributes(specialization_slug, spec_info.attributes)
            fragments.append(compile_profile_schema(inline))
        attachment = load_specialization_attachment_schema(repo_root, artifact_type, specialization_slug)
        if attachment is not None:
            fragments.append(attachment)

    if not fragments:
        return None, []
    merged, conflicts = merge_property_schemas(fragments)
    return merged, conflicts


def find_orphan_attachment_schemata(repo_root: Path, specialization_catalog: SpecializationCatalog) -> list[str]:
    """Return `attributes.{artifact_type}.{slug}.schema.json` filenames whose `slug` is not a
    declared entity specialization of `artifact_type` in *specialization_catalog*."""
    return [
        ref.filename
        for ref in list_schema_files(repo_root)
        if ref.kind == "specialization-attachment"
        and specialization_catalog.get("entity", ref.subject, ref.specialization_slug) is None
    ]


def validate_against_schema(instance: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate *instance* against *schema*, returning a list of error messages.

    Returns an empty list when *instance* conforms to *schema*.
    """
    validator_cls = jsonschema.Draft202012Validator
    validator = validator_cls(schema)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
        errors.append(f"{path}: {error.message}")
    return errors


def schema_required_properties(schema: dict[str, Any]) -> list[str]:
    """Return the list of required property names from a schema."""
    return list(schema.get("required", []))


def schema_all_properties(schema: dict[str, Any]) -> list[str]:
    """Return all declared property names from a schema."""
    return list(schema.get("properties", {}).keys())


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


@lru_cache(maxsize=128)
def _load_schema_file(repo_root: Path, filename: str) -> dict[str, Any] | None:
    schema_path = repo_root / SCHEMATA_DIR / filename
    if not schema_path.is_file():
        return None
    with open(schema_path, encoding="utf-8") as fh:
        return json.load(fh)


def clear_schema_cache() -> None:
    """Clear the in-memory schema cache (useful in tests)."""
    _load_schema_file.cache_clear()
