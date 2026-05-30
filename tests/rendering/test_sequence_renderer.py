from __future__ import annotations

from pathlib import Path

from src.diagram_types.sequence.renderer import SequencePumlRenderer


def _r(**kwargs: object) -> SequencePumlRenderer:
    return SequencePumlRenderer(dict(kwargs))


def _msg(msg_id: str, label: str, idx: int, arrow_style: str | None = None) -> dict[str, object]:
    m: dict[str, object] = {"id": msg_id, "label": label, "sequence_index": idx}
    if arrow_style:
        m["arrow_style"] = arrow_style
    return m


def _seq_from(msg_id: str, ll_id: str) -> dict[str, object]:
    return {"id": f"kc-from-{msg_id}", "conn_type": "seq-from", "source": msg_id, "target": ll_id}


def _seq_to(msg_id: str, ll_id: str) -> dict[str, object]:
    return {"id": f"kc-to-{msg_id}", "conn_type": "seq-to", "source": msg_id, "target": ll_id}


def _note_of(note_id: str, ll_id: str) -> dict[str, object]:
    return {"id": f"kc-note-{note_id}", "conn_type": "seq-note-of", "source": note_id, "target": ll_id}


def _render(
    diagram_entities: object = None,
    name: str = "Flow",
    diagram_connections: list[dict[str, object]] | None = None,
    **kwargs: object,
) -> str:
    return _r(**kwargs).render_body(
        name, [], [], "sequence", Path("/tmp"),
        diagram_entities=diagram_entities, diagram_connections=diagram_connections,
    )


def test_empty_renders_startuml_enduml() -> None:
    puml = _render(diagram_entities={})
    assert "@startuml" in puml
    assert "@enduml" in puml


def test_lifeline_declared_as_participant() -> None:
    puml = _render(diagram_entities={"lifeline": [{"id": "ll1", "label": "Web App"}]})
    assert 'participant "Web App" as LL1' in puml


def test_multiple_lifelines_get_sequential_aliases() -> None:
    lls = [{"id": "ll1", "label": "A"}, {"id": "ll2", "label": "B"}]
    puml = _render(diagram_entities={"lifeline": lls})
    assert "LL1" in puml
    assert "LL2" in puml


def test_simple_sync_message_arrow() -> None:
    lls = [{"id": "ll1", "label": "A"}, {"id": "ll2", "label": "B"}]
    msgs = [_msg("m1", "request", 1)]
    kcs = [_seq_from("m1", "ll1"), _seq_to("m1", "ll2")]
    puml = _render(
        diagram_entities={"lifeline": lls, "message": msgs},
        diagram_connections=kcs,
    )
    assert "LL1 -> LL2: request" in puml


def test_reply_arrow_style() -> None:
    lls = [{"id": "ll1", "label": "A"}, {"id": "ll2", "label": "B"}]
    msgs = [_msg("m1", "response", 1, arrow_style="reply")]
    kcs = [_seq_from("m1", "ll2"), _seq_to("m1", "ll1")]
    puml = _render(
        diagram_entities={"lifeline": lls, "message": msgs},
        diagram_connections=kcs,
    )
    assert "LL2 --> LL1: response" in puml


def test_async_arrow_style() -> None:
    lls = [{"id": "ll1", "label": "A"}, {"id": "ll2", "label": "B"}]
    msgs = [_msg("m1", "fire", 1, arrow_style="async")]
    kcs = [_seq_from("m1", "ll1"), _seq_to("m1", "ll2")]
    puml = _render(
        diagram_entities={"lifeline": lls, "message": msgs},
        diagram_connections=kcs,
    )
    assert "LL1 ->> LL2: fire" in puml


def test_messages_ordered_by_sequence_index() -> None:
    lls = [{"id": "ll1", "label": "A"}, {"id": "ll2", "label": "B"}]
    msgs = [_msg("m2", "second", 2), _msg("m1", "first", 1)]
    kcs = [
        _seq_from("m1", "ll1"), _seq_to("m1", "ll2"),
        _seq_from("m2", "ll2"), _seq_to("m2", "ll1"),
    ]
    puml = _render(
        diagram_entities={"lifeline": lls, "message": msgs},
        diagram_connections=kcs,
    )
    assert puml.index("first") < puml.index("second")


def test_opt_fragment_wraps_messages() -> None:
    lls = [{"id": "ll1", "label": "A"}, {"id": "ll2", "label": "B"}]
    msgs = [_msg("m1", "call", 1)]
    frags = [{"id": "f1", "kind": "opt", "from_index": 1, "to_index": 1, "condition": "if ready"}]
    kcs = [_seq_from("m1", "ll1"), _seq_to("m1", "ll2")]
    puml = _render(
        diagram_entities={"lifeline": lls, "message": msgs, "fragment": frags},
        diagram_connections=kcs,
    )
    assert "opt [if ready]" in puml
    assert "end" in puml
    assert puml.index("opt [if ready]") < puml.index("LL1 -> LL2: call")
    assert puml.index("LL1 -> LL2: call") < puml.rindex("end")


def test_loop_fragment_no_condition() -> None:
    lls = [{"id": "ll1", "label": "A"}, {"id": "ll2", "label": "B"}]
    msgs = [_msg("m1", "poll", 1)]
    frags = [{"id": "f1", "kind": "loop", "from_index": 1, "to_index": 1}]
    kcs = [_seq_from("m1", "ll1"), _seq_to("m1", "ll2")]
    puml = _render(
        diagram_entities={"lifeline": lls, "message": msgs, "fragment": frags},
        diagram_connections=kcs,
    )
    assert "loop\n" in puml or "loop " in puml or puml.count("loop") >= 1


def test_execution_spec_activate_deactivate() -> None:
    lls = [{"id": "ll1", "label": "A"}, {"id": "ll2", "label": "B"}]
    msgs = [_msg("m1", "work", 1)]
    exec_specs = [{"id": "es1", "lifeline_id": "ll2", "from_index": 1, "to_index": 1}]
    kcs = [_seq_from("m1", "ll1"), _seq_to("m1", "ll2")]
    puml = _render(
        diagram_entities={"lifeline": lls, "message": msgs, "execution-spec": exec_specs},
        diagram_connections=kcs,
    )
    assert "activate LL2" in puml
    assert "deactivate LL2" in puml


def test_note_rendered_after_participants() -> None:
    lls = [{"id": "ll1", "label": "A"}]
    notes = [{"id": "n1", "text": "important", "side": "right"}]
    kcs = [_note_of("n1", "ll1")]
    puml = _render(
        diagram_entities={"lifeline": lls, "note": notes},
        diagram_connections=kcs,
    )
    assert "note right of LL1: important" in puml


def test_collect_references_reads_entity_and_connection_bindings() -> None:
    renderer = _r()
    bindings = [
        {"id": "b1", "subject": {"kind": "entity", "id": "ll1"},
         "correspondence_kind": "represents", "target": {"entity_id": "ENT@123"}},
        {"id": "b2", "subject": {"kind": "connection", "id": "m1"},
         "correspondence_kind": "represents", "target": {"connection_id": "A---B@@serving"}},
        {"id": "b3", "subject": {"kind": "connection", "id": "m2"},
         "correspondence_kind": "abstracts",
         "target": {"connection_ids": ["A---B@@flow", "B---C@@access"]}},
    ]
    refs = renderer.collect_references(
        "sequence", Path("/tmp"), bindings=bindings
    )
    assert "ENT@123" in refs.entity_ids
    assert "A---B@@serving" in refs.connection_ids
    assert "A---B@@flow" in refs.connection_ids
    assert "B---C@@access" in refs.connection_ids


def test_title_uses_diagram_name() -> None:
    puml = _render(diagram_entities={}, name="My Sequence")
    assert "title My Sequence" in puml
