from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from src.domain.archimate_relation_rendering import format_cardinality_label
from src.domain.artifact_types import ConnectionRecord
from src.domain.ontology_protocol import DiagramRendererReferences
from src.infrastructure.rendering.generic_puml_renderer import GenericPumlRenderer


class ArchimatePumlRenderer(GenericPumlRenderer):
    """ArchiMate-specific renderer extensions for opt-in connection annotations."""

    def visible_connection_label(
        self,
        conn: ConnectionRecord,
        diagram_connections: list[dict[str, object]] | None = None,
    ) -> str:
        spec = _connection_annotation_spec(conn.artifact_id, diagram_connections)
        if spec is None:
            return super().visible_connection_label(conn, diagram_connections)

        label_parts: list[str] = []
        if bool(spec.get("include_cardinality")):
            cardinality = format_cardinality_label(conn.src_cardinality, conn.tgt_cardinality)
            if cardinality:
                label_parts.append(cardinality)
        if bool(spec.get("include_description")) and conn.content_text.strip():
            label_parts.append(conn.content_text.strip())
        extra = str(spec.get("label") or "").strip()
        if extra:
            label_parts.append(extra)
        return " | ".join(part for part in label_parts if part)

    def collect_references(
        self,
        diagram_type: str,
        repo_root: Path,
        *,
        diagram_entities: Mapping[str, object] | None = None,
        diagram_connections: list[dict[str, object]] | None = None,
        bindings: list[dict[str, object]] | None = None,
    ) -> DiagramRendererReferences:
        del diagram_type, repo_root, diagram_entities, bindings
        connection_ids: list[str] = []
        for item in diagram_connections or []:
            if not isinstance(item, dict):
                continue
            artifact_id = str(item.get("artifact_id") or item.get("connection_id") or "").strip()
            if artifact_id and artifact_id not in connection_ids:
                connection_ids.append(artifact_id)
        return DiagramRendererReferences(connection_ids=tuple(connection_ids))


def _connection_annotation_spec(
    artifact_id: str,
    diagram_connections: list[dict[str, object]] | None,
) -> dict[str, object] | None:
    for item in diagram_connections or []:
        if not isinstance(item, dict):
            continue
        current = str(item.get("artifact_id") or item.get("connection_id") or "").strip()
        if current == artifact_id:
            return item
    return None
