"""Workspace-aware repository and scope resolution helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml

CONFIG_FILENAME = "arch-workspace.yaml"
STATE_DIR = ".arch"
STATE_FILENAME = "init-state.yaml"
RepoScope = Literal["engagement", "enterprise", "unknown"]


def find_workspace_config(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        candidate = current / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def parse_workspace_config(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: {path} must be a YAML mapping")
    for key in ("engagement", "enterprise"):
        if key not in data:
            raise SystemExit(f"ERROR: {path} is missing required key '{key}'")
    return data


def load_workspace_config(start: Path | None = None) -> tuple[Path, dict] | None:
    config_path = find_workspace_config((start or Path.cwd()).resolve())
    if config_path is None:
        return None
    return config_path.parent.resolve(), parse_workspace_config(config_path)


def load_workspace_state(start: Path | None = None) -> dict | None:
    current = (start or Path.cwd()).resolve()
    while True:
        candidate = current / STATE_DIR / STATE_FILENAME
        if candidate.is_file():
            with open(candidate, encoding="utf-8") as fh:
                return yaml.safe_load(fh)
        parent = current.parent
        if parent == current:
            return None
        current = parent


def configured_repo_path(spec: dict, workspace_root: Path) -> Path:
    if "local" in spec:
        local = Path(spec["local"])
        return (local if local.is_absolute() else workspace_root / local).resolve()
    if "git" in spec:
        git = spec["git"]
        clone_path = git.get("path")
        if not clone_path:
            raise SystemExit("ERROR: git repo config is missing required key 'path'")
        dest = Path(clone_path)
        return (dest if dest.is_absolute() else workspace_root / dest).resolve()
    raise SystemExit("ERROR: repo config must specify either 'local' or 'git'")


def resolve_workspace_repo_roots(start: Path | None = None) -> tuple[Path, Path] | None:
    state = load_workspace_state(start)
    if state and "engagement_root" in state and "enterprise_root" in state:
        return (
            Path(str(state["engagement_root"])).resolve(),
            Path(str(state["enterprise_root"])).resolve(),
        )

    loaded = load_workspace_config(start)
    if loaded is None:
        return None
    workspace_root, cfg = loaded
    return (
        configured_repo_path(cfg["engagement"], workspace_root),
        configured_repo_path(cfg["enterprise"], workspace_root),
    )


def infer_repo_scope(path: Path, *, start: Path | None = None) -> RepoScope:
    resolved = path.resolve()
    roots = resolve_workspace_repo_roots(start or resolved)
    if roots is not None:
        engagement_root, enterprise_root = roots
        try:
            resolved.relative_to(enterprise_root)
            return "enterprise"
        except ValueError:
            pass
        try:
            resolved.relative_to(engagement_root)
            return "engagement"
        except ValueError:
            pass
    return "engagement" if "engagements" in resolved.parts else "enterprise"
