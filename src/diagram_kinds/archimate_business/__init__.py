from __future__ import annotations

from pathlib import Path

from src.diagram_kinds._archimate_kind import load_archimate_diagram_kind
from src.domain.ontology_protocol import DiagramKindModule

module: DiagramKindModule = load_archimate_diagram_kind(Path(__file__).parent)
