"""entity_spec_v2_migration.py — Migrate entity files to the v2 hierarchy-based paths.

Performs two changes per entity file:
1. Strips deprecated ``domain:`` and ``element-type:`` lines from the ``### archimate``
   display block (or any display block identified by section-id).
2. Moves the file from the old plural-subdir path to the new artifact-type-based path
   (e.g. ``model/motivation/requirements/{id}.md``
   → ``model/motivation/requirement/{id}.md``).
   The corresponding ``.outgoing.md`` is moved alongside.

Usage:
    uv run python -m src.infrastructure.migration.entity_spec_v2_migration [ROOT ...]

If no ROOT is given, discovers all repos under the workspace root
(``engagements/*/architecture-repository`` and ``enterprise-repository``).

Dry-run mode (default): prints what would change without writing files.
Pass ``--execute`` to apply changes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"^---\n(.*?\n)---\n", re.DOTALL)
_DISPLAY_SECTION_RE = re.compile(r"<!--\s*§display\s*-->", re.IGNORECASE)
_YAML_FENCE_RE = re.compile(r"(```ya?ml\n)(.*?)(```)", re.DOTALL)
_DEPRECATED_KEYS_RE = re.compile(r"(?m)^(domain|element-type):\s*.*\n?")


def _parse_artifact_type(text: str) -> str | None:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    import yaml as _yaml

    try:
        fm: dict[str, object] = _yaml.safe_load(m.group(1)) or {}
        return str(fm.get("artifact-type", "")) or None
    except Exception:  # noqa: BLE001
        return None


def _strip_display_deprecated(text: str) -> tuple[str, bool]:
    """Remove ``domain:`` and ``element-type:`` from display block YAML.

    Returns ``(updated_text, changed)``.
    """
    disp_start = _DISPLAY_SECTION_RE.search(text)
    if not disp_start:
        return text, False
    before = text[: disp_start.start()]
    display_part = text[disp_start.start() :]
    fence_m = _YAML_FENCE_RE.search(display_part)
    if not fence_m:
        return text, False
    original_yaml = fence_m.group(2)
    cleaned_yaml = _DEPRECATED_KEYS_RE.sub("", original_yaml)
    if cleaned_yaml == original_yaml:
        return text, False
    updated_display = display_part[: fence_m.start(2)] + cleaned_yaml + display_part[fence_m.end(2) :]
    return before + updated_display, True


def migrate_repo(repo_root: Path, *, execute: bool) -> None:
    from src.config.repo_paths import MODEL  # noqa: PLC0415
    from src.domain.module_types import EntityTypeName  # noqa: PLC0415
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415
    from src.infrastructure.write.artifact_write.entity import entity_path  # noqa: PLC0415

    registry = get_module_registry()
    model_root = repo_root / MODEL
    if not model_root.is_dir():
        print(f"  [skip] no model/ directory: {repo_root}")
        return

    moved = stripped = 0
    for md_file in sorted(model_root.rglob("*.md")):
        if md_file.name.endswith(".outgoing.md"):
            continue
        text = md_file.read_text(encoding="utf-8")
        artifact_type = _parse_artifact_type(text)
        if not artifact_type:
            continue
        info = registry.find_entity_type(EntityTypeName(artifact_type))
        if info is None:
            continue
        eid = md_file.stem
        expected_path = entity_path(repo_root, info, eid)

        # 1 — strip deprecated display keys
        new_text, changed = _strip_display_deprecated(text)
        if changed:
            stripped += 1
            if execute:
                md_file.write_text(new_text, encoding="utf-8")
            else:
                print(f"  [strip]  {md_file.relative_to(repo_root)}")
            text = new_text

        # 2 — move if path changed
        if md_file.resolve() != expected_path.resolve():
            moved += 1
            old_outgoing = md_file.with_suffix(".outgoing.md")
            new_outgoing = expected_path.with_suffix(".outgoing.md")
            if execute:
                expected_path.parent.mkdir(parents=True, exist_ok=True)
                md_file.rename(expected_path)
                if old_outgoing.exists():
                    new_outgoing.parent.mkdir(parents=True, exist_ok=True)
                    old_outgoing.rename(new_outgoing)
            else:
                print(f"  [move]   {md_file.relative_to(repo_root)}")
                print(f"        → {expected_path.relative_to(repo_root)}")
                if old_outgoing.exists():
                    print(f"  [move]   {old_outgoing.relative_to(repo_root)}")
                    print(f"        → {new_outgoing.relative_to(repo_root)}")

    action = "Migrated" if execute else "Would migrate"
    print(f"  {action}: {moved} moved, {stripped} stripped — {repo_root}")


def _discover_repos(workspace_root: Path) -> list[Path]:
    repos: list[Path] = []
    ent = workspace_root / "enterprise-repository"
    if ent.is_dir():
        repos.append(ent)
    for eng_arch in sorted(workspace_root.glob("engagements/*/architecture-repository")):
        repos.append(eng_arch)
    return repos


def main() -> None:
    args = sys.argv[1:]
    execute = "--execute" in args
    paths = [a for a in args if not a.startswith("--")]

    if paths:
        roots = [Path(p).resolve() for p in paths]
    else:
        workspace = Path.cwd()
        roots = _discover_repos(workspace)
        if not roots:
            print("ERROR: no repos found and no paths given. Run from the workspace root.", file=sys.stderr)
            sys.exit(1)

    mode = "EXECUTE" if execute else "DRY-RUN"
    print(f"=== entity_spec_v2_migration [{mode}] ===")
    if not execute:
        print("(pass --execute to apply changes)\n")

    for root in roots:
        print(f"\n>>> {root}")
        migrate_repo(root, execute=execute)


if __name__ == "__main__":
    main()
