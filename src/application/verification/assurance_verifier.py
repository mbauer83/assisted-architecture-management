"""Assurance verifier — §17(A) hard structural validity rules.

Separate from the architecture ArtifactVerifier. Operates on the
ConfidentialAssuranceStore (not git-backed files). Rules return AssuranceIssue
objects with codes in the E5xx/W5xx range.

Hard rules (always enforced, block sign-off):
  E501 — UCA must reference exactly one control-action (concerns edge)
  E502 — safety/security assurance-constraint must have a responsible controller (incoming responsible-for)
  E504 — edge references a nonexistent node (dangling endpoint; such edges are
         omitted from every navigation surface and reported only here)
  E503 — disposition=accepted on safety/security requires justification + sign-off
  E504 — risk.treatment=accept cannot be sole disposition for a safety hazard
  E505 — incident has no investigates edge (CAST investigation incomplete)

Informational findings (W5xx — never block writes):
  W501 — control-structure-node with binding_status=unbound-pending (modeling gap)
  W502 — assurance-constraint with no evidence (edge to an evidence node or evidenced-by-artifact arch ref)
  W503 — hazard with no leads-to loss connection
  W504 — obligation with no complies-with constraint (coverage gap)
  W505 — risk with no treatment attribute set
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from src.application.assurance_ports import ConfidentialAssuranceStore

SeverityLiteral = Literal["error", "warning"]

_SAFETY_CLASSES = frozenset({"safety", "security"})
_ACCEPT_SAFETY_DISPOSITIONS = frozenset({
    "eliminated", "prevented-by-design", "controlled-with-evidence", "alarp-justified",
})


@dataclass(frozen=True)
class AssuranceIssue:
    severity: SeverityLiteral
    code: str
    message: str
    node_id: str = ""


@dataclass
class AssuranceVerificationResult:
    issues: list[AssuranceIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def errors(self) -> list[AssuranceIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[AssuranceIssue]:
        return [i for i in self.issues if i.severity == "warning"]


def _check_uca_has_control_action(
    node: dict[str, object],
    edges: list[dict[str, object]],
    result: AssuranceVerificationResult,
) -> None:
    """E501: every UCA must reference exactly one control-action via 'concerns'."""
    node_id = str(node["node_id"])
    concerns_edges = [e for e in edges if str(e["source_id"]) == node_id and str(e["conn_type"]) == "concerns"]
    if len(concerns_edges) == 0:
        result.issues.append(AssuranceIssue(
            severity="error",
            code="E501",
            message="UCA must reference exactly one control-action via a 'concerns' edge.",
            node_id=node_id,
        ))
    elif len(concerns_edges) > 1:
        result.issues.append(AssuranceIssue(
            severity="error",
            code="E501",
            message=f"UCA must reference exactly ONE control-action; found {len(concerns_edges)}.",
            node_id=node_id,
        ))


def _check_constraint_has_owner(
    node: dict[str, object],
    edges: list[dict[str, object]],
    result: AssuranceVerificationResult,
) -> None:
    """E502: a safety/security assurance-constraint must have a responsible controller
    (incoming responsible-for — responsibilities assigned to control-structure entities
    refine the system-level constraints)."""
    node_id = str(node["node_id"])
    concern_class = str(node.get("concern_class") or "")
    if concern_class not in _SAFETY_CLASSES:
        return
    owner_edges = [
        e for e in edges
        if str(e["target_id"]) == node_id and str(e["conn_type"]) == "responsible-for"
    ]
    if not owner_edges:
        result.issues.append(AssuranceIssue(
            severity="error",
            code="E502",
            message=(
                f"Safety/security assurance-constraint ({concern_class}) must have an incoming "
                "'responsible-for' connection from the controller responsible for enforcing it."
            ),
            node_id=node_id,
        ))


def _check_accepted_disposition(
    node: dict[str, object],
    edges: list[dict[str, object]],
    result: AssuranceVerificationResult,
) -> None:
    """E503: disposition=accepted on safety/security requires justification doc + sign-off."""
    node_id = str(node["node_id"])
    concern_class = str(node.get("concern_class") or "")
    disposition = str(node.get("disposition") or "")
    if concern_class not in _SAFETY_CLASSES:
        return
    if disposition != "accepted":
        return
    result.issues.append(AssuranceIssue(
        severity="error",
        code="E503",
        message=(
            f"disposition='accepted' is rejected for {concern_class} constraints. "
            "Use 'eliminated', 'prevented-by-design', 'controlled-with-evidence', or "
            "'alarp-justified'. The safety-subordination safeguard (§2.1) prevents "
            "pricing away safety obligations via risk acceptance."
        ),
        node_id=node_id,
    ))


def _check_risk_not_sole_accept_for_safety(
    risk_node: dict[str, object],
    all_nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
    result: AssuranceVerificationResult,
) -> None:
    """E504: risk.treatment=accept cannot be sole disposition of a safety hazard."""
    import json as _json  # noqa: PLC0415

    node_id = str(risk_node["node_id"])
    attrs_raw = risk_node.get("attributes_json") or "{}"
    try:
        attrs: dict[str, object] = _json.loads(str(attrs_raw))
    except Exception:  # noqa: BLE001
        attrs = {}
    treatment = str(attrs.get("treatment") or "")
    if treatment != "accept":
        return
    assesses_edges = [e for e in edges if str(e["source_id"]) == node_id and str(e["conn_type"]) == "assesses"]
    hazard_ids = {str(e["target_id"]) for e in assesses_edges}
    nodes_by_id = {str(n["node_id"]): n for n in all_nodes}
    for haz_id in hazard_ids:
        haz = nodes_by_id.get(haz_id)
        if haz and str(haz.get("concern_class") or "") in _SAFETY_CLASSES:
            treated_edges = [
                e for e in edges if str(e["source_id"]) == node_id and str(e["conn_type"]) == "treated-by"
            ]
            if not treated_edges:
                result.issues.append(AssuranceIssue(
                    severity="error",
                    code="E504",
                    message=(
                        "risk.treatment='accept' cannot be the sole disposition of a safety hazard. "
                        "The risk must be treated-by at least one assurance-constraint."
                    ),
                    node_id=node_id,
                ))


def _check_unbound_nodes(
    node: dict[str, object],
    result: AssuranceVerificationResult,
) -> None:
    """W501: modeling-gap finding for unbound-pending control-structure-nodes."""
    node_id = str(node["node_id"])
    binding_status = str(node.get("binding_status") or "")
    if binding_status == "unbound-pending":
        result.issues.append(AssuranceIssue(
            severity="warning",
            code="W501",
            message=(
                "control-structure-node has binding_status='unbound-pending': "
                "this node is not linked to an architecture entity. "
                "Consider using the 'model this' workflow (§7.1) to bind it."
            ),
            node_id=node_id,
        ))


def _check_constraint_has_evidence(
    node: dict[str, object],
    edges: list[dict[str, object]],
    evidenced_ref_node_ids: set[str],
    result: AssuranceVerificationResult,
) -> None:
    """W502: assurance-constraint with no evidence — neither an evidenced-by edge to
    an evidence node nor an evidenced-by-artifact architecture reference."""
    node_id = str(node["node_id"])
    ev_edges = [e for e in edges if str(e["source_id"]) == node_id and str(e["conn_type"]) == "evidenced-by"]
    if not ev_edges and node_id not in evidenced_ref_node_ids:
        result.issues.append(AssuranceIssue(
            severity="warning",
            code="W502",
            message=(
                "Assurance constraint has no evidence: add an 'evidenced-by' connection to an "
                "evidence node, or an 'evidenced-by-artifact' architecture reference."
            ),
            node_id=node_id,
        ))


def _check_hazard_has_loss(
    node: dict[str, object],
    edges: list[dict[str, object]],
    result: AssuranceVerificationResult,
) -> None:
    """W503: hazard not connected to any loss."""
    node_id = str(node["node_id"])
    leads_to = [e for e in edges if str(e["source_id"]) == node_id and str(e["conn_type"]) == "leads-to"]
    if not leads_to:
        result.issues.append(AssuranceIssue(
            severity="warning",
            code="W503",
            message="Hazard has no 'leads-to' connection to a loss. Connect it to complete the STPA chain.",
            node_id=node_id,
        ))


def _check_incident_has_investigates(
    node: dict[str, object],
    edges: list[dict[str, object]],
    result: AssuranceVerificationResult,
) -> None:
    """E505: incident must have at least one investigates edge."""
    node_id = str(node["node_id"])
    has_inv = any(str(e["source_id"]) == node_id and str(e["conn_type"]) == "investigates" for e in edges)
    if not has_inv:
        result.issues.append(AssuranceIssue(
            severity="error",
            code="E505",
            message=(
                "CAST incident has no 'investigates' edge. "
                "Connect it to a control-structure-node or hazard (§10)."
            ),
            node_id=node_id,
        ))


def _check_obligation_has_constraint(
    node: dict[str, object],
    edges: list[dict[str, object]],
    result: AssuranceVerificationResult,
) -> None:
    """W504: obligation with no complies-with constraint (coverage gap)."""
    node_id = str(node["node_id"])
    linked = any(str(e["target_id"]) == node_id and str(e["conn_type"]) == "complies-with" for e in edges)
    if not linked:
        result.issues.append(AssuranceIssue(
            severity="warning",
            code="W504",
            message="Obligation has no 'complies-with' constraint. Link one to close the compliance gap.",
            node_id=node_id,
        ))


def _check_risk_has_treatment(
    node: dict[str, object],
    result: AssuranceVerificationResult,
) -> None:
    """W505: risk with no treatment attribute set."""
    import json as _json  # noqa: PLC0415

    node_id = str(node["node_id"])
    attrs_raw = node.get("attributes_json") or "{}"
    try:
        attrs: dict[str, object] = _json.loads(str(attrs_raw))
    except Exception:  # noqa: BLE001
        attrs = {}
    if not str(attrs.get("treatment") or "").strip():
        result.issues.append(AssuranceIssue(
            severity="warning",
            code="W505",
            message="Risk has no 'treatment' attribute. Set to: mitigate | transfer | avoid | accept.",
            node_id=node_id,
        ))


def _check_dangling_edges(
    all_nodes: list[dict[str, object]],
    all_edges: list[dict[str, object]],
    result: AssuranceVerificationResult,
) -> None:
    """E504: an edge whose source or target no longer exists. Navigation surfaces
    omit such edges silently (indistinguishable from a hidden endpoint), so the
    verifier is deliberately the only place they become visible."""
    node_ids = {str(n["node_id"]) for n in all_nodes}
    for edge in all_edges:
        source_id = str(edge.get("source_id", ""))
        target_id = str(edge.get("target_id", ""))
        missing = [nid for nid in (source_id, target_id) if nid not in node_ids]
        if missing:
            result.issues.append(AssuranceIssue(
                severity="error",
                code="E504",
                message=(
                    f"Edge {edge.get('edge_id', '?')} ({edge.get('conn_type', '?')}) references "
                    f"nonexistent node(s): {', '.join(missing)}. Delete the edge or restore the node."
                ),
                node_id=source_id if source_id in node_ids else target_id if target_id in node_ids else "",
            ))


def verify_store(store: ConfidentialAssuranceStore) -> AssuranceVerificationResult:
    """Run all §17(A) hard validity + informational checks on the assurance store."""
    result = AssuranceVerificationResult()
    if not store.is_unlocked():
        result.issues.append(AssuranceIssue(
            severity="error",
            code="E500",
            message="Assurance store is locked. Run `arch-assurance unlock` to verify.",
        ))
        return result

    all_nodes = store.list_nodes()
    all_edges = store.list_edges()
    evidenced_ref_node_ids = {
        str(r["assurance_node_id"])
        for r in store.list_arch_refs()
        if str(r.get("ref_type")) == "evidenced-by-artifact"
    }

    _check_dangling_edges(all_nodes, all_edges, result)

    for node in all_nodes:
        ntype = str(node.get("node_type", ""))

        if ntype == "unsafe-control-action":
            _check_uca_has_control_action(node, all_edges, result)

        if ntype == "assurance-constraint":
            _check_constraint_has_owner(node, all_edges, result)
            _check_accepted_disposition(node, all_edges, result)
            _check_constraint_has_evidence(node, all_edges, evidenced_ref_node_ids, result)

        if ntype == "risk":
            _check_risk_not_sole_accept_for_safety(node, all_nodes, all_edges, result)
            _check_risk_has_treatment(node, result)

        if ntype == "control-structure-node":
            _check_unbound_nodes(node, result)

        if ntype == "hazard":
            _check_hazard_has_loss(node, all_edges, result)

        if ntype == "incident":
            _check_incident_has_investigates(node, all_edges, result)

        if ntype == "obligation":
            _check_obligation_has_constraint(node, all_edges, result)

    return result


def format_result(result: AssuranceVerificationResult) -> dict[str, object]:
    return {
        "valid": result.valid,
        "error_count": len(result.errors),
        "warning_count": len(result.warnings),
        "issues": [
            {"severity": i.severity, "code": i.code, "message": i.message, "node_id": i.node_id}
            for i in result.issues
        ],
    }
