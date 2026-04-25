"""Schema-superset verification for promotion from engagement to enterprise repo.

Promotion requires that engagement schemata are supersets of enterprise schemata:
every property and required field defined in the enterprise schema must also exist in the
engagement schema. Violations block the promotion and return human-readable error strings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from src.common.artifact_schema import load_frontmatter_schema, load_attribute_schema
from src.common.workspace_paths import infer_repo_scope

if TYPE_CHECKING:
    from src.common.artifact_query import ArtifactRepository
    from src.common.artifact_verifier import ArtifactRegistry


def _schema_superset_errors(
    eng_schema: dict[str, Any],
    ent_schema: dict[str, Any],
    scope: str,
) -> list[str]:
    """Return error strings if *eng_schema* is not a superset of *ent_schema*."""
    errors: list[str] = []
    missing_props = set(ent_schema.get("properties", {}).keys()) - set(eng_schema.get("properties", {}).keys())
    if missing_props:
        errors.append(
            f"{scope}: engagement schema is missing properties required by enterprise: "
            + ", ".join(sorted(missing_props))
        )
    missing_required = set(ent_schema.get("required", [])) - set(eng_schema.get("required", []))
    if missing_required:
        errors.append(
            f"{scope}: engagement schema does not mark as required: "
            + ", ".join(sorted(missing_required))
            + " (required by enterprise schema)"
        )
    return errors


def check_promotion_schema_compatibility(
    entity_ids: list[str],
    has_diagrams: bool,
    document_ids: list[str],
    registry: "ArtifactRegistry",
    repo: "ArtifactRepository",
) -> list[str]:
    """Check that engagement schemata are supersets of enterprise schemata.

    Inspects attribute profiles, frontmatter schemas, and document schemas for all
    artifact types present in the promotion set.

    Returns a list of blocking error strings (empty = no violations).
    """
    eng_roots = [r for r in registry.repo_roots if infer_repo_scope(r) != "enterprise"]
    ent_roots = [r for r in registry.repo_roots if infer_repo_scope(r) == "enterprise"]
    if not eng_roots or not ent_roots:
        return []
    eng_root, ent_root = eng_roots[0], ent_roots[0]

    errors: list[str] = []
    has_entities = bool(entity_ids)

    # Attribute schemas per entity type
    artifact_types: set[str] = set()
    for eid in entity_ids:
        rec = repo.get_entity(eid)
        if rec is not None:
            artifact_types.add(rec.artifact_type)
    for atype in sorted(artifact_types):
        ent_s = load_attribute_schema(ent_root, atype)
        if ent_s is None:
            continue
        eng_s = load_attribute_schema(eng_root, atype)
        if eng_s is None:
            errors.append(
                f"attribute profile '{atype}': engagement repo missing schema — "
                f"add .arch-repo/schemata/attributes.{atype}.schema.json"
            )
            continue
        errors.extend(_schema_superset_errors(eng_s, ent_s, f"attribute profile '{atype}'"))

    # Frontmatter schemas for entities and diagrams
    for file_type in (["entity", "outgoing"] if has_entities else []) + (["diagram"] if has_diagrams else []):
        ent_s = load_frontmatter_schema(ent_root, file_type)
        if ent_s is None:
            continue
        eng_s = load_frontmatter_schema(eng_root, file_type)
        if eng_s is None:
            errors.append(
                f"frontmatter schema '{file_type}': engagement repo missing schema — "
                f"add .arch-repo/schemata/frontmatter.{file_type}.schema.json"
            )
            continue
        errors.extend(_schema_superset_errors(eng_s, ent_s, f"frontmatter '{file_type}'"))

    # Document schemas
    if document_ids:
        from src.common.artifact_document_schema import get_document_schema
        doc_types: set[str] = set()
        for did in document_ids:
            doc = repo.get_document(did)
            if doc is not None:
                doc_types.add(doc.doc_type)
        for doc_type in sorted(doc_types):
            ent_ds = get_document_schema(ent_root, doc_type)
            if ent_ds is None:
                continue
            eng_ds = get_document_schema(eng_root, doc_type)
            if eng_ds is None:
                errors.append(
                    f"document schema '{doc_type}': engagement repo missing schema — "
                    f"add .arch-repo/documents/{doc_type}.json"
                )
                continue
            ent_fm, eng_fm = ent_ds.get("frontmatter_schema") or {}, eng_ds.get("frontmatter_schema") or {}
            if ent_fm:
                errors.extend(_schema_superset_errors(eng_fm, ent_fm, f"document frontmatter '{doc_type}'"))
            missing_sections = set(ent_ds.get("required_sections", [])) - set(eng_ds.get("required_sections", []))
            if missing_sections:
                errors.append(
                    f"document schema '{doc_type}': engagement schema missing required sections: "
                    + ", ".join(sorted(missing_sections))
                )

    return errors
