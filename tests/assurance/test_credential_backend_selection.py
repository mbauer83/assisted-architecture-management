"""Regression: credential backend selection for headless / CI environments.

On a CI runner the SecretService keyring backend imports cleanly but crashes at runtime when
``DBUS_SESSION_BUS_ADDRESS`` is unset. An explicit ``ARCH_ASSURANCE_MASTER_PASSWORD`` is the
headless escape hatch and must select the Fernet vault first, regardless of platform; and a
Linux host without a session bus must never be routed to SecretService.
"""

from __future__ import annotations

import pytest

from src.infrastructure.assurance import _credential_store as cs


def test_master_password_env_selects_fernet_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cs, "_backend", None)
    monkeypatch.setenv(cs._MASTER_PW_ENV, "ci-secret")
    monkeypatch.setattr(cs.platform, "system", lambda: "Linux")
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)

    backend = cs._get_backend()

    assert isinstance(backend, cs._FernetVault)


def test_linux_without_session_bus_is_not_routed_to_secretservice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cs, "_backend", None)
    monkeypatch.delenv(cs._MASTER_PW_ENV, raising=False)
    monkeypatch.setattr(cs.platform, "system", lambda: "Linux")
    monkeypatch.setattr(cs, "_is_wsl2", lambda: False)
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)

    # No usable backend rather than a runtime D-Bus crash.
    with pytest.raises(RuntimeError):
        cs._get_backend()
