"""Assurance read-only MCP tools (core).

Tools registered on arch-assurance-read:
  assurance_store_status  — store config/lock status (gating check; always callable)
  assurance_list_nodes    — list assurance entities with filters
  assurance_read_node     — read a single assurance entity
  assurance_list_edges    — list connections in/out of a node
  assurance_stats         — counts by type
  assurance_verify        — run §17(A) verifier rules
  assurance_guidance      — per-step STPA/CAST/GRC method guidance
  assurance_stpa_complete — §17(B) STPA coverage profile check
  assurance_cast_complete — §17(B) CAST coverage profile check (G-g gate)
  assurance_grc_complete  — §17(B) GRC control-coverage-complete check

Dashboard/case tools are in dashboard_tools.py (registered via register_dashboard_tools).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.assurance_mcp.context import (
    _exposure_log,
    get_assurance_context,
    is_above_ceiling,
)
from src.infrastructure.mcp.assurance_mcp.dashboard_tools import register_dashboard_tools
from src.infrastructure.mcp.assurance_mcp.security_read_tools import register_security_read_tools


def register_read_tools(server: FastMCP) -> None:
    register_security_read_tools(server)
    register_dashboard_tools(server)
    ctx = get_assurance_context()

    @server.tool(
        name="assurance_store_status",
        description=(
            "Return the current status of the confidential assurance store: whether it is "
            "configured, locked, or unlocked. Always callable — does not require the store to be open."
        ),
    )
    def assurance_store_status() -> dict[str, object]:
        from src.infrastructure.mcp.assurance_mcp.context import default_db_path  # noqa: PLC0415

        bundle = ctx._bundle()  # noqa: SLF001
        store = bundle.store
        unlocked = store.is_unlocked()
        db_path = default_db_path()
        return {
            "store_backend": bundle.store_backend,
            "signals_backend": bundle.signals_backend,
            "max_classification": ctx.max_classification,
            "db_path": str(db_path),
            "db_exists": db_path.exists(),
            "unlocked": unlocked,
            "status": "unlocked" if unlocked else ("locked" if db_path.exists() else "not_initialised"),
            "hint": (
                None
                if unlocked
                else (
                    "Run `arch-assurance unlock` to open the store."
                    if db_path.exists()
                    else "Run `arch-assurance init` to initialise the store."
                )
            ),
        }

    @server.tool(
        name="assurance_list_nodes",
        description=(
            "List assurance entities (losses, hazards, UCAs, constraints, etc.). "
            "Filter by node_type, status, concern_class, or tlp."
        ),
    )
    def assurance_list_nodes(
        node_type: str | None = None,
        status: str | None = None,
        concern_class: str | None = None,
        tlp: str | None = None,
    ) -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        ceiling = ctx.max_classification
        nodes = ctx.store.list_nodes(
            node_type=node_type,
            status=status,
            concern_class=concern_class,
            tlp=tlp,
        )
        exposed: list[dict[str, object]] = []
        withheld_count = 0
        for node in nodes:
            node_tlp = str(node.get("tlp", "TLP:WHITE"))
            if is_above_ceiling(node_tlp, ceiling):
                withheld_count += 1
            else:
                exposed.append(node)
        if withheld_count:
            _exposure_log.info(
                "list_nodes: ceiling=%s returned=%d withheld=%d",
                ceiling, len(exposed), withheld_count,
            )
        return {"nodes": exposed, "count": len(exposed), "withheld": withheld_count}

    @server.tool(
        name="assurance_read_node",
        description="Read a single assurance entity by node_id. Returns all attributes and content.",
    )
    def assurance_read_node(node_id: str) -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        node = ctx.store.get_node(node_id)
        if node is None:
            return ctx.not_found_response(node_id)
        node_tlp = str(node.get("tlp", "TLP:WHITE"))
        ceiling = ctx.max_classification
        if is_above_ceiling(node_tlp, ceiling):
            _exposure_log.info(
                "read_node: ceiling=%s withheld=%s tlp=%s",
                ceiling, node_id, node_tlp,
            )
            return ctx.withheld_response(node_id, node_tlp)
        edges_out = ctx.store.list_edges(source_id=node_id)
        edges_in = ctx.store.list_edges(target_id=node_id)
        return {"node": node, "outgoing_edges": edges_out, "incoming_edges": edges_in}

    @server.tool(
        name="assurance_list_edges",
        description=(
            "List assurance connections. Filter by source_id, target_id, or conn_type."
        ),
    )
    def assurance_list_edges(
        source_id: str | None = None,
        target_id: str | None = None,
        conn_type: str | None = None,
    ) -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        edges = ctx.store.list_edges(source_id=source_id, target_id=target_id, conn_type=conn_type)
        return {"edges": edges, "count": len(edges)}

    @server.tool(
        name="assurance_stats",
        description="Return counts of assurance nodes and edges by type.",
    )
    def assurance_stats() -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        return ctx.store.stats()

    @server.tool(
        name="assurance_verify",
        description=(
            "Run §17(A) hard structural validity checks on all assurance entities in the store. "
            "Returns errors (block sign-off) and warnings (informational). "
            "Also emits W501 modeling-gap findings for unbound-pending control-structure-nodes."
        ),
    )
    def assurance_verify() -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        from src.application.verification.assurance_verifier import format_result, verify_store  # noqa: PLC0415

        result = verify_store(ctx.store)
        return format_result(result)

    @server.tool(
        name="assurance_stpa_complete",
        description=(
            "Run the §17(B) stpa-basic-complete coverage profile check on the assurance store. "
            "Checks: every hazard has ≥1 leads-to loss; every UCA has ≥1 concerns control-action "
            "AND ≥1 violates hazard; every loss-scenario has ≥1 explains UCA; every UCA and "
            "loss-scenario has ≥1 derives constraint. Returns gap counts and node IDs for each check."
        ),
    )
    def assurance_stpa_complete() -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        from src.application.verification.stpa_complete import run_stpa_complete  # noqa: PLC0415

        return run_stpa_complete(ctx.store)

    @server.tool(
        name="assurance_guidance",
        description=(
            "Return per-step STPA/CAST/GRC method guidance: what the step means, why it matters, "
            "and which standard applies. Always callable — does not require the store to be open. "
            "Topic examples: 'stpa-losses', 'stpa-hazards', 'stpa-control-structure', "
            "'stpa-ucas', 'stpa-constraints', 'grc-risk', 'grc-obligations', 'cast-investigation'."
        ),
    )
    def assurance_guidance(topic: str) -> dict[str, object]:
        from src.infrastructure.mcp.assurance_mcp.guidance import lookup  # noqa: PLC0415

        return lookup(topic)

    @server.tool(
        name="assurance_cast_complete",
        description=(
            "Run the §17(B) cast-complete coverage profile check. "
            "G-g gate: fails if any incident exists without a sealed analysis_baseline. "
            "Also checks: every incident has ≥1 investigates edge; every corrective-action "
            "has ≥1 derives edge to a constraint. Returns gap counts per check."
        ),
    )
    def assurance_cast_complete() -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        from src.application.verification.cast_complete import run_cast_complete  # noqa: PLC0415

        return run_cast_complete(ctx.store, ctx.archive)

    @server.tool(
        name="assurance_grc_complete",
        description=(
            "Run the §17(B) grc-control-coverage-complete profile check. "
            "Checks: every obligation has ≥1 complies-with constraint; "
            "every risk has a treatment attribute; every risk has an accountable-to owner. "
            "Returns gap counts per check."
        ),
    )
    def assurance_grc_complete() -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        from src.application.verification.grc_complete import run_grc_complete  # noqa: PLC0415

        return run_grc_complete(ctx.store)
