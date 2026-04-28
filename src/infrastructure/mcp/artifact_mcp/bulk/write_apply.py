"""Execution helpers for staged bulk-write operations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.application.verification.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.infrastructure.mcp.artifact_mcp.write._common import _out
from src.infrastructure.mcp.artifact_mcp.write.connection import _add_connection_impl
from src.infrastructure.write import artifact_write_ops
from src.infrastructure.write.artifact_write.connection_edit import _UNSET as _CONN_UNSET
from src.infrastructure.write.artifact_write.entity_edit import _UNSET as _ENTITY_UNSET

from .common import resolve_ref, strip_content


def skipped_result(op: str, *, dry_run: bool, operation_id: str) -> dict[str, object]:
    return {
        "op": op,
        "error": "Skipped because an earlier batch item failed",
        "wrote": False,
        "dry_run": dry_run,
        "operation_id": operation_id,
    }


def error_result(
    op: str,
    exc: Exception,
    *,
    dry_run: bool,
    operation_id: str,
) -> dict[str, object]:
    return {
        "op": op,
        "error": str(exc),
        "wrote": False,
        "dry_run": dry_run,
        "operation_id": operation_id,
    }


def apply_create_entities(
    creates_ent: list[tuple[int, dict[str, Any]]],
    *,
    ref_map: dict[str, str],
    results: dict[int, dict[str, object]],
    clear_repo_caches: Callable[[Path], None],
    mark_macros_dirty: Callable[[Path], None],
    staged_root: Path,
    dry_run: bool,
    operation_id: str,
) -> bool:
    skipped = False
    for index, item in creates_ent:
        ref = item.get("_ref")
        if skipped:
            results[index] = skipped_result("create_entity", dry_run=dry_run, operation_id=operation_id)
            continue
        try:
            result = artifact_write_ops.create_entity(
                repo_root=staged_root,
                verifier=ArtifactVerifier(None),
                clear_repo_caches=clear_repo_caches,
                mark_macros_dirty=mark_macros_dirty,
                artifact_type=item["artifact_type"],
                name=item["name"],
                summary=item.get("summary"),
                properties=item.get("properties"),
                notes=item.get("notes"),
                keywords=item.get("keywords"),
                artifact_id=item.get("artifact_id"),
                version=item.get("version", "0.1.0"),
                status=item.get("status", "draft"),
                last_updated=None,
                dry_run=False,
            )
            out = strip_content(_out(result, dry_run=False))
            out["op"] = "create_entity"
            results[index] = out
            if ref:
                ref_map[ref] = str(out["artifact_id"])
            skipped = skipped or not result.wrote
        except Exception as exc:  # noqa: BLE001
            results[index] = error_result("create_entity", exc, dry_run=dry_run, operation_id=operation_id)
            skipped = True
    return skipped


def apply_add_connections(
    creates_con: list[tuple[int, dict[str, Any]]],
    *,
    ref_map: dict[str, str],
    results: dict[int, dict[str, object]],
    clear_repo_caches: Callable[[Path], None],
    mark_macros_dirty: Callable[[Path], None],
    staged_root: Path,
    dry_run: bool,
    operation_id: str,
    skipped: bool,
) -> bool:
    for index, item in creates_con:
        if skipped:
            results[index] = skipped_result("add_connection", dry_run=dry_run, operation_id=operation_id)
            continue
        try:
            source = resolve_ref(item["source_entity"], ref_map)
            target = resolve_ref(item["target_entity"], ref_map)
            provisional_ids = frozenset(ref_map.values())
            out = strip_content(
                _add_connection_impl(
                    source_entity=source,
                    connection_type=item["connection_type"],
                    target_entity=target,
                    description=item.get("description"),
                    src_cardinality=item.get("src_cardinality"),
                    tgt_cardinality=item.get("tgt_cardinality"),
                    version=item.get("version", "0.1.0"),
                    status=item.get("status", "draft"),
                    dry_run=False,
                    repo_root=str(staged_root),
                    provisional_ids=provisional_ids,
                    clear_repo_caches=clear_repo_caches,
                    mark_macros_dirty=mark_macros_dirty,
                )
            )
            out["op"] = "add_connection"
            results[index] = out
            skipped = skipped or not bool(out.get("wrote"))
        except Exception as exc:  # noqa: BLE001
            results[index] = error_result("add_connection", exc, dry_run=dry_run, operation_id=operation_id)
            skipped = True
    return skipped


def apply_edits(
    edits: list[tuple[int, dict[str, Any]]],
    *,
    results: dict[int, dict[str, object]],
    clear_repo_caches: Callable[[Path], None],
    mark_macros_dirty: Callable[[Path], None],
    staged_root: Path,
    dry_run: bool,
    operation_id: str,
    skipped: bool,
    current_registry: Callable[[], ArtifactRegistry],
) -> bool:
    for index, item in edits:
        op = str(item.get("op", ""))
        if skipped:
            results[index] = skipped_result(op, dry_run=dry_run, operation_id=operation_id)
            continue
        try:
            registry = current_registry()
            verifier = ArtifactVerifier(registry)
            result = _apply_single_edit(
                item=item,
                op=op,
                registry=registry,
                verifier=verifier,
                clear_repo_caches=clear_repo_caches,
                mark_macros_dirty=mark_macros_dirty,
                staged_root=staged_root,
            )
            out = strip_content(_out(result, dry_run=False))
            out["op"] = op
            results[index] = out
            skipped = skipped or not result.wrote
        except Exception as exc:  # noqa: BLE001
            results[index] = error_result(op, exc, dry_run=dry_run, operation_id=operation_id)
            skipped = True
    return skipped


def _apply_single_edit(
    *,
    item: dict[str, Any],
    op: str,
    registry: ArtifactRegistry,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    mark_macros_dirty: Callable[[Path], None],
    staged_root: Path,
):
    if op == "edit_entity":
        return artifact_write_ops.edit_entity(
            repo_root=staged_root,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=clear_repo_caches,
            mark_macros_dirty=mark_macros_dirty,
            artifact_id=item["artifact_id"],
            name=item.get("name"),
            summary=item["summary"] if "summary" in item else _ENTITY_UNSET,
            properties=item["properties"] if "properties" in item else _ENTITY_UNSET,
            notes=item["notes"] if "notes" in item else _ENTITY_UNSET,
            keywords=item["keywords"] if "keywords" in item else _ENTITY_UNSET,
            version=item.get("version"),
            status=item.get("status"),
            dry_run=False,
        )
    if item.get("operation", "update") == "remove":
        return artifact_write_ops.remove_connection(
            repo_root=staged_root,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=clear_repo_caches,
            source_entity=item["source_entity"],
            target_entity=item["target_entity"],
            connection_type=item["connection_type"],
            dry_run=False,
        )
    return artifact_write_ops.edit_connection(
        repo_root=staged_root,
        registry=registry,
        verifier=verifier,
        clear_repo_caches=clear_repo_caches,
        source_entity=item["source_entity"],
        target_entity=item["target_entity"],
        connection_type=item["connection_type"],
        description=item.get("description"),
        src_cardinality=item["src_cardinality"] if "src_cardinality" in item else _CONN_UNSET,
        tgt_cardinality=item["tgt_cardinality"] if "tgt_cardinality" in item else _CONN_UNSET,
        dry_run=False,
    )
