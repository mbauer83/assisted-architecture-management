"""Ontology catalog utilities.

Registry-backed functions were removed in WU-05 (hexagonal conformance).
All registry data is now available via OntologyCatalog / ConnectionSemantics /
DiagramTypeCatalog (see src/domain/catalogs.py) injected from the composition root.
Pure utility functions remain here.
"""

from __future__ import annotations

from functools import lru_cache

from src.ontologies.archimate_next import matrix_abbreviations as _archimate_matrix_abbreviations


def format_entity_type_term(term: str) -> str:
    if term == "@all":
        return "entity"
    normalized = term[1:] if term.startswith("@") else term
    return normalized.replace("-", " ").replace("_", " ")


@lru_cache(maxsize=1)
def matrix_abbreviations_by_connection_type() -> dict[str, str]:
    return dict(_archimate_matrix_abbreviations)


@lru_cache(maxsize=1)
def matrix_connection_type_abbreviations() -> dict[str, str]:
    return {conn_type: abbrev for abbrev, conn_type in matrix_abbreviations_by_connection_type().items()}
