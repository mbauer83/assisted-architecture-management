"""Integration-test fixtures.

Installs the same transient in-memory credential backend used by the assurance
unit tests, so the SQLCipher store can be initialised and unlocked without an OS
keychain. Kept local to this package so integration tests are self-contained.
"""

from __future__ import annotations

import pytest

from src.infrastructure.assurance import _credential_store


class _MemoryBackend:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, account: str) -> str | None:
        return self._store.get(account)

    def set(self, account: str, value: str) -> None:
        self._store[account] = value

    def delete(self, account: str) -> None:
        self._store.pop(account, None)


@pytest.fixture(autouse=True)
def _in_memory_credential_store():
    """Replace the OS credential backend with an isolated in-memory store."""
    _credential_store._backend = _MemoryBackend()
    yield
    _credential_store.reset_backend()
