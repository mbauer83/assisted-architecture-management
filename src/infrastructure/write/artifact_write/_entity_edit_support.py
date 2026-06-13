"""Pure helpers for :func:`entity_edit.edit_entity`.

Holds the partial-update sentinel, the merged-field value object, and the
rename-impact counter — all free of write side effects so they stay easy to test
and reason about.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.application.repo_path_helpers import all_model_roots

from .coerce import as_optional_str, as_optional_str_dict, as_optional_str_list
from .parse_existing import ParsedEntity

# Sentinel to distinguish "not provided" from explicit None. Re-exported by
# entity_edit so existing callers keep importing it from there.
_UNSET = object()


@dataclass(frozen=True)
class MergedFields:
    """An entity's editable fields after merging partial updates with current values."""

    name: str
    version: str
    status: str
    keywords: list[str] | None
    summary: str | None
    properties: dict[str, str] | None
    notes: str | None


def merge_fields(
    parsed: ParsedEntity,
    *,
    name: str | None,
    version: str | None,
    status: str | None,
    keywords: object,
    summary: object,
    properties: object,
    notes: object,
) -> MergedFields:
    """Merge provided fields over the parsed entity; ``_UNSET``/``None`` keep current values."""
    fm = parsed.frontmatter
    return MergedFields(
        name=name if name is not None else str(fm.get("name", "")),
        version=version if version is not None else str(fm.get("version", "0.1.0")),
        status=status if status is not None else str(fm.get("status", "draft")),
        keywords=as_optional_str_list(keywords if keywords is not _UNSET else fm.get("keywords")),
        summary=as_optional_str(summary) if summary is not _UNSET else parsed.summary,
        properties=as_optional_str_dict(properties) if properties is not _UNSET else (parsed.properties or None),
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
