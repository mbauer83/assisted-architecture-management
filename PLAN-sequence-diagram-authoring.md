# Implementation Plan — Sequence-Diagram Authoring UX Redesign

**Mode:** [PLAN] · **Status:** Implemented · **Owner:** TBD · **Date:** 2026-06-02

> Make authoring sequence diagrams **clear and direct**. Replace the generic, jargon-leaking form
> (`Fragments`, `Execution Specifications`, `sequence_index`, `from_index`, `to_index`, `lifeline_id`,
> raw `arrow_style`) and its **index/id-based linking** with five well-named central concepts —
> **Lifelines, Messages, Groupings, Activations (optional), Notes (optional)** — edited by
> **direct manipulation** (drag-order, endpoint pickers, span-selection), with **live preview**.
>
> Inspiration: PlantUML sequence syntax (https://plantuml.com/en/sequence-diagram) and the UML
> Sequence Diagram concepts (participants, messages, combined fragments, activation bars, notes).

---

## 1. Business Context

The current sequence-diagram authoring UI (see the user's screenshot) is the **generic schema-driven
fallback** (`DiagramOwnEntityTypeSection.vue`): it renders each ontology property as a raw labelled
text box. Users must understand internal semantics — that `sequence_index` is a 1-based total order,
that a Fragment's `from_index`/`to_index` point at message indices, that an Execution Specification's
`lifeline_id` must equal some lifeline's `id` typed verbatim. Connecting elements means **bookkeeping
integers and ids by hand**. This is a usability failure for a first-class, frequently-used diagram
type.

This serves **GUI Exploration and Authoring for Humans** (`REQ@…NfAmrl`), **ArchiMate and UML
ER/Sequence/Activity Diagrams** (`REQ@…Ii5Jj5`), **Configurable diagrams** (`REQ@…qpOBOQ`), and the
human-access motivation goals. The fix is permitted to **change the sequence ontology, renderer, and
authoring UI** (no backwards-compatibility requirement; **confirmed zero existing `diagram-type:
sequence` diagrams** across engagement + enterprise catalogs — so no migration burden).

**Current state (recon):**

| Area | File | Note |
|---|---|---|
| Diagram-type module | `src/diagram_types/sequence/{config.yaml,ontology.yaml,renderer.py,__init__.py}` | standalone `SequencePumlRenderer` |
| Own-entity types | `sequence/ontology.yaml` | `lifeline`, `message`, `fragment`, `execution-spec`, `note` (note hidden from UI) |
| Index/id linking | `ontology.yaml` | `message.sequence_index`, `fragment.{from_index,to_index,kind,condition}`, `execution-spec.{lifeline_id,from_index,to_index}` |
| Endpoint refs | diagram **connections** | `seq-from`/`seq-to` (message→lifeline), `seq-note-of` (note→lifeline) |
| Authoring UI | `tools/gui/src/ui/components/DiagramOwnEntityTypeSection.vue` | **generic** schema form — the source of the leaked jargon |
| Extension point (unused by sequence) | `src/diagram_types/README.md:309-376`; `tools/gui/src/ui/lib/diagramAuthoringExtensions.ts:9`; `tools/gui/src/ui/diagram-types/index.ts` | `type_ui_slots` + `registerExtension(key, Component, {managedOwnTypes})`; precedent: `diagram-types/activity/ActivityStepEditor.vue`. **Typed slot props = `uiConfig/diagramEntities/entities` only**; emits `diagramEntitiesChange` |
| Connection transport | `tools/gui/src/ui/views/{Create,Edit}DiagramView.vue:220/410`; `src/infrastructure/gui/routers/_diagram_write.py:19` | save sends **only `diagram_entities`**; diagram-local connections ride in **`diagram_entities._connections`** (a `diagram-connections` prop is passed at runtime — `DiagramTypeConfigPanel.vue:55` — but is **not** in the typed contract or the save payload) |

---

## 2. Conceptual Reframe (terminology + linking)

### 2.1 Five central concepts (rename + reframe)

| New (user-facing) | Was | Linking — old → **new** | Optional? |
|---|---|---|---|
| **Lifeline** (Participant) | Lifeline | — ; add participant **type** (actor/participant/boundary/control/entity/database/queue), optional model-entity mapping, **left-to-right order (drag)** | no |
| **Message** | Message | `sequence_index` (typed) → **list order (drag)**; endpoints via `seq-from`/`seq-to` set by **from/to pickers**; `arrow_style` → **arrow-type picker** | no |
| **Grouping** | Fragment | `kind` free-text → **enum picker** (alt/opt/loop/par/break/critical) **plus custom-label `group "…"`**; `from_index`/`to_index` → **span-selection of messages**, stored as **start/end message ids**; **alternatives (alt/else) and custom labels are the priority kinds**; supports **nesting + branching** | no (added on demand) |
| **Activation** | Execution Specification | `lifeline_id`+`from_index`/`to_index` → **per-message "activate/deactivate" toggles** (PlantUML `++`/`--`), stored against **message ids**; explicit spans only in an advanced mode | **yes** |
| **Note** | Note (hidden) | exposed in UI; attach to lifeline(s) (`note over A,B`), anchor **after a message id**, side left/right/over | **yes (always)** |

**The core change:** eliminate user-entered **indices and raw ids**. Order is **positional** (the
message list reads top-to-bottom like the diagram); references are **pickers**; spans are
**selections**; cross-references are stored as **stable element ids**, never integer indices — so
reordering messages can never corrupt a grouping/activation/note anchor (today it silently does).

### 2.2 Groupings (combined fragments)
**Grouping = combined fragment over messages** (the direct rename of Fragment). "Partitions" are *not*
a distinct PlantUML sequence concept, so the term is dropped — Grouping is the single concept.
**Highest-priority kinds: alternatives (`alt`/`else`) and custom-labelled `group "…"`**; the remaining
kinds (`opt`, `loop`, `par`, `break`, `critical`) follow the same span-selection model. Groupings
**nest and branch**. (PlantUML's participant `box` is a minor visual nicety, not a central concept;
out of scope.)

### 2.3 Persisted schema — the hard parts (Phase-0/1 deliverable)

```
diagram_entities:
  lifeline:  [{ id, label, participant_type, entity_id? }]      # entity_id = optional model binding
  message:   [{ id, label, arrow: sync|async|reply|self|create|destroy,
               activate_target?: bool, deactivate_target?: bool }]   # order = array index
  grouping:  [{ id, kind: alt|opt|loop|par|break|critical|group, label?,   # label for group/loop bound
               operands: [ { guard?, start_message_id, end_message_id } ] }]
  note:      [{ id, text, placement: left_of|right_of|over,
               lifeline_ids: [...],      # exactly 1 for left_of/right_of; 1..N for `over A,B`
               after_message_id? }]      # sequence anchor; omitted ⇒ appended at end
diagram_entities._connections:           # existing transport convention (see §3)
  seq-from: message → lifeline           # source lifeline (set by picker)
  seq-to:   message → lifeline           # target lifeline (set by picker)
```

**Rules (Phase-3 validation enforces):** message order = array index (no `sequence_index`);
groupings/notes/activations reference **message ids**, never indices. Grouping `operands` — opt / loop /
break / critical / group: **exactly 1**; **alt**: ≥1 (first = guard, the rest = `else`/else-if guards);
par: ≥1 parallel — must be **contiguous, non-overlapping, adjacent**, and their union is the grouping's
contiguous span; a **nested** grouping's span lies entirely within one operand. Note cardinality:
left_of/right_of = 1 lifeline, `over` = 1..N. Activation = the incoming-message
`activate_target`/`deactivate_target` flags (renderer maps to `activate`/`deactivate`/`++`/`--`).

---

## 3. Extension-Point Research & Design (per the explicit instruction)

A new extension point is permitted *only if researched/designed/specified carefully*; otherwise reuse
the existing one. **Recommendation: reuse `type_ui_slots` + `registerExtension`** (it already keeps
diagram-type UI logic out of generic components — exactly the modularity boundary we want), registering
**one `sequence` slot that manages all five own-types** (`managedOwnTypes: [lifeline, message,
grouping, activation, note]`, suppressing the generic sections).

The **actual** exported contract (`DiagramTypeUiSlotProps`, `diagramAuthoringExtensions.ts:9`) is just
**`uiConfig, diagramEntities, entities`** and emits **`diagramEntitiesChange`** — *not*
`diagramConnections`/`diagramConnectionsChange` (the parent passes a `diagram-connections` prop at
runtime, `DiagramTypeConfigPanel.vue:55`, but it is **not** in the typed interface, and save sends
**only `diagram_entities`** — `{Create,Edit}DiagramView.vue:220/410`). **Diagram-local connections
travel inside `diagram_entities._connections`** and are extracted backend-side (`_diagram_write.py:19`).
So under the current convention the editor reads/writes `seq-from`/`seq-to` **within `diagram_entities`**
and emits `diagramEntitiesChange` — no separate connection channel is required (this is the Phase-0
transport decision). The remaining **candidate gaps** for a great UX are feedback channels handled at
the parent (`EditDiagramView`) today:

- **Scoped validation issues** — so the editor shows inline per-element errors (e.g. "message has no
  target") instead of a generic save-time failure.
- **A preview/render signal** — so the editor can show a responsive inline preview as the model
  changes.

**Phase 0 decides** whether to (a) keep the contract as-is and let the parent own preview/validation,
or (b) make a **small, carefully-specified additive extension** to `DiagramTypeUiSlotProps`
(`validationIssues?: Issue[]` scoped to the diagram, and/or an `onRequestPreview` callback). The
**decision criterion is architectural clarity & soundness plus simplicity** — choose the option that
keeps the contract clean and the editor responsive without over-generalising. Any extension must be
**additive, typed, documented in `src/diagram_types/README.md`, and backward-compatible for the
existing activity slot**. No new extension point is introduced without this gate.

---

## 4. User Stories

- **US-1 Add lifelines easily.** As an author, I add participants, set each one's type, optionally map
  it to a model entity, and reorder them left-to-right by dragging — no ids to type.
- **US-2 Compose messages directly.** As an author, I add messages as an **ordered list** (top→bottom
  = diagram order), choosing **from**/**to** lifelines from pickers and reordering by dragging — never
  typing a `sequence_index`. **Common settings need ≈zero clicks** (sensible defaults, e.g. a sync
  arrow); **less-common settings** (rarer arrow types, create/destroy, self-message) live in an
  **expandable advanced section** per message.
- **US-3 Group without indices.** As an author, I **select a contiguous span of messages** and wrap
  them in a Grouping — most often an **alternative (`alt` with `else` branches)** or a
  **custom-labelled `group`** — set a guard/label, and **nest** groupings, without typing
  `from_index`/`to_index`.
- **US-4 Activations are optional & effortless.** As an author, I toggle activation on the **incoming
  message** (it activates the target lifeline; a later toggle deactivates it) instead of declaring
  execution-spec ranges; if I add none, the diagram simply has no activation bars.
- **US-5 Notes are optional & discoverable.** As an author, I attach a Note to one or more lifelines at
  a chosen point, pick its side, and type its text — Notes are exposed in the UI (today they're hidden).
- **US-6 See it live.** As an author, the rendered sequence diagram updates as I edit, with
  **inline validation** flagging problems (message missing an endpoint, empty grouping, dangling note).
- **US-7 Reorder safely.** As an author, reordering messages never breaks my groupings, activations, or
  notes (they track message **ids**, not indices).
- **US-8 Read-only respect.** When the backend runs `--read-only`, sequence authoring is unavailable
  (GUI + backend), like every write path.

---

## 5. 🔴 Cross-Cutting Concerns

### 5.1 Modularity (primary architectural constraint)
All sequence-specific logic stays in the **sequence diagram-type module** (`src/diagram_types/sequence/`
backend; `tools/gui/src/ui/diagram-types/sequence/` frontend). The generic
`DiagramOwnEntityTypeSection`, `DiagramTypeConfigPanel`, and renderer base are **not** to carry
sequence concepts. The bespoke editor is registered through the extension point and **suppresses** the
generic sections via `managedOwnTypes`. The rule is **no *sequence-specific* logic in generic
components** — **additive, sequence-agnostic changes to the generic slot contract are allowed** (e.g.
typing the runtime `diagramConnections` prop, adding an optional `validationIssues?`).

### 5.2 Data Consistency & Integrity 🔴
- **Id-based references replace indices.** Groupings/activations/notes reference **message/lifeline
  ids**; ordering is array position. This removes the index-drift corruption class (US-7) and is the
  central integrity win.
- **Validation gates save** (Phase 3): every message has both endpoints; grouping spans are contiguous
  & properly nested; activation/note anchors resolve; lifeline references exist. Writes stay on the
  existing transactional diagram path (`diagram_edit.py`) with rollback on verify failure.
- **Migration:** none — **confirmed zero existing sequence diagrams** (reviewer-verified). The
  ontology change (indices→ids, rename, activation reframe) therefore lands without a data migration; a
  fixture round-trip test guards the new schema.

### 5.3 Security
Structured authoring **generates** PlantUML (it does not accept arbitrary user PUML), so it does *not*
add the injection surface of `PLAN-diagram-puml-editing.md`. The shared **render** path must still run
under that plan's sandbox/security profile; this plan depends on (does not duplicate) that hardening.

### 5.4 Read-only, Live Preview & Events
- **Read-only:** the backend already blocks writes via the write-block/read-only path
  (`src/infrastructure/gui/routers/state.py:258`) and shows a banner (`tools/gui/src/ui/App.vue:290`),
  but editor components do **not** yet receive a read-only prop. Phase 4 adds explicit frontend
  plumbing: a `readOnly` prop threaded into the editor and every subcomponent, disabling
  add/remove/drag/save.
- **Live preview:** today's diagram views are **manual-preview / preview-clean-gated**. The editor needs
  **debounced auto-preview** (≈300–500 ms) with **in-flight request cancellation**, **dirty-state**
  tracking, and a defined **validation channel** — cheap structural checks computed client-side for
  instant inline feedback, authoritative E-codes fetched from the validate/preview path.
- Emit the existing SSE save event so open views refresh; reuse the diagram preview/render pipeline.

### 5.5 Composition with other plans
- **`PLAN-diagram-puml-editing.md`**: a sequence diagram may *also* be body-edited; the two are the
  mutually-exclusive modes defined there (§6 of that plan). Structured authoring is the "picker" mode.
- **`PLAN-meta-ontology-v2.md`**: lifeline→model-entity mapping is a binding; align the mapping UI and
  storage with the bindings redesign.
- Rendered-asset/include paths use `PLAN-projects-feature.md`'s path helpers.

---

## 6. Key Decisions

- **Reuse the `type_ui_slots` extension point**; build one bespoke `sequence` slot managing all five
  own-types. Any contract extension is **additive**, decided in Phase 0 by **architectural
  clarity/soundness + simplicity**, and documented.
- **Eliminate user-entered indices/ids**: positional order (drag), endpoint/arrow **pickers**, grouping
  **span-selection**, and **id-based** cross-references.
- **Five central concepts** with clear names; **Activations & Notes optional** (progressive disclosure,
  not always-present cards).
- **Groupings** are the single combined-fragment concept ("Partitions" dropped — not a PlantUML
  sequence concept). **Alternatives (`alt`/`else`) and custom-labelled `group` are the priority kinds**;
  **nesting + branching are core v1 features**.
- **Progressive-disclosure message UI:** most-used settings need ≈zero clicks (sensible defaults);
  less-common settings sit in an **expandable advanced section**. v1 arrow types: sync, async, reply,
  self, create, destroy.
- **Activations via an incoming-message toggle** (PlantUML `++`/`--`); no advanced explicit-span mode in
  v1.
- **Expose Notes** in the UI (already in ontology/renderer).
- **Exact persisted schema in §2.3** is a Phase-0 deliverable (grouping `operands`/branches/labels,
  note placement/cardinality/anchor, activation flags) — not deferred to UI work.
- **Connection transport = `diagram_entities._connections`** (recommended; matches the backend and the
  current save payload) — decided in Phase 0.
- **Sequence validation via a diagram-type hook**; rules live in `src/diagram_types/sequence/`, never
  in generic verifier code.
- **Live preview = debounced + cancellable + dirty-tracked**, with a defined inline-validation channel
  (not an afterthought).
- **Read-only is plumbed explicitly** (a `readOnly` prop), not assumed from the backend block alone.
- **Modularity**: no *sequence-specific* logic in generic components; **additive** sequence-agnostic
  contract changes are allowed.
- **`SequenceEditor` is decomposed** into subcomponents + a composable so each file stays < 350 lines.
- **No backcompat**; **confirmed zero existing sequence diagrams** → no migration.

---

## 7. Phases, Tasks & Acceptance Criteria

> Small cohesive PRs; per-*file* < 350 lines. File references are recon starting points.

### Phase 0 — Data-Contract & Extension Foundations 🔴 (gate, before any UI work)
- **T0.1 — Persisted schema.** Finalise the exact §2.3 shapes (lifelines, messages, grouping
  `operands`/branches/labels, activation flags, notes) and the validation rules; this is the source of
  truth for Phases 1–4.
- **T0.2 — Connection transport.** Decide **`diagram_entities._connections` (recommended — matches
  `_diagram_write.py:19` and the current save payload) vs. first-class `diagram_connections`** in the
  GUI/API; record the convention the editor *and* backend will use for `seq-from`/`seq-to`.
- **T0.3 — Diagram-type validation hook.** Design a hook by which a diagram-type module contributes its
  own verification (invoked by the generic verifier `artifact_verifier.py:299-335`), so sequence rules
  live in `src/diagram_types/sequence/` — not in generic verifier code. Mirrors the existing
  per-type renderer hook.
- **T0.4 — Slot-contract decision.** Audit `DiagramTypeUiSlotProps` (`diagramAuthoringExtensions.ts:9`)
  vs. the editor's needs; decide (criterion: **architectural clarity/soundness + simplicity**) whether
  to keep it or make **additive** changes (type the runtime `diagramConnections` prop; add
  `validationIssues?`/`onRequestPreview?`); document in `src/diagram_types/README.md` (§309-376); keep
  the activity slot working unchanged.

**Acceptance:** four written decisions land before UI work — finalised §2.3 schema, connection-transport
convention, validation-hook design, and the slot-contract decision; any contract change is **additive**
and the activity slot compiles and behaves identically.

### Phase 1 — Ontology Reframe (to the §2.3 schema) 🔴
- **T1.1** Evolve `src/diagram_types/sequence/ontology.yaml` to the **§2.3 schema**: rename
  `fragment`→`grouping` (with `operands[]` = `guard` + `start_message_id`/`end_message_id`; `label` for
  `group`/loop bound); move activations to **`message` flags** (`activate_target`/`deactivate_target`),
  dropping `execution-spec`; drop user-facing `sequence_index` (order = array index); evolve `note`
  (placement left_of/right_of/**over**, `lifeline_ids` 1..N, `after_message_id`). Relabel
  `ui.diagram_only_types` in `config.yaml` (Grouping, Activation) and **add `note`**.
- **T1.2** No migration needed (confirmed zero existing diagrams); add a **fixture round-trip test**
  (parse→model→render) asserting the new schema.

**Acceptance:** ontology validates against §2.3; `types.generated.ts` regenerated; relabelled types
appear; the fixture round-trips through parse→model→render.

### Phase 2 — Renderer Update
- **T2.1** Update `src/diagram_types/sequence/renderer.py` to consume **array order** + **message-id
  spans** for groupings/activations + per-message activation flags + nesting/else + notes; map to
  PlantUML idioms (arrows, `alt/else/opt/loop/par`, `activate/deactivate` or `++/--`, `note … of/over`).

**Acceptance:** golden-file tests render expected PlantUML for: ordered messages, each arrow type,
nested groupings with an `else`, optional activations, and notes (left/right/over); render is stable
under message reordering when ids are preserved.

### Phase 3 — Sequence Validation (via the diagram-type hook)
- **T3.1** Implement the Phase-0 **diagram-type validation hook**, then put sequence rules **in
  `src/diagram_types/sequence/`** (not in generic verifier code): every message has both endpoints;
  grouping `operands` contiguous / adjacent / non-overlapping & properly nested (§2.3 rules); note
  cardinality (left/right = 1, `over` = 1..N) and `after_message_id` resolve; activation flags
  reference valid messages; referenced lifelines exist → diagram **E-codes**, also surfaced for the
  editor's inline display via the Phase-0 channel.

**Acceptance:** each invalid construct yields a specific E-code from the sequence module (generic
verifier carries no sequence logic); a valid diagram verifies clean; issues are retrievable for inline
display.

### Phase 4 — Bespoke Sequence Authoring Component 🔴 (the core)
- **T4.1** Create `tools/gui/src/ui/diagram-types/sequence/`; register the `sequence` slot
  (`registerExtension('sequence', SequenceEditor, {managedOwnTypes:[lifeline,message,grouping,
  activation,note]})`), wire it in `diagram-types/index.ts`, add `type_ui_slots` to
  `sequence/config.yaml`. **Decompose** into subcomponents + a composable — e.g. `SequenceEditor.vue`
  (shell), `LifelineStrip.vue`, `MessageList.vue` (+ `MessageRow.vue`), `GroupingControls.vue`,
  `NotesEditor.vue`, and `useSequenceModel.ts` (state, ordering, span-selection, `_connections`
  read/write) — so **each file stays < 350 lines**.
- **T4.2** **Lifeline strip:** add/remove, type picker, optional model mapping (reuse
  `EntityPickerInput`), drag-reorder.
- **T4.3** **Ordered message list:** rows of `[from ▾] [arrow ▾] [to ▾] : [label]`, drag-reorder, sets
  `seq-from`/`seq-to` connections; no index field. Common settings inline with sensible defaults
  (sync arrow); **rarer arrow types/options (create/destroy, self, async) in a per-row expandable
  advanced section**.
- **T4.4** **Groupings:** multi-select a contiguous message span → "Wrap in grouping" → kind (priority:
  **alt/else**, **custom-label `group`**) + guard/label; **nesting + branching**; rendered as brackets
  around rows.
- **T4.5** **Activations (optional):** an **incoming-message activate/deactivate toggle** (no explicit
  spans).
- **T4.6** **Notes (optional):** add note on a message row → attach lifeline(s), side, text.
- **T4.7** **Live preview & inline validation:** debounced auto-preview (≈300–500 ms) with in-flight
  cancellation + dirty-state; cheap client-side structural checks for instant inline errors;
  authoritative E-codes via the validate path (Phase-0 channel).
- **T4.8** **Read-only plumbing:** thread a `readOnly` prop (from the existing read-only/write-block
  state, `state.py:258` / `App.vue:290`) into the editor and every subcomponent; disable
  add/remove/drag/save when set.

**Acceptance:** a user builds a multi-lifeline diagram with groupings, an activation, and a note
**without seeing any index/id field**; reordering messages preserves groupings/activations/notes;
invalid states are flagged inline and block save; generic sections do **not** appear for sequence;
`npm run lint` + `npm run typecheck` clean.

### Phase 5 — Polish, Events & Docs
- **T5.1** Empty-states, keyboard a11y for reorder, SSE refresh on save.
- **T5.2** Update `src/diagram_types/README.md` (sequence authoring + any contract change) and
  `README.md` (UML sequence authoring capability).

**Acceptance:** docs match behaviour; reduced-clutter UI verified against the screenshot's problems.

---

## 8. Traceability (stories ↔ phases)

| Story | Phases |
|---|---|
| US-1 lifelines | P4.2 |
| US-2 messages | P1.1, P2.1, P4.3 |
| US-3 groupings | P1.1, P2.1, P4.4 |
| US-4 activations | P1.1, P2.1, P4.5 |
| US-5 notes | P1.1, P2.1, P4.6 |
| US-6 live preview + inline validation | P0.3, P3, P4.7, §5.4 |
| US-7 reorder-safe (id-based) | P0.1, P1.1, §5.2 |
| US-8 read-only | P4.8, §5.4 |

---

## 9. Definition of Done

- The five central concepts are authored by direct manipulation; **no index/id fields** are exposed;
  the screenshot's specific problems are gone.
- Cross-references are **id-based**; reordering is non-destructive (verified).
- Sequence logic is confined to the sequence diagram-type modules; **no sequence-specific logic in
  generic components** (additive generic contract changes allowed); the extension-point change (if any)
  is additive, documented, and leaves the activity slot intact.
- The §2.3 schema, connection-transport convention, and **diagram-type validation hook** are
  implemented; sequence rules live in `src/diagram_types/sequence/`.
- Validation gates save with specific E-codes; inline issues display; **debounced/cancellable live
  preview** works; **read-only** disables the editor via an explicit prop.
- `SequenceEditor` is **decomposed** into subcomponents/composables (each < 350 lines).
- Renderer golden-file tests pass for arrows, nested groupings/else, activations, notes.
- No migration (confirmed zero existing diagrams); `types.generated.ts` regenerated.
- `ruff`, `zuban check`, frontend `lint`/`typecheck` clean; per-*file* < 350 lines; small cohesive PRs.
- README + `src/diagram_types/README.md` updated; aligned with the PUML-editing, grouping, and
  meta-ontology-v2 plans.
- 🔴 concerns (§5) closed; key decisions (§6) honoured.
