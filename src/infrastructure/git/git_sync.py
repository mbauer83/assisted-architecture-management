"""Background git-sync manager: polls repos and coordinates writes around pulls.

Two repo roles are handled differently:

engagement  — fetch + pull (ff-only when clean, rebase when local commits exist).
              Rebase conflicts abort cleanly and surface a sync_conflict event.

enterprise  — state-machine-aware (see enterprise_sync_state.py):
  synced      : fetch + ff-only pull (checkout is always clean on main)
  accumulating: fetch only; emits sync_enterprise_diverged if origin/main moved
  pending     : fetch + content-diff; auto-transitions to main on merge detection
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from src.infrastructure.git.git_auth import GitCredentials

from src.config.repo_paths import DIAGRAM_CATALOG, DOCS, MODEL
from src.infrastructure.git import enterprise_sync_state

logger = logging.getLogger(__name__)
_DEFAULT_POLL_S = 60.0
_FETCH_TIMEOUT_S = 20.0
_PULL_TIMEOUT_S = 30.0
_AUTO_UNBLOCK_S = 60.0


@dataclass
class RepoSpec:
    """A git-backed repository and its role within the two-tier model."""

    path: Path
    role: Literal["engagement", "enterprise"]


class GitSyncManager:
    def __init__(
        self,
        repos: list[RepoSpec],
        poll_interval_s: float = _DEFAULT_POLL_S,
        credentials: "GitCredentials | None" = None,
        on_repo_changed: Callable[[Path], Awaitable[None]] | None = None,
    ) -> None:
        self._repos = repos
        self._poll_interval_s = poll_interval_s
        self._credentials = credentials
        self._on_repo_changed = on_repo_changed
        self._task: asyncio.Task[None] | None = None
        self._askpass_script: Path | None = None
        self._last_dirty_state: dict[Path, bool] = {}
        self._last_block_reason: dict[Path, str | None] = {}

    async def start(self) -> None:
        if self._credentials is not None:
            from src.infrastructure.git import git_env
            from src.infrastructure.git.git_auth import build_git_env, create_askpass_script

            self._askpass_script = create_askpass_script()
            git_env.set_ssh_env(build_git_env(self._credentials, self._askpass_script))
        self._task = asyncio.create_task(self._poll_loop(), name="git-sync")
        logger.info("git-sync started for %d repo(s) (poll %.1fs)", len(self._repos), self._poll_interval_s)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("git-sync stopped")
        if self._askpass_script is not None:
            try:
                self._askpass_script.unlink()
            except OSError:
                pass
            self._askpass_script = None
        from src.infrastructure.git import git_env

        git_env.set_ssh_env(None)

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        while True:
            for spec in self._repos:
                try:
                    if spec.role == "engagement":
                        await self._sync_engagement(spec.path)
                    else:
                        await self._sync_enterprise(spec.path)
                except Exception:
                    logger.exception("git sync error for %s (%s)", spec.path, spec.role)
            await asyncio.sleep(self._poll_interval_s)

    # ------------------------------------------------------------------
    # Low-level git helpers
    # ------------------------------------------------------------------

    async def _git(self, repo: Path, *args: str, timeout: float = 10.0) -> tuple[int, str, str]:
        from src.infrastructure.git.git_env import get_ssh_env

        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=repo,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=get_ssh_env(),
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return -1, "", "timeout"
        return_code = proc.returncode if proc.returncode is not None else -1
        return return_code, out.decode(errors="replace"), err.decode(errors="replace")

    async def _is_git_repo(self, path: Path) -> bool:
        rc, _, _ = await self._git(path, "rev-parse", "--git-dir")
        return rc == 0

    async def _count(self, repo: Path, range_: str) -> int:
        count = await self._rev_count(repo, range_)
        return count if count is not None else 0

    async def _rev_count(self, repo: Path, range_: str) -> int | None:
        """Commit count for ``range_``, or None when git could not evaluate it.

        The None case (invalid ref, repo error) is distinct from a genuine zero,
        so callers can surface a problem instead of silently treating it as
        "nothing to do".
        """
        rc, out, _ = await self._git(repo, "rev-list", "--count", range_)
        if rc != 0:
            return None
        try:
            return int(out.strip())
        except ValueError:
            return None

    async def _is_clean(self, repo: Path) -> bool:
        rc, out, _ = await self._git(repo, "status", "--porcelain")
        return rc == 0 and not out.strip()

    async def _upstream_ref(self, repo: Path) -> str | None:
        """Resolve the current branch's upstream (e.g. ``origin/main``), or None if unset."""
        rc, out, _ = await self._git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        ref = out.strip()
        return ref if rc == 0 and ref else None

    async def _notify_sync_blocked(self, repo: Path, reason: str) -> None:
        """Surface a non-fatal sync skip, once per distinct reason (avoids per-poll spam).

        Emitted as a dedicated ``sync_blocked`` event (no write block was taken), so the
        GUI can report the reason without the misleading "writes resume in 0s" wording.
        """
        if self._last_block_reason.get(repo) == reason:
            return
        self._last_block_reason[repo] = reason
        from src.infrastructure.gui.routers.events import event_bus  # noqa: PLC0415

        logger.warning("enterprise sync blocked for %s: %s", repo, reason)
        await event_bus.publish({"type": "sync_blocked", "repo": str(repo), "reason": reason})

    def _clear_block_reason(self, repo: Path) -> None:
        self._last_block_reason[repo] = None

    async def _promotion_merged(self, enterprise_root: Path) -> bool:
        rc, out, _ = await self._git(
            enterprise_root,
            "diff",
            "origin/main",
            "HEAD",
            "--",
            MODEL,
            DOCS,
            DIAGRAM_CATALOG,
        )
        return rc == 0 and not out.strip()

    async def _notify_changed(self, repo: Path) -> None:
        if self._on_repo_changed:
            await self._on_repo_changed(repo)

    async def _auto_unblock(self, repo: Path, delay_s: float, was_blocked: bool) -> None:
        await asyncio.sleep(delay_s)
        if not was_blocked:
            from src.infrastructure.gui.routers.events import event_bus
            from src.infrastructure.workspace.write_block_manager import unblock_repo

            unblock_repo(repo)
            await event_bus.publish({"type": "write_block_changed", "repo": str(repo), "blocked": False})
            logger.info("auto-unblock completed for %s", repo)

    # ------------------------------------------------------------------
    # Engagement
    # ------------------------------------------------------------------

    async def _publish_dirty_state_change(self, repo: Path, *, is_dirty: bool) -> None:
        from src.infrastructure.gui.routers.events import event_bus  # noqa: PLC0415

        if is_dirty != self._last_dirty_state.get(repo, False):
            self._last_dirty_state[repo] = is_dirty
            await event_bus.publish({"type": "sync_status_changed", "repo": str(repo)})

    async def _sync_engagement(self, repo: Path) -> None:
        from src.infrastructure.gui.routers.events import event_bus  # noqa: PLC0415
        from src.infrastructure.workspace.mutation_gate import get_workspace_gate  # noqa: PLC0415

        if not await self._is_git_repo(repo):
            return

        is_clean = await self._is_clean(repo)
        await self._publish_dirty_state_change(repo, is_dirty=not is_clean)

        rc, _, err = await self._git(repo, "fetch", "origin", timeout=_FETCH_TIMEOUT_S)
        if rc != 0:
            logger.warning("fetch failed for engagement %s: %s", repo, err.strip())
            return

        behind = await self._count(repo, "HEAD..@{u}")
        if behind == 0:
            return
        ahead = await self._count(repo, "@{u}..HEAD")
        if not is_clean and ahead == 0:
            logger.info("skipping engagement pull %s: uncommitted changes", repo)
            return

        rc, head_out, _ = await self._git(repo, "rev-parse", "HEAD")
        old_sha = head_out.strip()
        rc, branch_out, _ = await self._git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        branch = branch_out.strip()
        gate = get_workspace_gate()
        if gate.block_reason == "read_only":
            return

        from src.infrastructure.git.git_sync_m4 import (  # noqa: PLC0415
            add_detached_worktree,
            prepare_rebase_worktree,
            run_m4_pull,
        )

        await event_bus.publish({"type": "sync_pull_started", "repo": str(repo), "behind": behind})
        try:
            with gate.blocking_writes("sync_in_progress"):
                if ahead > 0:
                    rebase_result = await prepare_rebase_worktree(self._git, repo, old_sha, timeout=_PULL_TIMEOUT_S)
                    if rebase_result is None:
                        await event_bus.publish(
                            {"type": "sync_conflict", "repo": str(repo), "error": "rebase conflict"}
                        )
                        return
                    worktree_path, new_sha = rebase_result
                else:
                    rc, new_sha_out, _ = await self._git(repo, "rev-parse", "@{u}")
                    new_sha = new_sha_out.strip()
                    worktree_path = await add_detached_worktree(self._git, repo, new_sha, timeout=_PULL_TIMEOUT_S)
                try:
                    run_m4_pull(repo, worktree_path, branch=branch, old_sha=old_sha, new_sha=new_sha, gate=gate)
                finally:
                    await self._git(repo, "worktree", "remove", "--force", str(worktree_path))
                await self._git(repo, "reset", "--mixed", "HEAD")
        except Exception as exc:
            logger.exception("pull error for engagement %s", repo)
            await event_bus.publish({
                "type": "sync_pull_failed", "repo": str(repo), "error": str(exc),
                "auto_unblock_in_seconds": 0,
            })
            return

        await event_bus.publish({"type": "sync_pull_completed", "repo": str(repo), "commits_pulled": behind})
        await self._notify_changed(repo)

    # ------------------------------------------------------------------
    # Enterprise (state-machine dispatch)
    # ------------------------------------------------------------------

    async def _sync_enterprise(self, root: Path) -> None:
        if not await self._is_git_repo(root):
            return
        rc, _, err = await self._git(root, "fetch", "origin", timeout=_FETCH_TIMEOUT_S)
        if rc != 0:
            await self._notify_sync_blocked(root, f"git fetch from origin failed — {err.strip() or 'unknown error'}")
            return

        state = enterprise_sync_state.load(root)
        if state.is_synced():
            await self._ent_on_main(root)
        elif state.is_accumulating():
            await self._ent_accumulating(root, state)
        elif state.is_pending():
            await self._ent_pending(root, state)

    async def _ent_on_main(self, root: Path) -> None:
        from src.infrastructure.gui.routers.events import event_bus
        from src.infrastructure.workspace.mutation_gate import get_workspace_gate

        upstream = await self._upstream_ref(root)
        if upstream is None:
            await self._notify_sync_blocked(
                root,
                "no upstream tracking for the checked-out branch — the repository was not cloned "
                "from origin (likely an unrelated local init). Re-clone it so sync can fast-forward.",
            )
            return
        behind = await self._rev_count(root, f"HEAD..{upstream}")
        ahead = await self._rev_count(root, f"{upstream}..HEAD")
        if behind is None or ahead is None:
            await self._notify_sync_blocked(root, f"could not compute sync state against {upstream}")
            return
        if ahead > 0:
            await self._notify_sync_blocked(
                root,
                f"local branch is {ahead} commit(s) ahead of {upstream} — the enterprise mirror has "
                "diverged (unpublished commits). Investigate before sync can resume.",
            )
            return
        if behind == 0:
            self._clear_block_reason(root)
            return
        if not await self._is_clean(root):
            await self._notify_sync_blocked(root, "local working tree has uncommitted changes — pull skipped")
            return

        self._clear_block_reason(root)
        root_label = str(root)
        gate = get_workspace_gate()
        if gate.block_reason == "read_only":
            return

        rc, head_out, _ = await self._git(root, "rev-parse", "HEAD")
        old_sha = head_out.strip()
        rc, branch_out, _ = await self._git(root, "rev-parse", "--abbrev-ref", "HEAD")
        branch = branch_out.strip()
        rc, new_sha_out, _ = await self._git(root, "rev-parse", upstream)
        new_sha = new_sha_out.strip()

        from src.infrastructure.git.git_sync_m4 import add_detached_worktree, run_m4_pull  # noqa: PLC0415

        await event_bus.publish({"type": "sync_pull_started", "repo": root_label, "behind": behind})
        try:
            with gate.blocking_writes("sync_in_progress"):
                worktree_path = await add_detached_worktree(self._git, root, new_sha, timeout=_PULL_TIMEOUT_S)
                try:
                    run_m4_pull(root, worktree_path, branch=branch, old_sha=old_sha, new_sha=new_sha, gate=gate)
                finally:
                    await self._git(root, "worktree", "remove", "--force", str(worktree_path))
                await self._git(root, "reset", "--mixed", "HEAD")
        except Exception as exc:
            from src.infrastructure.gui.routers.events import event_bus as _bus  # noqa: PLC0415
            await _bus.publish({
                "type": "sync_pull_failed", "repo": root_label, "error": str(exc),
                "auto_unblock_in_seconds": int(_AUTO_UNBLOCK_S),
            })
            asyncio.create_task(self._auto_unblock(root, _AUTO_UNBLOCK_S, False))
            return

        await event_bus.publish({"type": "sync_pull_completed", "repo": root_label, "commits_pulled": behind})
        await self._notify_changed(root)

    async def _ent_accumulating(
        self,
        root: Path,
        state: enterprise_sync_state.EnterpriseSyncState,
    ) -> None:
        from src.infrastructure.gui.routers.events import event_bus

        behind = await self._count(root, "HEAD..origin/main")
        if behind != state.commits_behind:
            state.commits_behind = behind
            enterprise_sync_state.save(root, state)
        if behind > 0:
            await event_bus.publish({"type": "sync_enterprise_diverged", "repo": str(root), "commits_behind": behind})

    async def _ent_pending(
        self,
        root: Path,
        state: enterprise_sync_state.EnterpriseSyncState,
    ) -> None:
        from src.infrastructure.gui.routers.events import event_bus
        from src.infrastructure.workspace.write_block_manager import block_repo, unblock_repo

        behind = await self._count(root, "HEAD..origin/main")
        if behind != state.commits_behind:
            state.commits_behind = behind
            enterprise_sync_state.save(root, state)

        if not await self._promotion_merged(root):
            return

        root_label = str(root)
        block_repo(root)
        await event_bus.publish({"type": "sync_enterprise_merging", "repo": root_label})
        try:
            for git_args in [["checkout", "main"], ["pull", "--ff-only"]]:
                rc, _, err = await self._git(root, *git_args, timeout=_PULL_TIMEOUT_S)
                if rc != 0:
                    raise RuntimeError(err.strip() or "git error")
            if state.branch:
                await self._git(root, "branch", "-D", state.branch)
            enterprise_sync_state.clear(root)
            unblock_repo(root)
            await event_bus.publish({"type": "sync_enterprise_merged", "repo": root_label})
            await self._notify_changed(root)
        except Exception as exc:
            logger.exception("enterprise merge transition failed for %s", root)
            unblock_repo(root)
            await event_bus.publish({"type": "sync_enterprise_merge_failed", "repo": root_label, "error": str(exc)})
