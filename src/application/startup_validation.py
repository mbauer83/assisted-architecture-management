"""Startup validation: registry internal consistency and repo/registry compatibility.

Two independent checks:

- ``validate_registry_consistency`` — pure in-memory check that every type referenced
  in permitted_relationships is actually declared in the same module.  Fast, no I/O,
  runs inside ``build_module_registry`` so broken YAML is caught at startup.

- ``validate_repo_compatibility`` — scans indexed repo content and compares types found
  against the module registry.  Any type present in the repo but absent from the registry
  is reported as an error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.artifact_repository import ArtifactRepository
    from src.domain.module_registry import ModuleRegistry


# ── Registry consistency ──────────────────────────────────────────────────────


class RegistryConsistencyError(Exception):
    """Raised when a module's permitted_relationships reference undeclared types."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("\n".join(errors))


def validate_registry_consistency(registry: "ModuleRegistry") -> None:
    """Raise RegistryConsistencyError if any module has internal type drift.

    Checks for each registered ontology and diagram type that every entity type
    and connection type referenced in permitted_relationships is actually declared
    in that module's own types (or, for diagram types, in effective_entity/connection_types).
    """
    errors = _collect_consistency_errors(registry)
    if errors:
        raise RegistryConsistencyError(errors)


def _collect_consistency_errors(registry: "ModuleRegistry") -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()

    def _add(msg: str) -> None:
        if msg not in seen:
            seen.add(msg)
            errors.append(msg)

    # Ontology modules: every entity type and connection type referenced in
    # permitted_relationships must be declared in that same module.
    for om_name, om in registry.all_ontologies().items():
        known_entity = set(om.entity_types.keys())
        known_conn = set(om.connection_types.keys())
        for src, targets in om.permitted_relationships.by_source().items():
            if src not in known_entity:
                _add(f"Ontology {om_name!r}: permitted_relationships source {str(src)!r} is not a declared entity type")
            for tgt, conn in targets:
                if tgt not in known_entity:
                    _add(f"Ontology {om_name!r}: permitted_relationships target {str(tgt)!r}"
                         " is not a declared entity type")
                if conn not in known_conn:
                    _add(f"Ontology {om_name!r}: permitted_relationships connection {str(conn)!r}"
                         " is not a declared connection type")

    # Diagram types: entity types in own_permitted_relationships must be either a
    # diagram_only_type or a model entity type declared in a registered ontology.
    # The latter covers cross-references such as activity swimlane-maps-to rules that
    # point at ArchiMate entity types.  Diagram types backed entirely by an external
    # ontology (no diagram_only_types) are skipped.  Connection type vocabulary lives
    # inside the internal DiagramOntology and is not re-checked here.
    # NOTE: effective_entity_types() is intentionally avoided; for model-backed diagram
    # types (e.g. C4) it calls get_module_registry(), which would recurse during build.
    all_ontology_entity_names = frozenset(str(k) for k in registry.all_entity_types().keys())
    for dt_name, dt in registry.all_diagram_types().items():
        diagram_entity_names = frozenset(oe.entity_type for oe in dt.ui_config.diagram_only_types)
        if not diagram_entity_names:
            continue
        all_valid = diagram_entity_names | all_ontology_entity_names
        for src, targets in dt.own_permitted_relationships.by_source().items():
            if str(src) not in all_valid:
                _add(f"Diagram type {dt_name!r}: permitted_relationships source {str(src)!r}"
                     " is not a known entity type")
            for tgt, conn in targets:
                if str(tgt) not in all_valid:
                    _add(f"Diagram type {dt_name!r}: permitted_relationships target {str(tgt)!r}"
                         " is not a known entity type")

    return errors


# ── Repo compatibility ────────────────────────────────────────────────────────


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
    known_entity_types = set(registry.all_entity_types().keys()) | set(registry.all_diagram_entity_types())
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
