"""Shipped default attribute schemata for ArchiMate business-object and application-component
specializations, kept out of ``repo_default_schemata`` to hold that module within the
length policy. Merged into ``DEFAULT_SCHEMATA`` there, so the workspace template's ensure-missing
pass and the repository upgrade detector ship them identically.

Two single-source enums are defined ONCE here and referenced by every using schema. Both attach
via the existing convention: base ``attributes.<type>.schema.json`` and per-specialization
``attributes.<type>.<slug>.schema.json`` (resolved + merged by ``compute_effective_attribute_schema``).
Every schema is non-strict (``additionalProperties: true``) with ``required: []`` — the shipped set
is guidance, not a gate. Property keys follow the display-key (Title Case) convention.
"""

from __future__ import annotations

# Planner-friendly classification vocabulary; maps onto the TLP scale (documented in the
# Sensitivity description). Single-sourced so business-object and any future using schema agree.
SENSITIVITY_ENUM = ["Public", "Internal", "Confidential", "Strictly Confidential"]

# Portfolio lifecycle stage for a component/module/endpoint — distinct from a business object
# instance's own "Lifecycle States" list, which tracks an information item's states.
LIFECYCLE_STATE_ENUM = ["Planned", "In Development", "Active", "Deprecated", "Retired"]

_SENSITIVITY_DESCRIPTION = (
    "Planner-friendly sensitivity of the object's content. Maps to TLP: Public→WHITE, "
    "Internal→GREEN, Confidential→AMBER, Strictly Confidential→RED."
)
_LIFECYCLE_STATE_DESCRIPTION = "Portfolio lifecycle stage of this component."
_SOURCE_REPO_DESCRIPTION = (
    "Where the code lives. Informative only — declared as format: uri, but the validator runs no "
    "format checker, so any string is accepted."
)


def _str_list(description: str) -> dict:
    return {"type": "array", "items": {"type": "string"}, "description": description}


ARCHIMATE_ATTRIBUTE_SCHEMATA: dict[str, dict] = {
    "attributes.business-object.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.business-object.schema.json",
        "title": "Business Object Attribute Schema",
        "description": "Attribute schema for Properties table in Business Object entities.",
        "type": "object",
        "required": [],
        "properties": {
            "Meaning": {"type": "string", "description": "What the object means to stakeholders."},
            "Provenance": {"type": "string", "description": "Where the content originates."},
            "Contained Information": _str_list("Information items the object carries."),
            "Internal Consistency Criteria": _str_list("Criteria that must hold within one instance."),
            "External Consistency Criteria": _str_list("Criteria against other objects or systems."),
            "Sensitivity": {"type": "string", "enum": SENSITIVITY_ENUM, "description": _SENSITIVITY_DESCRIPTION},
            "Lifecycle States": _str_list(
                "States an information-object INSTANCE passes through — distinct from the "
                "component-level 'Lifecycle State' enum."
            ),
        },
        "additionalProperties": True,
    },
    "attributes.application-component.service.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.application-component.service.schema.json",
        "title": "Application Component (Service) Attribute Schema",
        "description": "Attributes for a 'service' application component: a deployable service.",
        "type": "object",
        "required": [],
        "properties": {
            "Programming Languages & Versions": _str_list("One entry per language, including version."),
            "Frameworks & Versions": _str_list("One entry per framework, including version."),
            "Runtime Environments": _str_list("One entry per runtime environment."),
            "Communication Protocols & Versions": _str_list("One entry per protocol, including version."),
            "Owner": {"type": "string", "description": "Responsible party for the service."},
            "Source Repository": {"type": "string", "format": "uri", "description": _SOURCE_REPO_DESCRIPTION},
            "Lifecycle State": {
                "type": "string", "enum": LIFECYCLE_STATE_ENUM, "description": _LIFECYCLE_STATE_DESCRIPTION,
            },
        },
        "additionalProperties": True,
    },
    "attributes.application-component.module.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.application-component.module.schema.json",
        "title": "Application Component (Module) Attribute Schema",
        "description": "Attributes for a 'module' application component: an internal code module.",
        "type": "object",
        "required": [],
        "properties": {
            "Problem Domain": {"type": "string", "description": "The domain this module addresses."},
            "Lifecycle State": {
                "type": "string", "enum": LIFECYCLE_STATE_ENUM, "description": _LIFECYCLE_STATE_DESCRIPTION,
            },
        },
        "additionalProperties": True,
    },
    "attributes.application-component.endpoint.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.application-component.endpoint.schema.json",
        "title": "Application Component (Endpoint) Attribute Schema",
        "description": "Attributes for an 'endpoint' application component: an exposed access point.",
        "type": "object",
        "required": [],
        "properties": {
            "Communication Protocol & Version": {
                "type": "string", "description": "e.g. 'HTTP/1.1 + SSE'.",
            },
            "Authentication Method": {"type": "string", "description": "How access is guarded."},
            "Lifecycle State": {
                "type": "string", "enum": LIFECYCLE_STATE_ENUM, "description": _LIFECYCLE_STATE_DESCRIPTION,
            },
        },
        "additionalProperties": True,
    },
}
