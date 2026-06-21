"""Sustained load profiles for the team-serving assurance architecture.

The profile models GUI users as read-heavy clients and agents as mixed read/write
clients. Reads execute directly on per-thread WAL connections; every mutation
passes through the same single-worker mechanism used at the REST/MCP boundary.
"""

from __future__ import annotations

import itertools
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import pytest

pytest.importorskip("sqlcipher3", reason="sqlcipher3 not installed")

_READ_P95_BUDGET_S = 0.5


@dataclass(frozen=True)
class _LoadProfile:
    read_clients: int
    agent_clients: int
    duration_s: float
    write_interval_s: float


_LOCAL = _LoadProfile(read_clients=2, agent_clients=2, duration_s=2.0, write_interval_s=0.75)
_TEAM = _LoadProfile(read_clients=12, agent_clients=12, duration_s=30.0, write_interval_s=6.0)


def _percentile(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = max(math.ceil(percentile * len(ordered)) - 1, 0)
    return ordered[index]


@pytest.fixture()
def load_bundle(tmp_path):  # type: ignore[no-untyped-def]
    from src.infrastructure.assurance._archive import SQLCipherAssuranceArchive
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore
    from src.infrastructure.assurance.lifecycle import init_store

    db_path = tmp_path / "store.db"
    init_store(db_path)
    store = SQLCipherAssuranceStore(db_path)
    store.unlock()
    archive = SQLCipherAssuranceArchive(store._thread_conn_or_none)  # noqa: SLF001
    yield store, archive
    store.lock()


@pytest.mark.parametrize(
    "profile",
    [_LOCAL, _TEAM],
    ids=["single-architect-local", "team-serving"],
)
def test_assurance_load_profile(profile: _LoadProfile, load_bundle) -> None:  # type: ignore[no-untyped-def]
    from src.application import assurance_mutations as mutations
    from src.infrastructure.concurrency.single_writer_queue import SingleWriterQueue

    store, archive = load_bundle
    queue = SingleWriterQueue("assurance-load-profile")
    client_count = profile.read_clients + profile.agent_clients
    start = threading.Barrier(client_count + 1)
    errors: list[str] = []
    read_latencies: list[float] = []
    created_node_ids: list[str] = []
    names = itertools.count()

    def _read() -> None:
        before = time.perf_counter()
        store.stats()
        store.list_nodes()
        read_latencies.append(time.perf_counter() - before)

    def _reader() -> None:
        start.wait()
        deadline = time.monotonic() + profile.duration_s
        while time.monotonic() < deadline:
            try:
                _read()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"read: {type(exc).__name__}: {exc}")
                return
            time.sleep(0.02)

    def _agent(agent_id: int) -> None:
        start.wait()
        deadline = time.monotonic() + profile.duration_s
        next_write = time.monotonic()
        while time.monotonic() < deadline:
            try:
                _read()
                now = time.monotonic()
                if now >= next_write:
                    sequence = next(names)
                    result = queue.run_sync(
                        mutations.create_node,
                        store,
                        archive,
                        node_type="hazard",
                        name=f"Load hazard {agent_id}-{sequence}",
                        concern_class="safety",
                    )
                    assert isinstance(result, mutations.MutationOk)
                    created_node_ids.append(str(result.payload["node_id"]))
                    next_write = now + profile.write_interval_s
            except Exception as exc:  # noqa: BLE001
                errors.append(f"agent: {type(exc).__name__}: {exc}")
                return
            time.sleep(0.05)

    try:
        with ThreadPoolExecutor(max_workers=client_count) as pool:
            futures = [pool.submit(_reader) for _ in range(profile.read_clients)]
            futures.extend(pool.submit(_agent, i) for i in range(profile.agent_clients))
            start.wait()
            for future in as_completed(futures):
                future.result()
        assert queue.wait_until_idle(timeout_s=10.0)
        peak_writes = queue.max_observed_in_flight
    finally:
        queue.shutdown()

    assert not errors, f"load errors: {errors[:3]}"
    assert peak_writes == 1
    assert len(created_node_ids) >= profile.agent_clients
    assert len(set(created_node_ids)) == len(created_node_ids)
    assert int(store.stats()["node_count"]) == len(created_node_ids)
    assert len(read_latencies) >= client_count
    assert _percentile(read_latencies, 0.95) <= _READ_P95_BUDGET_S
