"""Datatype diagram PUML renderer — restricted UML class diagram (no operations).

diagram_entities keys:
  classifier: [{id, label?, classifier_kind?, attributes?: [...], literals?: [...],
                is_abstract?: bool, generalization_set?: {is_covering, is_disjoint}}]

diagram_connections (all with conn_type from the dt-* vocabulary):
  dt-association   — solid line (symmetric)
  dt-aggregation   — hollow diamond at source (whole → part, shared)
  dt-composition   — filled diamond at source (whole → part, exclusive)
  dt-generalization — hollow triangle at target (child → parent)
  dt-dependency    — dashed arrow (source uses/depends-on target)

  Each connection dict: {source, target, conn_type, src_cardinality?,
                         tgt_cardinality?, label?}
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.ontology_protocol import DiagramRendererReferences

_ALIAS_RE = re.compile(r"[^A-Za-z0-9_]")
_NEWLINE_RE = re.compile(r"\r?\n|\r")

# dt-* conn_type → PlantUML arrow string
_PUML_ARROWS: dict[str, str] = {
    "dt-association": "--",
    "dt-aggregation": "o--",
    "dt-composition": "*--",
    "dt-generalization": "--|>",
    "dt-dependency": "..>",
}

# classifier_kind → (puml keyword, stereotype label or None)
_KIND_META: dict[str, tuple[str, str | None]] = {
    "class": ("class", None),
    "datatype": ("class", "datatype"),
    "enumeration": ("enum", None),
    "variant": ("abstract class", "variant"),
    "primitive": ("class", "primitive"),
}


def _safe_alias(raw_id: str) -> str:
    return "_" + _ALIAS_RE.sub("_", raw_id)


def _safe_text(text: str) -> str:
    return _NEWLINE_RE.sub(" ", text)


def _render_classifier(c: dict[str, Any]) -> list[str]:
    eid = str(c.get("id") or "")
    label = _safe_text(str(c.get("label") or eid))
    kind = str(c.get("classifier_kind") or "class")
    alias = _safe_alias(eid)
    keyword, stereotype = _KIND_META.get(kind, ("class", None))

    head_parts = [keyword, f'"{label}"']
    if stereotype:
        head_parts.append(f"<<{stereotype}>>")
    head_parts.append(f"as {alias}")
    lines: list[str] = [" ".join(head_parts) + " {"]

    if kind == "enumeration":
        for lit in (c.get("literals") or []):
            lines.append(f"  {_safe_text(str(lit))}")
    else:
        for attr in (c.get("attributes") or []):
            if not isinstance(attr, dict):
                continue
            name = str(attr.get("name") or "")
            atype = str(attr.get("type") or "")
            mult = str(attr.get("multiplicity") or "")
            is_id = bool(attr.get("is_id"))
            is_unique = bool(attr.get("is_unique"))
            parts: list[str] = [f"  + {name}"]
            if atype:
                parts.append(f" : {atype}")
            if mult:
                parts.append(f" [{mult}]")
            if is_id:
                parts.append(" {id}")
            if is_unique:
                parts.append(" {unique}")
            lines.append("".join(parts))

    lines.append("}")
    constraints = [
        ", ".join(str(name) for name in constraint)
        for constraint in (c.get("unique_constraints") or [])
        if isinstance(constraint, list) and constraint
    ]
    if constraints:
        lines.extend((
            f"note right of {alias}",
            *[f"{{unique({constraint})}}" for constraint in constraints],
            "end note",
        ))
    note = _safe_text(str(c.get("note") or "")).strip()
    if note:
        lines.extend((f"note right of {alias}", note, "end note"))
    return lines


def _render_connection(kc: dict[str, Any]) -> list[str]:
    src = _safe_alias(str(kc.get("source") or ""))
    tgt = _safe_alias(str(kc.get("target") or ""))
    conn_type = str(kc.get("conn_type") or "dt-association")
    arrow = _PUML_ARROWS.get(conn_type, "--")
    src_card = str(kc.get("src_cardinality") or "")
    tgt_card = str(kc.get("tgt_cardinality") or "")
    label = _safe_text(str(kc.get("label") or ""))

    src_part = f' "{src_card}"' if src_card else ""
    tgt_part = f'"{tgt_card}" ' if tgt_card else ""
    label_part = f" : {label}" if label else ""

    lines = [f"{src}{src_part} {arrow} {tgt_part}{tgt}{label_part}"]
    note = _safe_text(str(kc.get("note") or "")).strip()
    if note:
        lines.extend(("note on link", note, "end note"))
    return lines


class DatatypePumlRenderer:
    def __init__(self, config: Mapping[str, Any]) -> None:
        self._config = dict(config)

    def render_body(
        self,
        name: str,
        entities: Sequence[EntityRecord],
        connections: Sequence[ConnectionRecord],
        diagram_type: str,
        repo_root: Path,
        *,
        diagram_entities: Mapping[str, object] | None = None,
        diagram_connections: list[dict[str, object]] | None = None,
    ) -> str:
        del entities, connections, diagram_type, repo_root
        kd = diagram_entities or {}
        raw_cls = kd.get("classifier")
        classifiers: list[dict[str, Any]] = [
            c for c in (raw_cls if isinstance(raw_cls, (list, tuple)) else [])
            if isinstance(c, dict)
        ]
        kcs: list[dict[str, Any]] = [
            kc for kc in (diagram_connections or []) if isinstance(kc, dict)
        ]

        lines: list[str] = [
            f"@startuml {_safe_text(name)}",
            "skinparam linetype ortho",
            "",
        ]
        for c in classifiers:
            lines.extend(_render_classifier(c))
            lines.append("")
        for kc in kcs:
            if kc.get("conn_type") in _PUML_ARROWS:
                lines.extend(_render_connection(kc))
        lines += ["", "@enduml"]
        return "\n".join(lines)

    def inject_includes(self, body: str, repo_root: Path) -> str:
        del repo_root
        return body

    def collect_references(
        self,
        diagram_type: str,
        repo_root: Path,
        *,
        diagram_entities: Mapping[str, object] | None = None,
        diagram_connections: list[dict[str, object]] | None = None,
        bindings: list[dict[str, object]] | None = None,
    ) -> DiagramRendererReferences:
        del diagram_type, repo_root, diagram_entities, diagram_connections
        entity_ids: list[str] = []
        conn_ids: list[str] = []
        for b in bindings or []:
            if not isinstance(b, dict):
                continue
            target = b.get("target")
            if not isinstance(target, dict):
                continue
            eid = target.get("entity_id")
            cid = target.get("connection_id")
            if eid and str(eid) not in entity_ids:
                entity_ids.append(str(eid))
            if cid and str(cid) not in conn_ids:
                conn_ids.append(str(cid))
        return DiagramRendererReferences(
            entity_ids=tuple(entity_ids),
            connection_ids=tuple(conn_ids),
        )
