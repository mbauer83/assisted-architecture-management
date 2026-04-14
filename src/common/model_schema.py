"""Configurable JSON Schema loading for frontmatter and attribute validation.

Schema files are stored in ``.arch-repo/schemata/`` within a repository root.

File conventions
----------------
- ``frontmatter.{file-type}.schema.json``  — entity, outgoing, diagram
- ``attributes.{artifact-type}.schema.json`` — per entity-type attribute schema
- ``connection-metadata.{connection-type}.schema.json`` — per connection-type metadata

Default behaviour: when no schema file exists for a given scope/type,
validation is skipped (free schema).
"""


import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]


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


def load_connection_metadata_schema(
    repo_root: Path, connection_type: str
) -> dict[str, Any] | None:
    """Load the metadata JSON Schema for *connection_type*.

    Returns ``None`` when no schema file exists (free schema — skip validation).
    """
    return _load_schema_file(
        repo_root, f"connection-metadata.{connection_type}.schema.json"
    )


def validate_against_schema(
    instance: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
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
