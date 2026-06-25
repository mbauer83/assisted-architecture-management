from __future__ import annotations

import argparse
import os
from pathlib import Path

from src.application.git_repair import execute_git_repair
from src.domain.git_repair import RepairState
from src.infrastructure.git.git_auth import (
    GitCredentials,
    build_git_env,
    collect_credentials,
    create_askpass_script,
    register_token_file,
)
from src.infrastructure.git.repair_adapter import GitRepairAdapter


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        execute_repair(
            repo=Path(args.repo_root).resolve(),
            repair_branch=args.repair_branch,
            message=args.message,
            token_file=args.git_token_file,
            confirm=args.confirm,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


def execute_repair(
    *,
    repo: Path,
    repair_branch: str,
    message: str,
    token_file: str | None = None,
    confirm: bool = False,
) -> RepairState:
    if not confirm:
        raise ValueError("Pass --confirm after reviewing the working-tree changes")
    if not repair_branch.startswith("repair/"):
        raise ValueError("repair_branch must start with 'repair/'")
    register_token_file(token_file)
    credentials = collect_credentials([repo])
    askpass = create_askpass_script()
    try:
        state = execute_git_repair(
            GitRepairAdapter(repo, _git_env(credentials, askpass)),
            repair_branch=repair_branch,
            message=message,
        )
        print(f"Repair complete: {state.repair_branch} → {state.original_branch}")
        return state
    finally:
        askpass.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arch-repair",
        description="Guarded, resumable git repair for a quiesced architecture repository.",
    )
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--repair-branch", default="repair/architecture-repair")
    parser.add_argument("--message", default="fix(model): repair architecture repository")
    parser.add_argument("--git-token-file")
    parser.add_argument("--confirm", action="store_true")
    return parser


def _git_env(credentials: GitCredentials | None, askpass: Path) -> dict[str, str]:
    if credentials is not None:
        return build_git_env(credentials, askpass)
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env
