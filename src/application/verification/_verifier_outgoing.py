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
    if registry is not None and source:
        all_entities = registry.entity_ids()
        if source not in all_entities:
            result.issues.append(
                Issue(Severity.ERROR, "E120", f"source-entity '{source}' not found in model", loc)
            )
        elif scope == "enterprise" and source not in registry.enterprise_entity_ids():
            result.issues.append(
                Issue(
                    Severity.ERROR,
                    "E131",
                    f"enterprise connection has non-enterprise source-entity '{source}'",
                    loc,
                )
            )

    if "<!-- §connections -->" not in content:
        result.issues.append(
            Issue(Severity.ERROR, "E121", "Missing <!-- §connections --> section marker", loc)
        )

    if registry is not None:
        allowed_entities = (
            registry.enterprise_entity_ids() if scope == "enterprise" else registry.entity_ids()
        )
        all_entities_for_scope = registry.entity_ids()
    else:
        allowed_entities = all_entities_for_scope = set()

    seen_connections: set[str] = set()
    parsed_connections: list[tuple[str, str]] = []
    for line in content.splitlines():
        if line.startswith("### "):
            header = line[4:].strip()
            parsed = _parse_conn_header(header)
            if parsed is None:
                result.issues.append(
                    Issue(
                        Severity.ERROR,
                        "E122",
                        f"Connection header missing ' → ' separator: '{header}'",
                        loc,
                    )
                )
            else:
                conn_type, src_card, tgt_card, target_id = parsed
                if conn_type not in catalogs.ontology.all_connection_type_names():
                    result.issues.append(
                        Issue(Severity.ERROR, "E123", f"Unknown connection type '{conn_type}'", loc)
                    )
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
                if registry is not None and target_id not in allowed_entities:
                    issue = (
                        Issue(
                            Severity.ERROR,
                            "E130",
                            f"enterprise connection references non-enterprise entity '{target_id}'",
                            loc,
                        )
                        if target_id in all_entities_for_scope and scope == "enterprise"
                        else Issue(
                            Severity.ERROR,
                            "E124",
                            f"Target entity '{target_id}' not found in model",
                            loc,
                        )
                    )
                    result.issues.append(issue)
                conn_key = f"{conn_type} → {target_id}"
                if conn_key in seen_connections:
                    result.issues.append(
                        Issue(Severity.WARNING, "W120", f"Duplicate connection: '{conn_key}'", loc)
                    )
                seen_connections.add(conn_key)
                parsed_connections.append((conn_type, target_id))

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
