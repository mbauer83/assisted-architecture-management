"""Backend endpoints for assurance module status and metadata.

Phase 1d: minimal surfacing — store status endpoint + module_class-aware
exclusion from architecture stats. The assurance store's content is NOT
exposed through these endpoints (that's the MCP server's job).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

_DEFAULT_DB = Path(__file__).resolve().parents[4] / ".arch-assurance" / "store.db"


@router.get("/api/assurance/status")
def assurance_status() -> dict[str, object]:
    """Return confidential assurance store configuration and lock status.

    Always callable — does not require the store to be unlocked.
    Used by the frontend to show the locked/unlocked banner.
    """
    try:
        import keyring  # type: ignore[import-untyped]

        key_present = keyring.get_password("arch-assurance", "db-encryption-key") is not None
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
