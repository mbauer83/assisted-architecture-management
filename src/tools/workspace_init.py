"""
workspace_init.py — CLI tool for initializing architecture workspace.

Reads ``arch-workspace.yaml``, validates / clones git repos, and writes
``.arch/init-state.yaml`` so that MCP + GUI servers can resolve repo paths.

Usage::

    arch-init                     # find arch-workspace.yaml in CWD or parents
    arch-init --config /path/to/arch-workspace.yaml

Exit codes:
    0  — success
    1  — configuration or git error (message printed to stderr)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from src.common.repo_paths import MODEL
from src.common.workspace_paths import (
    CONFIG_FILENAME,
    STATE_DIR,
    STATE_FILENAME,
    find_workspace_config as _find_config,
    load_workspace_state as load_init_state,
    parse_workspace_config as _parse_config,
)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd,
        capture_output=True, text=True, timeout=120,
    )


def _is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def _current_branch(repo: Path) -> str | None:
    r = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    return r.stdout.strip() if r.returncode == 0 else None


def _is_dirty(repo: Path) -> bool:
    r = _run_git(["status", "--porcelain"], cwd=repo)
    return bool(r.stdout.strip())


def _clone(url: str, branch: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = _run_git(["clone", "--branch", branch, url, str(dest)])
    if r.returncode != 0:
        raise SystemExit(
            f"ERROR: git clone failed for {url}\n{r.stderr.strip()}"
        )


# ---------------------------------------------------------------------------
# Repo resolution
# ---------------------------------------------------------------------------

def _resolve_repo(
    label: str,
    spec: dict,
    workspace_root: Path,
) -> Path:
    """Resolve a repo spec to an absolute path, cloning if needed."""
    if "local" in spec:
        local = Path(spec["local"])
        resolved = local if local.is_absolute() else workspace_root / local
        if not resolved.is_dir():
            raise SystemExit(
                f"ERROR: {label} local path does not exist: {resolved}"
            )
        if not (resolved / MODEL).is_dir():
            raise SystemExit(
                f"ERROR: {label} path has no model/ directory: {resolved}"
            )
        return resolved.resolve()

    if "git" in spec:
        git = spec["git"]
        url = git.get("url")
        branch = git.get("branch", "main")
        clone_path = git.get("path")
        if not url:
            raise SystemExit(f"ERROR: {label}.git.url is required")
        if not clone_path:
            raise SystemExit(f"ERROR: {label}.git.path is required")
        dest = Path(clone_path)
        if not dest.is_absolute():
            dest = workspace_root / dest
        dest = dest.resolve()

        if dest.is_dir():
            if not _is_git_repo(dest):
                raise SystemExit(
                    f"ERROR: {label} path exists but is not a git repo: {dest}"
                )
            actual_branch = _current_branch(dest)
            if actual_branch != branch:
                raise SystemExit(
                    f"ERROR: {label} repo at {dest} is on branch "
                    f"'{actual_branch}', expected '{branch}'. "
                    f"Switch branch manually or remove the directory."
                )
            if _is_dirty(dest):
                raise SystemExit(
                    f"ERROR: {label} repo at {dest} has uncommitted changes. "
                    f"Commit or stash them before running arch-init."
                )
            print(f"  {label}: existing clone OK ({dest}, branch={branch})")
        else:
            print(f"  {label}: cloning {url} (branch={branch}) → {dest}")
            _clone(url, branch, dest)

        model_dir = dest / MODEL
        if not model_dir.is_dir():
            raise SystemExit(
                f"ERROR: cloned {label} repo has no {MODEL}/ directory: {dest}"
            )
        return dest

    raise SystemExit(
        f"ERROR: {label} must specify either 'local' or 'git'"
    )


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------

def _write_state(
    workspace_root: Path,
    engagement_root: Path,
    enterprise_root: Path,
) -> Path:
    state_dir = workspace_root / STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / STATE_FILENAME
    state = {
        "workspace_root": str(workspace_root),
        "engagement_root": str(engagement_root),
        "enterprise_root": str(enterprise_root),
        "initialized_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(state_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(state, fh, default_flow_style=False)
    return state_path




# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="arch-init",
        description="Initialize architecture workspace from arch-workspace.yaml",
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Path to arch-workspace.yaml (default: search from CWD upward)",
    )
    args = parser.parse_args(argv)

    if args.config:
        config_path = args.config.resolve()
        if not config_path.is_file():
            raise SystemExit(f"ERROR: config not found: {config_path}")
    else:
        config_path = _find_config(Path.cwd())
        if config_path is None:
            raise SystemExit(
                f"ERROR: {CONFIG_FILENAME} not found in current directory or parents"
            )

    workspace_root = config_path.parent
    print(f"arch-init: using {config_path}")
    print(f"  workspace root: {workspace_root}")

    cfg = _parse_config(config_path)

    engagement_root = _resolve_repo("engagement", cfg["engagement"], workspace_root)
    enterprise_root = _resolve_repo("enterprise", cfg["enterprise"], workspace_root)

    state_path = _write_state(workspace_root, engagement_root, enterprise_root)
    print(f"\narch-init: success")
    print(f"  engagement: {engagement_root}")
    print(f"  enterprise: {enterprise_root}")
    print(f"  state file: {state_path}")


if __name__ == "__main__":
    main()
