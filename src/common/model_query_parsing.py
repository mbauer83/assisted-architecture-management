
import re
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from src.common.model_verifier import entity_id_from_path
from src.common.model_query_types import (
    ConnectionRecord,
    DiagramRecord,
    Domain,
    DOMAIN_NAMES,
    EntityRecord,
    STANDARD_DIAGRAM_FIELDS,
    STANDARD_ENTITY_FIELDS,
    STANDARD_OUTGOING_FIELDS,
)


def extract_yaml_block(content: str) -> dict | None:
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    try:
        return yaml.safe_load(content[3:end].strip()) or {}
    except yaml.YAMLError:
        return None



def extract_section(content: str, marker: str) -> str:
    start_tag = f"<!-- §{marker} -->"
    start = content.find(start_tag)
    if start == -1:
        return ""
    body_start = start + len(start_tag)
    next_tag = re.search(r"<!-- §\w+ -->", content[body_start:])
    if next_tag:
        return content[body_start : body_start + next_tag.start()].strip()
    return content[body_start:].strip()


def extract_display_blocks(content: str) -> dict[str, str]:
    display_body = extract_section(content, "display")
    if not display_body:
        return {}

    blocks: dict[str, str] = {}
    parts = re.split(r"^###\s+(.+)$", display_body, flags=re.MULTILINE)
    iterator = iter(parts[1:])
    for lang, body in zip(iterator, iterator):
        blocks[lang.strip()] = body.strip()
    return blocks


def derive_domain(path: Path, root: Path) -> tuple[Domain, str]:
    try:
        rel = path.relative_to(root)
        parts = rel.parts
        domain_raw = parts[0] if len(parts) > 0 else "unknown"
        subdomain = parts[1] if len(parts) > 1 else ""
        domain: Domain = domain_raw if domain_raw in DOMAIN_NAMES else "unknown"  # type: ignore[assignment]
        return domain, subdomain
    except ValueError:
        return "unknown", ""


def extract_archimate_label_alias(display_blocks: dict[str, str]) -> tuple[str, str]:
    archimate_block = display_blocks.get("archimate", "")
    if not archimate_block:
        return "", ""
    block = re.sub(r"```\w*\s*|\s*```", " ", archimate_block)
    label_match = re.search(r"label:\s*[\"']?([^\"'\n]+)[\"']?", block)
    alias_match = re.search(r"alias:\s*([A-Za-z0-9_-]+)", block)
    label = label_match.group(1).strip() if label_match else ""
    alias = alias_match.group(1).strip().replace("-", "_") if alias_match else ""
    return label, alias


def normalize_puml_alias(alias: str) -> str:
    return alias.strip().replace("-", "_")


def extract_declared_puml_aliases(content: str) -> set[str]:
    aliases: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("'"):
            continue
        # Match "as ALIAS" optionally followed by "{" (composite/container entity declarations)
        m = re.search(r"\bas\s+([A-Za-z0-9_-]+)\s*\{?\s*$", stripped)
        if m:
            aliases.add(normalize_puml_alias(m.group(1)))
    return aliases


def parse_entity(path: Path, model_root: Path) -> EntityRecord | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter = extract_yaml_block(content)
    if not frontmatter:
        return None

    domain, subdomain = derive_domain(path, model_root)
    display_blocks = extract_display_blocks(content)
    display_label, display_alias = extract_archimate_label_alias(display_blocks)

    kw_raw = frontmatter.get("keywords") or []
    keywords: tuple[str, ...] = tuple(str(k) for k in kw_raw) if isinstance(kw_raw, list) else ()

    return EntityRecord(
        artifact_id=str(frontmatter.get("artifact-id", entity_id_from_path(path))),
        artifact_type=str(frontmatter.get("artifact-type", "")),
        name=str(frontmatter.get("name", "")),
        version=str(frontmatter.get("version", "")),
        status=str(frontmatter.get("status", "draft")),
        domain=domain,
        subdomain=subdomain,
        keywords=keywords,
        path=path,
        extra={key: value for key, value in frontmatter.items() if key not in STANDARD_ENTITY_FIELDS},
        content_text=extract_section(content, "content"),
        display_blocks=display_blocks,
        display_label=display_label,
        display_alias=display_alias,
    )


_CONN_HEADER_RE = re.compile(
    r"^###\s+(\S+)"                  # conn_type
    r"(?:\s+\[([^\]]+)\])?"          # optional [src_card]
    r"\s+→\s+"                       # arrow
    r"(?:\[([^\]]+)\]\s+)?"          # optional [tgt_card]
    r"(.+)$",                        # target_id
    re.MULTILINE,
)
_ASSOC_RE = re.compile(r"<!--\s*§assoc\s+(\S+)\s*-->")


def parse_outgoing_file(path: Path) -> list[ConnectionRecord]:
    """Parse an .outgoing.md file into individual ConnectionRecord entries."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []

    frontmatter = extract_yaml_block(content)
    if not frontmatter:
        return []

    source_entity = str(frontmatter.get("source-entity", ""))
    version = str(frontmatter.get("version", ""))
    status = str(frontmatter.get("status", "draft"))
    extra = {k: v for k, v in frontmatter.items() if k not in STANDARD_OUTGOING_FIELDS}

    records: list[ConnectionRecord] = []
    headers = list(_CONN_HEADER_RE.finditer(content))
    for i, m in enumerate(headers):
        conn_type = m.group(1).strip()
        src_card = (m.group(2) or "").strip()
        tgt_card = (m.group(3) or "").strip()
        target = m.group(4).strip()
        body_start = m.end()
        body_end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        body = content[body_start:body_end].strip()
        assoc = tuple(_ASSOC_RE.findall(body))
        clean_body = _ASSOC_RE.sub("", body).strip()

        artifact_id = f"{source_entity}---{target}@@{conn_type}"
        records.append(ConnectionRecord(
            artifact_id=artifact_id,
            source=source_entity,
            target=target,
            conn_type=conn_type,
            version=version,
            status=status,
            path=path,
            extra=extra,
            content_text=clean_body,
            associated_entities=assoc,
            src_cardinality=src_card,
            tgt_cardinality=tgt_card,
        ))
    return records


def parse_diagram(path: Path) -> DiagramRecord | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter = extract_yaml_block(content)
    if not frontmatter:
        return None

    return DiagramRecord(
        artifact_id=str(frontmatter.get("artifact-id", path.stem)),
        artifact_type=str(frontmatter.get("artifact-type", "diagram")),
        name=str(frontmatter.get("name", "")),
        diagram_type=str(frontmatter.get("diagram-type", "")),
        version=str(frontmatter.get("version", "")),
        status=str(frontmatter.get("status", "draft")),
        path=path,
        extra={key: value for key, value in frontmatter.items() if key not in STANDARD_DIAGRAM_FIELDS},
    )
