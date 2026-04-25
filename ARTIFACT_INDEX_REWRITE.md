# ArtifactIndex Concerns — Clean Re-write Plan

**Scope:** `src/infrastructure/artifact_index/` and its two callers:
`src/common/artifact_repository.py`, `src/tools/gui_routers/diagrams.py`

**Goal:** Eliminate the god-object / data-bag pattern, enforce the hexagonal
boundary between application and infrastructure, introduce protocol-based
interface segregation where it earns its keep, and achieve full testability
without compromising performance.

No backwards compatibility is required.

---

## 1. Current State Diagnosis

### 1.1 The Root Problem

`ArtifactIndex` is a mutable data bag passed by reference into free functions
across three modules (`storage.py`, `context.py`, `queries.py`). Each function
reaches directly into `index._conn`, `index._entities`, `index._lock`, etc.:

```python
# storage.py — reaches into everything
def upsert_entity_record(index: "ArtifactIndex", rec: EntityRecord) -> None:
    index._entities[rec.artifact_id] = rec
    index._entity_by_path[rec.path.resolve()] = rec.artifact_id
    with index._conn:
        ...
```

There is no encapsulation boundary. The class cannot be reasoned about or
tested in isolation because its state is mutated from the outside.

### 1.2 Cascading Violations

| Symptom | Root cause |
|---|---|
| `ArtifactRepository` holds `with self._index._lock:` while iterating dicts | Index does not own its own query surface; its lock leaks to the caller |
| `_entities`, `_connections`, `_diagrams`, `_documents` shortcut properties on `ArtifactRepository` that expose raw dicts | Index provides no typed query API; callers bypass it via property access |
| `diagrams.py` lines 135, 172, 242: `repo._entities.values()`, `repo._connections.values()` | Same — no query API means callers go directly to the backing store |
| `ArtifactRepository` imports `shared_artifact_index` from infrastructure | Application layer imports its own adapter — hexagonal boundary violated |
| Schema SQL in `schema.py`, write logic in `storage.py`, read logic in `queries.py`, projection logic in `context.py` | No single owner of the SQLite store; cohesion is cross-cut by the file split |
| `ArtifactRegistry` (verifier facade) duplicates the index via `shared_artifact_index` with an implicit extra `refresh()` | Removed `refresh()` from `__init__`; write ops now call `notify_paths_changed` for incremental sync |

### 1.3 What is Good and Must Be Preserved

- Dual in-memory + SQLite read model with reverse path indexes (fast
  incremental updates)
- Pre-computed `entity_context_stats` and `entity_context_edges` projections
- FTS5 full-text search with BM25 scoring
- Shared-instance singleton via `bootstrap.py`
- All external `ArtifactIndex` and `ArtifactRepository` method signatures
  consumed by MCP tools and GUI routers (these callers are in scope for
  mechanical updates, but the semantics are preserved)

---

## 2. Target Architecture

```
src/
  common/
    ports.py                    ← NEW: ArtifactStorePort, ArtifactScannerPort protocols
    artifact_repository.py      ← REWRITE: depends on ArtifactStorePort, not ArtifactIndex
    artifact_types.py           unchanged
    artifact_verifier_registry.py  minor: construction wiring only

  infrastructure/
    artifact_index/
      __init__.py               unchanged (re-exports ArtifactIndex, shared_artifact_index,
                                           ReadModelVersion, EntityContextReadModel, etc.)
      bootstrap.py              unchanged (singleton factory)
      coordination.py           unchanged (SSE event bus)
      events.py                 unchanged
      versioning.py             unchanged
      types.py                  unchanged (EntityContextReadModel, TypedDicts)

      _mem_store.py             NEW: _MemStore frozen-style dataclass — in-memory dicts
                                     + reverse path indexes
      _sqlite_store.py          NEW: _SqliteStore class — schema init + all write ops
                                     (upsert/delete/rebuild/projection maintenance)
      _sqlite_queries.py        NEW: pure read query functions (conn → typed results,
                                     no ArtifactIndex dependency)
      service.py                REWRITE: ArtifactIndex orchestrator — owns lock,
                                     scanning, incremental dispatch, public query API;
                                     implements ArtifactStorePort

      # Deleted:
      # storage.py, context.py, queries.py, schema.py
```

### 2.1 Dependency Graph (after)

```
GUI routers / MCP tools
        │
        ▼
ArtifactRepository          (src/common/)
        │  depends on (protocol)
        ▼
ArtifactStorePort           (src/common/ports.py)
        ▲  implemented by
        │
ArtifactIndex               (src/infrastructure/artifact_index/service.py)
   │        │
   ▼        ▼
_MemStore  _SqliteStore     (internal to infrastructure/artifact_index/)
                │
                ▼
         _sqlite_queries     (free functions; take conn: sqlite3.Connection)
```

`ArtifactRepository` has a compile-time dependency only on `ports.ArtifactStorePort`.
It never imports from `src.infrastructure.*`. The wiring (injecting a concrete
`ArtifactIndex`) happens at startup in `arch_backend.py` and `context.py`.

---

## 3. Protocol Interface Segregation Analysis

Python's structural subtyping (PEP 544) makes protocols a zero-cost boundary:
no base classes, no registration, no runtime overhead beyond a `isinstance`
check if you need it.

### 3.1 `ArtifactStorePort` ← **Primary protocol; clear benefit**

**Benefit:** Decouples `ArtifactRepository` (application layer) from
`ArtifactIndex` (infrastructure layer). Enables:
- Testing `ArtifactRepository` logic (semantic supplement, fallback scoring,
  `count_artifacts_by`) with a lightweight `FakeStore` — no SQLite, no
  file-system setup required
- Alternative store implementations (e.g. remote HTTP read model,
  test fixtures with pre-populated data)
- Type-safe dependency injection at wiring points

```python
# src/common/ports.py
from typing import Protocol, Literal
from pathlib import Path
from .artifact_types import (
    EntityRecord, ConnectionRecord, DiagramRecord, DocumentRecord,
    ArtifactSummary, RepoMount, SearchHit,
)
from src.infrastructure.artifact_index.versioning import ReadModelVersion
from src.infrastructure.artifact_index.types import EntityContextReadModel


class ArtifactStorePort(Protocol):
    # Lifecycle
    def refresh(self) -> None: ...
    def read_model_version(self) -> ReadModelVersion: ...
    def apply_file_changes(self, paths: list[Path]) -> ReadModelVersion: ...

    # Point lookups
    def get_entity(self, artifact_id: str) -> EntityRecord | None: ...
    def get_connection(self, artifact_id: str) -> ConnectionRecord | None: ...
    def get_diagram(self, artifact_id: str) -> DiagramRecord | None: ...
    def get_document(self, artifact_id: str) -> DocumentRecord | None: ...

    # Filtered list queries (all return sorted copies — callers never hold the live dict)
    def list_entities(
        self, *,
        artifact_type: str | None = None,
        domain: str | None = None,
        subdomain: str | None = None,
        status: str | None = None,
    ) -> list[EntityRecord]: ...

    def list_connections(
        self, *,
        conn_type: str | None = None,
        source: str | None = None,
        target: str | None = None,
        status: str | None = None,
    ) -> list[ConnectionRecord]: ...

    def list_diagrams(
        self, *, diagram_type: str | None = None, status: str | None = None,
    ) -> list[DiagramRecord]: ...

    def list_documents(
        self, *, doc_type: str | None = None, status: str | None = None,
    ) -> list[DocumentRecord]: ...

    def list_artifacts(
        self, *,
        artifact_type: str | list[str] | None = None,
        domain: str | list[str] | None = None,
        status: str | list[str] | None = None,
        include_connections: bool = False,
        include_diagrams: bool = False,
        include_documents: bool = False,
    ) -> list[ArtifactSummary]: ...

    # Richer queries
    def read_artifact(
        self, artifact_id: str, *,
        mode: Literal["summary", "full"] = "summary",
        section: str | None = None,
    ) -> dict[str, object] | None: ...

    def summarize_artifact(self, artifact_id: str) -> ArtifactSummary | None: ...

    def read_entity_context(self, artifact_id: str) -> EntityContextReadModel | None: ...

    def stats(self) -> dict[str, object]: ...

    # Connection-specific queries (used by various GUI routers)
    def connection_counts(self) -> dict[str, tuple[int, int, int]]: ...
    def connection_counts_for(self, entity_id: str) -> tuple[int, int, int]: ...
    def list_connections_by_types(self, types: frozenset[str]) -> list[ConnectionRecord]: ...
    def find_connections_for(
        self, entity_id: str, *,
        direction: Literal["any", "outbound", "inbound"] = "any",
        conn_type: str | None = None,
    ) -> list[ConnectionRecord]: ...
    def find_neighbors(
        self, entity_id: str, *, max_hops: int = 1, conn_type: str | None = None,
    ) -> dict[str, set[str]]: ...

    # Full-text search (returns raw hits for ArtifactRepository to enrich)
    def search_fts(
        self, query: str, *,
        limit: int,
        include_connections: bool,
        include_diagrams: bool,
        include_documents: bool,
        prefer_record_type: str | None,
        strict_record_type: bool,
    ) -> list[tuple[str, str, float]]: ...  # (artifact_id, record_type, score)

    # Scope
    def scope_for_path(self, path: Path) -> Literal["enterprise", "engagement", "unknown"]: ...
    def scope_of_entity(self, artifact_id: str) -> Literal["enterprise", "engagement", "unknown"]: ...
    def scope_of_connection(self, artifact_id: str) -> Literal["enterprise", "engagement", "unknown"]: ...

    # Registry-style queries (used by ArtifactVerifierRegistry)
    def entity_ids(self) -> set[str]: ...
    def connection_ids(self) -> set[str]: ...
    def enterprise_entity_ids(self) -> set[str]: ...
    def engagement_entity_ids(self) -> set[str]: ...
    def enterprise_connection_ids(self) -> set[str]: ...
    def engagement_connection_ids(self) -> set[str]: ...
    def enterprise_document_ids(self) -> set[str]: ...
    def enterprise_diagram_ids(self) -> set[str]: ...
    def entity_status(self, artifact_id: str) -> str | None: ...
    def entity_statuses(self) -> dict[str, str]: ...
    def connection_status(self, artifact_id: str) -> str | None: ...
    def find_file_by_id(self, artifact_id: str) -> Path | None: ...

    # Mount introspection
    @property
    def repo_mounts(self) -> list[RepoMount]: ...
    @property
    def repo_roots(self) -> list[Path]: ...
    @property
    def repo_root(self) -> Path: ...
```

**Note:** `ArtifactVerifierRegistry` also depends on many of these methods. It
can be wired with the same `ArtifactStorePort` instance, eliminating the
second `ArtifactRegistry` that currently builds its own index.

### 3.2 `ArtifactParserPort` ← **Testing protocol; moderate benefit**

The file-scanning and incremental update logic in `ArtifactIndex` calls
`parse_entity`, `parse_outgoing_file`, `parse_diagram`, `parse_document`
directly. Injecting these as a `ArtifactParserPort` dataclass makes
`ArtifactIndex` unit-testable without a real file system.

```python
# src/common/ports.py (continued)
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class ArtifactParsers:
    parse_entity: Callable[[Path, Path], EntityRecord | None]
    parse_outgoing: Callable[[Path], list[ConnectionRecord]]
    parse_diagram: Callable[[Path], DiagramRecord | None]
    parse_document: Callable[[Path], DocumentRecord | None]

    @staticmethod
    def default() -> "ArtifactParsers":
        from src.common.artifact_parsing import (
            parse_entity, parse_outgoing_file, parse_diagram, parse_document,
        )
        return ArtifactParsers(
            parse_entity=parse_entity,
            parse_outgoing=parse_outgoing_file,
            parse_diagram=parse_diagram,
            parse_document=parse_document,
        )
```

`ArtifactIndex.__init__` gains `parsers: ArtifactParsers = ArtifactParsers.default()`.
Production code is unchanged; tests inject `ArtifactParsers(parse_entity=lambda p, r: ...)`.

### 3.3 `FtsSearchProvider` ← **Not warranted at this scale**

The existing `_fts_enabled` flag already handles environments without FTS5.
A protocol here would add indirection for a single fallback branch. Skip.

### 3.4 Internal `_PersistencePort` ← **Not warranted**

`_SqliteStore` is a private, non-swappable implementation detail. The
SQLite in-memory store is fast enough that tests using it are still unit
tests in practice (no I/O). Introducing a protocol for `_SqliteStore`
would be premature abstraction.

---

## 4. Module Designs

### 4.1 `_mem_store.py` (~80 lines)

**Single responsibility:** Own the in-memory record dicts and the reverse
path→id indexes. No imports from infrastructure. No threading.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

from src.common.artifact_types import (
    ConnectionRecord, DiagramRecord, DocumentRecord, EntityRecord,
)


@dataclass
class _MemStore:
    entities: dict[str, EntityRecord] = field(default_factory=dict)
    connections: dict[str, ConnectionRecord] = field(default_factory=dict)
    diagrams: dict[str, DiagramRecord] = field(default_factory=dict)
    documents: dict[str, DocumentRecord] = field(default_factory=dict)
    # Reverse indexes: resolved path → artifact_id (or set for connections)
    entity_by_path: dict[Path, str] = field(default_factory=dict)
    connections_by_path: dict[Path, set[str]] = field(default_factory=dict)
    diagram_by_path: dict[Path, str] = field(default_factory=dict)
    document_by_path: dict[Path, str] = field(default_factory=dict)

    def clear(self) -> None:
        """Reset to empty — called before a full rebuild."""
        for attr in ("entities", "connections", "diagrams", "documents",
                     "entity_by_path", "connections_by_path",
                     "diagram_by_path", "document_by_path"):
            obj = getattr(self, attr)
            obj.clear()

    def rebuild_path_indexes(self) -> None:
        """Re-derive all four reverse indexes from the main dicts.
        Called once at the end of a full refresh when dicts are already populated.
        """
        self.entity_by_path = {r.path.resolve(): r.artifact_id for r in self.entities.values()}
        self.diagram_by_path = {r.path.resolve(): r.artifact_id for r in self.diagrams.values()}
        self.document_by_path = {r.path.resolve(): r.artifact_id for r in self.documents.values()}
        by_path: dict[Path, set[str]] = {}
        for r in self.connections.values():
            by_path.setdefault(r.path.resolve(), set()).add(r.artifact_id)
        self.connections_by_path = by_path
```

**No locking** — `_MemStore` is always accessed under `ArtifactIndex._lock`.

---

### 4.2 `_sqlite_store.py` (~320 lines)

**Single responsibility:** Own the SQLite connection and be the *sole* writer
to both the SQLite tables and the `_MemStore`. Guarantees the two stores
remain consistent after every write.

Accepts `_MemStore` by reference and a `scope_fn: Callable[[Path], str]`
from `ArtifactIndex` (encapsulates mount-scope lookup without circular dep).

```python
class _SqliteStore:
    def __init__(
        self,
        name_hash: str,
        mem: _MemStore,
        scope_fn: Callable[[Path], str],
    ) -> None:
        self._conn = sqlite3.connect(
            f"file:arch-artifact-index-{name_hash}?mode=memory&cache=shared",
            uri=True, check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._mem = mem
        self._scope = scope_fn
        self._fts_enabled = True
        self._init_schema()         # DDL — CREATE TABLE/INDEX/VIRTUAL TABLE

    # ── Write operations — update mem + SQL atomically ──────────────────────

    def upsert_entity(self, rec: EntityRecord) -> None: ...
    def delete_entity(self, artifact_id: str) -> None: ...

    def upsert_connection(self, rec: ConnectionRecord) -> None: ...
    def delete_connection(self, artifact_id: str) -> None: ...

    def upsert_diagram(self, rec: DiagramRecord) -> None: ...
    def delete_diagram(self, artifact_id: str) -> None: ...

    def upsert_document(self, rec: DocumentRecord) -> None: ...
    def delete_document(self, artifact_id: str) -> None: ...

    # ── Full rebuild (after fresh filesystem scan) ───────────────────────────

    def rebuild(self) -> None:
        """Clear + repopulate all SQL tables from mem. Calls rebuild_context_projection()."""
        ...

    # ── Incremental projection maintenance ───────────────────────────────────

    def rebuild_context_projection(self) -> None:
        """Rebuild entity_context_edges + entity_context_stats from scratch."""
        ...

    def rebuild_context_for(self, entity_id: str) -> None:
        """Incremental recompute of context rows for one entity."""
        ...

    # ── Read access for queries module ───────────────────────────────────────

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @property
    def fts_enabled(self) -> bool:
        return self._fts_enabled
```

**Key invariant:** Any code that needs to read `_mem` after a write can do so
because the write method updated both before returning. There is no window
where `_conn` and `_mem` disagree (writes are inside `with self._conn:` blocks
which are atomic).

**Line budget:** The schema DDL string (~130 lines of SQL) is extracted as a
module-level constant `_SCHEMA_SQL` at the top of the file. If the file still
exceeds 350 lines, split the DDL into `_sqlite_schema.py` (a single constant).

---

### 4.3 `_sqlite_queries.py` (~200 lines)

**Single responsibility:** Pure read queries against `sqlite3.Connection`.
No state. No writes. No threading. Only dependency: `sqlite3` + `types.py`.

All functions take `conn: sqlite3.Connection` as their first parameter — they
are standalone and can be called from a test with any connection, including
one populated with fixture data.

```python
def search_fts(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int,
    include_connections: bool,
    include_diagrams: bool,
    include_documents: bool,
    prefer_record_type: str | None,
    strict_record_type: bool,
    fts_enabled: bool,
) -> list[tuple[str, str, float]]: ...

def all_connection_stats(conn: sqlite3.Connection) -> dict[str, tuple[int, int, int]]: ...

def connection_stats_for(conn: sqlite3.Connection, entity_id: str) -> tuple[int, int, int]: ...

def connection_ids_by_types(conn: sqlite3.Connection, types: frozenset[str]) -> list[str]: ...

def connection_ids_for(
    conn: sqlite3.Connection,
    entity_id: str,
    *,
    direction: str = "any",
    conn_type: str | None = None,
) -> list[str]: ...

def find_neighbors(
    conn: sqlite3.Connection,
    entity_id: str,
    *,
    max_hops: int,
    conn_type: str | None,
) -> dict[str, set[str]]: ...

def entity_context(
    conn: sqlite3.Connection,
    mem: _MemStore,   # needed only for ConnectionRecord.version — see §4.3a
    entity_id: str,
) -> EntityContextReadModel | None: ...
```

**§4.3a — `entity_context` and `mem`:** The only field pulled from `_MemStore`
in `entity_context` is `connection.version` (not stored in `entity_context_edges`).
This can be eliminated by adding a `connection_version TEXT` column to
`entity_context_edges`, making `entity_context` purely connection-free and
removing the `mem` parameter. This is a recommended incremental improvement
tracked as an open question (§7.2).

---

### 4.4 `service.py` — `ArtifactIndex` rewrite (~250 lines)

**Single responsibility:** Orchestrate scanning, lock management, incremental
update dispatch, version tracking, and the complete public API surface.

```python
class ArtifactIndex:
    def __init__(
        self,
        repo_root: Path | list[Path] | list[RepoMount],
        parsers: ArtifactParsers = ArtifactParsers.default(),
    ) -> None:
        mounts = normalize_mounts(repo_root)
        self.repo_mounts = mounts
        self.repo_roots = [m.root for m in mounts]
        self.repo_root = mounts[0].root
        self._scope_key = service_key(mounts)
        self._lock = threading.RLock()
        self._parsers = parsers
        self._generation = 0
        self._loaded = False
        self._mem = _MemStore()
        name_hash = hashlib.blake2b(
            service_key(mounts).encode(), digest_size=10
        ).hexdigest()
        self._db = _SqliteStore(name_hash, self._mem, self._scope_for_path)
        self._etag = build_read_model_etag(self._scope_key, self._generation)
```

The class exposes **no private attributes** that callers should access. The
`_mem`, `_db`, and `_lock` attributes are implementation details. No shortcut
properties to the underlying dicts. No lock leakage.

**Complete public API on `ArtifactIndex`** (all handle their own locking):

Lifecycle:
- `refresh() -> None`
- `apply_file_changes(paths: list[Path]) -> ReadModelVersion`
- `read_model_version() -> ReadModelVersion`

Point lookups (single entity):
- `get_entity / get_connection / get_diagram / get_document`

Filtered list queries — **these are new**; they replace direct dict access:
- `list_entities(*, artifact_type, domain, subdomain, status) -> list[EntityRecord]`
- `list_connections(*, conn_type, source, target, status) -> list[ConnectionRecord]`
- `list_diagrams(*, diagram_type, status) -> list[DiagramRecord]`
- `list_documents(*, doc_type, status) -> list[DocumentRecord]`
- `list_artifacts(...) -> list[ArtifactSummary]`

Higher-level reads:
- `read_artifact(artifact_id, *, mode, section) -> dict | None`
- `summarize_artifact(artifact_id) -> ArtifactSummary | None`
- `read_entity_context(entity_id) -> EntityContextReadModel | None`
- `stats() -> dict[str, object]`

Connection-specific queries (delegating to `_sqlite_queries`):
- `connection_counts() -> dict[str, tuple[int,int,int]]`
- `connection_counts_for(entity_id) -> tuple[int,int,int]`
- `list_connections_by_types(types: frozenset[str]) -> list[ConnectionRecord]`
- `find_connections_for(entity_id, *, direction, conn_type) -> list[ConnectionRecord]`
- `find_neighbors(entity_id, *, max_hops, conn_type) -> dict[str, set[str]]`

Search:
- `search_fts(query, *, limit, include_connections, ...) -> list[tuple[str,str,float]]`

Scope queries:
- `scope_for_path(path) -> Literal["enterprise","engagement","unknown"]`
- `scope_of_entity / scope_of_connection`

Registry-style queries:
- `entity_ids / connection_ids / enterprise_* / engagement_*`
- `entity_status / entity_statuses / connection_status / find_file_by_id`

**Internal methods** (private, used only within service.py):
- `_ensure_loaded() -> None`
- `_scan_mount(mount, mem) -> None`
- `_scope_for_path(path: Path) -> str`
- `_mount_for_path(path: Path) -> RepoMount | None`
- `_is_diagram_source_path(path: Path) -> bool`
- `_is_document_path(path: Path) -> bool`
- `_bump_generation() -> None`
- `_apply_entity_change(path: Path) -> None`
- `_apply_outgoing_change(path: Path) -> None`
- `_apply_diagram_change(path: Path) -> None`
- `_apply_document_change(path: Path) -> None`

The incremental update methods (`_apply_*_change`) move from `context.py` into
`service.py` as private instance methods. This is appropriate — they are
orchestration logic, not infrastructure. The actual SQL writes go through
`self._db.upsert_*/delete_*`.

---

### 4.5 `artifact_repository.py` — Simplified (~280 lines)

**Changed constructor signature:**

```python
class ArtifactRepository:
    def __init__(
        self,
        store: ArtifactStorePort,
        semantic_provider: SemanticSearchProvider | None = None,
    ) -> None:
        self._store = store
        self._semantic = semantic_provider
```

Callsites change from `ArtifactRepository(roots)` to
`ArtifactRepository(shared_artifact_index(roots))`. There are three wiring
points: `arch_backend.py`, `artifact_mcp/context.py`, and tests.

**Removed:**
- `_entities`, `_connections`, `_diagrams`, `_documents` properties
- All `with self._index._lock:` blocks
- Import of `shared_artifact_index` from infrastructure

**All `list_*` methods become single-line delegations:**
```python
def list_entities(self, *, artifact_type=None, domain=None, ...) -> list[EntityRecord]:
    return self._store.list_entities(artifact_type=artifact_type, domain=domain, ...)
```

**`read_artifact`, `summarize_artifact`, `stats` become single-line delegations.**

**`search()` and its fallback `_search_*` methods** are the only non-trivial
logic remaining in `ArtifactRepository`. They use `self._store.list_entities()`,
`self._store.list_connections()`, etc. for the fallback Python-scoring path.
This is acceptable — the fallback is not a hot path.

**`apply_file_change` and `apply_file_changes`** delegate to `self._store`.

**`find_connections_for`, `find_neighbors`, `connection_counts*`** delegate.

**`count_artifacts_by`** is the only non-trivial computation that stays in the
repository — it aggregates the results of `list_diagrams` or `list_artifacts`.

---

### 4.6 `ArtifactVerifierRegistry` — Wiring change only

Currently constructs its own `shared_artifact_index(repo_root)`. After the
re-write, it receives a `ArtifactStorePort` at construction time:

```python
class ArtifactRegistry:
    def __init__(self, store: ArtifactStorePort) -> None:
        self._store = store
```

The duplicate index is eliminated. The same `ArtifactIndex` instance shared
with `ArtifactRepository` is injected here. Callers that currently do
`ArtifactRegistry(roots)` change to `ArtifactRegistry(shared_artifact_index(roots))`.

---

### 4.7 `diagrams.py` — Three line fixes

| Line | Current | Replacement |
|---|---|---|
| 135 | `for rec in repo._entities.values():` | `for rec in repo.list_entities():` |
| 172 | `for conn in repo._connections.values():` | `for conn in repo.list_connections():` |
| 242 | `for rec in repo._entities.values():` | `for rec in repo.list_entities():` |

No new methods needed. The existing `list_entities()` and `list_connections()`
with no filters return all records in sorted order.

---

## 5. Data Flow

### 5.1 Read path (e.g. `GET /api/entities`)

```
HTTP handler
  → ArtifactRepository.list_entities(domain="business")
  → ArtifactIndex.list_entities(domain="business")        ← acquires _lock
      → _mem.entities.values() filtered + sorted          ← returns copy
  ← list[EntityRecord]                                    ← lock released
```

**Copy semantics:** Every `list_*` method on `ArtifactIndex` returns a
**sorted copy** (a new Python list) created inside the lock. The lock is
released before the list is returned to the caller. Callers never hold a
reference to the live dict, eliminating the race condition where
`ArtifactRepository` previously iterated `_entities.values()` outside the lock.

### 5.2 Write path (e.g. file watcher triggers entity update)

```
FileWatcher → ArtifactIndex.apply_file_changes([path])
  → acquires _lock
  → _apply_entity_change(path)
      → parse_entity(path, model_root)          ← parsers injectable
      → _db.delete_entity(old_id)               ← updates _mem.entities + SQL
      → _db.upsert_entity(new_rec)              ← updates _mem.entities + SQL
      → _db.rebuild_context_for(impacted_ids)   ← updates projection tables
  → _bump_generation()
  → releases _lock
→ publish_authoritative_mutation(...)            ← SSE bus, outside lock
```

`_SqliteStore` methods execute under the `with self._conn:` SQLite transaction
context. The `_lock` (RLock on `ArtifactIndex`) is already held by the caller,
so there is no double-locking issue.

### 5.3 FTS search path

```
ArtifactRepository.search(query)
  → ArtifactIndex.search_fts(query, ...)        ← acquires _lock briefly
      → _sqlite_queries.search_fts(conn, ...)   ← SQL only, no mem access
      → returns [(artifact_id, record_type, score)]
  → releases _lock
  → enriches hits: for each (id, type, score):
      ArtifactIndex.get_entity(id) / get_connection(id) / ...
  → returns SearchResult
```

---

## 6. Testing Strategy

### 6.1 Unit testing `ArtifactRepository`

With `ArtifactStorePort` as a protocol, a lightweight fake can be constructed
in-process with no SQLite:

```python
# tests/fakes.py
class FakeStore:
    def __init__(self, entities: list[EntityRecord] = (), ...) -> None:
        self._entities = {e.artifact_id: e for e in entities}
        ...

    def list_entities(self, *, artifact_type=None, ...) -> list[EntityRecord]:
        results = [r for r in self._entities.values()
                   if artifact_type is None or r.artifact_type == artifact_type]
        return sorted(results, key=lambda r: r.artifact_id)

    # ... implement remaining protocol methods
```

Tests for `count_artifacts_by`, semantic supplement logic, fallback scoring, etc.
can now run without any file system or database.

### 6.2 Unit testing `ArtifactIndex`

The `ArtifactParsers` injection point makes `ArtifactIndex` testable without
real `.md` files:

```python
def test_entity_upsert_and_retrieve():
    fake_entity = EntityRecord(artifact_id="ent-001", name="Foo", ...)
    parsers = ArtifactParsers(
        parse_entity=lambda path, root: fake_entity if path.name == "foo.md" else None,
        parse_outgoing=lambda _: [],
        parse_diagram=lambda _: None,
        parse_document=lambda _: None,
    )
    index = ArtifactIndex([tmp_root], parsers=parsers)
    index.refresh()
    assert index.get_entity("ent-001") == fake_entity
    assert index.list_entities(artifact_type="system") == [fake_entity]
```

### 6.3 Unit testing `_sqlite_queries`

All query functions take `conn: sqlite3.Connection`. Tests can populate a
fresh in-memory SQLite database with fixture data and call query functions
directly — no `ArtifactIndex` required:

```python
def test_search_fts_returns_bm25_ranked_results():
    conn = sqlite3.connect(":memory:")
    _init_schema_on(conn)   # helper from _sqlite_store
    conn.execute("INSERT INTO entities_fts VALUES (?, ?, ...)", ...)
    hits = search_fts(conn, "payment gateway", limit=5, ...)
    assert hits[0][1] == "entity"
    assert "payment" in hits[0][0]  # artifact_id of top hit
```

### 6.4 Integration tests

Existing integration tests that use a real temp directory + real `.md` files
continue to work — the production wiring path (`ArtifactParsers.default()`)
is unchanged.

---

## 7. Open Questions

### 7.1 Constructor signature change scope

**Scope:** `ArtifactRepository(roots)` → `ArtifactRepository(store)` affects
every construction site. Known sites:

- `src/tools/arch_backend.py` — one site
- `src/tools/artifact_mcp/context.py` — `repo_cached(key)` function
- `src/common/artifact_verifier_registry.py` — becomes `ArtifactRegistry(store)`
- Tests

Action: grep all callsites before writing code; update in Phase 3.

### 7.2 Eliminate `mem` parameter from `entity_context`

Add `connection_version TEXT NOT NULL DEFAULT ''` to `entity_context_edges`.
Populate it during `rebuild_context_projection` and `rebuild_context_for`.
Then `entity_context(conn, entity_id)` has no `mem` dependency — it is a
pure SQL function. Mark as a follow-on improvement after the main re-write.

### 7.3 `_ensure_loaded` thread safety

The current double-checked locking pattern is:
```python
def _ensure_loaded(self) -> None:
    if self._loaded:        # first check (no lock)
        return
    with self._lock:
        if not self._loaded:  # second check (locked)
            self.refresh()
```

This is correct in CPython due to the GIL, but not formally safe in a
multi-interpreter / free-threaded future. Replace with a `threading.Event`
for correctness:

```python
self._ready = threading.Event()

def _ensure_loaded(self) -> None:
    if not self._ready.is_set():
        with self._lock:
            if not self._ready.is_set():
                self.refresh()
                self._ready.set()
```

Action: implement in the service.py rewrite.

### 7.4 `ArtifactVerifierRegistry` scope-filtered IDs

Currently `enterprise_entity_ids()` does a full linear scan of `_entities`
filtering by `scope_for_path(rec.path)`. These methods are called during
verification (write path). After the re-write they can be served by SQL
queries using the indexed `scope` column — much faster for large repos.
Candidate future improvement: add `scope_filtered_entity_ids(scope)` to
`_sqlite_queries.py`.

---

## 8. Implementation Checklist

### Phase 1 — New Internal Modules (no callers yet)

- [ ] **`_mem_store.py`**
  - [ ] `_MemStore` dataclass with all eight dict/reverse-index fields
  - [ ] `clear()` method
  - [ ] `rebuild_path_indexes()` method
  - [ ] Tests: `test_mem_store.py` — clear, rebuild_path_indexes

- [ ] **`_sqlite_store.py`**
  - [ ] Schema DDL extracted as `_SCHEMA_SQL` module constant (or `_sqlite_schema.py`)
  - [ ] `_SqliteStore.__init__` — creates connection, stores mem ref + scope_fn, calls `_init_schema()`
  - [ ] `upsert_entity / delete_entity` — update both `_mem.entities` + SQL + FTS
  - [ ] `upsert_connection / delete_connection` — update both + FTS
  - [ ] `upsert_diagram / delete_diagram` — update both + FTS
  - [ ] `upsert_document / delete_document` — update both + FTS
  - [ ] `rebuild()` — clear all SQL tables + `executemany` from `_mem.*` + call `rebuild_context_projection()`
  - [ ] `rebuild_context_projection()` — entity_context_edges + entity_context_stats from scratch
  - [ ] `rebuild_context_for(entity_id)` — incremental per-entity context recompute
  - [ ] Tests: `test_sqlite_store.py` — round-trip upsert/delete, projection correctness

- [ ] **`_sqlite_queries.py`**
  - [ ] `search_fts(conn, query, ...)` — BM25 ranked UNION ALL query
  - [ ] `all_connection_stats(conn)` — SELECT from entity_context_stats
  - [ ] `connection_stats_for(conn, entity_id)` — single-row SELECT
  - [ ] `connection_ids_by_types(conn, types)` — IN clause on connections
  - [ ] `connection_ids_for(conn, entity_id, ...)` — entity_context_edges query
  - [ ] `find_neighbors(conn, entity_id, ...)` — recursive CTE walk
  - [ ] `entity_context(conn, mem, entity_id)` — full context read
  - [ ] Tests: `test_sqlite_queries.py` — each function with fixture data

### Phase 2 — Rewrite `service.py`

- [ ] Constructor: `_mem: _MemStore`, `_db: _SqliteStore`, `_parsers: ArtifactParsers`
- [ ] `_ensure_loaded()` using `threading.Event` (§7.3)
- [ ] `refresh()` — scans mounts into `_mem`, calls `_db.rebuild()`
- [ ] `_scan_mount(mount, mem)` — uses `_parsers.*` callables
- [ ] `_apply_entity_change / _apply_outgoing_change / _apply_diagram_change / _apply_document_change`
  (moved from `context.py`, now private methods calling `self._db.*`)
- [ ] `apply_file_changes(paths)` — dispatch loop + `_bump_generation()`
- [ ] All new list query methods: `list_entities / list_connections / list_diagrams / list_documents`
- [ ] `list_artifacts(...)` — multi-collection gather + sort
- [ ] `read_artifact(id, *, mode, section)` — ordered lookup across all four dicts
- [ ] `summarize_artifact(id)` — same lookup, returns `ArtifactSummary`
- [ ] `stats()` — aggregate counts (inside lock, single snapshot)
- [ ] All delegation methods: `connection_counts / find_connections_for / search_fts / find_neighbors / ...`
- [ ] All scope + registry-style methods: `entity_ids / enterprise_entity_ids / entity_status / ...`
- [ ] Remove: `entity_records() / connection_records() / diagram_records() / document_records()`
  (these exposed raw dicts; replaced by typed list methods)
- [ ] Verify `ArtifactIndex` satisfies `ArtifactStorePort` (use `assert_type` or runtime check in test)
- [ ] Tests: `test_artifact_index.py` — incremental update correctness, version bumps, FTS search

### Phase 3 — Protocol + `ArtifactRepository` rewrite

- [ ] Write `src/common/ports.py` — `ArtifactStorePort` protocol (§3.1), `ArtifactParsers` (§3.2)
- [ ] Rewrite `ArtifactRepository.__init__(store: ArtifactStorePort, ...)`
- [ ] Remove `_entities / _connections / _diagrams / _documents` properties
- [ ] Remove all `with self._index._lock:` blocks
- [ ] Rewrite all `list_*` as single-line delegations
- [ ] Rewrite `read_artifact / summarize_artifact / stats` as delegations
- [ ] Update `_search_entities / _search_connections / _search_diagrams / _search_documents`
  to use `self._store.list_*()` instead of raw dict iteration
- [ ] `apply_file_change / apply_file_changes` — delegate to `self._store`
- [ ] `read_entity_context / find_connections_for / find_neighbors` — delegate
- [ ] `connection_counts / connection_counts_for / list_connections_by_types` — delegate
- [ ] `count_artifacts_by` — stays; aggregates over `self._store.list_*()` results
- [ ] Tests: `test_artifact_repository.py` — using `FakeStore` for all non-delegation logic

### Phase 3.5 — Interim: Incremental Index Notification (DONE)

Before Phase 3 (protocol + repository rewrite), the following incremental
consistency improvements were landed to fix test failures without reverting
to expensive `refresh()` calls in constructors:

- [x] **`src/infrastructure/artifact_index/bootstrap.py`** — added
  `notify_paths_changed(paths: list[Path])`: iterates all loaded `ArtifactIndex`
  instances in `_services` and calls `apply_file_changes` for paths that belong
  to each index's mounts. Synchronous. Incremental (only affected paths).

- [x] **`src/infrastructure/artifact_index/__init__.py`** — re-exports
  `notify_paths_changed`.

- [x] **`src/tools/artifact_mcp/context.py`**
  - `clear_caches_for_repo` now calls `notify_paths_changed` synchronously before
    enqueueing the async full refresh. Write ops are immediately reflected in all
    loaded indexes without waiting for the background thread.
  - `_refresh_repo_now` also calls `shared_artifact_index(roots).refresh()` so the
    `ArtifactIndex` is always in sync after a full background refresh.
  - `_apply_paths_now` calls `shared_artifact_index(roots).apply_file_changes(paths)`
    for the same incremental consistency guarantee on path-scoped refreshes.

- [x] **`src/common/artifact_verifier_registry.py`** — migrated import from
  `src.common.artifact_index` → `src.infrastructure.artifact_index` (Phase 4 partial).
  Removed `self._index.refresh()` from `__init__` (no longer needed; writes call
  `notify_paths_changed` instead).

- [x] **`src/common/artifact_repository.py`** — migrated import from
  `src.common.artifact_index` → `src.infrastructure.artifact_index` (Phase 4 partial).
  Removed `self._index.refresh()` from `__init__`.

### Phase 4 — Update Callers

- [x] **`src/common/artifact_verifier_registry.py`** — import migrated (Phase 3.5)
  - [ ] Change constructor to `ArtifactRegistry(store: ArtifactStorePort)` — deferred to Phase 3

- [x] **`src/common/artifact_repository.py`** — import migrated (Phase 3.5)
  - [ ] Change constructor to `ArtifactRepository(store: ArtifactStorePort)` — deferred to Phase 3

- [ ] **`src/tools/arch_backend.py`**
  - `index = shared_artifact_index(roots)`
  - `index.refresh()`
  - `repo = ArtifactRepository(index, semantic_provider=...)`
  - `gui_state.init_state(repo=repo, ...)`

- [ ] **`src/tools/artifact_mcp/context.py`**
  - `repo_cached(key)` → `ArtifactRepository(shared_artifact_index(roots))`
  - `registry_cached(key)` → `ArtifactRegistry(shared_artifact_index(roots))`

- [ ] **`src/tools/gui_routers/diagrams.py`**
  - L135: `repo._entities.values()` → `repo.list_entities()`
  - L172: `repo._connections.values()` → `repo.list_connections()`
  - L242: `repo._entities.values()` → `repo.list_entities()`

- [ ] Grep for any remaining `._entities`, `._connections`, `._diagrams`, `._documents`,
  `._index._lock`, `._index._conn` usages and fix

### Phase 5 — Cleanup

- [ ] Delete `src/infrastructure/artifact_index/storage.py`
- [ ] Delete `src/infrastructure/artifact_index/context.py`
- [ ] Delete `src/infrastructure/artifact_index/queries.py`
- [ ] Delete `src/infrastructure/artifact_index/schema.py`
- [ ] Update `src/infrastructure/artifact_index/__init__.py` — remove re-exports of deleted modules
- [ ] Run full test suite; fix failures
- [ ] Verify no import of deleted modules (`grep -r "from .storage\|from .context\|from .queries\|from .schema"`)

---

## 9. File Line-Count Budget

| File | Estimated lines | Status |
|---|---|---|
| `_mem_store.py` | ~80 | well within 250 soft |
| `_sqlite_store.py` | ~310 | within 350 hard (schema DDL as constant) |
| `_sqlite_queries.py` | ~200 | within 250 soft |
| `service.py` | ~250 | at 250 soft — monitor |
| `artifact_repository.py` | ~230 | within 250 soft |
| `ports.py` | ~100 | well within |

If `_sqlite_store.py` exceeds 350 lines, extract the schema DDL string into
`_sqlite_schema.py` (~130 lines) and import it. Do not split `_SqliteStore`'s
methods across files — the class boundary is the right cohesion unit.

---

## 10. Performance Considerations

| Concern | Current | After re-write |
|---|---|---|
| `list_entities()` | Iterates `_entities.values()` under `_index._lock` held by `ArtifactRepository` | Sorted copy returned by `ArtifactIndex.list_entities()` under its own lock. Same O(n) iteration; copy is correct and safe |
| `connection_counts()` | SQL `SELECT` from `entity_context_stats` | Unchanged |
| FTS search | SQL `UNION ALL` over FTS5 tables | Unchanged |
| Incremental update | O(1) path→id lookup via reverse indexes | Unchanged |
| Full refresh | Single full scan + `executemany` bulk insert | Unchanged |
| `_SqliteStore.rebuild()` | Same `DELETE + executemany` as current `rebuild_sqlite()` | Identical |
| `entity_context` query | 2 SQL queries per entity | Identical |
| `ArtifactVerifierRegistry` | Shared `ArtifactIndex` instance (no duplicate index) | Same instance, no extra refresh call |

No performance regression is expected. The copy cost of `list_entities()` is
O(n) and already existed implicitly (list comprehension inside the lock).
