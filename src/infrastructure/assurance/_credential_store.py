"""Secure credential storage for arch-assurance encryption keys.

Backend selection order:
  1. macOS Keychain        — macOS; always available and secure
  2. Windows DPAPI bridge  — WSL2; powershell.exe Export-Clixml (DPAPI-encrypted,
                             tied to Windows user login; cannot be decrypted by any
                             other user or on any other machine)
  3. SecretService D-Bus   — native Linux with a running desktop session
  4. Fernet-encrypted vault — headless Linux / CI; requires ARCH_ASSURANCE_MASTER_PASSWORD
                             env var; AES-128-CBC via PBKDF2-derived key

Fails loudly with actionable instructions if no secure backend is available.
Never falls back to plaintext storage.
"""

from __future__ import annotations

import logging
import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


@runtime_checkable
class _Backend(Protocol):
    def get(self, account: str) -> str | None: ...
    def set(self, account: str, value: str) -> None: ...
    def delete(self, account: str) -> None: ...

_SERVICE = "arch-assurance"
_MASTER_PW_ENV = "ARCH_ASSURANCE_MASTER_PASSWORD"
_CONFIG_DIR = Path.home() / ".config" / "arch-assurance"

_NO_BACKEND_MSG = (
    "No secure credential backend is available for arch-assurance.\n\n"
    "  macOS:                    automatic (Keychain)\n"
    "  WSL2:                     automatic (Windows DPAPI); ensure Windows\n"
    "                            PowerShell interop is enabled\n"
    "  Linux desktop (D-Bus):    automatic (SecretService / gnome-keyring)\n"
    "  Headless Linux / CI:      set ARCH_ASSURANCE_MASTER_PASSWORD env var\n"
    "                            (add to ~/.bashrc or systemd unit)\n"
)


# ── keyring-backed (macOS Keychain + SecretService) ───────────────────────────


class _KeyringBackend:
    """Thin wrapper around a specific `keyring` backend class."""

    def __init__(self, backend_module: str, backend_class: str) -> None:
        import importlib  # noqa: PLC0415

        cls = getattr(importlib.import_module(backend_module), backend_class)
        self._kr = cls()

    def get(self, account: str) -> str | None:
        return self._kr.get_password(_SERVICE, account)

    def set(self, account: str, value: str) -> None:
        self._kr.set_password(_SERVICE, account, value)

    def delete(self, account: str) -> None:
        try:
            self._kr.delete_password(_SERVICE, account)
        except Exception:  # noqa: BLE001
            pass


# ── Windows DPAPI via PowerShell bridge (WSL2) ────────────────────────────────


class _DPAPIBackend:
    """Each credential stored as a DPAPI-encrypted PSCredential XML file.

    PowerShell Export-Clixml serialises PSCredential with the password
    encrypted by Windows DPAPI (user-and-machine-scoped). Files live on the
    WSL2 filesystem; wslpath converts them to Windows UNC paths for PowerShell.
    """

    _creds = _CONFIG_DIR / "creds"

    def _path(self, account: str) -> Path:
        return self._creds / f"{account.replace('-', '_')}.clixml"

    @staticmethod
    def _win(path: Path) -> str:
        import subprocess  # noqa: PLC0415
        return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()

    def get(self, account: str) -> str | None:
        import subprocess  # noqa: PLC0415
        p = self._path(account)
        if not p.exists():
            return None
        try:
            out = subprocess.check_output(
                ["powershell.exe", "-NoProfile", "-Command",
                 f"(Import-Clixml '{self._win(p)}').GetNetworkCredential().Password"],
                text=True, timeout=15,
            )
            return out.strip() or None
        except Exception:  # noqa: BLE001
            return None

    def set(self, account: str, value: str) -> None:
        import subprocess  # noqa: PLC0415
        self._creds.mkdir(parents=True, exist_ok=True)
        os.chmod(self._creds, 0o700)
        p = self._path(account)
        esc = value.replace("'", "''")
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             f"[PSCredential]::new('arch-assurance',"
             f"(ConvertTo-SecureString '{esc}' -AsPlainText -Force))"
             f" | Export-Clixml '{self._win(p)}'"],
            check=True, timeout=15, capture_output=True,
        )
        os.chmod(p, 0o600)

    def delete(self, account: str) -> None:
        p = self._path(account)
        if p.exists():
            p.unlink()


# ── Fernet-encrypted vault (headless Linux / CI) ──────────────────────────────


class _FernetVault:
    """All credentials in one Fernet-encrypted JSON file, key from PBKDF2."""

    _vault = _CONFIG_DIR / "vault.enc"
    _ITERATIONS = 480_000

    def __init__(self, master_password: str) -> None:
        self._pw = master_password

    def _fernet(self, salt: bytes) -> Fernet:
        import base64  # noqa: PLC0415

        from cryptography.fernet import Fernet  # noqa: PLC0415
        from cryptography.hazmat.primitives import hashes  # noqa: PLC0415
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  # noqa: PLC0415
        key = base64.urlsafe_b64encode(
            PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                       iterations=self._ITERATIONS).derive(self._pw.encode())
        )
        return Fernet(key)

    def _load(self) -> dict[str, str]:
        import base64  # noqa: PLC0415
        import json  # noqa: PLC0415

        if not self._vault.exists():
            return {}
        raw = json.loads(self._vault.read_text())
        return json.loads(
            self._fernet(base64.b64decode(raw["salt"])).decrypt(
                base64.b64decode(raw["data"])
            )
        )

    def _save(self, entries: dict[str, str]) -> None:
        import base64  # noqa: PLC0415
        import json  # noqa: PLC0415
        salt = os.urandom(16)
        data = self._fernet(salt).encrypt(json.dumps(entries).encode())
        self._vault.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self._vault.parent, 0o700)
        self._vault.write_text(json.dumps({
            "v": 1,
            "salt": base64.b64encode(salt).decode(),
            "data": base64.b64encode(data).decode(),
        }))
        os.chmod(self._vault, 0o600)

    def get(self, account: str) -> str | None:
        return self._load().get(account)

    def set(self, account: str, value: str) -> None:
        entries = self._load()
        entries[account] = value
        self._save(entries)

    def delete(self, account: str) -> None:
        entries = self._load()
        entries.pop(account, None)
        self._save(entries)


# ── Backend detection ──────────────────────────────────────────────────────────


def _is_wsl2() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def _powershell_accessible() -> bool:
    import subprocess  # noqa: PLC0415
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", "exit 0"],
            capture_output=True, timeout=5, check=True,
        )
        return True
    except Exception:  # noqa: BLE001
        return False


def _dbus_available() -> bool:
    import subprocess  # noqa: PLC0415
    try:
        return subprocess.run(
            ["dbus-send", "--session", "--print-reply", "--dest=org.freedesktop.DBus",
             "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames"],
            capture_output=True, timeout=2,
        ).returncode == 0
    except Exception:  # noqa: BLE001
        return False


_backend: _Backend | None = None


def _get_backend() -> _Backend:
    global _backend  # noqa: PLW0603
    if _backend is not None:
        return _backend

    if platform.system() == "Darwin":
        logger.debug("credential store: macOS Keychain")
        _backend = _KeyringBackend("keyring.backends.macOS", "Keyring")
    elif _is_wsl2() and _powershell_accessible():
        logger.debug("credential store: Windows DPAPI (WSL2)")
        _backend = _DPAPIBackend()
    elif platform.system() == "Linux" and _dbus_available():
        logger.debug("credential store: SecretService (D-Bus)")
        _backend = _KeyringBackend("keyring.backends.SecretService", "Keyring")
    elif pw := os.environ.get(_MASTER_PW_ENV):
        logger.debug("credential store: Fernet-encrypted vault (master password from env)")
        _backend = _FernetVault(pw)
    else:
        raise RuntimeError(_NO_BACKEND_MSG)

    return _backend


# ── Public API ─────────────────────────────────────────────────────────────────


def reset_backend() -> None:
    """Evict the cached backend (tests and after CLI backend-switch)."""
    global _backend  # noqa: PLW0603
    _backend = None


def get(account: str) -> str | None:
    return _get_backend().get(account)


def set_credential(account: str, value: str) -> None:
    _get_backend().set(account, value)


def delete(account: str) -> None:
    _get_backend().delete(account)
