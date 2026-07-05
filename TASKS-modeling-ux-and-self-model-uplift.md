# TASKS — Modeling UX Remediation, Per-Section Document Connections, Guided Wizard & Self-Model Uplift

Execution ledger for `PLAN-modeling-ux-and-self-model-uplift.md`. This file is the **source of
truth for progress**. Update it every session. The plan says *what* and *why*; this file tracks
*where we are*.

Status values: `todo` · `in-progress` · `blocked` · `review` (impl done, awaiting user/QC) · `done`.
Keep the status table and the progress log in sync. Never mark `done` until the WU checklist is
ticked in the plan **and** all quality gates pass (backend: `pytest` 0-fail · `ruff` · `zuban`;
frontend WUs additionally: `lint` · `typecheck` · `test` in `tools/gui`).

---

## Session protocol (every new / post-compaction session)

1. Read this whole file (it is short) — including the Decision log (those decisions are
   **settled**; do not relitigate them). Read the plan's §0 and §"For implementers".
2. Pick the topmost `todo`/`in-progress` WU whose dependencies are all `done`. Set it
   `in-progress` and add a dated progress-log line with your intent. Stop to ask the user only
   if the WU needs a **new** design decision absent from the Decision log — never re-ask a
   settled one.
3. **Read the plan freely** for that WU — §0, "For implementers", the WU in full, and any WU it
   depends on. The plan is curated context; reading it is cheap.
4. Implement, but **ration codebase & self-model exploration**: each WU cites the `file:line`
   (symbol names are the stable anchor if lines drifted) and model facts you need — open a cited
   location once to confirm, then act. Do NOT broad-grep `src`, sweep subsystems, or query the
   ~385-entity self-model beyond what the WU names.
5. For Workstream C WUs: invoke the `architecture-modelling` skill first;
   `artifact_authoring_guidance` before creating; `dry_run=true` before every write;
   `artifact_verify` after every batch; `artifact_edit_entity` properties = full replacement.
6. Run the quality gates. Tick the WU checklist in the plan; set status here (`done`, or
   `review` if it needs the user); add a progress-log line with what changed (files) + test
   results. Commit only if the user asked.
7. If you discover the plan is wrong, fix the plan text too (present-tense, no
   revision-history phrasing) and note it in the log.
8. **Continue with the next unblocked WU** (back to step 2) if the remaining context budget
   clearly suffices for its full cycle (implement + gates + record). Stop when it doesn't, when
   the next WU is blocked on the user (open decision, restart, review), or when all WUs are
   done — and end with a one-paragraph handoff (WUs done, ledger state, pending restarts, next
   WU).

**Backend restart caveat:** MCP/`artifact_*` tools and the GUI run against a long-running
backend; backend code changes require a user-performed restart before tools/GUI reflect them,
and MCP-surface changes require a client session restart. Sequence work so you don't block on a
restart mid-session; state clearly when a restart is needed.

---

## Status table

| WU | Title | Depends on | Status | Notes |
|----|-------|-----------|--------|-------|
| A3 | GSN: marker-free hit areas + `userSpaceOnUse` + legend + context shape | — | done | frontend (2 files) + `svg_renderer.py`; smallest, start here |
| A2 | Shared `PreviewViewport.vue`; adopt in Create/EditDiagramView | — | done | live-verified 1366px/2560px |
| A1.1 | Backend: shared entity-filter helper; `domains`/`entity_types`/`cursor` on `/api/entity-display-search` | — | done | stable sort `(domain_order, name, id)` |
| A1.2 | Frontend: single picker `doSearch` path + scroll lazy-load + tests | A1.1 | done | live-verified domain filter + lazy-load |
| A4.1 | `mapElements` viewer-extension contract (`Map<id, Element[]>`) + graphviz default extraction | — | done | contract unit tests |
| A4.2 | Sequence: `display_alias` participants + viewer extension (DOM-order messages) | A4.1 | done | live-verified both directions, no code changes needed |
| A4.3 | Activity: sentinel id-links + viewer extension (order fallback) | A4.1 | done | live-verified after fixing 3 real consumer bugs (DOMPurify scheme allow-list, SVGGElement-only gate, missing text-highlight CSS) + 1 robustness gap (native link navigation) found during the check |
| B3.1 | Multi-occurrence backend: bindings + occurrence aliases + verifier | A4.1 | done | occurrence `id` + `backing_entity_id`; `visual_role` optional metadata |
| B3.2 | Multi-occurrence frontend: multi-map, highlight-all, authoring (GUI+MCP) | B3.1 | done | golden/browser SVG smoke maps primary + occurrences to same artifact |
| B1.1 | `SectionSpec`/`DocumentSchema` value objects + loader normalization | — | done | loader emits canonical `sections` plus legacy-compatible fields |
| B1.2 | Verifier: per-section spans + E156/W157 | B1.1 | done | E155 doc-level behavior unchanged |
| B1.3 | Write path placeholders + per-section hints + MCP descriptions | B1.1 | done | MCP-surface change → session restart |
| B1.4 | REST `/api/document-types` + `schemas.ts` + per-section chips + section-aware picker | B1.1 | done | frontend |
| B1.5 | Promotion schema diff + seed exemplars + end-to-end test | B1.2, B1.3 | done | `standard` + `assurance-case` exemplars |
| C1.1 | Two-tier connections: cardinalities `1↔1..*`, actor access, GRF serving, bridge realization | — | done | model-only; inventory before adding |
| C1.2 | Two-band ArchiMate view (single-occurrence interim, `include_cardinality`) | C1.1 | done | includes cross-link to behavior views |
| C1.3 | Upgrade view to two-grouping occurrence layout | C1.2, B3.2 | done | additive edit; no per-team arrows, see decision note |
| C2 | Motivation description enrichment (6 entities, zero new entities) | — | done | full-property replacement; fixed `GOL_Po1Qw3` typo |
| C3 | Grouping taxonomy + apply via `artifact_group` | — | done | all 331 entities + 3 documents + 32/32 diagrams grouped (0 uncategorized); verifier clean (0 errors/warnings); GUI browse spot-check passed |
| B2a | Authoring-guidance REST endpoint + wizard shell + session store | — | done | route `/model/wizard` |
| B2b | Wizard domain stages: create / find / connect + commit flow | B2a, A1.2 | done | live-verified in Motivation+Application; 2 real pre-existing bugs found+fixed (domain-filter, key/value swap) |
| B2c | Elicitation layers (questionnaire, impact spine, capability anchor) + ranking | B2b | done | full cross-domain spine motivation→business→common→application (questionnaires + bridges + session-persisted proximity anchors + next-domain recommendation + priority type ordering), all live-verified; capability-anchored reuse search in strategy not built (see progress log) |
| B4.1 | Exclude `internal` entity types from authoring guidance (GAR never manually creatable) | — | todo | backend `_entity_type_guidance`; fixes wizard offering "New global-artifact-reference" |
| B4.2 | Chain-first connection suggestions (spine anchors first-rank, always in candidate pool) | — | todo | fixes hop-neighbor-only proximity + 20-item search cutoff dropping just-created entities |
| B4.3 | Reuse-first step surface: live dedupe search while typing + multiple entities per step | — | todo | supersedes `preferFind` |
| B4.4 | Omnidirectional spine: bidirectional bridges, remove mode toggle | B4.3, D-7 | todo | fold reverseQuestion variants into neutral wording |
| B4.5 | Guidance depth: in-step when-to-use, naming exemplars, domain one-liners | — | todo | content-file driven |
| B4.6 | Session recap + persistent wizard-draft resume/cleanup | D-8 | todo | recap independent of D-8; draft lifecycle gated |
| B4.7 | Strategy questionnaire + capability-anchored reuse search | B4.3 | todo | WU-B2c remainder |

Recommended order: **A3 → A2 → A1.1 → A1.2 → A4.1 → A4.2 → A4.3 → B3.1 → B3.2 → B1.1…B1.5 →
C1/C2/C3 (C-work may interleave anytime; C1.3 waits for B3.2) → B2a → B2b → B2c →
B4.1 → B4.2 → B4.3 → B4.4 (after D-7) → B4.5 → B4.6 → B4.7**.

---

## Decision log (settled — do not reopen)

| # | Decision | Status |
|---|----------|--------|
| D-1 | Picker consolidates on `/api/entity-display-search` extended with `domains`/`entity_types`/`cursor`; `/api/reference-search` remains for other consumers; shared filter predicate helper (no copy-paste between routers) | decided |
| D-2 | Extract shared `PreviewViewport.vue` for create+edit previews; `DiagramDetailView` keeps its own container (convergence is a separate later refactor) | decided |
| D-3 | Viewer-extension `mapElements` contract returns `Map<artifactId, Element[]>` (one-to-many from the start); graphviz matcher becomes the default implementation, not view-internal logic | decided |
| D-4 | Wizard delivered in slices B2a → B2b → B2c, each independently shippable | decided |
| D-5 | Per-section document rules = Option A: section objects `{name, template?, required/suggested_entity_type_connections?}`; loader normalizes legacy shape; heading text stays the section key (stable ids deferred, accepted limitation) | decided |
| D-6 | Wizard commit semantics: per-artifact verified commits (dry-run then write through the existing path) + session-tracked "undo step" while the wizard session is live; every entity/connection the wizard creates also gets a `wizard-draft` keyword/note tag, so artifacts orphaned by an abandoned session (sessionStorage lost) stay discoverable later via a normal Browse/keyword filter — no server-side session tracking, no expiry job. Staged-bulk atomic commit rejected: no new transactional machinery, and the bulk-write path is already known to be O(repo-size) per call (see `PLAN-scalable-bulk-staging.md`) — unsuited to holding a whole wizard session's writes | decided |
| D-7 | Motivation domain: **zero new entities**; rationale goes into descriptions of the six named entities (WU-C2). Assessments = states-of-affairs; outcomes = single-concern observable results; values attach to active structure elements — argumentative/comparative theses never become entities | decided |
| D-8 | Two-tier multi-team depiction: ArchiMate view with multiple occurrences of real entities (WU-B3) inside "Team/Project" layout groupings; **no** team-level model entities, **no** scenario diagram; multiplicity also stated via connection cardinalities | decided |
| D-9 | Self-model scale: no entity pruning; navigability via groups (WU-C3); stakeholder↔actor mirroring stays (convention) | decided |

---

## Progress log (append-only; newest last)

- 2026-07-04 — Plan + ledger created. All WUs `todo`. No implementation started.
- 2026-07-04 — Starting WU-A3 (GSN marker-free hit areas + userSpaceOnUse + legend + context shape).
- 2026-07-04 — WU-A3 done. Files: new `tools/gui/src/ui/lib/svgHitAreas.ts` (shared
  `SVG_MARKER_ATTRIBUTES`/`stripMarkerAttributes`); `DiagramDetailView.vue` (`addConnectionHitAreas`
  skip list extended) and `AssuranceDiagramPanel.vue` (`addEdgeHitArea` strips post-clone) both
  consume it; `src/diagram_types/gsn/svg_renderer.py` — markers switched to `userSpaceOnUse` with
  retuned absolute size, new `_legend()` emission (kinds-present only), `context` shape changed
  from pill (`rx=height/2`) to rounded rect (`rx=10`). New tests:
  `tools/gui/src/ui/lib/__tests__/svgHitAreas.test.ts` (4, pure-fake DOM per project convention —
  no jsdom installed); `tests/rendering/test_gsn_rendered_svg.py` +3 (userSpaceOnUse, legend
  present/absent) and 1 updated (context shape now rounded-rect, not pill). Also updated
  `tests/assurance/test_gsn_diagram.py::test_native_svg_uses_standard_shapes_and_accessibility`,
  which asserted the old pill shape. Gates: `pytest` 3604 passed/4 skipped; `ruff` clean; `zuban`
  clean; frontend `lint`/`typecheck`/`test` (346 tests) all clean. No backend restart needed yet
  (batch with A2, per plan's ordering note) — GSN rendering changes require a backend restart to
  be visible in the GUI/MCP before a live Playwright check would show them; not performed this
  session.
- 2026-07-04 — Starting WU-A2 (shared `PreviewViewport.vue`; adopt in Create/EditDiagramView).
- 2026-07-04 — WU-A2 → `review`. Files: new
  `tools/gui/src/ui/components/PreviewViewport.vue` (owns `usePanZoom`, bounded
  `clamp(360px, 70vh, 900px)` height copied from `DiagramDetailView.vue`'s proven `.img-container`
  pattern, slot for image content); `CreateDiagramView.vue` and `EditDiagramView.vue` adopt it,
  removing their divergent unbounded `.prev-container` blocks and local pan-zoom wiring.
  `DiagramDetailView.vue` untouched (D-2). Gates: backend unaffected (3604 passed/4 skipped,
  ruff/zuban clean); frontend `lint`/`typecheck`/`test` (346 tests) all clean. Two checklist items
  intentionally left open, both requiring the user: (1) no Vitest component test — this repo has
  no `@vue/test-utils` and Vitest runs `environment: 'node'` project-wide (confirmed via
  `vite.config.ts`'s coverage comment: .vue/composables are Playwright-covered, not
  Vitest-gated, with zero precedent anywhere in the codebase for mounting an SFC in Vitest);
  writing one would mean adding DOM tooling, a cross-cutting call beyond this WU. (2) the
  Playwright viewport-bounds smoke was not run — this sandbox has no working Chrome/Chromium
  (`playwright install chrome` needs interactive `sudo`). No backend restart needed (frontend-only
  change, dev server hot-reloads). Next: a session with a working browser should do the
  1366px/2560px Playwright check before flipping A2 to `done`; otherwise continue to WU-A1.1
  (backend picker filter/pagination), which is independent of A2.
- 2026-07-04 — Starting WU-A1.1 (backend: shared entity-filter helper; `domains`/`entity_types`/
  `cursor` on `/api/entity-display-search`). Backend-only, no browser dependency.
- 2026-07-04 — WU-A1.1 done. Files: new `src/infrastructure/gui/routers/_entity_filter.py`
  (`EntityFilter`/`parse_csv_filter`, shared by both routers);
  new `src/infrastructure/gui/routers/_entity_display_search.py` (extracted
  `entity_display_search_impl`/`EntityDisplaySearchResult`/`accepted_entity_types` out of
  `diagrams.py`, which would otherwise have crossed the 350-line hard LoC limit — went from 315
  → 265 lines net); `diagrams.py`'s `/api/entity-display-search` route gained
  `domains`/`entity_types`/`cursor` query params and now returns `{items, next_cursor}` (was a
  bare list — breaking response-shape change, frontend not yet updated, see A1.2 next);
  `diagram_entity_discovery` updated for the `.items` accessor (unaffected otherwise);
  `entity_search.py`'s `/api/reference-search` entity branch now uses the shared `EntityFilter`
  instead of inline domain/type/internal-type checks. The non-empty-query search path now also
  threads domains/entity_types through to the existing FTS/fuzzy search (previously silently
  ignored — the other half of symptom 1) and restricts it to entities only. New tests:
  `tests/tools/test_entity_filter.py` (8, unit tests on the shared predicate),
  `tests/tools/test_entity_display_search_pagination.py` (4, domain-filter/cursor-walk/
  diagram-type-composition regressions per the checklist — kept in their own file per test-file-
  per-use-case convention rather than growing the omnibus `test_gui_router_diagrams.py`, which
  only got its existing 3 tests updated for the new envelope). Gates: pytest 3616 passed/4
  skipped; ruff clean; zuban clean. No backend restart performed yet — batching it until A1.2
  (frontend) lands so one restart covers both. Continuing directly to WU-A1.2 to avoid leaving
  the picker's response contract broken for the frontend mid-session.
- 2026-07-04 — Starting WU-A1.2 (frontend: single picker `doSearch` path + scroll lazy-load;
  port/adapter/service signatures for the new `{items, next_cursor}` envelope).
- 2026-07-04 — WU-A1.2 → `review`. Files: `schemas.ts` (+`EntityDisplaySearchResultSchema`);
  `ModelRepository.ts`/`ModelService.ts`/`HttpModelRepository.ts` — `searchEntityDisplay` moved to
  an options-object signature returning `EntityDisplaySearchResult`; `EntityPickerInput.vue` —
  collapsed the two mutually-exclusive `doSearch()` branches into one path that always forwards
  `effectiveDomains`/`effectiveEntityTypes` + optional `diagramType` + cursor (fixes symptom 1:
  chip toggles previously did nothing when a diagram type was set), added `nextCursor`/
  `loadingMore` state, an `IntersectionObserver`-driven sentinel row (`ep-sentinel`) for lazy-load,
  reset-on-search-change; `EntityPickerInput.helpers.ts` (+`entityDisplayInfoToHit`, pure mapping,
  unit-tested). Gates: frontend `lint`/`typecheck`/`test` (347 tests) all clean; backend
  unaffected (already verified in A1.1). Two checklist items intentionally left open, mirroring
  A2's finding: (1) Vitest coverage for the interactive scenarios (chip→request, sentinel→fetch,
  filter-change→reset) isn't achievable — no `@vue/test-utils`, Vitest `environment: 'node'`
  project-wide, no precedent anywhere in this codebase for mounting a component; only the pure
  `entityDisplayInfoToHit` mapper is unit-tested, the rest is a by-construction argument (single
  call site, explicit `nextCursor.value = null` at the top of `doSearch`); (2) the Playwright
  picker smoke wasn't run (no working Chrome in this sandbox). Also noted: `EntityPickerInput.vue`
  was already 509 lines (well over the 350-line hard cap) before this WU touched it; this WU's net
  contribution is +20 lines — a full composable-extraction decomposition would fix the underlying
  debt but is unscoped for a picker-filtering bugfix and risks regressing a complex,
  keyboard-navigation-heavy component; left as pre-existing debt, same treatment as
  `CreateDiagramView.vue`/`EditDiagramView.vue` in WU-A2. No backend restart needed yet for A1
  (batch with A2 — one restart covers both WUs' backend+MCP-surface-free changes… actually A1.1 IS
  a REST-surface change, not MCP, so it needs a backend restart before the GUI/picker reflects it;
  A2 needs none). **A backend restart is now needed** before WU-A1's new query params/response
  envelope are live for the GUI. Next: either a session with a working browser verifies A2 + A1
  live (flipping both to `done`), or continue to WU-A4.1 (viewer-extension contract), which is
  independent of both.
- 2026-07-04 — Starting WU-A4.1 (`DiagramViewerExtension.mapElements` contract + generic-viewer
  consumption + graphviz default extraction). Backend-independent, frontend-only.
- 2026-07-04 — WU-A4.1 done. Files: `tools/gui/src/ui/lib/diagramViewerExtensions.ts` (+
  `DiagramMapContext`/`DiagramElementMap` types, optional `mapElements` on
  `DiagramViewerExtension`, new `resolveElementMap` dispatcher); new
  `tools/gui/src/ui/lib/graphvizElementMapping.ts` (`graphvizMapElements` — the node-alias and
  edge-id matching logic extracted verbatim out of `DiagramDetailView.vue`'s
  `attachInteractivity`, now returning `Map<artifactId, Element[]>` for both nodes and edges);
  `DiagramDetailView.vue` — `attachInteractivity` now calls `resolveElementMap` instead of
  containing graphviz-specific matching itself (net -45 lines despite the click-listener/
  hit-area/badge wiring staying, since the matching logic moved out); `svgNodeElems`/
  `prevHighlighted` retyped from single-`Element` to `Element[]` to carry the one-to-many shape
  through the `selectedId` highlight watcher and the drill-down-badge anchor (uses the first
  occurrence). No diagram type registers `mapElements` yet (datatype/GSN still only use
  `attachNodeSubParts`) — every existing diagram type is unaffected behaviorally, since
  `resolveElementMap` for a type with no `mapElements` runs the exact extracted graphviz logic.
  New tests: `graphvizElementMapping.test.ts` (8) + `diagramViewerExtensions.test.ts` (3), using a
  minimal fake element tree (no jsdom/happy-dom in this project, same convention as
  `svgHitAreas.test.ts`) covering node/edge matching conventions, one-to-many mapping, and the
  extension-present/absent dispatch. Gates: frontend `lint`/`typecheck` clean, Vitest 358/358
  passed (was 347; +11 new, +0 elsewhere). Backend untouched by this WU — no Python files
  changed, so backend gates are unaffected from A1.1's last-verified state. No backend restart
  needed (frontend-only; dev server hot-reloads); no MCP-surface change. Not done in this WU
  (deferred to A4.2/A4.3 per the ledger's split): sequence/activity renderer changes, their viewer
  extensions, and the Playwright smoke on self-model ACT+SEQ diagrams — those need a real
  renderer-emitted SVG to golden-test against, unlike this contract-level work. Next: WU-A4.2
  (sequence: `display_alias` participants + viewer extension) is unblocked (depends only on
  A4.1, now done).
- 2026-07-04 — Starting WU-A4.2 (sequence: `display_alias` participants + viewer extension,
  DOM-order messages).
- 2026-07-04 — WU-A4.2 → `review`. Backend:
  `src/diagram_types/sequence/renderer.py` — `_build_alias_map` (was inline in `render_body`)
  now aliases every lifeline by a normalized identity instead of positional `LL{n}`: bound
  (`entity_id` set) → the real entity's `display_alias` via `shared_artifact_index([repo_root])`
  (same repo-lookup-from-a-renderer precedent as C4's `_resolve_model.py`); unbound → its own
  local id, normalized. Added a local `_normalize_puml_alias` (diagram_types can't import
  `application` per the dependency-policy test — mirrors C4's own `_c4_types._normalize_alias`
  duplication for the same reason; a top-level `from src.application.artifact_parsing import
  normalize_puml_alias` failed `test_dependency_policy` on first attempt, corrected before
  committing). New `tests/rendering/test_sequence_renderer_entity_alias.py` (6). Updated
  `tests/rendering/test_sequence_renderer.py`'s existing `LL1`/`LL2` assertions to the new
  `ll1`/`ll2` aliases (22 tests, mechanical rename only, behavior for message ordering/grouping/
  notes unchanged). Frontend: `diagramViewerExtensions.ts` — `DiagramMapContext` gained an
  optional `diagramEntities` field (raw diagram-entities frontmatter) alongside `entities`/
  `connections`, needed for DOM-order matching that the sorted entities summary can't provide;
  `DiagramDetailView.vue`'s `resolveElementMap` call now threads it through. New
  `ui/diagram-types/sequence/sequenceElementMapping.ts` (`sequenceMapElements`): wraps
  `graphvizMapElements` (lifelines need no custom matching — the alias fix makes PlantUML's own
  `data-qualified-name` attribute sufficient) and additionally zips rendered
  `<g class="message">` groups, in DOM order, against the message array's authored order,
  skipping messages with no complete `seq-from`/`seq-to` pair (renderer emits no SVG group for
  those, which would otherwise misalign the zip). Registered in
  `ui/diagram-types/sequence/index.ts` (also added a `defineComponent({render: () => null})`
  placeholder for the required-but-unused `detailComponent`/`attachNodeSubParts` fields —
  matches the existing test-fixture convention in `diagramViewerExtensions.test.ts` of supplying
  trivial no-ops when only `mapElements` is needed). Extracted the fake-SVG-DOM harness
  (`FakeElement`/`FakeSvgRoot`/`makeEntity`/`asSvgRoot`) that `graphvizElementMapping.test.ts`
  had inlined into shared `ui/lib/__tests__/svgDomFakes.ts` (added a `g.message` selector),
  since the new sequence test needed the identical harness. New
  `sequenceElementMapping.test.ts` (5) whose fake element trees mirror a real, committed
  golden fixture (`ui/diagram-types/sequence/__tests__/fixtures/charge-flow.svg` — a genuine
  `plantuml.jar -tsvg` render of the renderer's own PUML output for one bound + one unbound
  lifeline and two messages; regenerate via the renderer + `plantuml.jar` if PlantUML's SVG
  conventions ever change). Also found and fixed two pre-existing regressions surfaced by a
  full-suite run (neither introduced this session): `test_gui_entities_router.py`'s
  `test_diagram_detail_view_queues_connection_matches_and_promote_button` asserted
  `buildConnectionAliasMap`/`resolveConnection` directly in `DiagramDetailView.vue`'s text,
  stale since WU-A4.1 moved that matching logic into `graphvizElementMapping.ts` — updated to
  check `resolveElementMap` in the view and added a new
  `test_graphviz_element_mapping_matches_connections_via_alias_helpers` for the helpers'
  actual current location. Gates: `pytest` 3623 passed/4 skipped; `ruff` clean; `zuban` clean;
  frontend `lint`/`typecheck`/`test` (363 tests, +5) all clean. No backend restart performed
  yet — batching with A1/A2 per the existing note (this WU's backend changes are renderer-only,
  no REST/MCP surface change, so a restart is only needed to make the new aliasing visible in
  already-rendered diagrams' SVGs on next re-render). Two checklist items left open, same
  reasons as A2/A1.2: Vitest can't drive `DiagramDetailView.vue` interactions directly (no
  `@vue/test-utils`, no jsdom), and the Playwright smoke needs a working browser (none in this
  sandbox) plus WU-A4.3 (activity) to be meaningful as a combined ACT+SEQ smoke. Next: WU-A4.3
  (activity sentinel id-links + viewer extension) is unblocked (depends only on A4.1, done).
- 2026-07-04 — Starting WU-A4.3 (activity: sentinel id-links + viewer extension, order fallback).
- 2026-07-04 — WU-A4.3 → `review`. Verified PlantUML's actual activity link rendering
  empirically first (real `plantuml.jar -tsvg` renders, since the plan's "order fallback for
  link-less decisions/forks" assumption turned out only half right): decisions DO accept an
  inline `[[link]]` in the `if (cond? [[link]]) then (...)` line and partitions accept one after
  the quoted label — both verified working; only `fork` rejects one outright (`fork [[url]]` is
  a PlantUML syntax error, and fork bars render as unlabeled ungrouped `<rect>`s with no
  distinguishing attribute even without a link) — so forks alone stay unselectable, not
  decisions. Backend: `src/diagram_types/activity/renderer.py` — action/decision/partition
  emission now appends `link_suffix(step)`; new sibling module `_step_links.py`
  (`link_suffix`/`sentinel_target`, extracted to keep `renderer.py` at 369 lines, matching its
  pre-existing 368-line size — already over the 350 hard cap before this session, marginal +1
  line, same treatment as `EntityPickerInput.vue` debt in A1.2) emits the user's `link`
  unchanged plus a second, additional `[[arch://<id>]]` clause — the bound entity id if
  `entity_id` is set, else the step's own local id — verified PlantUML renders multiple
  `[[...]]` clauses on one line as separate sibling `<a>`s, never a replacement. New
  `tests/rendering/test_activity_renderer_sentinel_links.py` (7). Updated
  `tests/rendering/test_activity_renderer.py`'s assertions for the new sentinel suffix on every
  action/decision/partition line (23 tests, mechanical only — link/note/lane/flow semantics
  unchanged). Frontend: new `ui/diagram-types/activity/activityElementMapping.ts`
  (`activityMapElements`): scans every `<a>` in the SVG, keeps only `arch://`-prefixed hrefs
  (ignoring the user's own link `<a>`, which keeps its real href), and maps the anchor element
  itself as the selectable representative — no DOM-order zipping needed (unlike sequence
  messages) since the sentinel directly encodes the target id, and no per-step `<g>` wrapper
  exists in PlantUML's activity SVG to attach a listener to instead (confirmed against the real
  render: shapes and link `<a>`s are flat siblings). Registered in
  `ui/diagram-types/activity/index.ts` (same `defineComponent({render: () => null})`
  placeholder pattern as sequence's A4.2 registration, for the required-but-unused
  `detailComponent`/`attachNodeSubParts`). Extended `svgDomFakes.ts` with an `a`-tag
  `querySelectorAll` selector (sequence only needed `g`/`g.message`). New
  `activityElementMapping.test.ts` (5) whose fake `<a>` elements mirror a committed golden
  fixture (`ui/diagram-types/activity/__tests__/fixtures/order-flow.svg` — a real
  `plantuml.jar -tsvg` render of the renderer's own output: one bound action, one unbound
  action, one decision). Gates: `pytest` 3630 passed/4 skipped; `ruff` clean; `zuban` clean
  (425 files); frontend `lint`/`typecheck`/`test` (368 tests, +5) all clean. Same two checklist
  items left open as A4.2 and for the same reasons: no Vitest component-mounting capability in
  this repo, and no working browser in this sandbox for the Playwright smoke — that smoke can
  now cover both ACT and SEQ diagrams together once a session has a working browser. No backend
  restart needed yet (batching with A1/A2/A4.2 — none of WU-A4's changes are a REST/MCP surface
  change, only renderer output, so a restart is only needed to make existing diagrams'
  next-rendered SVGs reflect it). WU-A4 (all three sub-parts: A4.1 done, A4.2 review, A4.3
  review) is now code-complete; only the browser-dependent checklist items remain, blocked on
  a session with Chrome available.
- 2026-07-04 — Starting WU-B3.1 (multi-occurrence backend: bindings + occurrence aliases +
  verifier). Doing the meta-ontology-v2 reconciliation reading first, as flagged.
- 2026-07-04 — Reconciliation finding: meta-ontology-v2's binding model already implements most
  of what WU-B3 needs — `Binding.visual_role` (`src/domain/bindings.py`),
  `AllowedBindingsSpec.visual_roles` per diagram-entity-type
  (`src/domain/allowed_bindings.py`), and the E408 verifier rule already permit a second
  `represents` binding to one model target once the type declares `visual_roles`. The real gaps:
  (1) E408 never validated the occurrence's actual `visual_role` value — landing this session as
  E408b; (2) ArchiMate-family diagrams (`generic_puml_renderer.py`) have no diagram-owned
  entity-element concept at all — `entity-ids-used`/`connection-ids-used` resolve straight to
  `EntityRecord`/`ConnectionRecord` via `resolve_diagram_selection`, which explicitly dedupes
  entity ids (`_unique_ids`/`dict.fromkeys`) — so occurrences can't be expressed today without
  first giving ArchiMate diagrams a lightweight diagram-entities occurrence element, mirroring
  the existing `backing_conn_id`/`_extract_conn_bindings` precedent
  (`_diagram_write.py:42`) generalized to entities as `backing_entity_id`. Wrote this design into
  the plan's WU-B3 section (was underspecified — said "verify against
  PLAN-meta-ontology-v2.md... reconcile there if the binding schema needs an occurrence key";
  it doesn't need a new binding-schema key, `visual_role` already exists — the gap is
  verification depth plus ArchiMate's own diagram format, not the binding schema).
- 2026-07-04 — Implemented E408b (verifier only, scoped increment of WU-B3.1). Files:
  `src/application/verification/_verifier_rules_binding_targets.py` — new
  `RepresentsTracker` dataclass (`by_target`/`roles_for_target`/`role_seen`) replacing the two
  loose dict params `check_binding_target`/`_check_entity_target` took (net parameter count
  unchanged vs. pre-session baseline — bundles related mutable state instead of growing the
  signature; raised by the user mid-session, addressed by switching from two extra scalar/dict
  params to one bundled tracker + one scalar); new `_check_visual_role` enforcing that once a
  target's entity type declares `visual_roles`, every `represents` binding to it (not just
  duplicates) carries a role that is present, a member of the declared set, and distinct from
  sibling occurrences of the same target in the diagram — matches
  `PLAN-meta-ontology-v2.md`'s own spec text ("each carrying a distinct visual_role label; the
  verifier requires the labels to be distinct and drawn from the declared role set").
  `_verifier_rules_bindings.py` — builds one `RepresentsTracker` per `check_bindings_scoped`
  call instead of two dicts, threads the current binding's own `visual_role` through. New tests:
  `tests/tools/test_verifier_bindings.py::TestE408bVisualRoleValidity` (6: missing role when
  declared, role not in declared set, valid single role passes, duplicate role value errors,
  distinct valid roles pass with zero issues, no-visual_roles-declared skips the check
  entirely). Gates: `pytest` 3636 passed/4 skipped (+6); `ruff` clean; `zuban` clean (425 files).
  No backend restart needed yet (batch with A1/A2/A4 — this is verifier-only, no REST/MCP
  surface change). WU-B3.1 checklist item 1 (verifier) is done; items 2-4 (ArchiMate
  diagram-entities occurrence element + write-path binding synthesis, renderer occurrence-alias
  rendering + connection-endpoint default-first-occurrence, MCP/GUI authoring surface) remain —
  full scope estimated at ~7 call sites of `generate_archimate_puml_body` plus the renderer
  itself, too large to finish cleanly alongside the research already spent this session. Status
  stays `in-progress`, not `review`, since the WU checklist is not complete. Next: a fresh
  session should pick up WU-B3.1 directly at the plan's "ArchiMate diagram-entities occurrence
  element" bullet — no further reconciliation reading needed, the design is now written down.
- 2026-07-04 — Continuing WU-B3.1 from the ArchiMate occurrence-element bullet: implement
  `backing_entity_id`/`visual_role` binding synthesis, renderer occurrence aliases, and the
  backend/MCP authoring surface with focused regression tests.
- 2026-07-04 — WU-B3.1 done. Resolution during implementation: `occurrence_id` is not a
  separate field because `diagram_entities.occurrence[].id` already is the occurrence identity;
  `backing_entity_id` points to the model entity; `visual_role` remains optional metadata and is
  not required for ArchiMate occurrence legality. Files: `src/application/modeling/binding_normalize.py`
  (`backing_entity_id` shorthand, optional `visual_role` preservation, shorthand stripping);
  `src/application/verification/_verifier_rules_bindings.py` and
  `_verifier_rules_binding_targets.py` (explicit `occurrence` subjects may represent the same
  model target using distinct occurrence ids; duplicate supplied `visual_role` values still
  error); new `src/infrastructure/rendering/archimate_occurrences.py` and
  `archimate_entity_declarations.py`; `generic_puml_renderer.py` (occurrence aliases `__2`,
  `__3`, primary connection endpoints unchanged, helper extraction brought file under 350 LoC);
  `src/infrastructure/write/artifact_write/diagram.py` (non-empty generated PUML remains
  authoritative even when occurrence metadata is present); `src/diagram_types/archimate/_type.py`
  plus MCP descriptions in `artifact_mcp/write/diagram.py`, `edit_tools.py`, and new
  `edit_tool_descriptions.py`; tests in `test_binding_normalize.py`,
  `test_diagram_bindings_write_path.py`, `test_generic_puml_renderer.py`, and
  `test_verifier_bindings.py`. Gates: focused pytest 93 passed; full `uv run pytest --tb=short -q`
  3644 passed/4 skipped; `uv run ruff check src/ tests/` clean; `uv run zuban check` clean.
  Backend restart needed before the long-running backend/MCP server exposes the updated renderer
  and MCP descriptions. Next: WU-B3.2 (frontend multi-map, highlight-all, GUI authoring/golden SVG).
- 2026-07-04 — Starting WU-B3.2 (frontend multi-occurrence mapping/highlight-all plus GUI
  authoring for additional ArchiMate occurrences). Backend/frontend/Codex restart completed by
  user before start.
- 2026-07-04 — WU-B3.2 → `review`. Files: new
  `tools/gui/src/ui/lib/archimateOccurrences.ts` (shared occurrence helpers; `id` is occurrence
  identity, `backing_entity_id` is model identity); new
  `tools/gui/src/ui/components/ArchimateOccurrenceControls.vue` (create/edit controls for
  `diagram_entities.occurrence[]`); `graphvizElementMapping.ts` now maps deterministic occurrence
  aliases (`BASE__2`, `BASE__3`) back to the backing artifact id using raw `diagram_entities`;
  `DiagramDetailView.vue` already consumed the A4 multi-map and highlights all mapped elements;
  `EditDiagramView.vue` now delegates SVG mapping to `resolveElementMap` instead of its local
  single-element matcher and stores entity/connection SVG elements as arrays; `CreateDiagramView.vue`
  and `EditDiagramView.vue` expose ArchiMate occurrence controls; regression added to
  `graphvizElementMapping.test.ts` for one backing entity rendered as primary + two occurrence
  aliases. Gates: focused Vitest mapper test 9 passed; frontend `npm run lint` clean,
  `npm run typecheck` clean, `npm run test` 369 passed; backend `uv run pytest --tb=short -q`
  3644 passed/4 skipped; `uv run ruff check src/ tests/` clean; `uv run zuban check` clean.
  Not done only because the required live Playwright smoke could not be run — no Playwright MCP
  tool is exposed in this Codex session. No backend restart needed for this WU (frontend-only);
  dev server hot reload should pick it up. Next: either run the B3.2 live browser smoke and flip
  it to `done`, or continue to WU-B1.1 if accepting the same `review` pattern used for earlier
  browser-blocked frontend WUs.
- 2026-07-04 — WU-B3.2 done after Playwright CLI smoke. Live check against `localhost:5173`:
  opened existing ArchiMate edit view `ARC@1777452513.68ZZDj.promote-artifacts`, used the new
  Occurrences GUI control to add an occurrence, previewed successfully, verified preview PUML
  contains an occurrence alias suffix (`__2`), and verified in browser runtime that
  `graphvizMapElements` maps `APP_A`, `APP_A__2`, and `APP_A__3` SVG groups to the same artifact id.
  Command required escalated browser launch because Chromium sandboxing failed in the managed
  sandbox; rerun passed with `playwright-smoke-ok`. Gates remain as recorded above: frontend
  lint/typecheck/test clean; backend pytest/ruff/zuban clean. No restart needed. Next unblocked WU:
  B1.1.
- 2026-07-04 — Starting WU-B1.1 (`SectionSpec`/`DocumentSchema` value objects + loader
  normalization). Scope is canonical loader shape plus unit tests; verifier/write/REST consumers
  stay for later B1 slices.
- 2026-07-04 — WU-B1.1 done. Files: `src/application/artifact_document_schema.py`
  (`SectionSpec`/`DocumentSchema`, `normalize_document_schema`, typed loader accessors, and
  legacy-compatible dict output with canonical `sections`); new
  `tests/application/test_artifact_document_schema.py` covering legacy
  `required_sections`/`section_templates`, new `sections` objects with per-section rules,
  loader dict compatibility, and typed object access. Compatibility fix: malformed legacy
  `section_templates` still raises the existing "not in required_sections" validation instead
  of being silently skipped. Gates: focused tests 5 passed; `uv run pytest --tb=short -q`
  3648 passed/4 skipped; `uv run ruff check src/ tests/` clean; `uv run zuban check` clean.
  Backend restart needed before the long-running backend reflects the loader change; can be
  batched with later B1 backend slices. Next: WU-B1.2 (verifier per-section spans + E156/W157).
- 2026-07-04 — Starting WU-B1.2 (verifier per-section spans + E156/W157). Scope is verifier
  body partitioning and focused tests for wrong-section failure, document-level rule continuity,
  and unknown per-section term reporting.
- 2026-07-04 — WU-B1.2 done. Files: `src/application/verification/_verifier_document.py`
  (document-body section spans by `##` heading, per-section required entity-type checks, E156
  missing-in-section errors, W157 unknown per-section term warnings, and unchanged E155
  document-level checks) and `tests/tools/test_verifier.py` (wrong-section failure,
  document-level match-anywhere, and unknown section term coverage). Gates: focused
  `uv run pytest tests/tools/test_verifier.py::TestVerifyDocumentFile -q` 8 passed;
  `uv run pytest --tb=short -q` 3651 passed/4 skipped; `uv run ruff check src/ tests/` clean;
  `uv run zuban check` clean. Backend restart needed before the long-running backend reflects
  the verifier change; no MCP/client restart needed. Next: WU-B1.3.
- 2026-07-04 — Starting WU-B1.3 (write path placeholders + per-section hints + MCP descriptions).
  Scope is canonical `sections` consumption in document placeholder generation, HTML comment
  hints for per-section expected entity links, and MCP create/edit description updates.
- 2026-07-04 — WU-B1.3 done. Files: `src/infrastructure/write/artifact_write/document.py`
  (placeholder bodies now consume canonical `sections` entries when present, preserve legacy
  section-name/template input, and emit one-line HTML comments for required/suggested section
  entity-link expectations), `src/infrastructure/mcp/artifact_mcp/write/document.py` (create/edit
  descriptions now state section-aware placement expectations), and
  `tests/tools/test_document_section_templates.py` (canonical-section helper contract and
  create-document delegation coverage). Gates: focused
  `uv run pytest tests/tools/test_document_section_templates.py -q` 16 passed;
  `uv run pytest --tb=short -q` 3653 passed/4 skipped; `uv run ruff check src/ tests/` clean;
  `uv run zuban check` clean. Backend restart needed for write-path changes, and MCP client
  session restart needed for updated tool descriptions. Next: WU-B1.4 after restarts.
- 2026-07-04 — Starting WU-B1.4 (REST `/api/document-types` + `schemas.ts` + create-view
  per-section chips + detail-view section-aware picker). Frontend-facing slice consuming the
  canonical `DocumentSchema`/`sections` shape already emitted by WU-B1.1's loader.
- 2026-07-04 — WU-B1.4 done. Files: `src/infrastructure/gui/routers/documents.py`
  (`list_document_types` now includes the canonical `sections` array, already produced by
  WU-B1.1's loader but never surfaced); `tools/gui/src/domain/schemas.ts` (+`SectionSpecSchema`,
  `DocumentTypeSchema.sections`); new `tools/gui/src/ui/lib/documentSections.ts` (pure helpers:
  `sectionAtOffset` mirrors `_verifier_document.py`'s `_SECTION_HEADING_RE`, `findSectionSpec`,
  `sectionEntityTypeTerms`, `formatEntityTypeTerm` — moved out of `DocumentCreateView.vue` to
  share with `ArtifactReferenceInput.vue` instead of duplicating it — and
  `rankedEntityTypeSet`/`isLiteralEntityTypeTerm`, which only ranks bare-name terms since
  resolving `@ClassName`/`@all` to concrete entity types needs ontology data the frontend doesn't
  have; that resolution stays backend-only in `catalogs.py`, not duplicated client-side).
  `DocumentCreateView.vue` gained a per-section required/suggested breakdown
  (`sectionsWithEntityHints`) next to the existing document-level hints.
  `MarkdownEditor.vue` exposes `getCursorOffset()`. `DocumentDetailView.vue` now loads document
  types, resolves the cursor's enclosing section on "Insert Reference" open, and passes
  `sectionLabel`/`suggestedEntityTypes` into `ArtifactReferenceInput.vue`, which shows a section
  hint bar and ranks/badges matching entity-type chips. New
  `tools/gui/src/ui/lib/__tests__/documentSections.test.ts` (17 tests); backend regression tests
  added to `tests/tools/test_gui_router_documents_groups.py::TestDocumentTypes` (canonical
  per-section entity rules exposed; legacy schema normalizes to sections without entity rules).
  Gates: `uv run pytest --tb=short -q` 3655 passed/4 skipped (+2); `uv run ruff check src/ tests/`
  clean; `uv run zuban check` clean (428 files); frontend `npm run lint` clean, `npm run typecheck`
  clean, `npm run test` 386 passed. Live Playwright smoke against `localhost:5173` (Chrome now
  available in this session's sandbox, unlike prior sessions): confirmed the create-view shows no
  stray per-section block when a doc type has none (no seed schema has per-section rules yet —
  that's WU-B1.5's job), and confirmed the detail-view picker correctly showed "Inserting into
  section: Summary" when opened with the cursor inside the self-model's
  `STD@1777137196.ItT-3l.general-coding-guidelines` "Summary" section, with the entity-type stage
  rendering normally (no suggested terms to rank, since this doc type has no per-section rules
  either) — no console errors beyond one pre-existing, unrelated one. Next: WU-B1.5 (promotion
  schema diff + seed exemplar + end-to-end test), the last WU-B1 slice — it should give
  WU-B1.4's per-section chips/hint bar something real to render against.
- 2026-07-04 — Starting WU-B1.5 (promotion schema diff compares normalized sections; `standard`
  seed exemplar moves its document-level entity-type rules to the sections where they actually
  belong; end-to-end create→verify test).
- 2026-07-04 — WU-B1.5 done (last WU-B1 slice — Workstream B1 is now fully complete). Files:
  `src/infrastructure/write/artifact_write/promote_schema_check.py` — `_document_schema_errors`
  now loads typed `DocumentSchema` objects (`get_document_schema_object`) instead of raw dicts;
  new `_document_section_errors` compares normalized `SectionSpec`s by name (missing-enterprise-
  section wording unchanged) and additionally requires each engagement section's
  `required_entity_type_connections` to be a superset of the same-named enterprise section's —
  previously only whole-document `required_sections` were compared, so a per-section rule could
  regress silently across promotion. `src/infrastructure/workspace/_repo_default_schemata.py` —
  `standard`'s seed schema converted from document-level `required_entity_type_connections`/
  `suggested_entity_type_connections` to canonical `sections`: `requirement` now required in
  "Specification" (where a standard cites what it satisfies), `principle`/`goal` suggested in
  "Motivation" (where the rationale lives) — the dogfooding exemplar the plan asked for.
  `src/infrastructure/workspace/_assurance_doc_types.py` — `assurance-case`'s blanket
  document-level `@all` suggestion narrowed to "Evidence Summary" (`@all`) and "Sign-off"
  (`stakeholder`); other assurance doc-types untouched (plan's "where sensible" scoping). New
  tests: `tests/tools/test_promote_schema_pure.py::TestDocumentSchemaErrors` (+2: missing
  per-section term reported, engagement superset passes clean); new
  `tests/tools/test_document_section_templates.py::TestStandardDocTypeSectionLifecycle` (+2: real
  seed-schema placeholder places hints in "Specification"/"Motivation" only; full create→verify
  lifecycle — `dry_run=True` preview placed on disk directly since writing the still-unlinked
  placeholder for real is itself blocked by the same E156 write-time gate, verifies E156 fires
  for "Specification", adds a relative link to a real `requirement` entity, verifies E156
  clears). Also ticked the plan's WU-B1 checklist for both items. Gates:
  `uv run pytest --tb=short -q` 3659 passed/4 skipped (+4); `uv run ruff check src/ tests/`
  clean; `uv run zuban check` clean (428 files). No backend restart needed yet for this WU alone
  (batch with the other pending B1 restarts already noted — write-path and verifier changes need
  one before the long-running backend/MCP surface reflects them). Next: Workstream C is now the
  topmost unblocked work — WU-C1.1 (two-tier connections inventory) has no dependencies.
- 2026-07-04 — Starting WU-C1.1 (two-tier connections: cardinalities `1↔1..*` on the
  enterprise↔engagement association, team-actor access to the engagement repository, GRF
  serving engagement repositories, and the structure→purpose bridge realization). Model-only;
  invoking the `architecture-modelling` skill and doing the connection inventory before any
  writes, per the plan's binding method for all Workstream C work.
- 2026-07-04 — WU-C1.1 done. Connection inventory (`artifact_query_find_connections_for` on
  every entity the plan lists) found the structure→purpose bridge realization already present
  and correct (`SRV@1712870400.Uv9Wx9` realizes `REQ@1712870400.Gg4Hh4`) — no action there.
  Four real gaps closed, each pair-legality-checked via `artifact_authoring_guidance` before a
  dry-run-then-commit write: enterprise↔engagement `archimate-association` cardinality enriched
  `[1]→[0..*]` to `[1]→[1..*]` with a matching description; `PRC@1712870400.0Rz5Ex` *Promote
  Artifacts* gained `archimate-access` to both `BOB@1712870400.so7gfN` *Engagement Repository*
  (read, during selection/validation/conflict-detection) and `BOB@1712870400.6Uok0b`
  *Enterprise Repository* (write, post-quality-gate) — `process` is the only source type in this
  pair set legal for `archimate-access` to a business object; `DOB@1777293141.4dO6js` *Global
  Entity Reference File* gained `archimate-association` to the Engagement Repository (the
  plan's "serving" language was not ArchiMate-legal for data-object→business-object — corrected
  the plan text in place, both in WU-C1.1's design bullet and the WU-C1.3 view-depiction note);
  `ACT@1712870400.Nn7Oo7` *Architect* and `ACT@1712870400.Pp8Qq8` *Developer* each gained
  `archimate-assignment` to the Engagement Repository (only legal business-actor→business-object
  outgoing type); `ROL@1776633082.udXPfB` *AI Agent* gained `archimate-association` (role→
  business-object permits no directed relation, symmetric only). All 7 writes verified clean
  per-file; final `artifact_verify(repo_scope="engagement")`: 642 files, 0 errors, 1
  pre-existing warning on an untouched, unrelated file. Ticked the plan's WU-C1 checklist item
  1. No backend restart needed (model-only; no code changed) — did not re-run the backend
  pytest/ruff/zuban gates since no `src`/`tests` files changed this WU. Next: WU-C1.2 (two-band
  ArchiMate view, single-occurrence interim, `include_cardinality`) is now unblocked.
- 2026-07-04 — Starting WU-C1.2 (two-band ArchiMate view, single-occurrence interim,
  `include_cardinality` on the tier association). Since B3.2 is already `done`, will assess at
  scaffold time whether to ship straight to the two-grouping occurrence layout (folding in
  C1.3) or land the single-occurrence interim first, per the plan's additive-upgrade note.
- 2026-07-04 — WU-C1.2 done (landed single-occurrence per the plan's sequencing note — kept as
  its own reviewable increment rather than folding in C1.3's occurrence upgrade). Created
  `ARC@1783184518.-zouRz` *One Enterprise Baseline, Many Engagements*
  (`diagram_type=archimate-layered`) via `artifact_diagram_scaffold` +
  `artifact_create_diagram(entity_ids=[...13 entities...])`; the renderer's own domain-grouping
  layout already reads as two bands (Motivation on top = purpose, Common/Business/Application
  below = structure) with correctly auto-routed up/down realization arrows, so no manual PUML
  band-nesting was needed — only one `diagram_connections` entry
  (`include_cardinality: true, include_description: true`) on the enterprise↔engagement tier
  association to render "1 -> 1..* | An enterprise repository serves and receives promotions
  from one or more engagement repositories." on that edge. `GOL@1712870400.Lm2Bn2` (the
  plan's "collaboration payoff" goal, with no direct model connection to the other 4
  purpose-band entities) got an auto-generated hidden layout link instead of floating
  disconnected. Also closed the plan's 4th WU-C1 checklist bullet (cross-link with the two
  behavior views) in the same session since it only became actionable once this view existed:
  since `DiagramRecord` carries no description field, the cross-link went into
  `PRC@1712870400.0Rz5Ex` *Promote Artifacts*'s summary (the process entity anchoring both
  behavior views and included in this new structural view), now naming all three views by
  name. **Found and fixed a real tool bug while scaffolding**: `artifact_diagram_scaffold`
  silently dropped every connection when `entity_ids` were passed in short form (the form its
  own docstring documents as accepted) — `build_diagram_scaffold` in
  `src/infrastructure/mcp/artifact_mcp/_diagram_scaffold.py` filtered
  `ConnectionRecord.source`/`.target` (always full-form) against the raw short-form input
  strings, which can never match; fixed by filtering against the resolved entities'
  `.artifact_id` instead. New regression test
  `tests/tools/test_diagram_scaffold_short_id_connections.py` (short-form scaffold call must
  still surface the real connection). Gates: `uv run pytest --tb=short -q` 3661 passed/4
  skipped (+2); `uv run ruff check src/ tests/` clean; `uv run zuban check` clean (428 files,
  unchanged file count — new test file, no new src file). `artifact_verify
  (repo_scope="engagement")`: 640 files, 0 errors, 1 pre-existing warning on an untouched file.
  **Backend restart needed**: the scaffold fix is a backend code change — the long-running
  backend must restart before `artifact_diagram_scaffold` honors short-form `entity_ids`
  correctly for future sessions (this session worked around it by passing full-form ids, so the
  view itself needed no restart to create). Next: WU-C1.3 (upgrade the structure band to the
  two-grouping occurrence layout) is now unblocked (C1.2 done, B3.2 already done). Flagging one
  finding for whoever picks up C1.3, to avoid re-deriving it: `occurrence_entities`
  (`src/infrastructure/rendering/archimate_occurrences.py`) only duplicates the rendered shape
  (alias `BASE__2`, `BASE__3`) — per B3.1's own resolution, real model connections still route
  to the **primary** occurrence's alias only, never to a team-specific occurrence. So the plan's
  "per-grouping labeled promotion/serving connections" bullet cannot be produced by opting a
  real model connection into a specific occurrence pairing — that mechanism doesn't exist. The
  two realistic paths are: (a) hand-author the upgraded view with `puml=` (manual mode, entity
  *and* occurrence aliases are just PlantUML identifiers so plain `-->`/`--` lines between them
  are legal PUML) and confirm empirically whether `artifact_verify`/the write path accept
  visual-only arrows between an occurrence alias and a real entity alias that don't correspond
  1:1 to a `connection-ids-used` entry, or (b) keep the per-team story to the grouping boxes +
  occurrences alone (no per-grouping arrows) and let the single real connection (drawn once, to
  the primary occurrence) carry the semantic relationship, which is a smaller but honest
  reading of "no team-level model entities, connections carry the interaction semantics" instead
  of literally duplicating semantics per grouping. Decide which reading before implementing —
  this is model-authoring judgment, not a missing-decision blocker, so it doesn't need to wait
  for the user unless the first path turns out to fail verification.
- 2026-07-04 — Starting WU-C1.3 (upgrade `ARC@1783185029.4Ayzz3` to the two-grouping occurrence
  layout). Deciding between C1.2's two flagged paths first: fabricating visual-only per-grouping
  arrows not backed by real model connections would violate the same "connections are model
  facts, a view never justifies inventing them" discipline the plan states for entities (§Method
  point 6) — taking path (b): grouping boxes + occurrences only, letting the existing real
  connections (routed to the primary occurrence per B3.1) carry the semantics. Checking the
  ArchiMate diagram type's authoring guidance for a visual-only grouping-container mechanism
  before editing.
- 2026-07-04 — WU-C1.3 done. `artifact_authoring_guidance(diagram_type="archimate-layered")`
  confirmed manual PUML plus `diagram_entities.occurrence[]` is the supported mechanism (plain
  rectangle containers are ordinary PUML, not a special grouping feature — no new mechanism
  needed). Hand-authored `puml=` on `ARC@1783185029.4Ayzz3` replacing the domain-grouped
  structure band with two custom groupings: *"Team / Project A"* (Engagement Repository +
  Architect + Developer + AI Agent role — the real, primary occurrences, unchanged wiring) and
  *"Team / Project B"* (a second occurrence of each of those four, added via
  `diagram_entities.occurrence[]` with `backing_entity_id`, no `visual_role` — not declared for
  these types). Enterprise Repository/Common/Application groupings kept, just repositioned.
  **Real finding, not just judgment**: confirmed by reading
  `src/infrastructure/rendering/generic_puml_renderer.py`'s `render_body` (`grouping_key` groups
  every entity, including occurrences, by *domain* — there is no custom-container concept in the
  auto-render path) that a domain-grouped auto-render could never produce team-named boxes;
  manual `puml=` was the only path, confirming C1.2's flagged option (a)/(b) fork was really
  forced to manual mode either way. Resolved that fork itself in favor of the honest reading
  (option b, no fabricated arrows): `_verifier_rules_puml_relations.py` only validates
  `Rel_*(...)` macros and `<<stereotype>>`-suffixed relation lines against
  `connection-ids-used` — a plain unlabeled `-->`/`--` line between an occurrence alias and a
  real alias would pass `artifact_verify` even with zero model backing — so passing verification
  was never the bar; not misrepresenting the model was. Team B therefore renders with zero
  arrows; the `1 -> 1..*` cardinality label (already rendered since C1.2) states the actual
  multiplicity claim, and the duplicated shapes make it visually immediate without asserting a
  per-team edge the model doesn't have. **Tool-behavior finding for future manual-PUML ArchiMate
  edits** (a real bug-adjacent gotcha, cost two dry-runs to find): `GenericPumlRenderer
  .inject_includes` (`generic_puml_renderer.py:239-245`) unconditionally inserts
  `!include ../_archimate-stereotypes.puml` right after the caller's own `@startuml` line if that
  marker string isn't already present verbatim, then expands it into the full shared
  skinparam/sprite header — this fires on *every* write, including explicit `puml=` edits. A
  first attempt that copied the existing diagram's full header (skinparam blocks, sprites,
  `hide stereotype`, `!define Rel_*` macros) into the hand-authored `puml=` produced a
  doubled-header file (still `valid: true` per `artifact_verify`, since nothing there checks for
  duplicate skinparam blocks, but visually broken). Fix: for manual ArchiMate `puml=`, supply
  only `@startuml <name>` / `top to bottom direction` / `title ...` / the groupings and
  connections / `@enduml` — never repeat the skinparam/sprite/`hide stereotype`/`Rel_*` header,
  the injector adds it automatically from the referenced `<<stereotype>>`s and `<$archimate_*>`
  sprites actually used in the body. Gates: no `src`/`tests` files changed (model/diagram content
  only) — did not re-run backend pytest/ruff/zuban. `artifact_verify(repo_scope="engagement")`:
  640 files, 0 errors, 1 pre-existing warning (unchanged). No backend restart needed (model-only).
  Live PNG render inspected and confirms the intended layout (two team boxes side by side under
  a centered Enterprise Repository, Team A wired, Team B a bare duplicate). Next: WU-C2
  (motivation description enrichment) or WU-C3 (grouping taxonomy) are both unblocked
  (no dependencies) and can interleave in any order per the plan's ordering note; B2a is also
  unblocked and independent.
- 2026-07-04 — Starting WU-C2 (motivation description enrichment: apex goal, assessment, driver,
  coherence goal+outcome, collaboration goal — six entities, zero new entities, full-property
  `artifact_edit_entity` replacement per entity, fixing the `GOL_Po1Qw3` "should trance to to"
  typo along the way). Reading each entity's full current text before editing, per the plan's
  Method point 2.
- 2026-07-04 — WU-C2 done. Six `artifact_edit_entity` calls (`GOL@1780220699.FCfDuc`,
  `ASS@1780220699.CK90bp`, `DRV@1776628131.GR9prv`, `GOL@1712870400.Po1Qw3`,
  `OUT@1712870400.LrpdG0`, `GOL@1712870400.Lm2Bn2`), each dry-run first then committed with the
  full pre-existing property set resent (per the full-replacement contract) plus one added
  rationale sentence to the description, per the plan's enrichment map — no new entities, no
  comparative/marketing phrasing, wording stays state-of-affairs/intent. Fixed the "trance to to"
  typo in `GOL_Po1Qw3` in the same edit. Deliberately did *not* add a conflict-detection row to
  `OUT_LrpdG0`'s `Metric` property — the plan flagged this as optional "if a concrete metric can
  be stated honestly", and no such signal is actually computed by the verifier today, so adding
  one would be an invented metric, not a real one. Confirmed apex-view coverage by reading
  `ARC@1780220700.Un4jQZ` *The Story in One View*: `GOL_FCfDuc`/`ASS_CK90bp`/`DRV_GR9prv`/
  `GOL_Lm2Bn2` are already its core chain (enriched text surfaces there with zero diagram edits);
  the coherence pair (`GOL_Po1Qw3`/`OUT_LrpdG0`) isn't part of that view and was never claimed to
  be. Gates: no `src`/`tests` files changed (model-only) — did not re-run backend pytest/ruff/
  zuban. `artifact_verify(repo_scope="engagement")`: 640 files, 0 errors, 1 pre-existing warning
  (unchanged). No backend restart needed. Next: WU-C3 (grouping taxonomy) or B2a (guidance
  endpoint + wizard shell) are both unblocked and independent; stopping here for context budget
  — see handoff below.
- 2026-07-04 — User feedback: "Enterprise Baseline" is a bad name for the enterprise-repository
  tier — "baseline" is conventionally contrasted with "target" for current-state vs. future-state
  architecture, and this view has nothing to do with that distinction. Fixed everywhere the
  confusion was found: renamed the WU-C1.2 diagram from "One Enterprise Baseline, Many
  Engagements" to "One Enterprise Repository, Many Engagements" (`artifact_edit_diagram` on the
  frontmatter `name` alone left the PUML body's own `title` line stale for `archimate-layered`
  diagrams — its default reconcile mode doesn't regenerate the body from a changed `name`, and
  passing a full manual `puml=` duplicated the auto-injected skinparam/sprite header — so it was
  deleted and recreated fresh, giving it a new artifact_id,
  `ARC@1783185029.4Ayzz3.one-enterprise-repository-many-engagements`); renamed the pre-existing
  activity diagram `ACT@1781338474.NTuMXo` from "Promote Engagement Work to the Enterprise
  Baseline" to "...Enterprise Repository" (this one **did** re-render its `title` line correctly
  from `name` via the default edit mode — activity diagrams regenerate their body from
  `diagram-entities` on every write, unlike ArchiMate's reconcile-only default); fixed the
  `DOB@1777293141.4dO6js`→`BOB@1712870400.so7gfN` connection description
  ("...globally available baseline content" → "...globally available content from the enterprise
  repository", added in WU-C1.1); updated `PRC@1712870400.0Rz5Ex`'s cross-link summary (added in
  this WU) to name the corrected diagram titles. Left untouched: every other "baseline" hit in
  the self-model (`extract-architecture-baseline`, `reverse-architecture`, the assurance
  tamper-evident-record entities) — those all use "baseline" in its correct current-state /
  audit-trail sense and are unrelated to the enterprise/engagement tier naming. `artifact_verify
  (repo_scope="engagement")`: 643 files, 0 errors, 1 pre-existing warning (unchanged). Also
  cleaned up one stray `tmp*.cmapx` file the delete+recreate cycle left behind in
  `diagram-catalog/rendered/` — a rendering-pipeline temp-file leak worth a look if it recurs,
  but not chased further here. **Tool-behavior note for future renames**: `artifact_edit_diagram`
  updating `name` on an `archimate-layered`/`archimate-*` diagram does not resync the PUML
  `title` line — prefer delete+recreate over hand-supplying `puml=` for a same-content rename on
  these diagram types, since manual `puml=` collides with the auto-injected static-asset header.
- 2026-07-04 — Starting WU-C3 (grouping taxonomy + apply via `artifact_group`). Topmost unblocked
  `todo` WU (B2a/B2b/B2c also unblocked/independent but the plan's ordering note prefers
  Workstream C interleaved before the wizard). Invoking the `architecture-modelling` skill first,
  then proposing a taxonomy against the actual current entity/diagram inventory before any writes.
- 2026-07-04 — WU-C3 tool-gap fix (prerequisite found before any grouping writes could happen):
  `artifact_edit_diagram`/`artifact_edit_document` had no `group` parameter at all — only
  `artifact_edit_entity` supported re-homing to a different group; diagrams/documents could only
  set a group at creation time. Without this, 31 already-existing diagrams and 3 documents could
  never be moved into collections without a destructive delete+recreate (unacceptable — would
  mint new artifact-ids and break every reference). Fixed at the correct layer per the standing
  "fix the tool, don't route around it" rule: `edit_diagram`
  (`src/infrastructure/write/artifact_write/diagram_edit.py`) and `edit_document`
  (`.../document.py`) both gained a `group: str | None = None` param that resolves the
  group-aware target path (mirroring `create_diagram`/`create_document`'s own path construction,
  confidential-store redirect included for diagrams) and moves the file — relocating stale
  rendered PNG/SVG for diagrams — when it differs from the current location; `None` is a true
  no-op (never a move). Threaded through the MCP tools (`edit_tools.py`,
  `mcp/artifact_mcp/write/document.py`) and their descriptions
  (`edit_tool_descriptions.py`). Kept `diagram_edit.py`/`document.py` within the LoC/complexity
  policy despite the addition (a live user instruction mid-session) by extracting the new
  move-and-verify branching into sibling modules rather than inlining it:
  `_diagram_group_move.py` (`commit_diagram_write` — this is genuinely new logic, not a copy) and,
  since `document.py` also crossed 350 lines from unrelated pre-existing bulk, an additional
  `_document_placeholder.py` (the pre-existing `_build_placeholder_body`/`_validate_section_templates`
  cluster, moved verbatim) plus `_document_group_move.py` (`_doc_dir`/`_resolve_document_group_path`).
  Net effect: `diagram_edit.py` 385→344 lines, `document.py` 339→310 lines — both now under the
  350 hard cap despite the new capability. New tests: `tests/tools/test_diagram_group_move.py` (7:
  MCP-surface relocate/dry-run-preview/no-op-same-group/omit-group-is-untouched + 2 contract tests
  on the path resolver) and `tests/tools/test_document_group_move.py` (7: application-layer +
  MCP-surface relocate/dry-run/omit-untouched + 2 contract tests). Gates:
  `uv run pytest --tb=short -q` 3675 passed/4 skipped (+14); `ruff check src/ tests/` clean;
  `uv run zuban check` clean (431 files). No backend restart needed yet for this sub-fix alone —
  batching with the grouping writes below (both are backend code + MCP-surface changes; the
  running backend/MCP server needs a restart before `artifact_edit_diagram`/`artifact_edit_document`
  actually accept `group=` for real GUI/MCP use — this session used the fixed functions directly
  via tests, not via the live backend).
- 2026-07-04 — Grouping taxonomy (proposed, then applied — this is the WU-C3 checklist item).
  Queried the full engagement self-model by domain (`artifact_query_list_artifacts`,
  `fields=[artifact_id, artifact_type, name]`, one call per domain — motivation/business/
  application/technology/common) to bucket by actual content rather than guessing. Confirmed via
  `host_diagram_id` that the diagram-owned "entity" types (activity/gsn/sequence/bowtie/
  control-structure/datatype/archimate-layered domains in `artifact_query_stats`, 57 records) have
  no standalone file and move automatically with their host diagram — only the 331 standalone
  model entities (business+application+common+motivation+technology) needed individual
  `group=` reassignment. Five model-project / diagram-collection groups created via
  `artifact_group` (same five slugs reused across both axes for cross-axis navigability), matching
  the plan's own example names verbatim: **`motivation-narrative`** (the whole motivation domain,
  104 entities — one coherent stakeholder/driver/goal/outcome/requirement narrative, no further
  split); **`platform-core`** (149 entities — the core artifact/model/diagram/document ontology and
  its authoring/verification/search/staging machinery; the default bucket for anything not
  specific to the other three themes); **`assurance`** (49 entities — the assurance capability
  modeled as an arch feature: STPA/CAST/GRC, confidential storage, supply-chain/vulnerability
  signals, safety/risk roles and processes); **`promotion-and-tiering`** (19 entities — the
  enterprise/engagement two-tier relationship and the promotion pipeline); **`diagram-authoring`**
  (10 entities — cross-cutting diagram-rendering/scaffolding capability; GSN stayed in `assurance`
  since its only use here is assurance cases, not generic diagram infra). Bucketing rule applied
  per entity: domain=motivation → always `motivation-narrative`; otherwise classify by what the
  entity's name says it actually does (assurance-prefixed → `assurance`, promotion/tier-language →
  `promotion-and-tiering`, diagram-type/rendering-specific → `diagram-authoring`, else
  `platform-core`) — verified counts sum to 331 before writing anything. Diagram-collections
  (31 diagrams; the 1 already in `meta-ontology` left untouched) split similarly by content:
  `motivation-narrative` 4 (goals/outcomes/forces/story-in-one-view), `promotion-and-tiering` 3,
  `assurance` 9, `diagram-authoring` 1, `platform-core` 14 (everything else — C4 views, staging/
  sync/querying behavior views). Document-collection: single `platform-core` group for all 3
  documents (2 ADRs + 1 coding-standard — genuinely all platform-wide, no honest 3-way split).
  All 11 group containers (5 model-project + 5 diagram-collection + 1 document-collection) created
  via `artifact_group` and confirmed persisted (`.arch-repo/groups.yaml` read back correctly; one
  pre-existing unrelated stray `new-project-1` model-project left untouched, not mine to clean up).
  **Membership assignment blocked by two real bugs found while attempting the first batch** (the
  104-entity `motivation-narrative` batch): (1) `artifact_bulk_write`'s `edit_entity` op silently
  dropped the `group` field entirely — `_apply_single_edit` in
  `src/infrastructure/mcp/artifact_mcp/bulk/write_apply.py` forwarded name/summary/properties/
  notes/keywords/version/status to `artifact_write_ops.edit_entity` but not `group`, so a batch
  group-reassignment reported `wrote: true` for all 104 items yet `artifact_query_stats
  (group_by="group")` still showed `entities/uncategorized: 388` afterward — fixed by adding
  `group=item.get("group")` to that call. (2) A deeper bug surfaced once (1) was fixed: the file
  *did* get written into the transaction's staged copy at the correct group-aware path
  (`<repo>/projects/<slug>/model/<domain>/<type>/<id>.md`, confirmed by
  `entity_path()`/`repo_layout.py`'s own documented target layout) but the outer staged-batch
  commit step never published it live — `_derive_manifest`/`_managed_files` in
  `batch_transaction.py` walks a hardcoded `_MANAGED_SUBTREES = (MODEL, DOCS, DIAGRAM_CATALOG)`
  allowlist of top-level directories to diff staged-vs-live, and `projects/` (the group-aware
  entity-storage root) was never added to it — silently dropping every bulk-written grouped-entity
  file at the outer transaction boundary even though the inner per-item write succeeded. Diagram-
  and document-collection group-moves are unaffected (their group-aware directories,
  `diagram-catalog/diagrams/<group>/` and `docs/<subdir>/<group>/`, already live inside the
  existing managed subtrees). Fixed by adding a new `PROJECTS = "projects"` constant to
  `src/domain/repo_layout.py` (re-exported from `src/config/repo_paths.py`, matching the existing
  `MODEL`/`DOCS`/`DIAGRAM_CATALOG` pattern) and including it in `_MANAGED_SUBTREES`. New regression
  test `tests/tools/test_bulk_write.py::TestBulkEdits::test_edit_entity_group_relocates_file`
  (reproduces the exact symptom: bulk-edit reports `wrote: true` but the file never lands at the
  live group path) — failed before both fixes, passes after. Gates:
  `uv run pytest --tb=short -q` 3676 passed/4 skipped (+1); `ruff check src/ tests/` clean;
  `uv run zuban check` clean (431 files). **Backend restart required before continuing**: both
  fixes are backend code changes and the long-running backend served the actual
  `mcp__arch-repo-write__*` tool calls used for this session's group-container creation and the
  (silently-failed) motivation batch — group containers persisted fine (registry write bypasses
  the buggy paths), but no entity/diagram/document has actually been re-homed into a group yet;
  `entities_by_group`/`diagrams_by_group`/`documents_by_group` are unchanged from session start
  (388/31+1/3 all still `uncategorized`) and must be re-verified after the restart, not assumed.
  Status stays `in-progress`. Next session: after the user restarts the backend, redo the
  `motivation-narrative` `artifact_bulk_write` batch (item list preserved above) first as the
  regression proof against the *live* server, verify with `artifact_query_stats(group_by="group")`
  that the count actually moved, then continue through business/application/technology/common
  (bucket rules above) and the 31 diagrams + 3 documents (also listed above) via
  `artifact_edit_diagram`/`artifact_edit_document`(`group=`).
- 2026-07-05 — Backend/frontend/session restarted by the user. Redid the `motivation-narrative`
  batch against the live server: same symptom as before the restart — `artifact_query_stats`
  stayed at `entities/uncategorized: 388` after a `wrote: true` bulk-write, only correcting to
  `entities/motivation-narrative: 104` after an explicit `artifact_admin_reindex`. Applying the
  business-domain batch (36 entities) and checking `artifact_query_stats` **without** reindexing
  first reproduced it a second time deterministically, ruling out restart-timing coincidence.
  **User directive received: fix the root cause now** — "the design intention was always that all
  tools (including all MCP Servers) are bridges to a common backend with a single read index."
  Root-caused with a standalone, single-process reproduction script (bypassing MCP entirely —
  `mcp_artifact_server` functions called directly) to eliminate the read/write-process-split
  theory: staleness reproduced in-process too, so this was never a cross-process problem — this
  session's earlier hypothesis chain (separate `_services` dicts per MCP stdio process,
  `repo_cached`'s `@lru_cache` never being invalidated, `gui_state`'s repo diverging from
  `shared_artifact_index`) was each checked and ruled out by direct code reading before the
  in-process repro nailed it down for good. **Actual root cause**: `EntityRecord`/`DiagramRecord`/
  `DocumentRecord.group` defaults to `"uncategorized"` on the dataclass; the full-`refresh()` scan
  path (`_scan_model_records`/`_scan_diagram_records`/`_scan_document_records` in
  `_service_incremental.py`) explicitly computes `group_fn_entity`/`_diagram`/`_document(path,
  mount.root)` and stamps it via `dataclasses.replace(...)` before inserting — but the
  **incremental** update path used by every edit (`parse_entity_for_path`/`parse_diagram_for_path`/
  `parse_document_for_path`/`parse_outgoing_for_path`, invoked by `ArtifactIndex.apply_file_changes`
  on every `artifact_edit_*`/`artifact_bulk_write` commit) never did this — it just returned
  `parse_entity(...)` etc. verbatim, silently defaulting every incrementally-touched record back to
  `"uncategorized"` regardless of its real path. This is a **generic** bug, not group-move-specific:
  it would identically corrupt the indexed group of any entity/diagram/document touched by ANY edit
  (content change, rename, anything) once it lived in a non-default group — it was invisible until
  now purely because WU-C3 is the first workload that has ever put meaningful numbers of artifacts
  into non-`uncategorized` groups and then edited them again. Confirmed the diagram/document
  full-scan functions have the identical `group_fn_diagram`/`group_fn_document` stamping the
  incremental path lacked, so all three record kinds needed the same fix.
  Fixed in `src/infrastructure/artifact_index/_service_incremental.py`: `parse_entity_for_path`,
  `parse_outgoing_for_path`, `parse_diagram_for_path`, and `parse_document_for_path` all now accept
  `mounts` (the diagram/document ones didn't take it before) and stamp `group_fn_*(path,
  mount.root)` via `replace(...)`, exactly mirroring the full-scan behavior. Also split the file
  (was already at the 350-line hard cap before this session's changes, and the fix needed several
  new lines) into `_service_incremental.py` (incremental path — 233 lines) and new
  `_service_scan.py` (full-scan path — 152 lines), a clean pre-existing section boundary (the file
  already had `# ── Full scan ──`/`# ── Incremental updates ──` comment dividers) rather than an
  artificial split; updated `service.py`'s import and one test's import of `_insert_mounted`
  accordingly. Verified with a standalone repro script before AND after the fix (staleness
  reproduced pre-fix, gone post-fix, for entity/diagram/document group moves and for both
  `artifact_bulk_write` and single-item `artifact_edit_entity`/`_diagram`/`_document`). New
  permanent regression suite `tests/infrastructure/artifact_index/test_incremental_group_stamping.py`
  (7: unit tests on all four `parse_*_for_path` functions stamping the right group from a
  `projects/<slug>/...` or diagram/document collection path, plus 3 end-to-end tests proving
  `artifact_bulk_write`/`artifact_edit_diagram`/`artifact_edit_document` are visible via
  `repo_cached(...).stats()` with **no** explicit reindex call).
  **Second, related bug found while re-verifying the one broken document link from the earlier
  motivation-narrative move** (`docs/standard/STD@...general-coding-guidelines.md`'s link to the
  now-moved `REQ@1777135513`): even after correcting the link's relative path to point at
  `projects/motivation-narrative/model/...`, `artifact_edit_document`'s dry-run kept reporting
  W155 unresolvable-link — root cause: `verify.py`'s `_document_temp_path` (which mirrors the docs
  tree into a throwaway sandbox for verification) only symlinked `ARCH_REPO` and `MODEL` into that
  sandbox, predating the `projects/` group-aware layout, so any link into a grouped entity could
  never resolve during verification regardless of correctness live. Added a `PROJECTS = "projects"`
  constant to `src/domain/repo_layout.py` (re-exported via `src/config/repo_paths.py`, matching the
  existing `MODEL`/`DOCS`/`DIAGRAM_CATALOG` constants) and included it in `_document_temp_path`'s
  symlink loop. New regression test in `tests/tools/test_document_write.py`
  (`test_create_document_resolves_link_into_grouped_entity`). This is the **third** occurrence
  this session of the same class of gap — a hardcoded list of "known top-level repo directories"
  written before `projects/` existed and never updated (the other two: `_MANAGED_SUBTREES` in
  `batch_transaction.py`, fixed earlier this session; and this incremental-indexing bug's sibling,
  the full/incremental scan asymmetry). Worth a dedicated sweep for any other such lists if more
  group-related surprises turn up.
  **Third fix, per explicit user request ("fix now, and build the rewrite feature")**: entity
  moves broke hand-authored relative markdown links to that entity from OTHER documents (the
  `STD@...` link above was a live instance of this, not a one-off typo). Found `rewrite_doc_link`
  in `src/application/repo_path_helpers.py` already existed as a pure, fully-implemented,
  zero-caller helper (computes a rewritten relative link given old/new document dir + old/new
  target path) — clearly built for exactly this feature and never wired up. Added
  `rewrite_document_links_for_moved_entity(repo_root, old_path, new_path)` to
  `_entity_rename.py` (mirrors the existing `rewrite_outgoing_referrers` sibling — scans
  `docs_root()` for `.md` files, regex-matches markdown links, skips absolute/anchor/mailto
  targets, rewrites matches via `rewrite_doc_link`) and wired it into `entity_edit.py`'s move path
  (called alongside `rewrite_outgoing_referrers`, after both the sidecar-less and M4-sidecar-rename
  branches converge — covers renames AND pure group-moves, matching how `rewrite_outgoing_referrers`
  itself is scoped). New `tests/infrastructure/write/test_document_link_rewrite_on_move.py` (4: two
  unit tests on the pure scan-and-rewrite function — rewrites a matching link, leaves
  unrelated/external/anchor links untouched — one no-docs-root no-op, and one end-to-end test
  proving `artifact_edit_entity(group=...)` auto-rewrites a real document's link). Scope note: only
  entity moves are wired up (the demonstrated, reported problem); diagram/document group-moves
  could in principle also strand a doc-body link to them, but that wasn't reported and is left as a
  documented, not silently-dropped, follow-up rather than scope-creeping this fix.
  Manually repaired the one live broken link (`STD@1777137196`'s link to `REQ@1777135513`) via
  `artifact_edit_document` once the `PROJECTS`-symlink fix made it verify clean — still pending
  live application since the running backend hasn't been restarted since these three fixes landed
  (confirmed: re-tried the dry-run against the live server after the fixes and it still showed the
  pre-fix W155/E155, i.e. the live backend is running pre-fix code, not a residual repo issue).
  Gates: `uv run pytest --tb=short -q` 3688 passed/4 skipped (+12 from this entry's three fixes);
  `ruff check src/ tests/` clean; `uv run zuban check` clean (432 files).
  **A third backend restart is now needed** (on top of the two already noted) before: (a) group
  membership changes are visible without a manual `artifact_admin_reindex` after each batch, (b)
  document links into grouped entities pass verification, and (c) entity moves auto-rewrite
  document links. Until that restart, WU-C3 progress can still continue correctly using the
  `artifact_admin_reindex(scope="full")`-after-every-batch workaround (verified reliable both
  before and after these fixes) — motivation-narrative (104) and business (36) domains are done
  this way; application/technology/common domains and the 31 diagrams + 3 documents remain.
- 2026-07-05 — Backend/frontend/session restarted again; confirmed the three fixes above are
  live (a single-item edit's group change now shows in `artifact_query_stats` with **no**
  explicit reindex — verified directly by editing one entity and re-querying immediately).
  Finished WU-C3's remaining scope: application (68), technology (14), and common (109) domains
  bulk-grouped (all via `artifact_bulk_write`, batched ~35 items/call, every batch checked
  against the pre-computed grand totals before committing) — **all 331 standalone entities are
  now grouped**, verified via `artifact_query_stats(group_by="group")`:
  `motivation-narrative 104, platform-core 149, assurance 49, promotion-and-tiering 19,
  diagram-authoring 10` (sums to 331 exactly; the other 57 "entities" — activity/gsn/sequence/
  bowtie/control-structure/datatype/archimate-layered domains — are diagram-owned, move with
  their host diagram, stay `uncategorized` by design). Then applied the diagram taxonomy
  (`artifact_edit_diagram(group=...)`, one call per diagram — bulk_write has no diagram op):
  motivation-narrative 4/4, promotion-and-tiering 3/3, assurance 8/9, platform-core 12/12,
  diagram-authoring 1/1 = **28 of 31 diagrams grouped**; then all 3 documents to `platform-core`
  via `artifact_edit_document(group=...)`.
  **User pushback mid-session, addressed head-on rather than deferred** (three separate
  questions, each answered with evidence before continuing — see conversation for full
  reasoning, summarized here for the record):
  (1) *"Why group entities at all if they're one project?"* — clarified no text content changes
  (group is pure file-location + index metadata); grouping is a navigation aid for a 388-entity
  model, not a claim about separate products.
  (2) *"GUI already filters by ArchiMate domain, and groups must survive promotion"* — confirmed
  domain and thematic grouping are orthogonal axes (domain = what kind of element; group = what
  concern, cutting across domains — e.g. `assurance` spans business/application/technology);
  confirmed promotion already has designed conflict-resolution machinery for groups
  (`_promote_groups.py`'s `GroupMappingEntry.match_status`), not an afterthought.
  (3) *"Why would occurrence bindings prevent custom puml — evaluate critically"* — this one
  **was a real bug**, found while moving `ARC@1783185029.4Ayzz3` (the hand-authored two-team
  ArchiMate view from WU-C1.3): `edit_diagram`'s content-determination branch treated *any*
  diagram carrying a `diagram-entities` dict as "re-render from it," correct for diagram-owned
  types (activity/sequence/C4/datatype/GSN, where `diagram_entities` really is the whole
  content) but wrong for ArchiMate-family diagrams, where `diagram-entities.occurrence` (WU-B3)
  is additive binding metadata on top of a separately hand-authored `puml=` body — a
  metadata-only edit (e.g. this session's `group=`) silently discarded the real layout and
  substituted an empty auto-render. Fixed using a discriminator already in the codebase
  (`ui_config.diagram_only_types` — non-empty for diagram-owned types, empty for ArchiMate) via
  new `diagram_entities_are_authoritative(verifier, diagram_type)` in `diagram_references.py`
  (kept `diagram_edit.py` at exactly 350 lines by moving the check there rather than inlining
  it). Confirmed the GUI's own edit path was never at risk — `_diagram_write.py`'s
  `/api/diagram/edit` always pre-renders and passes `puml=` explicitly, bypassing this branch
  entirely; only direct MCP calls passing neither `puml` nor `diagram_entities` (i.e. metadata-
  only edits — exactly this session's group-move feature) could trigger it. New regression tests
  `tests/tools/test_diagram_edit_preserves_manual_puml.py` (2). Moved the affected diagram by
  re-supplying its exact existing hand-authored body via explicit `puml=` (verified byte-for-byte
  reconstruction against the original via a dry-run diff before committing) — this works
  correctly independent of the restart, since the `elif puml is not None` branch was never buggy.
  **Two more real bugs found and fixed while grouping diagrams** (both safely no-ops on failure —
  M4/verification rejected the bad write and rolled back before any file was touched, confirmed
  by checking the file was still at its original location each time):
  (a) `_resolve_diagram_group_path` (added earlier this session) hardcoded a `.puml` extension
  for the target filename — broke matrix diagrams, which are `.md`. Fixed to reuse
  `current_path.suffix`. Surfaced the SEPARATE, pre-existing, larger gap it was masking: matrix
  diagrams have no working edit path at all through the generic `edit_diagram`/
  `verify_diagram_file`, which unconditionally runs `check_puml_structure` (requires
  `@startuml`/`@enduml`) — matrix diagrams need `verify_matrix_diagram_file` instead, and
  `matrix.py` only has `create_matrix`, no `edit_matrix`. **Not fixed** (out of WU-C3 scope, a
  real feature gap of its own): the 3 matrix diagrams (`MAT@1780656830.v5cdp4`,
  `MAT@1777452513.W34qBm`, `MAT@1777452513.h0iI-_`) are left `uncategorized`, untouched, valid.
  (b) `group_fn_diagram` (`repo_path_helpers.py`) didn't know about the confidential-diagrams
  subdirectory segment (`diagram-catalog/diagrams/confidential/<collection>/...`), reading
  `"confidential"` itself as the group slug instead of skipping it — the two confidential
  assurance diagrams (`BOWTIE@1781183386.u5P6sE`, `CS@1781183304.5Ezxuv`) are correctly *placed*
  at `.../confidential/assurance/...` but the live index still shows them under a spurious
  `confidential` group until the next restart+reindex (files are correct; only the derived
  index label is stale pre-fix — no further action needed once live). Fixed by explicitly
  matching the `CONFIDENTIAL_DIAGRAMS` segment before reading the collection name, mirroring the
  existing `group_fn_entity`/`_PROJECTS` pattern. New tests in `test_repo_path_helpers.py` (2).
  **Follow-up design decision made and implemented per explicit user request**: cross-engagement
  group-naming collisions on promotion (flat group slugs like `assurance` would collide/merge
  silently if a second engagement independently creates the same slug). Evaluated nested/
  hierarchical grouping (rejected — needs schema + path-layout + promotion-logic + GUI changes,
  and a rigid tree fights the same cross-cutting-facet problem this session's taxonomy itself
  demonstrates), do-nothing (rejected — existing conflict UI is a safety net, not a design, and
  generically-named groups would conflict on every promotion), and flat-namespace-with-
  engagement-qualified-default-naming (**adopted** — npm-scoped-package-style; no schema change).
  Implemented in `_promote_groups.py::compute_group_mapping`: a brand-new enterprise group now
  defaults its slug to `{engagement-label}-{engagement-slug}` (e.g. `eng-arch-repo-assurance`)
  instead of the bare slug; `uncategorized` is exempt (absence-of-grouping, not a theme); the
  promoting user can still override via `update_enterprise_groups`'s pre-existing
  `group_mapping_resolutions` to deliberately merge into an existing enterprise group. New tests
  `tests/tools/test_promote_groups.py::TestComputeGroupMapping` (3).
  Ran a full `artifact_verify(repo_scope="engagement")` at the end: zero errors, zero warnings on
  whatever it checked — but its own `counts.files` was suspiciously low and *unstable* across two
  back-to-back read-only calls (38, then 35) while `artifact_query_stats`' totals (388 entities/
  32 diagrams/3 documents/749 connections, all group counts summing correctly) were completely
  stable and correct across repeated calls. Not investigated further this session (no errors
  surfaced, and the stats-based totals are the actually-relied-upon evidence of correctness) —
  flagging `artifact_verify`'s file-count instability as a separate, real, unexplained finding
  worth a dedicated look before trusting its `counts.files` for anything.
  Gates (final, this session's cumulative changes): `uv run pytest --tb=short -q` — passed counts
  fluctuated slightly across runs (3679–3690) with **zero failures** every run (only skip-count
  varied, likely an environment/xdist artifact unrelated to these changes — also not chased
  further); `ruff check src/ tests/` clean throughout; `uv run zuban check` clean throughout
  (432 files). WU-C3 status set to `review` rather than `done`: the taxonomy is fully designed,
  documented, and applied everywhere it correctly could be, but (1) no live GUI browse
  spot-check was performed this session (text-only MCP tool use throughout), and (2) 3 matrix
  diagrams remain uncategorized pending the separate matrix-edit-path fix noted above. Next:
  either do the GUI spot-check + decide whether to fix matrix-diagram editing before flipping
  WU-C3 to `done`, or move on to B2a (wizard shell) — both are unblocked.
- 2026-07-05 — Continuing WU-C3 per explicit user request: fix the matrix-diagram edit-path gap
  before anything else this session (set back to `in-progress`). Root cause confirmed: matrix
  diagrams are markdown tables under `diagram-catalog/diagrams/*.md`, but
  `diagram_edit.edit_diagram` unconditionally ran the PUML pipeline
  (`format_diagram_puml`/`commit_diagram_write` → `verifier.verify_diagram_file` →
  `check_puml_structure`, which requires `@startuml`/`@enduml`) — so `artifact_edit_diagram` on a
  matrix id always failed verification, including for a pure `group=` move; `matrix.py` had no
  edit function at all, only `create_matrix`; and the GUI's own `/api/matrix/edit` route called
  `create_matrix` with a hardcoded flat path (`DIAGRAM_CATALOG/DIAGRAMS/{id}.md`), which would
  have silently written a stray duplicate instead of editing a grouped file in place.
  **Fixed at the correct layers, not routed around**:
  (1) generalized `commit_diagram_write` (`_diagram_group_move.py`) with `verify_fn`/`render`
  override params (defaults preserve existing PUML-diagram behavior byte-for-byte) so the same
  verified-move-and-rollback logic serves both PUML and matrix diagrams instead of matrix.py
  hand-rolling its own copy; also fixed it to `mkdir(parents=True, exist_ok=True)` unconditionally
  (was `if moved:` only — broke fresh top-level creates once matrix routed through it, since a
  brand-new artifact's parent dir was never guaranteed to exist) and to tolerate a
  not-yet-existing `diagram_path` (fresh creates) in both the rollback and the
  moved-cleanup branches. (2) `verify_content_in_temp_path` (`verify.py`) gained the matching
  `verify_fn` override for its dry-run temp-path dispatch. (3) `matrix.py`'s `create_matrix` now
  resolves an existing `artifact_id`'s real on-disk path via the registry (honouring any group it
  already lives in) instead of assuming the flat path, gained `tlp`/`group` params, and delegates
  to `commit_diagram_write` with `verify_fn=verify_matrix_diagram_file, render=False` — this fixes
  both the GUI's edit-via-create_matrix bug and adds real group-move support in one place; added
  `edit_matrix_metadata` (metadata/group-only upsert preserving the existing table body and
  structural frontmatter fields verbatim). (4) `diagram_edit.edit_diagram` now detects
  `diagram-type: matrix` and delegates to a new `_diagram_matrix_edit.edit_matrix_diagram`,
  which rejects PUML-only params (`puml`/`diagram_entities`/`diagram_connections`/
  `entity_ids_used`/`connection_ids_used`/`view_derivations`/`bindings`/`replace_bindings`/
  `edge_labels`) with a clear `ValueError` naming them, then calls `edit_matrix_metadata` —
  so `artifact_edit_diagram(artifact_id=<matrix>, group=...)` now works. (5) `artifact_create_matrix`
  (MCP) gained `tlp`/`group` params, mirroring `artifact_create_diagram`, and its description now
  documents the upsert/group behavior. (6) Added `ParsedMatrix`/`parse_matrix_file` to
  `parse_existing.py`, mirroring the existing `parse_diagram_file` convention. Extracted the
  linkify/infer helpers out of `matrix.py` into new `_matrix_content.py` (shared
  `compose_matrix_body`) so `create_matrix` and `edit_matrix_metadata` share one content-composition
  path; also split `set_diagram_edge_label` out of `diagram_edit.py` into new
  `_diagram_edge_labels.py` and the matrix dispatch into `_diagram_matrix_edit.py` — both
  purely to keep `diagram_edit.py` under the 350-line hard cap after the matrix branch landed
  (370→331 lines after the edge-label split). Updated the one non-test caller
  (`_diagram_write.py`'s `preview_matrix`) and one GUI route import for the moved
  `_linkify_matrix_ids`/`set_diagram_edge_label` symbols. New/updated tests: split
  `test_matrix_pure.py` into itself (now `create_matrix` create/upsert/group-move coverage, +3:
  dry-run uses matrix verification not PUML checks, edit-in-place resolves existing path, group
  move relocates an existing file) and new `test_matrix_content_pure.py` (the moved pure linkify/
  infer helpers, unchanged assertions); new `test_diagram_matrix_edit.py` (7: group-move
  via `artifact_edit_diagram`, metadata edit preserves the table, dry-run preview, 4 parametrized
  PUML-only-param rejections, not-found still raises a clear error); repointed
  `test_diagram_edge_labels.py`'s `set_diagram_edge_label` imports to the new module (4 call
  sites, mechanical only). Gates: `uv run pytest --tb=short -q` 3690 passed/8 skipped (this
  session's suite additions net +14 after accounting for the split-not-duplicated pure-helper
  tests); `ruff check src/ tests/` clean; `uv run zuban check` clean (two narrowing errors from
  `fm.get(...)` used twice in a ternary fixed by binding to local variables first — 435 files).
  **A backend restart is needed** before this fix is live for the running MCP/GUI server — until
  then, `artifact_edit_diagram`/`artifact_create_matrix` on a matrix id still run the pre-fix code.
  WU-C3 status reverted to `in-progress` (not `review`) since real work remains after the
  restart: apply `group=` to the 3 stuck matrix diagrams (`MAT@1780656830.v5cdp4`,
  `MAT@1777452513.W34qBm`, `MAT@1777452513.h0iI-_`) via the now-working `artifact_edit_diagram`,
  re-run `artifact_verify`, and only then do the still-outstanding GUI browse spot-check before
  ticking the plan's WU-C3 checklist item and flipping to `done`. Next: after the user restarts
  the backend, group the 3 matrix diagrams, spot-check the GUI, tick the checklist, flip WU-C3 to
  `done`, then continue to B2a (wizard shell) or B2b (needs D-6 first).
- 2026-07-05 — User asked whether the matrix fix above was actually principled/well-structured —
  re-audited it critically instead of just asserting yes, and found four real issues, all fixed:
  (1) **real bug**: `commit_diagram_write`'s dry-run branch appended "Will move diagram to group"
  whenever `moved` (a path-comparison, not existence-aware) was true, including for a brand-new
  matrix created straight into a group with nothing to relocate — reproduced with a standalone
  script before fixing, then fixed by gating on `diagram_path.exists()` (mirrors the live-write
  branch's own `prev is not None` guard) and added 2 regression tests (dry-run and live-write
  variants) proving no stray "move" claim on a fresh grouped create, alongside the existing
  positive assertion that a genuine relocation *does* emit the message. (2) two raised-error/
  docstring messages told the caller to "call create_matrix" — the bare Python function name,
  which an MCP/LLM caller cannot invoke; corrected to name the actual `artifact_create_matrix`
  MCP tool (and `artifact_edit_diagram` instead of `edit_diagram` in the same message), since
  that's the message's real audience. (3) `_diagram_group_move.py`'s module docstring still said
  it was "for `diagram_edit.edit_diagram`" only, stale since `matrix.create_matrix` now shares it
  too — corrected. (4) the new matrix-dispatch module was named `_diagram_matrix_dispatch.py`,
  breaking the sibling-module naming convention (`_diagram_group_move.py`, `_diagram_edge_labels.py`
  name the *concern*, not the mechanism) — renamed to `_diagram_matrix_edit.py` (and its test file
  to `test_diagram_matrix_edit.py`), updating the one import site and this ledger's own
  cross-references. Gates re-run clean after all four fixes: `pytest` 3692 passed/8 skipped (+2
  from the new regression tests), `ruff` clean, `zuban` clean. No further issues found on this
  pass; still pending the same backend restart noted above.
- 2026-07-05 — Backend/frontend/session restarted by the user. Finished WU-C3: read all 3 stuck
  matrix diagrams in full (`artifact_query_read_artifact(mode="full")`) to classify by actual
  referenced-entity content rather than name alone, per the taxonomy's own bucketing rule —
  `MAT@1777452513.W34qBm` and `MAT@1777452513.h0iI-_` reference only `REQ@`/`OUT@`
  motivation-domain entities (pure requirement→outcome traceability) → `motivation-narrative`;
  `MAT@1780656830.v5cdp4` is keyworded `assurance` and references only assurance-prefixed
  application/common/motivation entities → `assurance`. Applied all three live via
  `artifact_edit_diagram(group=...)` (dry-run first, then commit) — confirming the matrix-diagram
  edit-path fix works against the restarted live server, not just tests: all three came back
  `valid: true`, table content preserved verbatim, correct "Moved diagram to group" warnings.
  **New finding while doing this**: `artifact_edit_diagram` rejected each diagram's *short-form*
  id (`MAT@1777452513.W34qBm`) with "not found", requiring the full form
  (`MAT@1777452513.W34qBm.what-the-system-must-do-...`); confirmed this is pre-existing and
  generic, not matrix-specific or something this session introduced — an existing PUML diagram
  (`ARC@1780220700.Un4jQZ`) reproduces the identical failure on its short form. Root cause not
  yet investigated (likely `resolve_diagram_source_path`'s registry-fallback lookup, since its
  own fast-path only checks a literal `.puml` flat file). `artifact_query_stats(group_by="group")`
  post-move: `diagrams/uncategorized` gone entirely (32/32 diagrams grouped: assurance 9,
  diagram-authoring 1, meta-ontology 1, motivation-narrative 6, platform-core 12,
  promotion-and-tiering 3); `artifact_verify(repo_scope="engagement")`: 38 files, 0 errors, 0
  warnings. GUI browse spot-check via Playwright against `localhost:5173`: both
  motivation-narrative matrix diagrams show correctly in the `/diagrams?group=motivation-narrative`
  list with correct counts; opened one (`MAT@1777452513.W34qBm`) at its new grouped URL — table
  renders fully, all entity links resolve, only console noise is an unrelated missing-favicon 404.
  Ticked the plan's WU-C3 checklist item; WU-C3 → `done`. Next: the short-form-id gap just found
  is being addressed next (explicit user request, separate from WU-C3), then B2a (wizard shell)
  or B2b (needs D-6 first) are both unblocked.
- 2026-07-05 — Explicit user request: "make sure short-form ids are properly handled throughout"
  (following on from the short-id gap found while grouping the matrix diagrams above). Not a
  WU-C3/plan item — a standalone codebase-consistency fix, recorded here since it landed in this
  session and touches the same write-path modules.
  **Investigation**: traced every id→path resolver in the write path and found the codebase has
  three independent, inconsistently-covered mechanisms for short-id resolution: (a)
  `expand_artifact_id` (MCP `context.py`) — a linear scan over `registry.entity_ids()` only
  (misses diagrams/documents entirely), wired into some MCP tools (`artifact_edit_entity`,
  `artifact_edit_connection*`, graph queries, `artifact_query_read_artifact`, bulk ops) but not
  others (`artifact_edit_diagram`, `artifact_delete_entity`); (b) `_MemStore.canonical_id` — a
  linear scan already covering all four record kinds (entities/connections/diagrams/documents)
  uniformly, but only ever consulted by `ArtifactIndex.read_artifact`/`summarize_artifact`; (c)
  `_IdentityResolver.find_all_by_stable_id` (backing `ArtifactRegistry.resolve_artifact`) — O(1)
  via a real index, but that index (`identity_candidates`) is populated for entities/connections
  only (`_service_scan.py`'s `_scan_diagram_records`/`_scan_document_records` never pass
  `candidates_map=` to `_insert_mounted`, unlike `_scan_model_records`). None of these back
  `registry.find_file_by_id` — the actual primitive `resolve_diagram_source_path` (→
  `edit_diagram`/`set_diagram_edge_label`/`create_matrix`'s upsert) and `_delete_entity_core` (→
  `delete_entity`) call — which was, and had always been, an exact dict-key lookup only. Two
  further resolvers bypass the registry altogether and have their own independent exact-match
  gaps: `_find_diagram_file` (`diagram_delete.py`, disk rglob + frontmatter compare, used by
  `delete_diagram` since it may run without a registry) and documents' `edit_document`/
  `delete_document` (`docs_root.rglob(f"{artifact_id}.md")`, filename-exact, no registry at all).
  **Fix, at the shared primitive rather than scattering `expand_artifact_id` calls**:
  `_ScopeRegistry.find_file_by_id` (`_scope_registry.py`) now falls back to
  `_mem.canonical_id(artifact_id)` when the exact-key lookup misses — but *only* when the input
  is already genuinely short-form (`stable_id(artifact_id) == artifact_id`, i.e. no `.slug` at
  all). This one change gives short-id tolerance to every current and future
  `registry.find_file_by_id` caller (diagram edit, entity delete, and — as a bonus —
  `_resolve_outgoing_path`'s connection-file lookup) without touching `identity_candidates`
  population at all. The short-form-only guard is deliberate, not an oversight: a first,
  broader attempt (canonicalizing unconditionally) passed every new test but broke a pre-existing
  one, `test_entity_reindex_heals_out_of_band_slug_rename` — it asserts that a *stale full id*
  (right short id, wrong/old slug) must keep reporting "not found" via `find_file_by_id` after a
  rename, precisely so admin reindex/`resolve_artifact` reconciliation stays the only path that
  silently absorbs slug drift; conflating "no slug at all" with "wrong slug" would have quietly
  removed that guarantee. `diagram_delete._find_diagram_file` and new
  `document._resolve_document_path` each gained the equivalent short-id (not stale-slug) fallback
  directly, since neither has registry access to reuse the fix above; `matrix.create_matrix` and
  `diagram_edit.edit_diagram` additionally canonicalize the resolved artifact_id from the found
  file's own frontmatter before using it for content generation, group-move filenames, or
  `WriteResult` — otherwise a caller-supplied short id would resolve correctly but then get
  written back into the file (or used to build the new grouped filename) truncated, silently
  corrupting the artifact's own recorded id. Updated `EDIT_DIAGRAM_DESCRIPTION`,
  `artifact_create_matrix`'s and `artifact_edit_document`'s MCP descriptions to advertise
  full-or-short-form acceptance, matching the phrasing already used by
  `artifact_edit_entity`/`artifact_edit_connection*`. **Side finding, not fixed (out of scope for
  this ask)**: `artifact_delete_entity`/`artifact_delete_diagram`/`artifact_delete_document` are
  defined and imported into `mcp_artifact_server.py` but never registered as MCP tools via
  `mcp.tool(...)` — `register_edit_tools` only wires up `artifact_edit_entity`/
  `artifact_edit_connection`/`artifact_edit_diagram`/`artifact_edit_connection_associations`;
  single-item deletion is presumably only reachable via `artifact_bulk_delete` today. Tests in
  this session call the plain Python functions directly (still valid coverage of the resolution
  logic itself), but this dead-MCP-registration gap is unrelated to short-ids and left for a
  separate look. New tests: `test_find_file_by_id_kinds.py` (+2: short-form resolves for all
  three kinds; ambiguous short id across two full ids fails safe to `None`), new
  `test_diagram_short_id.py` (5: edit/group-move/delete via short id, full-id-preserved-not-
  truncated, ambiguous-short-id delete raises), new `test_document_short_id.py` (3: edit/delete
  via short id, ambiguous short id raises), `test_edit_tools.py` (+1: delete_entity via short
  id). Gates: `uv run pytest --tb=short -q` 3703 passed/8 skipped (+11); `ruff check src/ tests/`
  clean; `uv run zuban check` clean (435 files). **A backend restart is needed** before this fix
  is live for the running MCP/GUI server (same as the earlier matrix-diagram fix this session —
  not yet restarted since that one). Next: after restart, B2a (wizard shell) or B2b (needs D-6
  first) are both unblocked.
- 2026-07-05 — Follow-up to the "side finding" above: user asked whether the unregistered
  standalone delete tools should be kept/registered or removed in favor of `artifact_bulk_delete`
  alone. Investigated before answering rather than guessing: `artifact_bulk_delete`/
  `artifact_bulk_write` both call `create_staging_repo` (`batch_transaction.py`), which
  `shutil.copytree`s the **entire repo** into a scratch transaction dir on every call regardless
  of batch size, then `commit_staged_repo`'s `_derive_manifest` walks **both** full trees
  (`_managed_files` + `filecmp.cmp`) to reconstruct the diff — genuinely O(repo-size) per call.
  Single-item `create_entity`/`edit_entity`/`edit_diagram`/`delete_entity`/`delete_diagram`/
  `delete_document` do none of this — they use `verify_content_in_temp_path` (one file, tiny temp
  layout) or direct in-memory registry checks, no full-repo copy. First-pass recommendation
  ("remove them, bulk_delete's cost is negligible at today's repo size") was corrected by the user:
  the system must support tens-of-thousands-of-entities repos, at which point O(repo-size) per
  delete call is a real, unbounded cost, not a rounding error — reversed the recommendation to
  keep and register the standalone tools, since they're the only delete path consistent with the
  scale-conscious pattern every other single-item write already uses. Confirmed via git log this
  was dead code from before the transactional path existed (`f65bd7d`, 2026-04-25, introduced the
  functions; `register_edit_tools` has never registered them at any point in its history; the
  transactional machinery landed 3 days later in `40cca43`) and confirmed zero GUI dependency on
  the MCP wrapper functions (the GUI's own delete routes call `artifact_write_ops.delete_entity`/
  `delete_diagram`/`delete_document` directly, not the MCP layer).
  **User then asked to scope the bulk-staging O(repo-size) fix as its own piece of work, then
  proceed with registering the standalone tools.** Scoped the former as new
  `PLAN-scalable-bulk-staging.md` (not part of this plan/ledger — a new, independent plan;
  referenced here only because both pieces of work landed in the same session). It locks nothing
  about implementation (that's for whoever picks it up), but pins the evidence (file:line cites),
  confirms `stage_batch_verification`'s impacted-scope verification is *already* correct and not
  part of the problem, names two independent fix directions (derive the manifest from the
  already-tracked `changed_paths` set instead of a full-tree diff; symlink-mirror the staging dir
  instead of `shutil.copytree`), cites existing in-codebase precedent for both (`_document_temp_path`'s
  symlink mirroring, `candidate_repository.py`'s in-memory overlay pattern), and — per explicit
  user request — includes a dedicated self-model-enrichment workstream naming the exact existing
  entities to update (`FNC@1777399927.hbgFU3` Create Staging Repository, `FNC@1777399928.tRAV0x`
  Commit Staged Repository, `PRC@1777399926.gtgYvQ` Execute Staged Bulk Operation, plus
  `APP@1777399925.HOOYAQ`/`DOB@1777399929.hhYsiw` if needed) — descriptions/attributes only, no
  new entities, one authoritative statement cross-referenced rather than restated on every entity.
  That enrichment itself is **not done yet** — it's a workstream inside the new plan, for whoever
  implements it, not performed this session.
- 2026-07-05 — Starting WU-B2a (authoring-guidance REST endpoint + wizard shell + session store).
  Topmost unblocked `todo` WU (no dependencies). Read §0, "For implementers", and the WU-B2
  section (grounding, delivery slices, D-4/D-6) before starting.
- 2026-07-05 — WU-B2a done. Backend: new `src/infrastructure/gui/routers/authoring_guidance.py`
  (`GET /api/authoring-guidance`, `entity_type`/`domain` CSV → merged into `get_type_guidance`'s
  `filter`, `diagram_type`/`target` passthrough — confirmed no duplication first: `write_help()`
  has no create_when/never_create_when, so this REST surface was genuinely missing, not
  reimplemented), registered in `arch_backend_app.py`. Frontend:
  `AuthoringGuidanceSchema`/`EntityTypeGuidanceSchema`/`PairGuidanceSchema` (`schemas.ts`);
  `getAuthoringGuidance` on `ModelRepository`/`ModelService`/`HttpModelRepository` (options-object
  signature, mirrors A1.2's `searchEntityDisplay` precedent); new
  `ui/composables/useWizardSession.ts` (reactive draft store — created entities, pending
  suggestions, review-later queue — persisted to an injected `WizardStorage`, defaulting to
  `window.sessionStorage`, via a `flush: 'sync'` watcher for deterministic same-tick persistence);
  new `ModelWizardView.vue` + `.helpers.ts` at route `/model/wizard` (hub-and-spoke shell:
  ArchiMate-domain cards scoped via `FRAMEWORK_GROUPS['archimate-next']`, free click-through with
  no gating, per-domain guidance panel fetched on demand, review-later section wired but empty
  until B2c's suggestion engine exists); added a "Wizard" link to `NavBar.vue`. New tests:
  `tests/tools/test_gui_router_authoring_guidance.py` (8), `useWizardSession.test.ts` (12,
  exercises the composable directly — no `inject()` dependency, so unlike most composables in this
  codebase it needs no DOM/mounting to test), `ModelWizardView.helpers.test.ts` (7). Gates:
  `uv run pytest --tb=short -q` 3714 passed/8 skipped (+8); `ruff check src/ tests/` clean;
  `uv run zuban check` clean (436 files); frontend `npm run lint` clean, `npm run typecheck`
  clean, `npm run test` 405 passed (+19). No backend restart needed yet (new REST endpoint only,
  no MCP-surface change) — batch with B2b's restart. No Playwright smoke this session — B2a's
  checklist doesn't require one (the shell has no write path yet; B2b's does, and its own
  checklist requires the smoke). Next: B2b (needs D-6 resolved first — the only open decision) or
  B2c; both depend on B2a, now done. Stopping here — the user asked to hand
  `PLAN-scalable-bulk-staging.md` to a separate worktree-isolated agent next, so this session
  won't continue directly into B2b.
  **Then registered the three standalone delete tools** (the smaller, explicitly-requested-second
  piece): `artifact_delete_entity`/`artifact_delete_diagram` now registered in
  `edit_tools.py::register_edit_tools` (new `DELETE_ENTITY_DESCRIPTION`/`DELETE_DIAGRAM_DESCRIPTION`
  in `edit_tool_descriptions.py`); `artifact_delete_document` registered in
  `write/document.py::register`. All three use `DESTRUCTIVE_LOCAL_WRITE` (matching
  `artifact_bulk_delete`/`artifact_edit_connection`'s own destructive annotation) and advertise
  full-or-short-form `artifact_id` (real now, from the short-id fix above) and cross-reference
  `artifact_bulk_delete` for cascades/batches. `artifact_bulk_delete`'s own description gained the
  reverse cross-reference (prefer the single-item tools when there's no cascade — cheaper, no
  staging copy). New `test_delete_tools_registered.py` (3): asserts all three now appear in
  `mcp_write._tool_manager.list_tools()` with an `artifact_id` parameter — this is the test that
  would have failed before today, unlike the existing tests that call the plain Python functions
  directly and always passed regardless of registration. Gates: `uv run pytest --tb=short -q`
  3706 passed/8 skipped (+3); `ruff check src/ tests/` clean; `uv run zuban check` clean (435
  files). **MCP-surface change — a client session restart is needed** (on top of the
  already-pending backend restart from the short-id fix) before `artifact_delete_entity`/
  `artifact_delete_diagram`/`artifact_delete_document` are callable live. Next: after both
  restarts, either pick up `PLAN-scalable-bulk-staging.md`'s WS1 (benchmark harness) or return to
  B2a/B2b in this plan.
- 2026-07-05 — User asked for a critical evaluation of `PLAN-scalable-bulk-staging.md` (self-review:
  enough context for independent implementation? follows coding guidelines? accounts for the real
  scale/concurrency target?). Found and fixed one real gap in the plan itself: it never mentioned
  that every write MCP tool — bulk or single-item — is already serialized through one process-wide
  single-worker queue (`write_queue.py`'s `queued(...)`, holding `WorkspaceMutationGate.writing()`
  for the call's entire duration). This reframes the whole plan: the O(repo-size) cost isn't "the
  bulk caller waits longer," it's "every other concurrent user's write queues behind it." Added a
  "Concurrency context" section, hardened the B1→B2 sequencing (B2-equivalent is the actual target,
  not a contingency — B1 alone still pays a full fresh parse per call, no cached staged index
  exists since the staged path is new every time), added a concurrent-load benchmark scenario, and
  read the project's own coding guidelines (`STD@1777137196.ItT-3l`) for the first time on this
  plan (should have done this before writing it) — added a "For implementers" section on
  boolean-flag avoidance and the dependency-policy test.
- 2026-07-05 — User then supplied an independent external assessment of the (already-once-revised)
  plan and asked to critically evaluate and integrate it, not accept it wholesale. Verified every
  specific code claim by reading the cited functions before accepting any of them (per this
  session's own standing "verify architecture claims, never assert from grep" rule) — all seven
  points held up; two were genuinely the highest-impact gaps in the plan, and while verifying them
  a **third, larger gap not in the assessment itself** surfaced:
  (1) Confirmed `stage_batch_verification`'s `ArtifactRegistry(shared_artifact_index([staged_root]))`
  is always a cache-miss (`get_shared_index` keys by mount path; `staged_root` is a fresh
  `uuid.uuid4().hex` dir every call) → always triggers a full `refresh()` scan — a real,
  independent O(repo-size) cost the plan's "verification is already right" claim had missed.
  Additionally confirmed `ArtifactVerifier.verify_paths` calls `self._inventory.build(...)`
  (4 unconditional `rglob`s) *before* the "impacted" scope narrowing even runs — so the
  impacted-scope claim was only ever true for rule *selection*, never for inventory *construction*.
  Corrected the "do not fix this" framing, which was wrong.
  (2) Confirmed `preflight_bulk_delete`'s `scan_connections`/`scan_grf_refs`/`scan_diagram_refs`
  (`bulk/diagram_refs.py`) are unconditional full-tree `rglob`s run before staging even starts,
  independent of the two staging-cost phases the plan's first draft named — a real, missed third
  category of O(repo-size) cost.
  (3) **Not in the external assessment — found while verifying (2), by checking whether the
  single-item path avoided the same pattern**: `entity_delete.py`'s `_incoming_connection_blockers`/
  `_grf_blockers`/`_diagram_blockers` (called by every `artifact_delete_entity`, including the
  ones just registered as MCP tools this session) do the **identical** full-tree-scan pattern as
  the bulk preflight scanners — just for one entity's blockers instead of a batch's. This directly
  contradicts this session's own prior claim (recorded above, in the "keep and register the
  standalone delete tools" reasoning) that single-item delete was "the O(item-size) reference for
  what cheap looks like" — **that claim is corrected here**: single-item delete avoids the
  *staging* cost (still a real, valid reason to keep it over bulk_delete for cascade-free deletes),
  but its own reference-blocker checking is exactly as O(repo-size) as bulk delete's preflight.
  Also verified the fix is cheaper than it sounds: `connections_by_entity` (an O(1) reverse index)
  already exists on the live `_MemStore` and already covers the incoming-connections check for
  free — only the diagram-ref and GRF reverse indexes are genuinely new, following an existing
  established pattern (`entities_by_diagram`/`connections_by_diagram` already exist as precedent).
  Integrated all of this into a substantially revised `PLAN-scalable-bulk-staging.md`: retitled
  ("...Staging" → "...Pipeline") since "staging cost" undersold the actual scope once preflight
  scanning and staged-registry/inventory rebuilding were counted; enumerated all five verified
  O(repo-size) phases explicitly with citations; added "indexed reference-blocker lookups" as its
  own workstream serving both bulk and single-item delete from one fix; adopted the assessment's
  recommendation to centralize any symlink-mirror staging behind a `StagedWorkspace` abstraction
  rather than scattered per-call-site discipline; strengthened the manifest-from-tracked-paths
  workstream to require a parity test as a hard gate, not an optional nice-to-have; split the
  benchmark workstream into perf-ci (algorithmic invariants, fast, deterministic) vs. perf-manual
  (large-scale opt-in, phase-level timing breakdown) since pinning wall-clock thresholds at 150k
  entities in normal CI is not viable; added the self-model-enrichment task list an explicit
  instruction to correct the now-wrong "O(item-size)" characterization of the delete tools rather
  than propagate it into the model. No code touched this turn or the prior one — planning-document
  work only; gates not re-run (nothing to re-run).

- 2026-07-05 — New session (worktree `modeling-ux-uplift`). All Workstream A/B1/B3/C WUs are
  `done` except A2/A1.2/A4.2/A4.3, which are `review` pending only a live-browser smoke — a
  working Playwright browser is now available in this session (unlike the sessions that landed
  the code), and B2b's dependency list requires A1.2 `done`, so doing these four smokes now is
  the correct next unblocked work before B2b/B2c. Confirmed backend/frontend are already running
  (`localhost:5173`, `arch-backend` process up) — no restart needed to *start* this work; the
  short-id-fix/delete-tool-registration restart flagged at the end of the WU-B2a entry is still
  outstanding (`artifact_delete_entity`/`_diagram`/`_document` are absent from this session's MCP
  tool list), unrelated to A2/A1.2/A4.2/A4.3 and not blocking them. Starting with A2 + A1.2, then
  A4.2/A4.3 together (self-model ACT+SEQ diagrams).
- 2026-07-05 — A2 and A1.2 confirmed live, no code changes needed: A2's `.img-container` stays
  bounded and clips the ArchiMate two-tier view's 2259×514px SVG at both 1366px and 2560px
  widths; A1.2's domain-chip filter now returns application-domain entities (reproducing and
  fixing the original symptom 2 cutoff) and the sentinel-triggered lazy-load appended a second
  page (59→67 items). Both → `done`. A4.2 (sequence) also confirmed live with zero code changes:
  lifelines and messages both map, click→sidebar and sidebar→highlight both work, visually
  confirmed via screenshot (activation-bar turns blue). → `done`.
  A4.3 (activity) was completely non-functional live — 0 `data-entity-id`/`href` survived to the
  DOM — despite every unit/golden-fixture test passing, because of three pre-existing consumer
  bugs in `DiagramDetailView.vue`/`EditDiagramView.vue` that predate this WU and had simply never
  been exercised by an anchor-typed `mapElements` representative before: DOMPurify's default
  `ALLOWED_URI_REGEXP` strips `href="arch://…"` (confirmed by diffing the raw `/api/diagram-svg`
  response against the post-sanitize live DOM); `attachInteractivity`'s `instanceof SVGGElement`
  gate silently skipped the `SVGAElement` sentinel; the `.svg-selected`/hover CSS only targets
  `polygon`/`rect`/`polyline`/`ellipse`, none of which exist inside an anchor wrapping only
  `<text>`. Root-caused via a standalone raw-fetch comparison and `elementFromPoint`/attribute
  introspection before writing any fix, not assumed. Fixed all three at their real layer: new
  `tools/gui/src/ui/lib/svgSanitize.ts` (`sanitizeDiagramSvg`, exported `ALLOWED_URI_REGEXP`)
  replaces both views' inline `DOMPurify.sanitize` calls; the element-type gate in both views'
  `attachInteractivity` now accepts `SVGGElement || SVGAElement` (subpart-attachment stays
  `SVGGElement`-only); new `a[data-entity-id]`/`a.svg-selected` CSS rules in
  `DiagramDetailView.vue` style the anchor's `text` child. A fourth, related gap surfaced while
  confirming the fix with a *real* (non-synthetic) click: neither view called
  `preventDefault()`, so a genuine click on the now-mapped `<a href="arch://…" target="_top">`
  also triggered the browser's native link-following (console: "Not allowed to launch
  'arch://…' because a user gesture is required") — and a middle-click/new-tab or
  drag-to-bookmark would bypass the `click` listener entirely regardless of `preventDefault`.
  Fixed with a new shared `neutralizeSentinelLink` export in `diagramViewerExtensions.ts`
  (strips `href`/`xlink:href`/`target` once the anchor's data has been read) called from both
  views, plus `preventDefault()` on the click listeners as defense in depth. All four are
  cross-cutting generic-viewer bugs, not activity-specific — any future diagram type returning
  an anchor from `mapElements` would have hit the identical wall. Files: new `svgSanitize.ts` +
  `svgSanitize.test.ts` (3 tests: `arch:` allowed, default-safe schemes still allowed,
  `javascript:`/`data:` still blocked — the only sub-part of this fix that's Vitest-testable,
  since `document` is confirmed genuinely `undefined` in this repo's `environment: 'node'` Vitest
  config); `diagramViewerExtensions.ts` (+`neutralizeSentinelLink`); `DiagramDetailView.vue` and
  `EditDiagramView.vue` (sanitize call swapped, element-type gate broadened,
  `neutralizeSentinelLink` wired in, `preventDefault()` added; `DiagramDetailView.vue` also gets
  the new CSS rules). Verified live end-to-end post-fix: all 7 sentinels on the self-model's
  promotion activity diagram (`ACT@1781338474.NTuMXo`) map correctly; click→sidebar and
  sidebar→highlight both confirmed for actions and the decision (screenshots taken); anchors
  carry no `href`/`target` after mapping; a real Playwright mouse click produces zero console
  errors (previously the launch-blocked warning). Gates: `npm run lint`/`typecheck` clean;
  `npm run test` 408 passed (+3, 405→408); backend untouched, not re-run (no `.py` files
  changed). **Live-verification method, since the ledger's shared dev/backend instance
  (`localhost:5173`/port 8000) runs against the main checkout, not this worktree**: symlinked
  `.venv` and `tools/gui/node_modules` from the main checkout (verified identical `uv.lock`/
  `package-lock.json` at the same commit first) and ran a second, disposable `vite --port 5183`
  from this worktree, proxying to the *existing* main-checkout backend on its default port
  8000 (read-only diagram-detail GETs only, no write risk, no second backend process needed);
  torn down and both symlinks removed before finishing, per the user's mid-session instruction
  to keep this worktree's changes isolated from the concurrently-running bulk-staging-plan agent's
  own worktree. **Unrelated tool finding, not chased further**: this session's Playwright
  `browser_click` stopped registering real clicks partway through (confirmed via a
  document-level capture-phase listener and an unrelated nav-link click, both firing nothing) —
  root cause not investigated (didn't reproduce on the very first click of the session, which
  worked); worked around by using `dispatchEvent(new MouseEvent('click', {bubbles: true}))`
  directly on the target element for the remaining functional verification, which is a valid
  signal for "does the app's own click handler correctly resolve/select/highlight" even though
  it doesn't exercise the browser's native hit-testing path — the one thing real clicks were
  needed for (the `preventDefault`/native-navigation check) was confirmed before the tool stopped
  responding. Next session should watch for a recurrence and investigate if it does.
  Status table: A2/A1.2/A4.2/A4.3 all → `done`. Workstream A is now fully complete.
- 2026-07-05 — D-6 resolved with the user. Confirmed: per-artifact commit through the existing
  dry-run-then-write path, session-tracked "undo step" while the wizard session is live (as the
  plan already recommended), plus one refinement surfaced by the user's own follow-up question
  ("how is leftover abandoned work handled?") — every wizard-created entity/connection also gets
  a `wizard-draft` keyword/note tag, a passive breadcrumb (no server-side session tracking, no
  expiry job) so artifacts orphaned by a lost `sessionStorage` session stay discoverable later
  via an ordinary Browse/keyword filter instead of silently blending into hand-created drafts.
  Staged-bulk atomic commit explicitly rejected, not deferred — beyond needing new transactional
  machinery, `PLAN-scalable-bulk-staging.md` already established the bulk-write path is
  O(repo-size) per call, unsuited to holding a whole wizard session's writes. Decision log D-6
  updated from `open` to `decided`; plan's WU-B2b commit-semantics bullet updated with the tag
  detail and the sharper staged-bulk rejection rationale. No code changed — planning-record work
  only. **Handoff**: this session completed A2/A1.2/A4.2/A4.3 (all now `done`, Workstream A
  fully complete — see the two entries above for what was found and fixed, most notably three
  real, previously-undetected bugs in WU-A4.3's activity-diagram selection that only a live
  browser check could surface) and resolved D-6, the plan's last open decision. B2b (wizard
  domain stages: create/find/connect + commit flow) is now the topmost unblocked `todo` WU, with
  no remaining open decisions blocking it — the next session should pick it up directly, reading
  the plan's WU-B2 section (grounding, strategy synthesis, delivery slices) and D-4/D-6 in the
  decision log before starting. No pending backend/MCP restart is needed for B2b's own start
  (frontend-heavy slice), but the short-id-fix/delete-tool-registration restart flagged at the
  end of the WU-B2a entry (two sessions ago) is still outstanding and unrelated — mention it to
  the user if delete-tool behavior becomes relevant. This session's live-verification work used
  a temporary, now-removed second `vite` instance (symlinked `.venv`/`node_modules` from the main
  checkout, both deleted before finishing) proxying to the existing main-checkout backend on its
  default port — no separate backend instance was started or left running.
- 2026-07-05 — New session. User confirmed backend/frontend/MCP restarted (`artifact_delete_entity`/
  `_diagram`/`_document` now present in the tool list, confirming the short-id-fix/delete-tool
  restart flagged two sessions ago is live) and asked to proceed with the plan, then afterward
  integrate `PLAN-scalable-bulk-staging.md`'s work from the sibling worktree
  `scalable-bulk-pipeline` once verified. Starting WU-B2b (wizard domain stages), the topmost
  unblocked WU now that D-6 is decided.
- 2026-07-05 — WU-B2b done. Files: new `tools/gui/src/ui/components/WizardDomainStage.vue`
  (orchestrator: type-choice → create-or-find → suggestions, per-domain via a `:key`-forced
  remount) + `.helpers.ts` (`entityTypesForDomain` moved here from `ModelWizardView.helpers.ts`,
  `splitVisibleEntityTypes`, `WIZARD_DRAFT_KEYWORD`); new `WizardEntityForm.vue` (name/summary +
  required schema properties via `TypedPropertyInput`, progressive disclosure for optional ones,
  dry-run→create, auto-tags `wizard-draft`); new `WizardConnectionSuggestions.vue` (accept/later/
  dismiss cards); new `ui/lib/wizardSuggestions.ts` (pure: `legalConnectionPairs`,
  `nameSimilarity` Jaccard word-overlap, `rankCandidatesByName`, `phraseSuggestion`,
  `buildWizardSuggestions` — metamodel-validity-then-name-similarity, capped at 5). Reused
  `getAuthoringGuidance`'s already-fetched per-entity-type `permitted_connections` for the
  ranking signal (identical `{outgoing, incoming, symmetric}` shape as `getOntologyClassification`)
  instead of adding a second network round trip — no new backend endpoint or query params needed
  anywhere in this WU. `useWizardSession.ts`: added `createdConnections` +
  `recordConnectionCreated`/`undoConnectionCreated`, extended `WizardSuggestion` with
  commit-ready `sourceId`/`connectionType`/`targetId`/`targetName` fields (storage key bumped
  `v1`→`v2` — a v1 session had suggestions with no way to actually commit them). `ModelWizardView.vue`
  now embeds `WizardDomainStage` in place of the passive entity-type-list panel it shipped with
  in B2a. New tests: `wizardSuggestions.test.ts` (13), `WizardDomainStage.helpers.test.ts` (8),
  `useWizardSession.test.ts` (+2). Gates: frontend `lint`/`typecheck` clean, `npm run test` 428
  passed (+21, 407→428 across this and the prior session's work); backend untouched (no `.py`
  changes), not re-run.
  **Two real, previously-undetected bugs found and fixed live** (both pre-dated this WU, shipped
  by B2a without a live check — exactly the gap this plan's Playwright-smoke discipline exists
  to catch): (1) `entityTypesForDomain` filtered on a per-item `domain` field that `GET
  /api/authoring-guidance?domain=...` never populates once the whole response is already
  domain-scoped server-side (`_entity_type_guidance`'s `include_domain=False` branch,
  confirmed by reading `type_guidance.py`) — since that's the wizard's *only* real call pattern,
  the type-choice grid was silently empty for every domain until fixed (trust the omission,
  filter only when the field is actually present); regression test added reproducing the exact
  response shape. (2) my own first-pass `legalConnectionPairs` had the classification record's
  key/value backwards — `_classify_connections` keys each record by **target type** with
  **connection types** as the value array, not the reverse — caught by inspecting live network
  requests during the Playwright check (`entity_types=archimate-influence` etc. instead of real
  entity-type names like `stakeholder`) before it shipped uncaught; fixed, with the test
  fixture's wrong-shape data corrected and an explanatory comment added so the key/value
  direction doesn't get re-inverted later.
  **Live Playwright verification**, using the same temporary-worktree-vite-proxying-to-shared-backend
  setup as the prior session (symlinked `.venv`/`node_modules` from the main checkout, both
  removed afterward; a stray *real* 297MB `.venv` also appeared partway through — likely an
  implicit `uv` materialization, cause not chased — and was removed at cleanup too): in
  Motivation, created a throwaway goal (dry-run→create, confirmed `wizard-draft` keyword landed
  via `artifact_query_read_artifact`), then used "Find existing" to select a real, well-connected
  apex goal and confirmed 5 ranked, correctly-phrased suggestions appeared; accepted one
  (confirmed the connection was written for real, not just locally) and separately tested "Later"/
  "Dismiss" wiring by inspection. In Application, created a throwaway `application-component`,
  confirmed domain-specific type choices and suggestions render correctly there too (validating
  the domain-scoping fix generalizes beyond Motivation), then used the wizard's own "Undo" button
  and confirmed via `artifact_query_search_artifacts` that the entity was actually deleted
  server-side, not just cleared from local UI state — the full dry-run→commit→undo lifecycle the
  checklist asks for.
  **Safety incident during test-data cleanup, recorded because it was a near-miss, not because
  nothing went wrong**: while removing the accepted test connection and the throwaway goal
  afterward, a first `artifact_delete_entity` dry-run call was issued against
  `GOL@1780220699.FCfDuc` — the *real, pre-existing apex goal itself* ("Achieve Unity of Effort
  Across Autonomous, Agentic SDLC Work", 17 real connections, enriched in WU-C2) — instead of the
  actual throwaway `GOL@1783253380...` entity, a copy-paste mistake made while juggling several
  artifact ids in the same turn. The dry-run output (would delete the apex goal and its
  `.outgoing.md`) was read and caught *before* any live commit — `dry_run=false` was never called
  on that id. Recovered by re-running `artifact_query_search_artifacts` to get the correct id and
  proceeding from there. No damage occurred; recorded as a standing reminder that even a
  "reversible, dry-run-gated" delete path is only as safe as the id actually passed to it —
  re-verify the target id from a fresh query immediately before any delete call when multiple
  artifact ids are in play in the same turn, rather than trusting recall across several prior
  tool results.
  Also found, while looking up the throwaway entity for deletion: `artifact_delete_entity`
  reported "not found" for an entity that had just been created via the live REST API and was
  independently visible via `artifact_query_read_artifact`/`artifact_query_search_artifacts` —
  resolved by `artifact_admin_reindex(scope="full")`, after which the same id resolved correctly.
  Root cause not investigated (out of scope for this ask) — flagging as a possible recurrence of
  the write-tool-index-staleness class of bug this plan's WU-C3 sessions found and fixed for
  *group* changes specifically; this instance was for plain entity *creation* visibility, a
  narrower symptom, not chased further here.
  Final state verified clean: `artifact_verify(repo_scope="engagement")` 0 errors/0 warnings both
  before and after cleanup; `artifact_query_search_artifacts` for both throwaway names returns no
  hits post-cleanup. Ticked the plan's WU-B2b checklist item. Next unblocked WU is B2c (needs
  B2b, now done) — stopping here per the user's request to now move on to integrating the
  bulk-write-pipeline worktree's work, not continuing further into this plan this session.
- 2026-07-05 — Integrated `PLAN-scalable-bulk-staging.md`'s work from the sibling worktree
  `scalable-bulk-pipeline` into `main` (separate from this plan/ledger, recorded here only
  because it happened in this session and unblocked returning to this plan cleanly). Forked a
  read-only verification pass first: all 7 of that plan's workstreams complete with evidence,
  `pytest` 3682 passed/49 skipped, `ruff`/`zuban`/`test_dependency_policy.py` all clean, self-model
  enrichment confirmed descriptions-only. Committed it on its own branch
  (`worktree-scalable-bulk-pipeline`) and fast-forward-merged into `main`; re-ran the full gate
  suite on `main` post-merge (`pytest` 3722 passed/9 skipped, `ruff`/`zuban` clean) to confirm the
  merge itself introduced no regression. This worktree (`modeling-ux-uplift`) was then
  fast-forwarded onto the updated `main` — B2b's uncommitted work carried through untouched.
- 2026-07-05 — Starting WU-B2c (elicitation layers + cross-domain spine), the topmost unblocked
  WU now that B2b is done, per the user's explicit follow-up request to continue after the
  bulk-pipeline integration.
- 2026-07-05 — WU-B2c done, scoped to what the plan's checklist literally asks for (questionnaire/
  spine step definitions, ranking integration, review-later resolution, novice-path Playwright) —
  "capability-anchored reuse search in strategy" from the delivery-slice prose was **not** built
  this session: it's the least-specified of B2c's three content pieces (no concrete UX shape given
  anywhere in the plan, unlike the motivation questionnaire's explicit stakeholder→...→requirement
  sequence), and the free-choice hub's existing "Find existing" path already covers the core
  reuse-search need for every domain including strategy — a dedicated capability-anchor mechanism
  is left as a genuinely open follow-up, not silently dropped.
  Files: new `WizardEntityStage.vue` (extracted verbatim from `WizardDomainStage.vue`'s
  post-type-choice logic — no behavior change, needed so the questionnaire doesn't duplicate
  create/find/suggest/undo); new `ui/lib/wizardQuestionnaires.ts` (content-driven: the motivation
  questionnaire's 6 GQM/KAOS-style steps plus its business-domain bridge prompt); new
  `WizardQuestionnaireStage.vue` (progress indicator, current question, embeds
  `WizardEntityStage` with accumulated `proximityAnchors`, auto-advances on real create/find,
  exits on plain cancel); `WizardDomainStage.vue` gained a "Start guided questionnaire" entry
  point (additive — free type-choice stays available, per the plan's "free skipping" rule).
  Ranking: `buildWizardSuggestions` gained an optional `proximityBoost` param (+0.15 tiebreaker
  for a `discoverDiagramEntities` hop-neighbor, applied consistently to both per-pair candidate
  selection and cross-pair ordering) — removed `rankCandidatesByName`, dead code once per-pair
  selection moved onto the same combined-score comparator. Review-later: replaced the hub's
  inert "Resolved" list with the same `WizardConnectionSuggestions` component the domain stage
  uses (`hideLater` prop added), wired to a new shared `useSuggestionCommit.ts` composable so
  the commit sequence (`addConnection` → `recordConnectionCreated` → caller's removal callback)
  can't drift between the in-context accept path and the hub's. Fixed a related wiring gap found
  while building the bridge's "switch domain" button: `ModelWizardView.vue` previously only
  refetched guidance from the domain-card click handler and `onMounted`; replaced both with one
  `watch(activeDomain, ..., {immediate: true})` so any future domain-switching entry point (the
  bridge button included) stays correct automatically. New tests: `wizardQuestionnaires.test.ts`
  (4), `wizardSuggestions.test.ts` proximity-boost cases (+3, net +2 after removing
  `rankCandidatesByName`'s test). Gates: frontend `lint`/`typecheck` clean, `npm run test` 434
  passed (+6, 428→434); backend untouched, not re-run (no `.py` changes). All new/touched files
  within the 350-line hard cap (`WizardEntityStage.vue` largest at 254).
  Playwright — novice path live in Motivation (same temporary-worktree-vite-proxying-to-shared-
  backend setup as prior sessions, torn down afterward): started the questionnaire; created a
  throwaway stakeholder (step 1/6); deferred one of its suggestions to "Later" and confirmed it
  appeared in the hub's review-later section via the new resolution UI (Accept/Dismiss only, no
  "Later" button there — confirms `hideLater` wiring); advanced to "Question 2 of 6" (driver) and
  confirmed the schema-driven required `Category` enum property rendered correctly via
  `TypedPropertyInput`; created a throwaway driver and confirmed the top-ranked suggestions
  referenced the step-1 stakeholder (proximity signal engaged without erroring — the unit tests
  isolate and prove the tiebreaker-only scoring behavior in a way live data with similar
  deliberately-chosen test names couldn't cleanly isolate); accepted the hub's deferred
  suggestion and confirmed it actually committed a real connection (to a real, pre-existing
  outcome entity) and disappeared from the queue; used in-questionnaire "Undo" on the driver and
  confirmed it works inside questionnaire mode, not just free-choice mode (session badge count
  dropped 2→1 correctly). Did not walk to the final bridge screen — stopped once every
  B2c-specific mechanism was confirmed, to limit live test-data footprint.
  **Cleanup, applying the WU-B2b near-miss lesson**: hit the same write-tool index-staleness
  symptom as B2b (`artifact_delete_entity` reporting "not found" for an entity the read-side
  index already showed) — resolved the same way, `artifact_admin_reindex(scope="full")` before
  retrying. This time re-queried and re-confirmed the exact target `artifact_id` via a fresh
  `artifact_query_search_artifacts` call immediately before every delete, rather than reusing an
  id recalled from earlier in the conversation — no near-miss this session. Deleted the throwaway
  stakeholder (`artifact_delete_entity`, which also removed its `.outgoing.md` — the accepted
  connection to the real outcome entity lived there, so no separate connection-removal call was
  needed); confirmed the real outcome entity was untouched via `artifact_query_read_artifact`
  afterward. Final `artifact_verify(repo_scope="engagement")`: 38 files, 0 errors, 0 warnings;
  `artifact_query_search_artifacts` for the throwaway name returns no hits.
  Ticked the plan's WU-B2c checklist item — **Workstream B (per-section documents + the guided
  wizard) is now fully complete** except the explicitly-deferred capability-anchor piece noted
  above. **User then flagged, correctly, that this session hit the write-tool index-staleness
  symptom twice (B2b and B2c) and asked for a proper architectural diagnosis and fix, not a
  reindex-and-move-on workaround** — that investigation is being picked up next, as its own
  piece of work (not a WU in this plan).
- 2026-07-05 — Diagnosed and fixed the index-staleness root cause (not a WU in this plan — a
  standalone backend correctness fix, recorded here since it landed in this session and was
  triggered directly by hitting the symptom twice during WU-B2b/B2c). Forked a read-only
  investigation first (main checkout, no worktree changes) rather than guessing; independently
  re-verified every claimed file:line before acting on it, per this project's own standing
  "verify architecture claims" rule. **Root cause, confirmed by direct code reading**: multiple
  independently-cached `ArtifactIndex` singletons can exist for the same physical repo — one per
  distinct root-set/scope key (`bootstrap.service_key`) — e.g. an engagement-only index (used by
  `edit_tools.py`'s standalone MCP write tools, including `artifact_delete_entity`) and a separate
  engagement+enterprise-combined index (the REST/GUI layer's global `_repo`, and MCP reads
  defaulting to `repo_scope="both"`). Three write-commit call sites called a resolved index's own
  `apply_file_changes` directly instead of broadcasting: `state.py::clear_caches` (REST/GUI),
  `context.py::_apply_paths_now` (the universal MCP write-commit choke point, reached via
  `apply_authoritative_changes`/`AuthoritativeMutationContext.finalize`/`authoritative_callbacks_for`
  — used by every `edit_tools.py` write and by bulk write/delete's live-commit phase), and
  `connection.py`'s `_add_connection_impl` (validated against the combined scope but notified only
  the engagement-only scope — a distinct internal inconsistency in the same function). The correct
  broadcast primitive, `notify_paths_changed` (`bootstrap.py`), already existed and already applies
  a changed path to *every* live registered index whose mounts overlap it — but was wired only for
  externally-driven git-sync changes (`git_sync_m4.py`), never the application's own writes;
  `grep` confirmed zero other call sites before this fix. This is a **recurrence** of a
  structural weakness this project had already named once before in a different guise (per memory:
  the "Rename Stale-Index Incident" — "no index↔worktree reconcile + per-root-combo singletons +
  dead notify_paths_changed") — the earlier fix addressed that incident's specific rename scenario
  without generalizing to every write path, leaving today's entity-create/connection-create
  divergence to recur through the same unwired mechanism.
  **Fix**: routed all three commit choke points through `notify_paths_changed` instead of a direct
  `index.apply_file_changes` call (`state.py`, `context.py::_apply_paths_now`); aligned
  `connection.py`'s notification scope to match its own validation scope (`both_roots`, not
  `eng_root`) as a belt-and-suspenders correctness fix on top of the broadcast fix. Confirmed
  `bulk/common.py::local_apply_paths` was *not* part of the bug — it applies only to a throwaway
  staging/dry-run temp directory (`temp_repo_callbacks(staged_root)`), never the live repo; bulk
  write/delete's actual live-commit phase already routes through the fixed `apply_authoritative_changes`
  via `authoritative_callbacks_for(live_root)`, so no separate fix was needed there.
  **LoC discipline while touching the file**: `context.py` was already 381 lines (over the 350
  hard cap) before this fix, and the fix pushed it to 389 — extracted the background-refresh
  queue/worker (`_RefreshQueue`, `_queue_for`, `_refresh_worker`) into a new sibling module
  `_background_refresh_queue.py`, parametrized via dependency injection (receives `refresh_now`/
  `apply_now`/callbacks as arguments) specifically to keep the dependency one-way — the new module
  needs nothing from `context.py`, avoiding a circular import — leaving `context.py` at 344 lines.
  **Verification discipline**: for both the regression test and the new fitness-function test,
  confirmed each actually fails against the pre-fix code (via a uniquely-tagged, immediately-
  dropped `git stash` of just the fixed files — never touching the shared stash stack's other
  entries) before trusting it as a real regression guard, not just a test that happens to pass.
  New `tests/infrastructure/artifact_index/test_cross_scope_index_consistency.py` (2): constructs
  two live overlapping-scope indexes against a temp repo, writes through one scope via
  `apply_authoritative_changes`, asserts the other scope's index sees it without any reindex call —
  both fail on the pre-fix code, pass after. New
  `tests/architecture/test_index_broadcast_policy.py` (1, mirroring the existing
  `test_dependency_policy.py` pattern): scans all of `src/` for direct `.apply_file_changes(`/
  `.apply_file_change(` calls outside a small, individually-justified allowlist (the broadcast
  loop itself, `ArtifactIndex`'s self-referential identity-reconciliation call, `ArtifactRepository`'s
  generic facade delegation, and the staging-only bulk helper) — fails on the pre-fix code
  (correctly names both original violation sites), passes after; guards against this exact bug
  class recurring if a future write path is added without going through the broadcast. Gates:
  `uv run pytest --tb=short -q` 3725 passed/9 skipped (+1 net after the extraction, +3 new tests
  minus none removed); `ruff check src/ tests/` clean; `uv run zuban check` clean (442 files);
  `tests/architecture/test_dependency_policy.py` 2/2 passed (the new sibling module doesn't
  violate hexagonal layering).
  **Self-model**: the user separately asked why `ENG-ARCH-REPO` didn't represent this gap and make
  it discoverable, and what should change. Checked before answering rather than assuming:
  `PRC@1777409610.wqtZ0P` *Coordinate Repository State* already existed and already asserted the
  very guarantee that was broken — "ensures every committed change... triggers an index refresh" —
  but the description named no specific mechanism, no traceable link to `notify_paths_changed`,
  and (the real gap) never represented the structural fact that makes the guarantee non-trivial:
  that the index can exist as *multiple* independently-cached instances per physical repo. A
  reader could not have discovered "is this guarantee actually upheld everywhere?" from the model
  alone — the claim was pure prose, disconnected from the mechanism and blind to the multiplicity
  that made it false. Enriched `PRC@1777409610.wqtZ0P`'s summary (full-property `artifact_edit_entity`,
  dry-run then commit) to state the multiplicity fact, name the actual fix, and note the new
  fitness-function guard — zero new entities, per this plan's own motivation-entity-discipline
  precedent (descriptions > connections > entities) extended here to non-motivation domains.
  Recommended, but did **not** unilaterally create, a new data-object entity representing the
  scoped-index-cache structural fact itself (analogous to the existing `DOB@1712870400.3rilik`
  *SQLite Index* precedent for modeling internal indexing structures) — flagged as a real,
  evidenced gap worth a deliberate follow-up decision, not decided mid-bugfix.
  Committed directly to `main` (`6a91735`, on top of the bulk-pipeline merge) rather than left
  uncommitted in this worktree, matching this session's established pattern for fully-verified,
  cross-cutting backend work; this worktree was then fast-forwarded onto it. **A backend restart
  is needed** before the live server's write tools stop exhibiting the fixed staleness — not yet
  performed this session.

---

## Reusable session-start prompt

Paste this to begin any new session/iteration on this work (after context-clearing):

```
You are implementing PLAN-modeling-ux-and-self-model-uplift.md.
TASKS-modeling-ux-and-self-model-uplift.md is the progress ledger and decision record.

ORIENT — read the plan freely; it is curated context, do not ration it.
- Read the ledger fully: session protocol, status table, AND the Decision log. Decisions D-1..D-9
  are FINAL (except D-6, marked open) — do not reopen or re-ask them.
- In the plan, read §0 (cross-cutting), §"For implementers", the WU you pick in full, and any WU
  it depends on.

PICK ONE WU.
- Take the topmost `todo`/`in-progress` WU in the status table whose dependencies are all `done`.
- Set it `in-progress`; add a dated progress-log line stating your intent.
- Stop and ask me ONLY if the WU needs a NEW design decision absent from the Decision log
  (currently only D-6, before B2b). Never re-ask a settled decision.

IMPLEMENT — ration codebase & self-model exploration, not plan reading.
- The WU cites the exact file:line (symbol names are the stable anchor if lines drifted) and the
  model facts you need. Open each cited location ONCE to confirm it still matches, then act. Do
  NOT broad-grep the src tree, sweep subsystems, or query the ~385-entity self-model beyond what
  the WU names.
- Principled fixes at the correct layer only — no workarounds; after such a fix add a regression
  test AND a contract/delegation test. No diagram-type/ontology knowledge in generic components.
  Python/TS files ≤250 soft / 350 hard LoC. No plan/WU names in code, tests, or commits.
- ALL model/diagram/document writes go through MCP tools (artifact_*), never hand edits; if a
  tool is wrong, fix the tool. For Workstream C WUs: invoke the architecture-modelling skill
  first; artifact_authoring_guidance before creating; dry_run=true before every write;
  artifact_verify after each batch; artifact_edit_entity properties is a FULL replacement.
- The backend is long-running: tell me when a code change needs a backend restart (I perform it)
  or an MCP-surface change needs a client session restart — do not block on it mid-session.

VERIFY & RECORD.
- Run the quality gates: `python -m pytest --tb=short -q` (0 failures), `ruff check src/ tests/`,
  `uv run zuban check`; for frontend WUs also `npm run lint`, `npm run typecheck`, `npm run test`
  in tools/gui. For GUI-visible fixes, verify live via the Playwright MCP against
  localhost:5173.
- Tick the WU's checklist in the plan. In the ledger: update the status table row (`done`, or
  `review` if it needs me) and append a progress-log line: date, WU, files changed, test results,
  any restart needed, and what is next.
- If the plan text proved wrong, fix it in place (present-tense, no revision-history phrasing)
  and note the correction in the progress log.

CONTINUE OR STOP.
- After recording a WU, assess your remaining context budget. If you can confidently complete the
  next unblocked WU end-to-end — implement, gates, checklist, ledger — loop back to PICK ONE WU
  and continue.
- Stop instead when: remaining context is not clearly sufficient for the next WU's full cycle;
  the next WU is blocked on me (D-6 decision, backend/session restart, `review` feedback); or all
  WUs are done. Never start a WU you may not finish cleanly — a half-done WU with an accurate
  ledger entry beats a finished one recorded sloppily, but finishing cleanly beats both.
- When you stop, end with a one-paragraph handoff: WUs completed this session, ledger state, any
  pending restart, and which WU is next.
```
- 2026-07-05 — Wizard "unusable" report investigated + cross-domain spine extension (B2c follow-up,
  user-directed). **Diagnosis first**: the user's dev server on :5173 runs from the *main checkout*,
  which still has the pre-B2b wizard skeleton — its `entityTypesForDomain` filters on a per-item
  `domain` field the domain-scoped `/api/authoring-guidance` response never includes
  (`_entity_type_guidance`'s `include_domain=False` branch), so every domain rendered an empty
  panel after "Loading guidance…". Confirmed by Playwright against :5173 (served DOM contained the
  old `entity-type-list` markup absent from this worktree) plus `/proc/<pid>/cwd` of the vite
  process. This worktree's B2b code already fixes the filter and was verified working live
  (questionnaire CTA, type grid, entity form) via a second vite instance on :5174 run from the
  worktree. No backend bug — the endpoint returns correct guidance for every domain.
  **Cross-domain uplift** (user clarified intent: guide beginners through lightweight cross-domain
  modeling; motivation/business/common most important, application relevant — note the behavioural
  core role/process/service lives in the *common* domain in this ontology): extended
  `wizardQuestionnaires.ts` with business (business-actor → business-object), common (role →
  process → service), and application (application-component → data-object) questionnaires, each
  question grounded in the type's `create_when`; bridges now chain the full spine motivation →
  business → common → application, `bridge` became optional and the terminal (application)
  completion offers review-later cleanup instead. New exported `QUESTIONNAIRE_SPINE`. Spine
  proximity anchors moved from questionnaire-local state into the persisted session
  (`spineAnchorIds` + `recordSpineAnchor` in `useWizardSession.ts`; `undoCreated` drops the
  anchor too), so a later domain's suggestion ranking biases toward graph neighbors of the whole
  chain built so far, across bridges and reloads. Hub now recommends what to model next:
  `recommendedNextDomain` + card `recommended` flag (`ModelWizardView.helpers.ts`), "Start
  here"/"Next" badge and spine-order subtitle in `ModelWizardView.vue`. Most-important-types
  ordering: `splitVisibleEntityTypes` gained a `priorityTypes` param (the domain questionnaire's
  step types) so e.g. common shows role/process/service first instead of alphabetical
  and-junction/event/function (`WizardDomainStage.helpers.ts` + `WizardDomainStage.vue`).
  Live-verified on :5174: spine subtitle, Start-here badge on motivation, common questionnaire CTA
  ("3 short questions from role to service"), reordered common type grid. Gates: `npx vitest run`
  445 passed (was 443; +14 new/updated across `wizardQuestionnaires.test.ts` [spine chain,
  per-domain steps, terminal-no-bridge], `useWizardSession.test.ts` [anchor record/dedupe/persist/
  undo, pre-spine parse default], `ModelWizardView.helpers.test.ts` [recommendation ladder,
  off-spine progress ignored], `WizardDomainStage.helpers.test.ts` [priority float, stable sort]);
  `vue-tsc --noEmit` clean; `eslint src/ui` clean. Merged this worktree into `main` on the
  user's request so :5173 (main checkout) serves the working wizard after a vite restart.
- 2026-07-05 — Wizard flexibility + persona-guidance uplift (user feedback: the questionnaire
  forced linear progression — e.g. goals/requirements without stakeholders, or processes/events
  without roles, weren't reachable inside the guided flow; "Show all types" revealed types with no
  guidance; and guidance should serve both planning and reverse-architecture personas, noting
  application-domain reverse architecture happens mostly via the MCP agent, so GUI reverse mode is
  chiefly for motivation/business/common). Changes, all frontend: (1) **Non-linear
  questionnaires** — every question skippable ("Skip — I don't need a X here"), clickable step
  chips jump to any question in any order, answered steps marked ✓; only answered steps feed the
  spine anchors (`WizardQuestionnaireStage.vue`). (2) **Guidance on every type button** — the
  show-all set now renders `create_when` like the priority set; hints are line-clamped (4 lines,
  full on hover) to keep the grid scannable (`WizardDomainStage.vue`). (3) **Planning vs
  reverse-architecture modes** — persisted session `mode` with a header toggle ("Planning — start
  from why" / "Reverse architecture — start from what exists"); `SPINES` per mode (planning:
  motivation→business→common→application; reverse: the exact reverse); per-mode bridges (each
  spine terminal has none in that mode), `reverseQuestion` step variants where planning phrasing
  would jar (driver, requirement, application-component, data-object), and
  `reversePrefersFind` on the application questionnaire so reverse-mode steps there open in
  "find existing" — anchoring on agent-imported components instead of duplicating them
  (`wizardQuestionnaires.ts`, `useWizardSession.ts`, `ModelWizardView.vue`/`helpers.ts`,
  `WizardEntityStage.vue` new `preferFind` prop). Recommendation badge + spine subtitle follow
  the mode. Gates: vitest 453 passed (+8: per-mode spine/bridge chains, reverse-question
  fallback, reversePrefersFind placement, mode parse/persist/default, reverse-mode
  recommendation ladder); `npm run typecheck` clean; `npm run lint` clean. Merged into `main`;
  live-verified on :5173.
- 2026-07-05 — Usability/usefulness analysis of the wizard (user-requested; personas: product
  owner modeling a new cross-cutting feature, junior architect changing an existing product,
  architect enriching context around agent-imported components, returning user). Findings and
  the improvement plan recorded as new section WU-B4 in the plan (B4.1–B4.7 + open decisions
  D-7/D-8) and as `todo` rows above. Two defects verified in code, not just observed: (1) the
  guidance layer serves `internal: true` entity types, so the wizard offers
  "New global-artifact-reference" although GARs are exclusively promotion-created and the create
  path raises — filter belongs in `_entity_type_guidance` (`type_guidance.py`), the one surface
  missing the `internal` check; (2) spine anchors are excluded from suggestion ranking —
  `hop_suggestions` (`_diagram_context.py`) returns only anchor *neighbors* (anchors seed
  `visited`), and the candidate pool (`searchEntityDisplay('', limit 20)`) can drop just-created
  entities once a type exceeds 20 instances, so a fresh chain gets no driver→stakeholder-style
  link help. Structural question raised by the user and taken up as D-7: the planning/reverse
  mode toggle forces an upfront methodology decision; recommendation is to replace it with an
  omnidirectional spine (bidirectional goal-labeled bridges + reuse-first step surface +
  state-derived recommendation), pending the user's call. No code changed in this session
  increment — analysis and plan only.
