"""Tests for _check_bindings / check_bindings_scoped (verifier rules for top-level bindings).

One test class per E4xx rule, plus a base-case class verifying clean bindings pass.
"""

from __future__ import annotations

from src.application.verification._verifier_rules_bindings import check_bindings_scoped
from src.application.verification.artifact_verifier_types import VerificationResult
from pathlib import Path


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

_LOC = "/test/diagram.puml"
_ENTITY_ID = "APP@1000000000.AbcDef.my-app"
_CONN_ID = f"{_ENTITY_ID}---APP@1000000000.AbcDef.my-db@@archimate-serving"


def _result() -> VerificationResult:
    p = Path(_LOC)
    return VerificationResult(path=p, file_type="diagram")


_SENTINEL = object()


def _run(fm: dict, *, allowed_entities=_SENTINEL, allowed_connections=_SENTINEL, all_entities=_SENTINEL, all_connections=_SENTINEL, scope="engagement"):
    r = _result()
    check_bindings_scoped(
        fm,
        file_scope=scope,
        allowed_entities=allowed_entities if allowed_entities is not _SENTINEL else {_ENTITY_ID},
        allowed_connections=allowed_connections if allowed_connections is not _SENTINEL else {_CONN_ID},
        all_entities=all_entities if all_entities is not _SENTINEL else {_ENTITY_ID},
        all_connections=all_connections if all_connections is not _SENTINEL else {_CONN_ID},
        result=r,
        loc=_LOC,
    )
    return r


def _codes(result: VerificationResult) -> set[str]:
    return {i.code for i in result.issues if i.severity == "error"}


def _fm_with_entity(binding_override: dict | None = None) -> dict:
    binding = {
        "id": "bind-box1",
        "subject": {"kind": "entity", "id": "box1"},
        "correspondence_kind": "represents",
        "target": {"entity_id": _ENTITY_ID},
    }
    if binding_override:
        binding.update(binding_override)
    return {
        "diagram-entities": {"container": [{"id": "box1", "label": "App"}]},
        "bindings": [binding],
    }


# ---------------------------------------------------------------------------
# Clean cases — no issues expected
# ---------------------------------------------------------------------------


class TestCleanBindings:
    def test_no_bindings_passes(self) -> None:
        r = _run({"diagram-entities": {"container": [{"id": "box1"}]}})
        assert r.valid, r.issues

    def test_represents_entity_passes(self) -> None:
        r = _run(_fm_with_entity())
        assert r.valid, [i.message for i in r.issues]

    def test_scoped_by_diagram_passes(self) -> None:
        fm = {
            "diagram-entities": {},
            "bindings": [
                {
                    "id": "bind-scope",
                    "subject": {"kind": "diagram"},
                    "correspondence_kind": "scoped-by",
                    "target": {"entity_id": _ENTITY_ID},
                }
            ],
        }
        r = _run(fm)
        assert r.valid, [i.message for i in r.issues]

    def test_abstracts_connection_ids_passes(self) -> None:
        fm = {
            "diagram-entities": {"container": [{"id": "box1"}]},
            "bindings": [
                {
                    "id": "bind-edge1",
                    "subject": {"kind": "connection", "id": "edge1"},
                    "correspondence_kind": "abstracts",
                    "target": {"connection_ids": [_CONN_ID]},
                }
            ],
            "connections": [{"id": "edge1", "from": "box1", "to": "box2"}],
        }
        r = _run(fm)
        assert r.valid, [i.message for i in r.issues]

    def test_traces_to_passes(self) -> None:
        fm = _fm_with_entity({"correspondence_kind": "traces-to"})
        r = _run(fm)
        assert r.valid, [i.message for i in r.issues]

    def test_bindings_none_passes(self) -> None:
        r = _run({"bindings": None})
        assert r.valid

    def test_diagram_local_target_same_diagram_passes(self) -> None:
        fm = {
            "diagram-entities": {"container": [{"id": "box1"}, {"id": "box2"}]},
            "bindings": [
                {
                    "id": "bind-box1",
                    "subject": {"kind": "entity", "id": "box1"},
                    "correspondence_kind": "scoped-by",
                    "target": {"diagram_local": {"element_id": "box2"}},
                }
            ],
        }
        r = _run(fm)
        assert r.valid, [i.message for i in r.issues]


# ---------------------------------------------------------------------------
# E401 — subject resolution failure
# ---------------------------------------------------------------------------


class TestE401SubjectNotFound:
    def test_entity_subject_missing_from_diagram(self) -> None:
        fm = _fm_with_entity({"subject": {"kind": "entity", "id": "nonexistent"}})
        r = _run(fm)
        assert "E401" in _codes(r)

    def test_connection_subject_missing_from_diagram(self) -> None:
        fm = {
            "diagram-entities": {},
            "bindings": [
                {
                    "id": "bind-edge1",
                    "subject": {"kind": "connection", "id": "nonexistent-edge"},
                    "correspondence_kind": "represents",
                    "target": {"connection_id": _CONN_ID},
                }
            ],
        }
        r = _run(fm)
        assert "E401" in _codes(r)

    def test_diagram_subject_with_id_is_error(self) -> None:
        fm = {
            "diagram-entities": {},
            "bindings": [
                {
                    "id": "bind-scope",
                    "subject": {"kind": "diagram", "id": "should-not-be-here"},
                    "correspondence_kind": "scoped-by",
                    "target": {"entity_id": _ENTITY_ID},
                }
            ],
        }
        r = _run(fm)
        assert "E401" in _codes(r)

    def test_diagram_local_target_element_missing(self) -> None:
        fm = {
            "diagram-entities": {"container": [{"id": "box1"}]},
            "bindings": [
                {
                    "id": "bind-box1",
                    "subject": {"kind": "entity", "id": "box1"},
                    "correspondence_kind": "scoped-by",
                    "target": {"diagram_local": {"element_id": "nonexistent"}},
                }
            ],
        }
        r = _run(fm)
        assert "E401" in _codes(r)

    def test_diagram_local_other_diagram_skips_resolution(self) -> None:
        fm = {
            "diagram-entities": {"container": [{"id": "box1"}]},
            "bindings": [
                {
                    "id": "bind-box1",
                    "subject": {"kind": "entity", "id": "box1"},
                    "correspondence_kind": "scoped-by",
                    "target": {"diagram_local": {"element_id": "any-id", "diagram_id": "other-diagram"}},
                }
            ],
        }
        r = _run(fm)
        # Cross-diagram resolution is deferred — no E401 expected
        assert "E401" not in _codes(r)


# ---------------------------------------------------------------------------
# E402 — target entity_id unknown
# ---------------------------------------------------------------------------


class TestE402EntityTargetUnknown:
    def test_unknown_entity_target(self) -> None:
        fm = _fm_with_entity({"target": {"entity_id": "APP@0000.Unknown.entity"}})
        r = _run(fm)
        assert "E402" in _codes(r)

    def test_known_entity_passes(self) -> None:
        r = _run(_fm_with_entity())
        assert "E402" not in _codes(r)

    def test_enterprise_scope_non_enterprise_entity(self) -> None:
        enterprise_entities: set[str] = set()  # entity exists in all but not enterprise
        fm = _fm_with_entity()
        r = _run(
            fm,
            allowed_entities=enterprise_entities,
            all_entities={_ENTITY_ID},
            scope="enterprise",
        )
        assert "E402" in _codes(r)
        msg = next(i.message for i in r.issues if i.code == "E402")
        assert "enterprise" in msg


# ---------------------------------------------------------------------------
# E403 — target connection_id unknown
# ---------------------------------------------------------------------------


class TestE403ConnectionTargetUnknown:
    def test_unknown_connection_target(self) -> None:
        fm = {
            "diagram-entities": {"container": [{"id": "box1"}]},
            "connections": [{"id": "edge1"}],
            "bindings": [
                {
                    "id": "bind-edge1",
                    "subject": {"kind": "connection", "id": "edge1"},
                    "correspondence_kind": "represents",
                    "target": {"connection_id": "NOEX@0000---NOEX@0001@@serving"},
                }
            ],
        }
        r = _run(fm)
        assert "E403" in _codes(r)

    def test_known_connection_passes(self) -> None:
        fm = {
            "diagram-entities": {},
            "connections": [{"id": "edge1"}],
            "bindings": [
                {
                    "id": "bind-edge1",
                    "subject": {"kind": "connection", "id": "edge1"},
                    "correspondence_kind": "represents",
                    "target": {"connection_id": _CONN_ID},
                }
            ],
        }
        r = _run(fm)
        assert "E403" not in _codes(r)


# ---------------------------------------------------------------------------
# E404 — duplicate represents for same subject
# ---------------------------------------------------------------------------


class TestE404DuplicateRepresentsSubject:
    def test_duplicate_represents_same_element(self) -> None:
        other_entity = "APP@1000000001.AbcDef.other"
        fm = {
            "diagram-entities": {"container": [{"id": "box1"}]},
            "bindings": [
                {
                    "id": "bind-box1-a",
                    "subject": {"kind": "entity", "id": "box1"},
                    "correspondence_kind": "represents",
                    "target": {"entity_id": _ENTITY_ID},
                },
                {
                    "id": "bind-box1-b",
                    "subject": {"kind": "entity", "id": "box1"},
                    "correspondence_kind": "represents",
                    "target": {"entity_id": other_entity},
                },
            ],
        }
        r = _run(fm, allowed_entities={_ENTITY_ID, other_entity}, all_entities={_ENTITY_ID, other_entity})
        assert "E404" in _codes(r)

    def test_different_elements_each_represents_passes(self) -> None:
        other_entity = "APP@1000000001.AbcDef.other"
        fm = {
            "diagram-entities": {"container": [{"id": "box1"}, {"id": "box2"}]},
            "bindings": [
                {
                    "id": "bind-box1",
                    "subject": {"kind": "entity", "id": "box1"},
                    "correspondence_kind": "represents",
                    "target": {"entity_id": _ENTITY_ID},
                },
                {
                    "id": "bind-box2",
                    "subject": {"kind": "entity", "id": "box2"},
                    "correspondence_kind": "represents",
                    "target": {"entity_id": other_entity},
                },
            ],
        }
        r = _run(fm, allowed_entities={_ENTITY_ID, other_entity}, all_entities={_ENTITY_ID, other_entity})
        assert "E404" not in _codes(r)


# ---------------------------------------------------------------------------
# E405 — duplicate diagram-level scoped-by
# ---------------------------------------------------------------------------


class TestE405DuplicateDiagramScopedBy:
    def test_two_diagram_level_scoped_by_errors(self) -> None:
        fm = {
            "diagram-entities": {},
            "bindings": [
                {
                    "id": "bind-scope-1",
                    "subject": {"kind": "diagram"},
                    "correspondence_kind": "scoped-by",
                    "target": {"entity_id": _ENTITY_ID},
                },
                {
                    "id": "bind-scope-2",
                    "subject": {"kind": "diagram"},
                    "correspondence_kind": "scoped-by",
                    "target": {"entity_id": _ENTITY_ID},
                },
            ],
        }
        r = _run(fm)
        assert "E405" in _codes(r)

    def test_single_diagram_scoped_by_passes(self) -> None:
        fm = {
            "diagram-entities": {},
            "bindings": [
                {
                    "id": "bind-scope",
                    "subject": {"kind": "diagram"},
                    "correspondence_kind": "scoped-by",
                    "target": {"entity_id": _ENTITY_ID},
                }
            ],
        }
        r = _run(fm)
        assert "E405" not in _codes(r)


# ---------------------------------------------------------------------------
# E406 — unrecognized correspondence_kind
# ---------------------------------------------------------------------------


class TestE406UnrecognizedCorrespondenceKind:
    def test_unknown_kind_errors(self) -> None:
        fm = _fm_with_entity({"correspondence_kind": "invented-kind"})
        r = _run(fm)
        assert "E406" in _codes(r)

    def test_all_core_kinds_pass(self) -> None:
        for kind in ("represents", "abstracts", "refines", "scoped-by", "traces-to"):
            fm = _fm_with_entity({"correspondence_kind": kind})
            r = _run(fm)
            assert "E406" not in _codes(r), f"E406 raised for core kind '{kind}'"


# ---------------------------------------------------------------------------
# E407 — connection_ids member unknown
# ---------------------------------------------------------------------------


class TestE407ConnectionIdsMemberUnknown:
    def test_unknown_member_in_connection_ids(self) -> None:
        fm = {
            "diagram-entities": {"container": [{"id": "box1"}]},
            "connections": [{"id": "edge1"}],
            "bindings": [
                {
                    "id": "bind-edge1",
                    "subject": {"kind": "connection", "id": "edge1"},
                    "correspondence_kind": "abstracts",
                    "target": {"connection_ids": [_CONN_ID, "NOEX@0---NOEX@1@@serving"]},
                }
            ],
        }
        r = _run(fm)
        assert "E407" in _codes(r)

    def test_all_known_connection_ids_pass(self) -> None:
        fm = {
            "diagram-entities": {},
            "connections": [{"id": "edge1"}],
            "bindings": [
                {
                    "id": "bind-edge1",
                    "subject": {"kind": "connection", "id": "edge1"},
                    "correspondence_kind": "abstracts",
                    "target": {"connection_ids": [_CONN_ID]},
                }
            ],
        }
        r = _run(fm)
        assert "E407" not in _codes(r)


# ---------------------------------------------------------------------------
# E408 — duplicate represents for same model target
# ---------------------------------------------------------------------------


class TestE408DuplicateRepresentsTarget:
    def test_two_elements_representing_same_model_entity(self) -> None:
        fm = {
            "diagram-entities": {"container": [{"id": "box1"}, {"id": "box2"}]},
            "bindings": [
                {
                    "id": "bind-box1",
                    "subject": {"kind": "entity", "id": "box1"},
                    "correspondence_kind": "represents",
                    "target": {"entity_id": _ENTITY_ID},
                },
                {
                    "id": "bind-box2",
                    "subject": {"kind": "entity", "id": "box2"},
                    "correspondence_kind": "represents",
                    "target": {"entity_id": _ENTITY_ID},  # same target
                },
            ],
        }
        r = _run(fm)
        assert "E408" in _codes(r)

    def test_two_elements_representing_different_targets_passes(self) -> None:
        other_entity = "APP@1000000001.AbcDef.other"
        fm = {
            "diagram-entities": {"container": [{"id": "box1"}, {"id": "box2"}]},
            "bindings": [
                {
                    "id": "bind-box1",
                    "subject": {"kind": "entity", "id": "box1"},
                    "correspondence_kind": "represents",
                    "target": {"entity_id": _ENTITY_ID},
                },
                {
                    "id": "bind-box2",
                    "subject": {"kind": "entity", "id": "box2"},
                    "correspondence_kind": "represents",
                    "target": {"entity_id": other_entity},
                },
            ],
        }
        r = _run(fm, allowed_entities={_ENTITY_ID, other_entity}, all_entities={_ENTITY_ID, other_entity})
        assert "E408" not in _codes(r)
