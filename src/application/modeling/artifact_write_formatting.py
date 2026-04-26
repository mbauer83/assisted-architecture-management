import re
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from src.application.artifact_schema import (
    load_attribute_schema,
    schema_all_properties,
    schema_required_properties,
)


def _dump_yaml_text(data: object) -> str:
    dumped = yaml.safe_dump(data, sort_keys=False)
    if not isinstance(dumped, str):
        raise TypeError("yaml.safe_dump returned non-string output")
    return dumped.strip()


def format_entity_markdown(
    *,
    artifact_id: str,
    artifact_type: str,
    name: str,
    version: str,
    status: str,
    last_updated: str,
    keywords: list[str] | None = None,
    summary: str | None,
    properties: dict[str, str] | None,
    notes: str | None,
    display_archimate: dict[str, str],
    repo_root: Path | None = None,
    extra_frontmatter: dict[str, object] | None = None,
) -> str:
    frontmatter: dict[str, object] = {
        "artifact-id": artifact_id,
        "artifact-type": artifact_type,
        "name": name,
        "version": version,
        "status": status,
    }
    if keywords:
        frontmatter["keywords"] = keywords
    frontmatter["last-updated"] = last_updated

    ordered_keys = [
        "artifact-id",
        "artifact-type",
        "name",
        "version",
        "status",
        "keywords",
        "last-updated",
    ]
    fm_out = {key: frontmatter[key] for key in ordered_keys if key in frontmatter}
    if extra_frontmatter:
        fm_out.update(extra_frontmatter)

    content_lines: list[str] = ["<!-- §content -->", "", f"## {name}", ""]
    if summary:
        content_lines.append(summary.strip())
        content_lines.append("")

    content_lines.extend(["## Properties", "", "| Attribute | Value |", "|---|---|"])
    props = properties or {}
    schema_keys = _scaffold_keys_from_schema(repo_root, artifact_type) if repo_root else []
    if props:
        for key in sorted(props.keys()):
            content_lines.append(f"| {key} | {props[key]} |")
        # Append any schema-required keys not already provided
        for key in schema_keys:
            if key not in props:
                content_lines.append(f"| {key} | |")
    elif schema_keys:
        for key in schema_keys:
            content_lines.append(f"| {key} | |")
    else:
        content_lines.append("| (none) | (none) |")
    content_lines.append("")

    if notes and notes.strip():
        content_lines.extend(["## Notes", "", notes.strip(), ""])

    display_yaml = _dump_yaml_text(display_archimate)
    display_lines = [
        "<!-- §display -->",
        "",
        "### archimate",
        "",
        "```yaml",
        display_yaml,
        "```",
    ]
    frontmatter_text = _dump_yaml_text(fm_out)
    return (
        "---\n"
        + frontmatter_text
        + "\n---\n\n"
        + "\n".join(content_lines)
        + "\n\n"
        + "\n".join(display_lines)
        + "\n"
    )


def format_outgoing_markdown(
    *,
    source_entity: str,
    version: str,
    status: str,
    last_updated: str,
    connections: list[dict[str, object]],
) -> str:
    """Format an .outgoing.md file.

    Each entry in *connections* should have keys:
      - ``connection_type``: e.g. ``archimate-realization``
      - ``target_entity``: target artifact-id
      - ``description``: prose description of the relationship (optional)
      - ``src_cardinality``: source-end cardinality (optional, e.g. "1", "0..1", "1..*", "*")
      - ``tgt_cardinality``: target-end cardinality (optional, same format)

    Header format:  ### conn-type [src_card] → [tgt_card] target_id
    Both cardinality parts are omitted when absent.  Cardinalities are not
    permitted on junction connections.
    """
    frontmatter = {
        "source-entity": source_entity,
        "version": version,
        "status": status,
        "last-updated": last_updated,
    }
    frontmatter_text = _dump_yaml_text(frontmatter)

    sections: list[str] = ["<!-- §connections -->"]
    for conn in connections:
        conn_type = str(conn["connection_type"])
        target = str(conn["target_entity"])
        desc = str(conn.get("description", "")).strip()
        src_card = str(conn.get("src_cardinality", "")).strip()
        tgt_card = str(conn.get("tgt_cardinality", "")).strip()

        src_part = f" [{src_card}]" if src_card else ""
        tgt_part = f"[{tgt_card}] " if tgt_card else ""
        sections.append("")
        sections.append(f"### {conn_type}{src_part} → {tgt_part}{target}")
        if desc:
            sections.append("")
            sections.append(desc)
        assoc_ids = conn.get("associated_entities")
        if isinstance(assoc_ids, list):
            for assoc_id in assoc_ids:
                sections.append(f"<!-- §assoc {assoc_id} -->")

    return "---\n" + frontmatter_text + "\n---\n\n" + "\n".join(sections) + "\n"


def format_diagram_puml(
    *,
    artifact_id: str,
    diagram_type: str,
    name: str,
    version: str,
    status: str,
    last_updated: str,
    keywords: list[str] | None = None,
    entity_ids_used: list[str] | None = None,
    connection_ids_used: list[str] | None = None,
    puml_body: str,
) -> str:
    frontmatter: dict[str, object] = {
        "artifact-id": artifact_id,
        "artifact-type": "diagram",
        "name": name,
        "version": version,
        "status": status,
    }
    if keywords:
        frontmatter["keywords"] = keywords
    frontmatter["diagram-type"] = diagram_type
    if entity_ids_used:
        frontmatter["entity-ids-used"] = entity_ids_used
    if connection_ids_used:
        frontmatter["connection-ids-used"] = connection_ids_used
    frontmatter["last-updated"] = last_updated

    ordered_keys = [
        "artifact-id",
        "artifact-type",
        "name",
        "version",
        "status",
        "keywords",
        "diagram-type",
        "entity-ids-used",
        "connection-ids-used",
        "last-updated",
    ]
    fm_out = {key: frontmatter[key] for key in ordered_keys if key in frontmatter}
    yaml_text = _dump_yaml_text(fm_out)

    body = _ensure_visible_title(puml_body, name)
    return f"---\n{yaml_text}\n---\n{body}"


def _ensure_visible_title(puml_body: str, title_text: str) -> str:
    lines = puml_body.strip("\n").splitlines()
    if not lines:
        return puml_body.strip("\n") + "\n"

    has_title = any(
        (not line.lstrip().startswith("'"))
        and re.match(r"^\s*title(\s|$)", line, flags=re.IGNORECASE)
        for line in lines
    )
    if has_title:
        return puml_body.strip("\n") + "\n"

    start_idx = next((i for i, line in enumerate(lines) if line.strip().startswith("@startuml")), 0)
    insert_idx = start_idx + 1
    for i in range(start_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("'"):
            continue
        if stripped.lower().startswith("!include"):
            insert_idx = i + 1
            continue
        break

    lines.insert(insert_idx, f"title {title_text}")
    return "\n".join(lines) + "\n"


def format_matrix_markdown(
    *,
    artifact_id: str,
    name: str,
    version: str,
    status: str,
    last_updated: str,
    keywords: list[str] | None = None,
    matrix_markdown: str,
    entity_ids: list[str] | None = None,
    from_entity_ids: list[str] | None = None,
    to_entity_ids: list[str] | None = None,
    conn_type_configs: list[dict[str, object]] | None = None,
    combined: bool | None = None,
) -> str:
    frontmatter: dict[str, object] = {
        "artifact-id": artifact_id,
        "artifact-type": "diagram",
        "diagram-type": "matrix",
        "name": name,
        "version": version,
        "status": status,
    }
    if keywords:
        frontmatter["keywords"] = keywords
    frontmatter["last-updated"] = last_updated
    if from_entity_ids is not None:
        frontmatter["from-entity-ids"] = from_entity_ids
        frontmatter["to-entity-ids"] = to_entity_ids or []
    elif entity_ids:
        frontmatter["entity-ids"] = entity_ids
    if conn_type_configs:
        frontmatter["conn-type-configs"] = conn_type_configs
    if combined is not None:
        frontmatter["combined"] = combined

    ordered_keys = [
        "artifact-id",
        "artifact-type",
        "diagram-type",
        "name",
        "version",
        "status",
        "keywords",
        "last-updated",
        "entity-ids",
        "from-entity-ids",
        "to-entity-ids",
        "conn-type-configs",
        "combined",
    ]
    fm_out = {key: frontmatter[key] for key in ordered_keys if key in frontmatter}
    yaml_text = _dump_yaml_text(fm_out)
    body = matrix_markdown.strip("\n") + "\n"
    return f"---\n{yaml_text}\n---\n\n{body}"


def _scaffold_keys_from_schema(repo_root: Path | None, artifact_type: str) -> list[str]:
    """Return ordered attribute keys from the attribute schema for scaffolding.

    Required keys come first, then optional keys.  Returns an empty list
    when no schema is configured (free schema).
    """
    if repo_root is None:
        return []
    schema = load_attribute_schema(repo_root, artifact_type)
    if schema is None:
        return []
    required = schema_required_properties(schema)
    all_props = schema_all_properties(schema)
    optional = [k for k in all_props if k not in required]
    return required + optional
