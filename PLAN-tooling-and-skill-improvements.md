# PLAN — Architecture MCP Tooling, Diagram-Label Editing & Modelling-Skill Improvements

Status: draft / ready for pickup (rev. 2 — incorporates design review)
Created: 2026-06-07
Mode: [PLAN] (software-architecture skill)
Owner: (unassigned)

> **How to use this plan (implementer).** Work top-down. Each task states problem →
> solution strategy → exact files/symbols (verified) → steps → its own acceptance.
> Tick units in §9 as you finish them (add commit ref). A task is done only when its
> units + acceptance pass; the plan is done only when the global gates (§8) pass. The
> golden rule from the codebase (`CLAUDE.md`): **fix at the correct architectural layer,
> never route around a gap.** If blocked/ambiguous, record it under the unit and stop.

> **Rev-2 note.** A design review corrected rev-1: T2 targeted the wrong execution path
> (MCP `auto-sync` calls `sync_diagram_to_model()` directly, not `diagram_edit.py`), and
> the real hazard is **diagram deletion**, not a blank placeholder. The plan is now
> defined at the **shared service boundary** and exposed through MCP + REST + bulk, adds
> an **editable-edge-label** capability, and adds a **self-model update** task.

---

## 1. Business context

The repository is operated by humans **and** AI agents over three interfaces (MCP, REST,
CLI/GUI) that, per the self-model (`REQ@1712870400.peinbQ`, `PRI@1780220699.kWgVgr`) and
README, must share behavior. A multi-session C4 effort surfaced concrete defects:

- **Data-loss hazard (critical).** Refreshing a *model-backed* diagram via
  `artifact_edit_diagram(puml="auto-sync")` routes to `sync_diagram_to_model()`
  (`src/infrastructure/mcp/artifact_mcp/edit_tools.py:192`). That service infers entities
  from frontmatter + PUML and, when it finds none, **deletes the diagram**
  (`src/infrastructure/write/artifact_write/diagram_sync.py:~320` → `delete_diagram`). It
  is **not projection-aware**: for a scope-bound diagram it should *re-run the projector*,
  never delete. The same service backs REST `/api/diagram/sync`
  (`src/infrastructure/gui/routers/_diagram_write.py:365`) and bulk auto-sync.
- **`auto-sync` is semantically overloaded.** Today it means "reconcile explicit refs +
  regenerate ArchiMate PUML"; a model-backed diagram needs "re-run the diagram-type
  projector" — a different operation with a different data source and deletion rules. The
  project already distinguishes ViewProjector vs derivation refresh
  (`src/diagram_types/README.md:435`).
- **Connection legality learned by rejection.** Agents author an edge, get verifier-
  rejected, retry. The capability to answer "what may connect X→Y?" already exists in the
  domain (`permissible_connection_types`, `connection_ontology.py`) and at REST
  `/api/ontology` (`connections.py:119`) — but is **absent from the agent guidance
  surface** (`artifact_authoring_guidance`).
- **Edge labels are not editable.** After the C4 verification fix, model-backed edge
  labels are derived short verbs; authors cannot set a view-specific label (e.g.
  "Reads/writes") from the GUI or MCP. The GUI sidebar already shows edge details on
  click but offers no label edit.
- **Monolithic, mis-located skill.** `skills/archimate-modelling` (the canonical dir;
  `.claude/skills/archimate-modelling` is a **symlink** to it) loads in full each
  session, is named too narrowly (covers C4/assurance/SysML now), and ships no task
  templates — agents re-derive the modelling lifecycle that the self-model already
  defines (`PRC@1776635640.U4aAdh`).

## 2. Use-cases

| # | Actor | Scenario | After |
|---|---|---|---|
| U1 | agent/human | Refresh a model-backed diagram | Re-projects from the model; **never deleted/blanked** on empty inference |
| U2 | agent | Choose a connection type for X→Y | One guidance call returns permitted types + direction, no rejected write |
| U3 | agent (new session) | Pick up a task and proceed correctly | Follows the **modeled** lifecycle (`PRC@…U4aAdh`) via a load-on-demand template |
| U4 | maintainer | Understand one tool | Loads a focused per-tool reference on demand |
| U5 | human/agent | Set a clear, view-specific label on a diagram edge | Edits the label in the GUI sidebar or via MCP/REST; the model connection's semantics are untouched |

## 3. 🔴 Security, data & consistency (explicit per skill)

- **Security/auth:** no runtime auth, endpoints’ authz, or trust boundaries change.
  System stays local-first with config-/availability-driven gating
  (`PLAN-backend-runtime-unification.md`). **No new attack surface.**
- **Data integrity (the central concern — T2):** the defect is *destructive*. Invariant:
  a refresh of a **scope-bound** diagram must **never delete or blank** it on empty
  inference; it re-projects, or (if the projection is genuinely empty) yields a valid
  empty view **or an explicit error — never a file deletion**. Dry-run must be
  **byte-for-byte non-mutating**. Standalone + ArchiMate reconcile behavior must be
  **unchanged**. These are enforced as test assertions (T2 acceptance).
- **Aggregates / domain events:** N/A with rationale — diagrams are file-based view
  artifacts in a local tool, not event-sourced aggregates in the company’s event-driven
  sense; the domain-events policy does not apply. (Stated explicitly.)
- **Migrations / "repos must keep working":** no backwards-compat with old *call shapes*
  is required, **but every existing architecture repository must continue to load and
  verify clean.** Concretely: (a) the editable-label field (T4) is **optional**; absent →
  current behavior, no data migration; the diagram frontmatter **schema** must be updated
  to permit it so existing diagrams stay valid. (b) After the T2 service fix, run a
  one-time **engagement-wide refresh+verify** to confirm no model-backed diagram is at
  deletion risk. (c) The skill rename (T6) requires updating the **self-model** reference
  (T7) — that is the only model migration.

## 4. Constraints & conventions (must follow)

- **Canonical quality gates** (every change):
  `uv run pytest --tb=short -q` → `uv run ruff check src tests gen_id.py` →
  `uv run zuban check`. (Use these exact commands; do not assert ruff covers configs it
  does not — if E501/tests coverage is wanted, change `ruff` config deliberately.)
- **Service-layer first, then adapters (🔴 architectural).** Behavior changes (T2, T3,
  T4) are defined once at the application/service boundary and exposed through MCP **and**
  REST (and bulk where relevant). Add **service-contract tests** + **thin adapter tests**;
  do not duplicate logic per interface. (Aligns with `REQ@…peinbQ`, `PRI@…kWgVgr`.)
- **Keep the MCP tool surface small.** Prefer extending an existing tool over adding one
  (T3 extends `artifact_authoring_guidance`; T4 extends `artifact_edit_diagram`). Tool
  **descriptions** grow ≤ ~2 lines per change.
- **No plan/phase/`T*`/`U*`/section labels in code, tests, skill, or filenames** —
  describe behavior instead.
- Code files 250 soft / 350 hard lines; SRP; no diagram-type/ontology logic in generic
  components; separate test file per component/use-case.
- **Skill topology:** edit the canonical `skills/…`; keep `.claude/skills/…` as a
  symlink. No backwards-compat redirect required (per maintainer) — but update every
  reference (incl. the self-model, T7) so nothing dangles.
- **MCP-surface changes** (params/descriptions on `authoring_guidance`, `edit_diagram`)
  require the **user to restart the backend** (SSH passphrase) **and** restart the
  **Claude session** (reload schemas). Internal-only changes need only a backend restart.
  State this in the handoff.

---

## 5. Tasks

### T1 — Specify refresh semantics & non-destructive invariants (design, no code)

**Problem.** "auto-sync" conflates projector-refresh with model-reference reconciliation
and has destructive edge-cases (§1).

**Solution strategy.** Write a short **dispatch matrix** (in this plan + a docstring in
the service module) keyed by *diagram ownership/capability*:

| Diagram kind | Refresh = | Empty result → | Deletion allowed? |
|---|---|---|---|
| Model-backed (has `scoped-by` binding / projector) | re-run the diagram-type **projector** | valid empty view **or** explicit error | **No** |
| ArchiMate reconcile (explicit refs, no projector) | reconcile refs + regenerate PUML | keep diagram; report unresolved | Only on explicit delete intent, never silent |
| Standalone (explicit diagram-entities) | re-render from stored entities | keep diagram | No |

Unknown/unsupported combinations **fail without modifying files**.

**Acceptance (T1).**
- [ ] Dispatch matrix documented (plan + service docstring); each row names its data
      source, empty-result behavior, and deletion rule.
- [ ] Reviewed/agreed before T2 implementation.

### T2 — Projection-aware refresh in the shared service (the critical fix)

**Problem.** `sync_diagram_to_model()` is projector-blind and deletes on empty inference;
this is the principal defect, reached via MCP, REST, and bulk.

**Solution strategy.** Make the **shared service** projection-aware (or introduce a
`refresh_diagram` dispatcher the three interfaces call), implementing the T1 matrix.
For a scope-bound diagram, refresh re-runs the projector (`project_c4` / `resolve_c4_state`
path) and **never** calls `delete_diagram` on empty entities. Keep ArchiMate/standalone
paths byte-identical to today.

**Files / anchors (verified).**
- `src/infrastructure/write/artifact_write/diagram_sync.py` (~L305–330: the
  `if not entity_records: delete_diagram(...)` branch — must not fire for scope-bound).
- `src/infrastructure/write/artifact_write_ops.py` (`sync_diagram_to_model`).
- MCP adapter: `src/infrastructure/mcp/artifact_mcp/edit_tools.py:192`.
- REST adapter: `src/infrastructure/gui/routers/_diagram_write.py:365` (`/api/diagram/sync`).
- Bulk: `src/infrastructure/mcp/artifact_mcp/bulk/diagram_refs.py` (auto-sync over many).
- Projector: `src/diagram_types/c4/_projection.py`, `_resolve.py`, `renderer.py`.

**Steps.**
1. Detect scope-bound/projector-owned diagrams (presence of a `scoped-by` binding /
   diagram-type projector capability).
2. Route those through projector refresh; guard the `not entity_records` deletion so it
   cannot fire for them (empty projection → valid empty view or explicit error).
3. Keep ArchiMate-reconcile and standalone paths unchanged.
4. Ensure MCP, REST, bulk all flow through the one service (no per-adapter logic).

**Acceptance (T2) — protect data, not symptoms.**
- [ ] scope-bound refresh: diagram is **not deleted**.
- [ ] `scoped-by` binding preserved.
- [ ] include/exclude selection (`_included/_excluded_entity_ids`) preserved.
- [ ] diagram type, name, status, version, keywords, and derivations preserved.
- [ ] projected entity/connection references **refreshed** (reflect current model).
- [ ] **dry-run is byte-for-byte non-mutating** (assert file bytes unchanged).
- [ ] empty valid projection → valid empty view **or** explicit error, **never deletion**.
- [ ] standalone + ArchiMate reconcile behavior **unchanged** (regression tests).
- [ ] MCP, REST `/api/diagram/sync`, and bulk auto-sync exercised through one service
      (service-contract test + thin adapter tests).
- [ ] One-time engagement-wide refresh+verify shows 0 errors (migration check, §3).
- [ ] Gates green.

### T3 — Pair-legality in `artifact_authoring_guidance` (extend, don’t add a tool)

**Problem.** The agent surface can’t answer "what may connect X→Y?"; REST already can.

**Solution strategy.** Add a constrained `target` parameter to
`artifact_authoring_guidance`, reusing the **same domain/service logic** REST uses (parity
with `/api/ontology`). Derive direction from the **raw permitted-relationship set /
`classify_connections`**, not from two calls to `permissible_connection_types` (which
folds in reverse symmetric rules and cannot cleanly explain directionality).

**Files / anchors (verified).**
- `src/domain/connection_ontology.py` (`permissible_connection_types`, `is_symmetric`,
  `classify_connections`).
- REST reference impl: `src/infrastructure/gui/routers/connections.py:119`.
- Guidance tool: `src/infrastructure/mcp/artifact_mcp/` (the `artifact_authoring_guidance`
  registration).

**Contract.**
- `target` is valid **only** when `filter` contains exactly **one concrete entity type**.
- Domain filters, multiple source types, or missing `filter` with `target` set →
  **validation error** (no guess).
- Preserve normal entity guidance; **add a `pair_guidance` block** with `source`,
  `target`, `outgoing`, `incoming`, and `symmetric` returned **separately**.
- Unknown types → return known-type suggestions.

**Acceptance (T3).**
- [ ] One call returns directional pair legality for a single concrete (source, target).
- [ ] Invalid combinations return a clear validation error (no file/model change).
- [ ] Results **consistent with REST `/api/ontology`** (parity test).
- [ ] Tests: domain helper, guidance response object, serialized YAML, MCP schema, REST
      parity.
- [ ] Description grows ≤ 1 line. Surface change → restart note (§4).

### T4 — Editable diagram-edge labels (service → MCP + REST + GUI)

**Problem.** Authors cannot set a view-specific edge label; model-backed labels are
derived (U5). The GUI sidebar shows edge details on click but no label edit.

**Solution strategy (domain-centric).** Introduce a **per-diagram edge-label override**:
each *diagram* (view) owns its own presentation labels; the *model connection* keeps its
semantics (prose/`content_text`) untouched — this preserves the separation established in
the C4 verification fix. Because the override lives on the diagram, **the same model
connection can carry different labels in different diagrams** (and none/derived in
others). The renderer uses the diagram’s override if present, else the derived/default
label. Define a single service operation `set_diagram_edge_label(diagram, edge_key,
label|none)`; expose via MCP (extend `artifact_edit_diagram`) and REST; consume in the GUI
sidebar.

**Data model & migration.**
- Add an **optional** diagram-frontmatter map, e.g. `edge-labels: { "<edge-key>": "..." }`,
  keyed by a **render-stable key** — recommend the rendered edge’s `(source_local_id,
  target_local_id)` (works for rolled-up C4 edges where one edge abstracts several
  connections); document the choice.
- Update the **diagram frontmatter schema** to permit the optional field so existing
  diagrams (without it) remain valid — **no data migration needed** (absence = derived
  label). The verifier must flag an override whose edge no longer exists (dangling).

**Edge-key design (decided).** Use `"{src_alias}:{tgt_alias}"` where `src_alias` and
`tgt_alias` are the rendered PUML aliases (e.g. `APP_hkrdtm:APP_Z_fI-N`). These are
computed deterministically from entity IDs and stable within a diagram's projection.
For rolled-up C4 edges the (src,tgt) alias pair uniquely identifies the visible edge.
A dangling key (alias pair no longer rendered) is flagged by the verifier. The choice
is documented in a comment in `_resolve.py`.

**Files / anchors (verified by code inspection).**
- `src/application/modeling/artifact_write_formatting.py` (`format_diagram_puml`) — add
  optional `edge_labels: dict[str,str] | None` param; include in frontmatter before `last-updated`; add to `ordered_keys` between `bindings` and `last-updated`.
- `src/infrastructure/write/artifact_write/diagram_edit.py` (`edit_diagram`) — add
  `edge_labels` param; read existing `edge-labels` from frontmatter if caller omits; pass to `format_diagram_puml`.
- `src/diagram_types/c4/renderer.py:117` — apply `edge_labels.get(f"{conn.src_alias}:{conn.tgt_alias}", conn.label)` before escaping; `edge_labels` flows in via `render_body` new kwarg.
- `src/diagram_types/c4/_resolve.py` — no change needed: `_C4Connection.label` is what the renderer currently uses; the override is applied at render time.
- New thin service op: `set_diagram_edge_label(repo_root, verifier, clear_repo_caches, artifact_id, edge_key, label|None, dry_run)` — calls `edit_diagram` with updated edge_labels map; place in `src/infrastructure/write/artifact_write/diagram_edit.py` or a new `diagram_edge_label.py`.
- `src/infrastructure/mcp/artifact_mcp/edit_tools.py` (`artifact_edit_diagram`) — add `edge_labels: dict[str,str] | None = None`; pass to service op.
- `src/infrastructure/gui/routers/_diagram_write.py` — new `PUT /api/diagram/edge-label` body `{artifact_id, edge_key, label|None, dry_run}`; calls same service op.
- Verifier `src/application/verification/` — add rule: for each key in `edge-labels`, verify the `src:tgt` alias pair appears in the rendered connections; else E4xx dangling-label-override.
- GUI `tools/gui/src/ui/views/DiagramDetailView.vue` — `selectedConnection` panel at line 753; add `<input>` for label below the `content_text` display; on blur/enter PUT `/api/diagram/edge-label`; optimistic update; error toast. The edge-key is `{selectedConnection.source_alias}:{selectedConnection.target_alias}`.
- `tools/gui/src/domain/` — `DiagramConnection` type may need `current_label?: string` field to show the rendered label; check `DiagramContext` response shape.

**Steps.**
1. Service op + frontmatter field + schema update + verifier dangling-override check.
2. Renderer applies override → else derived label (all diagram types).
3. MCP + REST adapters call the one service op (parity test).
4. GUI: sidebar label display + inline edit (consistent with existing sidebar patterns;
   optimistic update + error toast; no layout regressions).
5. Tests: service-contract, MCP, REST, renderer-with-override, verifier dangling case,
   GUI component.

**Acceptance (T4).**
- [ ] Setting/clearing an edge label via MCP and via REST yields identical results
      (parity), persisted as a per-diagram override; model connection unchanged.
- [ ] **Per-diagram independence:** the same connection rendered in two diagrams carries
      independent labels (overriding in one does not affect the other) — test.
- [ ] Renderer shows the override; clearing it reverts to the derived label.
- [ ] Existing diagrams without the field stay valid (schema permits optional).
- [ ] Verifier flags a dangling override (edge removed) — test.
- [ ] GUI: clicking an edge shows the label in the sidebar; editing saves and re-renders;
      UX is consistent/simple (manual check + component test).
- [ ] Gates green.

### T5 — Finalize terse MCP tool descriptions (after T2–T4 settle)

**Problem.** Descriptions should be rewritten **once** behavior is final (avoid the
rev-1 rework where a T1 caution had to be undone by T2).

**Solution strategy.** Update `artifact_edit_diagram` and `artifact_authoring_guidance`
descriptions to reflect final semantics (model-backed refresh is safe; binding modes;
`target` pair-guidance; `edge_labels`). Existing binding-mode descriptions
(`edit_tools.py:333`) are already reasonable — refine, don’t rewrite. Add a
**description/schema snapshot test** so drift is caught automatically rather than by
manual reading.

**Acceptance (T5).**
- [ ] Descriptions reflect final T2–T4 behavior; net growth within the §4 budget.
- [ ] Snapshot test pins tool schema + description; passes.
- [ ] Surface change → restart note (§4).

### T6 — Restructure skill → `architecture-modelling` (canonical dir; after T2–T5)

**Problem.** Monolithic, mis-located, prose-only skill; examples depend on final T2–T5
contracts (so it must come after them).

**Solution strategy.** Edit the **canonical** `skills/architecture-modelling/` (rename
from `skills/archimate-modelling/`); **repoint the `.claude/skills` symlink** to it. No
backwards-compat redirect (per maintainer). Slim core + load-on-demand `references/`.
**Derive the task-sequence from the modeled process `PRC@1776635640.U4aAdh`** (Scope →
Discover → Decide → Plan → Author → Verify → Refine) — do **not** invent a parallel
lifecycle. Lean on `artifact_authoring_guidance` for per-type data (don’t duplicate it).

**Steps.**
1. `git mv skills/archimate-modelling skills/architecture-modelling`; update the symlink.
2. Slim `SKILL.md` core (principles + tool map + "load `references/<x>.md` when…");
   broaden trigger to ArchiMate/C4/assurance/SysML.
3. `references/task-sequences.md` — the lifecycle **derived from `PRC@…U4aAdh`**, with
   explicit stop-gates (dry-run before writes; `artifact_verify` 0-errors before close;
   "model the target first, then project" for C4; pair-guidance before authoring edges).
4. `references/tool-examples.md` — ≥3 worked flows incl. **safe model-backed refresh**
   and **setting an edge label** (using the final T2/T4 contracts).
5. Update every reference to the old skill name across the repo (grep).

**Acceptance (T6).**
- [ ] Canonical dir renamed; `.claude/skills` symlink valid; no dangling old-name refs.
- [ ] Core materially smaller (see §8 budget); references load on demand; no per-type
      tables duplicated from guidance.
- [ ] `task-sequences.md` traceably derived from `PRC@…U4aAdh` (cite the entity).
- [ ] Trigger matrix (§8) passes.

### T7 — Update & verify the recursive self-model (last)

**Problem.** The project is self-describing (`README.md:15`); the skill rename + new
capabilities must be reflected or the model drifts.

**Solution strategy.** Via MCP (`arch-repo-write`), update the self-model:
- Update `DOB@1780656431.T8nsTi` (Architecture Modelling Guidance) to name
  `architecture-modelling`.
- **Trace** the restructured skill to the modeled workflow `PRC@1776635640.U4aAdh`.
- Add/refine requirements/outcomes **only where genuinely missing** (e.g. editable
  view labels, pair-legality guidance) — apply the Pareto rule, don’t over-model.
- Run engagement-wide `artifact_verify` → 0 errors.

**Acceptance (T7).**
- [ ] `DOB@…T8nsTi` updated; skill↔`PRC@…U4aAdh` trace present.
- [ ] Any new model content is minimal and justified.
- [ ] `artifact_verify(repo_scope="engagement", return_mode="full")` → 0 errors/0 warnings.

---

## 6. Sequencing

**T1 (semantics) → T2 (service fix) → T3 (guidance) → T4 (editable labels) →
T5 (descriptions) → T6 (skill) → T7 (self-model).** T2 is the only blocker for safety;
T3/T4 are service-boundary features; T5 finalizes descriptions once behavior is settled;
T6 depends on the final T2–T5 contracts (its examples reference them); T7 closes the loop.

## 7. Open questions

- T4 edge-key: `(source_local_id, target_local_id)` (recommended, render-stable) vs
  connection-artifact-id (ambiguous for rolled-up edges). Default: the local-id pair.
- T3: exact shape of the `pair_guidance` block vs REST’s response — keep them parity-
  identical or MCP-YAML-shaped? Default: same fields, YAML-serialized per MCP convention.

## 8. Global acceptance criteria (measurable)

- [ ] G1 — All per-task acceptance (§5) satisfied.
- [ ] G2 — `uv run pytest --tb=short -q` → 0 failures.
- [ ] G3 — `uv run ruff check src tests gen_id.py` → 0 errors; `uv run zuban check` → pass.
- [ ] G4 — Behavior changes (T2/T3/T4) verified through **both** MCP and REST via shared
      service-contract tests (no per-interface logic divergence).
- [ ] G5 — **Destructive-refresh invariant**: a scope-bound diagram fixture, refreshed
      repeatedly (≥3×) via MCP/REST/bulk, is **byte-stable and never deleted** (idempotent).
- [ ] G6 — Pair-legality answerable in **one** guidance call (no rejected write) — asserted.
- [ ] G7 — Skill core within an agreed **line/token budget**; **trigger matrix** of
      representative prompts selects the skill as expected; no MCP description exceeds the
      agreed char/token budget.
- [ ] G8 — Engagement-wide `artifact_verify` → 0 errors after T2 and after T7.
- [ ] G9 — No plan/phase/`T*`/`U*`/section labels introduced in code/tests/skill.
- [ ] G10 — Handoff note lists which changes need backend restart vs Claude-session restart.

## 9. Units of work — progress tracker

Legend: `[ ]` todo · `[~]` in progress · `[x]` done (add commit ref).

**T1 — refresh semantics**
- [x] T1.1 Write dispatch matrix (plan + service docstring) — bfb3bb7+local
- [x] T1.2 Review/agree before T2 — dispatch matrix accepted; recorded in diagram_sync.py module docstring

**T2 — projection-aware shared refresh**
- [x] T2.1 Make sync/refresh service projection-aware (dispatch by ownership) — `refresh_diagram` + `_is_scope_bound` in diagram_sync.py; helpers split to _sync_helpers.py
- [x] T2.2 Guard `not entity_records` deletion for scope-bound diagrams — `sync_diagram_to_model` raises ValueError; scope-bound path never reaches delete branch
- [x] T2.3 Route MCP, REST `/api/diagram/sync`, bulk through the one service — all three adapters call `refresh_diagram`
- [x] T2.4 Service-contract tests (preserve binding/selection/metadata/refs; dry-run non-mutating; empty→valid/err not deletion) — `tests/tools/test_scope_bound_refresh.py`
- [x] T2.5 Regression tests: standalone + ArchiMate reconcile unchanged — `TestArchiMateReconcileUnchanged` + all 10 existing `test_diagram_sync.py` tests pass
- [x] T2.6 One-time engagement-wide refresh+verify (migration check) — 4 scope-bound diagrams in ENG-ARCH-REPO: all SAFE on dry-run; 1524 tests green
- [x] T2.7 T2 acceptance + gates — 1524 passed, ruff clean, zuban clean

**T3 — pair-legality in authoring guidance**
- [x] T3.1 Add constrained `target` param (single concrete type; else validation error) — `get_type_guidance(target=)` + MCP `artifact_authoring_guidance(target=)`
- [x] T3.2 Derive direction from raw permitted set / `classify_connections`; `pair_guidance` block — `pair_connection_guidance` in type_guidance.py
- [x] T3.3 Tests: domain helper, guidance object, MCP, REST parity — `tests/tools/test_pair_legality_guidance.py` (20 tests)
- [x] T3.4 T3 acceptance + gates — 1544 passed, ruff clean, zuban clean

**T4 — editable diagram-edge labels**
- [x] T4.1 `format_diagram_puml` gains `edge_labels`; `edit_diagram` gains `edge_labels`; frontmatter round-trip (write + read-back)
- [x] T4.2 `set_diagram_edge_label` service op (thin wrapper on `edit_diagram`)
- [x] T4.3 Verifier: dangling-override check (key not in rendered connection pairs → error E410)
- [x] T4.4 Renderer (`renderer.py:117`) applies override → else derived label; `**extra` pattern avoids breaking non-C4 renderers
- [x] T4.5 MCP (`artifact_edit_diagram`) `edge_labels` param → service op
- [x] T4.6 REST `PUT /api/diagram/edge-label` → same service op (via `_diagram_edge_label.py`)
- [x] T4.7 GUI sidebar (`DiagramDetailView.vue`) selectedConnection panel: inline label input; PUT on enter/blur; optimistic reload; error toast
- [x] T4.8 Tests: service-contract, MCP, renderer-with-override, verifier E410, per-diagram independence — `tests/tools/test_diagram_edge_labels.py` (12 tests)
- [x] T4.9 T4 acceptance + gates — 1556 passed, ruff clean, zuban clean

**T5 — finalize MCP descriptions**
- [x] T5.1 Rewrite `edit_diagram` + `authoring_guidance` descriptions (final semantics) — edit_tools.py description updated; authoring_guidance already correct after T3
- [x] T5.2 Description/schema snapshot test — `tests/tools/test_mcp_tool_descriptions.py` (12 tests)
- [x] T5.3 T5 acceptance + restart note — 1568 passed, ruff clean, zuban clean; MCP surface change requires backend restart + Claude session restart (see §4)

**T6 — architecture-modelling skill**
- [x] T6.1 `git mv` to `skills/architecture-modelling`; repoint `.claude/skills` symlink
- [x] T6.2 Slim core SKILL.md + broadened trigger (209 lines vs 426; per-type tables removed)
- [x] T6.3 `references/task-sequences.md` derived from `PRC@…U4aAdh` (stop-gates)
- [x] T6.4 `references/tool-examples.md` (4 flows: safe refresh, set-edge-label, pair-legality, entity batch)
- [x] T6.5 Update all old-name references repo-wide (PLAN-assurance-*.md, DOB@T8nsTi via MCP)
- [x] T6.6 T6 acceptance + trigger matrix — 1568 passed, ruff clean, zuban clean; skill live in session

**T7 — self-model update**
- [x] T7.1 Update `DOB@1780656431.T8nsTi` to name the new skill (summary updated via MCP)
- [x] T7.2 Trace skill ↔ `PRC@1776635640.U4aAdh` (DOB→PRC archimate-association added; Pareto applied — no new REQ/OUT warranted)
- [x] T7.3 Engagement-wide `artifact_verify` → 0 errors (593 files, 0 errors, 0 warnings)

**Global**
- [x] G1–G10 (§8) all satisfied
- [x] Final handoff: restart matrix delivered; memory updated if conventions changed
