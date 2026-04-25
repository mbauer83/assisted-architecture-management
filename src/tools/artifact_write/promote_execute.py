"""Execute a promotion plan — copy artifact files to enterprise repo."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Callable, Protocol
from dataclasses import dataclass

from src.common.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.common.artifact_query import ArtifactRepository
from src.tools.generate_macros import generate_macros
from src.tools.artifact_write.parse_existing import parse_entity_file
from src.tools.artifact_write.promote_to_enterprise import (
    ConflictResolution, PromotionConflict, PromotionPlan, PromotionResult,
)

TargetResolver = Callable[[str], str | None]


def make_target_resolver(gar_map: dict[str, str], promoted_ids: set[str], enterprise_ids: set[str]) -> TargetResolver:
    keep_ids = promoted_ids | enterprise_ids
    def resolve(target_id: str) -> str | None:
        eid = gar_map.get(target_id)
        return eid if eid is not None else (target_id if target_id in keep_ids else None)
    return resolve


class _ConflictHandler(Protocol):
    def handle(self, conflict, eng_root, ent_root, registry, result, backups, resolve_target, conn_ids): ...

class _AcceptEnterpriseHandler:
    def handle(self, conflict, eng_root, ent_root, registry, result, backups, resolve_target, conn_ids): pass

@dataclass
class _AcceptEngagementHandler:
    def handle(self, conflict, eng_root, ent_root, registry, result, backups, resolve_target, conn_ids):
        _replace_enterprise_content(conflict, eng_root, ent_root, registry, result, backups, resolve_target, conn_ids)

@dataclass
class _MergeHandler:
    merged_fields: dict[str, Any]
    def handle(self, conflict, eng_root, ent_root, registry, result, backups, resolve_target, conn_ids):
        _apply_merge(conflict, ent_root, registry, self.merged_fields, result, backups)

def _build_handler(resolution: ConflictResolution) -> _ConflictHandler | None:
    match resolution.strategy:
        case "accept_enterprise": return _AcceptEnterpriseHandler()
        case "accept_engagement": return _AcceptEngagementHandler()
        case "merge" if resolution.merged_fields: return _MergeHandler(merged_fields=resolution.merged_fields)
        case _: return None


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
        result.verification_errors = list(plan.schema_errors); return result
    ent_copied: list[Path] = []
    ent_backups: list[tuple[Path, bytes | None]] = []

    from src.tools.artifact_write.global_artifact_reference import build_gar_map
    eng_repo = ArtifactRepository(engagement_root)
    gar_map = build_gar_map(eng_repo)
    promoted_ids = set(plan.entities_to_add) | {c.engagement_id for c in plan.conflicts}
    resolve_target = make_target_resolver(gar_map, promoted_ids, registry.enterprise_entity_ids())
    conn_ids = set(plan.connection_ids)
    resolutions = {r.engagement_id: r for r in (conflict_resolutions or [])}

    try:
        for eid in plan.entities_to_add:
            _copy_entity(eid, engagement_root, enterprise_root, registry, result, ent_copied, ent_backups, resolve_target, conn_ids)

        for conflict in plan.conflicts:
            res = resolutions.get(conflict.engagement_id)
            if res is None:
                result.plan.warnings.append(f"No resolution for conflict {conflict.engagement_id} — skipped")
                continue
            handler = _build_handler(res)
            if handler is None:
                result.plan.warnings.append(f"Unrecognised resolution strategy {res.strategy!r} for {conflict.engagement_id} — skipped")
                continue
            handler.handle(conflict, engagement_root, enterprise_root, registry, result, ent_backups, resolve_target, conn_ids)

        for did in plan.documents_to_add:
            _copy_simple(did, engagement_root, enterprise_root, registry, result, ent_copied, ent_backups)
        for dc in plan.doc_conflicts:
            _resolve_simple_conflict(dc, "document", engagement_root, enterprise_root, registry, result, ent_backups, resolutions)

        for did in plan.diagrams_to_add:
            _copy_simple(did, engagement_root, enterprise_root, registry, result, ent_copied, ent_backups)
        for dc in plan.diagram_conflicts:
            _resolve_simple_conflict(dc, "diagram", engagement_root, enterprise_root, registry, result, ent_backups, resolutions)

        if (enterprise_root / "model").is_dir():
            try: generate_macros(enterprise_root)
            except Exception: pass

        ent_registry = ArtifactRegistry(enterprise_root)
        errors = [
            f"{i.code}: {i.message} ({i.location})"
            for r in ArtifactVerifier(ent_registry).verify_all(enterprise_root, include_diagrams=False)
            for i in r.issues if i.severity == "error"
        ]
        result.verification_errors = errors

        if errors:
            _rollback(ent_copied, ent_backups)
            result.rolled_back = True
            return result

        result.executed = True

        for eid in list(plan.entities_to_add) + [c.engagement_id for c in plan.conflicts]:
            _replace_artifact_with_gar(eid, engagement_root, eng_repo, registry, result, "entity")

        _accepted = lambda confs: [c.engagement_id for c in confs if resolutions.get(c.engagement_id) and resolutions[c.engagement_id].strategy == "accept_engagement"]
        for did in plan.documents_to_add + _accepted(plan.doc_conflicts):
            doc = eng_repo.get_document(did)
            _replace_artifact_with_gar(did, engagement_root, eng_repo, registry, result, "document", name=doc.title if doc else did)
        for did in plan.diagrams_to_add + _accepted(plan.diagram_conflicts):
            diag = eng_repo.get_diagram(did)
            _replace_artifact_with_gar(did, engagement_root, eng_repo, registry, result, "diagram", name=diag.name if diag else did)

        try: generate_macros(engagement_root)
        except Exception: pass

    except Exception as exc:
        _rollback(ent_copied, ent_backups)
        result.rolled_back = True
        result.executed = False
        result.verification_errors.append(str(exc))

    return result


def _copy_entity(eid, eng_root, ent_root, registry, result, copied, backups, resolve_target, conn_ids):
    src = registry.find_file_by_id(eid)
    if src is None:
        result.verification_errors.append(f"File not found for {eid}")
        return
    rel = src.relative_to(eng_root)
    dest = ent_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    backups.append((dest, dest.read_bytes() if dest.exists() else None))
    shutil.copy2(src, dest)
    copied.append(dest); result.copied_files.append(str(rel))

    outgoing = src.with_suffix(".outgoing.md")
    if outgoing.exists():
        dest_out = ent_root / outgoing.relative_to(eng_root)
        backups.append((dest_out, dest_out.read_bytes() if dest_out.exists() else None))
        dest_out.parent.mkdir(parents=True, exist_ok=True)
        dest_out.write_text(_rewrite_outgoing(outgoing.read_text(encoding="utf-8"), resolve_target=resolve_target, result=result, conn_ids=None), encoding="utf-8")
        copied.append(dest_out); result.copied_files.append(str(outgoing.relative_to(eng_root)))


def _copy_simple(aid, eng_root, ent_root, registry, result, copied, backups):
    """Copy a document or diagram file verbatim to enterprise."""
    src = registry.find_file_by_id(aid)
    if src is None:
        result.verification_errors.append(f"File not found for {aid}"); return
    rel = src.relative_to(eng_root)
    dest = ent_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    backups.append((dest, dest.read_bytes() if dest.exists() else None))
    shutil.copy2(src, dest)
    copied.append(dest); result.copied_files.append(str(rel))


def _resolve_simple_conflict(dc, kind, eng_root, ent_root, registry, result, backups, resolutions):
    res = resolutions.get(dc.engagement_id)
    if res and res.strategy == "accept_engagement":
        eng_path = registry.find_file_by_id(dc.engagement_id)
        ent_path = registry.find_file_by_id(dc.enterprise_id)
        if not eng_path or not ent_path:
            result.plan.warnings.append(f"Could not find files for conflict {dc.engagement_id}"); return
        content = eng_path.read_text(encoding="utf-8").replace(dc.engagement_id, dc.enterprise_id, 1)
        backups.append((ent_path, ent_path.read_bytes()))
        ent_path.write_text(content, encoding="utf-8")
        result.updated_files.append(str(ent_path.relative_to(ent_root)))
    elif res and res.strategy not in ("accept_enterprise", None):
        result.plan.warnings.append(f"Merge not supported for {kind}s; skipping {dc.engagement_id}")


def _replace_artifact_with_gar(aid, eng_root, eng_repo, registry, result, artifact_type, *, name: str | None = None):
    """Replace a promoted engagement artifact with a GAR proxy."""
    src = registry.find_file_by_id(aid)
    if src is None or not src.is_relative_to(eng_root):
        return
    entity_subtype: str | None = None
    if name is None or artifact_type == "entity":
        try:
            parsed = parse_entity_file(src)
            if name is None: name = str(parsed.frontmatter.get("name", aid))
            if artifact_type == "entity": entity_subtype = str(parsed.frontmatter.get("artifact-type", "")) or None
        except Exception:
            if name is None: name = aid

    from src.tools.artifact_write.global_artifact_reference import ensure_global_artifact_reference
    gar_result = ensure_global_artifact_reference(
        engagement_repo=eng_repo, engagement_root=eng_root, verifier=ArtifactVerifier(None),
        clear_repo_caches=lambda _: None, global_artifact_id=aid,
        global_artifact_name=name, global_artifact_type=artifact_type,
        global_artifact_entity_type=entity_subtype, dry_run=False,
    )
    result.updated_files.append(f"[created GAR] {gar_result.artifact_id}")

    if artifact_type == "entity":
        _update_outgoing_references(aid, gar_result.artifact_id, eng_root, result)
    else:
        _update_body_references(aid, eng_root, result)

    try:
        src.unlink(); result.updated_files.append(f"[removed] {src.relative_to(eng_root)}")
    except OSError: pass
    if artifact_type == "entity":
        outgoing = src.with_suffix(".outgoing.md")
        if outgoing.exists():
            try:
                outgoing.unlink(); result.updated_files.append(f"[removed] {outgoing.relative_to(eng_root)}")
            except OSError: pass


def _update_outgoing_references(old_id, new_id, eng_root, result):
    model_dir = eng_root / "model"
    if not model_dir.is_dir(): return
    pattern = re.compile(rf"(^### .+? → ){re.escape(old_id)}$", re.MULTILINE)
    for f in model_dir.rglob("*.outgoing.md"):
        content = f.read_text(encoding="utf-8")
        updated, n = pattern.subn(rf"\g<1>{new_id}", content)
        if n > 0:
            f.write_text(updated, encoding="utf-8")
            result.updated_files.append(f"[ref-updated ×{n}] {f.relative_to(eng_root)}")


def _update_body_references(old_id, eng_root, result):
    docs_dir = eng_root / "documents"
    if not docs_dir.is_dir(): return
    pat = re.compile(rf"\]\(\s*([^)]*?{re.escape(old_id)}[^)]*?)\s*\)")
    for f in docs_dir.rglob("*.md"):
        content = f.read_text(encoding="utf-8")
        if old_id not in content: continue
        _, n = pat.subn(f"](GAR-proxy-for-{old_id})", content)
        if n > 0:
            result.updated_files.append(f"[link-stale ×{n}] {f.relative_to(eng_root)} — links to promoted artifact {old_id} may need updating")


def _rewrite_outgoing(content, *, resolve_target, result, conn_ids=None):
    _CONN_HEADER = re.compile(r"^### (.+?) → (.+)$")
    _SOURCE_ENTITY = re.compile(r"^source-entity:\s*(.+?)\s*$")
    lines = content.splitlines(keepends=True)
    out: list[str] = []
    drop_section = False
    source_entity_id: str | None = None

    for line in lines:
        stripped = line.rstrip("\n")
        if source_entity_id is None:
            m = _SOURCE_ENTITY.match(stripped)
            if m: source_entity_id = m.group(1).strip()
        m = _CONN_HEADER.match(stripped)
        if m:
            conn_type, target_id = m.group(1).strip(), m.group(2).strip()
            conn_aid = f"{source_entity_id}---{target_id}@@{conn_type}" if source_entity_id else None
            if conn_ids is not None and conn_aid is not None and conn_aid not in conn_ids:
                drop_section = True; continue
            resolved = resolve_target(target_id)
            if resolved is None:
                result.plan.warnings.append(f"Dropped connection → {target_id!r}: engagement-only entity not in promotion set")
                drop_section = True; continue
            drop_section = False
            if resolved != target_id:
                line = line.replace(target_id, resolved, 1)
        elif drop_section:
            if not stripped or stripped.startswith("### "):
                drop_section = False
                if stripped.startswith("### "):
                    out.append(line); continue
            continue
        out.append(line)
    return "".join(out)


def _replace_enterprise_content(conflict, eng_root, ent_root, registry, result, backups, resolve_target, conn_ids):
    ent_path = registry.find_file_by_id(conflict.enterprise_id)
    eng_path = registry.find_file_by_id(conflict.engagement_id)
    if not ent_path or not eng_path:
        result.plan.warnings.append(f"Could not find files for conflict {conflict.engagement_id}"); return
    content = eng_path.read_text(encoding="utf-8").replace(conflict.engagement_id, conflict.enterprise_id, 1)
    backups.append((ent_path, ent_path.read_bytes()))
    ent_path.write_text(content, encoding="utf-8")
    result.updated_files.append(str(ent_path.relative_to(ent_root)))
    eng_outgoing = eng_path.with_suffix(".outgoing.md")
    if eng_outgoing.exists():
        ent_outgoing = ent_root / eng_outgoing.relative_to(eng_root)
        backups.append((ent_outgoing, ent_outgoing.read_bytes() if ent_outgoing.exists() else None))
        rewritten = _rewrite_outgoing(eng_outgoing.read_text(encoding="utf-8"), resolve_target=resolve_target, result=result, conn_ids=conn_ids).replace(conflict.engagement_id, conflict.enterprise_id, 1)
        ent_outgoing.parent.mkdir(parents=True, exist_ok=True)
        ent_outgoing.write_text(rewritten, encoding="utf-8")
        result.updated_files.append(str(ent_outgoing.relative_to(ent_root)))


def _apply_merge(conflict, ent_root, registry, merged_fields, result, backups):
    from src.common.artifact_write_formatting import format_entity_markdown
    from src.tools.artifact_write.boundary import today_iso
    ent_path = registry.find_file_by_id(conflict.enterprise_id)
    if not ent_path:
        result.plan.warnings.append(f"Enterprise file not found for merge: {conflict.enterprise_id}"); return
    parsed = parse_entity_file(ent_path)
    fm = dict(parsed.frontmatter)
    content = format_entity_markdown(
        artifact_id=conflict.enterprise_id, artifact_type=conflict.artifact_type,
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


def _rollback(copied, backups):
    for path, original in reversed(backups):
        if original is None:
            if path.exists(): path.unlink()
        else:
            path.write_bytes(original)
    backed_up = {p for p, _ in backups}
    for f in reversed(copied):
        if f.exists() and f not in backed_up:
            f.unlink()
