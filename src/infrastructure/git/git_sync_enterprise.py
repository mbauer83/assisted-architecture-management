"""Enterprise half of the git-sync component: the branch-review state machine.

Split from git_sync.py purely along the engagement/enterprise seam — these
functions are GitSyncManager internals and use its low-level git helpers, the
same way git_sync_m4 receives them.

  synced      : fetch + ff-only pull (checkout is always clean on main)
  accumulating: fetch; emits sync_enterprise_diverged if origin/main moved, and
                auto-transitions to main when the working branch was pushed and
                merged outside the submit flow (real commits + clean tree +
                empty content diff against origin/main)
  pending     : fetch + content-diff; auto-transitions to main on merge detection
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from src.config.repo_paths import DIAGRAM_CATALOG, DOCS, MODEL
from src.infrastructure.git import enterprise_sync_state
from src.infrastructure.git.git_sync import (
    _AUTO_UNBLOCK_S,
    _FETCH_TIMEOUT_S,
    _PULL_TIMEOUT_S,
    GitSyncManager,
)

logger = logging.getLogger(__name__)


async def sync_enterprise(sync: GitSyncManager, root: Path) -> None:
    if not await sync._is_git_repo(root):
        return
    rc, _, err = await sync._git(root, "fetch", "origin", timeout=_FETCH_TIMEOUT_S)
    if rc != 0:
        await sync._notify_sync_blocked(root, f"git fetch from origin failed — {err.strip() or 'unknown error'}")
        return

    state = await reconcile_state(sync, root)
    if state.is_synced():
        await ent_on_main(sync, root)
    elif state.is_accumulating():
        await ent_accumulating(sync, root, state)
    elif state.is_pending():
        await ent_pending(sync, root, state)


async def reconcile_state(sync: GitSyncManager, root: Path) -> enterprise_sync_state.EnterpriseSyncState:
    """Repair the recorded state when git reality disagrees — git wins, every poll.

    The state file is a cache of intent, and it drifts whenever branches are
    switched, merged, or deleted outside the save/submit flow. Handling a stale
    record as truth mis-dispatches the state machine, so each poll re-grounds it:
    adopt the branch that is actually checked out, finish an externally completed
    merge, or fall back to SYNCED when the recorded branch no longer exists.
    """
    state = enterprise_sync_state.load(root)
    rc, out, _ = await sync._git(root, "rev-parse", "--abbrev-ref", "HEAD")
    head = out.strip()
    if rc != 0 or head == "HEAD":  # unreadable or detached HEAD: nothing safe to repair
        return state

    if state.is_synced():
        if head == "main":
            return state
        adopted = enterprise_sync_state.EnterpriseSyncState(status="accumulating", branch=head)
        enterprise_sync_state.save(root, adopted)
        logger.warning("enterprise checkout is on %s with no recorded state — adopted as accumulating", head)
        return adopted

    if head == state.branch:
        return state

    if head != "main":  # on a different working branch than recorded: adopt it
        adopted = enterprise_sync_state.EnterpriseSyncState(
            status=state.status,
            branch=head,
            branch_tip=state.branch_tip,
            pushed_at=state.pushed_at,
            commits_behind=state.commits_behind,
        )
        enterprise_sync_state.save(root, adopted)
        logger.warning("enterprise state recorded branch %s but %s is checked out — adopted", state.branch, head)
        return adopted

    branch = state.branch
    branch_exists = (
        branch is not None
        and (await sync._git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"))[0] == 0
    )
    if branch is None or not branch_exists:
        enterprise_sync_state.clear(root)
        logger.warning("enterprise state recorded missing branch %s — reset to synced", branch)
        return enterprise_sync_state.EnterpriseSyncState()

    rc, out, _ = await sync._git(root, "diff", "origin/main", branch, "--", MODEL, DOCS, DIAGRAM_CATALOG)
    if rc == 0 and not out.strip():  # branch content already in origin/main: finish the cleanup
        await sync._git(root, "branch", "-D", branch)
        enterprise_sync_state.clear(root)
        logger.info("enterprise working branch %s was merged externally — cleaned up", branch)
        return enterprise_sync_state.EnterpriseSyncState()

    await sync._notify_sync_blocked(
        root,
        f"checkout is on main but working branch {state.branch} still holds unmerged work — "
        "switch back to the branch or resolve it manually",
    )
    return state


async def ent_on_main(sync: GitSyncManager, root: Path) -> None:
    from src.infrastructure.gui.routers.events import event_bus
    from src.infrastructure.workspace.mutation_gate import get_workspace_gate

    upstream = await sync._upstream_ref(root)
    if upstream is None:
        await sync._notify_sync_blocked(
            root,
            "no upstream tracking for the checked-out branch — the repository was not cloned "
            "from origin (likely an unrelated local init). Re-clone it so sync can fast-forward.",
        )
        return
    behind = await sync._rev_count(root, f"HEAD..{upstream}")
    ahead = await sync._rev_count(root, f"{upstream}..HEAD")
    if behind is None or ahead is None:
        await sync._notify_sync_blocked(root, f"could not compute sync state against {upstream}")
        return
    if ahead > 0:
        await sync._notify_sync_blocked(
            root,
            f"local branch is {ahead} commit(s) ahead of {upstream} — the enterprise mirror has "
            "diverged (unpublished commits). Investigate before sync can resume.",
        )
        return
    if behind == 0:
        sync._clear_block_reason(root)
        return
    if not await sync._is_clean(root):
        await sync._notify_sync_blocked(root, "local working tree has uncommitted changes — pull skipped")
        return

    sync._clear_block_reason(root)
    root_label = str(root)
    gate = get_workspace_gate()
    if gate.block_reason == "read_only":
        return

    rc, head_out, _ = await sync._git(root, "rev-parse", "HEAD")
    old_sha = head_out.strip()
    rc, branch_out, _ = await sync._git(root, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch_out.strip()
    rc, new_sha_out, _ = await sync._git(root, "rev-parse", upstream)
    new_sha = new_sha_out.strip()

    from src.infrastructure.git.git_sync_m4 import add_detached_worktree, run_m4_pull  # noqa: PLC0415

    await event_bus.publish({"type": "sync_pull_started", "repo": root_label, "behind": behind})
    try:
        with gate.blocking_writes("sync_in_progress"):
            worktree_path = await add_detached_worktree(sync._git, root, new_sha, timeout=_PULL_TIMEOUT_S)
            try:
                run_m4_pull(root, worktree_path, branch=branch, old_sha=old_sha, new_sha=new_sha, gate=gate)
            finally:
                await sync._git(root, "worktree", "remove", "--force", str(worktree_path))
            await sync._git(root, "reset", "--mixed", "HEAD")
    except Exception as exc:
        from src.infrastructure.gui.routers.events import event_bus as _bus  # noqa: PLC0415
        await _bus.publish({
            "type": "sync_pull_failed", "repo": root_label, "error": str(exc),
            "auto_unblock_in_seconds": int(_AUTO_UNBLOCK_S),
        })
        asyncio.create_task(sync._auto_unblock(root, _AUTO_UNBLOCK_S, False))
        return

    await event_bus.publish({"type": "sync_pull_completed", "repo": root_label, "commits_pulled": behind})
    await sync._notify_changed(root)


async def ent_accumulating(
    sync: GitSyncManager,
    root: Path,
    state: enterprise_sync_state.EnterpriseSyncState,
) -> None:
    from src.infrastructure.gui.routers.events import event_bus

    behind = await sync._count(root, "HEAD..origin/main")
    if behind != state.commits_behind:
        state.commits_behind = behind
        enterprise_sync_state.save(root, state)
    if behind == 0:
        return
    if await merged_without_submit(sync, root):
        await ent_switch_to_main(sync, root, state)
        return
    await event_bus.publish({"type": "sync_enterprise_diverged", "repo": str(root), "commits_behind": behind})


async def merged_without_submit(sync: GitSyncManager, root: Path) -> bool:
    """Detect a working branch that was pushed and merged without going through submit.

    The branch must carry real commits (a fresh branch trivially matches
    origin/main), the tree must be clean (switching to main must not touch
    unsaved work), and the branch content must be contained in origin/main.
    """
    ahead_of_main = await sync._rev_count(root, "main..HEAD")
    if not ahead_of_main:
        return False
    if not await sync._is_clean(root):
        return False
    return await promotion_merged(sync, root)


async def ent_pending(
    sync: GitSyncManager,
    root: Path,
    state: enterprise_sync_state.EnterpriseSyncState,
) -> None:
    behind = await sync._count(root, "HEAD..origin/main")
    if behind != state.commits_behind:
        state.commits_behind = behind
        enterprise_sync_state.save(root, state)

    if not await promotion_merged(sync, root):
        return
    await ent_switch_to_main(sync, root, state)


async def promotion_merged(sync: GitSyncManager, root: Path) -> bool:
    """Merged means: origin/main already contains the branch's model/docs/diagram content."""
    rc, out, _ = await sync._git(root, "diff", "origin/main", "HEAD", "--", MODEL, DOCS, DIAGRAM_CATALOG)
    return rc == 0 and not out.strip()


async def ent_switch_to_main(
    sync: GitSyncManager,
    root: Path,
    state: enterprise_sync_state.EnterpriseSyncState,
) -> None:
    from src.infrastructure.gui.routers.events import event_bus
    from src.infrastructure.workspace.write_block_manager import block_repo, unblock_repo

    root_label = str(root)
    block_repo(root)
    await event_bus.publish({"type": "sync_enterprise_merging", "repo": root_label})
    try:
        for git_args in [["checkout", "main"], ["pull", "--ff-only"]]:
            rc, _, err = await sync._git(root, *git_args, timeout=_PULL_TIMEOUT_S)
            if rc != 0:
                raise RuntimeError(err.strip() or "git error")
        if state.branch:
            await sync._git(root, "branch", "-D", state.branch)
        enterprise_sync_state.clear(root)
        unblock_repo(root)
        await event_bus.publish({"type": "sync_enterprise_merged", "repo": root_label})
        await sync._notify_changed(root)
    except Exception as exc:
        logger.exception("enterprise merge transition failed for %s", root)
        unblock_repo(root)
        await event_bus.publish({"type": "sync_enterprise_merge_failed", "repo": root_label, "error": str(exc)})
