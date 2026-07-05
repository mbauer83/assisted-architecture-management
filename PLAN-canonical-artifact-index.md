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
(`src/infrastructure/artifact_index/bootstrap.py:25-40`):

- `{engagement}` alone — dozens of call sites resolve just the engagement root and
  call `shared_artifact_index([repo_root])` or `shared_artifact_index(repo_root)`,
  e.g. `src/diagram_types/c4/_resolve_model.py:66`,
  `src/diagram_types/sequence/renderer.py:176`,
  `src/infrastructure/gui/routers/_diagram_write.py:78`,
  `src/infrastructure/write/artifact_write/_artifact_deduplication.py:36`,
  `src/infrastructure/mcp/artifact_mcp/bulk/common.py:40,193,255`,
  `src/infrastructure/mcp/artifact_mcp/bulk/candidate_state.py:306`,
  `src/infrastructure/mcp/artifact_mcp/admin_tools.py:46`, and
  `edit_tools.py`'s `_resolve()` (the default scope for every standalone MCP write
  tool, including `artifact_delete_entity`).
- `{enterprise}` alone —
  `src/infrastructure/write/artifact_write/cleanup_broken_refs.py:171`.
- `{engagement, enterprise}` combined — the REST/GUI layer's process-global `_repo`
  (`src/infrastructure/backend/arch_backend.py:329`'s `_initialise_repo`, stored via
  `src/infrastructure/gui/routers/state.py::init_state`), plus
  `src/infrastructure/gui/routers/promote.py:52,134`,
  `src/infrastructure/gui/routers/state.py:258,285` (admin write deps), and every MCP
  read/write call that resolves `repo_scope="both"` (the default for
  `artifact_query_read_artifact` and most MCP read tools, via
  `src/infrastructure/mcp/artifact_mcp/context.py`'s `resolve_repo_roots`).

Each of these, once instantiated, independently runs a full `refresh()` — scanning
every model/diagram/document file under its own root set
(`src/infrastructure/artifact_index/service.py`'s `refresh()`, calling `scan_mount`
per mount) — and maintains its own `_MemStore` (flat dicts *plus* several derived
reverse indexes: `entities_by_diagram`, `connections_by_diagram`,
`diagrams_by_reference`, `grf_targets_by_entity`, `attribute_type_refs`,
`identity_candidates` — `src/infrastructure/artifact_index/_mem_store.py:11-33`) and
its own SQLite FTS index (`_sqlite_store.py`, rebuilt in `refresh()`). None of this
state is shared across instances even when their root sets overlap.

**The existing engine already has everything needed to avoid this.** `ArtifactIndex`
already derives per-record scope purely from the record's own path, with no
dependency on which roots the instance itself was constructed from:
`scope_for_path`/`scope_of_entity`/`scope_of_connection`
(`service.py:524-545`) resolve "engagement" vs. "enterprise" by checking which
configured root the path falls under, and `enterprise_entity_ids()`/
`engagement_entity_ids()`/`enterprise_connection_ids()`/`engagement_connection_ids()`/
`enterprise_document_ids()`/`enterprise_diagram_ids()` (`service.py:555-566` and
`_scope_registry.py`, `src/application/ports.py:208-213`) are already scope-partition
queries over *one* instance's own data. These are already used today by
combined-scope callers to narrow to "just the enterprise part" or "just the
engagement part" of one shared index (e.g. `connection.py`'s
`registry.enterprise_entity_ids()` check, read against the combined-scope
registry). In other words: the abstraction this plan needs already exists and is
already load-bearing — it just isn't the *only* way callers get a narrower view.
The ~29 call sites above instead independently construct their own separate,
narrower-rooted instance, each paying its own full parse/memory/SQLite cost for
content the combined instance (where one is active) already holds.

## Prior art already in this codebase (reuse, don't reinvent)

- `scope_for_path`/`scope_of_entity`/`scope_of_connection`/`enterprise_*_ids`/
  `engagement_*_ids` — the query-time scope-partition primitives this plan
  generalizes into the *only* way to narrow scope (see above).
- `RepoMount(root, scope, engagement_label)` (`src/domain/artifact_types.py:33-36`) —
  each physical root already carries its own "engagement" or "enterprise" scope
  tag; an `ArtifactIndex` mounted over both already knows, per file, which root it
  came from.
- `bootstrap.get_shared_index`/`service_key` — the singleton-cache pattern itself is
  correct and stays; only the *keying* changes (per physical root, not per
  requested combination).
- `notify_paths_changed`'s broadcast loop (`bootstrap.py:44-57`) — stays as the
  update mechanism for whatever indexes remain live; with one instance per physical
  root, a write only ever needs to update the single instance owning that root, so
  most calls become a no-op broadcast to zero siblings rather than N-way duplication.
- `_identity.scan_duplicate_short_ids()` / the startup fail-closed duplicate-id check
  (`arch_backend.py::_assert_no_duplicate_short_ids`) — already assumes ids are
  globally unique across all configured roots, which is exactly what makes
  "try engagement, then enterprise" a safe, unambiguous id lookup strategy for a
  combined reader (see Proposed direction).

## Proposed direction

**Exactly one canonical `ArtifactIndex` per physical root — at most two per running
instance (engagement, enterprise) — ever constructed.** `bootstrap.get_shared_index`
keys strictly by single resolved root, not by whatever combination a caller passed;
a request for `[engagement, enterprise]` never allocates a third instance.

A new, deliberately thin **`CombinedArtifactView`** (name TBD at implementation time)
implements the same `ArtifactStorePort` surface
(`src/application/ports.py:222` — ~35 methods) by holding references to the *same*
two canonical instances and delegating to (or merging across) both:

- **Single-artifact lookups** (`get_entity`, `find_file_by_id`, `read_artifact`, …):
  try the engagement instance, then the enterprise instance. Safe and unambiguous
  because ids are already asserted globally unique at startup (see Prior art).
- **Listing/filtering queries** (`list_entities`, `list_connections`, …): call both,
  concatenate. Existing per-record scope fields make de-duplication or re-filtering
  unnecessary — a record only ever exists in the one instance covering its root.
- **Search** (`search_fts`): query both SQLite-backed instances independently,
  merge the two ranked result sets by score, truncate to the requested limit — the
  standard bounded top-K merge, not a new SQLite schema.
- **`read_model_version()`**: a version that changes if *either* underlying
  instance's generation changes (e.g. a tuple or a hash of both generations/etags)
  — callers that only check "has anything changed" keep working unmodified.
- **`apply_file_changes`/`refresh`**: not meaningful on the combined view directly —
  a write always targets one physical root; route it to that root's canonical
  instance (unchanged from today, since `notify_paths_changed` already resolves
  target instances by path-overlap, not by which combination requested them).

Every one of the ~29 call sites enumerated above that currently requests a
*combination* of roots switches to holding (or being handed) the shared
`CombinedArtifactView` instead of allocating its own instance; call sites that
already request a single physical root are unaffected — they already get the one
canonical instance for that root, now guaranteed to be the *same* object every other
single-root caller for that physical repo gets, engagement-only MCP tools included.

This preserves the current physical separation for anyone who genuinely only wants
one root's data (they get exactly that, with zero risk of ever seeing the other
root's content — see Open decisions) while eliminating the redundant *third* copy
that today exists only because "both" was requested somewhere.

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
  discretion): represents the stateless combined-view read path. Realizes/serves
  `PRC@1777409610.wqtZ0P` *Coordinate Repository State*'s revised guarantee; is
  triggered by (or composed under) the same reads that today resolve
  `repo_scope="both"`. Keep the description honest about what it is: a read-time
  composition, not a cache — it holds no state of its own and therefore cannot itself
  go stale, which is the specific architectural property that makes this design
  immune to the class of bug the broadcast fix addressed.
- **Do not** create these two new entities, or revise `PRC@1777409610.wqtZ0P`,
  until the corresponding workstream below actually lands — self-model entries
  should describe what is true of the running system, not a plan for it (this
  plan document is where the plan lives).
- Use `artifact_authoring_guidance` before creating either new entity,
  `dry_run=true` then commit, `artifact_verify` after each batch, full-property
  `artifact_edit_entity` replacement for the `PRC` revision — standard process for
  this repo, unchanged by anything in this plan.

## Workstreams

| WS | Title | Depends on | Notes |
|----|-------|-----------|-------|
| 1 | Audit: classify every `shared_artifact_index`/`get_shared_index` call site (the ~29 above plus any missed) by whether it needs single-root or combined access, and whether any caller relies on an instance *not* seeing the other root's content for a correctness or permission reason (not just convenience) | — | Produces the answer to D-1; do not design the combined view's exact interface before this lands |
| 2 | Re-key `bootstrap.get_shared_index`/`service_key` to one canonical instance per physical root; single-root call sites need no further change | 1 | The smaller, lower-risk half — mechanical once WS1 confirms no call site was relying on cross-root isolation for correctness |
| 3 | `CombinedArtifactView` implementing `ArtifactStorePort` over the two canonical instances (delegated lookups, merged listings, top-K-merged search, composite `ReadModelVersion`) | 2 | The larger half — ~35-method port surface; budget for a full read-path implementation, not a thin wrapper |
| 4 | Migrate every combined-scope call site (REST/GUI global `_repo`, `promote.py`, admin write deps, MCP `repo_scope="both"` resolution) onto `CombinedArtifactView` | 3 | Mechanical once WS3 lands; each migrated call site drops one redundant full-repo parse |
| 5 | Reassess `notify_paths_changed`'s broadcast loop now that most combinations collapse to "one instance per changed root" — confirm it still does the right thing for the (now much smaller) remaining multiplicity, simplify if the N-way broadcast machinery is no longer earning its complexity | 4 | Do not remove the broadcast mechanism speculatively — confirm first whether any legitimate multiplicity remains (e.g. short-lived staging indexes) that still needs it |
| 6 | Self-model enrichment (see above) | 4 | Revise `PRC@1777409610.wqtZ0P`; add the two new entities; update `CC@1780829793.K3l46j` *Architecture Backend — Components* if the new composition changes what that diagram should show |

## Test plan

- **Parity tests**: for a representative set of read methods (`get_entity`,
  `list_connections`, `search_fts`, `find_file_by_id`, `enterprise_entity_ids`),
  assert `CombinedArtifactView`'s result over two canonical instances equals what
  today's single combined-root `ArtifactIndex` returns for the same synthetic
  two-repo fixture — a hard parity gate, not a spot check (mirrors
  `PLAN-scalable-bulk-staging.md`'s own parity-test precedent for its manifest
  refactor).
- **Memory/instance-count regression test**: construct the standard two-repo test
  fixture, request `{engagement}`, `{enterprise}`, and `{engagement, enterprise}`
  scope resolutions in sequence, and assert `len(bootstrap._services)` never
  exceeds 2 — the direct, mechanical assertion of this plan's goal.
- **Search ranking test**: a query whose top results span both repos returns them
  correctly interleaved by score, not "all engagement results, then all enterprise
  results" — the naive-concatenation failure mode a real top-K merge must avoid.
- Extend `tests/architecture/test_index_broadcast_policy.py`'s allowlist audit (or
  add a sibling fitness function) once WS2 lands: assert `service_key`/
  `get_shared_index` are never called with a multi-root list that resolves to
  more than the two canonical single-root keys — guards against a future call site
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

## Open decisions (resolve at implementation start, not before)

- **D-1**: does any current single-root call site rely on *not* seeing the other
  root's content for a correctness or permission reason, or is the physical split
  purely a historical convenience/performance artifact? (Working hypothesis, not yet
  fully confirmed: enterprise-repo *write* access is already gated by an explicit
  runtime check — `state.py`'s `is_admin_mode()` — not by which index instance is in
  scope, and the two-tier engagement/enterprise design elsewhere in this self-model
  describes the enterprise repo as a broadly-readable shared catalog, not
  confidential content — suggesting no read-side security boundary depends on
  physical index separation. WS1 must confirm this for every call site before WS2
  proceeds, not assume it.)
- **D-2**: exact shape of `CombinedArtifactView`'s `ReadModelVersion` composite (tuple
  of both generations vs. a combined hash) — resolve once WS3's actual callers'
  version-comparison usage is inventoried.
- **D-3**: whether `CombinedArtifactView` needs its own name distinct from
  `ArtifactIndex` in the self-model as a wholly separate technical concept, or
  whether it is more accurately modeled as a *capability* of the existing
  Architecture Backend component — resolve when writing WS6, informed by how WS3
  actually implements it (e.g. as its own class vs. a mode of an existing one).

## For implementers

- Coding guidelines: `STD@1777137196.ItT-3l` *General coding guidelines* — read
  before touching any file above.
- `src/infrastructure/artifact_index/service.py` is 630 lines; `_mem_store.py` is
  169; `_sqlite_store.py` is 439 — none of these are near the 350-line hard cap
  today, but `CombinedArtifactView`'s ~35-method surface is new code and must be
  split across sibling modules from the start (e.g. one file for single-lookup
  delegation, one for listing/merge logic, one for search-ranking merge) rather
  than written as one large new file — do not let it grow past the cap and then
  split reactively.
- Run `tests/architecture/test_dependency_policy.py` after any change to which
  layer constructs `CombinedArtifactView` — this is exactly the kind of
  composition-root-adjacent object that can accidentally violate hexagonal
  layering if wired as an ambient/service-locator lookup instead of an explicit
  injected dependency.
- No plan/workstream names in code, tests, or commit messages — use feature/
  concept names (e.g. "combined-scope index view", not "WS3").
