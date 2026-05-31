# C4 Renderer Corrections

**Status**: done (implemented 2026-05-31)  
**Root**: meta-ontology v2 post-implementation gap — discovered 2026-05-30 via browser testing.

## Background

Phase 0 (task #2) deleted `c4-contains` model connections. The legacy renderer
`_c4_resolve.py:_resolve_model_backed` was the only thing that used `c4-contains`
to separate *internal* entities from *external* ones. After Phase 0 it silently
broke: now every ArchiMate connection (including `archimate-aggregation`) is
followed and the target is labeled `«C4External»`. Phase 3 (task #14) built the
correct derivation strategy in `c4_scope_projection.py` — filtering structural
connections (`aggregation`/`composition`) from interaction connections
(`serving`/`flow`/`access`/`triggering`) — but only wired it into the MCP
`propose-bindings` path. The renderer was never updated.

The plan's SPEC-phase-3 §2.3 `c4-system-context` table also left a gap: it
didn't explicitly state that aggregation-connected entities are *excluded* at
context level (they are internal structure, not external context).

## Tasks

### A — Fix `_resolve_model_backed` in `_c4_resolve.py` *(critical)*

Replace the all-connections scan with connection-class-aware logic:
- **System context**: `internal_ids = ∅`; `candidate_ids` from `_NEIGHBOR_TYPES`
  connections only; aggregation-connected entities do not appear.
- **Container / component**: `internal_ids` from `_NESTING_TYPES` outbound from
  root; `candidate_ids` from `_NEIGHBOR_TYPES` incident to scope ∪ internal.
- **Connections rendered**: `_NEIGHBOR_TYPES` only; label falls back to a
  C4-appropriate default per type (`serving`→"uses", `flow`→"flows to",
  `triggering`→"triggers", `access`→"accesses") — never `<<aggregation>>`.
- Import/reuse the `_NESTING_TYPES` / `_NEIGHBOR_TYPES` constants already defined
  in `c4_scope_projection.py`; don't duplicate them.

**Acceptance criteria**
- [ ] AMS C4 System Context preview: zero `«C4External»` boxes, single `«C4System»`
  box only (AMS has no serving/flow neighbors).
- [ ] A service with real `archimate-serving` connections shows those neighbors as
  `«C4External»` with label "uses", not `<<serving>>`.
- [ ] `c4-container` still shows aggregation-connected entities as `«container»`
  inside the boundary (internal_items unchanged).
- [ ] `_conn_label` fallback never returns `<<aggregation>>` or any other nesting
  type label.
- [ ] `zuban check` green; full test suite green (≥ 1042 tests).

---

### B — Update SPEC-phase-3 §2.3 `c4-system-context` table

Add an explicit exclusion row and a note about the empty-neighbor case.

**Acceptance criteria**
- [ ] Table includes: entities reachable *only* via aggregation/composition →
  excluded from system-context projection (they are internal sub-components).
- [ ] Note added: when scope entity has zero `_NEIGHBOR_TYPES` connections the
  expected output is a single-node diagram; GUI or hint should suggest using C4
  Container instead.

---

### C — Add task #22 to `PLAN-meta-ontology-v2.md` Phase 5 checklist

Records the renderer rewire as a tracked, completable task.

**Acceptance criteria**
- [ ] Task #22 added under Phase 5: "Retire `_c4_resolve.py` all-connections scan;
  wire `c4.scope-projection/v1` into `_resolve_model_backed`; delete
  `c4-contains`-dependent paths; update connection labels."

---

### D — Add §2.4 use-case examples to SPEC-phase-3

Four concrete worked examples that future implementers and tests can use as
oracles.

**Acceptance criteria**
- [ ] §2.4 "C4 creation use-cases" added with:
  1. Nominal (serving connections present) — expected node types and edge labels.
  2. Aggregation-only scope (AMS case) — expected single-node output + hint.
  3. Mixed auto + manual — user adds a diagram-local person not yet in model;
     binding state and `view_derivations.selection` behavior described.
  4. Standalone sketch → model binding — standalone create then propose-bindings
     workflow described.

---

### E — Expose `excluded_entity_ids` in GUI model-backed create form *(UX, lower priority)*

Post-fix: make the derivation results interactive in the create form.

**Acceptance criteria**
- [ ] After clicking Preview in model-backed mode, auto-derived entities are shown
  as a checklist; unchecking sets `_excluded_entity_ids`.
- [ ] Zero-neighbor case shows: *"No external connections found. This entity may be
  better represented as a C4 Container diagram."* instead of a sparse render.

---

---

### F — Restructure `diagram_types/` into family subdirectories *(standalone, do separately)*

Move shared family files off the root of `diagram_types/` into proper subdirectories.
Do **both** C4 and ArchiMate in one pass to avoid a piecemeal restructure.

**Target layout:**
```
src/diagram_types/
  c4/
    __init__.py
    _type.py          (was _c4_type.py)
    renderer.py       (was c4_renderer.py)
    _resolve.py       (was _c4_resolve.py)
    _projection.py    (was _c4_projection.py)   ← added 2026-05-31
    _navigation.py    (was _c4_navigation.py)
    system_context/   (was c4_system_context/)
    container/        (was c4_container/)
    component/        (was c4_component/)
  archimate/
    __init__.py
    _type.py          (was _archimate_type.py)
    application/      (was archimate_application/)
    business/         (was archimate_business/)
    implementation/   (was archimate_implementation/)
    layered/          (was archimate_layered/)
    motivation/       (was archimate_motivation/)
    strategy/         (was archimate_strategy/)
    technology/       (was archimate_technology/)
  activity/           (unchanged)
  sequence/           (unchanged)
  matrix/             (unchanged)
  _config_type.py     (unchanged — shared across families)
  __init__.py         (updated imports only)
```

**Scope rules:**
- Python import paths change; diagram type string keys in `config.yaml` (`name:` fields)
  do **not** change — no frontend or artifact impact.
- This is a pure rename/move: zero logic changes. Any logic change is a bug, not part of
  this task.
- Do not combine with any logic fix. Run in isolation.
- Update `src/diagram_types/README.md` to reflect the new layout.

**Acceptance criteria**
- [ ] All files moved; no root-level `_c4_*`, `c4_renderer.py`, or `_archimate_type.py`
  remain.
- [ ] All Python imports updated (src + tests); `grep -r "diagram_types\._c4\|diagram_types\.c4_\|diagram_types\._archimate"` returns nothing.
- [ ] Full test suite green (≥ 1072 tests); `zuban check` clean.
- [ ] `src/diagram_types/README.md` updated to show new layout.
- [ ] No changes to `config.yaml` `name:` fields, no changes to frontend, no logic edits.

---

## Implementation order

A → C → B → D → E (E deferred if scope is too large for this session)  
F is independent — run separately after A–E are done.

## Checklist

- [x] A — `_c4_resolve.py` renderer fix
- [x] B — SPEC-phase-3 §2.3 table update
- [x] C — PLAN-meta-ontology-v2.md task #22
- [x] D — SPEC-phase-3 §2.4 use-cases
- [x] E — GUI excluded_entity_ids checklist
- [x] F — `diagram_types/` family subdirectory restructure (standalone, do separately)
- [x] G — `collect_derived_items` removed (2026-05-31). Replaced by `ViewProjector.project_view` + unified `project_c4` engine. Preview endpoint now calls `project_view_for_preview` (generic service). Renderer (`_c4_resolve._resolve_model_backed`) converged onto the same engine. See `PLAN-diagram-view-derivation.md` (status: done).
