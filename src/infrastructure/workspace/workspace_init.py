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
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import yaml

from src.config.repo_paths import MODEL
from src.config.settings import (
    repo_init_commit_author_email,
    repo_init_commit_author_name,
)
from src.config.workspace_paths import (
    CONFIG_FILENAME,
    STATE_DIR,
    STATE_FILENAME,
)
from src.config.workspace_paths import (
    find_workspace_config as _find_config,
)
from src.config.workspace_paths import (
    load_workspace_state as _load_workspace_state,
)
from src.config.workspace_paths import (
    parse_workspace_config as _parse_config,
)
from src.infrastructure.workspace.engagement_repo_template import create_engagement_repo

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _run_git(
    args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


def _is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def _current_branch(repo: Path) -> str | None:
    r = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    if r.returncode == 0:
        branch = r.stdout.strip()
        if branch and branch != "HEAD":
            return branch

    # Freshly initialized repositories may have an unborn HEAD, in which case
    # rev-parse fails even though the configured branch is already selected.
    fallback = _run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=repo)
    if fallback.returncode == 0:
        branch = fallback.stdout.strip()
        return branch or None
    return None


def _is_dirty(repo: Path) -> bool:
    r = _run_git(["status", "--porcelain"], cwd=repo)
    return bool(r.stdout.strip())


def _has_commits(repo: Path) -> bool:
    r = _run_git(["rev-parse", "--verify", "HEAD"], cwd=repo)
    return r.returncode == 0


def _clone(url: str, branch: str, dest: Path, env: dict[str, str] | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = _run_git(["clone", "--branch", branch, url, str(dest)], env=env)
    if r.returncode != 0:
        raise SystemExit(f"ERROR: git clone failed for {url}\n{r.stderr.strip()}")


# ---------------------------------------------------------------------------
# Repo resolution
# ---------------------------------------------------------------------------


def _resolve_repo(
    label: str,
    spec: dict,
    workspace_root: Path,
    *,
    allow_dirty_git_repo: bool = False,
    allow_dirty_uncommitted_git_repo: bool = False,
    initialize_if_empty: bool = False,
    git_env: dict[str, str] | None = None,
) -> Path:
    """Resolve a repo spec to an absolute path, cloning if needed."""
    if "local" in spec:
        local = Path(spec["local"])
        resolved = local if local.is_absolute() else workspace_root / local
        if not resolved.is_dir():
            raise SystemExit(f"ERROR: {label} local path does not exist: {resolved}")
        if not (resolved / MODEL).is_dir():
            raise SystemExit(f"ERROR: {label} path has no model/ directory: {resolved}")
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
                raise SystemExit(f"ERROR: {label} path exists but is not a git repo: {dest}")
            actual_branch = _current_branch(dest)
            if actual_branch is None and initialize_if_empty and not _has_commits(dest):
                create_engagement_repo(
                    dest,
                    git_url=str(url),
                    branch=str(branch),
                    commit_author_name=repo_init_commit_author_name(label),
                    commit_author_email=repo_init_commit_author_email(label),
                )
                actual_branch = _current_branch(dest)
            if actual_branch != branch:
                raise SystemExit(
                    f"ERROR: {label} repo at {dest} is on branch "
                    f"'{actual_branch}', expected '{branch}'. "
                    f"Switch branch manually or remove the directory."
                )
            if _is_dirty(dest):
                if allow_dirty_git_repo:
                    print(f"  {label}: using existing dirty git repo ({dest}, branch={branch})")
                elif allow_dirty_uncommitted_git_repo and not _has_commits(dest):
                    print(f"  {label}: using newly scaffolded git repo ({dest}, branch={branch}, no commits yet)")
                else:
                    raise SystemExit(
                        f"ERROR: {label} repo at {dest} has uncommitted changes. "
                        f"Commit or stash them before running arch-init."
                    )
            else:
                print(f"  {label}: existing clone OK ({dest}, branch={branch})")
        else:
            if initialize_if_empty:
                print(f"  {label}: initializing empty git repo at {dest} (branch={branch})")
                create_engagement_repo(
                    dest,
                    git_url=str(url),
                    branch=str(branch),
                    commit_author_name=repo_init_commit_author_name(label),
                    commit_author_email=repo_init_commit_author_email(label),
                )
            else:
                print(f"  {label}: cloning {url} (branch={branch}) → {dest}")
                _clone(url, branch, dest, env=git_env)

        model_dir = dest / MODEL
        if not model_dir.is_dir():
            raise SystemExit(f"ERROR: cloned {label} repo has no {MODEL}/ directory: {dest}")
        return dest

    raise SystemExit(f"ERROR: {label} must specify either 'local' or 'git'")


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------


class InitState(TypedDict):
    workspace_root: str
    engagement_root: str
    enterprise_root: str
    initialized_at: str


def load_init_state(start: Path | None = None) -> InitState | None:
    """Return the persisted arch-init state for the current workspace, if any."""
    state = _load_workspace_state(start)
    if not isinstance(state, dict):
        return None
    workspace_root = state.get("workspace_root")
    engagement_root = state.get("engagement_root")
    enterprise_root = state.get("enterprise_root")
    initialized_at = state.get("initialized_at")
    if not isinstance(workspace_root, str):
        return None
    if not isinstance(engagement_root, str):
        return None
    if not isinstance(enterprise_root, str):
        return None
    if not isinstance(initialized_at, str):
        return None
    return InitState(
        workspace_root=workspace_root,
        engagement_root=engagement_root,
        enterprise_root=enterprise_root,
        initialized_at=initialized_at,
    )


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
# Credential helpers
# ---------------------------------------------------------------------------


def _collect_init_credentials(cfg: dict) -> dict[str, str] | None:
    """Probe remote URLs from the workspace config; prompt interactively for any needed credentials."""
    from src.infrastructure.git.git_auth import build_git_env, collect_credentials, create_askpass_script

    urls = [url for key in ("engagement", "enterprise") if (url := cfg.get(key, {}).get("git", {}).get("url"))]
    if not urls:
        return None
    creds = collect_credentials(urls)  # type: ignore[arg-type]
    return build_git_env(creds, create_askpass_script()) if creds else None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="arch-init",
        description="Initialize architecture workspace from arch-workspace.yaml",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to arch-workspace.yaml (default: search from CWD upward)",
    )
    parser.add_argument(
        "--initialize-engagement-repo-if-empty",
        action="store_true",
        default=False,
        help="Initialize an existing empty git engagement repo if the configured branch does not exist yet",
    )
    parser.add_argument(
        "--initialize-enterprise-repo-if-empty",
        action="store_true",
        default=False,
        help="Initialize an existing empty git enterprise repo if the configured branch does not exist yet",
    )
    parser.add_argument(
        "--git-token-file",
        default=None,
        metavar="PATH",
        help="Read the HTTPS personal access token from this file (alternative to "
        "ARCH_GIT_HTTPS_TOKEN; keeps the secret out of the environment)",
    )
    args = parser.parse_args(argv)

    from src.infrastructure.git.git_auth import register_token_file

    register_token_file(args.git_token_file)

    if args.config:
        config_path = args.config.resolve()
        if not config_path.is_file():
            raise SystemExit(f"ERROR: config not found: {config_path}")
    else:
        config_path = _find_config(Path.cwd())
        if config_path is None:
            raise SystemExit(f"ERROR: {CONFIG_FILENAME} not found in current directory or parents")

    workspace_root = config_path.parent
    print(f"arch-init: using {config_path}")
    print(f"  workspace root: {workspace_root}")

    cfg = _parse_config(config_path)

    git_env = _collect_init_credentials(cfg)

    engagement_root = _resolve_repo(
        "engagement",
        cfg["engagement"],
        workspace_root,
        initialize_if_empty=args.initialize_engagement_repo_if_empty,
        git_env=git_env,
    )
    enterprise_root = _resolve_repo(
        "enterprise",
        cfg["enterprise"],
        workspace_root,
        initialize_if_empty=args.initialize_enterprise_repo_if_empty,
        git_env=git_env,
    )

    state_path = _write_state(workspace_root, engagement_root, enterprise_root)

    # Regenerate static ArchiMate include files for both repos
    try:
        from src.infrastructure.rendering.generate_static_includes import generate_static_includes  # noqa: PLC0415
        for root in (engagement_root, enterprise_root):
            generate_static_includes(root)
        print("  static includes: regenerated")
    except Exception as exc:  # noqa: BLE001
        print(f"  static includes: skipped ({exc})")

    print("\narch-init: success")
    print(f"  engagement: {engagement_root}")
    print(f"  enterprise: {enterprise_root}")
    print(f"  state file: {state_path}")


if __name__ == "__main__":
    main()
