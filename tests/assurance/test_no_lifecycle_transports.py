"""v1 deliberately exposes NO public run-lifecycle transport (F3.16/F3.17):
the RefreshSecuritySignals command is CLI/script-only; REST and MCP must not
grow staging/activation/failure routes — a new one is a conscious decision,
not an accident this test would miss."""

from __future__ import annotations

_FORBIDDEN_FRAGMENTS = ("refresh-run", "refresh_run", "refresh-signals", "activate")


def test_rest_exposes_no_run_lifecycle_route() -> None:
    from src.infrastructure.gui.routers.assurance import router

    paths = {getattr(route, "path", "") for route in router.routes}
    offenders = {
        path for path in paths
        if any(fragment in path for fragment in _FORBIDDEN_FRAGMENTS)
    }
    assert offenders == set(), (
        f"run-lifecycle REST routes are deliberately absent in v1: {offenders}"
    )
    # The read-side metrics endpoint IS expected — reads never drive lifecycle.
    assert "/api/assurance/security-metrics" in paths


def test_mcp_write_surface_exposes_no_run_lifecycle_tool() -> None:
    import inspect

    from src.infrastructure.mcp.assurance_mcp import security_write_tools, write_tools

    source = inspect.getsource(write_tools) + inspect.getsource(security_write_tools)
    tool_names = {
        line.split('name="')[1].split('"')[0]
        for line in source.splitlines()
        if 'name="' in line
    }
    offenders = {
        name for name in tool_names
        if any(fragment in name for fragment in ("refresh", "activate", "run_lifecycle"))
    }
    assert offenders == set(), (
        f"run-lifecycle MCP tools are deliberately absent in v1: {offenders}"
    )
