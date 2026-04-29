"""Execute a promotion plan — copy artifact files to enterprise repo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.application.artifact_query import ArtifactRepository
from src.application.verification.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.config.repo_paths import MODEL
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.rendering.generate_macros import generate_macros
from src.infrastructure.write.artifact_write._promote_conflicts import build_handler
from src.infrastructure.write.artifact_write._promote_file_ops import (
    copy_entity,
    copy_simple,
    make_target_resolver,
    rollback,
    update_body_references,
    update_outgoing_references,
)
from src.infrastructure.write.artifact_write.parse_existing import parse_entity_file
from src.infrastructure.write.artifact_write.promote_to_enterprise import (
    ConflictResolution,
    PromotionPlan,
    PromotionResult,
)


def execute_promotion(
    plan: PromotionPlan,
    engagement_root: Path,
    enterprise_root: Path,
    verifier: ArtifactVerifier,
    registry: ArtifactRegistry,
    *,
    conflict_resolutions: list[ConflictResolution] | None = None,
) -> PromotionResult:
    result = PromotionResult(plan=plan, executed=False)
    if plan.schema_errors:
        result.verification_errors = list(plan.schema_errors)
        return result
    ent_copied: list[Path] = []
    ent_backups: list[tuple[Path, bytes | None]] = []

    from src.infrastructure.write.artifact_write.global_artifact_reference import build_gar_map

    eng_repo = ArtifactRepository(shared_artifact_index(engagement_root))
    gar_map = build_gar_map(eng_repo)
    promoted_ids = set(plan.entities_to_add) | {c.engagement_id for c in plan.conflicts}
    resolve_target = make_target_resolver(gar_map, promoted_ids, registry.enterprise_entity_ids())
    conn_ids = set(plan.connection_ids)
    resolutions = {r.engagement_id: r for r in (conflict_resolutions or [])}

    try:
        for eid in plan.entities_to_add:
            copy_entity(
                eid,
                engagement_root,
                enterprise_root,
                registry,
                result,
                ent_copied,
                ent_backups,
                resolve_target,
                conn_ids,
            )

        for conflict in plan.conflicts:
            res = resolutions.get(conflict.engagement_id)
            if res is None:
                result.plan.warnings.append(f"No resolution for conflict {conflict.engagement_id} — skipped")
                continue
            handler = build_handler(res)
            if handler is None:
                result.plan.warnings.append(
                    f"Unrecognised resolution strategy {res.strategy!r} for {conflict.engagement_id} — skipped"
                )
                continue
            handler.handle(
                conflict,
                engagement_root,
                enterprise_root,
                registry,
                result,
                ent_backups,
                resolve_target,
                conn_ids,
            )

        for did in plan.documents_to_add:
            copy_simple(did, engagement_root, enterprise_root, registry, result, ent_copied, ent_backups)
        for dc in plan.doc_conflicts:
            _resolve_simple_conflict(
                dc,
                "document",
                engagement_root,
                enterprise_root,
                registry,
                result,
                ent_backups,
                resolutions,
            )

        for did in plan.diagrams_to_add:
            copy_simple(did, engagement_root, enterprise_root, registry, result, ent_copied, ent_backups)
        for diag_dc in plan.diagram_conflicts:
            _resolve_simple_conflict(
                diag_dc,
                "diagram",
                engagement_root,
                enterprise_root,
                registry,
                result,
                ent_backups,
                resolutions,
            )

        if (enterprise_root / MODEL).is_dir():
            try:
                generate_macros(enterprise_root)
            except Exception:  # noqa: BLE001
                pass

        ent_registry = ArtifactRegistry(shared_artifact_index(enterprise_root))
        errors = [
            f"{i.code}: {i.message} ({i.location})"
            for r in ArtifactVerifier(ent_registry).verify_all(enterprise_root, include_diagrams=False)
            for i in r.issues
            if i.severity == "error"
        ]
        result.verification_errors = errors

        if errors:
            rollback(ent_copied, ent_backups)
            result.rolled_back = True
            return result

        result.executed = True

        for eid in list(plan.entities_to_add) + [c.engagement_id for c in plan.conflicts]:
            _replace_artifact_with_gar(eid, engagement_root, eng_repo, registry, result, "entity")

        def _accepted(confs: list[Any]) -> list[str]:
            return [
                c.engagement_id
                for c in confs
                if resolutions.get(c.engagement_id) and resolutions[c.engagement_id].strategy == "accept_engagement"
            ]

        for did in plan.documents_to_add + _accepted(plan.doc_conflicts):
            doc = eng_repo.get_document(did)
            _replace_artifact_with_gar(
                did,
                engagement_root,
                eng_repo,
                registry,
                result,
                "document",
                name=doc.title if doc else did,
            )
        for did in plan.diagrams_to_add + _accepted(plan.diagram_conflicts):
            diag = eng_repo.get_diagram(did)
            _replace_artifact_with_gar(
                did,
                engagement_root,
                eng_repo,
                registry,
                result,
                "diagram",
                name=diag.name if diag else did,
            )

        try:
            generate_macros(engagement_root)
        except Exception:  # noqa: BLE001
            pass

    except Exception as exc:
        rollback(ent_copied, ent_backups)
        result.rolled_back = True
        result.executed = False
        result.verification_errors.append(str(exc))

    return result


def _resolve_simple_conflict(
    dc: Any,
    kind: str,
    eng_root: Path,
    ent_root: Path,
    registry: Any,
    result: Any,
    backups: list[Any],
    resolutions: dict[str, Any],
) -> None:
    res = resolutions.get(dc.engagement_id)
    if res and res.strategy == "accept_engagement":
        eng_path = registry.find_file_by_id(dc.engagement_id)
        ent_path = registry.find_file_by_id(dc.enterprise_id)
        if not eng_path or not ent_path:
            result.plan.warnings.append(f"Could not find files for conflict {dc.engagement_id}")
            return
        content = eng_path.read_text(encoding="utf-8").replace(dc.engagement_id, dc.enterprise_id, 1)
        backups.append((ent_path, ent_path.read_bytes()))
        ent_path.write_text(content, encoding="utf-8")
        result.updated_files.append(str(ent_path.relative_to(ent_root)))
    elif res and res.strategy not in ("accept_enterprise", None):
        result.plan.warnings.append(f"Merge not supported for {kind}s; skipping {dc.engagement_id}")


def _replace_artifact_with_gar(
    aid: str,
    eng_root: Path,
    eng_repo: Any,
    registry: Any,
    result: Any,
    artifact_type: str,
    *,
    name: str | None = None,
) -> None:
    """Replace a promoted engagement artifact with a GAR proxy."""
    src = registry.find_file_by_id(aid)
    if src is None or not src.is_relative_to(eng_root):
        return
    entity_subtype: str | None = None
    if name is None or artifact_type == "entity":
        try:
            parsed = parse_entity_file(src)
            if name is None:
                name = str(parsed.frontmatter.get("name", aid))
            if artifact_type == "entity":
                entity_subtype = str(parsed.frontmatter.get("artifact-type", "")) or None
        except Exception:  # noqa: BLE001
            if name is None:
                name = aid

    from src.infrastructure.write.artifact_write.global_artifact_reference import ensure_global_artifact_reference

    gar_result = ensure_global_artifact_reference(
        engagement_repo=eng_repo,
        engagement_root=eng_root,
        verifier=ArtifactVerifier(None),
        clear_repo_caches=lambda _: None,
        global_artifact_id=aid,
        global_artifact_name=name,
        global_artifact_type=artifact_type,
        global_artifact_entity_type=entity_subtype,
        dry_run=False,
    )
    result.updated_files.append(f"[created GAR] {gar_result.artifact_id}")

    if artifact_type == "entity":
        update_outgoing_references(aid, gar_result.artifact_id, eng_root, result)
    else:
        update_body_references(aid, eng_root, result)

    try:
        src.unlink()
        result.updated_files.append(f"[removed] {src.relative_to(eng_root)}")
    except OSError:
        pass
    if artifact_type == "entity":
        outgoing = src.with_suffix(".outgoing.md")
        if outgoing.exists():
            try:
                outgoing.unlink()
                result.updated_files.append(f"[removed] {outgoing.relative_to(eng_root)}")
            except OSError:
                pass
