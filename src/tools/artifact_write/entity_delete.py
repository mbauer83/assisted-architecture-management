"""Entity deletion operations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.common.artifact_verifier import ArtifactRegistry
from src.common.artifact_verifier_parsing import parse_diagram_refs, parse_frontmatter_from_path
from src.common.repo_paths import DIAGRAM_CATALOG, DIAGRAMS, MODEL, RENDERED

from .boundary import assert_engagement_write_root
from .parse_existing import parse_outgoing_file
from .types import WriteResult


def _verification(path: Path, *, valid: bool, issues: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "path": str(path),
        "file_type": "entity",
        "valid": valid,
        "issues": issues or [],
    }


def _owned_outgoing_path(entity_file: Path) -> Path:
    return entity_file.with_suffix(".outgoing.md")


def _owned_connection_ids(artifact_id: str, outgoing_path: Path) -> list[str]:
    if not outgoing_path.exists():
        return []
    parsed = parse_outgoing_file(outgoing_path)
    return [
        f"{artifact_id} {conn['connection_type']} → {conn['target_entity']}"
        for conn in parsed.connections
    ]


def _diagram_paths(repo_roots: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for root in repo_roots:
        diagrams_root = root / DIAGRAM_CATALOG / DIAGRAMS
        if not diagrams_root.exists():
            continue
        for suffix in ("*.puml", "*.md"):
            for path in diagrams_root.rglob(suffix):
                if path.parent.name != RENDERED:
                    paths.append(path)
    return sorted(paths)


def _format_dependency_tree(
    artifact_id: str,
    *,
    incoming_connections: list[str],
    diagram_refs: list[str],
    grf_refs: list[str],
) -> str:
    lines = [artifact_id]
    if incoming_connections:
        lines.append("  incoming-connections")
        lines.extend(f"    {item}" for item in incoming_connections)
    if diagram_refs:
        lines.append("  diagrams")
        lines.extend(f"    {item}" for item in diagram_refs)
    if grf_refs:
        lines.append("  global-entity-references")
        lines.extend(f"    {item}" for item in grf_refs)
    return "\n".join(lines)


def _entity_ref_blockers(
    *,
    registry: ArtifactRegistry,
    artifact_id: str,
    entity_file: Path,
    owned_connection_ids: set[str],
) -> tuple[list[str], list[str], list[str]]:
    incoming_connections: list[str] = []
    diagram_refs: list[str] = []
    grf_refs: list[str] = []
    for root in registry.repo_roots:
        model_root = root / MODEL
        if not model_root.exists():
            continue
        for outgoing_path in sorted(model_root.rglob("*.outgoing.md")):
            try:
                parsed = parse_outgoing_file(outgoing_path)
            except Exception:  # noqa: BLE001
                continue
            source_entity = str(parsed.frontmatter.get("source-entity", ""))
            if source_entity == artifact_id:
                continue
            for conn in parsed.connections:
                if conn["target_entity"] == artifact_id:
                    incoming_connections.append(
                        f"{source_entity} {conn['connection_type']} → {artifact_id}"
                    )
        for other_entity in sorted(model_root.rglob("*.md")):
            if other_entity.name.endswith(".outgoing.md") or other_entity == entity_file:
                continue
            fm = parse_frontmatter_from_path(other_entity) or {}
            if (
                str(fm.get("artifact-type", "")) == "global-artifact-reference"
                and str(fm.get("global-artifact-id", "")) == artifact_id
            ):
                grf_refs.append(
                    str(fm.get("artifact-id", other_entity.stem))
                )

    for diagram_path in _diagram_paths(registry.repo_roots):
        refs = parse_diagram_refs(diagram_path) or {}
        entity_ids = set(refs.get("entity_ids", []))
        conn_ids = set(refs.get("connection_ids", []))
        if artifact_id in entity_ids or owned_connection_ids.intersection(conn_ids):
            diagram_refs.append(diagram_path.stem)

    return incoming_connections, diagram_refs, grf_refs


def _delete_entity_core(
    *,
    repo_root: Path,
    registry: ArtifactRegistry,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    dry_run: bool,
) -> WriteResult:
    entity_file = registry.find_file_by_id(artifact_id)
    if entity_file is None:
        raise ValueError(f"Entity '{artifact_id}' not found in model")
    try:
        entity_file.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"Entity '{artifact_id}' is not in writable repo '{repo_root}'") from exc

    outgoing_path = _owned_outgoing_path(entity_file)
    owned_connection_ids = set(_owned_connection_ids(artifact_id, outgoing_path))
    incoming_connections, diagram_refs, grf_refs = _entity_ref_blockers(
        registry=registry,
        artifact_id=artifact_id,
        entity_file=entity_file,
        owned_connection_ids=owned_connection_ids,
    )
    if incoming_connections or diagram_refs or grf_refs:
        tree = _format_dependency_tree(
            artifact_id,
            incoming_connections=incoming_connections,
            diagram_refs=diagram_refs,
            grf_refs=grf_refs,
        )
        raise ValueError(
            f"Cannot delete entity '{artifact_id}' because it is still referenced.\n"
            "Delete or update these dependents first:\n"
            f"{tree}"
        )

    warnings: list[str] = []
    if outgoing_path.exists():
        warnings.append(f"Will delete owned outgoing file: {outgoing_path.name}")

    if dry_run:
        preview = "\n".join(
            [
                f"Would delete entity: {entity_file}",
                *( [f"Would delete outgoing file: {outgoing_path}"] if outgoing_path.exists() else [] ),
            ]
        )
        return WriteResult(
            wrote=False,
            path=entity_file,
            artifact_id=artifact_id,
            content=preview,
            warnings=warnings,
            verification=_verification(entity_file, valid=True),
        )

    entity_file.unlink(missing_ok=False)
    if outgoing_path.exists():
        outgoing_path.unlink()

    try:
        from src.tools.generate_macros import generate_macros
        generate_macros(repo_root)
    except Exception:  # noqa: BLE001
        warnings.append("Macro regeneration skipped after deletion")

    clear_repo_caches(entity_file)
    return WriteResult(
        wrote=True,
        path=entity_file,
        artifact_id=artifact_id,
        content=None,
        warnings=warnings,
        verification=_verification(entity_file, valid=True),
    )


def delete_entity(
    *,
    repo_root: Path,
    registry: ArtifactRegistry,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    dry_run: bool,
) -> WriteResult:
    assert_engagement_write_root(repo_root)
    return _delete_entity_core(
        repo_root=repo_root,
        registry=registry,
        clear_repo_caches=clear_repo_caches,
        artifact_id=artifact_id,
        dry_run=dry_run,
    )
