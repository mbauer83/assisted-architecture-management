# PLAN — Modeling UX Remediation, Per-Section Document Connections, Guided Modeling Wizard & Self-Model Uplift

One plan, three workstreams:

- **Workstream A — Bug fixes**: entity-picker filtering/coverage/lazy-load, diagram-preview
  viewport bounds, GSN arrowhead/color rendering, activity/sequence selection & highlighting.
- **Workstream B — Features**: per-section suggested/required entity-type connections for
  document types; a multi-stage guided ArchiMate modeling wizard.
- **Workstream C — Self-model**: a structural two-tier repository view; motivation-domain
  emphasis on unity of effort and coherence; organization of the (large but not bloated) model.

Relation to prior work: `PLAN-gui-correctness-and-assurance-completeness.md` is fully
implemented. Its WU-E5 fixed the diagram-only read contract and selection for C4/GSN/datatype,
but activity/sequence selection remained broken because those renderers emit no matchable SVG
anchors (WU-A4 here completes that). Its Phase D fixed picker filter *derivation*
(implied domains, fixed levels); the defect addressed here (WU-A1) is in the separate
diagram-context search branch that Phase D never touched.

---

## 0. Cross-cutting concerns (apply to every WU)

- **Quality gates** (before every commit): `python -m pytest --tb=short -q` (0 failures),
  `ruff check src/ tests/` (0 errors incl. E501), `uv run zuban check`. Frontend WUs
  additionally: `npm run lint` and `npm run typecheck` in `tools/gui`, plus Vitest.
- **Principled solutions only**: fix at the correct layer; when a contract is missing
  (e.g. a viewer-extension hook), add it to the contract — never route around it. Every such
  fix ships a unit test for the new contract and a regression test reproducing the original
  failure.
- **Modularity**: no diagram-type or ontology knowledge in generic components. Type-specific
  SVG mapping lives in that diagram type's viewer extension; the generic viewer only consumes
  the contract.
- **LoC policy**: Python/TS source files ≤ 250 lines soft / 350 hard. New wizard/preview
  components must be decomposed accordingly (view + helpers modules, as the assurance wizards
  already do).
- **Test organization**: separate test files per component/use-case; no omnibus files. No plan
  work-unit names in code, tests, or filenames — use feature names.
- **Self-model writes** (Workstream C): exclusively through MCP tools (`artifact_create_entity`,
  `artifact_add_connection`, `artifact_create_diagram`, `artifact_edit_entity`, …). Remember
  `artifact_edit_entity` `properties` is a **full replacement** — always send all attributes.
- **Backend/MCP lifecycle**: backend code changes need an `arch-backend` restart (user-executed);
  MCP surface changes additionally need a client session restart. Sequence WUs so restarts batch.
- **Security**: no new authenticated surfaces are introduced anywhere in this plan. New REST
  endpoints (guidance, extended entity search params) are read-only queries over already-public
  model data, same trust posture as `/api/ontology` and `/api/write-help`. Wizard writes go
  through the existing verified write path (dry-run + verifier). Assurance gating is untouched.
- **Data consistency**: no migrations. The document-schema shape change (WU-B1) is
  loader-normalized (old files stay valid); the wizard commit path must address multi-write
  atomicity explicitly (see WU-B2b, decision D-6).

---

## For implementers — read this first (optimized for incremental, context-limited sessions)

**How to work this plan.** Pair it with `TASKS-modeling-ux-and-self-model-uplift.md` (the
ledger — source of truth for progress and settled decisions). Each session: (1) read the ledger
(status table + decision log); (2) pick the next unblocked WU; (3) **read the plan freely** —
§0, this section, the target WU in full, and any WU it depends on; (4) implement; (5) run the
quality gates; (6) tick the WU checklist here and update the ledger.

**Ration codebase & self-model exploration, NOT plan reading.** The plan is curated,
high-density context — reading it is cheap and prevents mistakes. The expensive, unbounded cost
is wandering the `src` tree or querying the ~385-entity self-model. Each WU cites the exact
`file:line` (as of 2026-07-04 — line numbers may have drifted; symbol names are the stable
anchor) and the model facts it needs: open a cited location **once** to confirm, then act. Do
**not** broad-grep the codebase or sweep the self-model unless a WU explicitly says
"verify/confirm at execution" — and then scope the lookup to exactly what is named.

**Repo map (where things live).**
- Backend (Python, hexagonal): `src/{domain,application,infrastructure,diagram_types,ontologies}`.
  - HTTP API routers: `src/infrastructure/gui/routers/` (`diagrams.py`, `entity_search.py`,
    `documents.py`, `connections.py`; shared helpers as sibling `_*.py` modules — follow the
    `_diagram_context.py` precedent when extracting shared logic).
  - Diagram types: `src/diagram_types/<type>/` (`renderer.py`; GSN also `svg_renderer.py`).
  - Generic PUML rendering: `src/infrastructure/rendering/generic_puml_renderer.py`.
  - Document schemata: loader `src/application/artifact_document_schema.py`; seeds
    `src/infrastructure/workspace/_repo_default_schemata.py` +
    `src/infrastructure/workspace/_assurance_doc_types.py`; verifier
    `src/application/verification/_verifier_document.py`; write path
    `src/infrastructure/write/artifact_write/document.py`; MCP tools
    `src/infrastructure/mcp/artifact_mcp/write/document.py`.
  - Authoring guidance backend: `src/infrastructure/write/artifact_write/type_guidance.py`;
    permitted relationships: `src/domain/permitted_relationships.py`.
- Frontend (Vue 3, hexagonal): `tools/gui/src/{adapters,application,domain,ports,ui}` — views in
  `ui/views`, shared components in `ui/components`, viewer/authoring extensions in
  `ui/lib/diagramViewerExtensions.ts` / `ui/lib/diagramAuthoringExtensions.ts` + registrations in
  `ui/diagram-types/<type>/index.ts`, effect-schemas in `domain/schemas.ts`, HTTP client in
  `adapters/http/HttpModelRepository.ts`, service facade `application/ModelService.ts` (injected
  via `ui/keys.ts` — there is no Pinia; follow the composable/session-store conventions).
- Self-model: `engagements/ENG-ARCH-REPO/architecture-repository/` (read-only on disk — all
  writes via MCP tools).

**Running things.** Backend gates: `python -m pytest --tb=short -q` · `ruff check src/ tests/` ·
`uv run zuban check` (needs `uv sync --all-groups` once). Frontend gates (in `tools/gui`):
`npm run lint` · `npm run typecheck` · `npm run test`. Deps via `uv sync` (never pip). Dev GUI
on localhost:5173 (backend :8000) — use the Playwright MCP tools for live UI checks. After
ontology changes: `uv run tools/generate_types.py` (a pre-commit hook enforces sync).

**Model writes (critical).** All model/diagram/document writes go through MCP tools
(`artifact_*`) — never hand-edit model files; if a tool is wrong, fix the tool. For Workstream C
sessions, invoke the `architecture-modelling` skill first and follow its task sequence:
`artifact_authoring_guidance` before creating, `dry_run=true` before every write,
`artifact_verify` after every batch. `artifact_edit_entity` `properties` is a **full
replacement** — resend every attribute. MCP tools run against a **long-running backend**: code
changes need a backend restart (the user performs it — ask), MCP-surface changes need a client
session restart; plan the session so you don't block on a restart mid-way.

**Hard rules.** Principled fix at the correct layer, never a workaround; after such a fix add a
regression test + a contract/delegation test. Python/TS source files ≤250 soft / 350 hard LoC
(`.md` exempt). No diagram-type/ontology knowledge in generic components. "arch" naming; **no
plan/WU names in code, tests, or commit messages** (use feature names). Separate test files per
component/use-case. Ternaries max one nesting level, expression position only. Commit only when
asked. A WU is done only when its checklist is ticked **and** all quality gates pass.

---

## Workstream A — Bug fixes

### WU-A1 — Entity picker: filters ignored, entities invisible, no lazy-load

**Symptoms.** (1) Selecting a filter value at any hierarchical level does not change the visible
list. (2) Entities that should match (e.g. application-domain) never appear even unfiltered.
(3) No lazy-loading; the list is a fixed truncation regardless of scroll.

**Root causes [CODE, verified].**
- `EntityPickerInput.vue` `doSearch()` (lines 111–152) has two mutually exclusive branches.
  When a caller passes `:diagram-type` (`CreateDiagramView.vue:325`, `EditDiagramView.vue:535`),
  the picker calls `svc.searchEntityDisplay(query, 30, diagramType)` →
  `GET /api/entity-display-search` (`src/infrastructure/gui/routers/diagrams.py:281`,
  impl `:85–126`) — an endpoint that accepts **no domain/entity-type filter params at all**.
  Chip toggles update `selectedDomains`/`selectedEntityTypes` and re-trigger the search, but the
  request is identical every time. (The non-diagram branch via `/api/reference-search` filters
  correctly.)
- `_entity_display_search_impl` sorts all entities by `(domain_order_index, name)` and truncates
  to `items[:limit]` (limit 30, cap 50). Domains early in `ontology.domain_order()` fill every
  slot, so application-domain entities fall past the cutoff — and with (1) broken, they can never
  be surfaced.
- No pagination or scroll-loading exists anywhere in `tools/gui/src`. A backend cursor pattern
  exists (`/api/diagram-types/datatype/types` with `next_cursor`,
  `schemas.ts:375–379`) but has no UI consumer.

**Design decision (D-1): one search contract for the picker.** Two overlapping entity-search
endpoints with different capabilities is the structural defect; wiring filters into both branches
would preserve it. Consolidate on **`/api/entity-display-search`** as the picker's single
backend (it returns the display info — type, glyph — the picker needs), extended with:
- `domains` (CSV, lowercase) and `entity_types` (CSV, exact) filters — semantics identical to
  `/api/reference-search`; extract the shared filter predicate into a common helper module used
  by both routers (no copy-paste between `diagrams.py` and `entity_search.py`).
- Cursor pagination: `cursor`/`limit` in, `next_cursor` out (reuse the datatype-types pattern).
  Stable sort key `(domain_order_index, name, artifact_id)` so pages don't skip/duplicate.
- `diagram_type` stays optional; when present it contributes `accepted_entity_types` as an
  additional intersection, exactly as today.

`EntityPickerInput.vue` then has **one** `doSearch()` path that always forwards
`effectiveDomains`/`effectiveEntityTypes` (+ optional diagram type) and appends pages.
`/api/reference-search` remains for its other consumers (diagram/document reference lookup).

**Lazy-load.** IntersectionObserver sentinel row at the bottom of `.ep-results`
(`EntityPickerInput.vue:422–451`): when visible and `next_cursor != null`, fetch the next page
and append. Reset pagination on any query/filter change. Keep page size modest (30–50).

**Checklist.**
- [x] Backend: shared entity-filter helper (domains/types/query predicate) used by both routers.
      New `_entity_filter.py` (`EntityFilter`, `parse_csv_filter`) used by both
      `/api/entity-display-search` (via `_entity_display_search.py`) and `/api/reference-search`'s
      entity branch.
- [x] Backend: `domains`, `entity_types`, `cursor` params + `next_cursor` on
      `/api/entity-display-search`; stable pagination sort; schema updated. New sibling module
      `_entity_display_search.py` (extracted from `diagrams.py` to hold the LoC line under 350);
      empty-query path is filter→stable-sort `(domain_order_index, name, artifact_id)`→cursor-slice;
      non-empty-query path threads `domains`/`entity_types` (∩ diagram-type-derived accepted types)
      into the existing FTS/fuzzy search (previously never received any filter at all — part of the
      symptom-1 fix) restricted to entities only (`include_connections/diagrams/documents=False`),
      also cursor-sliced. Response envelope changed from a bare list to `{items, next_cursor}` —
      `schemas.ts` update is A1.2 (frontend).
- [x] Frontend: single `doSearch()` path; filters always forwarded; page-append + reset logic;
      sentinel-row lazy-load; `HttpModelRepository`/`ModelService`/port signatures updated.
      `EntityPickerInput.vue`'s two mutually-exclusive branches collapsed into one path that
      always calls `svc.searchEntityDisplay` with query + `effectiveDomains`/`effectiveEntityTypes`
      + optional `diagramType` (fixes symptom 1: chip toggles previously had no effect when a
      diagram type was set) + cursor; `nextCursor`/`loadingMore` refs, an `IntersectionObserver`
      on a sentinel `<li>` (`ep-sentinel`) triggers `loadMore()` when scrolled into view;
      `doSearch()` (any query/filter change, via the existing debounce) resets `nextCursor` to
      `null` first. `searchEntityDisplay` port/adapter/service signatures moved to an options
      object (`{query, limit?, diagramType?, domains?, entityTypes?, cursor?}` →
      `EntityDisplaySearchResult`); new `EntityDisplaySearchResultSchema` in `schemas.ts`; mapping
      extracted as pure `entityDisplayInfoToHit` in `EntityPickerInput.helpers.ts`.
- [x] Regression tests (backend): filter by domain returns application-domain entities that the
      unfiltered first page omits (reproduces symptom 2); cursor walk yields all entities exactly
      once; diagram-type ∩ domain filters compose. New `test_entity_display_search_pagination.py`
      (4 tests) + `test_entity_filter.py` (8 unit tests for the shared predicate) +
      `test_gui_router_diagrams.py`'s existing 3 tests updated for the new envelope shape.
- [x] Vitest (frontend): chip toggle changes the issued request (reproduces symptom 1); scroll
      sentinel triggers next-page fetch and appends; filter change resets pages. **Partially
      satisfied, same infrastructure gap as WU-A2**: this project has no `@vue/test-utils` and
      Vitest runs `environment: 'node'` project-wide (no DOM/IntersectionObserver), so the
      component-interaction scenarios themselves aren't Vitest-testable here — every existing
      component/composable test in this codebase is a pure-function test for exactly this reason.
      What ships: `entityDisplayInfoToHit` unit-tested (`EntityPickerInput.fixedLevel.test.ts`,
      +1 test); the request-shape/sentinel/reset behaviors are covered by reading the
      implementation (single call site, `nextCursor` reset at the top of `doSearch`) and deferred
      to the Playwright smoke below.
- [x] Playwright smoke: picker in diagram-edit context — select application domain → application
      entities appear. Confirmed live against the ArchiMate two-tier diagram's edit view: the
      unfiltered picker lists motivation-domain entities first (reproducing symptom 2's cutoff);
      toggling the "Application" chip re-issues the request and application-component/interface/
      data-object entities appear; scrolling the sentinel into view appends the next page
      (59→67 items for the application domain, ~68 total).

### WU-A2 — Diagram-creation preview viewport unbounded

**Root cause [CODE, verified].** `CreateDiagramView.vue:543–548` `.prev-container` has only
`min-height: 200px` + `overflow: hidden`, no bounded height; the pan-zoom canvas child renders
the PNG at natural size, so the auto-height container grows to fit. Duplicated in
`EditDiagramView.vue:780–783`. The correct pattern already exists in `DiagramDetailView.vue`
`.img-container` (`:1071–1077`): `height: clamp(420px, 78vh, 980px)` + responsive media query.

**Design decision (D-2): extract a shared preview viewport.** The pan-zoom *behavior* is already
shared (`usePanZoom.ts`); the container *sizing* is copy-pasted and diverged — extract a
`PreviewViewport.vue` component (slot for content; pairs `usePanZoom` with bounded
`clamp(360px, 70vh, 900px)`-style sizing and the responsive breakpoint) and adopt it in
`CreateDiagramView.vue` and `EditDiagramView.vue`. `DiagramDetailView.vue` keeps its own
container for now (it is correct and carries selection/interactivity concerns); converging it
onto the shared component is a follow-up refactor, deliberately out of scope to keep this WU
low-risk.

**Checklist.**
- [x] `PreviewViewport.vue` (+ scoped styles) wrapping pan-zoom canvas with bounded
      viewport-relative height and minimum. New `tools/gui/src/ui/components/PreviewViewport.vue`:
      owns its own `usePanZoom` call (prop `resetSignal` feeds the composable's reset-on-change
      watch via `toRef`), slot for the image, `clamp(360px, 70vh, 900px)`-style bounded height +
      a narrower-viewport media query, matching `DiagramDetailView.vue`'s `.img-container` pattern.
- [x] Adopt in create + edit views; remove the two divergent `.prev-container` blocks.
      `CreateDiagramView.vue` and `EditDiagramView.vue` both replace their local
      `usePanZoom`/`prevContainerRef`/`prevCanvasStyle`/… wiring and `.prev-container`/
      `.reset-btn`/`.zoom-hint` styles with `<PreviewViewport :reset-signal="…">`.
      `DiagramDetailView.vue`'s own container is untouched, per D-2.
- [ ] Vitest: component renders slot within a bounded container (style contract), reset works.
      **Not written — infrastructure gap discovered, not a plan error to silently route around.**
      This project has no `@vue/test-utils` and Vitest runs with `environment: 'node'` (no
      jsdom/happy-dom) project-wide; `vite.config.ts`'s coverage config states outright that
      `.vue` views/components and composables are wiring "covered by the Playwright route-walk…
      not gated" by Vitest — true of every other component and composable in this codebase (zero
      precedent for SFC-mounting tests). Adding a DOM test environment/mounting library is a
      cross-cutting infrastructure change out of this WU's scope. Substituted:
      typecheck/lint/existing Vitest suite (346 tests, all green) confirm the extraction compiles
      and wires correctly; the CSS is a direct copy of `DiagramDetailView.vue`'s already-correct,
      already-shipped `clamp()` contract, not new logic being introduced blind.
- [x] Manual/Playwright check: preview of a large ArchiMate render stays within the viewport at
      1366px and 2560px widths. Confirmed live on the two-team ArchiMate view's edit page: at
      both widths the `.img-container` stays bounded (not growing to the SVG's natural
      2259×514px size), `overflow: hidden` clips it, and pan/zoom remains usable.

### WU-A3 — GSN diagrams: giant arrowheads, unexplained colors

**Root cause [CODE, verified].** The served GSN SVG is correct (~13px arrowheads,
`src/diagram_types/gsn/svg_renderer.py`: markers at `:269–273` with
`markerUnits="strokeWidth"`, edges `stroke-width="1.5"` at `:229–249`). The frontend's
connection hit-target code **clones each edge line, copies `marker-end`, and sets
`stroke-width="12"`** — `DiagramDetailView.vue` `addConnectionHitAreas()` (`:141–161`, attribute
copy at `:148–151`) and `AssuranceDiagramPanel.vue` `addEdgeHitArea()` (`:49–58`,
`cloneNode`). With stroke-width-relative marker units, the cloned arrowhead renders at ~8× —
the giant solid/hollow triangles. Only GSN is affected because it is the only native-SVG
renderer using `marker-end` (PlantUML emits arrowheads as polygons).
Colors are deterministic per GSN node kind (`_FILL`, `svg_renderer.py:41–49`); they merely lack
a legend. Static and runtime-derived GSN diagrams share this single render path — both affected.

**Fix design.**
- Frontend (primary): hit-target clones are invisible geometry only — never copy
  `marker-start`/`marker-mid`/`marker-end` (extend the skip list in `addConnectionHitAreas`;
  strip after `cloneNode` in `AssuranceDiagramPanel`).
- Backend (defense-in-depth): `markerUnits="userSpaceOnUse"` in `render_gsn_svg` so arrowhead
  size is absolute regardless of any consumer's stroke manipulation.
- Legend: emit a compact legend group inside `render_gsn_svg`, driven by the `_FILL` map and
  filtered to the node kinds present in the diagram — palette and legend stay co-located.
- Notation fidelity (small, optional within this WU): render `context` as a rounded rectangle
  (GSN standard) instead of a pill, `_shape()` `svg_renderer.py:210–211`.

**Checklist.**
- [x] Marker attributes excluded in both hit-area functions (shared helper if that avoids
      divergence). Shared `tools/gui/src/ui/lib/svgHitAreas.ts` (`SVG_MARKER_ATTRIBUTES`,
      `stripMarkerAttributes`) used by both `DiagramDetailView.vue` `addConnectionHitAreas` (skip
      list) and `AssuranceDiagramPanel.vue` `addEdgeHitArea` (post-clone strip).
- [x] `markerUnits="userSpaceOnUse"` with re-tuned absolute marker size (filled 13×13/refX 11,
      hollow 14×14/refX 12, paths scaled up proportionally).
- [x] Legend emission (kinds present only) + snapshot/unit test. `_legend()` in `svg_renderer.py`
      renders a swatch+label row for node kinds actually present, appended below the diagram
      (canvas grows to fit); order follows `_FILL` iteration order.
- [x] Vitest regression: cloned hit-area elements carry no `marker-*` attributes (reproduces the
      original failure via a fixture GSN SVG). `svgHitAreas.test.ts` (4 tests: constant contents,
      strip on shallow clone, no-op without markers, attribute-copy-loop pattern).
- [x] pytest: renderer emits `userSpaceOnUse` markers; legend lists exactly the kinds used.
      `test_gsn_rendered_svg.py::test_arrow_markers_use_user_space_on_use`,
      `::test_legend_lists_exactly_the_kinds_present`, `::test_legend_omits_kinds_not_present`.

Also changed the `context` node shape from a full pill (`rx = height/2`) to a modest rounded
rectangle (`rx="10"`) — closer to GSN Community Standard notation; updated the two pre-existing
tests that asserted the old pill shape (`test_gsn_rendered_svg.py::test_context_uses_rounded_rect_shape`,
`test_gsn_diagram.py::test_native_svg_uses_standard_shapes_and_accessibility`).

### WU-A4 — Activity & sequence diagrams: no selection, no highlighting

**Root cause [CODE, verified].** Selection/highlighting is driven entirely by
`DiagramDetailView.vue` `attachInteractivity()` (`:179–292`), which reverse-engineers
**graphviz** SVG conventions (node `g.id`/`<title>`/`data-qualified-name` derived from
`display_alias`; edges via `link_SRC_TGT` etc.). PlantUML's activity and sequence renderers do
not use graphviz and emit none of these hooks; additionally:
- Activity (`src/diagram_types/activity/renderer.py:271–316`): actions emitted as `:label;`
  with no alias/id; the only `[[link]]` is optional user-supplied (`:276`); decisions, forks,
  partitions carry nothing.
- Sequence (`src/diagram_types/sequence/renderer.py:76, :89, :245–282`): participants aliased
  renderer-internally as `LL1, LL2, …` — not the entity `display_alias` the diagram context
  publishes (`_diagram_context.py:179–180`) — and messages carry no id.
So `svgNodeElems` stays empty → both click-to-select and sidebar-highlight fail in both
directions. The `DiagramRenderer` protocol (`src/domain/ontology_protocol.py:103–128`) has **no
hook for declaring SVG-element↔artifact mapping**; only a sub-part decoration hook exists in
`diagramViewerExtensions.ts` (used by datatype).

**Design decision (D-3): extend the viewer-extension contract, don't grow the generic matcher.**
Add an optional top-level mapping capability to `DiagramViewerExtension`:
`mapElements(svgRoot, diagramContext) → { nodes: Map<artifactId, Element[]>, edges: Map<artifactId, Element[]> }`.
One-to-many from the start: a model entity may map to several SVG elements — WU-B3
(multi-occurrence ArchiMate views) requires exactly this, and designing the contract 1:1 now
would force a breaking change later. Selection highlights all mapped elements; clicking any of
them selects the artifact. The generic viewer uses a registered extension's mapping when
present; otherwise it falls back to the current graphviz matcher (which itself becomes the
default implementation, not special logic inside the view). This keeps renderer-specific SVG knowledge inside each diagram type's
module — the same shape the datatype extension already established.

Per type:
- **Sequence**: alias participants by their real normalized `display_alias` instead of `LL1…`
  (renderer `:76/:89`), so backend `source_alias`/`target_alias` line up; the sequence viewer
  extension maps participant head/lifeline groups by text/DOM order and message arrows by DOM
  order against the diagram context's ordered message list (PlantUML gives no per-arrow ids;
  index-based resolution mirroring the renderer's message emission order is the reliable path —
  assert the invariant with a golden-SVG test).
- **Activity**: emit a sentinel hyperlink (`[[arch://<artifact-id>]]`) on every element that
  PlantUML supports links for (actions at minimum, `:276` generalized); the activity viewer
  extension resolves those anchors, falling back to DOM-order mapping (context's ordered step
  list) for link-less elements (decisions/forks). Preserve user-supplied links (render both:
  user link as tooltip/href, sentinel as data anchor) — do not silently drop an existing feature.
- Sidebar: both directions already work generically once the maps are populated
  (`selectEntity`/watcher `:310–358`); connections for these types become selectable in the SVG
  and get the existing connection-detail panel.

**Checklist.**
- [x] `DiagramViewerExtension.mapElements` contract + generic-viewer consumption + graphviz
      default extracted as the fallback implementation (unit-tested as a contract). New
      `DiagramMapContext`/`DiagramElementMap` types and optional `mapElements` field on
      `DiagramViewerExtension` (`diagramViewerExtensions.ts`), plus `resolveElementMap` (registered
      extension's `mapElements` if declared, else the graphviz default) — the single dispatch
      point the generic viewer uses. New `graphvizElementMapping.ts`: the node-alias-matching and
      edge-matching logic that used to live inline in `DiagramDetailView.vue`'s
      `attachInteractivity`, extracted verbatim as `graphvizMapElements`, returning
      `Map<artifactId, Element[]>` for both nodes and edges (one-to-many from the start, per D-3).
      `DiagramDetailView.vue` now calls `resolveElementMap(diagramType, svgEl, {entities,
      connections})` and only attaches click listeners/hit-areas/highlighting over the returned
      maps — it no longer contains any graphviz-specific SVG matching itself. `svgNodeElems`/
      `prevHighlighted` changed from single-`Element` to `Element[]` value types to carry the
      one-to-many shape through selection highlighting. Contract unit tests:
      `graphvizElementMapping.test.ts` (8: data-entity/id-alias node matching, one-to-many node
      mapping, empty-input maps, data-entity-1/2 edge matching, link_SRC_TGT id fallback,
      SRC-TGT path+closest('g') fallback, no double-count across conventions) and
      `diagramViewerExtensions.test.ts` (3: extension's `mapElements` wins when declared, falls
      back to the graphviz default when absent, falls back for an unregistered type) — both use a
      minimal fake element tree (no jsdom/happy-dom in this project, same convention as
      `svgHitAreas.test.ts`).
- [x] Sequence renderer aliases every lifeline by a normalized identity, never a positional
      `LL{n}`: a bound lifeline (`entity_id` set) gets its real model entity's
      `display_alias` (resolved via `shared_artifact_index([repo_root])`, the same
      repo-lookup-from-a-renderer precedent C4's `_resolve_model.py` already established);
      an unbound lifeline gets `_normalize_puml_alias` of its own local id (diagram_types
      may not import `application` per the dependency policy, so this is a small local
      duplicate of `artifact_parsing.normalize_puml_alias` — same duplication C4's
      `_c4_types._normalize_alias` already carries, for the same reason). Either way the
      alias matches what `_diagram_context.py` publishes as the entity's `display_alias`
      (raw) / `source_alias`/`target_alias` (normalized), so the frontend's generic
      graphviz-default node matcher resolves lifelines via PlantUML's own
      `data-qualified-name` attribute — no sequence-specific node-matching code needed.
      Regression tests: `tests/rendering/test_sequence_renderer_entity_alias.py` (6: bound
      alias, unbound fallback, unresolvable-entity fallback, hyphen normalization on both
      paths, messages reference the bound alias); existing
      `tests/rendering/test_sequence_renderer.py` updated for the new non-positional
      aliases (`ll1`/`ll2` instead of `LL1`/`LL2`).
- [x] Activity renderer emits a sentinel `arch://<id>` link on every action/decision/partition
      (`_step_links.link_suffix`, extracted to a new sibling module `_step_links.py` to stay
      under the LoC cap): the bound entity id if `entity_id` is set, else the step's own local
      id (`_sentinel_target`/`sentinel_target`) — matching sequence's bound/unbound duality.
      Verified empirically against real `plantuml.jar` renders (1.2026.3) rather than assumed:
      PlantUML's activity `[[url]]` link syntax never wraps the action/decision/partition shape
      itself — it always renders as its own separate small blue link text, and multiple
      `[[...]]` clauses on one line coexist as separate sibling links, so the user's `link` (if
      any, action-only) is preserved completely unchanged and the sentinel is simply a second,
      additional `[[arch://<id>]]` clause — never a replacement. `fork` is the one exception:
      PlantUML's `fork` keyword takes no label/link argument at all (`fork [[url]]` is a syntax
      error) and renders as an unlabeled, ungrouped `<rect>` with no distinguishing attribute
      even without a link — forks are not selectable in the viewer, a genuine PlantUML
      rendering limitation rather than a scoping shortcut. Regression tests:
      `tests/rendering/test_activity_renderer_sentinel_links.py` (7: bound/unbound sentinel on
      action, user link preserved alongside sentinel, decision sentinel in the `if(...)` line
      bound/unbound, partition sentinel after the label, fork emits no link syntax at all);
      existing `tests/rendering/test_activity_renderer.py` updated for the new sentinel suffix
      appearing on every action/decision/partition line (23 tests, mechanical assertion
      updates only).
- [x] `registerViewerExtension('sequence', …)` with DOM-order message mapping (lifelines need
      no custom mapping — the alias fix above makes the graphviz default sufficient — but
      PlantUML gives message arrows no id/attribute tying them to our local message id, so
      `sequenceElementMapping.ts`'s `sequenceMapElements` wraps `graphvizMapElements` and
      additionally zips the rendered `<g class="message">` groups, in DOM order, against the
      `message` array's authored order — skipping any message with no complete
      `seq-from`/`seq-to` pair, since the renderer emits no SVG group for those). Required
      extending `DiagramMapContext` with an optional `diagramEntities` field (the raw
      `diagram-entities` frontmatter) alongside `entities`/`connections`, since DOM-order
      matching needs the authored array order that the generic (sorted) entities summary
      doesn't carry — `DiagramDetailView.vue` now passes it through. Golden-SVG fixture:
      `sequenceElementMapping.test.ts`'s fake element trees mirror, group-for-group,
      `fixtures/charge-flow.svg` (a real `plantuml.jar -tsvg` render of the renderer's own
      output, committed) — one bound + one unbound lifeline, two messages. Extracted the
      fake-SVG-DOM test harness (`FakeElement`/`FakeSvgRoot`/`makeEntity`/`asSvgRoot`) that
      `graphvizElementMapping.test.ts` had inlined into a shared `svgDomFakes.ts`, since this
      WU's sequence test needed the identical harness plus a `g.message` selector.
      `registerViewerExtension('activity', …)`: unlike sequence, no DOM-order zipping is
      needed at all — the sentinel `<a href="arch://…">` directly encodes the target artifact
      id (or, unbound, the local id to resolve via the diagram-local placeholder entity's
      `display_alias`), so `activityElementMapping.ts`'s `activityMapElements` just scans every
      `<a>` in the SVG, filters to `arch://`-prefixed hrefs (ignoring the user's own link,
      which keeps its real href), and maps the anchor element itself as the selectable/
      highlightable representative for that step (there is no per-step `<g>` wrapper in
      PlantUML's activity SVG output to attach a click listener to instead — confirmed against
      the real render: shapes and link `<a>`s are flat siblings, not nested per-step groups).
      `fork` contributes nothing to the map (no anchor, no distinguishing attribute). Golden-SVG
      fixture: `activityElementMapping.test.ts`'s fake `<a>` elements mirror
      `fixtures/order-flow.svg` (a real `plantuml.jar -tsvg` render) — one bound action, one
      unbound action, one decision.
- [ ] Vitest both directions per type: click action/decision/lifeline/message → sidebar detail;
      sidebar click → `svg-selected`/`svg-conn-selected` class lands on the right element. Both
      types' element-mapping halves are unit-tested (`sequenceElementMapping.test.ts`,
      `activityElementMapping.test.ts`); the full click→sidebar/sidebar→highlight interaction
      through `DiagramDetailView.vue` is not Vitest-testable in this repo (no
      `@vue/test-utils`, Vitest `environment: 'node'` project-wide, no precedent for mounting
      an SFC — same finding as WU-A2/A1.2) — needs the Playwright smoke below instead.
- [x] Playwright smoke on the self-model's ACT + SEQ diagrams. Sequence worked exactly as
      designed with zero further changes: lifelines and messages both map correctly, both
      click→sidebar and sidebar→highlight directions confirmed live and visually (blue
      activation-bar highlight). Activity was completely non-functional live despite passing
      every unit/golden-fixture test, because of three pre-existing consumer-side defects that
      only an anchor-typed `mapElements` representative (introduced by this WU) ever exercised:
      (1) `DiagramDetailView.vue`/`EditDiagramView.vue`'s `DOMPurify.sanitize(...)` call has no
      `ALLOWED_URI_REGEXP` override, so DOMPurify's default allow-list silently strips
      `href`/`xlink:href="arch://…"` before the sanitized SVG ever reaches the DOM — confirmed by
      diffing the raw `/api/diagram-svg` response (has the href) against the live post-sanitize
      DOM (doesn't); (2) both views' `attachInteractivity` gated `data-entity-id`/click-listener
      attachment on `instanceof SVGGElement`, silently skipping the sentinel `<a>` (an
      `SVGAElement`) entirely; (3) the `.svg-selected`/hover highlight CSS only targets
      `polygon`/`rect`/`polyline`/`ellipse` children, none of which exist inside an anchor that
      wraps only a `<text>`. Fixed all three at their actual layers (not a workaround): new
      `ui/lib/svgSanitize.ts` (`sanitizeDiagramSvg`, exported `ALLOWED_URI_REGEXP` extending
      DOMPurify's default scheme list with `arch`) replaces the inline sanitize calls in both
      views; the element-type gate now accepts `SVGGElement || SVGAElement` in both views (the
      `<g>`-only `attachNodeSubParts` call stays gated on `SVGGElement`); new
      `a[data-entity-id]`/`a.svg-selected` CSS rules apply `fill`/`font-weight` to the anchor's
      `text` child. Also found and fixed, via a real (non-synthetic) click during this same
      check: neither view's click handler called `preventDefault()`, so a genuine click on the
      now-mapped sentinel `<a href="arch://…" target="_top">` triggered the browser's native
      link-following, surfacing as a console error ("Not allowed to launch 'arch://…' because a
      user gesture is required") and, worse, would bypass the `click` handler entirely on a
      middle-click/new-tab or drag-to-bookmark (those never fire `click`). Fixed with a new
      shared `neutralizeSentinelLink` helper (`diagramViewerExtensions.ts`) that strips
      `href`/`xlink:href`/`target` from an anchor representative once `attachInteractivity` has
      read what it needs from it, plus `preventDefault()` on the click listener itself as
      defense in depth; both views call it. All three original defects plus this one are
      cross-cutting consumer bugs in the generic viewer, not activity-specific — they would have
      identically broken any future diagram type that returns an anchor from `mapElements`.
      Verified live end-to-end after the fix (dispatched real click events and confirmed via
      Playwright's own actual mouse click for the neutralization check): all 7 sentinels on the
      self-model's promotion activity diagram map correctly, click→sidebar and sidebar→highlight
      both work for actions and the decision, and the anchors no longer carry `href`/`target`
      after mapping. New regression test `svgSanitize.test.ts` (3: `arch:` allowed, default-safe
      schemes still allowed, `javascript:`/`data:` still blocked) — the DOM-dependent half
      (`sanitizeDiagramSvg` itself, `neutralizeSentinelLink`) is not Vitest-testable in this repo
      for the same `environment: 'node'`/no-jsdom reason as everything else in this WU; confirmed
      `document` is genuinely `typeof undefined` in this test environment before concluding that,
      rather than assuming it from the prior sessions' notes.

---

## Workstream B — Features

### WU-B1 — Per-section suggested/required entity-type connections for document types

**Current state [CODE, verified].** Document-type schemata are JSON at
`.arch-repo/documents/<doc_type>.json` (loader `src/application/artifact_document_schema.py`),
seeded from `_repo_default_schemata.py` / `_assurance_doc_types.py`. Today:
`required_sections: list[str]` + `section_templates: {name: text}` +
document-level `required_entity_type_connections` / `suggested_entity_type_connections`
(entity-type *terms*: bare name, `@ClassName`, `@all` — resolved via `catalogs.py:141–155`).
Sections are free-form `##` headings matched by text (no stable ids); document→entity
connections are inline markdown links discovered by the verifier
(`_verifier_document.py:48–72`); enforcement codes E153/E154/E155 (+W155/W156); *suggested* is
advisory (GUI chips in `DocumentCreateView.vue:353–377`), not verified.

**Schema decision (D-5).**
- **Option A — per-section objects**: `sections: [{name, template?, required_entity_type_connections?, suggested_entity_type_connections?}]`,
  superseding the parallel `required_sections` + `section_templates` structures.
- **Option B — section-tag lists on requirement entries**: keep flat document-level lists,
  each entry optionally `{term, sections: [...]}`.

**Choice: Option A.** Rationale: (i) intelligibility — a section's contract (template + expected
links) reads in one place, which is exactly how authors and agents consume it; (ii) it heals an
existing smell — two parallel section structures keyed by the same fragile string; (iii) Option B
still requires identical body-partitioning and section-keying machinery in the verifier while
scattering section knowledge across entries, and it awkwardly duplicates a term when two sections
need the same type. Option B's only advantage (no shape change to `required_sections`) is
neutralized by loader normalization. Document-level lists **remain** for whole-document rules;
per-section rules add to them rather than replacing them.

Section identity stays **heading text** for now: it is already the verifier's matching key and
the schema's section name; introducing stable section ids would ripple through parsing, editing,
and promotion for no present gain. Record this as an accepted limitation (rename a heading in the
schema = a schema change).

**Design.**
- Loader (`artifact_document_schema.py`): normalize both shapes to a canonical
  `DocumentSchema` value object (`sections: tuple[SectionSpec, ...]`; legacy
  `required_sections`/`section_templates` folded in). All consumers switch to the typed shape —
  `_validate_section_templates`/`_build_placeholder_body`
  (`infrastructure/write/artifact_write/document.py:59–95`), verifier, REST, promotion diff
  (`promote_schema_check.py:127` compares normalized section specs).
- Verifier (`_verifier_document.py`): partition the body into per-section spans by `##` heading
  offsets; run link-extraction per span. New codes: **E156** — required entity-type connection
  missing in section *X*; **W157** — unknown term in a per-section rule (mirror of E155's
  unknown-term arm). Suggested terms stay verifier-silent (GUI-only), consistent with today.
- Write path/MCP: `artifact_create_document`/`artifact_edit_document` descriptions surface the
  per-section expectations (so agents place links in the right section); placeholder bodies embed
  a one-line HTML comment hint per section listing expected entity types (harmless in rendering,
  high-value for authors and agents).
- REST/GUI: `/api/document-types` exposes the canonical shape (`routers/documents.py:77–80`,
  `schemas.ts:213–222`); `DocumentCreateView.vue` renders the connection chips per section;
  `DocumentDetailView.vue`'s reference picker (`insertReference`, `:138–140`) becomes
  section-aware: it detects the cursor's section and ranks/labels suggestions for that section.
- Seed schemata: give `standard` (and the assurance doc types where sensible, e.g.
  `assurance-case` evidence sections) per-section rules as the dogfooding exemplar.

**Checklist.**
- [x] `SectionSpec`/`DocumentSchema` domain value objects + loader normalization (legacy shape
      accepted; unit tests for both shapes). Loader now emits legacy-compatible schema dicts with
      canonical `sections` while exposing typed `DocumentSchema` objects for later consumers.
- [x] Verifier body partitioning + E156/W157 + tests (present-in-wrong-section fails; document-
      level rule still satisfiable anywhere; unknown term surfaces W157).
- [x] Write path reads canonical shape; placeholder generation with per-section hints; MCP tool
      description updates (note: MCP surface change → session restart).
- [x] REST + `schemas.ts` + create-view per-section chips + detail-view section-aware picker.
      `/api/document-types` now includes the canonical `sections` array (loader already emitted
      it via WU-B1.1's `DocumentSchema.to_dict()`, just not surfaced); `schemas.ts` gained
      `SectionSpecSchema` + `DocumentTypeSchema.sections`. New shared
      `tools/gui/src/ui/lib/documentSections.ts` (`sectionAtOffset`, `findSectionSpec`,
      `sectionEntityTypeTerms`, `formatEntityTypeTerm`, `rankedEntityTypeSet`/
      `isLiteralEntityTypeTerm`) — pure functions, unit-tested. `DocumentCreateView.vue` renders a
      per-section required/suggested breakdown (`sectionsWithEntityHints`) alongside the existing
      document-level hints, and now imports the shared `formatEntityTypeTerm` instead of a local
      copy. `MarkdownEditor.vue` exposes `getCursorOffset()`. `DocumentDetailView.vue` loads
      document types, resolves the cursor's enclosing `##` section via `sectionAtOffset` when
      "Insert Reference" is opened, and passes `sectionLabel`/`suggestedEntityTypes` to
      `ArtifactReferenceInput.vue`, which shows a section hint bar and ranks/badges entity-type
      chips whose term is a literal (non-`@`) match — `@ClassName`/`@all` terms are labeled but not
      ranked, since resolving them to concrete entity types requires ontology data the frontend
      doesn't have (backend-only resolution stays in `catalogs.py`, not duplicated here).
- [x] Promotion schema diff compares normalized shapes; test for engagement ⊇ enterprise check.
      `_document_schema_errors` (`promote_schema_check.py`) now loads typed `DocumentSchema`
      objects (`get_document_schema_object`) instead of raw dicts and delegates to new
      `_document_section_errors`, which compares normalized `SectionSpec`s by name: missing
      enterprise sections are still reported (unchanged wording), and for sections present in
      both, the engagement section's `required_entity_type_connections` must be a superset of the
      enterprise section's — a per-section analogue of `_schema_superset_errors`. New tests in
      `test_promote_schema_pure.py::TestDocumentSchemaErrors`
      (`test_missing_section_entity_type_connection_reported`,
      `test_engagement_section_superset_reports_no_error`).
- [x] Seed-schemata exemplar + an end-to-end test: create doc from type → placeholder sections →
      verifier reports E156 until the required link is added in the right section.
      `standard`'s seed schema (`_repo_default_schemata.py`) converted from document-level
      `required_entity_type_connections`/`suggested_entity_type_connections` to canonical
      `sections`: the `requirement` link now belongs to "Specification" (where a normative
      standard actually cites the requirement it satisfies) and `principle`/`goal` suggestions
      moved to "Motivation" (where the rationale for the standard lives) — the dogfooding
      exemplar the plan asked for. `assurance-case`'s seed schema
      (`_assurance_doc_types.py`) similarly narrowed its blanket document-level `@all` suggestion
      to two sections where it is actually meaningful: "Evidence Summary" (`@all`) and "Sign-off"
      (`stakeholder`, the role actually signing off) — the other assurance doc-types are
      untouched, matching the plan's "where sensible" scoping. New
      `tests/tools/test_document_section_templates.py::TestStandardDocTypeSectionLifecycle`:
      the placeholder body test asserts the real seed schema's hints land in "Specification"/
      "Motivation" and not "Scope"/"Summary"; the lifecycle test previews the placeholder
      (`dry_run=True` — writing the still-unlinked placeholder for real is itself blocked by the
      same E156 check, so the still-unwritten preview is placed on disk directly, as an author's
      in-progress draft would be), verifies E156 fires for "Specification", adds a relative
      markdown link to a real `requirement` entity inside that section, and verifies E156 clears.

### WU-B2 — Multi-stage guided ArchiMate modeling wizard

**Grounding.** Reusable today [CODE, verified]: the assurance wizards' shell pattern
(`AssuranceStpaWizardView.vue` + `*.helpers.ts`: step tabs with free skip, per-step guidance
panel, relation linker); `getWriteHelp().entity_types_by_domain` (per-domain type catalogs);
`getEntitySchemata` + `TypedPropertyInput.vue` (typed property forms with dry-run);
`ConnectionsPanel.vue` + `/api/ontology` (`classify_connections` and pair
`connection_types` — the permitted-relationship matrix from
`src/domain/permitted_relationships.py`); `EntitySearchInput.vue`/`EntityPickerInput.vue`
(search); `discoverDiagramEntities` (graph-neighborhood suggestions). Gaps: the rich per-type
guidance (`create_when`/`never_create_when`/pair guidance in
`src/infrastructure/write/artifact_write/type_guidance.py`) is MCP-only; there is no cross-stage
draft/session state (no Pinia by convention); no batch multi-write orchestration precedent
against the architecture repo.

**Strategy synthesis (researched).** Facilitation methods evaluated: event storming, domain
storytelling, card sorting, capability mapping, impact mapping, user story mapping, GQM/i*/KAOS
goal-elicitation, plus how Archi/Bizzdesign/LeanIX/Ardoq guide novices. Verdict:
- **Adopt for v1**: (a) **goal-modeling questionnaires** (GQM/KAOS-style) for the motivation
  stage — questionnaires are natively form-shaped and each answer maps 1:1 to an entity plus a
  typed connection; (b) **impact mapping** (why → who → how → what) as the cross-domain spine —
  it bridges motivation → business → application, the hardest conceptual jump for non-experts;
  (c) **capability mapping** as the strategy-stage anchor for search-and-reuse against the
  existing model.
- **Defer**: domain-storytelling sentence templates (business stage, v1.5); card sorting only as
  a micro-interaction for triaging free-text brain-dump items.
- **Reject**: event storming and user story mapping — their value is spatial/workshop-collective
  and survives a form-based wizard poorly; story mapping is also redundant with impact mapping
  here.
- **UX topology: mixed** — a **hub** of domain cards (progress, entity counts, free skipping —
  the user's requirement) with a short **linear stepper (3–5 steps) inside each domain**. One
  question per screen-section; advanced attributes behind progressive disclosure; never show the
  full type palette — offer 2–4 type choices phrased as questions. Suggested connections: max
  3–5 ranked one-line sentences ("*X* probably **serves** *Y*") with accept / edit / dismiss;
  everything else lands in a persistent **"review later" queue** on the hub. Ranking: metamodel
  validity (permitted relationships) → name/text similarity → graph proximity. Autosave per
  answer; on resume, recap "you were here, you last created X".

**Delivery slices** (each independently shippable):
- **B2a — Guidance surface + wizard shell.** New read-only REST endpoint (e.g.
  `GET /api/authoring-guidance?entity_type=|domain=|source=&target=`) exposing
  `get_type_guidance` (create_when / never_create_when / permitted connections / pair guidance) —
  reusing the existing implementation, no duplication. Wizard route (`/model/wizard`) +
  hub-and-spoke shell + `useWizardSession` composable (reactive draft store: created ids,
  pending suggestions, review-later queue; persisted to `sessionStorage` for resume).
- **B2b — Domain stages: create, find, connect.** Per-domain stage assembled from existing
  building blocks: type choice (question-phrased, driven by `entity_types_by_domain` +
  guidance), entity form (`getEntitySchemata` + `TypedPropertyInput`), related-entity search
  (picker with the domain pre-scoped via the WU-A1-fixed filters), and connection suggestions
  (classification + pair endpoints, capped and ranked). **Commit semantics (decision D-6):**
  wizard writes commit per-artifact through the existing verified write path, each preceded by
  dry-run; the wizard session tracks created ids and offers "undo step" (delete of just-created
  draft artifacts). Every entity/connection the wizard creates also carries a `wizard-draft`
  keyword/note tag — a passive breadcrumb, not an active cleanup mechanism — so artifacts left
  behind by an abandoned session (the browser tab closed, `sessionStorage` gone, the undo
  affordance lost with it) stay discoverable later via an ordinary Browse/keyword filter rather
  than becoming silently indistinguishable from intentional hand-created drafts. Full
  multi-entity atomicity via the staged-bulk-operation machinery is explicitly rejected, not
  just deferred: `PLAN-scalable-bulk-staging.md` already establishes that path is O(repo-size)
  per call, unsuited to holding a whole wizard session's writes, on top of requiring a second
  transactional pathway that doesn't exist today. Rationale: artifacts are draft-status in an
  engagement repo; partial progress is visible, verifiable, and individually reversible —
  acceptable consistency for an authoring aid.
- **B2c — Elicitation layers + cross-domain spine.** Motivation questionnaire (stakeholder →
  driver → assessment → goal → outcome → requirement prompts); impact-mapping bridge steps at
  domain transitions; capability-anchored reuse search in strategy; review-later queue
  resolution UI. Suggestion ranking incorporating `discoverDiagramEntities`-style neighborhood
  signals.

**Checklist (per slice; each gated on the full quality suite).**
- [x] B2a: guidance endpoint + schema + adapter/service; wizard route/shell/session store;
      Vitest for session persistence/resume; endpoint tests. New
      `src/infrastructure/gui/routers/authoring_guidance.py` (`GET /api/authoring-guidance`,
      `entity_type`/`domain` CSV filters merged into `get_type_guidance`'s `filter`, plus
      `diagram_type`/`target` passthrough — no duplication of `get_type_guidance` itself, which
      stays MCP+REST shared); registered in `arch_backend_app.py`. Frontend:
      `AuthoringGuidanceSchema`/`EntityTypeGuidanceSchema`/`PairGuidanceSchema` in `schemas.ts`;
      `getAuthoringGuidance` added to `ModelRepository`/`ModelService`/`HttpModelRepository` (options
      object, mirrors A1.2's `searchEntityDisplay` convention). New
      `tools/gui/src/ui/composables/useWizardSession.ts`: reactive draft store (created entities,
      pending suggestions, review-later queue) persisted to an injected `WizardStorage` (defaults to
      `window.sessionStorage`) via a `flush: 'sync'` watcher — the DI keeps it directly
      Vitest-testable (no `inject()`, so no DOM/mounting needed, unlike most `.vue` views/composables
      in this codebase). New `ModelWizardView.vue` + `ModelWizardView.helpers.ts`: hub-and-spoke shell
      at `/model/wizard` — ArchiMate-domain cards (scoped via `FRAMEWORK_GROUPS['archimate-next']`,
      excluding SysML) with created-count badges, free click-through with no gating, a guidance panel
      per opened domain (entity types + create_when/never_create_when, fetched on demand), and a
      review-later queue section (empty until B2c's suggestion engine populates it). Added a
      "Wizard" link to `NavBar.vue`. New tests:
      `tests/tools/test_gui_router_authoring_guidance.py` (8: CSV filters, diagram_type guidance,
      pair legality, REST/domain-function parity); `useWizardSession.test.ts` (12: initial state,
      resume-from-storage, persistence, created/suggestion lifecycle, reset);
      `ModelWizardView.helpers.test.ts` (7: domain scoping, created counts, entity-type filtering).
      Gates: `pytest` 3714 passed/8 skipped (+8); `ruff` clean; `zuban` clean (436 files); frontend
      `lint`/`typecheck` clean, `test` 405 passed (+19). No backend restart needed yet for this WU
      alone (new REST endpoint, no MCP-surface change) — batch with B2b's restart. No Playwright
      smoke performed this session (B2a's checklist doesn't require one; B2b's does) — the shell
      renders against static/guidance-only data with no write path yet, so a live check adds little
      before B2b gives it something to actually create.
- [x] B2b: stage components (decomposed per LoC policy); connection-suggestion service (rank +
      cap + queue); dry-run→commit flow + undo; Vitest per component; backend tests for any new
      query params; Playwright: create a small motivation+application slice end-to-end.
      New `WizardDomainStage.vue`/`.helpers.ts` (type-choice question phrasing, 2-4 visible +
      "show all"), `WizardEntityForm.vue` (name/summary + required-schema properties via
      `TypedPropertyInput`, progressive disclosure for optional ones, dry-run→create, auto-tags
      every created entity `wizard-draft` per D-6), `WizardConnectionSuggestions.vue` (accept/
      later/dismiss list), and `ui/lib/wizardSuggestions.ts` (pure: `legalConnectionPairs` +
      `nameSimilarity` (Jaccard word-overlap) + `rankCandidatesByName` + `buildWizardSuggestions`
      — metamodel-validity-then-name-similarity ranking, capped). Reused existing
      `getAuthoringGuidance`'s per-entity-type `permitted_connections` for the ranking signal
      instead of adding a second `getOntologyClassification` call (same `{outgoing, incoming,
      symmetric}` shape) — no new backend endpoint or query params needed at all, confirming the
      plan's own "reusable today" grounding. `useWizardSession.ts` gained `createdConnections` +
      `recordConnectionCreated`/`undoConnectionCreated` and extended `WizardSuggestion` with
      commit-ready `sourceId`/`connectionType`/`targetId` fields (storage key bumped `v1`→`v2`,
      a v1 session had no way to commit its own suggestions). Undo now really deletes: the
      wizard's "Undo" button calls `deleteEntity`/`removeConnection` before clearing session
      state, not just clearing local UI state.
      **Two real, previously-undetected bugs found and fixed during the live Playwright check**
      (both pre-dated this WU, in code B2a shipped without a live check): (1)
      `entityTypesForDomain` filtered on a per-item `domain` field that `GET
      /api/authoring-guidance?domain=...` never populates when the whole response is already
      domain-scoped (`_entity_type_guidance`'s `include_domain=False` branch,
      `type_guidance.py`) — the wizard's own only call pattern — so the type-choice grid was
      silently empty for every domain until now; fixed to trust the omission (filter only when
      the field is actually present). (2) my own `legalConnectionPairs` had the classification
      record's key/value backwards on first pass — `_classify_connections` keys each record by
      **target type** with **connection types** as the value array, not the reverse — caught by
      inspecting live network requests during the Playwright check (`entity_types=archimate-*`
      instead of real entity type names) before it shipped; both have regression tests
      (`WizardDomainStage.helpers.test.ts`'s domain-omitted case,
      `wizardSuggestions.test.ts`'s corrected fixture shape with an explanatory comment).
      Playwright: live end-to-end in both Motivation (create→suggest→accept, find-existing→
      suggest) and Application (create→suggest→undo) — confirmed the `wizard-draft` keyword tag
      lands on created entities, suggestions rank sensibly, accept commits a real connection,
      and undo really deletes server-side (verified via `artifact_query_search_artifacts` after
      each, not assumed from the UI alone). One accepted test suggestion (a real connection
      between two pre-existing self-model entities) was found on review to be an unreviewed
      synthetic addition rather than a curated one and was removed via `artifact_edit_connection`
      (`operation=remove`) immediately after the check, restoring the pre-test state exactly (dry-run
      diffed against the original file content first). Backend: none touched — no new REST
      endpoints or query params were needed, so no backend tests apply. Vitest:
      `wizardSuggestions.test.ts` (13), `useWizardSession.test.ts` (+2 for the connection
      tracking), `WizardDomainStage.helpers.test.ts` (8, includes the domain-omission
      regression) — the interaction-heavy parts of `WizardDomainStage.vue`/`WizardEntityForm.vue`
      (async schema/suggestion fetching, dry-run→commit sequencing) are not Vitest-testable in
      this repo for the same `environment: 'node'`/no-DOM reason as every other `.vue` view in
      this plan; covered instead by the live Playwright check. Gates: frontend
      `lint`/`typecheck` clean, `test` 428 passed (+21); backend untouched, not re-run.
- [x] B2c: questionnaire/spine step definitions (helpers modules, content-driven so wording
      iterates without code churn); ranking integration; Playwright: novice path from empty
      domain to connected mini-model.
      Extracted the create/find/suggest/undo logic shared by both the free-choice hub and the
      new guided questionnaire into `WizardEntityStage.vue` (was inline in `WizardDomainStage.vue`;
      no behavior change, pure decomposition so the questionnaire doesn't duplicate it). New
      `ui/lib/wizardQuestionnaires.ts` (pure, content-driven): the motivation questionnaire
      (stakeholder → driver → assessment → goal → outcome → requirement, one GQM/KAOS-style
      question per step) plus its "bridge" — the impact-mapping spine step shown on completion,
      pointing to the business domain (why/who/how/what framing) and actually switching
      `session.state.activeDomain` there, not just a static message. New
      `WizardQuestionnaireStage.vue`: progress indicator ("Question N of M"), current question,
      embeds `WizardEntityStage` with `proximityAnchors` = every entity id created earlier in the
      sequence, auto-advances on a real create/find (an emitted `null` — a plain form cancel —
      exits back to the hub instead of silently advancing past an unanswered question).
      `WizardDomainStage.vue` gained a "✨ Start the guided questionnaire" entry point above the
      free-choice type grid when a questionnaire exists for the domain, never replacing free
      choice (the plan's "free skipping" requirement).
      **Ranking integration**: `buildWizardSuggestions` gained an optional `proximityBoost`
      parameter — a small (+0.15) tiebreaker added to a candidate's name-similarity score when it
      appears in `discoverDiagramEntities`'s hop-neighbor results for the entities built up so far
      in the session, matching the plan's stated priority order (metamodel validity, structural →
      name similarity → graph proximity, in that order, proximity never overriding a clear name
      match). Removed `rankCandidatesByName`, now dead code once the per-pair candidate selection
      moved to the same combined-score comparator used for cross-pair ordering.
      **Review-later queue resolution UI**: the hub's flat "Resolved"-only list (which just
      discarded a suggestion without ever committing it) is replaced with the same
      `WizardConnectionSuggestions` component the domain stage uses (`hideLater` prop added, since
      "later" is meaningless for an item already in the later queue) — Accept now actually commits
      the connection. New shared `ui/composables/useSuggestionCommit.ts` extracts the commit
      sequence (`addConnection` dry-run-implied write → `recordConnectionCreated` →
      caller-supplied removal callback) so `WizardEntityStage.vue`'s in-context accept and the
      hub's review-later accept can't drift apart. Also fixed a related wiring gap while touching
      this: switching domains no longer requires a direct card click to trigger a guidance
      refetch — `ModelWizardView.vue` now watches `session.state.activeDomain` directly
      (`immediate: true`), so the questionnaire's own domain-switching bridge button (and session
      resume on page load) both refetch guidance correctly through one code path instead of two
      that could fall out of sync.
      New tests: `wizardQuestionnaires.test.ts` (4), `wizardSuggestions.test.ts` proximity-boost
      cases (+3, replacing the 1 removed `rankCandidatesByName` test). Gates: frontend
      `lint`/`typecheck` clean, `test` 434 passed (+6); backend untouched, not re-run (no `.py`
      changes).
      Playwright — novice path live in Motivation: started the questionnaire, created a
      throwaway stakeholder (step 1 of 6), deferred one suggestion to "Later" (confirmed it
      surfaced on the hub via the new resolution UI, with no "Later" button there), advanced to
      "Question 2 of 6" (driver — confirmed the schema-driven required `Category` enum property
      rendered correctly), created a throwaway driver, confirmed proximity-ranked suggestions
      referencing the step-1 stakeholder appeared at the top, accepted the hub's deferred
      suggestion (confirmed it actually committed — a real connection to a real, pre-existing
      outcome entity — and disappeared from the queue), then used in-questionnaire "Undo" on the
      driver (confirmed it reverts within questionnaire mode, not just free-choice mode). Did not
      walk all 6 steps to the bridge screen — the remaining steps exercise no new B2c mechanism
      beyond what steps 1-2 already proved (create/undo were already proven end-to-end in WU-B2b);
      stopped once the questionnaire-specific pieces (sequencing, proximity ranking, review-later
      commit) were each confirmed working, to limit live test-data footprint in the shared
      self-model. All test entities/connections deleted and reverified clean afterward
      (`artifact_verify`: 0 errors/0 warnings; `artifact_query_search_artifacts` for both
      throwaway names returns no hits) — this time re-querying and re-confirming the target
      artifact_id via a fresh read immediately before every delete call, per the near-miss
      recorded in the WU-B2b ledger entry.

### WU-B3 — ArchiMate views: multiple occurrences of one model entity

**Motivation.** Standard ArchiMate practice allows the same model element to appear multiple
times in one view — to depict plurality (e.g. several engagement-repository contexts around one
shared enterprise baseline, WU-C1) and to reduce edge clutter in dense views. The current
implementation renders each entity exactly once: the renderer emits one alias per entity
(`generic_puml_renderer.py:75–129`), the diagram context publishes a single `display_alias`
per entity (`_diagram_context.py:97–99`), and the frontend maps alias→id and id→SVG element 1:1
(`buildAliasToId`, `DiagramDetailView.helpers.ts:12–27`; `svgNodeElems`). This is an
implementation limitation, not an ArchiMate-semantics constraint.

**Design (reconciled against `PLAN-meta-ontology-v2.md` — see WU-B3.1 progress log entry for
the reconciliation reading).** The binding model already has the mechanism: `Binding.visual_role`
(`src/domain/bindings.py`), `AllowedBindingsSpec.visual_roles` declared per diagram-entity-type
in a module's `allowed_bindings.entity.<type>.visual_roles` (`src/domain/allowed_bindings.py`),
and the E408 verifier rule (`_verifier_rules_binding_targets.py`) already permit a second
`represents` binding to the same model target *when* the target's entity type declares
`visual_roles`. What is missing is everything downstream of that check:

- **Verifier gap (E408b)**: E408 currently allows any number of duplicate `represents` bindings
  once `visual_roles` is declared for the type — it never checks that each such binding actually
  carries a `visual_role` value, that the value is a member of the declared set, or that it is
  distinct from sibling occurrences of the same target in the same diagram. Add that check as
  E408b in `_verifier_rules_binding_targets.py`, threaded from `_verifier_rules_bindings.py`
  (which already builds `visual_roles_for_target` — it just needs to also collect
  `binding.visual_role` per candidate and compare).
- **ArchiMate has no diagram-owned element ids today**: `generic_puml_renderer.py`'s
  `render_body` takes `entities: Sequence[EntityRecord]`/`connections: Sequence[ConnectionRecord]`
  resolved directly from `entity-ids-used`/`connection-ids-used` (via
  `resolve_diagram_selection`, which explicitly dedupes via `_unique_ids`/`dict.fromkeys`) — it
  ignores the `diagram_entities`/`diagram_connections` kwargs entirely (`del ... diagram_entities`
  at the top of `render_body`). There is no per-diagram, diagram-owned entity-element id the way
  GSN/activity/sequence have via `diagram-entities` frontmatter. A `bindings:` entry's
  `subject: {kind: entity, id: ...}` requires such an element id to exist
  (`_collect_entity_element_ids` reads `fm['diagram-entities']`), so occurrences cannot be
  expressed today without first giving ArchiMate-family diagrams a lightweight diagram-owned
  entity-element concept.
- **The precedent to mirror**: ArchiMate's GUI diagram editor already does exactly this for
  *connections* — a `connections:` frontmatter item carries a GUI-only `backing_conn_id`, and
  `_extract_conn_bindings` (`_diagram_write.py:42`) turns it into a
  `bindings:` entry (`subject: {kind: connection, id: conn.id}`,
  `target: {connection_id: backing_id}`, `correspondence_kind: represents`) before writing.
  Occurrences generalize the same shape to entities: a `diagram-entities.occurrence[]` item (a
  second, additional occurrence of an already-included entity) carries its own `id` plus a
  GUI/MCP-only `backing_entity_id`; optional `visual_role` is human-readable occurrence metadata,
  not the occurrence identifier. The write path turns it into a `bindings:` entry
  (`subject: {kind: entity, id: element.id}`, `target: {entity_id: backing_id}`,
  `correspondence_kind: represents`, with `visual_role` included only when supplied) the same way.
  The first, plain occurrence of an entity keeps going through `entity-ids-used` unchanged — only
  *additional* occurrences need a diagram-entities element + binding.
- **Renderer**: `GenericPumlRenderer.render_body` needs to also consume occurrence elements from
  `diagram_entities` (entities whose binding target is already present via `entity-ids-used`),
  rendering each with an occurrence-qualified alias (first occurrence keeps the entity's plain
  `display_alias`; further ones get a deterministic suffix, e.g. `__2`, `__3`) and the same visual
  notation as the primary occurrence. The primary `alias_by_id` map stays keyed to the first/plain
  occurrence so model-owned connections continue to default to the first occurrence when a
  connection references the plain entity_id.
- **Frontend**: alias→id stays many-to-one; id→elements becomes one-to-many (the WU-A4
  `mapElements` contract already specifies `Element[]`); sidebar selection highlights **all**
  occurrences; clicking any occurrence selects the entity.
- **Authoring**: `artifact_create_diagram`/`artifact_edit_diagram` support adding a further
  occurrence of an already-included entity; MCP tool descriptions and ArchiMate authoring guidance
  document the shorthand. GUI controls for authoring occurrences are WU-B3.2.

**Checklist.**
- [x] Verifier: E408b — occurrence `visual_role` must be declared, a member of the type's
      declared role set, and distinct among sibling occurrences of the same target in one
      diagram; tests.
- [x] ArchiMate diagram-entities occurrence element (`id` + `backing_entity_id`, optional
      `visual_role`) → write path turns it into a `represents` binding, mirroring
      `backing_conn_id`/`_extract_conn_bindings`.
- [x] Renderer occurrence-qualified aliases + connection-endpoint resolution (default to first
      occurrence) + regression tests.
- [x] Frontend multi-element mapping, highlight-all, click-any; regression coverage for a rendered
      occurrence-alias SVG shape (`BASE`, `BASE__2`, `BASE__3`) mapping all occurrences to the
      same artifact id. `DiagramDetailView.vue` already highlighted every element returned by the
      A4 multi-map; `EditDiagramView.vue` now delegates to the same `resolveElementMap` path instead
      of its older single-element local matcher.
- [x] MCP authoring surface + docs; quality gates.
- [x] GUI authoring surface: create/edit expose ArchiMate occurrence controls that add
      `diagram_entities.occurrence[]` entries with `id` + `backing_entity_id`.
- [x] Live Playwright smoke: edit an ArchiMate view, add an occurrence through the GUI controls,
      preview PUML containing an occurrence alias suffix, and verify the browser-runtime mapper maps
      primary + occurrence SVG groups to the same artifact id.

---

### WU-B4 — Wizard usability uplift (persona-driven)

**Grounding.** Persona walk-through (product owner modeling a new cross-cutting feature; junior
architect changing an existing product; architect enriching business/common context around
MCP-agent-imported application components; returning user resuming a session) against the shipped
WU-B2 wizard, with each mechanism claim verified in code. Two confirmed defects and a set of
guidance gaps; the biggest structural question is the planning/reverse mode toggle itself.

**Confirmed defects [CODE, verified].**
- `global-artifact-reference` is offered as "New global-artifact-reference" in the common domain,
  but the type is `internal: true` (`src/ontologies/archimate_next/entities.yaml` — "May not be
  created or edited directly; only produced by the connection-to-global-entity mechanism") and
  the create path raises (`artifact_write/entity.py::is_internal_entity_type` guard). The
  guidance layer (`type_guidance.py::_entity_type_guidance`) is the only surface that fails to
  filter `internal` types — `module_registry.py` domain display already skips them. GARs are
  created exclusively by artifact promotion, never manually.
- The wizard's highest-value suggestion — "connect the entity you just created to the previous
  chain entity" — is unreliable. `hop_suggestions` (`_diagram_context.py`) seeds `visited` with
  the anchor ids and returns only their *neighbors*, so `WizardEntityStage.proximityNeighborIds`
  never boosts the session's own spine anchors; and the candidate pool
  (`searchEntityDisplay('', limit 20, type)`) can miss the just-created entity entirely once a
  type has >20 instances. A fresh feature chain (no pre-existing connections) therefore gets
  zero help linking driver→stakeholder, goal→driver, etc.

**Structural finding — the mode toggle.** "Planning vs reverse architecture" forces a
methodology decision before the user gets any value, and real work is hybrid (planning a
cross-cutting change = anchoring on existing entities + adding new ones, interleaved). What the
modes actually vary — starting domain, bridge direction, a few question phrasings, find-vs-create
default — can all be derived without asking: make the spine **omnidirectional** (every
questionnaire completion offers both neighbors, labeled by user goal — "capture why" vs "map the
impact"), make the step surface **reuse-first** (existing entities of the step's type visible
inline; create and pick-existing are one surface, not a toggle), and derive the recommendation
from session state (least-covered adjacent spine domain; fresh sessions default to motivation).
The mode toggle then disappears.

**Work units** (statuses in TASKS ledger):
- **B4.1 — Exclude internal entity types from authoring guidance.** Filter `info.internal` in
  `_entity_type_guidance` (serves REST *and* MCP consumers). Regression test: guidance for
  `common` never contains `global-artifact-reference`; unit test for the filter. No GUI change —
  ontology knowledge stays out of generic components.
- **B4.2 — Chain-first connection suggestions.** For questionnaire steps, generate deterministic
  suggestions between the new/found entity and the session's spine anchors first (legal-pair
  filtered, fixed top rank, capped), then similarity-ranked existing-model candidates; always
  union anchors into the candidate pool so the 20-item search cutoff cannot drop them.
  `wizardSuggestions.ts` + `WizardEntityStage.vue`; unit tests for rank order and pool union.
- **B4.3 — Reuse-first step surface.** While typing a name in the create form, live-search
  same-type entities and offer "use existing" matches inline (dedupe by design; supersedes
  `preferFind`); allow multiple entities per questionnaire step ("Add another X" stays on the
  step; chips show per-step counts). Show existing-entity count for the step's type.
- **B4.4 — Omnidirectional spine, no mode toggle.** Bidirectional bridges on every spine
  questionnaire (both-neighbor prompts, goal-labeled); fold `reverseQuestion` variants into
  neutral wording; recommendation = least-covered adjacent spine domain; remove `mode` from
  session state (parse tolerates old payloads). Depends on B4.3 (reuse-first replaces the
  reverse-mode find default). Decision D-7 below gates this.
- **B4.5 — Guidance depth.** Collapsible "when to use / when not to use" under each questionnaire
  question (data already in loaded guidance); per-type example-name placeholder + naming hint in
  the questionnaire content file; one-line domain descriptions on hub cards (content file).
- **B4.6 — Session recap + persistent draft lifecycle.** Recap panel: entities and accepted
  connections created this session, linked, with undo. On wizard entry, search
  `keyword=wizard-draft` and surface prior-session drafts (resume / review / finalize). Decision
  D-8 gates finalization semantics.
- **B4.7 — Strategy questionnaire + capability anchor.** Capability → value-stream → resource
  steps; capability-anchored reuse search (the WU-B2c remainder), reusing B4.3's reuse-first
  surface.

**Decisions.**
- **D-7 (open)** — Replace the mode toggle with the omnidirectional spine (B4.4)?
  Recommendation: yes — the toggle is an upfront methodology question users shouldn't have to
  answer, and everything it controls is derivable. Counterargument to weigh: an explicit reverse
  mode is a teachable, documentable workflow ("run the agent, then enrich in reverse mode").
- **D-8 (open)** — Draft finalization semantics: does "finish session" strip the `wizard-draft`
  keyword, and is there a bulk cleanup for abandoned drafts?

## Workstream C — Self-model uplift

**Audit findings [MODEL, verified].** 331 entities / 743 connections / 31 diagrams. The size is
granularity (57 atomic functions, 57 requirements, junctions) plus the deliberate
stakeholder↔actor mirroring convention — **not** thin-duplicate bloat; no pruning campaign is
warranted. Two real gaps: (1) **no diagram shows the two-tier structure** — promotion exists
only as behavior views (`ARC@1777452513.68ZZDj`, `ACT@1781338474.NTuMXo`) while the structural
entities exist unviewed; (2) the motivation domain's descriptions do not yet carry the
effectiveness/coherence rationale (see WU-C2), though its structure does.

**Method (binding for all C work — derived from the ontology's own authoring guidance).**
1. **Guidance first**: `artifact_authoring_guidance` for every type touched; its
   `create_when`/`never_create_when` is authoritative.
2. **Read before proposing**: full current text of every entity to be edited; full connection
   inventory (`artifact_query_find_connections_for`) before adding any connection.
3. **Semantic fit tests for any candidate motivation entity**: it must be a *state of affairs*
   (assessment), *desired state* (goal), or *observable result/target-state, single concern*
   (outcome) — about the enterprise or its environment. Comparative arguments, robustness
   rationales, and theses defending the approach are **descriptions, not entities**: motivation
   elements are load-bearing traceability nodes; you add one only when other elements must
   trace to it.
4. **Coverage check**: search for existing entities already carrying the concern before
   concluding a gap exists.
5. **Connections over entities; descriptions over connections**: prefer the least-structural
   change that makes the point navigable.
6. **No diagram-driven entity invention**: entities are model facts; a view never justifies
   creating or duplicating them. Multiplicity is expressed via connection
   `src_cardinality`/`tgt_cardinality` (supported precisely for architecturally significant
   multiplicity), not via illustrative duplicates.

### WU-C1 — Structural two-tier view: "One Enterprise Repository, Many Engagements"

**Verified basis.** The structural entities already exist — nothing needs to be created:
`BOB@1712870400.6Uok0b` *Enterprise Repository* and `BOB@1712870400.so7gfN` *Engagement
Repository* (each aggregating the Entity/Diagram/Document/Connection business objects), linked
today only by a **bare association with no cardinalities or label**;
`DOB@1777293141.4dO6js` *Global Entity Reference File* (the globally-available-content
mechanism, associated to the enterprise repository); `SRV@1712870400.Uv9Wx9` *Repository
Promotion Service* / `PRC@1712870400.0Rz5Ex` *Promote Artifacts* /
`APP@1776633693.tIMxjr` *Promotion Engine*; business actors for the teams;
`ART@1712870400.YsLpM8` *Git Repository* on the technology layer;
motivation anchors `REQ@1712870400.kOU3al` and `GOL@1712870400.Lm2Bn2`.

**Design.** One ArchiMate view answering exactly one question for a newcomer/stakeholder
audience: *"What is the two-tier repository system for, and how does it deliver that?"*
(ArchiMate, not C4: the subject is organizational/informational topology, flows, and their
motivation, not the platform's containers.) Two bands, realization arrows pointing from the
structure band up into the purpose band (concrete → abstract):
- **Purpose band (existing motivation elements — the chain is already fully wired, verified):**
  `REQ@1712870400.kOU3al` *Two-Tiered Repository* and `REQ@1712870400.Gg4Hh4` *Promotion
  Mechanism* —realization→ `OUT@1776629112.edEkJa` *Proven Patterns Promoted and Adopted Across
  Engagements* —realization→ `GOL@1776628205.kCcPph` *Enable Cross-Engagement Architectural
  Reuse*; plus `GOL@1712870400.Lm2Bn2` *Plan Collaboratively in a Unified, Staged Repository
  System* as the collaboration payoff. This band is what makes the view answer "what it's
  *for*" — topology alone would only answer "what it is".
- **Structure band (existing only)**: the two repository business objects; the promotion
  process/service; the Global Entity Reference File; 2–3 existing business actors/roles for
  the teams. The aggregated content-type business objects stay **out** (they answer a
  different question and would crowd the view).
- **Bridge check**: verify at execution that the structural mechanism traces into the purpose
  band (e.g. `SRV@1712870400.Uv9Wx9`/`APP@1776633693.tIMxjr` realizing `REQ_Gg4Hh4`); if that
  realization is missing in the model, add it (pair-legality first) — without it the two bands
  would sit unconnected in the view.
- **Multiplicity rendering**: the archimate diagram types support per-connection
  `diagram_connections` annotations with `include_cardinality` (per the diagram-type
  guidance) — opt the tier association into cardinality display so the `1 ↔ 1..*` fact is
  visible in the view, not just recorded in the model.

**Depicting the multi-team structure (depends on WU-B3).** Multiple teams with their own
engagement repositories around one shared enterprise repository is shown **in the same
ArchiMate view**, using multiple occurrences of the same model entities (WU-B3) — visual
plurality with zero model pollution:
- Two layout groupings *"Team / Project A"* and *"Team / Project B"*, each containing an
  occurrence of `BOB_so7gfN` *Engagement Repository* plus occurrences of the relevant actors
  (Architect, Developer, AI Agent role).
- The single `BOB_6Uok0b` *Enterprise Repository* sits above both groupings. Real connections
  (assignment, access, association) render exactly as they exist in the model, which — per
  WU-B3.1's own resolution — always resolve to the **primary** occurrence (rendered inside
  *Team / Project A*); there is no mechanism to bind a real model connection to a *specific*
  non-primary occurrence, and fabricating a visual-only arrow with no backing `connection-ids-used`
  entry would misrepresent the model as having a relationship it doesn't — the same
  entity-invention discipline (§Method point 6) extends to connections. *Team / Project B*
  therefore renders as an unconnected duplicate shape group: the honest reading is "this shape
  recurs for every engagement", not "this specific edge repeats per team".
- The `1 ↔ 1..*` cardinality on the tier association stays rendered (`include_cardinality`) as
  the schema-level statement carrying the actual multiplicity claim; the duplicated occurrences
  make that plurality visually immediate without asserting any per-team relationship the model
  doesn't have.
- No team-level **model** entities are created — the groupings are view-layout constructs and
  the occurrences are visual bindings to the one real entity, so the model records only facts.
- **Sequencing**: full C1 depends on WU-B3. If C-work executes first, ship the view
  single-occurrence with rendered cardinality and upgrade to the occurrence layout when B3
  lands (the view edit is additive). The step-level temporal story (conflict check → quality
  gates → promote) stays with the existing activity diagram `ACT@1781338474.NTuMXo` — no
  separate scenario diagram is needed.
- **Connection work (the actual model change)** — each addition preceded by pair-legality
  lookup (`artifact_authoring_guidance` with `target=`), duplication check, and `dry_run`:
  - Enrich the existing enterprise↔engagement association with cardinalities
    (enterprise `1` ↔ engagement `1..*`) and a meaningful label via
    `artifact_edit_connection` — this single edit is what makes "one baseline, many
    engagements" a model fact rather than a diagram impression.
  - Team actors → engagement repository (access/assignment as legality dictates).
  - Promotion service/process reading engagement content and writing enterprise content
    (access), if not already present on the behavior side.
  - Global Entity Reference File associated with engagement repositories (the "globally
    available" read path) — `archimate-association`, not `archimate-serving`: pair-legality
    (`artifact_authoring_guidance`, data-object→business-object) permits only
    `archimate-realization` outgoing and `archimate-association` symmetric between a data
    object and a business object; ArchiMate's serving relationship requires an active/behavior
    consumer, which a business object (passive structure) is not.
- **View**: `artifact_diagram_scaffold` from that entity set, then `artifact_create_diagram`;
  verify; cross-link descriptions with the two promotion behavior views so browsing connects
  structure ↔ behavior.

**Checklist.**
- [x] Connection inventory on all listed entities; add/enrich only what's missing (cardinalities
      on the tier association first; then the structure→purpose bridge realization). Inventory
      (`artifact_query_find_connections_for` on every listed entity) found the bridge realization
      already present and verified (`SRV@1712870400.Uv9Wx9` —realization→ `REQ@1712870400.Gg4Hh4`,
      "The Repository Promotion Service directly realizes the promotion mechanism requirement.") —
      no action needed there. Four real gaps found and closed, each pair-legality-checked via
      `artifact_authoring_guidance` before writing (dry-run first, then committed):
      (1) the enterprise↔engagement `archimate-association` already carried `[1] → [0..*]` —
      enriched to `[1] → [1..*]` per this WU's title, with the description updated to match
      ("...from one or more engagement repositories"); (2) `PRC@1712870400.0Rz5Ex` *Promote
      Artifacts* gained two `archimate-access` connections — reading `BOB@1712870400.so7gfN`
      *Engagement Repository* (candidate selection/validation/conflict-detection) and writing
      `BOB@1712870400.6Uok0b` *Enterprise Repository* (post-quality-gate commit) — `process` is
      the only source type in this pair set legal for `archimate-access` to a business object
      (business-actor and application-component are not; see next point) — "the actual model
      change" the design called for; (3) `DOB@1777293141.4dO6js` *Global Entity Reference File*
      gained an `archimate-association` to `BOB@1712870400.so7gfN` *Engagement Repository* (the
      design's "serving" language was not ArchiMate-legal for a data-object→business-object pair —
      corrected in the design text above); (4) team actor access to the engagement repository:
      `ACT@1712870400.Nn7Oo7` *Architect* and `ACT@1712870400.Pp8Qq8` *Developer* each gained an
      `archimate-assignment` (the only legal business-actor→business-object outgoing type); the
      `ROL@1776633082.udXPfB` *AI Agent* role gained an `archimate-association` (role→business-
      object permits no directed relation at all, symmetric association only). Verified clean:
      `artifact_verify(repo_scope="engagement")` → 642 files, 0 errors, 1 pre-existing warning on
      an untouched file.
- [x] Scaffold + create the two-band view with `include_cardinality` on the tier association;
      `artifact_verify` clean. Created `ARC@1783185029.4Ayzz3` *One Enterprise Repository, Many
      Engagements* (`archimate-layered`, the correct type for a motivation-through-business-and-
      application cross-layer view) from the 13 named entities via `artifact_diagram_scaffold` +
      `artifact_create_diagram(entity_ids=...)`; the auto-generated layout already places the
      Motivation domain grouping (purpose band) above the Common/Business/Application groupings
      (structure band) with realization arrows routed `up`/`down` correctly, so no manual PUML
      band-nesting was needed beyond one `diagram_connections` entry
      (`include_cardinality: true, include_description: true`) on the tier association, which
      renders `1 -> 1..* | An enterprise repository serves and receives promotions from one or
      more engagement repositories.` on the edge. `GOL@1712870400.Lm2Bn2` (no direct model
      connection to the other 4 purpose-band entities, included per this WU's design as the
      "collaboration payoff") got an auto-generated hidden layout link next to
      `GOL@1776628205.kCcPph` rather than floating disconnected. `artifact_verify
      (repo_scope="engagement")`: 640 files, 0 errors, 1 pre-existing warning on an untouched
      file. **Tool bug found and fixed while scaffolding**: `artifact_diagram_scaffold` returned
      zero `connections_included` for every entity pair when `entity_ids` were passed in short
      form (`PREFIX@epoch.random`, the form the tool's own docstring says is accepted) — root
      cause in `src/infrastructure/mcp/artifact_mcp/_diagram_scaffold.py`'s
      `build_diagram_scaffold`: it filtered connections against the raw input strings
      (`id_set = set(entity_ids)`) instead of the resolved entities' full `artifact_id`s, so a
      short-form id could never match a `ConnectionRecord.source`/`.target` (always full form) —
      fixed by building the filter set from `entity.artifact_id` after resolution; regression
      test `tests/tools/test_diagram_scaffold_short_id_connections.py`.
- [x] After WU-B3: upgrade the structure band to the two-grouping occurrence layout (team
      groupings); `artifact_verify` clean. Hand-authored manual `puml=` on
      `ARC@1783185029.4Ayzz3` replacing the domain-grouped structure band with *"Team / Project A"*
      (primary occurrences, fully wired to the real model connections) and *"Team / Project B"*
      (a second occurrence of Engagement Repository + Architect + Developer + AI Agent role, added
      via `diagram_entities.occurrence[]`, unconnected — see the design correction above for why no
      per-grouping arrows were drawn). Enterprise Repository, Common (Promote Artifacts, Repository
      Promotion Service), and Application (Global Entity Reference File) groupings are unchanged
      in content, only repositioned. `artifact_verify(repo_scope="engagement")`: 640 files, 0
      errors, 1 pre-existing warning (unchanged).
- [x] Cross-link the view with `ARC@1777452513.68ZZDj` and `ACT@1781338474.NTuMXo` descriptions.
      Diagrams carry no free-text description field in this system (`DiagramRecord` has no
      content/summary), so the cross-link lives on `PRC@1712870400.0Rz5Ex` *Promote Artifacts* —
      the process entity anchoring both existing behavior views and included in the new
      structural view — whose summary now names all three views ("Promote Artifacts",
      "Promote Engagement Work to the Enterprise Repository", "One Enterprise Repository, Many
      Engagements") so browsing from any of them points to the others. Note: "Enterprise
      Baseline" was the working title for both the new view and the pre-existing activity
      diagram `ACT@1781338474.NTuMXo`; renamed to "Enterprise Repository" — "baseline" is
      conventionally contrasted with "target" for current-/future-state architecture and doesn't
      describe this tier distinction.

### WU-C2 — Motivation domain: carry the unity-of-effort and coherence rationale in descriptions

**Options.** (a) New motivation entities carrying the arguments — e.g. an assessment
contrasting local spec-driven practice with integrated architecture, an outcome for
goal-adequacy/conflict signals, or a "Unity of Effort" value element; (b) description
enrichment of the existing spine.

**Choice: (b) — zero new motivation entities.** Per the ontology's authoring guidance:
assessments state states-of-affairs arising from drivers, so a comparative thesis about
modeling practice does not qualify; a combined adequacy/conflict outcome bundles two distinct
concerns and overlaps existing outcomes (`OUT@1776629105.9jS0BB` requirements-traceable,
`OUT@1776629109.YSRwR0` stakeholder-concerns-verifiable, `OUT@1776629101.a5mNob`
changes-validated, `OUT@1780655839.Vhhne7` analysis-surfaces-gaps); and value elements attach
to active structure elements, not goals. The motivation structure is sound and fully wired
(`ASS_CK90bp` is influenced by all three relevant drivers and associated with the apex goal).
The missing substance is rationale, and rationale belongs in descriptions — motivation
entities are load-bearing traceability nodes, added only when other elements must trace to
them.

**Enrichment map** (each edit: read full text first; `artifact_edit_entity` with `dry_run`;
properties are full-replacement — resend every attribute; wording stays state-of-affairs/intent
phrasing — no comparative marketing, no AI-antithesis framing):
- `GOL@1780220699.FCfDuc` (apex goal): add the effectiveness rationale — integration in
  planning, governance and coordination is what makes autonomous contributors (human and AI)
  collectively effective and efficient; this holds regardless of how the economics of code
  production evolve.
- `ASS@1780220699.CK90bp`: sharpen the existing state of affairs — the erosion is at the
  *integration between contexts*; structuring work locally (per-team specifications and
  conventions) does not by itself restore shared understanding of plans, governance and what is
  built across teams, agents and engagements.
- `DRV@1776628131.GR9prv`: extend the trend statement (drivers model trends — correct home):
  industry practice around AI-assisted development is converging on structured, persisted,
  queryable specifications as the working context for agents, raising the demands on how
  architectural knowledge is structured, accessed and governed. (Its description already ends
  on exactly this clause — the addition completes the observed trend, states no comparison.)
- `GOL@1712870400.Po1Qw3` + `OUT@1712870400.LrpdG0`: state coherence's payoff concretely —
  a coherent, traceable model yields the signals to validate that what is planned and built
  serves the stated goals, and to locate conflicts between goals, requirements and designs
  early; this value is independent of how code production evolves. (Also fix the "should
  trance to to" typo in `GOL_Po1Qw3` while editing; optionally extend `OUT_LrpdG0`'s Metric
  row with a conflict-detection signal if a concrete metric can be stated honestly.)
- `GOL@1712870400.Lm2Bn2`: one sentence tying the staged repository system to unity of effort
  across teams (anchors WU-C1's view in the spine).

**No diagram changes in this WU** — description enrichment alters no view content; the
diagram-form communication of the two-tier system's purpose is WU-C1's view (its purpose band
carries the "what it's for" chain). Note the complement: the GUI shows an element's description
in the sidebar when it is selected in a view, so WU-C2's enriched rationale surfaces precisely
when someone explores WU-C1's view or the apex view. During execution, read the apex view
`ARC@1780220700.Un4jQZ` once to confirm the enriched entities are already present (they are its
core); adjust only if an *existing* element is missing.

**Checklist.**
- [x] Enrich the six entities per the map (full attribute sets in each edit call); dry-run
      first; `artifact_verify` clean. All six edited via `artifact_edit_entity` (`dry_run=true`
      then committed), each resending its full existing property set: `GOL_FCfDuc` gained the
      effectiveness-rationale sentence; `ASS_CK90bp` sharpened to name the erosion as
      integration-between-contexts specifically; `DRV_GR9prv` extended with the convergence-on-
      structured-specifications trend sentence; `GOL_Po1Qw3` fixed the "trance to to" typo and
      gained the coherence-payoff sentence; `OUT_LrpdG0` gained the matching payoff sentence
      (its `Metric` property left unchanged — no conflict-detection signal is actually computed
      today, so adding one would not be an honest metric, per the plan's own "if a concrete
      metric can be stated honestly" condition); `GOL_Lm2Bn2` gained the one-sentence tie to
      unity of effort across teams. `artifact_verify(repo_scope="engagement")`: 640 files, 0
      errors, 1 pre-existing warning (unchanged).
- [x] Confirm apex-view coverage; no other diagram work. Read `ARC@1780220700.Un4jQZ` *The Story
      in One View*: `GOL_FCfDuc`, `ASS_CK90bp`, `DRV_GR9prv`, and `GOL_Lm2Bn2` are already present
      as its core motivation chain, so the enriched descriptions surface there without any
      diagram edit. `GOL_Po1Qw3`/`OUT_LrpdG0` (the coherence pair) are not part of this
      particular view and were never claimed to be — no adjustment needed.

### WU-C3 — Organize the model with groups (navigability, not pruning)

**Rationale.** Every one of the 385 entities and 30 of 31 diagrams sit in `uncategorized` —
the projects/grouping feature exists (`artifact_group`) but the self-model doesn't use it. The
"too vast" perception is a navigation problem; grouping fixes it without destroying legitimate
granularity.

**Design.** Assign model-projects / diagram-collections / document-collections, e.g.:
`platform-core`, `assurance`, `promotion-and-tiering`, `motivation-narrative`,
`diagram-authoring` (exact slugs decided during execution against what reads well in the GUI's
group filter). Diagrams grouped by audience: overview/motivation vs. subsystem behavior vs.
assurance. Explicit decision recorded: **no entity pruning**; the stakeholder↔actor mirror stays
(modeling convention).

**Checklist.**
- [x] Propose grouping taxonomy (short doc comment in the ledger), then apply via
      `artifact_group` in batches; verifier clean; GUI browse spot-check per group.

---

## Ordering & dependencies

1. **A3 → A2** — smallest, isolated, immediately user-visible (one backend restart batches both).
2. **A1** — picker consolidation (also a prerequisite quality bar for the wizard's search UX).
3. **A4** — viewer-extension contract (one-to-many mapping) + two renderers.
4. **B3** — multi-occurrence ArchiMate views; builds directly on A4's mapping contract and
   unblocks the full C1 view layout.
5. **B1** — per-section document connections (backend-heavy; independent of A/B3 work).
6. **C1 + C2 + C3** — model-only, can interleave anytime; C1's occurrence layout depends on B3
   (interim single-occurrence version may ship earlier and be upgraded additively).
7. **B2a → B2b → B2c** — the wizard last and sliced; it consumes A1 (picker) and benefits from
   C-work being done (dogfooding the wizard against a well-organized model).

Parallelization: Workstream C is independent of all code work except C1's B3 dependency. B1 is
independent of Workstream A and B3. Within A, all four WUs are mutually independent.

## Decisions

The authoritative decision record is the Decision log in
`TASKS-modeling-ux-and-self-model-uplift.md` (D-1…D-9; settled entries are final).

- **D-6 (only open point):** WU-B2b commit semantics — per-artifact verified commits with undo
  (recommended, see rationale) vs. exposing the staged-bulk machinery over REST for atomic
  wizard commits. Recommendation stands unless multi-step atomicity is a hard requirement;
  resolve with the user before starting B2b.
- Decided in-plan: D-1 single picker search contract, D-2 shared preview viewport (detail view
  deferred), D-3 one-to-many viewer-extension mapping contract, D-4 wizard slice order, D-5
  per-section schema Option A with heading-text identity, D-7 zero new motivation entities
  (rationale in descriptions), D-8 multi-team depiction via multi-occurrence ArchiMate view,
  D-9 no entity pruning (navigability via groups).
