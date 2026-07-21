"""Composition of layered guidance context along a concept's ancestry (broadest first),
including the type→specialization bridge and the skip-empty-layers behavior."""

from __future__ import annotations

from src.application.guidance_composition import compose_context, compose_type_context
from src.domain.guidance import GuidanceContextKey, GuidanceOverlay
from src.domain.guidance_hierarchy import GuidanceHierarchy, GuidanceLevel, GuidanceNode
from src.domain.guidance_hierarchy_source import specialization_node_id


def _hierarchy() -> GuidanceHierarchy:
    return GuidanceHierarchy(
        levels=(
            GuidanceLevel("domain", "Domain", 0),
            GuidanceLevel("entity_type", "Entity type", 1),
            GuidanceLevel("specialization", "Specialization", 2),
        ),
        nodes=(
            GuidanceNode("domain", "motivation"),
            GuidanceNode("entity_type", "requirement", parent_node_id="motivation"),
            GuidanceNode(
                "specialization",
                specialization_node_id("requirement", "constraint"),
                parent_node_id="requirement",
            ),
        ),
    )


def _overlay(**context: str) -> GuidanceOverlay:
    entries = {
        GuidanceContextKey("archimate-4", level_node.split("/")[0], level_node.split("/")[1]): text
        for level_node, text in context.items()
    }
    return GuidanceOverlay(context_entries=entries)


class TestComposeContext:
    def test_type_gets_domain_context(self) -> None:
        overlay = _overlay(**{"domain/motivation": "WHY the architecture is shaped this way."})
        chain = compose_type_context(
            module_alias="archimate-4", hierarchy=_hierarchy(), overlay=overlay, type_name="requirement"
        )
        assert [(c.level_id, c.node_id, c.text) for c in chain] == [
            ("domain", "motivation", "WHY the architecture is shaped this way.")
        ]

    def test_specialization_composes_broadest_first(self) -> None:
        overlay = _overlay(
            **{
                "domain/motivation": "domain context",
                f"specialization/{specialization_node_id('requirement', 'constraint')}": "spec context",
            }
        )
        chain = compose_type_context(
            module_alias="archimate-4",
            hierarchy=_hierarchy(),
            overlay=overlay,
            type_name="requirement",
            specialization="constraint",
        )
        assert [c.text for c in chain] == ["domain context", "spec context"]

    def test_layers_without_context_are_skipped(self) -> None:
        overlay = _overlay()  # no context anywhere
        chain = compose_type_context(
            module_alias="archimate-4", hierarchy=_hierarchy(), overlay=overlay, type_name="requirement"
        )
        assert chain == ()

    def test_unknown_node_yields_empty_chain(self) -> None:
        overlay = _overlay(**{"domain/motivation": "x"})
        chain = compose_context(
            module_alias="archimate-4",
            hierarchy=_hierarchy(),
            overlay=overlay,
            leaf_level_id="entity_type",
            leaf_node_id="ghost",
        )
        assert chain == ()

    def test_other_module_alias_does_not_match(self) -> None:
        overlay = _overlay(**{"domain/motivation": "x"})
        chain = compose_type_context(
            module_alias="sysml-v2", hierarchy=_hierarchy(), overlay=overlay, type_name="requirement"
        )
        assert chain == ()
