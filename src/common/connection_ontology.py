"""
connection_ontology.py — Authoritative ArchiMate relationship rules.

Single source of truth for:
  - Which connection types are symmetric vs directed
  - Which element categories each entity type belongs to
  - Which (source_category, target_category) pairs are valid per connection type
  - Derived queries: permissible targets, permissible connection types, classify

Used by ModelVerifier (rule enforcement), GUI (form generation), and MCP tools.
"""

from __future__ import annotations

from typing import Literal

from src.common.archimate_types import ALL_ENTITY_TYPES, CONNECTION_TYPES_BY_LANGUAGE

# ---------------------------------------------------------------------------
# Element categories (ArchiMate structural classification)
# ---------------------------------------------------------------------------

ElementCategory = Literal[
    "active", "behavioral", "passive",
    "motivation", "strategy", "implementation", "composite",
]

_CATEGORY_MAP: dict[str, ElementCategory] = {}

# Motivation
for _t in ("stakeholder", "driver", "assessment", "goal", "outcome",
           "principle", "requirement", "architecture-constraint",
           "meaning", "value"):
    _CATEGORY_MAP[_t] = "motivation"

# Strategy
for _t in ("capability", "value-stream", "resource", "course-of-action"):
    _CATEGORY_MAP[_t] = "strategy"

# Common behavioral (domain-neutral)
for _t in ("service", "process", "function", "interaction", "event"):
    _CATEGORY_MAP[_t] = "behavioral"
_CATEGORY_MAP["role"] = "active"

# Business
for _t in ("business-actor", "business-interface"):
    _CATEGORY_MAP[_t] = "active"
for _t in ("business-object", "contract"):
    _CATEGORY_MAP[_t] = "passive"
_CATEGORY_MAP["product"] = "composite"

# Application
for _t in ("application-component", "application-interface"):
    _CATEGORY_MAP[_t] = "active"
_CATEGORY_MAP["data-object"] = "passive"

# Technology
for _t in ("technology-node", "device", "system-software", "technology-interface",
           "path", "communication-network"):
    _CATEGORY_MAP[_t] = "active"
_CATEGORY_MAP["artifact"] = "passive"

# Physical
for _t in ("equipment", "facility", "distribution-network"):
    _CATEGORY_MAP[_t] = "active"
_CATEGORY_MAP["material"] = "passive"

# Implementation
for _t in ("work-package", "deliverable", "implementation-event",
           "plateau"):
    _CATEGORY_MAP[_t] = "implementation"


def element_category(artifact_type: str) -> ElementCategory | None:
    return _CATEGORY_MAP.get(artifact_type)


# ---------------------------------------------------------------------------
# Symmetric connections
# ---------------------------------------------------------------------------

SYMMETRIC_CONNECTIONS: frozenset[str] = frozenset({
    "archimate-association",
})

#: ArchiMate connection types used for model-level entity connections.
#: Non-archimate types (ER, sequence, activity, use-case) are diagram-only.
ARCHIMATE_CONNECTION_TYPES: frozenset[str] = CONNECTION_TYPES_BY_LANGUAGE["archimate"]


def is_symmetric(conn_type: str) -> bool:
    return conn_type in SYMMETRIC_CONNECTIONS


# ---------------------------------------------------------------------------
# Relationship validity rules: conn_type → set of (src_cat, tgt_cat)
# ---------------------------------------------------------------------------

# Note: This is too loose. We need more complex rules. See comments on EntityTypeInfo in model_write_catalog.py
# Should use ConnectionTypeInfo (extend if necessary)
# Checking connection permissibility can happen as specified in model_write_catalog.py, but the general ArchiMate NEXT rules encoded here should be encoded in a fixed yaml configuration if possible that is then used in the way specified in model_write_catalog.py

# Actual rules for permitted direct relationships - should probably be yaml-specified in a <PROJECT_ROOT>/config directory or subdirectory thereof
#
# Abbreviations used for connection types:
# - (A)ccess
# - (F)low
# - a(G)gregation
# - ass(I)gnment
# - i(N)fluence
# - ass(O)ciation
# - (R)ealization
# - (S)pecialization
# - (T)riggering
# - ser(V)ing
#
# General:
# - Every element with its own type: G, S
# - Connections of the same type may be connected with AND or OR junctions, whose incoming and outgoing connections must all have the same type
# - Groupings, Locations with any other element, relationship, junction: G
# - Grouping may be the source of any relationship (target must still permit incoming relationship-type)
# - Grouping may be target of any relationship (source must still permit outgoing relationship-type)
# - Groupings may have any relationship to each other
# - Relationships may themselves have an association relationship with any element
# - Every element with any other element: O
# 
# Core Domains:
#
# Common Domain:
# - Active Structure Elements may realize Paths
# - External Active Structure Elements may be assigned to Services
# - Internal Active Structure Elements may be associated with Paths
# - Internal Active Structure Elements may be assigned to Roles
# - Events may trigger or flow to Services
# - Events may access Passive Structure Elements
# - Events may trigger or flow to Internal Behavioral Elements
# - Services may serve Active Structure Elements
# - Services may trigger or flow to Services
# - Services may access Passive Structure Elements
# - Services may serve Internal Behavioral Elements
# - Collaborations may aggregate Internal Active Structure Elements
# - Roles may aggregate External Active Structure Elements (Interfaces)
# - Roles may be assigned to Events
# - Roles may be assigned to Internal Behavioral Elements
# - Internal Behavioral Elements may trigger or flow to Events
# - Internal Behavioral Elements may realize Services
# - Internal Behavioral Elements may access Passive Structure Elements
# - Internal Behavioral Elements may aggregate Internal Behavioral Elements
# - Internal Behavioral Elements may trigger or flow to Internal Behavioral Elements
#
# Motivation Domain:
# - Motivation Elements may influence Motivation Elements
# - Stakeholder may be associated with Meaning
# - Stakeholder may be associated with Value
# - Stakeholder may be associated with Driver
# - Value may be associated with Outcome
# - Driver may be associated with Goal
# - Driver may be associated with Assessment
# - Assessment may be associated with Goal
# - Outcome may realize Goal
# - Principle may realize Outcome
# - Requirement may realize Principle
# - Requirement may realize Outcome
#
# Strategy Domain:
# - Resource may be assigned to Strategy Behavior Element
# - Strategy Behavior Element may trigger, flow to, or serve Strategy Behavior Element
# - Capability may realize Course of Action
# - Value Stream may realize Course of Action
#
# Business Domain:
# - Business Actor may aggregate Business Interface
# - Business Actor may be assigned to Business Object   
#
# Application Domain:
# - Application Component may be assigned to Application Interface
# - Application Component may be assigned to Data Object
#
# Technology Domain:
# - Technology Internal Active Structure Element may aggregate into Technology Interface
# - Node may aggregate into System Software
# - Node may aggregate into Facility
# - Node may aggregate into Device
# - Node may aggregate into Equipment
# - System Software may be assigned to System Software
# - System Software may be associated with Communication Network
# - Device may be assigned to System Software
# - Device may be associated with Communication Network
# - Equipment may aggregate into Device
# - Facility may be assigned to or aggregate into Node
# - Facility may be associated with Distribution Network
# - Facility may be assigned to Business Actor
# - Business Actor may be associated with Distribution Network
#
# Core Domain Relationships:
# - Application Interface may realize Business Interface
# - Data Object may realize Business Object
# - Technology Interface may realize Application Interface
# - Facility may be assigned to Business Actor
# - Artifact may realize Application Component
# - Artifact may realize Data Object
# - Material may realize Business Object
#
# Strategy Domain to Motivation Domain:
# - Capability to Requirement: N, R
# - Course of Action to Outcome, Requirement: N, R
# - Resource to Requirement: N, R
# - Value Stream to Requirement: N, R
#
# Common Domain to Motivation Domain:
# - Collaboration to Requirement: N, R
# - Event to Requirement: N, R
# - Function to Requirement: N, R
# - Grouping to Assessment, Driver, Meaning, Outcome, Principle, Requirement, Stakeholder, Value: G
# - Grouping to Requirement: N, R
# - Location to Assessment, Driver, Meaning, Outcome, Principle, Requirement, Stakeholder, Value: G
# - Location to Requirement: N, R
# - Path to Requirement: N, R
# - Process to Requirement: N, R
# - Role to Requirement: N, R
# - Service to Requirement: N, R
# 
# Common Domain to Strategy Domain:
# - Collaboration to Resource: R
# - Function to Capability, Course of Action, Value Stream: R
# - Grouping to Capability, Course of Action, Resource, Value Stream: G
# - Location to Capability, Course of Action, Resource, Value Stream: G
# - Location to Resource: R
# - Path to Resource: R
# - Process to Capability, Course of Action, Value Stream: R
# 
# Common Domain to Business Domain:
# - Collaboration to Business Actor: G
# - Event to Business Object: A
# - Function to Business Object: A
# - Grouping to Business Actor, Business Interface, Business Object, Product: G
# - Location to Business Actor, Business Interface, Business Object, Product: G
# - Process to Business Object: A
# - Role to Business Interface: G
# - Service to Business Actor, Business Interface: V
# - Service to Business Object: A 
#
# Common Domain to Application Domain:
# - Collaboration to Application Component: G
# - Event to Data Object: A
# - Function to Data Object: A
# - Grouping to Application Component, Application Interface, Data Object: G
# - Location to Application Component, Application Interface, Data Object: G
# - Process to Data Object: A
# - Role to Application Interface: G
# - Service to Application Component, Application Interface: V
# - Service to Data Object: A
#
# Common Domain to Technology Domain:
# - Collaboration to Device, Equipment, Facility, Node, System Software: G
# - Event to Artifact: A
# - Event to Material: A
# - Function to Artifact: A
# - Function to Material: A
# - Grouping to Artifact, Communication Network, Device, Distribution Network, Equipment, Facility, Material, Node, System Software, Technology Interface: G
# - Location to Artifact, Communication Network, Device, Distribution Network, Equipment, Facility, Material, Node, System Software, Technology Interface: G
# - Process to Artifact, Material: A
# - Role to Technology Interface: G
# - Service to Artifact, Material: A
# - Service to Communication Network, Device, Distribution Network, Equipment, Facility, Node, System Software, Technology Interface: V
#
# Common Domain to Implementation & Migration Domain:
# - Event to Deliverable: A
# - Event to Plateau: T
# - Event to Work Package: F, T
# - Grouping to Deliverable, Plateau, Work Package: G
# - Location to Deliverable, Plateau, Work Package: G
#
# Business & Application Domains to Common Domain:
# - Business Actor to Path: R
# - Business Actor to Role: I
# - Business Interface to Path: R
# - Business Interface to Service: I
# - Product to Service: G
# - Application Component to Path: R
# - Application Component to Role: I
# - Application Interface to Path: R
# - Application Interface to Service: I
#
# Business & Application Domains to Motivation Domain:
# - Business Actor to Requirement: N, R
# - Business Interface to Requirement: N, R
# - Business Object to Requirement: N, R
# - Product to Requirement: N, R
# - Application Component to Requirement: N, R
# - Application Interface to Requirement: N, R
# - Data Object to Requirement: N, R
#
# Business & Application Domains to Strategy Domain:
# - Business Actor to Resource: N, R
# - Business Interface to Resource: N, R
# - Business Object to Resource: N, R
# - Product to Resource: N, R
# - Application Component to Resource: N, R
# - Application Interface to Resource: N, R
# - Data Object to Resource: N, R
#
# Business & Application Domains to Technology Domain:
# - Product to Artifact, Material: G
#
# Business & Application Domain to Integration & Migration Domain:
# - Business Object to Deliverable: S
# - Data Object to Deliverable: S
#
# Technology Domain to Common Domain:
# - Communication Network to Path: R
# - Device to Path: R
# - Device to Role: I
# - Distribution Network to Path: R
# - Equipment to Path: R
# - Equipment to Role: I
# - Facility to Path: R
# - Facility to Role: I
# - Node to Path: R
# - Node to Role: I
# - System Software to Path: R
# - System Software to Role: I
# - Technology Interface to Path: R
# - Technology Interface to Role: I
#
# Technology Domain to Motivation Domain:
# - Artifact to Requirement: N, R
# - Communication Network to Requirement: N, R
# - Device to Requirement: N, R
# - Distribution Network to Requirement: N, R
# - Equipment to Requirement: N, R
# - Facility to Requirement: N, R
# - Node to Requirement: N, R
# - System Software to Requirement: N, R
# - Technology Interface to Requirement: N, R
#
# Technology Domain to Strategy Domain:
# - Artifact to Resource: R
# - Communication Network to Resource: R
# - Device to Resource: R
# - Distribution Network to Resource: R
# - Equipment to Resource: R
# - Facility to Resource: R
# - Node to Resource: R
# - System Software to Resource: R
# - Technology Interface to Resource: R
#
# Technology Domain to Business & Application Domains:
# - Artifact to Business Object: S
# - Artifact to Application Component: R
# - Artifact to Data Object: R, S
# - Distribution Network to Business Actor: G
# - Facility to Business Actor: I
# - Material to Business Object: R
# - Material to Business Object, Data Object: S
# - Technology Interface to Application Interface: R
#
# Supporting Domains
#
# Implementation & Migration Domain:
# - Work Package may trigger or flow to Work Package
# - Work Package may access or realize Deliverable
# - Work Package may trigger or flow to Event
# - Deliverable may realize Plateau
# - Plateau may trigger Plateau
# - Plateau may trigger Event
# - Event may trigger or flow to Work Package
# - Event may access Deliverable
# - Event may trigger Plateau
#
# Implementation & Migration Domain to Common Domain:
# - Deliverable to Collaboration, Event, Function, Location, Path, Process, Role, Service: R
# - Plateau to Collaboration, Event, Function, Location, Path, Process, Role, Service: G, R
# - Plateau to Event: T
# - Work Package to Collaboration, Event, Function, Location, Path, Process, Role, Service: R
# - Work Package to Event: F, T
#
# Implementation & Migration Domain to Motivation Domain:
# - Deliverable to Requirement: R
# - Plateau to Goal, Requirement: G
# - Plateau to Requirement: N, R
# - Work Package to Requirement: N, R
#
# Implementation & Migration Domain to Strategy Domain:
# - Deliverable to Capability, Course of Action, Resource, Value Stream: R
# - Plateau to Capability, Course of Action, Resource, Value Stream: G, R
# - Work Package to Capability, Course of Action, Resource, Value Stream: R
#
# Implementation & Migration Domain to Business & Application Domains:
# - Deliverable to Business Actor, Business Interface, Business Object, Product, Application Component, Application Interface, Data Object: R
# - Plateau to Business Actor, Business Interface, Business Object, Product, Application Component, Application Interface, Data Object: G, R
# - Work Package to Business Actor, Business Interface, Business Object, Product, Application Component, Application Interface, Data Object: R
#
# Implementation & Migration Domain to Technology Domain:
# - Deliverable to Artifact, Communication Network, Device, Distribution Network, Equipment, Facility, Material, Node, System Software, Technology Interface: R
# - Plateau to Artifact, Communication Network, Device, Distribution Network, Equipment, Facility, Material, Node, System Software, Technology Interface: G, R
# - Work Package to Artifact, Communication Network, Device, Distribution Network, Equipment, Facility, Material, Node, System Software, Technology Interface: R



_CAT_ALL = ("active", "behavioral", "passive", "motivation",
            "strategy", "implementation", "composite")

RELATIONSHIP_RULES: dict[str, set[tuple[str, str]]] = {
    "archimate-composition": {(s, s) for s in _CAT_ALL},
    "archimate-aggregation": {(s, s) for s in _CAT_ALL},
    "archimate-assignment": {
        ("active", "behavioral"), ("active", "active"),
        ("active", "passive"), ("behavioral", "active"),
    },
    "archimate-realization": {(s, t) for s in _CAT_ALL for t in _CAT_ALL},
    "archimate-serving": {
        ("behavioral", "behavioral"), ("behavioral", "active"),
        ("active", "behavioral"), ("active", "active"),
        ("behavioral", "composite"), ("active", "composite"),
    },
    "archimate-access": {("behavioral", "passive"), ("active", "passive")},
    "archimate-influence": {(s, "motivation") for s in _CAT_ALL},
    "archimate-association": {(s, t) for s in _CAT_ALL for t in _CAT_ALL},
    "archimate-specialization": {(s, s) for s in _CAT_ALL},
    "archimate-flow": {("behavioral", "behavioral")},
    "archimate-triggering": {("behavioral", "behavioral")},
}


def _matches(src_cat: str, tgt_cat: str, valid: set[tuple[str, str]]) -> bool:
    return (src_cat, tgt_cat) in valid


# We need to map permitted relationships within ArchiMate NEXT domains, then between them.
# Common:
# - Every element may have aggregattion and specialization relationships with its own type.
#  


# ---------------------------------------------------------------------------
# Public query API
# ---------------------------------------------------------------------------


def permissible_connection_types(
    source_type: str, target_type: str,
) -> list[str]:
    """Return ArchiMate connection types valid between source and target type."""
    src_cat = element_category(source_type)
    tgt_cat = element_category(target_type)
    if src_cat is None or tgt_cat is None:
        return []
    result: list[str] = []
    for ct, valid_pairs in RELATIONSHIP_RULES.items():
        if _matches(src_cat, tgt_cat, valid_pairs):
            result.append(ct)
        elif is_symmetric(ct) and _matches(tgt_cat, src_cat, valid_pairs):
            result.append(ct)
    if source_type != target_type and "archimate-specialization" in result:
        result.remove("archimate-specialization")
    return sorted(result)


def permissible_target_types(source_type: str) -> dict[str, list[str]]:
    """For a source type, return {conn_type: [valid_target_types]}.

    Only includes ArchiMate connection types with at least one valid target.
    """
    src_cat = element_category(source_type)
    if src_cat is None:
        return {}
    out: dict[str, list[str]] = {}
    for ct, valid_pairs in RELATIONSHIP_RULES.items():
        valid_tgt_cats = {pair[1] for pair in valid_pairs if pair[0] == src_cat}
        if is_symmetric(ct):
            valid_tgt_cats |= {pair[0] for pair in valid_pairs if pair[1] == src_cat}
        targets = [
            etype for etype in sorted(ALL_ENTITY_TYPES)
            if element_category(etype) in valid_tgt_cats
            and not (ct == "archimate-specialization" and etype != source_type)
        ]
        if targets:
            out[ct] = targets
    return out


def classify_connections(
    source_type: str,
) -> dict[str, dict[str, list[str]]]:
    """Classify permissible connections into outgoing/incoming/symmetric.

    Returns ``{"outgoing": {tgt_type: [conn_types]}, "incoming": ...,
    "symmetric": ...}``.  Only ArchiMate connection types are included.
    """
    src_cat = element_category(source_type)
    if src_cat is None:
        return {"outgoing": {}, "incoming": {}, "symmetric": {}}

    outgoing: dict[str, list[str]] = {}
    incoming: dict[str, list[str]] = {}
    symmetric: dict[str, list[str]] = {}

    for ct, valid_pairs in RELATIONSHIP_RULES.items():
        sym = is_symmetric(ct)
        for etype in sorted(ALL_ENTITY_TYPES):
            ecat = element_category(etype)
            if ecat is None:
                continue
            if ct == "archimate-specialization" and etype != source_type:
                continue
            if sym:
                if _matches(src_cat, ecat, valid_pairs) or _matches(ecat, src_cat, valid_pairs):
                    symmetric.setdefault(etype, []).append(ct)
            else:
                if _matches(src_cat, ecat, valid_pairs):
                    outgoing.setdefault(etype, []).append(ct)
                if _matches(ecat, src_cat, valid_pairs):
                    incoming.setdefault(etype, []).append(ct)

    return {"outgoing": outgoing, "incoming": incoming, "symmetric": symmetric}
