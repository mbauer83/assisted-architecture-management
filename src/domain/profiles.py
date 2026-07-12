"""Domain model for attribute profiles (D13).

A profile and its specialization are one concept, one-to-one: there is no separate,
reusable profile registry a specialization references by slug. The existing
`attributes.{artifact_type}.schema.json` files are the *default* profile for unspecialized
elements (base-type profiles, unchanged on disk, still loaded by
`artifact_schema.load_attribute_schema`); a specialization's own profile is compiled
directly from its inline `attributes: {}` mapping (`profile_from_inline_attributes`) or from
its dedicated `attributes.{artifact_type}.{slug}.schema.json` attachment file — both already
1:1 with the specialization by construction (embedded, or filename-scoped to that slug).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

AttributeLevel = Literal["required", "recommended", "optional"]


@dataclass(frozen=True)
class ProfileAttribute:
    """One typed attribute in a profile."""

    name: str
    type: str = "string"
    level: AttributeLevel = "optional"
    default: Any = None
    enum: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfileDefinition:
    """A compiled attribute set — a specialization's own profile, or the default
    (base-type) profile for unspecialized elements. Never independently reusable."""

    slug: str
    name: str
    applicable_types: tuple[str, ...] = ()
    attributes: tuple[ProfileAttribute, ...] = ()


def compile_profile_schema(profile: ProfileDefinition) -> dict[str, Any]:
    """Compile a `ProfileDefinition` to a JSON Schema fragment.

    `required` covers `level: required` attributes; the extension keyword
    `x-recommended` (JSON Schema has no native "recommended") covers `level:
    recommended` ones, consumed by the verifier for warnings rather than errors.
    """
    properties: dict[str, Any] = {}
    required: list[str] = []
    recommended: list[str] = []
    for attr in profile.attributes:
        prop_schema: dict[str, Any] = {"type": attr.type}
        if attr.enum:
            prop_schema["enum"] = list(attr.enum)
        if attr.default is not None:
            prop_schema["default"] = attr.default
        properties[attr.name] = prop_schema
        if attr.level == "required":
            required.append(attr.name)
        elif attr.level == "recommended":
            recommended.append(attr.name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    if recommended:
        schema["x-recommended"] = recommended
    return schema


def profile_from_inline_attributes(slug: str, attributes: Mapping[str, Any]) -> ProfileDefinition:
    """Compile a specialization's inline `attributes: {}` mapping to an anonymous profile."""
    attrs: list[ProfileAttribute] = []
    for attr_name, raw in attributes.items():
        if not isinstance(raw, Mapping):
            continue
        level = raw.get("level")
        attrs.append(
            ProfileAttribute(
                name=str(attr_name),
                type=str(raw.get("type") or "string"),
                level=level if level in ("required", "recommended", "optional") else "optional",
                default=raw.get("default"),
                enum=tuple(str(v) for v in raw["enum"]) if isinstance(raw.get("enum"), (list, tuple)) else (),
            )
        )
    return ProfileDefinition(slug=f"{slug}:inline", name=f"{slug} (inline)", attributes=tuple(attrs))


def merge_property_schemas(schemas: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """Merge a sequence of JSON-Schema-shaped fragments (`properties`/`required`/
    `x-recommended`), in order. Returns `(merged_schema, conflict_messages)`.

    A property redefined with an incompatible `type` across schemas is a conflict, reported
    but not applied (the later definition is dropped so the merge stays deterministic); any
    other redefinition (e.g. a different `default`) resolves last-writer-wins.
    """
    properties: dict[str, Any] = {}
    required: set[str] = set()
    recommended: set[str] = set()
    conflicts: list[str] = []
    for schema in schemas:
        schema_properties: dict[str, Any] = schema.get("properties") or {}
        for prop_name, prop_schema in schema_properties.items():
            existing = properties.get(prop_name)
            if existing is not None and existing.get("type") and prop_schema.get("type"):
                if existing["type"] != prop_schema["type"]:
                    conflicts.append(
                        f"Conflicting definitions for attribute '{prop_name}': "
                        f"type '{existing['type']}' vs '{prop_schema['type']}'"
                    )
                    continue
            merged_prop = dict(existing or {})
            merged_prop.update(prop_schema)
            properties[prop_name] = merged_prop
        required |= set(schema.get("required") or [])
        recommended |= set(schema.get("x-recommended") or [])
    merged: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        merged["required"] = sorted(required)
    recommended_only = sorted(recommended - required)
    if recommended_only:
        merged["x-recommended"] = recommended_only
    return merged, conflicts
