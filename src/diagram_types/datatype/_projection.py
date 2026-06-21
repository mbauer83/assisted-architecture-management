"""WU-1.3: DatatypeVerificationProjection compiler.

Builds a read-only cross-diagram view of all classifier definitions and
attribute-type usages from a CandidateRepository. Compiled only from
CandidateRepository reads — no SQLite direct access.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Mapping

from src.domain.diagram_verification import BaseDiagramVerificationContext


@dataclass(frozen=True)
class ClassifierDefinition:
    """A classifier known to the workspace at verification time."""

    type_id: str
    label: str
    kind: str
    scope: str
    status: str
    host_diagram_id: str


@dataclass(frozen=True)
class AttributeTypeUsage:
    """One attribute on one classifier that references a classifier type by id."""

    diagram_id: str
    classifier_local_id: str
    attr_name: str


@dataclass(frozen=True)
class DatatypeVerificationProjection:
    """Cross-diagram projection used by E332/W333 and other datatype rules."""

    classifiers_by_id: Mapping[str, ClassifierDefinition]
    classifier_ids_by_name: Mapping[str, tuple[str, ...]]
    usages_by_id: Mapping[str, tuple[AttributeTypeUsage, ...]]


def compile_projection(
    candidate: Any,
    ctx: BaseDiagramVerificationContext,
) -> DatatypeVerificationProjection:
    """Compile a DatatypeVerificationProjection from *candidate*.

    Uses only CandidateRepository reads; candidate is typed Any to avoid
    cross-layer imports (it satisfies CandidateRepository at runtime).
    """
    classifiers_by_id: dict[str, ClassifierDefinition] = {}
    name_to_ids: dict[str, list[str]] = defaultdict(list)

    for entity in candidate.list_entities(artifact_type="classifier"):
        scope = str(candidate.scope_for_path(entity.path))
        extra: dict[str, Any] = dict(entity.extra) if entity.extra else {}
        clf_def = ClassifierDefinition(
            type_id=entity.artifact_id,
            label=entity.name,
            kind=str(extra.get("classifier_kind") or ""),
            scope=scope,
            status=entity.status,
            host_diagram_id=str(entity.host_diagram_id or ""),
        )
        classifiers_by_id[entity.artifact_id] = clf_def
        norm_name = entity.name.lower().strip()
        if norm_name:
            name_to_ids[norm_name].append(entity.artifact_id)

    classifier_ids_by_name: dict[str, tuple[str, ...]] = {
        name: tuple(ids) for name, ids in name_to_ids.items()
    }

    usages_raw: dict[str, list[AttributeTypeUsage]] = defaultdict(list)
    for diagram in candidate.list_diagrams(diagram_type="datatype"):
        extra_d: dict[str, Any] = dict(diagram.extra) if diagram.extra else {}
        de: dict[str, Any] = extra_d.get("diagram-entities") or {}
        if not isinstance(de, dict):
            continue
        classifiers_raw: list[Any] = de.get("classifier") or []
        if not isinstance(classifiers_raw, list):
            continue
        for clf in classifiers_raw:
            if not isinstance(clf, dict):
                continue
            clf_id = str(clf.get("id") or "")
            attrs: list[Any] = clf.get("attributes") or []
            if not isinstance(attrs, list):
                continue
            for attr in attrs:
                if not isinstance(attr, dict):
                    continue
                type_ref = attr.get("type")
                if not isinstance(type_ref, dict):
                    continue
                if type_ref.get("kind") != "classifier":
                    continue
                ref_id = str(type_ref.get("id") or "")
                if not ref_id:
                    continue
                attr_name = str(attr.get("name") or "")
                usages_raw[ref_id].append(AttributeTypeUsage(
                    diagram_id=diagram.artifact_id,
                    classifier_local_id=clf_id,
                    attr_name=attr_name,
                ))

    return DatatypeVerificationProjection(
        classifiers_by_id=classifiers_by_id,
        classifier_ids_by_name=classifier_ids_by_name,
        usages_by_id={k: tuple(v) for k, v in usages_raw.items()},
    )
