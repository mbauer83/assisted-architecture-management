"""ERP v2.0 Model Query public API facade."""

from src.common.artifact_repository import ArtifactRepository
from src.common.artifact_types import (
    ArtifactSummary,
    ConnectionRecord,
    DiagramRecord,
    DuplicateArtifactIdError,
    EntityRecord,
    RepoMount,
    SearchHit,
    SearchResult,
    SemanticSearchProvider,
)
from src.infrastructure.artifact_index import shared_artifact_index


def main(argv: list[str] | None = None) -> int:
    from src.common.artifact_query_cli import main as cli_main

    return cli_main(argv)


__all__ = [
    "ArtifactSummary",
    "ConnectionRecord",
    "DiagramRecord",
    "DuplicateArtifactIdError",
    "EntityRecord",
    "ArtifactRepository",
    "RepoMount",
    "SearchHit",
    "SearchResult",
    "SemanticSearchProvider",
    "main",
    "shared_artifact_index",
]


if __name__ == "__main__":
    import sys

    sys.exit(main())
