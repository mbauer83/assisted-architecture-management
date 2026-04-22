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
]


if __name__ == "__main__":
    import sys

    sys.exit(main())
