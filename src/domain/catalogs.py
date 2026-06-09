"""Focused injectable catalog Protocols and their ModuleCatalog-backed implementations.

Protocols (OntologyCatalog, ConnectionSemantics, DiagramTypeCatalog) live in the
domain layer; implementations are built at the composition root from a frozen
ModuleCatalog and injected into consumers.
"""

from __future__ import annotations

import functools
from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from src.domain.module_catalog import ModuleCatalog
from src.domain.module_types import ConnectionTypeName, ElementClassName, EntityTypeName
from src.domain.ontology_protocol import DiagramTypeModule
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet

# ── Protocols ─────────────────────────────────────────────────────────────────

@runtime_checkable
class OntologyCatalog(Protocol):
    """Read-only ontology data derived from the registered module catalog."""

    def all_entity_types(self) -> Mapping[str, EntityTypeInfo]: ...
    def all_connection_types(self) -> Mapping[str, ConnectionTypeInfo]: ...
    def all_entity_type_names(self) -> frozenset[str]: ...
    def all_connection_type_names(self) -> frozenset[str]: ...
    def known_domain_names(self) -> frozenset[str]: ...
    def domain_order(self) -> Sequence[str]: ...
    def domain_grouping(self) -> Mapping[str, str]: ...
    def entity_types_with_class(self, element_class: str) -> frozenset[str]: ...
    def expand_entity_type_term(self, term: str) -> Sequence[str]: ...
    def format_entity_type_term(self, term: str) -> str: ...
    def entity_type_term_matches(self, term: str, linked_types: set[str]) -> bool: ...
    def archimate_stereotype_to_connection_type(self) -> Mapping[str, str]: ...
    def entity_type_prefixes(self) -> Mapping[str, str]: ...
    def matrix_abbreviations_by_connection_type(self) -> Mapping[str, str]: ...
    def matrix_connection_type_abbreviations(self) -> Mapping[str, str]: ...


@runtime_checkable
class ConnectionSemantics(Protocol):
    """Permitted-relationship and symmetry queries over registered ontologies."""

    def is_symmetric(self, conn_type: str) -> bool: ...
    def permissible_connection_types(self, source_type: str, target_type: str) -> Sequence[str]: ...
    def permissible_target_types(self, source_type: str) -> Mapping[str, Sequence[str]]: ...
    def classify_connections(self, source_type: str) -> Mapping[str, Mapping[str, Sequence[str]]]: ...


@runtime_checkable
class DiagramTypeCatalog(Protocol):
    """Diagram-type lookup and relation-label suppression logic."""

    def suppressed_stereotype_tokens(self) -> frozenset[str]: ...
    def diagram_type_domain(self, name: str) -> str | None: ...
    def get_diagram_type(self, name: str) -> DiagramTypeModule: ...
    def find_diagram_type(self, name: str) -> DiagramTypeModule | None: ...
    def all_diagram_types(self) -> Mapping[str, DiagramTypeModule]: ...


# ── Implementations ───────────────────────────────────────────────────────────

class OntologyCatalogImpl:
    """ModuleCatalog-backed OntologyCatalog.

    matrix_abbreviations: Mapping[abbrev → conn_type] — supplied at the
    composition root from the ontology package so that domain stays free of
    ontologies imports (resolves D8 when injected in Phase C/D).
    """

    def __init__(self, catalog: ModuleCatalog, matrix_abbreviations: Mapping[str, str]) -> None:
        self._catalog = catalog
        self._matrix_abbrevs: dict[str, str] = dict(matrix_abbreviations)

    @functools.cached_property
    def _et(self) -> dict[str, EntityTypeInfo]:
        return {str(n): info for n, info in self._catalog.all_entity_types().items()}

    @functools.cached_property
    def _ct(self) -> dict[str, ConnectionTypeInfo]:
        return {str(n): info for n, info in self._catalog.all_connection_types().items()}

    @functools.cached_property
    def _et_names(self) -> frozenset[str]:
        return frozenset(self._et)

    @functools.cached_property
    def _ct_names(self) -> frozenset[str]:
        return frozenset(self._ct)

    @functools.cached_property
    def _domain_names(self) -> frozenset[str]:
        domains = {info.hierarchy[0] for info in self._et.values() if info.hierarchy}
        return frozenset(domains | {"unknown"})

    @functools.cached_property
    def _domain_ord(self) -> list[str]:
        return self._catalog.domain_order()

    @functools.cached_property
    def _archimate_stereo_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for info in self._ct.values():
            if info.conn_lang == "archimate" and info.archimate_relationship_type is not None:
                result[info.archimate_relationship_type.lower()] = info.artifact_type
        return result

    @functools.cached_property
    def _et_prefix_map(self) -> dict[str, str]:
        return {info.prefix: at for at, info in self._et.items()}

    def all_entity_types(self) -> Mapping[str, EntityTypeInfo]:
        return self._et

    def all_connection_types(self) -> Mapping[str, ConnectionTypeInfo]:
        return self._ct

    def all_entity_type_names(self) -> frozenset[str]:
        return self._et_names

    def all_connection_type_names(self) -> frozenset[str]:
        return self._ct_names

    def known_domain_names(self) -> frozenset[str]:
        return self._domain_names

    def domain_order(self) -> Sequence[str]:
        return list(self._domain_ord)

    def domain_grouping(self) -> Mapping[str, str]:
        return {d: f"{d.capitalize()}Grouping" for d in self._domain_ord}

    def entity_types_with_class(self, element_class: str) -> frozenset[str]:
        raw = self._catalog.entity_types_with_class(ElementClassName(element_class))
        return frozenset(str(n) for n in raw)

    def expand_entity_type_term(self, term: str) -> Sequence[str]:
        if term == "@all":
            return sorted(self._et_names)
        if term.startswith("@"):
            return sorted(self.entity_types_with_class(term[1:]))
        return [term] if term in self._et_names else []

    def format_entity_type_term(self, term: str) -> str:
        if term == "@all":
            return "entity"
        normalized = term[1:] if term.startswith("@") else term
        return normalized.replace("-", " ").replace("_", " ")

    def entity_type_term_matches(self, term: str, linked_types: set[str]) -> bool:
        return bool(set(self.expand_entity_type_term(term)) & linked_types)

    def archimate_stereotype_to_connection_type(self) -> Mapping[str, str]:
        return self._archimate_stereo_map

    def entity_type_prefixes(self) -> Mapping[str, str]:
        return self._et_prefix_map

    def matrix_abbreviations_by_connection_type(self) -> Mapping[str, str]:
        return self._matrix_abbrevs

    def matrix_connection_type_abbreviations(self) -> Mapping[str, str]:
        return {ct: abbrev for abbrev, ct in self._matrix_abbrevs.items()}


class ConnectionSemanticsImpl:
    """ModuleCatalog-backed ConnectionSemantics."""

    def __init__(self, catalog: ModuleCatalog) -> None:
        self._catalog = catalog

    @functools.cached_property
    def _permitted(self) -> PermittedRelationshipSet:
        return self._catalog.aggregated_permitted_relationships()

    def is_symmetric(self, conn_type: str) -> bool:
        info = self._catalog.find_connection_type(ConnectionTypeName(conn_type))
        return info.symmetric if info is not None else False

    def permissible_connection_types(self, source_type: str, target_type: str) -> Sequence[str]:
        prs = self._permitted
        src, tgt = EntityTypeName(source_type), EntityTypeName(target_type)
        result = set(prs.permitted_connection_types(src, tgt))
        for ct in prs.permitted_connection_types(tgt, src):
            if self.is_symmetric(ct):
                result.add(ct)
        return sorted(result)

    def permissible_target_types(self, source_type: str) -> Mapping[str, Sequence[str]]:
        out: dict[str, list[str]] = {}
        for tgt, ct in self._permitted.by_source().get(EntityTypeName(source_type), []):
            out.setdefault(str(ct), []).append(str(tgt))
        return {ct: sorted(tgts) for ct, tgts in sorted(out.items())}

    def classify_connections(self, source_type: str) -> Mapping[str, Mapping[str, Sequence[str]]]:
        prs = self._permitted
        src = EntityTypeName(source_type)
        outgoing: dict[str, list[str]] = {}
        incoming: dict[str, list[str]] = {}
        symmetric: dict[str, list[str]] = {}
        for tgt, ct in prs.by_source().get(src, []):
            target = symmetric if self.is_symmetric(ct) else outgoing
            target.setdefault(str(tgt), []).append(str(ct))
        for src2, ct in prs.by_target().get(src, []):
            key = str(src2)
            if self.is_symmetric(ct):
                symmetric.setdefault(key, []).extend([] if key in symmetric else [str(ct)])
            else:
                incoming.setdefault(key, []).append(str(ct))
        return {"outgoing": outgoing, "incoming": incoming, "symmetric": symmetric}


def _display_connection_label(conn_type: str) -> str:
    return conn_type.removeprefix("archimate-")


class DiagramTypeCatalogImpl:
    """ModuleCatalog-backed DiagramTypeCatalog."""

    def __init__(self, catalog: ModuleCatalog) -> None:
        self._catalog = catalog

    @functools.cached_property
    def _suppressed(self) -> frozenset[str]:
        return frozenset(
            _display_connection_label(str(name)).lower()
            for name, info in self._catalog.all_connection_types().items()
            if not info.show_stereotype
        )

    def suppressed_stereotype_tokens(self) -> frozenset[str]:
        return self._suppressed

    def diagram_type_domain(self, name: str) -> str | None:
        dt = self._catalog.find_diagram_type(name)
        if dt is None:
            return None
        domains = {
            info.hierarchy[0]
            for info in dt.effective_entity_types().values()
            if not info.internal and info.hierarchy
        }
        non_common = {d for d in domains if d != "common"}
        if len(non_common) == 1:
            return next(iter(non_common))
        if not non_common and len(domains) == 1:
            return next(iter(domains))
        return None

    def get_diagram_type(self, name: str) -> DiagramTypeModule:
        return self._catalog.get_diagram_type(name)

    def find_diagram_type(self, name: str) -> DiagramTypeModule | None:
        return self._catalog.find_diagram_type(name)

    def all_diagram_types(self) -> Mapping[str, DiagramTypeModule]:
        return self._catalog.all_diagram_types()
