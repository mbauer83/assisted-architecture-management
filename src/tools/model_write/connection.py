from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.common.archimate_types import ALL_CONNECTION_TYPES
from src.common.model_verifier import ModelRegistry, ModelVerifier
from src.common.model_write import format_outgoing_markdown

from .boundary import assert_engagement_write_root, today_iso
from .types import WriteResult


def _verification_to_dict(path: Path, res) -> dict[str, object]:
    return {
        "path": str(path),
        "file_type": "connection",
        "valid": res.valid,
        "issues": [
            {"severity": i.severity, "code": i.code, "message": i.message, "location": i.location}
            for i in res.issues
        ],
    }


def _validate_inputs(
    registry: ModelRegistry,
    connection_type: str,
    source_entity: str,
    target_entity: str,
) -> None:
    if connection_type not in ALL_CONNECTION_TYPES:
        raise ValueError(f"Unknown connection type: {connection_type!r}")
    if source_entity not in registry.entity_ids():
        raise ValueError(f"Source entity '{source_entity}' not found in model")
    if target_entity not in registry.entity_ids():
        raise ValueError(f"Target entity '{target_entity}' not found in model")


def _resolve_outgoing_path(registry: ModelRegistry, source_entity: str) -> Path:
    source_file = registry.find_file_by_id(source_entity)
    if source_file is None:
        raise ValueError(f"Cannot locate file for source entity '{source_entity}'")
    return source_file.with_suffix(".outgoing.md")


def _build_content(
    outgoing_path: Path,
    source_entity: str,
    connection_type: str,
    target_entity: str,
    description: str | None,
    version: str,
    status: str,
    last_updated: str,
) -> str:
    conn_header = f"### {connection_type} → {target_entity}"

    if outgoing_path.exists():
        existing = outgoing_path.read_text(encoding="utf-8")
        if conn_header in existing:
            raise ValueError(
                f"Connection '{connection_type} → {target_entity}' already exists in {outgoing_path.name}"
            )
        new_section = f"\n\n{conn_header}\n"
        if description and description.strip():
            new_section += f"\n{description.strip()}\n"
        return existing.rstrip("\n") + new_section

    return format_outgoing_markdown(
        source_entity=source_entity,
        version=version,
        status=status,
        last_updated=last_updated,
        connections=[{
            "connection_type": connection_type,
            "target_entity": target_entity,
            "description": description or "",
        }],
    )


def _write_and_verify(
    outgoing_path: Path,
    content: str,
    verifier: ModelVerifier,
    connection_type: str,
    target_entity: str,
) -> WriteResult:
    prev = outgoing_path.read_text(encoding="utf-8") if outgoing_path.exists() else None
    outgoing_path.parent.mkdir(parents=True, exist_ok=True)
    outgoing_path.write_text(content, encoding="utf-8")

    res = verifier.verify_outgoing_file(outgoing_path)
    conn_id = f"{connection_type} → {target_entity}"

    if not res.valid:
        _rollback(outgoing_path, prev)
        return WriteResult(
            wrote=False, path=outgoing_path, artifact_id=conn_id,
            content=content, warnings=[], verification=_verification_to_dict(outgoing_path, res),
        )

    return WriteResult(
        wrote=True, path=outgoing_path, artifact_id=conn_id,
        content=None, warnings=[], verification=_verification_to_dict(outgoing_path, res),
    )


def _rollback(path: Path, prev: str | None) -> None:
    if prev is None:
        try:
            path.unlink()
        except OSError:
            pass
    else:
        path.write_text(prev, encoding="utf-8")


def add_connection(
    *,
    repo_root: Path,
    registry: ModelRegistry,
    verifier: ModelVerifier,
    clear_repo_caches: Callable[[Path], None],
    source_entity: str,
    connection_type: str,
    target_entity: str,
    description: str | None,
    version: str,
    status: str,
    last_updated: str | None,
    dry_run: bool,
) -> WriteResult:
    """Add a connection to the source entity's .outgoing.md file."""
    assert_engagement_write_root(repo_root)
    _validate_inputs(registry, connection_type, source_entity, target_entity)

    last = last_updated or today_iso()
    outgoing_path = _resolve_outgoing_path(registry, source_entity)
    conn_id = f"{connection_type} → {target_entity}"

    content = _build_content(
        outgoing_path, source_entity, connection_type, target_entity,
        description, version, status, last,
    )

    if dry_run:
        return WriteResult(
            wrote=False, path=outgoing_path, artifact_id=conn_id,
            content=content, warnings=[], verification=None,
        )

    result = _write_and_verify(outgoing_path, content, verifier, connection_type, target_entity)
    if result.wrote:
        clear_repo_caches(repo_root)
    return result
