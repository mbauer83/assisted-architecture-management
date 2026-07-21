"""Backend endpoints for the assurance module.

Includes:
  - Store status / reload (always callable)
  - Unlock-gated read endpoints (nodes, edges, stats, coverage, verify,
    risk-register, BOM/vuln, baselines, architecture lens) — via _assurance_read.
  - Unlock-gated write endpoints (create/edit/delete nodes, edges, arch-refs,
    baselines/seal, model-this, BOM/vuln/anchor imports) — via _assurance_write.
  - AI-BOM coverage / candidate scan / ML-BOM export — via _assurance_aibom.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.application.assurance_edge_catalog import build_edge_catalog
from src.infrastructure.app_bootstrap import assurance_ontology_module, get_module_registry
from src.infrastructure.gui.routers._assurance_aibom import aibom_router
from src.infrastructure.gui.routers._assurance_analysis_routes import analysis_router
from src.infrastructure.gui.routers._assurance_neighbors_routes import neighbors_router
from src.infrastructure.gui.routers._assurance_read import read_router
from src.infrastructure.gui.routers._assurance_signals_routes import signals_router
from src.infrastructure.gui.routers._assurance_write import write_router

router = APIRouter()
router.include_router(read_router)
router.include_router(neighbors_router)
router.include_router(signals_router)
router.include_router(write_router)
router.include_router(analysis_router)
router.include_router(aibom_router)

_DEFAULT_DB = Path(__file__).resolve().parents[4] / ".arch-assurance" / "store.db"


@router.post("/api/assurance/reload", status_code=200)
def assurance_reload() -> dict[str, object]:
    """Evict the assurance bundle cache and rebuild it (runs auto-unlock).

    Called by `arch-assurance unlock` so the running backend picks up a newly
    initialised or re-keyed store without requiring a full restart.
    """
    from src.infrastructure.mcp.assurance_mcp.context import clear_context_cache  # noqa: PLC0415

    clear_context_cache()
    # Eagerly rebuild so the response reflects the new unlocked state.
    return assurance_status()


@router.get("/api/assurance/edge-catalog")
def assurance_edge_catalog() -> JSONResponse:
    """Edge and reference type catalog from the loaded assurance module.

    Configured-gated but NOT unlock-gated: it serves module configuration,
    never store content. Registry enablement (capability present) is the gate.
    """
    if get_module_registry().find_ontology("assurance") is None:
        return JSONResponse(
            status_code=404,
            content={"error": "assurance_module_not_configured"},
        )
    return JSONResponse(content=build_edge_catalog(assurance_ontology_module()))


@router.get("/api/assurance/status")
def assurance_status() -> dict[str, object]:
    """Return confidential assurance store configuration and lock status.

    Always callable — does not require the store to be unlocked.
    Used by the frontend to show the locked/unlocked banner.
    """
    try:
        from src.infrastructure.assurance import _credential_store as creds  # noqa: PLC0415

        key_present = creds.get("db-encryption-key") is not None
    except Exception:  # noqa: BLE001
        key_present = False

    db_exists = _DEFAULT_DB.exists()
    configured = db_exists and key_present

    try:
        from src.infrastructure.mcp.assurance_mcp.context import get_assurance_context  # noqa: PLC0415

        unlocked = get_assurance_context().is_available()
    except Exception:  # noqa: BLE001
        unlocked = False

    if unlocked:
        store_status = "unlocked"
    elif configured:
        store_status = "locked"
    else:
        store_status = "not_initialised"

    return {
        "configured": configured,
        "unlocked": unlocked,
        "db_exists": db_exists,
        "key_in_keychain": key_present,
        "status": store_status,
        "module_class": "assurance",
    }
