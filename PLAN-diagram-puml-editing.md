# Implementation Plan — Editable Diagram PUML (body-authoring)

**Mode:** [PLAN] · **Status:** Implemented · **Owner:** TBD · **Date:** 2026-06-01

> Let users **edit a diagram's PlantUML body directly**, **preview it with validation** (no persist),
> and **store it** (only after validation, which then triggers a re-render). The body becomes the
> source of truth for such a diagram; **frontmatter is recomputed**, never hand-edited.
>
> **Orthogonal** to `PLAN-projects-feature.md` (artifact grouping). The only contact point: rendered
> assets and `!include` resolution must go through the grouping plan's path helpers rather than
> hard-coded `diagram-catalog/...` roots. Binding recomputation should align with the in-flight
> `PLAN-meta-ontology-v2.md` (diagram↔model bindings).

---

## 1. Business Context

Today a diagram's `.puml` body is **generated** server-side from an entity selection (the GUI's
visual picker → `generate_archimate_puml_body()`), and `entity-ids-used` / `connection-ids-used` /
`bindings` are written into the frontmatter. Power users and agents frequently need finer control of
layout and notation (grouping rectangles, hidden layout edges, ortho routing, skinparams) that the
generator does not express. They should be able to **edit the PUML directly**, see it render live with
validation, and save it — while the model-side bookkeeping (which entities/connections the diagram
references) stays correct and verifiable.

This serves **GUI Exploration and Authoring for Humans** (`REQ@…NfAmrl`), **PlantUML Diagrams**
(`REQ@…NkMp_0`), **Verify diagram syntax automatically** (`REQ@…t_NpFC`), and **Authoring tools use
verifier** (`REQ@…mvrJxo`).

**Most of the backend already exists** — this feature is mostly *exposure + UI + safety*:

| Capability | State | Evidence |
|---|---|---|
| `puml` input on edit → frontmatter inferred from body | ✅ exists | `diagram_references.py:108-145` (`_infer_reference_ids_from_puml`), used at `diagram_edit.py:143` |
| PUML syntax validation (dry-runnable) | ✅ exists | `artifact_verifier_syntax.py:54-122` (renders SVG via `-tsvg -verbose`, parses stderr — *not* `-checkonly`) |
| Model-side diagram verification (E-codes) | ✅ exists | `artifact_verifier.py:299-335` |
| Dry-run validate (no write) | ✅ exists | `diagram_edit.py:166-181` |
| Render-on-save (+ rollback on verify fail) | ✅ exists | `diagram_edit.py:183-203` |
| Ephemeral preview render → base64/SVG | ✅ exists | `diagram_builder.py:252-330`; `/api/diagram/preview` |
| Raw-PUML preview endpoint (body in) | ⚠️ partial | `/api/diagram/preview` takes `entity_ids`/`diagram_entities`, **not** raw body |
| **Render-input safety** (deny-list + profile + limits) | ❌ missing | renderer invokes `plantuml.jar` on the body; no directive deny-list, security profile, or size/time limits |
| **PUML editor + live preview UI** | ❌ missing | `EditDiagramView.vue` is entity-picker-driven; `showSource` is a read-only **source viewer**, not an editor |

---

## 2. Architecture Summary

### 2.1 The inversion: body-authoritative diagrams
For a diagram edited via its body, control inverts: the **body is source of truth**, and the system
(a) **recomputes derived frontmatter** — **`entity-ids-used`/`connection-ids-used` are *replaced***
(not merged — §2.2); **bindings are *not* synthesized in v1** (kept only if still valid, else dropped;
synthesis deferred to `PLAN-meta-ontology-v2.md`); (b) **strips system-generated `!include` lines and
generated ArchiMate blocks** on read/save and **re-injects** them on render — without touching user
style directives (§4.2); and (c) **does not regenerate or relayout** the body — **body-edit mode MUST
bypass `optimize_puml_layout()` / `_prepare_diagram_puml_body()`**, which the current edit path calls
(`diagram_edit.py:137`) and would otherwise rewrite hand-authored layout. Identity (`artifact-id`,
`diagram-type`) and `version` are preserved; `last-updated` is bumped.

Body-authoring and entity-picker generation are **mutually exclusive** per diagram — **but this is not
enforced today**: `edit_diagram` accepts both `puml` and `diagram_entities` without rejecting. **Body
mode MUST reject a request carrying both** (a new backend validation error). Switching a body-authored
diagram back to the picker would clobber hand edits, so that transition is a warned, confirm-to-reset
action (§6).

### 2.2 Reference recomputation (how body→frontmatter works)
The body references entities by **alias** (e.g. `as STK_aB3dE1`); the alias maps to an artifact id via
the entity's normalized `display_alias` (and a `prefix_timepart` fallback) in
`diagram_references.py:69-78`. Relations are extracted by regex (`Rel_TYPE(a,b)` and arrow forms).
`_infer_reference_ids_from_puml()` already turns a body into `(entity_ids, connection_ids)`.
**Non-entity nodes are legitimate** (grouping rectangles like `<<MotivationGrouping>>`, hidden layout
edges) and simply don't contribute refs; an alias used in a *relation* that resolves to no
entity/connection becomes a **validation warning** (the author referenced something unbound).

**Replace, not merge.** The current edit path *merges* inferred refs with the existing ones
(`_merge_reference_ids`, `diagram_edit.py:143`), which can preserve **stale** `entity-ids-used`/
`connection-ids-used`. For body-authored saves the derived refs **replace** the stored ones — the body
is authoritative. (Pinned/manual refs, if ever needed, are modelled explicitly, never hidden in merge.)

### 2.3 Scope — v1: ArchiMate-style / manual PUML only
v1 targets **ArchiMate-style and manual PUML diagrams** rendered by `GenericPumlRenderer`.
**Diagram-owned types (C4, activity, sequence) are out of scope for v1** — they have **custom
renderers** (not `GenericPumlRenderer`) and structured `diagram_entities`, and "edit usage but not
declarations" is not enforceable in free text. The **matrix** type (non-PUML) is also excluded.
Body-editing of diagram-owned types is deferred until a clear **mode decision**: a diagram is *either*
structured (`diagram_entities`-driven) *or* free-text body — **not both**.

> ⚠️ **Revises the earlier OQ-3 resolution** (which had included diagram-owned *usage*-editing). The
> review showed that premise rested on a wrong renderer assumption; **flagged for your confirmation.**

### 2.4 Surface delta (minimal)
- **Shared `prepare_body_edit` service.** One application service performs validate + infer-refs
  (replace) + prepare (strip generated includes/blocks, keep user body); **dry-run, preview, and save
  all call it** so their semantics cannot drift. Preview adds an ephemeral render; save adds the write
  + asset render.
- **MCP — no new tools.** Body edit reuses `artifact_edit_diagram(puml=…)`; validation-only reuses
  `artifact_edit_diagram(puml=…, dry_run=True)` (verification, no write/image).
- **REST — one preview affordance.** A raw-PUML preview path (extend `/api/diagram/preview` with a
  `puml` mode, or a sibling) calls the shared service + ephemeral render and returns the
  inferred-frontmatter summary; never persists.
- **GUI** — a PUML body editor with live preview + validation + save.

### 2.5 Layer mapping (hexagonal)
| Layer | Change |
|---|---|
| **Application** (`src/application/`) | shared **`prepare_body_edit`** service (validate + infer-refs *(replace)* + strip/prepare body), used by dry-run/preview/save; validation orchestration (syntax + model). |
| **Infrastructure** (`src/infrastructure/`) | **lightweight PUML input safety** (directive deny-list + security profile + time/size limits); raw-PUML preview endpoint; render-on-save (exists); SSE on save. |
| **Frontend** (`tools/gui/`) | PUML editor component, debounced live preview, inline validation, detected-refs panel, save flow. |

---

## 3. User Stories

- **US-1 Edit the body.** As an author, I can open a diagram's PUML body in an editor and edit it
  directly; I cannot edit frontmatter (it's recomputed).
- **US-2 Live preview + validation.** As an author, I see the diagram re-render as I edit, with syntax
  and model-reference issues surfaced inline, **without saving**.
- **US-3 See what was detected.** As an author, I see which entities/connections my body resolved to,
  and warnings for aliases/relations that didn't bind to any model artifact.
- **US-4 Store safely.** As an author, save is **blocked while invalid**; on save the body is
  validated, stored transactionally, frontmatter recomputed, `last-updated` bumped, and a **re-render**
  is triggered.
- **US-5 Agent parity.** As an AI agent, I can submit a PUML body via `artifact_edit_diagram` and
  validate it via `dry_run` — same recompute/validation semantics as the GUI.
- **US-6 Safety (right-sized).** As an operator of this internal tool, an **accidental or careless**
  body (`!include /…`, `%getenv`, a runaway diagram) is rejected or bounded — it can't read arbitrary
  files, fetch remote includes, or hang the renderer — via a directive deny-list, a restricted
  PlantUML profile, and time/size limits.
- **US-7 Mode interaction.** PUML editing is a **secondary** mode. As an author, activating it on a
  diagram with **no unsaved picker changes** simply deactivates the entity-picker; if **unsaved
  changes** exist in either mode, switching to the other **warns me they will be reset** first (§6).
- **US-8 Read-only respect.** When the backend runs `--read-only`, PUML editing and its save are
  **unavailable** in both GUI and backend — like every other write path.

---

## 4. 🔴 Cross-Cutting Concerns

### 4.1 Security — render-input safety (right-sized for a local/internal tool)
This is **not** a public service, so SSRF / hostile-user hardening is **lower priority**. The realistic
risks are **accidental**: a stray `!include /…`, `%getenv`, remote includes, a runaway diagram, or
broken repo output. v1 uses a **lightweight input policy** (not a full OS sandbox):
- **Directive deny-list** (rejected as a validation **error**, applied to preview *and* save): any
  `!include` outside the allow-listed `_archimate-*.puml` + the diagram's own dir; **all**
  `!includeurl`/remote includes; `%getenv`/file-embed. Cheap, and guards both accidents *and* an agent
  emitting something unsafe.
- **Restricted PlantUML security profile** for render + validate.
- **Time + output-size limits** (wall-clock timeout; `diagrams.plantuml_limit_size`).
- **OS-level no-network sandbox is optional/demoted** — adopt only if a simple existing mechanism
  (container/firejail) is already available; **not a v1 blocker**.

### 4.2 Data Consistency & Integrity 🔴
- **Validation gates the write.** Save runs syntax + model verification; on failure → **no write**,
  issues returned (rollback already implemented at `diagram_edit.py:188`).
- **Derived refs are *replaced*, not merged** (§2.2): deleting a reference in the body removes it from
  `entity-ids-used`/`connection-ids-used`. **Bindings are not synthesized** in v1 (kept only if still
  valid, else dropped — deferred to meta-ontology v2).
- **Frontmatter stays consistent** (recomputed in the same operation); identity and `version`
  preserved, `last-updated` bumped.
- **Write is serialized** through the existing write queue; **render is post-commit best-effort** — a
  validated body has already rendered during validation, so a render failure yields a **warning +
  "stale asset" flag + retry**, not a lost edit.
- **Include/style contract (idempotent).** On read/save, **strip only system-generated `!include`
  lines and generated ArchiMate blocks**; **store the user body verbatim, keeping user `skinparam`/
  style directives**; re-inject generated content on render. This fixes the duplicated generated
  preamble in current stored bodies and never silently removes user styling.
- **Read-only mode:** the editor and its save path are **unavailable under `--read-only`** (GUI hides
  the PUML edit mode; backend rejects the write) — like every other write operation.

### 4.3 Migrations
None (no schema/data migration). **Path coupling:** rendered-asset paths and `!include` bases must use
the grouping plan's path helpers (so this feature composes with `projects` without rework).

### 4.4 Observability / Events 🟡
- Emit an **SSE event** on diagram save so open detail/preview views refresh.
- **Log** validation failures (syntax vs model), include-policy rejections, and render failures (with
  the diagram id and timing).

---

## 5. Key Decisions

- **Body is source-of-truth** for body-edited diagrams; frontmatter is recomputed, never hand-edited.
  **Body preservation is strict:** body-edit **skips `optimize_puml_layout()`/relayout**; an optional
  explicit "normalize layout" action may come later.
- **Derived refs are *replaced*, not merged**; **bindings are not synthesized in v1** (deferred to
  `PLAN-meta-ontology-v2.md`; kept only if still valid).
- **Scope v1 = ArchiMate-style / manual PUML only.** Diagram-owned C4/activity/sequence are **deferred**
  (custom renderers; a diagram is structured *xor* free-text body). *(Revises OQ-3 — see §2.3.)*
- **Shared `prepare_body_edit` service** backs dry-run, preview, and save (no logic drift).
- **Reuse existing inference** (`_infer_reference_ids_from_puml`) and validation; this is exposure +
  safety + UI, not a new engine.
- **No new MCP tools** — `artifact_edit_diagram(puml=…[, dry_run=True])` covers edit + validate; GUI
  gets one raw-PUML preview endpoint.
- **Mutual exclusivity is enforced:** body mode **rejects a request carrying both `puml` and
  `diagram_entities`** (not enforced today).
- **Lightweight input safety** (directive deny-list + restricted profile + time/size limits) is the
  Phase-0 prerequisite; **OS sandbox optional/demoted** for this internal tool.
- **Include/style contract:** strip only **system-generated** includes + generated ArchiMate blocks;
  keep user `skinparam`/style verbatim; re-inject on render (idempotent).
- **Validation gates save; render is post-commit best-effort.**
- **Secondary mode** (mutually exclusive with the picker; switch rules in §6); **unavailable under
  `--read-only`**. **Version preserved; only `last-updated` bumped.** **Editor = CodeMirror.**

---

## 6. Mode Interaction & Availability

PUML editing is a **secondary** editing mode, mutually exclusive with the entity-picker for a given
diagram:
- **Activating PUML mode with a clean picker** (no unsaved entity-picker changes) **deactivates the
  entity-picker**.
- **Switching modes with unsaved changes** — picker→PUML *or* PUML→picker — shows a **notification that
  the unsaved changes will be reset**, and proceeds only on confirmation.
- Once PUML mode is used, the **body is source-of-truth** (§2.1); the two modes never co-edit a diagram.

**Availability:** like every write path, PUML editing and its save are **unavailable when the backend
runs `--read-only`** — the GUI does not offer the editor and the backend rejects the write. Viewing an
already-rendered diagram is unaffected.

---

## 7. Phases, Tasks & Acceptance Criteria

> Small cohesive PRs; per-*file* < 350 lines. Phase 0 is a hard prerequisite for 1–3. File references
> are recon starting points (line numbers approximate), not an exhaustive change list.

### Phase 0 — Lightweight Input Safety (prerequisite)
- **T0.1 — Directive deny-list.** New validator (`src/application/verification/`, invoked from the
  diagram verifier `src/application/verification/artifact_verifier.py:299-335`) that permits only
  `_archimate-*.puml` + the diagram's resolved dir and **rejects** any other `!include`, all
  `!includeurl`/remote includes, and `%getenv`/file-embed → new diagram **E-code**. Reconcile with
  include injection at `generic_puml_renderer.py:225-231` and `diagram_references.py:148-156`.
- **T0.2 — Security profile + limits.** Apply a restricted PlantUML security profile and wall-clock
  **timeout** + output-size cap (`diagrams.plantuml_limit_size`, `config/settings.yaml`) to the java
  entry points: render `diagram_render.py:39-124`, preview render `diagram_builder.py:252-330`,
  validation `artifact_verifier_syntax.py:54-122`. Keep the existing `ARCH_SKIP_PUML_SYNTAX` escape.
- **T0.3 — (optional) OS sandbox.** *Only if* a simple existing mechanism (container/firejail) is on
  hand, add no-network/ephemeral-CWD isolation. **Not a v1 blocker.**

**Acceptance:** bodies with `!include /etc/passwd`, a remote include, or `%getenv` are **rejected with
the new E-code** in *both* preview and save; benign diagrams still render; a pathological body **times
out cleanly** within the configured limit. One test per vector.

### Phase 1 — Body-Authoritative Edit Contract (backend) 🔴
- **T1.1 — `prepare_body_edit` service.** A shared application service (`src/application/…`) that, for a
  given body: validates (deny-list + syntax + model), **infers refs and *replaces*** `entity-ids-used`/
  `connection-ids-used` (drop the merge — `diagram_references.py:108-145`, `diagram_edit.py:143`),
  **strips system-generated includes/blocks** (keeps user body verbatim), and returns the prepared body
  + detected-refs + issues. Consumed by dry-run, preview, and save.
- **T1.2 — Body-edit save path.** In `diagram_edit.py:36-212` (puml branch ~`:137-147`): call the
  shared service; **bypass `optimize_puml_layout()`/`_prepare_diagram_puml_body()`** for body edits (no
  relayout); preserve identity + `version`; bump `last-updated`; serialise via `format_diagram_puml`
  (`artifact_write_formatting.py:158-219`); keep transactional write+rollback (`:183-196`) and
  re-render (`:198-203`). **Reject a request carrying both `puml` and `diagram_entities`** (new error).
  **Bindings:** keep existing only if still valid, else drop — **no synthesis** (defer to meta-ontology).
- **T1.3 — Unresolved-reference & include/style rules.** A relation referencing an unbound alias → new
  **W-code**; decorative non-entity nodes allowed. **Strip only system-generated includes + generated
  ArchiMate blocks; never user `skinparam`/style** (idempotent — fixes the duplicated preamble).
- **T1.4 — MCP entry (no new tool).** Confirm `edit_tools.py:157-228` routes the `puml` arg to the
  body-edit save path under the write queue (`edit_tools.py:299`).

**Acceptance:** for an **unchanged** real body, recomputed refs **equal the picker's output**
(diff-tested) and re-saving is a **no-op** (no relayout, no preamble duplication); **removing** a
reference in the body removes it from `entity-ids-used` (replace, not merge); submitting both `puml`
and `diagram_entities` is **rejected**; invalid body → **no write** + issues; valid body → written,
re-rendered, full `verify` clean; an unbound relation raises the W-code.

### Phase 2 — Preview & Validate (no persist)
- **T2.1 — Raw-PUML preview path.** Extend `/api/diagram/preview`
  (`src/infrastructure/gui/routers/_diagram_write.py:69-95`) with a `puml` mode (or a sibling
  endpoint) that calls the **shared `prepare_body_edit` service** (T1.1) and adds an ephemeral render
  (`diagram_builder.py:252-330`); returns the inferred-frontmatter summary; never persists. (Save and
  dry-run call the same service → no drift.)
- **T2.2 — GUI client method.** Add `previewPuml(...)` to `tools/gui/src/adapters/http/HttpModelRepository.ts`
  and the `ModelRepository` port (alongside `previewDiagram`/`editDiagram`).
- **T2.3 — MCP parity (no new tool).** `artifact_edit_diagram(puml=…, dry_run=True)` returns
  verification only (no image, no write) via `diagram_edit.py:166-181`, routed through the shared
  service; document it.

**Acceptance:** preview returns `{image, issues, detected_refs, warnings}` and **writes nothing**;
because preview and save share one service, `detected_refs` **necessarily match** what a subsequent
save computes for the same body (cross-checked test); invalid bodies return issues plus a best-effort
image or a clear render error.

### Phase 3 — GUI PUML Editor
- **T3.1 — Editor component.** PUML editor (**CodeMirror**, with PUML syntax highlight) under
  `tools/gui/src/ui/`. Today `showSource` (`DiagramDetailView.vue` ~line 61) is a **read-only source
  viewer**; add an **edit mode** on top of it (or in `EditDiagramView.vue`) for ArchiMate/manual PUML
  diagrams only; frontmatter shown **read-only**.
- **T3.2 — Live preview + validation.** Debounced calls to `previewPuml` (T2.2); render image + inline
  syntax/model issues; **detected-references panel** (recomputed refs + unresolved-alias warnings).
- **T3.3 — Save flow.** Disabled while invalid; validate→store (`editDiagram`)→re-render; success
  toast; asset refresh via SSE; **mode-switch guard** per §6 (deactivate a clean picker; warn-and-reset
  on unsaved changes); editor **hidden/disabled under `--read-only`**.

**Acceptance:** edit→preview→fix→save loop works end-to-end; **save is blocked while any issue is
present**; the rendered asset updates after save; mode-switch warning shown; **editor not offered under
`--read-only`**; `npm run lint` + `npm run typecheck` clean.

### Phase 4 — Events, Observability & Docs
- **T4.1 — Events & logs.** Emit an SSE event on diagram save (existing bus `GET /api/events`);
  structured logs for validation / include-policy / render failures (diagram id + timing).
- **T4.2 — Docs.** Update `README.md`: the body-authoring workflow, the input-safety policy, **v1 scope
  (ArchiMate/manual PUML only; diagram-owned deferred; matrix excluded)**, and the body↔frontmatter
  contract (replace-not-merge, no binding synthesis, strip-generated-includes-only).

**Acceptance:** open detail/preview views refresh on save; README matches behaviour.

---

## 8. Tooling / Surface Rationale

- **Zero new MCP tools.** Edit = `artifact_edit_diagram(puml=…)`; validate = same with `dry_run=True`.
  This keeps the agent surface unchanged (per the small-surface guidance) and reuses the existing
  body→frontmatter inference.
- **One REST preview affordance** (raw-PUML mode) serves the GUI's live image preview — the only thing
  agents don't already get from `dry_run`.

---

## 9. Traceability (stories ↔ phases)

| Story | Phases |
|---|---|
| US-1 edit body | P1.1, P3.1 |
| US-2 live preview + validation | P2, P3.2 |
| US-3 detected refs | P1.3, P2.1, P3.2 |
| US-4 store safely | P1.1, P3.3, §4.2 |
| US-5 agent parity | P2.3 |
| US-6 safety | P0, §4.1 |
| US-7 mode interaction | §6, P3.3 |
| US-8 read-only respect | §6, §4.2 |

---

## 10. Definition of Done

- All phase acceptance criteria met; full-repo `verify` (incl. diagram syntax + reference E-codes)
  clean after body edits; render assets regenerate on save.
- **Input safety:** directive deny-list + restricted profile + time/size limits proven against the
  file-read / remote-include / getenv / runaway vectors (§4.1); OS sandbox optional.
- Body→frontmatter recompute is correct (diff-tested), **replaces (not merges)** refs, **synthesizes no
  bindings**, and **does not relayout**; strips only system-generated includes/blocks (idempotent).
- **Both-fields rejection** enforced; **v1 scope = ArchiMate/manual PUML only** (diagram-owned deferred).
- **Shared `prepare_body_edit` service** backs dry-run/preview/save (no drift).
- No new MCP tools; one raw-PUML REST preview path; descriptions concise.
- `ruff`, `zuban check`, frontend `lint`/`typecheck` clean; per-*file* < 350 lines; delivered as small
  cohesive PRs.
- Rendered-path/include resolution routed through the grouping plan's path helpers (composes with
  `PLAN-projects-feature.md`).
- README + (if applicable) self-describing model updated.
- 🔴 concerns (§4) closed; key decisions (§5) and mode/availability rules (§6) honoured.
