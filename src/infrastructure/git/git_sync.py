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
import os
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
        ssh_passphrase: str | None = None,
        on_repo_changed: Callable[[Path], Awaitable[None]] | None = None,
    ) -> None:
        self._repos = repos
        self._poll_interval_s = poll_interval_s
        self._ssh_passphrase = ssh_passphrase
        self._on_repo_changed = on_repo_changed
        self._task: asyncio.Task[None] | None = None
        self._askpass_script: Path | None = None
        self._last_dirty_state: dict[Path, bool] = {}

    async def start(self) -> None:
        if self._ssh_passphrase:
            self._askpass_script = self._create_askpass_script()
            from src.infrastructure.git import git_env

            git_env.set_ssh_env(self._ssh_env())
        self._task = asyncio.create_task(self._poll_loop(), name="git-sync")
        logger.info(
            "git-sync started for %d repo(s) (poll %.1fs)", len(self._repos), self._poll_interval_s
        )

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
    # SSH helpers
    # ------------------------------------------------------------------

    def _create_askpass_script(self) -> Path:
        fd, path_str = tempfile.mkstemp(prefix="arch-askpass-", suffix=".sh")
        path = Path(path_str)
        try:
            os.write(fd, b"#!/bin/sh\nprintf '%s\\n' \"$ARCH_GIT_SSH_PASSWORD\"\n")
        finally:
            os.close(fd)
        path.chmod(0o700)
        return path

    def _ssh_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["SSH_ASKPASS"] = str(self._askpass_script)
        env["SSH_ASKPASS_REQUIRE"] = "force"
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["ARCH_GIT_SSH_PASSWORD"] = self._ssh_passphrase or ""
        return env

    def _git_env(self) -> dict[str, str] | None:
        return self._ssh_env() if self._askpass_script and self._ssh_passphrase else None

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
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=repo,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._git_env(),
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
        rc, out, _ = await self._git(repo, "rev-list", "--count", range_)
        try:
            return int(out.strip()) if rc == 0 else 0
        except ValueError:
            return 0

    async def _is_clean(self, repo: Path) -> bool:
        rc, out, _ = await self._git(repo, "status", "--porcelain")
        return rc == 0 and not out.strip()

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
            await event_bus.publish(
                {"type": "write_block_changed", "repo": str(repo), "blocked": False}
            )
            logger.info("auto-unblock completed for %s", repo)

    # ------------------------------------------------------------------
    # Engagement
    # ------------------------------------------------------------------

    async def _sync_engagement(self, repo: Path) -> None:
        from src.infrastructure.gui.routers.events import event_bus
        from src.infrastructure.workspace.write_block_manager import block_repo, is_blocked, unblock_repo

        if not await self._is_git_repo(repo):
            return

        is_clean = await self._is_clean(repo)
        is_dirty = not is_clean
        was_dirty = self._last_dirty_state.get(repo, False)
        if is_dirty != was_dirty:
            self._last_dirty_state[repo] = is_dirty
            await event_bus.publish({"type": "sync_status_changed", "repo": str(repo)})

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

        pull_args = ["pull", "--rebase"] if ahead > 0 else ["pull", "--ff-only"]
        repo_label, was_blocked = str(repo), is_blocked(repo)
        block_repo(repo)
        await event_bus.publish({"type": "sync_pull_started", "repo": repo_label, "behind": behind})

        try:
            rc, _, err = await self._git(repo, *pull_args, timeout=_PULL_TIMEOUT_S)
        except Exception as exc:
            logger.exception("pull error for engagement %s", repo)
            await event_bus.publish(
                {"type": "sync_pull_failed", "repo": repo_label, "error": str(exc)}
            )
            asyncio.create_task(self._auto_unblock(repo, _AUTO_UNBLOCK_S, was_blocked))
            return

        if rc == 0:
            if not was_blocked:
                unblock_repo(repo)
            await event_bus.publish(
                {"type": "sync_pull_completed", "repo": repo_label, "commits_pulled": behind}
            )
            await self._notify_changed(repo)
        else:
            if "--rebase" in pull_args and "CONFLICT" in err:
                await self._git(repo, "rebase", "--abort")
                await event_bus.publish(
                    {"type": "sync_conflict", "repo": repo_label, "error": err.strip()}
                )
            else:
                await event_bus.publish(
                    {"type": "sync_pull_failed", "repo": repo_label, "error": err.strip()}
                )
            asyncio.create_task(self._auto_unblock(repo, _AUTO_UNBLOCK_S, was_blocked))

    # ------------------------------------------------------------------
    # Enterprise (state-machine dispatch)
    # ------------------------------------------------------------------

    async def _sync_enterprise(self, root: Path) -> None:
        if not await self._is_git_repo(root):
            return
        rc, _, err = await self._git(root, "fetch", "origin", timeout=_FETCH_TIMEOUT_S)
        if rc != 0:
            logger.warning("fetch failed for enterprise %s: %s", root, err.strip())
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
        from src.infrastructure.workspace.write_block_manager import block_repo, is_blocked, unblock_repo

        behind = await self._count(root, "HEAD..@{u}")
        if behind == 0 or not await self._is_clean(root):
            return
        root_label, was_blocked = str(root), is_blocked(root)
        block_repo(root)
        await event_bus.publish({"type": "sync_pull_started", "repo": root_label, "behind": behind})
        try:
            rc, _, err = await self._git(root, "pull", "--ff-only", timeout=_PULL_TIMEOUT_S)
        except Exception as exc:
            await event_bus.publish(
                {"type": "sync_pull_failed", "repo": root_label, "error": str(exc)}
            )
            asyncio.create_task(self._auto_unblock(root, _AUTO_UNBLOCK_S, was_blocked))
            return

        if rc == 0:
            if not was_blocked:
                unblock_repo(root)
            await event_bus.publish(
                {"type": "sync_pull_completed", "repo": root_label, "commits_pulled": behind}
            )
            await self._notify_changed(root)
        else:
            await event_bus.publish(
                {"type": "sync_pull_failed", "repo": root_label, "error": err.strip()}
            )
            asyncio.create_task(self._auto_unblock(root, _AUTO_UNBLOCK_S, was_blocked))

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
            await event_bus.publish(
                {"type": "sync_enterprise_diverged", "repo": str(root), "commits_behind": behind}
            )

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
            await event_bus.publish(
                {"type": "sync_enterprise_merge_failed", "repo": root_label, "error": str(exc)}
            )
