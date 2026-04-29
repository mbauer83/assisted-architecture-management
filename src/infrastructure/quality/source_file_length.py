"""Source-file length policy checks for non-test Python code.

Ruff does not provide a native max-file-length rule. This module implements the
project's local policy so it can be enforced in tests and CI without expanding
the linter stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SOURCE_FILE_SOFT_LIMIT = 250
SOURCE_FILE_HARD_LIMIT = 350
SOURCE_FILE_BASELINE_LIMITS: dict[str, int] = {
    "gen_id.py": 0,
    "src/application/verification/artifact_verifier.py": 787,
    "src/application/verification/artifact_verifier_rules.py": 473,
    "src/infrastructure/rendering/diagram_builder.py": 391,
    "src/application/verification/artifact_verifier_incremental.py": 351,
    "src/infrastructure/artifact_index/_sqlite_store.py": 378,
    "src/infrastructure/artifact_index/service.py": 475,
    "src/infrastructure/backend/arch_backend.py": 384,
    "src/infrastructure/mcp/artifact_mcp/query_scaffold_tools.py": 375,
    "src/infrastructure/write/artifact_write/admin_ops.py": 463,
}


@dataclass(frozen=True)
class SourceLengthViolation:
    path: str
    counted_lines: int
    limit: int
    reason: str


def iter_policy_source_files(repo_root: Path) -> list[Path]:
    paths = sorted((repo_root / "src").rglob("*.py"))
    gen_id = repo_root / "gen_id.py"
    if gen_id.exists():
        paths.append(gen_id)
    return paths


def counted_source_lines(path: Path) -> int:
    return sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def find_source_length_violations(repo_root: Path) -> list[SourceLengthViolation]:
    violations: list[SourceLengthViolation] = []
    for path in iter_policy_source_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        counted = counted_source_lines(path)
        if counted <= SOURCE_FILE_HARD_LIMIT:
            continue

        baseline = SOURCE_FILE_BASELINE_LIMITS.get(rel)
        if baseline is None:
            violations.append(
                SourceLengthViolation(
                    path=rel,
                    counted_lines=counted,
                    limit=SOURCE_FILE_HARD_LIMIT,
                    reason="new file exceeds hard limit",
                )
            )
            continue

        if counted > baseline:
            violations.append(
                SourceLengthViolation(
                    path=rel,
                    counted_lines=counted,
                    limit=baseline,
                    reason="existing oversized file grew beyond recorded baseline",
                )
            )
    return violations
