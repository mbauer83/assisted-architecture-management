"""Unit tests for the named-profile registry format, version guard, and merge."""

from __future__ import annotations

import pytest

from src.domain.profile_registry import (
    PROFILE_SCHEMA_VERSION,
    ProfileRegistry,
    ProfileRegistryError,
    classify_profile_conflicts,
    merge_profile_registries,
    profile_registry_from_mapping,
)
from src.domain.profiles import merge_property_schemas


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


# --- WU-P4: conflict classification -----------------------------------------------------

_REGISTRY = profile_registry_from_mapping(
    {"profile_schema": 1, "profiles": {"known": {"version": 1, "attributes": {"X": {"type": "string"}}}}},
    label="test",
)


def test_undefined_binding_is_a_structural_conflict() -> None:
    conflicts = classify_profile_conflicts(["known", "ghost"], _REGISTRY, [])
    assert [(c.conflict_class, "ghost" in c.message) for c in conflicts] == [("structural", True)]


def test_defined_binding_is_not_a_conflict() -> None:
    assert classify_profile_conflicts(["known"], _REGISTRY, []) == ()


def test_identical_redefinition_is_not_a_conflict() -> None:
    # Two fragments declaring the same attribute+type compose with no merge conflict, so
    # classification reports nothing scoped.
    _merged, merge_conflicts = merge_property_schemas(
        [{"properties": {"Supplier": {"type": "string"}}}, {"properties": {"Supplier": {"type": "string"}}}]
    )
    assert merge_conflicts == []
    assert classify_profile_conflicts([], _REGISTRY, merge_conflicts) == ()


def test_incompatible_type_redefinition_is_a_scoped_conflict() -> None:
    _merged, merge_conflicts = merge_property_schemas(
        [{"properties": {"Supplier": {"type": "string"}}}, {"properties": {"Supplier": {"type": "number"}}}]
    )
    assert len(merge_conflicts) == 1
    conflicts = classify_profile_conflicts([], _REGISTRY, merge_conflicts)
    assert [c.conflict_class for c in conflicts] == ["scoped"]


def test_both_classes_are_assigned_in_one_pass() -> None:
    _merged, merge_conflicts = merge_property_schemas(
        [{"properties": {"S": {"type": "string"}}}, {"properties": {"S": {"type": "integer"}}}]
    )
    conflicts = classify_profile_conflicts(["ghost"], _REGISTRY, merge_conflicts)
    assert {c.conflict_class for c in conflicts} == {"structural", "scoped"}
    # Structural is reported first (it subsumes the scoped one: the schema is indeterminable).
    assert conflicts[0].conflict_class == "structural"
