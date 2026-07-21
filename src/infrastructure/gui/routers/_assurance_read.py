"""Unlock-gated HTTP read endpoints for the confidential assurance store.

All endpoints share one pattern:
  1. Build an AssuranceExposurePolicy from the current context.
  2. Check locked → 423 with Cache-Control: no-store.
  3. Fetch from the store/archive/connector.
  4. Apply the policy (filter, redact, apply_node).
  5. Return with Cache-Control: no-store.

Response semantics (per the AssuranceExposurePolicy contract):
  - Locked store           → 423 Locked
  - Collection reads       → omit above-ceiling records; visibility_limited flag
  - Direct read (/nodes/:id) → 404 for absent AND above-ceiling (indistinguishable)
  - HTTP 403               → never on reads (would disclose existence)
  - All responses          → Cache-Control: no-store
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse

from src.application.assurance_diagrams import (
    AVAILABLE_DIAGRAMS,
    bowtie_nodes,
    render_bowtie,
    render_control_structure,
    uca_matrix_nodes,
)
from src.application.assurance_edge_enrichment import enrich_edges, visible_nodes_by_id
from src.application.assurance_exposure import AssuranceExposurePolicy, Visible
from src.application.assurance_queries import coverage_gaps, risk_register
from src.infrastructure.gui.routers._assurance_http import locked_response as _locked_response
from src.infrastructure.gui.routers._assurance_http import not_found_response as _not_found_response
from src.infrastructure.gui.routers._assurance_http import ok as _ok
from src.infrastructure.mcp.assurance_mcp.context import AssuranceContext, get_assurance_context

logger = logging.getLogger(__name__)

read_router = APIRouter()

_NO_STORE = "no-store"


def _policy() -> tuple[AssuranceContext, AssuranceExposurePolicy]:
    # Defined locally (not imported) so the context lookup is patched at this module.
    ctx = get_assurance_context()
    return ctx, AssuranceExposurePolicy(ctx.max_classification, ctx.is_available())


# ── Search ────────────────────────────────────────────────────────────────────

def _assurance_hit(node: dict[str, object]) -> dict[str, object]:
    """Shape a visible assurance node into the standard SearchHit envelope.

    Content snippets are intentionally excluded — they may contain classified text.
    """
    return {
        "score": 1.0,
        "record_type": "assurance-node",
        "artifact_id": str(node["node_id"]),
        "name": str(node.get("name", "")),
        "artifact_type": str(node.get("node_type", "")),
        "status": str(node.get("status", "")),
        "path": "",
    }


@read_router.get("/api/assurance/search")
def search_assurance_nodes(
    q: str,
    limit: int = Query(default=20, le=100),
) -> JSONResponse:
    ctx, pol = _policy()
    if pol.check_locked():
        return _locked_response()
    if not q.strip():
        return _ok({"query": q, "hits": [], "count": 0})
    raw = ctx.store.search_nodes(q.strip(), limit=limit * 2)
    visible, _ = pol.filter_nodes(raw)
    hits = [_assurance_hit(n) for n in visible[:limit]]
    logger.info("assurance_search: ceiling=%s hits=%d (redacted telemetry)", pol.scope().ceiling, len(hits))
    return _ok({"query": q, "hits": hits, "count": len(hits)})


# ── Nodes ─────────────────────────────────────────────────────────────────────

@read_router.get("/api/assurance/nodes")
def list_assurance_nodes(
    node_type: str | None = None,
    status: str | None = None,
    concern_class: str | None = None,
    tlp: str | None = None,
    binding_status: str | None = None,
    analysis_id: str | None = None,
    response: Response = Response(),
) -> JSONResponse:
    ctx, pol = _policy()
    if pol.check_locked():
        return _locked_response()
    nodes = ctx.store.list_nodes(
        node_type=node_type,
        status=status,
        concern_class=concern_class,
        tlp=tlp,
        analysis_id=analysis_id,
    )
    if binding_status:
        nodes = [n for n in nodes if str(n.get("binding_status", "")) == binding_status]
    visible, withheld = pol.filter_nodes(nodes)
    scope = pol.scope()
    if withheld:
        logger.info("list_nodes: ceiling=%s returned=%d withheld=%d", scope.ceiling, len(visible), withheld)
    return _ok({
        "nodes": visible,
        "count": len(visible),
        "visibility_limited": scope.visibility_limited,
    })


@read_router.get("/api/assurance/nodes/{node_id}")
def read_assurance_node(node_id: str) -> JSONResponse:
    ctx, pol = _policy()
    if pol.check_locked():
        return _locked_response()
    node = ctx.store.get_node(node_id)
    outcome = pol.apply_node(node)
    if not isinstance(outcome, Visible):
        return _not_found_response()
    visible_nodes, _ = pol.filter_nodes(ctx.store.list_nodes())
    nodes_by_id = visible_nodes_by_id(visible_nodes)
    nodes_by_id[node_id] = outcome.value
    all_visible = frozenset(nodes_by_id)
    edges_out = ctx.store.list_edges(source_id=node_id)
    edges_in = ctx.store.list_edges(target_id=node_id)
    arch_refs = ctx.store.list_arch_refs(assurance_node_id=node_id)
    return _ok({
        "node": outcome.value,
        "outgoing_edges": enrich_edges(pol.filter_edges(edges_out, all_visible), nodes_by_id),
        "incoming_edges": enrich_edges(pol.filter_edges(edges_in, all_visible), nodes_by_id),
        "arch_refs": arch_refs,
        "visibility_limited": pol.scope().visibility_limited,
    })


# ── Edges ─────────────────────────────────────────────────────────────────────

@read_router.get("/api/assurance/edges")
def list_assurance_edges(
    source_id: str | None = None,
    target_id: str | None = None,
    conn_type: str | None = None,
) -> JSONResponse:
    ctx, pol = _policy()
    if pol.check_locked():
        return _locked_response()
    edges = ctx.store.list_edges(source_id=source_id, target_id=target_id, conn_type=conn_type)
    visible_nodes, _ = pol.filter_nodes(ctx.store.list_nodes())
    nodes_by_id = visible_nodes_by_id(visible_nodes)
    filtered = enrich_edges(pol.filter_edges(edges, frozenset(nodes_by_id)), nodes_by_id)
    return _ok({"edges": filtered, "count": len(filtered), "visibility_limited": pol.scope().visibility_limited})


# ── Aggregates ────────────────────────────────────────────────────────────────

@read_router.get("/api/assurance/stats")
def assurance_stats() -> JSONResponse:
    ctx, pol = _policy()
    if pol.check_locked():
        return _locked_response()
    visible, _ = pol.filter_nodes(ctx.store.list_nodes())
    all_edges = ctx.store.list_edges()
    return _ok(pol.redact_stats(visible, all_edges))


@read_router.get("/api/assurance/coverage")
def assurance_coverage() -> JSONResponse:
    ctx, pol = _policy()
    if pol.check_locked():
        return _locked_response()
    visible, _ = pol.filter_nodes(ctx.store.list_nodes())
    visible_ids = frozenset(str(n["node_id"]) for n in visible)
    all_edges = ctx.store.list_edges()
    visible_edges = pol.filter_edges(all_edges, visible_ids)
    return _ok(coverage_gaps(visible, visible_edges))


@read_router.get("/api/assurance/verify")
def assurance_verify() -> JSONResponse:
    ctx, pol = _policy()
    if pol.check_locked():
        return _locked_response()
    from src.application.verification.assurance_verifier import format_result, verify_store  # noqa: PLC0415
    result = format_result(verify_store(ctx.store))
    visible, _ = pol.filter_nodes(ctx.store.list_nodes())
    visible_ids = frozenset(str(n["node_id"]) for n in visible)
    findings_val = result.get("findings") if isinstance(result, dict) else None
    raw_findings: list[object] = findings_val if isinstance(findings_val, list) else []
    redacted = pol.redact_findings(
        [f if isinstance(f, dict) else {"message": str(f)} for f in raw_findings],
        visible_ids,
    )
    result_out = dict(result) if isinstance(result, dict) else {"raw": result}
    result_out["findings"] = redacted
    result_out["visibility_limited"] = pol.scope().visibility_limited
    return _ok(result_out)


@read_router.get("/api/assurance/risk-register")
def assurance_risk_register() -> JSONResponse:
    ctx, pol = _policy()
    if pol.check_locked():
        return _locked_response()
    visible, _ = pol.filter_nodes(ctx.store.list_nodes())
    visible_ids = frozenset(str(n["node_id"]) for n in visible)
    visible_edges = pol.filter_edges(ctx.store.list_edges(), visible_ids)
    return _ok(risk_register(visible, visible_edges))


# ── Derived diagram previews ──────────────────────────────────────────────────

@read_router.get("/api/assurance/diagrams")
def list_assurance_diagrams() -> JSONResponse:
    ctx, pol = _policy()
    if pol.check_locked():
        return _locked_response()
    return _ok({"diagrams": AVAILABLE_DIAGRAMS})


@read_router.get("/api/assurance/diagrams/{diagram_id}/rendered")
def render_assurance_diagram(diagram_id: str) -> JSONResponse:
    ctx, pol = _policy()
    if pol.check_locked():
        return _locked_response()

    visible_nodes, _ = pol.filter_nodes(ctx.store.list_nodes())
    visible_ids = frozenset(str(n["node_id"]) for n in visible_nodes)
    all_edges = ctx.store.list_edges()
    visible_edges = pol.filter_edges(all_edges, visible_ids)

    projected_nodes: list[dict[str, object]]
    projected_edges: list[dict[str, object]]
    if diagram_id == "bowtie":
        projected_nodes = bowtie_nodes(visible_nodes)
        projected_ids = {str(n["node_id"]) for n in projected_nodes}
        projected_edges = [
            e for e in visible_edges
            if str(e.get("source_id", "")) in projected_ids
            and str(e.get("target_id", "")) in projected_ids
        ]
        puml = render_bowtie(projected_nodes, projected_edges)
    elif diagram_id == "control-structure":
        projected_nodes = [
            n for n in visible_nodes
            if str(n.get("node_type", "")) in {"control-structure-node", "control-action"}
        ]
        projected_ids = {str(n["node_id"]) for n in projected_nodes}
        projected_edges = [
            e for e in visible_edges
            if str(e.get("source_id", "")) in projected_ids
            and str(e.get("target_id", "")) in projected_ids
        ]
        puml = render_control_structure(projected_nodes, projected_edges)
    elif diagram_id == "uca-matrix":
        projected_nodes = uca_matrix_nodes(visible_nodes)
        projected_ids = {str(n["node_id"]) for n in projected_nodes}
        projected_edges = [
            e for e in visible_edges
            if str(e.get("source_id", "")) in projected_ids
            and str(e.get("target_id", "")) in projected_ids
            and str(e.get("conn_type", "")) == "concerns"
        ]
        puml = None
    else:
        return JSONResponse(
            status_code=404,
            content={"error": "unknown_diagram_id", "diagram_id": diagram_id,
                     "available": [d["diagram_id"] for d in AVAILABLE_DIAGRAMS]},
            headers={"Cache-Control": _NO_STORE},
        )

    svg: str | None = None
    if puml is not None:
        try:
            from src.infrastructure.gui.routers import state as s  # noqa: PLC0415
            from src.infrastructure.rendering.diagram_builder import render_puml_svg  # noqa: PLC0415

            repo_root = s.maybe_engagement_root()
            if repo_root is not None:
                svg_text, _ = render_puml_svg(puml, repo_root, "generic")
                if svg_text is not None:
                    svg = svg_text
        except Exception:  # noqa: BLE001
            pass

    return _ok({
        "diagram_id": diagram_id,
        "puml": puml,
        "svg": svg,
        "nodes": projected_nodes,
        "edges": projected_edges,
        "visibility_limited": pol.scope().visibility_limited,
    })


# ── Baselines ─────────────────────────────────────────────────────────────────

@read_router.get("/api/assurance/baselines")
def list_baselines() -> JSONResponse:
    ctx, pol = _policy()
    if pol.check_locked():
        return _locked_response()
    baselines = ctx.archive.list_baselines()
    return _ok({"baselines": baselines, "count": len(baselines)})


# ── Architecture lens (for G2: assurance findings about an arch element) ──────

@read_router.get("/api/assurance/arch-lens/{arch_artifact_id}")
def arch_lens(arch_artifact_id: str) -> JSONResponse:
    """Return assurance nodes that concern a given architecture artifact.

    Used by EntityDetailView / DiagramDetailView to show the assurance lens.
    Returns an empty result (not 404) when no references exist or store is locked,
    so the UI can distinguish locked from empty from truly unlocked.
    """
    ctx, pol = _policy()
    if pol.check_locked():
        return _ok({
            "arch_artifact_id": arch_artifact_id,
            "locked": True,
            "nodes": [],
            "count": 0,
        })
    refs = ctx.store.list_arch_refs(arch_artifact_id=arch_artifact_id)
    node_ids = {str(r["assurance_node_id"]) for r in refs}
    all_nodes = ctx.store.list_nodes()
    matched = [n for n in all_nodes if str(n["node_id"]) in node_ids]
    visible, _ = pol.filter_nodes(matched)
    scope = pol.scope()
    return _ok({
        "arch_artifact_id": arch_artifact_id,
        "locked": False,
        "nodes": visible,
        "count": len(visible),
        "visibility_limited": scope.visibility_limited,
    })
