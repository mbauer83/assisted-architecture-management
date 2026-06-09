"""JSON Schema and attribute validation rules."""

from __future__ import annotations

from pathlib import Path

from src.application.artifact_schema import (
    load_attribute_schema,
    load_frontmatter_schema,
    validate_against_schema,
)
from src.application.verification.artifact_verifier_types import Issue, Severity, VerificationResult

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
        result.issues.append(
            Issue(
                Severity.WARNING,
                "W041",
                f"Frontmatter schema ({file_type}): {msg}",
                loc,
            )
        )


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
            result.issues.append(
                Issue(
                    Severity.WARNING,
                    "W042",
                    (f"Attribute schema ({artifact_type}): no Properties table found but schema requires: {required}"),
                    loc,
                )
            )
        return
    errors = validate_against_schema(props, schema)
    for msg in errors:
        result.issues.append(
            Issue(
                Severity.WARNING,
                "W042",
                f"Attribute schema ({artifact_type}): {msg}",
                loc,
            )
        )


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
# Module source-path existence check (W160)
# ---------------------------------------------------------------------------


def _find_source_root(path: Path) -> Path | None:
    """Return the first ancestor of *path* that contains a ``src/`` subdirectory."""
    for parent in path.parents:
        if (parent / "src").is_dir():
            return parent
    return None


def check_module_source_path(
    content: str,
    file_path: Path,
    result: VerificationResult,
    loc: str,
) -> None:
    """Warn (W160) when a ``Module:`` property in the Properties table points at a
    source path that does not exist on disk.

    Silently skips when the entity has no ``Module:`` property, or when no
    ancestor directory containing ``src/`` can be found (the architecture repo
    is not co-located with the source tree).
    """
    props = parse_properties_table(content)
    if not props:
        return
    module_val = props.get("Module", "").strip()
    if not module_val:
        return
    source_root = _find_source_root(file_path)
    if source_root is None:
        return
    if not (source_root / module_val).exists():
        result.issues.append(
            Issue(
                Severity.WARNING,
                "W160",
                f"Module property references non-existent source path: '{module_val}'",
                loc,
            )
        )


# ---------------------------------------------------------------------------
