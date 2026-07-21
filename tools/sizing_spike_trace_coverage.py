"""Sizing spike for branch-complete trace-coverage evaluation.

Defines the expansion accounting unit, measures a deterministic branching fixture cold and
warm over the REAL evaluation path (the shipped ``motivation-coverage`` grammar, the real
module catalog, and ``evaluate_declared_trace_table``), and derives a default expanded-node
budget plus a hard clamp from the measurements. The live self-model half of the acceptance
protocol runs against the backend and is recorded separately; this harness is portable and
network-free so the fixture measurement is reproducible anywhere.

Accounting unit (bounds actual work): ONE traversal expansion = one read-access adjacency
lookup during index construction plus evaluation. The harness wraps the read access and
counts every ``find_connections_for`` / ``get_connection`` / ``get_entity`` / ``*_ids`` call,
so the reported "expansions" is the objective work unit the request-wide budget clamps.

Protocol: deterministic fixture seed (pure integer arithmetic, no RNG); cold-process figure =
the first run of a fresh interpreter; a stated warmup count; >= 30 timed samples for p95;
machine/runtime metadata and the configured request timeout recorded with the evidence.
"""

from __future__ import annotations

import argparse
import platform
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from src.application.viewpoints.trace_execution import evaluate_declared_trace_table
from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.infrastructure.app_bootstrap import get_module_registry
from src.infrastructure.viewpoint_declarations import load_module_viewpoint_catalog
from src.ontologies.archimate_4._loader import _PACKAGE_DIR

_REALIZATION = "archimate-realization"
_INFLUENCE = "archimate-influence"


@dataclass
class _CountingStore:
    """A ``RepositoryReadAccess`` that counts every adjacency touch — the accounting unit."""

    entities: dict[str, EntityRecord]
    connections: list[ConnectionRecord]
    _by_source: dict[str, list[ConnectionRecord]] = field(default_factory=dict)
    _by_target: dict[str, list[ConnectionRecord]] = field(default_factory=dict)
    _by_id: dict[str, ConnectionRecord] = field(default_factory=dict)
    expansions: int = 0

    def __post_init__(self) -> None:
        for conn in self.connections:
            self._by_source.setdefault(conn.source, []).append(conn)
            self._by_target.setdefault(conn.target, []).append(conn)
            self._by_id[conn.artifact_id] = conn

    def get_entity(self, artifact_id: str) -> EntityRecord | None:
        self.expansions += 1
        return self.entities.get(artifact_id)

    def find_connections_for(
        self,
        entity_id: str,
        *,
        direction: Literal["any", "outbound", "inbound"] = "any",
        conn_type: str | None = None,
    ) -> list[ConnectionRecord]:
        self.expansions += 1
        out = self._by_source.get(entity_id, [])
        inbound = self._by_target.get(entity_id, [])
        found = out if direction == "outbound" else inbound if direction == "inbound" else out + inbound
        return [c for c in found if conn_type is None or c.conn_type == conn_type]

    def get_connection(self, artifact_id: str) -> ConnectionRecord | None:
        self.expansions += 1
        return self._by_id.get(artifact_id)

    def entity_ids(self) -> set[str]:
        return set(self.entities)

    def enterprise_entity_ids(self) -> set[str]:
        return set()

    def engagement_entity_ids(self) -> set[str]:
        return set(self.entities)

    def connection_ids(self) -> set[str]:
        self.expansions += len(self._by_id)
        return set(self._by_id)

    def enterprise_connection_ids(self) -> set[str]:
        return set()

    def engagement_connection_ids(self) -> set[str]:
        return set(self._by_id)


def _entity(artifact_id: str, artifact_type: str, domain: str) -> EntityRecord:
    return EntityRecord(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        name=artifact_id,
        version="1.0",
        status="active",
        domain=domain,
        subdomain="",
        path=Path("/fixture") / f"{artifact_id}.md",
        keywords=(),
        extra={},
        content_text="",
        display_blocks={},
        display_label=artifact_id,
        display_alias="",
    )


def _conn(cid: str, source: str, target: str, conn_type: str = _REALIZATION) -> ConnectionRecord:
    return ConnectionRecord(
        artifact_id=cid,
        source=source,
        target=target,
        conn_type=conn_type,
        version="1.0",
        status="active",
        path=Path("/fixture") / f"{cid}.md",
        extra={},
        content_text="",
    )


def build_fixture(goals: int) -> tuple[_CountingStore, tuple[str, ...]]:
    """A deterministic branching motivation graph. Each goal fans out to outcomes, each outcome
    to requirements, each requirement to realizers — with reproducible incomplete branches
    (every third outcome has no requirement; every fifth requirement has no realizer) so the
    evaluator exercises terminal, missing-*, shortcut, and multi-realizer obligations. No RNG:
    the shape is a pure function of the entity index."""
    entities: dict[str, EntityRecord] = {}
    connections: list[ConnectionRecord] = []
    row_ids: list[str] = []
    cid = 0

    def edge(src: str, tgt: str, conn_type: str = _REALIZATION) -> None:
        nonlocal cid
        connections.append(_conn(f"C@{cid:06d}", src, tgt, conn_type))
        cid += 1

    for g in range(goals):
        gid = f"GOL@{g:05d}"
        entities[gid] = _entity(gid, "goal", "motivation")
        row_ids.append(gid)
        for o in range((g % 3) + 1):  # 1..3 outcome branches
            oid = f"OUT@{g:05d}-{o}"
            entities[oid] = _entity(oid, "outcome", "motivation")
            row_ids.append(oid)
            edge(oid, gid)  # outcome -realization-> goal (incoming to goal)
            if o % 3 == 2:
                continue  # incomplete branch: outcome with no requirement (missing-requirement)
            for r in range((o % 2) + 1):
                rid = f"REQ@{g:05d}-{o}-{r}"
                entities[rid] = _entity(rid, "requirement", "motivation")
                row_ids.append(rid)
                edge(rid, oid)  # requirement -realization-> outcome
                if (g + o + r) % 5 == 0:
                    continue  # requirement with no realizer (uncovered leaf)
                for k in range((r % 2) + 1):  # 1..2 realizers (multi-realizer leaf)
                    aid = f"APP@{g:05d}-{o}-{r}-{k}"
                    entities[aid] = _entity(aid, "application-component", "application")
                    edge(aid, rid)  # component -realization-> requirement
        if g % 7 == 0:  # a shortcut branch: requirement -influence-> goal
            sid = f"REQ@short-{g:05d}"
            entities[sid] = _entity(sid, "requirement", "motivation")
            edge(sid, gid, _INFLUENCE)
    return _CountingStore(entities=entities, connections=connections), tuple(row_ids)


def _registries() -> RegistrySnapshot:
    catalog = get_module_registry()
    return RegistrySnapshot(
        known_entity_types=frozenset(),
        known_connection_types=frozenset(),
        known_specialization_slugs=frozenset(),
        entity_attribute_types={},
        connection_attribute_types={},
        derivation_catalog=catalog,
    )


def _query():
    catalog = load_module_viewpoint_catalog(_PACKAGE_DIR)
    definition = catalog.get("motivation-coverage")
    if definition is None or definition.query is None:
        raise SystemExit("shipped motivation-coverage viewpoint not found or has no query")
    return definition.query


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * fraction), len(ordered) - 1)]


def measure(goals: int, warmups: int, samples: int) -> None:
    query = _query()
    registries = _registries()
    store, row_ids = build_fixture(goals)
    params = {"gaps_only": False}

    def run_once() -> tuple[float, int, int]:
        store.expansions = 0
        started = time.perf_counter()
        table = evaluate_declared_trace_table(
            query, row_ids, read_access=store, registries=registries, bound_parameters=params, limit=None
        )
        elapsed = (time.perf_counter() - started) * 1000
        rows = 0 if table is None else table.total_rows
        return elapsed, store.expansions, rows

    cold_ms, cold_expansions, rows = run_once()
    for _ in range(warmups):
        run_once()
    timings = [run_once()[0] for _ in range(samples)]

    request_timeout = registries.derivation_time_budget_seconds * 1000
    p95 = _percentile(timings, 0.95)
    print(f"machine: {platform.platform()} | python {sys.version.split()[0]}")
    print(f"fixture: goals={goals} entities={len(store.entities)} rows={len(row_ids)} materialized_rows={rows}")
    print(f"configured request time budget: {request_timeout:.0f}ms (derivation_time_budget_seconds)")
    print(f"accounting unit = one read-access adjacency touch; cold expansions={cold_expansions}")
    print(f"cold-process run: {cold_ms:.3f}ms")
    print(
        f"warm (n={samples}, warmups={warmups}): "
        f"p50={statistics.median(timings):.3f}ms p95={p95:.3f}ms "
        f"max={max(timings):.3f}ms | p95/timeout={p95 / request_timeout:.1%}"
    )
    headroom = "OK (<=70%)" if p95 <= 0.7 * request_timeout else "OVER 70% — raise timeout or clamp"
    print(f"headroom vs 70% acceptance: {headroom}")
    # Derived budget recommendation: default = expansions with generous headroom; hard clamp above.
    default_budget = int(cold_expansions * 4)
    hard_clamp = int(cold_expansions * 20)
    print(f"recommended expanded-node default={default_budget} hard_clamp={hard_clamp} "
          f"(cold_expansions x4 / x20 — must not abort ordinary live-model execution)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goals", type=int, default=30,
                        help="goal count; ~30 approximates the live self-model motivation tier")
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--samples", type=int, default=30)
    args = parser.parse_args()
    measure(args.goals, args.warmups, args.samples)


if __name__ == "__main__":
    main()
