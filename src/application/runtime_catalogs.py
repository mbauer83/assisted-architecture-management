"""RuntimeCatalogs — frozen bundle of all domain catalogs.

Built once at each composition root (FastAPI app-state, CLI main(), MCP context)
and injected into consumers. Never accessed via a global singleton.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.derivation.strategy_registry import DerivationStrategyCatalog
from src.domain.catalogs import ConnectionSemantics, DiagramTypeCatalog, OntologyCatalog
from src.domain.module_catalog import ModuleCatalog


@dataclass(frozen=True, eq=False)
class RuntimeCatalogs:
    """Immutable bundle of domain catalogs built once at the composition root."""

    module_catalog: ModuleCatalog
    ontology: OntologyCatalog
    connections: ConnectionSemantics
    diagram_types: DiagramTypeCatalog
    derivation: DerivationStrategyCatalog
    datatype_type_references_blocking: bool = True
