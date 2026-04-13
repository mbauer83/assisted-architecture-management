"""
archimate_types.py — Canonical type registries for architecture models.

This module is the **single source of truth** for:
  - Valid ``artifact-type`` values in entity and connection frontmatter
  - Valid ``artifact-type`` values for connection types (per diagram language)
  - Valid ``element-type`` values in §display ###archimate blocks
  - Valid ``relationship-type`` values in §display ###archimate blocks

Usage
-----
- ``ModelVerifier`` imports from this module for all type validation.
- When a new ArchiMate element type or connection type is added to the model,
  update this file **first**, then update documentation to match.

Design notes
------------
- **Entity types follow the ArchiMate NEXT ontology.** Six domains:
  motivation, strategy, common (domain-neutral behavioral), business,
  application, technology.  The "common" domain hosts behavioral elements
  (services, processes, functions, events, roles, interactions) that are
  domain-neutral — they are not prefixed with a layer name.
- **Connection types are organised per diagram language.** ArchiMate structural
  relationships form the primary set; ER, sequence, activity, and use-case
  languages each have their own relationship vocabulary.
- Each registry is provided in two forms:
  1. An organised ``dict[str, frozenset[str]]`` grouped by domain/language.
  2. A flat ``frozenset[str]`` (``ALL_*``) for O(1) membership tests.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Entity artifact-type values
# (the ``artifact-type:`` field in entity frontmatter)
# ---------------------------------------------------------------------------

ENTITY_TYPES_BY_DOMAIN: dict[str, frozenset[str]] = {
    "motivation": frozenset(
        {
            "stakeholder",
            "driver",
            "assessment",
            "goal",
            "outcome",
            "principle",
            "requirement",
            "architecture-constraint",
            "meaning",
            "value",
        }
    ),
    "strategy": frozenset(
        {
            "capability",
            "value-stream",
            "resource",
            "course-of-action",
        }
    ),
    "common": frozenset(
        {
            "service",
            "process",
            "function",
            "interaction",
            "event",
            "role",
        }
    ),
    "business": frozenset(
        {
            "business-actor",
            "business-role",
            "business-collaboration",
            "business-interface",
            "business-process",
            "business-function",
            "business-interaction",
            "business-event",
            "business-service",
            "business-object",
            "contract",
            "representation",
            "product",
        }
    ),
    "application": frozenset(
        {
            "application-component",
            "application-collaboration",
            "application-interface",
            "application-function",
            "application-interaction",
            "application-process",
            "application-event",
            "application-service",
            "data-object",
        }
    ),
    "technology": frozenset(
        {
            "technology-node",
            "device",
            "system-software",
            "technology-collaboration",
            "technology-interface",
            "path",
            "communication-network",
            "technology-function",
            "technology-process",
            "technology-interaction",
            "technology-event",
            "technology-service",
            "artifact",
        }
    ),
    "physical": frozenset(
        {
            "equipment",
            "facility",
            "distribution-network",
            "material",
        }
    ),
    "implementation": frozenset(
        {
            "work-package",
            "deliverable",
            "implementation-event",
            "plateau",
            "gap",
        }
    ),
}

#: Flat union of all valid entity ``artifact-type`` values.
ALL_ENTITY_TYPES: frozenset[str] = frozenset().union(*ENTITY_TYPES_BY_DOMAIN.values())


# ---------------------------------------------------------------------------
# Connection artifact-type values
# (the ``artifact-type:`` field in connection frontmatter, prefixed by language)
# ---------------------------------------------------------------------------

CONNECTION_TYPES_BY_LANGUAGE: dict[str, frozenset[str]] = {
    "archimate": frozenset(
        {
            "archimate-composition",
            "archimate-aggregation",
            "archimate-assignment",
            "archimate-realization",
            "archimate-serving",
            "archimate-access",
            "archimate-influence",
            "archimate-association",
            "archimate-specialization",
            "archimate-flow",
            "archimate-triggering",
        }
    ),
    "er": frozenset(
        {
            "er-one-to-many",
            "er-many-to-many",
            "er-one-to-one",
        }
    ),
    "sequence": frozenset(
        {
            "sequence-synchronous",
            "sequence-asynchronous",
            "sequence-return",
            "sequence-create",
            "sequence-destroy",
        }
    ),
    "activity": frozenset(
        {
            "activity-sequence-flow",
            "activity-decision",
            "activity-message-flow",
            "activity-data-association",
        }
    ),
    "usecase": frozenset(
        {
            "usecase-include",
            "usecase-extend",
            "usecase-association",
            "usecase-generalization",
        }
    ),
}

#: Flat union of all valid connection ``artifact-type`` values.
ALL_CONNECTION_TYPES: frozenset[str] = frozenset().union(
    *CONNECTION_TYPES_BY_LANGUAGE.values()
)


# ---------------------------------------------------------------------------
# ArchiMate element-type values
# (the ``element-type:`` field in §display ###archimate blocks)
# Follows ArchiMate 3 UpperCamelCase naming convention.
# ---------------------------------------------------------------------------

ARCHIMATE_ELEMENT_TYPES_BY_DOMAIN: dict[str, frozenset[str]] = {
    "motivation": frozenset(
        {
            "Stakeholder",
            "Driver",
            "Assessment",
            "Goal",
            "Outcome",
            "Principle",
            "Requirement",
            "Constraint",
            "Meaning",
            "Value",
        }
    ),
    "strategy": frozenset(
        {
            "Capability",
            "ValueStream",
            "Resource",
            "CourseOfAction",
        }
    ),
    "common": frozenset(
        {
            "Service",
            "Process",
            "Function",
            "Interaction",
            "Event",
            "Role",
        }
    ),
    "business": frozenset(
        {
            "BusinessActor",
            "BusinessRole",
            "BusinessCollaboration",
            "BusinessInterface",
            "BusinessProcess",
            "BusinessFunction",
            "BusinessInteraction",
            "BusinessEvent",
            "BusinessService",
            "BusinessObject",
            "Contract",
            "Representation",
            "Product",
        }
    ),
    "application": frozenset(
        {
            "ApplicationComponent",
            "ApplicationCollaboration",
            "ApplicationInterface",
            "ApplicationFunction",
            "ApplicationInteraction",
            "ApplicationProcess",
            "ApplicationEvent",
            "ApplicationService",
            "DataObject",
        }
    ),
    "technology": frozenset(
        {
            "Node",
            "Device",
            "SystemSoftware",
            "TechnologyCollaboration",
            "TechnologyInterface",
            "Path",
            "CommunicationNetwork",
            "TechnologyFunction",
            "TechnologyProcess",
            "TechnologyInteraction",
            "TechnologyEvent",
            "TechnologyService",
            "Artifact",
        }
    ),
    "physical": frozenset(
        {
            "Equipment",
            "Facility",
            "DistributionNetwork",
            "Material",
        }
    ),
    "implementation": frozenset(
        {
            "WorkPackage",
            "Deliverable",
            "ImplementationEvent",
            "Plateau",
            "Gap",
        }
    ),
}

#: Flat union of all valid ArchiMate ``element-type`` values.
ALL_ARCHIMATE_ELEMENT_TYPES: frozenset[str] = frozenset().union(
    *ARCHIMATE_ELEMENT_TYPES_BY_DOMAIN.values()
)


# ---------------------------------------------------------------------------
# ArchiMate relationship-type values
# (the ``relationship-type:`` field in §display ###archimate connection blocks)
# Follows ArchiMate 3 UpperCamelCase naming convention.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ArchiMate grouping stereotype names
# (the ``<<Stereotype>>`` applied to grouping rectangle containers)
# One stereotype per ArchiMate layer; no generic <<Grouping>> permitted in diagrams.
# Grouping containers must not have inline color overrides — the stereotype
# provides the only permissible background.
# ---------------------------------------------------------------------------

ARCHIMATE_GROUPING_STEREOTYPES: frozenset[str] = frozenset(
    {
        # Layer-specific (use when all contained elements belong to one layer)
        "MotivationGrouping",
        "StrategyGrouping",
        "BusinessGrouping",
        "ApplicationGrouping",
        "TechnologyGrouping",
        "PhysicalGrouping",
        "ImplementationGrouping",
        # Neutral (use for heterogeneous or purely organisational groupings)
        "Grouping",
    }
)

# ---------------------------------------------------------------------------
# ArchiMate relationship-type values
# (the ``relationship-type:`` field in §display ###archimate connection blocks)
# Follows ArchiMate 3 UpperCamelCase naming convention.
# ---------------------------------------------------------------------------

ARCHIMATE_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {
        "Composition",
        "Aggregation",
        "Assignment",
        "Realization",
        "Serving",
        "Access",
        "Influence",
        "Association",
        "Specialization",
        "Flow",
        "Triggering",
    }
)
