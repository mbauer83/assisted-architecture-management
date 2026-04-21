"""Helpers for the unified backend process and stdio bridge."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import shutil
import importlib.util
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from src.tools.workspace_init import load_init_state


BACKEND_STATE_FILENAME = "backend.pid"
BACKEND_LOG_FILENAME = "backend.log"


def workspace_root(start: Path | None = None) -> Path | None:
    state = load_init_state(start)
    if state and state.get("workspace_root"):
        return Path(str(state["workspace_root"])).resolve()
    return None


def _state_dir(start: Path | None = None) -> Path:
    env_dir = os.getenv("ARCH_BACKEND_STATE_DIR", "").strip()
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    root = workspace_root(start)
    if root is not None:
        return root / ".arch"

    base = (start or Path.cwd()).resolve()
    if base.is_file():
        base = base.parent
    return base / ".arch"


def backend_state_path(start: Path | None = None) -> Path:
    return _state_dir(start) / BACKEND_STATE_FILENAME


def backend_log_path(start: Path | None = None) -> Path:
    return _state_dir(start) / BACKEND_LOG_FILENAME


def read_backend_state(start: Path | None = None) -> dict[str, object] | None:
    path = backend_state_path(start)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_backend_state(*, port: int, pid: int | None = None, start: Path | None = None) -> Path:
    path = backend_state_path(start)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"pid": pid or os.getpid(), "port": port}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def remove_backend_state(start: Path | None = None) -> None:
    path = backend_state_path(start)
    try:
        path.unlink()
    except FileNotFoundError:
        return


def backend_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def backend_start_command(*, port: int) -> list[str]:
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "--extra", "gui", "arch-backend", "--port", str(port)]

    if importlib.util.find_spec("fastapi") and importlib.util.find_spec("uvicorn"):
        return [sys.executable, "-m", "src.tools.arch_backend", "--port", str(port)]

    return [sys.executable, "-m", "src.tools.arch_backend", "--port", str(port)]


def probe_backend_url(url: str, *, timeout_s: float = 1.0) -> bool:
    req = Request(f"{url.rstrip('/')}/api/stats", headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
            return 200 <= resp.status < 500
    except (URLError, TimeoutError, OSError, ValueError):
        return False


def probe_backend(port: int, *, timeout_s: float = 1.0) -> bool:
    return probe_backend_url(backend_url(port), timeout_s=timeout_s)


def port_in_use(*, host: str = "127.0.0.1", port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def configured_backend_url() -> str | None:
    raw = os.getenv("ARCH_MCP_BACKEND_URL", "").strip()
    return raw.rstrip("/") if raw else None


def ensure_backend_running(*, port: int = 8000, start_if_missing: bool = True, cwd: Path | None = None) -> int:
    state = read_backend_state(cwd)
    if state is not None:
        maybe_port = state.get("port")
        if isinstance(maybe_port, int) and probe_backend(maybe_port):
            return maybe_port

    external_url = configured_backend_url()
    if external_url:
        if probe_backend_url(external_url):
            return port
        raise RuntimeError(f"Configured external backend is not reachable: {external_url}")

    if not start_if_missing:
        raise RuntimeError("Unified backend is not running.")

    if cwd is None:
        cwd = Path.cwd()
    log_path = backend_log_path(cwd)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "ab") as log:
        subprocess.Popen(
            backend_start_command(port=port),
            cwd=str(cwd),
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        state = read_backend_state(cwd)
        effective_port = port
        if state is not None and isinstance(state.get("port"), int):
            effective_port = int(state["port"])
        if probe_backend(effective_port):
            return effective_port
        time.sleep(0.25)

    raise RuntimeError(f"Timed out waiting for unified backend on port {port}. See {log_path}.")


def backend_status(*, cwd: Path | None = None, port: int = 8000) -> dict[str, object]:
    state = read_backend_state(cwd)
    if state is None:
        if probe_backend(port):
            return {"running": False, "reason": "unmanaged_backend", "port": port}
        if port_in_use(port=port):
            return {"running": False, "reason": "port_in_use", "port": port}
        return {"running": False, "reason": "not_running"}

    pid = state.get("pid")
    port = state.get("port")
    if not isinstance(pid, int) or not isinstance(port, int):
        return {"running": False, "reason": "invalid_state"}

    healthy = probe_backend(port)
    return {
        "running": healthy,
        "reason": "ok" if healthy else "unhealthy",
        "pid": pid,
        "port": port,
    }


def stop_backend(*, cwd: Path | None = None, timeout_s: float = 5.0) -> dict[str, object]:
    state = read_backend_state(cwd)
    if state is None:
        return {"stopped": False, "reason": "not_running"}

    pid = state.get("pid")
    port = state.get("port")
    if not isinstance(pid, int):
        remove_backend_state(cwd)
        return {"stopped": False, "reason": "invalid_state"}

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        remove_backend_state(cwd)
        return {"stopped": False, "reason": "stale_pid", "pid": pid}

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            remove_backend_state(cwd)
            return {"stopped": True, "pid": pid, "port": port}
        time.sleep(0.1)

    return {"stopped": False, "reason": "timeout", "pid": pid, "port": port}
