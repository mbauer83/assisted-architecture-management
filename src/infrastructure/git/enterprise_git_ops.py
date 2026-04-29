"""Synchronous git operations for the enterprise repository branch lifecycle.

These functions run inside the write-queue executor thread (not the asyncio
event loop), so they use subprocess.run. Network operations (push/pull) inherit
the shared SSH environment from git_env.py, which is populated by GitSyncManager
on startup, so the same askpass credentials apply here as in the background sync.

Engagement-repo helpers are also here to keep all git commit/push logic in one place.
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.config.repo_paths import DIAGRAM_CATALOG, DOCS, MODEL
from src.infrastructure.git import enterprise_sync_state
from src.infrastructure.git.enterprise_sync_state import EnterpriseSyncState

logger = logging.getLogger(__name__)
_GIT_TIMEOUT = 30
_PUSH_TIMEOUT = 60


def _run(repo: Path, *args: str, timeout: float = _GIT_TIMEOUT) -> tuple[int, str, str]:
    from src.infrastructure.git.git_env import get_ssh_env

    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=get_ssh_env(),
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


# ---------------------------------------------------------------------------
# Introspection helpers
# ---------------------------------------------------------------------------


def current_branch(repo: Path) -> str | None:
    rc, out, _ = _run(repo, "rev-parse", "--abbrev-ref", "HEAD")
    return out if rc == 0 and out not in ("", "HEAD") else None


def current_commit(repo: Path) -> str | None:
    rc, out, _ = _run(repo, "rev-parse", "HEAD")
    return out if rc == 0 else None


def has_uncommitted_changes(repo: Path, *pathspecs: str) -> bool:
    args = ["status", "--porcelain"]
    if pathspecs:
        args += ["--", *pathspecs]
    rc, out, _ = _run(repo, *args)
    return rc == 0 and bool(out)


def commits_ahead_of_main(repo: Path) -> int:
    rc, out, _ = _run(repo, "rev-list", "--count", "origin/main..HEAD")
    try:
        return int(out) if rc == 0 else 0
    except ValueError:
        return 0


def commits_behind_main(repo: Path) -> int:
    rc, out, _ = _run(repo, "rev-list", "--count", "HEAD..origin/main")
    try:
        return int(out) if rc == 0 else 0
    except ValueError:
        return 0


def promotion_merged_into_main(repo: Path) -> bool:
    """Detect merge via content diff: empty diff means working branch is in origin/main."""
    rc, out, _ = _run(
        repo,
        "diff",
        "origin/main",
        "HEAD",
        "--",
        MODEL,
        DOCS,
        DIAGRAM_CATALOG,
    )
    return rc == 0 and not out


# ---------------------------------------------------------------------------
# Enterprise branch lifecycle
# ---------------------------------------------------------------------------


def ensure_working_branch(enterprise_root: Path) -> str:
    """Ensure the enterprise checkout is on a working branch, creating one if SYNCED.

    Safe to call repeatedly — idempotent when already on the correct branch.
    Returns the working branch name.  Raises RuntimeError if branch creation fails.
    """
    state = enterprise_sync_state.load(enterprise_root)

    if state.status in ("accumulating", "pending"):
        branch = current_branch(enterprise_root)
        if branch:
            if branch != state.branch:
                logger.warning(
                    "Enterprise branch mismatch: state=%s actual=%s — reconciling",
                    state.branch,
                    branch,
                )
                enterprise_sync_state.save(
                    enterprise_root,
                    EnterpriseSyncState(
                        status=state.status,
                        branch=branch,
                        branch_tip=state.branch_tip,
                        pushed_at=state.pushed_at,
                        commits_behind=state.commits_behind,
                    ),
                )
            return branch

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    branch_name = f"arch/work-{ts}"
    rc, _, stderr = _run(enterprise_root, "checkout", "-b", branch_name)
    if rc != 0:
        raise RuntimeError(f"Failed to create enterprise working branch '{branch_name}': {stderr}")
    enterprise_sync_state.save(
        enterprise_root,
        EnterpriseSyncState(status="accumulating", branch=branch_name),
    )
    logger.info("Created enterprise working branch: %s", branch_name)
    return branch_name


def commit_enterprise_work(enterprise_root: Path, message: str) -> str:
    """Stage and commit all changes in the enterprise repo. Returns the new commit hash."""
    if not has_uncommitted_changes(enterprise_root):
        raise ValueError("No changes to save in the enterprise repository")
    rc, _, stderr = _run(enterprise_root, "add", ".")
    if rc != 0:
        raise RuntimeError(f"Failed to stage enterprise changes: {stderr}")
    rc, _, stderr = _run(enterprise_root, "commit", "-m", message)
    if rc != 0:
        raise RuntimeError(f"Failed to commit enterprise changes: {stderr}")
    commit = current_commit(enterprise_root) or ""
    logger.info("Enterprise work saved: %.7s — %s", commit, message)
    return commit


def push_enterprise_branch(enterprise_root: Path) -> str:
    """Push the working branch to origin and transition the state to PENDING.

    Returns the branch name. Raises ValueError if there are unsaved changes,
    RuntimeError if the push fails.
    """
    state = enterprise_sync_state.load(enterprise_root)
    branch = current_branch(enterprise_root)
    if not branch:
        raise RuntimeError("Enterprise repo is in detached HEAD state")
    if has_uncommitted_changes(enterprise_root):
        raise ValueError("Enterprise repository has unsaved changes. Save your work before submitting for review.")
    rc, _, stderr = _run(enterprise_root, "push", "-u", "origin", branch, timeout=_PUSH_TIMEOUT)
    if rc != 0:
        raise RuntimeError(f"Failed to push enterprise branch '{branch}': {stderr}")
    commit = current_commit(enterprise_root) or ""
    enterprise_sync_state.save(
        enterprise_root,
        EnterpriseSyncState(
            status="pending",
            branch=branch,
            branch_tip=commit,
            pushed_at=datetime.now(timezone.utc).isoformat(),
            commits_behind=state.commits_behind,
        ),
    )
    logger.info("Enterprise branch submitted for review: %s", branch)
    return branch


def abandon_enterprise_branch(enterprise_root: Path) -> str | None:
    """Discard all working-branch changes and return the enterprise repo to main."""
    state = enterprise_sync_state.load(enterprise_root)
    branch = state.branch
    rc, _, stderr = _run(enterprise_root, "checkout", "main")
    if rc != 0:
        raise RuntimeError(f"Failed to return enterprise repo to main: {stderr}")
    if branch:
        _run(enterprise_root, "branch", "-D", branch)
    enterprise_sync_state.clear(enterprise_root)
    logger.info("Enterprise working branch abandoned: %s", branch)
    return branch


# ---------------------------------------------------------------------------
# Engagement repo
# ---------------------------------------------------------------------------


def commit_engagement_work(engagement_root: Path, message: str) -> str:
    """Stage and commit all changes in the engagement repo. Returns the commit hash."""
    if not has_uncommitted_changes(engagement_root):
        raise ValueError("No changes to save in the engagement repository")
    rc, _, stderr = _run(engagement_root, "add", ".")
    if rc != 0:
        raise RuntimeError(f"Failed to stage engagement changes: {stderr}")
    rc, _, stderr = _run(engagement_root, "commit", "-m", message)
    if rc != 0:
        raise RuntimeError(f"Failed to commit engagement changes: {stderr}")
    commit = current_commit(engagement_root) or ""
    logger.info("Engagement work saved: %.7s — %s", commit, message)
    return commit


def push_engagement(engagement_root: Path) -> None:
    """Push the engagement repo's current branch to origin."""
    rc, _, stderr = _run(engagement_root, "push", timeout=_PUSH_TIMEOUT)
    if rc != 0:
        raise RuntimeError(f"Failed to push engagement changes: {stderr}")
    logger.info("Engagement changes pushed to remote")
