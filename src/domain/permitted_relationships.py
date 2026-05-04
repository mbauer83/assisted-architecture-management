"""PermittedRelationship and PermittedRelationshipSet value types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.module_types import ConnectionTypeName, EntityTypeName


@dataclass(frozen=True)
class PermittedRelationship:
    source_type: EntityTypeName
    target_type: EntityTypeName
    connection_type: ConnectionTypeName


@dataclass(frozen=True)
class PermittedRelationshipSet:
    _rules: frozenset[PermittedRelationship]

    def permits(
        self,
        src: EntityTypeName,
        tgt: EntityTypeName,
        conn: ConnectionTypeName,
    ) -> bool:
        return PermittedRelationship(src, tgt, conn) in self._rules

    def permitted_connection_types(
        self,
        src: EntityTypeName,
        tgt: EntityTypeName,
    ) -> frozenset[ConnectionTypeName]:
        return frozenset(
            r.connection_type
            for r in self._rules
            if r.source_type == src and r.target_type == tgt
        )

    def by_source(self) -> dict[EntityTypeName, list[tuple[EntityTypeName, ConnectionTypeName]]]:
        out: dict[EntityTypeName, list[tuple[EntityTypeName, ConnectionTypeName]]] = {}
        for r in self._rules:
            out.setdefault(r.source_type, []).append((r.target_type, r.connection_type))
        return out

    def filter_to(
        self,
        entity_types: frozenset[EntityTypeName],
        connection_types: frozenset[ConnectionTypeName],
    ) -> PermittedRelationshipSet:
        return PermittedRelationshipSet(frozenset(
            r for r in self._rules
            if r.source_type in entity_types
            and r.target_type in entity_types
            and r.connection_type in connection_types
        ))

    def __or__(self, other: PermittedRelationshipSet) -> PermittedRelationshipSet:
        return PermittedRelationshipSet(self._rules | other._rules)

    @staticmethod
    def empty() -> PermittedRelationshipSet:
        return PermittedRelationshipSet(frozenset())
