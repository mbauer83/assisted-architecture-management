"""Promote entities from engagement to enterprise repository.

"Promote" means transferring entity files (and their connections) from the
engagement repo into the enterprise repo.  This is a one-way operation.

Conflict detection matches entities by (artifact_type, friendly_name) so that
the same logical entity under different artifact_ids is recognized.

Conflict resolution strategies:
  - accept_engagement: replace enterprise content, keep enterprise artifact_id
  - accept_enterprise: skip, keep enterprise entity as-is
  - merge: caller provides merged field values (GUI merge form)

Execution logic lives in promote_execute.py.
"""

from __future__ import annotations

# Connection types traversed bidirectionally to build the transitive closure
# pre-selection for promotion.  Each captures a structural / dependency bond
# between elements that typically should travel together.
PROMOTION_TRAVERSAL_TYPES: frozenset[str] = frozenset({
    "archimate-composition",   # whole ↔ part (structural)
    "archimate-aggregation",   # whole ↔ part (weaker structural)
    "archimate-assignment",    # actor/role ↔ behavioural element
    "archimate-realization",   # implementation ↔ abstraction
    "archimate-serving",       # provider ↔ consumer of service
    "archimate-flow",          # data/material flow endpoint ↔ endpoint
    "archimate-triggering",    # trigger ↔ triggered process
})

from dataclasses import dataclass, field
from typing import Any, Literal

from src.common.artifact_query import ArtifactRepository
from src.common.artifact_verifier import ArtifactRegistry
from src.tools.artifact_write.parse_existing import parse_entity_file


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

def _parse_conn_full(cid: str) -> tuple[str, str, str] | None:
    """Parse canonical connection artifact IDs into (source, conn_type, target)."""
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


def _friendly_name(artifact_id: str) -> str:
    """Extract the friendly-name segment from an artifact_id."""
    parts = artifact_id.split(".")
    return ".".join(parts[2:]) if len(parts) > 2 else ""


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace("-", " ").replace("_", " ")


def _build_enterprise_name_index(
    repo: ArtifactRepository,
    registry: ArtifactRegistry,
) -> dict[tuple[str, str], Any]:
    """Build {(artifact_type, normalized_name): entity_record} for enterprise."""
    enterprise_ids = registry.enterprise_entity_ids()
    index: dict[tuple[str, str], Any] = {}
    for eid in enterprise_ids:
        rec = repo.get_entity(eid)
        if rec is None:
            continue
        key = (rec.artifact_type, _normalize_name(rec.name))
        index[key] = rec
    return index


def _entity_frontmatter(registry: ArtifactRegistry, eid: str) -> dict[str, Any]:
    """Read frontmatter fields for an entity."""
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
    entity_id: str,
    registry: ArtifactRegistry,
    repo: ArtifactRepository,
    *,
    include_transitive: bool = True,
    exclude_entity_ids: set[str] | None = None,
    exclude_connection_ids: set[str] | None = None,
) -> PromotionPlan:
    """Compute entities/connections to promote, detecting name-based conflicts.

    Transitive closure follows ``PROMOTION_TRAVERSAL_TYPES`` bidirectionally.
    ``exclude_entity_ids`` and ``exclude_connection_ids`` are removed from
    the preselection before returning so callers can prune the plan.
    """
    all_entities = registry.entity_ids()
    enterprise_ids = registry.enterprise_entity_ids()
    # GRFs are engagement-only proxies; never promote them
    grf_ids = {eid for eid in all_entities if eid.startswith("GRF@")}

    if entity_id not in all_entities:
        raise ValueError(f"Entity '{entity_id}' not found in model")

    # Build enterprise name index for conflict detection
    ent_index = _build_enterprise_name_index(repo, registry)

    candidates: list[str] = []
    already: list[str] = []
    visited: set[str] = set()
    warnings: list[str] = []

    # Pre-index connections by entity for efficient traversal
    conn_by_entity: dict[str, list[tuple[str, str, str]]] = {}
    for cid in registry.connection_ids():
        parsed = _parse_conn_full(cid)
        if parsed is None:
            continue
        src, conn_type, tgt = parsed
        conn_by_entity.setdefault(src, []).append((cid, conn_type, tgt))
        if tgt != src:
            conn_by_entity.setdefault(tgt, []).append((cid, conn_type, src))

    def _walk(eid: str) -> None:
        if eid in visited:
            return
        visited.add(eid)
        if eid in enterprise_ids:
            already.append(eid)
            return
        if eid in grf_ids:
            return  # GRFs are never promoted
        candidates.append(eid)
        if not include_transitive:
            return
        for _cid, conn_type, neighbor in conn_by_entity.get(eid, []):
            if conn_type not in PROMOTION_TRAVERSAL_TYPES:
                continue
            if neighbor in all_entities:
                _walk(neighbor)

    _walk(entity_id)

    # Classify candidates into fresh adds vs conflicts
    to_add: list[str] = []
    conflicts: list[PromotionConflict] = []
    for eid in candidates:
        rec = repo.get_entity(eid)
        if rec is None:
            warnings.append(f"Entity record not found for {eid}")
            continue
        key = (rec.artifact_type, _normalize_name(rec.name))
        ent_rec = ent_index.get(key)
        if ent_rec is not None:
            conflicts.append(PromotionConflict(
                engagement_id=eid,
                enterprise_id=ent_rec.artifact_id,
                artifact_type=rec.artifact_type,
                engagement_name=rec.name,
                enterprise_name=ent_rec.name,
                engagement_fields=_entity_frontmatter(registry, eid),
                enterprise_fields=_entity_frontmatter(registry, ent_rec.artifact_id),
            ))
        else:
            to_add.append(eid)

    # Connections: include those where source is promotable and target is
    # promotable, a resolved-conflict entity, or already in enterprise.
    promotable = set(to_add) | {c.engagement_id for c in conflicts}
    target_ok = promotable | enterprise_ids
    conn_ids: list[str] = []
    for cid in registry.connection_ids():
        parsed = _parse_conn_full(cid)
        if parsed is None:
            continue
        src, _conn_type, tgt = parsed
        if src in promotable and tgt in target_ok:
            conn_ids.append(cid)

    # Apply caller-supplied exclusions
    exc_ents = exclude_entity_ids or set()
    exc_conns = exclude_connection_ids or set()
    if exc_ents:
        to_add = [e for e in to_add if e not in exc_ents]
        already = [e for e in already if e not in exc_ents]
        conflicts = [c for c in conflicts if c.engagement_id not in exc_ents]
    if exc_conns:
        conn_ids = [c for c in conn_ids if c not in exc_conns]

    return PromotionPlan(
        root_entity=entity_id,
        entities_to_add=to_add,
        conflicts=conflicts,
        connection_ids=conn_ids,
        already_in_enterprise=already,
        warnings=warnings,
    )
