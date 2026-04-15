"""
archimate_types.py — Flat membership sets for type validation.

Derived from the YAML ontology config loaded by ``ontology_loader``.
To add a new type, update config/entity_ontology.yaml or
config/connection_ontology.yaml.
"""

from src.common.ontology_loader import CONNECTION_TYPES, ENTITY_TYPES

#: Every valid entity ``artifact-type`` value.
ALL_ENTITY_TYPES: frozenset[str] = frozenset(ENTITY_TYPES)

#: Every valid connection ``artifact-type`` value.
ALL_CONNECTION_TYPES: frozenset[str] = frozenset(CONNECTION_TYPES)
