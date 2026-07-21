"""The standard guidance-hierarchy derivation over the real archimate-4 module (and the
override hook). The derived tree must be structurally sound (no validation errors) and place
each entity type under its declared domain with specializations qualified per type.
"""

from __future__ import annotations

from src.domain.guidance_hierarchy import GuidanceHierarchy, GuidanceLevel, GuidanceNode
from src.domain.guidance_hierarchy_source import (
    DOMAIN_LEVEL,
    ENTITY_TYPE_LEVEL,
    SPECIALIZATION_LEVEL,
    derive_standard_hierarchy,
    resolve_guidance_hierarchy,
    specialization_node_id,
)


def _archimate_module():
    from src.infrastructure.app_bootstrap import build_module_registry, resolve_meta_ontology_module

    module = resolve_meta_ontology_module("archimate-4", build_module_registry())
    assert module is not None
    return module


class TestStandardDerivation:
    def test_derived_archimate_tree_is_sound(self) -> None:
        h = derive_standard_hierarchy(_archimate_module())
        assert h.validation_errors() == ()

    def test_levels_are_domain_type_specialization(self) -> None:
        h = derive_standard_hierarchy(_archimate_module())
        assert [level.id for level in h.ordered_levels()] == [
            DOMAIN_LEVEL,
            ENTITY_TYPE_LEVEL,
            SPECIALIZATION_LEVEL,
        ]

    def test_requirement_sits_under_motivation_domain(self) -> None:
        h = derive_standard_hierarchy(_archimate_module())
        chain = h.ancestry(ENTITY_TYPE_LEVEL, "requirement")
        assert [(n.level_id, n.node_id) for n in chain] == [
            (DOMAIN_LEVEL, "motivation"),
            (ENTITY_TYPE_LEVEL, "requirement"),
        ]

    def test_specialization_ancestry_is_domain_type_spec(self) -> None:
        h = derive_standard_hierarchy(_archimate_module())
        node = specialization_node_id("requirement", "constraint")
        chain = h.ancestry(SPECIALIZATION_LEVEL, node)
        assert [(n.level_id, n.node_id) for n in chain] == [
            (DOMAIN_LEVEL, "motivation"),
            (ENTITY_TYPE_LEVEL, "requirement"),
            (SPECIALIZATION_LEVEL, node),
        ]

    def test_domain_nodes_are_deduplicated(self) -> None:
        h = derive_standard_hierarchy(_archimate_module())
        domain_ids = [n.node_id for n in h.nodes if n.level_id == DOMAIN_LEVEL]
        assert len(domain_ids) == len(set(domain_ids))
        assert "motivation" in domain_ids


class TestOverrideHook:
    def test_module_provided_hierarchy_is_preferred(self) -> None:
        custom = GuidanceHierarchy(
            levels=(GuidanceLevel("concern_class", "Concern class", 0),),
            nodes=(GuidanceNode("concern_class", "safety"),),
        )

        class _Fake:
            def guidance_hierarchy(self) -> GuidanceHierarchy:
                return custom

        assert resolve_guidance_hierarchy(_Fake()) is custom  # type: ignore[arg-type]

    def test_falls_back_to_standard_when_absent(self) -> None:
        h = resolve_guidance_hierarchy(_archimate_module())
        assert h.is_declared_level(DOMAIN_LEVEL)
