"""Pure application-layer query functions for the assurance store.

These functions accept pre-fetched, exposure-filtered node/edge lists and
produce the computed views used by both the HTTP read endpoints and the MCP
dashboard tools. They contain no IO and no store access.
"""

from __future__ import annotations

import json
from typing import Any


def coverage_gaps(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute coverage gaps over an exposure-filtered node/edge set."""
    by_type: dict[str, list[dict[str, Any]]] = {}
    for n in nodes:
        t = str(n.get("node_type", ""))
        by_type.setdefault(t, []).append(n)

    def _has_out(nid: str, conn: str) -> bool:
        return any(str(e["source_id"]) == nid and str(e["conn_type"]) == conn for e in edges)

    def _has_in(nid: str, conn: str) -> bool:
        return any(str(e["target_id"]) == nid and str(e["conn_type"]) == conn for e in edges)

    def _ids(ntype: str, test: Any) -> list[dict[str, str]]:
        return [
            {"node_id": str(n["node_id"]), "name": str(n.get("name", ""))}
            for n in by_type.get(ntype, [])
            if test(str(n["node_id"]))
        ]

    risk_without_treatment = [
        {"node_id": str(n["node_id"]), "name": str(n.get("name", ""))}
        for n in by_type.get("risk", [])
        if not str(
            json.loads(str(n.get("attributes_json") or "{}")).get("treatment") or ""
        ).strip()
    ]
    unbound_csns = [
        {"node_id": str(n["node_id"]), "name": str(n.get("name", ""))}
        for n in by_type.get("control-structure-node", [])
        if str(n.get("binding_status", "")) == "unbound-pending"
    ]

    gaps: dict[str, list[dict[str, str]]] = {
        "constraints_without_evidence": _ids(
            "assurance-constraint", lambda nid: not _has_out(nid, "evidenced-by")
        ),
        "hazards_without_constraints": _ids(
            "hazard", lambda nid: not _has_in(nid, "violates")
        ),
        "obligations_without_constraints": _ids(
            "obligation", lambda nid: not _has_in(nid, "complies-with")
        ),
        "risks_without_treatment": risk_without_treatment,
        "unbound_pending_csns": unbound_csns,
        "orphan_corrective_actions": _ids(
            "corrective-action", lambda nid: not _has_out(nid, "derives")
        ),
    }
    total = sum(len(v) for v in gaps.values())
    categories = sum(1 for v in gaps.values() if v)
    return {
        "total_gaps": total,
        "gaps": gaps,
        "summary": (
            "No coverage gaps found." if total == 0
            else f"{total} coverage gap(s) detected across {categories} category/categories."
        ),
    }


_UNANCHORED_PAGE_SIZE = 50


def aibom_coverage(
    components: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
) -> dict[str, Any]:
    """AI-BOM coverage/gap report over exposure-filtered BOM components and anchors.

    Accepts pre-fetched, exposure-filtered records (no store access). Surfaces BOM
    components with no architecture anchor (not linked to an entity) and the set of
    anchored entity ids, so callers can see where AI-component marking is incomplete.
    """
    unanchored = [c for c in components if not c.get("arch_entity_id")]
    anchor_entity_ids = {str(a["arch_entity_id"]) for a in anchors if a.get("arch_entity_id")}
    return {
        "total_bom_components": len(components),
        "unanchored_components": len(unanchored),
        "unanchored_truncated": len(unanchored) > _UNANCHORED_PAGE_SIZE,
        "anchor_mappings": len(anchors),
        "unanchored": unanchored[:_UNANCHORED_PAGE_SIZE],
        "anchored_entity_ids": sorted(anchor_entity_ids),
        "summary": (
            "All BOM components are linked to an architecture entity." if not unanchored
            else f"{len(unanchored)} BOM component(s) not linked to an architecture entity."
        ),
    }


def risk_register(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Tabular risk register from an exposure-filtered node/edge set."""
    nodes_by_id = {str(n["node_id"]): n for n in nodes}

    def _targets_of(source_id: str, conn: str) -> list[str]:
        return [
            str(e["target_id"]) for e in edges
            if str(e["source_id"]) == source_id and str(e["conn_type"]) == conn
            and str(e["target_id"]) in nodes_by_id
        ]

    rows = []
    for node in nodes:
        if str(node.get("node_type", "")) != "risk":
            continue
        rid = str(node["node_id"])
        attrs: dict[str, object] = {}
        try:
            attrs = json.loads(str(node.get("attributes_json") or "{}"))
        except Exception:  # noqa: BLE001
            pass

        def _refs(ids: list[str]) -> list[dict[str, str]]:
            return [
                {"node_id": i, "name": str(nodes_by_id[i].get("name", ""))}
                for i in ids
            ]

        rows.append({
            "node_id": rid,
            "name": str(node.get("name", "")),
            "status": str(node.get("status", "")),
            "treatment": str(attrs.get("treatment") or ""),
            "likelihood": str(attrs.get("likelihood") or ""),
            "impact": str(attrs.get("impact") or ""),
            "risk_score": str(attrs.get("risk_score") or ""),
            "assesses": _refs(_targets_of(rid, "assesses")),
            "treated_by": _refs(_targets_of(rid, "treated-by")),
            "owners": _refs(_targets_of(rid, "accountable-to")),
        })
    return {"risks": rows, "count": len(rows)}
