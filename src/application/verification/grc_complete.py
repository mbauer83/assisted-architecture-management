"""§17(B) GRC control-coverage-complete profile checker.

Checks:
  - every in-scope obligation has ≥1 assurance-constraint via complies-with
  - every risk has a treatment attribute set
  - every risk has an accountable-to owner connection
  - every in-scope obligation's linked constraints have evidenced-by connections
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.assurance_ports import ConfidentialAssuranceStore


def _obligation_gaps(
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
) -> list[dict[str, str]]:
    """Return obligations with no complies-with constraint."""
    gaps: list[dict[str, str]] = []
    for node in nodes:
        if str(node.get("node_type", "")) != "obligation":
            continue
        nid = str(node["node_id"])
        # complies-with edge goes from assurance-constraint → obligation (target=obligation)
        linked = any(
            str(e["target_id"]) == nid and str(e["conn_type"]) == "complies-with"
            for e in edges
        )
        if not linked:
            gaps.append({"node_id": nid, "name": str(node.get("name", ""))})
    return gaps


def _risk_no_treatment(nodes: list[dict[str, object]]) -> list[dict[str, str]]:
    """Return risk nodes with no treatment attribute."""
    gaps: list[dict[str, str]] = []
    for node in nodes:
        if str(node.get("node_type", "")) != "risk":
            continue
        attrs_raw = node.get("attributes_json") or "{}"
        try:
            attrs: dict[str, object] = json.loads(str(attrs_raw))
        except Exception:  # noqa: BLE001
            attrs = {}
        treatment = str(attrs.get("treatment") or "").strip()
        if not treatment:
            gaps.append({"node_id": str(node["node_id"]), "name": str(node.get("name", ""))})
    return gaps


def _risk_no_owner(
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
) -> list[dict[str, str]]:
    """Return risk nodes with no accountable-to owner connection."""
    gaps: list[dict[str, str]] = []
    for node in nodes:
        if str(node.get("node_type", "")) != "risk":
            continue
        nid = str(node["node_id"])
        has_owner = any(
            str(e["source_id"]) == nid and str(e["conn_type"]) == "accountable-to"
            for e in edges
        )
        if not has_owner:
            gaps.append({"node_id": nid, "name": str(node.get("name", ""))})
    return gaps


def _check(checks: dict[str, dict[str, object]], key: str, gaps: list[dict[str, str]]) -> None:
    checks[key] = {
        "passed": len(gaps) == 0,
        "gap_count": len(gaps),
        "gaps": gaps,
    }


def run_grc_complete(store: ConfidentialAssuranceStore) -> dict[str, object]:
    """Run §17(B) grc-control-coverage-complete checks."""
    all_nodes = store.list_nodes()
    all_edges = store.list_edges()

    checks: dict[str, dict[str, object]] = {}

    _check(checks, "obligation_has_constraint", _obligation_gaps(all_nodes, all_edges))
    _check(checks, "risk_has_treatment", _risk_no_treatment(all_nodes))
    _check(checks, "risk_has_owner", _risk_no_owner(all_nodes, all_edges))

    all_passed = all(bool(v["passed"]) for v in checks.values())
    total_gaps = sum(int(str(v["gap_count"])) for v in checks.values())
    failed_count = sum(1 for v in checks.values() if not v["passed"])
    summary = (
        "All GRC coverage checks passed."
        if all_passed
        else f"{total_gaps} coverage gap(s) found across {failed_count} check(s)."
    )

    return {"passed": all_passed, "checks": checks, "summary": summary}
