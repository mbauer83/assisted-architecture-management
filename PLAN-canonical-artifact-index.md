# PLAN — One Canonical ArtifactIndex Per Physical Repo (eliminate scope-keyed duplication)

## Goal

Any running instance of this system has at most two fixed physical repository roots —
one engagement repo, one enterprise repo (enterprise optional). Today the backend can
nonetheless hold **several independent, fully-populated `ArtifactIndex` instances**
for that same pair of physical directories, keyed by which *combination* of roots a
caller happened to ask for (`{engagement}`, `{enterprise}`, `{engagement, enterprise}`).
Each instance separately parses, holds in memory, and SQLite-indexes whatever physical
content its root set covers — so engagement content that's covered by more than one
active combination is parsed and held redundantly, once per combination.

This plan replaces that with **exactly one canonical `ArtifactIndex` per physical
root** (so at most two total: engagement, enterprise), with a thin, stateless
combined-scope reader used wherever a caller needs to see both. It does not change
externally observable behavior — the point is to stop paying to build and hold the
same data more than once, and to remove the class of consistency bug this multiplicity
already caused once (see below).

**Resource-optimality, stated concretely.** In the worst realistic case today (all
three combinations simultaneously live — the common case in practice, since MCP write
tools default to engagement-only and the GUI/REST layer defaults to combined), the
same engagement-repo content is fully parsed, held in memory, and SQLite-indexed
**up to three times over** (once per combination that includes it). This plan bounds
that to **exactly once per physical root** — at most 2x total, never 3x, regardless
of how many distinct scope combinations any caller ever requests — with combined-scope
reads paying a small constant per-call fan-out cost (dispatch to the two already-warm
canonical instances) rather than a redundant full rebuild. This is the specific,
measurable sense in which the design is resource-optimal, not just "simpler."

## Requirements this design must satisfy

Grounded in two existing self-model requirements this plan must not regress:

- **`REQ@1782080517.IIl8-4` *Concurrent Reads, Serialized Writes*** (Must):
  "all store reads execute concurrently across threads via a per-thread WAL
  connection pool, while all store writes are strictly serialized through a
  single-writer queue... without blocking readers." `CombinedArtifactView`'s
  fan-out to two underlying instances must preserve this, not silently regress it
  by serializing what today is one instance's already-concurrent read path into two
  sequential calls. Concretely: **`search_fts` — the one method that actually
  touches SQLite per call — must dispatch to both underlying instances'
  `search_fts` concurrently** (a small thread-pool fan-out, consistent with this
  codebase's existing threading-based concurrency primitives — `_RWLock`
  (`_rwlock.py`), the background-refresh worker's own `threading.Thread` usage
  extracted into `_background_refresh_queue.py` — not a new concurrency model such
  as asyncio, which nothing in the `ArtifactIndex`/`_sqlite_store.py` read path uses
  today) and merge results once both return, rather than querying one instance,
  waiting, then querying the other. Pure in-memory methods (`get_entity`,
  `list_entities`, the scope-partition sets, …) do **not** need concurrent
  dispatch — a dict lookup on each of two small in-memory maps is negligible next to
  thread-dispatch overhead itself; sequential fallback/concatenation there is
  already the resource-optimal choice, not a shortcut taken under time pressure.
  State this distinction explicitly in the WS3 implementation — treating every
  method identically (either "concurrent everywhere" or "sequential everywhere")
  would be wrong in one direction or the other.
- **`REQ@1712870400.NfAmrl` *GUI Exploration and Authoring for Humans*** (Should):
  the GUI is the primary consumer of the combined-scope path today (the process-
  global `_repo`) — this plan serves it directly (lower backend memory footprint;
  removal of the staleness risk the GUI's own create/edit/delete workflows already
  hit once this session). The explicit acceptance bar: **combined-scope GUI read
  latency must not measurably regress** versus today's single already-combined
  instance — the concurrent-dispatch commitment above for `search_fts` is what
  makes this true for the one method where sequential fan-out would otherwise
  double perceived latency; every other method's fan-out cost is dict-lookup-scale
  and not observable to a human user.

## Relationship to the index-broadcast fix already shipped

A prior fix (commit `6a91735`, "broadcast every write commit to all live cached
indexes") made the current multi-instance design *correct*: `notify_paths_changed`
now updates every live cached instance whose mounts overlap a changed path, so no
instance goes silently stale. That fix is necessary regardless of this plan — new
short-lived or narrowly-scoped indexes can always appear — but it does not address
the *reason* multiple instances covering the same physical content exist in the first
place, which is pure duplication, not a functional requirement. This plan removes the
duplication at its root; the broadcast mechanism stays as defense-in-depth for
whatever legitimate multiplicity remains (see Open decisions).

## The problem, with evidence

**Every one of these is a distinct cache key** in `bootstrap._services`, keyed by
`service_key(mounts)` — the sorted, resolved root paths joined with `"|"`
(`src/infrastructure/artifact_index/bootstrap.py:25-40`, reproduced in full below).
Each instantiated key independently runs a full `refresh()` — scanning every
model/diagram/document file under its own root set
(`src/infrastructure/artifact_index/service.py`'s `refresh()`, calling `scan_mount`
per mount) — and maintains its own `_MemStore` (flat dicts *plus* six derived reverse
indexes: `entities_by_diagram`, `connections_by_diagram`, `diagrams_by_reference`,
`grf_targets_by_entity`, `attribute_type_refs`, `identity_candidates` —
`_mem_store.py:11-33`) and its own SQLite FTS index (`_sqlite_store.py`, rebuilt in
`refresh()`). None of this state is shared across instances even when their root
sets overlap.

### Call-site inventory (classified — do not re-derive; confirm and proceed)

Every current `shared_artifact_index(...)`/`get_shared_index(...)` call site, found via
`grep -rn "shared_artifact_index(\|get_shared_index("`  and classified by what root
set it actually needs. WS1 (below) is to re-run this grep against the then-current
tree (call sites drift) and confirm each classification still holds — it is **not**
starting from zero.

| Call site | Roots requested today | Classification | Notes |
|---|---|---|---|
| `src/diagram_types/c4/_resolve_model.py:66` | `[repo_root]` | Single (engagement) | Renderer resolving model refs for its own repo; no cross-repo need. |
| `src/diagram_types/sequence/renderer.py:176` | `[repo_root]` | Single (engagement) | Same pattern — renderer-local lookup. |
| `src/infrastructure/gui/routers/_diagram_write.py:78` | `[repo_root]` | Single (engagement) | Diagram write preview, engagement-scoped by construction. |
| `src/infrastructure/write/artifact_write/_artifact_deduplication.py:36` | `[repo_root]` | Single | Dedup check within one repo at a time; called once per repo where needed (see `cleanup_broken_refs.py` below for the enterprise-side call). |
| `src/infrastructure/mcp/artifact_mcp/bulk/common.py:40` (`local_apply_paths`) | `[repo_root]` | **Not part of this plan** | Applies to a throwaway staging/dry-run temp directory (`temp_repo_callbacks(staged_root)`), never the live repo — confirmed during the broadcast fix; no canonical-instance question applies. |
| `src/infrastructure/mcp/artifact_mcp/bulk/common.py:193,255` | `[live_root]` / `[repo_root]` | Single | Live-repo registry for bulk preflight/commit; one physical root at a time. |
| `src/infrastructure/mcp/artifact_mcp/bulk/candidate_state.py:306` | `[live_root]` | Single | Same live-commit path as above. |
| `src/infrastructure/mcp/artifact_mcp/admin_tools.py:46` | `root` (singular, from `resolve_repo_root`) | Single | `artifact_admin_reindex` targets one named repo at a time by design — reindexing "both" is two calls, not a combined instance. |
| `edit_tools.py::_resolve()` (via `src/infrastructure/mcp/artifact_mcp/write/_common.py`) | engagement by default | Single (default) | The default scope for every standalone MCP write tool (`artifact_delete_entity`, `artifact_edit_entity`, `artifact_edit_diagram`, …). This is the exact call path whose divergence from the GUI's combined scope caused the incident the broadcast fix addressed — confirm no such tool secretly needs enterprise visibility (expected: no, since these are engagement-write tools) as part of WS1. |
| `src/infrastructure/write/artifact_write/cleanup_broken_refs.py:99,135` | `engagement_root` | Single (engagement) | |
| `src/infrastructure/write/artifact_write/cleanup_broken_refs.py:171` | `enterprise_root` | Single (enterprise) | Confirms single-root enterprise access is a real, exercised case, not hypothetical. |
| `src/infrastructure/write/artifact_write/promote_execute.py:141` | `engagement_root` | Single (engagement) | |
| `src/infrastructure/backend/arch_backend.py:329` (`_initialise_repo`) | `[engagement_root, enterprise_root]` (enterprise omitted if unconfigured) | **Combined** | The process-global `_repo` (`gui_state.init_state`) — the GUI/REST layer's canonical "both" instance today; becomes the primary `CombinedArtifactView` construction site. |
| `src/infrastructure/gui/routers/promote.py:52,134` | `[eng_root, ent_root]` | **Combined** | Promotion plan/execute genuinely reads engagement (source) and enterprise (target) together to compute a diff — confirmed combined by inspection, not just by call shape. |
| `src/infrastructure/gui/routers/state.py:258,285` (`get_admin_write_deps`) | `[enterprise_root, repo_root?]` | **Combined** | Admin-mode enterprise-write path; registry spans both so cross-repo entity references in outgoing files validate. |
| `src/infrastructure/mcp/artifact_mcp/context.py:178,184,204,219` (`repo_cached`, `registry_cached`, `_refresh_repo_now`, `_apply_paths_now`) | whatever `roots` the caller resolved (`resolve_repo_roots(repo_scope=...)`) | **Passthrough — inherits caller's scope** | These are the shared cache/apply primitives; they do not choose scope themselves. Every MCP tool that resolves `repo_scope="both"` (the default for `artifact_query_read_artifact` and most read tools) flows through here. Fixing this file's callers to request the canonical combined view (rather than a fresh `[eng, ent]` key) covers this whole class at once. |
| `src/infrastructure/mcp/artifact_mcp/_diagram_binding_modes.py:25,98,212` | `[Path(p) for p in key.split("|") if p]` | **Passthrough — inherits caller's scope** | Reconstructs roots from an already-resolved `roots_key` string threaded through MCP call context; whatever scope the original caller resolved is what these get. No independent classification needed — fixed automatically once upstream callers request the canonical instance(s). |

**Do not treat this table as exhaustive on faith** — WS1 re-runs the grep (call
sites are added over time) and confirms nothing new has appeared with a genuinely
different requirement. The pattern above (single-root sites are overwhelmingly
either engagement-write-tool defaults or renderer/dedup-local lookups; combined
sites are overwhelmingly promotion/admin/GUI-global) is expected to hold.

### Key existing primitives (verified — reuse these, do not reinvent)

**`bootstrap.py`'s current keying** (`src/infrastructure/artifact_index/bootstrap.py:1-58`,
reproduced in full since this is the file WS2 changes):

```python
def normalize_mounts(repo_root: Path | list[Path] | list[RepoMount]) -> list[RepoMount]:
    # ... resolves to a sorted list[RepoMount]
def service_key(mounts: list[RepoMount]) -> str:
    return "|".join(sorted(str(m.root.resolve()) for m in mounts))

_services: dict[str, "ArtifactIndex"] = {}
_services_mu = threading.Lock()

def get_shared_index(factory, repo_root) -> "ArtifactIndex":
    mounts = normalize_mounts(repo_root)
    key = service_key(mounts)          # <-- keys by the FULL requested combination
    with _services_mu:
        service = _services.get(key)
        if service is None:
            service = factory(mounts)
            _services[key] = service
        return service

def notify_paths_changed(paths: list[Path]) -> None:
    # iterates every live _services value, applies changes to any whose mounts overlap
```

`service_key` is the exact thing WS2 changes: it must key by **each individual
root**, not by the combination requested, so `{engagement}` and
`{engagement, enterprise}` resolve to the *same* underlying engagement instance
rather than two.

**`ArtifactStorePort`** (`src/application/ports.py:222-227`) is composed of seven
`Protocol`s — this decomposition is the natural grouping for `CombinedArtifactView`'s
implementation, and is used as such in the per-method table below:
`ArtifactIdentityResolver`, `ArtifactLookup`, `ArtifactSearch`, `RelationshipGraph`,
`RepositoryScopeResolver`, `ArtifactIndexLifecycle`, `ArtifactMutationObserver`.

**Scope-partition primitives already exist and are already load-bearing** —
`service.py:524-566`:

```python
def scope_for_path(self, path: Path) -> Literal["enterprise", "engagement", "unknown"]:
    # checks which configured root `path` falls under; "enterprise" if infer_repo_scope(root) == "enterprise"
def scope_of_entity(self, artifact_id: str) -> Literal[...]:
    rec = self.get_entity(artifact_id)
    return self.scope_for_path(rec.path) if rec is not None else "unknown"
# scope_of_connection is identical, for connections

def enterprise_entity_ids(self) -> set[str]:
    return self._registry.enterprise_entity_ids()   # delegates to _ScopeRegistry
def engagement_entity_ids(self) -> set[str]: ...
def enterprise_connection_ids(self) -> set[str]: ...
def engagement_connection_ids(self) -> set[str]: ...
```

`_ScopeRegistry` (`src/infrastructure/artifact_index/_scope_registry.py:1-50`) backs
these with a plain filter over the instance's own `_mem`:

```python
def enterprise_entity_ids(self) -> set[str]:
    self._ensure_loaded()
    with self._lock.reading():
        return {aid for aid, r in self._mem.entities.items() if self._scope(r.path) == "enterprise"}
```

This confirms scope partitioning is **already** just "filter what I have by path" —
exactly the operation `CombinedArtifactView` needs to replicate by calling the
equivalent method on each of its two underlying canonical instances and merging.

**`find_file_by_id` already has the fallback-across-collections pattern this plan
generalizes across instances** (`_scope_registry.py:96-126`):

```python
def find_file_by_id(self, artifact_id: str) -> Path | None:
    for table in (self._mem.entities, self._mem.diagrams, self._mem.documents):
        r = table.get(artifact_id)
        if r is not None:
            return r.path
    if stable_id(artifact_id) == artifact_id:
        resolved_id = self._mem.canonical_id(artifact_id)
        ...
```

`CombinedArtifactView.find_file_by_id` is the same shape one level up: try the
engagement instance's `find_file_by_id`, then the enterprise instance's.

**`find_entity_by_workspace_id`/`find_entities_by_name` already accept a
`scope: Literal["both", "engagement", "enterprise"]` parameter**
(`ports.py:133-146`; implemented `service.py:486-514`) — but today `scope` is only
a **filter on whatever one instance already holds**, e.g.:

```python
def find_entity_by_workspace_id(self, artifact_id, *, scope="both") -> EntityRecord | None:
    rec = self._mem.entities.get(artifact_id)
    if rec is None or scope == "both":
        return rec
    return rec if self.scope_for_path(rec.path) == scope else None
```

Called on an engagement-only instance today, `scope="enterprise"` silently returns
nothing (there is no enterprise content to find), not an error — it looks like a
correct three-way scope selector but is actually narrower than it appears. **This is
a real semantic gap `CombinedArtifactView` must close, not just delegate past**: on
the combined view, `scope="both"` must merge across both canonical instances,
`scope="engagement"` must query *only* the engagement instance, and
`scope="enterprise"` *only* the enterprise instance — call out this one method pair
specifically when implementing WS3; a naive "delegate to instance A, else instance B"
strategy would only be correct for `scope="both"`.

**`ReadModelVersion`** (`src/application/read_models.py:9-12`) is a two-field
dataclass: `generation: int`, `etag: str`. This resolves D-2 concretely (see below).

**GRF proxy mechanism** (`ensure_global_artifact_reference`, referenced from
`src/infrastructure/mcp/artifact_mcp/write/connection.py`'s `_ensure_gar`) is why a
combined view never needs a cross-repo relational join: a connection from an
engagement entity to an enterprise entity is stored as engagement → GRF-proxy
(itself an engagement-repo entity), never as a raw cross-repo reference. Every
connection record's source and target already resolve within *one* repo's own
`_mem`. This is what makes "merge two independent instances' results" sufficient —
no query needs to reach across both simultaneously to resolve a single relationship.

**Duplicate-id fail-closed guarantee** (`arch_backend.py::_assert_no_duplicate_short_ids`,
calling `index.scan_duplicate_short_ids()` at startup) already asserts stable ids are
unique *within* one mount; combined with GRF-based cross-repo referencing, ids are
effectively unique across the whole system in the space that matters (no code path
today expects the same id to legitimately resolve to two different physical files
across engagement and enterprise) — this is what makes "try engagement, then
enterprise" unambiguous for single-artifact lookups.

## Proposed direction

**Exactly one canonical `ArtifactIndex` per physical root — at most two per running
instance (engagement, enterprise) — ever constructed.** `bootstrap.get_shared_index`
keys strictly by single resolved root; a request for `[engagement, enterprise]`
never allocates a third instance — instead, the caller is handed (or itself
constructs) a `CombinedArtifactView` wrapping the two canonical single-root
instances (each obtained via the *same* re-keyed `get_shared_index`, so there is
never a second engagement instance floating around either).

### `CombinedArtifactView` — method-by-method design

Grouped by `ArtifactStorePort`'s own seven constituent `Protocol`s
(`ports.py:43-227`), so the implementation can be split into one sibling module per
group from the start (see "For implementers" on file layout):

**`ArtifactIdentityResolver`** — delegate to whichever instance owns the artifact;
`find_all_by_stable_id` concatenates both instances' results (a short id could
in principle collide across repos even though full ids don't — return both
candidates rather than assuming uniqueness here specifically).
- `find_all_by_stable_id(short)` → concat both instances' results.
- `reconcile_short_id(short)` → call on both (idempotent no-op on whichever doesn't have it).
- `scan_duplicate_short_ids()` → merge both dicts (keys are paths; a genuine
  cross-repo id collision would show up as one short id mapping to paths in both —
  worth surfacing, not silently dropping either side).

**`ArtifactLookup`** — try-engagement-then-enterprise for everything (mirrors
`find_file_by_id`'s existing internal pattern, one level up):
- `get_entity`/`get_connection`/`get_diagram`/`get_document` → return engagement's
  result if not `None`, else enterprise's.
- `read_artifact`/`summarize_artifact`/`read_entity_context`/`find_file_by_id` → same
  fallback pattern.
- `stats()` → merge the two dicts' counts (sum numeric fields; this is the one
  method here that needs real merge logic, not a fallback — inventory the exact
  shape of `stats()`'s return dict when implementing, it is not part of the
  `ArtifactStorePort` protocol signature and may have grown ad hoc fields).

**`ArtifactSearch`**:
- `list_entities`/`list_connections`/`list_diagrams`/`list_documents`/`list_artifacts`
  → call both, concatenate. No dedup needed (GRF guarantee above).
- `search_fts(query, *, limit, ...)` → query both with the *same* `limit` (to avoid
  under-fetching whichever repo actually has the better matches), merge the two
  `list[tuple[str, str, float]]` result lists by the float score (third tuple
  element) descending, truncate to `limit`. This is the one place a naive
  concatenation is visibly wrong (see Test plan's ranking test) — implement the
  merge explicitly, don't rely on either side's list already being appropriately
  truncated before merging.
- `find_entity_by_workspace_id`/`find_entities_by_name` — **do not delegate to
  either single instance's own `scope` handling** (see "Key existing primitives"
  above for why that would silently narrow incorrectly). Implement directly:
  `scope="engagement"` → engagement instance only, `scope="enterprise"` →
  enterprise instance only, `scope="both"` → merge both.
- `diagrams_referencing_type_id` → concat both.

**`RelationshipGraph`** — every method here operates on connections, which per the
GRF guarantee never span repos, so straightforward concat/merge suffices for all of:
`candidate_connections_for_entities`, `connection_counts` (merge dicts, summing any
overlapping keys — should not occur given id uniqueness, but sum defensively rather
than asserting), `connection_counts_for`, `connection_counts_for_entities`,
`list_connections_by_types`, `list_connections_by_types_for_entities`,
`find_connections_for`, `diagrams_referencing_artifact`, `grf_references_to_entity`,
`find_neighbors` (merge the two `dict[str, set[str]]` hop-maps, unioning sets for any
shared key).

**`RepositoryScopeResolver`**:
- `repo_mounts`/`repo_roots` → concat both instances'.
- `repo_root` (singular) → this property assumes exactly one root; on a combined
  view this is ambiguous by construction. Audit every caller of `.repo_root` (not
  `.repo_roots`) on a combined-scope object during WS3/WS4 — if none exist (expected,
  since combined-scope code should already be using `.repo_roots`), raise
  `NotImplementedError` here rather than guessing which root to return.
- `scope_for_path`/`scope_of_entity`/`scope_of_connection` → try engagement's
  version, fall back to enterprise's (each independently returns `"unknown"` if the
  path/id isn't theirs — combine as "engagement's answer unless unknown, else
  enterprise's answer").
- `entity_status`/`connection_status` → fallback pattern (`None` from one, try the
  other).
- `entity_statuses()` → merge dicts.

**`ArtifactIndexLifecycle`**:
- `refresh()` → not meaningful as a single call on the combined view in the sense of
  "rebuild me" (there is no separate combined state to rebuild) — call both underlying
  instances' `refresh()`. Audit whether any caller actually calls `.refresh()` on a
  combined-scope object today (expected: yes, e.g. `arch_backend.py`'s startup
  `repo.refresh()`) and confirm calling both is the correct semantic (it is — startup
  wants both physical repos scanned).
- `read_model_version()` → see D-2 resolution below.
- `entity_ids()`/`connection_ids()` → union both sets.
- `enterprise_entity_ids()`/`engagement_entity_ids()`/`enterprise_connection_ids()`/
  `engagement_connection_ids()` → **route to the one instance that actually has that
  data** (`enterprise_entity_ids()` → call the *enterprise* instance's
  `entity_ids()` directly — it holds only enterprise content, so its own
  `enterprise_entity_ids()` and plain `entity_ids()` are already equivalent; do not
  call the engagement instance's `enterprise_entity_ids()`, which is always empty by
  construction and would silently work but wastes a call). Same pattern for
  `enterprise_document_ids()`/`enterprise_diagram_ids()`.

**`ArtifactMutationObserver`**:
- `apply_file_changes(paths)` → not applicable to the combined view as a single
  call in practice (a physical write always lands under one root); if ever called
  with paths spanning both roots, partition `paths` by which root each belongs to
  (`scope_for_path`) and call each affected instance's own `apply_file_changes` with
  its subset, returning... there is no single coherent `ReadModelVersion` for a
  mixed-root call — resolve as part of D-2, but the expected real-world case is this
  method is never invoked on the combined view at all, since `notify_paths_changed`
  (unchanged by this plan) already resolves target instances by path independently
  of what any caller's "current" combined view object is.

### D-2 resolution: composite `ReadModelVersion`

Given `ReadModelVersion` is exactly `(generation: int, etag: str)`
(`read_models.py:9-12`), the combined view's `read_model_version()` returns:

```python
ReadModelVersion(
    generation=engagement.read_model_version().generation + enterprise.read_model_version().generation,
    etag=f"{engagement.read_model_version().etag}:{enterprise.read_model_version().etag}",
)
```

Summing generations is monotonic in either underlying instance changing (sufficient
for any caller using generation only to detect "something changed since last check");
the colon-joined etag composite is stable and equality-comparable the same way a
single instance's etag is today. No caller needs to decompose the composite back into
per-repo parts — audit this during WS3 to confirm, but no current caller does
anything with `ReadModelVersion` beyond storing and comparing it for equality/
change-detection (SSE broadcast payloads, ETag headers).

### Call-site migration

Every call site classified **Combined** in the inventory above switches to
obtaining the shared `CombinedArtifactView` instead of calling
`shared_artifact_index([eng, ent])` directly — concretely, a new
`combined_artifact_index(engagement_root, enterprise_root)` function alongside
`shared_artifact_index` in `bootstrap.py`, itself backed by the *same* `_services`
singleton cache (so the combined view object itself is also a singleton, not
reconstructed per call) but returning a `CombinedArtifactView` wrapping two
`get_shared_index` calls rather than a single `factory(mounts)` call. Call sites
classified **Single** are unaffected — they already call `shared_artifact_index`
with one root and now transparently share the *same* instance a combined view
would also be built from. Call sites classified **Passthrough** need no direct
change; they inherit whatever their caller resolves once the caller itself is fixed.

## Self-model changes (describe at the granularity this plan operates at)

This plan operates at the *component/data-structure* level (a caching/indexing
mechanism inside the Architecture Backend), not at the motivation or business level
— so the self-model changes belong under `APP@1777293133.OYEmP1` *Architecture
Backend* (confirmed existing application-component; see also the *Architecture
Backend — Components* C4 diagram, `CC@1780829793.K3l46j`, for the diagram this may
need a corresponding update in once implemented). Per this project's own descriptions-
over-connections-over-entities discipline, prefer enriching existing entities; add
new ones only where a structural fact genuinely has no home today.

- **`PRC@1777409610.wqtZ0P` *Coordinate Repository State*** — this entity's
  description was corrected during the broadcast fix (this session) to say the index
  "can exist as multiple independently-cached instances... one per distinct
  root-set scope." That sentence is accurate *today* but becomes wrong once this
  plan lands (there will be at most one instance per physical root, never one per
  *combination*). **Revise this description as part of implementing this plan, not
  before** — describe the post-refactor shape (one canonical index per physical
  root; a stateless combined view composes them; a write only ever updates the one
  instance owning the changed path) rather than leaving stale prose describing a
  design that no longer exists. Do not describe the target architecture here before
  it is real — that would be modeling aspiration as fact.
- **New data-object entity — "Canonical Per-Repo Artifact Index"** (name at
  implementer's discretion; check `artifact_authoring_guidance(filter=["data-object"])`
  for the current create/never-create guidance before naming it): represents the
  one-instance-per-physical-root invariant itself. This is a genuinely new
  structural fact with no existing home — `DOB@1712870400.3rilik` *SQLite Index*
  models the search-acceleration structure *inside* one instance; nothing today
  models the higher-level fact that exactly one such instance exists per physical
  root. Composition: *Architecture Backend* → composes → this entity (multiplicity
  1..2, stated in the description, not as a fabricated cardinality connection — see
  D-4 in `PLAN-modeling-ux-and-self-model-uplift.md` for why this project states
  multiplicity in prose/connection cardinality rather than inventing per-instance
  entities). `DOB@1712870400.3rilik` *SQLite Index* becomes composed *by* this new
  entity (one per canonical index), correcting today's implicit assumption of
  a single SQLite Index system-wide.
- **New function entity — "Compose Combined-Scope Read"** (name at implementer's
  discretion): represents the stateless combined-view read path
  (`CombinedArtifactView`). Realizes/serves `PRC@1777409610.wqtZ0P` *Coordinate
  Repository State*'s revised guarantee; is triggered by (or composed under) the
  same reads that today resolve `repo_scope="both"`. Keep the description honest
  about what it is: a read-time composition, not a cache — it holds no state of its
  own and therefore cannot itself go stale, which is the specific architectural
  property that makes this design immune to the class of bug the broadcast fix
  addressed. State explicitly in the description which port methods merge results
  (search, listings) versus which fall back engagement-then-enterprise (single-id
  lookups) — this asymmetry is a real, non-obvious fact about the mechanism worth
  recording, not implementation trivia to omit.
- **`CC@1780829793.K3l46j` *Architecture Backend — Components*** — read this
  diagram's current content before deciding whether it needs a corresponding update
  (it may already be too high-level to show internal indexing structure, in which
  case no change is needed — do not add detail to a C4-components-level diagram
  that belongs at a lower level of abstraction than the diagram's own stated
  viewpoint).
- **Do not** create the two new entities, or revise `PRC@1777409610.wqtZ0P`, until
  the corresponding workstream below actually lands — self-model entries should
  describe what is true of the running system, not a plan for it (this plan
  document is where the plan lives).
- Use `artifact_authoring_guidance` before creating either new entity,
  `dry_run=true` then commit, `artifact_verify` after each batch, full-property
  `artifact_edit_entity` replacement for the `PRC` revision — standard process for
  this repo, unchanged by anything in this plan.

## Workstreams

| WS | Title | Depends on | Notes |
|----|-------|-----------|-------|
| 1 | Audit: re-confirm the call-site inventory above against the then-current tree (`grep -rn "shared_artifact_index(\|get_shared_index("` ) and resolve D-1 for every *Single*-classified site | — | Starts from the inventory above, does not redo it from scratch; only needs to confirm no new site has appeared and no site secretly needs isolation for a correctness/permission reason |
| 2 | Re-key `bootstrap.get_shared_index`/`service_key` to one canonical instance per physical root (see "Key existing primitives" code excerpt above for exactly what changes); single-root call sites need no further change | 1 | Mechanical once WS1 confirms no call site was relying on cross-root isolation for correctness |
| 3 | `CombinedArtifactView` implementing `ArtifactStorePort` per the method-by-method design above, split across sibling modules by the port's own seven `Protocol` groupings | 2 | The larger half — budget for a full read-path implementation, not a thin wrapper; the design section above is the spec, not just a sketch |
| 4 | Add `combined_artifact_index(engagement_root, enterprise_root)` to `bootstrap.py`; migrate every *Combined*-classified call site onto it | 3 | Mechanical once WS3 lands; each migrated call site drops one redundant full-repo parse |
| 5 | Reassess `notify_paths_changed`'s broadcast loop now that most combinations collapse to "one instance per changed root" — confirm it still does the right thing for the (now much smaller) remaining multiplicity, simplify if the N-way broadcast machinery is no longer earning its complexity | 4 | Do not remove the broadcast mechanism speculatively — confirm first whether any legitimate multiplicity remains (e.g. short-lived staging indexes, which `bulk/common.py::local_apply_paths` confirms already exist and are out of this plan's scope) that still needs it |
| 6 | Self-model enrichment (see above) | 4 | Revise `PRC@1777409610.wqtZ0P`; add the two new entities; check (not necessarily edit) `CC@1780829793.K3l46j` *Architecture Backend — Components* |

## Test plan

- **Parity tests**: for every method in the per-method design table above (not just a
  sample), assert `CombinedArtifactView`'s result over two canonical instances equals
  the semantically-correct union/fallback/merge computed independently in the test —
  a hard parity gate per method group, not a spot check (mirrors
  `PLAN-scalable-bulk-staging.md`'s own parity-test precedent for its manifest
  refactor). Use a synthetic two-repo fixture: one engagement-scoped entity, one
  enterprise-scoped entity, one GRF proxy connecting them (exercising the GRF
  guarantee directly), and at least one entity/connection pair per repo whose names
  overlap in a full-text search query (to exercise the ranking-merge test below with
  real ambiguity).
- **Memory/instance-count regression test**: against the same fixture, request
  `{engagement}`, `{enterprise}`, and the combined view in sequence, and assert
  `len(bootstrap._services)` never exceeds 2 — the direct, mechanical assertion of
  this plan's goal. Also assert the *same* `ArtifactIndex` object identity
  (`is`, not `==`) backs both the standalone engagement request and the engagement
  half of the combined view — the point of this plan is one shared object, not two
  equal-but-distinct ones.
- **Search ranking test**: construct entities in both repos whose names partially
  match a query with different scores, assert the merged `search_fts` result is
  correctly score-sorted across repo boundaries, not "all engagement results (in
  their own order), then all enterprise results" — the naive-concatenation failure
  mode a real top-K merge must avoid. This is the one method where an implementer
  is most likely to ship a subtly-wrong "concat and hope" instead of an actual merge
  — make this test strict (assert exact ordering for a hand-constructed score set,
  not just "results present").
- **Concurrent-dispatch test for `search_fts`** (guards `REQ@1782080517.IIl8-4`):
  instrument (via a fake/spy `ArtifactStorePort` standing in for one of the two
  canonical instances, entered/exited with a small artificial delay) and assert the
  combined view's total `search_fts` wall-clock time is close to the *slower* of the
  two underlying calls, not their sum — the direct, mechanical check that the fan-out
  is genuinely concurrent, not sequential-but-still-technically-correct.
- **`find_entity_by_workspace_id`/`find_entities_by_name` scope test**: assert
  `scope="engagement"` on the combined view never returns an enterprise-repo record
  even when one matches, and vice versa — the specific semantic gap identified above
  that a naive delegate-to-one-instance implementation would get wrong silently.
- Extend `tests/architecture/test_index_broadcast_policy.py`'s allowlist audit (or
  add a sibling fitness function) once WS2 lands: assert `service_key`/
  `get_shared_index` are never called with a multi-root list that resolves to more
  than the two canonical single-root keys — guards against a future call site
  reintroducing a third combination.

## Out of scope

- The write-broadcast mechanism itself (`notify_paths_changed`) — already correct;
  WS5 only reassesses its *necessity*, not its correctness, once this plan reduces
  how much multiplicity it has to cover.
- Multi-engagement workspace configurations, if the workspace config format ever
  allows more than one *active* engagement root at a time — out of scope because
  today's `arch-init`/workspace config activates exactly one engagement root per
  running instance (per the premise this plan starts from); revisit if that
  changes.
- Any change to the GRF (global-entity-reference) proxy mechanism
  (`ensure_global_artifact_reference`) — it already ensures no connection needs to
  span two physically-separate stores, which is *why* a combined view can safely
  merge two independent instances without needing cross-repo relational joins; this
  plan relies on that guarantee, it does not touch it.
- `bulk/common.py::local_apply_paths`'s throwaway staging-directory index — already
  confirmed unrelated (see call-site inventory).

## Open decisions (resolve at implementation start, not before)

- **D-1**: does any current single-root call site rely on *not* seeing the other
  root's content for a correctness or permission reason, or is the physical split
  purely a historical convenience/performance artifact? (Working hypothesis, not yet
  fully confirmed: enterprise-repo *write* access is already gated by an explicit
  runtime check — `state.py`'s `is_admin_mode()` — not by which index instance is in
  scope, and the two-tier engagement/enterprise design elsewhere in this self-model
  describes the enterprise repo as a broadly-readable shared catalog, not
  confidential content — suggesting no read-side security boundary depends on
  physical index separation. WS1 must confirm this for the *Single*-classified sites
  in the inventory above before WS2 proceeds, not assume it — pay particular
  attention to `edit_tools.py::_resolve()`'s engagement-only default, since that is
  the one instance where "engagement-only" could plausibly be a deliberate write-
  permission boundary rather than convenience.) **Resolved as "no" would confirm
  this plan is safe as designed; resolved as "yes, for site X" would mean site X
  keeps calling `shared_artifact_index([single_root])` directly exactly as today —
  it does not block the rest of the plan, since single-root call sites are
  unaffected either way.**
- **D-2**: ~~exact shape of `CombinedArtifactView`'s `ReadModelVersion` composite~~
  — **resolved above** (summed generation, colon-joined etag). Re-open only if WS3's
  caller inventory finds something that decomposes the composite back into parts
  (not expected).
- **D-3**: whether `CombinedArtifactView` needs its own name distinct from
  `ArtifactIndex` in the self-model as a wholly separate technical concept, or
  whether it is more accurately modeled as a *capability* of the existing
  Architecture Backend component — resolve when writing WS6, informed by how WS3
  actually implements it (e.g. as its own class vs. a mode of an existing one).

## For implementers

- Coding guidelines: `STD@1777137196.ItT-3l` *General coding guidelines* — read
  before touching any file above; the specific bullets this plan's design already
  follows, made explicit so a review can check them directly rather than trusting
  the design section's prose alone:
  - **Aggregate roots as consistency boundaries** (guideline: "find a natural
    partitioning into aggregate roots constituting boundaries of coherence and
    consistency enforced by the aggregate root itself"). Each canonical
    per-physical-root `ArtifactIndex` **is** the aggregate root/consistency
    boundary — it owns its own `_MemStore`, SQLite index, and `_RWLock`, and
    enforces its own internal invariants (e.g. `scan_duplicate_short_ids`) under
    that lock. `CombinedArtifactView` is deliberately **not** a second aggregate
    root: it holds no independent mutable state and enforces no invariant of its
    own — it is a pure read-side composition over two existing aggregate roots.
    State this explicitly in the class's own docstring when implementing WS3; it
    is the property that makes the design immune to the staleness bug class the
    broadcast fix addressed (a stateless composition cannot itself go stale), and
    a future maintainer adding cached/derived state to `CombinedArtifactView`
    directly (instead of to one of the two canonical instances) would silently
    reintroduce that risk.
  - **No boolean-flag-driven branching for scope dispatch** (guideline: boolean
    flags changing behavior "usually indicate a need for proper separation...
    something like the strategy pattern"). The per-`Protocol` sibling-module split
    below already *is* this separation — each module is the "strategy" for its
    method group. Within a module, dispatch on the `Literal["both", "engagement",
    "enterprise"]` scope parameter (`find_entity_by_workspace_id`,
    `find_entities_by_name`) via exhaustive `match`, not `if scope == "both": ...
    elif ...: ...` chains — the guideline's own "prefer (exhaustive)
    pattern-matching" bullet.
  - **Expressions over statements** for the `ArtifactLookup` fallback family: the
    engagement-then-enterprise pattern is `engagement.get_entity(id) or
    enterprise.get_entity(id)`-shaped (or a small shared `first_not_none(*calls)`
    helper if the repetition across ~8 lookup methods gets unwieldy) — not an
    `if/else` with an intermediate mutable variable.
  - **Correctness by construction via the type checker**: implement
    `CombinedArtifactView` as a class that structurally satisfies
    `ArtifactStorePort` the same way `ArtifactIndex` already does (no `cast`, no
    `Any` on the public surface) — a missing or mistyped method must be a `zuban`
    error, not a runtime `AttributeError` discovered later. Run `uv run zuban
    check` as part of WS3, not only at the end.
  - **Prepared statements / parameterized queries** (guideline, DB-interaction
    bullet): confirm during WS3 that `_sqlite_store.py`'s existing `search_fts`
    already uses parameterized queries (expected — verify, do not assume) before
    building the merge layer on top of it; the merge layer itself touches no SQL
    directly (it operates on the `list[tuple[str, str, float]]` each side already
    returns), so this is a confirmation step, not new surface to get wrong.
  - **Immutability**: any new dataclass this plan introduces (e.g. a composite
    version type, if D-2's tuple-of-two-fields approach is later generalized)
    should be `@dataclass(frozen=True)`, matching `ReadModelVersion`, `RepoMount`,
    `Candidate`, and `ResolvedArtifact`'s existing convention in
    `ports.py`/`artifact_types.py` — do not introduce a mutable value type into a
    codebase that has been consistently immutable-by-default for this class of
    object.
- `src/infrastructure/artifact_index/service.py` is 630 lines; `_mem_store.py` is
  169; `_sqlite_store.py` is 439 — none of these are near the 350-line hard cap
  today. `CombinedArtifactView` is new code covering ~35 methods and must be split
  from the start along the same seven `Protocol` boundaries used in the design
  section above, e.g.: `_combined_lookup.py` (`ArtifactIdentityResolver` +
  `ArtifactLookup`), `_combined_search.py` (`ArtifactSearch` + the ranking merge +
  the concurrent-dispatch fan-out required above), `_combined_graph.py`
  (`RelationshipGraph`), `_combined_scope.py` (`RepositoryScopeResolver` +
  `ArtifactIndexLifecycle` + `ArtifactMutationObserver`), with a slim
  `combined_index.py` composing them into the concrete `ArtifactStorePort`
  implementation — do not write one large file and split reactively.
- Run `tests/architecture/test_dependency_policy.py` after any change to which
  layer constructs `CombinedArtifactView` — this is exactly the kind of
  composition-root-adjacent object that can accidentally violate hexagonal
  layering if wired as an ambient/service-locator lookup instead of an explicit
  injected dependency.
- No plan/workstream names in code, tests, or commit messages — use feature/
  concept names (e.g. "combined-scope index view", not "WS3").
