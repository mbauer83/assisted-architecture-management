from __future__ import annotations

from src.domain.guidance import GuidanceEntry, GuidanceKey, GuidanceOverlay
from src.ontologies.archimate_4._loader import _PACKAGE_DIR, META_ONTOLOGY_ALIAS, load_archimate_4_module


class TestArchimate4LoaderGuidanceOverlay:
    def test_absent_guidance_param_matches_current_behavior(self) -> None:
        default = load_archimate_4_module(_PACKAGE_DIR)
        explicit_none = load_archimate_4_module(_PACKAGE_DIR, guidance=None)
        assert (
            default.entity_types["stakeholder"].create_when
            == explicit_none.entity_types["stakeholder"].create_when
        )

    def test_empty_overlay_matches_current_behavior(self) -> None:
        default = load_archimate_4_module(_PACKAGE_DIR)
        with_empty_overlay = load_archimate_4_module(_PACKAGE_DIR, guidance=GuidanceOverlay())
        assert (
            default.entity_types["stakeholder"].create_when
            == with_empty_overlay.entity_types["stakeholder"].create_when
        )

    def test_overlay_overrides_one_entity_types_guidance(self) -> None:
        baseline = load_archimate_4_module(_PACKAGE_DIR)
        assert baseline.entity_types["stakeholder"].create_when != "OVERRIDDEN"

        overlay = GuidanceOverlay(
            {
                GuidanceKey(
                    module_alias=META_ONTOLOGY_ALIAS, concept_kind="entity", type_name="stakeholder"
                ): GuidanceEntry(create_when="OVERRIDDEN", never_create_when="OVERRIDDEN-NEVER"),
            }
        )
        overridden = load_archimate_4_module(_PACKAGE_DIR, guidance=overlay)

        assert overridden.entity_types["stakeholder"].create_when == "OVERRIDDEN"
        assert overridden.entity_types["stakeholder"].never_create_when == "OVERRIDDEN-NEVER"
        # unrelated entity types are untouched by the overlay
        assert (
            overridden.entity_types["capability"].create_when
            == baseline.entity_types["capability"].create_when
        )
