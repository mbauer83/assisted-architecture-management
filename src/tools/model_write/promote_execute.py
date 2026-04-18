"""Execute a promotion plan — copy/merge entity files to enterprise repo.

Split from promote_to_enterprise to keep files within line-count limits.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Callable, Protocol
from dataclasses import dataclass

from src.common.model_verifier import ModelRegistry, ModelVerifier
from src.tools.generate_macros import generate_macros
from src.tools.model_write.parse_existing import parse_entity_file
from src.tools.model_write.promote_to_enterprise import (
    ConflictResolution,
    PromotionConflict,
    PromotionPlan,
    PromotionResult,
)


# ---------------------------------------------------------------------------
# Target resolver — functional abstraction for outgoing.md rewriting
# ---------------------------------------------------------------------------

TargetResolver = Callable[[str], str | None]
"""Maps a connection target artifact-id to its enterprise equivalent, or None to drop."""


def make_target_resolver(
    grf_map: dict[str, str],
    promoted_ids: set[str],
    enterprise_ids: set[str],
) -> TargetResolver:
    """Build a resolver for rewriting connection targets in promoted outgoing files.

    Resolution order:
    1. GRF → its referenced global entity ID (transparent proxy rewrite)
    2. Promoted or already-enterprise entity → keep unchanged
    3. Anything else (engagement-only, not promoted) → None (drop)
    """
    keep_ids = promoted_ids | enterprise_ids

    def resolve(target_id: str) -> str | None:
        enterprise_id = grf_map.get(target_id)
        if enterprise_id is not None:
            return enterprise_id
        return target_id if target_id in keep_ids else None

    return resolve


# ---------------------------------------------------------------------------
# Conflict strategy — strategy pattern for conflict resolution
# ---------------------------------------------------------------------------

class _ConflictHandler(Protocol):
    def handle(
        self,
        conflict: PromotionConflict,
        eng_root: Path,
        ent_root: Path,
        registry: ModelRegistry,
        result: PromotionResult,
        backups: list[tuple[Path, bytes | None]],
        resolve_target: TargetResolver,
    ) -> None: ...


class _AcceptEnterpriseHandler:
    def handle(self, conflict, eng_root, ent_root, registry, result, backups, resolve_target):
        pass  # Keep enterprise entity as-is; engagement version discarded


@dataclass
class _AcceptEngagementHandler:
    def handle(self, conflict, eng_root, ent_root, registry, result, backups, resolve_target):
        _replace_enterprise_content(conflict, eng_root, ent_root, registry, result, backups, resolve_target)


@dataclass
class _MergeHandler:
    merged_fields: dict[str, Any]

    def handle(self, conflict, eng_root, ent_root, registry, result, backups, resolve_target):
        _apply_merge(conflict, ent_root, registry, self.merged_fields, result, backups)


def _build_handler(resolution: ConflictResolution) -> _ConflictHandler | None:
    match resolution.strategy:
        case "accept_enterprise":
            return _AcceptEnterpriseHandler()
        case "accept_engagement":
            return _AcceptEngagementHandler()
        case "merge" if resolution.merged_fields:
            return _MergeHandler(merged_fields=resolution.merged_fields)
        case _:
            return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def execute_promotion(
    plan: PromotionPlan,
    engagement_root: Path,
    enterprise_root: Path,
    verifier: ModelVerifier,
    registry: ModelRegistry,
    *,
    conflict_resolutions: list[ConflictResolution] | None = None,
) -> PromotionResult:
    """Copy/merge entity files into the enterprise repo, then replace promoted
    engagement entities with GRF proxies.

    Steps:
    1. Copy fresh entities + rewrite their outgoing files (GRF→real, drop stranded)
    2. Apply conflict resolutions
    3. Regenerate enterprise macros
    4. Verify enterprise repo
    5. On success: replace promoted engagement entities with GRF proxies
    6. On failure: rollback enterprise changes
    """
    result = PromotionResult(plan=plan, executed=False)
    ent_copied: list[Path] = []
    ent_backups: list[tuple[Path, bytes | None]] = []

    from src.tools.model_write.global_entity_reference import build_grf_map
    from src.common.model_query import ModelRepository as _MR

    eng_repo = _MR(engagement_root)
    grf_map = build_grf_map(eng_repo)
    promoted_ids = set(plan.entities_to_add) | {c.engagement_id for c in plan.conflicts}
    enterprise_ids = registry.enterprise_entity_ids()
    resolve_target = make_target_resolver(grf_map, promoted_ids, enterprise_ids)

    resolutions = {r.engagement_id: r for r in (conflict_resolutions or [])}

    try:
        # 1. Fresh adds
        for eid in plan.entities_to_add:
            _copy_entity(
                eid, engagement_root, enterprise_root,
                registry, result, ent_copied, ent_backups, resolve_target,
            )

        # 2. Conflicts
        for conflict in plan.conflicts:
            res = resolutions.get(conflict.engagement_id)
            if res is None:
                result.plan.warnings.append(
                    f"No resolution for conflict: {conflict.engagement_id} "
                    f"vs {conflict.enterprise_id} — skipped"
                )
                continue
            handler = _build_handler(res)
            if handler is None:
                result.plan.warnings.append(
                    f"Unrecognised resolution strategy {res.strategy!r} for "
                    f"{conflict.engagement_id} — skipped"
                )
                continue
            handler.handle(
                conflict, engagement_root, enterprise_root,
                registry, result, ent_backups, resolve_target,
            )

        # 3. Regenerate enterprise macros
        if (enterprise_root / "model").is_dir():
            try:
                generate_macros(enterprise_root)
            except Exception:  # noqa: BLE001
                pass

        # 4. Verify enterprise repo
        ent_registry = ModelRegistry(enterprise_root)
        ent_verifier = ModelVerifier(ent_registry)
        vresults = ent_verifier.verify_all(enterprise_root, include_diagrams=False)
        errors = [
            f"{i.code}: {i.message} ({i.location})"
            for r in vresults for i in r.issues if i.severity == "error"
        ]
        result.verification_errors = errors

        if errors:
            _rollback(ent_copied, ent_backups)
            result.rolled_back = True
            return result

        result.executed = True

        # 5. Replace promoted engagement entities with GRF proxies
        all_promoted = list(plan.entities_to_add) + [c.engagement_id for c in plan.conflicts]
        for eid in all_promoted:
            _replace_engagement_entity_with_grf(
                eid, engagement_root, registry, result,
            )

        # Regenerate engagement macros so GRFs are picked up
        try:
            generate_macros(engagement_root)
        except Exception:  # noqa: BLE001
            pass

    except Exception as exc:
        _rollback(ent_copied, ent_backups)
        result.rolled_back = True
        result.executed = False
        result.verification_errors.append(str(exc))

    return result


# ---------------------------------------------------------------------------
# Entity copy + outgoing rewrite
# ---------------------------------------------------------------------------

def _copy_entity(
    eid: str,
    eng_root: Path,
    ent_root: Path,
    registry: ModelRegistry,
    result: PromotionResult,
    copied: list[Path],
    backups: list[tuple[Path, bytes | None]],
    resolve_target: TargetResolver,
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

    outgoing = src.with_suffix(".outgoing.md")
    if outgoing.exists():
        dest_out = ent_root / outgoing.relative_to(eng_root)
        backups.append((dest_out, dest_out.read_bytes() if dest_out.exists() else None))
        rewritten = _rewrite_outgoing(
            outgoing.read_text(encoding="utf-8"),
            resolve_target=resolve_target,
            result=result,
        )
        dest_out.parent.mkdir(parents=True, exist_ok=True)
        dest_out.write_text(rewritten, encoding="utf-8")
        copied.append(dest_out)
        result.copied_files.append(str(outgoing.relative_to(eng_root)))


def _rewrite_outgoing(
    content: str,
    resolve_target: TargetResolver,
    result: PromotionResult,
) -> str:
    """Rewrite an outgoing.md for inclusion in the enterprise repo.

    Uses ``resolve_target`` to map each connection target:
    - GRF → its global entity ID
    - Promoted / enterprise entity → unchanged
    - Engagement-only entity not in set → section dropped with warning
    """
    _CONN_HEADER = re.compile(r"^### (.+?) → (.+)$")
    lines = content.splitlines(keepends=True)
    out: list[str] = []
    drop_section = False

    for line in lines:
        stripped = line.rstrip("\n")
        m = _CONN_HEADER.match(stripped)
        if m:
            conn_type, target_id = m.group(1).strip(), m.group(2).strip()
            resolved = resolve_target(target_id)
            if resolved is None:
                result.plan.warnings.append(
                    f"Dropped connection → {target_id!r}: "
                    "engagement-only entity not in promotion set"
                )
                drop_section = True
                continue
            drop_section = False
            if resolved != target_id:
                line = line.replace(target_id, resolved, 1)
        elif drop_section:
            # Skip body lines of a dropped section; resume on next header or blank
            if not stripped or stripped.startswith("### "):
                drop_section = not bool(stripped)
                if stripped.startswith("### "):
                    # Will be processed in the next iteration; re-insert
                    # by NOT setting drop_section and falling through
                    drop_section = False
                    out.append(line)
                    continue
            continue

        out.append(line)

    return "".join(out)


# ---------------------------------------------------------------------------
# Engagement-side GRF replacement
# ---------------------------------------------------------------------------

def _replace_engagement_entity_with_grf(
    eid: str,
    eng_root: Path,
    registry: ModelRegistry,
    result: PromotionResult,
) -> None:
    """Replace a promoted engagement entity with a GRF proxy in the engagement repo.

    After promotion to enterprise, the same artifact-id now lives in enterprise.
    In the engagement repo:
    1. Create a GRF proxy pointing to the promoted entity ID.
    2. Update all engagement outgoing files referencing the old ID to use the GRF.
    3. Remove the original engagement entity file (and its outgoing.md).
    """
    src = registry.find_file_by_id(eid)
    if src is None or not src.is_relative_to(eng_root):
        return  # already in enterprise or not found

    # Derive entity name for GRF label
    try:
        parsed = parse_entity_file(src)
        entity_name = str(parsed.frontmatter.get("name", eid))
    except Exception:  # noqa: BLE001
        entity_name = eid

    # Create GRF (or reuse if already exists — idempotent)
    from src.tools.model_write.global_entity_reference import ensure_global_entity_reference
    from src.common.model_query import ModelRepository as _MR

    eng_repo = _MR(eng_root)
    grf_result = ensure_global_entity_reference(
        engagement_repo=eng_repo,
        engagement_root=eng_root,
        verifier=ModelVerifier(None),  # minimal verifier — no registry needed here
        clear_repo_caches=lambda _: None,
        global_entity_id=eid,
        global_entity_name=entity_name,
        dry_run=False,
    )
    grf_id = grf_result.artifact_id
    result.updated_files.append(f"[created GRF] {grf_id}")

    # Update engagement outgoing files that reference the old entity ID
    _update_outgoing_references(eid, grf_id, eng_root, result)

    # Remove original engagement files
    try:
        src.unlink()
        result.updated_files.append(f"[removed] {src.relative_to(eng_root)}")
    except OSError:
        pass
    outgoing = src.with_suffix(".outgoing.md")
    if outgoing.exists():
        try:
            outgoing.unlink()
            result.updated_files.append(f"[removed] {outgoing.relative_to(eng_root)}")
        except OSError:
            pass


def _update_outgoing_references(
    old_id: str,
    new_id: str,
    eng_root: Path,
    result: PromotionResult,
) -> None:
    """Rewrite all engagement outgoing files that reference old_id as a connection target."""
    model_dir = eng_root / "model"
    if not model_dir.is_dir():
        return
    # Precise replacement: only in connection headers `### ... → old_id`
    pattern = re.compile(rf"(^### .+? → ){re.escape(old_id)}$", re.MULTILINE)
    for outgoing_file in model_dir.rglob("*.outgoing.md"):
        content = outgoing_file.read_text(encoding="utf-8")
        updated, n = pattern.subn(rf"\g<1>{new_id}", content)
        if n > 0:
            outgoing_file.write_text(updated, encoding="utf-8")
            result.updated_files.append(
                f"[ref-updated ×{n}] {outgoing_file.relative_to(eng_root)}"
            )


# ---------------------------------------------------------------------------
# Conflict helpers
# ---------------------------------------------------------------------------

def _replace_enterprise_content(
    conflict: PromotionConflict,
    eng_root: Path,
    ent_root: Path,
    registry: ModelRegistry,
    result: PromotionResult,
    backups: list[tuple[Path, bytes | None]],
    resolve_target: TargetResolver,
) -> None:
    ent_path = registry.find_file_by_id(conflict.enterprise_id)
    eng_path = registry.find_file_by_id(conflict.engagement_id)
    if not ent_path or not eng_path:
        result.plan.warnings.append(
            f"Could not find files for conflict {conflict.engagement_id}"
        )
        return
    content = eng_path.read_text(encoding="utf-8").replace(
        conflict.engagement_id, conflict.enterprise_id, 1
    )
    backups.append((ent_path, ent_path.read_bytes()))
    ent_path.write_text(content, encoding="utf-8")
    result.updated_files.append(str(ent_path.relative_to(ent_root)))

    # Also rewrite outgoing file
    eng_outgoing = eng_path.with_suffix(".outgoing.md")
    if eng_outgoing.exists():
        ent_outgoing = ent_root / eng_outgoing.relative_to(eng_root)
        backups.append((ent_outgoing, ent_outgoing.read_bytes() if ent_outgoing.exists() else None))
        rewritten = _rewrite_outgoing(
            eng_outgoing.read_text(encoding="utf-8"), resolve_target=resolve_target, result=result
        ).replace(conflict.engagement_id, conflict.enterprise_id, 1)
        ent_outgoing.parent.mkdir(parents=True, exist_ok=True)
        ent_outgoing.write_text(rewritten, encoding="utf-8")
        result.updated_files.append(str(ent_outgoing.relative_to(ent_root)))


def _apply_merge(
    conflict: PromotionConflict,
    ent_root: Path,
    registry: ModelRegistry,
    merged_fields: dict[str, Any],
    result: PromotionResult,
    backups: list[tuple[Path, bytes | None]],
) -> None:
    from src.common.model_write_formatting import format_entity_markdown
    from src.tools.model_write.boundary import today_iso

    ent_path = registry.find_file_by_id(conflict.enterprise_id)
    if not ent_path:
        result.plan.warnings.append(
            f"Enterprise file not found for merge: {conflict.enterprise_id}"
        )
        return

    parsed = parse_entity_file(ent_path)
    fm = dict(parsed.frontmatter)

    content = format_entity_markdown(
        artifact_id=conflict.enterprise_id,
        artifact_type=conflict.artifact_type,
        name=merged_fields.get("name", fm.get("name", "")),
        version=merged_fields.get("version", fm.get("version", "0.1.0")),
        status=merged_fields.get("status", fm.get("status", "draft")),
        last_updated=today_iso(),
        keywords=merged_fields.get("keywords", fm.get("keywords")),
        summary=merged_fields.get("summary", parsed.summary),
        properties=merged_fields.get("properties", parsed.properties),
        notes=merged_fields.get("notes", parsed.notes),
        display_archimate=dict(parsed.display_archimate),
    )
    backups.append((ent_path, ent_path.read_bytes()))
    ent_path.write_text(content, encoding="utf-8")
    result.updated_files.append(str(ent_path.relative_to(ent_root)))


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

def _rollback(
    copied: list[Path],
    backups: list[tuple[Path, bytes | None]],
) -> None:
    for path, original in reversed(backups):
        if original is None:
            if path.exists():
                path.unlink()
        else:
            path.write_bytes(original)
    backed_up = {p for p, _ in backups}
    for f in reversed(copied):
        if f.exists() and f not in backed_up:
            f.unlink()
