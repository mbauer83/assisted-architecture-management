"""Pure helpers for :func:`entity_edit.edit_entity`.

Holds the partial-update sentinel, the merged-field value object, and the
rename-impact counter — all free of write side effects so they stay easy to test
and reason about.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.application.repo_path_helpers import all_model_roots

from .boundary import normalize_specializations
from .coerce import as_optional_str, as_optional_str_dict, as_optional_str_list, as_optional_typed_dict
from .parse_existing import ParsedEntity

# Sentinel to distinguish "not provided" from explicit None. Re-exported by
# entity_edit so existing callers keep importing it from there.
_UNSET = object()


def _fm_specializations(value: object) -> tuple[str, ...]:
    """The current applied set from a frontmatter ``specialization`` value (scalar, list, or
    absent) — the read mirror of what the writer serialises."""
    if isinstance(value, list):
        return normalize_specializations(None, [str(v) for v in value])
    return normalize_specializations(str(value) if isinstance(value, str) else None, None)


def _merge_specializations(current: object, specialization: object, specializations: object) -> tuple[str, ...]:
    """The post-edit applied set. An explicit update (either the scalar ``specialization`` or
    the list ``specializations``) REPLACES the current set; ``_UNSET`` on both keeps it.
    Passing ``""``/``[]`` clears it, exactly as the single-value edit already cleared one."""
    if specializations is not _UNSET:
        raw = specializations if isinstance(specializations, list) else []
        return normalize_specializations(None, [str(v) for v in raw])
    if specialization is not _UNSET:
        scalar = str(specialization) if isinstance(specialization, str) else None
        return normalize_specializations(scalar, None)
    return _fm_specializations(current)


@dataclass(frozen=True)
class MergedFields:
    """An entity's editable fields after merging partial updates with current values."""

    name: str
    version: str
    status: str
    keywords: list[str] | None
    specializations: tuple[str, ...]
    summary: str | None
    properties: dict[str, Any] | None
    attribute_types: dict[str, str] | None
    notes: str | None


def merge_fields(
    parsed: ParsedEntity,
    *,
    name: str | None,
    version: str | None,
    status: str | None,
    keywords: object,
    specialization: object = _UNSET,
    specializations: object = _UNSET,
    summary: object,
    properties: object,
    attribute_types: object,
    notes: object,
) -> MergedFields:
    """Merge provided fields over the parsed entity; ``_UNSET``/``None`` keep current values."""
    fm = parsed.frontmatter
    return MergedFields(
        name=name if name is not None else str(fm.get("name", "")),
        version=version if version is not None else str(fm.get("version", "0.1.0")),
        status=status if status is not None else str(fm.get("status", "draft")),
        keywords=as_optional_str_list(keywords if keywords is not _UNSET else fm.get("keywords")),
        specializations=_merge_specializations(fm.get("specialization"), specialization, specializations),
        summary=as_optional_str(summary) if summary is not _UNSET else parsed.summary,
        properties=(
            as_optional_typed_dict(properties) if properties is not _UNSET else (parsed.properties or None)
        ),
        attribute_types=(
            as_optional_str_dict(attribute_types)
            if attribute_types is not _UNSET
            else as_optional_str_dict(fm.get("attribute-types"))
        ),
        notes=as_optional_str(notes) if notes is not _UNSET else parsed.notes,
    )


def count_rename_referrers(repo_root: Path, artifact_id: str, own_outgoing: Path) -> int:
    """Count outgoing files a rename would rewrite: the entity's own file plus any referrers."""
    impacted = 1 if own_outgoing.exists() else 0
    for model_root in all_model_roots(repo_root):
        for outgoing_path in model_root.rglob("*.outgoing.md"):
            if outgoing_path == own_outgoing:
                continue
            try:
                if artifact_id in outgoing_path.read_text(encoding="utf-8"):
                    impacted += 1
            except OSError:
                continue
    return impacted
