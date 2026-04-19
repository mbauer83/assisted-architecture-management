"""Connection editing and removal operations."""

from pathlib import Path
from collections.abc import Callable

from src.common.model_verifier import ModelRegistry, ModelVerifier
from src.common.model_write import format_outgoing_markdown

from .boundary import assert_engagement_write_root, today_iso
from .connection import _resolve_outgoing_path, verification_to_conn_dict, _rollback
from .types import WriteResult


_UNSET = object()


def edit_connection(
    *,
    repo_root: Path,
    registry: ModelRegistry,
    verifier: ModelVerifier,
    clear_repo_caches: Callable[[Path], None],
    source_entity: str,
    target_entity: str,
    connection_type: str,
    description: str | None = None,
    src_cardinality: str | None | object = _UNSET,
    tgt_cardinality: str | None | object = _UNSET,
    dry_run: bool,
) -> WriteResult:
    """Update an existing connection (description and/or cardinalities).

    Identifies the connection by (source, target, type) triple.
    Rebuilds the .outgoing.md file with the updated fields.
    Pass src_cardinality="" or tgt_cardinality="" to remove an existing cardinality.
    Omit (leave as _UNSET) to preserve the existing value.
    """
    assert_engagement_write_root(repo_root)
    outgoing_path = _resolve_outgoing_path(registry, source_entity)

    if not outgoing_path.exists():
        raise ValueError(f"No outgoing file for '{source_entity}'")

    from .parse_existing import parse_outgoing_file
    parsed = parse_outgoing_file(outgoing_path)

    # Find the target connection
    found = False
    for conn in parsed.connections:
        if conn["connection_type"] == connection_type and conn["target_entity"] == target_entity:
            conn["description"] = description or ""
            if src_cardinality is not _UNSET:
                if src_cardinality:
                    conn["src_cardinality"] = str(src_cardinality)
                else:
                    conn.pop("src_cardinality", None)
            if tgt_cardinality is not _UNSET:
                if tgt_cardinality:
                    conn["tgt_cardinality"] = str(tgt_cardinality)
                else:
                    conn.pop("tgt_cardinality", None)
            found = True
            break

    if not found:
        raise ValueError(
            f"Connection '{connection_type} -> {target_entity}' not found in {outgoing_path.name}"
        )

    content = format_outgoing_markdown(
        source_entity=source_entity,
        version=str(parsed.frontmatter.get("version", "0.1.0")),
        status=str(parsed.frontmatter.get("status", "draft")),
        last_updated=today_iso(),
        connections=parsed.connections,
    )
    conn_id = f"{connection_type} -> {target_entity}"

    if dry_run:
        return WriteResult(
            wrote=False, path=outgoing_path, artifact_id=conn_id,
            content=content, warnings=[], verification=None,
        )

    return _write_verify_clear(
        outgoing_path, content, verifier, conn_id, clear_repo_caches, repo_root,
    )


def remove_connection(
    *,
    repo_root: Path,
    registry: ModelRegistry,
    verifier: ModelVerifier,
    clear_repo_caches: Callable[[Path], None],
    source_entity: str,
    target_entity: str,
    connection_type: str,
    dry_run: bool,
) -> WriteResult:
    """Remove a connection from an .outgoing.md file.

    If this was the last connection, the .outgoing.md file is deleted.
    """
    assert_engagement_write_root(repo_root)
    outgoing_path = _resolve_outgoing_path(registry, source_entity)

    if not outgoing_path.exists():
        raise ValueError(f"No outgoing file for '{source_entity}'")

    from .parse_existing import parse_outgoing_file
    parsed = parse_outgoing_file(outgoing_path)
    conn_id = f"{connection_type} -> {target_entity}"

    original_count = len(parsed.connections)
    remaining = [
        c for c in parsed.connections
        if not (c["connection_type"] == connection_type and c["target_entity"] == target_entity)
    ]

    if len(remaining) == original_count:
        raise ValueError(f"Connection '{conn_id}' not found in {outgoing_path.name}")

    if dry_run:
        if not remaining:
            return WriteResult(
                wrote=False, path=outgoing_path, artifact_id=conn_id,
                content="(file would be deleted — last connection removed)",
                warnings=[], verification=None,
            )
        content = format_outgoing_markdown(
            source_entity=source_entity,
            version=str(parsed.frontmatter.get("version", "0.1.0")),
            status=str(parsed.frontmatter.get("status", "draft")),
            last_updated=today_iso(),
            connections=remaining,
        )
        return WriteResult(
            wrote=False, path=outgoing_path, artifact_id=conn_id,
            content=content, warnings=[], verification=None,
        )

    # Real write
    if not remaining:
        prev = outgoing_path.read_text(encoding="utf-8")
        outgoing_path.unlink()
        clear_repo_caches(repo_root)
        return WriteResult(
            wrote=True, path=outgoing_path, artifact_id=conn_id,
            content=None, warnings=["Deleted empty .outgoing.md file"],
            verification={"path": str(outgoing_path), "file_type": "connection",
                          "valid": True, "issues": []},
        )

    content = format_outgoing_markdown(
        source_entity=source_entity,
        version=str(parsed.frontmatter.get("version", "0.1.0")),
        status=str(parsed.frontmatter.get("status", "draft")),
        last_updated=today_iso(),
        connections=remaining,
    )

    return _write_verify_clear(
        outgoing_path, content, verifier, conn_id, clear_repo_caches, repo_root,
    )


def _write_verify_clear(
    outgoing_path: Path,
    content: str,
    verifier: ModelVerifier,
    conn_id: str,
    clear_repo_caches: Callable[[Path], None],
    repo_root: Path,
) -> WriteResult:
    """Write content, verify, rollback on failure, clear caches on success."""
    prev = outgoing_path.read_text(encoding="utf-8") if outgoing_path.exists() else None
    outgoing_path.parent.mkdir(parents=True, exist_ok=True)
    outgoing_path.write_text(content, encoding="utf-8")

    res = verifier.verify_outgoing_file(outgoing_path)
    vdict = verification_to_conn_dict(outgoing_path, res)

    if not res.valid:
        _rollback(outgoing_path, prev)
        return WriteResult(
            wrote=False, path=outgoing_path, artifact_id=conn_id,
            content=content, warnings=[], verification=vdict,
        )

    clear_repo_caches(repo_root)
    return WriteResult(
        wrote=True, path=outgoing_path, artifact_id=conn_id,
        content=None, warnings=[], verification=vdict,
    )
