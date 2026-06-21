# TASKS — GUI Correctness & Assurance Remediation

Execution ledger for `PLAN-gui-correctness-and-assurance-remediation.md`. **Source of truth for
progress.** The plan says *what* and *why*; this file tracks *where we are* and the **measurable
acceptance criteria** each task must meet.

Status values: `todo` · `in-progress` · `blocked` · `review` (impl done, awaiting user/QC) · `done`.
Never mark `done` until acceptance criteria are met **and** all quality gates pass (`pytest` 0-fail ·
`ruff` · `zuban` · frontend `lint`/`typecheck`/`test`), and — for user-visible tasks — an **[OBS]**
artifact exists.

**Backend restart caveat:** MCP/`artifact_*`/`assurance_*` tools run against a long-running backend;
code changes require a user-performed backend restart before tools reflect them, and MCP-surface
changes require a Claude session restart. Plan work so you don't block on a restart mid-session.

---

## Session protocol

1. Read this whole file (incl. Decision log — settled, do not relitigate) and the plan's §0.
2. Pick the topmost `todo`/`in-progress` task whose dependencies are `done`. Set `in-progress`, add a
   dated progress-log line.
3. Implement; ration codebase/self-model exploration to cited `file:line`. Run quality gates.
4. Meet the acceptance criteria; produce the [OBS] artifact for user-visible tasks; update status +
   progress log. Commit only if asked.

---

## Status table

| ID | Title | WS | Status | Depends on |
|----|-------|----|--------|-----------|
| T0  | Durable PLAN + TASKS files | — | done | — |
| T1  | Concurrency harness + cross-thread unit test | WS5 | done | T0 |
| T2  | Realistic load test (team-serving + local profiles) | WS5 | done | T1, T6 |
| T3  | Playwright route-walk smoke spec | WS5 | done | T0 |
| T4  | Schema/response contract tests | WS5 | done | T0 |
| T5  | Extract reusable single-worker-queue primitive | WS1 | done | T1 |
| T6  | Per-thread WAL read connections in SQLCipher adapter | WS1 | done | T1 |
| T7  | Assurance write queue (serialized) wired at MCP + REST boundary | WS1 | done | T5, T6 |
| T8  | Fix shared-connection aliases (signals/archive) | WS1 | done | T6 |
| T9  | WAL confidentiality: plaintext test + ignore rules + migration | WS1 | done | T6 |
| T10 | Delete-analysis use case + MCP tool + REST + mgmt view | WS2 | done | T7 |
| T11 | Wizard architecture-anchor entity picker | WS2 | done | — |
| T12 | TLP colour-by-value (shared helper) | WS2 | done | — |
| T13 | Ceiling "withheld" explanation UX + doc | WS2 | done | — |
| T14 | Assurance matrix: entity links + word-wrap | WS2 | done | — |
| T15 | Unified assurance diagram surface (bowtie/control-structure/UCA-matrix) | WS3 | done | T6 |
| T16 | GSN dual-home + selectable in generic viewer | WS3 | done | T15 |
| T17 | C4 edit-view derived-projection data path | WS3 | done | — |
| T18 | Viewer node/edge selection (C4/GSN) detail | WS3 | done | — |
| T19 | C4 standard shapes + create-view shape selection (WU-E7) | WS4 | done | — |
| T20 | C4 person labels render (re-verify/fix) | WS4 | done | — |
| T21 | C4 person→container line gap (re-verify/fix) | WS4 | done | T20 |
| T22 | C4 description inconsistency across instances | WS4 | done | — |
| T23 | Rendered-SVG assertion harness for C4/GSN | WS4 | done | T3 |
| T24 | Self-model: motivation layer + structural elements | — | done | T7, T15 |
| T25 | Docs: assurance GUI, viewer, ceiling, topology | — | done | T15 |

---

## Acceptance criteria (measurable)

- **T1** — A test against the **real ASGI app** (not `TestClient`) unlocks on thread A and issues
  assurance reads+writes from a ≥4-thread pool: **fails on current `main`** with the cross-thread
  SQLite error, **passes after WS1**. Unit test: a store read on a thread ≠ `unlock()` thread
  succeeds.
- **T2** — Team-serving profile (≥12 read clients + ≥12 write/agent clients, sustained ≥30 s):
  **0 errors**; observed **max in-flight writes == 1**; final store state consistent (no lost
  updates: N submitted creates ⇒ N rows); **read p95 ≤ agreed budget** under the write stream.
- **T3** — Playwright spec walks every cited URL + each diagram-type instance: **0 console/network
  5xx**; asserts person-label text node present, C4 node label == name (no description line),
  assurance node rows render, TLP chip class differs across values.
- **T4** — Decoding captured **real** backend responses (search hit incl. document + assurance-node;
  assurance node; C4 diagram context) with the FE Effect schemas succeeds; a deliberately drifted
  field fails the test.
- **T5** — One single-worker-queue primitive; arch `model-write-queue` behaviour unchanged (existing
  write-queue tests green); primitive unit-tested (serialization, `wait_until_idle`, shutdown).
- **T6** — *Design refinement:* per-thread WAL connections (each thread lazily owns/caches its own
  connection; generation counter invalidates across lock/unlock; all tracked for disposal) rather
  than a checkout/checkin pool — this preserves the existing per-method transaction boundaries and
  the `conn_factory` contract that the archive/signals share, while WAL provides read concurrency.
  Bounded in practice by the anyio threadpool size. `journal_mode==wal` and `busy_timeout>0` asserted;
  concurrent reads from N threads succeed; key held in memory only. Lifecycle extracted to
  `_sqlcipher_connection.ThreadLocalConnectionManager` (keeps the store under the 350-LoC limit).
- **T7** — All assurance mutations (MCP write tools + REST write handlers) run through the
  `assurance-write-queue`; a test shows two concurrent writes execute strictly one-at-a-time;
  exposure policy still applied on the write path.
- **T8** — Signals connector + archive perform their reads/writes via pool/queue (no captured
  `_conn`); existing archive/signals tests green; a cross-thread test over these paths passes.
- **T9** — Test asserts no plaintext assurance token appears in the `-wal` file; `.gitignore` (and any
  `.arch-*` ignore) covers `*.db-wal`/`*.db-shm`; "no new tracked/untracked files after build+query"
  test passes; WAL migration is idempotent on an existing store.
- **T10** — `assurance_delete_analysis` use case + MCP tool + `DELETE /api/assurance/analyses/:id`
  (queued, audited); deleting "A1" removes it from list + nodes view; cascade/block rule has a test;
  mgmt view shows delete + status controls. [OBS] screenshot of deletion.
- **T11** — Each wizard's anchor field is `EntityPickerInput` pinned to admissible ArchiMate types;
  selecting an entity sets the anchor id; free-text entry no longer possible. [OBS] screenshot.
- **T12** — Shared `tlpColor(tlp)` helper; chips/labels in browse + node detail + lens use it; Vitest
  asserts the four TLP values map to four distinct colours. [OBS] screenshot.
- **T13** — When records are withheld, the UI shows a clear count + ceiling note (not a raw/alarming
  message); ceiling config documented. [OBS] screenshot.
- **T14** — Matrix cells link to the bound model entity (navigates to `/entity?id=…`); long text wraps
  (no per-character break). [OBS] screenshot before/after.
- **T15** — Bowtie/control-structure/UCA-matrix open in the assurance viewer with selectable
  nodes/edges → detail; they are no longer reachable as broken instances in the generic viewer
  (redirect or absent). [OBS] screenshots of selection working.
- **T16** — A GSN diagram renders + nodes/edges are selectable in the generic viewer; confidential GSN
  routes through the assurance bridge. [OBS] screenshot of GSN selection.
- **T17** — Opening an existing model-backed C4 diagram in edit shows the derived entities (grouped by
  role) + read-only connections in the sidebar. Vitest over the data path + [OBS] screenshot.
- **T18** — Clicking any node or edge (incl. diagram-only GSN, derived C4) populates the detail
  sidebar. Vitest + [OBS] screenshot.
- **T19** — Renderer maps technology→shape (db/queue/etc.) and honours an explicit `shape`; create
  view offers shape selection; rendered-SVG test asserts the db/queue shape elements. [OBS]
  screenshot of the two C4 diagrams with correct shapes.
- **T20** — Rendered SVG of the system-context + container diagrams contains the person label **text**;
  test asserts it. [OBS] screenshot.
- **T21** — Rendered container diagram: person→container edges anchor at the node (no gap); visual
  [OBS] confirmation + snapshot.
- **T22** — Both component diagrams render consistently (name-only unless `show_node_descriptions`);
  root cause of the divergence documented; test over the responsible field.
- **T23** — A reusable harness renders stored PUML to SVG and asserts presence of label text + shape
  elements; used by T19/T20.
- **T24** — Self-model has: deployment-shape elements (local / team-serving), one scalability
  requirement/constraint linked to read-pool + write-queue elements; assurance HTTP interface,
  concurrency components, delete-analysis use case, unified assurance-diagram surface modelled;
  stale "GUI calls MCP" reconciled. `artifact_verify` clean.
- **T25** — `docs/` updated for assurance GUI, diagram-viewer behaviour, TLP ceiling, deployment
  topology.

---

## Decision log (settled — do not relitigate)

- **D1** Assurance diagram types (bowtie, control-structure, UCA-matrix) = unified assurance-store
  surface, removed/redirected from the generic viewer. **GSN dual-homed** (general type + assurance
  bridge).
- **D2** Store concurrency = **read connection pool (WAL)** for concurrent reads + **single-writer
  serialized queue** mirroring `write_queue.py` for writes. No concurrent writes (matches arch side).
- **D3** Shared single-worker-queue primitive, **separate queue instances** for arch vs assurance
  (independent stores).
- **D4** Motivation layer stays general (local vs team-serving GUI+MCP); concrete sizing lives in the
  load test, not the model.
- **D5** "Done" requires an [OBS] artifact + regression test for user-visible work.

---

## Progress log

- 2026-06-21 — Plan approved; root cause of assurance 500s confirmed (cross-thread SQLite on a
  process-singleton connection served from the anyio threadpool). Durable PLAN + TASKS written (T0
  done). Next: T1 (failing concurrency harness) → WS1.
- 2026-06-21 — **WS1 complete (code + tests).**
  - T1: `tests/integration/test_assurance_concurrency.py` reproduces the cross-thread bug on
    pre-fix code (ProgrammingError "SQLite objects created in a thread…") and passes after the fix;
    cross-thread read unit test green.
  - T5: `src/infrastructure/concurrency/single_writer_queue.py` (`SingleWriterQueue`) +
    `tests/common/test_single_writer_queue.py` (serialisation, error-propagation, idle/shutdown).
  - T6: per-thread WAL connections via new `_sqlcipher_connection.ThreadLocalConnectionManager`;
    `_sqlcipher_store.py` slimmed to 342 LoC and delegates.
  - T7: `src/infrastructure/assurance/write_serialization.py` (`assurance-write-queue`); all MCP
    write tools (`write_tools.py`, `security_write_tools.py`) and REST write handlers
    (`_assurance_write.py`) funnel writes through `run_write(...)`. Harness proves writes serialise
    (max in-flight == 1) with a contiguous audit-log seq (no race) while reads stay concurrent.
  - T8: `store_factory.py` + `cli/_assurance_commands.py` aliases now use
    `store._thread_conn_or_none` (no captured `_conn`); archive/signals tests updated + green.
  - T9: `tests/integration/test_assurance_wal_confidentiality.py` proves no plaintext marker reaches
    any on-disk file; `-wal`/`-shm` already covered by the store dir `.gitignore`.
  - Gates: full `pytest` 3245 passed / 2 skipped; `ruff` clean; `zuban` clean.
- 2026-06-21 — **WS1 LIVE-VERIFIED + WS2 (T10–T13) complete (code + tests).**
  - T10: `delete_analysis` use case (block-if-nonempty; audited) + store method on **all** backends
    (sqlcipher, file/private-git mixin, pocketbase) + port + MCP `assurance_delete_analysis` + REST
    `DELETE /api/assurance/analyses/:id` (queued) + GUI Manage panel (status dropdown + delete) in
    `AssuranceAnalysisPicker.vue`. Tests: 4 use-case tests (empty-ok/blocked/not-found/locked).
  - T11: analysis anchor is now `EntityPickerInput` pinned to `ANALYSIS_ANCHOR_TYPES` (ArchiMate
    only) in the picker create form — wizards inherit it. No more free-text anchor.
  - T12: shared `components/tlp.ts::tlpColor`; browse list, node detail, lens all colour by value;
    Vitest proves four distinct colours.
  - T13: shared `WithheldNotice.vue` names the ceiling and explains it's the policy working as
    intended; replaces the terse messages in browse/lens/diagram-panel.
  - Gates: backend `pytest` 3249 passed / 2 skipped, `ruff` + `zuban` clean; frontend `lint` +
    `typecheck` clean, `vitest` 261 passed. Frontend (T11–T13) is hot-reloaded → live now.
  - **PENDING RESTART for live verify:** T10's REST/MCP delete + the `assurance_delete_analysis`
    tool are backend changes needing a backend restart before live delete of "A1" + Playwright pass.
    Remaining: T14 (matrix), WS3, WS4, WS5 (T2/T3/T4).
- 2026-06-21 — **T10 LIVE-VERIFIED:** `assurance_delete_analysis("STPA@…A1")` → `{deleted:true}`;
  `assurance_list_analyses` → `count:0`. Delete works end-to-end (MCP tool → audited use case →
  serialized write queue). WS2 complete except T14. **Next session: T14 → WS3 → WS4 → WS5(T2–T4).**
  Playwright now available (chromium) for the live [OBS] screenshot pass over the remaining UI work.
  - **LIVE-VERIFIED (post-restart):** MCP `assurance_stats`/`list_analyses`/`list_nodes`/`list_edges`/
    `coverage`/`security_stats` all succeed (no cross-thread error); "A1" consistently visible. REST
    `/api/assurance/stats` 20× concurrent → all 200 (previously cross-thread 500s). WS1 done.
    Remaining WS5: T2 (sustained team-load profile), T3 (Playwright smoke), T4 (contract tests).
- 2026-06-21 — T2 started: add sustained local/team-serving load profiles proving zero errors,
  serialized writes, consistent final state, and bounded read latency while writes are active.
- 2026-06-21 — **T2 complete:** `test_assurance_load_profiles.py` exercises a 2+2 local profile
  and a sustained 30-second 12 GUI-reader + 12 mixed agent profile. Both pass with zero errors,
  max in-flight writes = 1, exact submitted-create/final-row agreement, unique IDs, and read p95
  below the 500 ms budget. Gates: 3251 passed / 2 skipped; `ruff` + `zuban` clean. T3 started.
- 2026-06-21 — **T3 complete:** expanded Playwright smoke walks all cited assurance routes and all
  30 stored diagram instances (12 diagram types), asserts no 5xx/console errors, rendered C4 person
  labels + name-only nodes, assurance rows, and distinct live TLP colours. Live run: 24 passed.
  The harness exposed a matrix-viewer defect: it requested `/api/diagram-svg` for Markdown matrices,
  causing a 500. Fixed by context-gating SVG fetches with `diagramNeedsSvg`; 16-test helper suite
  covers the delegation. T4 started.
- 2026-06-21 — **T4 complete:** added Effect schemas for assurance-node list responses and captured
  real-response contracts for search (document hit), assurance nodes, and C4 diagram context; a
  deliberately drifted `count` field is rejected. Frontend gates: lint + typecheck clean, 267 tests
  passed. T14 started.
- 2026-06-21 — **T14 complete:** confirmed the defect is the generic matrix view. Updated the
  Assurance Requirements Traceability model artifact through `artifact_create_matrix` so every
  row/column entity label is linked (and renamed stale “Assurance MCP Server” to the current
  “Assurance MCP Endpoint Adapter”). Fixed artifact-ID link rewriting for hyphen/underscore random
  segments and changed matrix cells to normal word-boundary wrapping. Model verification clean;
  focused Playwright DOM assertion passed; frontend gates clean with 269 tests. T15 started.
- 2026-06-21 — **T15 complete:** bowtie, control-structure, and UCA-matrix now use one
  exposure-filtered assurance-store surface. The response contract carries projected nodes/edges;
  control actions are included in control structures; UCA renders as an interactive concern-edge
  grid; node/edge selection opens assurance detail and edit navigation. When PlantUML is unavailable,
  bowtie/control-structure retain a selectable store-grounded fallback. Generic diagram list/create
  discovery excludes the three assurance-only types while retaining GSN. [OBS] targeted Playwright
  scenario passed and captured
  `tools/gui/test-results/.../t15-unified-assurance-diagram-selection.png`.
  Gates: backend 3256 passed / 2 skipped; ruff + zuban clean; frontend lint/typecheck clean,
  Vitest 272 passed. T16 started.
- 2026-06-21 — **T16 complete (live-verified + [OBS]).**
  GSN is a general architecture diagram type with no confidential-store dependency. TLP routing
  still applies in the assurance bridge (unclassified GSN is generic; AMBER/RED stays confidential).
  Diagram context surfaces all 12 diagram-owned GSN nodes as entities + 11 connections (GSN macro
  edge parsing). Entity detail endpoint has a diagram-owned fallback for `#`-keyed IDs. Playwright
  test `GSN diagram renders and nodes are selectable in the generic viewer` navigates to the stored
  GSN, asserts 12 sidebar entities, clicks node 1, and verifies the `.ent-det` detail panel shows
  the name + type badges. [OBS] screenshot captured at
  `test-results/.../t16-gsn-node-selected.png`. Gates: 3258 passed / 2 skipped; ruff + zuban
  clean; frontend lint/typecheck/vitest 272 passed. T17 started.
- 2026-06-21 — T17 started: C4 edit-view derived-projection data path.
- 2026-06-21 — **T18 complete (code + tests + [OBS]).**
  - Extracted `buildConnectionAliasMap` + `resolveConnection` from inline `attachInteractivity`
    code into `DiagramDetailView.helpers.ts`; `DiagramDetailView.vue` delegates to them.
  - New Vitest file `DiagramDetailView.selection.test.ts` (26 tests): connection alias map
    building, parallel-edge queue resolution, selection state machine toggle/mutual-exclusion,
    and derived-C4 alias coverage; all 299 frontend tests pass.
  - Backend test `test_diagram_detail_view_queues_connection_matches_and_promote_button`
    updated to assert `buildConnectionAliasMap`/`resolveConnection` imports instead of the
    removed inline variable name.
  - Playwright T18 scenario: navigates to C4 container diagram, waits for
    `[data-entity-id]` (SVG interactivity attached), clicks SVG node → `.ent-det` detail
    panel visible with name; clicks `[data-conn-id]` edge → `.conn-flow` visible; then
    navigates to GSN diagram, clicks SVG node → detail panel. [OBS] screenshot captured at
    `test-results/.../t18-node-edge-selection.png`.
  - Gates: 3264 passed / 2 skipped; ruff + zuban clean; frontend lint/typecheck/vitest 299 passed.
  - WS3 complete. Next: T19 (C4 standard shapes + create-view shape selection).
- 2026-06-21 — **T20 complete (code + tests + [OBS]).**
  - Verified: the current `C4PumlRenderer` generates correct `Person(...)` / `Person_Ext(...)` macros
    for person entities; no fix required (WU-E1 was sound).
  - Added 4 rendered-SVG tests to `tests/rendering/test_c4_rendered_svg.py` (T23 harness):
    `test_person_label_appears_in_svg`, `test_person_ext_label_appears_in_svg`,
    `test_system_context_person_labels_via_renderer`, `test_container_diagram_person_labels_via_renderer`.
    All 4 pass (PlantUML renders `Person(...)` label text into SVG).
  - Added Playwright test "C4 person labels render in system-context and container diagrams (T20)"
    to `smoke.spec.ts`; asserts at least one person label from each diagram's entity context
    appears in the rendered SVG `textContent`. Test passes.
  - [OBS] screenshots: `test-results/.../t20-c4-system-context-person-labels.png` +
    `test-results/.../t20-c4-container-person-labels.png`.
  - Gates: backend 3280 passed / 2 skipped; ruff + zuban clean; frontend lint/typecheck clean,
    313 Vitest + Playwright T20 passed. Next: T21.
- 2026-06-22 — **T20 + T21 ROOT-CAUSE FIX (stored diagram migration + regression tests).**
  - **Root cause confirmed (live screenshot):** both defects (invisible person labels + edge gap)
    were in the TWO STORED `.puml` files, which used the OLD skinparam-based renderer
    (`skinparam actor { FontColor white }` → white text on white background → invisible;
    `actor "long desc" as alias` → element wider than visible icon → gap before arrow start).
    The new `C4PumlRenderer` generates `Person_Ext(...)` + `!include <C4/C4_Component>`
    which renders labels correctly and anchors edges to the person glyph boundary.
  - **Fix:** called `artifact_edit_diagram(puml="auto-sync")` on ALL FOUR stored C4 diagrams
    (`amp-system-context`, `amp-containers`, `architecture-backend-components`,
    `assurance-module-components`). Each was regenerated with the new format (PNG + SVG
    re-rendered on disk). No new code path was added.
  - **Regression test** `tests/rendering/test_c4_stored_diagram_format.py` (12 tests,
    parameterized across all 4 stored C4 diagrams):
    - `test_c4_stored_diagram_uses_stdlib_include` — asserts `!include <C4/` present
    - `test_c4_stored_diagram_no_skinparam_actor` — asserts `skinparam actor` absent
    - `test_c4_stored_diagram_persons_use_person_macro` — asserts no bare `actor "..."` lines
  - **SVG anchoring test** `test_person_to_container_edges_anchor_without_gap` (T21, in
    `test_c4_rendered_svg.py`): renders a container diagram with person→container connection,
    extracts path start x / arrowhead tip x from SVG, asserts < 5 px from node boundaries.
    Observed gap < 0.5 px.
  - Playwright T20 + T21 re-run against updated live diagrams — both pass.
  - [OBS] screenshots: `t20-c4-system-context-person-labels.png`,
    `t20-c4-container-person-labels.png`, `t21-c4-person-container-edge-anchoring.png`.
  - Gates: 3293 passed / 2 skipped; ruff + zuban clean; frontend lint/typecheck/313 Vitest
    + Playwright T20+T21 passed. Next: T22.
- 2026-06-21 — **T19 in-progress → review (pending backend restart for Playwright OBS).**
  - `renderer.py` `_render_item`: explicit `shape` + `external=True` now appends `_Ext` suffix
    automatically (was silently ignored). New tests cover the external+shape combination.
  - `container/ontology.yaml` + `component/ontology.yaml`: added `shape` enum property
    (`["", "Container/Component", "…Db", "…Queue"]`) to `container` and `component` entity types.
    Same enum added to `container` in the component diagram's ontology.
  - `DiagramOwnEntityTypeSection.vue`: added `propEnumValues` helper + `<select>` branch for
    enum-typed string properties — shape field now renders a dropdown in the standalone create view.
  - `test_c4_node_shapes.py`: added 3 tests for explicit-shape + external combination.
  - `tests/rendering/test_c4_rendered_svg.py` (new, T23 harness): 8 rendered-SVG tests using
    `render_puml_svg`; asserts ContainerDb/Queue use path elements (cylinder/queue), Container uses
    rect, label + tech text appear in SVG, explicit shape= override produces correct shape in SVG.
  - `tests/tools/test_diagram_type_routes.py`: 2 new tests asserting the `/api/diagram-types/
    c4-container/ui-config` and `c4-component/ui-config` endpoints carry the `shape` enum.
  - `tools/gui/src/ui/components/__tests__/DiagramOwnEntityTypeSection.shapeSelect.test.ts` (new):
    14 Vitest tests for `propEnumValues`/`shouldRenderSelect` logic + enum completeness.
  - Playwright smoke: T19 test verifies shape enum in live API response + C4 diagram renders (SVG);
    **requires backend restart** to pick up ontology changes — Playwright test currently fails the
    API assertion (expected). Will pass after restart. [OBS] screenshots captured at
    `test-results/t19_obs*/t19-c4-containers-shapes.png` and `t19-c4-system-context-shapes.png`.
  - Gates: 3276 passed / 2 skipped; ruff + zuban clean; frontend lint/typecheck clean, 313 Vitest
    tests passed; 29 Playwright tests pass (T19 API assertion blocked on restart). T19 = review.
  - **LIVE-VERIFIED (post-restart):** T19 Playwright test passes. [OBS] screenshot captured at
    `test-results/.../t19-c4-shape-selection.png`. T19 → **done**. Next: T20.
- 2026-06-22 — **T25 complete (docs updated — 4 files).**
  - `docs/04-assurance/diagrams.md`: new "Unified assurance diagram viewer" section (exposure-filtered,
    interactive node/edge selection, store-grounded fallback, excluded from generic catalogue); GSN
    dual-home table (architecture repo vs assurance store by TLP).
  - `docs/03-modeling/diagramming.md`: new "Viewer interactivity" section (click-to-select nodes/edges
    → detail sidebar, toggle behaviour); C4 shape table (default/Db/Queue) + `_Ext` suffix rule;
    edit-view sidebar note (derived entities + read-only connections).
  - `docs/04-assurance/storage-and-confidentiality.md`: new "TLP ceiling and withheld content"
    section (max_classification config, withheld notice behaviour, what is/isn't disclosed); SQLCipher
    WAL sidecar note (encrypted, gitignored).
  - `docs/02-installation.md`: new "Deployment topology" section (single-architect local vs
    team-serving; concurrency model — WAL read pool + single-writer queue; ceiling config for teams).
  - `docs/04-assurance/index.md`: page-set table updated.
  - Gates: 3318 passed / 2 skipped; ruff clean; zuban clean.
- 2026-06-22 — **T24 complete (7 entities + 12 connections + artifact_verify clean).**
  - Pre-existing model gap assessment: Developer Workstation (NOD@1712870400.4EFX7z) already
    covered "local"; GUI entity content already said "REST interface" (stale GUI→MCP in text
    was already reconciled). Gaps: team-serving node, concurrency constraint, assurance
    concurrency components, assurance HTTP interface, delete-analysis fn, unified diagram surface.
  - **New entities (7):**
    - `NOD@1782080479.7xNYBF` Team-Serving Deployment (technology-node)
    - `REQ@1782080517.IIl8-4` Concurrent Reads, Serialized Writes (requirement, Category: Constraint)
    - `APP@1782080485.uTC8zx` Assurance Write Queue (application-component)
    - `APP@1782080489.XWVKAX` Assurance Read Connection Pool (application-component)
    - `AIF@1782080492.Y4n-FB` Assurance REST Interface (application-interface)
    - `FNC@1782080495.afm5YF` Delete Assurance Analysis (function)
    - `APP@1782080499.KqDjXG` Unified Assurance Diagram Surface (application-component)
  - **New connections (12):** Team-Serving Deployment→AMP (serving); Backend aggregates
    write-queue + read-pool + unified-surface; Backend serves assurance-REST-interface;
    GUI→assurance-REST-interface (archimate-association — reconciles stale GUI-calls-MCP);
    assurance-REST→write-queue (association); write-queue + read-pool + arch-write-queue →
    concurrency-constraint (3× realization); MCP-adapter→delete-analysis (assignment);
    delete-analysis + write-queue + read-pool + unified-surface → assurance-knowledge-base (4× access).
  - `artifact_verify`: 638 files, 0 errors, 1 pre-existing warning (W160 on arch-mcp-endpoint-adapter).
  - Committed: `5589c5e`. Next: T25.
- 2026-06-22 — **T23 complete (tests/rendering/test_gsn_rendered_svg.py created).**
  - C4 harness (`test_c4_rendered_svg.py`) was already created and used by T19/T20.
  - GSN counterpart added: `tests/rendering/test_gsn_rendered_svg.py` (17 tests).
    Reusable `_render(nodes, edges)` helper calls `render_gsn()` → `render_gsn_svg()`.
    Tests: label text for all 6 labelled node types + undeveloped-no-text assertion;
    shape element per type (rect/polygon/circle/ellipse); supported-by + in-context-of
    edges (line elements + data-gsn-edge attributes); multi-node integration test.
    No PlantUML required — GSN uses native SVG renderer.
  - Gates: 3318 passed / 2 skipped; ruff clean; zuban clean. Next: T22.
- 2026-06-22 — **T22 complete (tests + root cause documented).**
  - **Root cause:** The old model-backed renderer produced `rectangle "Name\nDescription..." <<C4External>>`
    for external nodes unconditionally when the entity had `content_text` (via `_short_description(entity)`).
    Internal `<<C4Component>>` nodes never got descriptions. Result: `architecture-backend-components`
    showed long description text on external data-object nodes (SQLite Index, Workspace Configuration, etc.)
    while `assurance-module-components` did not (entities had shorter/no content_text). Neither diagram
    intended to show descriptions — the `show_node_descriptions` flag did not exist in the old renderer.
    The new `C4PumlRenderer` gates ALL node types (Component, System_Ext, Container, etc.) uniformly
    via `show_node_descriptions` (default: False). Stored PUML files were migrated via auto-sync (T20/T21).
  - **Tests added to `test_c4_node_description.py`** (4 new tests for the c4-component type):
    - `test_component_diagram_default_omits_description_from_internal_component`
    - `test_component_diagram_default_omits_description_from_external_node` — targets the exact divergence
    - `test_component_diagram_show_descriptions_true_includes_description`
    - `test_component_config_has_no_show_node_descriptions_flag` — asserts shipped config stays off
  - **Test added to `test_c4_stored_diagram_format.py`**:
    - `test_c4_stored_diagram_no_embedded_description_in_labels` — guards against old `"Name\\nDesc"` pattern
      reappearing in any stored C4 PUML; parameterized across all 4 stored C4 diagrams.
  - Gates: 3301 passed / 2 skipped; ruff clean; zuban clean. Next: T23.
