"""Assurance write MCP tools.

Tools registered on arch-assurance-write:
  assurance_create_node         — create any assurance entity
  assurance_add_edge            — add a typed assurance connection
  assurance_edit_node           — update node attributes
  assurance_delete_node         — delete a node (cascades edges)
  assurance_seal_baseline       — seal a signed analysis baseline
  assurance_register_arch_ref   — record an assurance→architecture reference
  assurance_model_this          — propose architecture entity to bind an unbound-pending CSN
  assurance_promotion_preflight — pre-check safety/security constraints before promotion
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.assurance_mcp.context import get_assurance_context

_VALID_NODE_TYPES = frozenset({
    "loss", "hazard", "control-structure-node", "control-action",
    "unsafe-control-action", "loss-scenario", "assurance-constraint",
    "risk", "incident", "corrective-action", "obligation",
})


def register_write_tools(server: FastMCP) -> None:
    ctx = get_assurance_context()

    @server.tool(
        name="assurance_create_node",
        description=(
            "Create an assurance entity (loss, hazard, control-structure-node, control-action, "
            "unsafe-control-action, loss-scenario, assurance-constraint, risk, incident, "
            "corrective-action, obligation). "
            "Returns the new node_id. All writes are appended to the audit log."
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
        content_text: str = "",
        attributes: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        if node_type not in _VALID_NODE_TYPES:
            return {
                "error": "invalid_node_type",
                "node_type": node_type,
                "valid_types": sorted(_VALID_NODE_TYPES),
            }
        node_id = ctx.store.create_node(
            node_type,
            name,
            status=status,
            tlp=tlp,
            concern_class=concern_class,
            disposition=disposition,
            uca_type=uca_type,
            binding_status=binding_status,
            node_role=node_role,
            content=content_text,
            attributes=attributes,
        )
        ctx.archive.append(
            "CREATE",
            node_id=node_id,
            payload={"node_type": node_type, "name": name, "status": status},
        )
        return {"node_id": node_id, "node_type": node_type, "name": name}

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
        if not ctx.is_available():
            return ctx.locked_response()
        if ctx.store.get_node(source_id) is None:
            return ctx.not_found_response(source_id)
        if ctx.store.get_node(target_id) is None:
            return ctx.not_found_response(target_id)
        edge_id = ctx.store.add_edge(source_id, target_id, conn_type, attributes=attributes)
        ctx.archive.append(
            "ADD_EDGE",
            payload={"edge_id": edge_id, "source_id": source_id, "target_id": target_id, "conn_type": conn_type},
        )
        return {"edge_id": edge_id, "source_id": source_id, "target_id": target_id, "conn_type": conn_type}

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
        if not ctx.is_available():
            return ctx.locked_response()
        if ctx.store.get_node(node_id) is None:
            return ctx.not_found_response(node_id)
        updates: dict[str, object] = {}
        for field_name, value in [
            ("name", name), ("status", status), ("tlp", tlp),
            ("concern_class", concern_class), ("disposition", disposition),
            ("uca_type", uca_type), ("binding_status", binding_status),
            ("node_role", node_role), ("content_text", content_text),
        ]:
            if value is not None:
                updates[field_name] = value
        if attributes is not None:
            updates["attributes"] = attributes
        if updates:
            ctx.store.update_node(node_id, **updates)
            ctx.archive.append("UPDATE", node_id=node_id, payload={"updated_fields": list(updates)})
        return {"node_id": node_id, "updated": list(updates)}

    @server.tool(
        name="assurance_delete_node",
        description=(
            "Delete an assurance node and all its incoming/outgoing edges. "
            "This action is logged in the audit trail but is not reversible."
        ),
    )
    def assurance_delete_node(node_id: str) -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        node = ctx.store.get_node(node_id)
        if node is None:
            return ctx.not_found_response(node_id)
        ctx.store.delete_node(node_id)
        ctx.archive.append("DELETE", node_id=node_id, payload={"node_type": node.get("node_type")})
        return {"deleted": node_id}

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
        if not ctx.is_available():
            return ctx.locked_response()
        if ctx.store.get_node(assurance_node_id) is None:
            return ctx.not_found_response(assurance_node_id)
        ctx.store.register_arch_ref(assurance_node_id, arch_artifact_id, ref_type)
        ctx.archive.append(
            "ADD_ARCH_REF",
            node_id=assurance_node_id,
            payload={"arch_artifact_id": arch_artifact_id, "ref_type": ref_type},
        )
        return {
            "assurance_node_id": assurance_node_id,
            "arch_artifact_id": arch_artifact_id,
            "ref_type": ref_type,
            "status": "registered",
        }

    @server.tool(
        name="assurance_model_this",
        description=(
            "Propose an architecture entity to bind an unbound-pending control-structure-node. "
            "Returns a structured three-step task spec telling the agent what to call on "
            "arch-repo-write to create the architecture entity, then register the arch reference, "
            "then update binding_status to 'bound'. Does NOT modify any state itself."
        ),
    )
    def assurance_model_this(
        assurance_node_id: str,
        suggested_arch_type: str,
        suggested_name: str,
        domain: str = "application",
    ) -> dict[str, object]:
        if not ctx.is_available():
            return ctx.locked_response()
        node = ctx.store.get_node(assurance_node_id)
        if node is None:
            return ctx.not_found_response(assurance_node_id)
        binding_status = str(node.get("binding_status") or "")
        if binding_status != "unbound-pending":
            return {
                "error": "invalid_binding_status",
                "assurance_node_id": assurance_node_id,
                "current_binding_status": binding_status,
                "message": (
                    "assurance_model_this only applies to nodes with "
                    "binding_status='unbound-pending'."
                ),
            }
        node_name = str(node.get("name", ""))
        return {
            "assurance_node_id": assurance_node_id,
            "assurance_node_name": node_name,
            "action_required": "create_arch_entity_then_bind",
            "step_1": {
                "call": "artifact_create_entity",
                "on_server": "arch-repo-write",
                "params": {
                    "artifact_type": suggested_arch_type,
                    "name": suggested_name,
                    "domain": domain,
                    "dry_run": True,
                },
                "note": (
                    "Call with dry_run=true first to preview, then false to create. "
                    "Capture the returned entity_id for step 2."
                ),
            },
            "step_2": {
                "call": "assurance_register_arch_ref",
                "on_server": "arch-assurance-write",
                "params": {
                    "assurance_node_id": assurance_node_id,
                    "arch_artifact_id": "<entity_id_from_step_1>",
                    "ref_type": "binds-to",
                },
            },
            "step_3": {
                "call": "assurance_edit_node",
                "on_server": "arch-assurance-write",
                "params": {
                    "node_id": assurance_node_id,
                    "binding_status": "bound",
                },
            },
        }

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
