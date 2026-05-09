"""Startup compatibility validation: repo content vs. registered ontology/diagram modules.

Scans indexed entities, connections, diagrams, and per-type schema files in each
repo root and compares the types found against the module registry.  Any type
present in the repo but absent from the registry is reported as an error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.artifact_repository import ArtifactRepository
    from src.domain.module_registry import ModuleRegistry


class RepoCompatibilityError(Exception):
    """Raised when indexed repo content references types unknown to the registry."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("\n".join(errors))


def validate_repo_compatibility(
    repo: "ArtifactRepository",
    registry: "ModuleRegistry",
) -> None:
    """Raise RepoCompatibilityError if the indexed repo uses types not in the registry.

    Checks:
    - Entity artifact_type values
    - Connection conn_type values
    - Diagram diagram_type values (diagram types)
    - Attribute schema filenames for entity types
    - Connection-metadata schema filenames for connection types
    """
    errors = _collect_errors(repo, registry)
    if errors:
        raise RepoCompatibilityError(errors)


def _collect_errors(
    repo: "ArtifactRepository",
    registry: "ModuleRegistry",
) -> list[str]:
    errors: list[str] = []
    known_entity_types = set(registry.all_entity_types().keys())
    known_connection_types = set(registry.all_connection_types().keys())
    known_diagram_types = set(registry.all_diagram_types().keys())

    unknown_entities: dict[str, str] = {}
    for entity in repo.list_entities():
        t = entity.artifact_type
        if t and t not in known_entity_types and t not in unknown_entities:
            unknown_entities[t] = entity.artifact_id
    for t, example in sorted(unknown_entities.items()):
        errors.append(f"Unknown entity type {t!r} (example artifact: {example})")

    unknown_conns: dict[str, str] = {}
    for conn in repo.list_connections():
        t = conn.conn_type
        if t and t not in known_connection_types and t not in unknown_conns:
            unknown_conns[t] = conn.artifact_id
    for t, example in sorted(unknown_conns.items()):
        errors.append(f"Unknown connection type {t!r} (example artifact: {example})")

    unknown_diagrams: dict[str, str] = {}
    for diagram in repo.list_diagrams():
        t = diagram.diagram_type
        if t and t not in known_diagram_types and t not in unknown_diagrams:
            unknown_diagrams[t] = diagram.artifact_id
    for t, example in sorted(unknown_diagrams.items()):
        errors.append(f"Unknown diagram type {t!r} (example artifact: {example})")

    for repo_root in repo.repo_roots:
        schemata_dir = repo_root / ".arch-repo" / "schemata"
        if not schemata_dir.is_dir():
            continue
        prefix, suffix = "attributes.", ".schema.json"
        for f in sorted(schemata_dir.glob(f"{prefix}*{suffix}")):
            stem = f.name[len(prefix) : -len(suffix)]
            if stem and stem not in known_entity_types:
                errors.append(f"Attribute schema for unknown entity type {stem!r} (file: {f.relative_to(repo_root)})")
        prefix, suffix = "connection-metadata.", ".schema.json"
        for f in sorted(schemata_dir.glob(f"{prefix}*{suffix}")):
            stem = f.name[len(prefix) : -len(suffix)]
            if stem and stem not in known_connection_types:
                errors.append(
                    f"Connection metadata schema for unknown connection type {stem!r}"
                    f" (file: {f.relative_to(repo_root)})"
                )

    try:
        known_element_classes = set(registry.all_element_classes().keys())
    except ValueError as exc:
        errors.append(f"Element class declaration conflict: {exc}")
        return errors

    for om in registry.all_ontologies().values():
        for etype, einfo in om.entity_types.items():
            for cls in einfo.element_classes:
                if cls not in known_element_classes:
                    errors.append(f"Entity type {etype!r} references undeclared element class {cls!r}")

    for dk in registry.all_diagram_types().values():
        for oe in dk.ui_config.diagram_only_types:
            for cls in oe.element_classes:
                if cls not in known_element_classes:
                    errors.append(
                        f"Diagram type {dk.name!r} entity type {oe.entity_type!r} "
                        f"references undeclared element class {cls!r}"
                    )

    return errors
