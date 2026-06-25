"""Verification logic for .outgoing.md connection files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from src.application.runtime_catalogs import RuntimeCatalogs
from src.application.verification._verifier_rules_schema import check_frontmatter_schema
from src.application.verification._verifier_rules_semantic import check_connection_semantics
from src.application.verification.artifact_verifier_parsing import parse_frontmatter, read_file
from src.application.verification.artifact_verifier_registry import ArtifactRegistry
from src.application.verification.artifact_verifier_rules import check_enum, check_required_fields
from src.application.verification.artifact_verifier_types import (
    OUTGOING_FILE_REQUIRED,
    VALID_STATUSES,
    Issue,
    Severity,
    VerificationResult,
)
from src.domain.artifact_id import stable_id

_CARDINALITY_RE = re.compile(r"^\d+$|^\d+\.\.\d+$|^\d+\.\.\*$|^\*$")

_CONN_HEADER_RE = re.compile(
    r"^(?P<conn_type>[a-z][a-z0-9-]+)"
    r"(?:\s+\[(?P<src_card>[^\]]+)\])?"
    r"\s+→\s+"
    r"(?:\[(?P<tgt_card>[^\]]+)\]\s+)?"
    r"(?P<target_id>\S+)$"
)


def _parse_conn_header(header: str) -> tuple[str, str, str, str] | None:
    m = _CONN_HEADER_RE.match(header)
    if not m:
        return None
    return (
        m.group("conn_type"),
        m.group("src_card") or "",
        m.group("tgt_card") or "",
        m.group("target_id"),
    )


def _target_issue(target_id: str, all_short_ids: set[str], scope: str, loc: str) -> Issue:
    """Distinguish an enterprise-scope leak (E130) from a genuinely missing target (E124)."""
    if stable_id(target_id) in all_short_ids and scope == "enterprise":
        return Issue(
            Severity.ERROR, "E130", f"enterprise connection references non-enterprise entity '{target_id}'", loc
        )
    return Issue(Severity.ERROR, "E124", f"Target entity '{target_id}' not found in model", loc)


def _check_source_entity(
    source: str,
    *,
    entity_short_ids: set[str],
    enterprise_short_ids: set[str],
    scope: str,
    result: VerificationResult,
    loc: str,
) -> None:
    """Validate that ``source-entity`` exists and respects enterprise scoping (E120/E131)."""
    source_short = stable_id(source)
    if source_short not in entity_short_ids:
        result.issues.append(Issue(Severity.ERROR, "E120", f"source-entity '{source}' not found in model", loc))
    elif scope == "enterprise" and source_short not in enterprise_short_ids:
        result.issues.append(
            Issue(Severity.ERROR, "E131", f"enterprise connection has non-enterprise source-entity '{source}'", loc)
        )


def _check_connection_block(
    header: str,
    *,
    catalogs: RuntimeCatalogs,
    has_registry: bool,
    allowed_short_ids: set[str],
    all_short_ids: set[str],
    scope: str,
    seen_connections: set[str],
    result: VerificationResult,
    loc: str,
) -> tuple[str, str] | None:
    """Validate a single ``### <header>`` connection block, appending any issues.

    Returns ``(conn_type, target_id)`` for downstream semantic checks, or ``None``
    when the header is malformed.
    """
    parsed = _parse_conn_header(header)
    if parsed is None:
        result.issues.append(
            Issue(Severity.ERROR, "E122", f"Connection header missing ' → ' separator: '{header}'", loc)
        )
        return None

    conn_type, src_card, tgt_card, target_id = parsed
    if conn_type not in catalogs.ontology.all_connection_type_names():
        result.issues.append(Issue(Severity.ERROR, "E123", f"Unknown connection type '{conn_type}'", loc))
    for card_label, card_val in (("source", src_card), ("target", tgt_card)):
        if card_val and not _CARDINALITY_RE.match(card_val):
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E125",
                    f"Invalid {card_label} cardinality '{card_val}' in '{header}' "
                    f"— expected n, n..m, n..*, or *",
                    loc,
                )
            )
    if has_registry and stable_id(target_id) not in allowed_short_ids:
        result.issues.append(_target_issue(target_id, all_short_ids, scope, loc))

    conn_key = f"{conn_type} → {stable_id(target_id)}"
    if conn_key in seen_connections:
        result.issues.append(Issue(Severity.WARNING, "W120", f"Duplicate connection: '{conn_key}'", loc))
    seen_connections.add(conn_key)
    return conn_type, target_id


def verify_outgoing(
    path: Path,
    *,
    registry: ArtifactRegistry | None,
    catalogs: RuntimeCatalogs,
    scope: Literal["enterprise", "engagement", "unknown"],
    repo_root: Path | None,
) -> VerificationResult:
    """Verify a .outgoing.md file."""
    result = VerificationResult(path=path, file_type="connection")
    loc = str(path)
    content = read_file(path, result, loc)
    if content is None:
        return result
    fm = parse_frontmatter(content, result, loc)
    if fm is None:
        return result

    check_required_fields(fm, OUTGOING_FILE_REQUIRED, result, loc)
    check_enum(fm, "status", VALID_STATUSES, result, loc)

    source = fm.get("source-entity", "")
    if registry is not None:
        all_entity_ids = registry.entity_ids()
        ent_entity_ids = registry.enterprise_entity_ids()
        all_short_ids = {stable_id(e) for e in all_entity_ids}
        ent_short_ids = {stable_id(e) for e in ent_entity_ids}
        allowed_short_ids = ent_short_ids if scope == "enterprise" else all_short_ids
    else:
        all_short_ids = ent_short_ids = allowed_short_ids = set()

    if source:
        if registry is not None:
            _check_source_entity(
                source,
                entity_short_ids=all_short_ids,
                enterprise_short_ids=ent_short_ids,
                scope=scope,
                result=result,
                loc=loc,
            )

    if "<!-- §connections -->" not in content:
        result.issues.append(
            Issue(Severity.ERROR, "E121", "Missing <!-- §connections --> section marker", loc)
        )

    seen_connections: set[str] = set()
    parsed_connections: list[tuple[str, str]] = []
    for line in content.splitlines():
        if not line.startswith("### "):
            continue
        conn = _check_connection_block(
            line[4:].strip(),
            catalogs=catalogs,
            has_registry=registry is not None,
            allowed_short_ids=allowed_short_ids,
            all_short_ids=all_short_ids,
            scope=scope,
            seen_connections=seen_connections,
            result=result,
            loc=loc,
        )
        if conn is not None:
            parsed_connections.append(conn)

    if registry is not None and source and parsed_connections:
        check_connection_semantics(
            source,
            parsed_connections,
            registry,
            result,
            loc,
            connections_catalog=catalogs.connections,
            ontology_catalog=catalogs.ontology,
        )

    if repo_root is not None:
        check_frontmatter_schema(fm, repo_root, "outgoing", result, loc)

    return result
