"""JSON Schema and attribute validation rules."""
from __future__ import annotations
from pathlib import Path
from src.common.artifact_verifier_types import Issue, Severity, VerificationResult
from src.common.artifact_schema import (
    load_attribute_schema, load_frontmatter_schema, validate_against_schema,
)

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


# ---------------------------------------------------------------------------
