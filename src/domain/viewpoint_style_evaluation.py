"""Style-rule evaluation for one placed entity/connection occurrence (companion plan §5.2):
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
from typing import Literal

from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.viewpoint_condition_evaluation import read_attribute_value
from src.domain.viewpoint_condition_validation import CriteriaContext, RegistrySnapshot, resolve_attribute_path
from src.domain.viewpoint_criteria import ConnectionCriteriaGroup, EntityCriteriaGroup
from src.domain.viewpoint_criteria_evaluation import evaluate_connection_criteria, evaluate_entity_criteria
from src.domain.viewpoint_evaluation_context import CriteriaReadAccess
from src.domain.viewpoints import PresentationSpec, RangeBand, StyleRule

ItemKind = Literal["entity", "connection"]
Item = EntityRecord | ConnectionRecord


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
    rule: StyleRule, item: Item, context: CriteriaContext, *, registries: RegistrySnapshot
) -> tuple[str | None, frozenset[str]]:
    if rule.range_attribute is None:
        return None, frozenset()
    declared = resolve_attribute_path(rule.range_attribute, context=context, registries=registries)
    if declared is None:
        return None, frozenset({rule.range_attribute})
    value, present = read_attribute_value(item, rule.range_attribute, context=context)
    if not present:
        return None, frozenset()
    return _band_for(value, rule.range_bands), frozenset()


def evaluate_item_style(
    item: Item,
    item_kind: ItemKind,
    presentation: PresentationSpec | None,
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
) -> tuple[Mapping[str, str], frozenset[str]]:
    """Resolve every display capability for one occurrence: ``(style_map, schema_drift)``."""
    if presentation is None:
        return {}, frozenset()
    context: CriteriaContext = item_kind
    tags = _item_tags(item, item_kind)
    resolved: dict[str, str] = {}
    decided: set[str] = set()
    drift: set[str] = set()
    for rule in presentation.styling_rules:
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
        else:
            token, rule_drift = _range_token(rule, item, context, registries=registries)
            drift |= rule_drift
            if token is not None:
                resolved[rule.capability] = token
                decided.add(rule.capability)
    for capability, token in presentation.default_style.items():
        resolved.setdefault(capability, token)
    return resolved, frozenset(drift)
