"""Bulk create/edit execution for MCP write tools."""

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
    KNOWN_OPS,
    normalize_staged_result,
    resolve_root,
    stage_batch_verification,
)
from .diagram_refs import auto_sync_diagrams, collect_bulk_write_auto_sync_diagram_ids
from .write_apply import apply_add_connections, apply_create_entities, apply_edits


def artifact_bulk_write(
    *,
    items: list[dict[str, Any]],
    dry_run: bool = True,
    repo_root: str | None = None,
    idempotency_key: str | None = None,
    auto_sync_diagrams: bool = False,
) -> list[dict[str, object]]:
    operation, reused_result = operation_registry.begin(
        tool_name="artifact_bulk_write",
        idempotency_key=idempotency_key,
    )
    if reused_result is not None:
        return reused_result

    live_root = resolve_root(repo_root)
    indexed = list(enumerate(items))
    creates_ent = [(index, item) for index, item in indexed if item.get("op") == "create_entity"]
    creates_con = [(index, item) for index, item in indexed if item.get("op") == "add_connection"]
    edits = [(index, item) for index, item in indexed if item.get("op") in {"edit_entity", "edit_connection"}]
    unknown = [(index, item) for index, item in indexed if item.get("op") not in KNOWN_OPS]
    if unknown:
        payload = _unknown_op_payload(
            indexed=indexed,
            unknown=unknown,
            dry_run=dry_run,
            operation_id=operation.operation_id,
        )
        operation_registry.complete(operation.operation_id, payload)
        return payload

    staging_dir, staged_root = create_staging_repo(live_root)
    try:
        payload = _execute_staged(
            indexed=indexed,
            creates_ent=creates_ent,
            creates_con=creates_con,
            edits=edits,
            staged_root=staged_root,
            live_root=live_root,
            dry_run=dry_run,
            auto_sync_enabled=auto_sync_diagrams,
            operation_id=operation.operation_id,
        )
        operation_registry.complete(operation.operation_id, payload)
        return payload
    finally:
        staging_dir.cleanup()


def _unknown_op_payload(
    *,
    indexed: list[tuple[int, dict[str, Any]]],
    unknown: list[tuple[int, dict[str, Any]]],
    dry_run: bool,
    operation_id: str,
) -> list[dict[str, object]]:
    results: dict[int, dict[str, object]] = {}
    for index, item in unknown:
        results[index] = {
            "op": item.get("op", "unknown"),
            "error": f"Unknown op '{item.get('op')}'",
            "wrote": False,
            "dry_run": dry_run,
            "operation_id": operation_id,
        }
    for index, item in indexed:
        if index not in results:
            results[index] = {
                "op": str(item.get("op", "unknown")),
                "error": "Skipped because the batch failed validation",
                "wrote": False,
                "dry_run": dry_run,
                "operation_id": operation_id,
            }
    return [results[index] for index in range(len(indexed))]


def _execute_staged(
    *,
    indexed: list[tuple[int, dict[str, Any]]],
    creates_ent: list[tuple[int, dict[str, Any]]],
    creates_con: list[tuple[int, dict[str, Any]]],
    edits: list[tuple[int, dict[str, Any]]],
    staged_root: Path,
    live_root: Path,
    dry_run: bool,
    auto_sync_enabled: bool,
    operation_id: str,
) -> list[dict[str, object]]:
    operation_registry.set_phase(operation_id, "apply")
    from .common import temp_repo_callbacks

    clear_repo_caches, mark_macros_dirty, macros_dirty, changed_paths = temp_repo_callbacks(staged_root)
    ref_map: dict[str, str] = {}
    results: dict[int, dict[str, object]] = {}
    skipped = apply_create_entities(
        creates_ent,
        ref_map=ref_map,
        results=results,
        clear_repo_caches=clear_repo_caches,
        mark_macros_dirty=mark_macros_dirty,
        staged_root=staged_root,
        dry_run=dry_run,
        operation_id=operation_id,
    )
    skipped = apply_add_connections(
        creates_con,
        ref_map=ref_map,
        results=results,
        clear_repo_caches=clear_repo_caches,
        mark_macros_dirty=mark_macros_dirty,
        staged_root=staged_root,
        dry_run=dry_run,
        operation_id=operation_id,
        skipped=skipped,
    )
    skipped = apply_edits(
        edits,
        results=results,
        clear_repo_caches=clear_repo_caches,
        mark_macros_dirty=mark_macros_dirty,
        staged_root=staged_root,
        dry_run=dry_run,
        operation_id=operation_id,
        skipped=skipped,
        current_registry=lambda: ArtifactRegistry(shared_artifact_index([staged_root])),
    )

    committed = False
    if not skipped:
        committed = _sync_verify_and_commit(
            indexed=indexed,
            results=results,
            staged_root=staged_root,
            live_root=live_root,
            dry_run=dry_run,
            auto_sync_enabled=auto_sync_enabled,
            clear_repo_caches=clear_repo_caches,
            changed_paths=changed_paths,
            macros_dirty=macros_dirty,
            operation_id=operation_id,
        )

    payload = [
        normalize_staged_result(
            results[index],
            staged_root=staged_root,
            live_root=live_root,
            dry_run=dry_run,
            committed=committed,
        )
        for index in range(len(indexed))
    ]
    for item in payload:
        item["operation_id"] = operation_id
    return payload


def _sync_verify_and_commit(
    *,
    indexed: list[tuple[int, dict[str, Any]]],
    results: dict[int, dict[str, object]],
    staged_root: Path,
    live_root: Path,
    dry_run: bool,
    auto_sync_enabled: bool,
    clear_repo_caches,
    changed_paths: set[Path],
    macros_dirty: set[Path],
    operation_id: str,
) -> bool:
    if auto_sync_enabled:
        operation_registry.set_phase(operation_id, "sync_diagrams")
        auto_sync_diagram_ids = collect_bulk_write_auto_sync_diagram_ids(
            staged_root,
            items=[item for _index, item in indexed],
            results=results,
        )
        auto_sync_diagrams(
            repo_root=staged_root,
            verifier=ArtifactVerifier(ArtifactRegistry(shared_artifact_index([staged_root]))),
            clear_repo_caches=clear_repo_caches,
            diagram_ids=auto_sync_diagram_ids,
            dry_run=dry_run,
        )

    operation_registry.set_phase(operation_id, "verify")
    verification = stage_batch_verification(staged_root, changed_paths=changed_paths)
    if not verification["valid"]:
        _mark_verification_failure(indexed=indexed, results=results, dry_run=dry_run, operation_id=operation_id)
        return False
    if dry_run:
        return False

    operation_registry.set_phase(operation_id, "update_index")
    commit_result = commit_staged_repo(live_root=live_root, staged_root=staged_root)
    mutation_context, _live_clear, live_mark_macros_dirty = authoritative_callbacks_for(live_root)
    for path in [*commit_result.changed_paths, *commit_result.deleted_paths]:
        mutation_context.record_changed(path)
    if macros_dirty:
        live_mark_macros_dirty(live_root)
    mutation_context.finalize()
    return True


def _mark_verification_failure(
    *,
    indexed: list[tuple[int, dict[str, Any]]],
    results: dict[int, dict[str, object]],
    dry_run: bool,
    operation_id: str,
) -> None:
    for index, item in indexed:
        existing = results.get(index)
        if existing is None:
            results[index] = {
                "op": str(item.get("op", "unknown")),
                "error": "Batch verification failed before commit",
                "wrote": False,
                "dry_run": dry_run,
                "operation_id": operation_id,
            }
        elif "error" not in existing:
            existing["error"] = "Batch verification failed before commit"
