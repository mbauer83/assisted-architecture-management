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
- [x] **S2b — Registration factory + MCP migration.**
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
      > Evidence (2026-07-18): `mutation_registration.py` — manifest of all 22
      > mutators (intents + per-call request builders over bound-with-defaults
      > arguments; save_changes switches intent on its target param; withdraw reads
      > pending state for the remote-discard variant) + `NON_MUTATING_WRITE_TOOLS`
      > (help, authoring_guidance, get_operation); `register_mutation_tool` refuses
      > unmanifested names and installs the executor wrapper (signature-preserving,
      > marker attribute). All register() sites migrated; `queued` DELETED from
      > write_queue.py (structural: the old wrapper no longer exists);
      > `artifact_admin_reindex` migrated to maintenance intent (internal gate
      > acquisition removed — executor owns the gate). Executor installed at the
      > backend composition root (`_configure_server_state`); standalone servers
      > compose a workspace-default lazily. Dry-run variants classified: they route
      > through the executor like live calls (fail-closed, same as prior queue
      > behavior). Tests: test_mcp_mutation_manifest.py (both-direction registry ⇔
      > manifest equality, wrapper markers/signatures, every builder invoked),
      > test_mcp_write_authorization.py (enterprise/child/symlink/non-configured ×
      > normal/admin rejected — enterprise rejections name the admin surface;
      > read-only; timeout-bounded single-submission/single-gate on artifact_group +
      > artifact_create_entity), test_write_queue.py rewritten onto
      > submit_serialized, test_mutation_gate.py MCP surface rewritten onto the
      > executor, test_reindex_tool.py gate test via executor. Gates: pytest 5390
      > passed/5 skipped, ruff 0, zuban 0. Counted lines: mutation_registration 184,
      > edit_tools 337, write_queue 201, arch_backend 343 (all ≤ limits). Backend
      > restart NEEDED (pending owner).
- [x] **S2c — REST inventory migration.**
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
      > Evidence (2026-07-18): `rest_mutation_manifest.py` — 40 mutators classified
      > by (METHOD, path) → intent (29 engagement, 7 admin, promotion,
      > save/submit/withdraw), 9 non-mutating routes (previews, plan, summarize,
      > query execution/export, identifier mint), `/api/assurance/*` excluded by
      > prefix (own gating). `state.run_serialized_write` DELETED; the only REST
      > write path is `authorized_write`/`authorized_write_async` (manifest row
      > required → LookupError otherwise; MutationRejected → 423 retryable / 403
      > forbidden). Executor registry moved to
      > `write/mutation_executor_registry.py` (shared by MCP + REST; fallback
      > provider re-reads gui state per snapshot — O(1)). Migrations: 25
      > run_serialized_write sites (entities/connections/documents/diagram
      > write+edge-label/admin/_arch_entity_creator), groups (_exec_op executor-run,
      > manual read-only check removed), viewpoint pins/create/edit/remove writes,
      > promote/execute (one write lease: branch+copy+state), sync routes (one
      > operation per workflow transaction). Save commits run the artifact verifier
      > in `commit_engagement_work`/`commit_enterprise_work`
      > (write/save_commit_verification.py); Submit push + Discard documented as the
      > content-neutral exemption in enterprise_git_ops. Tests:
      > test_rest_mutation_manifest.py (both-direction app-route ⇔ manifest
      > equality, per-intent builders, unmanifested-route refusal),
      > test_gui_router_sync_workflow.py (10 real-git: save commits, malformed
      > artifact → 400 + no commit + tree untouched, read-only 423 side-effect-free,
      > enterprise save under persisted fetch fault ACCEPTED, submit pushes with
      > upstream / denied under fault with no push + state preserved, withdraw local
      > allowed under fault / read-only preserved),
      > test_gui_router_write_authorization.py (10: groups/viewpoints/entity
      > read-only 423 with no side effects, promotion read-only rejection leaves
      > enterprise repo untouched, promotion serializes behind a queued write —
      > timeout-bounded), gate/mutation HTTP-surface tests rewritten onto
      > authorized_write. Gates: pytest 5414 passed/5 skipped (two unrelated
      > timing/isolation flakes observed once each under xdist load —
      > test_http_concurrent read-latency bound, test_viewpoint_execute_after_create
      > — both pass in isolation and in the final full run), ruff 0, zuban 0.
      > Counted lines: state.py 302, viewpoint_authoring 286, all others < 250; no
      > pressure-list file touched. Backend restart NEEDED (pending owner).

## S3 — Tier URL codec & shared components

- [x] **S3a — Pure tier codec (per-surface allowed set) + route-merge composable.**
      Codec accepts an allowed-tier parameter (viewpoints:
      engagement/enterprise/module; other lists: engagement/enterprise); absent, array,
      or disallowed values normalize to All via one `router.replace` preserving
      unrelated keys + hash. Vitest: codec table incl. disallowed-value normalization,
      merge rules.
      > Evidence (2026-07-18): `ui/lib/tierUrlState.ts` (Tier/TierSelection unions,
      > LIST_TIERS/VIEWPOINT_TIERS, decodeTier/tierNeedsNormalization/withTier) +
      > `ui/composables/useTierFacet.ts` (immediate-watch normalization, one
      > replace, hash preserved, owned key only). Vitest table:
      > tierUrlState.test.ts (12 — absent/array/empty/null/disallowed/case,
      > per-surface module handling, merge rules).
- [x] **S3b — `TierFacet` + `TierBadge` presentational components.**
      Facet emits typed tier (no router import); badge one semantic + ARIA label,
      visual language from the viewpoint tier-tag. Vitest per component.
      > Evidence (2026-07-18): TierFacet.vue (typed v-model emit, aria-pressed
      > segmented group, no router import) + TierBadge.vue (role=img, one
      > `tierBadgeAriaLabel`, pill styling matching the viewpoint tier-tag) with
      > logic in .helpers.ts per the repo's node-env Vitest idiom
      > (TierFacet.helpers.test.ts 3, TierBadge.helpers.test.ts 3 — incl.
      > "never renders Global"). GUI gates: eslint 0 (new files), vue-tsc clean,
      > vitest 964 passed incl. new suites.

## S4 — List contracts

- [x] **S4a — Backend scope + `is_global` on documents and diagrams.**
      `/api/documents`, `/api/diagrams`: `scope` param; filter via
      `s.is_global(record.path)` **before** totals/pagination; `is_global: bool`
      required in both list serializers. Router tests: one artifact per tier; exact
      totals per scope; badge values; tier+type and tier+group combinations.
      > Evidence (2026-07-18): scope param + pre-total tier filter on both routes;
      > `is_global` added to the document item serializer and to
      > `state.diagram_to_summary` (single diagram-summary producer). Tests:
      > tests/tools/test_gui_router_list_scopes.py (11 — per-tier fixtures, exact
      > totals, filtered-before-pagination limit=1 pin, badge values, tier+type,
      > tier+group). Backend restart NEEDED (pending owner).
- [x] **S4b — Frontend contract threading + entity contract closure.**
      Typed diagram list params (diagram_type, status, group, scope) through port →
      service → adapter (delegation test pins `group` no longer dropped); document
      scope param; `DocumentSummarySchema`/`DiagramSummarySchema` gain required
      `is_global`; `EntitySummarySchema.is_global` becomes **required** (backend
      already always emits it — list summary only; detail/search schemas unchanged);
      schema contract tests updated; entity list contract test renders both badge
      variants.
      > Evidence (2026-07-18): `listDiagrams` is now a typed params object across
      > ModelRepository port → ModelService → HttpModelRepository (the positional
      > service signature that dropped `group` is gone); `listDocuments` gains
      > `scope`. Required `is_global` on all three summary schemas (producers
      > verified: entity rows + diagram-context + diagram-entities all serialize via
      > entity_to_summary; ViewpointDiagramView alias stub defaults engagement).
      > Tests: ModelService.listParams.test.ts (3, pins group/scope forwarding),
      > domain/schemas/listSummaries.contract.test.ts (6 — both badge variants +
      > closed-contract rejection per record kind). Gates: GUI lint 0 / vue-tsc
      > clean / vitest 973 passed; backend pytest 5425 passed/5 skipped, ruff 0,
      > zuban 0.

## S5 — Facet adoption & route consolidation

- [x] **S5a — Adopt codec/facet/badge on Documents, Diagrams, Entities, Viewpoints.**
      Remove the `DiagramsView` global stub. **Remove the mandatory first-visit
      redirect to group management** on Documents and Diagrams: no `group` + no saved
      preference → list at All/no collection; saved preference merges into the URL only
      when the tier allows engagement collections; selecting Enterprise clears `group`;
      All does not implicitly restore it. Viewpoint tier filter becomes URL-backed
      (keeps `module`). Extract view state into composables/helpers per the pressure
      list. Vitest: per-surface facet↔URL↔fetch mapping; adjacent-mutation
      preservation; clean-localStorage direct load shows the list.
      > Evidence (2026-07-18): Documents/Diagrams state extracted into
      > useDocumentsListState/useDiagramsListState (views 290→233, 336→248 counted;
      > global stub + scope prop REMOVED; query writes merge `...route.query` +
      > hash); EntitiesView adopts useTierFacet (scope prop removed, vestigial
      > enterprise flat-domain sidebar removed, sort logic extracted → 532→518,
      > baseline ratcheted); viewpoint tier filter now URL-backed through
      > useTierFacet(VIEWPOINT_TIERS) keeping `module`
      > (ViewpointDefinitionsList 252→251 via helper extraction). First-visit
      > group-management redirects REMOVED on all three surfaces (savedGroupToMerge:
      > clean localStorage → list at All; merge only when tier allows engagement
      > collections; Enterprise clears `group`; All never restores). TierBadge on
      > document rows, diagram cards, entity rows; scope mapping via pure
      > listRequestParams helpers. Vitest: listRequestParams.test.ts (facet↔fetch per
      > surface, savedGroupToMerge table, viewpoint filter round-trip),
      > EntitiesViewSort.helpers.test.ts, ViewpointDefinitionsList.helpers additions.
- [x] **S5b — Functional redirects + link inventory.**
      `/global/entities`, `/global/diagrams` → faceted routes via
      `to => ({ path, query: { ...to.query, tier: "enterprise" }, hash: to.hash })`.
      Update `EntityDetailView`/`DiagramDetailView` back-links, Home, NavBar Browse
      link, literal `/global/*` links. Do **not** modify `searchHitRoute`.
      Tests: redirect preserves query+hash (pin
      `/global/entities?domain=motivation&view=treemap#catalog`,
      `/global/diagrams?type=archimate&group=x`); back/forward; copied URL.
      > Evidence (2026-07-18): router `/global/entities` + `/global/diagrams` are
      > functional redirects `to => ({ path, query: { ...to.query, tier:
      > 'enterprise' }, hash: to.hash })`; `/global/search` unchanged;
      > `searchHitRoute` untouched. Links updated: NavBar enterprise Browse/Diagrams
      > → faceted routes; DiagramDetailView back-push → `/diagrams?tier=enterprise`;
      > EntityDetailView backTo carries `tier=enterprise` for enterprise entities.
      > Tests: router/__tests__/globalRedirects.test.ts (5 — both pinned URLs with
      > query+hash, back/forward across the redirect, copied faceted URL,
      > /global/search) via memory-history navigation. Gates: GUI lint 0, vue-tsc
      > clean, vitest 994 passed (95 files); backend length policy green with
      > EntitiesView baseline ratcheted 532→518.

## S6 — Sync aggregate, authority read model & status cluster

- [x] **S6a — Pure versioned lifecycle+health aggregate.**
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
      > Evidence (2026-07-18): aggregate v2 (version field, frozen dataclasses,
      > closed lifecycle union + SyncHealthRecord serializing the
      > application-owned reason type, atomic tmp+os.replace persist-on-change,
      > default aggregate = no file, re-recording identical block = no-op, corrupt/
      > unknown-reason/unknown-status → state_file_corrupt health; NO GUI/event
      > imports). Helpers: replace_lifecycle/clear_lifecycle/record_commits_behind/
      > record_block/clear_block returning SyncTransition; `save`/`clear` REMOVED
      > (all call sites in git_sync_enterprise.py + enterprise_git_ops.py
      > converted). ReconcileOutcome(lifecycle, health, completed) from
      > reconcile_state; sync_enterprise clears health only on completed +
      > cleanly-handled polls; git_sync faults typed (fetch_failed,
      > upstream_missing, diverged, sync_state_unknown; dirty tree = notify-only,
      > never health). GitSyncManager gains injected on_health_changed port
      > (wired to invalidate_sync_status_cache at the backend composition root);
      > _record_sync_blocked persists BEFORE invalidate/notify (failed persistence
      > → no event, no cache update — tested). New tests:
      > test_enterprise_sync_aggregate.py (16), test_sync_health_clearing.py (5,
      > real git + bare origin); reconcile/visibility/merge suites updated to the
      > typed API. Also: suite-wide autouse executor reset in tests/conftest.py
      > (fixes cross-test executor leakage that intermittently 403'd unrelated
      > viewpoint tests in full runs). Gates: pytest 5446 passed/5 skipped, ruff 0,
      > zuban 0. Counted lines: enterprise_sync_state 187, git_sync_enterprise 243,
      > git_sync 237, enterprise_git_ops 235. Backend restart NEEDED (pending
      > owner).
- [x] **S6b — Per-action authority read model and truthful workflow ops.**
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
      > Evidence (2026-07-18): sync_status_cache caches ONLY `_measure()` git probes
      > (dirty flags + live commits_ahead in every mode incl. read-only);
      > `_compose()` per request pulls fresh lifecycle+health from the aggregate's
      > mtime-validated `load_cached` and the authority projection
      > (`_sync_authority.py`: per-intent denied_intents with codes, block_kind
      > read_only > sync_in_progress > sync_health) from the installed executor's
      > snapshot provider (`snapshot_provider` property + registry
      > `authorization_snapshot()`). Persisted health now feeds the EXECUTOR too:
      > `persisted_sync_health` reader wired at the backend install and the dynamic
      > fallback (O(1): one stat per snapshot). `abandon_enterprise_branch` is the
      > idempotent desired-state transition (remote ref absent → checkout main →
      > local branch absent → aggregate cleared; failed deletion of an absent ref =
      > step success; rejects nothing-to-discard + dirty trees); REST withdraw drops
      > the silent nothing_to_discard success (ValueError → 400), MCP withdraw
      > errors truthfully; SaveChangesDialog copy updated; TS sync-status schema
      > closed (lifecycle/health-reason/block-kind literals, SyncAuthority required,
      > nothing_to_discard removed). Tests:
      > test_gui_router_sync_status_authority.py (6 — real blocking_writes
      > before/during/after with no TTL, persisted-health reconstruction on a fresh
      > request, read-only denial sweep + truthful ahead counts,
      > accumulating+clean+ahead=0, pending+dirty),
      > test_enterprise_discard.py (8 — real bare remote: postconditions, truthful
      > rejections, initial remote-deletion failure preserves pending,
      > fault-injection after remote deletion/checkout/local deletion/state
      > persistence each converging on retry with unrelated files preserved);
      > test_sync_status_cache.py updated to the measurements API. Gates: pytest
      > 5460 passed/5 skipped, ruff 0, zuban 0; GUI lint 0/vue-tsc clean/vitest 994.
      > Backend restart NEEDED (pending owner).
- [x] **S6c — `SyncStatusCluster` component + fail-closed authority.**
      Implements the §12 reducer (every row component-tested, incl.
      `accumulating+clean+ahead=0`, `pending+dirty`, precedence, behind overlay);
      authority initializes unknown → mutating controls hidden/disabled until the first
      successful authority response; server-info/status failure stays fail-closed;
      reconnect during an existing block reconstructs it from the snapshot; SSE only
      triggers re-reads. Engagement Save + enterprise Save/Submit/Discard + Promote
      entry; empty-state cycle one-liner. Extract App.vue sync/authority coordination
      into a composable (pressure list). NavBar.vue shrinks.
      > Evidence (2026-07-18): reducer in SyncStatusCluster.helpers.ts (available =
      > intent-not-denied ∧ lifecycle-offers; behind = post-selection overlay; dirty
      > never an authority block) with 15 Vitest rows covering EVERY §12 row incl.
      > accumulating+clean+ahead=0, pending+dirty, dirty+behind precedence,
      > health-filtered actions, unknown-authority fail-closed, engagement-save
      > availability. SyncStatusCluster.vue = right-aligned status chip (tone +
      > behind glyph) + Changes menu (aria-haspopup/expanded, Escape + focusout
      > close) housing engagement Save, enterprise Save/Submit/Discard, Promote
      > entry; synced-clean presentation carries the promote workflow hint.
      > useSyncCoordination.ts extracts ALL App.vue sync/authority coordination:
      > authority initializes UNKNOWN (authorityFresh ∧ serverInfoKnown), cross-tab
      > cached status renders lifecycle but never enables actions, server-info/
      > status failure stays closed, SSE handlers only scheduleSyncStatusRefresh
      > (re-reads); provide('writeBlocked') is now fail-closed
      > (!authorityKnown ∨ readOnly ∨ writeBlocked). SSE guards extracted to
      > lib/syncEvents.ts. Counted lines: App.vue 301→74, NavBar 305→267
      > (workflow buttons/status pill removed; cluster hosted with
      > margin-inline-start:auto), useSyncCoordination 238. GUI gates: lint 0,
      > vue-tsc clean, vitest 1009 passed (96 files). Backend restart NEEDED
      > (shared with S6a/S6b).

## S7 — Nav consolidation, rename, docs

- [x] **S7a — NavBar restructure.**
      Left nav landmark (5 content links + Search) / right workflow-status landmark
      (`margin-inline-start: auto` or grid equivalent); defined wrap order; menu
      keyboard/focus behavior; keep viewpoint-driven highlight. Component test pins
      landmark/link/action membership; record a manual viewport check.
      > Evidence (2026-07-18): one `aria-label="Primary"` nav landmark
      > (Browse · Documents · Diagrams · Viewpoints · Assurance) — tier sections,
      > per-tier duplicate links, and the nav Promote verb are gone (verbs live in
      > the cluster); right `aria-label="Workflow and status"` group hosts
      > SyncStatusCluster + search with `margin-inline-start: auto`; wrap order
      > documented in CSS (primary links shrink first, workflow/search keep size);
      > viewpoint-driven highlight preserved; cluster menu has
      > aria-haspopup/expanded + Escape/focusout handling (S6c). Structure pinned by
      > NavBar.structure.test.ts (5 assertions incl. nouns-only-left and
      > no-/global-links). NavBar 305→218 counted. Manual viewport check DEFERRED to
      > the S8b live pass (needs the restarted backend).
- [x] **S7b — Rendered-copy rename with allowlist.**
      Inventory: App admin banner, HomeView badge, PromoteView title,
      EntityDetailHeader/DiagramDetailHeader, DocumentDetailView promote button,
      EntitiesView computed titles/chips, dialogs, toasts, ARIA labels, empty states.
      Component tests assert rendered "Enterprise" and absence of rendered "Global";
      final audit: `rg -n -i "global" tools/gui/src docs` reviewed against a recorded
      allowlist (`/global/*` routes, `scope=global`, `is_global`/`isGlobal*`, GAR
      terminology, compatibility comments).
      > Evidence (2026-07-18): renamed — EntityDetailHeader badge/titles/promote
      > link, DiagramDetailHeader + DocumentDetailView promote links, PromoteView
      > title/subtitle/result heading, PromotionPlanSummary conflict copy,
      > HomeView repo card + empty state, EntitiesView computed title prefix +
      > header badge + read-only subtitle, EntitySearchInput + SearchView row chips,
      > App admin banner (S6c). renderedCopyAudit.test.ts scans EVERY .vue
      > template's rendered text for \bglobal\b (one explicit allowlist entry: the
      > delete panel's GAR-terminology sentence) and pins Enterprise on the key
      > surfaces. Final `rg -n -i global tools/gui/src docs`: 113 hits, all in
      > allowlisted categories — internal identifiers (is_global/isGlobal*/scope=
      > global/'global' literals), /global/* redirect routes, CSS class names
      > (global-badge/global-chip/item-global/row--global/repo-*--global),
      > GAR terminology, compatibility comments, generic-English "global(ly)" in
      > extensibility docs.
- [x] **S7c — Docs.** Update `docs/03-modeling/interfaces-and-mcp.md`,
      `docs/03-modeling/views-and-exploration.md`,
      `docs/reference/git-sync-promotion.md`, `docs/reference/cli-and-backend.md` for
      content-first nav, tier facets, Enterprise wording, the write-boundary/read-only
      semantics, and the workflow-ops verifier exception.
      > Evidence (2026-07-18): views-and-exploration gains the tier-facet paragraph
      > (?tier= URL persistence, uniform badges, enterprise-clears-collection);
      > interfaces-and-mcp documents the single authorized mutation path
      > (engagement-only standard authoring incl. child/relative/symlink spellings,
      > admin-surface-naming rejection, read-only scope, save-verifier +
      > content-neutral exemptions); git-sync-promotion documents save verification,
      > upstream-tracking submit, truthful + idempotent discard, the Changes menu ×
      > per-intent authority, and the versioned health overlay; cli-and-backend's
      > --read-only/--admin-mode rows updated. Gates: pytest 5460 passed/5 skipped,
      > ruff 0, zuban 0; GUI vitest 1016 (98 files), vue-tsc clean, lint 0.

## S8 — Deterministic end-to-end closure

- [x] **S8a — Fixture cycle test.** Local bare remote + second reviewer worktree:
      promote → save → submit (assert upstream tracking) → reviewer merge → bounded
      poll → assert checkout main, aggregate cleared, enterprise content under the
      Enterprise facet, GAR in raw reads but absent from every search surface (GUI/MCP
      combined roots; CLI single root).
      > Evidence (2026-07-18): tests/integration/test_promotion_cycle_end_to_end.py —
      > full cycle on a real bare origin with a reviewer clone: live REST promote
      > (executed=True, files landed), enterprise save (arch/work-* branch), submit
      > with `branch@{upstream} == origin/branch` asserted + pending state, reviewer
      > --no-ff merge + push, bounded 30s poll via sync_enterprise → checkout main +
      > aggregate cleared (state file gone). Enterprise facet: /api/entities?
      > scope=global lists the promoted entity with is_global=true. GAR: exactly one
      > in raw list_entities; absent from /api/search, /api/artifact-search, and
      > repo.search_artifacts on the combined roots; CLI single-root search hides it
      > while `entities --type global-artifact-reference` lists it. Preconditions
      > recorded in the module docstring (fresh tmp fixture, normal mode, fixture
      > entity id). Gates: pytest 5462 passed/5 skipped, ruff 0, zuban 0.
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
      > Pre-restart closure review (2026-07-18) — PLAN §10 criteria:
      > 1 Search: DONE (S1a suites — FTS/fallback/semantic on all six surfaces,
      >   rank-ordered ≥50-entity fixtures incl. multiple leading GARs, explicit
      >   GAR-type query → zero entity hits, GAR-free repo).
      > 2 List contracts: DONE (S4a router tests, required is_global on all three).
      > 3 URL state: DONE (S3a codec table; S5 redirect/back-forward/copied-URL
      >   tests; clean-localStorage direct load).
      > 4 Mutation authority: DONE (S2a policy matrix + spellings; S2b registry ⇔
      >   manifest both directions + builders invoked + single-submission timeout
      >   tests; S2c REST manifest equality + read-only/side-effect tests; S6b
      >   dirty+fetch-fault Save ACCEPTED end-to-end).
      > 5 Promotion/save/submit/withdraw: DONE (S2c real-git suites, S6b discard,
      >   S8a cycle; rejection side-effect-freedom asserted on the filesystem;
      >   promotion-vs-queued-write concurrency timeout test).
      > 6 Status: DONE (S6b authority-freshness through real blocking_writes with
      >   no TTL, old-file load, health preservation, failed-persistence ordering,
      >   completed-gated clearing; S6c reducer rows component-tested).
      > 7 Discard postconditions + fault injection: DONE (S6b, real bare remote).
      > 8 S8 fixture cycle: DONE (S8a, bounded poll, recorded preconditions).
      > 9 Rendered-copy audit: DONE (S7b test + recorded rg allowlist).
      > 10 Counted lines: DONE (per-WU records; service.py 547→546 and EntitiesView
      >   532→518 baselines ratcheted; no non-grandfathered file over 350).
      > 11 Quality gates: DONE every WU (final: pytest 5462 passed/5 skipped,
      >   ruff 0, zuban 0; GUI vitest 1016/98 files, vue-tsc, eslint 0).
      > REMAINING for closure: S8b live pass (blocked on owner backend restart) +
      > the S7a manual viewport check (deferred into that pass). Open Q2 (viewpoint
      > tier label `module` vs `Built-in`) stays cosmetic/non-blocking.
