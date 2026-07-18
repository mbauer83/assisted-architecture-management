# TASKS — Content-First Navigation & Tier Transparency

Execution ledger for `PLAN-navigation-and-tier-transparency.md`. Trust this file over
memory. Tick items only after the listed verification passes, recording evidence
(commands + key output) in the WU line or a short note under it.

## Resume protocol

1. Read the PLAN, then this ledger top to bottom.
2. The first unticked WU is the current one. A WU may create a shared component that a
   later WU generalizes only if this ledger says so explicitly.
3. Quality gates for **every** WU before ticking (run targeted tests first, then full):
   - `uv run python -m pytest --tb=short -q` (0 failures)
   - `uv run ruff check src/ tests/` (0 errors, incl. E501)
   - `uv run zuban check`
   - GUI (when `tools/gui` touched, cold, from `tools/gui/`): `npm run lint`,
     `npm run typecheck`, `npx vitest run`
   - Length policy passes; record counted lines before/after for every file in the
     pressure list below that a WU touches.
4. **LoC pressure list** (counted lines; reduce by extraction, never spend remaining
   budget): `NavBar.vue` 305, `DiagramsView.vue` 336, `DocumentsView.vue` 290,
   `ViewpointDefinitionsList.vue` 252, `mcp/artifact_mcp/context.py` 256,
   `src/application/artifact_repository.py` 301 (keep it a thin facade; new behavior in
   focused helpers), `src/application/_artifact_search.py` 286,
   `src/infrastructure/artifact_index/_sqlite_queries.py` 274 (split search-specific SQL
   construction if it would grow materially),
   `src/infrastructure/artifact_index/service.py` 547 (**at its non-growing baseline —
   zero counted-line growth**; extract or offset in the same WU),
   `tools/gui/src/ui/App.vue` 301 (extract sync/authority coordination into a
   composable in S6c).
5. Hard rules — **diff-scoped**: no phase/WU/decision references, no `Any`/`any`, in any
   line this effort adds or modifies (pre-existing occurrences elsewhere are not this
   effort's cleanup unless a WU lists them). Ternaries ≤ 1 nesting, expression position.
   Separate test file per component/use-case. Real-git/real-file tests for
   git/filesystem behavior. Prepared/parameterized SQL for dynamic values.
6. Restarts: backend code changes are inert until the owner restarts the backend (ask;
   never restart yourself). GUI dev server hot-reloads. Record needed restarts per WU.

## Open questions

- [ ] **Q2**: viewpoint third-tier facet label `module` vs `Built-in` — cosmetic,
      non-blocking; default `module` until answered.

## S1 — Search visibility policy

- [x] **S1a — Policy through the application search layer, all three branches.**
      Files: `src/application/artifact_repository.py` (frozen
      `excluded_entity_types: frozenset[str]` ctor param; facade stays thin),
      `src/application/_artifact_search.py` + new focused helper(s): ONE effective
      eligibility predicate `visible ∧ matches_entity_type ∧ matches_domain` used in
      FTS acceptance/kind-hit marking, scored fallback, and **semantic refill** (refill
      past ALL ineligible/seen ids — hidden type, wrong type, wrong domain — preserving
      provider ranking and the result bound; empty effective requested set → skip
      semantic, zero entity hits), `ReadableArtifactStore.search_fts` port +
      SQLite/combined implementations (prepared `NOT IN` on the entity subquery only),
      composition roots: backend init, MCP context, `artifact_query_cli.py`.
      Tests (application-level): FTS GAR + real entity; FTS-disabled/no-token fallback;
      GAR-only FTS hit with legitimate fallback candidate (kind-hit predicate);
      rank-ordered semantic fixtures ≥ 50 entities (leading GAR / wrong-type /
      wrong-domain candidates before an eligible entity → eligible returned; multiple
      leading GARs); explicit `artifact_type="global-artifact-reference"` query →
      **zero entity hits**; combined roots; GAR-free repo.
      Adapter/delegation tests for the new `search_fts` parameter (SQLite + combined).
      Surface tests: `/api/search` (in `connection_read_routes.py`),
      `/api/artifact-search`, MCP search, CLI search (single-root construction); pin
      the already-safe `/api/reference-search` and `/api/entity-display-search`.
      Regression: `find_existing_gar`/`build_gar_map` + live promotion still see GARs;
      raw `list_entities`/id reads unfiltered. Backend restart.
      > Evidence (2026-07-18): `EntityEligibility` + semantic refill in new
      > `src/application/_search_eligibility.py`; aggregation split to
      > `_artifact_aggregation.py`; prepared `NOT IN` pushdown in `_sqlite_queries.py`
      > (+ port/SQLite/combined signatures); exclusions injected at backend
      > (`_initialise_repo`), MCP (`repo_cached`), CLI (`artifact_query_cli.main`)
      > roots from `ontology.entity_types_with_class("internal")`. `.search()` now
      > delegates to `search_artifacts` (duplicate kind-assembly removed).
      > New tests: tests/application/test_search_visibility_policy.py (11),
      > test_search_semantic_refill.py (8), test_artifact_query_cli_visibility.py (2),
      > tests/infrastructure/artifact_index/test_search_fts_exclusion.py (5),
      > tests/infrastructure/write/test_gar_raw_access_regression.py (6),
      > tests/tools/test_gui_router_search_visibility.py (4, incl. reference-search +
      > entity-display-search pins), test_mcp_search_visibility.py (4); shared fixture
      > tests/support/search_visibility_fixtures.py. Gates: pytest 5199 passed/5 skipped,
      > ruff 0, zuban 0. Counted lines: _artifact_search 286→223,
      > artifact_repository 301→284, _sqlite_queries 274→268, service 547→546
      > (baseline ratcheted), context 256→252, arch_backend 349→328
      > (`_repair_group_registries` → backend/_group_registry_startup.py). Live
      > promotion covered by existing promotion suite (green). Backend restart NEEDED
      > (pending owner).
- [x] **S1b — Internal-type parity on `scope=global` list/taxonomy branches.**
      Files: `routers/entities.py`, `routers/entity_search.py`. Router tests per scope.
      > Evidence (2026-07-18): `is_internal_entity_type` added to the `scope=global`
      > branches of `/api/entities` (entities.py) and `/api/entity-taxonomy`
      > (entity_search.py), matching the merged/engagement branches. Tests:
      > tests/tools/test_gui_router_entities_scope_internal_types.py (7 — list +
      > taxonomy × global/engagement/merged, plus filtered-before-total pin).
      > Gates: pytest 5206 passed/5 skipped, ruff 0, zuban 0. Backend restart NEEDED
      > (pending owner, shared with S1a).

## S2 — Authorized mutation executor & write-target policy

- [x] **S2a — Authorization policy, intents, snapshot provider, executor.**
      `src/application` (new focused modules): closed `MutationIntent`
      (`engagement_authoring | enterprise_admin_authoring | promotion |
      enterprise_save | enterprise_submit | enterprise_discard | maintenance` — Save,
      Submit, and Discard are distinguishable authorization identities) with per-intent
      target shape (promotion = source + enterprise destination; bulk authorizes the
      LIVE destination root before staging; standard write targets must equal the
      configured active engagement root; enterprise_discard distinguishes local vs
      pending-remote targets), the closed health-reason value type (owned HERE, inward
      — the infrastructure aggregate only serializes it), pure authorization policy
      incl. `denied_intents(reason, target)` (dirty tree is NEVER an authority block —
      enterprise_save resolves it; fetch/upstream/divergence faults allow
      enterprise_save and local discard, deny promotion, enterprise_submit, and
      pending-remote discard; read-only denies all external repository intents;
      maintenance always allowed), immutable per-operation authorization snapshot +
      provider protocol, executor port. `src/infrastructure`: concrete `AuthorizedMutationExecutor` adapter
      composing the existing queue, gate, and event publication; wired only at
      composition roots; authorize (fresh snapshot) → ONE queue submission → gate
      acquired once inside the worker after fresh re-check → execute →
      publish/invalidate; rejections use the ordinary REST write status/payload.
      `boundary.py` guards remain narrow context-free invariants. Tests: path
      spellings (exact, child, `..`, relative, symlink, non-configured root) and the
      full reason × action matrix — every health reason × every enterprise workflow
      action, incl. `accumulating + dirty + persisted fetch fault → enterprise_save
      offered and accepted`; upstream fault permits engagement authoring and
      enterprise_save, denies promotion, enterprise_submit, and pending-remote discard.
      > Evidence (2026-07-18): contract in `src/application/mutation_authorization.py`
      > (intents, target shapes RepositoryWrite/PromotionWrite/DiscardWrite, closed
      > `SyncHealthReason` = fetch_failed|upstream_missing|diverged|sync_state_unknown|
      > state_file_corrupt|repository_uninitialized, snapshot + provider/executor
      > ports); pure policy in `mutation_policy.py` (`authorize`, `denied_intents`);
      > infrastructure: `write/workspace_authorization.py` (fresh-snapshot provider,
      > O(1) inputs) + `write/authorized_mutation_executor.py` (authorize → ONE
      > `submit_serialized` → fresh re-check in worker → gate once); public
      > `submit_serialized` added to write_queue.py. Wiring to composition roots
      > lands with the first consumers (S2b/S2c) — no dead wiring now. The
      > `accumulating+dirty+fetch → Save ACCEPTED` end-to-end case lands with S2c
      > real-git REST tests (policy side covered here: dirty is not a policy input).
      > Tests: test_mutation_policy_targets.py (path spellings incl. symlink/../
      > relative/child/non-configured), test_mutation_policy_matrix.py (reason ×
      > action × mode, both discard variants, denied_intents projection),
      > test_authorized_mutation_executor.py (single submission/single gate,
      > timeout-bounded, fresh re-check rejection, gate release on failure, perf
      > guard). 168 targeted tests; full gates: pytest 5374 passed/5 skipped,
      > ruff 0, zuban 0. Perf (owner request, grounded in self-model
      > REQ concurrent-reads-serialized-writes): snapshot+authorize ≈ 10µs/call,
      > model-size independent (~20µs per write for both checks vs ms-scale
      > serialized writes); guard test bounds it at 500µs.
- [ ] **S2b — Registration factory + MCP migration.**
      Mutation registration goes through a wrapper/factory that REQUIRES a manifest row
      (intent + target extractor) and installs the executor — unwrapped mutators cannot
      register. Migrate the direct writers (`write/group.py`, `write/viewpoint.py`,
      `bulk/common.py` + `bulk/write.py` live-root authorization) and the queued tools:
      the executor REPLACES `@queued`/`run_sync` ownership (no wrapping/re-entry).
      Classify non-mutating POST and dry-run/validation endpoints explicitly. Tests:
      registry ⇔ manifest equality; every extractor invoked; timeout-bounded
      single-submission/single-gate test on representative formerly queued tools;
      enterprise/child/symlink/non-configured targets rejected on standard tools in
      every mode with an error naming the admin surface. Backend restart.
- [ ] **S2c — REST inventory migration.**
      Manifest rows + executor adoption for ALL architecture-repository REST mutators:
      ordinary entity/connection/document/diagram routes (already queued — wire through
      the executor's authorize step), `routers/viewpoint_authoring.py` (pins,
      create/edit/delete — currently no read-only check, no queue),
      `routers/groups.py` (currently manual check + unqueued thread),
      `routers/promote.py` and `routers/sync.py` (one write lease per workflow
      transaction: branch + commit + push + state update + publication; **Save commits
      run the artifact verifier** — malformed-artifact fixture rejected with no commit
      and no state change; only content-neutral git ops — Submit's push, Discard — are
      exempt, documented in code where the exemption lives), admin routes (keep
      `is_admin_mode` + `assert_enterprise_write_root`). Migrated REST handlers
      surrender their old queue wrappers to the executor (single submission — timeout
      test). Real-git REST tests: normal / read-only / denied-intent health reasons /
      transient `sync_in_progress`; assert no branch/commit/push/state-file/model
      change after rejection; synced-dirty Save succeeds under enterprise health
      warnings; concurrency test: promotion cannot overlap a queued write. Backend
      restart.

## S3 — Tier URL codec & shared components

- [ ] **S3a — Pure tier codec (per-surface allowed set) + route-merge composable.**
      Codec accepts an allowed-tier parameter (viewpoints:
      engagement/enterprise/module; other lists: engagement/enterprise); absent, array,
      or disallowed values normalize to All via one `router.replace` preserving
      unrelated keys + hash. Vitest: codec table incl. disallowed-value normalization,
      merge rules.
- [ ] **S3b — `TierFacet` + `TierBadge` presentational components.**
      Facet emits typed tier (no router import); badge one semantic + ARIA label,
      visual language from the viewpoint tier-tag. Vitest per component.

## S4 — List contracts

- [ ] **S4a — Backend scope + `is_global` on documents and diagrams.**
      `/api/documents`, `/api/diagrams`: `scope` param; filter via
      `s.is_global(record.path)` **before** totals/pagination; `is_global: bool`
      required in both list serializers. Router tests: one artifact per tier; exact
      totals per scope; badge values; tier+type and tier+group combinations.
- [ ] **S4b — Frontend contract threading + entity contract closure.**
      Typed diagram list params (diagram_type, status, group, scope) through port →
      service → adapter (delegation test pins `group` no longer dropped); document
      scope param; `DocumentSummarySchema`/`DiagramSummarySchema` gain required
      `is_global`; `EntitySummarySchema.is_global` becomes **required** (backend
      already always emits it — list summary only; detail/search schemas unchanged);
      schema contract tests updated; entity list contract test renders both badge
      variants.

## S5 — Facet adoption & route consolidation

- [ ] **S5a — Adopt codec/facet/badge on Documents, Diagrams, Entities, Viewpoints.**
      Remove the `DiagramsView` global stub. **Remove the mandatory first-visit
      redirect to group management** on Documents and Diagrams: no `group` + no saved
      preference → list at All/no collection; saved preference merges into the URL only
      when the tier allows engagement collections; selecting Enterprise clears `group`;
      All does not implicitly restore it. Viewpoint tier filter becomes URL-backed
      (keeps `module`). Extract view state into composables/helpers per the pressure
      list. Vitest: per-surface facet↔URL↔fetch mapping; adjacent-mutation
      preservation; clean-localStorage direct load shows the list.
- [ ] **S5b — Functional redirects + link inventory.**
      `/global/entities`, `/global/diagrams` → faceted routes via
      `to => ({ path, query: { ...to.query, tier: "enterprise" }, hash: to.hash })`.
      Update `EntityDetailView`/`DiagramDetailView` back-links, Home, NavBar Browse
      link, literal `/global/*` links. Do **not** modify `searchHitRoute`.
      Tests: redirect preserves query+hash (pin
      `/global/entities?domain=motivation&view=treemap#catalog`,
      `/global/diagrams?type=archimate&group=x`); back/forward; copied URL.

## S6 — Sync aggregate, authority read model & status cluster

- [ ] **S6a — Pure versioned lifecycle+health aggregate.**
      Files: `src/infrastructure/git/enterprise_sync_state.py` (version field; closed
      lifecycle + health unions: `healthy | blocked` with closed reason code, message,
      observed timestamp via `src/domain/clock.py`; unversioned files load as healthy
      with lifecycle preserved; atomic write; persist-on-change). Helpers
      (`replace_lifecycle`, `record_block`, `clear_block`) do typed
      load/transition/persist ONLY and return transition results — **no GUI cache or
      event imports in git state**; the sync orchestrator and executor
      publish/invalidate via injected ports AFTER successful persistence (failed
      persistence → no event, no cache update). Reconcile
      (`git_sync_enterprise.py`) returns `ReconcileOutcome(lifecycle, health,
      completed)`; only `completed=True` clears a prior block; `git_sync.py` faults
      become typed reasons. Convert every fresh-constructor call site
      (`git_sync_enterprise.py`, `enterprise_git_ops.py`). Corrupt/torn file → blocked
      health, not silent synced.
      Tests: old-file load, restart survival, every transition preserves health,
      completed-gated clearing (failed reconcile does NOT clear), failed-persistence
      ordering, corrupt file, concurrent lifecycle/health updates. Backend restart.
- [ ] **S6b — Per-action authority read model and truthful workflow ops.**
      Restructure the status service (`sync_status_cache.py`): the cache holds ONLY
      expensive git/lifecycle measurements; every status request composes the fresh
      authority projection (`denied_intents` with reasons,
      `block_kind ∈ none|read_only|sync_in_progress|sync_health`, `blocked_reason`)
      from the snapshot provider (live gate state + persisted health) over the cached
      measurements — **authority is never cached**, so direct `gate.blocking_writes()`
      transitions in `git_sync.py`/`git_sync_enterprise.py` are visible immediately.
      Test through the REAL `blocking_writes` production path: status before, during,
      after — no TTL wait, no `block_repo`-only shortcut. Persisted-health transitions
      still invalidate cached measurements. Live behind/ahead computed also in
      read-only mode. Pending Discard = idempotent desired-state transition (PLAN §12):
      remote ref absent → checkout main → local branch absent → aggregate cleared;
      "already absent / already on main" = step success; aggregate stays pending until
      all postconditions hold; initial remote-deletion failure (ref still present)
      preserves pending and reports. Fault-injection tests after remote deletion, after
      checkout, after local deletion, during state-file persistence — each retry
      converges (real bare-remote assertions on both ref locations).
      `withdraw_enterprise` rejects when there is nothing to discard and on dirty
      trees (real-git postcondition tests per PLAN §12/criterion 7). Close the TS
      sync-status schema to typed unions. Backend restart.
- [ ] **S6c — `SyncStatusCluster` component + fail-closed authority.**
      Implements the §12 reducer (every row component-tested, incl.
      `accumulating+clean+ahead=0`, `pending+dirty`, precedence, behind overlay);
      authority initializes unknown → mutating controls hidden/disabled until the first
      successful authority response; server-info/status failure stays fail-closed;
      reconnect during an existing block reconstructs it from the snapshot; SSE only
      triggers re-reads. Engagement Save + enterprise Save/Submit/Discard + Promote
      entry; empty-state cycle one-liner. Extract App.vue sync/authority coordination
      into a composable (pressure list). NavBar.vue shrinks.

## S7 — Nav consolidation, rename, docs

- [ ] **S7a — NavBar restructure.**
      Left nav landmark (5 content links + Search) / right workflow-status landmark
      (`margin-inline-start: auto` or grid equivalent); defined wrap order; menu
      keyboard/focus behavior; keep viewpoint-driven highlight. Component test pins
      landmark/link/action membership; record a manual viewport check.
- [ ] **S7b — Rendered-copy rename with allowlist.**
      Inventory: App admin banner, HomeView badge, PromoteView title,
      EntityDetailHeader/DiagramDetailHeader, DocumentDetailView promote button,
      EntitiesView computed titles/chips, dialogs, toasts, ARIA labels, empty states.
      Component tests assert rendered "Enterprise" and absence of rendered "Global";
      final audit: `rg -n -i "global" tools/gui/src docs` reviewed against a recorded
      allowlist (`/global/*` routes, `scope=global`, `is_global`/`isGlobal*`, GAR
      terminology, compatibility comments).
- [ ] **S7c — Docs.** Update `docs/03-modeling/interfaces-and-mcp.md`,
      `docs/03-modeling/views-and-exploration.md`,
      `docs/reference/git-sync-promotion.md`, `docs/reference/cli-and-backend.md` for
      content-first nav, tier facets, Enterprise wording, the write-boundary/read-only
      semantics, and the workflow-ops verifier exception.

## S8 — Deterministic end-to-end closure

- [ ] **S8a — Fixture cycle test.** Local bare remote + second reviewer worktree:
      promote → save → submit (assert upstream tracking) → reviewer merge → bounded
      poll → assert checkout main, aggregate cleared, enterprise content under the
      Enterprise facet, GAR in raw reads but absent from every search surface (GUI/MCP
      combined roots; CLI single root).
- [ ] **S8b — Live verification pass** (owner restarts backend first; record flags,
      clean-localStorage precondition, commands, outputs): GAR-free dropdown;
      documents/diagrams facets with real promoted artifacts (start `/documents`,
      fixture `STD@1777137196.ItT-3l.general-coding-guidelines`, ≤ 2 interactions =
      one facet click + one row click); redirects; status cluster rows reachable;
      enterprise Submit functional without `--admin-mode`; REST viewpoint/group write
      rejected in read-only backend; MCP enterprise-targeted group/viewpoint/bulk
      writes rejected.
- [ ] **S8c — Ledger closure.** Every PLAN §10 criterion checked off with evidence;
      leftovers converted to explicit follow-ups or dropped with rationale.
