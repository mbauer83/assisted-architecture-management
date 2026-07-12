"""Tests for attribute profiles (D13): compilation to JSON Schema fragments, and
deterministic multi-fragment merge (conflict/defaults). A profile is one-to-one with its
specialization (inline attributes or the dedicated attachment file) — there is no separate,
reusable profile registry to parse here."""

from __future__ import annotations

from src.domain.profiles import (
    ProfileAttribute,
    ProfileDefinition,
    compile_profile_schema,
    merge_property_schemas,
    profile_from_inline_attributes,
)


class TestCompileProfileSchema:
    def test_required_and_recommended_split(self) -> None:
        profile = ProfileDefinition(
            slug="p",
            name="P",
            attributes=(
                ProfileAttribute(name="a", type="string", level="required"),
                ProfileAttribute(name="b", type="integer", level="recommended", default=1),
                ProfileAttribute(name="c", type="boolean", level="optional"),
            ),
        )
        schema = compile_profile_schema(profile)
        assert schema["required"] == ["a"]
        assert schema["x-recommended"] == ["b"]
        assert schema["properties"]["b"]["default"] == 1
        assert "c" not in schema.get("required", [])
        assert "c" not in schema.get("x-recommended", [])

    def test_inline_attributes_compile_to_anonymous_profile(self) -> None:
        inline = profile_from_inline_attributes(
            "business-service", {"criticality": {"type": "string", "level": "required"}}
        )
        schema = compile_profile_schema(inline)
        assert schema["properties"]["criticality"]["type"] == "string"
        assert schema["required"] == ["criticality"]


class TestMergePropertySchemas:
    def test_merges_properties_across_fragments(self) -> None:
        base = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
        spec = {"type": "object", "properties": {"b": {"type": "integer"}}, "x-recommended": ["b"]}
        merged, conflicts = merge_property_schemas([base, spec])
        assert conflicts == []
        assert set(merged["properties"]) == {"a", "b"}
        assert merged["required"] == ["a"]
        assert merged["x-recommended"] == ["b"]

    def test_incompatible_type_redefinition_is_a_conflict(self) -> None:
        base = {"type": "object", "properties": {"a": {"type": "string"}}}
        spec = {"type": "object", "properties": {"a": {"type": "integer"}}}
        merged, conflicts = merge_property_schemas([base, spec])
        assert len(conflicts) == 1
        assert "a" in conflicts[0]
        # The conflicting redefinition is dropped; the earlier definition survives.
        assert merged["properties"]["a"]["type"] == "string"

    def test_defaults_are_last_writer_wins(self) -> None:
        base = {"type": "object", "properties": {"a": {"type": "string", "default": "x"}}}
        spec = {"type": "object", "properties": {"a": {"type": "string", "default": "y"}}}
        merged, conflicts = merge_property_schemas([base, spec])
        assert conflicts == []
        assert merged["properties"]["a"]["default"] == "y"

    def test_required_never_also_recommended(self) -> None:
        base = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
        spec = {"type": "object", "properties": {"a": {"type": "string"}}, "x-recommended": ["a"]}
        merged, _ = merge_property_schemas([base, spec])
        assert merged["required"] == ["a"]
        assert "x-recommended" not in merged

    def test_empty_input_yields_empty_object_schema(self) -> None:
        merged, conflicts = merge_property_schemas([])
        assert merged == {"type": "object", "properties": {}}
        assert conflicts == []
