"""Read the ACTIVE refresh run's itemized signal data, exposure-filtered.

The single application read surface behind the signal LIST tools (MCP + REST):
components of the active run, and vulnerability findings (optionally scoped to one
component / purl) — always filtered by the exposure policy BEFORE returning, with a
finding only visible when its component is also visible (the same consistency rule
``compute_security_metrics`` applies). Aggregate counts read the run model directly
(operational view; no per-record exposure filter, mirroring the old store stats).
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from src.application.assurance_exposure import AssuranceExposurePolicy


class RefreshRunReadStore(Protocol):
    """The refresh-run read slice the signal LIST surface needs (segregated port)."""

    def get_active_run(self, anchor_entity_id: str) -> Mapping[str, Any] | None: ...
    def list_run_components(self, run_id: str) -> list[dict[str, Any]]: ...
    def list_run_findings(self, run_id: str) -> list[dict[str, Any]]: ...
    def list_runs(self, *, anchor_entity_id: str | None = None) -> list[dict[str, Any]]: ...


def _active_run_id(anchor_entity_id: str, run_store: RefreshRunReadStore) -> str | None:
    run = run_store.get_active_run(anchor_entity_id)
    return str(run["run_id"]) if run is not None else None


def list_active_components(
    anchor_entity_id: str, *, run_store: RefreshRunReadStore, policy: AssuranceExposurePolicy,
) -> tuple[list[dict[str, Any]], int]:
    """Visible components of the anchor's active run + the withheld count."""
    run_id = _active_run_id(anchor_entity_id, run_store)
    if run_id is None:
        return [], 0
    visible, withheld = policy.filter_security_records(run_store.list_run_components(run_id))
    return visible, withheld


def list_active_findings(
    anchor_entity_id: str,
    *,
    run_store: RefreshRunReadStore,
    policy: AssuranceExposurePolicy,
    purl: str | None = None,
    component_id: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Visible findings of the anchor's active run (optionally scoped to one component
    by ``component_id`` or ``purl``), each enriched with its component name/purl. A
    finding is withheld when its component is hidden, so the two stay consistent."""
    run_id = _active_run_id(anchor_entity_id, run_store)
    if run_id is None:
        return [], 0
    visible_components, _ = policy.filter_security_records(run_store.list_run_components(run_id))
    component_by_id = {str(c["component_id"]): c for c in visible_components}
    visible_findings, withheld = policy.filter_security_records(run_store.list_run_findings(run_id))
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


def signals_stats(*, run_store: RefreshRunReadStore) -> dict[str, int]:
    """Operational aggregate over the refresh-run model (privileged, unfiltered — the
    tool is unlock-gated). Counts runs and the components/findings of the active runs."""
    runs = run_store.list_runs()
    active = [r for r in runs if str(r["status"]) == "active"]
    components = 0
    findings = 0
    for run in active:
        run_id = str(run["run_id"])
        components += len(run_store.list_run_components(run_id))
        findings += len(run_store.list_run_findings(run_id))
    return {
        "total_runs": len(runs),
        "active_runs": len(active),
        "anchors_with_active_run": len({str(r["anchor_entity_id"]) for r in active}),
        "active_run_components": components,
        "active_run_findings": findings,
    }
