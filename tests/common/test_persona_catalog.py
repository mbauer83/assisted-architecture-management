"""Guards for the canonical persona catalog (spec/personas/personas.yaml): structural
integrity, vocabulary discipline, and — most importantly — that every candidate-route
viewpoint slug stays valid against the shipped library, so evaluation sessions never
inherit a silently stale answer key."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CATALOG_PATH = _REPO_ROOT / "spec" / "personas" / "personas.yaml"
_LIBRARY_PATH = _REPO_ROOT / "src" / "ontologies" / "archimate_4" / "viewpoints.yaml"

_FIT_KINDS = frozenset({"shipped", "fork", "authoring", "docs", "fixture-gap", "gap"})
_CATALOG_ACTIONS = frozenset({
    "execute", "fork", "create", "consult-docs", "recognize-fixture-gap", "recognize-product-gap",
})
_ACTION_BY_FIT = {
    "shipped": "execute",
    "fork": "fork",
    "authoring": "create",
    "docs": "consult-docs",
    "fixture-gap": "recognize-fixture-gap",
    "gap": "recognize-product-gap",
}
_DECISION_ARTIFACTS = frozenset({
    "slide", "ticket", "design-review", "audit-evidence", "incident-note",
    "go-no-go", "link", "worklist", "steering-recommendation", "governance-review",
})
_PERSONA_FIELDS = frozenset({
    "id", "name", "segment", "expert", "capabilities", "resources",
    "cognitive_profile", "focus", "strategies", "questions", "authoring_challenge", "budgets",
})
_QUESTION_FIELDS = frozenset({
    "id", "text", "information_need", "decision_artifact", "candidate_routes",
    "fit_kind", "preconditions", "expected_catalog_action",
})
_CHALLENGE_FIELDS = frozenset({"id", "text", "preconditions"})
_BUDGET_FIELDS = frozenset({"max_task_actions", "max_authoring_actions"})


def _load_catalog() -> dict[str, Any]:
    loaded: Any = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _library_slugs() -> frozenset[str]:
    loaded: Any = yaml.safe_load(_LIBRARY_PATH.read_text(encoding="utf-8"))
    return frozenset(str(entry["slug"]) for entry in loaded["viewpoints"])


def test_catalog_parses_with_expected_scope() -> None:
    catalog = _load_catalog()
    assert catalog["schema"] == 3
    assert catalog["scope"] == "viewpoints"
    assert len(catalog["personas"]) >= 12


def test_personas_and_questions_are_complete_and_unique() -> None:
    catalog = _load_catalog()
    persona_ids: list[str] = []
    question_ids: list[str] = []
    for persona in catalog["personas"]:
        missing = _PERSONA_FIELDS - persona.keys()
        assert not missing, f"{persona.get('id')}: missing persona fields {sorted(missing)}"
        persona_ids.append(persona["id"])
        assert isinstance(persona["expert"], bool)
        assert _BUDGET_FIELDS <= persona["budgets"].keys(), persona["id"]
        for budget in persona["budgets"].values():
            assert isinstance(budget, int) and budget > 0
        challenge = persona["authoring_challenge"]
        assert _CHALLENGE_FIELDS <= challenge.keys(), persona["id"]
        assert challenge["id"].startswith(persona["id"])
        assert persona["questions"], f"{persona['id']}: no questions"
        for question in persona["questions"]:
            missing_q = _QUESTION_FIELDS - question.keys()
            assert not missing_q, f"{question.get('id')}: missing question fields {sorted(missing_q)}"
            question_ids.append(question["id"])
            assert question["id"].startswith(persona["id"]), question["id"]
    assert len(persona_ids) == len(set(persona_ids))
    assert len(question_ids) == len(set(question_ids))


def test_fit_kinds_actions_and_decision_artifacts_use_declared_vocabulary() -> None:
    catalog = _load_catalog()
    for persona in catalog["personas"]:
        for question in persona["questions"]:
            assert question["fit_kind"] in _FIT_KINDS, question["id"]
            assert question["decision_artifact"] in _DECISION_ARTIFACTS, question["id"]
            assert question["expected_catalog_action"] in _CATALOG_ACTIONS, question["id"]


def test_expected_catalog_action_is_consistent_with_fit_kind() -> None:
    """hit@k scoring validity depends on this pairing: only `execute` questions may be
    scored by candidate-route hits; every other fit kind scores route-class recognition."""
    catalog = _load_catalog()
    for persona in catalog["personas"]:
        for question in persona["questions"]:
            expected = _ACTION_BY_FIT[question["fit_kind"]]
            assert question["expected_catalog_action"] == expected, question["id"]


def test_candidate_routes_reference_shipped_library_slugs() -> None:
    known = _library_slugs()
    catalog = _load_catalog()
    for persona in catalog["personas"]:
        for question in persona["questions"]:
            for slug in question["candidate_routes"]:
                assert slug in known, f"{question['id']}: unknown viewpoint slug {slug!r}"


def test_shipped_questions_name_at_least_one_candidate_route() -> None:
    catalog = _load_catalog()
    for persona in catalog["personas"]:
        for question in persona["questions"]:
            if question["fit_kind"] == "shipped":
                assert question["candidate_routes"], f"{question['id']}: shipped fit without candidate routes"
