"""Assurance read-only MCP tools.

Tools registered on arch-assurance-read:
  assurance_store_status      — store config/lock status (gating check; always callable)
  assurance_list_nodes        — list assurance entities with filters
  assurance_read_node         — read a single assurance entity
  assurance_list_edges        — list connections in/out of a node
  assurance_stats             — counts by type
  assurance_verify            — run §17(A) verifier rules
  assurance_guidance          — per-step STPA/CAST/GRC method guidance
  assurance_stpa_complete     — §17(B) STPA coverage profile check
  assurance_cast_complete     — §17(B) CAST coverage profile check (G-g gate)
  assurance_grc_complete      — §17(B) GRC control-coverage-complete check
  assurance_risk_register     — query view over risk entities with treatment + owner status
  assurance_coverage          — coverage/gap summary dashboard across all concerns
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.assurance_mcp.context import get_assurance_context


def register_read_tools(server: FastMCP) -> None:
    ctx = get_assurance_context()

    @server.tool(
        name="assurance_store_status",
        description=(
            "Return the current status of the confidential assurance store: whether it is "
            "configured, locked, or unlocked. Always callable — does not require the store to be open."
        ),
    )
    def assurance_store_status() -> dict[str, object]:
        store = ctx.store
        configured = store._db_path.exists()  # noqa: SLF001
        unlocked = store.is_unlocked()
        return {
            "configured": configured,
            "unlocked": unlocked,
            "db_path": str(store._db_path),  # noqa: SLF001
            "status": "unlocked" if unlocked else ("locked" if configured else "not_initialised"),
            "hint": (
                None
                if unlocked
                else (
                    "Run `arch-assurance unlock` to open the store."
                    if configured
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
        nodes = ctx.store.list_nodes(
            node_type=node_type,
            status=status,
            concern_class=concern_class,
            tlp=tlp,
        )
        return {"nodes": nodes, "count": len(nodes)}

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

    @server.tool(
        name="assurance_risk_register",
        description=(
            "Return a tabular view of all risk entities with their treatment, owner status, "
            "linked hazards/loss-scenarios (via assesses), and treating constraints (via treated-by). "
            "Useful for the GRC risk register view (US8)."
        ),
    )
    def assurance_risk_register() -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        import json as _json  # noqa: PLC0415

        all_nodes = ctx.store.list_nodes()
        all_edges = ctx.store.list_edges()
        nodes_by_id = {str(n["node_id"]): n for n in all_nodes}

        risks = [n for n in all_nodes if str(n.get("node_type", "")) == "risk"]
        rows = []
        for risk in risks:
            rid = str(risk["node_id"])
            attrs_raw = risk.get("attributes_json") or "{}"
            try:
                attrs: dict[str, object] = _json.loads(str(attrs_raw))
            except Exception:  # noqa: BLE001
                attrs = {}

            assesses_ids = [
                str(e["target_id"]) for e in all_edges
                if str(e["source_id"]) == rid and str(e["conn_type"]) == "assesses"
            ]
            treated_by_ids = [
                str(e["target_id"]) for e in all_edges
                if str(e["source_id"]) == rid and str(e["conn_type"]) == "treated-by"
            ]
            owner_ids = [
                str(e["target_id"]) for e in all_edges
                if str(e["source_id"]) == rid and str(e["conn_type"]) == "accountable-to"
            ]

            rows.append({
                "node_id": rid,
                "name": str(risk.get("name", "")),
                "status": str(risk.get("status", "")),
                "treatment": str(attrs.get("treatment") or ""),
                "likelihood": str(attrs.get("likelihood") or ""),
                "impact": str(attrs.get("impact") or ""),
                "risk_score": str(attrs.get("risk_score") or ""),
                "assesses": [
                    {"node_id": i, "name": str(nodes_by_id.get(i, {}).get("name", ""))}
                    for i in assesses_ids
                ],
                "treated_by": [
                    {"node_id": i, "name": str(nodes_by_id.get(i, {}).get("name", ""))}
                    for i in treated_by_ids
                ],
                "owners": [
                    {"node_id": i, "name": str(nodes_by_id.get(i, {}).get("name", ""))}
                    for i in owner_ids
                ],
            })

        return {"risks": rows, "count": len(rows)}

    @server.tool(
        name="assurance_coverage",
        description=(
            "Return a coverage/gap summary across the assurance store: "
            "constraints without evidence, hazards without constraints, "
            "obligations without constraints, risks without treatment, "
            "unbound-pending CSNs, and orphan corrective-actions. "
            "Use this dashboard to identify where analysis is incomplete."
        ),
    )
    def assurance_coverage() -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()

        all_nodes = ctx.store.list_nodes()
        all_edges = ctx.store.list_edges()

        def _nodes_of(ntype: str) -> list[dict[str, object]]:
            return [n for n in all_nodes if str(n.get("node_type", "")) == ntype]

        def _has_outgoing(node_id: str, conn: str) -> bool:
            return any(
                str(e["source_id"]) == node_id and str(e["conn_type"]) == conn
                for e in all_edges
            )

        def _has_incoming(node_id: str, conn: str) -> bool:
            return any(
                str(e["target_id"]) == node_id and str(e["conn_type"]) == conn
                for e in all_edges
            )

        gaps: dict[str, list[dict[str, str]]] = {}

        gaps["constraints_without_evidence"] = [
            {"node_id": str(n["node_id"]), "name": str(n.get("name", ""))}
            for n in _nodes_of("assurance-constraint")
            if not _has_outgoing(str(n["node_id"]), "evidenced-by")
        ]
        gaps["hazards_without_constraints"] = [
            {"node_id": str(n["node_id"]), "name": str(n.get("name", ""))}
            for n in _nodes_of("hazard")
            if not _has_incoming(str(n["node_id"]), "violates")
        ]
        gaps["obligations_without_constraints"] = [
            {"node_id": str(n["node_id"]), "name": str(n.get("name", ""))}
            for n in _nodes_of("obligation")
            if not _has_incoming(str(n["node_id"]), "complies-with")
        ]
        import json as _json  # noqa: PLC0415

        gaps["risks_without_treatment"] = [
            {"node_id": str(n["node_id"]), "name": str(n.get("name", ""))}
            for n in _nodes_of("risk")
            if not str(
                _json.loads(str(n.get("attributes_json") or "{}")).get("treatment") or ""
            ).strip()
        ]
        gaps["unbound_pending_csns"] = [
            {"node_id": str(n["node_id"]), "name": str(n.get("name", ""))}
            for n in _nodes_of("control-structure-node")
            if str(n.get("binding_status", "")) == "unbound-pending"
        ]
        gaps["orphan_corrective_actions"] = [
            {"node_id": str(n["node_id"]), "name": str(n.get("name", ""))}
            for n in _nodes_of("corrective-action")
            if not _has_outgoing(str(n["node_id"]), "derives")
        ]

        total_gaps = sum(len(v) for v in gaps.values())
        category_count = sum(1 for v in gaps.values() if v)
        return {
            "total_gaps": total_gaps,
            "gaps": gaps,
            "summary": (
                "No coverage gaps found."
                if total_gaps == 0
                else f"{total_gaps} coverage gap(s) detected across {category_count} category/categories."
            ),
        }
