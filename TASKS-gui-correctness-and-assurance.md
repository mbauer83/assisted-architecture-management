# TASKS — GUI Correctness, Attribute Typing, Diagram UX & Assurance Completeness

Execution ledger for `PLAN-gui-correctness-and-assurance-completeness.md`. This file is the **source
of truth for progress**. Update it every session. The plan says *what* and *why*; this file tracks
*where we are*.

Status values: `todo` · `in-progress` · `blocked` · `review` (impl done, awaiting user/QC) · `done`.
Keep the status table and the progress log in sync. Never mark `done` until the WU checklist is
ticked in the plan **and** all quality gates pass (`pytest` 0-fail · `ruff` · `zuban` · frontend
`lint`/`typecheck`/`test`).

---

## Session protocol (every new / post-compaction session)

1. Read this whole file (it is short) — including the Decision log (those decisions are **settled**;
   do not relitigate them). Read the plan's §0 and §"For implementers".
2. Pick the topmost `todo`/`in-progress` WU whose dependencies are all `done`. Set it `in-progress`
   and add a dated progress-log line with your intent. Only stop to ask the user if the WU needs a
   **new** design decision not already in the Decision log (e.g. the B3 spike output) — never re-ask
   a settled one.
3. **Read the plan freely** for that WU — §0, the WU's phase intro, the WU, and any WU it depends on.
   The plan is curated context; reading it is cheap.
4. Implement, but **ration codebase & self-model exploration**: each WU cites the exact `file:line`
   and model facts you need — open a cited location once to confirm, then act. Do NOT broad-grep the
   `src` tree, sweep subsystems, or query the ~340-entity self-model unless the WU says `[HYP]
   reproduce first` / `find/confirm`, and then scope it to exactly what's named. Run quality gates.
5. Tick the WU checklist in the plan; set status here (`done`, or `review` if it needs the user);
   add a progress-log line with what changed (files) + test results. Commit only if the user asked.
6. If you discover the plan is wrong, fix the plan text too (and note it in the log).

**Backend restart caveat:** MCP/`artifact_*`/`assurance_*` tools run against a long-running backend;
code changes require a user-performed backend restart before tools reflect them, and MCP-surface
changes require a Claude session restart. Plan work so you don't block on a restart mid-session.

---

## Status table

| WU | Title | Phase | Status | Depends on | Notes |
|----|-------|-------|--------|-----------|-------|
| A1 | Search results schema union + per-hit decode | A | done | — | prereq for assurance search hits (G3) |
| A2 | Ranked-search redesign (`included_record_types`, per-kind merge, semantic supplement) | A | done | — | shares RecordType abstraction with A3 |
| A3 | `list_artifacts` honour include-set | A | done | — | share RecordType abstraction with A2 |
| A4 | Browse: reset entity-type filter on domain change | A | done | — | frontend only |
| B3 | Typed-property foundation (spike → impl) | B | done | — | **foundational**; OQ-2 approved; full port complete |
| B1 | Repo authoring policy (createability + valid defaults) | B | done | B2 | ships with B2 (boot) |
| B2 | Remediate schemata + templates (disposition table) | B | done | — | disposition decided (OQ-1) |
| B4 | Typed attribute editor | B | done | B3 | — |
| B5 | Ad-hoc attribute scalar typing | B | done | B3 | — |
| B6 | Self-model delta (B-phase) | B | done | B1,B3 | tools only |
| C1 | Documents open in view mode; single Edit toggle | C | done | — | audit MarkdownEditor callers first |
| C2 | Document spec section-templates (+ validation, template) | C | done | — | — |
| D1 | Entity-picker implied **domain** (not group) | D | done | — | — |
| D2 | Entity-picker fixed-level display (strategy A) | D | done | D1 | feeds F1 DOB picker |
| E1 | C4 person labels render | E | done | — | root cause: actor FontColor white → white-on-white; fix: rectangle <<C4Person>> |
| E2 | C4 container person line-origin gap | E | done | E1 | resolved by E1 fix (rectangle border anchors vs actor glyph tail) |
| E3 | C4 drill-down on-node + sticky up-banner | E | done | — | — |
| E4 | C4 model-backed edit sidebar (entity curation only) | E | done | — | connections read-only/derived |
| E5 | Diagram-only read-contract fix + viewer selection | E | done | — | backend defect; helps C4+GSN |
| E6 | C4 node labels show name only (not full description) | E | done | — | bug; name vs description in renderer |
| E7 | C4 standard node shapes by default; explicit shape where multiple options exist | E | done | — | always-on; shape resolution: explicit→technology map→rectangle; [HYP] validate plantuml.jar keywords first |
| F1 | Datatype attribute type selectable | F | done | — | superseded and completed by Type-Resolution WU-5.2: closed cross-repo picker with tagged references |
| F2 | Datatype relabel mult / src-tgt cardinality | F | done | — | completed by Type-Resolution WU-5.4 |
| F3 | Datatype unique constraints (+ mandatory verifier ext) | F | done | TypeRes P0/P1 | E337 datatype contribution validates composite constraints |
| F4 | Datatype notes on classifiers/relations | F | done | — | completed by Type-Resolution WU-5.4: ontology, editor, and PUML rendering |
| F5 | Datatype create/edit UX consistency pass | F | done | TypeRes P5, F3 | capstone complete |
| G-INV | Capability matrix + exposure policy + benchmark + analysis aggregate + GSN dual-home | G | done | — | direct SQLCipher search selected; design recorded |
| G0 | Governing principle: assurance grounded in architecture | G | done | G-INV | contracts + self-model complete |
| G1 | Unlock-gated read endpoints + exposure policy + 423/404 | G | done | G-INV | with G2 = one milestone |
| G2 | Navigable assurance browse + arch↔assurance lens | G | done | G1 | ships with G1 |
| G3 | Assurance search (direct or ephemeral index) | G | done | G-INV(benchmark),A1 | direct queries (p95 31ms); no index |
| G4 | Write endpoints + mutation policy + forms | G | done | G-INV | — |
| G5-P1 | Analysis aggregate foundation (store+port+use cases) | G | done | G4 | G-INV req use case #1; anchor optional (user decision B); central clock added |
| G5-P2 | ModelAndBind orchestration use case (Bound/TaskRequired) | G | done | G5-P1 | G-INV req use case #7; HTTP create+bind, MCP task-only |
| G5-P3 | Analysis REST/MCP surface + frontend analysis picker | G | done | G5-P1 | exposure-filtered; analysis-scoped read filters |
| G5a | STPA wizard (analysis-scoped) | G | done | G5-P1,G5-P2,G5-P3 | impl+tests done; live API smoke green against real unlocked store |
| G5b | GRC wizard (analysis-scoped) | G | done | G5-P1,G5-P2,G5-P3 | impl+tests done; live API smoke green against real unlocked store |
| G5c-1 | CAST wizard (analysis-scoped) | G | done | G5a,G5b,G6 | impl+tests done; live API smoke green (scoping verified) |
| G5c-2 | Supply-chain wizard: SBOM scope + vuln dashboard | G | done | G5b,D2 | 🔴 scope assigned against ArchiMate model (entity-picker); frontend-only, smoke green |
| G5c-2b | Supply-chain: AI-BOM coverage/export + AI-candidate scan | G | done | G5c-2 | impl+tests done; live API smoke green (4 new endpoints; role-vocabulary single-sourced) |
| G5c-3 | Model-this affordances (W501 → model_and_bind) | G | done | G5-P2 | ModelThisPanel on unbound CSN in node detail; endpoint pre-existing |
| G5c-4 | GSN / assurance-case wizard (dual-home bridge) | G | done | G7 | code+test+live smoke green; classified→preview / cleared→publish→bind→check; 4 endpoints live |
| G6 | Assurance diagram views (3 sources) + baselines | G | done | G1 | — |
| G7 | GSN renderer + reusable PUML shapes | G* | done | OQ-7 | native SVG capability; exact GSN shapes + semantic PUML macros |
| G8 | Rework GSN exemplar (via artifact_edit_diagram) | G | done | G7,G-INV(#5 bridge) | reworked via artifact_edit_diagram; substantive strategy + assumption/justification + evidence solutions; verify valid; renders with G7 shapes |

Recommended order: **A1→A4**, then **B3 spike**→(B1+B2)→B4→B5→B6, then **C/D**, then **E** (E1 repro
first; G7 can ride here since it's architecture-subsystem).

**Phase F is now driven by `PLAN-datatype-type-resolution.md`** (the cross-repo type-validation plan
promised in WU-F1). Order: Type-Resolution **P0–P5** (P5 supersedes F1; WU-5.4 folds in F2+F4) → **F3**
as a datatype verification contribution on the new hook → Type-Resolution **P6–P8** → **F5** capstone.
Then **G-INV**→(G1+G2)→G3→G4→G5→G6→(G7)→G8 (assurance stays last, DEC-seq).

---

## Decision log (resolve before the dependent WU)

| ID | Decision | Status | Resolution |
|----|----------|--------|-----------|
| OQ-1 | B2 schema disposition | **decided** | Two classification enums stay required + genuine member (Maturity→"Not Assessed", Category→"Unspecified"); all other listed attrs optional |
| OQ-2 | B3 typed-property spike output | gate | Review spike (value model + lexical grammar + subset + migration) before B3 impl/B4/B5 |
| OQ-3 | E1/E2 reproduce C4 person-label loss | gate | Render stored PUML with plantuml.jar before choosing fix |
| OQ-4 | G5 first-milestone wizard breadth | **decided** | STPA + GRC first (CAST needs baselines+control-structure; GSN needs G7) |
| OQ-5 | Assurance analysis persistence | **decided** | First-class analysis aggregate (nodes belong to an analysis); store schema migration |
| OQ-6 | G3 index-vs-direct | gate | Decided by the G-INV benchmark; no-plaintext-persistence constraint holds |
| OQ-7 | GSN notation authority + split | **decided** | Authority = GSN Community Standard; keep G7/G8 in this plan unless the prototype warrants a split |
| OQ-8 | GSN bridge shape | **decided** | Classification-gated dual home (confidential→store preview; cleared→arch-repo gsn diagram) |
| DEC-auth | Authn/authz out of scope; loopback default, non-loopback only behind perimeter + opt-in + startup warning | **decided** | §0 |
| DEC-typed | Typed properties: canonical lexical in files + schema-driven decode; one representation | **decided** | §0 / WU-B3 |
| DEC-search-persist | Searchable assurance content: zero unencrypted persistence / never committed | **decided** | WU-G3 |
| DEC-seq | Assurance (Phase G) runs last (architecture-first product) | **decided** | Sequencing |
| DEC-typeres | Phase F driven by `PLAN-datatype-type-resolution.md` (the cross-repo type-validation plan WU-F1 promised) | **decided** (2026-06-20) | F1 superseded by its WU-5.2; F2+F4 fold into its WU-5.4; F3 verifier ext rides its contribution hook; F5 is the post-P5 capstone; order = TypeRes P0–P5 → F3 → P6–P8 → F5 → G |

---

## Progress log (append-only; newest last)

- 2026-06-21 — WU-G8 (rework GSN exemplar) **done** — **final WU; plan complete.** Reworked
  `GSN@1781338120.3U4cRc` via `artifact_edit_diagram` (tool-based; diagram-owned nodes), after a
  user-corrected design discussion. **Key correction (user):** a GSN *Strategy* names a substantive
  property of the concrete system, not a meta "argument over …" (which is a category error outside an
  abstract assurance process; cf. the user's braking exemplar where S1 = "Prove that braking function
  is fail operational"). Reworked structure: top goal `g1` + two contexts (`c1` system, `c2` operating
  scope — STPA-Sec + EU AI Act Art. 12); strategy `s1` now asserts the property "Prove the store keeps
  evidence confidential across its access lifecycle — fail-closed entry, bounded activation,
  tamper-evident recording"; assumption `a1` (supported deployment boundary, §0 DEC-auth) and
  justification `j1` (the three sub-goals are the complete STPA-Sec disclosure mitigations) both
  in-context-of `s1`; sub-goals `g11/g12/g13` map to the three lifecycle properties. The three
  restated-control "solutions" are replaced with **evidence solutions** citing real verification
  artifacts: `sn1` negative-leak (`test_assurance_exposure.py`, `test_assurance_http_read.py`), `sn2`
  lock-lifecycle (`test_assurance_store.py::test_unlock_and_lock`), `sn3` hash-chain integrity + the
  append-only audit log as Art. 12 evidence (`test_assurance_archive.py::test_verify_chain_with_entries`).
  Diagram re-verified `valid` (no issues; all goals developed, solutions are leaves). On-demand SVG
  (G-f: never persisted to disk for a confidential GSN) renders all 12 nodes with correct G7 shapes
  (goal rect, strategy parallelogram, solution circle, assumption/justification ovals, context
  stadium), 12 stable `data-qualified-name` click targets, 13 aria-labels. No new self-model element
  (exemplar content edit). **All WUs in `PLAN-gui-correctness-and-assurance-completeness.md` are now
  `done`.**
- 2026-06-21 — WU-G5c-4 (GSN / assurance-case wizard) **done**. Implementation (parallel session) +
  full gates + live smoke verified this session against the restarted backend. Implements the OQ-8 /
  WU-G-INV #5 classification-gated dual home: new `src/application/assurance_gsn.py` (`build_gsn_draft`
  derives an analysis-scoped GSN draft + `diagram_entities` from assurance content via `case_draft`,
  computes the effective TLP across the analysis + nodes, and sets `publishable` via `is_publishable`;
  `record_publication` is **gated on publishability**, binds assurance nodes ↔ published GSN diagram
  nodes through `gsn-source` arch-refs, and appends a `PUBLISH_GSN` audit entry). Four endpoints on
  `_assurance_analysis_routes.py`: `GET /api/assurance/gsn/draft`, `/gsn/rendered` (renders via the G7
  `gsn` pipeline), `/gsn/completeness`, `POST /api/assurance/gsn/publications`. Frontend
  `AssuranceGsnWizardView.vue` + pure `AssuranceGsnWizard.helpers.ts` (+ tests): draft → preview →
  (confidential ⇒ store-resident preview only; cleared ⇒ publish to the arch repo via `POST
  /api/diagram` as a `gsn` diagram) → bind → completeness. **Live smoke (restarted backend, real
  unlocked store):** all three GSN GET endpoints return an **indistinguishable 404** for an absent /
  above-ceiling `analysis_id` (exposure-policy-correct); populated draft/publish paths are covered by
  the integration suite (`tests/application/test_assurance_gsn.py`, analysis-http tests) rather than
  writing into the dogfood store (no delete-analysis by design). **G7 renderer confirmed live:** the
  stored GSN exemplar (`GSN@1781338120.3U4cRc`) now renders via the native SVG renderer with correct
  Community-Standard shapes — goal `<rect>`, strategy `<polygon>` parallelogram, solution `<circle>` —
  9 stable `data-qualified-name` click targets, `data-gsn-type` semantics, `aria-label`+`<title>`
  a11y, and text labels. Gates: pytest 3236 passed / 2 skipped, ruff + zuban clean; GUI lint/typecheck
  clean, vitest 252 passed (21 files). Only remaining WU: **G8** (rework the GSN exemplar for soundness
  — needs user domain input on the claim/strategy/evidence wording).
- 2026-06-21 — WU-G5c-2b **done** (was `review`). Backend restarted; the 4 new endpoints are live.
  Read-only API smoke against the **real unlocked SQLCipher store**: `aibom/roles` → 200 with the
  canonical 11-role vocabulary (confirms the GUI's single backend source); `aibom/coverage` → 200,
  exposure-filtered (`visibility_limited:true`); `aibom/scan?limit=5` → 200 ranking **real self-model
  entities** (`ROL@…ai-agent` score 55, `AIF@…mcp-interface`, …) and honouring the limit — and
  surfacing the expected heuristic false positives, which the "confirm each candidate" note covers;
  `POST aibom/export` → 200 emitting valid CycloneDX 1.6 (`ai_role:"agent"` → component
  `type:"application"`, `arch:entity_id` property). All four carry `Cache-Control: no-store`.
  Locked/423 not re-probed live (would require locking the dogfood store; covered by the integration
  suite). Next: **G7** (GSN renderer — architecture-subsystem; unblocks G5c-4 + G8).
- 2026-06-21 — WU-G5c-2b (AI-BOM coverage/export + AI-candidate scan) impl+tests **done** →
  `review` (awaiting a backend restart for a live smoke of the 4 new endpoints). **Backend:** extracted
  the inline `assurance_aibom_coverage` MCP logic into a pure `aibom_coverage(components, anchors)` use
  case in `assurance_queries.py` (now reused by MCP + HTTP — no drift); new `_assurance_aibom.py`
  router (wired in `assurance.py`) with `GET /api/assurance/aibom/coverage` (signals-gated, exposure-
  filtered store components + anchors), `GET /api/assurance/aibom/scan` (un-gated — scans the **public**
  architecture repo via `state.get_repo().list_entities()` + `scan_candidates`, excludes diagram-only
  nodes, honours `limit`; touches no confidential content), `POST /api/assurance/aibom/export`
  (un-gated pure transform of caller-confirmed AI components → CycloneDX 1.6 via `build_cyclonedx_16`),
  and `GET /api/assurance/aibom/roles`. **Principled-solution fix (user-raised):** the AI-role
  vocabulary was hard-coded in the frontend — replaced with a single backend source
  (`AI_BOM_ROLES = tuple(_CDX_AI_ROLE_TO_TYPE)` in `_aibom_exporter.py`) exposed via the new `roles`
  endpoint; the GUI fetches it at runtime (`parseRoles`), so the enum can no longer drift (a backend
  test asserts the endpoint mirrors `AI_BOM_ROLES`). **Frontend:** new `AssuranceAibomPanel.vue` +
  pure `AssuranceAibom.helpers.ts` (parseRoles/parseCoverage/parseCandidates/selectedAiComponents/
  scoreBand) mounted as the 5th supply-chain wizard step (coverage report → candidate scan with
  per-row select → export ML-BOM with download), keeping the wizard view modular. New tests:
  `tests/assurance/test_assurance_aibom_http.py` (13: locked/coverage/scan-exclusions/limit/no-repo/
  export/malformed/roles-sync), `tests/application/test_assurance_queries.py` (4: pure coverage),
  `AssuranceAibom.test.ts` (9 helper tests); updated `AssuranceSupplyChainWizard.test.ts` for the new
  anchor-free `aibom` step. Full gate: pytest 3224 passed / 2 skipped, ruff + zuban clean; GUI
  lint/typecheck clean, vitest 248 passed. No self-model change (proportional additions to the
  already-modeled assurance REST interface; consistent with G5c-1/2/3). **Backend restart needed** for
  the 4 new endpoints; then a read-only API smoke flips this to done. Next: **G7** (GSN renderer —
  architecture-subsystem; unblocks G5c-4 + G8).
- 2026-06-21 — WU-G5c-3 (model-this affordances) **done** — frontend-only; the `model_and_bind` use
  case + `POST /api/assurance/model-this` already existed (G5-P2), confirmed live via OpenAPI. New
  reusable `ModelThisPanel.vue` + pure `ModelThisPanel.helpers.ts` (isUnboundControlNode for the W501
  state, MODELABLE_ARCH_TYPES, type→domain derivation, request body builder, typed
  bound/task/error outcome parser). Mounted in `AssuranceNodeDetail.vue` for unbound-pending
  control-structure nodes: pick an ArchiMate type + name → Model & bind (create+bind), or tick
  "separation of duties" to emit a task for an architecture-write session; on bound it reloads the
  detail. This also completes the STPA wizard's existing "model & bind → /assurance/browse" hop,
  which now lands on a working affordance (the browse view renders AssuranceNodeDetail). 9 vitest
  helper tests; full vitest 239 passed (19 files), lint/typecheck clean; backend untouched. Next:
  **G5c-2b** (AI-BOM coverage/export + AI-candidate scan — needs new HTTP read endpoints) or the
  blocked **G5c-4** GSN (after G7).
- 2026-06-21 — WU-G5c-2 (supply-chain wizard) **done** — frontend-only, no backend change, so no
  restart. The plan's 🔴 requirement (assign SBOM scope against the **ArchiMate** model, never C4) is
  satisfied: `AssuranceSupplyChainWizardView.vue` (stepper Scope → Import SBOM → Components →
  Vulnerabilities) forces selection of an ArchiMate anchor via the WU-D2 `EntityPickerInput` pinned
  (`fixedEntityTypes`, `widenableTo="none"`) to the admissible types (application-component,
  application-collaboration, grouping, node, system-software) **before** import; steps after Scope are
  locked until an anchor is set. Import → `POST /api/assurance/bom/import` with `anchor_entity_id`;
  Components → `GET /api/assurance/bom/components?anchor_entity_id=…` (per-scope, with anchor-match
  summary); Vulnerabilities → import + `GET /api/assurance/vulnerabilities` with a severity filter and
  a severity-count bar. Pure `AssuranceSupplyChainWizard.helpers.ts` (SUPPLY_STEPS, admissible types,
  JSON object/array parse guards, severity summary, component-match summary) + 10 vitest tests.
  Backend already carries the ArchiMate anchor end-to-end (connector `import_bom(anchor_entity_id=…)` +
  `list_bom_components(anchor_entity_id=…)`), so no extension was needed. Route
  `/assurance/supply-chain` + landing-page link. Read-only smoke: `bom/components` (+anchor filter)
  and `vulnerabilities` return 200 (signals available, exposure-filtered). Gate: vitest 230 passed (18
  files), lint/typecheck clean; backend untouched. Deferred to **G5c-2b**: AI-BOM coverage/export +
  AI-candidate scan (need new HTTP read endpoints — not on the signals connector port). Next:
  **G5c-3** (model-this affordances).
- 2026-06-21 — WU-G5c-1 (CAST wizard) **done** (was `review`). Backend restarted; cast-complete is
  live. Read-only API smoke: unscoped returns the three checks (+`baseline_count`/`incident_count`);
  scoping verified — the stray unscoped baseline (no `analysis_id`) does not leak into a scoped query
  (`baseline_count: 0`); cast-investigation guidance resolves. Next: **G5c-2** (supply-chain).
- 2026-06-21 — WU-G5c-1 (CAST wizard) impl+tests **done** → `review` (awaiting backend restart for
  the new `/api/assurance/cast-complete`, currently 404). **Backend:**
  `run_cast_complete(store, archive, *, analysis_id=None)` now scopes nodes/edges and the §10
  baseline gate to one analysis (baselines carry `analysis_id`, so an A@1 baseline no longer
  satisfies A@2); new `GET /api/assurance/cast-complete`. **Frontend:** `AssuranceCastWizardView.vue`
  (stepper Baseline → Incident → Investigate → Corrective Actions → Review; baseline step seals/lists
  the analysis-scoped baseline for the G-g reproducibility gate; incident gap badge from
  `incident_has_investigates`; target-centric linker incident→investigates→observed factor;
  source-centric linker corrective-action→derives→constraint with an inline constraint add; review
  runs cast-complete + seal gated on pass) + pure `AssuranceCastWizard.helpers.ts` (CAST_STEPS,
  summary, gap extraction, step badges, source/target link helpers — self-contained small generic
  helpers; a future DRY could share these across STPA/GRC/CAST). Route `/assurance/cast` +
  landing-page link. New tests: `test_cast_complete.py` (+analysis scoping isolates baseline+nodes),
  `test_assurance_analysis_http.py` (+cast-complete scoped/locked, +`list_baselines` on the fake
  archive), `AssuranceCastWizard.test.ts` (10 helper tests). Full gate: pytest 3212 passed / 2
  skipped, ruff + zuban clean; GUI lint/typecheck clean, vitest 220 passed. **Backend restart
  needed** for cast-complete; then a read-only API smoke flips this to done. Next: **G5c-2**
  (supply-chain wizard).
- 2026-06-21 — WU-G5c decomposed (same approach as G5). The single G5c row bundled four wizards
  whose dependencies differ; split into **G5c-1 CAST** (deps met — baselines G6, control-structure
  projector, `cast_complete`), **G5c-2 supply-chain** (SBOM scope vs ArchiMate model + entity-picker
  D2), **G5c-3 model-this** (W501 badges → `model_and_bind`, the G5-P2 use case), and **G5c-4
  GSN/assurance-case** which stays **blocked on G7** (there is no GSN renderer yet; per the plan's
  "do not build a wizard step on a missing capability" rule). Building in the plan's sequence minus
  the blocked one: CAST → supply-chain → model-this; GSN follows G7. Starting **G5c-1 (CAST)**.
- 2026-06-21 — WU-G5b **done** (was `review`). Backend restarted; `GET /api/assurance/grc-complete`
  is live. Read-only API smoke against the real unlocked store: unscoped grc-complete returns the
  three checks (`obligation_has_constraint`, `risk_has_treatment`, `risk_has_owner`) each with a
  `gaps` array (the wizard's source of truth for per-risk status); analysis-scoping returns the same
  shape for an empty scope (all pass); both GRC guidance topics (`grc-risk`, `grc-obligations`)
  resolve. STPA wizard re-smoked: stpa-complete + guidance live; the seal-path fix targets the known
  working `/api/assurance/baselines/seal` route (not re-probed to avoid a stray sealed baseline). No
  write probes against the confidential store. Next: **G5c**.
- 2026-06-21 — WU-G5b impl+tests **done** → `review` (awaiting backend restart for the new
  `/api/assurance/grc-complete` endpoint, currently 404 on the running backend). **Backend:**
  `run_grc_complete(store, *, analysis_id=None)` now scopes nodes/edges to one analysis (mirrors
  `run_stpa_complete`); `risk_has_owner` passes on an `accountable-to` edge **or** an `accountable-to`
  architecture reference (user decision — accountability resolves to an architecture role, WU-G0
  one-way grounding); new `GET /api/assurance/grc-complete` in `_assurance_analysis_routes.py`.
  **Frontend:** `AssuranceGrcWizardView.vue` (stepper Risks → Treatment → Controls → Obligations →
  Coverage; risk likelihood/impact attrs; treatment via attribute PATCH (merged, since assurance
  edits replace wholesale); accountability via `POST /api/assurance/arch-refs`
  (ref_type=accountable-to); target-centric linkers for treated-by (risk→control) and complies-with
  (control→obligation); coverage dashboard runs grc-complete, surfaces the §9 anti-subordination
  safeguard, seal gated on a clean pass) + pure `AssuranceGrcWizard.helpers.ts` (GRC_STEPS,
  attribute parsing, risk score, completeness summary, gap-node extraction, step badges, link
  helpers). Per-risk treatment/owner status derives from the server's grc-complete gaps (single
  source of truth — owner edge-or-ref rule stays server-side, so no arch-refs read endpoint or N+1
  needed). `AssuranceAnalysisPicker` gained a `defaultMethod` prop (GRC wizard pre-selects GRC).
  Route `/assurance/grc` + landing-page link. **Also fixed the G5a STPA seal bug** found here: it
  POSTed `/api/assurance/baselines` (405) → now `/api/assurance/baselines/seal`. New tests:
  `test_grc_complete.py` (+arch-ref owner, +unrelated-ref negative, +analysis scoping isolation),
  `test_assurance_analysis_http.py` (+grc-complete scoped/locked, +`list_arch_refs` on the fake
  store), `AssuranceGrcWizard.test.ts` (16 helper tests), `AssuranceAnalysisPicker.test.ts`
  (+defaultMethod). Full gate: pytest 3209 passed / 2 skipped, ruff + zuban clean; GUI lint/typecheck
  clean, vitest 210 passed. **Backend restart needed** for `grc-complete`; then a read-only API smoke
  flips this to done. Next: **G5c** (CAST / GSN / supply-chain / model-this wizards).
- 2026-06-21 — WU-G5b in-progress. Intent: build the guided GRC wizard (Risks → Treatment →
  Controls → Obligations → Coverage), analysis-scoped, mirroring the STPA wizard. **User decision
  (risk ownership):** a risk is *accountable to an architecture role* via an assurance→architecture
  reference; `grc_complete.risk_has_owner` extended to pass on an `accountable-to` edge **or** an
  `accountable-to` arch-ref (one-way grounding, WU-G0 principle). Backend: add `analysis_id` scoping
  to `run_grc_complete` (mirror `run_stpa_complete`) + the arch-ref owner rule; add
  `GET /api/assurance/grc-complete`. Frontend: `AssuranceGrcWizardView` + pure helpers; treatment via
  PATCH attribute; accountability via `POST /api/assurance/arch-refs` (ref_type=accountable-to);
  coverage dashboard runs grc-complete + surfaces the §9 anti-subordination safeguard; seal gated on
  pass. Also fixing a G5a bug found here: the STPA wizard sealed via `POST /api/assurance/baselines`
  (405) instead of `/api/assurance/baselines/seal`.
- 2026-06-19 — Plan + ledger created after three review rounds. All WUs `todo`/`blocked`. No code
  written yet. Blocking gates: OQ-1 (B2), OQ-5/OQ-8 (G-INV). Next recommended WU: **A1** (no
  dependencies, user-visible crash fix).
- 2026-06-19 — Decisions OQ-1, OQ-4, OQ-5, OQ-7, OQ-8 resolved (folded into plan WUs). **B2 and
  G-INV unblocked.** Remaining gates OQ-2/3/6 are resolved during execution, not user decisions.
  No code yet. Start point still **A1**.
- 2026-06-19 — WU-A1 in-progress. Intent: merge SearchHitSchema into ArtifactSearchHitSchema (single union schema covering entity/connection/diagram/document + assurance placeholder); add per-hit decoding so one bad hit doesn't crash the whole results page.
- 2026-06-19 — WU-A1 done. Files: schemas.ts (unified SearchHitSchema, ArtifactSearchHitSchema=alias), HttpModelRepository.ts (per-hit decode via Schema.decodeUnknownEither), SearchView.vue (document RouterLink), NavBar.vue (document routing + hitGlyphType fallback), vite.config.ts + package.json (Vitest setup), schemas.search.test.ts (8 tests). Results: vitest 8/8, lint clean, typecheck clean, pytest 2566/2566, ruff pre-existing 40 (unchanged), zuban pass.
- 2026-06-19 — WU-A2 done. Replaced independent boolean include-flags + broken strict/prefer trio with canonical `SearchableKind`/`included_kinds` abstraction (shared with A3). Per-kind FTS sub-query limits prevent minority-kind starvation. Entity inclusion is now explicit (no longer implicit). Supplement scored path fires per-kind when FTS returns 0 hits for that kind. Semantic supplement gated on "entities" ∈ included_kinds. Removed `prefer_record_type`/`strict_record_type` from SQL layer (application layer handles). Files changed: _artifact_search.py, ports.py, _sqlite_queries.py, service.py, artifact_repository.py, query_search_tools.py, entity_search.py, test_artifact_repository.py, test_diagram_entity_index.py. New test file: tests/application/test_artifact_search_ranked.py (7 tests). Results: pytest 2573/2573, ruff clean, zuban pass.
- 2026-06-19 — WU-A4 done. Added `watch(activeDomain, () => { typeFilter.value = '' })` to EntitiesView.vue so switching ArchiMate domain always resets the type filter to "All". `uniqueTypes` re-derives from activeDomain automatically via computed (no extra load). Files: EntitiesView.vue (+1 watch). New test file: EntitiesView.domainReset.test.ts (4 tests). Results: vitest 12/12, lint clean, typecheck clean, pytest 2581/2581.
- 2026-06-19 — WU-B3 spike done → review (OQ-2 gate). Files: src/domain/property_value.py (new, 232 lines), tests/domain/test_property_value.py (87 tests). Spike covers: PropertyValue ADT, canonical lexical grammar for string/integer/number/boolean/array incl. Markdown-cell escaping (sentinel-based unescape), schema-driven decode, lenient decode for migration, validate(), startup unsupported-construct detection, ad-hoc type carrier (attribute_types frontmatter key). Results: pytest 2668/2668, ruff clean, zuban pass. AWAITING OQ-2 user review of the value model + grammar + subset + migration design before full port.
- 2026-06-19 — WU-A3 done. Added `include_entities: bool = True` to `list_artifacts` port + service + repository + stub; gated entity output on the flag (entities are now a normal member of the include-set, no longer always-on). Updated `_include_flags` in `query_list_read_tools.py` to return a 4-tuple and import `ALL_SEARCHABLE_KINDS` from `_artifact_search.py` (one canonical abstraction for both list and search). Files changed: ports.py, artifact_repository.py, service.py, query_list_read_tools.py, test_artifact_repository.py (stub). New test file: tests/tools/test_list_artifacts_include_set.py (8 tests). Results: pytest 2581/2581, ruff clean, zuban pass.
- 2026-06-19 — WU-B2 done. Applied B2 disposition table to all 3 live repos (ENG-ARCH-REPO, TECHNOLOGY_ARCHITECTURE, u2p-enterprise) + engagement_repo_template.py: goal/principle/requirement/stakeholder `required: []`; capability.Maturity keeps required + adds "Not Assessed" enum member + default; driver.Category keeps required + adds "Unspecified" + default; driver.Source dropped from required. Also synced missing driver enum values (Market Gap, Regulatory & Standards Trend) to template. Verification: 0 W042/E042 across all 6 affected types. Files: 18 JSON schema files + engagement_repo_template.py. Results: pytest 2683/2683, ruff clean, zuban pass.
- 2026-06-19 — WU-B3 full port done (OQ-2 approved). Files changed: artifact_write_formatting.py (`dict[str,Any]` + attribute_types param + `_encode_cell`), _verifier_rules_schema.py (E042/W042 schema-driven decode), artifact_parsing.py (`decode_entity_properties`), coerce.py (`as_optional_typed_dict`), _entity_edit_support.py (`MergedFields.attribute_types`, `attribute_types` kwarg), entity_edit.py, entity.py, admin_entity_ops.py, materialization.py, routers/entities.py, mcp/edit_tools.py, mcp/write/entity.py. New test file: tests/application/write/test_typed_properties_integration.py (15 tests). Updated tests: test_entity_edit_pure.py. Results: pytest 2683/2683, ruff clean, zuban pass.
- 2026-06-19 — WU-B5 in-progress. Intent: add type-selector dropdown when adding a new ad-hoc property in EntityDetailView + EntityCreateView; wire the selected type into the `attribute_types` frontmatter carrier (B3); use TypedPropertyInput for the value cell; backend round-trip: ad-hoc bool/int/number values encode/decode correctly.
- 2026-06-19 — WU-B4 done. Files: routers/entities.py (`_attribute_descriptors()` + `descriptors` field), schemas.ts (EntityAttributeDescriptor type + descriptors in EntitySchemaInfo + EntityDetail.properties→Unknown), TypedPropertyInput.vue (new; enum/bool/number/array/string controls + validation), EntityDetailView.vue (schema load in startEdit, toLexical, editSchemaDescriptors/Required, typed inputs, required-missing Save guard), EntityCreateView.vue (schemaDescriptors, createRequiredMissing, defaults from schema, typed inputs). New test file: TypedPropertyInput.test.ts (19 tests). Results: vitest 31/31, lint clean, typecheck clean, pytest 2683/2683, ruff clean, zuban pass.
- 2026-06-19 — WU-B5 done. Files: ModelRepository.ts (`attribute_types` field on createEntity/editEntity/adminEditEntity), EntityDetailView.vue (AdHocType, _ADHOC_VALID Set, editProperties extended with adHocType, startEdit loads attribute-types from extra, buildEditBody collects non-string ad-hoc types, type-selector + TypedPropertyInput on ad-hoc rows), EntityCreateView.vue (same AdHocType, buildBody, type-selector multi-line options). New test file: adHocTypeRoundtrip.test.ts (11 tests: collectAttributeTypes + loadSavedAttrTypes + type-change reset). Results: vitest 44/44, lint clean, typecheck clean, pytest 2683/2683, ruff clean, zuban pass.
- 2026-06-19 — WU-B6 done. Created REQ@1781886720.VJ2ml- (Repository Authoring Policy: Required Attribute Defaults) + REQ@1781886727.m0KjkK (Typed Attribute Persistence and Editing). Added archimate-aggregation from REQ@1712870400.6ZR3nk to each, and archimate-realization from APP@1712870400.ca3vm7 (Model Verifier) to each. artifact_verify: 616 files, 0 errors, 1 pre-existing W160. pytest 2699/2699, ruff clean, zuban pass.
- 2026-06-19 — WU-B1 done. Files: src/application/_startup_schema_policy.py (new, SchemaPolicyError + validate_schema_policy + per-repo schema-syntax/default-validity/required-defaults-policy checks), startup_validation.py (re-export SchemaPolicyError/validate_schema_policy, +4 lines), arch_backend.py (call validate_schema_policy at startup), engagement_repo_template.py (_write_arch_repo_config_if_missing, config.yaml scaffold with non-strict default), .arch-repo/config.yaml (strict) in ENG-ARCH-REPO + TECHNOLOGY_ARCHITECTURE + u2p-enterprise-repository. New test files: tests/application/test_startup_schema_policy.py (16 tests), tools/gui/src/ui/views/__tests__/entityCreateability.test.ts (10 tests). Results: pytest 2699/2699, ruff clean, zuban pass, vitest 54/54, lint clean, typecheck clean.
- 2026-06-19 — WU-C1 done. Audit: MarkdownEditor has two callers (DocumentDetailView, DocumentCreateView). DocumentCreateView always stays in edit mode (create flow) — unchanged. DocumentDetailView reworked: page-level editing=ref(false) + startEdit/cancelEdit + Save/Cancel; view mode renders DOMPurify-sanitized markdown HTML (no MarkdownEditor mounted — correctness by construction); edit mode mounts MarkdownEditor. Added DocumentDetailView.vue to ESLint vue/no-v-html off-list (content is DOMPurify-sanitized). Files: DocumentDetailView.vue (rewritten), eslint.config.js (+1 file). New test: documentDetailMode.test.ts (8 tests). Results: vitest 62/62, lint clean, typecheck clean, pytest 2699/2699, ruff clean, zuban pass.
- 2026-06-19 — WU-D1 done. Files: useEntityFilters.ts (buildTypeToDomain + deriveImpliedDomains + intersectWithFixed exported as pure helpers; impliedDomains computed; availableEntityTypes intersects fixedEntityTypes; options param), EntityPickerInput.vue (pass fixedEntityTypes to useEntityFilters; impliedDomains in effectiveDomains; chip--implied style on domain chips derived from type selection). Groups not inferred. New test file: composables/__tests__/useEntityFilters.helpers.test.ts (12 tests). Results: vitest 74/74, lint clean, typecheck clean, pytest 2713/2713, ruff clean, zuban pass.
- 2026-06-19 — WU-C2 done. Files: document.py (_validate_section_templates + _build_placeholder_body section_templates param + create_document extraction/validation), engagement_repo_template.py (section_templates for adr/spec/standard), mcp/write/document.py (description update). New test file: tests/tools/test_document_section_templates.py (14 tests: unit _build_placeholder_body + _validate_section_templates + integration create_document). Results: pytest 2713/2713, ruff clean, zuban pass, vitest 62/62, lint clean, typecheck clean.
- 2026-06-19 — WU-D2 done. Added `widenableTo: 'none'|'domain'|'group'` prop to EntityPickerInput. Extracted calcHasStageUI/calcCanGoBack/calcCanGoForward to EntityPickerInput.helpers.ts (testable). Fixed domain display (compact chip/disabled row) + entity type display added to picker dropdown. Migrated callers: ActivityEntityPicker, C4DiagramEditor (scope picker), DiagramOwnEntityTypeSection to widenableTo="none". Files: EntityPickerInput.vue, EntityPickerInput.helpers.ts (new), ActivityEntityPicker.vue, C4DiagramEditor.vue, DiagramOwnEntityTypeSection.vue. New test: EntityPickerInput.fixedLevel.test.ts (19 tests). Results: vitest 93/93, lint clean, typecheck clean, pytest 2713/2713, ruff clean, zuban pass.
- 2026-06-19 — Plan amended: added WU-E6 (C4 node labels show name not description; fix in renderer.py _render_item_body, default show_node_descriptions=false) and WU-E7 (C4 standard node shapes always on by default; shape resolution: explicit shape attr → technology map → rectangle fallback; explicit shape selector only where multiple candidates exist for a type; no external PlantUML library includes) per user direction. Both added to Phase E in plan and ledger.
- 2026-06-19 — WU-E1 + WU-E2 done. Root cause: `skinparam actor { FontColor white }` renders person label as white text on white canvas (below the stick figure) → invisible. Fix: switched person emission from `actor "name" as alias` to `rectangle "name" <<C4Person/PersonExt>> as alias` in `_render_item`; added `skinparam rectangle<<C4Person>>` (dark blue #08427b, white font) + `skinparam rectangle<<C4PersonExt>>` (grey #999999, white font); removed `skinparam actor {}` block. Edge gap (E2) resolved automatically: rectangle border anchors work correctly with linetype ortho. Files: renderer.py. New test file: test_c4_person_rendering.py (6 tests). Updated: test_c4_renderer.py (assertion updated to C4PersonExt — Customer is outside system scope). Results: pytest 2719/2719, ruff clean, zuban pass.
- 2026-06-19 — Plan WU-E7 amended: notation authority added (https://c4model.com/diagrams/notation; C4 is notation-independent). Chosen style updated to C4-PlantUML stdlib (plantuml-stdlib/C4-PlantUML; !include <C4/C4_Container> etc.; plantuml.jar stdlib, no external URL). Macros: Person/Person_Ext, Container/ContainerDb/ContainerQueue, System/SystemDb, Component/ComponentDb/ComponentQueue. [HYP] step updated to test stdlib availability first, then native keyword fallback. Technology mapping updated to show macro variants (ContainerDb for databases, ContainerQueue for queues) vs native fallback. Item 5 updated to C4-PlantUML colored-box style as the "main styling". Golden-PUML test items updated to reference macros.
- 2026-06-19 — WU-E4 done. Files: C4DiagramEditor.helpers.ts (new; buildC4RoleMap/parseExcludedIds/groupEntitiesByRole), C4ModelBackedPanel.vue (new; entity curation panel with per-entity exclude toggle and read-only connections), C4DiagramEditor.vue (import + use C4ModelBackedPanel + handleExcludedChange). New test: __tests__/C4DiagramEditor.modelBacked.test.ts (14 tests). Results: vitest 121/121, lint clean, typecheck clean, pytest 2719/2719, ruff clean, zuban pass.
- 2026-06-19 — WU-E5 in-progress. Intent: fix `_extract_diagram_entities` to recognize `node_id` (GSN format) + set `display_alias`; fix connection extraction to handle `source_id`/`target_id` + `diagram-entities` sub-keys; filter cross-diagram entity contamination in context; widen `artifact_type` schema to `string` in frontend; add connection detail + SVG click wiring for diagram-only nodes.
- 2026-06-19 — WU-E5 done. Backend: extracted `_diagram_entity_extraction.py` (helpers `_diagram_local_id`, `_is_connection_item`, `extract_diagram_entities`, `diagram_local_to_full`, `extract_diagram_connections`, `_leaf_strings`, `_diagram_entity_content_text`) from `_service_incremental.py` to stay under 350-line limit; `_diagram_context.py` cross-diagram contamination filter; `state.py` `host_diagram_id` in entity_to_summary. Frontend: `schemas.ts` widened `artifact_type` + `domain` to `Schema.String` on `EntitySummarySchema`, `EntityDetailSchema`, `EntityDisplayInfoSchema`; added `host_diagram_id: optional(String)` to both entity schemas; removed unused `EntityTypeNameSchema`/`DomainNameSchema`; `DiagramDetailView.helpers.ts` extracted `buildAliasToId` + `isDiagramOnly`. New test files: `tests/tools/test_diagram_only_read_contract.py` (17 tests — regression for GSN node_id null read, extraction, connections); `tools/gui/src/ui/views/__tests__/DiagramDetailView.diagramOnly.test.ts` (13 tests — schema decoding, alias map, isDiagramOnly). Results: pytest 2736/2736, ruff clean, zuban pass, vitest 134/134, lint clean, typecheck clean.
- 2026-06-19 — WU-E3 done. drilldownByEntityId computed on frontend from existing c4Nav.child_diagrams[].scope_entity_id (no backend change — data was already present). SVG drill badge injected in attachInteractivity via getBBox()+svgEl.appendChild for each entity with a drill target; badge click navigates via router.push. Replaced old .c4-nav panel (parent+child links in one block) with .c4-up-banner (sticky, above canvas, parents only) + .c4-child-nav (de-emphasised child links). Files: DiagramDetailView.helpers.ts (new), DiagramDetailView.vue (import, computed, badge injection, template, styles). New test file: DiagramDetailView.drilldown.test.ts (13 tests). Results: vitest 107/107, lint clean, typecheck clean, pytest 2719/2719, ruff clean, zuban pass.
- 2026-06-19 — WU-E6 done. Removed description line from default `_render_item_body` output; added `show_node_descriptions` flag (default `false`) read from `config["c4"]["show_node_descriptions"]` in `render_body`; threaded as `show_descriptions` kwarg through `_render_item` → `_render_item_body`. `_ResolvedItem.description` and `_short_description` unchanged. Updated outdated comment in test_c4_person_rendering.py. New test file: tests/rendering/test_c4_node_description.py (11 tests). Results: pytest 2746/2746, ruff clean, zuban pass.
- 2026-06-20 — WU-F1 done. Added `primitive_types: tuple[str, ...]` to `DiagramTypeUiConfig` (domain/diagram_type_config.py); added scalar catalog (String/Integer/Number/Boolean/Date/DateTime/UUID) to `src/diagram_types/datatype/config.yaml`; added `primitive_types` to frontend `DiagramTypeUiConfigSchema` (schemas.ts). Extracted `buildTypeOptions` to `ClassifierCard.helpers.ts`; `ClassifierCard.vue` replaced free-text type input with `<input list=...>` + `<datalist>` (scalars ∪ in-diagram classifiers ∪ free entry); `DatatypeEditor.vue` now accepts `uiConfig` prop and passes `primitiveTypes`/`classifierLabels` down. New test files: `tests/diagram_types/test_datatype_primitive_types.py` (4 tests), `tools/gui/src/ui/diagram-types/datatype/__tests__/ClassifierCard.typeOptions.test.ts` (7 tests). Results: pytest 2783/2783, ruff clean, zuban pass, vitest 141/141, lint clean, typecheck clean.
- 2026-06-20 — WU-E7 done. Replaced skinparam-rectangle C4 style with C4-PlantUML stdlib macros (`!include <C4/C4_Component>`). New files: `_c4_types.py` (shared dataclasses incl. `_ResolvedItem.shape`), `_resolve_model.py` (model-backed resolution); rewritten `_resolve.py` (re-exports for compat; 175 lines) and `renderer.py` (230 lines). Shape resolution order: explicit `shape` attr → technology keyword inference (DB/queue sets) → item-type default macro. Technology inference via `_tech_variant()` → `_c4_macro_name()` produces `ContainerDb/ContainerQueue/Person_Ext/System_Ext` etc. Boundary rendering: `System_Boundary(alias, "label") {`. Extended `extract_declared_puml_aliases` in `artifact_parsing.py` with `_PUML_MACRO_ALIAS_RE` to recognise `MacroName(ALIAS, ...)` syntax (general, not C4-specific) — fixes E309 verifier false-positive on macro-style diagrams. New test file: `tests/rendering/test_c4_node_shapes.py` (33 tests). Updated: `test_c4_renderer.py`, `test_c4_person_rendering.py`, `test_c4_node_description.py`. Results: pytest 2779/2779, ruff clean, zuban pass.
- 2026-06-20 — WU-F3 in-progress. Intent: expose attribute-level uniqueness, add classifier composite unique constraints, render both forms, and validate composite constraint references through a datatype-owned verification contribution before the UX capstone.
- 2026-06-20 — WU-F3 done. Added attribute `{unique}` checkbox/render marker; classifier `unique_constraints: string[][]` ontology + multi-select editor + UML constraint notes; datatype-owned E337 contribution rejects empty, duplicate, or unknown attribute references. Added pure GUI constraint helpers/tests and backend verifier/renderer tests; regenerated types. Results: pytest 3036 passed, 2 skipped; GUI 134 tests; lint, typecheck, Ruff, Zuban, and diff checks clean.
- 2026-06-20 — WU-F5 in-progress. Intent: reorganize datatype cards into Identity, Attributes/Literals, Constraints, and Notes sections; align controls and labels with activity/sequence editors; clarify the backing-relation status and quick-fix action.
- 2026-06-20 — WU-F5 done. Reorganized classifier cards into labelled Identity, Attributes/Literals, Constraints, and Notes sections; clarified classifier naming, Data Object binding, and add actions; aligned section/control styling with activity/sequence editors. Reworded backing status and quick-fix action to explain that a compatible model relation is required and will be created/bound. Results: pytest 3036 passed, 2 skipped; GUI 134 tests; lint, typecheck, Ruff, Zuban, and diff checks clean.
- 2026-06-20 — WU-G-INV in-progress. Intent: inventory the actual assurance capability surface, define one exposure policy, benchmark direct filtered reads, design the first-class analysis aggregate migration, and specify the classification-gated GSN dual-home bridge before implementing G1–G6.
- 2026-06-20 — WU-G-INV done. Added `docs/04-assurance/gui-capability-design.md` with the code-backed capability matrix, missing application-use-case prerequisites, shared non-leaking exposure contract, staged audited analysis migration, and TLP-gated GSN dual-home bridge. Added reproducible encrypted benchmark `tools/benchmark_assurance_direct_reads.py`; 100k nodes/8 readers: direct search p95 31.836 ms, so G3 will use direct parameterized SQLCipher queries rather than an in-memory index. Results: pytest 3036 passed, 2 skipped; GUI 134 tests; lint, typecheck, Ruff, and Zuban clean.
- 2026-06-20 — WU-G0 in-progress. Intent: turn the architecture-grounding directive into explicit cross-cutting contracts for analysis entry, bidirectional navigation, gap detection, and model-and-bind orchestration before the G1/G2 implementation milestone.
- 2026-06-20 — WU-G0 done. Extended the assurance GUI design with mandatory architecture anchors, architecture-lens/back-navigation contracts, shared binding/gap states, and direct-bind vs separation-of-duties `ModelAndBind` outcomes. Self-model: updated the existing Assurance to Architecture Linkage requirement, GUI Authoring Tool, and Assurance Service; added realizations from GUI and service to the requirement; corrected the GUI's stale MCP claim to REST. Model verify: 626/626 valid, one pre-existing W160. Results: pytest 3036 passed, 2 skipped; GUI 134 tests; lint, typecheck, Ruff, and Zuban clean.
- 2026-06-20 — WU-G1 in-progress. Intent: implement the application-layer exposure policy and analysis-scoped read use cases, route both HTTP and MCP reads through them, and add locked/404/no-leak contracts before the G2 browse UI consumes the surface.
- 2026-06-20 — WU-G1 done. New files: `src/application/assurance_exposure.py` (AssuranceExposurePolicy, is_above_ceiling, PolicyScope, Visible, Locked, NotFound, ForbiddenWrite; ~155 lines), `src/application/assurance_queries.py` (coverage_gaps, risk_register extracted from MCP; ~100 lines), `src/infrastructure/gui/routers/_assurance_read.py` (11 unlock-gated read endpoints, all via policy; ~270 lines). Updated: `routers/assurance.py` (include read_router), `mcp/read_tools.py` + `dashboard_tools.py` + `security_read_tools.py` (delegate to shared policy/queries; removed ~120 lines of inline logic). New test files: `tests/application/test_assurance_exposure.py` (28 pure-policy unit tests), `tests/assurance/test_assurance_http_read.py` (12 negative-leak/locked/no-store HTTP tests). Updated: `test_max_classification.py` (TestFilterByCeiling → AssuranceExposurePolicy). Results: pytest 3076 passed, 2 skipped; ruff clean; zuban pass.
- 2026-06-20 — WU-G2 in-progress. Intent: new AssuranceBrowseView (faceted filter + node list + inline detail panel) at /assurance/browse; AssuranceNodeDetail component (arch refs link to /entity; in/out edges); AssuranceLens component on EntityDetailView (additive, silent when locked, links to browse view via helpers).
- 2026-06-20 — WU-G2 done. New frontend files: `AssuranceLens.vue` + `AssuranceLens.helpers.ts` (parseLensResponse + browseLinkForNode; hidden when locked/empty), `AssuranceNodeDetail.vue` (node identity/content/arch-refs/edges; RouterLink to /entity for arch refs), `AssuranceBrowseView.vue` (faceted filter: type/status/concern/tlp/binding; node list; inline detail panel). Router: `/assurance/browse` added; `/assurance/analyses` → redirect to browse. `AssuranceView.vue` updated hint + link. `EntityDetailView.vue` imports + uses AssuranceLens after connections section. New test file: `views/__tests__/assuranceBrowse.test.ts` (16 tests: parseLensResponse + filter logic + router config). Results: vitest 150/150, lint clean, typecheck clean, pytest 3076 passed 2 skipped, ruff clean, zuban pass.
- 2026-06-20 — WU-G3 done. Direct SQLCipher queries (G-INV benchmark: p95 31.836ms); no index. Files: `assurance_ports.py` (+`search_nodes` to protocol), `_sqlcipher_store.py` (parameterized LIKE query), `_private_git_store.py`/`_encrypted_private_git_store.py`/`_pocketbase_store.py` (in-memory filter over `list_nodes`), `_assurance_read.py` (`GET /api/assurance/search` + `_assurance_hit()` helper), `entity_search.py` (`_try_assurance_hits()` global merge), `SearchView.vue` (`assurance-node` → `/assurance/browse?node_id=`). New test files: `test_assurance_search_safety.py` (no-new-file test + concurrent HTTP test + store behaviours), extended `test_assurance_http_read.py` (+`search_nodes` to `_FakeStore` + 7 search tests). Results: pytest 3092 passed 2 skipped, ruff clean, zuban pass, vitest 150/150, lint clean, typecheck clean.
- 2026-06-20 — WU-G6 done. Item 1 (arch-repo diagrams): already satisfied by existing pipeline — no new code. Item 2: `src/application/assurance_diagrams.py` (render_control_structure + render_uca_matrix projectors; AVAILABLE_DIAGRAMS catalog), `_assurance_read.py` (+`GET /api/assurance/diagrams` + `GET /api/assurance/diagrams/{id}/rendered`; exposure-policy filtered; SVG via render_puml_svg if plantuml available, PUML text always). Item 3: `tools/gui/src/ui/views/AssuranceBaselinesView.vue` (list + seal form at /assurance/baselines), `AssuranceDiagramsView.vue` (sidebar + panel at /assurance/diagrams), `AssuranceDiagramPanel.vue` (SVG/PUML display component), router (`/assurance/baselines`, `/assurance/diagrams`), `AssuranceView.vue` (baselines + diagrams links). New test files: `tests/assurance/test_assurance_diagrams.py` (13 tests — projector purity), `tests/assurance/test_assurance_diagram_http.py` (10 tests — HTTP contracts). Results: pytest 3158 passed 2 skipped, ruff clean, zuban pass, vitest 176/176, lint clean, typecheck clean.
- 2026-06-20 — WU-G5 decomposed. Picking up G5 surfaced two unmet backing prerequisites that
  WU-G-INV's "required application use cases" list explicitly flagged but G1–G4 did not build: (#1)
  the analysis aggregate (today only a nullable `analysis_id` column on baselines + an optional
  filter param — no CRUD, no aggregate, no node-level `analysis_id`), and (#7) `ModelAndBind`
  orchestration (`assurance_model_this` still returns a spec only; the G-INV `Bound`/`TaskRequired`
  use case was never built). Per the plan's "do not build a wizard step on a missing capability"
  rule and the user's direction, building the prerequisites first. Split G5 into: **G5-P1** analysis
  aggregate foundation → **G5-P2** ModelAndBind → **G5-P3** analysis REST/MCP + frontend picker →
  **G5a** STPA wizard + **G5b** GRC wizard (first shippable milestone, OQ-4) → **G5c** the rest.
  Migration approach for the analysis aggregate: forward-only (greenfield/pre-prod store, "major
  reworks OK"); add the table + node `analysis_id` column, enforce the FK/anchor invariants at the
  application layer. The staged production-data migration in the G-INV design doc is deferred until
  there is real data to partition.
- 2026-06-20 — WU-G5a impl+tests **done** → `review` (live Playwright smoke pending a backend
  restart; `/api/assurance/guidance` currently 404 on the running backend, `/api/assurance/analyses`
  already 200). **Backend prep:** threaded `analysis_id` through node creation
  (`mutations.create_node` + HTTP `CreateNodeBody`/endpoint + MCP `assurance_create_node`) so wizard
  nodes belong to the analysis; moved `guidance.py` → `src/application/assurance_guidance.py` (pure
  content; re-pointed the MCP import — application is the principled home, lets HTTP reuse it without
  GUI→MCP coupling); added analysis scoping to `run_stpa_complete`; new endpoints
  `GET /api/assurance/guidance` + `GET /api/assurance/stpa-complete` in `_assurance_analysis_routes.py`.
  **Frontend:** `AssuranceStpaWizardView.vue` (stepper: Losses → Hazards → Control Structure → UCAs →
  Constraints → Review; per-step guidance panel + analysis-scoped node list + add form; per-node
  relation linker for the completeness edges (hazard leads-to loss, uca violates hazard); UCA
  guideword grid that creates UCA + concerns edge; model-&-bind affordance on unbound
  control-structure nodes → browse; Review runs stpa-complete + seal-gated-on-pass) +
  `AssuranceStpaWizard.helpers.ts` (pure: STEPS, guideword grid, completeness summary, step badges,
  unbound nodes). Route `/assurance/stpa` + landing-page link. New tests:
  `tests/assurance/test_assurance_analysis_http.py` (+guidance/stpa-complete/locked),
  `test_assurance_http_write.py` (+node carries analysis_id), `AssuranceStpaWizard.test.ts` (9
  helper tests). Full gate: pytest 3204 passed / 2 skipped, ruff + zuban clean; GUI lint/typecheck
  clean, vitest 195 passed. **Backend restart needed** for the new endpoints; **session restart**
  for the `analysis_id` param on `assurance_create_node`. Next: **G5b** (GRC wizard).
- 2026-06-21 — WU-G5a **done** (was `review`). Backend + Claude session restarted; the new endpoints
  are now live on the running backend. Live API smoke against the **real unlocked SQLCipher store**:
  `GET /api/assurance/status` → `unlocked`; `GET /api/assurance/guidance?topic=stpa-losses` returns
  the full coaching record (step/what/why/how/standards) — confirmed the hyphenated topic keys the
  wizard helper emits (`stpa-losses`…`stpa-constraints`) match the guidance dictionary;
  `GET /api/assurance/stpa-complete` returns all six coverage checks; `GET /api/assurance/analyses`
  returns the exposure-filtered (`visibility_limited`) scoped list. Browser-level Playwright smoke
  could not run — the Playwright MCP is pinned to the `chrome` channel, which isn't installed and whose
  install needs sudo (no TTY for the password); only bundled chromium is present. Write paths
  (create-analysis/node/edge, seal) are left covered by the green integration suites rather than
  polluting the confidential dogfood store (no delete-analysis by design). Next: **G5b** (GRC wizard).
- 2026-06-20 — WU-G5a in-progress. Intent: build the guided STPA wizard (Losses → Hazards →
  Control Structure → UCAs guideword grid → Constraints → completeness → seal), analysis-scoped, with
  per-step `assurance_guidance` coaching and model-this gap affordances. Backend prep: thread
  `analysis_id` through node creation (`mutations.create_node` + HTTP `CreateNodeBody` + MCP
  `assurance_create_node`) so wizard nodes belong to the analysis; move `guidance.py` content to a new
  `src/application/assurance_guidance.py` (pure method-coaching content; re-point the MCP import) and
  add `GET /api/assurance/guidance`; add analysis scoping to `run_stpa_complete` + a
  `GET /api/assurance/stpa-complete` endpoint. Frontend: `AssuranceStpaWizardView` + pure helpers +
  tests.
- 2026-06-20 — WU-G5-P3 **done**. Exposed the analysis aggregate over REST + MCP, added
  analysis-scoped read filtering, and a frontend analysis picker. **Exposure:** added
  `filter_analyses`/`apply_analysis` to `AssuranceExposurePolicy` (above-ceiling analyses omitted
  from lists, indistinguishable 404 on direct read). **REST:** new
  `src/infrastructure/gui/routers/_assurance_analysis_routes.py` (`GET/POST /api/assurance/analyses`,
  `GET/PATCH /api/assurance/analyses/{id}`) wired in `assurance.py`; added `analysis_id` filter to
  `GET /api/assurance/nodes`. Extracted shared HTTP helpers to `_assurance_http.py`
  (`build_policy`/`locked_response`/`not_found_response`/`ok`) — this also trimmed `_assurance_read.py`
  back under the 350 limit (kept its own local `_policy` so existing test patch-sites stay valid).
  **MCP:** `assurance_list_analyses` (read; list/get + exposure), `assurance_create_analysis` +
  `assurance_update_analysis` (write; delegate to the use cases). **Frontend:**
  `AssuranceAnalysisPicker.vue` + `.helpers.ts` (select existing / inline-create an analysis; method
  enum + optional anchor); `AssuranceBrowseView.vue` now scopes the node list by selected analysis
  (`nodesUrlForAnalysis`, watch-driven reload). Also replaced production `assert isinstance(...)`
  type-narrowing with positive `isinstance` checks (per user — assert is stripped under `python -O`),
  in the new code and the two adjacent pre-existing read paths. New tests:
  `tests/assurance/test_assurance_analysis_http.py` (12; CRUD/locked/invalid/exposure/scoping) using
  `monkeypatch` (no patch leakage), `AssuranceAnalysisPicker.test.ts` (10 helper tests). Fixed a
  fake-store conformance gap (`list_nodes` gained `analysis_id`) and my own leaking-patch bug in the
  new HTTP test. Full gate: pytest 3199 passed / 2 skipped, ruff + zuban clean; GUI lint/typecheck
  clean, vitest 186 passed. **Backend restart + Claude session restart needed** (new MCP tools).
  Next: **G5a** (STPA wizard) — first shippable wizard milestone.
- 2026-06-20 — WU-G5-P2 **done**. New `src/application/assurance_model_bind.py`: `ModelAndBind`
  use case + `ArchitectureEntityCreator` port (Protocol) + typed outcomes
  `Bound`/`TaskRequired`/`BindLocked`/`BindNotFound`/`BindInvalid` + `build_task_spec`. Bound path
  reuses `assurance_mutations.register_arch_ref`+`edit_node` (audit + post-write verify); on
  post-create binding failure returns a compensating `TaskRequired` referencing the already-created
  entity and leaves the node `unbound-pending` (no cross-repo atomicity claim). New infra adapter
  `src/infrastructure/gui/routers/_arch_entity_creator.py` (`GuiArchitectureEntityCreator`) wraps the
  backend serialized write path. HTTP `model_this` rewritten to delegate (default → create+bind;
  `separation_of_duties=true` → task) with `_translate_bind` (200 bound / 200 task_required /
  423 / 404 / 409 / 400). MCP `assurance_model_this` delegates with `arch_creator=None` (assurance
  server is arch-write-free → always task) — removed the inlined spec duplication. Dependency policy
  respected (application→application only; adapter is infrastructure). New tests:
  `tests/assurance/test_assurance_model_bind.py` (7: preconditions, task, unknown-type, bound,
  compensating-task); extended `test_assurance_http_write.py` (separation-of-duties task +
  patched-creator bound path). Full gate: pytest 3187 passed / 2 skipped, ruff clean, zuban clean.
  **Backend restart needed** before MCP/HTTP `model_this` reflects the new behaviour. Next: **G5-P3**
  (analysis REST/MCP surface + frontend analysis picker) — the last prerequisite before the STPA/GRC
  wizards (G5a/G5b).
- 2026-06-20 — WU-G5-P2 in-progress. Intent: build the `ModelAndBind` application use case
  (`src/application/assurance_model_bind.py`) with an `ArchitectureEntityCreator` port and typed
  outcomes `Bound`/`TaskRequired`/`BindLocked`/`BindNotFound`/`BindInvalid`. Bound path reuses
  `assurance_mutations.register_arch_ref`+`edit_node` (audit + post-write verify); on post-create
  binding failure it returns a compensating `TaskRequired` and leaves the node `unbound-pending`
  (never claims cross-repo atomicity). Wire HTTP `model_this` with a GUI-backed creator (unified
  backend → Bound by default; `separation_of_duties=true` → TaskRequired) and MCP
  `assurance_model_this` with creator=None (assurance-scoped server → always TaskRequired), both
  delegating to the use case (removes the inlined spec duplication).
- 2026-06-20 — WU-G5-P1 **done**. Resolved the design question: analysis carries a **single but
  OPTIONAL** `architecture_anchor_id` (user decision B) — names the system-under-analysis when one
  applies (STPA/CAST), empty for cross-system work (GRC); individual nodes still carry their own
  arch refs. Made anchor optional end-to-end (schema default `''`, port/use-case/adapters), dropped
  the `missing_anchor` invariant. **Architecture fix:** the analysis vocabulary
  (`ANALYSIS_METHODS/STATUSES/UPDATABLE`) was moved to a new **domain** module
  `src/domain/assurance_analysis.py` so the application use case imports it from domain, not
  infrastructure — fixed a real dependency-policy violation (NOT baselined; policy matrix
  untouched). **Central clock (user request):** new `src/domain/clock.py`
  (`epoch_seconds`/`utc_now_iso`/`utc_now_compact`) is now the single source for every ID epoch and
  timestamp across the repo (arch-repo `generate_entity_id`, group-registry ids, all assurance
  store/archive/worm/signals ids + timestamps). Audit confirmed zero timezone-dependent calls
  (no `localtime`/`datetime.now()`/`mktime`/`fromtimestamp`); the central module enforces UTC in one
  place so it can't regress. New tests: `tests/domain/test_clock.py` (5, incl. TZ-independence).
  Also de-flaked `test_concurrent_search_via_http_completes` (per-thread `mock.patch` raced on a
  shared module global → spurious 423; now patched once around the thread lifecycle) — verified 6/6.
  Files: `src/domain/clock.py` (NEW), `src/domain/assurance_analysis.py` (NEW),
  `src/application/{modeling/artifact_write,group_registry,group_registry_validation,assurance_analysis}.py`,
  `_id_utils.py`, `_schema.py`, `assurance_ports.py`, all 4 store adapters + `_sqlcipher_analysis.py`
  + `_pocketbase_analysis.py` + `_analysis_records.py` + `_sqlcipher_util.py`, `pocketbase_lifecycle.py`,
  and the assurance archive/worm/signals/aibom/lifecycle modules (clock wiring). Full gate:
  pytest 3179 passed / 2 skipped, ruff clean, zuban clean. **Backend restart needed** before the new
  analysis port methods are callable via MCP/HTTP. Next: **G5-P2** (ModelAndBind orchestration).
- 2026-06-20 — WU-G5-P1 code landed, gates green, **paused for design review** (NOT done). Files:
  `_id_utils.py` (`make_analysis_id`), `_analysis_records.py` (NEW: record shape/vocab/filters +
  `FileAnalysisStoreMixin`), `_sqlcipher_util.py` (NEW: extracted SQL plumbing to free room),
  `_sqlcipher_analysis.py` (NEW: analysis SQL), `_pocketbase_analysis.py` (NEW: REST analysis +
  `RestAnalysisStoreMixin`), `_schema.py` (analyses table + node `analysis_id` migration + indices,
  SCHEMA_VERSION 3), `assurance_ports.py` (analysis CRUD on the port + `analysis_id` on
  create_node/list_nodes), all four store adapters, `pocketbase_lifecycle.py`,
  `assurance_analysis.py` (NEW use cases), `tests/assurance/test_assurance_analysis.py` (NEW, 16+1
  tests incl. real private-git round-trip). zuban clean; ruff clean; assurance suite 479 passed /
  1 skipped. **Open design question raised by user:** whether an analysis should carry a *single*
  `architecture_anchor_id` (system-under-analysis scope) vs. collect many lower-level assurance
  artifacts each binding to many model entities. The single-anchor invariant came from the G-INV
  design doc (OQ-5 + the G0 "analysis requires one visible architecture anchor" contract). Holding
  before G5-P2 until the user confirms or revises this. No code reverted.
- 2026-06-20 — WU-G5-P1 in-progress. Intent: add a first-class `AssuranceAnalysis` aggregate —
  `assurance_analyses` table + node `analysis_id`; analysis CRUD on the `ConfidentialAssuranceStore`
  port implemented across all four adapters (SQLCipher, private-git, encrypted-private-git,
  pocketbase); a shared analysis-record helper; and an `assurance_analysis.py` application use-case
  module (create/list/get/update) enforcing method-enum + required architecture anchor + unlocked,
  with audit on create and typed outcomes mirroring `assurance_mutations`.
- 2026-06-20 — WU-G4 done. New files: `src/application/assurance_mutations.py` (shared use cases: create/edit/delete node, add/delete edge, register-arch-ref; MutationOk|MutationLocked|MutationNotFound typed outcomes; post-write verify; E503 safeguard), `src/infrastructure/mcp/assurance_mcp/write_tools.py` (rewritten; all mutations delegate to use cases; new `assurance_delete_edge` tool), `src/infrastructure/assurance/security_write_tools.py` (BOM/vuln/anchor now unlock-checked + audited), `src/infrastructure/gui/routers/_assurance_write.py` (POST/PATCH/DELETE nodes; POST/DELETE edges; POST baselines/seal/arch-refs/model-this; Cache-Control: no-store; 423/404/409/200), `tools/gui/src/ui/views/AssuranceNodeForm.vue` + `AssuranceNodeForm.helpers.ts` (type-aware form; E503 safeguard warning), `tools/gui/src/ui/components/AssuranceEdgePicker.vue` (typed conn picker), `tools/gui/src/ui/views/AssuranceBrowseView.vue` (rewritten with create/edit/delete/add-edge panel modes). New test files: `tests/assurance/test_assurance_mutations.py` (38 tests), `tests/assurance/test_assurance_http_write.py` (24 tests), `tools/gui/src/ui/views/__tests__/AssuranceNodeForm.test.ts` (pure-logic helpers tests). Results: pytest 3135 passed 2 skipped, ruff clean, zuban pass, vitest 176/176, lint clean, typecheck clean.
- 2026-06-21 — WU-G7 **done**. Replaced generic `card`/`database`/`usecase` approximations with a
  dedicated GSN diagram module: reusable semantic PUML macros (`notation.puml`) plus an optional
  `NativeSvgDiagramRenderer` capability, dispatched generically by the rendering infrastructure.
  `svg_renderer.py` owns exact Community Standard geometry (goal rectangle, strategy parallelogram,
  solution circle, context stadium, assumption/justification ovals, undeveloped diamond), layered
  layout, filled/hollow connector heads, stable `data-qualified-name` click targets, and accessible
  labels. Native SVG is used for GUI previews and persisted SVG; misleading fallback PNG output is
  skipped. PlantUML fallback remains syntactically valid and portable. Extracted ephemeral rendering
  runtime from `diagram_builder.py` to keep both modules below the file-size limits. Tests cover every
  shape, connectors, click targets, accessibility, native preview dispatch, fallback syntax, unknown
  diagram types, and source length. Full gate: pytest 3228 passed / 2 skipped; Ruff and Zuban clean.
  Self-model: added `APP@1782027168.bARYLw` GSN Diagram Type Module, aggregated by Module Catalog and
  realizing Pluggable Diagram-Type Verification & Rendering; model verify 625/625 valid, one
  pre-existing W160. The running architecture-write MCP still has the old renderer loaded, so
  re-rendering the stored GSN exemplar requires a backend/session restart. Next: **G5c-4**.

---

## Reusable session-start prompt

Paste this to begin any new session/iteration on this work (after context-clearing):

```
You are implementing PLAN-gui-correctness-and-assurance-completeness.md.
TASKS-gui-correctness-and-assurance.md is the progress ledger and decision record.

ORIENT — read the plan freely; it is curated context, do not ration it.
- Read the ledger: the status table AND the Decision log. Decisions marked `decided`/`settled` are
  FINAL — do not reopen or re-ask them.
- In the plan, read §0 (cross-cutting), the "For implementers" section, the phase intro of the WU you
  pick, that WU in full, and any WU it depends on.

PICK ONE WU.
- From the status table take the topmost `todo`/`in-progress` WU whose dependencies are all `done`.
- Set it `in-progress`; add a dated progress-log line with your intent.
- Stop and ask me ONLY if the WU needs a NEW design decision absent from the Decision log (e.g. the
  B3 typed-property spike, OQ-2). Never re-ask a settled decision.

IMPLEMENT — ration codebase & self-model exploration, not plan reading.
- The WU cites the exact file:line and model facts you need. Open each cited location ONCE to confirm
  it still matches, then act. Do NOT broad-grep the src tree, sweep subsystems, or query the
  ~340-entity self-model unless the WU says "[HYP] reproduce first" or "find/confirm" — and then scope
  the search to exactly what is named. Re-deriving what the plan states wastes the budget.
- Principled fixes at the correct layer only — no workarounds; after such a fix add a regression test
  AND a contract/delegation test.
- ALL model/diagram/document/assurance writes go through MCP tools (artifact_*/assurance_*), never
  hand edits; if a tool is wrong, fix the tool. Tools run against a long-running backend — tell me
  when a code change needs a backend restart (I perform it) or an MCP-surface change needs a session
  restart, and sequence work so you don't block mid-session.
- Python files ≤350 lines; "arch" naming; no phase names in code/tests; regenerate
  types.generated.ts after any ontology change.

VERIFY — all green before `done`.
- Backend: `python -m pytest --tb=short -q` · `ruff check src/ tests/` · `uv run zuban check`.
- Frontend (in tools/gui): `npm run lint` · `npm run typecheck` · `npm run test`.
- For UI/diagram WUs, confirm real behaviour (Playwright MCP at localhost:5173, or render the PUML).

RECORD & STOP.
- Tick the WU's checklist in the plan; set its ledger status (`done`, or `review` if it needs my
  sign-off); append a progress-log line: WU id, files changed, test results.
- One WU per turn. Don't commit/push unless I ask. Report concisely what you did and the next WU.
```
