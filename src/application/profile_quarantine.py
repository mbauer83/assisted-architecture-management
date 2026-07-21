"""Class B quarantine (PLAN §4): a ``(entity-type, specialization)`` pair whose bound
profiles conflict with each other or the base schema on an attribute's type. The rest of the
model stays well-defined, so the failure is confined to the pair — reads continue, but a
create/edit for that pair is rejected at the write boundary (WU-Q3).

Quarantine is computed on demand from ``(repo, catalogs)`` and never persisted — the same
discipline as the schema resolution it wraps — so it self-clears the moment the conflicting
profiles or bindings change. Class A (an undefined binding) is a startup concern: it aborts
the engagement repo at boot (WU-Q1) and therefore never reaches a running write boundary, so
here every conflict is Class B (scoped).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from src.application.artifact_schema import compute_effective_attribute_schema
from src.application.runtime_catalogs import RuntimeCatalogs
from src.domain.profile_registry import ProfileConflict


def pair_quarantine_conflicts(
    repo_root: Path, artifact_type: str, specialization_slugs: Sequence[str], *, catalogs: RuntimeCatalogs
) -> tuple[ProfileConflict, ...]:
    """The scoped (Class B) conflicts for one applied-specialization set, or empty when the
    pair resolves cleanly. Every merge conflict is Class B — an incompatible-type
    redefinition — so it is reported directly (a running engagement backend has already
    ruled out Class A at startup)."""
    _schema, merge_conflicts = compute_effective_attribute_schema(
        repo_root,
        artifact_type,
        list(specialization_slugs),
        specialization_catalog=catalogs.specializations,
        profile_registry=catalogs.profiles,
    )
    return tuple(ProfileConflict("scoped", message) for message in merge_conflicts)


def compute_quarantine_set(
    repo_root: Path, catalogs: RuntimeCatalogs
) -> dict[tuple[str, str], tuple[ProfileConflict, ...]]:
    """Every quarantined ``(entity-type, specialization)`` pair with its reasons, over the
    whole catalog. Confined by construction: each pair is resolved independently, so one
    conflicting pair never taints its siblings."""
    quarantined: dict[tuple[str, str], tuple[ProfileConflict, ...]] = {}
    for entity_type in catalogs.ontology.all_entity_type_names():
        for specialization in catalogs.specializations.for_type("entity", str(entity_type)):
            conflicts = pair_quarantine_conflicts(
                repo_root, str(entity_type), (specialization.slug,), catalogs=catalogs
            )
            if conflicts:
                quarantined[(str(entity_type), specialization.slug)] = conflicts
    return quarantined


class ProfileQuarantineError(ValueError):
    """A create/edit was refused because its ``(entity-type, specialization)`` pair is
    quarantined. A ``ValueError`` so every transport surfaces it through the existing write
    rejection path (REST → HTTP 400, MCP → tool error)."""

    def __init__(self, artifact_type: str, specialization: str, conflicts: tuple[ProfileConflict, ...]) -> None:
        self.artifact_type = artifact_type
        self.specialization = specialization
        self.conflicts = conflicts
        subject = f"{artifact_type}/{specialization}" if specialization else artifact_type
        detail = "; ".join(conflict.message for conflict in conflicts)
        super().__init__(
            f"Cannot write {subject}: its attribute profile is quarantined by a conflict — {detail}. "
            "Fix the conflicting named profiles or unbind one, then retry."
        )


def assert_not_quarantined(
    repo_root: Path, artifact_type: str, specialization_slugs: Sequence[str], *, catalogs: RuntimeCatalogs
) -> None:
    """Reject a write whose applied-specialization set resolves to a quarantined schema. The
    single gate every transport passes through (WU-Q3), closing the gap where the write path
    only ever saw the base-type schema."""
    conflicts = pair_quarantine_conflicts(repo_root, artifact_type, specialization_slugs, catalogs=catalogs)
    if conflicts:
        specialization = next((slug for slug in specialization_slugs if slug), "")
        raise ProfileQuarantineError(artifact_type, specialization, conflicts)
