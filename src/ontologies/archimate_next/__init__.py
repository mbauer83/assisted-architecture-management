"""ArchiMate NEXT Snapshot 1 ontology module."""

from pathlib import Path

from src.domain.ontology_protocol import OntologyModule
from src.ontologies.archimate_next._loader import load_archimate_next_module

_mod = load_archimate_next_module(Path(__file__).parent)
module: OntologyModule = _mod  # type: ignore[assignment]
matrix_abbreviations: dict[str, str] = _mod.matrix_abbreviations
