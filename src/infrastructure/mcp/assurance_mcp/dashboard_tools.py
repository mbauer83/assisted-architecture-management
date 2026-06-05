"""Assurance dashboard + assurance-case MCP tools.

Tools registered on arch-assurance-read:
  assurance_risk_register     — query view over risk entities with treatment + owner status
  assurance_coverage          — coverage/gap summary dashboard across all concerns
  assurance_draft_gsn         — scaffold GSN argument structure from store content
  assurance_case_completeness — argument-completeness check
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.assurance_mcp.context import get_assurance_context


def register_dashboard_tools(server: FastMCP) -> None:
    ctx = get_assurance_context()

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

    @server.tool(
        name="assurance_draft_gsn",
        description=(
            "Scaffold a GSN (Goal Structuring Notation) argument structure from the assurance store. "
            "Queries losses, hazards, assurance-constraints, and evidenced-by edges to return a structured "
            "GSN dict with: top_goal (overall safety/security claim), sub_goals (one per hazard), "
            "strategies (constraint-derivation argument per hazard), solutions (evidence artifacts), "
            "and gaps (constraints without evidence, hazards without constraints)."
        ),
    )
    def assurance_draft_gsn() -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        from src.application.verification.case_draft import draft_gsn_from_store  # noqa: PLC0415

        return draft_gsn_from_store(ctx.store)

    @server.tool(
        name="assurance_case_completeness",
        description=(
            "Run argument-completeness checks for an assurance case. "
            "Checks: every assurance-constraint has ≥1 evidenced-by edge; "
            "every hazard has ≥1 constraint via the UCA derives chain; "
            "every loss has ≥1 hazard via leads-to. "
            "Returns structured result with passed/checks/summary, same pattern as assurance_stpa_complete."
        ),
    )
    def assurance_case_completeness() -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        from src.application.verification.case_draft import run_case_completeness  # noqa: PLC0415

        return run_case_completeness(ctx.store)
