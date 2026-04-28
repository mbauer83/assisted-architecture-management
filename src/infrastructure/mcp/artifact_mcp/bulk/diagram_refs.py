"""Diagram reference scanning and bulk auto-sync helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.application.artifact_repository import ArtifactRepository
from src.application.verification.artifact_verifier import ArtifactVerifier
from src.application.verification.artifact_verifier_parsing import (
    parse_diagram_refs,
    parse_frontmatter_from_path,
)
from src.config.repo_paths import DIAGRAM_CATALOG, DIAGRAMS, DOCS, MODEL, RENDERED
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.write import artifact_write_ops
from src.infrastructure.write.artifact_write.parse_existing import parse_outgoing_file


def connection_artifact_id(source_entity: str, connection_type: str, target_entity: str) -> str:
    return f"{source_entity}---{target_entity}@@{connection_type}"


def legacy_connection_ref_id(source_entity: str, connection_type: str, target_entity: str) -> str:
    return f"{source_entity} {connection_type} → {target_entity}"


def connection_ref_ids(source_entity: str, connection_type: str, target_entity: str) -> set[str]:
    return {
        connection_artifact_id(source_entity, connection_type, target_entity),
        legacy_connection_ref_id(source_entity, connection_type, target_entity),
    }


def parse_connection_ref_id(connection_id: str) -> tuple[str, str, str] | None:
    if "---" in connection_id and "@@" in connection_id:
        try:
            source, remainder = connection_id.split("---", 1)
            target, connection_type = remainder.rsplit("@@", 1)
        except ValueError:
            return None
        return source, target, connection_type
    if " → " in connection_id:
        try:
            left, target = connection_id.split(" → ", 1)
            source, connection_type = left.split(" ", 1)
        except ValueError:
            return None
        return source, target, connection_type
    return None


def connection_id_involves_entity(connection_id: str, entity_id: str) -> bool:
    parsed = parse_connection_ref_id(connection_id)
    if parsed is None:
        return False
    source, target, _connection_type = parsed
    return source == entity_id or target == entity_id


def diagram_paths(repo_root: Path) -> list[Path]:
    diagrams_root = repo_root / DIAGRAM_CATALOG / DIAGRAMS
    if not diagrams_root.exists():
        return []
    paths: list[Path] = []
    for suffix in ("*.puml", "*.md"):
        for path in sorted(diagrams_root.rglob(suffix)):
            if path.parent.name != RENDERED:
                paths.append(path)
    return paths


def find_diagram_artifact_id(path: Path) -> str | None:
    fm = parse_frontmatter_from_path(path) or {}
    artifact_id = str(fm.get("artifact-id", "")).strip()
    return artifact_id or None


def find_document_path(repo_root: Path, artifact_id: str) -> Path | None:
    docs_root = repo_root / DOCS
    candidates = list(docs_root.rglob(f"{artifact_id}.md")) if docs_root.exists() else []
    return candidates[0] if candidates else None


def find_diagram_path(repo_root: Path, artifact_id: str) -> Path | None:
    for path in diagram_paths(repo_root):
        if find_diagram_artifact_id(path) == artifact_id:
            return path
    return None


def scan_connections(
    repo_root: Path,
) -> tuple[dict[tuple[str, str, str], Path], dict[str, list[tuple[str, str, str]]]]:
    connection_paths: dict[tuple[str, str, str], Path] = {}
    incoming: dict[str, list[tuple[str, str, str]]] = {}
    model_root = repo_root / MODEL
    if not model_root.exists():
        return connection_paths, incoming
    for outgoing_path in sorted(model_root.rglob("*.outgoing.md")):
        try:
            parsed = parse_outgoing_file(outgoing_path)
        except Exception:  # noqa: BLE001
            continue
        source = str(parsed.frontmatter.get("source-entity", ""))
        for conn in parsed.connections:
            key = (source, str(conn["connection_type"]), str(conn["target_entity"]))
            connection_paths[key] = outgoing_path
            incoming.setdefault(key[2], []).append(key)
    return connection_paths, incoming


def scan_grf_refs(repo_root: Path) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    model_root = repo_root / MODEL
    if not model_root.exists():
        return refs
    for path in sorted(model_root.rglob("*.md")):
        if path.name.endswith(".outgoing.md"):
            continue
        fm = parse_frontmatter_from_path(path) or {}
        if str(fm.get("artifact-type", "")) != "global-artifact-reference":
            continue
        target = str(fm.get("global-artifact-id", "")).strip()
        gar_id = str(fm.get("artifact-id", path.stem)).strip()
        if target and gar_id:
            refs.setdefault(target, []).append(gar_id)
    return refs


def scan_diagram_refs(repo_root: Path) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    for path in diagram_paths(repo_root):
        diagram_id = find_diagram_artifact_id(path)
        if not diagram_id:
            continue
        parsed = parse_diagram_refs(path) or {}
        for entity_id in parsed.get("entity_ids", []):
            refs.setdefault(entity_id, []).append(diagram_id)
        for connection_id in parsed.get("connection_ids", []):
            refs.setdefault(connection_id, []).append(diagram_id)
    return refs


def auto_sync_diagrams(
    *,
    repo_root: Path,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    diagram_ids: list[str],
    dry_run: bool,
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for diagram_id in sorted(set(diagram_ids)):
        store = ArtifactRepository(shared_artifact_index([repo_root]))
        result = artifact_write_ops.sync_diagram_to_model(
            repo_root=repo_root,
            store=store,
            verifier=verifier,
            clear_repo_caches=clear_repo_caches,
            artifact_id=diagram_id,
            dry_run=dry_run,
        )
        actions.append(
            {
                "artifact_id": diagram_id,
                "wrote": result.wrote,
                "deleted_diagram": result.deleted_diagram,
                "removed_entity_ids": result.removed_entity_ids,
                "removed_connection_ids": result.removed_connection_ids,
            }
        )
    return actions


def collect_bulk_write_auto_sync_diagram_ids(
    repo_root: Path,
    *,
    items: list[dict[str, Any]],
    results: dict[int, dict[str, object]],
) -> list[str]:
    refs = scan_diagram_refs(repo_root)
    diagram_ids: set[str] = set()
    connection_ref_keys = [key for key in refs if parse_connection_ref_id(key) is not None]

    for index, item in enumerate(items):
        result = results.get(index)
        if result is None or not bool(result.get("wrote")):
            continue
        op = str(item.get("op", ""))
        if op == "edit_entity":
            old_entity_id = str(item["artifact_id"])
            new_entity_id = str(result.get("artifact_id", old_entity_id))
            if new_entity_id == old_entity_id:
                continue
            diagram_ids.update(refs.get(old_entity_id, []))
            for connection_id in connection_ref_keys:
                if connection_id_involves_entity(connection_id, old_entity_id):
                    diagram_ids.update(refs.get(connection_id, []))
        elif op == "edit_connection" and item.get("operation", "update") == "remove":
            for connection_id in connection_ref_ids(
                str(item["source_entity"]),
                str(item["connection_type"]),
                str(item["target_entity"]),
            ):
                diagram_ids.update(refs.get(connection_id, []))
    return sorted(diagram_ids)


def entity_owned_connection_ids(
    entity_id: str, connection_paths: dict[tuple[str, str, str], Path]
) -> set[str]:
    return {
        connection_id
        for (src, conn_type, target) in connection_paths
        if src == entity_id
        for connection_id in connection_ref_ids(src, conn_type, target)
    }


def toposort_entities(entity_ids: set[str], grf_refs: dict[str, list[str]]) -> list[str]:
    deps: dict[str, set[str]] = {entity_id: set() for entity_id in entity_ids}
    for target, gar_ids in grf_refs.items():
        if target not in entity_ids:
            continue
        for gar_id in gar_ids:
            if gar_id in entity_ids:
                deps[target].add(gar_id)

    ordered: list[str] = []
    remaining = {entity_id: set(blockers) for entity_id, blockers in deps.items()}
    while remaining:
        ready = sorted(entity_id for entity_id, blockers in remaining.items() if not blockers)
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise ValueError(
                "Cannot resolve entity delete order because of cyclic inter-entity dependencies: "
                f"{cycle}"
            )
        for entity_id in ready:
            ordered.append(entity_id)
            remaining.pop(entity_id)
        for blockers in remaining.values():
            blockers.difference_update(ready)
    return ordered
