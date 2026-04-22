"""global_entity_reference.py — Create and look up GRF proxy entities.

A Global Entity Reference (GRF) is an automatically-managed stub in the
engagement repo that acts as a transparent proxy for a global (enterprise)
entity.  GRFs may NOT be created or edited through the standard entity API;
this module is the only authorised creator.
"""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

from src.common.model_query import ModelRepository
from src.common.model_write import ENTITY_TYPES, generate_entity_id
from src.common.model_write_formatting import format_entity_markdown
from src.common.model_verifier import ModelVerifier
from src.tools.generate_macros import generate_macros

from .boundary import assert_engagement_write_root, today_iso
from .types import WriteResult


_GRF_TYPE = "global-entity-reference"
_GRF_FRONTMATTER_KEY = "global-entity-id"


def find_existing_grf(repo: ModelRepository, global_entity_id: str) -> str | None:
    """Return the artifact_id of an existing GRF for *global_entity_id*, or None."""
    for rec in repo.list_entities(artifact_type=_GRF_TYPE):
        if rec.extra.get(_GRF_FRONTMATTER_KEY) == global_entity_id:
            return rec.artifact_id
    return None


def ensure_global_entity_reference(
    *,
    engagement_repo: ModelRepository,
    engagement_root: Path,
    verifier: ModelVerifier,
    clear_repo_caches: Callable[[Path], None],
    global_entity_id: str,
    global_entity_name: str,
    dry_run: bool = False,
) -> WriteResult:
    """Return (or create) a GRF for *global_entity_id* in the engagement repo.

    If a GRF already exists for this global entity, its artifact_id is returned
    in a WriteResult with ``wrote=False``.  Otherwise a new GRF file is created.
    """
    assert_engagement_write_root(engagement_root)

    existing = find_existing_grf(engagement_repo, global_entity_id)
    if existing is not None:
        path = engagement_root / "model" / "common" / "global-references" / f"{existing}.md"
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=existing,
            content=None,
            warnings=["GRF already exists"],
            verification=None,
        )

    info = ENTITY_TYPES[_GRF_TYPE]
    eid = generate_entity_id(info.prefix, global_entity_name)
    path = engagement_root / "model" / info.domain_dir / info.subdir / f"{eid}.md"

    display = {
        "domain": "",
        "element-type": "",
        "label": global_entity_name,
        "alias": f"GRF_{eid.split('.')[1]}" if "." in eid else eid.replace("-", "_"),
    }

    content = format_entity_markdown(
        artifact_id=eid,
        artifact_type=_GRF_TYPE,
        name=global_entity_name,
        version="0.1.0",
        status="active",
        last_updated=today_iso(),
        summary=f"Engagement-repo proxy for global entity `{global_entity_id}`.",
        properties=None,
        notes=None,
        display_archimate=display,
        extra_frontmatter={_GRF_FRONTMATTER_KEY: global_entity_id},
    )

    if dry_run:
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=eid,
            content=content,
            warnings=[],
            verification=None,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    res = verifier.verify_entity_file(path)
    if not res.valid:
        try:
            path.unlink()
        except OSError:
            pass
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=eid,
            content=content,
            warnings=[],
            verification={
                "valid": False,
                "issues": [{"severity": i.severity, "code": i.code, "message": i.message} for i in res.issues],
            },
        )

    try:
        generate_macros(engagement_root)
    except Exception:  # noqa: BLE001
        pass
    clear_repo_caches(path)

    return WriteResult(
        wrote=True,
        path=path,
        artifact_id=eid,
        content=None,
        warnings=[],
        verification={"valid": True, "issues": []},
    )


def build_grf_map(engagement_repo: ModelRepository) -> dict[str, str]:
    """Return {grf_artifact_id: global_entity_id} for all GRFs in the engagement repo."""
    result: dict[str, str] = {}
    for rec in engagement_repo.list_entities(artifact_type=_GRF_TYPE):
        geid = rec.extra.get(_GRF_FRONTMATTER_KEY)
        if isinstance(geid, str) and geid:
            result[rec.artifact_id] = geid
    return result
