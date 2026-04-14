"""Execute a promotion plan — copy/merge entity files to enterprise repo.

Split from promote_to_enterprise to keep files within line-count limits.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from src.common.model_verifier import ModelRegistry, ModelVerifier
from src.tools.generate_macros import generate_macros
from src.tools.model_write.parse_existing import parse_entity_file
from src.tools.model_write.promote_to_enterprise import (
    ConflictResolution,
    PromotionPlan,
    PromotionResult,
)


def execute_promotion(
    plan: PromotionPlan,
    engagement_root: Path,
    enterprise_root: Path,
    verifier: ModelVerifier,
    registry: ModelRegistry,
    *,
    conflict_resolutions: list[ConflictResolution] | None = None,
) -> PromotionResult:
    """Copy/merge entity files to enterprise repo and verify.

    Unresolved conflicts are skipped with a warning.
    """
    result = PromotionResult(plan=plan, executed=False)
    copied: list[Path] = []
    backups: list[tuple[Path, bytes | None]] = []  # (path, original_content_or_None)

    resolutions = {r.engagement_id: r for r in (conflict_resolutions or [])}

    try:
        # 1. Fresh adds: copy engagement files directly
        for eid in plan.entities_to_add:
            _copy_entity(eid, engagement_root, enterprise_root,
                         registry, result, copied, backups)

        # 2. Conflicts: apply resolutions
        for conflict in plan.conflicts:
            res = resolutions.get(conflict.engagement_id)
            if res is None:
                result.plan.warnings.append(
                    f"No resolution for conflict: {conflict.engagement_id} "
                    f"vs {conflict.enterprise_id} — skipped"
                )
                continue
            if res.strategy == "accept_enterprise":
                continue  # nothing to do
            if res.strategy == "accept_engagement":
                _replace_enterprise_content(
                    conflict, engagement_root, enterprise_root,
                    registry, result, backups,
                )
            elif res.strategy == "merge" and res.merged_fields:
                _apply_merge(conflict, enterprise_root, registry,
                             res.merged_fields, result, backups)

        # 3. Regenerate macros
        if (enterprise_root / "model").is_dir():
            try:
                generate_macros(enterprise_root)
            except Exception:  # noqa: BLE001
                pass

        # 4. Verify
        ent_registry = ModelRegistry(enterprise_root)
        ent_verifier = ModelVerifier(ent_registry)
        vresults = ent_verifier.verify_all(enterprise_root, include_diagrams=False)
        errors = [
            f"{i.code}: {i.message} ({i.location})"
            for r in vresults for i in r.issues if i.severity == "error"
        ]
        result.verification_errors = errors

        if errors:
            _rollback(copied, backups)
            result.rolled_back = True
        else:
            result.executed = True

    except Exception as exc:
        _rollback(copied, backups)
        result.rolled_back = True
        result.verification_errors.append(str(exc))

    return result


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

def _copy_entity(
    eid: str, eng_root: Path, ent_root: Path,
    registry: ModelRegistry, result: PromotionResult,
    copied: list[Path], backups: list[tuple[Path, bytes | None]],
) -> None:
    src = registry.find_file_by_id(eid)
    if src is None:
        result.verification_errors.append(f"File not found for {eid}")
        return
    rel = src.relative_to(eng_root)
    dest = ent_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    backups.append((dest, dest.read_bytes() if dest.exists() else None))
    shutil.copy2(src, dest)
    copied.append(dest)
    result.copied_files.append(str(rel))
    # .outgoing.md
    outgoing = src.with_suffix(".outgoing.md")
    if outgoing.exists():
        dest_out = ent_root / outgoing.relative_to(eng_root)
        backups.append((dest_out, dest_out.read_bytes() if dest_out.exists() else None))
        shutil.copy2(outgoing, dest_out)
        copied.append(dest_out)
        result.copied_files.append(str(outgoing.relative_to(eng_root)))


def _replace_enterprise_content(
    conflict: "PromotionConflict",
    eng_root: Path, ent_root: Path,
    registry: ModelRegistry, result: PromotionResult,
    backups: list[tuple[Path, bytes | None]],
) -> None:
    """Replace enterprise entity content with engagement version, keeping enterprise ID."""
    from src.tools.model_write.promote_to_enterprise import PromotionConflict  # noqa: F811

    ent_path = registry.find_file_by_id(conflict.enterprise_id)
    eng_path = registry.find_file_by_id(conflict.engagement_id)
    if not ent_path or not eng_path:
        result.plan.warnings.append(
            f"Could not find files for conflict {conflict.engagement_id}")
        return
    # Read engagement content, rewrite artifact-id to enterprise
    content = eng_path.read_text(encoding="utf-8")
    content = content.replace(conflict.engagement_id, conflict.enterprise_id, 1)
    backups.append((ent_path, ent_path.read_bytes()))
    ent_path.write_text(content, encoding="utf-8")
    result.updated_files.append(str(ent_path.relative_to(ent_root)))


def _apply_merge(
    conflict: "PromotionConflict",
    ent_root: Path, registry: ModelRegistry,
    merged_fields: dict[str, Any], result: PromotionResult,
    backups: list[tuple[Path, bytes | None]],
) -> None:
    """Apply merged fields to the enterprise entity file."""
    from src.common.model_write import format_entity_markdown
    from src.tools.model_write.boundary import today_iso

    ent_path = registry.find_file_by_id(conflict.enterprise_id)
    if not ent_path:
        result.plan.warnings.append(
            f"Enterprise file not found for merge: {conflict.enterprise_id}")
        return

    parsed = parse_entity_file(ent_path)
    fm = dict(parsed.frontmatter)

    # Merge: caller-provided fields override, keep enterprise defaults for rest
    eff_name = merged_fields.get("name", fm.get("name", ""))
    eff_version = merged_fields.get("version", fm.get("version", "0.1.0"))
    eff_status = merged_fields.get("status", fm.get("status", "draft"))
    eff_keywords = merged_fields.get("keywords", fm.get("keywords"))
    eff_summary = merged_fields.get("summary", parsed.summary)
    eff_properties = merged_fields.get("properties", parsed.properties)
    eff_notes = merged_fields.get("notes", parsed.notes)

    content = format_entity_markdown(
        artifact_id=conflict.enterprise_id,
        artifact_type=conflict.artifact_type,
        name=eff_name, version=eff_version, status=eff_status,
        last_updated=today_iso(),
        keywords=eff_keywords, summary=eff_summary,
        properties=eff_properties, notes=eff_notes,
        display_archimate=dict(parsed.display_archimate),
    )
    backups.append((ent_path, ent_path.read_bytes()))
    ent_path.write_text(content, encoding="utf-8")
    result.updated_files.append(str(ent_path.relative_to(ent_root)))


def _rollback(
    copied: list[Path],
    backups: list[tuple[Path, bytes | None]],
) -> None:
    """Restore files to pre-promotion state."""
    for path, original in reversed(backups):
        if original is None:
            if path.exists():
                path.unlink()
        else:
            path.write_bytes(original)
    for f in reversed(copied):
        if f.exists() and not any(p == f for p, _ in backups):
            f.unlink()
