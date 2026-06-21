"""Assurance write MCP tools.

Tools registered on arch-assurance-write:
  assurance_create_node         — create any assurance entity
  assurance_add_edge            — add a typed assurance connection
  assurance_edit_node           — update node attributes
  assurance_delete_node         — delete a node (cascades edges)
  assurance_delete_edge         — delete a single edge by edge_id
  assurance_seal_baseline       — seal a signed analysis baseline
  assurance_register_arch_ref   — record an assurance→architecture reference
  assurance_model_this          — propose architecture entity to bind an unbound-pending node
  assurance_promotion_preflight — pre-check safety/security constraints before promotion

All node/edge/ref mutations delegate to src.application.assurance_mutations use cases,
which enforce the three-step protocol: unlock-check → write → audit → post-write verify.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.application import assurance_mutations as mutations
from src.infrastructure.mcp.assurance_mcp.context import get_assurance_context
from src.infrastructure.mcp.assurance_mcp.security_write_tools import register_security_write_tools


def _ok(result: mutations.MutationOk) -> dict[str, object]:
    out: dict[str, object] = dict(result.payload)
    if result.findings:
        out["verification_findings"] = result.findings
    return out


def _analysis_result(result: Any, ctx: Any) -> dict[str, object]:
    from src.application import assurance_analysis as analysis_uc  # noqa: PLC0415

    if isinstance(result, analysis_uc.AnalysisLocked):
        return ctx.locked_response()
    if isinstance(result, analysis_uc.AnalysisNotFound):
        return ctx.not_found_response(result.analysis_id)
    if isinstance(result, analysis_uc.AnalysisInvalid):
        return {"error": result.error, "message": result.message}
    return result.payload


def register_write_tools(server: FastMCP) -> None:
    register_security_write_tools(server)
    ctx = get_assurance_context()

    @server.tool(
        name="assurance_create_node",
        description=(
            "Create an assurance entity (loss, hazard, control-structure-node, control-action, "
            "unsafe-control-action, loss-scenario, assurance-constraint, risk, incident, "
            "corrective-action, obligation). "
            "Returns the new node_id. All writes are audited; post-write verification findings "
            "are included in the response (writes are never blocked by the verifier)."
        ),
    )
    def assurance_create_node(
        node_type: str,
        name: str,
        status: str = "draft",
        tlp: str = "TLP:WHITE",
        concern_class: str | None = None,
        disposition: str | None = None,
        uca_type: str | None = None,
        binding_status: str | None = None,
        node_role: str | None = None,
        analysis_id: str | None = None,
        content_text: str = "",
        attributes: dict[str, object] | None = None,
    ) -> dict[str, object]:
        result = mutations.create_node(
            ctx.store, ctx.archive,
            node_type=node_type, name=name, status=status, tlp=tlp,
            concern_class=concern_class, disposition=disposition,
            uca_type=uca_type, binding_status=binding_status,
            node_role=node_role, analysis_id=analysis_id,
            content_text=content_text, attributes=attributes,
        )
        if isinstance(result, mutations.MutationLocked):
            return ctx.locked_response()
        if isinstance(result, mutations.MutationNotFound):
            return ctx.not_found_response(result.artifact_id)
        return _ok(result)

    @server.tool(
        name="assurance_add_edge",
        description=(
            "Add a typed assurance connection between two nodes. "
            "Both nodes must exist in the assurance store. "
            "Valid connection types: issues, acts-on, feedback, concerns, by-controller, violates, "
            "leads-to, explains, derives, refines, satisfied-by, accountable-to, responsible-of, "
            "evidenced-by, assesses, treated-by, complies-with, cites, binds-to, investigates."
        ),
    )
    def assurance_add_edge(
        source_id: str,
        target_id: str,
        conn_type: str,
        attributes: dict[str, object] | None = None,
    ) -> dict[str, object]:
        result = mutations.add_edge(
            ctx.store, ctx.archive,
            source_id=source_id, target_id=target_id,
            conn_type=conn_type, attributes=attributes,
        )
        if isinstance(result, mutations.MutationLocked):
            return ctx.locked_response()
        if isinstance(result, mutations.MutationNotFound):
            return ctx.not_found_response(result.artifact_id)
        return _ok(result)

    @server.tool(
        name="assurance_edit_node",
        description=(
            "Update attributes of an existing assurance node. "
            "Provide only the attributes to change. "
            "Updatable: name, status, tlp, concern_class, disposition, uca_type, binding_status, "
            "node_role, content_text, attributes (dict of extra fields)."
        ),
    )
    def assurance_edit_node(
        node_id: str,
        name: str | None = None,
        status: str | None = None,
        tlp: str | None = None,
        concern_class: str | None = None,
        disposition: str | None = None,
        uca_type: str | None = None,
        binding_status: str | None = None,
        node_role: str | None = None,
        content_text: str | None = None,
        attributes: dict[str, object] | None = None,
    ) -> dict[str, object]:
        result = mutations.edit_node(
            ctx.store, ctx.archive,
            node_id=node_id, name=name, status=status, tlp=tlp,
            concern_class=concern_class, disposition=disposition,
            uca_type=uca_type, binding_status=binding_status,
            node_role=node_role, content_text=content_text, attributes=attributes,
        )
        if isinstance(result, mutations.MutationLocked):
            return ctx.locked_response()
        if isinstance(result, mutations.MutationNotFound):
            return ctx.not_found_response(result.artifact_id)
        return _ok(result)

    @server.tool(
        name="assurance_delete_node",
        description=(
            "Delete an assurance node and all its incoming/outgoing edges. "
            "This action is logged in the audit trail but is not reversible."
        ),
    )
    def assurance_delete_node(node_id: str) -> dict[str, object]:
        result = mutations.delete_node(ctx.store, ctx.archive, node_id=node_id)
        if isinstance(result, mutations.MutationLocked):
            return ctx.locked_response()
        if isinstance(result, mutations.MutationNotFound):
            return ctx.not_found_response(result.artifact_id)
        return _ok(result)

    @server.tool(
        name="assurance_delete_edge",
        description=(
            "Delete a single assurance edge by its edge_id. "
            "Unlike assurance_delete_node, this removes only the edge (not its endpoints). "
            "The operation is logged in the audit trail and is not reversible."
        ),
    )
    def assurance_delete_edge(edge_id: str) -> dict[str, object]:
        result = mutations.delete_edge(ctx.store, ctx.archive, edge_id=edge_id)
        if isinstance(result, mutations.MutationLocked):
            return ctx.locked_response()
        if isinstance(result, mutations.MutationNotFound):
            return ctx.not_found_response(result.artifact_id)
        return _ok(result)

    @server.tool(
        name="assurance_seal_baseline",
        description=(
            "Seal a signed baseline of the current assurance analysis state. "
            "The baseline captures the current audit-log head hash as a tamper-evident snapshot. "
            "Required before CAST investigations (pins the 'as-existed' model state). "
            "Also satisfies EU AI Act Art. 18 technical-documentation retention."
        ),
    )
    def assurance_seal_baseline(
        notes: str = "",
        analysis_id: str | None = None,
    ) -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        return ctx.archive.seal_baseline(notes=notes, analysis_id=analysis_id)

    @server.tool(
        name="assurance_register_arch_ref",
        description=(
            "Record an assurance→architecture cross-reference. "
            "This is the ONLY direction allowed (one-way persistence rule). "
            "The architecture artifact ID must be a valid ID from the arch-repo-read store. "
            "Dangling refs (arch entity not found) are tolerated and marked as unresolved."
        ),
    )
    def assurance_register_arch_ref(
        assurance_node_id: str,
        arch_artifact_id: str,
        ref_type: str,
    ) -> dict[str, object]:
        result = mutations.register_arch_ref(
            ctx.store, ctx.archive,
            assurance_node_id=assurance_node_id,
            arch_artifact_id=arch_artifact_id,
            ref_type=ref_type,
        )
        if isinstance(result, mutations.MutationLocked):
            return ctx.locked_response()
        if isinstance(result, mutations.MutationNotFound):
            return ctx.not_found_response(result.artifact_id)
        return _ok(result)

    @server.tool(
        name="assurance_model_this",
        description=(
            "Propose an architecture entity to bind an unbound-pending control-structure-node. "
            "Returns a structured three-step task spec telling the agent what to call on "
            "arch-repo-write to create the architecture entity, then register the arch reference, "
            "then update binding_status to 'bound'. This assurance-scoped server does NOT modify "
            "the architecture repository — the GUI's create+bind path (POST /api/assurance/model-this) "
            "is the direct-bind alternative."
        ),
    )
    def assurance_model_this(
        assurance_node_id: str,
        suggested_arch_type: str,
        suggested_name: str,
        domain: str = "application",
    ) -> dict[str, object]:
        from src.application import assurance_model_bind as model_bind  # noqa: PLC0415

        if not ctx.is_available():
            return ctx.locked_response()
        # No architecture-write port here (separation of duties): always a task spec.
        result = model_bind.model_and_bind(
            ctx.store, ctx.archive,
            assurance_node_id=assurance_node_id,
            suggested_arch_type=suggested_arch_type,
            suggested_name=suggested_name,
            domain=domain,
            arch_creator=None,
        )
        if isinstance(result, model_bind.BindNotFound):
            return ctx.not_found_response(result.assurance_node_id)
        if isinstance(result, model_bind.BindLocked):
            return ctx.locked_response()
        if isinstance(result, model_bind.BindInvalid):
            return {
                "error": result.error,
                "assurance_node_id": assurance_node_id,
                "message": result.message,
            }
        if isinstance(result, model_bind.TaskRequired):
            return result.spec
        return {  # defensive: Bound never occurs with arch_creator=None
            "outcome": "bound",
            "assurance_node_id": result.assurance_node_id,
            "arch_artifact_id": result.arch_artifact_id,
        }

    @server.tool(
        name="assurance_create_analysis",
        description=(
            "Create an assurance analysis — the aggregate root for a unit of STPA/CAST/GRC work; "
            "every node is created within one analysis. method must be STPA, CAST, or GRC. "
            "architecture_anchor_id is OPTIONAL: the single system-under-analysis element when one "
            "applies (typical for STPA/CAST); leave empty for cross-system work (typical for GRC)."
        ),
    )
    def assurance_create_analysis(
        name: str,
        method: str,
        architecture_anchor_id: str = "",
        tlp: str = "TLP:WHITE",
        status: str = "draft",
    ) -> dict[str, object]:
        from src.application import assurance_analysis as analysis_uc  # noqa: PLC0415

        if not ctx.is_available():
            return ctx.locked_response()
        result = analysis_uc.create_analysis(
            ctx.store, ctx.archive,
            name=name, method=method, architecture_anchor_id=architecture_anchor_id,
            tlp=tlp, status=status,
        )
        return _analysis_result(result, ctx)

    @server.tool(
        name="assurance_update_analysis",
        description=(
            "Update an analysis's name, status (draft/active/completed/archived), or tlp. "
            "method and architecture_anchor_id are immutable (they scope the whole aggregate)."
        ),
    )
    def assurance_update_analysis(
        analysis_id: str,
        name: str | None = None,
        status: str | None = None,
        tlp: str | None = None,
    ) -> dict[str, object]:
        from src.application import assurance_analysis as analysis_uc  # noqa: PLC0415

        if not ctx.is_available():
            return ctx.locked_response()
        result = analysis_uc.update_analysis(
            ctx.store, ctx.archive,
            analysis_id=analysis_id, name=name, status=status, tlp=tlp,
        )
        return _analysis_result(result, ctx)

    @server.tool(
        name="assurance_promotion_preflight",
        description=(
            "Pre-check safety/security assurance-constraints before promoting findings to a "
            "wider audience tier. Blocks promotion if any safety/security constraint is missing "
            "an accountable-to owner OR an evidenced-by connection (§6 promotion pre-check, §23). "
            "Returns a list of blocking issues and a promote_safe flag."
        ),
    )
    def assurance_promotion_preflight(
        node_ids: list[str] | None = None,
    ) -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        from src.application.assurance_promotion import promotion_preflight  # noqa: PLC0415

        return promotion_preflight(ctx.store, node_ids=node_ids)
