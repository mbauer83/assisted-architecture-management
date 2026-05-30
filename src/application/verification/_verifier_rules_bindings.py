"""Verifier rules for top-level diagram bindings.

E401: binding subject element not found in diagram.
E402: binding target entity_id unknown or out of scope.
E403: binding target connection_id unknown or out of scope.
E404: duplicate 'represents' binding for the same subject element.
E405: duplicate diagram-level 'scoped-by' binding.
E406: correspondence_kind not in the core five (Phase 2 adds module-declared kinds).
E407: a member of target.connection_ids is unknown or out of scope.
E408: duplicate 'represents' binding for the same model target (visual_roles not yet supported).
"""

from __future__ import annotations

from typing import Literal

from src.domain.bindings import CORE_CORRESPONDENCE_KINDS
from src.application.verification.artifact_verifier_types import Issue, Severity, VerificationResult

# ---------------------------------------------------------------------------
# Public entry point — called from check_diagram_references_scoped
# ---------------------------------------------------------------------------


def check_bindings_scoped(
    fm: dict,
    file_scope: Literal["enterprise", "engagement", "unknown"],
    allowed_entities: set[str],
    allowed_connections: set[str],
    all_entities: set[str],
    all_connections: set[str],
    result: VerificationResult,
    loc: str,
) -> None:
    """Validate top-level bindings in a diagram's frontmatter.

    Skips silently when there are no bindings.  Calls _check_bindings.
    """
    raw_bindings = fm.get("bindings")
    if not raw_bindings or not isinstance(raw_bindings, list):
        return

    entity_element_ids = _collect_entity_element_ids(fm)
    connection_element_ids = _collect_connection_element_ids(fm)

    _check_bindings(
        raw_bindings,
        entity_element_ids,
        connection_element_ids,
        file_scope,
        allowed_entities,
        allowed_connections,
        all_entities,
        all_connections,
        result,
        loc,
    )


# ---------------------------------------------------------------------------
# Private implementation
# ---------------------------------------------------------------------------


def _collect_entity_element_ids(fm: dict) -> set[str]:
    ids: set[str] = set()
    de = fm.get("diagram-entities")
    if not isinstance(de, dict):
        return ids
    for items in de.values():
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("id") is not None:
                    ids.add(str(item["id"]))
    return ids


def _collect_connection_element_ids(fm: dict) -> set[str]:
    ids: set[str] = set()
    conns = fm.get("connections")
    if not isinstance(conns, list):
        return ids
    for item in conns:
        if isinstance(item, dict) and item.get("id") is not None:
            ids.add(str(item["id"]))
    return ids


def _check_bindings(
    raw_bindings: list,
    entity_element_ids: set[str],
    connection_element_ids: set[str],
    file_scope: Literal["enterprise", "engagement", "unknown"],
    allowed_entities: set[str],
    allowed_connections: set[str],
    all_entities: set[str],
    all_connections: set[str],
    result: VerificationResult,
    loc: str,
) -> None:
    represents_by_subject: dict[str, str] = {}  # subject_id → first binding id
    represents_by_target: dict[str, str] = {}   # model_target → first binding id
    scoped_by_diagram_count = 0

    for raw in raw_bindings:
        if not isinstance(raw, dict):
            continue

        binding_id = str(raw.get("id") or "(no-id)")
        subject = raw.get("subject")
        corr_kind = str(raw.get("correspondence_kind") or "")
        target = raw.get("target")

        # --- correspondence_kind ---
        if corr_kind not in CORE_CORRESPONDENCE_KINDS:
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E406",
                    (
                        f"binding '{binding_id}': correspondence_kind '{corr_kind}' "
                        "is not one of the core five "
                        f"({', '.join(sorted(CORE_CORRESPONDENCE_KINDS))})"
                    ),
                    loc,
                )
            )

        # --- subject resolution ---
        if not isinstance(subject, dict):
            continue
        subject_kind = str(subject.get("kind") or "")
        subject_id = subject.get("id")

        if subject_kind == "diagram":
            if subject_id is not None:
                result.issues.append(
                    Issue(
                        Severity.ERROR,
                        "E401",
                        (
                            f"binding '{binding_id}': diagram-level binding must have no "
                            f"subject.id (got '{subject_id}')"
                        ),
                        loc,
                    )
                )
            if corr_kind == "scoped-by":
                scoped_by_diagram_count += 1
                if scoped_by_diagram_count > 1:
                    result.issues.append(
                        Issue(
                            Severity.ERROR,
                            "E405",
                            f"binding '{binding_id}': diagram may have at most one diagram-level 'scoped-by' binding",
                            loc,
                        )
                    )
        elif subject_kind == "entity":
            subject_id_str = str(subject_id) if subject_id is not None else ""
            if not subject_id_str or subject_id_str not in entity_element_ids:
                result.issues.append(
                    Issue(
                        Severity.ERROR,
                        "E401",
                        (
                            f"binding '{binding_id}': subject entity element '{subject_id_str}' "
                            "not found in diagram-entities"
                        ),
                        loc,
                    )
                )
            elif corr_kind == "represents":
                if subject_id_str in represents_by_subject:
                    result.issues.append(
                        Issue(
                            Severity.ERROR,
                            "E404",
                            (
                                f"binding '{binding_id}': duplicate 'represents' binding for "
                                f"subject element '{subject_id_str}' "
                                f"(first seen in binding '{represents_by_subject[subject_id_str]}')"
                            ),
                            loc,
                        )
                    )
                else:
                    represents_by_subject[subject_id_str] = binding_id
        elif subject_kind == "connection":
            subject_id_str = str(subject_id) if subject_id is not None else ""
            if not subject_id_str or subject_id_str not in connection_element_ids:
                result.issues.append(
                    Issue(
                        Severity.ERROR,
                        "E401",
                        (
                            f"binding '{binding_id}': subject connection element '{subject_id_str}' "
                            "not found in diagram connections"
                        ),
                        loc,
                    )
                )

        # --- target resolution ---
        if not isinstance(target, dict):
            continue
        _check_binding_target(
            binding_id,
            corr_kind,
            target,
            entity_element_ids,
            connection_element_ids,
            file_scope,
            allowed_entities,
            allowed_connections,
            all_entities,
            all_connections,
            represents_by_target,
            result,
            loc,
        )


def _check_binding_target(
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
    result: VerificationResult,
    loc: str,
) -> None:
    if "entity_id" in target:
        eid = str(target["entity_id"]) if target["entity_id"] is not None else ""
        _check_entity_target(binding_id, corr_kind, eid, file_scope, allowed_entities, all_entities, represents_by_target, result, loc)

    elif "connection_id" in target:
        cid = str(target["connection_id"]) if target["connection_id"] is not None else ""
        _check_single_connection_target(binding_id, cid, file_scope, allowed_connections, all_connections, result, loc)

    elif "connection_ids" in target:
        raw_cids = target["connection_ids"]
        if isinstance(raw_cids, list):
            for cid_raw in raw_cids:
                cid = str(cid_raw)
                _check_single_connection_target(binding_id, cid, file_scope, allowed_connections, all_connections, result, loc, code="E407")

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
        # If diagram_id is set, it references another diagram — skip resolution (not in scope here)

    # connection_path: Phase 3 — no resolution check yet


def _check_entity_target(
    binding_id: str,
    corr_kind: str,
    entity_id: str,
    file_scope: Literal["enterprise", "engagement", "unknown"],
    allowed_entities: set[str],
    all_entities: set[str],
    represents_by_target: dict[str, str],
    result: VerificationResult,
    loc: str,
) -> None:
    if not entity_id:
        return
    if entity_id not in allowed_entities:
        if entity_id in all_entities and file_scope == "enterprise":
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E402",
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
                    Severity.ERROR,
                    "E402",
                    f"binding '{binding_id}': target entity_id '{entity_id}' does not exist in scope",
                    loc,
                )
            )
        return

    if corr_kind == "represents":
        if entity_id in represents_by_target:
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E408",
                    (
                        f"binding '{binding_id}': model entity '{entity_id}' already has a "
                        f"'represents' binding in this diagram "
                        f"(first seen in binding '{represents_by_target[entity_id]}'). "
                        "Use visual_roles in the diagram module to allow multiple occurrences."
                    ),
                    loc,
                )
            )
        else:
            represents_by_target[entity_id] = binding_id


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
                    Severity.ERROR,
                    code,
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
                    Severity.ERROR,
                    code,
                    f"binding '{binding_id}': target connection '{connection_id}' does not exist in scope",
                    loc,
                )
            )
