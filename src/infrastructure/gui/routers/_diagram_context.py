"""Diagram context-building helpers for the diagram GUI router."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from src.application.artifact_parsing import extract_declared_puml_aliases, normalize_puml_alias
from src.domain.artifact_types import DiagramRecord, EntityRecord
from src.domain.ontology_loader import DOMAIN_ORDER as _DOMAIN_ORDER
from src.infrastructure.gui.routers import state as s


def declared_aliases_in_puml(puml: str) -> set[str]:
    return extract_declared_puml_aliases(puml)


def puml_contains(d: DiagramRecord, *aliases: str) -> bool:
    try:
        puml = d.path.read_text(encoding="utf-8")
        return all(normalize_puml_alias(a) in declared_aliases_in_puml(puml) for a in aliases)
    except OSError:
        return False


def entity_display_item(rec: EntityRecord) -> dict[str, Any]:
    import yaml as _yaml

    arch_data: dict[str, Any] = {}
    arch_block = rec.display_blocks.get("archimate", "")
    if arch_block:
        try:
            arch_data = _yaml.safe_load(arch_block) or {}
        except Exception:  # noqa: BLE001
            arch_data = {}
    return {
        "artifact_id": rec.artifact_id,
        "name": rec.name,
        "artifact_type": rec.artifact_type,
        "domain": rec.domain,
        "subdomain": rec.subdomain,
        "status": rec.status,
        "display_alias": rec.display_alias,
        "element_type": arch_data.get("element-type", ""),
        "element_label": arch_data.get("label", rec.name),
    }


def diagram_entities_and_puml(repo: Any, diag_rec: DiagramRecord) -> tuple[list[dict[str, Any]], str]:
    try:
        puml = diag_rec.path.read_text(encoding="utf-8")
    except OSError:
        return [], ""
    aliases = declared_aliases_in_puml(puml)
    entities = []
    for rec in repo.list_entities():
        if rec.display_alias and normalize_puml_alias(rec.display_alias) in aliases:
            row = s.entity_to_summary(rec)
            row["display_alias"] = rec.display_alias
            entities.append(row)
    entities.sort(
        key=lambda e: (
            _DOMAIN_ORDER.index(e["domain"]) if e["domain"] in _DOMAIN_ORDER else 99,
            e["name"],
        )
    )
    return entities, puml


def candidate_connections_for_entities(repo: Any, entity_ids: list[str]) -> list[dict[str, Any]]:
    return repo.candidate_connections_for_entities(entity_ids)


def parse_explicit_connection_pairs(puml: str) -> set[tuple[str, str]]:
    """Return (src_alias, tgt_alias) pairs for visible connection lines in PUML."""
    _conn_re = re.compile(
        r"^\s*(\w+)\s+"
        r"([-.*|o<>][^\s]*[-.*|o<>])"
        r"\s+(\w+)"
    )
    _macro_re = re.compile(
        r"^\s*Rel_[A-Za-z0-9]+(?:_(?:Up|Down|Left|Right))?"
        r"\(\s*(\w+)\s*,\s*(\w+)"
    )
    pairs: set[tuple[str, str]] = set()
    for line in puml.splitlines():
        stripped = line.strip()
        if stripped.startswith("'") or "[hidden]" in stripped:
            continue
        m = _conn_re.match(line)
        if m:
            pairs.add((normalize_puml_alias(m.group(1)), normalize_puml_alias(m.group(3))))
            continue
        macro = _macro_re.match(line)
        if macro:
            pairs.add((normalize_puml_alias(macro.group(1)), normalize_puml_alias(macro.group(2))))
    return pairs


def diagram_context_payload(repo: Any, diag_rec: DiagramRecord) -> dict[str, Any]:
    from src.infrastructure.gui.routers.diagrams import read_diagram

    version = repo.read_model_version()
    diagram = read_diagram(diag_rec.artifact_id)
    entities, puml = diagram_entities_and_puml(repo, diag_rec)
    entity_ids = [str(entity["artifact_id"]) for entity in entities]
    in_diagram = {
        str(entity["artifact_id"]): rec
        for entity in entities
        if (rec := repo.get_entity(str(entity["artifact_id"]))) is not None
    }
    explicit_pairs = parse_explicit_connection_pairs(puml)
    connections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for conn in repo.list_connections():
        if conn.artifact_id in seen:
            continue
        src = in_diagram.get(conn.source)
        tgt = in_diagram.get(conn.target)
        if src is None or tgt is None:
            continue
        sa = normalize_puml_alias(src.display_alias or "")
        ta = normalize_puml_alias(tgt.display_alias or "")
        if (sa, ta) not in explicit_pairs and (ta, sa) not in explicit_pairs:
            continue
        d = s.connection_to_dict(conn)
        d["source_name"] = src.name
        d["target_name"] = tgt.name
        d["source_alias"] = sa
        d["target_alias"] = ta
        connections.append(d)
        seen.add(conn.artifact_id)
    return {
        "diagram": diagram,
        "entities": entities,
        "connections": connections,
        "candidate_connections": candidate_connections_for_entities(repo, entity_ids),
        "suggested_entities": hop_suggestions(repo, entity_ids, max_hops=2, limit_per_hop=25),
        "explicit_connection_pairs": [list(pair) for pair in sorted(explicit_pairs)],
        "generation": version.generation,
        "etag": version.etag,
    }


def hop_suggestions(repo: Any, entity_ids: list[str], *, max_hops: int, limit_per_hop: int) -> list[dict[str, Any]]:
    frontier = set(entity_ids)
    visited = set(entity_ids)
    groups: list[dict[str, Any]] = []
    for hop in range(1, max(max_hops, 0) + 1):
        next_frontier: set[str] = set()
        for entity_id in frontier:
            context = repo.read_entity_context(entity_id)
            if context is None:
                continue
            for bucket in ("outbound", "inbound", "symmetric"):
                for conn in context["connections"][bucket]:
                    other_id = str(conn["other_entity_id"])
                    if other_id not in visited:
                        next_frontier.add(other_id)
        next_frontier.difference_update(visited)
        if not next_frontier:
            break
        items = [
            entity_display_item(rec)
            for entity_id in sorted(next_frontier)
            if (rec := repo.get_entity(entity_id)) is not None and rec.artifact_type != "global-artifact-reference"
        ]
        items.sort(
            key=lambda item: (
                _DOMAIN_ORDER.index(item["domain"]) if item["domain"] in _DOMAIN_ORDER else 99,
                item["name"],
            )
        )
        if items:
            groups.append({"hop": hop, "items": items[:limit_per_hop]})
        visited.update(next_frontier)
        frontier = next_frontier
    return groups


def fuzzy_entity_hits(repo: Any, q: str, limit: int, excluded: set[str]) -> list[dict[str, Any]]:
    query = q.strip().lower()
    if not query or limit <= 0:
        return []
    scored: list[tuple[float, EntityRecord]] = []
    for rec in repo.list_entities():
        if rec.artifact_type == "global-artifact-reference" or rec.artifact_id in excluded:
            continue
        haystack = " ".join((rec.name, rec.artifact_type, rec.domain, rec.subdomain, rec.content_text[:400]))
        score = SequenceMatcher(None, query, haystack.lower()).ratio()
        if score >= 0.35:
            scored.append((score, rec))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [entity_display_item(rec) for _, rec in scored[:limit]]
