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
  sequential calls. **Classify by backing store, not by API shape** — checked
  directly against `service.py` (grep for `self._db.reader(`): eleven methods hit
  SQLite per call, not just `search_fts` — `read_entity_context`,
  `candidate_connections_for_entities`, `connection_counts`,
  `connection_counts_for`, `connection_counts_for_entities`,
  `list_connections_by_types`, `list_connections_by_types_for_entities`,
  `find_connections_for`, `find_neighbors`, `diagrams_referencing_type_id`, and
  `search_fts` itself. **Every one of these eleven must dispatch to both
  underlying instances concurrently**, not just `search_fts` — sequential fan-out
  on any of them doubles latency on the combined path exactly the same way it
  would for search. Use **one bounded shared `ThreadPoolExecutor`** (module-level,
  sized small — e.g. 4 workers, since fan-out is always exactly 2 calls per
  combined-view invocation) created once in `combined_index.py`, not a per-call
  pool construction (pool creation itself is not free and there is no reason to
  pay it on every read). Pure in-memory methods (`get_entity`, `list_entities`,
  the scope-partition sets, …) do **not** need concurrent dispatch — a dict lookup
  on each of two small in-memory maps is negligible next to thread-dispatch
  overhead itself; sequential fallback/concatenation there is already the
  resource-optimal choice, not a shortcut taken under time pressure. State this
  distinction explicitly in the WS3 implementation — treating every method
  identically (either "concurrent everywhere" or "sequential everywhere") would be
  wrong in one direction or the other, and this is a materially different (larger)
  set of concurrent methods than a shape-based classification would suggest.
- **`REQ@1712870400.NfAmrl` *GUI Exploration and Authoring for Humans*** (Should):
  the GUI is the primary consumer of the combined-scope path today (the process-
  global `_repo`) — this plan serves it directly (lower backend memory footprint;
  removal of the staleness risk the GUI's own create/edit/delete workflows already
  hit once this session). The explicit acceptance bar: **combined-scope GUI read
  latency must not measurably regress** versus today's single already-combined
  instance — the concurrent-dispatch commitment above for the eleven SQLite-backed
  methods is what makes this true; every purely in-memory method's fan-out cost is
  dict-lookup-scale and not observable to a human user.

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
reproduced in full since this is the file WS2a/2b change):

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

`service_key` is the exact thing WS2a changes: it must key by **each individual
root**, not by the combination requested, so `{engagement}` and
`{engagement, enterprise}` resolve to the *same* underlying engagement instance
rather than two — additively at first (multi-root requests still work the old way
until WS4), then exclusively once WS4's callers have all migrated (see
"Workstream ordering constraint" below).

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

**Duplicate-id guarantee — narrower than "ids never collide across repos" suggests.**
`arch_backend.py::_assert_no_duplicate_short_ids`
calls `scan_duplicate_short_ids()` on `index = shared_artifact_index(roots)` where
`roots` is `[engagement_root, enterprise_root]` **today** (`arch_backend.py:326`) —
i.e. the startup check already runs against the *combined* mount's `_MemStore`, so
it already effectively catches a short id colliding across engagement and
enterprise, not just within one repo. **This must not regress**: post-refactor,
`_assert_no_duplicate_short_ids` runs against `combined_artifact_index(...)`, and
`CombinedArtifactView.scan_duplicate_short_ids()`'s merge must not be a naive
`{**engagement_dict, **enterprise_dict}` — that silently *drops* a same-short-id
collision (the second dict's value overwrites the first's under the same key,
exactly hiding the case worth surfacing). Merge by concatenating the path lists for
any key present in both, so a genuine cross-repo collision shows up as one short id
mapping to paths in both repos, not one.

There **is** a real, expected, non-hypothetical case where the *same full*
`artifact_id` exists in both repos simultaneously: promotion
(`execute_promotion`, `src/infrastructure/write/artifact_write/promote_execute.py`)
calls `_copy_entities` (writes the entity into `enterprise_root` under its
unchanged id), then verifies, and only *afterward* calls
`_replace_promoted_with_gars` → `_remove_promoted_file` → `path.unlink()` on the
engagement copy. Between those two steps, the identical full id is a live file in
both roots — by design, not as a bug. This is **pre-existing behavior this plan
must preserve, not newly introduce or newly break**: today's single combined
instance already has both copies in one `_MemStore` keyed by the same id (one
silently shadows the other, dict-overwrite order depending on scan order) during
this window; `CombinedArtifactView`'s engagement-then-enterprise fallback for
single-artifact lookups (`get_entity` et al.) reproduces the same
"one side wins, non-fatal" behavior for parity — **do not** make single-id lookups
raise on this specific transient case, since that would turn an expected,
self-resolving promotion step into a hard failure it isn't today.

What changes: the **startup check** (no promotion in flight, by definition) is the
right place to fail closed on a *persistent* full/short id collision — extend
`_assert_no_duplicate_short_ids` (or add a sibling startup check) to also assert no
full `artifact_id` is present in both canonical instances' `entity_ids() |
connection_ids() | ...` sets at startup, since that state is never legitimate
outside promotion's transient window. For ambiguous *short*-id resolution
specifically (`find_all_by_stable_id` returning candidates from both repos),
**reuse the existing `AmbiguousArtifactError`** (`ports.py:39`, already raised by
`artifact_verifier_registry.py:124` for exactly this class of problem — a short id
resolving to more than one candidate without a unique scope) rather than inventing
new fail-closed machinery: any `CombinedArtifactView` caller that needs a single
answer from a multi-candidate `find_all_by_stable_id` result should raise it the
same way that registry already does, not silently pick engagement-first.

**GRF-based cross-repo referencing** (see above) is what makes "try engagement,
then enterprise" an acceptable *fallback* for the ordinary case — a connection
never needs to resolve the same id from both sides simultaneously outside the
promotion window just described.

## Proposed direction

**Exactly one canonical `ArtifactIndex` per physical root — at most two per running
instance (engagement, enterprise) — ever constructed.** `bootstrap.get_shared_index`
keys strictly by single resolved root; a request for `[engagement, enterprise]`
never allocates a third instance — instead, the caller is handed (or itself
constructs) a `CombinedArtifactView` wrapping the two canonical single-root
instances (each obtained via the *same* re-keyed `get_shared_index`, so there is
never a second engagement instance floating around either).

**`combined_artifact_index` only ever accepts the one configured active pair, not
arbitrary roots.** Verified: `resolve_workspace_repo_roots`
(`src/config/workspace_paths.py:135`) already centrally enforces this at the type
level — its return type is `tuple[Path, Path] | None`, never a list, and every
caller in the codebase that needs "the" engagement/enterprise pair goes through
it (or `context.py`'s `default_engagement_repo_root`/`default_enterprise_repo_root`
wrappers around it). A dedicated `WorkspaceTopology` class would duplicate a
constraint this function already encodes structurally — not introduced here, to
avoid a redundant abstraction over something the codebase already makes
unrepresentable. What *is* missing: nothing today stops a caller from
constructing `combined_artifact_index(some_path, some_other_path)` with two paths
that didn't come from `resolve_workspace_repo_roots` — e.g. an arbitrary pair
passed by a future MCP tool parameter. Close that gap directly: `bootstrap.py`'s
`combined_artifact_index` takes exactly two required positional `Path` arguments
(not a `list[Path]`, deliberately narrower than `get_shared_index`'s signature),
and every one of the *Combined*-classified call sites in the inventory above is
migrated (WS4) to call it with roots obtained from
`resolve_workspace_repo_roots`/the equivalent already-resolved `_repo_root`/
`_enterprise_root` state in `gui_state`/`context.py` — never a caller-supplied
arbitrary pair. Add a fitness-function test (sibling to
`test_index_broadcast_policy.py`) asserting no call site invokes
`combined_artifact_index` with a literal/locally-constructed `Path(...)` pair
that didn't originate from one of those resolution functions — a textual/AST
check in the same spirit as the existing dependency-policy tests, not a runtime
guard (a runtime check on two already-`Path` arguments can't distinguish
"resolved from config" from "typed by hand" — the discipline is enforced by
which functions are allowed to call it, which is exactly what a fitness function
checks).

### `CombinedArtifactView` — method-by-method design

Grouped by `ArtifactStorePort`'s own seven constituent `Protocol`s
(`ports.py:43-227`), so the implementation can be split into one sibling module per
group from the start (see "For implementers" on file layout):

**`ArtifactIdentityResolver`** — delegate to whichever instance owns the artifact;
`find_all_by_stable_id` concatenates both instances' results (a short id could
in principle collide across repos even though full ids don't — return both
candidates rather than assuming uniqueness here specifically). Callers that need a
single answer from a multi-candidate result raise the existing
`AmbiguousArtifactError` (`ports.py:39`) — see "Duplicate-id guarantee" above —
this method itself stays a pure reporter, it does not raise.
- `find_all_by_stable_id(short)` → concat both instances' results.
- `reconcile_short_id(short)` → call on both (idempotent no-op on whichever doesn't have it).
- `scan_duplicate_short_ids()` → merge the two `dict[str, list[Path]]` by
  **concatenating the path list for any key present in both**, not
  `{**a, **b}` — a plain dict-union would let the second instance's value silently
  overwrite the first's under a shared key, hiding exactly the cross-repo
  collision this method exists to surface (see "Duplicate-id guarantee" above;
  this is the mechanism the corrected startup check in that section depends on).

**`ArtifactLookup`** — try-engagement-then-enterprise for everything (mirrors
`find_file_by_id`'s existing internal pattern, one level up):
- `get_entity`/`get_connection`/`get_diagram`/`get_document` → return engagement's
  result if not `None`, else enterprise's.
- `read_artifact`/`summarize_artifact`/`read_entity_context`/`find_file_by_id` → same
  fallback pattern (try engagement, else enterprise — a fallback only ever needs
  one side to actually resolve, so no concurrent dispatch applies here even though
  `read_entity_context` is one of the eleven SQLite-backed methods listed in the
  Requirements section — concurrency there matters for the merge/concat cases in
  `RelationshipGraph` and `search_fts`, where both sides' results are always
  needed, not for fallback lookups where only one side is ever actually queried).
- `stats()` → merge the two dicts' counts (sum numeric fields; this is the one
  method here that needs real merge logic, not a fallback — inventory the exact
  shape of `stats()`'s return dict when implementing, it is not part of the
  `ArtifactStorePort` protocol signature and may have grown ad hoc fields).

**`ArtifactSearch`**:
- `list_entities`/`list_connections`/`list_diagrams`/`list_documents`/`list_artifacts`
  → **not** plain concatenation — verified each delegates to `_list_sorted`
  (`service.py`), which returns a single globally-sorted list within one instance
  today. Concatenating engagement's sorted list then enterprise's sorted list is
  *not* the same as one global sort (e.g. an engagement entity named "Zebra" would
  sort before an enterprise entity named "Apple", which the single-instance
  behavior never produces). Call both, then **merge-sort the two already-sorted
  lists by `_list_sorted`'s own key** (inventory that key exactly when
  implementing — do not re-derive a different one) rather than concatenate-then-
  ignore-order. No dedup needed (GRF guarantee above).
- `search_fts(query, *, limit, ...)` → **not** a single global top-K merge.
  Verified in `_sqlite_queries.py::search_fts`: today's single-instance query
  already applies a **per-kind** `LIMIT` inside SQL (`per_kind_limit =
  max(limit, 1)`, one independent `ORDER BY score DESC LIMIT per_kind_limit`
  subquery per included kind — entities/connections/diagrams/documents each
  capped separately, "so that a dominant kind... cannot crowd out minority
  kinds"). A single instance can therefore already return up to `4 × limit` rows
  when all kinds are included — `limit` is a *per-kind* budget, not a total. The
  combined view must preserve this: query both instances with the same `limit`
  and kind flags (each already returns its own per-kind-balanced set), then
  **group the two result lists by `record_type`, merge-sort each kind's
  engagement+enterprise rows by score descending, and cap each kind's merged
  group at `per_kind_limit`** — concatenate the capped groups for the final
  result. Do **not** flatten-merge-then-truncate to a single `limit` across all
  kinds — a naive "concat and hope" or single-global-limit merge would shrink the
  combined result well below what either single-instance behavior already
  produces and is a visible regression (see Test plan's per-kind ranking test).
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
shared key). **Concurrency note**: verified against `service.py`, every method
named in this paragraph *except* `diagrams_referencing_artifact` and
`grf_references_to_entity` goes through `self._db.reader()` (SQLite), not just
in-memory `_mem` access — per the Requirements section above, these must dispatch
to both underlying instances concurrently via the shared executor, not
sequentially; the merge logic described here (concat/sum/union) is unaffected by
*when* both results arrive, only by whether they're fetched in parallel.

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

**`ArtifactMutationObserver` — deliberately not implemented at all.** Verified by
tracing every real caller: `_apply_paths_now` (`context.py:210-222`, the one
function MCP write paths actually depend on after a broadcast) calls
`notify_paths_changed(paths)` — a *module-level* function, not a method on
whatever `shared_artifact_index(roots)` returns — and then only calls
`.read_model_version()` (a read) on that object. No traced call site ever invokes
`.apply_file_changes()` on a combined-scope object; the only three production call
sites of `.apply_file_changes(` are `bootstrap.py`'s own broadcast loop (acting on
real single-root instances), `ArtifactRepository`'s pass-through methods
(confirmed dead code below), and `bulk/common.py`'s already-out-of-scope staging
path. `CombinedArtifactView` therefore implements exactly six of
`ArtifactStorePort`'s seven `Protocol`s — `ArtifactIdentityResolver`,
`ArtifactLookup`, `ArtifactSearch`, `RelationshipGraph`, `RepositoryScopeResolver`,
`ArtifactIndexLifecycle` — and **omits `ArtifactMutationObserver` entirely**,
consistent with `ports.py`'s own docstring on `ArtifactStorePort`: "Prefer narrow
sub-contracts where the consumer only needs a subset." This resolves the
"stateless view with mutation methods" contradiction directly, rather than
implementing a method that is never meant to be called: a type that doesn't
declare the method can't be misused as if it did, whereas a method that raises at
runtime can still be called by mistake and only fails later.

This has one concrete consequence elsewhere: introduce
`ReadableArtifactStore(ArtifactLookup, ArtifactSearch, RelationshipGraph,
RepositoryScopeResolver, ArtifactIndexLifecycle, ArtifactIdentityResolver,
Protocol)` in `ports.py` (the same six, named for what it is) and change
`ArtifactRepository.__init__`'s `store: ArtifactStorePort` parameter
(`artifact_repository.py:45`) to `store: ReadableArtifactStore`. `ArtifactIndex`
already structurally satisfies the wider `ArtifactStorePort`, so it trivially
satisfies this narrower type too — no change needed at any existing single-root
call site. **Delete `ArtifactRepository.apply_file_changes` and
`.apply_file_change`** (`artifact_repository.py:73-76`) as part of this same
change — verified via `grep -rn "\.apply_file_changes(\|\.apply_file_change("
src/` that neither has a production caller today (the index-broadcast fix already
replaced `state.py`'s only real call site with `notify_paths_changed`); once the
constructor narrows to `ReadableArtifactStore`, these two methods become a
`zuban` type error against `self._store`, not just unused — narrow the type and
delete the dead methods together, don't leave a `# type: ignore`. Audit test
callers of these two methods during WS3 before deleting (expected: none, or tests
exercising the exact pre-fix pattern the broadcast fix already made obsolete).

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
`shared_artifact_index` in `bootstrap.py`.

**Combined views live in a second, separate cache — never in `_services`.**
Sharing `_services` between real single-root instances and combined views would
reintroduce exactly the staleness/duplication risk this whole plan exists to
remove: `notify_paths_changed` (`bootstrap.py:44-58`) iterates `_services.values()`
and calls `.apply_file_changes()` on every entry it finds; a `CombinedArtifactView`
in that same dict would either be called on a method it doesn't implement (per the
`ArtifactMutationObserver` decision above — a hard error) or, if it *did*
implement some stand-in, would double-apply every change (once via its own dict
entry, once again via the two real per-root entries `notify_paths_changed` also
updates). Concretely: add a second module-level cache in `bootstrap.py`,
`_combined_views: dict[str, "CombinedArtifactView"] = {}` (own lock, same pattern
as `_services_mu`), populated only by `combined_artifact_index`. `_services`
continues to hold **only** genuine `ArtifactIndex` instances, keyed by single
physical root once WS2a lands; `notify_paths_changed`'s iteration is unchanged and
never sees a `_combined_views` entry. `combined_artifact_index` itself is still a
singleton per resolved `(engagement_root, enterprise_root)` pair (so the view
object is not reconstructed per call) — it just isn't sharing `_services`'s dict
or its broadcast-iteration contract. This is safe *because* the view is stateless
(per the aggregate-root discussion in "For implementers" below): it never needs
its own invalidation, so it has no business being in the dict that exists
specifically to drive invalidation. Add a fitness-function assertion (extend
`tests/architecture/test_index_broadcast_policy.py` or add a sibling test) that
`_services` never contains a non-`ArtifactIndex` value — a direct, mechanical
guard against this exact class of regression recurring.

Call sites classified **Single** are unaffected — they already call
`shared_artifact_index` with one root and now transparently share the *same*
instance a combined view would also be built from. Call sites classified
**Passthrough** need no direct change; they inherit whatever their caller
resolves once the caller itself is fixed — see "Workstream ordering constraint"
below for why this must happen *before*, not after, `service_key` is restricted
to single roots.

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

## Workstream ordering constraint

Re-keying `get_shared_index`/`service_key` to reject or collapse multi-root
requests **must not land before `CombinedArtifactView` exists and every current
multi-root caller has migrated to it** — reordering by dependency, not by which
piece looks simpler in isolation. Verified against the current tree: multiple
real call sites already request `shared_artifact_index`/`get_shared_index` with a
**multi-root** list and depend on getting back a working, queryable
`ArtifactIndex` —
- `context.py::_apply_paths_now` (line 219) and `::_refresh_repo_now` (line 204),
  called via `apply_authoritative_changes`/`sync_refresh_for_roots` from
  essentially every MCP write tool's finalize step when `repo_scope="both"` —
  traced concretely through `_add_connection_impl`
  (`write/connection.py:52`, `authoritative_callbacks_for(both_roots)`) →
  `AuthoritativeMutationContext.finalize()` → `apply_authoritative_changes` →
  `_apply_paths_now(both_roots, ...)` → `shared_artifact_index(both_roots)`.
- `context.py::repo_cached`/`registry_cached` (lines 178, 184), the caches behind
  every `repo_scope="both"` MCP read/write tool.
- `state.py::get_write_deps`/`get_admin_write_deps` (lines 258, 285).
- `promote.py:52,134` and `promote_execute.py:141`.
- `arch_backend.py::_initialise_repo` (line 326), which also feeds
  `_assert_no_duplicate_short_ids` — see "Duplicate-id guarantee" above.

Restricting `service_key` to reject/collapse multi-root requests before
`CombinedArtifactView` exists and these exact call sites are migrated onto it
would break every one of them the moment that restriction merges — there would
be no working intermediate state. The workstreams below are sequenced so a
working combined-scope path always exists before anything stops honoring
multi-root requests the old way (WS2a introduces per-root keying purely
additively; only WS4, once every caller has migrated, restricts it).

## Workstreams

| WS | Title | Depends on | Notes |
|----|-------|-----------|-------|
| 1 | Audit: re-confirm the call-site inventory above against the then-current tree (`grep -rn "shared_artifact_index(\|get_shared_index("` ) and resolve D-1 for every *Single*-classified site | — | Starts from the inventory above, does not redo it from scratch; only needs to confirm no new site has appeared and no site secretly needs isolation for a correctness/permission reason |
| 2a | Introduce the single-physical-root instance cache: add per-root keying to `bootstrap.py` (see "Key existing primitives" code excerpt above) **additively** — `get_shared_index`/`service_key` start keying by single root, but multi-root requests still succeed by falling through to today's combined-instance behavior (do not remove that path yet) | 1 | Purely additive; nothing that depends on multi-root `shared_artifact_index` breaks, because that path is untouched in this step |
| 2b | Add `combined_artifact_index(engagement_root, enterprise_root)` to `bootstrap.py` and the separate `_combined_views` cache (see "Call-site migration" above) — `CombinedArtifactView` does not exist yet, so this step only wires the cache/entry-point shape | 2a | Can be developed in parallel with WS3 once the cache shape is agreed; the function body is a stub until WS3 lands |
| 3 | `CombinedArtifactView` implementing the six-`Protocol` `ReadableArtifactStore` surface per the method-by-method design above (including the corrected per-kind `search_fts` merge, global-sort `list_*` merge, and concurrent dispatch for the eleven SQLite-backed methods), split across sibling modules by protocol grouping | 2b | The larger half — budget for a full read-path implementation, not a thin wrapper; the design section above is the spec, not just a sketch |
| 4 | Migrate every *Combined*-classified and *Passthrough*-classified call site in the inventory above onto `combined_artifact_index(...)` instead of `shared_artifact_index([eng, ent])`. Only *after* every such call site is migrated and verified (full test suite green, manual GUI smoke of at least one combined-scope read and one combined-scope write): restrict `get_shared_index`/`service_key` to reject a multi-root request outright (raise, rather than silently falling through) | 3 | This is the step that actually removes the old multi-root path — sequencing it last is what keeps every intermediate commit working. `ArtifactRepository`'s `ReadableArtifactStore` narrowing and dead-method deletion (see `ArtifactMutationObserver` section above) land here too, once no call site still needs the wider type |
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
- **Search ranking test — per-kind, not global**: construct entities/connections/
  diagrams/documents across both repos whose names partially match a query with
  different scores *within each kind*, and assert the merged `search_fts` result
  (a) is correctly score-sorted **within each kind** across the repo boundary, and
  (b) each kind's merged group is capped at `per_kind_limit` independently — not
  one global `limit` applied across all kinds combined. Include a case where one
  repo alone would already produce `per_kind_limit` entity hits *and* the other
  repo has additional connection hits, asserting the connection hits are not
  crowded out — this is the exact per-kind-isolation property
  `_sqlite_queries.py::search_fts` already provides for a single instance, which
  the combined view must reproduce rather than a naive "concat and hope"/
  single-limit merge.
- **List-method global-sort test**: construct an engagement entity and an
  enterprise entity whose names are ordered such that a per-instance-sorted-then-
  concatenated result would visibly differ from a true global sort (e.g.
  engagement entity name sorts after the enterprise one alphabetically), assert
  `list_entities` (and at least one other `list_*` method) returns the
  globally-sorted order, not the concatenated-per-instance order.
- **Concurrent-dispatch test for all eleven SQLite-backed methods** (guards
  `REQ@1782080517.IIl8-4`), not `search_fts` alone: instrument (via a fake/spy
  `ArtifactStorePort` standing in for one of the two canonical instances, entered/
  exited with a small artificial delay) and assert each of `read_entity_context`,
  `candidate_connections_for_entities`, `connection_counts`,
  `connection_counts_for`, `connection_counts_for_entities`,
  `list_connections_by_types`, `list_connections_by_types_for_entities`,
  `find_connections_for`, `find_neighbors`, `diagrams_referencing_type_id`, and
  `search_fts` has combined wall-clock time close to the *slower* of the two
  underlying calls, not their sum — parametrize one test over the method list
  rather than writing eleven near-identical tests. Also assert the shared
  `ThreadPoolExecutor` is constructed once (module-level in `combined_index.py`),
  not per call — a regression test on executor identity/call-count, not just
  timing.
- **`find_entity_by_workspace_id`/`find_entities_by_name` scope test**: assert
  `scope="engagement"` on the combined view never returns an enterprise-repo record
  even when one matches, and vice versa — the specific semantic gap identified above
  that a naive delegate-to-one-instance implementation would get wrong silently.
- **Cache-separation test** (guards the point-1 finding above): assert
  `combined_artifact_index(eng, ent)`'s returned object is never a value in
  `bootstrap._services` (only in the separate `_combined_views` cache), and that
  calling `notify_paths_changed` with a path under either root does **not** invoke
  any method on the combined view object (spy/mock it and assert zero calls) —
  the direct, mechanical check that broadcast iteration and the combined-view
  cache are genuinely disjoint, not just documented as such.
- **Cross-repo duplicate-id startup test** (guards the point-6 finding above):
  construct a fixture where the *same* short id maps to a file in both the
  engagement and enterprise mounts (no promotion involved — a persistent, not
  transient, collision) and assert `_assert_no_duplicate_short_ids` (or its
  post-refactor equivalent operating on `combined_artifact_index`) fails closed;
  separately, assert `scan_duplicate_short_ids`'s merge concatenates both paths
  under the shared key rather than one overwriting the other (a direct unit test
  of the merge function, not just the startup integration behavior).
- **Promotion transient-duplicate parity test**: reproduce
  `execute_promotion`'s window where the same full `artifact_id` briefly exists in
  both `_copy_entities`'s enterprise write and the not-yet-unlinked engagement
  file; assert this does **not** raise (distinguishing it from the persistent-
  duplicate startup test above) and that `CombinedArtifactView.get_entity` returns
  a deterministic (documented, not necessarily "correct" in an absolute sense)
  side during the window — parity with today's single-combined-instance behavior,
  not a behavior change.
- Extend `tests/architecture/test_index_broadcast_policy.py`'s allowlist audit (or
  add a sibling fitness function) once WS4 lands: assert `service_key`/
  `get_shared_index` are never called with a multi-root list that resolves to more
  than the two canonical single-root keys — guards against a future call site
  reintroducing a third combination. Add the `combined_artifact_index`-callers
  fitness function described in "Proposed direction" above as part of the same
  WS4 test batch.
- **`ArtifactRepository` type-narrowing regression test**: assert
  `ArtifactRepository.__init__` accepts a `CombinedArtifactView` (structurally, no
  `cast`) once `ReadableArtifactStore` lands, and that `apply_file_changes`/
  `apply_file_change` no longer exist on `ArtifactRepository` — a `hasattr`-based
  negative assertion is acceptable here since the point is exactly that the
  method should be gone, not just untyped.

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
    `CombinedArtifactView` as a class that structurally satisfies the new
    `ReadableArtifactStore` protocol (`ArtifactStorePort` minus
    `ArtifactMutationObserver` — see above) the same way `ArtifactIndex` already
    satisfies the full `ArtifactStorePort` (no `cast`, no `Any` on the public
    surface) — a missing or mistyped method must be a `zuban` error, not a
    runtime `AttributeError` discovered later. Deliberately do **not** make
    `CombinedArtifactView` satisfy the full `ArtifactStorePort` — the absence of
    `apply_file_changes` from its type is the enforcement mechanism for the CQS
    boundary described above, not an oversight to paper over with a stub method.
    Run `uv run zuban check` as part of WS3, not only at the end.
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
  today. `CombinedArtifactView` is new code covering ~35 methods across six
  `Protocol`s (`ArtifactMutationObserver` deliberately excluded — see above) and
  must be split from the start along those boundaries, e.g.: `_combined_lookup.py`
  (`ArtifactIdentityResolver` + `ArtifactLookup`), `_combined_search.py`
  (`ArtifactSearch` including the per-kind `search_fts` merge and the global-sort
  `list_*` merge), `_combined_graph.py` (`RelationshipGraph`), `_combined_scope.py`
  (`RepositoryScopeResolver` + `ArtifactIndexLifecycle`), with a slim
  `combined_index.py` composing them into the concrete `ReadableArtifactStore`
  implementation plus the module-level shared `ThreadPoolExecutor` used by the
  eleven SQLite-backed methods' concurrent dispatch (`_combined_search.py` and
  `_combined_graph.py` both need it — construct it once in `combined_index.py` and
  pass it in, not one pool per module) — do not write one large file and split
  reactively.
- Run `tests/architecture/test_dependency_policy.py` after any change to which
  layer constructs `CombinedArtifactView` — this is exactly the kind of
  composition-root-adjacent object that can accidentally violate hexagonal
  layering if wired as an ambient/service-locator lookup instead of an explicit
  injected dependency.
- No plan/workstream names in code, tests, or commit messages — use feature/
  concept names (e.g. "combined-scope index view", not "WS3").
