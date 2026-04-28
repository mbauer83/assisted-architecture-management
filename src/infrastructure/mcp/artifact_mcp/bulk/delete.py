"""Bulk delete execution for MCP write tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.application.verification.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.mcp.artifact_mcp.context import authoritative_callbacks_for
from src.infrastructure.write.artifact_write.batch_transaction import (
    commit_staged_repo,
    create_staging_repo,
)
from src.infrastructure.write.operation_registry import operation_registry

from .common import (
    normalize_staged_result,
    normalize_staged_verification,
    resolve_root,
    stage_batch_verification,
    temp_repo_callbacks,
)
from .delete_apply import (
    apply_implicit_connection_deletes,
    apply_planned_deletes,
    mark_delete_verification_failure,
    serialize_connections,
)
from .delete_preflight import preflight_bulk_delete
from .diagram_refs import auto_sync_diagrams


def artifact_bulk_delete(
    *,
    items: list[dict[str, Any]],
    dry_run: bool = True,
    repo_root: str | None = None,
    idempotency_key: str | None = None,
    auto_sync_diagrams: bool = False,
) -> dict[str, Any]:
    operation, reused_result = operation_registry.begin(
        tool_name="artifact_bulk_delete",
        idempotency_key=idempotency_key,
    )
    if reused_result is not None:
        return reused_result

    live_root = resolve_root(repo_root)
    operation_registry.set_phase(operation.operation_id, "preflight")
    preflight_errors, planned, implicit_deletes, entity_order, auto_sync_ids = preflight_bulk_delete(
        live_root,
        items,
        auto_sync_diagrams=auto_sync_diagrams,
    )
    if preflight_errors:
        payload = _preflight_failure_payload(
            items=items,
            results=preflight_errors,
            implicit_connection_deletes=implicit_deletes,
            entity_order=entity_order,
            operation_id=operation.operation_id,
        )
        operation_registry.complete(operation.operation_id, payload)
        return payload

    staging_dir, staged_root = create_staging_repo(live_root)
    try:
        payload = _execute_staged_delete_batch(
            staged_root=staged_root,
            live_root=live_root,
            items=items,
            planned=planned,
            implicit_connection_deletes=implicit_deletes,
            entity_order=entity_order,
            auto_sync_ids=auto_sync_ids,
            dry_run=dry_run,
            operation_id=operation.operation_id,
        )
    finally:
        staging_dir.cleanup()
    operation_registry.complete(operation.operation_id, payload)
    return payload


def _preflight_failure_payload(
    *,
    items: list[dict[str, Any]],
    results: dict[int, dict[str, object]],
    implicit_connection_deletes: list[tuple[str, str, str]],
    entity_order: list[str],
    operation_id: str,
) -> dict[str, Any]:
    for index, item in enumerate(items):
        if index not in results:
            results[index] = {
                "op": str(item.get("op", "unknown")),
                "error": "Skipped because the delete batch failed preflight validation",
                "wrote": False,
                "dry_run": True,
            }
        results[index]["operation_id"] = operation_id
    return {
        "results": [results[index] for index in range(len(items))],
        "batch_verification": {
            "valid": False,
            "executed": False,
            "preflight_errors": [results[index] for index in range(len(items)) if "error" in results[index]],
            "implicit_connection_deletes": serialize_connections(implicit_connection_deletes),
            "entity_delete_order": entity_order,
            "auto_synced_diagrams": [],
        },
        "operation_id": operation_id,
    }


def _execute_staged_delete_batch(
    *,
    staged_root: Path,
    live_root: Path,
    items: list[dict[str, Any]],
    planned: list[dict[str, Any]],
    implicit_connection_deletes: list[tuple[str, str, str]],
    entity_order: list[str],
    auto_sync_ids: list[str],
    dry_run: bool,
    operation_id: str,
) -> dict[str, Any]:
    results: dict[int, dict[str, object]] = {}
    clear_repo_caches, mark_macros_dirty, macros_dirty, changed_paths = temp_repo_callbacks(staged_root)
    registry = ArtifactRegistry(shared_artifact_index([staged_root]))
    verifier = ArtifactVerifier(registry)
    operation_registry.set_phase(operation_id, "apply")

    apply_implicit_connection_deletes(
        implicit_connection_deletes=implicit_connection_deletes,
        root=staged_root,
        registry=registry,
        verifier=verifier,
        clear_repo_caches=clear_repo_caches,
    )
    skipped = apply_planned_deletes(
        planned=planned,
        root=staged_root,
        registry=registry,
        verifier=verifier,
        clear_repo_caches=clear_repo_caches,
        mark_macros_dirty=mark_macros_dirty,
        operation_id=operation_id,
        results=results,
    )

    auto_sync_actions: list[dict[str, object]] = []
    if not skipped and auto_sync_ids:
        operation_registry.set_phase(operation_id, "sync_diagrams")
        auto_sync_actions = auto_sync_diagrams(
            repo_root=staged_root,
            verifier=ArtifactVerifier(ArtifactRegistry(shared_artifact_index([staged_root]))),
            clear_repo_caches=clear_repo_caches,
            diagram_ids=auto_sync_ids,
            dry_run=False,
        )

    verification = _staged_delete_verification(
        skipped=skipped,
        staged_root=staged_root,
        live_root=live_root,
        changed_paths=changed_paths,
        operation_id=operation_id,
    )
    committed = False
    if verification["valid"] and not dry_run:
        operation_registry.set_phase(operation_id, "update_index")
        commit_result = commit_staged_repo(live_root=live_root, staged_root=staged_root)
        mutation_context, _live_clear, live_mark_macros_dirty = authoritative_callbacks_for(live_root)
        for path in [*commit_result.changed_paths, *commit_result.deleted_paths]:
            mutation_context.record_changed(path)
        if macros_dirty:
            live_mark_macros_dirty(live_root)
        mutation_context.finalize()
        committed = True
    elif not verification["valid"]:
        mark_delete_verification_failure(
            results=results,
            items=items,
            dry_run=dry_run,
            operation_id=operation_id,
        )

    for item in results.values():
        item["operation_id"] = operation_id
    payload_results = [
        normalize_staged_result(
            results[index],
            staged_root=staged_root,
            live_root=live_root,
            dry_run=dry_run,
            committed=committed,
        )
        for index in range(len(items))
    ]
    verification["implicit_connection_deletes"] = serialize_connections(implicit_connection_deletes)
    verification["entity_delete_order"] = entity_order
    verification["auto_synced_diagrams"] = auto_sync_actions
    return {
        "results": payload_results,
        "batch_verification": verification,
        "operation_id": operation_id,
    }


def _staged_delete_verification(
    *,
    skipped: bool,
    staged_root: Path,
    live_root: Path,
    changed_paths: set[Path],
    operation_id: str,
) -> dict[str, object]:
    if skipped:
        return {
            "valid": False,
            "executed": False,
            "counts": {"files": 0, "valid_files": 0, "invalid_files": 0, "errors": 0, "warnings": 0},
            "results": [],
            "repo_root": str(live_root),
        }
    operation_registry.set_phase(operation_id, "verify")
    verification = stage_batch_verification(staged_root, changed_paths=changed_paths)
    return normalize_staged_verification(
        verification,
        staged_root=staged_root,
        live_root=live_root,
    )
