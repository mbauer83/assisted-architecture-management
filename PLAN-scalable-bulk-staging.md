# PLAN — Scalable Bulk Write/Delete Pipeline (avoid O(repo-size) cost per call)

Retitled from "...Staging" — an external review of this plan's first draft (integrated below,
verified claim-by-claim against the code before accepting) correctly found that "staging cost"
was too narrow a frame: the pipeline has *more than two* O(repo-size) phases, and one of them
(reference-blocker scanning) turned out to also live in the single-item delete path this plan's
first draft had named as the scale-safe reference. Scope note below now enumerates every phase
found so far; this list is not guaranteed closed — say so if implementation finds another.

WS5 of `PLAN-rename-stale-index-fix.md` already built M4 (`src/infrastructure/write/artifact_write/m4_transaction.py`)
— a lean, per-file, crash-safe apply/publish primitive keyed by a manifest of
`{create|replace|delete}` entries. M4 itself is correct and lean and stays out of scope. Every
phase below runs *before* M4 ever sees a manifest.

## Goal

Make every phase of `artifact_bulk_write`/`artifact_bulk_delete` — and, per the finding below,
`artifact_delete_entity`'s own reference-blocker checks — cost proportional to the size of the
batch (items touched + their direct references), not to total repo size, at the stated target:
engagement repos of tens of thousands of entities, enterprise repos up to the low hundreds of
thousands, ~12 concurrent users each issuing potentially several concurrent MCP calls. Today a
single-item bulk delete and a 300,000-entity repo pay the same full-repo cost at *every* phase
below; that ratio gets worse, not better, as repos grow, in the exact direction the codebase is
already heading (D-9 in `TASKS-modeling-ux-and-self-model-uplift.md`: no entity pruning, navigate
via groups instead — the self-model is expected to keep growing).

## Concurrency context — why this is a system-wide throughput problem, not just caller latency

**Every write MCP tool call — single-item or bulk — is already fully serialized through one
global, single-worker queue.** `src/infrastructure/mcp/artifact_mcp/write_queue.py`'s `queued(...)`
(wrapping every `artifact_edit_*`/`artifact_create_*`/`artifact_delete_*`/`artifact_bulk_*` tool
registration) submits to a module-level `ThreadPoolExecutor(max_workers=1)`
(`_WRITE_EXECUTOR_WORKERS = 1`, `write_queue.py:30`) and holds
`src/infrastructure/workspace/mutation_gate.py`'s `WorkspaceMutationGate.writing()`
(acquired at `write_queue.py:159`) for the *entire* duration of the wrapped call — confirmed a true
process-wide singleton, not per-workspace despite the class's own docstring (`get_workspace_gate()`
returns one module-level `_gate`, `mutation_gate.py:174-176`). There is no write concurrency in
this system today, by design — at most one write executes at any moment, process-wide, regardless
of which workspace it targets.

This changes what "O(repo-size) per call" means in practice: it is not "the calling user waits
longer for a big batch," it is **"every other user's write of any kind — including a trivial
one-field edit — queues behind whichever write is currently running, for that write's entire
duration."** With ~12 concurrent users each issuing several MCP calls, one bulk operation on a
large repo stalls every other user's write for its whole window. This is the primary reason this
plan exists, more than raw latency for the bulk caller — **fix it because it blocks everyone, not
because one call is slow.** (Reads are less affected: `WorkspaceMutationGate`'s own docstring says
pure index reads bypass the gate — read-only MCP/REST calls are not queued behind a write, only
other writes and filesystem-dependent reads are.)

Since writes are already globally serialized one-at-a-time, no design here needs to handle two
batches (or a batch and a single-item edit) mutating the live repo concurrently — simplifies the
overlay design below considerably, and is why the hardlink rejection further down is about a
single-writer hazard, not a concurrent-writer one.

## The problem, with evidence — five independent O(repo-size) phases, not two

Verified by reading each cited function, not inferred from names.

1. **Staging copy.** `src/infrastructure/write/artifact_write/batch_transaction.py:44`
   `create_staging_repo`: `shutil.copytree(repo_root, staged_root, ...)` — full physical copy of
   the entire repo tree (including regenerable rendered PNG/SVG under `diagram-catalog/rendered/`,
   not excluded by `_ignore_transaction_storage`) before a single item is touched.
2. **Manifest diff.** `batch_transaction.py:90` `commit_staged_repo` → `_derive_manifest`:
   `_managed_files` (`batch_transaction.py:135`) does `rglob("*")` over *both* the full live tree
   and the full staged tree, then `filecmp.cmp(..., shallow=False)` every file present in both —
   reconstructing information the batch already produced and threw away (see `changed_paths` below).
3. **Staged registry rebuild.** `src/infrastructure/mcp/artifact_mcp/bulk/common.py:240`
   `stage_batch_verification` builds `ArtifactRegistry(shared_artifact_index([repo_root]))` for
   `repo_root=staged_root`. `shared_artifact_index` → `get_shared_index`
   (`src/infrastructure/artifact_index/bootstrap.py:33`) caches by `service_key(mounts)` — a key
   derived from the mount *path*. `staged_root` is a fresh `uuid.uuid4().hex` directory every call,
   so this is **always** a cache miss, **always** a brand-new `ArtifactIndex`, and the first access
   triggers `_ensure_loaded()` → full `refresh()` scan of the whole staged tree
   (`src/infrastructure/artifact_index/service.py:92`). This is a real, independent cost from (1) —
   even a symlink-mirrored staging directory (see B1 below) still pays this in full, since it's a
   parse cost, not a copy cost.
4. **Staged inventory rebuild — inside the very call the first plan draft called "already
   correct."** `stage_batch_verification` calls `verifier.verify_paths(..., changed_paths=...,
   verification_scope="impacted")`. **The "impacted" scoping is real but only narrows the
   *selection* of what gets checked, not what gets built to check it.**
   `ArtifactVerifier.verify_paths` (`src/application/verification/artifact_verifier.py:298`)
   unconditionally calls `self._inventory.build(repo_path, ...)` at line 309 — *before* the
   `changed_paths`/impacted-scope narrowing at line 314 even runs — and `build`
   (`src/application/verification/artifact_verifier_incremental.py`) does four separate
   `rglob("*.md")`/`rglob("*.outgoing.md")`/`rglob("*.puml")` calls over the whole tree. The
   original plan's "do not fix this, it's the model to follow" framing was wrong: this phase is not
   yet proportional to anything, it's O(repo-size) exactly like (1)-(3). **Correction from the
   first draft — do not repeat "verification is already right" as a blanket statement.** Only the
   rule-selection half of it is right.
5. **Reference-blocker scans — and this phase exists in the single-item path too, not just bulk.**
   `artifact_bulk_delete`'s preflight (`src/infrastructure/mcp/artifact_mcp/bulk/delete.py:51`
   `preflight_bulk_delete` → `src/infrastructure/mcp/artifact_mcp/bulk/delete_preflight.py:60`)
   calls `scan_connections`, `scan_grf_refs`, `scan_diagram_refs`
   (`src/infrastructure/mcp/artifact_mcp/bulk/diagram_refs.py:94,115,135`), each an unconditional
   `rglob` over every `.outgoing.md` file, every entity `.md` file, or every diagram file in the
   repo, run *before staging even starts*, regardless of batch size. **The same pattern is
   independently duplicated in the single-item path**: `src/infrastructure/write/artifact_write/entity_delete.py`'s
   `_incoming_connection_blockers` (`:87`), `_grf_blockers` (`:106`), `_diagram_blockers` (`:123`) —
   called by `_delete_entity_core` for every `artifact_delete_entity` call — do the identical
   full-tree scan, just for one entity's blockers instead of a batch's. **This directly contradicts
   this session's own prior finding** (recorded in `TASKS-modeling-ux-and-self-model-uplift.md`)
   that single-item delete was "the O(item-size) reference for what cheap looks like" — it avoids
   the *staging* cost (phases 1-4), but its own reference-checking is exactly as O(repo-size) as
   bulk delete's preflight. Correct that record when this plan's self-model-enrichment workstream
   runs (see below) and in the ledger.

Phase (2)'s redundancy is worth calling out on its own: every `artifact_write_ops` call inside a
staged batch already reports its own touched path via `clear_repo_caches`
(`bulk/common.py:40`'s `temp_repo_callbacks`, threaded through `apply_planned_deletes`/
`apply_single_delete` and the write-side equivalents) into a `changed_paths: set[Path]` the caller
already holds. `_derive_manifest` ignores it and re-derives the same information from scratch.

## Prior art already in this codebase (reuse, don't reinvent)

- **`_document_temp_path`** (`src/infrastructure/write/artifact_write/verify.py`) already mirrors
  the docs tree via **symlinks** for unaffected files and only materializes the one file under
  test — proof the symlink-mirror pattern is already accepted practice here.
- **`candidate_repository.py`'s `candidate_with(...)`** (used by `diagram_edit.py`'s E334 check)
  already builds an in-memory "repo as it would be after this change" overlay on top of the live
  index, zero file I/O, for exactly the "what would break" reasoning bulk operations need. Scoped
  to single-diagram-edit impact analysis today, not directly reusable as-is, but demonstrates the
  overlay-without-copy approach is already trusted for correctness-critical checks elsewhere.
- **`connections_by_entity: dict[str, set[str]]`** already exists on the live `_MemStore`
  (`src/infrastructure/artifact_index/_mem_store.py:19`, maintained incrementally) — an O(1)
  reverse lookup for exactly the "who has an incoming connection to entity X" check phase-5's
  `scan_connections`/`_incoming_connection_blockers` currently rebuild by scanning every
  `.outgoing.md` file. **Reuse this directly; do not scan for it.** No equivalent reverse index
  exists yet for "which diagrams reference entity/connection X" (what `scan_diagram_refs`/
  `_diagram_blockers` need) or "which entities' `global-artifact-id` points at X" (what
  `scan_grf_refs`/`_grf_blockers` need) — those need new indexes, following the exact same
  established pattern (`_mem_store.py` already has `entities_by_diagram`, `connections_by_diagram`
  as precedent for adding a reverse map incrementally maintained alongside the forward one).
- **`changed_paths`** tracking already exists end-to-end in the bulk apply path (see phase 2 above)
  — the fix there is mostly *stop discarding data you already have*, not new plumbing.

## Proposed direction

**A. Manifest from tracked changes, not a full-tree diff (phase 2).** Change
`commit_staged_repo`'s signature to accept the batch's own `changed_paths`/`deleted_paths` and
derive `ManifestEntry` records directly from that set — hash each touched path in staged vs. live
to classify create/replace, treat the caller's deletion list as the delete entries — instead of
`_managed_files` + `filecmp.cmp` over the whole tree. **Do not trust the tracked set blindly**: the
set is assembled from several call sites (deletes, writes, implicit connection deletes, auto-sync)
and it is plausible some operation (a rename, a group-move, an entity edit that also rewrites a
referrer document link) reports one of its touched paths but not another. Ship this only alongside
a parity test — for a representative set of batches (plain edit, delete, rename, group-move,
multi-item batch with overlapping paths, auto-synced diagram) assert the tracked-set-derived
manifest is byte-for-byte identical to what today's full-tree diff produces. If parity fails for
any case, that is real information the tracked set is missing an intent, not a fixture bug to
delete — go find and fix the missing `clear_repo_caches` call rather than special-casing the test.

**B. Indexed reference-blocker lookups (phase 5), shared by bulk and single-item delete.** Replace
`scan_connections`/`scan_grf_refs`/`scan_diagram_refs`/`find_document_path`/`find_diagram_path`
(bulk) and `_incoming_connection_blockers`/`_grf_blockers`/`_diagram_blockers` (single-item) with
lookups against the live index: `connections_by_entity` already covers incoming-connections; add
`diagrams_by_reference: dict[str, set[str]]` (entity/connection id → referencing diagram ids) and
`grf_targets_by_entity: dict[str, set[str]]` (target id → GRF proxy ids) to `_mem_store.py`,
maintained incrementally the same way `entities_by_diagram` already is. This is genuinely one fix
serving two call sites — do not implement it twice. `find_document_path`/`find_diagram_path`
(single-artifact-id → path) should route through `registry.find_file_by_id` (already indexed,
already short-id-aware per this session's earlier fix) instead of their own `rglob`.

**C. Avoid full registry/inventory rebuild for the staged root (phases 3-4).** This is the
overlay design the first draft deferred as a "maybe" — it is not a maybe. Even with A and B and a
symlink-mirrored staging directory, phases 3 and 4 still parse the *entire* repo from scratch on
every call, because the staged path is always new. Build a `BulkCandidateState` (name TBD at
implementation time) carrying: the live index/registry, the batch's created/replaced parsed
records, the batch's deleted ids/paths, and the changed relpaths — and make
`stage_batch_verification`'s registry construction and `verify_paths`'s inventory construction both
consume that state instead of calling `shared_artifact_index([staged_root])` /
`self._inventory.build(staged_root)` for a repo whose vast majority of files didn't change. This is
the harder design question of the plan: it requires auditing which verifier rules read file content
directly from disk vs. could accept the registry/inventory's in-memory view for a path that only
exists in the batch's delta (D-3 below) — do that audit before committing to a shape.

**D. Avoid the full physical copy in `create_staging_repo` (phase 1), if a staged directory is
still needed at all after C.** If C removes the need to parse a staged directory for
verification, a physical (or even symlinked) staged directory may only be needed for M4's own
apply step, which already operates per-file from a manifest — in which case phase 1 may disappear
entirely rather than needing a cheaper replacement. Resolve this ordering question (D vs. C) once C
is scoped; do not build D's symlink-mirror machinery speculatively if C turns out to obsolete it.
If a staged directory is still needed, **do not implement it as a raw symlink farm plus scattered
"remember to materialize before writing" discipline at every `write_text`/`unlink`/`rename` call
site across the write-path modules** (this session alone touched write logic in at least six
different modules — `matrix.py`, `diagram_edit.py`, `document.py`, `entity.py`, `entity_edit.py`,
`connection.py` — a missed call site silently corrupts the live file through a shared symlink
target). Centralize it: a `StagedWorkspace` helper (`materialize(path)`, `write_text`, `unlink`,
`rename`, path classification) that every bulk apply call routes through, tested against edit,
delete, rename, group-move, outgoing-sidecar-rewrite, diagram-refresh, and document-move cases
before any `artifact_write_ops` function is allowed to write into a symlink-mirrored tree
unguarded.
  - Do not attempt hardlinks as a copy substitute: a hardlinked staged path shares the live file's
    *inode*, so an ordinary `write_text`/`open(path, "w")` against it truncates and rewrites the
    same on-disk bytes the live file points to — corrupting the live file the instant the batch
    writes to its staged copy, no concurrency required. Symlinks don't have this hazard because a
    symlink is a separate inode pointing at a name; the `StagedWorkspace.materialize` step means
    the batch's writes never go through the link at all.

**Sequencing for implementation:** A and B are independently shippable, low-risk, and directly
address real duplicated/wasted work — do both regardless of what C/D resolve to. **Do not present
A+B (or A+B+D) as sufficient for the stated scaling target and stop there** — phases 3 and 4 (C)
are, on the evidence above, very likely to dominate at tens-of-thousands-to-low-hundreds-of-
thousands scale once 1, 2, and 5 are fixed, precisely because they are full parses, not full
copies, and no symlink trick touches parse cost. WS1's benchmark (below) is what turns "very
likely" into a measured decision about C's design, not about whether it's needed.

## Workstreams

| WS | Title | Depends on | Notes |
|----|-------|-----------|-------|
| 1 | Benchmark harness, split perf-ci / perf-manual (see Test plan) | — | Establish the baseline before touching code; re-run after each workstream |
| 2 | Indexed reference-blocker lookups (direction B) | 1 | `_mem_store.py` (new `diagrams_by_reference`, `grf_targets_by_entity`), `bulk/diagram_refs.py`, `bulk/delete_preflight.py`, `entity_delete.py` — one fix, two call sites; also route `find_document_path`/`find_diagram_path` through `registry.find_file_by_id` |
| 3 | Manifest from tracked changes + parity test (direction A) | 1 | `batch_transaction.py`, `bulk/delete.py`, `bulk/write.py`; parity test is a hard gate, not optional |
| 4 | Audit verifier rule file-content access (disk vs. registry-accepting) — prerequisite for C | 1, 2, 3 | Read every verifier rule that opens a file path itself rather than working from parsed frontmatter/content already in the registry; produces the answer to D-3 |
| 5 | Overlay registry/inventory for staged verification (direction C) | 4 | The core fix for phases 3-4; design shape depends on WS4's audit |
| 6 | Resolve whether a staged directory is still needed post-WS5; if yes, `StagedWorkspace` abstraction (direction D) | 5 | Do not build speculatively — see D vs. C ordering note above |
| 7 | Self-model enrichment (see below) | 2, 3 (at minimum; extend as 5/6 land) | Descriptions/attributes only, no new entities/connections |

## Self-model enrichment (explicit workstream, not optional)

The self-model already has entities for this exact mechanism — enrich their descriptions with the
finding and fix direction; do **not** add new entities or connections, this is a
description/attribute-only update at the granularity the model already uses elsewhere (e.g.
WU-C2's motivation-description enrichment in `PLAN-modeling-ux-and-self-model-uplift.md`):

- `FNC@1777399927.hbgFU3` *Create Staging Repository* — current text says only "Copies the live
  repository tree to a temporary directory"; add that this is currently a full physical copy
  (`shutil.copytree`), an identified O(repo-size)-per-call constraint, and that whether it's needed
  at all is now conditional on the overlay work resolving verification's own full-parse cost first
  (don't just say "will be symlinked" — that assumption changed).
- `FNC@1777399928.tRAV0x` *Commit Staged Repository* — note that manifest derivation currently
  re-diffs the whole tree via `filecmp` rather than using the batch's own already-tracked
  changed-path set; note the fix direction and the parity-test requirement.
- `PRC@1777399926.gtgYvQ` *Execute Staged Bulk Operation* — state the current cost profile (every
  phase — staging copy, manifest diff, staged registry rebuild, staged inventory rebuild,
  reference-blocker scanning — is O(repo-size), not O(batch-size)) and that every write is
  serialized through one global gate, so this cost is paid by every concurrent user, not just the
  caller. **Correct an inaccuracy from this session's earlier enrichment guidance**: do not
  describe `artifact_delete_entity`/`artifact_delete_diagram`/`artifact_delete_document` as simply
  "the O(item-size) alternative" — they avoid the *staging* phases but their own reference-blocker
  checks are equally O(repo-size) today (see phase 5 finding above); say so plainly rather than
  repeating the earlier, now-corrected claim.
- `APP@1777399925.HOOYAQ` *Batch Transaction Manager*, `DOB@1777399929.hhYsiw` *Staged Repository*
  — check current descriptions when this work starts; add the constraint note only if these two
  don't already inherit it clearly enough via their connections to the entities above (one
  authoritative statement, cross-referenced, beats five paraphrases).
- Use `artifact_authoring_guidance` before editing (per standing process), `dry_run=true` then
  commit, `artifact_verify` after. Full-property replacement on every `artifact_edit_entity` call.

## Test plan

Split per the general practice of separating algorithmic invariants (fast, deterministic, CI-safe)
from machine-dependent wall-clock benchmarks (slow, variable, not CI material):

- **perf-ci** (runs in the normal suite): assert *operation counts*, not wall-clock — e.g. "staging
  a batch that touches N files performs O(N) `rglob`/file-read calls, not O(repo file count)" via a
  counting fake/spy on the filesystem access points, at a small synthetic scale (hundreds of
  files). Assert the WS3 parity test (tracked-set manifest == full-diff manifest) across the
  representative batch shapes listed under direction A. These must be deterministic and fast.
- **perf-manual** (opt-in marker, not run by default in CI): synthetic repo generator parametrized
  by entity count (1k/10k/50k/150k, covering the stated engagement and enterprise scale), timing
  `artifact_bulk_write`/`artifact_bulk_delete` at batch sizes 1/10/100, with **phase-level
  instrumentation** reporting copy-or-mirror time, preflight/reference-scan time, staged-index-build
  time, staged-inventory-build time, verification time, manifest-derivation time, M4-publish time,
  and write-queue wait time *separately* — a regression should identify which phase got slower, not
  just that the call got slower. Also run the concurrent-load scenario: with a bulk operation
  in-flight against a 50k+/150k-entity repo, measure how long a concurrently-submitted trivial
  single-item edit queues behind it — this is the number that represents the concurrency-context
  motivation above, and it should shrink as WS2-WS6 land, tracked run over run rather than pinned
  to one hard threshold (machine-dependent).
- If WS6 (StagedWorkspace) lands: a test that writing to a staged path never mutates the
  corresponding live file (the hardlink-hazard guard) and that an already-broken symlink (deleted
  target) in the mirror is handled as absent, not as an error.

## Out of scope

- M4 itself (`m4_transaction.py`) — already correct and lean; not touched.
- Whether to register standalone single-item delete MCP tools — already done this session
  (separate, smaller piece of work); this plan corrects one claim made about them (see phase 5 and
  self-model enrichment above) but does not redo that work.
- Rule-selection scoping in `verify_paths` (`verification_scope="impacted"`) — this part is already
  correct; only the inventory/registry construction feeding it is in scope (phases 3-4).

## Open decisions (resolve at implementation start, not before)

- D-1: exact shape of the phase 3-4 overlay (direction C) — depends on WS4's audit of which
  verifier rules read disk directly. Do not design this in the abstract before that audit.
- D-2: whether `diagram-catalog/rendered/` (regenerable binary output) should be excluded from
  staging entirely rather than mirrored/copied — likely yes, confirm nothing in verify/commit
  depends on it being present in the staged tree.
- D-3: (surfaces from WS4) which verifier rules need to change to accept overlaid/in-memory content
  for a path that exists only in the batch's delta, and whether that change is safe within the
  existing port/verifier segregation (see dependency-policy note below).
- D-4: whether a staged directory is needed at all once C lands (see direction D's note) — resolve
  after WS5, before building WS6.

## For implementers

- Coding guidelines: `STD@1777137196.ItT-3l` *General coding guidelines* — read before touching any
  of the files above. Relevant here specifically: no behavior-switching boolean flags (if a staged
  directory is still needed, the symlink-mirror step should be the new unconditional behavior, not
  a toggle between old and new); keep files ≤350 lines hard / 250 soft
  (`src/infrastructure/write/artifact_write/batch_transaction.py` is 149 lines today, headroom
  exists — split rather than let it creep past the cap if WS5/WS6 grow it substantially).
- If WS5 (overlay) touches how the verifier resolves file content, run
  `tests/architecture/test_dependency_policy.py` before considering the change done — this
  codebase enforces hexagonal layering (no service-locator, port/verifier segregation) via an
  AST-based test, and an overlay mechanism is exactly the kind of change that can accidentally
  violate it if threaded in as a global/ambient lookup instead of an explicit injected dependency.
- WS2's new reverse indexes (`diagrams_by_reference`, `grf_targets_by_entity`) must be maintained by
  *both* the full-scan path (`_service_scan.py`) and the incremental path (`_service_incremental.py`)
  — this codebase has hit the "full scan does X, incremental path forgot to" bug three separate
  times in one session already (see `TASKS-modeling-ux-and-self-model-uplift.md`'s WU-C3 entries);
  add both, and add a test that edits an entity's referencing diagram *after* the index was built
  and checks the reverse index updated, not just that a fresh full scan produces it correctly.
