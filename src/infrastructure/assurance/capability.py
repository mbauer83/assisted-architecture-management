"""Confidential-store capability sentinel.

Adding this sentinel to `registered_names` before the assurance ontology module
is evaluated allows `is_module_enabled` to satisfy
`requires: ["confidential_store"]` — a pure name-based capability signal.

The sentinel's `enabled` property probes whether the store key exists in the OS
keychain and the DB file is present.  If either is missing the capability is
unavailable and the assurance module will not be registered (fail-closed).
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SERVICE_NAME = "arch-assurance"
_KEY_ACCOUNT = "db-encryption-key"


def _store_available(db_path: Path) -> bool:
    """Return True if the keychain key exists and the DB file is present."""
    try:
        import keyring  # type: ignore[import-untyped]

        key = keyring.get_password(_SERVICE_NAME, _KEY_ACCOUNT)
        if not key:
            return False
    except Exception:  # noqa: BLE001
        return False
    return db_path.exists()


class _ConfidentialStoreCapability:
    """Synthetic 'module' that satisfies the confidential_store capability dep.

    Not an OntologyModule — never registered as one. Only its `.name` and
    `.enabled` are consumed by `is_module_enabled` during bootstrap.
    """

    name = "confidential_store"
    requires: list[str] = []

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._available: bool | None = None

    @property
    def enabled(self) -> bool:
        if self._available is None:
            self._available = _store_available(self._db_path)
            if not self._available:
                logger.info(
                    "confidential_store: unavailable (key or DB missing at %s). "
                    "Run `arch-assurance init` to enable.",
                    self._db_path,
                )
        return self._available


def make_capability(db_path: Path) -> _ConfidentialStoreCapability:
    return _ConfidentialStoreCapability(db_path)
