"""Unified FastAPI + MCP backend entry point."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import uvicorn

from src.common.settings import backend_min_log_level
from src.tools import gui_server
from src.tools.arch_backend_app import _build_app
from src.tools.backend_control import backend_status, stop_backend
from src.tools.backend_probe import probe_backend, resolve_backend_port
from src.tools.backend_state import (
    backend_log_path,
    read_backend_state,
    remove_backend_state,
    write_backend_state,
)

logger = logging.getLogger(__name__)


def _print_stopped(result: dict) -> None:
    pids = result.get("pids")
    if isinstance(pids, list) and len(pids) > 1:
        print(f"stopped backend pids {', '.join(str(p) for p in pids)}")
    else:
        print(f"stopped backend pid {result.get('pid')}")


def _confirm_stop_other_instance(*, expected_port: int, pid: int, actual_port: object) -> bool:
    prompt = (
        f"Configured backend port is {expected_port}, but found one arch-backend instance "
        f"on port {actual_port} (pid {pid}). Stop it? [y/N] "
    )
    if not sys.stdin.isatty():
        print(
            (
                f"found one arch-backend instance on port {actual_port} "
                f"(pid {pid}), but the configured port is {expected_port}; "
                f"rerun interactively or pass --port {actual_port}"
            )
        )
        return False
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def _is_background_tty_job() -> bool:
    try:
        return sys.stderr.isatty() and os.tcgetpgrp(sys.stderr.fileno()) != os.getpgrp()
    except OSError:
        return False


def _redirect_stdio_to_backend_log(*, start: Path | None = None) -> Path:
    log_path = backend_log_path(start)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    null_fd = os.open(os.devnull, os.O_RDONLY)
    try:
        os.dup2(null_fd, sys.stdin.fileno())
        os.dup2(log_fd, sys.stdout.fileno())
        os.dup2(log_fd, sys.stderr.fileno())
    finally:
        if log_fd > 2:
            os.close(log_fd)
        if null_fd > 2:
            os.close(null_fd)
    return log_path


def _status_detail_lines(result: dict[str, object]) -> list[str]:
    lines: list[str] = []
    if result.get("process_state"):
        lines.append(f"process state: {result.get('process_state')}")
    stdio = [
        f"stdin={result.get('stdin')}" if result.get("stdin") is not None else None,
        f"stdout={result.get('stdout')}" if result.get("stdout") is not None else None,
        f"stderr={result.get('stderr')}" if result.get("stderr") is not None else None,
    ]
    stdio_text = " ".join(part for part in stdio if part)
    if stdio_text:
        lines.append(f"stdio: {stdio_text}")
    if result.get("log_path"):
        lines.append(f"log: {result.get('log_path')}")
    return lines


def _print_status_details(result: dict[str, object]) -> None:
    for line in _status_detail_lines(result):
        print(f"  {line}")


def _daemon_argv(argv: list[str] | None) -> list[str]:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    return [arg for arg in raw_args if arg not in ("--daemon", "--restart", "--stop")]


def _start_daemon(*, argv: list[str] | None, log_path: Path) -> int:
    command = [sys.argv[0], *_daemon_argv(argv)]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(Path.cwd()),
        )
    return int(proc.pid)


def _run_status(resolved_port: int) -> None:
    result = backend_status(port=resolved_port)
    reason = result.get("reason")
    if result.get("running"):
        print(f"backend is running on port {result.get('port')} (pid {result.get('pid')})")
        _print_status_details(result)
    elif reason == "unmanaged_backend":
        print(
            (
                "backend is responding on port "
                f"{result.get('port')} but is not managed by this workspace"
            )
        )
        _print_status_details(result)
    elif reason == "port_in_use":
        print(f"port {result.get('port')} is in use by another process")
        _print_status_details(result)
    elif reason == "not_running":
        print("backend is not running")
    elif reason == "stopped_backend":
        print(f"backend process pid {result.get('pid')} is stopped on port {result.get('port')}")
        _print_status_details(result)
    elif reason == "unhealthy_backend":
        print(
            (
                f"backend process pid {result.get('pid')} is not responding "
                f"on port {result.get('port')}"
            )
        )
        _print_status_details(result)
    elif reason == "stale_pid":
        print(f"removed stale backend pid {result.get('pid')}")
    elif reason == "invalid_state":
        print("backend state is invalid")
    else:
        print(f"backend is not healthy on port {result.get('port')} (pid {result.get('pid')})")
        _print_status_details(result)


def _run_stop(args: argparse.Namespace, resolved_port: int) -> None:
    result = stop_backend(port=resolved_port)
    reason = result.get("reason")
    if result.get("stopped"):
        _print_stopped(result)
    elif reason == "not_running":
        print("backend is not running")
    elif reason == "stale_pid":
        print(f"removed stale backend pid {result.get('pid')}")
    elif reason == "single_other_port":
        pid_obj = result.get("pid")
        if not isinstance(pid_obj, int):
            raise SystemExit("failed to determine backend pid")
        pid = pid_obj
        other_port = result.get("port")
        if _confirm_stop_other_instance(
            expected_port=resolved_port, pid=pid, actual_port=other_port
        ):
            follow_up = stop_backend(port=int(other_port) if isinstance(other_port, int) else None)
            if follow_up.get("stopped"):
                _print_stopped(follow_up)
            else:
                raise SystemExit(f"failed to stop backend pid {follow_up.get('pid')}")
        else:
            raise SystemExit(1)
    elif reason == "invalid_state":
        print("removed invalid backend state")
    else:
        raise SystemExit(f"failed to stop backend pid {result.get('pid')}")


def _guard_prestart(resolved_port: int, *, for_daemon: bool, restart: bool) -> bool:
    """Check pre-start conditions; return False if startup should abort (already running etc.).

    Raises SystemExit for unrecoverable conditions.
    """
    existing = read_backend_state()
    if existing is not None:
        existing_port = existing.get("port")
        if isinstance(existing_port, int) and probe_backend(existing_port):
            print(f"backend already running on port {existing_port}")
            return False

    status = backend_status(port=resolved_port)
    if status.get("running"):
        print(f"backend already running on port {status.get('port')} (pid {status.get('pid')})")
        return False
    if status.get("reason") in {"stopped_backend", "unhealthy_backend"}:
        if for_daemon and restart:
            cleanup = stop_backend(port=resolved_port)
            if not cleanup.get("stopped") and cleanup.get("reason") not in {
                "not_running",
                "stale_pid",
            }:
                raise SystemExit(
                    (
                        f"arch-backend pid {status.get('pid')} is not healthy "
                        "and could not be stopped; run "
                        "'arch-backend --stop' manually"
                    )
                )
        else:
            suffix = (
                " or 'arch-backend --restart --daemon'"
                if for_daemon
                else " or 'arch-backend --restart'"
            )
            raise SystemExit(
                (
                    f"arch-backend pid {status.get('pid')} is on port "
                    f"{resolved_port} but is not healthy; run "
                    f"'arch-backend --stop'{suffix}"
                )
            )
    if status.get("reason") == "unmanaged_backend":
        print(
            (
                f"backend already responding on port {resolved_port} but is "
                "not managed by this workspace"
            )
        )
        return False
    if status.get("reason") == "port_in_use":
        raise SystemExit(f"port {resolved_port} is already in use by another process")
    return True


def _run_daemon(args: argparse.Namespace, resolved_port: int, argv: list[str] | None) -> None:
    if not _guard_prestart(resolved_port, for_daemon=True, restart=args.restart):
        return
    log_path = backend_log_path(Path.cwd())
    pid = _start_daemon(argv=argv, log_path=log_path)
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        if probe_backend(resolved_port):
            print(f"backend started on port {resolved_port} (pid {pid}); log: {log_path}")
            return
        time.sleep(0.25)
    raise SystemExit(f"timed out waiting for backend on port {resolved_port}; see {log_path}")


def _run_foreground(
    args: argparse.Namespace, parser: argparse.ArgumentParser, resolved_port: int
) -> None:
    if not _guard_prestart(resolved_port, for_daemon=False, restart=False):
        return

    repo_root_path, enterprise_root_path = gui_server.resolve_server_roots(
        args.repo_root, args.enterprise_root
    )
    if repo_root_path is None:
        parser.error(
            "No --repo-root given, ARCH_REPO_ROOT not set, and no .arch/init-state.yaml found. "
            "Run arch-init first."
        )

    roots: list[Path] = [repo_root_path]
    if enterprise_root_path is not None:
        roots.append(enterprise_root_path)

    from src.common.artifact_query import ArtifactRepository, shared_artifact_index

    logger.info(
        (
            "Initializing backend for repo_root=%s enterprise_root=%s "
            "admin_mode=%s read_only=%s host=%s port=%s"
        ),
        repo_root_path,
        enterprise_root_path,
        args.admin_mode,
        args.read_only,
        args.host,
        resolved_port,
    )
    repo = ArtifactRepository(shared_artifact_index(roots))
    repo.refresh()
    from src.tools.gui_routers import state as gui_state

    gui_state.init_state(
        repo,
        repo_root_path,
        enterprise_root_path,
        admin_mode=args.admin_mode,
        read_only=args.read_only,
    )
    from src.common.artifact_document_schema import load_document_schemata

    load_document_schemata(repo_root_path)
    if args.read_only:
        from src.tools.write_block_manager import block_repo

        block_repo(repo_root_path)

    git_ssh_passphrase = args.git_ssh_password or os.environ.get("ARCH_GIT_SSH_PASSWORD") or None
    log_level_name = backend_min_log_level()
    app = _build_app(git_ssh_passphrase=git_ssh_passphrase)
    write_backend_state(port=resolved_port)
    logger.info("Backend state file written for pid=%s port=%s", os.getpid(), resolved_port)
    try:
        uvicorn.run(app, host=args.host, port=resolved_port, log_level=log_level_name.lower())
    except Exception:
        logger.exception("arch-backend terminated during startup")
        raise
    finally:
        logger.info("Removing backend state file")
        remove_backend_state()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Unified architecture backend")
    p.add_argument(
        "--repo-root",
        default=None,
        help="Engagement repository root (default: ARCH_REPO_ROOT env var or arch-init state)",
    )
    p.add_argument(
        "--enterprise-root",
        default=None,
        help=(
            "Enterprise repository root (default: ARCH_ENTERPRISE_ROOT env var "
            "or arch-init state)"
        ),
    )
    p.add_argument(
        "--admin-mode",
        action="store_true",
        default=False,
        help="Enable enterprise-repo writes through /admin/api/*",
    )
    p.add_argument(
        "--read-only",
        action="store_true",
        default=False,
        help="Block all engagement-repo writes (use for shared/review deployments)",
    )
    p.add_argument(
        "--stop",
        action="store_true",
        default=False,
        help="Stop the currently running arch-backend for this workspace",
    )
    p.add_argument(
        "--status",
        action="store_true",
        default=False,
        help="Show whether arch-backend is running for this workspace",
    )
    p.add_argument(
        "--restart",
        action="store_true",
        default=False,
        help="Restart the currently running backend before starting a new one",
    )
    p.add_argument(
        "--daemon",
        action="store_true",
        default=False,
        help=(
            "Start arch-backend detached with stdin from /dev/null and output "
            "in .arch/backend.log"
        ),
    )
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=None)
    p.add_argument(
        "--git-ssh-password",
        default=None,
        metavar="PASSPHRASE",
        help="SSH key passphrase for git operations (overrides ARCH_GIT_SSH_PASSWORD env var)",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not (args.status or args.stop) and _is_background_tty_job():
        log_path = _redirect_stdio_to_backend_log(start=Path.cwd())
        print(f"arch-backend detected a background TTY job; redirecting output to {log_path}")

    log_level_name = backend_min_log_level()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(
        level=logging.CRITICAL if args.status else log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    resolved_port = resolve_backend_port(start=Path.cwd(), explicit_port=args.port)

    if args.status:
        _run_status(resolved_port)
        return

    if args.stop:
        _run_stop(args, resolved_port)
        return

    if args.restart:
        result = stop_backend(port=resolved_port)
        if result.get("stopped"):
            _print_stopped(result)
        elif result.get("reason") not in {"not_running", "stale_pid", "invalid_state"}:
            raise SystemExit(f"failed to restart backend pid {result.get('pid')}")

    if args.daemon:
        _run_daemon(args, resolved_port, argv)
        return

    _run_foreground(args, parser, resolved_port)


if __name__ == "__main__":
    main()
