"""Unit tests for the named-profile registry format, version guard, and merge."""

from __future__ import annotations

import pytest

from src.domain.profile_registry import (
    PROFILE_SCHEMA_VERSION,
    ProfileRegistry,
    ProfileRegistryError,
    merge_profile_registries,
    profile_registry_from_mapping,
)


def _valid_mapping() -> dict[str, object]:
    return {
        "profile_schema": 1,
        "profiles": {
            "supplier-info": {
                "version": 2,
                "attributes": {
                    "Supplier": {"type": "string", "level": "required"},
                    "Rating": {"type": "number"},
                },
            }
        },
    }


def test_valid_registry_loads_with_versions_and_attributes() -> None:
    registry = profile_registry_from_mapping(_valid_mapping(), label="test")
    assert registry.profile_schema == 1
    profile = registry.get("supplier-info")
    assert profile is not None
    assert profile.version == 2
    names = {attr.name: attr for attr in profile.definition.attributes}
    assert names["Supplier"].level == "required"
    assert names["Rating"].type == "number"


def test_absent_profiles_key_is_a_valid_empty_registry() -> None:
    registry = profile_registry_from_mapping({"profile_schema": 1}, label="test")
    assert dict(registry.profiles) == {}


def test_empty_registry_is_the_no_named_profiles_state() -> None:
    empty = ProfileRegistry.empty()
    assert empty.profile_schema == PROFILE_SCHEMA_VERSION
    assert empty.get("anything") is None


def test_unknown_profile_schema_is_rejected() -> None:
    with pytest.raises(ProfileRegistryError, match="unsupported profile_schema 99"):
        profile_registry_from_mapping({"profile_schema": 99, "profiles": {}}, label="bad.yaml")


def test_missing_profile_schema_is_rejected() -> None:
    with pytest.raises(ProfileRegistryError, match="'profile_schema' is required"):
        profile_registry_from_mapping({"profiles": {}}, label="bad.yaml")


def test_non_integer_profile_schema_is_rejected() -> None:
    with pytest.raises(ProfileRegistryError, match="profile_schema must be an integer"):
        profile_registry_from_mapping({"profile_schema": "1"}, label="bad.yaml")
    # A bool is not an acceptable integer version.
    with pytest.raises(ProfileRegistryError, match="profile_schema must be an integer"):
        profile_registry_from_mapping({"profile_schema": True}, label="bad.yaml")


def test_profile_missing_version_is_rejected() -> None:
    raw = {"profile_schema": 1, "profiles": {"p": {"attributes": {}}}}
    with pytest.raises(ProfileRegistryError, match="profile 'p' is missing 'version'"):
        profile_registry_from_mapping(raw, label="bad.yaml")


def test_non_mapping_registry_is_rejected() -> None:
    with pytest.raises(ProfileRegistryError, match="registry must be a mapping"):
        profile_registry_from_mapping(["not", "a", "mapping"], label="bad.yaml")


def test_error_label_names_the_source() -> None:
    with pytest.raises(ProfileRegistryError) as excinfo:
        profile_registry_from_mapping({}, label="/repo/.arch-repo/profiles.yaml")
    assert str(excinfo.value).startswith("/repo/.arch-repo/profiles.yaml:")
    assert excinfo.value.label == "/repo/.arch-repo/profiles.yaml"


def test_merge_unions_disjoint_registries() -> None:
    a = profile_registry_from_mapping({"profile_schema": 1, "profiles": {"a": {"version": 1}}}, label="a")
    b = profile_registry_from_mapping({"profile_schema": 1, "profiles": {"b": {"version": 1}}}, label="b")
    merged = merge_profile_registries([a, b])
    assert set(merged.profiles) == {"a", "b"}


def test_merge_rejects_a_duplicate_name_across_registries() -> None:
    a = profile_registry_from_mapping({"profile_schema": 1, "profiles": {"dup": {"version": 1}}}, label="a")
    b = profile_registry_from_mapping({"profile_schema": 1, "profiles": {"dup": {"version": 2}}}, label="b")
    with pytest.raises(ProfileRegistryError, match="'dup' is defined more than once"):
        merge_profile_registries([a, b])
