"""Helpers for the unified backend process and stdio bridge."""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import pathlib
import signal
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from src.common.settings import backend_log_path as configured_backend_log_path
from src.common.settings import backend_port as global_backend_port
from src.tools.workspace_init import load_init_state


BACKEND_STATE_FILENAME = "backend.pid"
BACKEND_LOG_FILENAME = "backend.log"
logger = logging.getLogger(__name__)
_PROC_DIR = Path("/proc")


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
    configured = Path(configured_backend_log_path()).expanduser()
    if configured.is_absolute():
        return configured

    root = workspace_root(start)
    if root is not None:
        return (root / configured).resolve()

    base = (start or Path.cwd()).resolve()
    if base.is_file():
        base = base.parent
    return (base / configured).resolve()


def read_backend_state(start: Path | None = None) -> dict[str, object] | None:
    path = backend_state_path(start)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


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


def resolve_backend_port(*, start: Path | None = None, explicit_port: int | None = None) -> int:
    if explicit_port is not None:
        logger.info("Using explicit backend port %s", explicit_port)
        return explicit_port

    resolved = global_backend_port()
    logger.info("Using backend port %s from config/settings.yaml", resolved)
    return resolved


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
            logger.debug("Backend probe to %s returned HTTP %s", url, resp.status)
            return 200 <= resp.status < 500
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        logger.debug("Backend probe to %s failed: %s", url, exc)
        return False


def probe_backend(port: int, *, timeout_s: float = 1.0) -> bool:
    return probe_backend_url(backend_url(port), timeout_s=timeout_s)


def port_in_use(*, host: str = "127.0.0.1", port: int) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except OSError as exc:
        logger.warning("Unable to open socket while checking port %s: %s", port, exc)
        return False
    try:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0
    except OSError as exc:
        logger.warning("Unable to probe port %s on host %s: %s", port, host, exc)
        return False
    finally:
        sock.close()


def configured_backend_url() -> str | None:
    raw = os.getenv("ARCH_MCP_BACKEND_URL", "").strip()
    return raw.rstrip("/") if raw else None


def _read_cmdline(pid: int) -> list[str]:
    try:
        raw = (_PROC_DIR / str(pid) / "cmdline").read_bytes()
    except OSError:
        return []
    return [part for part in raw.decode("utf-8", errors="replace").split("\x00") if part]


def _read_process_state(pid: int) -> str | None:
    try:
        stat = (_PROC_DIR / str(pid) / "stat").read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return stat.rsplit(") ", 1)[1].split(" ", 1)[0]
    except IndexError:
        return None


def _parse_cli_port(argv: list[str]) -> int | None:
    for idx, arg in enumerate(argv):
        if arg == "--port" and idx + 1 < len(argv):
            try:
                return int(argv[idx + 1])
            except ValueError:
                return None
    return None


def _matches_arch_backend_process(argv: list[str]) -> bool:
    if not argv:
        return False
    argv0 = pathlib.PurePath(argv[0]).name
    if argv0 == "arch-backend":
        return True
    if argv0.startswith("python") and len(argv) >= 3 and argv[1] == "-m" and argv[2] == "src.tools.arch_backend":
        return True
    normalized = {pathlib.PurePath(arg).name for arg in argv}
    if "arch-backend" in normalized:
        return True
    if any(arg.endswith("src/tools/arch_backend.py") for arg in argv):
        return True
    return "src.tools.arch_backend" in argv


def _list_listening_socket_inodes() -> dict[str, int]:
    inode_to_port: dict[str, int] = {}
    for proc_path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(proc_path).read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 10 or parts[3] != "0A":
                continue
            local_address = parts[1]
            inode = parts[9]
            try:
                port = int(local_address.split(":")[1], 16)
            except (IndexError, ValueError):
                continue
            inode_to_port[inode] = port
    return inode_to_port


def _ports_for_pid(pid: int, inode_to_port: dict[str, int]) -> list[int]:
    fd_dir = _PROC_DIR / str(pid) / "fd"
    ports: set[int] = set()
    try:
        for fd_path in fd_dir.iterdir():
            try:
                target = os.readlink(fd_path)
            except OSError:
                continue
            if not target.startswith("socket:[") or not target.endswith("]"):
                continue
            inode = target[8:-1]
            port = inode_to_port.get(inode)
            if port is not None:
                ports.add(port)
    except OSError:
        return []
    return sorted(ports)


def _fd_target(pid: int, fd: int) -> str | None:
    try:
        return os.readlink(_PROC_DIR / str(pid) / "fd" / str(fd))
    except OSError:
        return None


def backend_process_diagnostics(pid: int) -> dict[str, object]:
    inode_to_port = _list_listening_socket_inodes()
    return {
        "process_state": _read_process_state(pid),
        "ports": _ports_for_pid(pid, inode_to_port),
        "stdin": _fd_target(pid, 0),
        "stdout": _fd_target(pid, 1),
        "stderr": _fd_target(pid, 2),
        "argv": _read_cmdline(pid),
    }


def find_arch_backend_instances() -> list[dict[str, object]]:
    inode_to_port = _list_listening_socket_inodes()
    candidates: list[dict[str, object]] = []
    current_pid = os.getpid()
    try:
        proc_entries = [entry for entry in _PROC_DIR.iterdir() if entry.name.isdigit()]
    except OSError:
        return []
    proc_entries.sort(key=lambda path: int(path.name))
    for entry in proc_entries:
        pid = int(entry.name)
        if pid == current_pid:
            continue
        argv = _read_cmdline(pid)
        if not _matches_arch_backend_process(argv):
            continue
        candidates.append(
            {
                "pid": pid,
                "argv": argv,
                "ports": _ports_for_pid(pid, inode_to_port),
                "declared_port": _parse_cli_port(argv),
                "process_state": _read_process_state(pid),
                "stdin": _fd_target(pid, 0),
                "stdout": _fd_target(pid, 1),
                "stderr": _fd_target(pid, 2),
            }
        )
    logger.debug(
        "Detected %d arch-backend process candidate(s): %s",
        len(candidates),
        [
            {
                "pid": int(candidate["pid"]),
                "ports": list(candidate.get("ports") or []),
                "declared_port": candidate.get("declared_port"),
                "process_state": candidate.get("process_state"),
            }
            for candidate in candidates
        ],
    )
    return candidates


def find_arch_backend_instance_for_port(port: int) -> dict[str, object] | None:
    matches = [
        instance
        for instance in find_arch_backend_instances()
        if port in list(instance.get("ports") or [])
        or instance.get("declared_port") == port
    ]
    if len(matches) == 1:
        logger.info(
            "Matched arch-backend pid %s for port %s (state=%s, ports=%s, declared_port=%s)",
            matches[0].get("pid"),
            port,
            matches[0].get("process_state"),
            matches[0].get("ports"),
            matches[0].get("declared_port"),
        )
        return matches[0]
    if len(matches) > 1:
        logger.warning("Multiple arch-backend candidates matched port %s: %s", port, [m.get("pid") for m in matches])
    else:
        logger.info("No arch-backend process candidate matched port %s", port)
    return None


def ensure_backend_running(*, port: int | None = None, start_if_missing: bool = True, cwd: Path | None = None) -> int:
    resolved_port = resolve_backend_port(start=cwd, explicit_port=port)
    state = read_backend_state(cwd)
    if state is not None:
        maybe_port = state.get("port")
        if isinstance(maybe_port, int) and probe_backend(maybe_port):
            logger.info("Reusing healthy backend on port %s", maybe_port)
            return maybe_port
        pid = state.get("pid")
        if isinstance(pid, int) and not _process_exists(pid):
            logger.warning("Removing stale backend state for pid %s", pid)
            remove_backend_state(cwd)

    external_url = configured_backend_url()
    if external_url:
        if probe_backend_url(external_url):
            logger.info("Using externally configured backend at %s", external_url)
            return resolved_port
        raise RuntimeError(f"Configured external backend is not reachable: {external_url}")

    if not start_if_missing:
        raise RuntimeError("Unified backend is not running.")

    if cwd is None:
        cwd = Path.cwd()
    log_path = backend_log_path(cwd)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "ab") as log:
        command = backend_start_command(port=resolved_port)
        logger.info("Starting backend with command: %s", " ".join(command))
        subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        state = read_backend_state(cwd)
        effective_port = resolved_port
        if state is not None and isinstance(state.get("port"), int):
            effective_port = int(state["port"])
        if probe_backend(effective_port):
            logger.info("Backend became healthy on port %s", effective_port)
            return effective_port
        time.sleep(0.25)

    raise RuntimeError(f"Timed out waiting for unified backend on port {resolved_port}. See {log_path}.")


def backend_status(*, cwd: Path | None = None, port: int | None = None) -> dict[str, object]:
    resolved_port = resolve_backend_port(start=cwd, explicit_port=port)
    logger.info("Evaluating backend status for port %s (cwd=%s)", resolved_port, cwd or Path.cwd())
    log_path = backend_log_path(cwd)
    state = read_backend_state(cwd)
    if state is None:
        instance = find_arch_backend_instance_for_port(resolved_port)
        if instance is not None:
            process_state = instance.get("process_state")
            if process_state in {"T", "t"}:
                logger.warning(
                    "arch-backend pid %s is stopped/suspended while still holding port %s",
                    instance.get("pid"),
                    resolved_port,
                )
                return {
                    "running": False,
                    "reason": "stopped_backend",
                    "pid": int(instance["pid"]),
                    "port": resolved_port,
                    "process_state": process_state,
                    "stdin": instance.get("stdin"),
                    "stdout": instance.get("stdout"),
                    "stderr": instance.get("stderr"),
                    "log_path": str(log_path),
                }
            if not probe_backend(resolved_port):
                logger.warning(
                    "arch-backend pid %s matched port %s but backend probe failed",
                    instance.get("pid"),
                    resolved_port,
                )
                return {
                    "running": False,
                    "reason": "unhealthy_backend",
                    "pid": int(instance["pid"]),
                    "port": resolved_port,
                    "process_state": process_state,
                    "stdin": instance.get("stdin"),
                    "stdout": instance.get("stdout"),
                    "stderr": instance.get("stderr"),
                    "log_path": str(log_path),
                }
            logger.info("arch-backend pid %s is healthy on port %s without state file", instance.get("pid"), resolved_port)
            return {
                "running": True,
                "reason": "ok_untracked",
                "pid": int(instance["pid"]),
                "port": resolved_port,
                "process_state": process_state,
                "stdin": instance.get("stdin"),
                "stdout": instance.get("stdout"),
                "stderr": instance.get("stderr"),
                "log_path": str(log_path),
            }
        if probe_backend(resolved_port):
            logger.warning("Port %s responds to backend probe but is not identified as arch-backend", resolved_port)
            return {"running": False, "reason": "unmanaged_backend", "port": resolved_port}
        if port_in_use(port=resolved_port):
            logger.warning("Port %s is in use by a non-backend or unidentifiable process", resolved_port)
            return {"running": False, "reason": "port_in_use", "port": resolved_port}
        logger.info("No backend is running on port %s", resolved_port)
        return {"running": False, "reason": "not_running"}

    pid = state.get("pid")
    port = state.get("port")
    if not isinstance(pid, int) or not isinstance(port, int):
        logger.warning("Removing invalid backend state: %s", state)
        remove_backend_state(cwd)
        return {"running": False, "reason": "invalid_state"}
    if not _process_exists(pid):
        logger.warning("Removing stale backend state for missing pid %s", pid)
        remove_backend_state(cwd)
        return {"running": False, "reason": "stale_pid", "pid": pid, "port": port}

    process_state = _read_process_state(pid)
    diagnostics = backend_process_diagnostics(pid)
    if process_state in {"T", "t"}:
        logger.warning("Tracked arch-backend pid %s is stopped/suspended on port %s", pid, port)
        return {
            "running": False,
            "reason": "stopped_backend",
            "pid": pid,
            "port": port,
            "process_state": process_state,
            "stdin": diagnostics.get("stdin"),
            "stdout": diagnostics.get("stdout"),
            "stderr": diagnostics.get("stderr"),
            "log_path": str(log_path),
        }

    healthy = probe_backend(port)
    logger.info("Backend state file points to pid=%s port=%s healthy=%s", pid, port, healthy)
    return {
        "running": healthy,
        "reason": "ok" if healthy else "unhealthy",
        "pid": pid,
        "port": port,
        "process_state": process_state,
        "stdin": diagnostics.get("stdin"),
        "stdout": diagnostics.get("stdout"),
        "stderr": diagnostics.get("stderr"),
        "log_path": str(log_path),
    }


def _stop_pid(pid: int, *, cwd: Path | None = None, timeout_s: float = 5.0, port: int | None = None) -> dict[str, object]:
    tracked_state = read_backend_state(cwd)
    tracked_pid = tracked_state.get("pid") if isinstance(tracked_state, dict) else None
    process_state = _read_process_state(pid)
    logger.info(
        "Attempting to stop pid=%s on port=%s (tracked_pid=%s, cwd=%s, timeout_s=%.1f, process_state=%s)",
        pid,
        port,
        tracked_pid,
        cwd or Path.cwd(),
        timeout_s,
        process_state,
    )
    if process_state in {"T", "t"}:
        try:
            os.kill(pid, signal.SIGCONT)
            logger.info("Sent SIGCONT to stopped pid %s before termination", pid)
        except ProcessLookupError:
            logger.warning("SIGCONT target pid %s does not exist", pid)
            if tracked_pid == pid:
                remove_backend_state(cwd)
            return {"stopped": False, "reason": "stale_pid", "pid": pid}
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        logger.warning("SIGTERM target pid %s does not exist", pid)
        if tracked_pid == pid:
            remove_backend_state(cwd)
        return {"stopped": False, "reason": "stale_pid", "pid": pid}

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _process_exists(pid):
            logger.info("pid %s exited after SIGTERM", pid)
            if tracked_pid == pid:
                remove_backend_state(cwd)
            return {"stopped": True, "pid": pid, "port": port}
        time.sleep(0.1)

    logger.warning("Timed out waiting for pid %s to exit after SIGTERM; escalating to SIGKILL", pid)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        logger.info("pid %s exited before SIGKILL was delivered", pid)
        if tracked_pid == pid:
            remove_backend_state(cwd)
        return {"stopped": True, "pid": pid, "port": port}

    kill_deadline = time.monotonic() + min(timeout_s, 2.0)
    while time.monotonic() < kill_deadline:
        if not _process_exists(pid):
            logger.info("pid %s exited after SIGKILL", pid)
            if tracked_pid == pid:
                remove_backend_state(cwd)
            return {"stopped": True, "pid": pid, "port": port}
        time.sleep(0.05)

    logger.error("Timed out waiting for pid %s to exit even after SIGKILL", pid)
    return {"stopped": False, "reason": "timeout", "pid": pid, "port": port}


def stop_backend(*, cwd: Path | None = None, timeout_s: float = 5.0, port: int | None = None) -> dict[str, object]:
    resolved_port = resolve_backend_port(start=cwd, explicit_port=port)
    logger.info("Stop request for backend on port %s (cwd=%s)", resolved_port, cwd or Path.cwd())
    state = read_backend_state(cwd)
    if state is not None:
        pid = state.get("pid")
        state_port = state.get("port")
        logger.info("Existing backend state for stop request: %s", state)
        if not isinstance(pid, int) or not isinstance(state_port, int):
            remove_backend_state(cwd)
            return {"stopped": False, "reason": "invalid_state"}
        if state_port == resolved_port or not _process_exists(pid):
            return _stop_pid(pid, cwd=cwd, timeout_s=timeout_s, port=state_port)

    instances = find_arch_backend_instances()
    matches = [
        instance for instance in instances
        if resolved_port in list(instance.get("ports") or [])
        or instance.get("declared_port") == resolved_port
    ]
    if len(matches) == 1:
        instance = matches[0]
        logger.info("Stopping matched arch-backend instance pid=%s for port=%s", instance["pid"], resolved_port)
        return _stop_pid(
            int(instance["pid"]),
            cwd=cwd,
            timeout_s=timeout_s,
            port=resolved_port,
        )
    if len(matches) > 1:
        return {
            "stopped": False,
            "reason": "multiple_matching",
            "port": resolved_port,
            "pids": [int(instance["pid"]) for instance in matches],
        }

    if len(instances) == 1:
        instance = instances[0]
        ports = list(instance.get("ports") or [])
        other_port = ports[0] if ports else instance.get("declared_port")
        logger.warning(
            "Only one arch-backend instance exists, but it is on port %s instead of requested port %s (pid=%s)",
            other_port,
            resolved_port,
            instance["pid"],
        )
        return {
            "stopped": False,
            "reason": "single_other_port",
            "pid": int(instance["pid"]),
            "port": other_port,
            "expected_port": resolved_port,
        }

    if state is None:
        logger.info("Stop request found no backend state and no matching arch-backend process")
        return {"stopped": False, "reason": "not_running"}

    pid = state.get("pid")
    if isinstance(pid, int):
        remove_backend_state(cwd)
        return {"stopped": False, "reason": "stale_pid", "pid": pid}
    return {"stopped": False, "reason": "not_running"}
