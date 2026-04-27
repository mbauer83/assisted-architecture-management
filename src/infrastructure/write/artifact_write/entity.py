from collections.abc import Callable
from pathlib import Path

from src.application.modeling.artifact_write import ENTITY_TYPES, format_entity_markdown, generate_entity_id
from src.application.verification.artifact_verifier import ArtifactVerifier
from src.config.repo_paths import MODEL
from src.domain.archimate_types import ALL_ENTITY_TYPES
from src.infrastructure.rendering.generate_macros import generate_macros

from ._artifact_deduplication import (
    ensure_unique_entity_random_part,
    extract_friendly_slug,
    get_repository,
    validate_entity_unique,
)
from .boundary import assert_engagement_write_root, today_iso
from .types import WriteResult
from .verify import verify_content_in_temp_path


def verification_to_entity_dict(path: Path, res) -> dict[str, object]:
    return {
        "path": str(path),
        "file_type": "entity",
        "valid": res.valid,
        "issues": [
            {"severity": i.severity, "code": i.code, "message": i.message, "location": i.location}
            for i in res.issues
        ],
    }


def create_entity(
    *,
    repo_root: Path,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    artifact_type: str,
    name: str,
    summary: str | None,
    properties: dict[str, str] | None,
    notes: str | None,
    keywords: list[str] | None = None,
    artifact_id: str | None,
    version: str,
    status: str,
    last_updated: str | None,
    dry_run: bool,
) -> WriteResult:
    assert_engagement_write_root(repo_root)

    if artifact_type == "global-artifact-reference":
        raise ValueError(
            "global-artifact-reference entities may not be created directly. "
            "Use model_ensure_global_entity_reference (MCP) or "
            "POST /api/global-entity-reference (GUI) instead."
        )

    if artifact_type not in ALL_ENTITY_TYPES:
        raise ValueError(f"Unknown entity artifact_type: {artifact_type!r}")
    info = ENTITY_TYPES.get(artifact_type)
    if info is None:
        raise ValueError(
            f"Entity artifact_type '{artifact_type}' is supported by the verifier but is missing a writer mapping"
        )

    last = last_updated or today_iso()

    eid = artifact_id or generate_entity_id(info.prefix, name)
    repo = get_repository(repo_root)

    # Ensure random part is unique within this type (prevents sharing same random part)
    try:
        eid = ensure_unique_entity_random_part(eid, artifact_type, repo, info.prefix, name)
    except ValueError as e:
        error_msg = str(e)
        path = repo_root / MODEL / info.domain_dir / info.subdir / f"{eid}.md"
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=eid,
            content=None,
            warnings=[error_msg],
            verification={
                "valid": False,
                "issues": [
                    {
                        "severity": "error",
                        "code": "random_part_collision",
                        "message": error_msg,
                        "location": None,
                    }
                ],
            },
        )

    # Ensure type + friendly-name is unique (prevents semantic duplicates)
    friendly_slug = extract_friendly_slug(eid)
    try:
        validate_entity_unique(repo, artifact_type, friendly_slug)
    except ValueError as e:
        # Report validation error in preview/dry_run
        error_msg = str(e)
        path = repo_root / MODEL / info.domain_dir / info.subdir / f"{eid}.md"
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=eid,
            content=None,
            warnings=[error_msg],
            verification={
                "valid": False,
                "issues": [
                    {
                        "severity": "error",
                        "code": "duplicate_artifact",
                        "message": error_msg,
                        "location": None,
                    }
                ],
            },
        )
    path = repo_root / MODEL / info.domain_dir / info.subdir / f"{eid}.md"

    display = {
        "domain": info.domain_dir.capitalize(),
        "element-type": info.archimate_element_type,
        "label": name,
        "alias": f"{info.prefix}_{eid.split('.')[1]}" if "." in eid else eid.replace("-", "_"),
    }

    content = format_entity_markdown(
        artifact_id=eid,
        artifact_type=artifact_type,
        name=name,
        version=version,
        status=status,
        last_updated=last,
        keywords=keywords,
        summary=summary,
        properties=properties,
        notes=notes,
        display_archimate=display,
    )

    if dry_run:
        res = verify_content_in_temp_path(
            verifier=verifier,
            file_type="entity",
            desired_name=path.name,
            content=content,
        )
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=eid,
            content=content,
            warnings=[],
            verification=verification_to_entity_dict(path, res),
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    prev = path.read_text(encoding="utf-8") if path.exists() else None
    path.write_text(content, encoding="utf-8")

    res = verifier.verify_entity_file(path)
    if not res.valid:
        if prev is None:
            try:
                path.unlink()
            except OSError:
                pass
        else:
            path.write_text(prev, encoding="utf-8")
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=eid,
            content=content,
            warnings=[],
            verification=verification_to_entity_dict(path, res),
        )

    try:
        generate_macros(repo_root)
    except Exception:  # noqa: BLE001
        pass

    clear_repo_caches(path)

    return WriteResult(
        wrote=True,
        path=path,
        artifact_id=eid,
        content=None,
        warnings=[],
        verification=verification_to_entity_dict(path, res),
    )
