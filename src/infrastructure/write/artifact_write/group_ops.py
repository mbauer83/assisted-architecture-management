"""Group lifecycle operations: create, rename, archive/unarchive, delete (collections only).

Model-project cascade delete is deferred (Phase 9).
All mutating ops update .arch-repo/groups.yaml atomically via the staged transaction.
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Literal

from src.application.group_registry import load_group_registry, registry_to_yaml
from src.config.repo_paths import ARCH_REPO
from src.domain.groups import UNCATEGORIZED, GroupAxis, GroupEntry, GroupRegistry

_GROUPS_FILE = "groups.yaml"

GroupAction = Literal["create", "rename", "archive", "unarchive", "delete", "update"]

_DRY_RUN_SENTINEL = object()  # default sentinel to distinguish "not provided" from False


class GroupOpError(ValueError):
    """Raised on invalid group lifecycle operations."""


def _write_registry(repo_root: Path, registry: GroupRegistry) -> None:
    arch_dir = repo_root / ARCH_REPO
    arch_dir.mkdir(parents=True, exist_ok=True)
    (arch_dir / _GROUPS_FILE).write_text(registry_to_yaml(registry), encoding="utf-8")


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def _git_add(path: Path, repo_root: Path) -> None:
    _run_git(["add", str(path.relative_to(repo_root))], repo_root)


def _subtree_files(directory: Path) -> list[Path]:
    return [p for p in directory.rglob("*") if p.is_file()]


def _update_axis(
    registry: GroupRegistry,
    axis: GroupAxis,
    entries: list[GroupEntry],
) -> GroupRegistry:
    match axis:
        case "model-project":
            return replace(registry, model_projects=tuple(entries))
        case "diagram-collection":
            return replace(registry, diagram_collections=tuple(entries))
        case _:
            return replace(registry, document_collections=tuple(entries))


def _new_id() -> str:
    from src.application.group_registry import _new_group_id  # noqa: PLC0415

    return _new_group_id()


# ---------------------------------------------------------------------------
# Public operation functions
# ---------------------------------------------------------------------------


def group_create(
    repo_root: Path,
    *,
    axis: GroupAxis,
    slug: str,
    name: str,
    description: str = "",
    order: int = 0,
    meta_ontology: str = "",
    type_filter: tuple[str, ...] = (),
) -> dict[str, object]:
    """Register a new group (and lazily create the directory)."""
    registry = load_group_registry(repo_root)
    if registry.find(axis, slug) is not None:
        raise GroupOpError(f"Group {slug!r} already exists on axis {axis!r}.")
    is_model = axis == "model-project"
    entry = GroupEntry(
        slug=slug, id=_new_id(), name=name, description=description, order=order,
        meta_ontology=meta_ontology if is_model else "",
        type_filter=type_filter if not is_model else (),
    )
    entries = list(registry._by_axis(axis)) + [entry]
    registry = _update_axis(registry, axis, entries)
    _write_registry(repo_root, registry)
    _git_add(repo_root / ARCH_REPO / _GROUPS_FILE, repo_root)
    return {"action": "created", "axis": axis, "slug": slug, "id": entry.id}


def group_rename(
    repo_root: Path,
    *,
    axis: GroupAxis,
    slug: str,
    new_name: str | None = None,
    new_slug: str | None = None,
) -> dict[str, object]:
    """Rename a group: display name only (registry edit) or slug (git mv subtree + registry)."""
    registry = load_group_registry(repo_root)
    entry = registry.find(axis, slug)
    if entry is None:
        raise GroupOpError(f"Group {slug!r} not found on axis {axis!r}.")

    if new_slug is not None and new_slug != slug:
        if registry.find(axis, new_slug) is not None:
            raise GroupOpError(f"A group named {new_slug!r} already exists on axis {axis!r}.")
        old_dir = _group_dir(repo_root, axis, slug)
        new_dir = _group_dir(repo_root, axis, new_slug)
        if old_dir is not None and new_dir is not None and old_dir.exists():
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            result = _run_git(
                ["mv", str(old_dir.relative_to(repo_root)), str(new_dir.relative_to(repo_root))],
                repo_root,
            )
            if result.returncode != 0:
                raise GroupOpError(f"git mv failed: {result.stderr}")
        updated = replace(entry, slug=new_slug, name=new_name or entry.name)
    else:
        updated = replace(entry, name=new_name or entry.name)

    entries = [updated if e.slug == slug else e for e in registry._by_axis(axis)]
    registry = _update_axis(registry, axis, entries)
    _write_registry(repo_root, registry)
    _git_add(repo_root / ARCH_REPO / _GROUPS_FILE, repo_root)
    return {"action": "renamed", "axis": axis, "slug": updated.slug, "old_slug": slug}


def group_archive(
    repo_root: Path,
    *,
    axis: GroupAxis,
    slug: str,
    confirm: str | None,
) -> dict[str, object]:
    """Set archived=True on a group. Non-empty collections require typed confirm."""
    registry = load_group_registry(repo_root)
    entry = registry.find(axis, slug)
    if entry is None:
        raise GroupOpError(f"Group {slug!r} not found on axis {axis!r}.")
    if entry.slug == UNCATEGORIZED:
        raise GroupOpError("The 'uncategorized' group cannot be archived.")

    if axis == "document-collection":
        all_dirs = _all_doc_group_dirs(repo_root, slug)
        is_nonempty = any(any(d.rglob("*")) for d in all_dirs)
    else:
        group_dir = _group_dir(repo_root, axis, slug)
        is_nonempty = group_dir is not None and group_dir.exists() and any(group_dir.rglob("*"))
    if is_nonempty and confirm != slug:
        raise GroupOpError(
            f"Group {slug!r} is non-empty. Pass confirm={slug!r} to archive it."
        )

    entries = [replace(e, archived=True) if e.slug == slug else e for e in registry._by_axis(axis)]
    registry = _update_axis(registry, axis, entries)
    _write_registry(repo_root, registry)
    _git_add(repo_root / ARCH_REPO / _GROUPS_FILE, repo_root)
    return {"action": "archived", "axis": axis, "slug": slug}


def group_unarchive(
    repo_root: Path,
    *,
    axis: GroupAxis,
    slug: str,
) -> dict[str, object]:
    """Set archived=False on a group."""
    registry = load_group_registry(repo_root)
    entry = registry.find(axis, slug)
    if entry is None:
        raise GroupOpError(f"Group {slug!r} not found on axis {axis!r}.")
    entries = [replace(e, archived=False) if e.slug == slug else e for e in registry._by_axis(axis)]
    registry = _update_axis(registry, axis, entries)
    _write_registry(repo_root, registry)
    _git_add(repo_root / ARCH_REPO / _GROUPS_FILE, repo_root)
    return {"action": "unarchived", "axis": axis, "slug": slug}


def group_delete_collection(
    repo_root: Path,
    *,
    axis: GroupAxis,
    slug: str,
    confirm: str | None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Delete a diagram- or document-collection, or a model-project (cascade).

    For model-project: two-stage cascade delete via dry_run flag.
    For diagram/document collections: removes the folder and its files.
    All cases require typed confirm equal to the target slug.
    """
    if axis == "model-project":
        from src.infrastructure.write.artifact_write.cascade_delete import cascade_delete_model_project  # noqa: PLC0415

        try:
            return cascade_delete_model_project(repo_root, slug, confirm or "", dry_run=dry_run)
        except ValueError as exc:
            raise GroupOpError(str(exc)) from exc
    registry = load_group_registry(repo_root)
    entry = registry.find(axis, slug)
    if entry is None:
        raise GroupOpError(f"Group {slug!r} not found on axis {axis!r}.")
    if entry.slug == UNCATEGORIZED:
        raise GroupOpError("The 'uncategorized' group cannot be deleted.")

    if axis == "document-collection":
        all_dirs = _all_doc_group_dirs(repo_root, slug)
        files = [f for d in all_dirs for f in _subtree_files(d)]
    else:
        group_dir = _group_dir(repo_root, axis, slug)
        files = _subtree_files(group_dir) if group_dir is not None and group_dir.exists() else []
    if files and confirm != slug:
        raise GroupOpError(
            f"Group {slug!r} contains {len(files)} file(s). Pass confirm={slug!r} to delete."
        )
    if files:
        rel_paths = [str(f.relative_to(repo_root)) for f in files]
        _run_git(["rm", "-f", *rel_paths], repo_root)
        if axis == "document-collection":
            for d in _all_doc_group_dirs(repo_root, slug):
                try:
                    d.rmdir()
                except OSError:
                    pass
        else:
            d = _group_dir(repo_root, axis, slug)
            if d and d.exists():
                try:
                    d.rmdir()
                except OSError:
                    pass

    # Remove from registry
    entries = [e for e in registry._by_axis(axis) if e.slug != slug]
    registry = _update_axis(registry, axis, entries)
    _write_registry(repo_root, registry)
    _git_add(repo_root / ARCH_REPO / _GROUPS_FILE, repo_root)
    return {"action": "deleted", "axis": axis, "slug": slug, "files_removed": len(files)}


def _all_doc_group_dirs(repo_root: Path, slug: str) -> list[Path]:
    """Return all existing docs/<doc-type>/<slug> directories for a document-collection."""
    from src.application.repo_path_helpers import docs_root  # noqa: PLC0415
    docs = docs_root(repo_root)
    result = []
    if docs.exists():
        for doc_type_dir in sorted(docs.iterdir()):
            if doc_type_dir.is_dir():
                candidate = doc_type_dir / slug
                if candidate.exists():
                    result.append(candidate)
    return result


def _group_dir(repo_root: Path, axis: GroupAxis, slug: str) -> Path | None:
    """Return the filesystem directory for this group, or None if it has no dedicated dir."""
    from src.application.repo_path_helpers import diagram_source_root  # noqa: PLC0415

    if axis == "model-project":
        return repo_root / "projects" / slug
    if axis == "diagram-collection":
        return diagram_source_root(repo_root) / slug
    # document-collection: return first existing match across doc-type subdirs
    dirs = _all_doc_group_dirs(repo_root, slug)
    return dirs[0] if dirs else None


def group_update(
    repo_root: Path,
    *,
    axis: GroupAxis,
    slug: str,
    name: str | None = None,
    description: str | None = None,
    meta_ontology: str | None = None,
    type_filter: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Update display metadata without moving files.

    meta_ontology applies to model-project groups only.
    type_filter applies to diagram/document-collection groups only.
    """
    registry = load_group_registry(repo_root)
    entry = registry.find(axis, slug)
    if entry is None:
        raise GroupOpError(f"Group {slug!r} not found on axis {axis!r}.")
    is_model = axis == "model-project"
    updated = replace(
        entry,
        name=name if name is not None else entry.name,
        description=description if description is not None else entry.description,
        meta_ontology=(meta_ontology if meta_ontology is not None else entry.meta_ontology) if is_model else "",
        type_filter=(type_filter if type_filter is not None else entry.type_filter) if not is_model else (),
    )
    entries = [updated if e.slug == slug else e for e in registry._by_axis(axis)]
    registry = _update_axis(registry, axis, entries)
    _write_registry(repo_root, registry)
    _git_add(repo_root / ARCH_REPO / _GROUPS_FILE, repo_root)
    return {"action": "updated", "axis": axis, "slug": slug}


# ---------------------------------------------------------------------------
# Public dispatch
# ---------------------------------------------------------------------------


def group_op(
    repo_root: Path,
    *,
    axis: GroupAxis,
    action: GroupAction,
    target: str | None = None,
    name: str | None = None,
    new_slug: str | None = None,
    description: str = "",
    order: int = 0,
    confirm: str | None = None,
    dry_run: bool = False,
    meta_ontology: str = "",
    type_filter: list[str] | None = None,
) -> dict[str, object]:
    """Dispatch a group lifecycle operation and return a summary dict."""
    slug = target or ""
    match action:
        case "create":
            if not slug:
                raise GroupOpError("target (slug) is required for action='create'.")
            return group_create(
                repo_root, axis=axis, slug=slug, name=name or slug,
                description=description, order=order,
                meta_ontology=meta_ontology,
                type_filter=tuple(type_filter) if type_filter is not None else (),
            )
        case "rename":
            if not slug:
                raise GroupOpError("target (existing slug) is required for action='rename'.")
            return group_rename(repo_root, axis=axis, slug=slug, new_name=name, new_slug=new_slug)
        case "archive":
            if not slug:
                raise GroupOpError("target (slug) is required for action='archive'.")
            return group_archive(repo_root, axis=axis, slug=slug, confirm=confirm)
        case "unarchive":
            if not slug:
                raise GroupOpError("target (slug) is required for action='unarchive'.")
            return group_unarchive(repo_root, axis=axis, slug=slug)
        case "delete":
            if not slug:
                raise GroupOpError("target (slug) is required for action='delete'.")
            return group_delete_collection(repo_root, axis=axis, slug=slug, confirm=confirm, dry_run=dry_run)
        case "update":
            if not slug:
                raise GroupOpError("target (slug) is required for action='update'.")
            return group_update(
                repo_root, axis=axis, slug=slug,
                name=name,
                description=description or None,
                meta_ontology=meta_ontology or None,
                type_filter=tuple(type_filter) if type_filter is not None else None,
            )
        case _:
            raise GroupOpError(
                f"Unknown action: {action!r}. Valid: create, rename, archive, unarchive, delete, update."
            )
