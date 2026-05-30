"""explicit-selection/v1 strategy.

Candidate set = the caller-supplied entity_ids and optional connection_ids,
filtered to those that exist in the model query's known ids.

No pre_filters are supported (the caller specifies the set explicitly).
Projects to ``represents`` by default.
"""

from __future__ import annotations

from src.application.derivation.strategy_registry import StrategySpec, register_strategy
from src.application.derivation.types import CandidateSet, ModelQuery
from src.domain.view_derivations import SourceModelSnapshot


def derive(
    params: dict[str, object],
    snapshot: SourceModelSnapshot,
    query: ModelQuery,
) -> CandidateSet:
    """Return the supplied entity_ids/connection_ids filtered to those that exist."""
    raw_entity_ids = params.get("entity_ids")
    entity_ids: list[str] = (
        [str(x) for x in raw_entity_ids] if isinstance(raw_entity_ids, list) else []
    )

    raw_conn_ids = params.get("connection_ids")
    connection_ids: list[str] = (
        [str(x) for x in raw_conn_ids] if isinstance(raw_conn_ids, list) else []
    )

    known_entities = query.entity_ids()
    known_connections = query.connection_ids()

    return CandidateSet(
        entity_ids=frozenset(eid for eid in entity_ids if eid in known_entities),
        connection_ids=frozenset(cid for cid in connection_ids if cid in known_connections),
    )


SPEC = StrategySpec(
    name="explicit-selection",
    version=1,
    supported_filters=frozenset(),
)
register_strategy(SPEC, derive)
