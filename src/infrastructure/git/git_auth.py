"""Git authentication: credential detection, interactive prompts, and askpass env setup.

Handles SSH key passphrases (via SSH_ASKPASS) and HTTPS username/password (via GIT_ASKPASS).
Credentials are never written to disk; they live in memory for the process lifetime.

CI / non-interactive overrides (skips prompting):
  ARCH_GIT_SSH_PASSWORD   — SSH key passphrase
  ARCH_GIT_HTTPS_USERNAME — HTTPS username
  ARCH_GIT_HTTPS_PASSWORD — HTTPS password or token
"""

from __future__ import annotations

import getpass
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitCredentials:
    ssh_passphrase: str | None = None
    https_username: str | None = None
    https_password: str | None = None

    @property
    def has_ssh(self) -> bool:
        return bool(self.ssh_passphrase)

    @property
    def has_https(self) -> bool:
        return bool(self.https_username or self.https_password)


# ---------------------------------------------------------------------------
# Protocol detection
# ---------------------------------------------------------------------------


def detect_remote_protocol(repo_path: Path) -> str | None:
    """Return 'ssh', 'https', or None (local / no remote configured)."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        return None
    return _protocol_from_url(result.stdout.strip())


def _protocol_from_url(url: str) -> str | None:
    if url.startswith(("git@", "ssh://", "git+ssh://")):
        return "ssh"
    if url.startswith(("https://", "http://")):
        return "https"
    return None


# ---------------------------------------------------------------------------
# Credential probing
# ---------------------------------------------------------------------------

_NO_ASKPASS = "/bin/false"
_AUTH_PHRASES = (
    "permission denied",
    "passphrase",
    "bad permissions",
    "authentication failed",
    "could not read username",
    "authorization failed",
    "403",
    "invalid username or password",
)


def probe_needs_credential(target: Path | str) -> bool:
    """Return True when git ls-remote fails specifically due to missing authentication.

    Accepts either a local repo path or a bare remote URL (for arch-init pre-clone probing).
    Returns False on network timeout or non-auth errors so we don't over-prompt.
    """
    if isinstance(target, Path):
        cmd = ["git", "ls-remote", "--quiet", "--exit-code", "origin", "HEAD"]
        cwd = target
    else:
        cmd = ["git", "ls-remote", "--quiet", "--exit-code", str(target), "HEAD"]
        cwd = Path.cwd()

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            env={
                **os.environ,
                "SSH_ASKPASS": _NO_ASKPASS,
                "SSH_ASKPASS_REQUIRE": "force",
                "GIT_ASKPASS": _NO_ASKPASS,
                "GIT_TERMINAL_PROMPT": "0",
            },
            timeout=8,
        )
    except subprocess.TimeoutExpired:
        return False

    if result.returncode == 0:
        return False
    combined = (result.stdout + result.stderr).decode(errors="replace").lower()
    return any(p in combined for p in _AUTH_PHRASES)


# ---------------------------------------------------------------------------
# Interactive collection
# ---------------------------------------------------------------------------


def collect_credentials(targets: list[Path | str]) -> GitCredentials | None:
    """Detect what credentials are needed and prompt interactively for any that are missing.

    Checks env-var overrides first; only prompts when on a TTY and probing confirms auth is needed.
    Returns None when no git remotes are found or no credentials are required.
    """
    ssh_targets = [t for t in targets if _target_protocol(t) == "ssh"]
    https_targets = [t for t in targets if _target_protocol(t) == "https"]

    if not ssh_targets and not https_targets:
        return None

    creds = GitCredentials()
    is_tty = sys.stdin.isatty()

    if ssh_targets:
        env_val = os.environ.get("ARCH_GIT_SSH_PASSWORD")
        if env_val:
            creds.ssh_passphrase = env_val
        elif is_tty and any(probe_needs_credential(t) for t in ssh_targets):
            creds.ssh_passphrase = getpass.getpass("SSH key passphrase: ")

    if https_targets:
        env_user = os.environ.get("ARCH_GIT_HTTPS_USERNAME")
        env_pass = os.environ.get("ARCH_GIT_HTTPS_PASSWORD")
        if env_user or env_pass:
            creds.https_username = env_user
            creds.https_password = env_pass
        elif is_tty and any(probe_needs_credential(t) for t in https_targets):
            creds.https_username = input("Git username: ")
            creds.https_password = getpass.getpass("Git password/token: ")

    return creds if (creds.has_ssh or creds.has_https) else None


def _target_protocol(target: Path | str) -> str | None:
    if isinstance(target, str):
        return _protocol_from_url(target)
    return detect_remote_protocol(target)


# ---------------------------------------------------------------------------
# Askpass env construction
# ---------------------------------------------------------------------------

_ASKPASS_SCRIPT = (
    "#!/bin/sh\n"
    'prompt="${1:-}"\n'
    'case "$prompt" in\n'
    '  Username*) printf \'%s\\n\' "${ARCH_GIT_HTTPS_USERNAME:-}" ;;\n'
    '  Password*) printf \'%s\\n\' "${ARCH_GIT_HTTPS_PASSWORD:-}" ;;\n'
    '  *)         printf \'%s\\n\' "${ARCH_GIT_SSH_PASSWORD:-}" ;;\n'
    "esac\n"
)


def create_askpass_script() -> Path:
    """Write the shared askpass helper to a tempfile and return its path."""
    fd, path_str = tempfile.mkstemp(prefix="arch-askpass-", suffix=".sh")
    path = Path(path_str)
    try:
        os.write(fd, _ASKPASS_SCRIPT.encode())
    finally:
        os.close(fd)
    path.chmod(0o700)
    return path


def build_git_env(credentials: GitCredentials, askpass: Path) -> dict[str, str]:
    """Return a git subprocess environment with askpass wired for SSH and HTTPS."""
    env = os.environ.copy()
    env["SSH_ASKPASS"] = str(askpass)
    env["SSH_ASKPASS_REQUIRE"] = "force"
    env["GIT_ASKPASS"] = str(askpass)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["ARCH_GIT_SSH_PASSWORD"] = credentials.ssh_passphrase or ""
    env["ARCH_GIT_HTTPS_USERNAME"] = credentials.https_username or ""
    env["ARCH_GIT_HTTPS_PASSWORD"] = credentials.https_password or ""
    return env


# ---------------------------------------------------------------------------
# Daemon credential handoff
# ---------------------------------------------------------------------------


def credentials_to_env_overrides(credentials: GitCredentials | None) -> dict[str, str]:
    """Return env-var overrides to set before spawning a daemon so it inherits credentials."""
    if credentials is None:
        return {}
    result: dict[str, str] = {}
    if credentials.ssh_passphrase:
        result["ARCH_GIT_SSH_PASSWORD"] = credentials.ssh_passphrase
    if credentials.https_username:
        result["ARCH_GIT_HTTPS_USERNAME"] = credentials.https_username
    if credentials.https_password:
        result["ARCH_GIT_HTTPS_PASSWORD"] = credentials.https_password
    return result
