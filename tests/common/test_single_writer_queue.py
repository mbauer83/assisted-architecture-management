"""Unit tests for the shared SingleWriterQueue primitive."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from src.infrastructure.concurrency.single_writer_queue import SingleWriterQueue


def test_runs_serially_max_in_flight_one() -> None:
    q = SingleWriterQueue("test-queue")
    try:
        observed_concurrent = []
        counter = {"active": 0}
        lock = threading.Lock()

        def _job() -> None:
            with lock:
                counter["active"] += 1
                observed_concurrent.append(counter["active"])
            time.sleep(0.01)
            with lock:
                counter["active"] -= 1

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(q.run_sync, _job) for _ in range(20)]
            for f in futures:
                f.result()

        assert max(observed_concurrent) == 1
        assert q.max_observed_in_flight == 1
    finally:
        q.shutdown()


def test_run_sync_returns_result_and_propagates_errors() -> None:
    q = SingleWriterQueue("test-queue")
    try:
        assert q.run_sync(lambda x: x + 1, 41) == 42

        def _boom() -> None:
            raise ValueError("boom")

        try:
            q.run_sync(_boom)
        except ValueError as exc:
            assert str(exc) == "boom"
        else:  # pragma: no cover
            raise AssertionError("expected ValueError")
    finally:
        q.shutdown()


def test_wait_until_idle_and_shutdown() -> None:
    q = SingleWriterQueue("test-queue")
    results: list[int] = []
    for i in range(5):
        q.submit(lambda n: results.append(n), i)
    assert q.wait_until_idle(timeout_s=5.0)
    assert sorted(results) == [0, 1, 2, 3, 4]
    assert q.pending() == 0
    q.shutdown()
