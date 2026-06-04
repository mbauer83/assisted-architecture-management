"""AI-BOM export and reconcile — CycloneDX 1.6 ML-BOM/ASBOM.

build_cyclonedx_16() emits a CycloneDX 1.6-flavoured JSON document from a
list of AI-component dicts (sourced from architecture entities with the
ai-component attribute profile applied).

reconcile_aibom() diffs a modeled list against a discovered list and returns
a drift report: added (in discovered, not modeled), removed (modeled, not
discovered), and matched components.

Component dict keys used by this module (all optional except name):
  name, purl, cpe, ai_role, version, provider, hosted, external,
  model_card_ref, dataset_provenance, component_type, arch_entity_id
"""

from __future__ import annotations

import hashlib
import time
import uuid

_CDX_AI_ROLE_TO_TYPE: dict[str, str] = {
    "machine-learning-model": "machine-learning-model",
    "dataset": "data",
    "inference-service": "service",
    "mcp-server": "service",
    "tool": "library",
    "agent": "application",
    "orchestrator": "application",
    "prompt": "data",
    "guardrail": "library",
    "vector-store": "data",
    "rag-pipeline": "application",
}


def _cdx_component(comp: dict[str, object]) -> dict[str, object]:
    ai_role = str(comp.get("ai_role") or "")
    cdx_type = _CDX_AI_ROLE_TO_TYPE.get(ai_role, "library")
    node: dict[str, object] = {
        "type": cdx_type,
        "name": str(comp.get("name") or ""),
    }
    if comp.get("version"):
        node["version"] = str(comp["version"])
    if comp.get("purl"):
        node["purl"] = str(comp["purl"])
    if comp.get("cpe"):
        node["cpe"] = str(comp["cpe"])
    props: list[dict[str, str]] = []
    if ai_role:
        props.append({"name": "ai:role", "value": ai_role})
    if comp.get("provider"):
        props.append({"name": "ai:provider", "value": str(comp["provider"])})
    if comp.get("hosted"):
        props.append({"name": "ai:hosted", "value": str(comp["hosted"])})
    if comp.get("external"):
        props.append({"name": "ai:external", "value": str(comp["external"])})
    if comp.get("arch_entity_id"):
        props.append({"name": "arch:entity_id", "value": str(comp["arch_entity_id"])})
    if comp.get("model_card_ref"):
        node["modelCard"] = {"bom-ref": str(comp["model_card_ref"])}
    if props:
        node["properties"] = props
    return node


def build_cyclonedx_16(
    ai_components: list[dict[str, object]],
    *,
    serial: str | None = None,
    notes: str = "",
) -> dict[str, object]:
    """Emit a CycloneDX 1.6 ML-BOM/ASBOM JSON document."""
    bom_serial = serial or f"urn:uuid:{uuid.uuid4()}"
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": bom_serial,
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "tools": [{"name": "arch-assurance", "version": "1.0"}],
            "notes": notes,
        },
        "components": [_cdx_component(c) for c in ai_components],
    }


def _component_key(comp: dict[str, object]) -> str:
    """Stable identity key for reconciliation: purl if present, else name."""
    purl = str(comp.get("purl") or "")
    if purl:
        return purl
    return "name:" + hashlib.sha256(str(comp.get("name") or "").encode()).hexdigest()[:8]


def reconcile_aibom(
    modeled: list[dict[str, object]],
    discovered: list[dict[str, object]],
) -> dict[str, object]:
    """Diff a modeled AI-BOM against a discovered one.

    Returns a drift report with added, removed, and matched component lists.
    """
    modeled_keys = {_component_key(c): c for c in modeled}
    discovered_keys = {_component_key(c): c for c in discovered}

    added = [discovered_keys[k] for k in discovered_keys if k not in modeled_keys]
    removed = [modeled_keys[k] for k in modeled_keys if k not in discovered_keys]
    matched_keys = set(modeled_keys) & set(discovered_keys)
    matched = [
        {
            "key": k,
            "modeled": modeled_keys[k],
            "discovered": discovered_keys[k],
        }
        for k in matched_keys
    ]

    return {
        "added_count": len(added),
        "removed_count": len(removed),
        "matched_count": len(matched),
        "added": added,
        "removed": removed,
        "matched": matched,
        "summary": (
            f"{len(added)} component(s) in discovered but not modeled; "
            f"{len(removed)} modeled but not in discovered; "
            f"{len(matched)} matched."
        ),
    }
