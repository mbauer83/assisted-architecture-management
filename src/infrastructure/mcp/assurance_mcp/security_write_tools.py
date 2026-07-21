"""Security-signal write MCP tools.

Tools registered on arch-assurance-write:
  assurance_reconcile_aibom       — drift report: modeled vs discovered AI-BOM

Signal ingestion is performed by the RefreshSecuritySignals command (the refresh
tool / CLI), which owns the run lifecycle and the §6.0(a)/D21 mutation+audit
transaction boundary. There is no ad-hoc MCP signal-write path.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]


def register_security_write_tools(server: FastMCP) -> None:
    @server.tool(
        name="assurance_reconcile_aibom",
        description=(
            "Diff a modeled AI-BOM (from the architecture model) against a discovered one "
            "(from a runtime discovery tool or an imported BOM file). "
            "Returns: added (in discovered but not modeled), removed (modeled but not discovered), "
            "and matched components. "
            "modeled_components: list of component dicts from assurance_aibom_export or manually. "
            "discovered_components: list of component dicts from an external AI discovery tool. "
            "Each component needs at least 'name'; 'purl' is used as the identity key if present."
        ),
    )
    def assurance_reconcile_aibom(
        modeled_components: list[dict[str, object]],
        discovered_components: list[dict[str, object]],
    ) -> dict[str, object]:
        from src.infrastructure.assurance._aibom_exporter import reconcile_aibom  # noqa: PLC0415

        return reconcile_aibom(modeled_components, discovered_components)
