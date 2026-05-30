from pathlib import Path

from src.diagram_types._c4_type import load_c4_diagram_type
from src.domain.ontology_protocol import DiagramTypeModule

module: DiagramTypeModule = load_c4_diagram_type(Path(__file__).parent)
