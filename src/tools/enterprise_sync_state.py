"""Persistent state machine for the enterprise repository's working-branch lifecycle.

States
------
synced       — checkout is on main, clean; background sync pulls normally
accumulating — checkout is on a working branch; changes are being authored
pending      — working branch has been pushed; waiting for it to be merged into main

The state is persisted to .arch/enterprise-sync.json so it survives backend
restarts. All public functions are thread-safe.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

EnterpriseSyncStatus = Literal["synced", "accumulating", "pending"]
_STATE_FILENAME = ".arch/enterprise-sync.json"
_lock = threading.Lock()


@dataclass
class EnterpriseSyncState:
    status: EnterpriseSyncStatus = "synced"
    branch: str | None = None        # e.g. "arch/work-20260425-143012"
    branch_tip: str | None = None    # commit SHA recorded at push time
    pushed_at: str | None = None     # ISO-8601 timestamp of push
    commits_behind: int = 0          # commits on origin/main not yet on working branch

    def is_synced(self) -> bool:
        return self.status == "synced"

    def is_accumulating(self) -> bool:
        return self.status == "accumulating"

    def is_pending(self) -> bool:
        return self.status == "pending"


def _state_path(enterprise_root: Path) -> Path:
    return enterprise_root / _STATE_FILENAME


def load(enterprise_root: Path) -> EnterpriseSyncState:
    """Load persisted state; returns a fresh SYNCED state if missing or corrupt."""
    path = _state_path(enterprise_root)
    with _lock:
        if not path.exists():
            return EnterpriseSyncState()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return EnterpriseSyncState(
                status=data.get("status", "synced"),
                branch=data.get("branch"),
                branch_tip=data.get("branch_tip"),
                pushed_at=data.get("pushed_at"),
                commits_behind=int(data.get("commits_behind", 0)),
            )
        except (OSError, json.JSONDecodeError, ValueError):
            return EnterpriseSyncState()


def save(enterprise_root: Path, state: EnterpriseSyncState) -> None:
    path = _state_path(enterprise_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        path.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")


def clear(enterprise_root: Path) -> None:
    """Remove the state file, returning the enterprise repo to the SYNCED state."""
    with _lock:
        try:
            _state_path(enterprise_root).unlink()
        except FileNotFoundError:
            pass
