"""Declarative pairwise relationship-composition rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Certainty = Literal["certain", "potential"]


@dataclass(frozen=True)
class CompositionRule:
    """One source-specification rule, identified only through traceability metadata."""

    spec_ref: str
    certainty: Certainty
    first_role: str
    second_role: str
    result: Literal["first", "second", "weakest", "specialization", "triggering", "flow"]
    second_orientation: Literal["forward", "reverse", "either"] = "forward"


CERTAIN_COMPOSITION_RULES: tuple[CompositionRule, ...] = (
    CompositionRule("DR1", "certain", "specialization", "specialization", "specialization"),
    CompositionRule("DR2", "certain", "structural", "structural", "weakest"),
    CompositionRule("DR3", "certain", "structural", "dependency", "second"),
    CompositionRule("DR4", "certain", "structural", "dependency", "second", "reverse"),
    CompositionRule("DR5", "certain", "structural", "dynamic", "second"),
    CompositionRule("DR6", "certain", "structural", "dynamic", "flow", "reverse"),
    CompositionRule("DR7", "certain", "dynamic", "structural", "triggering"),
    CompositionRule("DR8", "certain", "dynamic", "dynamic", "triggering"),
)
