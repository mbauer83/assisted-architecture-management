"""Configured signal-attribute capability over a REAL SQLCipher store:
per-call availability (locked → unavailable; unlock → values — the F3.9 lock
cycle), no fabricated zeros for anchors without an active run, snapshot
mixing protection, and the composition-root selection (configured vs null —
never conditional on the current lock state)."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import pytest

from src.application.security_refresh.command import RefreshBundle, refresh_security_signals
from src.application.viewpoints.ports import NullSignalAttributeCapability
from src.infrastructure.assurance.signal_attribute_capability import (
    AssuranceSignalAttributeCapability,
    composed_signal_attribute_capability,
)

pytest.importorskip("sqlcipher3", reason="sqlcipher3 not installed")

_counter = itertools.count(1)


class _Context:
    def __init__(self, store: Any, run_store: Any, vex_store: Any) -> None:
        self.store = store
        self.refresh_run_store = run_store
        self.vex_store = vex_store
        self.max_classification = "TLP:RED"

    def is_available(self) -> bool:
        return self.store.is_unlocked()


@pytest.fixture()
def ctx(tmp_path: Path):
    from src.infrastructure.assurance._refresh_run_store import SQLCipherRefreshRunStore
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore
    from src.infrastructure.assurance._vex_assessment_store import SQLCipherVexAssessmentStore
    from src.infrastructure.assurance.lifecycle import init_store

    db_path = tmp_path / "capability.db"
    init_store(db_path)
    store = SQLCipherAssuranceStore(db_path)
    store.unlock()
    yield _Context(
        store,
        SQLCipherRefreshRunStore(store._thread_conn_or_none),  # noqa: SLF001
        SQLCipherVexAssessmentStore(store._thread_conn_or_none),  # noqa: SLF001
    )
    store.lock()


def _refresh(ctx: _Context, anchor: str) -> None:
    refresh_security_signals(
        RefreshBundle(
            anchor_entity_id=anchor,
            request_id=f"req-{next(_counter)}",
            components=({"component_id": "C1", "name": "a", "purl": "pkg:pypi/a@1"},),
            findings=({"component_id": "C1", "external_ids": ["CVE-2024-1"],
                       "severity_band": "high", "cvss_score": 8.0},),
        ),
        store=ctx.refresh_run_store,
        new_run_id=lambda: f"RUN@{next(_counter)}",
    )


class TestLockCycle:
    def test_locked_then_unlocked_per_call_availability(self, ctx: _Context) -> None:
        _refresh(ctx, "APP@1")
        capability = AssuranceSignalAttributeCapability(lambda: ctx)  # type: ignore[arg-type]

        ctx.store.lock()
        locked = capability.fetch_metrics(["APP@1"], ["distinct_open_vulnerabilities"])
        assert locked.available is False
        assert "locked" in str(locked.note)

        ctx.store.unlock()
        unlocked = capability.fetch_metrics(["APP@1"], ["distinct_open_vulnerabilities"])
        assert unlocked.available is True
        assert unlocked.values[("APP@1", "distinct_open_vulnerabilities")] == 1


class TestValueSemantics:
    def test_anchor_without_active_run_contributes_no_values(self, ctx: _Context) -> None:
        _refresh(ctx, "APP@1")
        capability = AssuranceSignalAttributeCapability(lambda: ctx)  # type: ignore[arg-type]
        batch = capability.fetch_metrics(
            ["APP@1", "APP@ghost"], ["distinct_open_vulnerabilities"])
        assert batch.available is True
        assert ("APP@1", "distinct_open_vulnerabilities") in batch.values
        assert ("APP@ghost", "distinct_open_vulnerabilities") not in batch.values

    def test_unknown_metric_names_yield_no_values(self, ctx: _Context) -> None:
        _refresh(ctx, "APP@1")
        capability = AssuranceSignalAttributeCapability(lambda: ctx)  # type: ignore[arg-type]
        batch = capability.fetch_metrics(["APP@1"], ["no_such_metric"])
        assert batch.available is True
        assert batch.values == {}

    def test_missing_colocated_stores_are_unavailable(self, ctx: _Context) -> None:
        ctx.refresh_run_store = None
        capability = AssuranceSignalAttributeCapability(lambda: ctx)  # type: ignore[arg-type]
        batch = capability.fetch_metrics(["APP@1"], ["finding_total"])
        assert batch.available is False


class TestCompositionRoot:
    def test_disabled_capability_composes_the_null_implementation(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import src.infrastructure.assurance.capability as capability_module

        class _Disabled:
            enabled = False

        monkeypatch.setattr(capability_module, "make_capability", lambda _path: _Disabled())
        composed = composed_signal_attribute_capability()
        assert isinstance(composed, NullSignalAttributeCapability)
        batch = composed.fetch_metrics(["APP@1"], ["finding_total"])
        assert batch.available is False
        assert "not configured" in str(batch.note)
