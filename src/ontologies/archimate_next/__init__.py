"""ArchiMate NEXT Snapshot 1 ontology module."""

from pathlib import Path

from src.domain.ontology_protocol import OntologyModule
from src.ontologies.archimate_next._loader import load_archimate_next_module

module: OntologyModule = load_archimate_next_module(Path(__file__).parent)  # type: ignore[assignment]
