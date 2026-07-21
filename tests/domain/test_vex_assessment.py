"""Contextual VEX contract (D21/§6.0(d)): validation (suppressing dispositions
require justification), latest-valid revision precedence with retained
history, and exact suppression semantics."""

from __future__ import annotations

from src.domain.vex_assessment import (
    VexAssessmentKey,
    VexRevision,
    current_revision,
    suppresses_finding,
    validate_assessment,
)

KEY = VexAssessmentKey(
    anchor_entity_id="APP@1",
    canonical_component_id="pkg:pypi/requests@2.31.0",
    canonical_vulnerability_id="VID@aaa",
)


def _rev(revision: int, disposition: str, justification: str = "reviewed") -> VexRevision:
    return VexRevision(
        key=KEY, revision=revision, disposition=disposition,
        justification=justification, author="analyst", created_at=f"2026-07-2{revision}T00:00:00Z",
    )


class TestValidation:
    def test_suppressing_dispositions_require_a_justification(self) -> None:
        for disposition in ("not_affected", "fixed"):
            errors = validate_assessment(disposition, "", "analyst")
            assert any(e.field == "justification" for e in errors)
            assert validate_assessment(disposition, "vendored copy unused", "analyst") == []

    def test_non_suppressing_dispositions_do_not_require_one(self) -> None:
        assert validate_assessment("affected", "", "analyst") == []
        assert validate_assessment("under_investigation", "", "analyst") == []

    def test_unknown_disposition_and_missing_author_are_rejected(self) -> None:
        errors = validate_assessment("wontfix", "x", "")
        assert {e.field for e in errors} == {"disposition", "author"}


class TestRevisionPrecedence:
    def test_latest_revision_wins_and_history_is_retained(self) -> None:
        history = [_rev(1, "affected"), _rev(3, "not_affected"), _rev(2, "under_investigation")]
        current = current_revision(history)
        assert current is not None and current.revision == 3
        assert len(history) == 3  # nothing dropped

    def test_no_revisions_means_no_current(self) -> None:
        assert current_revision([]) is None


class TestSuppression:
    def test_only_not_affected_and_fixed_suppress(self) -> None:
        assert suppresses_finding(_rev(1, "not_affected"))
        assert suppresses_finding(_rev(1, "fixed"))
        assert not suppresses_finding(_rev(1, "affected"))
        assert not suppresses_finding(_rev(1, "under_investigation"))
        assert not suppresses_finding(None)

    def test_a_later_affected_revision_reopens_the_finding(self) -> None:
        history = [_rev(1, "not_affected"), _rev(2, "affected")]
        assert not suppresses_finding(current_revision(history))
