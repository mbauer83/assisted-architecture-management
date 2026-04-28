"""Preflight planning for bulk delete operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config.repo_paths import DOCS
from src.infrastructure.mcp.artifact_mcp.edit_tools import _require_registry, _resolve

from .common import KNOWN_DELETE_OPS
from .delete_plan import (
    ConnectionKey,
    collect_requests,
    planned_steps,
    validation_error,
)
from .diagram_refs import (
    connection_id_involves_entity,
    connection_ref_ids,
    entity_owned_connection_ids,
    find_diagram_path,
    find_document_path,
    scan_connections,
    scan_diagram_refs,
    scan_grf_refs,
    toposort_entities,
)


def preflight_bulk_delete(
    repo_root: Path,
    items: list[dict[str, Any]],
    *,
    auto_sync_diagrams: bool,
) -> tuple[
    dict[int, dict[str, object]],
    list[dict[str, Any]],
    list[ConnectionKey],
    list[str],
    list[str],
]:
    indexed = list(enumerate(items))
    results: dict[int, dict[str, object]] = {}
    planned: list[dict[str, Any]] = []

    unknown = [(index, item) for index, item in indexed if item.get("op") not in KNOWN_DELETE_OPS]
    if unknown:
        for index, item in unknown:
            results[index] = validation_error(
                str(item.get("op", "unknown")),
                f"Unknown op '{item.get('op')}'",
            )
        return results, planned, [], [], []

    root, registry, _verifier = _resolve(str(repo_root), need_registry=True)
    registry = _require_registry(registry)
    connection_paths, incoming = scan_connections(root)
    grf_refs = scan_grf_refs(root)
    diagram_refs = scan_diagram_refs(root)

    explicit_connection_deletes, entity_deletes, document_deletes, diagram_deletes, duplicate_errors = (
        collect_requests(indexed)
    )
    if duplicate_errors:
        for index, op, message in duplicate_errors:
            results[index] = validation_error(op, message)
        return results, planned, [], [], []

    entity_delete_set = set(entity_deletes)
    diagram_delete_set = set(diagram_deletes)
    explicit_connection_delete_set = set(explicit_connection_deletes)
    implicit_connection_deletes: set[ConnectionKey] = set()
    auto_sync_diagram_ids: set[str] = set()
    connection_ref_keys = [key for key in diagram_refs if " → " in key or ("---" in key and "@@" in key)]

    _validate_entity_deletes(
        entity_deletes=entity_deletes,
        entity_delete_set=entity_delete_set,
        diagram_delete_set=diagram_delete_set,
        explicit_connection_delete_set=explicit_connection_delete_set,
        connection_paths=connection_paths,
        incoming=incoming,
        grf_refs=grf_refs,
        diagram_refs=diagram_refs,
        connection_ref_keys=connection_ref_keys,
        registry=registry,
        root=root,
        auto_sync_diagrams=auto_sync_diagrams,
        results=results,
        implicit_connection_deletes=implicit_connection_deletes,
        auto_sync_diagram_ids=auto_sync_diagram_ids,
    )
    _validate_connection_deletes(
        explicit_connection_deletes=explicit_connection_deletes,
        connection_paths=connection_paths,
        diagram_refs=diagram_refs,
        diagram_delete_set=diagram_delete_set,
        auto_sync_diagrams=auto_sync_diagrams,
        results=results,
        auto_sync_diagram_ids=auto_sync_diagram_ids,
    )
    for artifact_id, index in document_deletes.items():
        if find_document_path(root, artifact_id) is None:
            results[index] = validation_error(
                "delete_document",
                f"Document '{artifact_id}' not found under {root / DOCS}",
            )
    for artifact_id, index in diagram_deletes.items():
        if find_diagram_path(root, artifact_id) is None:
            results[index] = validation_error(
                "delete_diagram",
                f"Diagram '{artifact_id}' not found in repo '{root}'",
            )
    if results:
        return results, planned, sorted(implicit_connection_deletes), [], sorted(auto_sync_diagram_ids)

    entity_order = toposort_entities(entity_delete_set, grf_refs)
    planned.extend(planned_steps(indexed=indexed, entity_order=entity_order))
    return (
        results,
        planned,
        sorted(implicit_connection_deletes),
        entity_order,
        sorted(auto_sync_diagram_ids),
    )

def _validate_entity_deletes(
    *,
    entity_deletes: dict[str, int],
    entity_delete_set: set[str],
    diagram_delete_set: set[str],
    explicit_connection_delete_set: set[ConnectionKey],
    connection_paths: dict[ConnectionKey, Path],
    incoming: dict[str, list[ConnectionKey]],
    grf_refs: dict[str, list[str]],
    diagram_refs: dict[str, list[str]],
    connection_ref_keys: list[str],
    registry: Any,
    root: Path,
    auto_sync_diagrams: bool,
    results: dict[int, dict[str, object]],
    implicit_connection_deletes: set[ConnectionKey],
    auto_sync_diagram_ids: set[str],
) -> None:
    for artifact_id, index in entity_deletes.items():
        blockers = _entity_delete_blockers(
            artifact_id=artifact_id,
            index=index,
            entity_delete_set=entity_delete_set,
            diagram_delete_set=diagram_delete_set,
            explicit_connection_delete_set=explicit_connection_delete_set,
            connection_paths=connection_paths,
            incoming=incoming,
            grf_refs=grf_refs,
            diagram_refs=diagram_refs,
            connection_ref_keys=connection_ref_keys,
            registry=registry,
            root=root,
            auto_sync_diagrams=auto_sync_diagrams,
            results=results,
            implicit_connection_deletes=implicit_connection_deletes,
            auto_sync_diagram_ids=auto_sync_diagram_ids,
        )
        if blockers:
            results[index] = validation_error(
                "delete_entity",
                (
                    f"Cannot delete entity '{artifact_id}' in this batch because dependent artifacts remain:\n"
                    + "\n".join(f"- {blocker}" for blocker in blockers)
                ),
            )


def _entity_delete_blockers(
    *,
    artifact_id: str,
    index: int,
    entity_delete_set: set[str],
    diagram_delete_set: set[str],
    explicit_connection_delete_set: set[ConnectionKey],
    connection_paths: dict[ConnectionKey, Path],
    incoming: dict[str, list[ConnectionKey]],
    grf_refs: dict[str, list[str]],
    diagram_refs: dict[str, list[str]],
    connection_ref_keys: list[str],
    registry: Any,
    root: Path,
    auto_sync_diagrams: bool,
    results: dict[int, dict[str, object]],
    implicit_connection_deletes: set[ConnectionKey],
    auto_sync_diagram_ids: set[str],
) -> list[str]:
    entity_file = registry.find_file_by_id(artifact_id)
    if entity_file is None:
        results[index] = validation_error("delete_entity", f"Entity '{artifact_id}' not found in model")
        return []
    try:
        entity_file.relative_to(root)
    except ValueError:
        results[index] = validation_error(
            "delete_entity",
            f"Entity '{artifact_id}' is not in writable repo '{root}'",
        )
        return []

    blockers: list[str] = []
    for conn in incoming.get(artifact_id, []):
        if conn in explicit_connection_delete_set:
            continue
        if conn[0] in entity_delete_set:
            implicit_connection_deletes.add(conn)
            continue
        blockers.append(f"incoming connection must also be deleted: {conn[0]} {conn[1]} -> {artifact_id}")

    _collect_entity_diagram_effects(
        artifact_id=artifact_id,
        diagram_delete_set=diagram_delete_set,
        connection_paths=connection_paths,
        diagram_refs=diagram_refs,
        connection_ref_keys=connection_ref_keys,
        auto_sync_diagrams=auto_sync_diagrams,
        blockers=blockers,
        auto_sync_diagram_ids=auto_sync_diagram_ids,
    )
    for gar_id in grf_refs.get(artifact_id, []):
        if gar_id not in entity_delete_set:
            blockers.append(f"global entity reference must also be deleted: {gar_id}")
    return blockers


def _collect_entity_diagram_effects(
    *,
    artifact_id: str,
    diagram_delete_set: set[str],
    connection_paths: dict[ConnectionKey, Path],
    diagram_refs: dict[str, list[str]],
    connection_ref_keys: list[str],
    auto_sync_diagrams: bool,
    blockers: list[str],
    auto_sync_diagram_ids: set[str],
) -> None:
    refs_to_check = set(diagram_refs.get(artifact_id, []))
    for owned_conn_id in entity_owned_connection_ids(artifact_id, connection_paths):
        refs_to_check.update(diagram_refs.get(owned_conn_id, []))
    if auto_sync_diagrams:
        for connection_id in connection_ref_keys:
            if connection_id_involves_entity(connection_id, artifact_id):
                refs_to_check.update(diagram_refs.get(connection_id, []))
    for ref in sorted(refs_to_check):
        if ref in diagram_delete_set:
            continue
        if auto_sync_diagrams:
            auto_sync_diagram_ids.add(ref)
        else:
            blockers.append(f"diagram must also be deleted: {ref}")


def _validate_connection_deletes(
    *,
    explicit_connection_deletes: dict[ConnectionKey, int],
    connection_paths: dict[ConnectionKey, Path],
    diagram_refs: dict[str, list[str]],
    diagram_delete_set: set[str],
    auto_sync_diagrams: bool,
    results: dict[int, dict[str, object]],
    auto_sync_diagram_ids: set[str],
) -> None:
    for key, index in explicit_connection_deletes.items():
        if key not in connection_paths:
            results[index] = validation_error(
                "delete_connection",
                f"Connection '{key[1]} -> {key[2]}' not found for source '{key[0]}'",
            )
            continue
        blocking_diagrams = sorted(
            {
                ref
                for connection_id in connection_ref_ids(key[0], key[1], key[2])
                for ref in diagram_refs.get(connection_id, [])
                if ref not in diagram_delete_set
            }
        )
        if not blocking_diagrams:
            continue
        if auto_sync_diagrams:
            auto_sync_diagram_ids.update(blocking_diagrams)
            continue
        results[index] = validation_error(
            "delete_connection",
            (
                f"Cannot delete connection '{key[1]} -> {key[2]}' in this batch because "
                "dependent diagrams remain:\n"
                + "\n".join(
                    f"- diagram must also be deleted: {diagram_id}"
                    for diagram_id in blocking_diagrams
                )
            ),
        )
