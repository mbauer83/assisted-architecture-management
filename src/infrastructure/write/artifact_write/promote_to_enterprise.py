"""Promote artifacts from engagement to enterprise repository.

"Promote" means transferring artifact files from the engagement repo into the
enterprise repo.  Supported types: entities (+ connections), documents, diagrams.
This is a one-way operation.

Conflict detection:
- Entities: matched by (artifact_type, normalized_name) OR (artifact_type, id_suffix)
- Documents: matched by (doc_type, normalized_title)
- Diagrams:  matched by (diagram_type, normalized_name)

Schema superset verification (see promote_schema_check.py) blocks promotion when
engagement schemata are not supersets of the corresponding enterprise schemata.

Execution logic lives in promote_execute.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from src.application.artifact_query import ArtifactRepository
from src.application.verification.artifact_verifier import ArtifactRegistry
from src.infrastructure.write.artifact_write.parse_existing import parse_entity_file
from src.infrastructure.write.artifact_write.promote_schema_check import check_promotion_schema_compatibility

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class PromotionConflict:
    """An engagement entity that matches an enterprise entity by type+name."""

    engagement_id: str
    enterprise_id: str
    artifact_type: str
    engagement_name: str
    enterprise_name: str
    engagement_fields: dict[str, Any]
    enterprise_fields: dict[str, Any]


@dataclass
class DocPromotionConflict:
    """An engagement document that matches an enterprise document by doc_type+title."""

    engagement_id: str
    enterprise_id: str
    doc_type: str
    engagement_title: str
    enterprise_title: str


@dataclass
class DiagramPromotionConflict:
    """An engagement diagram that matches an enterprise diagram by diagram_type+name."""

    engagement_id: str
    enterprise_id: str
    diagram_type: str
    engagement_name: str
    enterprise_name: str


@dataclass
class ConflictResolution:
    engagement_id: str
    strategy: Literal["accept_engagement", "accept_enterprise", "merge"]
    merged_fields: dict[str, Any] | None = None


@dataclass
class PromotionPlan:
    root_entity: str
    entities_to_add: list[str]
    conflicts: list[PromotionConflict]
    connection_ids: list[str]
    already_in_enterprise: list[str]
    warnings: list[str]
    documents_to_add: list[str] = field(default_factory=list)
    diagrams_to_add: list[str] = field(default_factory=list)
    doc_conflicts: list[DocPromotionConflict] = field(default_factory=list)
    diagram_conflicts: list[DiagramPromotionConflict] = field(default_factory=list)
    schema_errors: list[str] = field(default_factory=list)


@dataclass
class PromotionResult:
    plan: PromotionPlan
    executed: bool
    copied_files: list[str] = field(default_factory=list)
    updated_files: list[str] = field(default_factory=list)
    verification_errors: list[str] = field(default_factory=list)
    rolled_back: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_id_suffix(artifact_id: str) -> str | None:
    """Return the portion after '@' (epoch.random), or None if the ID has no '@'."""
    if "@" not in artifact_id:
        return None
    return artifact_id.split("@", 1)[1]


def _parse_conn_full(cid: str) -> tuple[str, str, str] | None:
    if "---" in cid and "@@" in cid:
        source, rest = cid.split("---", 1)
        target, conn_type = rest.rsplit("@@", 1)
        if source and target and conn_type:
            return source.strip(), conn_type.strip(), target.strip()
    if " → " not in cid:
        return None
    left, target = cid.rsplit(" → ", 1)
    parts = left.split(" ", 1)
    if len(parts) < 2:
        return None
    return (parts[0].strip(), parts[1].strip(), target.strip())


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace("-", " ").replace("_", " ")


def _build_enterprise_name_index(
    repo: ArtifactRepository,
    registry: ArtifactRegistry,
) -> dict[tuple[str, str], Any]:
    enterprise_ids = registry.enterprise_entity_ids()
    index: dict[tuple[str, str], Any] = {}
    for eid in enterprise_ids:
        rec = repo.get_entity(eid)
        if rec is None:
            continue
        key = (rec.artifact_type, _normalize_name(rec.name))
        index[key] = rec
    return index


def _build_enterprise_id_suffix_index(
    repo: ArtifactRepository,
    registry: ArtifactRegistry,
) -> dict[tuple[str, str], Any]:
    """Index enterprise entities by (artifact_type, id_suffix) to catch same-ID renames."""
    enterprise_ids = registry.enterprise_entity_ids()
    index: dict[tuple[str, str], Any] = {}
    for eid in enterprise_ids:
        rec = repo.get_entity(eid)
        if rec is None:
            continue
        suffix = _extract_id_suffix(eid)
        if suffix is not None:
            index[(rec.artifact_type, suffix)] = rec
    return index


def _entity_frontmatter(registry: ArtifactRegistry, eid: str) -> dict[str, Any]:
    path = registry.find_file_by_id(eid)
    if path is None:
        return {}
    try:
        parsed = parse_entity_file(path)
        return dict(parsed.frontmatter)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def plan_promotion(
    entity_id: str | None,
    registry: ArtifactRegistry,
    repo: ArtifactRepository,
    *,
    entity_ids: list[str] | None = None,
    connection_ids: set[str] | None = None,
    exclude_entity_ids: set[str] | None = None,
    exclude_connection_ids: set[str] | None = None,
    document_ids: list[str] | None = None,
    diagram_ids: list[str] | None = None,
) -> PromotionPlan:
    """Compute an explicit promotion plan from a caller-selected artifact set."""
    all_entities = registry.entity_ids()
    enterprise_ids = registry.enterprise_entity_ids()
    gar_ids = {eid for eid in all_entities if eid.startswith("GAR@")}

    selected_ids = list(dict.fromkeys(entity_ids or ([entity_id] if entity_id else [])))
    if not selected_ids and not document_ids and not diagram_ids:
        raise ValueError("At least one artifact must be selected for promotion")
    missing = [eid for eid in selected_ids if eid not in all_entities]
    if missing:
        raise ValueError(f"Entity '{missing[0]}' not found in model")

    ent_name_index = _build_enterprise_name_index(repo, registry)
    ent_id_suffix_index = _build_enterprise_id_suffix_index(repo, registry)
    warnings: list[str] = []
    already: list[str] = []
    candidates: list[str] = []
    for eid in selected_ids:
        if eid in enterprise_ids:
            already.append(eid)
            continue
        if eid in gar_ids:
            warnings.append(f"Skipped GAR {eid} from promotion set")
            continue
        candidates.append(eid)

    to_add: list[str] = []
    conflicts: list[PromotionConflict] = []
    for eid in candidates:
        rec = repo.get_entity(eid)
        if rec is None:
            warnings.append(f"Entity record not found for {eid}")
            continue
        # Match by name first, then fall back to ID suffix (catches same entity renamed in one repo)
        name_key = (rec.artifact_type, _normalize_name(rec.name))
        ent_rec = ent_name_index.get(name_key)
        if ent_rec is None:
            suffix = _extract_id_suffix(eid)
            if suffix is not None:
                ent_rec = ent_id_suffix_index.get((rec.artifact_type, suffix))
        if ent_rec is not None:
            conflicts.append(
                PromotionConflict(
                    engagement_id=eid,
                    enterprise_id=ent_rec.artifact_id,
                    artifact_type=rec.artifact_type,
                    engagement_name=rec.name,
                    enterprise_name=ent_rec.name,
                    engagement_fields=_entity_frontmatter(registry, eid),
                    enterprise_fields=_entity_frontmatter(registry, ent_rec.artifact_id),
                )
            )
        else:
            to_add.append(eid)

    promotable = set(candidates)
    selected_set = set(selected_ids)
    explicit_connection_ids = set(connection_ids or ())
    conn_ids: list[str] = []
    for cid in registry.connection_ids():
        parsed = _parse_conn_full(cid)
        if parsed is None:
            continue
        src, _conn_type, tgt = parsed
        if src not in promotable:
            continue
        if tgt in selected_set and cid in explicit_connection_ids:
            conn_ids.append(cid)

    exc_ents = exclude_entity_ids or set()
    exc_conns = exclude_connection_ids or set()
    if exc_ents:
        to_add = [e for e in to_add if e not in exc_ents]
        already = [e for e in already if e not in exc_ents]
        conflicts = [c for c in conflicts if c.engagement_id not in exc_ents]
    if exc_conns:
        conn_ids = [c for c in conn_ids if c not in exc_conns]

    # ── Documents ────────────────────────────────────────────────────────────
    docs_to_add: list[str] = []
    doc_conflicts: list[DocPromotionConflict] = []
    enterprise_doc_ids = registry.enterprise_document_ids()
    enterprise_doc_index: dict[tuple[str, str], Any] = {}
    for doc_rec in repo.list_documents():
        if doc_rec.artifact_id in enterprise_doc_ids:
            key = (doc_rec.doc_type, _normalize_name(doc_rec.title))
            enterprise_doc_index[key] = doc_rec
    for did in document_ids or []:
        doc = repo.get_document(did)
        if doc is None:
            warnings.append(f"Document not found: {did}")
            continue
        if did in enterprise_doc_ids:
            already.append(did)
            continue
        key = (doc.doc_type, _normalize_name(doc.title))
        ent_doc = enterprise_doc_index.get(key)
        if ent_doc is not None:
            doc_conflicts.append(
                DocPromotionConflict(
                    engagement_id=did,
                    enterprise_id=ent_doc.artifact_id,
                    doc_type=doc.doc_type,
                    engagement_title=doc.title,
                    enterprise_title=ent_doc.title,
                )
            )
        else:
            docs_to_add.append(did)

    # ── Diagrams ─────────────────────────────────────────────────────────────
    diags_to_add: list[str] = []
    diagram_conflicts: list[DiagramPromotionConflict] = []
    enterprise_diag_ids = registry.enterprise_diagram_ids()
    enterprise_diag_index: dict[tuple[str, str], Any] = {}
    for diag_rec in repo.list_diagrams():
        if diag_rec.artifact_id in enterprise_diag_ids:
            key = (diag_rec.diagram_type, _normalize_name(diag_rec.name))
            enterprise_diag_index[key] = diag_rec
    for did in diagram_ids or []:
        diag = repo.get_diagram(did)
        if diag is None:
            warnings.append(f"Diagram not found: {did}")
            continue
        if did in enterprise_diag_ids:
            already.append(did)
            continue
        key = (diag.diagram_type, _normalize_name(diag.name))
        ent_diag = enterprise_diag_index.get(key)
        if ent_diag is not None:
            diagram_conflicts.append(
                DiagramPromotionConflict(
                    engagement_id=did,
                    enterprise_id=ent_diag.artifact_id,
                    diagram_type=diag.diagram_type,
                    engagement_name=diag.name,
                    enterprise_name=ent_diag.name,
                )
            )
        else:
            diags_to_add.append(did)

    schema_errors = check_promotion_schema_compatibility(
        entity_ids=to_add + [c.engagement_id for c in conflicts],
        has_diagrams=bool(diags_to_add or diagram_conflicts),
        document_ids=docs_to_add + [c.engagement_id for c in doc_conflicts],
        registry=registry,
        repo=repo,
    )

    return PromotionPlan(
        root_entity=selected_ids[0] if selected_ids else (document_ids or diagram_ids or [""])[0],
        entities_to_add=to_add,
        conflicts=conflicts,
        connection_ids=conn_ids,
        already_in_enterprise=already,
        warnings=warnings,
        documents_to_add=docs_to_add,
        diagrams_to_add=diags_to_add,
        doc_conflicts=doc_conflicts,
        diagram_conflicts=diagram_conflicts,
        schema_errors=schema_errors,
    )
