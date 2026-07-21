"""Default assurance attribute schemata for repo scaffolding.

Split out of `repo_default_schemata.py` purely to stay under the source-length policy —
merged into `DEFAULT_SCHEMATA` there. Migrated off the dormant
`OntologyModule.attribute_profiles` surface (removed; it had no live consumer besides these
scaffolding defaults, per the WU-D7 call-path verification).
"""

from __future__ import annotations

ASSURANCE_ATTRIBUTE_SCHEMATA: dict[str, dict] = {
    "attributes.assurance-constraint.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.assurance-constraint.schema.json",
        "title": "Assurance Constraint Attribute Schema",
        "description": "Attribute schema for Properties table in Assurance Constraint entities.",
        "type": "object",
        "required": [],
        "properties": {
            "concern_class": {
                "type": "string",
                "enum": ["safety", "security", "operational", "financial", "privacy"],
            },
            "disposition": {
                "type": "string",
                "enum": [
                    "eliminated",
                    "prevented-by-design",
                    "controlled-with-evidence",
                    "alarp-justified",
                    "accepted",
                    "mitigate",
                    "transfer",
                    "avoid",
                ],
            },
            "level": {"type": "string", "enum": ["system", "controller", "technical"]},
            "tlp": {
                "type": "string",
                "enum": ["TLP:WHITE", "TLP:GREEN", "TLP:AMBER", "TLP:RED"],
            },
            "enforcement_status": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "attributes.control-structure-node.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.control-structure-node.schema.json",
        "title": "Control Structure Node Attribute Schema",
        "description": "Attribute schema for Properties table in Control Structure Node entities.",
        "type": "object",
        "required": [],
        "properties": {
            "node_role": {
                "type": "string",
                "enum": ["controller", "controlled-process", "actuator", "sensor"],
            },
            "binding_status": {
                "type": "string",
                "enum": ["bound", "unbound-pending", "out-of-scope"],
                "default": "unbound-pending",
            },
            "granularity_note": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "attributes.hazard.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.hazard.schema.json",
        "title": "Hazard Attribute Schema",
        "description": "Attribute schema for Properties table in Hazard entities.",
        "type": "object",
        "required": [],
        "properties": {
            "concern_class": {
                "type": "string",
                "enum": ["safety", "security", "operational", "financial", "privacy"],
            },
            "tlp": {
                "type": "string",
                "enum": ["TLP:WHITE", "TLP:GREEN", "TLP:AMBER", "TLP:RED"],
                "default": "TLP:WHITE",
            },
            "classification_scheme": {"type": "string"},
            "classification_code": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "attributes.risk.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.risk.schema.json",
        "title": "Risk Attribute Schema",
        "description": "Attribute schema for Properties table in Risk entities.",
        "type": "object",
        "required": [],
        "properties": {
            "likelihood": {"type": "string", "enum": ["rare", "unlikely", "possible", "likely", "almost-certain"]},
            "impact": {"type": "string", "enum": ["negligible", "minor", "moderate", "major", "catastrophic"]},
            "treatment": {"type": "string", "enum": ["mitigate", "transfer", "avoid", "accept"]},
            "residual_likelihood": {"type": "string"},
            "residual_impact": {"type": "string"},
            "review_date": {"type": "string", "format": "date"},
        },
        "additionalProperties": True,
    },
    "attributes.unsafe-control-action.schema.json": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "attributes.unsafe-control-action.schema.json",
        "title": "Unsafe Control Action Attribute Schema",
        "description": "Attribute schema for Properties table in Unsafe Control Action entities.",
        "type": "object",
        "required": [],
        "properties": {
            "uca_type": {
                "type": "string",
                "enum": ["not-provided", "provided", "wrong-timing", "stopped-too-soon"],
            },
            "mode": {"type": "string", "enum": ["hypothesized", "observed"]},
            "context": {"type": "string"},
            "concern_class": {
                "type": "string",
                "enum": ["safety", "security", "operational", "financial", "privacy"],
            },
        },
        "additionalProperties": True,
    },
}
