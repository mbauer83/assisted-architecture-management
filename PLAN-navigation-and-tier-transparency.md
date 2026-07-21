# PLAN — Content-First Navigation & Tier Transparency

Restructure the GUI header navigation from tier-first (Engagement / Global sections) to
content-first (one entry per content type, tier as a per-surface facet), separate workflow
controls from navigation, make global-artifact-reference (GAR) records invisible in every
search surface, and enforce the write boundary and read-only mode server-side on every
interface through one structurally unavoidable authorization path.

Companion files: `TASKS-navigation-and-tier-transparency.md` (execution ledger),
`PROMPT-navigation-and-tier-transparency.md` (executor prompt).

---

## 1. Business context

The two-tier repository model (engagement working repo + reviewed enterprise repo) is the
product's core collaboration story: architects author in the engagement repo, promote
selected content, finalize the promotion (enterprise save → submit → external PR review →
watcher auto-sync back to main), and everyone reads across both tiers. The header
contradicts this: it groups by tier while most surfaces are already tier-merged, hides
the enterprise workflow behind an admin flag, lacks enterprise documents/diagram
listings, and the search dropdown leaks GAR proxies.

Actors and authority:
- Any client of a writable backend may author engagement content, promote, and finalize
  promotions. There are no per-user roles; review happens on the git host via PR.
- `--admin-mode` additionally enables direct enterprise authoring through the dedicated
  admin operations surface only.
- `--read-only` blocks every **architecture-repository** mutation — authoring, workflow
  git operations, promotion, finalization — on every interface. Assurance-store
  mutations are governed by their own unlock gating and are out of scope here.
- "Engagement" always means the single active engagement; switching engagements requires
  a backend restart (owner-performed). Cross-engagement facets are out of scope.
- Discarding *uncommitted* working-tree changes is a destructive operation that is NOT
  part of this effort: Discard means branch discard on a clean tree only (§12).

## 2. Locked decisions

- **D1 — Content-first primary nav**: `Browse · Documents · Diagrams · Viewpoints ·
  Assurance` (+ Search). No tier section headers, no duplicated entries.
- **D2 — Tier is a facet, not a place**: every list surface gets the same segmented tier
  control, default `All`, persisted in the URL query (`?tier=`). The codec takes a
  **per-surface allowed-tier set**: Viewpoints allows `engagement | enterprise | module`;
  Entities/Documents/Diagrams allow `engagement | enterprise`. Absent, array, or
  disallowed values normalize to All via one `router.replace` preserving unrelated query
  keys and hash. `/global/entities` and `/global/diagrams` become query-preserving
  redirects.
- **D3 — Uniform tier badges with total contracts**: one shared row-badge component with
  one accessibility label; `is_global: bool` is **required** on entity, document, and
  diagram list summaries (entity rows already always emit it — the TS schema closes it).
- **D4 — Rename user-facing "Global" → "Enterprise"** in all rendered copy. API paths,
  query values (`scope=global`), internal identifiers (`is_global`, `isGlobal*`), GAR
  terminology, and compatibility comments keep their names.
- **D5 — Status cluster, right-aligned**: repo/sync status chip plus a Changes menu
  housing engagement Save, enterprise Save/Submit/Discard, and the Promote entry point.
  Navigation on the left is nouns only; verbs live in the cluster.
- **D6 — Fail-closed, backend-authoritative action availability**: the frontend
  initializes mutation authority as *unknown* and disables mutating controls until the
  first successful authority response; SSE events only trigger re-reads of backend
  authority, never act as its sole source. Authority is **per-intent, not scalar**: the
  read model exposes a `denied_intents` projection (with reasons), and the backend
  policy, REST/MCP rejection, and the status reducer all consume the same fresh
  projection. Enterprise sync status is visible to everyone and truthful after action,
  poll, reconcile, and reload.
- **D7 — Search visibility is an application policy.** One injected policy (excluded
  internal-class entity types) owned by the application search layer
  (`ArtifactRepository` / `_artifact_search`) and applied to all three branches: FTS
  (exclusion set pushed down into the store query as prepared-SQL parameters so hidden
  rows never consume result budgets, and applied before marking an FTS kind as hit),
  scored fallback, and semantic supplement **with refill** (a leading hidden candidate
  must not consume the semantic budget — see S1). Raw id/list access (`get_entity`,
  `list_entities`, registry lookups, index ingestion) is unchanged: promotion and
  connection internals keep full GAR access.
- **D8 — No ontology or stored-artifact changes**; `types.generated.ts` untouched. The
  enterprise sync **state file** does evolve (D11) — that is a runtime-state schema
  change with an explicit compatibility rule, not an artifact migration.
- **D9 — Enterprise write boundary via one structurally unavoidable path**: promotion —
  including finalization (enterprise save, submit with upstream-tracking push, withdraw)
  — is the only enterprise write outside admin mode. Standard authoring tools (MCP and
  normal REST/GUI writes) are engagement-only in every mode and accept only the
  configured active engagement root (canonically resolved; arbitrary raw `repo_root`
  write targets are rejected). Admin mode enables direct enterprise authoring
  exclusively through the admin operations surface. Enforcement: a pure
  application-level authorization policy consumed by one injected
  **AuthorizedMutationExecutor** — the only way any interface executes a mutation.
  Layering: policy types, intents, target rules, and narrow protocols live in
  `src/application`; the concrete executor adapter that composes the existing queue,
  mutation gate, and event publication lives in `src/infrastructure` and is wired only
  at composition roots. Authorization uses a **fresh immutable snapshot per operation**
  obtained from a provider (never a startup-time context holding mutable health).
  `assert_engagement_write_root` / `assert_enterprise_write_root` remain as narrow,
  context-free target-class invariants (defense in depth), not a second authority
  model.
- **D10 — One mutation pipeline, one queue submission**: every architecture-repository
  mutation — MCP tools, ordinary REST writes, REST group and viewpoint routes,
  promotion, engagement save, enterprise save/submit/withdraw — goes authorize → shared
  single-worker queue → workspace write gate → execute → publish/invalidate. The
  executor **replaces** existing `@queued`/`run_sync` ownership on migrated paths (never
  wraps or re-enters it — nested submission to the single-worker queue deadlocks); the
  gate is acquired exactly once inside the worker after authorization is re-checked
  from a fresh snapshot. Mutation registration goes through a wrapper/factory that
  requires a manifest row and installs the executor, so unwrapped mutators cannot be
  registered (coverage is structural, not observational); non-mutating POST and
  validation/dry-run endpoints are explicitly classified. Verifier scope: engagement
  and enterprise **Save commits run the artifact verifier** (they stage the current
  working tree, which may contain manually changed files); only content-neutral
  git-state operations that introduce no artifact content (Submit's push, the specified
  Discard) are exempt. Background sync/reconcile uses an explicit maintenance/recovery
  intent, never a boolean bypass.
- **D11 — Sync state is one pure versioned aggregate; authority is a per-intent read
  model**: the persisted enterprise sync state becomes a versioned aggregate of a
  closed lifecycle union (`synced | accumulating | pending`) plus a typed health
  overlay (`healthy | blocked` with a **closed reason code**, message, observed
  timestamp; the reason type is owned by the application policy). Old unversioned files
  load as healthy with lifecycle preserved. Aggregate helpers (`replace_lifecycle`,
  `record_block`, `clear_block`) do typed load/transition/atomic persistence ONLY
  (persist-on-change) and return a transition result — they never import GUI cache or
  event modules. The sync orchestrator and the executor publish events and invalidate
  cached measurements through injected ports/callbacks **after successful persistence**
  (failed persistence → no success event, no authoritative cache update). Reconcile
  returns a typed `ReconcileOutcome(lifecycle, health, completed)`; only
  `completed=True` may clear a prior health block. **Authority is never cached**: the
  status cache holds only expensive git/lifecycle measurements; every status response
  composes the fresh per-request authority projection from the snapshot provider (live
  gate state + persisted health) over those cached measurements — so direct
  `WorkspaceMutationGate.blocking_writes()` transitions in the sync paths are reflected
  immediately, with no TTL and no dependency on `write_block_manager` shims. **Health
  is reason- and action-aware**: a pure `denied_intents(reason, target)` policy maps
  each reason code to the intents it blocks — a dirty working tree is
  lifecycle/working-tree state (never an authority block; `enterprise_save` must remain
  available to resolve it); enterprise fetch/upstream/divergence faults **allow
  `enterprise_save` (local commit) and local-branch discard, deny `promotion`,
  `enterprise_submit`, and pending (remote-touching) discard**, and never touch
  engagement authoring; read-only blocks all external repository mutations;
  maintenance/recovery is always allowed. The status read model exposes the
  `denied_intents` projection with `block_kind ∈ none | read_only | sync_in_progress |
  sync_health` and `blocked_reason`, so a tab joining during a transient block
  reconstructs it.

## 3. Current state (verified)

Navigation and surfaces:
- `tools/gui/src/ui/components/NavBar.vue` — tier-first sections; enterprise workflow
  buttons render only when `entStatus && adminMode`; `adminMode` comes from
  `/admin/api/server-info`. `App.vue` initializes `readOnly`/`writeBlocked` to `false`
  and only toasts when server info fails — authority is currently fail-open.
- `/api/entities` supports `scope`; entity list rows always emit `is_global`, but
  `EntitySummarySchema` declares it optional. Merged/engagement list and taxonomy
  branches exclude internal types; the `scope=global` branches filter only assurance
  types.
- `/api/documents` list rows lack `is_global` (detail has it); no `scope` param.
  `/api/diagrams` has no `scope` and no tier field; `DiagramsView.vue` hard-codes a
  global empty stub. Both views redirect a first visit without a saved collection
  preference to group management, and their query mutators rebuild `route.query` from a
  field subset (would drop `tier`).
- Viewpoints' tier filter is a local ref (not URL-backed); detail back-links target
  `/global/*`.

Search (all paths traced):
- `/api/search` (registered in `connection_read_routes.py`), `/api/artifact-search`,
  MCP search, and the query CLI all flow through `ArtifactRepository.search/…_artifacts`
  → `src/application/_artifact_search.py`, which has three branches: FTS via
  `store.search_fts` (no visibility predicate in SQLite/combined), a scored
  `list_entities()` fallback for kinds without FTS hits, and a semantic supplement that
  requests **k=1** at threshold 0.75 when the store has ≥ 50 entities — a leading GAR
  consumes the whole semantic budget. `/api/reference-search` and
  `/api/entity-display-search` already exclude internal types; `EntitySearchInput` uses
  the filtered entity list.

Write boundary and pipeline:
- `boundary.py`: `assert_engagement_write_root` rejects enterprise roots unconditionally
  for standard writers; `assert_enterprise_write_root` guards admin ops (entities,
  connections, diagrams only). Ordinary REST model writes use
  `state.run_serialized_write` (queue + gate, read-only → HTTP 423).
- Outside that pipeline today: REST viewpoint pins and viewpoint create/edit/delete
  (`routers/viewpoint_authoring.py` — direct catalog/sidecar writes, no read-only
  check, no queue); REST group ops (`routers/groups.py` — manual read-only check, then
  direct `group_op` thread outside the queue); REST promotion and sync mutations
  (`routers/promote.py`, `routers/sync.py` — direct git ops, no gate, no read-only
  check); MCP group/viewpoint/bulk paths (direct writes / neutral staging committed to
  the caller's live root). The MCP write registry carries no intent or target metadata,
  so enumerating tools cannot prove policy invocation — only a structurally unavoidable
  executor can.
- `withdraw_enterprise` returns success without doing anything in `synced` state;
  `abandon_enterprise_branch` checks out main and deletes the branch but never resets or
  cleans uncommitted files — Discard on a dirty tree is currently not implementable
  truthfully.
- Sync health today: fetch/reconcile faults only publish a `sync_blocked` SSE event with
  an in-memory dedupe string (`git_sync.py`); nothing is persisted or cache-invalidated;
  the SSE bus replays nothing to new subscribers; several transitions build fresh
  `EnterpriseSyncState` instances that would erase any naively added health fields.
- `push_enterprise_branch` already pushes `-u` (upstream tracking).

## 4. Approach — contract/policy slices

Ordered so every UI slice lands on a stable contract. Each slice is independently
shippable.

### S1 — Search visibility policy (D7)
Frozen policy value (`excluded_entity_types: frozenset[str]`) on
`ArtifactRepository.__init__`, built from
`ontology.entity_types_with_class("internal")` at the backend, MCP, and CLI composition
roots; behavior lives in focused application search helpers (keep the facade thin).
Define **one effective entity-eligibility predicate** —
`visible(entity) AND matches_entity_type(entity) AND matches_domain(entity)` — and use
it in all three branches: prepared-SQL `NOT IN` pushdown on the entity subquery of
`search_fts` (port + SQLite + combined delegates), the predicate before marking an FTS
kind as hit and in the scored fallback, and **semantic refill**: refill past ALL known
ineligible/seen ids (hidden types, wrong entity_type, wrong domain), preserving provider
ranking and the configured result bound; when the effective requested set is empty
(e.g. an explicit `global-artifact-reference` query after visibility) skip semantic
search entirely and return zero entity hits. Align the `scope=global` list/taxonomy
branches in `entities.py`/`entity_search.py` with the internal-type predicate used by
the merged branches.

### S2 — Authorized mutation executor & write-target policy (D9, D10)
`src/application`: closed `MutationIntent` (`engagement_authoring`,
`enterprise_admin_authoring`, `promotion` [source + enterprise destination roles],
`enterprise_save`, `enterprise_submit`, `enterprise_discard`, `maintenance` — Save,
Submit, and Discard are **distinguishable authorization identities**, so a health fault
can allow the local commit that recovers a dirty tree while denying unsafe remote
actions) with a target shape per intent (bulk authorizes the **live** destination root
before staging), the pure authorization policy including
`denied_intents(reason, target)`, the **closed health-reason value type** (defined here,
inward, alongside the policy — the infrastructure aggregate only
serializes/deserializes it), an immutable per-operation authorization snapshot type +
provider protocol, and the executor port. `src/infrastructure`: the concrete
executor adapter composing the existing queue, mutation gate, and event publication;
wired only at composition roots. Order: authorize (fresh snapshot) → single queue
submission → gate acquired once inside the worker after re-checking a fresh snapshot →
execute → publish/invalidate. Migrated paths **surrender** their `@queued`/`run_sync`
ownership to the executor (no wrapping/re-entry); a timeout-bounded test on
representative formerly queued MCP and REST handlers proves one submission, one gate
acquisition, no nested wait. Mutation **registration** goes through a wrapper/factory
requiring a manifest row (intent + target extractor) — unwrapped mutators cannot
register; registry ⇔ manifest equality tests + every extractor invoked; non-mutating
POST and dry-run/validation endpoints explicitly classified. REST inventory includes
group lifecycle, viewpoint pins/create/edit/delete, ordinary
entity/connection/document/diagram routes, admin routes, promotion, and enterprise
save/submit/discard. Save commits run the artifact verifier (malformed-artifact fixture
must reject with no commit/state change); Submit/Discard are the content-neutral
exemption.
Path checks compare canonically resolved roots (exact, child, `..`, relative, symlink
spellings); standard write targets must equal the configured active engagement root.
`boundary.py` guards stay as context-free deep invariants.

### S3 — Tier URL codec & shared components (D2, D3)
Pure typed codec with a per-surface allowed-tier parameter; route-merge composable
(`...route.query`, owned keys only, hash preserved); presentational `TierFacet` (emits
typed tier, no router import) + `TierBadge` (one semantic + ARIA label).

### S4 — List contracts (D3)
`scope` param on `/api/documents` and `/api/diagrams`; filter via
`s.is_global(record.path)` **before** totals/pagination; `is_global: bool` required on
document, diagram, **and entity** list summaries (TS schemas + contract tests; detail
and search schemas keep their own contracts). Typed diagram list params object through
port → service → adapter (delegation test pins that `group` is no longer dropped).
Facet mapping: `tier=enterprise → scope=global`, `tier=engagement → scope=engagement`,
absent → no scope. Collections stay engagement-only: selecting Enterprise clears
`group`; All does not implicitly restore a cleared collection.

### S5 — Facet adoption & route consolidation (D2)
DocumentsView + DiagramsView (remove the global stub) + EntitiesView + viewpoints list
adopt codec/facet/badge; viewpoint tier filter becomes URL-backed. **Remove the
mandatory first-visit redirect to group management** on Documents and Diagrams: with no
`group` and no saved preference the list loads at All/no collection; a saved preference
merges into the URL only when the tier allows engagement collections. Functional
redirects preserve query + hash while adding `tier=enterprise`. Update detail
back-links, Home, NavBar Browse link, literal `/global/*` links. `searchHitRoute` is
untouched.

### S6 — Sync aggregate, authority read model & status cluster (D5, D6, D11)
Backend: evolve `enterprise_sync_state.py` into the pure versioned lifecycle+health
aggregate (typed load/transition/atomic persist only; helpers return transition
results; no GUI cache or event imports); the sync orchestrator and executor
publish/invalidate through injected ports after successful persistence. Reconcile in
`git_sync_enterprise.py` returns `ReconcileOutcome(lifecycle, health, completed)` —
only `completed=True` clears a prior block; `git_sync.py` faults become typed
`record_block` reasons. Convert every fresh-constructor call site
(`git_sync_enterprise.py`, `enterprise_git_ops.py`) to the helpers. **Authority is
composed fresh per status request** — the cache (`sync_status_cache.py`) keeps only
expensive git/lifecycle measurements, and the per-request `denied_intents` projection
comes from the snapshot provider (live gate state + persisted health), so direct
`gate.blocking_writes()` transitions in the sync paths are visible immediately (test
through the real `blocking_writes` production path: status before, during, and after,
with no TTL wait); persisted-health transitions still invalidate cached measurements.
Pending Discard implements the idempotent desired-state transition of §12 with
fault-injection tests after each step. `withdraw_enterprise` rejects when there is
nothing to discard and on dirty trees. Frontend: close the TS sync-status schema to
the typed unions; `SyncStatusCluster` implements the §12 reducer; authority
initializes unknown and fails closed; extract App.vue's sync/authority coordination
into a composable.

### S7 — Nav consolidation, rename, docs (D1, D4)
NavBar restructure (left nav landmark + right workflow/status landmark; defined wrap
order; menu keyboard/focus behavior). Rename per rendered-copy inventory with allowlist
(App admin banner, Home badge, Promote view, entity/diagram/document detail headers,
Entities computed titles/chips, dialogs/toasts/ARIA labels/empty states). Update
`docs/03-modeling/interfaces-and-mcp.md`, `docs/03-modeling/views-and-exploration.md`,
`docs/reference/git-sync-promotion.md`, `docs/reference/cli-and-backend.md`.

### S8 — Deterministic end-to-end closure
Scripted cycle on a local bare-remote fixture with a second worktree as reviewer:
promote → save → submit (assert upstream tracking) → reviewer merge → bounded poll →
assert checkout main, aggregate cleared, enterprise content under the Enterprise facet,
GAR present in raw reads but absent from every search surface. Preconditions recorded:
clean browser localStorage (no saved collection), fixture ids, backend flags. The query
CLI is exercised against its single-root construction; GUI/MCP against the combined
pair. Human git-host PR walkthrough is supplementary evidence only.

## 5. Security & auth considerations 🔴

- One authorization path: the injected executor is the only way REST and MCP execute
  architecture-repository mutations; UI gating is presentation only. Today REST
  viewpoint/group/promotion/sync writers bypass read-only and serialization — S2 closes
  all of them via the manifest inventory, not spot fixes.
- Standard authoring stays engagement-only in every mode; admin ops keep
  `assert_enterprise_write_root` + `is_admin_mode`; promotion/finalization intents stay
  open in normal mode and are rejected exactly when `denied_intents` says so
  (read-only always; enterprise-affecting health reasons for enterprise intents).
- Fail-closed frontend authority (D6); backend enforcement never depends on it.
- Search-policy change only narrows exposed data; prepared SQL for dynamic exclusions.

## 6. Data & consistency considerations 🔴

- One write lease per workflow transaction (branch + commit + push + state update +
  publication) under the documented lock order (workspace gate → artifact index);
  promotion cannot overlap queued writes (concurrency test).
- The sync aggregate is single-source-of-truth: lifecycle and health update through
  immutable helpers only; a lifecycle transition must not erase active health; recovery
  clears health exactly once on full success; corrupt/torn files surface as blocked
  health, not silent `synced`.
- Tier filtering before totals/pagination; GAR raw-access contract pinned
  (`find_existing_gar`/`build_gar_map`, live promotion, unfiltered raw lists/id reads).

## 7. Migrations

No artifact, ontology, or model-file changes. One runtime-state evolution: the
enterprise sync state file gains a version and health fields; unversioned files load as
healthy with lifecycle preserved (test-pinned). Router redirects preserve deep links.

## 8. Observability 🟡

- Health/blocked reasons are persisted state surfaced through the status read model
  (survive reload and reconnect); SSE remains notification/invalidation only. Existing
  `sync_*` events keep flowing.

## 9. Open questions

- **Q2 (owner, cosmetic)**: viewpoint third-tier facet label — `module` or `Built-in`?
  Default `module` until answered.

## 10. Acceptance criteria (objective)

1. Search: tests exercise FTS, fallback, and semantic branches on `/api/search`,
   `/api/artifact-search`, MCP search, entity-display search, reference search, and the
   query CLI; rank-ordered semantic fixtures (≥ 50 entities; leading candidates that
   are GAR, wrong entity_type, and wrong domain followed by an eligible entity — also
   multiple leading GARs) assert the eligible artifact IS returned; the eligibility
   predicate (visible ∧ type ∧ domain) holds identically in all three branches; an
   explicit `artifact_type="global-artifact-reference"` query returns **zero entity
   hits** (not merely "no GAR"); GAR-free-repo case included.
2. Documents/diagrams/entities: router tests plant one artifact per tier and assert
   exact totals (filtered before pagination) and required `is_global` on all three list
   contracts.
3. URL state: copied URLs restore tier; adjacent filter mutations preserve it;
   `/global/*` redirects preserve query+hash adding `tier=enterprise`; invalid, array,
   and per-surface-disallowed (`tier=module` outside viewpoints) values normalize to
   All; direct `/documents` and `/diagrams` loads with clean localStorage show the list
   (no group-management redirect).
4. Mutation authority: registration-factory coverage (unwrapped mutators cannot
   register) + registry ⇔ manifest equality for MCP tools AND REST handlers; the
   reason × action matrix is tested per {normal, admin, read-only, each health reason}
   × {engagement root, enterprise root, enterprise child, symlink, non-configured
   root} × each enterprise workflow action (`enterprise_save`, `enterprise_submit`,
   `enterprise_discard` local and pending-remote): engagement authoring succeeds only
   on the configured engagement root in writable modes and remains available under
   enterprise fetch/upstream faults; standard enterprise targets are rejected in every
   mode; admin ops succeed only in admin mode; read-only denies all external
   repository intents; `accumulating + dirty + persisted fetch fault → Save is offered
   AND accepted` (not only synced+dirty without a health reason); fetch/upstream/
   divergence faults deny promotion, submit, and pending-remote discard while allowing
   local save and local discard; maintenance always proceeds. REST viewpoint
   pins/create/edit/delete and group ops are in the matrix. A timeout-bounded test on
   formerly queued MCP and REST paths proves one queue submission, one gate
   acquisition, no nested wait.
5. Promotion and enterprise save/submit/withdraw succeed in normal mode, are rejected
   without side effects (no branch/commit/push/state/model change — asserted on the
   filesystem) when their intents are denied, and cannot overlap a queued write. Save
   commits run the artifact verifier: a malformed-artifact fixture is rejected with no
   commit and no state change.
6. Status: every §12 reducer row is component-tested; real-git API tests cover the
   underlying states incl. `accumulating+clean+ahead=0`, `pending+dirty`, dirty+behind
   precedence, read-only behind-state truthfulness, reconnect-during-block, and
   authority freshness through the REAL `gate.blocking_writes()` production path —
   status asserted before, during, and after the block with no TTL wait (authority is
   composed per request, never cached) — plus server-info failure (fail-closed),
   old-state-file load, health preservation across lifecycle transitions,
   failed-persistence ordering (no event, no cache update), and
   `ReconcileOutcome.completed`-gated clearing.
7. Every allowed Discard's real-git test asserts: checkout main, local branch absent,
   aggregate cleared, unrelated files preserved. Pending Discard: remote ref absent on
   a real bare remote; initial remote-deletion failure preserves pending; and
   fault-injection tests after remote deletion, after checkout, after local deletion,
   and during state-file persistence each show a retry converging to the full
   postcondition (already-absent ref = step success, never a Discard failure). No
   Discard is offered on dirty trees.
8. The S8 fixture cycle passes with a bounded poll deadline and recorded preconditions.
9. Rendered-copy audit: component tests assert "Enterprise"; final
   `rg -n -i "global" tools/gui/src docs` output matches the recorded allowlist.
10. Counted-line records before/after for every file in the ledger's pressure list; no
    non-grandfathered file exceeds 350; `service.py` gains zero counted lines; touched
    soft-limit files are reduced by extraction.
11. Quality gates: `uv run python -m pytest`, `uv run ruff check src/ tests/`,
    `uv run zuban check`; GUI cold `npm run lint`, `npm run typecheck`,
    `npx vitest run`.

## 11. Out of scope

- Renaming API paths/params; per-user identity/roles; cross-engagement facets;
  enterprise collection management; extending the admin operations family; reworking
  the Promote flow; destructive cleanup of uncommitted working-tree changes (dirty
  Discard); assurance-store gating (owns its own unlock model); ontology/self-model
  changes beyond descriptions of touched GUI components.

## 12. Status & action reducer (normative for S6)

Inputs: configured × per-intent authority (`denied_intents`/`block_kind`) × health ×
lifecycle × dirty × ahead × behind. Precedence: an action renders as available exactly
when its intent is not denied for its target AND the lifecycle row offers it; `behind`
is an orthogonal warning overlay applied after action selection — never silently "up to
date". A dirty working tree is lifecycle state, never an authority block — Save stays
available to resolve it. Enterprise fetch/upstream/divergence health blocks only
enterprise-affecting intents; engagement authoring stays available unless the gate
itself is read-only or transiently locked.

| State | Presentation | Actions (subject to per-intent authority) |
|---|---|---|
| Enterprise not configured | "Enterprise not configured" | none |
| Read-only / transient gate block | truthful status + block reason | none (until unblock) |
| Enterprise health blocked | health reason + lifecycle state | intents not denied by the reason (e.g. Save on a dirty tree) |
| Synced, clean | "Enterprise up to date" + workflow hint | Promote |
| Synced, dirty | "Unsaved enterprise changes" | Save |
| Accumulating, clean, ahead=0 | "Empty working branch" | Discard (empty local branch) |
| Accumulating, dirty | "Changes in progress — unsaved" | Save |
| Accumulating, clean, ahead>0 | "Ready to submit" | Submit, Discard (local branch) |
| Pending, clean | "Awaiting review" | Discard (remote + local, see below) |
| Pending, dirty | "Manual recovery needed" + guidance | none |
| Admin, any | same as above | workflow rules unchanged |

Discard contract: always requires a clean tree; `withdraw_enterprise` rejects (never
silently succeeds) when there is nothing to discard or the tree is dirty. In
accumulating states it deletes the local branch and clears the aggregate (local-only —
allowed under enterprise fetch faults). Pending Discard is an **idempotent
desired-state transition** over four postconditions, in order: remote ref absent →
checkout `main` → local branch absent → aggregate cleared. Each step treats
"already absent / already on main" as success, so a retry after any partial failure
converges without recreating or requiring the remote ref (git's failure on deleting an
absent ref must be recognized as the ref being absent, not as a Discard failure). The
aggregate stays `pending` until every postcondition is satisfied; only then is it
cleared. Initial remote-deletion failure (ref still present) preserves pending state
and reports — no claimed withdrawal. Fault-injection tests cover failure after remote
deletion, after checkout, after local deletion, and during state-file persistence;
each retry reaches the full postcondition while preserving unrelated files.
Uninitialized-but-configured repos (no `main`/upstream) surface as blocked health with
an actionable reason.

## 13. Variation dimensions (must be exercised by tests)

Tier (all/engagement/enterprise/module per surface + invalid/array/disallowed values) ×
authority (normal/admin/read-only/transient/each health reason × workflow action/unknown-at-load/server-info
failure) × enterprise repo (not configured / uninitialized / empty / populated / no
upstream / detached HEAD tolerated by reconcile) × lifecycle (all §12 rows incl.
ahead=0 and pending+dirty) × search branch (FTS enabled/disabled, no-token, fallback,
semantic with 1..n leading GARs; single + combined roots; CLI single-root) × caller
(GUI nav, search page, pickers, REST incl. viewpoint/group routes, MCP read/write,
admin REST, CLI) × URL state (direct load with clean/populated localStorage, facet
click, adjacent mutation, redirect, back/forward, copied URL). "Engagement" means the
active engagement only; raw MCP write roots outside it are rejected.
