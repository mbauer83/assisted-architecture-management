"""Tests for the /api/modules registry discovery endpoint."""

from __future__ import annotations

from src.infrastructure.app_bootstrap import build_module_registry
from src.infrastructure.gui.routers.modules import list_modules


class TestModulesRoute:
    def test_returns_list_of_ontology_modules(self) -> None:
        result = list_modules()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_response_shape(self) -> None:
        result = list_modules()
        for entry in result:
            assert "name" in entry
            assert "module_class" in entry
            assert "enabled" in entry
            assert "requires" in entry
            assert "entity_type_count" in entry
            assert "connection_type_count" in entry

    def test_module_class_is_architecture_for_default_modules(self) -> None:
        result = list_modules()
        for entry in result:
            assert entry["module_class"] == "architecture", (
                f"Module {entry['name']!r} has unexpected module_class {entry['module_class']!r}"
            )

    def test_registered_modules_appear_in_response(self) -> None:
        registry = build_module_registry()
        registered_names = set(registry.all_ontologies().keys())
        response_names = {entry["name"] for entry in list_modules()}
        assert registered_names == response_names

    def test_entity_type_count_is_positive_for_real_modules(self) -> None:
        result = list_modules()
        for entry in result:
            assert int(entry["entity_type_count"]) > 0, (  # type: ignore[arg-type]
                f"Module {entry['name']!r} reported zero entity types"
            )
