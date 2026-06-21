# PLAN — GUI Correctness & Assurance Remediation (make "done" mean "works")

Status: approved · Mode: [PLAN] (embedded [DESIGN] decisions flagged inline)

Companion to `PLAN-gui-correctness-and-assurance-completeness.md`. That plan was implemented and
almost every checklist item is marked `[x]`, yet a live walkthrough shows many defects remain — most
severely, the confidential assurance capability throws intermittent **500s** and is usually
unusable. This plan (a) **fixes the remaining issues**, (b) **explains why they were not caught**
despite being marked done, and (c) **installs preventive strategies + scoped tests** so a future
"done" actually means "works for a user".

Ledger: `TASKS-gui-correctness-and-assurance-remediation.md` (source of truth for progress +
measurable acceptance criteria). Verification legend (inherited): **[OBS]** reproduced/confirmed by
observation · **[CODE]** confirmed by reading code · **[HYP]** hypothesis, reproduce before coding.

---

## 0. Cross-cutting constraints

- **Scalability requirement.** A deployment is either *single-architect local* or *team-serving*; a
  team-serving deployment must serve a team's **GUI and MCP** users concurrently. Concrete sizing for
  testing: **~12 GUI users + ~12 agents** issuing many concurrent MCP calls. The model captures the
  general requirement (reads concurrent, writes serialized); the numbers live in the load test, not
  the self-model.
- **Confidentiality is feature-correctness, not access control.** The assurance store is
  TLP-classified by design; the `AssuranceExposurePolicy` (already present) must remain applied
  uniformly across **both** REST and MCP. No plaintext assurance content may be written to disk
  (§ original-plan §0) — this now explicitly includes WAL sidecar files.
- **Principled fixes only** (`CLAUDE.md`): fix at the correct layer, never route around a gap; after
  such a fix add a regression test + a contract/delegation test. Python ≤250 soft / 350 hard LoC;
  `.md` exempt. No phase names in code/tests. Commit/push only when asked.
- **Quality gates (every change):** `python -m pytest --tb=short -q` (0 fail) → `ruff check src/
  tests/` → `uv run zuban check`; frontend (`tools/gui`) `npm run lint` → `npm run typecheck` →
  `npm run test`. Regenerate `types.generated.ts` after any ontology change.
- **Definition of done (upgraded).** Each user-visible task is done only with an **[OBS] artifact**
  (screenshot or asserted DOM/SVG) **and** a regression test — not code + green unit tests alone.

---

## Root cause of the *process* failure (why "done" ≠ "works")

Confirmed this session:

1. **The flakiness is a cross-thread SQLite bug, invisible to the test suite.**
   `src/infrastructure/assurance/_sqlcipher_store.py:54` calls `sqlcipher3.connect(...)` with no
   `check_same_thread=False` and stores a single `self._conn` (created on whichever thread first
   unlocked). The store is a **process singleton** (`app_bootstrap.py:45` →
   `store_factory.get_assurance_bundle`), but the one uvicorn process serves REST endpoints *and* the
   FastMCP assurance servers on an **anyio threadpool** — so any call on a thread ≠ the unlock thread
   raises *"SQLite objects created in a thread can only be used in that same thread."* Reproduced
   this session via `assurance_stats` / `assurance_list_analyses`. "A1 appears then vanishes" and
   "viewing was the exception" are exactly this: success only when a request lands on the unlock
   thread. The existing assurance HTTP tests use FastAPI `TestClient`, whose **single portal thread**
   runs unlock + queries together, so the bug **cannot** appear there. No test exercises the real
   multi-threaded server; none exercises concurrency.

2. **Completion was certified from code-reading + isolated unit/Vitest tests, not live behaviour.**
   `[x]` was awarded on `[CODE]`-level evidence; many notes describe the *change made*, not an
   *observation that the user-visible result is correct*. E.g. WU-E4 added `C4ModelBackedPanel.vue`
   (wired at `C4DiagramEditor.vue:209`) but it renders from `props.entities`; if the edit view never
   passes the derived projection, the panel is correctly coded yet empty — the reported symptom.

3. **Frontend tests cover pure helpers, not rendered DOM or real responses.** The TLP tag is
   hardcoded red (`AssuranceBrowseView.vue:733`, `AssuranceNodeDetail.vue:316`: `color:#dc2626`) and
   no test asserts colour-by-value, so a value-independent colour passes.

4. **"Golden-PUML" tests assert the PUML *string*, not the rendered diagram.** Person labels, shape
   glyphs and edge anchoring are PlantUML *rendering* outcomes; asserting emitted PUML text misses a
   label PlantUML drops or a shape that renders wrong.

**Net:** the gap is methodological — "done" required code + green unit tests, never a live render or a
concurrent run. WS5 closes exactly this gap and is a first-class deliverable.

---

## Hexagonal soundness (placement of the concurrency machinery)

Concurrency is an **infrastructure** concern and must not leak into domain/application:

- The **read pool** lives inside the SQLCipher adapter (`_sqlcipher_store.py`), behind the existing
  `ConfidentialAssuranceStore` port (`src/application/assurance_ports.py`). Application use cases keep
  calling port methods, unaware of pooling.
- The **single-writer queue** wraps at the **composition boundary** (MCP tool registration + REST
  handler), exactly where arch's `queued()` / `run_sync()` sit — *not* inside use cases or the domain.
  Application logic stays threading-agnostic and unit-testable without a queue.
- The reusable queue primitive is shared infrastructure; the two store domains (arch files+index vs.
  assurance SQLCipher) get **separate queue instances** so they don't falsely serialize — correct
  because they are independent aggregates with independent consistency boundaries.
- **Read/write classification at the boundary** is mandatory: every assurance tool/endpoint is
  declared read (concurrent) or write (queued), made explicit at registration so it can't drift.

---

## WS5 — Prevention test harness (build FIRST, use throughout)

- **Live-server concurrency harness** (`tests/integration/`): start the **real ASGI app** (uvicorn in
  a thread, or a multi-worker threadpool driving the app — not single-thread `TestClient`). Unlock on
  thread A, exercise assurance read+write endpoints from a worker pool; assert zero 5xx and correct
  payloads. **Must fail on current `main`, pass after WS1.** Plus a focused unit test calling store
  methods from a thread ≠ the `unlock()` thread.
- **Realistic load test** (validates the architecture meets the load, not just "no crash"):
  team-serving profile (~12 GUI-like read-heavy clients + ~12 agent-like clients issuing many MCP
  calls incl. a write stream) for a sustained window. Assert: zero errors; **writes observably
  serialize** (max in-flight == 1, consistent final state, no lost updates); **reads stay concurrent**
  (read p95 not collapsed by the write stream) within an agreed budget. Plus a lighter local profile.
- **Playwright route-walk smoke** (driven via the Playwright MCP, then codified): visit every diagram
  type instance + every assurance page the user cited; assert no console 5xx and key DOM facts
  (person-label text present; C4 node = name only; assurance rows render; TLP chip colour varies by
  value).
- **Schema/response contract tests**: decode representative *real* backend responses with the
  frontend Effect schemas (not hand-written fixtures) to catch wire drift.

---

## WS1 — Assurance store concurrency & scalability (CRITICAL; foundational)

**Symptom [OBS].** Intermittent 500s across assurance pages/tools; analyses appear/disappear.
**Root cause [CODE].** Single thread-bound `self._conn` shared across the threadpool (root-cause #1).

**Fix — split reads (concurrent pool) from writes (serialized queue), mirroring arch-write.**

- *Reads — concurrent pool.* In `SQLCipherAssuranceStore` replace the single `self._conn` with a
  **read connection pool**: each connection `check_same_thread=False`, `PRAGMA key`, `PRAGMA
  journal_mode=WAL`, `PRAGMA busy_timeout`; handed out per operation via a context manager
  (`with store.read_connection() as c:`) and returned to the pool. Key read once from the credential
  store and reused per connection (no plaintext persistence; same `creds.get(_KEY_ACCOUNT)` path).
- *Writes — single-writer serialized queue.* Route **all** assurance mutations through a single-worker
  serialized queue exactly as `src/infrastructure/mcp/artifact_mcp/write_queue.py`
  (`ThreadPoolExecutor(max_workers=1)`, `queued()` for MCP write tools, `run_sync()` for REST write
  handlers, `operation_registry`, `wait_until_idle`, **bulk-op** support paralleling
  `artifact_mcp/bulk/`). The worker owns a **dedicated write connection** — every write runs on that
  one thread, so writes are cross-thread-safe *and* race-free (the deliberate "no concurrent writes"
  discipline already adopted on the arch side). **Preferred structure:** extract the `write_queue.py`
  mechanism into a reusable single-worker-queue primitive, instantiated twice (`model-write-queue` +
  new `assurance-write-queue`) so the two independent stores don't falsely serialize while sharing
  one proven mechanism. If clean extraction is disproportionate, build an analogous
  `assurance_write_queue.py` of the same shape — do **not** fork a divergent design.
- *Shared-connection aliases.* `store_factory.py:172,213` capture `sqlcipher_store._conn` via
  `conn_factory`; the colocated signals connector (`_collocated_signals_connector.py`) and archive
  (`_archive.py`) must take a read-pool connection (reads) or run on the write-worker connection
  (writes) per operation, not hold the one bound connection.
- *Lifecycle.* `unlock()` opens the pool + write connection, applies key, sets WAL, runs
  schema/migrations on the bootstrap write connection; `lock()` drains the queue and disposes pool +
  writer; `is_unlocked()` reflects that. Update the store docstring (no longer "single-threaded").
- *🔴 WAL confidentiality.* WAL adds `-wal`/`-shm` sidecars. SQLCipher encrypts the WAL, but this must
  be **proven**: a test inspects the `-wal` file for plaintext assurance content; add ignore rules for
  the sidecars; confirm they never land under a tracked repo/`.arch-*` path. Specify an idempotent
  WAL migration for the existing store.

**Tests.** Cross-thread unit test; writes-serialized test; reads-stay-concurrent test; WAL +
busy_timeout assertions; lock drains+disposes; signals/archive still work; WAL-plaintext test. The
realistic load test lives in WS5.

---

## WS2 — Assurance runtime correctness & management

- **Analysis management / delete.** Abandoned "A1" is visible but unmanageable. Backend has
  `assurance_update_analysis` but **no delete-analysis use case/tool**. Add the application use case +
  MCP tool + HTTP `DELETE /api/assurance/analyses/:id` (cascade vs block-if-nonempty decided in impl)
  routed through the write queue; add an **Analyses management** view/section (delete + status). Add
  the missing capability at the application layer, expose via both MCP and HTTP.
- **Wizard architecture anchor uses the entity picker.** STPA/GRC/CAST wizards take the anchor as
  plain text; replace with `EntityPickerInput.vue` (WU-D2 props) pinned via `fixedEntityTypes` to
  admissible ArchiMate anchor types (cf. `C4DiagramEditor.vue:172`).
- **TLP colours by value.** Replace hardcoded red (`AssuranceBrowseView.vue:733`,
  `AssuranceNodeDetail.vue:316`, check `AssuranceLens.vue`) with one shared TLP→colour helper
  (WHITE neutral/grey, GREEN green, AMBER amber/orange, RED red); Vitest asserts colour varies by
  value.
- **Ceiling "withheld" UX.** Working as designed (ceiling `TLP:AMBER` from
  `storage.assurance.max_classification`; `TLP:RED` omitted). Fix the *explanation*: a clear,
  non-alarming "N items withheld above your TLP:AMBER ceiling" note + document the config.
- **Assurance matrix diagram.** No links to model entities + character word-break. `[HYP — reproduce
  first]` whether this is the generic `matrix` type (`src/diagram_types/matrix/`) or an
  assurance-derived projection; then make cells link to bound model entities (reuse the assurance
  lens arch-ref resolution) and fix column layout to wrap rather than break.

---

## WS3 — Diagram viewer architecture (decided with user)

- **Unified assurance diagram surface.** The assurance diagram viewer (`assurance_diagrams.py`,
  `_assurance_diagram*` routers, `AssuranceDiagram*` components) becomes the *only* place
  bowtie/control-structure/UCA-matrix are viewed and edited — store-grounded, exposure-policy
  filtered, and **functional** (selectable nodes/edges → detail; editable via assurance navigation).
  Remove/redirect these types from the generic diagram viewer registry so they no longer present a
  broken, non-selectable, "edit shows nothing" experience.
- **GSN dual-home.** GSN stays a working general diagram type (real renderer from G7) for
  cleared/architecture diagrams, *and* is reachable from assurance for confidential cases via the
  TLP-gated bridge. GSN nodes/edges must be selectable in the generic viewer (WU-E5 path).
- **C4 edit-view data path (the "still empty" bug).** `C4DiagramEditor.vue` renders
  `C4ModelBackedPanel` from `props.entities`/`props.diagramConnections`. `[HYP — reproduce first]`
  root-cause why `EditDiagramView.vue` does not populate these from the derived projection
  (`context.entities`/`context.connections`); fix the data path so the panel lists derived entities +
  read-only connections.
- **Selection in viewer (C4/GSN).** Verify the WU-E5 diagram-only read contract actually returns
  detail on click in the live viewer; fix any remaining click-target/resolution gap.

---

## WS4 — C4 rendering correctness (assert the *render*, not the PUML string)

All `[HYP — reproduce first]` via PlantUML render harness + Playwright screenshot:

- **Standard C4 shapes/icons** by container technology (db/queue/etc.) + create-view shape selection —
  WU-E7 was left `[ ]`; implement shape-resolution + technology map in
  `src/diagram_types/c4/renderer.py` and expose `shape` selection in the create view.
- **Person labels invisible** (system-context + container) — re-verify the WU-E1 fix renders the
  label in the SVG; fix the person branch if not.
- **Person→container line gap** — re-verify WU-E2; adjust anchoring if present.
- **Long descriptions still shown** on some diagrams but not others — find why instances differ
  (`show_node_descriptions` / diagram-owned `description`) and normalize.
- Replace string-only golden-PUML assertions with **rendered-SVG assertions** (label text present,
  shape element present) for these.

---

## Self-model & docs

- **Motivation layer (kept general).** Model only the general shape via **MCP write tools**: a
  deployment is *single-architect local* or *team-serving* (serves a team's GUI + MCP concurrently).
  Capture one scalability **requirement/constraint** — "a team-serving deployment supports concurrent
  GUI + MCP users; reads concurrent, writes serialized" — linked to the elements that realize it
  (read pool, single-writer queue). No topology specifics (e.g. "VPN") in the model.
- **Structure.** Model via MCP tools: assurance HTTP interface, read-pool + single-writer-queue
  concurrency components (and that arch + assurance share the queue mechanism), the delete-analysis
  use case, the unified assurance-diagram surface. Fix stale "GUI calls MCP" statements (GUI uses
  REST). Update `docs/` (assurance GUI, diagram-viewer behaviour, TLP ceiling, deployment topology).
  Run `artifact_verify`; regenerate `types.generated.ts` if any ontology changes.

---

## Sequencing

**WS5 harness skeleton → WS1 (unblocks all assurance) → WS2 → WS3 → WS4 → self-model/docs.** WS5's
concurrency harness is written first so WS1 has a failing test to make pass.

## Verification (end-to-end)

1. Backend + frontend quality gates green.
2. **Concurrency proof:** WS5 harness fails on `main`, passes after WS1; cross-thread unit test green;
   team-serving load profile error-free with writes serialized + reads concurrent within budget.
3. **Live walkthrough (Playwright MCP)** of the exact URLs cited: person labels visible, C4 standard
   shapes, name-only nodes, selectable nodes/edges with detail, populated C4 edit sidebar, TLP chips
   coloured by value, manageable/deletable analysis, no 500s.
4. **MCP smoke:** `assurance_stats`, `assurance_list_analyses`, `assurance_list_nodes` succeed
   repeatedly (no cross-thread error).

## Open items (resolved during implementation, not blockers)

- Cascade vs block-if-nonempty for analysis delete.
- Whether the matrix defect is the generic `matrix` type or an assurance-derived projection.
- Exact `EditDiagramView.vue` data-path fix for the C4 panel.
- Whether the user expects a ceiling other than `TLP:AMBER`.
