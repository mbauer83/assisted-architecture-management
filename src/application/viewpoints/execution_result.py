"""``ViewpointExecutionResult``: the ephemeral, never-persisted DTO
``EvaluateViewpoint`` returns. Identical shape for REST and both MCP tools — one contract,
no per-transport reshaping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Membership = Literal["primary", "expanded"]


@dataclass(frozen=True)
class EntityItemSummary:
    """Fixed, non-customizable per-entity summary."""

    id: str
    name: str
    type: str
    specialization_slugs: tuple[str, ...]
    group: str
    membership: Membership


@dataclass(frozen=True)
class ConnectionItemSummary:
    """Fixed, non-customizable per-connection summary."""

    id: str
    type: str
    source: str
    target: str
    certainty: Literal["certain", "potential"] | None = None
    hops: int | None = None
    via_connection_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class MatrixAxisIds:
    """Present iff the executed definition's presentation is a criteria-axes matrix.
    Sorted subsets of the result's returned entity ids; unrendered entities are the
    complement, derivable, so not duplicated here."""

    row_entity_ids: tuple[str, ...]
    column_entity_ids: tuple[str, ...]


@dataclass(frozen=True)
class ViewpointExecutionResult:
    """One execution's full result — identity/provenance, content, counts/truncation,
    optional matrix axes, warnings, and timing. Never persisted."""

    slug: str | None
    version: int | None
    query_schema: int
    repo_scope: str
    executed_at: str
    index_generation: int | None
    entity_ids: tuple[str, ...]
    connection_ids: tuple[str, ...]
    entities: tuple[EntityItemSummary, ...]
    connections: tuple[ConnectionItemSummary, ...]
    total_entity_count: int
    returned_entity_count: int
    total_connection_count: int
    returned_connection_count: int
    truncated: bool
    entity_limit: int
    matrix_axes: MatrixAxisIds | None
    warnings: tuple[str, ...]
    duration_ms: float
    query_summary: str
    anchor_ids: tuple[str, ...] = ()
    """Entity ids the execution was anchored on — resolved ``entity-id`` parameter values.
    Presentations use these to mark/center the anchor and derive hop distances."""
