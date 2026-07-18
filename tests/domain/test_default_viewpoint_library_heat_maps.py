"""Tests for the heat-map style rule on ``resource-map``: the ``investment_level``
profile attribute (a repo-defined convention, present only when a repo's profile schema
declares it) drives a scale-mode ``node_color`` rule. Covers legend presence, correct
scale-position mapping, and graceful degradation (default style + a drift warning, never
an error) when a repo has not declared the attribute at all. ``capability-map``
deliberately ships NO heat rule — the strategy layer carries no investment attribute, and
a rule that can never resolve would be a standing unresolvable-outcome warning."""

from __future__ import annotations

from src.application.viewpoints.registry_snapshot import build_registry_snapshot
from src.application.viewpoints.repository_projection import project_repository
from src.domain.artifact_types import EntityRecord
from src.domain.viewpoint_style_evaluation import ScaleStyleValue
from tests.application.viewpoints._fixtures import Store, entity
from tests.domain.test_default_viewpoint_library import _CATALOGS, _REGISTRIES, _repo_root_with_fixture_profiles

_NO_PROFILE_REGISTRIES = build_registry_snapshot(_CATALOGS, [])


def _resource(artifact_id: str, investment_level: int | None) -> EntityRecord:
    extra: dict[str, object] = {} if investment_level is None else {"investment_level": investment_level}
    return entity(artifact_id=artifact_id, artifact_type="resource", domain="strategy", extra=extra)


class TestCapabilityMapShipsNoHeatRule:
    def test_capability_map_has_no_styling_rules_and_declares_its_targets(self) -> None:
        definition = _CATALOGS.viewpoints.get("capability-map")
        assert definition is not None
        assert definition.presentation is not None
        assert definition.presentation.styling_rules == ()
        assert definition.presentation.target_types == ("capability", "resource")

    def test_capability_map_execution_raises_no_style_warnings(self) -> None:
        definition = _CATALOGS.viewpoints.get("capability-map")
        assert definition is not None
        store = Store(
            entities={
                "ENT@c1": entity(artifact_id="ENT@c1", artifact_type="capability", domain="strategy"),
            }
        )
        projection = project_repository(definition, read_access=store, registries=_NO_PROFILE_REGISTRIES)
        assert projection.warnings == ()
        assert projection.rule_outcomes == ()


class TestHeatMapLegendAndScaling:
    def test_resource_map_projection_carries_a_heat_legend(self) -> None:
        definition = _CATALOGS.viewpoints.get("resource-map")
        assert definition is not None
        store = Store(entities={"ENT@r1": _resource("ENT@r1", 2)})
        projection = project_repository(definition, read_access=store, registries=_REGISTRIES)
        assert len(projection.scale_legends) == 1
        legend = projection.scale_legends[0]
        assert legend.capability == "node_color"
        assert legend.attribute == "investment_level"
        assert legend.tokens == ("heat-low", "heat-high")

    def test_low_and_high_investment_entities_scale_to_opposite_ends(self) -> None:
        definition = _CATALOGS.viewpoints.get("resource-map")
        assert definition is not None
        store = Store(entities={"ENT@low": _resource("ENT@low", 1), "ENT@high": _resource("ENT@high", 5)})
        projection = project_repository(definition, read_access=store, registries=_REGISTRIES)
        by_id = {item.item_id: item for item in projection.items}
        low_style = by_id["ENT@low"].style["node_color"]
        high_style = by_id["ENT@high"].style["node_color"]
        assert isinstance(low_style, ScaleStyleValue)
        assert isinstance(high_style, ScaleStyleValue)
        assert low_style.position == 0.0
        assert high_style.position == 1.0


class TestHeatMapAbsenceDegradesGracefully:
    def test_entity_missing_the_attribute_falls_back_to_default_style_not_a_crash(self) -> None:
        definition = _CATALOGS.viewpoints.get("resource-map")
        assert definition is not None
        store = Store(entities={"ENT@bare": _resource("ENT@bare", None)})
        projection = project_repository(definition, read_access=store, registries=_REGISTRIES)
        item = projection.items[0]
        assert "node_color" not in item.style or item.style.get("node_color") is None

    def test_repo_without_the_profile_attribute_declared_is_a_drift_warning_not_an_error(self) -> None:
        definition = _CATALOGS.viewpoints.get("resource-map")
        assert definition is not None
        store = Store(entities={"ENT@r1": _resource("ENT@r1", 4)})
        projection = project_repository(definition, read_access=store, registries=_NO_PROFILE_REGISTRIES)
        assert any("investment_level" in warning for warning in projection.warnings)
        item = projection.items[0]
        assert "node_color" not in item.style


def test_fixture_profile_repo_root_helper_is_reusable() -> None:
    """A sanity check that the shared fixture-profile installer this file imports from
    the base library test module still produces a root with both heat-map schemas."""
    root = _repo_root_with_fixture_profiles()
    assert (root / ".arch-repo" / "schemata" / "attributes.capability.schema.json").exists()
    assert (root / ".arch-repo" / "schemata" / "attributes.resource.schema.json").exists()
