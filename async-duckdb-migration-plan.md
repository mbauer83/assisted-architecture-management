# Implementation Plan: Concurrency Rework for the Artifact Index

**Author:** Michael Bauer
**Date:** 2026-05-31
**Status:** Draft v2 — revised after technical review (engineer + architect)

---

## Revision Note (v2)

This plan was reviewed by an engineer and an architect. Their findings were
verified against the codebase and against current (2026) DuckDB documentation,
and **all material findings were confirmed**. Two were found to be *understated*:

- The plan claimed `notify_paths_changed` is dead code "never called anywhere."
  It is in fact exported in `artifact_index/__init__.__all__` **and** actively
  called by `tests/tools/test_two_repo_and_grf.py:232`. Deleting it is an API +
  test change, not a no-op.
- The DuckDB FTS limitation is more damaging than "under-specified." DuckDB's
  FTS index **does not update incrementally** (see Concern B), which breaks the
  cheap per-write FTS upserts the current SQLite path relies on.

The key structural changes in v2:

1. **The work is split into three tracks** (see *Track Structure*), because the
   two concerns the original plan bundled — Copy-on-Write read-model and DuckDB
   backend — are independent and separately riskable. The detailed phase
   checklists are preserved, nested under the track they belong to.
2. **The DuckDB premise is dropped.** DuckDB's FTS regression (no incremental
   update) undermines the write-responsiveness goal, and its only real advantage
   (columnar analytics) is not this read model's bottleneck. The strategy is
   **keep SQLite (FTS5 + recursive CTEs) + CoW as the primary path**, with
   **Tantivy as a gated fallback** for the text index only if SQLite's read path
   falls short after CoW (see Concern B). Track 1 (CoW) removes reader-lock
   contention and is measured first to decide whether the fallback is needed.
3. **Async end-state is `AsyncArtifactStorePort` + a temporary sync adapter**,
   so the verifier/CLI/test surface migrates incrementally rather than in one
   1,057-test big bang. The adapter is explicitly temporary and removed once all
   callers are async — it is *not* a permanent sync/async seam.
4. Acceptance criteria are split into **correctness** and **performance**, AC-5
   is rewritten around measurable signals, and a **workload matrix** is added.
5. Factual errors corrected (FTS install/update semantics, Python 3.14 status,
   `notify_paths_changed`, DuckDB thread model).

---

## User Story

As a platform engineer,
I want the architecture repository backend to handle 100–200 concurrent read
requests and several concurrent writers without thread exhaustion or reader
starvation,
so that the MCP server remains responsive under realistic multi-agent load.

---

## Acceptance Criteria

ACs are split into **correctness** (must hold regardless of backend or load) and
**performance** (only meaningful against the workload matrix below). Performance
ACs name the workload row they are measured against.

### Correctness ACs

- [ ] **AC-1 (Reader lock-freedom):** Given a writer holds the write lock for
  500 ms, when 50 readers issue point-lookup requests during that window, then
  all readers return immediately without waiting for the writer (they read the
  previous committed snapshot).
- [ ] **AC-2 (Snapshot consistency — single store):** Given a writer is
  mid-mutation, when a reader retrieves any record, then the reader sees only a
  fully-committed prior snapshot — never partial state from the in-progress
  write.
- [ ] **AC-3 (Snapshot consistency — mem+DB combined reads):** Given a read that
  combines a DB query result with a `_MemStore` lookup (e.g.
  `find_connections_for`, `list_connections_by_types`), when a write commits
  between the DB query and the mem lookup, then the reader sees a single
  consistent generation — never DB IDs from generation N joined to records from
  generation N+1, or vice versa. *(This is the failure mode the naïve "swap
  `_mem` only" design introduces; see Snapshot Consistency Design.)*
- [ ] **AC-4 (Concurrent write serialisation):** Given 3 concurrent calls to
  `apply_file_changes` targeting different paths, when all complete, then the
  final `_MemStore` and secondary-index state reflect all changes with no lost
  update.
- [ ] **AC-5 (Event-loop health under load):** *(rewritten — see review #3)*
  Given 3 concurrent writers serialising on the write lock and 200 concurrent
  readers, when measured, then: (a) no read path calls `Condition.wait()` or any
  blocking lock acquisition; (b) write-lock awaiters park on the event loop
  (`asyncio.Lock`), consuming no OS thread while waiting; (c) event-loop latency
  (measured via `loop.slow_callback_duration` instrumentation) stays under
  50 ms; (d) executor queue depth stays bounded (does not grow without limit).
  *Note: DuckDB/secondary-store reads dispatched via `asyncio.to_thread` legitimately
  occupy worker threads while running — "zero threads blocked" was incorrect; the
  target is "no threads blocked on the old RW lock, event loop stays responsive."*
- [ ] **AC-6 (Behaviour preservation):** All existing integration tests pass with
  no change to their *assertions* (test bodies may gain `await`).
- [ ] **AC-7 (Write correctness):** Given an entity file is updated on disk, when
  `apply_file_changes` completes, then `get_entity` returns the new record and
  `entity_context` reflects the updated adjacency.
- [ ] **AC-8 (Mutation safety of CoW):** Given `new = snap.with_entity(rec)`,
  then `snap` is unchanged — including its nested secondary-index sets
  (`connections_by_entity`, `entities_by_diagram`, etc.) and the records it
  holds. Verified by dedicated mutation-safety tests (see review #5).
- [ ] **AC-9 (CLI correctness):** Both CLI entry points
  (`artifact_write_cli.py`, `artifact_query_cli.py`) run all commands correctly
  after the async conversion, producing identical outputs to pre-migration.
- [ ] **AC-10 (FTS parity / golden):** Search results match a frozen golden
  baseline (top-10 result sets per query in the corpus; order may differ within
  score ties). *(Replaces the SQLite↔DuckDB live parity AC — see review #8.)*

### Performance ACs (measured against the workload matrix)

- [ ] **AC-P1 (Read concurrency):** Workload row **W1** (200 concurrent
  `search_fts`, warm index, 100k-record fixture, direct-service layer, executor
  per *Thread Pool Sizing*): P99 latency < 200 ms; no request times out or
  receives a 503.
- [ ] **AC-P2 (Read concurrency over HTTP/MCP):** Workload row **W2** (same as
  W1 but through the FastAPI/MCP layer): P99 < 300 ms (HTTP overhead budgeted
  separately).
- [ ] **AC-P3 (Memory ceiling):** Workload row **W5**: during a full `refresh()`
  under CoW on a 50k-record fixture, peak RSS does not exceed 2× steady-state RSS.
- [ ] **AC-P4 (Write throughput under read load):** Workload row **W3**: with 200
  readers active, a burst of 20 `apply_file_changes` writes completes with P99
  write latency < 1 s, including any secondary-index refresh cost (this is the AC
  that bounds FTS-maintenance cost — cheap row-level upserts on SQLite, or
  incremental segment indexing on the Tantivy fallback).

### Workload Matrix

Every performance AC names a row here so "P99 < X" is reproducible.

| Row | Layer | Dataset | Read mix | Write mix | State | Notes |
|-----|-------|---------|----------|-----------|-------|-------|
| **W1** | Direct service | 100k records | 200× `search_fts` | none | warm | core read-concurrency |
| **W2** | HTTP + MCP | 100k records | 200× search via REST/MCP | none | warm | end-to-end latency |
| **W3** | Direct service | 100k records | 200× mixed read | 20× `apply_file_changes` | warm | read/write contention; FTS refresh cost |
| **W4** | Direct service | 100k records | 50× point-lookup | 1 writer holds lock 500 ms | warm | AC-1 lock-freedom |
| **W5** | Direct service | 50k records | none | full `refresh()` | cold→warm | AC-P3 memory |
| **W6** | HTTP + MCP | 100k records | promotion + verifier + background sync running | concurrent | warm | the cross-feature interactions review #9 flagged |

Hardware baseline for all rows: record it in `SCALING.md` (CPU model, core
count, RAM). P99 numbers are only comparable on the same baseline.

---

## Business Context

The architecture repository MCP server is used by AI agents and human engineers
simultaneously. As multi-agent usage grows, read concurrency will regularly hit
100+ simultaneous requests. The current design has two suspected failure modes:

1. **Reader starvation (confirmed, design-level):** `_RWLock`
   (`threading.Condition`) holds the write lock across parse + `_MemStore`
   mutation + secondary-index rebuild, blocking all readers for the write
   duration. This is independent of the database engine and is addressed by
   Track 1 (CoW).
2. **Thread/pool exhaustion (asserted, not yet measured):** FastAPI's `anyio`
   thread pool fills with blocked readers/writers; the SQLite read pool (4–8
   connections) is claimed to be the concurrency ceiling.

**Open question this plan must answer before any backend change:** failure mode
(2) is currently *asserted*, not measured. Much of it is caused by the same
`_RWLock` as (1) — readers block on `Condition.wait()`, not on SQLite. After
Track 1 removes the lock, the SQLite read pool may no longer be the ceiling.
Track 1 therefore includes a load test (AC-P1/AC-P2) **on the existing SQLite
backend** to determine whether a backend change is justified at all. The
research below (Concern B) shows that mature in-memory SQLite with WAL/read-pool
splitting serves hundreds of concurrent reads/sec — so the DuckDB migration is
*not* assumed; it must earn its place.

---

## Scope

**In scope:**

- Introduce Copy-on-Write (CoW) semantics for `_MemStore` to eliminate reader
  blocking, with correct handling of nested mutable secondary indexes and record
  immutability (Track 1).
- Replace `_RWLock` (threading) with `asyncio.Lock` (write-only serialisation)
  (Track 1 / Track 3).
- Introduce `AsyncArtifactStorePort` and a **temporary** sync adapter; migrate
  callers to async incrementally (Track 3).
- Convert `ArtifactIndex` methods to `async def` behind the async port (Track 3).
- Keep SQLite (FTS5 + recursive CTEs) as the secondary-index backend; tune its
  read concurrency. Adopt the Tantivy text-index fallback only if measurements
  require it (Track 2, see Concern B).
- Update the **full** async blast radius (see review #2), not just `ArtifactIndex`:
  - `ArtifactRepository` (`src/application/artifact_repository.py`, 32 methods) —
    used by backend startup, query CLI, promotion, dedup, cleanup; **not** merely
    "CLI-facing."
  - `ArtifactRegistry` (`src/application/verification/artifact_verifier_registry.py`,
    23 methods) — entirely sync over `ArtifactStorePort`, ~15 instantiation sites
    across MCP bulk write/delete, promotion, GUI promote routes, context caches.
  - `_artifact_search.py` helper functions (`_search_entities/connections/diagrams/documents`).
  - `coordination.py` background-refresh workers (threading + event bus) that
    drive `apply_file_changes` / `refresh`.
  - **Backend startup**: `arch_backend.py:271` calls `repo.refresh()`
    synchronously *before* uvicorn's loop exists — this needs an explicit
    `asyncio.run()`/lifespan strategy, not just lazy `__init__` safety.
  - Both CLI entry points: `artifact_write_cli.py` **and** `artifact_query_cli.py`.
- Migrate the test suite to `pytest-asyncio` incrementally (Track 3), not as a
  prerequisite big bang.

**Out of scope:**

- LanceDB / vector search integration (future phase).
- DuckPGQ graph extension (recursive CTEs cover current needs in both SQLite and
  DuckDB).
- Multi-process / persistent secondary store (always rebuilt from markdown on
  startup).
- Markdown file format / parsing changes.
- HTTP API surface changes (paths, parameters, response shapes unchanged).

---

## Track Structure

The original single 7-phase sequence assumed CoW and DuckDB ship together. They
are independent. v2 splits them so each de-risks separately; **the detailed phase
checklists are preserved and nested under the relevant track.**

- **Track 1 — Read-model CoW (on the current SQLite backend).** Make `_MemStore`
  functionally immutable; replace reader-lock contention with an atomic
  read-model snapshot swap. *Independently shippable and independently
  valuable.* Ends with a load test that decides whether Track 2 is needed.
  *(Contains former Phase 0 and Phase 2.)*
- **Track 2 — Confirm SQLite, Tantivy fallback gated.** Primary path is "keep
  SQLite + CoW"; tune its read concurrency. Only if Track 1's load test shows
  SQLite still falls short do we prototype and adopt the Tantivy text-index
  fallback (Concern B). Output: a short decision record.
- **Track 3 — Full async (gated on Track 1 landing; backend per Track 2).**
  Introduce `AsyncArtifactStorePort` + temporary sync adapter, convert the index
  and the blast radius, migrate tests, add observability. *(Contains former
  Phases 3, 4, 6, 7.)*

Tracks 1 and 2 can run in parallel. Track 3 starts once Track 1 lands and Track 2
has chosen a backend.

---

## Technical Approach

### Concern A — Copy-on-Write read-model (Track 1)

Replace the single mutable `_MemStore` guarded by `_RWLock` with an immutable
read-model snapshot that is atomically replaced on each write. Readers capture a
reference to the current snapshot; the GIL makes the reference read/assignment
atomic. The snapshot is stable for the read's lifetime.

```
Before:   _MemStore (mutable)  ──RWLock──►  all readers/writers
After:    self._snapshot → ReadModel(mem, db_view, generation)   (GIL-atomic ref)
          readers: snap = self._snapshot; use snap freely, no lock
          writers: asyncio.Lock → build new ReadModel → publish via single swap
```

#### CoW must be deep enough (review #5 — confirmed)

`_MemStore` (`_mem_store.py`) holds **dicts of sets** and record objects:
`connections_by_path`, `connections_by_entity`, `entities_by_diagram`,
`connections_by_diagram` are `dict[..., set[str]]`. Shallow-copying the outer
dict still **shares the inner `set` objects** with the previous snapshot;
mutating a shared set corrupts a snapshot a reader is holding. Functional updates
must therefore:

- Copy-on-write the **specific inner set(s)** touched, not just the outer dict:
  `new_set = self.connections_by_entity[eid] | {cid}` (new frozenset/set), then
  `{**self.connections_by_entity, eid: new_set}`.
- Treat records as immutable. Verify `EntityRecord`/`ConnectionRecord`/
  `DiagramRecord`/`DocumentRecord` are frozen dataclasses (or are never mutated
  after construction); freeze them if not.
- Prefer `frozenset` for the secondary-index values and `MappingProxyType` for
  the published snapshot's dicts, *or* enforce immutability by discipline + tests.

```python
def with_entity(self, rec: EntityRecord) -> "_MemStore":
    new_entities = {**self.entities, rec.artifact_id: rec}
    new_by_path = self.entity_by_path
    if rec.host_diagram_id is None:
        new_by_path = {**self.entity_by_path, rec.path.resolve(): rec.artifact_id}
    return dataclasses.replace(self, entities=new_entities, entity_by_path=new_by_path)
# with_connection MUST also COW the affected connections_by_entity / _by_path /
# _by_diagram inner sets, not just the outer dict.
```

**AC-8** plus dedicated mutation-safety tests guard this.

#### Snapshot Consistency Design — mem + DB combined reads (review #4 — confirmed)

This is the deepest correctness issue and the original plan's biggest gap.
Several reads **mix a DB query with a `_mem` lookup** under a single read lock
today, e.g. `service.py:389 find_connections_for`:

```python
with self._lock.reading():
    with self._db.reader() as conn:
        cids = _q.connection_ids_for(conn, entity_id, ...)   # DB
    return [r for cid in cids if (r := self._mem.connections.get(cid))]  # mem
```

Today this is consistent because the **read lock spans both the DB query and the
mem lookup**. The original plan removed the read lock and swapped only `_mem`
atomically — but the DB is a *separate* mutable store mutated in place under the
write lock. With lock-free readers, a reader can read `cids` from DB generation
N and then resolve them against `_mem` generation N+1 (or vice versa), yielding
missing/mismatched records. The "swap `_mem` only" design is **not** sufficient.

Resolution: publish an **immutable read-model snapshot object** that binds the
mem snapshot and a consistent DB view together, swapped atomically:

```python
@dataclass(frozen=True)
class ReadModel:
    mem: _MemStore
    db: DbView          # backend-specific consistent view (see options)
    generation: int
```

`DbView` must give a read that is consistent with `mem` at the same generation.
Options, in order of preference / by backend:

1. **Materialize-from-DB without consulting `_mem`.** Change the mixed reads so
   the DB query returns fully-formed rows (or all the fields the caller needs),
   eliminating the second `_mem` lookup entirely. Cleanest; removes the coupling.
2. **Per-generation DB snapshot.** If the backend is cheap to snapshot (e.g.
   DuckDB read-only transaction / `BEGIN` snapshot, or a generation column the
   read filters on), bind that snapshot/version into `ReadModel.db`.
3. **Read lock around DB-backed reads only.** Keep pure-`_mem` reads lock-free
   (the common, hot path) but take a lightweight shared lock around the
   DB-then-mem reads. DB reads go through the thread pool anyway, so a shared
   read lock there costs little and is simplest to prove correct. Acceptable
   fallback if (1)/(2) are too invasive.

The chosen option is recorded in the Track 1 design step and validated by AC-3.

#### Refresh under CoW

`refresh()` builds a fresh `_MemStore` from scratch and publishes it in a single
swap — same as today but without holding readers out. Peak RSS is bounded by
AC-P3 (two snapshots live during rebuild → ≤ 2× steady state).

### Concern B — Secondary-index backend strategy (Track 2)

The original plan pre-selected DuckDB. Verification against current docs shows
that choice is **wrong** for this workload, so v2 keeps SQLite as the primary
backend and names Tantivy as the fallback. The decisive constraint is **cheap
incremental updates on every write**, which the current SQLite FTS5 path has and
DuckDB FTS lacks.

**Confirmed facts (DuckDB docs, 2026):**

- FTS is a **core** extension, loaded with `INSTALL fts; LOAD fts;` (autoloads on
  first use). The original plan's `INSTALL fts FROM community` is **wrong**.
- **The FTS index does not auto-update:** *"The FTS index will not update
  automatically when the input table changes. A workaround of this limitation can
  be recreating the index to refresh."* So keeping DuckDB FTS current after each
  `apply_file_changes` requires **rebuilding the whole FTS index** — there is no
  row-level upsert.
- DuckDB FTS uses `PRAGMA create_fts_index(...)` + `match_bm25(...)`, **not**
  SQLite-style virtual FTS tables.
- Concurrency: a single connection is shared via **per-thread `.cursor()`** for
  *every* thread that touches DuckDB, including writers — not "any number of
  threads" freely. CPU, executor, and transaction-conflict limits still apply.

**What the current SQLite path does (confirmed in `_sqlite_store.py`):** every
`upsert_*` does `DELETE FROM <x>_fts WHERE artifact_id=?; INSERT INTO <x>_fts ...`
— cheap, row-level, incremental FTS maintenance via FTS5 virtual tables. This is
exactly what DuckDB FTS cannot do.

**Why DuckDB was proposed — and whether it holds:** the stated benefit is
concurrent read parallelism beyond the SQLite 4–8 connection pool. But (a) the
reader-starvation is the `_RWLock`, fixed by Track 1 regardless of engine; and
(b) 2026 guidance shows in-memory SQLite with WAL + split read/write pools
serves hundreds of concurrent reads/sec. DuckDB's genuine edge is **columnar
analytical scans** (e.g. `all_connection_stats` aggregations over large sets),
not text search or graph traversal (recursive CTEs work in both).

#### Strategy: keep SQLite first, Tantivy as the fallback

Given the above, **DuckDB is dropped** as the backend for this rework — its FTS
regression directly undermines the write-responsiveness goal, and its only real
advantage (columnar analytics) is not what this read model is bottlenecked on.
The strategy is:

- **Primary — keep SQLite (FTS5 + recursive CTEs), add CoW only.** This is the
  detailed, default path (Track 1 + the SQLite-tuning steps in Track 2). It keeps
  the cheap row-level FTS upserts, adds no new dependency, and relies on CoW
  (removing `_RWLock`) plus SQLite read-concurrency tuning (WAL / read-pool
  sizing) for the concurrency goal. 2026 guidance shows in-memory SQLite with
  WAL + split read/write pools serving hundreds of concurrent reads/sec, so this
  is expected to suffice — Track 1's load test (T1.2.2) confirms it.

- **Fallback — SQLite for graph/stats + Tantivy for text search.** If, and only
  if, the SQLite read path does **not** meet AC-P1/AC-P2 after CoW, swap the FTS
  layer to [Tantivy](https://github.com/quickwit-oss/tantivy) (Rust/Lucene-class,
  BM25, **incremental segment** indexing — no full rebuild — multithreaded,
  embeddable in Python, ~200 ms p99 over millions of docs in 2025–2026 embedded
  use). Tantivy is the right fallback precisely because it preserves the property
  DuckDB FTS lacks: incremental updates without rebuilding the index. Graph
  traversal and connection-stats stay on SQLite (recursive CTEs already cover
  them). This adds a native dependency and a second index to keep consistent with
  the CoW snapshot — taken on only if measurements force it.

Other options considered and not pursued: DuckDB-for-everything (FTS regression),
DuckDB+SQLite-FTS hybrid (DuckDB earns nothing here once FTS stays on SQLite), and
a hand-rolled in-memory token index (reinvents tokenization/stemming/ranking).

#### Track 2 deliverables

1. **Confirm the primary path.** Run AC-P1/AC-P2 on **SQLite + CoW** (T1.2.2). If
   it meets the ACs, record "no backend change needed" — Track 2's FTS-swap steps
   are skipped entirely.
2. **Tune SQLite first, before any swap.** If the ceiling is real, exhaust the
   cheap SQLite levers — read-pool size, WAL vs. in-memory shared-cache trade-off
   — and re-measure. A pool/WAL change may close the gap with no new dependency.
3. **Only if still short, prototype the Tantivy fallback** and measure:
   incremental write latency (AC-P4), 200-reader P99 (AC-P1), and FTS golden
   parity against the SQLite baseline (AC-10).
4. Produce a short **decision record** (primary confirmed, or fallback adopted
   with the numbers that justified it).

### Async strategy — `AsyncArtifactStorePort` + temporary sync adapter (Track 3)

Per the chosen end-state: introduce `AsyncArtifactStorePort` (all 44 methods
`async def`) and a **temporary** `SyncStoreAdapter` that wraps it for sync
callers via a controlled bridge, so the ~15 `ArtifactRegistry` sites, both CLIs,
the verifier, promotion, dedup, cleanup, and ~1,057 tests migrate **incrementally**
rather than in one big bang. The adapter is deleted once all callers are async —
it exists to stage the migration, not as a permanent seam (which would re-create
exactly the sync/async split this rework aims to remove).

Migration order: external async edges first (FastAPI/MCP handlers already run in
an event loop), then application facades (`ArtifactRepository`, `ArtifactRegistry`),
then CLIs (`asyncio.run(main())`), then the test suite. The async API shape must
be **proven on one vertical slice** (e.g. `search_fts` end-to-end through the MCP
handler) before the mass test migration, so the test churn is paid once against a
stable signature (review #2).

### Secondary-store concurrency (SQLite read pool)

SQLite reads run through the existing connection pool (currently 4–8 read
connections); Track 2 tunes pool size and the WAL-vs-shared-cache trade-off
against the workload matrix. *(The DuckDB per-thread-cursor concern from review
#6 no longer applies, since DuckDB is dropped; it is documented in Concern B
only as part of why DuckDB was rejected. If the Tantivy fallback is adopted, its
own thread-safety model is followed for the text index.)*

### Thread pool sizing (configurable; review #7)

`max_workers` is a **configurable setting**, defaulting to a benchmark-derived
value, not a hard-coded 256. Start from `min(64, 4 * os.cpu_count())` and tune
against the workload matrix. Oversubscription (many threads each running a
secondary-store query) can *raise* P99. Add executor **queue-depth metrics**
(AC-5d) so saturation is observable.

```python
loop = asyncio.get_running_loop()           # get_event_loop() is deprecated (3.10+)
loop.set_default_executor(ThreadPoolExecutor(max_workers=settings.index_executor_workers))
```

### Initialization safety (corrected — includes startup refresh)

`asyncio.Lock()`/`asyncio.Event()` are constructible without a running loop in
Python 3.10+, so `ArtifactIndex.__init__` from sync contexts is fine. **But** the
original plan missed that `arch_backend.py:271` calls `repo.refresh()`
*synchronously* before uvicorn starts the loop. Once `refresh()` is async this
must move into the FastAPI **lifespan** (run inside the server's loop) or be
wrapped in `asyncio.run()` for the foreground/CLI startup path. The
`_services_mu` registry guard stays `threading.Lock` (module-level, pre-loop).

### Python version (corrected — review #10)

Python 3.13+ (already in use) satisfies all requirements. **Python 3.14.0 was
released 2025-10-07 and is stable** (the original "3.14 is in development" was
wrong). No upgrade is required for this work.

---

## Security & Auth Considerations

No new attack surface. Authentication, authorisation, input validation, and trust
boundaries are untouched. Any secondary store is process-local (in-memory, no
network port). SQL uses parameterised queries throughout. SQLite (primary) adds
no new install-time dependency. If the Tantivy fallback is adopted, verify its
native wheel installs in air-gapped/CI environments (Track 2).

---

## Data & Consistency Considerations

- **Snapshot consistency:** Readers always see a fully-committed `ReadModel`
  (mem + DB view + generation). See *Snapshot Consistency Design*; AC-2/AC-3.
- **Write serialisation:** `asyncio.Lock` admits one writer at a time; waiters
  park on the event loop (AC-5b).
- **DB transaction atomicity:** each write runs in a backend transaction; on
  failure the `ReadModel` is not published — the index stays on the previous
  generation. In-memory stores have no durability requirement (rebuilt from
  markdown on startup).
- **Secondary-store transition:** any dual-write window must be short-lived and
  bounded by golden FTS parity (AC-10) before removing the old store.
- **No aggregate mutations:** this is a read model / projection; source of truth
  is the markdown files.

---

## Resolved & Open Design Questions

- **Secondary-index backend:** *(decided)* DuckDB is rejected — its FTS index has
  **no incremental update** (`INSTALL fts; LOAD fts;` is core, not community; the
  index must be rebuilt on source change). Primary path keeps SQLite (FTS5 +
  CTEs) + CoW; Tantivy is the gated text-index fallback. See Concern B.
- **`notify_paths_changed`:** *(corrected — was wrong)* It is exported in
  `artifact_index/__init__.__all__` and **called by
  `tests/tools/test_two_repo_and_grf.py:232`**. It is **not** uncalled dead code.
  Resolution: determine whether the test exercises real behaviour; if the
  function is genuinely obsolete, remove it *and* update `__all__`, the import,
  and the test together; otherwise convert it. Tracked as an explicit task, not a
  trivial deletion.
- **FastAPI loop / `asyncio.Lock` safety:** safe to construct in `__init__`
  (3.10+). The *startup `refresh()` call* (`arch_backend.py:271`) must move to
  lifespan / `asyncio.run()` — see Initialization Safety.
- **`_ScopeRegistry` async contract:** receives a snapshot accessor
  `Callable[[], ReadModel]`; methods stay synchronous (read a stable snapshot, no
  lock). The owning async `ArtifactIndex` method calls `await self._ensure_loaded()`
  before delegating.
- **Test infrastructure scope:** ~1,057 test functions, 98% sync, 0 native async,
  19 `asyncio.run()` wrappers across 6 files. Migration is staged via the sync
  adapter (Track 3), after the async API shape is proven on a vertical slice — not
  a prerequisite big bang.

---

## Implementation Checklist

Phase numbers from v1 are preserved in brackets and grouped under their track.

### Track 1 — Read-model CoW (current SQLite backend)

#### T1.0 [was Phase 0] — Decouple `_MemStore` from `_SqliteStore`

> Pure structural refactor; no behaviour change.

- [ ] **T1.0.1** Remove all `self._mem.*` mutations from `_sqlite_store.py`
  write methods; they accept only DB row data.
  **AC: `_SqliteStore` no longer imports or references `_MemStore`.**
- [ ] **T1.0.2** Move those `_mem` mutations up into `_service_incremental.py`.
  **AC: `_service_incremental.py` owns all `_MemStore` mutation; `_SqliteStore`
  owns only DB mutation.**
- [ ] **T1.0.3** Drop the `mem: _MemStore` parameter from `_SqliteStore.__init__`.
- [ ] **T1.0.4** Update `ArtifactIndex.__init__` for the new constructor.
- [ ] **T1.0.5** Full test suite green, zero behaviour change.

#### T1.1 [was Phase 2] — Copy-on-Write `_MemStore`

- [ ] **T1.1.1** Add `with_*/without_*` functional update methods. Each
  COWs **the specific inner sets** it touches (not just outer dicts) and shares
  everything else. **AC-8.**
- [ ] **T1.1.2** Confirm/declare records immutable (frozen dataclasses); use
  `frozenset` for secondary-index values or enforce by discipline + tests.
- [ ] **T1.1.3** Refactor `_service_incremental.py` apply_* functions to be pure
  (return a new `_MemStore`, no input mutation).
- [ ] **T1.1.4** Introduce the `ReadModel(mem, db_view, generation)` snapshot
  object and choose the **mem+DB consistency** strategy (Concern A options 1/2/3).
  **AC-3.**
- [ ] **T1.1.5** Update `apply_file_changes` to build a new `ReadModel` and
  publish via a single atomic swap (still under `_RWLock.writing()` at this
  track; the lock wrapper changes in Track 3). **AC-4.**
- [ ] **T1.1.6** Update `refresh()` to build a fresh snapshot and swap. **AC-P3.**
- [ ] **T1.1.7** Update `_ScopeRegistry` to take a snapshot accessor; no lock.
- [ ] **T1.1.8** Mutation-safety tests (AC-8) + snapshot-consistency tests
  (AC-2/AC-3) including the `find_connections_for` mem+DB race.

#### T1.2 — Lock-freedom + measurement (decides Track 2)

- [ ] **T1.2.1** Remove read-lock acquisition from pure-`_mem` reads (still sync
  here). **AC-1.**
- [ ] **T1.2.2** Load test on the **current SQLite backend**: workload rows
  W1/W2/W4. Record P99, executor behaviour, RSS.
  **AC: a written conclusion on whether the SQLite read path meets AC-P1/AC-P2 —
  i.e. whether Track 2 (backend change) is needed at all.**

### Track 2 — Confirm SQLite, with Tantivy as the gated fallback

> Can run in parallel with Track 1. Primary path is "keep SQLite + CoW"; the
> Tantivy-fallback steps execute **only** if the SQLite read path falls short.

- [ ] **T2.1** Confirm the primary path: review T1.2.2's load-test conclusion. If
  SQLite + CoW meets AC-P1/AC-P2, record "no backend change needed" and **skip
  T2.3–T2.fallback**.
- [ ] **T2.2** Tune SQLite before any swap: evaluate read-pool size and the
  WAL-vs-in-memory-shared-cache trade-off; re-measure W1/W2. A pool/WAL change
  may close the gap with **no new dependency**.
- [ ] **T2.3** Only if still short, prototype the **Tantivy** text index:
  incremental segment indexing (no full rebuild), BM25. Measure incremental write
  latency (AC-P4), 200-reader P99 (AC-P1), and golden FTS parity vs. the SQLite
  baseline (AC-10). Confirm graph/stats stay on SQLite recursive CTEs unchanged.
- [ ] **T2.4** Write the short **decision record** (primary confirmed, or Tantivy
  fallback adopted with the numbers that justified it).

#### T2.fallback — Tantivy text-index swap (only if T2.4 adopts the fallback)

- [ ] **T2.fallback.1** Add `tantivy` to `pyproject.toml`; `uv sync`. Verify
  offline/CI install of the native wheel.
- [ ] **T2.fallback.2** Implement a Tantivy-backed text index covering the four
  FTS corpora (entities/connections/diagrams/documents), updated incrementally
  from the CoW write path and rebuilt from the snapshot on `refresh()`.
- [ ] **T2.fallback.3** Keep graph/stats/context on SQLite; route only
  `search_fts` to Tantivy. Ensure the text index participates in the `ReadModel`
  snapshot so it stays consistent with `_mem` (AC-3 generalises to mem+SQLite+text).
- [ ] **T2.fallback.4** Wire as a **second** index alongside SQLite FTS5;
  dual-write; read Tantivy, fall back to FTS5 on exception (transition only).
- [ ] **T2.fallback.5** Golden FTS parity (AC-10); then cut over — remove the
  dual-write/fallback and the now-unused FTS5 virtual tables.
- [ ] **T2.fallback.6** Keep a **golden regression test** of search results
  (serialized expected outputs) through at least one release after cutover
  (review #8).

### Track 3 — Full async (gated on Track 1; backend per Track 2)

#### T3.0 — Async port + temporary sync adapter (vertical slice first)

- [ ] **T3.0.1** Define `AsyncArtifactStorePort` (all methods `async def`) in
  `ports.py`.
- [ ] **T3.0.2** Implement a **temporary** `SyncStoreAdapter` bridging async →
  sync for not-yet-migrated callers. Mark it clearly as removal-on-completion.
- [ ] **T3.0.3** Prove the async shape end-to-end on **one vertical slice**
  (`search_fts`: handler → port → store → response) before mass migration.

#### T3.1 [was Phase 3] — Async write path + lock replacement

- [ ] **T3.1.1** Replace `_RWLock` write usage with `asyncio.Lock`
  (`async with self._write_lock:`). Replace `threading.Event` ready flag with
  `asyncio.Event`; `_init_lock` → `asyncio.Lock`.
- [ ] **T3.1.2** `_ensure_loaded`, `refresh`, `apply_file_changes` → `async def`;
  wrap blocking file-scan and DB work in `asyncio.to_thread`. **AC-4, AC-5.**
- [ ] **T3.1.3** Resolve `notify_paths_changed` per the corrected design question
  (remove + update `__all__`/import/test, or convert). **Not** a trivial delete.
- [ ] **T3.1.4** Delete `_rwlock.py` once no caller (read or write) uses it.

#### T3.2 [was Phase 4] — Async read path + port

- [ ] **T3.2.1** Convert read methods to `async def`; pure-`_mem` reads are
  `await self._ensure_loaded()` then a lock-free snapshot access.
- [ ] **T3.2.2** DB-querying reads dispatch via `asyncio.to_thread`, honouring the
  AC-3 consistency strategy for mem+DB combined reads.
- [ ] **T3.2.3** `_ScopeRegistry` stays sync over the snapshot accessor; the async
  `ArtifactIndex` method awaits `_ensure_loaded` then delegates.

#### T3.3 [was Phase 6] — Blast-radius conversion + entry points

- [ ] **T3.3.1** Convert `ArtifactRepository` (32 methods) to async; update its
  call sites: backend startup, `artifact_query_cli.py`, promotion, dedup,
  cleanup.
- [ ] **T3.3.2** Convert `ArtifactRegistry` (23 methods) to async; update its ~15
  instantiation sites (MCP bulk write/delete, promotion, GUI promote routes,
  context caches).
- [ ] **T3.3.3** Convert `_artifact_search.py` helpers.
- [ ] **T3.3.4** Bridge `coordination.py` background-refresh workers (threading +
  event bus) to drive async `apply_file_changes`/`refresh` (e.g. run on the loop
  or via `asyncio.run_coroutine_threadsafe`).
- [ ] **T3.3.5** Move startup `repo.refresh()` (`arch_backend.py:271`) into the
  FastAPI lifespan / `asyncio.run()`; both CLI entry points adopt
  `asyncio.run(main())`.
- [ ] **T3.3.6** Convert remaining sync FastAPI route handlers (incl. the two
  sync promote routes) and MCP handlers; remove `run_in_executor` shims.
- [ ] **T3.3.7** Configure the executor in lifespan with the **configurable**
  worker count (not hard-coded 256). **AC-5d (queue metrics).**
- [ ] **T3.3.8** Remove the temporary `SyncStoreAdapter` once all callers are
  async.

#### T3.4 [was Phase 7] — Tests & observability

- [ ] **T3.4.1** Add `pytest-asyncio`, `asyncio_mode = "auto"`; `uv sync --all-groups`.
- [ ] **T3.4.2** Migrate test functions to `async def` **incrementally** behind the
  adapter; remove the 19 `asyncio.run()` wrappers across 6 files. AST-assisted for
  the `async` prefix; manual review for the wrappers.
- [ ] **T3.4.3** Concurrency test: workload W1 (200× `search_fts`). **AC-P1.**
- [ ] **T3.4.4** Concurrent-write test: workload W3. **AC-4, AC-P4.**
- [ ] **T3.4.5** Snapshot-consistency tests: W4 + the mem+DB combined-read race.
  **AC-1, AC-2, AC-3.**
- [ ] **T3.4.6** Memory test: workload W5. **AC-P3.**
- [ ] **T3.4.7** Cross-feature test: workload W6 (promotion + verifier +
  background sync concurrently). **(review #9.)**
- [ ] **T3.4.8** Structured logging: write-lock wait time (>100 ms warn), DB query
  duration per type, `refresh()` duration/counts, executor queue depth.
- [ ] **T3.4.9** `SCALING.md`: hardware baseline, executor tuning, CoW memory
  estimation, secondary-store setup + offline/fallback behaviour, the workload
  matrix and measured numbers.

---

## Migration Rollback

This is a stateless read model — the index is rebuilt from markdown at startup.
No schema migration, no persistent data at risk. Rollback is: revert the commit,
restart. Markdown source is unchanged throughout.

- **Track 1** is independently revertible and independently valuable.
- **Track 2** is SQLite tuning + an (optional) Tantivy fallback swap; the dual-write bridge and
  golden parity test (kept through one release) are the safety net for the swap.
- **Track 3** rides on Track 1; the temporary sync adapter means async conversion
  can land incrementally and be paused between sub-phases without a broken tree.
```
