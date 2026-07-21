"""Read the ACTIVE signal snapshot's itemized signal data, exposure-filtered.

The single application read surface behind the signal LIST tools (MCP + REST):
components of the active snapshot, and vulnerability findings (optionally scoped to one
component / purl) — always filtered by the exposure policy BEFORE returning, with a
finding only visible when its component is also visible (the same consistency rule
``compute_security_metrics`` applies). Aggregate counts read the snapshot model directly
(operational view; no per-record exposure filter, mirroring the old store stats).
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from src.application.assurance_exposure import AssuranceExposurePolicy


class SnapshotReadStore(Protocol):
    """The signal-snapshot read slice the signal LIST surface needs (segregated port)."""

    def get_active_snapshot(self, anchor_entity_id: str) -> Mapping[str, Any] | None: ...
    def list_snapshot_components(self, snapshot_id: str) -> list[dict[str, Any]]: ...
    def list_snapshot_findings(self, snapshot_id: str) -> list[dict[str, Any]]: ...
    def list_snapshots(self, *, anchor_entity_id: str | None = None) -> list[dict[str, Any]]: ...


def _active_snapshot_id(anchor_entity_id: str, snapshot_store: SnapshotReadStore) -> str | None:
    snapshot = snapshot_store.get_active_snapshot(anchor_entity_id)
    return str(snapshot["snapshot_id"]) if snapshot is not None else None


def list_active_components(
    anchor_entity_id: str, *, snapshot_store: SnapshotReadStore, policy: AssuranceExposurePolicy,
) -> tuple[list[dict[str, Any]], int]:
    """Visible components of the anchor's active snapshot + the withheld count."""
    snapshot_id = _active_snapshot_id(anchor_entity_id, snapshot_store)
    if snapshot_id is None:
        return [], 0
    visible, withheld = policy.filter_security_records(snapshot_store.list_snapshot_components(snapshot_id))
    return visible, withheld


def list_active_findings(
    anchor_entity_id: str,
    *,
    snapshot_store: SnapshotReadStore,
    policy: AssuranceExposurePolicy,
    purl: str | None = None,
    component_id: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Visible findings of the anchor's active snapshot (optionally scoped to one component
    by ``component_id`` or ``purl``), each enriched with its component name/purl. A
    finding is withheld when its component is hidden, so the two stay consistent."""
    snapshot_id = _active_snapshot_id(anchor_entity_id, snapshot_store)
    if snapshot_id is None:
        return [], 0
    visible_components, _ = policy.filter_security_records(snapshot_store.list_snapshot_components(snapshot_id))
    component_by_id = {str(c["component_id"]): c for c in visible_components}
    visible_findings, withheld = policy.filter_security_records(snapshot_store.list_snapshot_findings(snapshot_id))
    out: list[dict[str, Any]] = []
    for finding in visible_findings:
        cid = str(finding["component_id"])
        component = component_by_id.get(cid)
        if component is None:
            withheld += 1  # its component is hidden → the finding is hidden with it
            continue
        if component_id is not None and cid != component_id:
            continue
        if purl is not None and str(component.get("purl") or "") != purl:
            continue
        out.append({
            **dict(finding),
            "component_name": component.get("name"),
            "component_purl": component.get("purl"),
            "component_directness": component.get("directness"),
        })
    return out, withheld


def signals_stats(*, snapshot_store: SnapshotReadStore) -> dict[str, int]:
    """Operational aggregate over the signal-snapshot model (privileged, unfiltered — the
    tool is unlock-gated). Counts snapshots and the components/findings of the active snapshots."""
    snapshots = snapshot_store.list_snapshots()
    active = [r for r in snapshots if str(r["status"]) == "active"]
    components = 0
    findings = 0
    for snapshot in active:
        snapshot_id = str(snapshot["snapshot_id"])
        components += len(snapshot_store.list_snapshot_components(snapshot_id))
        findings += len(snapshot_store.list_snapshot_findings(snapshot_id))
    return {
        "total_snapshots": len(snapshots),
        "active_snapshots": len(active),
        "anchors_with_active_snapshot": len({str(r["anchor_entity_id"]) for r in active}),
        "active_snapshot_components": components,
        "active_snapshot_findings": findings,
    }
