"""Tests for direct per-entity derived attributes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.viewpoint_binding_evaluation import BindingEvaluationInput, evaluate_derived_attributes
from src.domain.viewpoint_bindings import DerivedAttribute
from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.domain.viewpoint_criteria import AttributeCondition, EntityCriteriaGroup, ValueRef
from src.domain.viewpoint_criteria_evaluation import evaluate_entity_criteria
from src.domain.viewpoint_evaluation_context import EvaluationEnvironment


def _entity(identifier: str, *, score: int = 0) -> EntityRecord:
    return EntityRecord(
        identifier,
        "component",
        identifier,
        "1",
        "draft",
        "application",
        "components",
        Path(f"/{identifier}.md"),
        (),
        {"score": score},
        "",
        {},
        identifier,
        "",
    )


@dataclass
class _Graph:
    entities: dict[str, EntityRecord] = field(default_factory=dict)
    connections: list[ConnectionRecord] = field(default_factory=list)

    def get_entity(self, artifact_id: str) -> EntityRecord | None:
        return self.entities.get(artifact_id)

    def get_connection(self, artifact_id: str) -> ConnectionRecord | None:
        return next((item for item in self.connections if item.artifact_id == artifact_id), None)

    def find_connections_for(self, entity_id: str, *, direction: str = "any", conn_type: str | None = None):
        return [item for item in self.connections if item.involves(entity_id)]


_REGISTRIES = RegistrySnapshot(
    frozenset({"component"}), frozenset({"serves"}), frozenset(), {"score": "integer"}, {"weight": "integer"}
)


def test_direct_derived_attribute_is_available_as_a_criteria_path() -> None:
    graph = _Graph(entities={"A": _entity("A"), "B": _entity("B", score=7)})
    graph.connections.append(ConnectionRecord("C", "A", "B", "serves", "1", "draft", Path("/C.md"), {"weight": 4}, ""))
    input = BindingEvaluationInput(("A", "B"), ("C",), graph, _REGISTRIES)
    attributes = (
        DerivedAttribute("served-count"),
        DerivedAttribute("maximum-score", reduce="max", of="endpoint.score"),
    )
    environment = evaluate_derived_attributes(attributes, ("A",), input=input, environment=EvaluationEnvironment())
    assert environment.derived_values[("A", "served-count")] == 1
    assert environment.derived_values[("A", "maximum-score")] == 7
    criteria = EntityCriteriaGroup(children=(AttributeCondition("derived.maximum-score", "eq", ValueRef(literal=7)),))
    assert evaluate_entity_criteria(
        criteria, graph.entities["A"], read_access=graph, registries=_REGISTRIES, environment=environment
    ).matched
