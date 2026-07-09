"""Tests for the assurance ontology module loading and types."""

from __future__ import annotations

import pytest

from src.ontologies.assurance import module as assurance_module


def test_module_name_and_class() -> None:
    assert assurance_module.name == "assurance"
    assert assurance_module.module_class == "assurance"


def test_module_requires_confidential_store() -> None:
    requires = list(getattr(assurance_module, "requires", []))
    assert "confidential_store" in requires


def test_core_entity_types_present() -> None:
    types = assurance_module.entity_types
    for expected in ["loss", "hazard", "control-structure-node", "control-action",
                     "unsafe-control-action", "loss-scenario", "assurance-constraint"]:
        assert expected in types, f"Expected entity type '{expected}' in assurance module"


def test_optional_entity_types_present() -> None:
    types = assurance_module.entity_types
    for expected in ["risk", "incident", "corrective-action", "obligation"]:
        assert expected in types, f"Expected entity type '{expected}' in assurance module"


def test_entity_prefixes() -> None:
    types = assurance_module.entity_types
    assert types["loss"].prefix == "LSS"
    assert types["hazard"].prefix == "HAZ"
    assert types["control-structure-node"].prefix == "CSN"
    assert types["control-action"].prefix == "CAC"
    assert types["unsafe-control-action"].prefix == "UCA"
    assert types["assurance-constraint"].prefix == "ACN"


def test_core_connection_types_present() -> None:
    conns = assurance_module.connection_types
    for expected in [
        "issues", "acts-on", "feedback", "concerns", "by-controller",
        "violates", "leads-to", "explains", "derives",
        "refines", "accountable-to", "evidenced-by",
        "assesses", "treated-by", "complies-with", "binds-to",
    ]:
        assert expected in conns, f"Expected connection type '{expected}' in assurance module"


def test_attribute_profiles_present() -> None:
    profiles = assurance_module.attribute_profiles
    assert "hazard" in profiles
    assert "assurance-constraint" in profiles
    assert "unsafe-control-action" in profiles
    assert "control-structure-node" in profiles


def test_concern_class_in_hazard_profile() -> None:
    profile = assurance_module.attribute_profiles["hazard"]
    props = profile.get("properties", {})
    assert isinstance(props, dict)
    assert "concern_class" in props
    enum = props["concern_class"].get("enum", [])  # type: ignore[union-attr]
    assert "safety" in enum
    assert "security" in enum


def test_disposition_in_constraint_profile() -> None:
    profile = assurance_module.attribute_profiles["assurance-constraint"]
    props = profile.get("properties", {})
    assert isinstance(props, dict)
    disp = props.get("disposition", {})
    assert isinstance(disp, dict)
    enum = disp.get("enum", [])
    assert "eliminated" in enum
    assert "accepted" in enum


def test_element_classes_declared() -> None:
    classes = assurance_module.element_classes
    assert "assurance-element" in classes
    assert "loss-element" in classes
    assert "hazard-element" in classes
    assert "constraint-element" in classes


def test_entity_hierarchy_includes_assurance() -> None:
    types = assurance_module.entity_types
    for name, info in types.items():
        assert "assurance" in info.hierarchy, f"{name}: hierarchy must include 'assurance'"


def test_sprite_for_returns_none() -> None:
    assert assurance_module.sprite_for("loss") is None


def test_module_not_registered_without_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assurance module is skipped when confidential_store is not in registered_names."""
    from src.domain.module_filter import is_module_enabled

    assert not is_module_enabled(assurance_module, {}, set())
    assert is_module_enabled(assurance_module, {}, {"confidential_store"})


class TestAssuranceLoaderGuidanceOverlay:
    def test_absent_guidance_matches_current_behavior(self) -> None:
        from src.ontologies.assurance._loader import _PACKAGE_DIR, load_assurance_module

        default = load_assurance_module(_PACKAGE_DIR)
        explicit_none = load_assurance_module(_PACKAGE_DIR, guidance=None)
        assert default.entity_types["hazard"].create_when == explicit_none.entity_types["hazard"].create_when

    def test_overlay_overrides_one_entity_types_guidance(self) -> None:
        from src.domain.guidance import GuidanceEntry, GuidanceKey, GuidanceOverlay
        from src.ontologies.assurance._loader import _PACKAGE_DIR, META_ONTOLOGY_ALIAS, load_assurance_module

        overlay = GuidanceOverlay(
            {
                GuidanceKey(
                    module_alias=META_ONTOLOGY_ALIAS, concept_kind="entity", type_name="hazard"
                ): GuidanceEntry(create_when="OVERRIDDEN", never_create_when="OVERRIDDEN-NEVER"),
            }
        )
        overridden = load_assurance_module(_PACKAGE_DIR, guidance=overlay)

        assert overridden.entity_types["hazard"].create_when == "OVERRIDDEN"
        assert overridden.entity_types["hazard"].never_create_when == "OVERRIDDEN-NEVER"
