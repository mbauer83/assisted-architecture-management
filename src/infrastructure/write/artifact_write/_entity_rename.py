"""File-mechanics for renaming an entity's identity and moving its outgoing files."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from pathlib import Path

from src.application.repo_path_helpers import all_model_roots, docs_root, rewrite_doc_link

_MD_LINK_RE = re.compile(r"(\[[^\]]*\]\()([^)\s]+)(\))")


def rewrite_document_links_for_moved_entity(
    *, repo_root: Path, old_path: Path, new_path: Path
) -> list[Path]:
    """Rewrite markdown-body relative links that point at an entity's old path.

    Best-effort cosmetic update, mirroring rewrite_outgoing_referrers() for
    connection sidecars — entity moves (group re-home or rename) change the
    file's location, but nothing else updates a hand-authored `[label](../..
    /old/path.md)` link elsewhere in the docs tree.
    """
    changed: list[Path] = []
    doc_root = docs_root(repo_root)
    if not doc_root.exists():
        return changed
    for doc_path in doc_root.rglob("*.md"):
        text = doc_path.read_text(encoding="utf-8")

        def _replace(match: re.Match[str]) -> str:
            prefix, target, suffix = match.group(1), match.group(2), match.group(3)
            if target.startswith(("http://", "https://", "#", "mailto:")):
                return match.group(0)
            rewritten = rewrite_doc_link(
                target,
                doc_old_dir=doc_path.parent,
                doc_new_dir=doc_path.parent,
                target_old_path=old_path,
                target_new_path=new_path,
            )
            return f"{prefix}{rewritten}{suffix}" if rewritten != target else match.group(0)

        new_text = _MD_LINK_RE.sub(_replace, text)
        if new_text != text:
            doc_path.write_text(new_text, encoding="utf-8")
            changed.append(doc_path)
    return changed


def rename_entity_via_m4(
    *,
    entity_file: Path,
    target_entity_file: Path,
    new_content: str,
    repo_root: Path,
    artifact_id: str,
    effective_artifact_id: str,
    rebuild_index: Callable[[], None],
    on_boundary: Callable[[str], None] | None = None,
) -> list[Path]:
    """Commit an entity + outgoing sidecar rename atomically via M4.

    Manifest: create new entity, create new sidecar, delete old entity, delete old sidecar.
    Referrer slug-hint rewrites are NOT included; call rewrite_outgoing_referrers() separately.
    Returns [old_entity, new_entity, old_sidecar, new_sidecar].
    """
    from src.infrastructure.write.artifact_write.m4_transaction import (
        ManifestEntry,
        TransactionManifest,
        ensure_transactions_root,
        fsync_directory,
        hash_file,
        publish_transaction,
        write_transaction_intent,
    )

    old_sidecar = entity_file.with_suffix(".outgoing.md")
    new_sidecar = target_entity_file.with_suffix(".outgoing.md")

    old_entity_rel = entity_file.relative_to(repo_root).as_posix()
    new_entity_rel = target_entity_file.relative_to(repo_root).as_posix()
    old_sidecar_rel = old_sidecar.relative_to(repo_root).as_posix()
    new_sidecar_rel = new_sidecar.relative_to(repo_root).as_posix()

    sidecar_content = old_sidecar.read_text(encoding="utf-8").replace(artifact_id, effective_artifact_id)

    # Step 1: create transaction dir + staged root
    txns_dir = ensure_transactions_root(repo_root)
    fsync_directory(txns_dir.parent)
    txn_dir = txns_dir / f"rename-{uuid.uuid4().hex}"
    txn_dir.mkdir()
    fsync_directory(txns_dir)

    staged = txn_dir / "staged"
    staged.mkdir()

    # Write payloads to staged root
    (staged / new_entity_rel).parent.mkdir(parents=True, exist_ok=True)
    (staged / new_entity_rel).write_text(new_content, encoding="utf-8")
    (staged / new_sidecar_rel).parent.mkdir(parents=True, exist_ok=True)
    (staged / new_sidecar_rel).write_text(sidecar_content, encoding="utf-8")

    entries = [
        ManifestEntry(
            kind="create",
            dest=new_entity_rel,
            target_hash=hash_file(staged / new_entity_rel),
            prior_hash_or_absent="absent",
            payload="payloads/entity",
        ),
        ManifestEntry(
            kind="delete",
            dest=old_entity_rel,
            target_hash="absent",
            prior_hash_or_absent=hash_file(entity_file),
            payload=None,
        ),
        ManifestEntry(
            kind="create",
            dest=new_sidecar_rel,
            target_hash=hash_file(staged / new_sidecar_rel),
            prior_hash_or_absent="absent",
            payload="payloads/sidecar",
        ),
        ManifestEntry(
            kind="delete",
            dest=old_sidecar_rel,
            target_hash="absent",
            prior_hash_or_absent=hash_file(old_sidecar),
            payload=None,
        ),
    ]
    manifest = TransactionManifest(entries=entries)
    write_transaction_intent(
        repo_root=repo_root,
        transaction_dir=txn_dir,
        staged_root=staged,
        manifest=manifest,
        on_boundary=on_boundary,
    )
    publish_transaction(
        repo_root=repo_root,
        transaction_dir=txn_dir,
        manifest=manifest,
        rebuild_index=rebuild_index,
        on_boundary=on_boundary,
    )
    return [entity_file, target_entity_file, old_sidecar, new_sidecar]


def rewrite_outgoing_referrers(
    *,
    repo_root: Path,
    old_artifact_id: str,
    new_artifact_id: str,
    exclude_path: Path | None = None,
) -> list[Path]:
    """Rewrite slug hints in outgoing files that reference old_artifact_id.

    Best-effort cosmetic update; not part of any M4 transaction.
    """
    changed: list[Path] = []
    for model_root in all_model_roots(repo_root):
        for outgoing_path in model_root.rglob("*.outgoing.md"):
            if exclude_path is not None and outgoing_path == exclude_path:
                continue
            text = outgoing_path.read_text(encoding="utf-8")
            if old_artifact_id not in text:
                continue
            outgoing_path.write_text(text.replace(old_artifact_id, new_artifact_id), encoding="utf-8")
            changed.append(outgoing_path)
    return changed


# ---------------------------------------------------------------------------
# Legacy helpers kept for the sidecar-less rename path in entity_edit.py
# ---------------------------------------------------------------------------


def rename_entity_identity(
    *,
    entity_file: Path,
    repo_root: Path,
    old_artifact_id: str,
    new_artifact_id: str,
) -> tuple[Path, list[Path]]:
    """Rewrite the entity's own outgoing file and every referrer from old id to new id."""
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

    for model_root in all_model_roots(repo_root):
        for outgoing_path in model_root.rglob("*.outgoing.md"):
            if outgoing_path == new_outgoing:
                continue
            text = outgoing_path.read_text(encoding="utf-8")
            if old_artifact_id not in text:
                continue
            outgoing_path.write_text(text.replace(old_artifact_id, new_artifact_id), encoding="utf-8")
            changed_paths.append(outgoing_path)

    return new_entity_file, changed_paths


def persist_rename(
    *, entity_file: Path, target_entity_file: Path, repo_root: Path, artifact_id: str, effective_artifact_id: str
) -> list[Path]:
    """Move the old entity file's identity to the new id, also relocating outgoing files on a group-move."""
    entity_file.unlink()
    _, renamed_paths = rename_entity_identity(
        entity_file=entity_file,
        repo_root=repo_root,
        old_artifact_id=artifact_id,
        new_artifact_id=effective_artifact_id,
    )
    if target_entity_file.parent != entity_file.parent:
        for outgoing_src in (
            entity_file.with_suffix(".outgoing.md"),
            entity_file.with_name(f"{effective_artifact_id}.outgoing.md"),
        ):
            if outgoing_src.exists():
                new_outgoing = target_entity_file.with_suffix(".outgoing.md")
                new_outgoing.parent.mkdir(parents=True, exist_ok=True)
                outgoing_src.rename(new_outgoing)
                renamed_paths.extend([outgoing_src, new_outgoing])
                break
    return renamed_paths
