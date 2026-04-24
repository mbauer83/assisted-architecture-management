"""Background git-sync manager: polls git repos and blocks writes during pull."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_POLL_S = 60.0
_FETCH_TIMEOUT_S = 20.0
_PULL_TIMEOUT_S = 30.0
_AUTO_UNBLOCK_S = 60.0


class GitSyncManager:
    """Manages periodic git syncs of git-backed repositories."""

    def __init__(
        self,
        repos: list[Path],
        poll_interval_s: float = _DEFAULT_POLL_S,
        ssh_passphrase: str | None = None,
    ) -> None:
        self._repos = repos
        self._poll_interval_s = poll_interval_s
        self._ssh_passphrase = ssh_passphrase
        self._task: asyncio.Task[None] | None = None
        self._askpass_script: Path | None = None

    async def start(self) -> None:
        """Start the background polling task."""
        if self._ssh_passphrase:
            self._askpass_script = self._create_askpass_script()
        self._task = asyncio.create_task(self._poll_loop(), name="git-sync")
        logger.info("git-sync manager started for %d repos (poll interval: %.1fs)",
                    len(self._repos), self._poll_interval_s)

    async def stop(self) -> None:
        """Stop the background polling task."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("git-sync manager stopped")
        if self._askpass_script is not None:
            try:
                self._askpass_script.unlink()
            except OSError:
                pass
            self._askpass_script = None

    def _create_askpass_script(self) -> Path:
        """Create a temporary SSH_ASKPASS helper; passphrase comes from env, not the script."""
        fd, path_str = tempfile.mkstemp(prefix="arch-askpass-", suffix=".sh")
        path = Path(path_str)
        try:
            os.write(fd, b"#!/bin/sh\nprintf '%s\\n' \"$ARCH_GIT_SSH_PASSWORD\"\n")
        finally:
            os.close(fd)
        path.chmod(0o700)
        return path

    def _git_env(self) -> dict[str, str] | None:
        """Return a subprocess env dict with SSH askpass wired up, or None to inherit."""
        if self._askpass_script is None or self._ssh_passphrase is None:
            return None
        env = os.environ.copy()
        env["SSH_ASKPASS"] = str(self._askpass_script)
        env["SSH_ASKPASS_REQUIRE"] = "force"
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["ARCH_GIT_SSH_PASSWORD"] = self._ssh_passphrase
        return env

    async def _poll_loop(self) -> None:
        """Main polling loop: periodically check each repo for updates."""
        while True:
            for repo in self._repos:
                try:
                    await self._sync_repo(repo)
                except Exception:  # noqa: BLE001
                    logger.exception("git sync error for %s", repo)
            await asyncio.sleep(self._poll_interval_s)

    async def _run_git(
        self,
        repo: Path,
        *args: str,
        timeout: float = 10.0,
    ) -> tuple[int, str, str]:
        """Run a git command and return (returncode, stdout, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=repo,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._git_env(),
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return -1, "", "timeout"
        return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")

    async def _is_git_repo(self, path: Path) -> bool:
        """Check if a path is a git repository."""
        rc, _, _ = await self._run_git(path, "rev-parse", "--git-dir")
        return rc == 0

    async def _commits_behind(self, repo: Path) -> int:
        """Return the number of upstream commits not yet in HEAD (0 = up to date)."""
        rc, out, _ = await self._run_git(repo, "rev-list", "--count", "HEAD..@{u}")
        if rc != 0:
            return 0
        try:
            return int(out.strip())
        except ValueError:
            return 0

    async def _is_workspace_clean(self, repo: Path) -> bool:
        """Check if the working tree is clean."""
        rc, out, _ = await self._run_git(repo, "status", "--porcelain")
        return rc == 0 and not out.strip()

    async def _sync_repo(self, repo: Path) -> None:
        """Attempt to sync a single repo (fetch, check for updates, pull if clean)."""
        from src.tools.gui_routers.events import event_bus
        from src.tools.write_block_manager import block_repo, unblock_repo, is_blocked

        if not await self._is_git_repo(repo):
            return

        # Fetch updates from origin (non-blocking, doesn't affect write state)
        rc, _, stderr = await self._run_git(repo, "fetch", "origin", timeout=_FETCH_TIMEOUT_S)
        if rc != 0:
            logger.warning("git fetch failed for %s: %s", repo, stderr.strip())
            return

        # Check if there are updates available
        n_commits = await self._commits_behind(repo)
        if n_commits == 0:
            return

        # Don't pull if workspace is dirty
        if not await self._is_workspace_clean(repo):
            logger.info("skipping git pull for %s: workspace dirty", repo)
            return

        repo_label = str(repo)
        was_blocked = is_blocked(repo)

        # Block writes before pulling
        block_repo(repo)
        await event_bus.publish({"type": "git_sync_started", "repo": repo_label})
        logger.info("starting git pull for %s (%d commits)", repo_label, n_commits)

        try:
            rc, _, stderr = await self._run_git(repo, "pull", "--ff-only", timeout=_PULL_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001
            logger.exception("git pull error for %s", repo)
            await event_bus.publish({
                "type": "git_sync_failed",
                "repo": repo_label,
                "error": str(exc),
                "auto_unblock_in_seconds": _AUTO_UNBLOCK_S,
            })
            # Schedule auto-unblock to prevent deadlock
            asyncio.create_task(self._auto_unblock(repo, _AUTO_UNBLOCK_S, was_blocked))
            return

        if rc == 0:
            # Pull succeeded: restore original block state and notify clients
            if not was_blocked:
                unblock_repo(repo)
                await event_bus.publish({
                    "type": "write_block_changed",
                    "repo": repo_label,
                    "blocked": False,
                })
            await event_bus.publish({
                "type": "git_sync_completed",
                "repo": repo_label,
                "commits_pulled": n_commits,
            })
            logger.info("git pull completed for %s (%d commits)", repo_label, n_commits)
        else:
            # Pull failed: keep blocked, schedule auto-unblock
            error_msg = stderr.strip() or "unknown error"
            await event_bus.publish({
                "type": "git_sync_failed",
                "repo": repo_label,
                "error": error_msg,
                "auto_unblock_in_seconds": _AUTO_UNBLOCK_S,
            })
            logger.warning("git pull failed for %s: %s", repo_label, error_msg)
            asyncio.create_task(self._auto_unblock(repo, _AUTO_UNBLOCK_S, was_blocked))

    async def _auto_unblock(
        self,
        repo: Path,
        delay_s: float,
        was_blocked: bool,
    ) -> None:
        """Auto-unblock a repo after a delay (failure recovery)."""
        await asyncio.sleep(delay_s)
        if not was_blocked:
            from src.tools.write_block_manager import unblock_repo
            from src.tools.gui_routers.events import event_bus
            unblock_repo(repo)
            await event_bus.publish({
                "type": "write_block_changed",
                "repo": str(repo),
                "blocked": False,
            })
            logger.info("auto-unblock completed for %s after failure recovery", repo)
