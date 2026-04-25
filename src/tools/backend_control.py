"""Backend lifecycle control: status, stop, and ensure-running."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from pathlib import Path

from src.tools.backend_state import (
    _process_exists,
    backend_log_path,
    backend_state_path,
    read_backend_state,
    remove_backend_state,
    write_backend_state,
)
from src.tools.backend_probe import (
    backend_start_command,
    backend_url,
    configured_backend_url,
    port_in_use,
    probe_backend,
    probe_backend_url,
    resolve_backend_port,
)
from src.tools.backend_process import (
    _read_process_state,
    backend_process_diagnostics,
    find_arch_backend_instance_for_port,
    find_arch_backend_instances,
)


logger = logging.getLogger(__name__)


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


def _instance_status(instance: dict[str, object], port: int, log_path: object) -> dict[str, object]:
    """Build a status dict for an untracked arch-backend instance."""
    process_state = instance.get("process_state")
    pid = int(instance["pid"])
    base = {
        "pid": pid, "port": port, "process_state": process_state,
        "stdin": instance.get("stdin"), "stdout": instance.get("stdout"),
        "stderr": instance.get("stderr"), "log_path": str(log_path),
    }
    if process_state in {"T", "t"}:
        logger.warning("arch-backend pid %s is stopped/suspended while still holding port %s", pid, port)
        return {"running": False, "reason": "stopped_backend", **base}
    if not probe_backend(port):
        logger.warning("arch-backend pid %s matched port %s but backend probe failed", pid, port)
        return {"running": False, "reason": "unhealthy_backend", **base}
    logger.info("arch-backend pid %s is healthy on port %s without state file", pid, port)
    return {"running": True, "reason": "ok_untracked", **base}


def backend_status(*, cwd: Path | None = None, port: int | None = None) -> dict[str, object]:
    resolved_port = resolve_backend_port(start=cwd, explicit_port=port)
    logger.info("Evaluating backend status for port %s (cwd=%s)", resolved_port, cwd or Path.cwd())
    log_path = backend_log_path(cwd)
    state = read_backend_state(cwd)
    if state is None:
        instance = find_arch_backend_instance_for_port(resolved_port)
        if instance is not None:
            return _instance_status(instance, resolved_port, log_path)
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


def _stop_pid(
    pid: int, *, cwd: Path | None = None, timeout_s: float = 5.0, port: int | None = None
) -> dict[str, object]:
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
        # Prefer the process that owns the listening socket; launcher wrappers
        # (e.g. ``uv run``) may share the declared port but not the socket.
        socket_owners = [m for m in matches if resolved_port in list(m.get("ports") or [])]
        if len(socket_owners) == 1:
            instance = socket_owners[0]
            logger.info(
                "Resolved multiple port matches to socket owner pid=%s for port=%s",
                instance["pid"], resolved_port,
            )
            result = _stop_pid(int(instance["pid"]), cwd=cwd, timeout_s=timeout_s, port=resolved_port)
            # Terminate any declarants that claimed the port but don't own the socket (e.g. launcher wrappers).
            for m in matches:
                leftover_pid = int(m["pid"])
                if leftover_pid == int(instance["pid"]):
                    continue
                logger.info(
                    "Terminating leftover arch-backend declarant pid=%s for port=%s",
                    leftover_pid,
                    resolved_port,
                )
                try:
                    os.kill(leftover_pid, signal.SIGTERM)
                except ProcessLookupError:
                    continue
                wait_deadline = time.monotonic() + min(timeout_s, 3.0)
                while time.monotonic() < wait_deadline:
                    if not _process_exists(leftover_pid):
                        break
                    time.sleep(0.1)
            return result
        # Genuinely multiple backend instances on the same port — stop all.
        pids = [int(m["pid"]) for m in (socket_owners or matches)]
        logger.warning("Stopping all %d arch-backend instances on port %s: %s", len(pids), resolved_port, pids)
        stopped_pids: list[int] = []
        for pid in pids:
            r = _stop_pid(pid, cwd=cwd, timeout_s=timeout_s, port=resolved_port)
            if r.get("stopped"):
                stopped_pids.append(pid)
        if stopped_pids:
            return {"stopped": True, "pid": stopped_pids[0], "pids": stopped_pids, "port": resolved_port}
        return {"stopped": False, "reason": "multiple_matching", "port": resolved_port, "pids": pids}

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
