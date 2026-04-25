from __future__ import annotations

from src.infrastructure.gui.routers._diagram_context import (
    parse_explicit_connection_pairs as _parse_explicit_connection_pairs,
)


def test_parse_explicit_connection_pairs_supports_archimate_relation_macros() -> None:
    puml = """\
@startuml test
rectangle "A" as A
rectangle "B" as B
rectangle "C" as C
Rel_Influence_Down(A, B, "")
Rel_Association(B, C, "")
@enduml
"""

    pairs = _parse_explicit_connection_pairs(puml)

    assert ("A", "B") in pairs
    assert ("B", "C") in pairs
