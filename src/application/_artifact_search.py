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

_NONE_LABEL = "(none)"
_RecordType = Literal["entity", "connection", "diagram", "document"]


def count_artifacts_by(
    store: ArtifactStorePort,
    group_by: Literal["artifact_type", "diagram_type", "domain"],
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
    include_connections: bool = True,
    include_diagrams: bool = True,
    include_documents: bool = True,
    prefer_record_type: _RecordType | None = None,
    strict_record_type: bool = False,
) -> SearchResult:
    domains: set[str] = {d.lower() for d in (domain if isinstance(domain, list) else ([domain] if domain else []))}
    types: set[str] = set(
        artifact_type if isinstance(artifact_type, list) else ([artifact_type] if artifact_type else [])
    )
    return search(
        store,
        semantic,
        query,
        limit=limit,
        domains=list(domains) if domains else None,
        entity_types=list(types) if types else None,
        include_connections=include_connections,
        include_diagrams=include_diagrams,
        include_documents=include_documents,
        prefer_record_type=prefer_record_type,
        strict_record_type=strict_record_type,
    )


def search(
    store: ArtifactStorePort,
    semantic: SemanticSearchProvider | None,
    query: str,
    *,
    limit: int = 10,
    entity_types: list[str] | None = None,
    domains: list[str] | None = None,
    include_connections: bool = True,
    include_diagrams: bool = True,
    include_documents: bool = True,
    prefer_record_type: _RecordType | None = None,
    strict_record_type: bool = False,
) -> SearchResult:
    query_lc = query.lower()
    tokens = tokenize(query_lc)
    entity_type_set = set(entity_types) if entity_types else set()
    domain_set = set(domains) if domains else set()
    hits: list[SearchHit] = []

    fts_hits = store.search_fts(
        query,
        limit=max(limit * 4, 20),
        include_connections=include_connections,
        include_diagrams=include_diagrams,
        include_documents=include_documents,
        prefer_record_type=prefer_record_type,
        strict_record_type=strict_record_type,
    )
    seen: set[tuple[str, str]] = set()
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
        typed_rt = cast(_RecordType, record_type)
        hits.append(SearchHit(score=score, record_type=typed_rt, record=artifact))

    if not hits:
        hits.extend(_search_entities(store, query_lc, tokens, entity_type_set, domain_set))
        if include_connections:
            hits.extend(_search_connections(store, query_lc, tokens))
        if include_diagrams:
            hits.extend(_search_diagrams(store, query_lc, tokens))
        if include_documents:
            hits.extend(_search_documents(store, query_lc, tokens))

    _apply_semantic_supplement(store, semantic, query, hits)
    if strict_record_type and prefer_record_type is not None:
        hits = [h for h in hits if h.record_type == prefer_record_type]
    hits.sort(
        key=lambda h: (h.record_type == prefer_record_type, h.score) if prefer_record_type else h.score,
        reverse=True,
    )
    return SearchResult(query=query, hits=hits[:limit])


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
) -> None:
    if semantic is None or not isinstance(semantic, SemanticSearchProvider):
        return
    if len(store.entity_ids()) < 50:
        return
    seen_ids = {hit.record.artifact_id for hit in hits if hasattr(hit.record, "artifact_id")}
    for sem_score, artifact_id in semantic.top_k(query, k=1, threshold=0.75):
        if artifact_id in seen_ids:
            continue
        rec = store.get_entity(artifact_id)
        if rec is not None:
            hits.append(SearchHit(score=sem_score * 3.0, record_type="entity", record=rec))
