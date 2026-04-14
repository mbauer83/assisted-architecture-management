
from pathlib import Path
from collections.abc import Callable
from src.common.archimate_types import ALL_ENTITY_TYPES
from src.common.model_verifier import ModelVerifier
from src.common.model_write import ENTITY_TYPES, generate_entity_id, format_entity_markdown
from src.tools.generate_macros import generate_macros

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
    verifier: ModelVerifier,
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

    if artifact_type not in ALL_ENTITY_TYPES:
        raise ValueError(f"Unknown entity artifact_type: {artifact_type!r}")
    info = ENTITY_TYPES.get(artifact_type)
    if info is None:
        raise ValueError(
            f"Entity artifact_type '{artifact_type}' is supported by the verifier but is missing a writer mapping"
        )

    last = last_updated or today_iso()

    eid = artifact_id or generate_entity_id(info.prefix, name)
    path = repo_root / "model" / info.layer_dir / info.subdir / f"{eid}.md"

    display = {
        "domain": info.archimate_layer,
        "element-type": info.archimate_element_type,
        "label": name,
        "alias": f"{info.prefix}_{eid.split('.')[1]}" if '.' in eid else eid.replace("-", "_"),
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

    clear_repo_caches(repo_root)

    return WriteResult(
        wrote=True,
        path=path,
        artifact_id=eid,
        content=None,
        warnings=[],
        verification=verification_to_entity_dict(path, res),
    )
