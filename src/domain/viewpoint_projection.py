"""The viewpoint projection: the unifying contract between repository execution, the
verifier's artifact-local checks, and the GUI's ghost/hide overlay.

Deliberately parallel to ``view_projection.py``'s opacity contract — same philosophy
(opaque display tokens, generic code never interprets them), different concern (derivation
preview vs. viewpoint evaluation). Pure shapes only; the application-layer projection
service that produces instances of these types is a later work unit.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

ProjectionTarget = Literal["repository", "diagram", "matrix"]
OcclusionState = Literal["visible", "ghosted"]
ExclusionReason = Literal[
    "out_of_scope",  # fails effective ConceptScope (diagram-type scope ∩ viewpoint scope)
    "criteria_mismatch",  # fails the definition's entity/connection criteria
    "endpoint_excluded",  # connection whose source/target is itself excluded
]
Membership = Literal["primary", "expanded"]


@dataclass(frozen=True)
class ProjectedOccurrence:
    """One entity's or connection's state within a projection.

    ``style`` is documented (not structurally enforced here — the producing service owns
    the invariant) to be empty whenever ``reasons`` is non-empty: an excluded occurrence is
    never styled, in every enforcement mode, because style tokens express the viewpoint's
    semantics, which an excluded item by definition does not satisfy.
    """

    item_id: str
    item_kind: Literal["entity", "connection"]
    state: OcclusionState
    membership: Membership = "primary"  # connections are always "primary"
    reasons: tuple[ExclusionReason, ...] = ()  # empty iff the item fully matches
    style: Mapping[str, object] = field(default_factory=dict)  # capability -> opaque token or scale position
    connection_type: str | None = None
    source_id: str | None = None
    target_id: str | None = None
    certainty: Literal["certain", "potential"] | None = None
    hops: int | None = None
    via_connection_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ViewpointProjection:
    target: ProjectionTarget
    items: tuple[ProjectedOccurrence, ...]
    stale_pin: bool = False  # artifact-local only: pinned_version < current definition version
    warnings: tuple[str, ...] = ()  # schema drift, capability drift, unresolved references
    scale_legends: tuple["ScaleLegendData", ...] = ()


@dataclass(frozen=True)
class ScaleLegendData:
    """A scale's resolved bounds and endpoint tokens for a presentation adapter."""

    capability: str
    attribute: str
    minimum: float
    maximum: float
    tokens: tuple[str, str]


def drift_warnings(drift: frozenset[str]) -> tuple[str, ...]:
    """One human-readable warning per schema-drifted attribute path (degraded loudly,
    never silently"), sorted for deterministic output."""
    return tuple(f"schema drift: attribute '{attribute}' is no longer resolvable" for attribute in sorted(drift))
