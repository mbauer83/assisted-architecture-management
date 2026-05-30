"""Sequence diagram PUML renderer — PlantUML sequence syntax.

diagram_entities keys:
  lifeline:       [{id, label?}]
  message:        [{id, label?, sequence_index, arrow_style?}]
  fragment:       [{id, kind, from_index, to_index, condition?}]
  execution-spec: [{id, lifeline_id, from_index, to_index}]
  note:           [{id, text, side?}]

diagram_connections:
  seq-from:     message → lifeline (source lifeline)
  seq-to:       message → lifeline (target lifeline)
  seq-note-of:  note → lifeline
  seq-message:  lifeline → lifeline (direct edge without message entity)
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.ontology_protocol import DiagramRendererReferences

_ARROW_MAP = {
    "sync": "->",
    "async": "->>",
    "reply": "-->",
    "create": "->",
    "destroy": "->",
    "": "->",
}


class SequencePumlRenderer:
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
        del diagram_type, entities, connections
        diagram_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower()).strip("-") or "sequence"
        kd = diagram_entities or {}
        kcs = diagram_connections or []

        lifelines = _read_list(kd, "lifeline")
        messages = sorted(_read_list(kd, "message"), key=lambda m: int(m.get("sequence_index") or 0))
        fragments = sorted(_read_list(kd, "fragment"), key=lambda f: int(f.get("from_index") or 0))
        exec_specs = _read_list(kd, "execution-spec")

        alias_map = {ll["id"]: f"LL{i + 1}" for i, ll in enumerate(lifelines) if ll.get("id")}
        from_map = _build_single(kcs, "seq-from")   # msg_id → lifeline_id
        to_map = _build_single(kcs, "seq-to")       # msg_id → lifeline_id
        note_map = _build_single(kcs, "seq-note-of")  # note_id → lifeline_id

        # activation tracking: lifeline_id → sorted list of (from_idx, to_idx) specs
        active_ranges: dict[str, list[tuple[int, int]]] = {}
        for es in exec_specs:
            ll_id = str(es.get("lifeline_id") or "")
            if ll_id:
                f, t = int(es.get("from_index") or 0), int(es.get("to_index") or 0)
                active_ranges.setdefault(ll_id, []).append((f, t))

        lines: list[str] = [f"@startuml {diagram_name}", f"title {_puml_text(name)}", ""]

        for ll in lifelines:
            ll_id = str(ll.get("id") or "")
            alias = alias_map.get(ll_id, ll_id)
            label = str(ll.get("label") or ll_id)
            lines.append(f'participant "{_puml_text(label)}" as {alias}')

        _emit_notes(kd, note_map, alias_map, lines)
        if lifelines:
            lines.append("")

        _emit_messages(messages, fragments, active_ranges, from_map, to_map, alias_map, lines)

        lines.append("")
        lines.append("@enduml")
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
        for b in (bindings or []):
            if not isinstance(b, dict):
                continue
            target = b.get("target")
            if not isinstance(target, dict):
                continue
            eid = target.get("entity_id")
            if eid and str(eid) not in entity_ids:
                entity_ids.append(str(eid))
            cid = target.get("connection_id")
            if cid and str(cid) not in conn_ids:
                conn_ids.append(str(cid))
            for cid2 in (target.get("connection_ids") or []):
                if cid2 and str(cid2) not in conn_ids:
                    conn_ids.append(str(cid2))
        return DiagramRendererReferences(entity_ids=tuple(entity_ids), connection_ids=tuple(conn_ids))


# ── Helpers ───────────────────────────────────────────────────────────────────


def _read_list(kd: Mapping[str, object], key: str) -> list[dict[str, Any]]:
    raw = kd.get(key)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict) and item.get("id")]


def _build_single(kcs: list[dict[str, object]], conn_type: str) -> dict[str, str]:
    return {
        str(kc["source"]): str(kc["target"])
        for kc in kcs
        if isinstance(kc, dict)
        and kc.get("conn_type") == conn_type
        and kc.get("source") and kc.get("target")
    }


def _emit_notes(
    kd: Mapping[str, object],
    note_map: dict[str, str],
    alias_map: dict[str, str],
    lines: list[str],
) -> None:
    notes = _read_list(kd, "note")
    if not notes:
        return
    lines.append("")
    for note in notes:
        note_id = str(note.get("id") or "")
        ll_id = note_map.get(note_id, "")
        alias = alias_map.get(ll_id, ll_id) if ll_id else ""
        side = str(note.get("side") or "right")
        if side not in ("left", "right"):
            side = "right"
        text = str(note.get("text") or "")
        if not text:
            continue
        if alias:
            lines.append(f"note {side} of {alias}: {_puml_text(text)}")
        else:
            lines.append(f"note {side}: {_puml_text(text)}")


def _emit_messages(
    messages: list[dict[str, Any]],
    fragments: list[dict[str, Any]],
    active_ranges: dict[str, list[tuple[int, int]]],
    from_map: dict[str, str],
    to_map: dict[str, str],
    alias_map: dict[str, str],
    lines: list[str],
) -> None:
    # Build fragment open/close events keyed by message sequence_index
    frag_open: dict[int, list[dict[str, Any]]] = {}
    frag_close: dict[int, list[dict[str, Any]]] = {}
    for frag in fragments:
        fi = int(frag.get("from_index") or 0)
        ti = int(frag.get("to_index") or 0)
        frag_open.setdefault(fi, []).append(frag)
        frag_close.setdefault(ti, []).append(frag)

    # Build activation open/close events keyed by message index
    act_open: dict[int, list[str]] = {}
    act_close: dict[int, list[str]] = {}
    for ll_id, ranges in active_ranges.items():
        for fi, ti in ranges:
            act_open.setdefault(fi, []).append(ll_id)
            act_close.setdefault(ti, []).append(ll_id)

    for msg in messages:
        msg_id = str(msg.get("id") or "")
        idx = int(msg.get("sequence_index") or 0)

        for frag in frag_open.get(idx, []):
            kind = str(frag.get("kind") or "opt")
            cond = str(frag.get("condition") or "")
            header = f"{kind}" + (f" [{_puml_text(cond)}]" if cond else "")
            lines.append(header)

        for ll_id in act_open.get(idx, []):
            alias = alias_map.get(ll_id, ll_id)
            lines.append(f"activate {alias}")

        src_ll = from_map.get(msg_id, "")
        tgt_ll = to_map.get(msg_id, "")
        src_alias = alias_map.get(src_ll, src_ll)
        tgt_alias = alias_map.get(tgt_ll, tgt_ll)
        arrow = _ARROW_MAP.get(str(msg.get("arrow_style") or ""), "->")
        label = _puml_text(str(msg.get("label") or ""))
        if src_alias and tgt_alias:
            lines.append(f"{src_alias} {arrow} {tgt_alias}: {label}")
        elif label:
            lines.append(f"' {label}")

        for ll_id in act_close.get(idx, []):
            alias = alias_map.get(ll_id, ll_id)
            lines.append(f"deactivate {alias}")

        for _frag in frag_close.get(idx, []):
            lines.append("end")


def _puml_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", " ").replace("|", "/")
