
import re
from pathlib import Path
from typing import Any, Literal

from src.common.model_verifier_registry import ModelRegistry
from src.common.model_verifier_types import (
    DIAGRAM_ARTIFACT_TYPES,
    ENTITY_ID_RE,
    Issue,
    Severity,
    VerificationResult,
    entity_id_from_path,
)
from src.common.model_schema import (
    load_attribute_schema,
    load_frontmatter_schema,
    validate_against_schema,
)


def check_required_fields(fm: dict, required: frozenset[str], result: VerificationResult, loc: str) -> None:
    for field_name in sorted(required):
        if field_name not in fm or fm[field_name] is None:
            result.issues.append(Issue(
                Severity.ERROR,
                "E021",
                f"Required frontmatter field '{field_name}' is missing or null",
                loc,
            ))


def check_artifact_id_entity(fm: dict, result: VerificationResult, loc: str) -> None:
    if "artifact-id" not in fm:
        return
    aid = str(fm["artifact-id"])
    if not ENTITY_ID_RE.match(aid):
        result.issues.append(Issue(
            Severity.ERROR,
            "E101",
            f"artifact-id '{aid}' does not match TYPE@epoch.random.name pattern",
            loc,
        ))
        return

    file_id = entity_id_from_path(result.path)
    if file_id != aid:
        result.issues.append(Issue(
            Severity.ERROR,
            "E104",
            f"entity filename stem '{file_id}' does not match artifact-id '{aid}'",
            loc,
        ))


def check_artifact_type(
    fm: dict,
    valid: frozenset[str],
    label: str,
    result: VerificationResult,
    loc: str,
) -> None:
    if "artifact-type" not in fm:
        return
    artifact_type = str(fm["artifact-type"])
    if artifact_type not in valid:
        result.issues.append(Issue(
            Severity.ERROR,
            "E102",
            f"artifact-type '{artifact_type}' is not a recognised {label}",
            loc,
        ))


def check_enum(
    fm: dict,
    field_name: str,
    valid: frozenset[str],
    result: VerificationResult,
    loc: str,
) -> None:
    if field_name not in fm or fm[field_name] is None:
        return
    value = str(fm[field_name])
    if value not in valid:
        result.issues.append(Issue(
            Severity.ERROR,
            "E022",
            f"Field '{field_name}' has invalid value '{value}'; expected one of: {sorted(valid)}",
            loc,
        ))


def check_section(
    content: str,
    section: str,
    *,
    required: bool,
    result: VerificationResult,
    loc: str,
) -> None:
    marker = f"<!-- {section} -->"
    if marker in content:
        return
    severity = Severity.ERROR if required else Severity.WARNING
    code = "E031" if required else "W031"
    msg = f"Section marker '{marker}' is {'absent' if required else 'absent (optional for connections)'}"
    result.issues.append(Issue(severity, code, msg, loc))


def check_diagram_references_scoped(
    fm: dict,
    registry: ModelRegistry,
    file_scope: Literal["enterprise", "engagement", "unknown"],
    result: VerificationResult,
    loc: str,
) -> None:
    diagram_is_baselined = str(fm.get("status", "")) == "baselined"

    allowed_entities = registry.enterprise_entity_ids() if file_scope == "enterprise" else registry.entity_ids()
    allowed_connections = (
        registry.enterprise_connection_ids() if file_scope == "enterprise" else registry.connection_ids()
    )
    all_entities = registry.entity_ids()
    all_connections = registry.connection_ids()

    _check_entity_ids_used(
        fm,
        registry,
        file_scope,
        allowed_entities,
        all_entities,
        diagram_is_baselined,
        result,
        loc,
    )
    _check_connection_ids_used(
        fm,
        registry,
        file_scope,
        allowed_connections,
        all_connections,
        diagram_is_baselined,
        result,
        loc,
    )


def _check_entity_ids_used(
    fm: dict,
    registry: ModelRegistry,
    file_scope: Literal["enterprise", "engagement", "unknown"],
    allowed_entities: set[str],
    all_entities: set[str],
    diagram_is_baselined: bool,
    result: VerificationResult,
    loc: str,
) -> None:
    if "entity-ids-used" not in fm:
        return
    entity_ids = fm["entity-ids-used"]
    if not isinstance(entity_ids, list):
        if entity_ids is not None:
            result.issues.append(Issue(Severity.WARNING, "W303", "entity-ids-used should be a YAML list", loc))
        return

    for eid in entity_ids:
        eid_str = str(eid)
        if eid_str not in allowed_entities:
            if eid_str in all_entities and file_scope == "enterprise":
                msg = (
                    f"entity-ids-used references non-enterprise entity '{eid_str}' "
                    "— enterprise diagrams may only reference enterprise entities"
                )
                result.issues.append(Issue(Severity.ERROR, "E310", msg, loc))
            else:
                result.issues.append(Issue(
                    Severity.ERROR,
                    "E301",
                    f"entity-ids-used references unknown entity '{eid_str}'",
                    loc,
                ))
            continue

        if diagram_is_baselined and registry.entity_status(eid_str) == "draft":
            result.issues.append(Issue(
                Severity.ERROR,
                "E306",
                f"baselined diagram references draft entity '{eid_str}' — all entities in a baselined diagram must be baselined",
                loc,
            ))


def _check_connection_ids_used(
    fm: dict,
    registry: ModelRegistry,
    file_scope: Literal["enterprise", "engagement", "unknown"],
    allowed_connections: set[str],
    all_connections: set[str],
    diagram_is_baselined: bool,
    result: VerificationResult,
    loc: str,
) -> None:
    if "connection-ids-used" not in fm:
        return
    conn_ids = fm["connection-ids-used"]
    if not isinstance(conn_ids, list):
        if conn_ids is not None:
            result.issues.append(Issue(Severity.WARNING, "W304", "connection-ids-used should be a YAML list", loc))
        return

    for cid in conn_ids:
        cid_str = str(cid)
        if cid_str not in allowed_connections:
            if cid_str in all_connections and file_scope == "enterprise":
                msg = (
                    f"connection-ids-used references non-enterprise connection '{cid_str}' "
                    "— enterprise diagrams may only reference enterprise connections"
                )
                result.issues.append(Issue(Severity.ERROR, "E320", msg, loc))
            else:
                result.issues.append(Issue(
                    Severity.ERROR,
                    "E302",
                    f"connection-ids-used references unknown connection '{cid_str}'",
                    loc,
                ))
            continue

        if diagram_is_baselined and registry.connection_status(cid_str) == "draft":
            result.issues.append(Issue(
                Severity.ERROR,
                "E307",
                (
                    f"baselined diagram references draft connection '{cid_str}' — "
                    "all connections in a baselined diagram must be baselined"
                ),
                loc,
            ))


def check_puml_structure(content: str, fm: dict, result: VerificationResult, loc: str) -> None:
    if "@startuml" not in content:
        result.issues.append(Issue(Severity.ERROR, "E304", "@startuml marker is missing", loc))
    if "@enduml" not in content:
        result.issues.append(Issue(Severity.ERROR, "E305", "@enduml marker is missing", loc))

    body_lines = [line for line in content.splitlines() if not line.lstrip().startswith("'")]
    has_visible_title = any(re.match(r"^\s*title(\s|$)", line, flags=re.IGNORECASE) for line in body_lines)
    if not has_visible_title:
        result.issues.append(Issue(
            Severity.ERROR,
            "E308",
            "Diagram must include a visible title line (for example: 'title <diagram name>')",
            loc,
        ))

    diagram_type = str(fm.get("diagram-type", ""))
    if "archimate" in diagram_type or "usecase" in diagram_type:
        has_macros = "_macros.puml" in content
        has_stereotypes = "_archimate-stereotypes.puml" in content
        if not has_macros and not has_stereotypes:
            result.issues.append(Issue(
                Severity.ERROR,
                "E303",
                "ArchiMate/use-case diagram must include _macros.puml or _archimate-stereotypes.puml",
                loc,
            ))


def check_diagram_artifact_type(fm: dict, result: VerificationResult, loc: str) -> None:
    check_artifact_type(fm, DIAGRAM_ARTIFACT_TYPES, "diagram artifact type", result, loc)


# ---------------------------------------------------------------------------
# Configurable JSON Schema checks (WS-C)
# ---------------------------------------------------------------------------


def check_frontmatter_schema(
    fm: dict,
    repo_root: Path,
    file_type: str,
    result: VerificationResult,
    loc: str,
) -> None:
    """Validate frontmatter dict against the repo's JSON Schema for *file_type*.

    If no schema file exists for the file type, validation is silently skipped
    (free schema).  Schema errors are reported as warnings (W041) rather than
    hard errors so that repos can adopt schemas incrementally.
    """
    schema = load_frontmatter_schema(repo_root, file_type)
    if schema is None:
        return
    errors = validate_against_schema(fm, schema)
    for msg in errors:
        result.issues.append(Issue(
            Severity.WARNING,
            "W041",
            f"Frontmatter schema ({file_type}): {msg}",
            loc,
        ))


def check_attribute_schema(
    content: str,
    fm: dict,
    repo_root: Path,
    result: VerificationResult,
    loc: str,
) -> None:
    """Validate Properties table attributes against the per-type attribute schema.

    Extracts key-value pairs from the ``## Properties`` markdown table and
    validates them against ``attributes.{artifact-type}.schema.json``.

    If no schema file exists for the entity's artifact-type, validation is
    silently skipped (free schema).
    """
    artifact_type = fm.get("artifact-type", "")
    if not artifact_type:
        return
    schema = load_attribute_schema(repo_root, str(artifact_type))
    if schema is None:
        return
    props = parse_properties_table(content)
    if props is None:
        # No Properties table found — if schema has required fields, report
        required = schema.get("required", [])
        if required:
            result.issues.append(Issue(
                Severity.WARNING,
                "W042",
                f"Attribute schema ({artifact_type}): no Properties table found but schema requires: {required}",
                loc,
            ))
        return
    errors = validate_against_schema(props, schema)
    for msg in errors:
        result.issues.append(Issue(
            Severity.WARNING,
            "W042",
            f"Attribute schema ({artifact_type}): {msg}",
            loc,
        ))


def parse_properties_table(content: str) -> dict[str, str] | None:
    """Extract key-value pairs from the ``## Properties`` markdown table.

    Returns ``None`` if no Properties table is found, or a dict mapping
    attribute names to their values.
    """
    lines = content.splitlines()
    in_table = False
    header_found = False
    props: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## Properties"):
            header_found = True
            continue
        if header_found and not in_table:
            # Skip the table header row and separator
            if stripped.startswith("| Attribute"):
                continue
            if stripped.startswith("|---") or stripped.startswith("| ---"):
                in_table = True
                continue
            if stripped.startswith("##") or stripped.startswith("<!--"):
                # Hit next section without finding table
                break
            continue
        if in_table:
            if not stripped.startswith("|"):
                break
            cells = [c.strip() for c in stripped.split("|")]
            # split on | gives ['', 'key', 'value', ''] for '| key | value |'
            cells = [c for c in cells if c]
            if len(cells) >= 2 and cells[0] != "(none)":
                props[cells[0]] = cells[1]
    if not header_found:
        return None
    return props
