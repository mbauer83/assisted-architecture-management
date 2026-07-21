from __future__ import annotations

from src.domain.guidance import (
    GuidanceContextKey,
    GuidanceEntry,
    GuidanceKey,
    GuidanceOverlay,
    guidance_overlay_from_mapping,
)


def _entry(text: str) -> GuidanceEntry:
    return GuidanceEntry(create_when=f"create: {text}", never_create_when=f"never: {text}")


class TestGuidanceOverlayLookup:
    def test_empty_overlay_is_noop(self) -> None:
        overlay = GuidanceOverlay()
        assert overlay.is_empty()
        key = GuidanceKey(module_alias="archimate-4", concept_kind="entity", type_name="stakeholder")
        assert overlay.get(key) is None

    def test_known_key_resolves(self) -> None:
        key = GuidanceKey(module_alias="archimate-4", concept_kind="entity", type_name="stakeholder")
        overlay = GuidanceOverlay({key: _entry("stakeholder")})
        assert not overlay.is_empty()
        assert overlay.get(key) == _entry("stakeholder")

    def test_unknown_key_passes_through_as_none(self) -> None:
        key = GuidanceKey(module_alias="archimate-4", concept_kind="entity", type_name="stakeholder")
        other = GuidanceKey(module_alias="archimate-4", concept_kind="entity", type_name="capability")
        overlay = GuidanceOverlay({key: _entry("stakeholder")})
        assert overlay.get(other) is None


class TestGuidanceKeyShape:
    def test_entity_specialization_key(self) -> None:
        key = GuidanceKey(
            module_alias="archimate-4",
            concept_kind="entity",
            type_name="stakeholder",
            specialization="business-service",
        )
        overlay = GuidanceOverlay({key: _entry("business-service")})
        assert overlay.get(key) == _entry("business-service")
        base_key = GuidanceKey(module_alias="archimate-4", concept_kind="entity", type_name="stakeholder")
        assert overlay.get(base_key) is None

    def test_connection_specialization_key(self) -> None:
        key = GuidanceKey(
            module_alias="archimate-4",
            concept_kind="connection",
            type_name="archimate-flow",
            specialization="money-flow",
        )
        overlay = GuidanceOverlay({key: _entry("money-flow")})
        assert overlay.get(key) == _entry("money-flow")

    def test_entity_and_connection_keys_are_distinct(self) -> None:
        entity_key = GuidanceKey(module_alias="archimate-4", concept_kind="entity", type_name="service")
        connection_key = GuidanceKey(module_alias="archimate-4", concept_kind="connection", type_name="service")
        overlay = GuidanceOverlay({entity_key: _entry("entity-service")})
        assert overlay.get(entity_key) == _entry("entity-service")
        assert overlay.get(connection_key) is None


class TestGuidanceOverlayFromMapping:
    def test_entity_base_guidance(self) -> None:
        data = {
            "guidance_format": 1,
            "meta_ontologies": {
                "archimate-4": {
                    "entity_types": {
                        "stakeholder": {"create_when": "c", "never_create_when": "n"},
                    },
                },
            },
        }
        overlay = guidance_overlay_from_mapping(data)
        key = GuidanceKey(module_alias="archimate-4", concept_kind="entity", type_name="stakeholder")
        assert overlay.get(key) == GuidanceEntry(create_when="c", never_create_when="n")

    def test_entity_specialization_guidance(self) -> None:
        data = {
            "meta_ontologies": {
                "archimate-4": {
                    "entity_types": {
                        "stakeholder": {
                            "create_when": "c",
                            "never_create_when": "n",
                            "specializations": {
                                "business-service": {"create_when": "sc", "never_create_when": "sn"},
                            },
                        },
                    },
                },
            },
        }
        overlay = guidance_overlay_from_mapping(data)
        base_key = GuidanceKey(module_alias="archimate-4", concept_kind="entity", type_name="stakeholder")
        spec_key = GuidanceKey(
            module_alias="archimate-4",
            concept_kind="entity",
            type_name="stakeholder",
            specialization="business-service",
        )
        assert overlay.get(base_key) == GuidanceEntry(create_when="c", never_create_when="n")
        assert overlay.get(spec_key) == GuidanceEntry(create_when="sc", never_create_when="sn")

    def test_connection_specialization_without_base_guidance(self) -> None:
        """Reserved, not-yet-populated connection base guidance (D3) must not create an
        override entry that would blank out the module's own inline text."""
        data = {
            "meta_ontologies": {
                "archimate-4": {
                    "connection_types": {
                        "archimate-flow": {
                            "specializations": {
                                "money-flow": {"create_when": "mc", "never_create_when": "mn"},
                            },
                        },
                    },
                },
            },
        }
        overlay = guidance_overlay_from_mapping(data)
        base_key = GuidanceKey(module_alias="archimate-4", concept_kind="connection", type_name="archimate-flow")
        spec_key = GuidanceKey(
            module_alias="archimate-4",
            concept_kind="connection",
            type_name="archimate-flow",
            specialization="money-flow",
        )
        assert overlay.get(base_key) is None
        assert overlay.get(spec_key) == GuidanceEntry(create_when="mc", never_create_when="mn")

    def test_missing_meta_ontologies_key_returns_empty_overlay(self) -> None:
        assert guidance_overlay_from_mapping({}).is_empty()
        assert guidance_overlay_from_mapping({"meta_ontologies": "not-a-mapping"}).is_empty()

    def test_malformed_entries_are_skipped_not_raised(self) -> None:
        data = {
            "meta_ontologies": {
                "archimate-4": {
                    "entity_types": {
                        "stakeholder": "not-a-mapping",
                        123: {"create_when": "ignored — non-string type name"},
                    },
                    "connection_types": "not-a-mapping",
                },
                "sysml-v2": "not-a-mapping",
            },
        }
        assert guidance_overlay_from_mapping(data).is_empty()


class TestGuidanceOverlayV2Context:
    """v2 broader-level context maps (any non-type-slot top-level key) parse into context
    entries alongside the unchanged type slots. The parser needs no hierarchy — level/node
    validation is the import CLI's --strict job and the runtime cache is already clean."""

    def _doc(self) -> dict:
        return {
            "guidance_format": 2,
            "meta_ontologies": {
                "archimate-4": {
                    "domain": {
                        "motivation": {"context": "Why the architecture is shaped this way."},
                        "strategy": {"context": "The business model, org-independently."},
                    },
                    "entity_types": {
                        "requirement": {"create_when": "cw", "never_create_when": "nw"},
                    },
                },
            },
        }

    def test_context_parsed(self) -> None:
        overlay = guidance_overlay_from_mapping(self._doc())
        key = GuidanceContextKey("archimate-4", "domain", "motivation")
        assert overlay.context_for(key) == "Why the architecture is shaped this way."

    def test_type_slots_still_parse_in_v2(self) -> None:
        overlay = guidance_overlay_from_mapping(self._doc())
        base = GuidanceKey(module_alias="archimate-4", concept_kind="entity", type_name="requirement")
        assert overlay.get(base) == GuidanceEntry(create_when="cw", never_create_when="nw")

    def test_node_without_context_field_produces_no_entry(self) -> None:
        doc = self._doc()
        doc["meta_ontologies"]["archimate-4"]["domain"]["business"] = {"note": "no context key here"}
        overlay = guidance_overlay_from_mapping(doc)
        assert overlay.context_for(GuidanceContextKey("archimate-4", "domain", "business")) is None

    def test_every_context_level_key_is_read(self) -> None:
        overlay = guidance_overlay_from_mapping(self._doc())
        assert overlay.context_for(GuidanceContextKey("archimate-4", "domain", "strategy")) is not None
