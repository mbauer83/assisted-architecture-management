"""Default diagram-type registrations."""

from __future__ import annotations

from src.diagram_types.activity import module as activity
from src.diagram_types.sequence import module as sequence
from src.diagram_types.archimate.application import module as archimate_application
from src.diagram_types.archimate.business import module as archimate_business
from src.diagram_types.archimate.implementation import module as archimate_implementation
from src.diagram_types.archimate.layered import module as archimate_layered
from src.diagram_types.archimate.motivation import module as archimate_motivation
from src.diagram_types.archimate.strategy import module as archimate_strategy
from src.diagram_types.archimate.technology import module as archimate_technology
from src.diagram_types.c4.component import module as c4_component
from src.diagram_types.c4.container import module as c4_container
from src.diagram_types.c4.system_context import module as c4_system_context
from src.diagram_types.matrix import module as matrix
from src.domain.module_registry import ModuleRegistry
from src.domain.ontology_protocol import DiagramTypeModule

DEFAULT_DIAGRAM_KINDS: tuple[DiagramTypeModule, ...] = (
    activity,
    sequence,
    archimate_motivation,
    archimate_strategy,
    archimate_business,
    archimate_application,
    archimate_technology,
    archimate_implementation,
    archimate_layered,
    c4_system_context,
    c4_container,
    c4_component,
    matrix,
)


def register_default_diagram_types(registry: ModuleRegistry) -> None:
    """Register the built-in diagram types on *registry*."""
    for module in DEFAULT_DIAGRAM_KINDS:
        registry.register_diagram_type(module)
