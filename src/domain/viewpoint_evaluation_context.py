"""Shared context types for the pure criteria evaluator (companion plan §3.4): the
read-access surface it needs for adjacency/endpoint lookups, and the outcome shape every
evaluation function returns.

``CriteriaReadAccess`` is deliberately narrow and structurally identical to the relevant
slice of the existing ``ArtifactLookup``/``RelationshipGraph`` application ports
(``src/application/ports.py``) — any real artifact store already satisfies it, so no new
port or adapter is needed to wire a live evaluator, per the standing "use existing read
ports" rule. Direction filtering is always done by the evaluator itself (symmetric-type
normalization lives in ``viewpoint_criteria_evaluation.py``), so callers only ever pass
``direction="any"`` here and let the evaluator narrow further.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from src.domain.artifact_types import ConnectionRecord, EntityRecord


class CriteriaReadAccess(Protocol):
    def get_entity(self, artifact_id: str) -> EntityRecord | None: ...

    def find_connections_for(
        self,
        entity_id: str,
        *,
        direction: Literal["any", "outbound", "inbound"] = "any",
        conn_type: str | None = None,
    ) -> list[ConnectionRecord]: ...


@dataclass(frozen=True)
class EvaluationOutcome:
    """Result of evaluating one criteria (sub)tree: the match/no-match verdict plus any
    schema-drift attribute paths encountered anywhere in the subtree (§3.4's "schema drift
    at evaluation time" rule). Drift is collected from every branch regardless of which one
    decided the match — evaluation never short-circuits away a warning."""

    matched: bool
    schema_drift: frozenset[str] = frozenset()
