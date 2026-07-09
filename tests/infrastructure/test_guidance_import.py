from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.module_registry import ModuleRegistry
from src.infrastructure.app_bootstrap import build_module_registry
from src.infrastructure.guidance_import import (
    GuidanceImportError,
    fetch_source,
    filter_alias_document,
    select_aliases,
    validate_schema,
)


class TestValidateSchema:
    def test_accepts_valid_document(self) -> None:
        data = {"guidance_format": 1, "meta_ontologies": {"archimate-4": {}}}
        assert validate_schema(data) == data

    def test_rejects_non_mapping(self) -> None:
        with pytest.raises(GuidanceImportError, match="mapping"):
            validate_schema(["not", "a", "mapping"])

    def test_rejects_unsupported_format(self) -> None:
        with pytest.raises(GuidanceImportError, match="guidance_format"):
            validate_schema({"guidance_format": 2, "meta_ontologies": {}})

    def test_rejects_missing_meta_ontologies(self) -> None:
        with pytest.raises(GuidanceImportError, match="meta_ontologies"):
            validate_schema({"guidance_format": 1})


class TestSelectAliases:
    def test_no_module_returns_all_aliases(self) -> None:
        data = {"meta_ontologies": {"archimate-4": {"a": 1}, "sysml-v2": {"b": 2}}}
        assert select_aliases(data, None) == {"archimate-4": {"a": 1}, "sysml-v2": {"b": 2}}

    def test_module_filters_to_one_alias(self) -> None:
        data = {"meta_ontologies": {"archimate-4": {"a": 1}, "sysml-v2": {"b": 2}}}
        assert select_aliases(data, "archimate-4") == {"archimate-4": {"a": 1}}

    def test_unknown_module_raises(self) -> None:
        data = {"meta_ontologies": {"archimate-4": {}}}
        with pytest.raises(GuidanceImportError, match="not present"):
            select_aliases(data, "no-such-alias")


class TestFilterAliasDocument:
    @pytest.fixture
    def registry(self) -> ModuleRegistry:
        return build_module_registry()

    def test_known_entity_type_matched(self, registry: ModuleRegistry) -> None:
        alias_data = {"entity_types": {"stakeholder": {"create_when": "c", "never_create_when": "n"}}}
        summary = filter_alias_document("archimate-4", alias_data, registry, strict=False)
        assert summary.matched_keys == ("entity_types.stakeholder",)
        assert summary.unmatched_keys == ()
        assert summary.filtered_document["meta_ontologies"]["archimate-4"]["entity_types"]["stakeholder"][
            "create_when"
        ] == "c"

    def test_unknown_entity_type_listed_and_dropped_when_not_strict(self, registry: ModuleRegistry) -> None:
        alias_data = {"entity_types": {"not-a-real-type": {"create_when": "c"}}}
        summary = filter_alias_document("archimate-4", alias_data, registry, strict=False)
        assert summary.unmatched_keys == ("entity_types.not-a-real-type",)
        assert "entity_types" not in summary.filtered_document["meta_ontologies"]["archimate-4"]

    def test_unknown_entity_type_raises_when_strict(self, registry: ModuleRegistry) -> None:
        alias_data = {"entity_types": {"not-a-real-type": {"create_when": "c"}}}
        with pytest.raises(GuidanceImportError, match="not-a-real-type"):
            filter_alias_document("archimate-4", alias_data, registry, strict=True)

    def test_unknown_module_alias_raises(self, registry: ModuleRegistry) -> None:
        with pytest.raises(GuidanceImportError, match="no-such-alias"):
            filter_alias_document("no-such-alias", {}, registry, strict=False)

    def test_non_mapping_alias_data_raises(self, registry: ModuleRegistry) -> None:
        with pytest.raises(GuidanceImportError, match="mapping"):
            filter_alias_document("archimate-4", "not-a-mapping", registry, strict=False)

    def test_connection_types_section_validated_too(self, registry: ModuleRegistry) -> None:
        alias_data = {"connection_types": {"not-a-real-connection": {}}}
        summary = filter_alias_document("archimate-4", alias_data, registry, strict=False)
        assert summary.unmatched_keys == ("connection_types.not-a-real-connection",)

    def test_known_specialization_slug_matched(self, registry: ModuleRegistry) -> None:
        alias_data = {
            "entity_types": {
                "service": {"specializations": {"business-service": {"create_when": "c", "never_create_when": "n"}}}
            }
        }
        summary = filter_alias_document("archimate-4", alias_data, registry, strict=False)
        assert summary.matched_keys == (
            "entity_types.service",
            "entity_types.service.specializations.business-service",
        )
        assert summary.unmatched_keys == ()
        filtered_service = summary.filtered_document["meta_ontologies"]["archimate-4"]["entity_types"]["service"]
        assert filtered_service["specializations"]["business-service"]["create_when"] == "c"

    def test_unknown_specialization_slug_listed_and_dropped_when_not_strict(self, registry: ModuleRegistry) -> None:
        alias_data = {"entity_types": {"service": {"specializations": {"not-a-real-slug": {"create_when": "c"}}}}}
        summary = filter_alias_document("archimate-4", alias_data, registry, strict=False)
        assert summary.unmatched_keys == ("entity_types.service.specializations.not-a-real-slug",)
        filtered_service = summary.filtered_document["meta_ontologies"]["archimate-4"]["entity_types"]["service"]
        assert "specializations" not in filtered_service

    def test_unknown_specialization_slug_raises_when_strict(self, registry: ModuleRegistry) -> None:
        alias_data = {"entity_types": {"service": {"specializations": {"not-a-real-slug": {"create_when": "c"}}}}}
        with pytest.raises(GuidanceImportError, match="not-a-real-slug"):
            filter_alias_document("archimate-4", alias_data, registry, strict=True)

    def test_specialization_slug_unmatched_for_module_without_catalog(self) -> None:
        """sysml-v2 carries an empty SpecializationCatalog, so any specialization slug for
        one of its types is unknown."""
        complete_registry = build_module_registry(complete_vocabulary=True)
        alias_data = {"entity_types": {"part-definition": {"specializations": {"anything": {"create_when": "c"}}}}}
        summary = filter_alias_document("sysml-v2", alias_data, complete_registry, strict=False)
        assert summary.unmatched_keys == ("entity_types.part-definition.specializations.anything",)


class TestFetchSource:
    def test_reads_local_file(self, tmp_path: Path) -> None:
        source = tmp_path / "guidance.yaml"
        source.write_text("hello", encoding="utf-8")
        assert fetch_source(str(source), allow_http=False) == b"hello"

    def test_missing_local_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(GuidanceImportError, match="not found"):
            fetch_source(str(tmp_path / "missing.yaml"), allow_http=False)

    def test_oversize_local_file_raises(self, tmp_path: Path) -> None:
        from src.infrastructure.guidance_import import _MAX_SOURCE_BYTES

        source = tmp_path / "big.yaml"
        source.write_bytes(b"x" * (_MAX_SOURCE_BYTES + 1))
        with pytest.raises(GuidanceImportError, match="size cap"):
            fetch_source(str(source), allow_http=False)

    def test_plain_http_rejected_by_default(self) -> None:
        with pytest.raises(GuidanceImportError, match="allow-http"):
            fetch_source("http://example.invalid/guidance.yaml", allow_http=False)
