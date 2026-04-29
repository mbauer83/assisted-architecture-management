"""Low-level file operations for the promotion workflow."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Callable

from src.config.repo_paths import DOCS, MODEL

TargetResolver = Callable[[str], str | None]


def make_target_resolver(
    gar_map: dict[str, str],
    promoted_ids: set[str],
    enterprise_ids: set[str],
) -> TargetResolver:
    keep_ids = promoted_ids | enterprise_ids

    def resolve(target_id: str) -> str | None:
        eid = gar_map.get(target_id)
        return eid if eid is not None else (target_id if target_id in keep_ids else None)

    return resolve


def copy_entity(
    eid: str,
    eng_root: Path,
    ent_root: Path,
    registry: Any,
    result: Any,
    copied: list[Path],
    backups: list[Any],
    resolve_target: TargetResolver,
    conn_ids: Any,
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
        dest_out.parent.mkdir(parents=True, exist_ok=True)
        dest_out.write_text(
            rewrite_outgoing(
                outgoing.read_text(encoding="utf-8"),
                resolve_target=resolve_target,
                result=result,
                conn_ids=None,
            ),
            encoding="utf-8",
        )
        copied.append(dest_out)
        result.copied_files.append(str(outgoing.relative_to(eng_root)))


def copy_simple(
    aid: str,
    eng_root: Path,
    ent_root: Path,
    registry: Any,
    result: Any,
    copied: list[Path],
    backups: list[Any],
) -> None:
    """Copy a document or diagram file verbatim to enterprise."""
    src = registry.find_file_by_id(aid)
    if src is None:
        result.verification_errors.append(f"File not found for {aid}")
        return
    rel = src.relative_to(eng_root)
    dest = ent_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    backups.append((dest, dest.read_bytes() if dest.exists() else None))
    shutil.copy2(src, dest)
    copied.append(dest)
    result.copied_files.append(str(rel))


def update_outgoing_references(old_id: str, new_id: str, eng_root: Path, result: Any) -> None:
    model_dir = eng_root / MODEL
    if not model_dir.is_dir():
        return
    pattern = re.compile(rf"(^### .+? → ){re.escape(old_id)}$", re.MULTILINE)
    for f in model_dir.rglob("*.outgoing.md"):
        content = f.read_text(encoding="utf-8")
        updated, n = pattern.subn(rf"\g<1>{new_id}", content)
        if n > 0:
            f.write_text(updated, encoding="utf-8")
            result.updated_files.append(f"[ref-updated ×{n}] {f.relative_to(eng_root)}")


def update_body_references(old_id: str, eng_root: Path, result: Any) -> None:
    docs_dir = eng_root / DOCS
    if not docs_dir.is_dir():
        return
    pat = re.compile(rf"\]\(\s*([^)]*?{re.escape(old_id)}[^)]*?)\s*\)")
    for f in docs_dir.rglob("*.md"):
        content = f.read_text(encoding="utf-8")
        if old_id not in content:
            continue
        _, n = pat.subn(f"](GAR-proxy-for-{old_id})", content)
        if n > 0:
            result.updated_files.append(
                f"[link-stale ×{n}] {f.relative_to(eng_root)} — links to promoted artifact {old_id} may need updating"
            )


def rewrite_outgoing(
    content: str,
    *,
    resolve_target: TargetResolver,
    result: Any,
    conn_ids: set[str] | None = None,
) -> str:
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
            if m:
                source_entity_id = m.group(1).strip()
        m = _CONN_HEADER.match(stripped)
        if m:
            conn_type, target_id = m.group(1).strip(), m.group(2).strip()
            conn_aid = f"{source_entity_id}---{target_id}@@{conn_type}" if source_entity_id else None
            if conn_ids is not None and conn_aid is not None and conn_aid not in conn_ids:
                drop_section = True
                continue
            resolved = resolve_target(target_id)
            if resolved is None:
                result.plan.warnings.append(
                    f"Dropped connection → {target_id!r}: engagement-only entity not in promotion set"
                )
                drop_section = True
                continue
            drop_section = False
            if resolved != target_id:
                line = line.replace(target_id, resolved, 1)
        elif drop_section:
            if not stripped or stripped.startswith("### "):
                drop_section = False
                if stripped.startswith("### "):
                    out.append(line)
                    continue
            continue
        out.append(line)
    return "".join(out)


def rollback(copied: list[Path], backups: list[tuple[Path, bytes | None]]) -> None:
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
