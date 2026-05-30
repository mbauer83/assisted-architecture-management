"""Idempotent scope-connection creation for diagram types that declare parent→child links."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.application.verification.artifact_verifier import ArtifactVerifier
from src.application.verification.artifact_verifier_registry import ArtifactRegistry


def apply_scope_connections(
    diagram_type: str,
    diagram_entities: dict[str, Any] | None,
    repo_root: Path,
    registry: ArtifactRegistry,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
) -> None:
    """Create scope-derived model connections declared by the diagram type.

    Idempotent: silently skips connections that already exist.
    Only runs when diagram_entities is provided (not None).
    """
    if diagram_entities is None:
        return

    from src.infrastructure.diagram_types import find_diagram_type  # noqa: PLC0415

    dt = find_diagram_type(diagram_type)
    if dt is None:
        return

    pairs = dt.build_scope_connections(diagram_entities)
    if not pairs:
        return

    from src.infrastructure.write.artifact_write.connection import add_connection  # noqa: PLC0415

    for source_id, target_id, conn_type in pairs:
        try:
            add_connection(
                repo_root=repo_root,
                registry=registry,
                verifier=verifier,
                clear_repo_caches=clear_repo_caches,
                source_entity=source_id,
                connection_type=conn_type,
                target_entity=target_id,
                description=None,
                version="0.1.0",
                status="draft",
                last_updated=None,
                dry_run=False,
            )
        except ValueError as exc:
            if "already exists" in str(exc):
                continue
            raise
