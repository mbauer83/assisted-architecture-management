"""Regression: `arch-assurance status` must reflect real auto-unlock state.

The bug: cmd_status built a bare SQLCipher store and reported its (always-false) in-memory
lock state, so an activated store showed `unlocked: false` right after `unlock` succeeded.
The fix runs the same auto-unlock gate the backend uses against a throwaway probe.

Also covers the new `lock` command (clears the setup-confirmed gate).

The autouse `_in_memory_credential_store` fixture (tests/assurance/conftest.py) isolates the
keychain, so these never touch the real OS credential store.
"""

from __future__ import annotations

import argparse

import pytest

from src.config import settings
from src.infrastructure.cli import _assurance_commands as ac


@pytest.fixture(autouse=True)
def _force_sqlcipher_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storage_assurance_store_backend", lambda: "sqlcipher")
    monkeypatch.setattr(settings, "storage_assurance_signals_backend", lambda: "sqlcipher-colocated")
    monkeypatch.setattr(settings, "storage_assurance_archive_backend", lambda: "standard")
    monkeypatch.setattr(settings, "storage_assurance_max_classification", lambda: "TLP:RED")
    # Keep cmd_unlock/cmd_lock from blocking on a real backend reload POST.
    monkeypatch.setattr(ac, "_notify_backend_reload", lambda: None)


pytest.importorskip("sqlcipher3", reason="sqlcipher3 not installed")


def _init(db_path) -> None:  # type: ignore[no-untyped-def]
    from src.infrastructure.assurance.lifecycle import init_store

    init_store(db_path)


def test_status_reports_unlocked_after_activation(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    db = tmp_path / "store.db"
    _init(db)
    args = argparse.Namespace(db_path=str(db))

    assert ac.cmd_unlock(args) == 0
    capsys.readouterr()

    assert ac.cmd_status(args) == 0
    out = capsys.readouterr().out
    assert "unlocked: true" in out
    assert "status: unlocked" in out


def test_lock_disables_auto_unlock(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    db = tmp_path / "store.db"
    _init(db)
    args = argparse.Namespace(db_path=str(db))
    assert ac.cmd_unlock(args) == 0
    capsys.readouterr()

    assert ac.cmd_lock(args) == 0
    capsys.readouterr()

    assert ac.cmd_status(args) == 0
    out = capsys.readouterr().out
    assert "unlocked: false" in out
    assert "setup_confirmed: false" in out
    assert "locked_needs_activation" in out
