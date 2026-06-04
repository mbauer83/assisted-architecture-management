"""Assurance read-only MCP tools.

Tools registered on arch-assurance-read:
  assurance_store_status   — store config/lock status (gating check; always callable)
  assurance_list_nodes     — list assurance entities with filters
  assurance_read_node      — read a single assurance entity
  assurance_list_edges     — list connections in/out of a node
  assurance_stats          — counts by type
  assurance_verify         — run §17(A) verifier rules
  assurance_guidance       — per-step STPA/CAST/GRC method guidance
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
        name="assurance_guidance",
        description=(
            "Return per-step STPA/CAST/GRC method guidance: what the step means, why it matters, "
            "and which standard applies. Topic examples: 'stpa-losses', 'stpa-hazards', "
            "'stpa-control-structure', 'stpa-ucas', 'stpa-constraints', "
            "'grc-risk', 'grc-obligations', 'cast-investigation'."
        ),
    )
    def assurance_guidance(topic: str) -> dict[str, object]:
        return _guidance(topic)


_GUIDANCE: dict[str, dict[str, object]] = {
    "stpa-losses": {
        "step": "STPA Step 1 — Identify Losses",
        "what": (
            "A loss is an unacceptable outcome stakeholders must avoid: loss of life, injury, "
            "property damage, mission failure, privacy violation, regulatory non-compliance."
        ),
        "why": (
            "Losses anchor the entire analysis. Every hazard, UCA, and constraint traces back "
            "to one or more losses. Without losses, STPA has no direction."
        ),
        "how": (
            "Brainstorm stakeholder-relevant outcomes to avoid. Use broad categories first "
            "(safety, security, financial, privacy). Each loss should be a noun phrase, "
            "e.g. 'Loss of vehicle control', 'Breach of personal data'."
        ),
        "standards": [
            "STPA Handbook (Leveson & Thomas) §2.2",
            "ISO 26262 Part 3 §6 (hazard analysis and risk assessment)",
        ],
    },
    "stpa-hazards": {
        "step": "STPA Step 2 — Identify System-Level Hazards",
        "what": (
            "A hazard is a system state that, with worst-case environment, leads to a loss. "
            "It describes the system state, not the cause or outcome."
        ),
        "why": (
            "Hazards bridge losses and the control structure. They are system-level "
            "(not component-level) to remain stable across design changes."
        ),
        "how": (
            "For each loss, ask: what system state could produce this loss? "
            "Write hazards as system states, e.g. 'Vehicle moves at unsafe speed for road conditions'."
        ),
        "standards": ["STPA Handbook §2.3", "ISO/SAE 21434 Clause 9 (TARA)"],
    },
    "stpa-control-structure": {
        "step": "STPA Step 3 — Model the Control Structure",
        "what": (
            "The control structure is a hierarchical diagram of controllers and controlled "
            "processes connected by control actions and feedback — the STAMP governance model."
        ),
        "why": (
            "UCAs can only be identified with respect to a specific control action on a specific "
            "control loop. The control structure makes those loops explicit."
        ),
        "how": (
            "Identify controllers (issue commands), controlled processes (receive commands), "
            "control actions (specific commands), and feedback signals. Mark binding_status for each node."
        ),
        "standards": ["STPA Handbook §2.4", "STAMP/STPA overview (UL)"],
    },
    "stpa-ucas": {
        "step": "STPA Step 4 — Identify Unsafe Control Actions (UCAs)",
        "what": (
            "A UCA is a specific control action unsafe in a particular context. "
            "Four types: (1) not provided, (2) provided when unsafe, "
            "(3) wrong timing, (4) stopped too soon / applied too long."
        ),
        "why": (
            "UCAs are the direct cause of hazards in STAMP. Systematically applying "
            "the four guidewords to each control action ensures completeness."
        ),
        "how": (
            "For each control action on each controller, apply all four guidewords. Record the "
            "context (state variables) under which each guideword produces a UCA. "
            "Each UCA must reference exactly one control-action."
        ),
        "standards": ["STPA Handbook §2.5", "UCA guideword guide"],
    },
    "stpa-constraints": {
        "step": "STPA Step 5 — Derive Safety/Security Constraints",
        "what": (
            "An assurance-constraint is a requirement derived from UCAs: "
            "'The controller must/must not issue action X in context Y.' "
            "Constraints are the actionable output of STPA."
        ),
        "why": (
            "Constraints are directly implementable and testable. They link hazard analysis "
            "to system requirements (via refines) and to evidence (via evidenced-by)."
        ),
        "how": (
            "For each UCA, derive its negation as a constraint. Set concern_class, disposition, level. "
            "Link to an ArchiMate requirement via refines. Assign an owner via accountable-to."
        ),
        "standards": ["STPA Handbook §2.6", "ISO 26262 Part 4 §6 (functional safety concept)"],
    },
    "grc-risk": {
        "step": "GRC — Risk Evaluation",
        "what": (
            "A risk entity evaluates a hazard or loss-scenario: likelihood × impact = risk score. "
            "OPTIONAL — constraints are valid without a risk entity (§9 anti-subordination safeguard)."
        ),
        "why": (
            "Risk prioritises which constraints to treat first, but never closes a safety/security "
            "constraint. treatment=accept cannot be the sole disposition of a safety hazard."
        ),
        "how": (
            "Create a risk entity, set likelihood and impact, connect via assesses→hazard "
            "and treated-by→assurance-constraint. Assign an owner. Set review_date."
        ),
        "standards": ["ISO 31000:2018 §6 (risk treatment)", "Cerrix risk register best practices"],
    },
    "grc-obligations": {
        "step": "GRC — Compliance Obligations",
        "what": (
            "An obligation entity represents a compliance instance: 'Does our system comply "
            "with clause X of standard Y?' Status and evidence are assurance-owned and confidential."
        ),
        "why": (
            "Obligations close the loop between technical constraints and regulatory requirements. "
            "They enable an auditable compliance statement."
        ),
        "how": (
            "Create an obligation, set cites to a scheme:code reference (e.g. ISO26262:6-8). "
            "Link assurance-constraints via complies-with. Add evidenced-by connections for evidence."
        ),
        "standards": [
            "ISO 27001:2022 Annex A controls",
            "GDPR Art. 5 (data processing principles)",
            "EU AI Act Art. 12/18/19/26",
        ],
    },
    "cast-investigation": {
        "step": "CAST — Incident/Accident Investigation",
        "what": (
            "CAST (Causal Analysis using System Theory) is the reactive counterpart of STPA. "
            "It reconstructs the control structure as-existed at the incident and derives corrective constraints."
        ),
        "why": (
            "CAST reuses the STAMP model and adds incident entity, observed UCAs (mode=observed), "
            "and corrective-actions. Corrective constraints enter the same GRC lifecycle as STPA constraints."
        ),
        "how": (
            "Create an incident entity, seal an analysis_baseline to pin the model state, "
            "then trace observed UCAs and loss-scenarios back to the incident. "
            "Derive corrective-action entities and then constraints."
        ),
        "standards": ["CAST Handbook (Leveson)", "STPA/CAST overview (UL)"],
    },
}


def _guidance(topic: str) -> dict[str, object]:
    normalized = topic.lower().strip().replace(" ", "-")
    for key, value in _GUIDANCE.items():
        if key == normalized or normalized in key or key in normalized:
            return {"topic": key, **value}
    return {
        "topic": topic,
        "available_topics": list(_GUIDANCE.keys()),
        "message": f"No guidance found for '{topic}'. Try one of the available topics.",
    }
