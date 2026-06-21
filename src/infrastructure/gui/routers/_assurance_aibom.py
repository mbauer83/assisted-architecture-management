"""HTTP read endpoints for AI-BOM coverage, candidate scanning, and ML-BOM export.

These three capabilities are not exposed by the SecuritySignalConnector port, so
they get a dedicated router (keeps _assurance_read.py within its size budget):

  GET  /api/assurance/aibom/coverage  — coverage/gap report over store BOM components
                                         + anchors (signals-gated, exposure-filtered).
  GET  /api/assurance/aibom/scan      — heuristic AI-candidate scan over the *public*
                                         architecture repository (un-gated: touches no
                                         confidential content, only ranks model entities).
  GET  /api/assurance/aibom/roles     — canonical AI-BOM role vocabulary (single backend
                                         source of truth; the GUI consumes this rather than
                                         redeclaring the enum).
  POST /api/assurance/aibom/export    — emit a CycloneDX 1.6 ML-BOM from caller-confirmed
                                         AI components (un-gated: a pure transform of the
                                         request body, no store access).

All responses carry ``Cache-Control: no-store``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from src.application.assurance_queries import aibom_coverage
from src.infrastructure.gui.routers._assurance_http import build_policy as _build_policy
from src.infrastructure.gui.routers._assurance_http import locked_response as _locked_response
from src.infrastructure.gui.routers._assurance_http import ok as _ok

logger = logging.getLogger(__name__)

aibom_router = APIRouter()


@aibom_router.get("/api/assurance/aibom/coverage")
def aibom_coverage_report() -> JSONResponse:
    ctx, pol = _build_policy()
    if not ctx.signals_available():
        return _locked_response()
    components, withheld = pol.filter_security_records(ctx.connector.list_bom_components())
    anchors, _ = pol.filter_security_records(ctx.connector.list_anchors())
    report = aibom_coverage(components, anchors)
    report["withheld_components"] = withheld
    report["visibility_limited"] = pol.scope().visibility_limited
    if withheld:
        logger.info("aibom_coverage: ceiling=%s withheld=%d", pol.scope().ceiling, withheld)
    return _ok(report)


@aibom_router.get("/api/assurance/aibom/scan")
def aibom_scan_candidates(domain: str | None = None, limit: int = 50) -> JSONResponse:
    """Rank public architecture model entities by AI-BOM relevance (assistive only)."""
    from src.infrastructure.assurance.ai_candidate_scanner import scan_candidates  # noqa: PLC0415
    from src.infrastructure.gui.routers import state as s  # noqa: PLC0415

    repo = s.maybe_get_repo()
    if repo is None:
        return _ok({"candidates": [], "count": 0, "note": _SCAN_NOTE})
    entities: list[dict[str, object]] = [
        {
            "entity_id": e.artifact_id,
            "name": e.name,
            "entity_type": e.artifact_type,
            "description": e.content_text,
        }
        for e in repo.list_entities(domain=domain)
        if e.host_diagram_id is None  # model entities only; not diagram-only nodes
    ]
    candidates = scan_candidates(entities)[: max(limit, 0)]
    return _ok({"candidates": candidates, "count": len(candidates), "note": _SCAN_NOTE})


@aibom_router.get("/api/assurance/aibom/roles")
def aibom_roles() -> JSONResponse:
    """Canonical AI-BOM role vocabulary (single backend source; GUI consumes this)."""
    from src.infrastructure.assurance._aibom_exporter import AI_BOM_ROLES  # noqa: PLC0415

    return _ok({"roles": list(AI_BOM_ROLES)})


@aibom_router.post("/api/assurance/aibom/export")
def aibom_export(payload: dict[str, object] = Body(default={})) -> JSONResponse:
    """Emit a CycloneDX 1.6 ML-BOM from caller-confirmed AI components."""
    from src.infrastructure.assurance._aibom_exporter import build_cyclonedx_16  # noqa: PLC0415

    raw = payload.get("ai_components")
    ai_components = [c for c in raw if isinstance(c, dict)] if isinstance(raw, list) else []
    notes = str(payload.get("notes") or "")
    bom = build_cyclonedx_16(ai_components, notes=notes)
    return _ok({"bom": bom, "component_count": len(ai_components)})


_SCAN_NOTE = (
    "Heuristic suggestions only — confirm each candidate before exporting it as an "
    "AI component. The scan ranks architecture model entities by name/type patterns."
)
