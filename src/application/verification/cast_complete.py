"""§17(B) CAST basic-complete coverage profile checker.

G-g gate: a CAST investigation without a sealed analysis_baseline fails.

Checks:
  - baseline_exists: ≥1 sealed analysis_baseline in the archive (required for reproducibility; G-g)
  - incident_has_investigates: every incident has ≥1 investigates edge (to a CSN or hazard)
  - corrective_action_derives_constraint: every corrective-action has ≥1 derives edge to a constraint
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.assurance_ports import AssuranceArchive, ConfidentialAssuranceStore


def _gap_nodes(
    nodes: list[dict[str, object]],
    node_type: str,
    edges: list[dict[str, object]],
    source_conn: str,
) -> list[dict[str, str]]:
    """Return nodes of *node_type* with no outgoing edge of *source_conn*."""
    gaps: list[dict[str, str]] = []
    for node in nodes:
        if str(node.get("node_type", "")) != node_type:
            continue
        nid = str(node["node_id"])
        count = sum(
            1 for e in edges
            if str(e["source_id"]) == nid and str(e["conn_type"]) == source_conn
        )
        if count < 1:
            gaps.append({"node_id": nid, "name": str(node.get("name", ""))})
    return gaps


def _check(checks: dict[str, dict[str, object]], key: str, gaps: list[dict[str, str]]) -> None:
    checks[key] = {
        "passed": len(gaps) == 0,
        "gap_count": len(gaps),
        "gaps": gaps,
    }


def run_cast_complete(
    store: ConfidentialAssuranceStore,
    archive: AssuranceArchive,
) -> dict[str, object]:
    """Run §17(B) cast-complete checks and return a structured result."""
    all_nodes = store.list_nodes()
    all_edges = store.list_edges()
    baselines = archive.list_baselines()

    incidents = [n for n in all_nodes if str(n.get("node_type", "")) == "incident"]
    has_incidents = len(incidents) > 0

    checks: dict[str, dict[str, object]] = {}

    # G-g: sealed baseline required when incidents exist
    baseline_gap: list[dict[str, str]] = (
        [{"node_id": "", "name": "No sealed baseline found — required for CAST reproducibility (§10)"}]
        if has_incidents and not baselines
        else []
    )
    _check(checks, "baseline_exists", baseline_gap)

    # Every incident must have ≥1 investigates edge
    _check(
        checks,
        "incident_has_investigates",
        _gap_nodes(all_nodes, "incident", all_edges, "investigates"),
    )

    # Every corrective-action must derive ≥1 constraint
    _check(
        checks,
        "corrective_action_derives_constraint",
        _gap_nodes(all_nodes, "corrective-action", all_edges, "derives"),
    )

    all_passed = all(bool(v["passed"]) for v in checks.values())
    total_gaps = sum(int(str(v["gap_count"])) for v in checks.values())
    failed_count = sum(1 for v in checks.values() if not v["passed"])
    summary = (
        "All CAST coverage checks passed."
        if all_passed
        else f"{total_gaps} coverage gap(s) found across {failed_count} check(s)."
    )

    return {
        "passed": all_passed,
        "checks": checks,
        "summary": summary,
        "baseline_count": len(baselines),
        "incident_count": len(incidents),
    }
