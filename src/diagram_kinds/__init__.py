"""Default diagram-kind registrations."""

from __future__ import annotations

from src.diagram_kinds.archimate_application import module as archimate_application
from src.diagram_kinds.archimate_business import module as archimate_business
from src.diagram_kinds.archimate_implementation import module as archimate_implementation
from src.diagram_kinds.archimate_layered import module as archimate_layered
from src.diagram_kinds.archimate_motivation import module as archimate_motivation
from src.diagram_kinds.archimate_strategy import module as archimate_strategy
from src.diagram_kinds.archimate_technology import module as archimate_technology
from src.domain.module_registry import ModuleRegistry
from src.domain.ontology_protocol import DiagramKindModule

DEFAULT_DIAGRAM_KINDS: tuple[DiagramKindModule, ...] = (
    archimate_motivation,
    archimate_strategy,
    archimate_business,
    archimate_application,
    archimate_technology,
    archimate_implementation,
    archimate_layered,
)


def register_default_diagram_kinds(registry: ModuleRegistry) -> None:
    """Register the built-in diagram kinds on *registry*."""
    for module in DEFAULT_DIAGRAM_KINDS:
        registry.register_diagram_kind(module)
