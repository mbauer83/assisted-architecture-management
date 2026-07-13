"""Scale-style evaluation and validation contracts."""

from __future__ import annotations

from pathlib import Path

from src.domain.artifact_types import EntityRecord
from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.domain.viewpoint_evaluation_context import EvaluationEnvironment
from src.domain.viewpoint_presentation_validation import validate_presentation
from src.domain.viewpoint_style_evaluation import ScaleStyleValue, calculate_scale_bounds, evaluate_item_style
from src.domain.viewpoints import PresentationSpec, StyleRule


def _entity(identifier: str, score: int | None) -> EntityRecord:
    extra: dict[str, object] = {} if score is None else {"score": score}
    return EntityRecord(
        artifact_id=identifier,
        artifact_type="application-component",
        name=identifier,
        version="1",
        status="draft",
        domain="application",
        subdomain="",
        path=Path("/fake/entity.md"),
        keywords=(),
        extra=extra,
        content_text="",
        display_blocks={},
        display_label=identifier,
        display_alias="",
    )


_REGISTRIES = RegistrySnapshot(
    known_entity_types=frozenset({"application-component"}),
    known_connection_types=frozenset(),
    known_specialization_slugs=frozenset(),
    entity_attribute_types={"score": "number"},
    connection_attribute_types={},
)


def _presentation(**overrides: object) -> PresentationSpec:
    fields: dict[str, object] = {
        "capability": "node_color",
        "mode": "scale",
        "scale_attribute": "score",
        "scale_tokens": ("cool", "warm"),
    }
    fields.update(overrides)
    rule = StyleRule(**fields)  # type: ignore[arg-type]
    return PresentationSpec(
        representation="exploration",
        styling_rules=(rule,),
        default_style={"node_color": "neutral"},
    )


def test_data_driven_scale_bounds_are_order_independent_and_emit_legend() -> None:
    low, high = _entity("low", 10), _entity("high", 30)
    presentation = _presentation()
    bounds, legends, drift = calculate_scale_bounds(
        presentation,
        ((high, "entity"), (low, "entity")),
        registries=_REGISTRIES,
        environment=EvaluationEnvironment(),
    )

    assert bounds[0].minimum == 10
    assert bounds[0].maximum == 30
    assert legends[0].tokens == ("cool", "warm")
    assert drift == frozenset()
    style, _ = evaluate_item_style(
        low,
        "entity",
        presentation,
        read_access=_EmptyGraph(),
        registries=_REGISTRIES,
        scale_bounds=bounds,
    )
    assert style == {"node_color": ScaleStyleValue(position=0.0, tokens=("cool", "warm"))}


def test_missing_and_out_of_range_scale_values_use_default_style() -> None:
    missing, outside = _entity("missing", None), _entity("outside", 50)
    presentation = _presentation(scale_min=10, scale_max=30)
    bounds, _, _ = calculate_scale_bounds(
        presentation,
        ((missing, "entity"), (outside, "entity")),
        registries=_REGISTRIES,
        environment=EvaluationEnvironment(),
    )
    for entity in (missing, outside):
        style, _ = evaluate_item_style(
            entity,
            "entity",
            presentation,
            read_access=_EmptyGraph(),
            registries=_REGISTRIES,
            scale_bounds=bounds,
        )
        assert style == {"node_color": "neutral"}


def test_scale_validation_rejects_mixed_mode_fields_and_wrong_token_count() -> None:
    presentation = _presentation(value="not-valid", scale_tokens=("only-one",))
    issues = validate_presentation(presentation, path="/presentation", registries=_REGISTRIES, check_ergonomics=True)

    assert {(issue.code, issue.path) for issue in issues} == {
        ("style-mode-field-mismatch", "/presentation/styling_rules/0"),
        ("scale-token-count", "/presentation/styling_rules/0/scale_tokens"),
    }


class _EmptyGraph:
    def get_entity(self, artifact_id: str) -> EntityRecord | None:
        return None

    def find_connections_for(
        self, entity_id: str, *, direction: str = "any", conn_type: str | None = None
    ) -> list[object]:
        return []
