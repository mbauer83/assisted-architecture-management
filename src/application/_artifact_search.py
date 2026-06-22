"""Standalone search and aggregation functions for ArtifactRepository."""

from __future__ import annotations

from typing import Literal, cast

from src.application._artifact_query_helpers import single_or_none as _single_or_none
from src.application._artifact_query_helpers import summary_group_key as _summary_group_key
from src.application.artifact_scoring import (
    score_connection,
    score_diagram,
    score_document,
    score_entity,
    tokenize,
)
from src.application.ports import ArtifactStorePort
from src.domain.artifact_types import (
    ConnectionRecord,
    DiagramRecord,
    DocumentRecord,
    EntityRecord,
    SearchHit,
    SearchResult,
    SemanticSearchProvider,
)

# ── Canonical record-type vocabulary (shared with list_artifacts / WU-A3) ───
# Singular form: discriminator value on individual hit records.
RecordType = Literal["entity", "connection", "diagram", "document"]
# Plural form: member of an include-set that gates which kinds participate.
SearchableKind = Literal["entities", "connections", "diagrams", "documents"]

ALL_SEARCHABLE_KINDS: frozenset[str] = frozenset({"entities", "connections", "diagrams", "documents"})

_KIND_TO_RECORD_TYPE: dict[str, str] = {
    "entities": "entity",
    "connections": "connection",
    "diagrams": "diagram",
    "documents": "document",
}
_RECORD_TYPE_TO_KIND: dict[str, str] = {v: k for k, v in _KIND_TO_RECORD_TYPE.items()}

_NONE_LABEL = "(none)"
_RecordType = RecordType  # internal alias for cast()


def count_artifacts_by(
    store: ArtifactStorePort,
    group_by: Literal["artifact_type", "diagram_type", "domain", "group"],
    *,
    artifact_type: str | list[str] | None = None,
    domain: str | list[str] | None = None,
    status: str | list[str] | None = None,
    include_connections: bool = True,
    include_diagrams: bool = True,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    if group_by == "diagram_type":
        for diag in store.list_diagrams(status=_single_or_none(status)):
            key = diag.diagram_type or _NONE_LABEL
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))
    if group_by == "domain":
        for ent in store.list_entities(
            artifact_type=_single_or_none(artifact_type),
            domain=_single_or_none(domain),
            status=_single_or_none(status),
        ):
            key = ent.domain or _NONE_LABEL
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))
    if group_by == "group":
        result: dict[str, int] = {}
        for ent in store.list_entities(artifact_type=_single_or_none(artifact_type), status=_single_or_none(status)):
            result[f"entities/{ent.group}"] = result.get(f"entities/{ent.group}", 0) + 1
        for diag in store.list_diagrams(status=_single_or_none(status)):
            result[f"diagrams/{diag.group}"] = result.get(f"diagrams/{diag.group}", 0) + 1
        for doc in store.list_documents(status=_single_or_none(status)):
            result[f"documents/{doc.group}"] = result.get(f"documents/{doc.group}", 0) + 1
        return dict(sorted(result.items()))
    for summary in store.list_artifacts(
        artifact_type=artifact_type,
        domain=domain,
        status=status,
        include_connections=include_connections,
        include_diagrams=include_diagrams,
    ):
        key = _summary_group_key(summary, group_by)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def search_artifacts(
    store: ArtifactStorePort,
    semantic: SemanticSearchProvider | None,
    query: str,
    *,
    limit: int = 10,
    domain: str | list[str] | None = None,
    artifact_type: str | list[str] | None = None,
    include_entities: bool = True,
    include_connections: bool = True,
    include_diagrams: bool = True,
    include_documents: bool = True,
    prefer_record_type: RecordType | None = None,
    strict_record_type: bool = False,
) -> SearchResult:
    """Backward-compatible wrapper: maps old boolean flags to included_kinds."""
    kinds: set[str] = set()
    if include_entities:
        kinds.add("entities")
    if include_connections:
        kinds.add("connections")
    if include_diagrams:
        kinds.add("diagrams")
    if include_documents:
        kinds.add("documents")
    # strict_record_type: restrict search to just the preferred kind.
    if strict_record_type and prefer_record_type is not None:
        kind = _RECORD_TYPE_TO_KIND.get(prefer_record_type)
        if kind:
            kinds = {kind}
    prefer_kind = _RECORD_TYPE_TO_KIND.get(prefer_record_type) if prefer_record_type else None
    domains = domain if isinstance(domain, list) else ([domain] if domain else None)
    entity_types = artifact_type if isinstance(artifact_type, list) else ([artifact_type] if artifact_type else None)
    return search(
        store,
        semantic,
        query,
        limit=limit,
        domains=domains,
        entity_types=entity_types,
        included_kinds=frozenset(kinds),
        prefer_kind=prefer_kind,
    )


def search(
    store: ArtifactStorePort,
    semantic: SemanticSearchProvider | None,
    query: str,
    *,
    limit: int = 10,
    entity_types: list[str] | None = None,
    domains: list[str] | None = None,
    included_kinds: frozenset[str] | None = None,
    prefer_kind: str | None = None,
) -> SearchResult:
    """Search across requested kinds with per-kind FTS + scored supplement.

    ``included_kinds`` selects which record kinds participate (default: all four).
    Per-kind FTS limits prevent a dominant kind from starving minority kinds in
    the ranked results. For any included kind that returns zero FTS hits, the
    full scored path supplements.
    ``prefer_kind`` boosts one kind in cross-kind ranking without excluding others.
    """
    kinds = (included_kinds if included_kinds is not None else ALL_SEARCHABLE_KINDS) & ALL_SEARCHABLE_KINDS
    query_lc = query.lower()
    tokens = tokenize(query_lc)
    entity_type_set = set(entity_types) if entity_types else set()
    domain_set = set(domains) if domains else set()

    # Per-kind FTS: each kind gets its own slot budget to prevent starvation.
    per_kind_limit = max(limit * 2, 10)
    fts_hits = store.search_fts(
        query,
        limit=per_kind_limit,
        include_entities="entities" in kinds,
        include_connections="connections" in kinds,
        include_diagrams="diagrams" in kinds,
        include_documents="documents" in kinds,
    )

    seen: set[tuple[str, str]] = set()
    hits: list[SearchHit] = []
    fts_kinds_with_hits: set[str] = set()

    for artifact_id, record_type, score in fts_hits:
        artifact: EntityRecord | ConnectionRecord | DiagramRecord | DocumentRecord | None
        match record_type:
            case "entity":
                artifact = store.get_entity(artifact_id)
                if artifact is None:
                    continue
                if entity_type_set and artifact.artifact_type not in entity_type_set:
                    continue
                if domain_set and artifact.domain not in domain_set:
                    continue
            case "connection":
                artifact = store.get_connection(artifact_id)
                if artifact is None:
                    continue
            case "document":
                artifact = store.get_document(artifact_id)
                if artifact is None:
                    continue
            case "diagram":
                artifact = store.get_diagram(artifact_id)
                if artifact is None:
                    continue
            case _:
                continue
        key = (record_type, artifact_id)
        if key in seen:
            continue
        seen.add(key)
        fts_kinds_with_hits.add(_RECORD_TYPE_TO_KIND.get(record_type, ""))
        hits.append(SearchHit(score=score, record_type=cast(_RecordType, record_type), record=artifact))

    # Supplement scored path for any included kind that got zero FTS hits.
    for kind in kinds:
        if kind in fts_kinds_with_hits:
            continue
        match kind:
            case "entities":
                scored = _search_entities(store, query_lc, tokens, entity_type_set, domain_set)
            case "connections":
                scored = _search_connections(store, query_lc, tokens)
            case "diagrams":
                scored = _search_diagrams(store, query_lc, tokens)
            case "documents":
                scored = _search_documents(store, query_lc, tokens)
            case _:
                scored = []
        for h in scored:
            key = (h.record_type, h.record.artifact_id)
            if key not in seen:
                seen.add(key)
                hits.append(h)

    # Semantic supplement is entity-only; only inject when entities are in scope.
    if "entities" in kinds:
        _apply_semantic_supplement(store, semantic, query, hits, seen)

    prefer_rt = _KIND_TO_RECORD_TYPE.get(prefer_kind) if prefer_kind else None
    return SearchResult(query=query, hits=_rank_balanced(hits, limit, prefer_rt))


def _rank_balanced(hits: list[SearchHit], limit: int, prefer_rt: str | None) -> list[SearchHit]:
    """Select up to ``limit`` hits with fair representation across record kinds.

    Per-table FTS (bm25) and the token-match supplement produce scores on incomparable
    scales, so a single global sort lets a high-volume kind (entities) crowd minority
    kinds (diagrams, documents) out of the result window entirely. Instead, rank within
    each kind by its own score, then round-robin across kinds — ordering the kinds by
    their strongest hit (``prefer_rt`` first) — so every matching kind stays visible.
    """
    by_kind: dict[str, list[SearchHit]] = {}
    for h in hits:
        by_kind.setdefault(h.record_type, []).append(h)
    for group in by_kind.values():
        group.sort(key=lambda h: h.score, reverse=True)
    order = sorted(by_kind, key=lambda rt: by_kind[rt][0].score, reverse=True)
    if prefer_rt in by_kind:
        order = [prefer_rt, *(rt for rt in order if rt != prefer_rt)]
    ranked: list[SearchHit] = []
    rank = 0
    while len(ranked) < limit:
        drawn = [by_kind[rt][rank] for rt in order if rank < len(by_kind[rt])]
        if not drawn:
            break
        ranked.extend(drawn)
        rank += 1
    return ranked[:limit]


def _search_entities(
    store: ArtifactStorePort,
    query_lc: str,
    tokens: list[str],
    entity_type_set: set[str],
    domain_set: set[str],
) -> list[SearchHit]:
    hits = []
    for rec in store.list_entities():
        if entity_type_set and rec.artifact_type not in entity_type_set:
            continue
        if domain_set and rec.domain not in domain_set:
            continue
        if (score := score_entity(rec, query_lc, tokens)) > 0:
            hits.append(SearchHit(score=score, record_type="entity", record=rec))
    return hits


def _search_connections(store: ArtifactStorePort, query_lc: str, tokens: list[str]) -> list[SearchHit]:
    return [
        SearchHit(score=s, record_type="connection", record=r)
        for r in store.list_connections()
        if (s := score_connection(r, query_lc, tokens)) > 0
    ]


def _search_diagrams(store: ArtifactStorePort, query_lc: str, tokens: list[str]) -> list[SearchHit]:
    return [
        SearchHit(score=s, record_type="diagram", record=r)
        for r in store.list_diagrams()
        if (s := score_diagram(r, query_lc, tokens)) > 0
    ]


def _search_documents(store: ArtifactStorePort, query_lc: str, tokens: list[str]) -> list[SearchHit]:
    return [
        SearchHit(score=s, record_type="document", record=r)
        for r in store.list_documents()
        if (s := score_document(r, query_lc, tokens)) > 0
    ]


def _apply_semantic_supplement(
    store: ArtifactStorePort,
    semantic: SemanticSearchProvider | None,
    query: str,
    hits: list[SearchHit],
    seen: set[tuple[str, str]],
) -> None:
    if semantic is None or not isinstance(semantic, SemanticSearchProvider):
        return
    if len(store.entity_ids()) < 50:
        return
    for sem_score, artifact_id in semantic.top_k(query, k=1, threshold=0.75):
        if ("entity", artifact_id) in seen:
            continue
        rec = store.get_entity(artifact_id)
        if rec is not None:
            seen.add(("entity", artifact_id))
            hits.append(SearchHit(score=sem_score * 3.0, record_type="entity", record=rec))
