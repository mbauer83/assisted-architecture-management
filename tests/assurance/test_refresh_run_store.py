"""Refresh-run store integration (real SQLCipher): lifecycle transitions with
audit in the same transaction, atomic activation (crash leaves the previous
run the sole basis), the one-active-per-anchor DB constraint through the
adapter, idempotent replay wiring, stale-staging recovery, and alias-merge
repointing across findings and VEX rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import src.infrastructure.assurance._refresh_run_store as store_module
from src.domain.security_refresh_run import ReplayStoredSuccess, StoredRunKey, replay_decision
from src.infrastructure.assurance._refresh_run_store import (
    RefreshRunTransitionError,
    SQLCipherRefreshRunStore,
)

pytest.importorskip("sqlcipher3", reason="sqlcipher3 not installed")


@pytest.fixture()
def store(tmp_path: Path):
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore
    from src.infrastructure.assurance.lifecycle import init_store

    db_path = tmp_path / "runs.db"
    init_store(db_path)
    sql_store = SQLCipherAssuranceStore(db_path)
    sql_store.unlock()
    yield SQLCipherRefreshRunStore(sql_store._thread_conn_or_none)  # noqa: SLF001
    sql_store.lock()


def _staging(store: SQLCipherRefreshRunStore, run_id: str = "RUN@1",
             anchor: str = "APP@1", request_id: str = "req-1", digest: str = "d1") -> None:
    store.create_staging_run(
        run_id=run_id, anchor_entity_id=anchor, request_id=request_id,
        request_payload_digest=digest,
    )


class TestLifecycle:
    def test_full_lifecycle_with_timestamps_and_audit(self, store: Any) -> None:
        _staging(store)
        store.populate_run("RUN@1", components=[
            {"component_id": "C1", "name": "requests", "purl": "pkg:pypi/requests@2.31.0",
             "version": "2.31.0", "directness": "direct"},
        ], findings=[
            {"component_id": "C1", "external_ids": ["CVE-2024-1"], "severity_band": "high",
             "cvss_score": 8.1},
        ])
        store.complete_run("RUN@1")
        result = store.activate_run("RUN@1")
        assert result == {"run_id": "RUN@1", "activated": True, "superseded_run_id": None}
        run = store.get_run("RUN@1")
        assert run["status"] == "active"
        assert run["completed_at"] and run["activated_at"]
        assert run["superseded_at"] is None

    def test_activation_requires_complete(self, store: Any) -> None:
        _staging(store)
        with pytest.raises(RefreshRunTransitionError):
            store.activate_run("RUN@1")

    def test_reactivating_the_active_run_is_a_noop_success(self, store: Any) -> None:
        _staging(store)
        store.complete_run("RUN@1")
        store.activate_run("RUN@1")
        assert store.activate_run("RUN@1") == {
            "run_id": "RUN@1", "activated": False, "already_active": True,
        }

    def test_failed_is_terminal(self, store: Any) -> None:
        _staging(store)
        store.fail_run("RUN@1", reason="acquisition failed")
        with pytest.raises(RefreshRunTransitionError):
            store.complete_run("RUN@1")
        with pytest.raises(RefreshRunTransitionError):
            store.populate_run("RUN@1", components=[], findings=[])


class TestActivationAtomicity:
    def test_new_activation_supersedes_the_previous_in_one_step(self, store: Any) -> None:
        _staging(store, "RUN@1", request_id="req-1")
        store.complete_run("RUN@1")
        store.activate_run("RUN@1")
        _staging(store, "RUN@2", request_id="req-2")
        store.complete_run("RUN@2")
        result = store.activate_run("RUN@2")
        assert result["superseded_run_id"] == "RUN@1"
        assert store.get_run("RUN@1")["status"] == "superseded"
        assert store.get_run("RUN@1")["superseded_at"]
        assert store.get_active_run("APP@1")["run_id"] == "RUN@2"

    def test_crash_inside_activation_leaves_the_previous_run_active(
        self, store: Any, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _staging(store, "RUN@1", request_id="req-1")
        store.complete_run("RUN@1")
        store.activate_run("RUN@1")
        _staging(store, "RUN@2", request_id="req-2")
        store.complete_run("RUN@2")

        def _boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("crash before commit")

        monkeypatch.setattr(store_module, "append_audit_row", _boom)
        with pytest.raises(RuntimeError, match="crash before commit"):
            store.activate_run("RUN@2")
        monkeypatch.undo()
        # The whole transaction rolled back: RUN@1 still sole active basis.
        assert store.get_active_run("APP@1")["run_id"] == "RUN@1"
        assert store.get_run("RUN@2")["status"] == "complete"

    def test_crash_during_population_leaves_no_partial_rows(
        self, store: Any, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _staging(store)

        def _boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("crash before commit")

        monkeypatch.setattr(store_module, "append_audit_row", _boom)
        with pytest.raises(RuntimeError):
            store.populate_run("RUN@1", components=[
                {"component_id": "C1", "name": "requests"},
            ], findings=[])
        monkeypatch.undo()
        conn = store._conn()  # noqa: SLF001
        assert conn.execute("SELECT COUNT(*) AS n FROM run_components").fetchone()["n"] == 0


class TestReplayWiring:
    def test_stored_run_feeds_the_domain_replay_table(self, store: Any) -> None:
        _staging(store, digest="d1")
        store.complete_run("RUN@1")
        store.activate_run("RUN@1")
        row = store.find_run_by_request("APP@1", "req-1")
        key = StoredRunKey(
            run_id=row["run_id"], status=row["status"],
            request_payload_digest=row["request_payload_digest"],
        )
        assert replay_decision(key, "d1") == ReplayStoredSuccess(run_id="RUN@1")

    def test_duplicate_key_is_rejected_by_the_db(self, store: Any) -> None:
        _staging(store, "RUN@1", request_id="req-1")
        with pytest.raises(Exception, match="(?i)unique"):
            _staging(store, "RUN@2", request_id="req-1")


class TestStaleStaging:
    def test_stale_staging_runs_are_failed_never_activated(self, store: Any) -> None:
        _staging(store, "RUN@1", request_id="req-1")
        failed = store.fail_stale_staging(started_before_iso="9999-01-01T00:00:00Z")
        assert failed == ["RUN@1"]
        assert store.get_run("RUN@1")["status"] == "failed"
        assert store.get_active_run("APP@1") is None

    def test_fresh_staging_runs_are_untouched(self, store: Any) -> None:
        _staging(store, "RUN@1", request_id="req-1")
        assert store.fail_stale_staging(started_before_iso="2000-01-01T00:00:00Z") == []
        assert store.get_run("RUN@1")["status"] == "staging"


class TestAliasMerge:
    def test_linking_two_groups_repoints_findings_transactionally(self, store: Any) -> None:
        _staging(store, "RUN@1", request_id="req-1")
        store.populate_run("RUN@1", components=[
            {"component_id": "C1", "name": "a"},
            {"component_id": "C2", "name": "b"},
        ], findings=[
            {"component_id": "C1", "external_ids": ["CVE-2024-1"]},
            {"component_id": "C2", "external_ids": ["GHSA-x"]},
        ])
        # A later record reveals the two ids are the same vulnerability.
        mapping = store.populate_run("RUN@1", components=[], findings=[
            {"component_id": "C1", "external_ids": ["CVE-2024-1", "GHSA-x"]},
        ])
        canonical = next(iter(mapping.values()))
        conn = store._conn()  # noqa: SLF001
        distinct = conn.execute(
            "SELECT COUNT(DISTINCT canonical_vulnerability_id) AS n FROM run_vulnerability_findings"
        ).fetchone()["n"]
        assert distinct == 1
        merged = conn.execute(
            "SELECT COUNT(*) AS n FROM canonical_vulnerabilities WHERE merged_into=?",
            (canonical,),
        ).fetchone()["n"]
        assert merged == 1  # history preserved, not deleted
