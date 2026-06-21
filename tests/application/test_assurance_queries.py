"""Unit tests for pure assurance query use cases (no store/IO)."""

from __future__ import annotations

from src.application.assurance_queries import aibom_coverage


def test_aibom_coverage_all_anchored() -> None:
    components = [{"name": "a", "arch_entity_id": "APP@1"}]
    report = aibom_coverage(components, anchors=[{"arch_entity_id": "APP@1"}])
    assert report["total_bom_components"] == 1
    assert report["unanchored_components"] == 0
    assert report["unanchored"] == []
    assert "All BOM components" in report["summary"]


def test_aibom_coverage_flags_unanchored() -> None:
    components = [
        {"name": "anchored", "arch_entity_id": "APP@1"},
        {"name": "orphan", "arch_entity_id": ""},
        {"name": "missing-key"},
    ]
    report = aibom_coverage(components, anchors=[{"arch_entity_id": "APP@1"}])
    assert report["unanchored_components"] == 2
    assert {c["name"] for c in report["unanchored"]} == {"orphan", "missing-key"}
    assert report["anchored_entity_ids"] == ["APP@1"]


def test_aibom_coverage_truncates_unanchored_page() -> None:
    components = [{"name": f"c{i}"} for i in range(60)]
    report = aibom_coverage(components, anchors=[])
    assert report["unanchored_components"] == 60
    assert report["unanchored_truncated"] is True
    assert len(report["unanchored"]) == 50


def test_aibom_coverage_dedupes_anchor_entity_ids() -> None:
    anchors = [{"arch_entity_id": "APP@1"}, {"arch_entity_id": "APP@1"}, {"arch_entity_id": "APP@2"}]
    report = aibom_coverage([], anchors=anchors)
    assert report["anchored_entity_ids"] == ["APP@1", "APP@2"]
    assert report["anchor_mappings"] == 3
