"""Entity editing and promotion operations."""

from pathlib import Path
from collections.abc import Callable

from src.common.model_verifier import ModelRegistry, ModelVerifier
from src.common.model_write import ENTITY_TYPES, format_entity_markdown
from src.tools.generate_macros import generate_macros

from .boundary import assert_engagement_write_root, today_iso
from .entity import verification_to_entity_dict
from .parse_existing import parse_entity_file
from .types import WriteResult
from .verify import verify_content_in_temp_path

# Sentinel to distinguish "not provided" from explicit None
_UNSET = object()


def edit_entity(
    *,
    repo_root: Path,
    registry: ModelRegistry,
    verifier: ModelVerifier,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    name: str | None = None,
    summary: object = _UNSET,
    properties: object = _UNSET,
    notes: object = _UNSET,
    keywords: object = _UNSET,
    version: str | None = None,
    status: str | None = None,
    dry_run: bool,
) -> WriteResult:
    """Edit an existing entity file by merging partial updates.

    Only provided fields are changed; omitted fields keep their current value.
    ``last-updated`` is always bumped to today.  If the display block label
    changes (because ``name`` changed), macros are regenerated.
    """
    assert_engagement_write_root(repo_root)

    entity_file = registry.find_file_by_id(artifact_id)
    if entity_file is None:
        raise ValueError(f"Entity '{artifact_id}' not found in model")

    parsed = parse_entity_file(entity_file)
    fm = parsed.frontmatter
    artifact_type = str(fm.get("artifact-type", ""))

    # Merge updates — _UNSET means "keep existing"
    eff_name = name if name is not None else str(fm.get("name", ""))
    eff_version = version if version is not None else str(fm.get("version", "0.1.0"))
    eff_status = status if status is not None else str(fm.get("status", "draft"))
    eff_keywords = keywords if keywords is not _UNSET else (fm.get("keywords") or None)
    eff_summary = summary if summary is not _UNSET else parsed.summary
    eff_properties = properties if properties is not _UNSET else (parsed.properties or None)
    eff_notes = notes if notes is not _UNSET else parsed.notes

    # Update display block — keep existing, update label if name changed
    display = dict(parsed.display_archimate)
    if name is not None and display:
        display["label"] = eff_name

    content = format_entity_markdown(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        name=eff_name,
        version=eff_version,
        status=eff_status,
        last_updated=today_iso(),
        keywords=eff_keywords,
        summary=eff_summary,
        properties=eff_properties,
        notes=eff_notes,
        display_archimate=display,
    )

    if dry_run:
        res = verify_content_in_temp_path(
            verifier=verifier, file_type="entity",
            desired_name=entity_file.name, content=content,
        )
        return WriteResult(
            wrote=False, path=entity_file, artifact_id=artifact_id,
            content=content, warnings=[],
            verification=verification_to_entity_dict(entity_file, res),
        )

    prev = entity_file.read_text(encoding="utf-8")
    entity_file.write_text(content, encoding="utf-8")

    res = verifier.verify_entity_file(entity_file)
    if not res.valid:
        entity_file.write_text(prev, encoding="utf-8")
        return WriteResult(
            wrote=False, path=entity_file, artifact_id=artifact_id,
            content=content, warnings=[],
            verification=verification_to_entity_dict(entity_file, res),
        )

    if name is not None:
        try:
            generate_macros(repo_root)
        except Exception:  # noqa: BLE001
            pass

    clear_repo_caches(repo_root)
    return WriteResult(
        wrote=True, path=entity_file, artifact_id=artifact_id,
        content=None, warnings=[],
        verification=verification_to_entity_dict(entity_file, res),
    )


def promote_entity(
    *,
    repo_root: Path,
    registry: ModelRegistry,
    verifier: ModelVerifier,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    dry_run: bool,
) -> WriteResult:
    """Promote entity status: draft -> active -> deprecated.

    Bumps version (minor for draft->active, major for active->deprecated).
    Rejects promotion if entity has verification errors.
    """
    assert_engagement_write_root(repo_root)

    entity_file = registry.find_file_by_id(artifact_id)
    if entity_file is None:
        raise ValueError(f"Entity '{artifact_id}' not found in model")

    pre_check = verifier.verify_entity_file(entity_file)
    errors = [i for i in pre_check.issues if i.severity == "error"]
    if errors:
        raise ValueError(
            f"Cannot promote: {len(errors)} verification error(s): "
            + "; ".join(i.message for i in errors[:3])
        )

    parsed = parse_entity_file(entity_file)
    current_status = str(parsed.frontmatter.get("status", "draft"))

    promotion_map = {"draft": "active", "active": "deprecated"}
    next_status = promotion_map.get(current_status)
    if next_status is None:
        raise ValueError(f"Cannot promote from '{current_status}' — terminal state")

    current_version = str(parsed.frontmatter.get("version", "0.1.0"))
    new_version = _bump_version(current_version, current_status)

    return edit_entity(
        repo_root=repo_root, registry=registry, verifier=verifier,
        clear_repo_caches=clear_repo_caches,
        artifact_id=artifact_id, status=next_status, version=new_version,
        dry_run=dry_run,
    )


def _bump_version(version: str, current_status: str) -> str:
    """Bump version: draft->active bumps minor, active->deprecated bumps major."""
    parts = version.split(".")
    if len(parts) != 3:
        return version
    major, minor, _patch = int(parts[0]), int(parts[1]), int(parts[2])
    if current_status == "draft":
        return f"{major}.{minor + 1}.0"
    return f"{major + 1}.0.0"
