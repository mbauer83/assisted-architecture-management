import re
from collections.abc import Callable
from pathlib import Path

from src.application.modeling.artifact_write import format_outgoing_markdown
from src.application.verification.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.domain.archimate_types import ALL_CONNECTION_TYPES

from .boundary import assert_engagement_write_root, today_iso
from .types import WriteResult

_JUNCTION_ENTITY_TYPES = frozenset({"and-junction", "or-junction"})
_CONN_TYPE_RE = re.compile(r"^### (\S+)", re.MULTILINE)


def verification_to_conn_dict(path: Path, res) -> dict[str, object]:
    return {
        "path": str(path),
        "file_type": "connection",
        "valid": res.valid,
        "issues": [
            {"severity": i.severity, "code": i.code, "message": i.message, "location": i.location} for i in res.issues
        ],
    }


def _entity_artifact_type(registry: ArtifactRegistry, entity_id: str) -> str | None:
    """Read artifact-type from an entity's frontmatter without importing the full parser."""
    import yaml as _yaml

    path = registry.find_file_by_id(entity_id)
    if path is None:
        return None
    try:
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return None
        end = content.find("\n---", 3)
        if end == -1:
            return None
        fm: dict[str, object] = _yaml.safe_load(content[3:end].strip()) or {}
        return str(fm.get("artifact-type", "")) or None
    except Exception:
        return None


def _check_junction_homogeneity(
    registry: ArtifactRegistry,
    connection_type: str,
    source_entity: str,
    target_entity: str,
) -> None:
    """Enforce that all connections at a junction have the same relationship type.

    Reads the junction's .outgoing.md file to determine the locked type (set by
    the first connection added).  Checks both the source and target when either
    is a junction.  Incoming connections to a junction (stored in other entities'
    outgoing files) are not checked here — the write layer enforces homogeneity
    whenever a connection involving a junction is written.
    """
    for entity_id in (source_entity, target_entity):
        if _entity_artifact_type(registry, entity_id) not in _JUNCTION_ENTITY_TYPES:
            continue
        junc_file = registry.find_file_by_id(entity_id)
        if junc_file is None:
            continue
        out_file = junc_file.with_suffix(".outgoing.md")
        if not out_file.exists():
            continue
        existing_types = {
            m for m in _CONN_TYPE_RE.findall(out_file.read_text(encoding="utf-8")) if m != connection_type
        }
        if existing_types:
            locked = sorted(existing_types)[0]
            raise ValueError(
                f"Junction '{entity_id}' is locked to connection type '{locked}' "
                f"(determined by its first connection). All connections at a junction "
                f"must be the same type. Cannot add '{connection_type}'."
            )


def _validate_inputs(
    registry: ArtifactRegistry,
    connection_type: str,
    source_entity: str,
    target_entity: str,
    extra_known_ids: frozenset[str] = frozenset(),
) -> None:
    if connection_type not in ALL_CONNECTION_TYPES:
        raise ValueError(f"Unknown connection type: {connection_type!r}")
    known_ids = registry.entity_ids() | extra_known_ids
    if source_entity not in known_ids:
        raise ValueError(f"Source entity '{source_entity}' not found in model")
    if target_entity not in known_ids:
        raise ValueError(f"Target entity '{target_entity}' not found in model")
    _check_junction_homogeneity(registry, connection_type, source_entity, target_entity)


def _resolve_outgoing_path(
    registry: ArtifactRegistry,
    source_entity: str,
    *,
    dry_run: bool = False,
    extra_known_ids: frozenset[str] = frozenset(),
) -> Path:
    source_file = registry.find_file_by_id(source_entity)
    if source_file is not None:
        return source_file.with_suffix(".outgoing.md")
    if dry_run and source_entity in extra_known_ids:
        # Provisional entity: return a synthetic path for content preview
        repo_roots = registry.repo_roots
        if repo_roots:
            return repo_roots[0] / f"{source_entity}.outgoing.md"
    raise ValueError(f"Cannot locate file for source entity '{source_entity}'")


def _build_content(
    outgoing_path: Path,
    source_entity: str,
    connection_type: str,
    target_entity: str,
    description: str | None,
    version: str,
    status: str,
    last_updated: str,
    src_cardinality: str | None = None,
    tgt_cardinality: str | None = None,
) -> str:
    src_part = f" [{src_cardinality}]" if src_cardinality else ""
    tgt_part = f"[{tgt_cardinality}] " if tgt_cardinality else ""
    conn_header = f"### {connection_type}{src_part} → {tgt_part}{target_entity}"

    if outgoing_path.exists():
        existing = outgoing_path.read_text(encoding="utf-8")
        # Duplicate check ignores cardinalities — same (conn_type, target) pair is a duplicate
        dup_marker = f"### {connection_type} → "
        dup_marker_with_card = f"### {connection_type} ["
        for line in existing.splitlines():
            if line.startswith(dup_marker) or line.startswith(dup_marker_with_card):
                _, after_arrow = line.split(" → ", 1)
                existing_target = after_arrow.strip()
                if existing_target.startswith("["):
                    bracket_end = existing_target.find("]")
                    if bracket_end != -1:
                        existing_target = existing_target[bracket_end + 1 :].lstrip()
                if existing_target == target_entity:
                    raise ValueError(
                        f"Connection '{connection_type} → {target_entity}' already exists in {outgoing_path.name}"
                    )
        new_section = f"\n\n{conn_header}\n"
        if description and description.strip():
            new_section += f"\n{description.strip()}\n"
        return existing.rstrip("\n") + new_section

    conn_dict: dict[str, object] = {
        "connection_type": connection_type,
        "target_entity": target_entity,
        "description": description or "",
    }
    if src_cardinality:
        conn_dict["src_cardinality"] = src_cardinality
    if tgt_cardinality:
        conn_dict["tgt_cardinality"] = tgt_cardinality
    return format_outgoing_markdown(
        source_entity=source_entity,
        version=version,
        status=status,
        last_updated=last_updated,
        connections=[conn_dict],
    )


def _write_and_verify(
    outgoing_path: Path,
    content: str,
    verifier: ArtifactVerifier,
    source_entity: str,
    connection_type: str,
    target_entity: str,
) -> WriteResult:
    prev = outgoing_path.read_text(encoding="utf-8") if outgoing_path.exists() else None
    outgoing_path.parent.mkdir(parents=True, exist_ok=True)
    outgoing_path.write_text(content, encoding="utf-8")

    res = verifier.verify_outgoing_file(outgoing_path)
    conn_id = f"{source_entity}---{target_entity}@@{connection_type}"

    if not res.valid:
        _rollback(outgoing_path, prev)
        return WriteResult(
            wrote=False,
            path=outgoing_path,
            artifact_id=conn_id,
            content=content,
            warnings=[],
            verification=verification_to_conn_dict(outgoing_path, res),
        )

    return WriteResult(
        wrote=True,
        path=outgoing_path,
        artifact_id=conn_id,
        content=None,
        warnings=[],
        verification=verification_to_conn_dict(outgoing_path, res),
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
    registry: ArtifactRegistry,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    source_entity: str,
    connection_type: str,
    target_entity: str,
    description: str | None,
    version: str,
    status: str,
    last_updated: str | None,
    dry_run: bool,
    src_cardinality: str | None = None,
    tgt_cardinality: str | None = None,
    extra_known_ids: frozenset[str] = frozenset(),
) -> WriteResult:
    """Add a connection to the source entity's .outgoing.md file."""
    assert_engagement_write_root(repo_root)
    _validate_inputs(registry, connection_type, source_entity, target_entity, extra_known_ids)

    if src_cardinality or tgt_cardinality:
        for eid, label in ((source_entity, "source"), (target_entity, "target")):
            if _entity_artifact_type(registry, eid) in _JUNCTION_ENTITY_TYPES:
                raise ValueError(
                    f"Cardinalities are not permitted at junction connection-ends "
                    f"(the {label} entity '{eid}' is a junction)."
                )

    last = last_updated or today_iso()
    outgoing_path = _resolve_outgoing_path(registry, source_entity, dry_run=dry_run, extra_known_ids=extra_known_ids)
    conn_id = f"{source_entity}---{target_entity}@@{connection_type}"

    content = _build_content(
        outgoing_path,
        source_entity,
        connection_type,
        target_entity,
        description,
        version,
        status,
        last,
        src_cardinality=src_cardinality,
        tgt_cardinality=tgt_cardinality,
    )

    if dry_run:
        return WriteResult(
            wrote=False,
            path=outgoing_path,
            artifact_id=conn_id,
            content=content,
            warnings=[],
            verification=None,
        )

    result = _write_and_verify(outgoing_path, content, verifier, source_entity, connection_type, target_entity)
    if result.wrote:
        clear_repo_caches(outgoing_path)
    return result
