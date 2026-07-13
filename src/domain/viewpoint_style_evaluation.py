"""Style-rule evaluation for one placed entity/connection occurrence:
declaration-order first-match-wins per capability, ``applies_to`` type/specialization
scoping, half-open range bands, and ``default_style`` fallback. Relational styling (a
``mode="match"`` rule whose criteria contain an ``IncidentConnectionCondition``) is not a
separate mechanism — it falls out of reusing ``evaluate_entity_criteria``/
``evaluate_connection_criteria`` unchanged.

Callers (the projection service) are responsible for the "occlusion dominates styling"
invariant: this module always computes a style map from ``styling_rules``; it is the
caller's job to discard it when an occurrence carries exclusion reasons.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.viewpoint_condition_evaluation import read_attribute_value
from src.domain.viewpoint_condition_validation import CriteriaContext, RegistrySnapshot, resolve_attribute_path
from src.domain.viewpoint_criteria import ConnectionCriteriaGroup, EntityCriteriaGroup
from src.domain.viewpoint_criteria_evaluation import evaluate_connection_criteria, evaluate_entity_criteria
from src.domain.viewpoint_evaluation_context import CriteriaReadAccess, EvaluationEnvironment
from src.domain.viewpoints import PresentationSpec, RangeBand, StyleRule

ItemKind = Literal["entity", "connection"]
Item = EntityRecord | ConnectionRecord


@dataclass(frozen=True)
class ScaleStyleValue:
    """Adapter-facing scale result: interpolate between tokens at ``position``."""

    position: float
    tokens: tuple[str, str]


StyleValue = str | ScaleStyleValue


@dataclass(frozen=True)
class ScaleBounds:
    minimum: float
    maximum: float


@dataclass(frozen=True)
class ScaleLegend:
    capability: str
    attribute: str
    minimum: float
    maximum: float
    tokens: tuple[str, str]


def _item_tags(item: Item, item_kind: ItemKind) -> frozenset[str]:
    if item_kind == "connection":
        assert isinstance(item, ConnectionRecord)
        return frozenset({item.conn_type, item.specialization}) - {""}
    assert isinstance(item, EntityRecord)
    return frozenset({item.artifact_type, item.specialization}) - {""}


def _match_outcome(
    rule: StyleRule, item: Item, item_kind: ItemKind, *, read_access: CriteriaReadAccess, registries: RegistrySnapshot
) -> tuple[bool, frozenset[str]]:
    if rule.match_criteria is None:
        return False, frozenset()
    if item_kind == "entity":
        assert isinstance(rule.match_criteria, EntityCriteriaGroup)
        assert isinstance(item, EntityRecord)
        outcome = evaluate_entity_criteria(rule.match_criteria, item, read_access=read_access, registries=registries)
    else:
        assert isinstance(rule.match_criteria, ConnectionCriteriaGroup)
        assert isinstance(item, ConnectionRecord)
        outcome = evaluate_connection_criteria(
            rule.match_criteria, item, read_access=read_access, registries=registries
        )
    return outcome.matched, outcome.schema_drift


def _band_for(value: object, bands: tuple[RangeBand, ...]) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    for band in bands:
        if (band.minimum is None or value >= band.minimum) and (band.maximum is None or value < band.maximum):
            return band.value
    return None


def _range_token(
    rule: StyleRule,
    item: Item,
    context: CriteriaContext,
    *,
    registries: RegistrySnapshot,
    environment: EvaluationEnvironment,
) -> tuple[str | None, frozenset[str]]:
    if rule.range_attribute is None:
        return None, frozenset()
    declared = resolve_attribute_path(rule.range_attribute, context=context, registries=registries)
    if declared is None:
        return None, frozenset({rule.range_attribute})
    value, present = read_attribute_value(item, rule.range_attribute, context=context, environment=environment)
    if not present:
        return None, frozenset()
    return _band_for(value, rule.range_bands), frozenset()


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        return float(value.date().toordinal())
    if isinstance(value, date):
        return float(value.toordinal())
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            try:
                return float(date.fromisoformat(value).toordinal())
            except ValueError:
                return None
    return None


def _scale_bound(value: float | str | None) -> float | None:
    return _number(value) if value is not None else None


def calculate_scale_bounds(
    presentation: PresentationSpec | None,
    items: tuple[tuple[Item, ItemKind], ...],
    *,
    registries: RegistrySnapshot,
    environment: EvaluationEnvironment,
) -> tuple[Mapping[int, ScaleBounds], tuple[ScaleLegend, ...], frozenset[str]]:
    """Calculate deterministic bounds from the complete selected result set."""
    if presentation is None:
        return {}, (), frozenset()
    bounds: dict[int, ScaleBounds] = {}
    legends: list[ScaleLegend] = []
    drift: set[str] = set()
    for index, rule in enumerate(presentation.styling_rules):
        if rule.mode != "scale" or rule.scale_attribute is None or len(rule.scale_tokens) != 2:
            continue
        values: list[float] = []
        for item, kind in items:
            if rule.applies_to and not (rule.applies_to & _item_tags(item, kind)):
                continue
            context: CriteriaContext = kind
            if resolve_attribute_path(rule.scale_attribute, context=context, registries=registries) is None:
                if not rule.scale_attribute.startswith("derived."):
                    drift.add(rule.scale_attribute)
                continue
            value, present = read_attribute_value(
                item, rule.scale_attribute, context=context, environment=environment
            )
            numeric = _number(value) if present else None
            if numeric is not None:
                values.append(numeric)
        minimum = _scale_bound(rule.scale_min)
        maximum = _scale_bound(rule.scale_max)
        if minimum is None and values:
            minimum = min(values)
        if maximum is None and values:
            maximum = max(values)
        if minimum is None or maximum is None:
            continue
        tokens = (rule.scale_tokens[0], rule.scale_tokens[1])
        bounds[index] = ScaleBounds(minimum=minimum, maximum=maximum)
        legends.append(
            ScaleLegend(
                capability=rule.capability,
                attribute=rule.scale_attribute,
                minimum=minimum,
                maximum=maximum,
                tokens=tokens,
            )
        )
    return bounds, tuple(legends), frozenset(drift)


def _scale_value(
    rule: StyleRule,
    index: int,
    item: Item,
    context: CriteriaContext,
    *,
    registries: RegistrySnapshot,
    environment: EvaluationEnvironment,
    bounds: Mapping[int, ScaleBounds],
) -> ScaleStyleValue | None:
    if rule.scale_attribute is None or len(rule.scale_tokens) != 2 or index not in bounds:
        return None
    # Same schema-drift contract as every other comparator/style path: an attribute path
    # the registries don't know (and isn't a derived. path, which bypasses schema lookup
    # by design) is treated as absent, not read straight off raw extra data.
    if (
        not rule.scale_attribute.startswith("derived.")
        and resolve_attribute_path(rule.scale_attribute, context=context, registries=registries) is None
    ):
        return None
    value, present = read_attribute_value(item, rule.scale_attribute, context=context, environment=environment)
    numeric = _number(value) if present else None
    if numeric is None:
        return None
    scale = bounds[index]
    if numeric < scale.minimum or numeric > scale.maximum:
        return None
    position = 0.0 if scale.maximum == scale.minimum else (numeric - scale.minimum) / (scale.maximum - scale.minimum)
    return ScaleStyleValue(position=position, tokens=(rule.scale_tokens[0], rule.scale_tokens[1]))


def evaluate_item_style(
    item: Item,
    item_kind: ItemKind,
    presentation: PresentationSpec | None,
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
    environment: EvaluationEnvironment = EvaluationEnvironment(),
    scale_bounds: Mapping[int, ScaleBounds] = {},
) -> tuple[Mapping[str, StyleValue], frozenset[str]]:
    """Resolve every display capability for one occurrence: ``(style_map, schema_drift)``."""
    if presentation is None:
        return {}, frozenset()
    context: CriteriaContext = item_kind
    tags = _item_tags(item, item_kind)
    resolved: dict[str, StyleValue] = {}
    decided: set[str] = set()
    drift: set[str] = set()
    for index, rule in enumerate(presentation.styling_rules):
        if rule.capability in decided:
            continue
        if rule.applies_to and not (rule.applies_to & tags):
            continue
        if rule.mode == "match":
            matched, rule_drift = _match_outcome(rule, item, item_kind, read_access=read_access, registries=registries)
            drift |= rule_drift
            if matched and rule.value is not None:
                resolved[rule.capability] = rule.value
                decided.add(rule.capability)
        elif rule.mode == "range":
            token, rule_drift = _range_token(
                rule, item, context, registries=registries, environment=environment
            )
            drift |= rule_drift
            if token is not None:
                resolved[rule.capability] = token
                decided.add(rule.capability)
        else:
            value = _scale_value(
                rule, index, item, context, registries=registries, environment=environment, bounds=scale_bounds
            )
            if value is not None:
                resolved[rule.capability] = value
                decided.add(rule.capability)
    for capability, token in presentation.default_style.items():
        resolved.setdefault(capability, token)
    return resolved, frozenset(drift)
