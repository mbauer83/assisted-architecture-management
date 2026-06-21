"""Shared assurance mutation use cases (application layer).

Each function enforces the three-step write protocol:
  1. Check the store is unlocked → MutationLocked if not.
  2. Perform the write on the store.
  3. Append to the audit log.
  4. Run the post-write verifier; return findings in the result.

Writes are NEVER blocked by the verifier — findings are informational.
The safety-disposition safeguard (E503) surfaces as a teaching message in the
findings list when disposition='accepted' is set on a safety/security constraint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.application.assurance_ports import AssuranceArchive, ConfidentialAssuranceStore

# ── Vocabulary (mirrors write_tools.py) ────────────────────────────────────────

VALID_NODE_TYPES: frozenset[str] = frozenset({
    "loss", "hazard", "control-structure-node", "control-action",
    "unsafe-control-action", "loss-scenario", "assurance-constraint",
    "risk", "incident", "corrective-action", "obligation",
})

VALID_CONN_TYPES: frozenset[str] = frozenset({
    "issues", "acts-on", "feedback", "concerns", "by-controller", "violates",
    "leads-to", "explains", "derives", "refines", "satisfied-by", "accountable-to",
    "responsible-of", "evidenced-by", "assesses", "treated-by", "complies-with",
    "cites", "binds-to", "investigates",
})

# ── Typed outcomes ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MutationOk:
    """Write succeeded; payload is the operation result; findings from post-write verify."""

    payload: dict[str, Any]
    findings: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class MutationLocked:
    """Store not unlocked; translate to HTTP 423 / MCP locked envelope."""


@dataclass(frozen=True)
class MutationNotFound:
    """Node/edge absent; translate to HTTP 404 / MCP not_found."""

    artifact_id: str


MutationResult = MutationOk | MutationLocked | MutationNotFound

# ── Post-write verification ────────────────────────────────────────────────────


def _post_write_findings(
    store: ConfidentialAssuranceStore,
    *,
    node_id: str | None = None,
) -> list[dict[str, Any]]:
    """Run the full verifier; return findings scoped to node_id (or all when None)."""
    from src.application.verification.assurance_verifier import verify_store  # noqa: PLC0415

    result = verify_store(store)
    issues = [
        {
            "severity": i.severity,
            "code": i.code,
            "message": i.message,
            "node_id": i.node_id,
        }
        for i in result.issues
    ]
    if node_id is not None:
        issues = [f for f in issues if not f["node_id"] or f["node_id"] == node_id]
    return issues


# ── Use cases ──────────────────────────────────────────────────────────────────


def create_node(
    store: ConfidentialAssuranceStore,
    archive: AssuranceArchive,
    *,
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
) -> MutationResult:
    if not store.is_unlocked():
        return MutationLocked()
    if node_type not in VALID_NODE_TYPES:
        return MutationOk(
            payload={
                "error": "invalid_node_type",
                "node_type": node_type,
                "valid_types": sorted(VALID_NODE_TYPES),
            },
            findings=[],
        )
    node_id = store.create_node(
        node_type, name,
        status=status, tlp=tlp,
        concern_class=concern_class, disposition=disposition,
        uca_type=uca_type, binding_status=binding_status,
        node_role=node_role, analysis_id=analysis_id, content=content_text,
        attributes=attributes,
    )
    archive.append(
        "CREATE", node_id=node_id,
        payload={"node_type": node_type, "name": name, "status": status},
    )
    return MutationOk(
        payload={"node_id": node_id, "node_type": node_type, "name": name},
        findings=_post_write_findings(store, node_id=node_id),
    )


def edit_node(
    store: ConfidentialAssuranceStore,
    archive: AssuranceArchive,
    *,
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
) -> MutationResult:
    if not store.is_unlocked():
        return MutationLocked()
    if store.get_node(node_id) is None:
        return MutationNotFound(node_id)
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
        store.update_node(node_id, **updates)
        archive.append("UPDATE", node_id=node_id, payload={"updated_fields": list(updates)})
    return MutationOk(
        payload={"node_id": node_id, "updated": list(updates)},
        findings=_post_write_findings(store, node_id=node_id),
    )


def delete_node(
    store: ConfidentialAssuranceStore,
    archive: AssuranceArchive,
    *,
    node_id: str,
) -> MutationResult:
    if not store.is_unlocked():
        return MutationLocked()
    node = store.get_node(node_id)
    if node is None:
        return MutationNotFound(node_id)
    store.delete_node(node_id)
    archive.append("DELETE", node_id=node_id, payload={"node_type": node.get("node_type")})
    return MutationOk(payload={"deleted": node_id}, findings=[])


def add_edge(
    store: ConfidentialAssuranceStore,
    archive: AssuranceArchive,
    *,
    source_id: str,
    target_id: str,
    conn_type: str,
    attributes: dict[str, object] | None = None,
) -> MutationResult:
    if not store.is_unlocked():
        return MutationLocked()
    if store.get_node(source_id) is None:
        return MutationNotFound(source_id)
    if store.get_node(target_id) is None:
        return MutationNotFound(target_id)
    edge_id = store.add_edge(source_id, target_id, conn_type, attributes=attributes)
    archive.append("ADD_EDGE", payload={
        "edge_id": edge_id, "source_id": source_id,
        "target_id": target_id, "conn_type": conn_type,
    })
    return MutationOk(
        payload={
            "edge_id": edge_id, "source_id": source_id,
            "target_id": target_id, "conn_type": conn_type,
        },
        findings=_post_write_findings(store, node_id=source_id),
    )


def delete_edge(
    store: ConfidentialAssuranceStore,
    archive: AssuranceArchive,
    *,
    edge_id: str,
) -> MutationResult:
    if not store.is_unlocked():
        return MutationLocked()
    all_edges = store.list_edges()
    edge = next((e for e in all_edges if str(e.get("edge_id", "")) == edge_id), None)
    if edge is None:
        return MutationNotFound(edge_id)
    store.remove_edge(edge_id)
    archive.append("DELETE_EDGE", payload={
        "edge_id": edge_id,
        "source_id": edge.get("source_id"),
        "target_id": edge.get("target_id"),
    })
    return MutationOk(payload={"deleted": edge_id}, findings=[])


def register_arch_ref(
    store: ConfidentialAssuranceStore,
    archive: AssuranceArchive,
    *,
    assurance_node_id: str,
    arch_artifact_id: str,
    ref_type: str,
) -> MutationResult:
    if not store.is_unlocked():
        return MutationLocked()
    if store.get_node(assurance_node_id) is None:
        return MutationNotFound(assurance_node_id)
    store.register_arch_ref(assurance_node_id, arch_artifact_id, ref_type)
    archive.append("ADD_ARCH_REF", node_id=assurance_node_id, payload={
        "arch_artifact_id": arch_artifact_id, "ref_type": ref_type,
    })
    return MutationOk(
        payload={
            "assurance_node_id": assurance_node_id,
            "arch_artifact_id": arch_artifact_id,
            "ref_type": ref_type,
            "status": "registered",
        },
        findings=_post_write_findings(store, node_id=assurance_node_id),
    )
