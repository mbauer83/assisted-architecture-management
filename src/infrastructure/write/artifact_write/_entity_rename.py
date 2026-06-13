"""File-mechanics for renaming an entity's identity and moving its outgoing files."""

from __future__ import annotations

from pathlib import Path

from src.application.repo_path_helpers import all_model_roots


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
