"""Entity editing and promotion operations."""

from pathlib import Path
from collections.abc import Callable

from src.common.model_verifier import ModelRegistry, ModelVerifier
from src.common.model_write import ENTITY_TYPES, format_entity_markdown, slugify
from src.tools.generate_macros import generate_macros

from .boundary import assert_engagement_write_root, today_iso
from .entity import verification_to_entity_dict
from .parse_existing import parse_entity_file
from .types import WriteResult
from .verify import verify_content_in_temp_path

# Sentinel to distinguish "not provided" from explicit None
_UNSET = object()


def _rename_entity_identity(
    *,
    entity_file: Path,
    repo_root: Path,
    old_artifact_id: str,
    new_artifact_id: str,
) -> tuple[Path, list[Path]]:
    new_entity_file = entity_file.with_name(f"{new_artifact_id}.md")

    old_outgoing = entity_file.with_suffix(".outgoing.md")
    new_outgoing = new_entity_file.with_suffix(".outgoing.md")
    changed_paths: list[Path] = []

    if old_outgoing.exists():
        outgoing_text = old_outgoing.read_text(encoding="utf-8").replace(old_artifact_id, new_artifact_id)
        new_outgoing.write_text(outgoing_text, encoding="utf-8")
        if new_outgoing != old_outgoing:
            old_outgoing.unlink()
        changed_paths.extend([old_outgoing, new_outgoing])

    for outgoing_path in (repo_root / "model").rglob("*.outgoing.md"):
        if outgoing_path == new_outgoing:
            continue
        text = outgoing_path.read_text(encoding="utf-8")
        if old_artifact_id not in text:
            continue
        outgoing_path.write_text(text.replace(old_artifact_id, new_artifact_id), encoding="utf-8")
        changed_paths.append(outgoing_path)

    return new_entity_file, changed_paths


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
    current_name = str(fm.get("name", ""))
    effective_artifact_id = artifact_id
    target_entity_file = entity_file
    rename_summary: list[str] = []

    # Merge updates — _UNSET means "keep existing"
    eff_name = name if name is not None else current_name
    eff_version = version if version is not None else str(fm.get("version", "0.1.0"))
    eff_status = status if status is not None else str(fm.get("status", "draft"))
    eff_keywords = keywords if keywords is not _UNSET else (fm.get("keywords") or None)
    eff_summary = summary if summary is not _UNSET else parsed.summary
    eff_properties = properties if properties is not _UNSET else (parsed.properties or None)
    eff_notes = notes if notes is not _UNSET else parsed.notes
    if name is not None:
        current_slug = slugify(current_name)
        next_slug = slugify(eff_name)
        if next_slug != current_slug:
            effective_artifact_id = f"{artifact_id.rsplit('.', 1)[0]}.{next_slug}"
            target_entity_file = entity_file.with_name(f"{effective_artifact_id}.md")
            if target_entity_file.exists() and target_entity_file != entity_file:
                raise ValueError(f"Target entity file already exists: {target_entity_file.name}")

    # Update display block — keep existing, update label if name changed
    display = dict(parsed.display_archimate)
    if name is not None and display:
        display["label"] = eff_name

    content = format_entity_markdown(
        artifact_id=effective_artifact_id,
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

    preview_res = verify_content_in_temp_path(
        verifier=verifier,
        file_type="entity",
        desired_name=target_entity_file.name,
        content=content,
    )

    if dry_run:
        if effective_artifact_id != artifact_id:
            impacted = 0
            own_outgoing = entity_file.with_suffix(".outgoing.md")
            if own_outgoing.exists():
                impacted += 1
            for outgoing_path in (repo_root / "model").rglob("*.outgoing.md"):
                if outgoing_path == own_outgoing:
                    continue
                try:
                    if artifact_id in outgoing_path.read_text(encoding="utf-8"):
                        impacted += 1
                except OSError:
                    continue
            rename_summary.append(
                f"Rename will update artifact-id to {effective_artifact_id} and rewrite {impacted} outgoing file(s)."
            )
        return WriteResult(
            wrote=False, path=target_entity_file, artifact_id=effective_artifact_id,
            content=content, warnings=rename_summary,
            verification=verification_to_entity_dict(target_entity_file, preview_res),
        )

    if not preview_res.valid:
        return WriteResult(
            wrote=False,
            path=target_entity_file,
            artifact_id=effective_artifact_id,
            content=content,
            warnings=rename_summary,
            verification=verification_to_entity_dict(target_entity_file, preview_res),
        )

    prev = entity_file.read_text(encoding="utf-8")
    target_entity_file.write_text(content, encoding="utf-8")
    if target_entity_file != entity_file:
        entity_file.unlink()
        target_entity_file, renamed_paths = _rename_entity_identity(
            entity_file=entity_file,
            repo_root=repo_root,
            old_artifact_id=artifact_id,
            new_artifact_id=effective_artifact_id,
        )
        rename_summary.append(
            f"Renamed artifact-id to {effective_artifact_id} and updated {len(renamed_paths)} outgoing file(s)."
        )
    else:
        renamed_paths = []

    res = verifier.verify_entity_file(target_entity_file)
    if not res.valid:
        if target_entity_file != entity_file:
            target_entity_file.unlink(missing_ok=True)
            entity_file.write_text(prev, encoding="utf-8")
        else:
            entity_file.write_text(prev, encoding="utf-8")
        return WriteResult(
            wrote=False, path=target_entity_file, artifact_id=effective_artifact_id,
            content=content, warnings=rename_summary,
            verification=verification_to_entity_dict(target_entity_file, res),
        )

    if name is not None:
        try:
            generate_macros(repo_root)
        except Exception:  # noqa: BLE001
            pass

    if target_entity_file != entity_file:
        clear_repo_caches([entity_file, target_entity_file, *renamed_paths])
    else:
        clear_repo_caches(target_entity_file)
    return WriteResult(
        wrote=True, path=target_entity_file, artifact_id=effective_artifact_id,
        content=None, warnings=rename_summary,
        verification=verification_to_entity_dict(target_entity_file, res),
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
