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
# Grandfathered files still above the 350-line hard limit. Each entry is a ratchet: the
# recorded number is the current counted length, and the policy test fails if the file grows
# past it — so these only ever shrink. Files driven back under 350 are removed entirely.
SOURCE_FILE_BASELINE_LIMITS: dict[str, int] = {
    "src/application/verification/artifact_verifier.py": 388,
    "src/infrastructure/artifact_index/_sqlite_store.py": 387,
    "src/infrastructure/artifact_index/service.py": 484,
    "src/infrastructure/gui/routers/_diagram_write.py": 353,
}


@dataclass(frozen=True)
class SourceLengthViolation:
    path: str
    counted_lines: int
    limit: int
    reason: str


def iter_policy_source_files(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "src").rglob("*.py"))


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
