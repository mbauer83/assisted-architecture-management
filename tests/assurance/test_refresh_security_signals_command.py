"""RefreshSecuritySignals command: validation, the wired replay decisions,
failure recording (terminal), end-to-end activation over the REAL SQLCipher
adapter, feed-shrinkage retirement, and same-serial-different-digest runs
(F3.4/F3.8)."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import pytest

from src.application.security_refresh.command import (
    RefreshActivated,
    RefreshBundle,
    RefreshConflict,
    RefreshFailed,
    RefreshInvalid,
    RefreshReplayed,
    refresh_security_signals,
)

pytest.importorskip("sqlcipher3", reason="sqlcipher3 not installed")

_counter = itertools.count(1)


def _run_ids() -> Any:
    return lambda: f"RUN@{next(_counter)}"


@pytest.fixture()
def store(tmp_path: Path):
    from src.infrastructure.assurance._refresh_run_store import SQLCipherRefreshRunStore
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore
    from src.infrastructure.assurance.lifecycle import init_store

    db_path = tmp_path / "cmd.db"
    init_store(db_path)
    sql_store = SQLCipherAssuranceStore(db_path)
    sql_store.unlock()
    yield SQLCipherRefreshRunStore(sql_store._thread_conn_or_none)  # noqa: SLF001
    sql_store.lock()


def _bundle(request_id: str = "req-1", *, findings: tuple = (), components: tuple | None = None,
            bom_serial: str = "urn:uuid:1", diagnostics: dict | None = None) -> RefreshBundle:
    return RefreshBundle(
        anchor_entity_id="APP@1",
        request_id=request_id,
        components=components if components is not None else (
            {"component_id": "C1", "name": "requests", "purl": "pkg:pypi/requests@2.31.0",
             "directness": "direct"},
        ),
        findings=findings,
        bom_serial=bom_serial,
        diagnostics=diagnostics or {},
    )


class TestValidation:
    def test_missing_anchor_and_bad_finding_are_typed_errors(self, store: Any) -> None:
        bundle = RefreshBundle(
            anchor_entity_id="", request_id="r",
            components=({"component_id": "", "name": ""},),
            findings=({"component_id": "ghost", "external_ids": []},),
        )
        result = refresh_security_signals(bundle, store=store, new_run_id=_run_ids())
        assert isinstance(result, RefreshInvalid)
        fields = {e.field for e in result.errors}
        assert fields == {"anchor_entity_id", "components", "findings"}


class TestExecution:
    def test_successful_refresh_activates_atomically(self, store: Any) -> None:
        result = refresh_security_signals(
            _bundle(findings=({"component_id": "C1", "external_ids": ["CVE-2024-1"]},)),
            store=store, new_run_id=_run_ids(),
        )
        assert isinstance(result, RefreshActivated)
        assert store.get_active_run("APP@1")["run_id"] == result.run_id
        assert result.finding_count == 1

    def test_second_refresh_supersedes_the_first(self, store: Any) -> None:
        first = refresh_security_signals(_bundle("req-1"), store=store, new_run_id=_run_ids())
        second = refresh_security_signals(_bundle("req-2"), store=store, new_run_id=_run_ids())
        assert isinstance(first, RefreshActivated) and isinstance(second, RefreshActivated)
        assert second.superseded_run_id == first.run_id
        assert store.get_active_run("APP@1")["run_id"] == second.run_id

    def test_feed_shrinkage_retires_findings_with_the_superseded_run(self, store: Any) -> None:
        """A vulnerability absent from the new feed simply is not in the new
        active run — metrics read only the active run, so it retires without
        any delete or tombstone (F3.4)."""
        with_finding = _bundle(
            "req-1", findings=({"component_id": "C1", "external_ids": ["CVE-2024-1"]},),
        )
        without_finding = _bundle("req-2")
        refresh_security_signals(with_finding, store=store, new_run_id=_run_ids())
        second = refresh_security_signals(without_finding, store=store, new_run_id=_run_ids())
        assert isinstance(second, RefreshActivated)
        conn = store._conn()  # noqa: SLF001
        active_findings = conn.execute(
            "SELECT COUNT(*) AS n FROM run_vulnerability_findings WHERE run_id=?",
            (second.run_id,),
        ).fetchone()["n"]
        assert active_findings == 0
        total_findings = conn.execute(
            "SELECT COUNT(*) AS n FROM run_vulnerability_findings"
        ).fetchone()["n"]
        assert total_findings == 1  # history retained under the superseded run

    def test_same_serial_different_digest_creates_distinct_runs(self, store: Any) -> None:
        """Same BOM serial with changed content is a NEW run under a new
        request_id (F3.8) — serial equality never implies payload equality."""
        first = refresh_security_signals(
            _bundle("req-1", bom_serial="urn:uuid:same"),
            store=store, new_run_id=_run_ids(),
        )
        second = refresh_security_signals(
            _bundle("req-2", bom_serial="urn:uuid:same", diagnostics={"unmatched": 1}),
            store=store, new_run_id=_run_ids(),
        )
        assert isinstance(first, RefreshActivated) and isinstance(second, RefreshActivated)
        assert first.run_id != second.run_id


class TestReplay:
    def test_replaying_a_success_returns_the_original_run_without_mutation(self, store: Any) -> None:
        first = refresh_security_signals(_bundle("req-1"), store=store, new_run_id=_run_ids())
        assert isinstance(first, RefreshActivated)
        replay = refresh_security_signals(_bundle("req-1"), store=store, new_run_id=_run_ids())
        assert replay == RefreshReplayed(
            run_id=first.run_id, stored_outcome="success",
            message="This request already succeeded; returning the original run.",
        )
        assert len(store.list_runs(anchor_entity_id="APP@1")) == 1

    def test_replaying_an_in_flight_staging_run_says_retry_later(self, store: Any) -> None:
        bundle = _bundle("req-1")
        store.create_staging_run(
            run_id="RUN@staging", anchor_entity_id="APP@1", request_id="req-1",
            request_payload_digest=bundle.payload_digest(),
        )
        replay = refresh_security_signals(bundle, store=store, new_run_id=_run_ids())
        assert isinstance(replay, RefreshReplayed)
        assert replay.stored_outcome == "in_progress"
        assert len(store.list_runs(anchor_entity_id="APP@1")) == 1

    def test_same_request_different_payload_is_a_conflict_with_no_write(self, store: Any) -> None:
        refresh_security_signals(_bundle("req-1"), store=store, new_run_id=_run_ids())
        conflict = refresh_security_signals(
            _bundle("req-1", diagnostics={"changed": True}),
            store=store, new_run_id=_run_ids(),
        )
        assert isinstance(conflict, RefreshConflict)
        assert len(store.list_runs(anchor_entity_id="APP@1")) == 1

    def test_replaying_a_failure_points_at_a_new_request_id(self, store: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        original = store.complete_run

        def _boom(run_id: str) -> None:
            raise RuntimeError("complete blew up")

        monkeypatch.setattr(store, "complete_run", _boom)
        failed = refresh_security_signals(_bundle("req-1"), store=store, new_run_id=_run_ids())
        assert isinstance(failed, RefreshFailed)
        monkeypatch.setattr(store, "complete_run", original)
        replay = refresh_security_signals(_bundle("req-1"), store=store, new_run_id=_run_ids())
        assert isinstance(replay, RefreshReplayed)
        assert replay.stored_outcome == "failed"
        assert "new request_id" in replay.message
        # And a NEW request id executes fine — failed never resumes, callers move on.
        retry = refresh_security_signals(_bundle("req-2"), store=store, new_run_id=_run_ids())
        assert isinstance(retry, RefreshActivated)


class TestFailureRecording:
    def test_populate_error_records_a_failed_run_with_safe_reason(
        self, store: Any, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _boom(*args: object, **kwargs: object) -> None:
            raise ValueError("secret detail that must not leak")

        monkeypatch.setattr(store, "populate_run", _boom)
        result = refresh_security_signals(_bundle("req-1"), store=store, new_run_id=_run_ids())
        assert isinstance(result, RefreshFailed)
        assert "secret detail" not in result.reason  # type name only
        run = store.find_run_by_request("APP@1", "req-1")
        assert run["status"] == "failed"
        assert "secret detail" not in str(run["failure_reason"])

class TestConcurrentDuplicates:
    def test_concurrent_same_request_yields_one_run(self, store: Any) -> None:
        """Two racing submissions of the same bundle: the UNIQUE(anchor,
        request_id) constraint guarantees at most one staging run is created;
        the loser either replays the stored outcome or surfaces the constraint
        (the write queue serializes real transports on top of this)."""
        import threading

        bundle = _bundle("req-race")
        results: list[object] = []

        def _submit() -> None:
            try:
                results.append(
                    refresh_security_signals(bundle, store=store, new_run_id=_run_ids())
                )
            except Exception as exc:  # noqa: BLE001 — constraint loss is acceptable
                results.append(exc)

        threads = [threading.Thread(target=_submit) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        runs = store.list_runs(anchor_entity_id="APP@1")
        assert len(runs) == 1
        assert sum(1 for r in results if isinstance(r, RefreshActivated)) >= 1
