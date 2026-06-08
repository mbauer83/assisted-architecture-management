"""Diagram reference-ID inference helpers."""

import re
from functools import lru_cache
from pathlib import Path

from src.application.artifact_parsing import extract_declared_puml_aliases, normalize_puml_alias
from src.application.modeling.artifact_write import ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE
from src.domain.archimate_relation_rendering import strip_suppressed_relation_labels

from ._artifact_deduplication import get_repository


@lru_cache(maxsize=1)
def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry()


@lru_cache(maxsize=1)
def _symmetric_conn_types() -> frozenset[str]:
    return frozenset(
        str(name)
        for name, info in _registry().all_connection_types().items()
        if getattr(info, "symmetric", False)
    )


@lru_cache(maxsize=1)
def _suppressed_stereotype_tokens() -> frozenset[str]:
    from src.infrastructure.app_bootstrap import build_runtime_catalogs  # noqa: PLC0415

    return build_runtime_catalogs(_registry()).diagram_types.suppressed_stereotype_tokens()


def _collect_diagram_renderer_references(
    diagram_type: str,
    repo_root: Path,
    diagram_entities: dict[str, object],
    diagram_connections: list[dict[str, object]] | None,
    bindings: list[dict[str, object]] | None = None,
) -> tuple[list[str] | None, list[str] | None]:
    from src.infrastructure.diagram_type_registry import get_diagram_type  # noqa: PLC0415

    diagram_type_mod = get_diagram_type(diagram_type)
    refs = diagram_type_mod.renderer.collect_references(
        diagram_type,
        repo_root,
        diagram_entities=diagram_entities,
        diagram_connections=diagram_connections,
        bindings=bindings,
    )
    entity_ids = list(refs.entity_ids) if getattr(refs, "entity_ids", None) else None
    connection_ids = list(refs.connection_ids) if getattr(refs, "connection_ids", None) else None
    return entity_ids, connection_ids


def _merge_reference_ids(
    explicit: list[str] | None,
    collected: list[str] | None,
) -> list[str] | None:
    if explicit is None and collected is None:
        return None
    merged: list[str] = []
    for group in (explicit or [], collected or []):
        for value in group:
            if value not in merged:
                merged.append(value)
    return merged


_REL_MACRO_RE = re.compile(
    r"^\s*Rel_(?P<rel>[A-Za-z0-9]+)(?:_(?:Up|Down|Left|Right))?"
    r"\(\s*(?P<src>[A-Za-z0-9_-]+)\s*,\s*(?P<tgt>[A-Za-z0-9_-]+)",
    re.MULTILINE,
)
_REL_LINE_RE = re.compile(
    r"^\s*(?P<src>[A-Za-z0-9_-]+)\s+[-.*|o<>][^\n:]*\s+(?P<tgt>[A-Za-z0-9_-]+)\s*:\s*[^<\n]*?<<(?P<rel>[A-Za-z]+)>>",
    re.MULTILINE,
)


def _normalize_standard_alias(artifact_id: str) -> str:
    parts = artifact_id.split(".")
    if len(parts) < 2 or "@" not in parts[0]:
        return ""
    prefix = parts[0].split("@", 1)[0]
    return normalize_puml_alias(f"{prefix}_{parts[1]}")


def _alias_entity_lookup(repo_root: Path) -> dict[str, str]:
    repo = get_repository(repo_root)
    alias_map: dict[str, str] = {}
    for entity in repo.list_entities():
        if entity.display_alias:
            alias_map.setdefault(normalize_puml_alias(entity.display_alias), entity.artifact_id)
        std_alias = _normalize_standard_alias(entity.artifact_id)
        if std_alias:
            alias_map.setdefault(std_alias, entity.artifact_id)
    return alias_map


def _iter_declared_relations(content: str) -> list[tuple[str, str, str]]:
    relations: list[tuple[str, str, str]] = []
    for match in _REL_MACRO_RE.finditer(content):
        conn_type = ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE.get(match.group("rel").lower())
        if conn_type is None:
            continue
        relations.append(
            (
                normalize_puml_alias(match.group("src")),
                normalize_puml_alias(match.group("tgt")),
                conn_type,
            )
        )
    for match in _REL_LINE_RE.finditer(content):
        conn_type = ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE.get(match.group("rel").lower())
        if conn_type is None:
            continue
        relations.append(
            (
                normalize_puml_alias(match.group("src")),
                normalize_puml_alias(match.group("tgt")),
                conn_type,
            )
        )
    return relations


def _infer_reference_ids_from_puml(
    repo_root: Path,
    puml_body: str,
) -> tuple[list[str] | None, list[str] | None]:
    repo = get_repository(repo_root)
    alias_map = _alias_entity_lookup(repo_root)

    entity_ids: list[str] = []
    for alias in sorted(extract_declared_puml_aliases(puml_body)):
        artifact_id = alias_map.get(normalize_puml_alias(alias))
        if artifact_id is not None and artifact_id not in entity_ids:
            entity_ids.append(artifact_id)

    conn_index: dict[tuple[str, str, str], str] = {}
    reverse_conn_index: dict[tuple[str, str, str], str] = {}
    symmetric_types = _symmetric_conn_types()
    for conn in repo.list_connections():
        conn_index[(conn.source, conn.target, conn.conn_type)] = conn.artifact_id
        if conn.conn_type in symmetric_types:
            reverse_conn_index[(conn.target, conn.source, conn.conn_type)] = conn.artifact_id

    connection_ids: list[str] = []
    for src_alias, tgt_alias, conn_type in _iter_declared_relations(puml_body):
        src_id = alias_map.get(src_alias)
        tgt_id = alias_map.get(tgt_alias)
        if src_id is None or tgt_id is None:
            continue
        artifact_id = conn_index.get((src_id, tgt_id, conn_type))
        if artifact_id is None and conn_type in symmetric_types:
            artifact_id = reverse_conn_index.get((src_id, tgt_id, conn_type))
        if artifact_id is not None and artifact_id not in connection_ids:
            connection_ids.append(artifact_id)

    return entity_ids or None, connection_ids or None


def _prepare_diagram_puml_body(puml_body: str, repo_root: Path, diagram_type: str) -> str:
    from src.infrastructure.diagram_type_registry import get_diagram_type  # noqa: PLC0415

    # Drop relation-stereotype edge labels the arrow style already conveys. This
    # is an ontology-global normalisation (keyed on ``show_stereotype`` across all
    # connection types), not a per-diagram-type concern, so it applies uniformly.
    puml_body = strip_suppressed_relation_labels(puml_body, _suppressed_stereotype_tokens())
    diagram_type_mod = get_diagram_type(diagram_type)
    return diagram_type_mod.renderer.inject_includes(puml_body, repo_root)
