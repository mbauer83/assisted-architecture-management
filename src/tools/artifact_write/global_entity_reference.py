"""Backward-compat shim — delegates to global_artifact_reference."""

from src.tools.artifact_write.global_artifact_reference import (  # noqa: F401
    _GAR_TYPE as _GRF_TYPE,
)
from src.tools.artifact_write.global_artifact_reference import (
    ensure_global_artifact_reference as _ensure_gar,
)


def ensure_global_entity_reference(
    *,
    engagement_repo,
    engagement_root,
    verifier,
    clear_repo_caches,
    global_entity_id: str,
    global_entity_name: str,
    dry_run: bool = False,
):
    return _ensure_gar(
        engagement_repo=engagement_repo,
        engagement_root=engagement_root,
        verifier=verifier,
        clear_repo_caches=clear_repo_caches,
        global_artifact_id=global_entity_id,
        global_artifact_name=global_entity_name,
        global_artifact_type="entity",
        dry_run=dry_run,
    )
