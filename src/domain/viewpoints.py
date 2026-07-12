"""Domain model for viewpoints: definitions, applications, and the concept-level catalog
they live in.

A ``ViewpointDefinition`` narrows a diagram type's ``ConceptScope`` and, independently, may
carry an ``ExecutableViewpointQuery`` (on-demand selection, criteria trees from
``viewpoint_criteria.py``) and a ``PresentationSpec`` (how a result is displayed) — a
definition with a query is directly executable against the live model, producing an
ephemeral result with no diagram or matrix artifact involved. ``ViewpointApplication`` is a
separate, optional concept: it records one *persisted* diagram's or matrix's use of a
definition to narrow its authoring scope, pinned to a specific version so drift is explicit
rather than silent. Parsing lives in ``viewpoint_parsing.py``; registry-aware correctness in
``viewpoint_validation.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from src.domain.concept_scope import ConceptScope
from src.domain.viewpoint_criteria import (
    ConnectionCriteriaGroup,
    ConnectionSelection,
    EntityCriteriaGroup,
    NeighborInclusion,
)

Purpose = Literal["designing", "deciding", "informing"]
Content = Literal["details", "coherence", "overview"]
RepoScope = Literal["enterprise", "engagement", "both"]
Representation = Literal["exploration", "table", "matrix", "diagram"]
StyleConditionMode = Literal["match", "range"]
TargetKind = Literal["diagram", "matrix"]
EnforcementSetting = Literal["off", "warn", "ghost"]

QUERY_SCHEMA_VERSION = 2
VALID_PURPOSES: frozenset[str] = frozenset({"designing", "deciding", "informing"})
VALID_CONTENTS: frozenset[str] = frozenset({"details", "coherence", "overview"})
VALID_REPO_SCOPES: frozenset[str] = frozenset({"enterprise", "engagement", "both"})
VALID_TARGET_KINDS: frozenset[str] = frozenset({"diagram", "matrix"})
VALID_ENFORCEMENT_SETTINGS: frozenset[str] = frozenset({"off", "warn", "ghost"})
VALID_STYLE_CONDITION_MODES: frozenset[str] = frozenset({"match", "range"})

REPRESENTATION_CAPABILITIES: Mapping[Representation, frozenset[str]] = {
    "exploration": frozenset(
        {"node_shape", "node_icon", "node_color", "edge_color", "edge_emphasis", "cluster_grouping"}
    ),
    "table": frozenset({"columns", "badges", "sort", "row_grouping"}),
    "matrix": frozenset({"row_by", "column_by", "cell_emphasis"}),
    "diagram": frozenset({"node_color", "edge_color", "edge_emphasis", "cluster_grouping"}),
}
"""Capability vocabulary per representation (companion plan §5.1). ``node_*``/``cluster_*``
capabilities and table columns take ``EntityCriteriaGroup`` match criteria; ``edge_*``
capabilities take ``ConnectionCriteriaGroup`` — a mismatch is a save-time validation error.
"""

GROUP_BY_DIMENSIONS: frozenset[str] = frozenset({"type", "specialization", "group"})
"""Non-attribute ``group_by``/matrix ``row_by``/``column_by`` keys; any other value names a
discrete profile attribute."""


@dataclass(frozen=True)
class RangeBand:
    """One half-open ``[minimum, maximum)`` band of a ``mode="range"`` style rule."""

    minimum: float | None  # None = unbounded below; inclusive
    maximum: float | None  # None = unbounded above; exclusive
    value: str  # opaque style token, resolved only by surface adapters


@dataclass(frozen=True)
class StyleRule:
    """Maps matching occurrences to an ABSTRACT style token for one display capability.

    ``match_criteria``/``range_bands`` are mutually exclusive per ``mode``; ``value``
    carries an opaque token — meaningless to domain code, resolved to shape/icon/color only
    by surface adapters (``view_projection.py`` opacity contract).
    """

    capability: str
    applies_to: frozenset[str] = frozenset()  # entity/connection type or specialization slugs
    mode: StyleConditionMode = "match"
    match_criteria: EntityCriteriaGroup | ConnectionCriteriaGroup | None = None  # mode == "match"
    range_attribute: str | None = None  # mode == "range": numeric/date attribute path
    range_bands: tuple[RangeBand, ...] = ()  # mode == "range"
    value: str | None = None  # mode == "match": token applied when matched


@dataclass(frozen=True)
class ColumnSpec:
    label: str
    source: str  # dotted attribute path (§3.3) — the only supported column source today


@dataclass(frozen=True)
class PresentationSpec:
    representation: Representation
    display_options: Mapping[str, object] = field(default_factory=dict)
    columns: tuple[ColumnSpec, ...] | None = None  # table only
    row_by: str | None = None  # matrix, grouped axes only
    column_by: str | None = None  # matrix, grouped axes only
    row_criteria: EntityCriteriaGroup | None = None  # matrix, criteria axes only
    column_criteria: EntityCriteriaGroup | None = None  # matrix, criteria axes only
    group_by: str | None = None  # exploration/table row_grouping
    styling_rules: tuple[StyleRule, ...] = ()  # ordered, first-match-wins per capability
    default_style: Mapping[str, str] = field(default_factory=dict)  # capability -> fallback token


@dataclass(frozen=True)
class ExecutableViewpointQuery:
    """Selects one included entity population — the primary ``entity_criteria`` matches
    plus any ``include_connected`` neighbors — and its constrained connections (companion
    plan §4). Representation-specific projection lives in ``PresentationSpec``.
    """

    query_schema: int = QUERY_SCHEMA_VERSION
    entity_criteria: EntityCriteriaGroup = EntityCriteriaGroup()
    include_connected: tuple[NeighborInclusion, ...] = ()
    connections: ConnectionSelection = ConnectionSelection()
    repo_scope: RepoScope = "both"


@dataclass(frozen=True)
class ViewpointDefinition:
    slug: str
    version: int
    name: str
    description: str = ""
    rationale: str = ""
    purpose: tuple[Purpose, ...] = ("informing",)
    content: tuple[Content, ...] = ("overview",)
    stakeholders: tuple[str, ...] = ()
    concerns: tuple[str, ...] = ()
    scope: ConceptScope = field(default_factory=ConceptScope.unrestricted)
    representation_types: tuple[str, ...] = ()
    derivation_defaults: Mapping[str, object] = field(default_factory=dict)
    query: ExecutableViewpointQuery | None = None
    presentation: PresentationSpec | None = None


@dataclass(frozen=True)
class ViewpointApplication:
    """One *persisted* diagram's or matrix's use of a definition to narrow its authoring
    scope. Unrelated to on-demand execution: executing a definition's query directly
    needs no application and creates no artifact."""

    target_kind: TargetKind
    target_id: str
    viewpoint_slug: str
    pinned_version: int
    enforcement_override: EnforcementSetting | None = None
    derivation_params: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ViewpointCatalog:
    """Immutable lookup for viewpoint definitions, unique by slug."""

    entries: tuple[ViewpointDefinition, ...] = ()

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for entry in self.entries:
            if entry.slug in seen:
                raise ValueError(f"Duplicate viewpoint slug '{entry.slug}'")
            seen.add(entry.slug)

    def __or__(self, other: "ViewpointCatalog") -> "ViewpointCatalog":
        return ViewpointCatalog(self.entries + other.entries)

    def get(self, slug: str) -> ViewpointDefinition | None:
        for entry in self.entries:
            if entry.slug == slug:
                return entry
        return None

    @staticmethod
    def empty() -> "ViewpointCatalog":
        return ViewpointCatalog()
