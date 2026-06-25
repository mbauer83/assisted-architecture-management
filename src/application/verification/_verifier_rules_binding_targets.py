"""Target-resolution helpers for binding verifier rules (E402, E403, E407, E408)."""

from __future__ import annotations

from typing import Literal

from src.application.verification.artifact_verifier_types import Issue, Severity, VerificationResult
from src.domain.artifact_id import MalformedArtifactIdError, parse_connection_id, stable_conn_id, stable_id


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
    elif "connection_path" in target:
        cp_raw = target["connection_path"]
        if isinstance(cp_raw, list):
            _check_connection_path_target(
                binding_id, cp_raw, allowed_connections, result, loc
            )


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
    allowed_short = {stable_id(a) for a in allowed_entities}
    all_short = {stable_id(a) for a in all_entities}
    eid_short = stable_id(entity_id)
    if eid_short not in allowed_short:
        message = (
            (
                f"binding '{binding_id}': target entity_id '{entity_id}' is not an "
                "enterprise entity — enterprise diagram bindings may only target enterprise entities"
            )
            if eid_short in all_short and file_scope == "enterprise"
            else f"binding '{binding_id}': target entity_id '{entity_id}' does not exist in scope"
        )
        result.issues.append(Issue(Severity.ERROR, "E402", message, loc))
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


def _conn_endpoints(conn_id: str) -> tuple[str, str] | None:
    """Parse stable (source_short, target_short) from a connection id."""
    try:
        key = parse_connection_id(conn_id)
        return key.src_short, key.tgt_short
    except MalformedArtifactIdError:
        return None


def _check_connection_path_target(
    binding_id: str,
    cp_raw: list,
    allowed_connections: set[str],
    result: VerificationResult,
    loc: str,
) -> None:
    """E409: step id not in scope. E410: chain not contiguous under orientation."""
    allowed_short_conns = {stable_conn_id(c) for c in allowed_connections}
    prev_to: str | None = None
    for i, step in enumerate(cp_raw):
        if isinstance(step, dict):
            step_id = str(step.get("id") or "")
            reversed_flag = bool(step.get("reversed", False))
            if not step_id or stable_conn_id(step_id) not in allowed_short_conns:
                result.issues.append(Issue(
                    Severity.ERROR, "E409",
                    f"binding '{binding_id}': connection_path step {i} id '{step_id}' does not exist in scope",
                    loc,
                ))
                prev_to = None
            elif (endpoints := _conn_endpoints(step_id)) is None:
                prev_to = None
            else:
                src, tgt = endpoints
                step_from = tgt if reversed_flag else src
                step_to = src if reversed_flag else tgt
                if prev_to is not None and step_from != prev_to:
                    result.issues.append(Issue(
                        Severity.ERROR, "E410",
                        (
                            f"binding '{binding_id}': connection_path is not contiguous at step {i}: "
                            f"expected from='{prev_to}', got from='{step_from}' (id='{step_id}')"
                        ),
                        loc,
                    ))
                prev_to = step_to


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
    allowed_short_conns = {stable_conn_id(c) for c in allowed_connections}
    conn_stable = stable_conn_id(connection_id)
    if conn_stable not in allowed_short_conns:
        all_short_conns = {stable_conn_id(c) for c in all_connections}
        if conn_stable in all_short_conns and file_scope == "enterprise":
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
