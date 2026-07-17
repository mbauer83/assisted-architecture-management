"""Tests for the safety-critical usability-test helpers: manifest validation and
baseline verification in the cleanup script (must never be able to delete a
pre-existing definition), and the persona-brief composer (answer-key fields must never
leak into a persona brief)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HELPERS_DIR = _REPO_ROOT / "tools" / "usability_test"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _HELPERS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cleanup = _load("cleanup_usability_viewpoints")
inventory = _load("viewpoint_inventory")
composer = _load("compose_persona_brief")

_BASELINE = {
    "definitions": {
        "capability-map": {"tier": "module", "version": 1, "hash": "h1"},
        "my-team-view": {"tier": "engagement", "version": 2, "hash": "h2"},
    },
    "pins": ["capability-map"],
}


class TestValidateTargets:
    def test_accepts_only_run_prefixed_new_slugs(self) -> None:
        manifest = {"run_id": "r1", "created_slugs": ["usability-r1-a", "usability-r1-b"]}
        assert cleanup.validate_targets(manifest, _BASELINE) == ["usability-r1-a", "usability-r1-b"]

    def test_rejects_missing_run_id(self) -> None:
        with pytest.raises(ValueError, match="no run_id"):
            cleanup.validate_targets({"created_slugs": ["usability-r1-a"]}, _BASELINE)

    def test_rejects_slug_outside_run_namespace(self) -> None:
        manifest = {"run_id": "r1", "created_slugs": ["usability-r2-a"]}
        with pytest.raises(ValueError, match="outside this run's namespace"):
            cleanup.validate_targets(manifest, _BASELINE)

    def test_rejects_pre_existing_baseline_slug_even_with_matching_prefix(self) -> None:
        baseline = {
            "definitions": {**_BASELINE["definitions"], "usability-r1-leftover": {"hash": "h3"}},
            "pins": [],
        }
        manifest = {"run_id": "r1", "created_slugs": ["usability-r1-leftover"]}
        with pytest.raises(ValueError, match="existed before the run"):
            cleanup.validate_targets(manifest, baseline)

    def test_rejects_pre_existing_engagement_definition_named_by_malformed_manifest(self) -> None:
        manifest = {"run_id": "r1", "created_slugs": ["my-team-view"]}
        with pytest.raises(ValueError, match="outside this run's namespace"):
            cleanup.validate_targets(manifest, _BASELINE)

    def test_rejects_duplicates_and_non_strings(self) -> None:
        manifest = {"run_id": "r1", "created_slugs": ["usability-r1-a", "usability-r1-a", 7]}
        with pytest.raises(ValueError, match="duplicate"):
            cleanup.validate_targets(manifest, _BASELINE)


class TestVerifyAgainstBaseline:
    def _catalog(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        return {"viewpoints": entries}

    def _entry(self, slug: str) -> dict[str, Any]:
        return {"slug": slug, "name": slug}

    def _baseline_for(self, entries: list[dict[str, Any]], pins: list[str]) -> dict[str, Any]:
        return {
            "definitions": {
                str(e["slug"]): {"hash": cleanup.canonical_hash(e)} for e in entries
            },
            "pins": pins,
        }

    def test_clean_restoration_passes(self) -> None:
        entries = [self._entry("capability-map")]
        baseline = self._baseline_for(entries, ["capability-map"])
        assert cleanup.verify_against_baseline(
            self._catalog(entries), ["capability-map"], baseline, set()
        ) == []

    def test_detects_changed_definition_missing_slug_residual_and_pin_change(self) -> None:
        original = [self._entry("capability-map"), self._entry("my-team-view")]
        baseline = self._baseline_for(original, [])
        mutated = [
            {**self._entry("capability-map"), "name": "renamed"},
            self._entry("usability-r1-leftover"),
        ]
        problems = cleanup.verify_against_baseline(
            self._catalog(mutated), ["new-pin"], baseline, {"usability-r1-leftover"}
        )
        assert any("changed during run" in p for p in problems)
        assert any("missing after cleanup: my-team-view" in p for p in problems)
        assert any("residual test slug: usability-r1-leftover" in p for p in problems)
        assert any("pin list changed" in p for p in problems)

    def test_hashes_agree_between_inventory_and_cleanup(self) -> None:
        entry = self._entry("capability-map")
        assert cleanup.canonical_hash(entry) == inventory.canonical_hash(entry)


class TestComposePersonaBrief:
    _FORBIDDEN = ("candidate_routes", "fit_kind", "preconditions", "expected_catalog_action")

    def _catalog(self) -> dict[str, Any]:
        path = _REPO_ROOT / "spec" / "personas" / "personas.yaml"
        loaded: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        return loaded

    def test_no_answer_key_field_ever_appears_in_any_brief(self) -> None:
        catalog = self._catalog()
        for persona in catalog["personas"]:
            brief = composer.compose_brief(catalog, persona["id"])
            rendered = composer.render_markdown(persona["id"], brief)
            for forbidden in self._FORBIDDEN:
                assert forbidden not in str(brief), (persona["id"], forbidden)
                assert forbidden not in rendered, (persona["id"], forbidden)

    def test_brief_carries_budgets_questions_and_challenge(self) -> None:
        catalog = self._catalog()
        brief = composer.compose_brief(catalog, "PA")
        assert brief["budgets"]["max_task_actions"] > 0
        assert all({"id", "text", "information_need", "decision_artifact"} <= q.keys() for q in brief["questions"])
        assert set(brief["authoring_challenge"]) == {"id", "text"}

    def test_unknown_persona_id_fails_loudly(self) -> None:
        with pytest.raises(SystemExit):
            composer.compose_brief(self._catalog(), "PZ")
