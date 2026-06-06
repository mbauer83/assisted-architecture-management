"""Parity tests between connection_rules_snapshot1.yaml and the loaded ontology.

Sentinel cases from PLAN-archimate-next-rule-conformance-and-repository-cleanup.md §3.1:
  - function → service realization: PERMITTED
  - process → service realization: PERMITTED
  - application-component → service realization: PROHIBITED
  - service → application-component realization: PROHIBITED
  - service → application-component serving: PERMITTED
  - system-software → application-component serving: PERMITTED (§3.2 correction)
  - association is symmetric (permitted in both orientations)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.domain.connection_ontology import permissible_connection_types

_FIXTURE_PATH = Path(__file__).parent.parent.parent / "src/ontologies/archimate_next/connection_rules_snapshot1.yaml"


@pytest.fixture(scope="module")
def fixture_data() -> dict:
    return yaml.safe_load(_FIXTURE_PATH.read_text(encoding="utf-8"))


class TestDirectPermissions:
    """Each 'direct' entry in the fixture must be present in the loaded ontology."""

    def test_function_realizes_service(self) -> None:
        assert "archimate-realization" in permissible_connection_types("function", "service")

    def test_process_realizes_service(self) -> None:
        assert "archimate-realization" in permissible_connection_types("process", "service")

    def test_service_serves_application_component(self) -> None:
        assert "archimate-serving" in permissible_connection_types("service", "application-component")

    def test_service_association_application_component(self) -> None:
        assert "archimate-association" in permissible_connection_types("service", "application-component")

    def test_association_is_symmetric(self) -> None:
        # association must appear for either orientation
        assert "archimate-association" in permissible_connection_types("application-component", "service")

    def test_system_software_serves_application_component(self) -> None:
        assert "archimate-serving" in permissible_connection_types("system-software", "application-component")

    def test_technology_node_serves_application_component(self) -> None:
        assert "archimate-serving" in permissible_connection_types("technology-node", "application-component")

    def test_device_serves_application_component(self) -> None:
        assert "archimate-serving" in permissible_connection_types("device", "application-component")


class TestProhibitions:
    """Each 'prohibited' entry in the fixture must be absent from the loaded ontology."""

    def test_application_component_does_not_realize_service(self) -> None:
        allowed = permissible_connection_types("application-component", "service")
        assert "archimate-realization" not in allowed, (
            f"application-component→service realization must be prohibited; found in {allowed}"
        )

    def test_service_does_not_realize_application_component(self) -> None:
        allowed = permissible_connection_types("service", "application-component")
        assert "archimate-realization" not in allowed, (
            f"service→application-component realization must be prohibited; found in {allowed}"
        )


class TestFixtureCompleteness:
    """The fixture file itself is well-formed."""

    def test_fixture_has_direct_and_prohibited_sections(self, fixture_data: dict) -> None:
        assert "direct" in fixture_data
        assert "prohibited" in fixture_data

    def test_direct_entries_have_required_fields(self, fixture_data: dict) -> None:
        for entry in fixture_data.get("direct", []):
            assert "source" in entry
            assert "target" in entry
            assert "connection" in entry
            assert "provenance" in entry

    def test_prohibited_entries_have_required_fields(self, fixture_data: dict) -> None:
        for entry in fixture_data.get("prohibited", []):
            assert "source" in entry
            assert "target" in entry
            assert "connection" in entry

    def test_all_direct_entries_are_permitted(self, fixture_data: dict) -> None:
        for entry in fixture_data.get("direct", []):
            src = entry["source"]
            tgt = entry["target"]
            conn = entry["connection"]
            allowed = permissible_connection_types(src, tgt)
            assert conn in allowed, (
                f"Fixture says '{src} → {tgt} [{conn}]' is direct-permitted "
                f"but ontology disagrees. Allowed: {allowed}"
            )

    def test_all_prohibited_entries_are_absent(self, fixture_data: dict) -> None:
        for entry in fixture_data.get("prohibited", []):
            src = entry["source"]
            tgt = entry["target"]
            conn = entry["connection"]
            allowed = permissible_connection_types(src, tgt)
            assert conn not in allowed, (
                f"Fixture says '{src} → {tgt} [{conn}]' is prohibited "
                f"but ontology permits it. Allowed: {allowed}"
            )
