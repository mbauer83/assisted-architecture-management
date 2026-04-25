"""Admin-mode write operations — enterprise repository writes.

This module is the ONLY authorised path for writing to the enterprise repo.
It is called exclusively from src/tools/gui_routers/admin.py and never from
any MCP tool.  It enforces the enterprise boundary via assert_enterprise_write_root
at every entry point.

The standard write functions (entity.py, connection.py, …) unconditionally
reject enterprise roots via assert_engagement_write_root and are not called here.
This module calls the shared formatting, verification, and macro-generation
logic directly — the same layer those functions use — keeping the boundary
check entirely at the callsite level.
"""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

from src.common.archimate_types import ALL_CONNECTION_TYPES, ALL_ENTITY_TYPES
from src.common.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.common.artifact_write import ENTITY_TYPES, generate_entity_id, format_outgoing_markdown
from src.common.repo_paths import DIAGRAM_CATALOG, DIAGRAMS, MODEL
from src.common.artifact_write_formatting import format_entity_markdown
from src.tools.generate_macros import generate_macros

from .boundary import assert_enterprise_write_root, today_iso
from .connection import (
    _build_content as _build_conn_content,
    _resolve_outgoing_path,
    _rollback,
    _validate_inputs,
    _write_and_verify as _write_and_verify_conn,
    verification_to_conn_dict,
)
from .entity import verification_to_entity_dict
from .parse_existing import parse_entity_file, parse_outgoing_file
from .types import WriteResult
from .verify import verify_content_in_temp_path
from .entity_delete import _delete_entity_core
from .diagram_delete import _delete_diagram_core


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

def admin_create_entity(
    *,
    repo_root: Path,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    artifact_type: str,
    name: str,
    summary: str | None,
    properties: dict[str, str] | None,
    notes: str | None,
    keywords: list[str] | None = None,
    artifact_id: str | None,
    version: str,
    status: str,
    last_updated: str | None,
    dry_run: bool,
) -> WriteResult:
    assert_enterprise_write_root(repo_root)

    if artifact_type not in ALL_ENTITY_TYPES:
        raise ValueError(f"Unknown entity artifact_type: {artifact_type!r}")
    info = ENTITY_TYPES.get(artifact_type)
    if info is None:
        raise ValueError(f"No writer mapping for artifact_type '{artifact_type}'")

    last = last_updated or today_iso()
    eid = artifact_id or generate_entity_id(info.prefix, name)
    path = repo_root / MODEL / info.domain_dir / info.subdir / f"{eid}.md"
    display = {
        "domain": info.domain_dir.capitalize(),
        "element-type": info.archimate_element_type,
        "label": name,
        "alias": f"{info.prefix}_{eid.split('.')[1]}" if "." in eid else eid.replace("-", "_"),
    }
    content = format_entity_markdown(
        artifact_id=eid, artifact_type=artifact_type, name=name,
        version=version, status=status, last_updated=last,
        keywords=keywords, summary=summary, properties=properties,
        notes=notes, display_archimate=display,
    )

    if dry_run:
        res = verify_content_in_temp_path(verifier=verifier, file_type="entity",
                                          desired_name=path.name, content=content)
        return WriteResult(wrote=False, path=path, artifact_id=eid, content=content,
                           warnings=[], verification=verification_to_entity_dict(path, res))

    path.parent.mkdir(parents=True, exist_ok=True)
    prev = path.read_text(encoding="utf-8") if path.exists() else None
    path.write_text(content, encoding="utf-8")
    res = verifier.verify_entity_file(path)
    if not res.valid:
        if prev is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(prev, encoding="utf-8")
        return WriteResult(wrote=False, path=path, artifact_id=eid, content=content,
                           warnings=[], verification=verification_to_entity_dict(path, res))

    try:
        generate_macros(repo_root)
    except Exception:  # noqa: BLE001
        pass
    clear_repo_caches(path)
    return WriteResult(wrote=True, path=path, artifact_id=eid, content=None,
                       warnings=[], verification=verification_to_entity_dict(path, res))


_UNSET = object()


def admin_edit_entity(
    *,
    repo_root: Path,
    registry: ArtifactRegistry,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    name: str | None = None,
    summary: object = _UNSET,
    properties: object = _UNSET,
    notes: object = _UNSET,
    keywords: object = _UNSET,
    version: str | None = None,
    status: str | None = None,
    dry_run: bool,
) -> WriteResult:
    assert_enterprise_write_root(repo_root)

    entity_file = registry.find_file_by_id(artifact_id)
    if entity_file is None:
        raise ValueError(f"Entity '{artifact_id}' not found in model")

    parsed = parse_entity_file(entity_file)
    fm = parsed.frontmatter
    artifact_type = str(fm.get("artifact-type", ""))

    eff_name = name if name is not None else str(fm.get("name", ""))
    eff_version = version if version is not None else str(fm.get("version", "0.1.0"))
    eff_status = status if status is not None else str(fm.get("status", "draft"))
    eff_keywords = keywords if keywords is not _UNSET else (fm.get("keywords") or None)
    eff_summary = summary if summary is not _UNSET else parsed.summary
    eff_properties = properties if properties is not _UNSET else (parsed.properties or None)
    eff_notes = notes if notes is not _UNSET else parsed.notes

    display = dict(parsed.display_archimate)
    if name is not None and display:
        display["label"] = eff_name

    content = format_entity_markdown(
        artifact_id=artifact_id, artifact_type=artifact_type,
        name=eff_name, version=eff_version, status=eff_status,
        last_updated=today_iso(), keywords=eff_keywords,
        summary=eff_summary, properties=eff_properties,
        notes=eff_notes, display_archimate=display,
    )

    if dry_run:
        res = verify_content_in_temp_path(verifier=verifier, file_type="entity",
                                          desired_name=entity_file.name, content=content)
        return WriteResult(wrote=False, path=entity_file, artifact_id=artifact_id,
                           content=content, warnings=[],
                           verification=verification_to_entity_dict(entity_file, res))

    prev = entity_file.read_text(encoding="utf-8")
    entity_file.write_text(content, encoding="utf-8")
    res = verifier.verify_entity_file(entity_file)
    if not res.valid:
        entity_file.write_text(prev, encoding="utf-8")
        return WriteResult(wrote=False, path=entity_file, artifact_id=artifact_id,
                           content=content, warnings=[],
                           verification=verification_to_entity_dict(entity_file, res))

    if name is not None:
        try:
            generate_macros(repo_root)
        except Exception:  # noqa: BLE001
            pass
    clear_repo_caches(entity_file)
    return WriteResult(wrote=True, path=entity_file, artifact_id=artifact_id,
                       content=None, warnings=[],
                       verification=verification_to_entity_dict(entity_file, res))


def admin_delete_entity(
    *,
    repo_root: Path,
    registry: ArtifactRegistry,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    dry_run: bool,
) -> WriteResult:
    assert_enterprise_write_root(repo_root)
    return _delete_entity_core(
        repo_root=repo_root,
        registry=registry,
        clear_repo_caches=clear_repo_caches,
        artifact_id=artifact_id,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def admin_add_connection(
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
) -> WriteResult:
    assert_enterprise_write_root(repo_root)
    _validate_inputs(registry, connection_type, source_entity, target_entity)

    last = last_updated or today_iso()
    outgoing_path = _resolve_outgoing_path(registry, source_entity)
    conn_id = f"{connection_type} → {target_entity}"
    content = _build_conn_content(outgoing_path, source_entity, connection_type,
                                  target_entity, description, version, status, last)

    if dry_run:
        return WriteResult(wrote=False, path=outgoing_path, artifact_id=conn_id,
                           content=content, warnings=[], verification=None)

    result = _write_and_verify_conn(outgoing_path, content, verifier,
                                    connection_type, target_entity)
    if result.wrote:
        clear_repo_caches(outgoing_path)
    return result


def admin_remove_connection(
    *,
    repo_root: Path,
    registry: ArtifactRegistry,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    source_entity: str,
    target_entity: str,
    connection_type: str,
    dry_run: bool,
) -> WriteResult:
    assert_enterprise_write_root(repo_root)
    outgoing_path = _resolve_outgoing_path(registry, source_entity)

    if not outgoing_path.exists():
        raise ValueError(f"No outgoing file for '{source_entity}'")

    parsed = parse_outgoing_file(outgoing_path)
    conn_id = f"{connection_type} -> {target_entity}"
    remaining = [
        c for c in parsed.connections
        if not (c["connection_type"] == connection_type and c["target_entity"] == target_entity)
    ]
    if len(remaining) == len(parsed.connections):
        raise ValueError(f"Connection '{conn_id}' not found in {outgoing_path.name}")

    if dry_run:
        if not remaining:
            return WriteResult(wrote=False, path=outgoing_path, artifact_id=conn_id,
                               content="(file would be deleted — last connection removed)",
                               warnings=[], verification=None)
        content = format_outgoing_markdown(
            source_entity=source_entity,
            version=str(parsed.frontmatter.get("version", "0.1.0")),
            status=str(parsed.frontmatter.get("status", "active")),
            last_updated=today_iso(), connections=remaining,
        )
        return WriteResult(wrote=False, path=outgoing_path, artifact_id=conn_id,
                           content=content, warnings=[], verification=None)

    if not remaining:
        outgoing_path.unlink()
        clear_repo_caches(outgoing_path)
        return WriteResult(wrote=True, path=outgoing_path, artifact_id=conn_id,
                           content=None, warnings=["Deleted empty .outgoing.md file"],
                           verification={"path": str(outgoing_path), "file_type": "connection",
                                         "valid": True, "issues": []})

    content = format_outgoing_markdown(
        source_entity=source_entity,
        version=str(parsed.frontmatter.get("version", "0.1.0")),
        status=str(parsed.frontmatter.get("status", "active")),
        last_updated=today_iso(), connections=remaining,
    )
    prev = outgoing_path.read_text(encoding="utf-8")
    outgoing_path.write_text(content, encoding="utf-8")
    res = verifier.verify_outgoing_file(outgoing_path)
    vdict = verification_to_conn_dict(outgoing_path, res)
    if not res.valid:
        _rollback(outgoing_path, prev)
        return WriteResult(wrote=False, path=outgoing_path, artifact_id=conn_id,
                           content=content, warnings=[], verification=vdict)
    clear_repo_caches(outgoing_path)
    return WriteResult(wrote=True, path=outgoing_path, artifact_id=conn_id,
                       content=None, warnings=[], verification=vdict)


# ---------------------------------------------------------------------------
# Diagram
# ---------------------------------------------------------------------------

def _write_diagram_to_enterprise(
    *,
    repo_root: Path,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    diagram_type: str,
    name: str,
    puml: str,
    artifact_id: str,
    keywords: list[str] | None = None,
    version: str,
    status: str,
    dry_run: bool,
) -> WriteResult:
    """Write a diagram PUML file into the enterprise repo's diagram-catalog."""
    assert_enterprise_write_root(repo_root)
    import re
    from src.common.artifact_write import format_diagram_puml

    diagrams_dir = repo_root / DIAGRAM_CATALOG / DIAGRAMS
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    path = diagrams_dir / f"{artifact_id}.puml"

    content = format_diagram_puml(
        artifact_id=artifact_id, diagram_type=diagram_type,
        name=name, puml=puml, keywords=keywords,
        version=version, status=status, last_updated=today_iso(),
    )

    if dry_run:
        return WriteResult(
            wrote=False, path=path, artifact_id=artifact_id,
            content=content, warnings=[],
            verification={"file_type": "diagram", "valid": True, "issues": []},
        )

    prev = path.read_text(encoding="utf-8") if path.exists() else None
    path.write_text(content, encoding="utf-8")
    res = verifier.verify_diagram_file(path)
    if not res.valid:
        if prev is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(prev, encoding="utf-8")
        return WriteResult(
            wrote=False, path=path, artifact_id=artifact_id,
            content=content, warnings=[],
            verification={
                "file_type": "diagram", "valid": False,
                "issues": [{"severity": i.severity, "code": i.code,
                            "message": i.message} for i in res.issues],
            },
        )

    clear_repo_caches(path)
    return WriteResult(
        wrote=True, path=path, artifact_id=artifact_id,
        content=None, warnings=[],
        verification={"file_type": "diagram", "valid": True, "issues": []},
    )


def admin_delete_diagram(
    *,
    repo_root: Path,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    dry_run: bool,
) -> WriteResult:
    assert_enterprise_write_root(repo_root)
    return _delete_diagram_core(
        repo_root=repo_root,
        clear_repo_caches=clear_repo_caches,
        artifact_id=artifact_id,
        dry_run=dry_run,
    )
