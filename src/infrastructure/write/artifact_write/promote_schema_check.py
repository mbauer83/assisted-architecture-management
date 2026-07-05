"""Schema-superset verification for promotion from engagement to enterprise repo.

Promotion requires that engagement schemata are supersets of enterprise schemata:
every property and required field defined in the enterprise schema must also exist in the
engagement schema. Violations block the promotion and return human-readable error strings.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.application.artifact_schema import load_attribute_schema, load_frontmatter_schema
from src.config.workspace_paths import infer_repo_scope

if TYPE_CHECKING:
    from src.application.artifact_document_schema import DocumentSchema
    from src.application.artifact_query import ArtifactRepository
    from src.application.verification.artifact_verifier import ArtifactRegistry


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


def _compare_schema_pairs(
    keys: Iterable[str],
    *,
    load_ent: Callable[[str], dict[str, Any] | None],
    load_eng: Callable[[str], dict[str, Any] | None],
    missing_eng_msg: Callable[[str], str],
    scope_label: Callable[[str], str],
) -> list[str]:
    """For each key, compare the enterprise/engagement schema pair, collecting errors.

    A key with no enterprise schema is skipped; one whose enterprise schema exists but
    whose engagement counterpart is absent yields ``missing_eng_msg(key)``.
    """
    errors: list[str] = []
    for key in keys:
        ent_s = load_ent(key)
        if ent_s is None:
            continue
        eng_s = load_eng(key)
        if eng_s is None:
            errors.append(missing_eng_msg(key))
            continue
        errors.extend(_schema_superset_errors(eng_s, ent_s, scope_label(key)))
    return errors


def _attribute_schema_errors(
    eng_root: Path, ent_root: Path, entity_ids: list[str], repo: "ArtifactRepository"
) -> list[str]:
    types = sorted({rec.artifact_type for eid in entity_ids if (rec := repo.get_entity(eid)) is not None})
    return _compare_schema_pairs(
        types,
        load_ent=lambda atype: load_attribute_schema(ent_root, atype),
        load_eng=lambda atype: load_attribute_schema(eng_root, atype),
        missing_eng_msg=lambda atype: (
            f"attribute profile '{atype}': engagement repo missing schema — "
            f"add .arch-repo/schemata/attributes.{atype}.schema.json"
        ),
        scope_label=lambda atype: f"attribute profile '{atype}'",
    )


def _frontmatter_schema_errors(
    eng_root: Path, ent_root: Path, has_entities: bool, has_diagrams: bool
) -> list[str]:
    file_types = (["entity", "outgoing"] if has_entities else []) + (["diagram"] if has_diagrams else [])
    return _compare_schema_pairs(
        file_types,
        load_ent=lambda ft: load_frontmatter_schema(ent_root, ft),
        load_eng=lambda ft: load_frontmatter_schema(eng_root, ft),
        missing_eng_msg=lambda ft: (
            f"frontmatter schema '{ft}': engagement repo missing schema — "
            f"add .arch-repo/schemata/frontmatter.{ft}.schema.json"
        ),
        scope_label=lambda ft: f"frontmatter '{ft}'",
    )


def _document_section_errors(doc_type: str, ent_ds: "DocumentSchema", eng_ds: "DocumentSchema") -> list[str]:
    """Compare normalized section specs: engagement must cover every enterprise section and,

    for sections present in both, require at least the same entity-type connection terms.
    """
    errors: list[str] = []
    eng_sections = {section.name: section for section in eng_ds.sections}
    missing_sections = [section.name for section in ent_ds.sections if section.name not in eng_sections]
    if missing_sections:
        errors.append(
            f"document schema '{doc_type}': engagement schema missing required sections: "
            + ", ".join(sorted(missing_sections))
        )
    for ent_section in ent_ds.sections:
        eng_section = eng_sections.get(ent_section.name)
        if eng_section is None:
            continue
        missing_terms = set(ent_section.required_entity_type_connections) - set(
            eng_section.required_entity_type_connections
        )
        if missing_terms:
            errors.append(
                f"document schema '{doc_type}': section '{ent_section.name}' engagement schema does not "
                "require entity-type connections: " + ", ".join(sorted(missing_terms))
                + " (required by enterprise schema)"
            )
    return errors


def _document_schema_errors(
    eng_root: Path, ent_root: Path, document_ids: list[str], repo: "ArtifactRepository"
) -> list[str]:
    if not document_ids:
        return []
    from src.application.artifact_document_schema import get_document_schema_object

    doc_types = sorted({doc.doc_type for did in document_ids if (doc := repo.get_document(did)) is not None})
    errors: list[str] = []
    for doc_type in doc_types:
        ent_ds = get_document_schema_object(ent_root, doc_type)
        if ent_ds is None:
            continue
        eng_ds = get_document_schema_object(eng_root, doc_type)
        if eng_ds is None:
            errors.append(
                f"document schema '{doc_type}': engagement repo missing schema — "
                f"add .arch-repo/documents/{doc_type}.json"
            )
            continue
        ent_fm: dict[str, object] = ent_ds.data.get("frontmatter_schema") or {}
        eng_fm: dict[str, object] = eng_ds.data.get("frontmatter_schema") or {}
        if ent_fm:
            errors.extend(_schema_superset_errors(eng_fm, ent_fm, f"document frontmatter '{doc_type}'"))
        errors.extend(_document_section_errors(doc_type, ent_ds, eng_ds))
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

    return [
        *_attribute_schema_errors(eng_root, ent_root, entity_ids, repo),
        *_frontmatter_schema_errors(eng_root, ent_root, bool(entity_ids), has_diagrams),
        *_document_schema_errors(eng_root, ent_root, document_ids, repo),
    ]
