"""CLI for engagement-repository write operations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.common.model_verifier import ModelRegistry
from src.tools.model_write import delete_diagram, delete_entity
from src.tools.workspace_init import load_init_state


def _default_repo_root() -> Path | None:
    state = load_init_state()
    if state and "engagement_root" in state:
        return Path(state["engagement_root"])
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arch-model-write")
    parser.add_argument(
        "--repo-root",
        default=str(_default_repo_root()) if _default_repo_root() else None,
        help="Engagement repository root (default: arch-init state)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    delete_entity_parser = sub.add_parser("delete-entity", help="Delete an entity from the engagement repo")
    delete_entity_parser.add_argument("artifact_id")
    delete_entity_parser.add_argument("--dry-run", action="store_true")

    delete_diagram_parser = sub.add_parser("delete-diagram", help="Delete a diagram from the engagement repo")
    delete_diagram_parser.add_argument("artifact_id")
    delete_diagram_parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.repo_root:
        parser.error("No --repo-root given and no arch-init state found.")
    repo_root = Path(args.repo_root)
    registry = ModelRegistry(repo_root)

    try:
        if args.command == "delete-entity":
            result = delete_entity(
                repo_root=repo_root,
                registry=registry,
                clear_repo_caches=lambda _: None,
                artifact_id=args.artifact_id,
                dry_run=bool(args.dry_run),
            )
        else:
            result = delete_diagram(
                repo_root=repo_root,
                clear_repo_caches=lambda _: None,
                artifact_id=args.artifact_id,
                dry_run=bool(args.dry_run),
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if result.content:
        print(result.content)
    else:
        action = "Would delete" if args.dry_run else "Deleted"
        print(f"{action} {args.command.split('-', 1)[1]} '{result.artifact_id}' at {result.path}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
