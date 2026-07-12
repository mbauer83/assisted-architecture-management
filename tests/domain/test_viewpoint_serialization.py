"""Round-trip tests: a definition parsed from YAML serializes back to the same mapping
shape, and vice versa — the primitive any future authoring surface (GUI or MCP tool) reuses
to persist edits."""

from __future__ import annotations

from src.domain.viewpoint_parsing import viewpoint_catalog_from_mapping
from src.domain.viewpoint_serialization import viewpoint_catalog_to_mapping, viewpoint_definition_to_mapping

_FULL_DEFINITION_MAPPING = {
    "slug": "filtered",
    "version": 4,
    "name": "Filtered",
    "description": "A description.",
    "rationale": "A rationale.",
    "purpose": ["deciding", "designing"],
    "content": "coherence",
    "stakeholders": ["enterprise-architects"],
    "concerns": ["why"],
    "scope": {"entity_types": ["driver", "goal"]},
    "representation_types": ["archimate-motivation"],
    "derivation_defaults": {"depth": 2},
    "query": {
        "query_schema": 2,
        "entity_criteria": {
            "kind": "group",
            "conjunction": "and",
            "children": [
                {"kind": "condition", "attribute": "type", "comparator": "eq", "value": "goal"},
                {
                    "kind": "condition",
                    "attribute": "specialization",
                    "comparator": "eq",
                    "value": "business-service",
                    "negate": True,
                },
            ],
        },
        "include_connected": [
            {
                "direction": "outgoing",
                "connection_criteria": {
                    "kind": "group",
                    "conjunction": "and",
                    "children": [
                        {"kind": "condition", "attribute": "type", "comparator": "eq", "value": "archimate-serving"}
                    ],
                },
            }
        ],
        "connections": {
            "criteria": {
                "kind": "group",
                "conjunction": "and",
                "children": [
                    {"kind": "condition", "attribute": "type", "comparator": "eq", "value": "archimate-serving"}
                ],
            }
        },
        "repo_scope": "engagement",
    },
    "presentation": {
        "representation": "table",
        "display_options": {"columns": True},
        "group_by": "type",
        "columns": [{"label": "Name", "source": "name"}],
        "styling_rules": [{"capability": "row_grouping", "mode": "match", "applies_to": ["goal"], "value": "token-a"}],
        "default_style": {"row_grouping": "token-b"},
    },
}


def test_definition_round_trips_through_parse_and_serialize() -> None:
    catalog = viewpoint_catalog_from_mapping({"viewpoints": [_FULL_DEFINITION_MAPPING]})
    definition = catalog.get("filtered")
    assert definition is not None

    reserialized = viewpoint_definition_to_mapping(definition)

    assert reserialized["slug"] == "filtered"
    assert reserialized["version"] == 4
    assert reserialized["purpose"] == ["deciding", "designing"]
    assert reserialized["content"] == "coherence"
    assert reserialized["scope"]["entity_types"] == ["driver", "goal"]
    assert reserialized["query"]["entity_criteria"]["children"][1]["negate"] is True
    assert reserialized["presentation"]["representation"] == "table"
    assert reserialized["presentation"]["styling_rules"][0]["value"] == "token-a"

    reparsed = viewpoint_catalog_from_mapping({"viewpoints": [reserialized]}).get("filtered")
    assert reparsed == definition


def test_catalog_to_mapping_serializes_every_entry() -> None:
    catalog = viewpoint_catalog_from_mapping(
        {"viewpoints": [{"slug": "a", "version": 1, "name": "A"}, {"slug": "b", "version": 1, "name": "B"}]}
    )
    mapping = viewpoint_catalog_to_mapping(catalog)
    assert [entry["slug"] for entry in mapping["viewpoints"]] == ["a", "b"]


def test_minimal_definition_round_trips() -> None:
    catalog = viewpoint_catalog_from_mapping({"viewpoints": [{"slug": "bare", "version": 1, "name": "Bare"}]})
    definition = catalog.get("bare")
    assert definition is not None
    reserialized = viewpoint_definition_to_mapping(definition)
    assert reserialized == {
        "slug": "bare",
        "version": 1,
        "name": "Bare",
        "purpose": "informing",
        "content": "overview",
    }


def test_defaults_omitted_and_negate_only_when_true() -> None:
    catalog = viewpoint_catalog_from_mapping(
        {
            "viewpoints": [
                {
                    "slug": "simple",
                    "version": 1,
                    "name": "Simple",
                    "query": {
                        "query_schema": 2,
                        "entity_criteria": {
                            "kind": "group",
                            "conjunction": "and",
                            "children": [
                                {"kind": "condition", "attribute": "type", "comparator": "eq", "value": "goal"}
                            ],
                        },
                    },
                }
            ]
        }
    )
    definition = catalog.get("simple")
    assert definition is not None
    condition = viewpoint_definition_to_mapping(definition)["query"]["entity_criteria"]["children"][0]
    assert "negate" not in condition
    assert "value" in condition
