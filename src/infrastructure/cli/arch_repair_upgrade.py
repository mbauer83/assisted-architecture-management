"""`arch-repair upgrade` subcommand: version-aware repo upgrade.

Dry-run/report is always allowed (backend running or not) and never mutates. `--commit`, in
order:
  1. refuses when a backend serves the target repo — the **only** hard, non-overridable
     gate. This is the actual consistency invariant: two writers touching the same files.
     Runs before anything else touches disk.
  2. sweeps orphaned atomic-write temp files a previous, killed run may have left behind;
  3. recovers any transaction left mid-flight by a crashed backend (the same idempotent
     `recover_transactions` the backend itself runs at startup), so upgrade steps always see a
     consistent repo regardless of git-sync/promotion history;
  4. applies. Git status is deliberately **not** a gate. An out-of-date-and-actively-used
     repo — the exact situation this command exists for — routinely has uncommitted edits to
     the very files that need migrating (entity frontmatter, profiles, connection
     declarations); requiring a clean tree first would make `--commit` fail on the common
     case, not the rare one. It's also not a safety property: every step does
     read-current-content → transform → write-back against whatever is on disk *right now*,
     committed or not, so an uncommitted edit is carried forward into the rewrite, never
     clobbered or lost — git cleanliness has no bearing on correctness here, only on how easy
     the resulting diff is to read. So a touched-file/dirty-file overlap is reported as an
     informational note (which files, so the operator knows to review the combined diff
     before committing) and nothing more.

Resumability: every step's `detect()` re-derives its finding from actual repo content, never
from the `.arch-repo/config.yaml` applied-steps stamp — the stamp is metadata for reporting
only. Combined with atomic (temp+rename) writes and per-step/per-repo failure isolation (see
`apply.py`/`workspace.py`), this means `--commit` may be interrupted at any point (killed
process, crash, power loss) and safely re-run from scratch: partially-applied repos, stale
stamps, and stray temp files are all self-healing on the next invocation.
See `src.infrastructure.repository_upgrade.guard`.
"""

from __future__ import annotations

import argparse
import json
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

from src.application.repository_upgrade.registry import DEFAULT_REGISTRY, StepRegistry
from src.application.repository_upgrade.workspace import (
    RepoUpgradeTarget,
    apply_workspace,
    evaluate_workspace,
)
from src.domain.repository_upgrade import COVERAGE_NOTE, RepoUpgradeReport, WorkspaceUpgradeReport
from src.infrastructure.backend.backend_probe import (
    backend_url,
    configured_backend_url,
    probe_backend_url,
    resolve_backend_port,
)
from src.infrastructure.repository_upgrade.atomic_write import sweep_stale_tmp_files
from src.infrastructure.repository_upgrade.fs_adapter import (
    FilesystemRepoUpgradeView,
    FilesystemRepoUpgradeWriter,
)
from src.infrastructure.repository_upgrade.guard import (
    check_backend_not_serving,
    conflicting_dirty_files,
    probe_backend_identity,
)
from src.infrastructure.workspace.workspace_init import load_init_state
from src.infrastructure.write.artifact_write.m4_transaction import (
    TransactionRecoveryError,
    recover_transactions,
)


def software_version() -> str:
    try:
        return _pkg_version("architectonic")
    except PackageNotFoundError:
        return "unknown"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="arch-repair upgrade",
        description="Detect and (with --commit) apply persisted-format upgrades for one or more repo roots.",
    )
    p.add_argument("--repo-root", action="append", default=[], metavar="PATH")
    p.add_argument("--workspace", metavar="PATH", help="Resolve engagement + enterprise roots from arch-init state")
    p.add_argument("--commit", action="store_true", default=False)
    p.add_argument("--json", action="store_true", default=False, dest="json_output")
    return p


def resolve_repo_roots(*, repo_root: list[str], workspace: str | None) -> list[Path]:
    roots = [Path(p).resolve() for p in repo_root]
    if workspace is not None:
        state = load_init_state(Path(workspace).resolve())
        if state is None:
            raise SystemExit(f"ERROR: no arch-init state found under {workspace}")
        roots.append(Path(state["engagement_root"]).resolve())
        roots.append(Path(state["enterprise_root"]).resolve())
    if not roots:
        raise SystemExit("ERROR: specify --repo-root (repeatable) and/or --workspace")
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return unique


def main_upgrade(argv: list[str], *, registry: StepRegistry = DEFAULT_REGISTRY) -> int:
    args = parser().parse_args(argv)
    roots = resolve_repo_roots(repo_root=args.repo_root, workspace=args.workspace)
    version = software_version()
    targets = [RepoUpgradeTarget(FilesystemRepoUpgradeView(r), FilesystemRepoUpgradeWriter(r)) for r in roots]

    if not args.commit:
        report = evaluate_workspace(targets, registry=registry, software_version=version)
        _emit(report, args.json_output)
        return 0

    # 1–3: hard backend guard, then sweep + recovery — must all land before we look at git
    # status at all, since recovery can itself materialize real (legitimate) file changes.
    for root in roots:
        _guard_backend_not_serving(root)
    for root in roots:
        _sweep_and_recover(root)

    # 4: evaluate against the now-consistent repo purely to report which touched files (if
    # any) already have uncommitted local edits — informational only, never blocking; see the
    # module docstring for why git status is not a safety gate here.
    preflight = evaluate_workspace(targets, registry=registry, software_version=version)
    for root, repo_report in zip(roots, preflight.per_repo, strict=True):
        _note_dirty_overlap(root, repo_report.touched_locations)
        print(f"Backup/branch recommendation: commit or branch {root} before proceeding.")

    report = apply_workspace(targets, registry=registry, software_version=version)
    _emit(report, args.json_output)
    return 1 if report.has_errors else 0


def _guard_backend_not_serving(repo_root: Path) -> None:
    base_url = configured_backend_url() or backend_url(resolve_backend_port())
    responding = probe_backend_url(base_url)
    identity = probe_backend_identity(base_url) if responding else None
    guard = check_backend_not_serving(repo_root, backend_responding=responding, identity=identity)
    if guard.blocked:
        raise SystemExit(f"ERROR: {guard.reason}")


def _sweep_and_recover(repo_root: Path) -> None:
    # Sweep orphaned atomic-write temp files a previous, killed `upgrade --commit` may have
    # left behind — harmless litter, never a source of truth, safe to remove now that no
    # concurrent writer can be holding one open.
    swept = sweep_stale_tmp_files(repo_root)
    if swept:
        print(f"Removed {len(swept)} stale temp file(s) from a previous interrupted run in {repo_root}.")

    # Idempotent recovery of any transaction a crashed backend left mid-flight, so steps
    # always see a consistent repo regardless of git-sync/promotion history.
    try:
        recovered = recover_transactions(
            repo_root, rebuild_index=FilesystemRepoUpgradeWriter(repo_root).rebuild_index
        )
    except TransactionRecoveryError as exc:
        raise SystemExit(
            f"ERROR: {repo_root} has an unrecoverable pending transaction — resolve manually "
            f"before upgrading: {exc}"
        ) from exc
    if recovered:
        print(f"Recovered {recovered} pending transaction(s) in {repo_root} before upgrading.")


def _note_dirty_overlap(repo_root: Path, touched_locations: frozenset[str]) -> None:
    overlap = conflicting_dirty_files(repo_root, touched_locations)
    if overlap:
        files = "\n".join(f"  {f}" for f in overlap)
        print(
            f"Note: {repo_root} has uncommitted local edits to {len(overlap)} file(s) this "
            f"run will also rewrite — your edits are carried forward, not lost, but review "
            f"the combined diff before committing:\n{files}"
        )


def _emit(report: WorkspaceUpgradeReport | RepoUpgradeReport, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return
    print(f"Note: {COVERAGE_NOTE}")
    repos = report.per_repo if isinstance(report, WorkspaceUpgradeReport) else [report]
    for repo_report in repos:
        print(f"\n{repo_report.repo_root}")
        print(f"  format_contract_version: {repo_report.format_contract_version}")
        print(f"  applied_steps: {', '.join(repo_report.applied_steps_after) or '(none)'}")
        if not repo_report.results:
            print("  no findings")
            continue
        for result in repo_report.results:
            f = result.finding
            print(f"  [{result.outcome}] {f.step_id}/{f.finding_id} ({f.severity}) — {f.location}: {f.description}")
