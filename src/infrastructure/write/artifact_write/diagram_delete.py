"""Diagram deletion operations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.application.verification.artifact_verifier_parsing import parse_frontmatter_from_path
from src.config.repo_paths import DIAGRAM_CATALOG, DIAGRAMS, RENDERED

from .boundary import assert_engagement_write_root
from .types import WriteResult


def _verification(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "file_type": "diagram",
        "valid": True,
        "issues": [],
    }


def _find_diagram_file(repo_root: Path, artifact_id: str) -> Path | None:
    diagrams_root = repo_root / DIAGRAM_CATALOG / DIAGRAMS
    if not diagrams_root.exists():
        return None
    for suffix in ("*.puml", "*.md"):
        for path in sorted(diagrams_root.rglob(suffix)):
            if path.parent.name == RENDERED:
                continue
            fm = parse_frontmatter_from_path(path) or {}
            if str(fm.get("artifact-id", "")) == artifact_id:
                return path
    return None


def _rendered_paths(diagram_path: Path) -> list[Path]:
    rendered_dir = diagram_path.parent.parent / RENDERED
    stem = diagram_path.stem
    candidates = {stem}
    parts = stem.split(".", 2)
    if len(parts) >= 3:
        candidates.add(parts[2])
    paths: list[Path] = []
    for name in candidates:
        paths.append(rendered_dir / f"{name}.png")
        paths.append(rendered_dir / f"{name}.svg")
    return paths


def _delete_diagram_core(
    *,
    repo_root: Path,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    dry_run: bool,
) -> WriteResult:
    diagram_path = _find_diagram_file(repo_root, artifact_id)
    if diagram_path is None:
        raise ValueError(f"Diagram '{artifact_id}' not found in repo '{repo_root}'")

    rendered = [path for path in _rendered_paths(diagram_path) if path.exists()]
    warnings = [f"Will delete rendered artifact: {path.name}" for path in rendered]

    if dry_run:
        preview = "\n".join(
            [
                f"Would delete diagram: {diagram_path}",
                *(f"Would delete rendered artifact: {path}" for path in rendered),
            ]
        )
        return WriteResult(
            wrote=False,
            path=diagram_path,
            artifact_id=artifact_id,
            content=preview,
            warnings=warnings,
            verification=_verification(diagram_path),
        )

    diagram_path.unlink(missing_ok=False)
    for path in rendered:
        path.unlink(missing_ok=True)
    clear_repo_caches(diagram_path)
    return WriteResult(
        wrote=True,
        path=diagram_path,
        artifact_id=artifact_id,
        content=None,
        warnings=warnings,
        verification=_verification(diagram_path),
    )


def delete_diagram(
    *,
    repo_root: Path,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    dry_run: bool,
) -> WriteResult:
    assert_engagement_write_root(repo_root)
    return _delete_diagram_core(
        repo_root=repo_root,
        clear_repo_caches=clear_repo_caches,
        artifact_id=artifact_id,
        dry_run=dry_run,
    )
