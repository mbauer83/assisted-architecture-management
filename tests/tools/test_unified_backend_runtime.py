from __future__ import annotations

from pathlib import Path

from starlette.routing import Match

from src.tools import mcp_artifact_server
from src.tools import backend_runtime
from src.tools import arch_backend
from src.tools.arch_backend import _build_app


def test_arch_mcp_model_stdio_delegates_to_bridge_by_default(monkeypatch) -> None:
    called: dict[str, list[str]] = {}

    def fake_bridge_main(argv: list[str] | None = None) -> None:
        called["argv"] = argv or []

    monkeypatch.setattr("src.tools.arch_mcp_stdio.main", fake_bridge_main)

    mcp_artifact_server.main(["--transport", "stdio"])

    assert called["argv"] == ["--port", "8000"]


def test_arch_mcp_model_stdio_can_still_run_standalone(monkeypatch) -> None:
    called: dict[str, object] = {"run": False}

    def fake_run(*, transport: str) -> None:
        called["run"] = transport

    monkeypatch.setattr(mcp_artifact_server.mcp, "run", fake_run)

    mcp_artifact_server.main(["--transport", "stdio", "--standalone-stdio"])

    assert called["run"] == "stdio"


def test_backend_state_path_falls_back_without_arch_init(tmp_path: Path) -> None:
    path = backend_runtime.backend_state_path(tmp_path)
    assert path == tmp_path / ".arch" / "backend.pid"


def test_ensure_backend_running_requires_explicit_external_backend(monkeypatch) -> None:
    monkeypatch.setattr(backend_runtime, "read_backend_state", lambda start=None: None)
    monkeypatch.setattr(backend_runtime, "configured_backend_url", lambda: None)

    try:
        backend_runtime.ensure_backend_running(port=8123, start_if_missing=False)
    except RuntimeError as exc:
        assert "not running" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_ensure_backend_running_uses_explicit_external_backend(monkeypatch) -> None:
    monkeypatch.setattr(backend_runtime, "read_backend_state", lambda start=None: None)
    monkeypatch.setattr(backend_runtime, "configured_backend_url", lambda: "http://127.0.0.1:8123")
    monkeypatch.setattr(backend_runtime, "probe_backend_url", lambda url, timeout_s=1.0: url == "http://127.0.0.1:8123")

    port = backend_runtime.ensure_backend_running(port=8000, start_if_missing=False)

    assert port == 8000


def test_backend_start_command_falls_back_to_uv_for_gui_extras(monkeypatch) -> None:
    monkeypatch.setattr(backend_runtime.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)

    cmd = backend_runtime.backend_start_command(port=8123)

    assert cmd == ["/usr/bin/uv", "run", "--extra", "gui", "arch-backend", "--port", "8123"]


def test_backend_start_command_only_uses_current_python_when_uv_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(backend_runtime.shutil, "which", lambda name: None)
    monkeypatch.setattr(backend_runtime.importlib.util, "find_spec", lambda name: object())

    cmd = backend_runtime.backend_start_command(port=8123)

    assert cmd == [backend_runtime.sys.executable, "-m", "src.tools.arch_backend", "--port", "8123"]


def test_unified_backend_routes_mcp_on_bare_and_slash_paths() -> None:
    app = _build_app()
    bare_scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "server": ("127.0.0.1", 8000),
    }
    slash_scope = {**bare_scope, "path": "/mcp/"}

    mcp_routes = [route for route in app.routes if getattr(route, "path", None) in {"/mcp", "/mcp/"}]
    bare_matches = [route.matches(bare_scope)[0] for route in mcp_routes]
    slash_matches = [route.matches(slash_scope)[0] for route in mcp_routes]

    assert Match.FULL in bare_matches
    assert Match.FULL in slash_matches


def test_stop_backend_returns_not_running_when_no_state(monkeypatch) -> None:
    monkeypatch.setattr(backend_runtime, "read_backend_state", lambda start=None: None)

    result = backend_runtime.stop_backend()

    assert result == {"stopped": False, "reason": "not_running"}


def test_backend_status_reports_not_running_when_no_state(monkeypatch) -> None:
    monkeypatch.setattr(backend_runtime, "read_backend_state", lambda start=None: None)
    monkeypatch.setattr(backend_runtime, "probe_backend", lambda port, timeout_s=1.0: False)
    monkeypatch.setattr(backend_runtime, "port_in_use", lambda host="127.0.0.1", port=8000: False)

    result = backend_runtime.backend_status()

    assert result == {"running": False, "reason": "not_running"}


def test_backend_status_reports_unmanaged_backend(monkeypatch) -> None:
    monkeypatch.setattr(backend_runtime, "read_backend_state", lambda start=None: None)
    monkeypatch.setattr(backend_runtime, "probe_backend", lambda port, timeout_s=1.0: True)

    result = backend_runtime.backend_status(port=8000)

    assert result == {"running": False, "reason": "unmanaged_backend", "port": 8000}


def test_backend_status_reports_port_in_use(monkeypatch) -> None:
    monkeypatch.setattr(backend_runtime, "read_backend_state", lambda start=None: None)
    monkeypatch.setattr(backend_runtime, "probe_backend", lambda port, timeout_s=1.0: False)
    monkeypatch.setattr(backend_runtime, "port_in_use", lambda host="127.0.0.1", port=8000: True)

    result = backend_runtime.backend_status(port=8000)

    assert result == {"running": False, "reason": "port_in_use", "port": 8000}


def test_stop_backend_removes_stale_pid(monkeypatch) -> None:
    removed: list[object] = []

    monkeypatch.setattr(backend_runtime, "read_backend_state", lambda start=None: {"pid": 123, "port": 8000})
    monkeypatch.setattr(backend_runtime, "remove_backend_state", lambda start=None: removed.append(start))

    def fake_kill(pid: int, sig: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr(backend_runtime.os, "kill", fake_kill)

    result = backend_runtime.stop_backend()

    assert result == {"stopped": False, "reason": "stale_pid", "pid": 123}
    assert removed == [None]


def test_arch_backend_stop_prints_not_running(monkeypatch, capsys) -> None:
    monkeypatch.setattr(arch_backend, "stop_backend", lambda: {"stopped": False, "reason": "not_running"})

    arch_backend.main(["--stop"])

    out = capsys.readouterr().out
    assert "not running" in out


def test_arch_backend_status_prints_running(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        arch_backend,
        "backend_status",
        lambda port=8000: {"running": True, "reason": "ok", "pid": 321, "port": port},
    )

    arch_backend.main(["--status"])

    out = capsys.readouterr().out
    assert "running on port 8000" in out


def test_arch_backend_status_prints_unmanaged_backend(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        arch_backend,
        "backend_status",
        lambda port=8000: {"running": False, "reason": "unmanaged_backend", "port": port},
    )

    arch_backend.main(["--status"])

    out = capsys.readouterr().out
    assert "not managed by this workspace" in out


def test_arch_backend_restart_stops_then_returns_to_startup(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(
        arch_backend,
        "stop_backend",
        lambda: {"stopped": True, "pid": 123, "port": 8000},
    )
    monkeypatch.setattr(arch_backend, "read_backend_state", lambda: None)
    monkeypatch.setattr(
        arch_backend.gui_server,
        "resolve_server_roots",
        lambda repo_root, enterprise_root: (tmp_path, None),
    )
    monkeypatch.setattr(
        arch_backend,
        "backend_status",
        lambda port=8000: {"running": False, "reason": "not_running"},
    )
    monkeypatch.setattr(arch_backend, "_build_app", lambda: object())
    ran: dict[str, object] = {}

    def fake_run(app, host: str, port: int, log_level: str) -> None:
        ran["host"] = host
        ran["port"] = port

    monkeypatch.setattr(arch_backend.uvicorn, "run", fake_run)

    arch_backend.main(["--restart", "--repo-root", str(tmp_path)])

    out = capsys.readouterr().out
    assert "stopped backend pid 123" in out
    assert ran == {"host": "127.0.0.1", "port": 8000}


def test_arch_backend_refuses_to_start_when_port_used_by_other_process(monkeypatch) -> None:
    monkeypatch.setattr(arch_backend, "read_backend_state", lambda: None)
    monkeypatch.setattr(
        arch_backend,
        "backend_status",
        lambda port=8000: {"running": False, "reason": "port_in_use", "port": port},
    )

    try:
        arch_backend.main([])
    except SystemExit as exc:
        assert "already in use" in str(exc)
    else:
        raise AssertionError("expected SystemExit")
