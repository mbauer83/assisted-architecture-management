from __future__ import annotations

import pytest

from src.domain.guidance import GuidanceEntry, GuidanceKey, GuidanceOverlay
from src.domain.specializations import SpecializationCatalog, specialization_catalog_from_mapping
from src.ontologies.archimate_4._loader import _PACKAGE_DIR, META_ONTOLOGY_ALIAS, load_archimate_4_module


class TestArchimate4SpecializationLibrary:
    def test_module_loads_informative_entity_and_connection_library(self) -> None:
        module = load_archimate_4_module(_PACKAGE_DIR)
        catalog = module.specialization_catalog

        business_service = catalog.get("entity", "service", "business-service", module_alias=META_ONTOLOGY_ALIAS)
        assert business_service is not None
        assert business_service.name == "Business Service"
        assert business_service.create_when == ""
        assert business_service.never_create_when == ""

        business_collaboration = catalog.get(
            "entity", "grouping", "business-collaboration", module_alias=META_ONTOLOGY_ALIAS
        )
        assert business_collaboration is not None
        assert business_collaboration.name == "Business Collaboration"

        money_flow = catalog.get("connection", "archimate-flow", "money-flow", module_alias=META_ONTOLOGY_ALIAS)
        assert money_flow is not None
        assert money_flow.name == "Money Flow"

        assignment_specs = {
            spec.slug
            for spec in catalog.for_type(
                "connection",
                "archimate-assignment",
                module_alias=META_ONTOLOGY_ALIAS,
            )
        }
        assert {"responsibility-assignment", "behavior-assignment"} <= assignment_specs

    def test_guidance_overlay_applies_to_entity_and_connection_specializations(self) -> None:
        overlay = GuidanceOverlay(
            {
                GuidanceKey(
                    module_alias=META_ONTOLOGY_ALIAS,
                    concept_kind="entity",
                    type_name="service",
                    specialization="business-service",
                ): GuidanceEntry(create_when="entity-create", never_create_when="entity-never"),
                GuidanceKey(
                    module_alias=META_ONTOLOGY_ALIAS,
                    concept_kind="connection",
                    type_name="archimate-flow",
                    specialization="money-flow",
                ): GuidanceEntry(create_when="connection-create", never_create_when="connection-never"),
            }
        )

        module = load_archimate_4_module(_PACKAGE_DIR, guidance=overlay)
        entity = module.specialization_catalog.get(
            "entity", "service", "business-service", module_alias=META_ONTOLOGY_ALIAS
        )
        connection = module.specialization_catalog.get(
            "connection", "archimate-flow", "money-flow", module_alias=META_ONTOLOGY_ALIAS
        )

        assert entity is not None
        assert entity.create_when == "entity-create"
        assert entity.never_create_when == "entity-never"
        assert connection is not None
        assert connection.create_when == "connection-create"
        assert connection.never_create_when == "connection-never"

    def test_repo_specialization_duplicate_of_module_library_is_rejected(self) -> None:
        repo_catalog = specialization_catalog_from_mapping(
            {
                "specializations": {
                    "entity": {
                        "service": [
                            {
                                "slug": "business-service",
                                "name": "Custom Business Service",
                            }
                        ]
                    }
                }
            },
            module_alias=META_ONTOLOGY_ALIAS,
        )

        with pytest.raises(ValueError, match="Duplicate specialization"):
            load_archimate_4_module(_PACKAGE_DIR, specializations=repo_catalog)

    def test_unknown_parent_type_is_rejected(self) -> None:
        repo_catalog = SpecializationCatalog(
            specialization_catalog_from_mapping(
                {
                    "specializations": {
                        "entity": {
                            "not-a-parent": [
                                {
                                    "slug": "custom",
                                    "name": "Custom",
                                }
                            ]
                        }
                    }
                },
                module_alias=META_ONTOLOGY_ALIAS,
            ).entries
        )

        with pytest.raises(ValueError, match="Unknown parent entity type"):
            load_archimate_4_module(_PACKAGE_DIR, specializations=repo_catalog)
