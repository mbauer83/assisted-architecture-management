"""MCP bulk write/delete tools: batched repository operations."""

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.application.verification.artifact_verifier_parsing import parse_diagram_refs, parse_frontmatter_from_path
from src.config.repo_paths import DIAGRAM_CATALOG, DIAGRAMS, DOCS, MODEL, RENDERED
from src.infrastructure.mcp.artifact_mcp.edit_tools import (
    _require_registry,
    _resolve,
    artifact_delete_diagram,
    artifact_delete_entity,
    artifact_edit_connection,
    artifact_edit_entity,
)
from src.infrastructure.mcp.artifact_mcp.tool_annotations import DESTRUCTIVE_LOCAL_WRITE, LOCAL_WRITE
from src.infrastructure.mcp.artifact_mcp.write.connection import _add_connection_impl
from src.infrastructure.mcp.artifact_mcp.write.document import artifact_delete_document
from src.infrastructure.mcp.artifact_mcp.write.entity import artifact_create_entity
from src.infrastructure.write.artifact_write.parse_existing import parse_outgoing_file

_KNOWN_OPS = frozenset({"create_entity", "add_connection", "edit_entity", "edit_connection"})
_KNOWN_DELETE_OPS = frozenset(
    {"delete_entity", "delete_connection", "delete_document", "delete_diagram"}
)


def _resolve_ref(value: str, ref_map: dict[str, str]) -> str:
    if value.startswith("$ref:"):
        key = value[5:]
        resolved = ref_map.get(key)
        if resolved is None:
            raise ValueError(
                f"Unresolved $ref '{key}' — no create_entity item with _ref='{key}' succeeded"
            )
        return resolved
    return value


def _strip(r: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in r.items() if k != "content"}


def _resolve_root(repo_root: str | None) -> Path:
    root, _registry, _verifier = _resolve(repo_root, need_registry=False)
    return root


def _batch_verification(
    repo_root: str | None,
    *,
    dry_run: bool,
    executed: bool,
) -> dict[str, object]:
    if dry_run or not executed:
        return {
            "valid": True,
            "executed": False,
            "counts": {"files": 0, "valid_files": 0, "invalid_files": 0, "errors": 0, "warnings": 0},
            "results": [],
        }
    root, registry, verifier = _resolve(repo_root, need_registry=True)
    registry = _require_registry(registry)
    results = verifier.verify_all(root, include_diagrams=True)
    invalid = [r for r in results if not r.valid]
    return {
        "valid": not invalid,
        "executed": True,
        "counts": {
            "files": len(results),
            "valid_files": sum(1 for r in results if r.valid),
            "invalid_files": len(invalid),
            "errors": sum(len(r.errors) for r in results),
            "warnings": sum(len(r.warnings) for r in results),
        },
        "results": [
            {
                "path": str(r.path),
                "file_type": r.file_type,
                "valid": r.valid,
                "issues": [
                    {
                        "severity": i.severity,
                        "code": i.code,
                        "message": i.message,
                        "location": i.location,
                    }
                    for i in r.issues
                ],
            }
            for r in invalid
        ],
        "repo_root": str(root),
        "registry_entities": len(registry.entity_ids()),
    }


def artifact_bulk_write(
    *,
    items: list[dict[str, Any]],
    dry_run: bool = True,
    repo_root: str | None = None,
) -> list[dict[str, object]]:
    """Execute a batch of create/edit operations in a single serialized call.

    Items are auto-ordered: create_entity → add_connection → edit_entity/edit_connection.
    Client ordering within each group is preserved.

    Supported ops and their fields:
      create_entity   — artifact_type, name, summary?, properties?, notes?, keywords?,
                        artifact_id?, version?, status?
                        Optional _ref key assigns a batch-local name; use $ref:name in
                        add_connection source_entity/target_entity within this batch.
      add_connection  — source_entity, connection_type, target_entity, description?,
                        src_cardinality?, tgt_cardinality?, version?, status?
                        source_entity/target_entity may be '$ref:name'.
      edit_entity     — artifact_id, name?, summary?, properties?, notes?, keywords?,
                        version?, status?
      edit_connection — source_entity, target_entity, connection_type, operation?,
                        description?, src_cardinality?, tgt_cardinality?

    Returns one result dict per input item (input order).
    Content is always omitted; use individual tools with dry_run=true to preview file output.
    """
    indexed = list(enumerate(items))
    creates_ent = [(i, it) for i, it in indexed if it.get("op") == "create_entity"]
    creates_con = [(i, it) for i, it in indexed if it.get("op") == "add_connection"]
    edits = [(i, it) for i, it in indexed if it.get("op") in ("edit_entity", "edit_connection")]
    unknown = [(i, it) for i, it in indexed if it.get("op") not in _KNOWN_OPS]

    results: dict[int, dict[str, object]] = {}
    ref_map: dict[str, str] = {}

    for i, item in creates_ent:
        ref = item.get("_ref")
        try:
            r = _strip(artifact_create_entity(
                artifact_type=item["artifact_type"],
                name=item["name"],
                summary=item.get("summary"),
                properties=item.get("properties"),
                notes=item.get("notes"),
                keywords=item.get("keywords"),
                artifact_id=item.get("artifact_id"),
                version=item.get("version", "0.1.0"),
                status=item.get("status", "draft"),
                dry_run=dry_run,
                repo_root=repo_root,
            ))
            r["op"] = "create_entity"
            results[i] = r
            if ref:
                ref_map[ref] = str(r["artifact_id"])
        except Exception as exc:  # noqa: BLE001
            results[i] = {"op": "create_entity", "error": str(exc), "wrote": False, "dry_run": dry_run}

    for i, item in creates_con:
        try:
            source = _resolve_ref(item["source_entity"], ref_map)
            target = _resolve_ref(item["target_entity"], ref_map)
            provisional_ids = frozenset(ref_map.values())
            r = _strip(_add_connection_impl(
                source_entity=source,
                connection_type=item["connection_type"],
                target_entity=target,
                description=item.get("description"),
                src_cardinality=item.get("src_cardinality"),
                tgt_cardinality=item.get("tgt_cardinality"),
                version=item.get("version", "0.1.0"),
                status=item.get("status", "draft"),
                dry_run=dry_run,
                repo_root=repo_root,
                provisional_ids=provisional_ids,
            ))
            r["op"] = "add_connection"
            results[i] = r
        except Exception as exc:  # noqa: BLE001
            results[i] = {"op": "add_connection", "error": str(exc), "wrote": False, "dry_run": dry_run}

    for i, item in edits:
        op = str(item.get("op", ""))
        try:
            if op == "edit_entity":
                r = _strip(artifact_edit_entity(
                    artifact_id=item["artifact_id"],
                    name=item.get("name"),
                    summary=item.get("summary"),
                    properties=item.get("properties"),
                    notes=item.get("notes"),
                    keywords=item.get("keywords"),
                    version=item.get("version"),
                    status=item.get("status"),
                    dry_run=dry_run,
                    repo_root=repo_root,
                ))
            else:
                r = _strip(artifact_edit_connection(
                    source_entity=item["source_entity"],
                    target_entity=item["target_entity"],
                    connection_type=item["connection_type"],
                    operation=item.get("operation", "update"),
                    description=item.get("description"),
                    src_cardinality=item.get("src_cardinality"),
                    tgt_cardinality=item.get("tgt_cardinality"),
                    dry_run=dry_run,
                    repo_root=repo_root,
                ))
            r["op"] = op
            results[i] = r
        except Exception as exc:  # noqa: BLE001
            results[i] = {"op": op, "error": str(exc), "wrote": False, "dry_run": dry_run}

    for i, item in unknown:
        results[i] = {
            "op": item.get("op", "unknown"),
            "error": f"Unknown op '{item.get('op')}'",
            "wrote": False,
            "dry_run": dry_run,
        }

    return [results[i] for i in range(len(items))]


def _connection_key(source_entity: str, connection_type: str, target_entity: str) -> tuple[str, str, str]:
    return (source_entity, connection_type, target_entity)


def _diagram_paths(repo_root: Path) -> list[Path]:
    diagrams_root = repo_root / DIAGRAM_CATALOG / DIAGRAMS
    if not diagrams_root.exists():
        return []
    paths: list[Path] = []
    for suffix in ("*.puml", "*.md"):
        for path in sorted(diagrams_root.rglob(suffix)):
            if path.parent.name != RENDERED:
                paths.append(path)
    return paths


def _find_diagram_artifact_id(path: Path) -> str | None:
    fm = parse_frontmatter_from_path(path) or {}
    artifact_id = str(fm.get("artifact-id", "")).strip()
    return artifact_id or None


def _find_document_path(repo_root: Path, artifact_id: str) -> Path | None:
    docs_root = repo_root / DOCS
    candidates = list(docs_root.rglob(f"{artifact_id}.md")) if docs_root.exists() else []
    return candidates[0] if candidates else None


def _find_diagram_path(repo_root: Path, artifact_id: str) -> Path | None:
    for path in _diagram_paths(repo_root):
        if _find_diagram_artifact_id(path) == artifact_id:
            return path
    return None


def _scan_connections(
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
            key = _connection_key(source, str(conn["connection_type"]), str(conn["target_entity"]))
            connection_paths[key] = outgoing_path
            incoming.setdefault(key[2], []).append(key)
    return connection_paths, incoming


def _scan_grf_refs(repo_root: Path) -> dict[str, list[str]]:
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


def _scan_diagram_refs(repo_root: Path) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    for path in _diagram_paths(repo_root):
        diagram_id = _find_diagram_artifact_id(path)
        if not diagram_id:
            continue
        parsed = parse_diagram_refs(path) or {}
        for entity_id in parsed.get("entity_ids", []):
            refs.setdefault(entity_id, []).append(diagram_id)
        for connection_id in parsed.get("connection_ids", []):
            refs.setdefault(connection_id, []).append(diagram_id)
    return refs


def _entity_owned_connection_ids(entity_id: str, connection_paths: dict[tuple[str, str, str], Path]) -> set[str]:
    return {f"{src} {conn_type} → {target}" for (src, conn_type, target) in connection_paths if src == entity_id}


def _toposort_entities(entity_ids: set[str], grf_refs: dict[str, list[str]]) -> list[str]:
    deps: dict[str, set[str]] = {entity_id: set() for entity_id in entity_ids}
    for target, gar_ids in grf_refs.items():
        if target not in entity_ids:
            continue
        for gar_id in gar_ids:
            if gar_id in entity_ids:
                deps[target].add(gar_id)

    ordered: list[str] = []
    remaining = {k: set(v) for k, v in deps.items()}
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


def _preflight_bulk_delete(
    repo_root: Path,
    items: list[dict[str, Any]],
) -> tuple[dict[int, dict[str, object]], list[dict[str, Any]], list[tuple[str, str, str]], list[str]]:
    indexed = list(enumerate(items))
    results: dict[int, dict[str, object]] = {}
    planned: list[dict[str, Any]] = []

    unknown = [(i, it) for i, it in indexed if it.get("op") not in _KNOWN_DELETE_OPS]
    if unknown:
        for i, item in unknown:
            results[i] = {
                "op": item.get("op", "unknown"),
                "error": f"Unknown op '{item.get('op')}'",
                "wrote": False,
                "dry_run": True,
            }
        return results, planned, [], []

    root, registry, _verifier = _resolve(str(repo_root), need_registry=True)
    registry = _require_registry(registry)
    connection_paths, incoming = _scan_connections(root)
    grf_refs = _scan_grf_refs(root)
    diagram_refs = _scan_diagram_refs(root)

    explicit_connection_deletes: dict[tuple[str, str, str], int] = {}
    entity_deletes: dict[str, int] = {}
    document_deletes: dict[str, int] = {}
    diagram_deletes: dict[str, int] = {}
    duplicate_errors: list[tuple[int, str, str]] = []

    for i, item in indexed:
        op = str(item.get("op", ""))
        if op == "delete_connection":
            try:
                key = _connection_key(
                    str(item["source_entity"]),
                    str(item["connection_type"]),
                    str(item["target_entity"]),
                )
            except KeyError as exc:
                duplicate_errors.append((i, op, f"Missing required field: {exc.args[0]}"))
                continue
            if key in explicit_connection_deletes:
                duplicate_errors.append((i, op, f"Duplicate delete_connection request for {key}"))
            else:
                explicit_connection_deletes[key] = i
        else:
            try:
                artifact_id = str(item["artifact_id"])
            except KeyError as exc:
                duplicate_errors.append((i, op, f"Missing required field: {exc.args[0]}"))
                continue
            bucket = {
                "delete_entity": entity_deletes,
                "delete_document": document_deletes,
                "delete_diagram": diagram_deletes,
            }[op]
            if artifact_id in bucket:
                duplicate_errors.append((i, op, f"Duplicate {op} request for '{artifact_id}'"))
            else:
                bucket[artifact_id] = i

    if duplicate_errors:
        for i, op, message in duplicate_errors:
            results[i] = {"op": op, "error": message, "wrote": False, "dry_run": True}
        return results, planned, [], []

    entity_delete_set = set(entity_deletes)
    diagram_delete_set = set(diagram_deletes)
    explicit_connection_delete_set = set(explicit_connection_deletes)
    implicit_connection_deletes: set[tuple[str, str, str]] = set()

    for artifact_id, index in entity_deletes.items():
        entity_file = registry.find_file_by_id(artifact_id)
        if entity_file is None:
            results[index] = {
                "op": "delete_entity",
                "error": f"Entity '{artifact_id}' not found in model",
                "wrote": False,
                "dry_run": True,
            }
            continue
        try:
            entity_file.relative_to(root)
        except ValueError:
            results[index] = {
                "op": "delete_entity",
                "error": f"Entity '{artifact_id}' is not in writable repo '{root}'",
                "wrote": False,
                "dry_run": True,
            }
            continue

        blockers: list[str] = []
        for conn in incoming.get(artifact_id, []):
            source_entity = conn[0]
            if conn in explicit_connection_delete_set:
                continue
            if source_entity in entity_delete_set:
                implicit_connection_deletes.add(conn)
                continue
            blockers.append(f"incoming connection must also be deleted: {source_entity} {conn[1]} -> {artifact_id}")

        owned_connection_ids = _entity_owned_connection_ids(artifact_id, connection_paths)
        for ref in diagram_refs.get(artifact_id, []):
            if ref not in diagram_delete_set:
                blockers.append(f"diagram must also be deleted: {ref}")
        for owned_conn_id in owned_connection_ids:
            for ref in diagram_refs.get(owned_conn_id, []):
                if ref not in diagram_delete_set:
                    blockers.append(f"diagram must also be deleted: {ref}")
        for gar_id in grf_refs.get(artifact_id, []):
            if gar_id not in entity_delete_set:
                blockers.append(f"global entity reference must also be deleted: {gar_id}")

        if blockers:
            results[index] = {
                "op": "delete_entity",
                "error": (
                    f"Cannot delete entity '{artifact_id}' in this batch because dependent artifacts remain:\n"
                    + "\n".join(f"- {blocker}" for blocker in blockers)
                ),
                "wrote": False,
                "dry_run": True,
            }

    for key, index in explicit_connection_deletes.items():
        if key not in connection_paths:
            results[index] = {
                "op": "delete_connection",
                "error": f"Connection '{key[1]} -> {key[2]}' not found for source '{key[0]}'",
                "wrote": False,
                "dry_run": True,
            }

    for artifact_id, index in document_deletes.items():
        path = _find_document_path(root, artifact_id)
        if path is None:
            results[index] = {
                "op": "delete_document",
                "error": f"Document '{artifact_id}' not found under {root / DOCS}",
                "wrote": False,
                "dry_run": True,
            }

    for artifact_id, index in diagram_deletes.items():
        path = _find_diagram_path(root, artifact_id)
        if path is None:
            results[index] = {
                "op": "delete_diagram",
                "error": f"Diagram '{artifact_id}' not found in repo '{root}'",
                "wrote": False,
                "dry_run": True,
            }

    if results:
        return results, planned, sorted(implicit_connection_deletes), []

    entity_order = _toposort_entities(entity_delete_set, grf_refs)
    entity_rank = {artifact_id: pos for pos, artifact_id in enumerate(entity_order)}

    for i, item in indexed:
        op = str(item.get("op", ""))
        if op == "delete_connection":
            planned.append({"phase": 0, "index": i, "item": item})
        elif op == "delete_diagram":
            planned.append({"phase": 1, "index": i, "item": item})
        elif op == "delete_document":
            planned.append({"phase": 2, "index": i, "item": item})
        elif op == "delete_entity":
            planned.append(
                {
                    "phase": 3,
                    "phase_order": entity_rank[str(item["artifact_id"])],
                    "index": i,
                    "item": item,
                }
            )
    planned.sort(key=lambda p: (int(p["phase"]), int(p.get("phase_order", 0)), int(p["index"])))
    return results, planned, sorted(implicit_connection_deletes), entity_order


def artifact_bulk_delete(
    *,
    items: list[dict[str, Any]],
    dry_run: bool = True,
    repo_root: str | None = None,
) -> dict[str, object]:
    """Execute a dependency-aware batch of destructive operations.

    Supported ops:
      delete_entity     — artifact_id
      delete_connection — source_entity, connection_type, target_entity
      delete_document   — artifact_id
      delete_diagram    — artifact_id

    Deletion batches are preflighted as a whole before any live write occurs.
    """
    root = _resolve_root(repo_root if repo_root is not None else None)
    results: dict[int, dict[str, object]] = {}
    preflight_errors, planned, implicit_connection_deletes, entity_order = _preflight_bulk_delete(
        root, items
    )
    if preflight_errors:
        results.update(preflight_errors)
        for i, item in enumerate(items):
            if i not in results:
                results[i] = {
                    "op": str(item.get("op", "unknown")),
                    "error": "Skipped because the delete batch failed preflight validation",
                    "wrote": False,
                    "dry_run": dry_run,
                }
        return {
            "results": [results[i] for i in range(len(items))],
            "batch_verification": {
                "valid": False,
                "executed": False,
                "preflight_errors": [results[i] for i in range(len(items)) if "error" in results[i]],
                "implicit_connection_deletes": [
                    {
                        "source_entity": src,
                        "connection_type": conn_type,
                        "target_entity": target,
                    }
                    for src, conn_type, target in implicit_connection_deletes
                ],
                "entity_delete_order": entity_order,
            },
        }

    executed = False
    skipped = False

    for src, conn_type, target in implicit_connection_deletes:
        if dry_run:
            continue
        artifact_edit_connection(
            source_entity=src,
            target_entity=target,
            connection_type=conn_type,
            operation="remove",
            dry_run=False,
            repo_root=str(root),
        )

    for step in planned:
        i = int(step["index"])
        item = step["item"]
        op = str(item.get("op", ""))
        if skipped:
            results[i] = {
                "op": op,
                "error": "Skipped because an earlier delete operation failed",
                "wrote": False,
                "dry_run": dry_run,
            }
            continue
        try:
            if op == "delete_connection":
                r = _strip(
                    artifact_edit_connection(
                        source_entity=str(item["source_entity"]),
                        target_entity=str(item["target_entity"]),
                        connection_type=str(item["connection_type"]),
                        operation="remove",
                        dry_run=dry_run,
                        repo_root=str(root),
                    )
                )
            elif op == "delete_diagram":
                r = _strip(
                    artifact_delete_diagram(
                        artifact_id=str(item["artifact_id"]),
                        dry_run=dry_run,
                        repo_root=str(root),
                    )
                )
            elif op == "delete_document":
                r = _strip(
                    artifact_delete_document(
                        artifact_id=str(item["artifact_id"]),
                        dry_run=dry_run,
                        repo_root=str(root),
                    )
                )
            else:
                r = _strip(
                    artifact_delete_entity(
                        artifact_id=str(item["artifact_id"]),
                        dry_run=dry_run,
                        repo_root=str(root),
                    )
                )
            r["op"] = op
            results[i] = r
            executed = executed or (not dry_run and bool(r.get("wrote")))
        except Exception as exc:  # noqa: BLE001
            results[i] = {"op": op, "error": str(exc), "wrote": False, "dry_run": dry_run}
            skipped = True

    batch_verification = _batch_verification(str(root), dry_run=dry_run, executed=executed)
    batch_verification["implicit_connection_deletes"] = [
        {
            "source_entity": src,
            "connection_type": conn_type,
            "target_entity": target,
        }
        for src, conn_type, target in implicit_connection_deletes
    ]
    batch_verification["entity_delete_order"] = entity_order
    return {
        "results": [results[i] for i in range(len(items))],
        "batch_verification": batch_verification,
    }


def register(mcp: FastMCP) -> None:
    from src.infrastructure.mcp.artifact_mcp.write_queue import queued

    mcp.tool(
        name="artifact_bulk_write",
        title="Artifact Write: Bulk Create/Edit",
        description=(
            "Batch entity creates, connection adds, and edits in one call. "
            "Items auto-sort (create_entity → add_connection → edits); submit in any order.\n"
            "op values: create_entity (artifact_type, name), "
            "add_connection (source_entity, connection_type, target_entity), "
            "edit_entity (artifact_id), "
            "edit_connection (source_entity, target_entity, connection_type, operation=update|remove). "
            "All other fields match the corresponding single-item tools.\n"
            "To connect entities created in the same batch: set '_ref':'<alias>' on the create_entity item, "
            "then use '$ref:<alias>' as source_entity or target_entity in add_connection — "
            "the backend substitutes the assigned artifact_id before processing connections.\n"
            "Returns one result per item (input order): op, artifact_id, wrote, verification, warnings?, error?. "
            "No file content in results. dry_run=true previews without writing."
        ),
        annotations=LOCAL_WRITE,
        structured_output=True,
    )(queued(artifact_bulk_write))

    mcp.tool(
        name="artifact_bulk_delete",
        title="Artifact Write: Bulk Delete",
        description=(
            "Batch destructive operations with dependency-aware planning and final repository verification. "
            "Supported ops: delete_entity (artifact_id), "
            "delete_connection (source_entity, connection_type, target_entity), "
            "delete_document (artifact_id), delete_diagram (artifact_id). "
            "The batch is preflighted as a whole before any live deletes occur. "
            "Connections are removed before dependent entity deletes; diagrams/documents are removed before entities; "
            "the tool returns per-item results plus a batch_verification summary."
        ),
        annotations=DESTRUCTIVE_LOCAL_WRITE,
        structured_output=True,
    )(queued(artifact_bulk_delete))
