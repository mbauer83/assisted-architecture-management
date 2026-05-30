"""Target-resolution helpers for binding verifier rules (E402, E403, E407, E408)."""

from __future__ import annotations

from typing import Literal

from src.application.verification.artifact_verifier_types import Issue, Severity, VerificationResult


def check_binding_target(
    binding_id: str,
    corr_kind: str,
    target: dict,
    entity_element_ids: set[str],
    connection_element_ids: set[str],
    file_scope: Literal["enterprise", "engagement", "unknown"],
    allowed_entities: set[str],
    allowed_connections: set[str],
    all_entities: set[str],
    all_connections: set[str],
    represents_by_target: dict[str, str],
    visual_roles_for_target: dict[str, tuple[str, ...]],
    result: VerificationResult,
    loc: str,
) -> None:
    """Dispatch to the appropriate target-form check based on which target key is present."""
    if "entity_id" in target:
        eid = str(target["entity_id"]) if target["entity_id"] is not None else ""
        _check_entity_target(
            binding_id, corr_kind, eid, file_scope,
            allowed_entities, all_entities,
            represents_by_target, visual_roles_for_target,
            result, loc,
        )
    elif "connection_id" in target:
        cid = str(target["connection_id"]) if target["connection_id"] is not None else ""
        _check_single_connection_target(binding_id, cid, file_scope, allowed_connections, all_connections, result, loc)
    elif "connection_ids" in target:
        raw_cids = target["connection_ids"]
        if isinstance(raw_cids, list):
            for cid_raw in raw_cids:
                _check_single_connection_target(
                    binding_id, str(cid_raw), file_scope,
                    allowed_connections, all_connections, result, loc, code="E407",
                )
    elif "diagram_local" in target:
        dl = target["diagram_local"]
        if isinstance(dl, dict) and dl.get("diagram_id") is None:
            element_id = str(dl.get("element_id") or "")
            all_element_ids = entity_element_ids | connection_element_ids
            if element_id and element_id not in all_element_ids:
                result.issues.append(
                    Issue(
                        Severity.ERROR,
                        "E401",
                        (
                            f"binding '{binding_id}': diagram_local target element_id "
                            f"'{element_id}' not found in diagram elements"
                        ),
                        loc,
                    )
                )
    # connection_path: Phase 3 — no resolution check yet


def _check_entity_target(
    binding_id: str,
    corr_kind: str,
    entity_id: str,
    file_scope: Literal["enterprise", "engagement", "unknown"],
    allowed_entities: set[str],
    all_entities: set[str],
    represents_by_target: dict[str, str],
    visual_roles_for_target: dict[str, tuple[str, ...]],
    result: VerificationResult,
    loc: str,
) -> None:
    if not entity_id:
        return
    if entity_id not in allowed_entities:
        if entity_id in all_entities and file_scope == "enterprise":
            result.issues.append(
                Issue(
                    Severity.ERROR, "E402",
                    (
                        f"binding '{binding_id}': target entity_id '{entity_id}' is not an "
                        "enterprise entity — enterprise diagram bindings may only target enterprise entities"
                    ),
                    loc,
                )
            )
        else:
            result.issues.append(
                Issue(
                    Severity.ERROR, "E402",
                    f"binding '{binding_id}': target entity_id '{entity_id}' does not exist in scope",
                    loc,
                )
            )
        return

    if corr_kind != "represents":
        return

    if entity_id not in represents_by_target:
        represents_by_target[entity_id] = binding_id
        return

    # Duplicate represents — check visual_roles
    declared_roles = visual_roles_for_target.get(entity_id, ())
    if declared_roles:
        # visual_roles are declared for this target's entity type — allow; role-distinctness checked in E408b
        pass
    else:
        result.issues.append(
            Issue(
                Severity.ERROR, "E408",
                (
                    f"binding '{binding_id}': model entity '{entity_id}' already has a "
                    f"'represents' binding in this diagram "
                    f"(first seen in binding '{represents_by_target[entity_id]}'). "
                    "Use visual_roles in the diagram module to allow multiple occurrences."
                ),
                loc,
            )
        )


def _check_single_connection_target(
    binding_id: str,
    connection_id: str,
    file_scope: Literal["enterprise", "engagement", "unknown"],
    allowed_connections: set[str],
    all_connections: set[str],
    result: VerificationResult,
    loc: str,
    code: str = "E403",
) -> None:
    if not connection_id:
        return
    if connection_id not in allowed_connections:
        if connection_id in all_connections and file_scope == "enterprise":
            result.issues.append(
                Issue(
                    Severity.ERROR, code,
                    (
                        f"binding '{binding_id}': target connection '{connection_id}' is not an "
                        "enterprise connection — enterprise diagram bindings may only target enterprise connections"
                    ),
                    loc,
                )
            )
        else:
            result.issues.append(
                Issue(
                    Severity.ERROR, code,
                    f"binding '{binding_id}': target connection '{connection_id}' does not exist in scope",
                    loc,
                )
            )
