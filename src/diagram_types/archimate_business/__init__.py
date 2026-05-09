from __future__ import annotations

from pathlib import Path

from src.diagram_types._archimate_type import load_archimate_diagram_type
from src.domain.ontology_protocol import DiagramTypeModule

module: DiagramTypeModule = load_archimate_diagram_type(Path(__file__).parent)
