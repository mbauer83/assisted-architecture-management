"""Infrastructure adapters implementing the application-owned verifier ports.

These adapters wrap the concrete I/O implementations (subprocess, ThreadPool,
filesystem) and expose them through the Protocol contracts defined in
src/application/verification/verifier_ports.py.

ThreadPoolVerifierScheduler, FilesystemInventoryAdapter, and
DefaultIncrementalStateAdapter have been moved to the application layer
(src/application/verification/_verifier_stdlib_adapters.py) as they only
depend on stdlib + application code. They are re-exported here for any
infrastructure code that still imports from this module.
"""

from __future__ import annotations

from pathlib import Path

from src.application.verification._verifier_stdlib_adapters import (
    DefaultIncrementalStateAdapter,
    FilesystemInventoryAdapter,
    ThreadPoolVerifierScheduler,
)
from src.application.verification.artifact_verifier_syntax import (
    check_puml_syntax,
    check_puml_syntax_batch,
)
from src.application.verification.artifact_verifier_types import Issue

__all__ = [
    "DefaultIncrementalStateAdapter",
    "DefaultPumlSyntaxAdapter",
    "FilesystemInventoryAdapter",
    "ThreadPoolVerifierScheduler",
]


class DefaultPumlSyntaxAdapter:
    """Delegates to the subprocess-based PlantUML runner."""

    def check_one(self, path: Path, loc: str) -> list[Issue]:
        return check_puml_syntax(path, loc)

    def check_batch(self, paths: list[Path]) -> dict[Path, list[Issue]]:
        return check_puml_syntax_batch(paths)
