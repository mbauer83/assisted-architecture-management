# TASKS — Datatype (ER) Diagram Refinements

Execution ledger for `plans/` PLAN — Datatype (ER) Diagram Refinements (the approved plan
at `~/.claude/plans/synchronous-scribbling-oasis.md`). Checkbox work-units with file
anchors, acceptance criteria, deps, and a resume protocol. Markdown — no LoC limit.

## Locked decisions
- D1 GeneralizationSet = first-class diagram entity (`generalization_set`, `id_prefix: GSET`,
  `identity_scope: workspace`); `dt-generalization` carries a `generalization_set` id ref.
- D2 `identity` + `unique_keys` = dedicated validated structural fields (NOT generic schema).
- D3 Remove `unique_constraints` (property + UI + E337 reuse → repurposed for unique_keys).
- D4 Attributes get stable ids (`id`), hidden in UI; `name` freely renamable.
- D5 `optional` = distinct boolean on product-type attributes (separate from `multiplicity`).
- D6 `role` non-nullable for attribute-bearing classifiers + sum-type general end; not for
  enumeration / attribute-less value datatype.

## Diagnostic codes (final)
- E337 — `unique_keys`: member refs unresolved / duplicated / empty (repurposed from the old
  unique_constraints check; now references attribute **ids**).
- E338 — `identity`: member refs unresolved / duplicated; malformed shape.
- E339 — `generalization_set`: members of one set must share one general (target) end; the
  referenced set id must resolve.
- (existing E330/E331/E332/E334/E336/W333 unchanged.)

---

## Phase 1 — Backend contracts  (needs backend restart by user at end)  ✅ CODE COMPLETE

- [x] **WU-1.1 Ontology: kinds + GeneralizationSet + connection ref**
  `src/diagram_types/datatype/ontology.yaml`
  - Drop `variant` from `classifier_kind.enum` → `[class, datatype, enumeration, primitive]`.
  - Remove `classifier.properties.generalization_set` and `classifier.properties.unique_constraints`.
  - Per-attribute schema: remove `is_id`/`is_unique`; add `id` (string, stable).
  - Add `classifier.properties.identity` (array<string> attr-ids) + `unique_keys`
    (array<{name?, attribute_ids: array<string>}>).
  - Add entity type `generalization_set` (identity_scope: workspace, id_prefix: GSET;
    props: is_covering bool, is_disjoint bool, note?; permitted_mappings empty).
  - Add `generalization_set` ref property to `dt-generalization` connection_type.
  - Acceptance: `load_diagram_ontology` parses; startup_validation passes (`uv run zuban check`
    + import the module).

- [x] **WU-1.2 Ontology: descriptive metadata schemata (problem 4 defaults)**
  Same file. Add to `classifier.properties`: `role` (string), `internal_consistency_criteria`
  (array<string>), `external_consistency_criteria` (array<string>), `tags` (array<string>),
  `provenance` (string). Mark `required` per D6 semantics (note nullability is a GUI concern).
  Decide attribute-level metadata carrier (nested `attribute` schema block) — see WU-2.x.

- [x] **WU-1.3 config.yaml** — register `generalization_set` under `ui.diagram_only_types`
  (label, plural). `src/diagram_types/datatype/config.yaml`.

- [x] **WU-1.4 Renderer** `src/diagram_types/datatype/renderer.py`
  - Remove `"variant"` from `_KIND_META`; honour `is_abstract` → `abstract class` keyword.
  - Replace per-attr `is_id`/`is_unique` + `unique_constraints` note with `identity`/`unique_keys`:
    `{id}` on identity members, `{unique}`/`{unique:<name>}` on unique-key members
    (resolve attr-id → attr to place markers; keep a single composite-key note per classifier).
  - Render GeneralizationSet `{complete,disjoint}` note keyed by set over its generalizations.

- [x] **WU-1.5 Verifier contributions** `src/diagram_types/datatype/_contributions.py`
  - Repurpose `_UniqueConstraintContribution` → unique_keys over attribute **ids** (E337).
  - Add identity validation (E338) and generalization-set consistency (E339) contributions;
    wire into `__init__.py:diagram_verification_contributions`.
  - Remove `unique_constraints` consumption.

- [x] **WU-1.6 Type generation** `uv run tools/generate_types.py`; verify `types.generated.ts`
  diff (Attribute.id, identity, unique_keys, generalization_set; variant/is_id/is_unique/
  unique_constraints gone). Pre-commit hook enforces sync.

- [x] **WU-1.7 Backend tests** `tests/diagram_types/` + `tests/application/verification/`
  - Renderer: abstract general end, gen-set note, `{id}`/`{unique}` placement, composite note;
    assert no `variant`, no `unique_constraints` note.
  - Verifier: E337/E338/E339 happy + crafted-bad paths.
  - Gate: `python -m pytest --tb=short -q`, `ruff check src/ tests/`, `uv run zuban check`.

**>>> backend restart by user (SSH passphrase) before Phase 2/3 exercise live MCP/GUI <<<**

## Phase 2 — Schema mechanism (problem 4 plumbing)  ✅ DONE

- [x] **WU-2.1 Attribute metadata carrier** — declare a nested `attribute` schema so per-attr
  `optional`/`role`/`provenance` are ontology-driven (decision: nested schema block on
  classifier vs. `entity_types.attribute`). Wire through `diagram_type_config` /
  `DiagramOwnEntityTypePropertySpec` if a new shape is needed.
- [x] **WU-2.2 Attribute id allocation** — default to `IdentifierAllocator`
  (`src/application/identifier_allocator.py`) with `ATR` prefix, else diagram-local uid;
  ensure ids minted at create + back-filled on load.
- [x] **WU-2.3 Generic array UX upgrade** — `TypedPropertyInput.vue` / a small wrapper:
  add/remove line editor for `array<string>` instead of the JSON textarea (criteria/tags).

## Phase 3 — GUI  ✅ DONE

- [x] **WU-3.1 useDatatypeModel.ts** — interfaces: drop variant/is_id/is_unique/
  unique_constraints; add `Attribute.id`, `identity`, `unique_keys`, `GeneralizationSet`,
  conn `generalization_set`. Add CRUD for generalization_set + key editing helpers.
- [x] **WU-3.2 ClassifierCard.vue (+helpers)** — delete Constraints section + id/unique
  checkboxes + unique-constraint helpers; add compact Keys section (Identity ordered picker;
  Unique keys list) referencing attr-ids with name display; add metadata expander (role inline
  required marker + criteria/tags/provenance) and per-attribute chevron (optional/role/provenance).
- [x] **WU-3.3 GeneralizationSetCard.vue (new)** + wire into `DatatypeEditor.vue`; section CRUD.
- [x] **WU-3.4 ConnRow.vue / RelationList.vue** — generalization-set selector on dt-generalization.
- [x] **WU-3.5 Vitest** — `ClassifierCard.spec.ts` (Keys editor, Constraints removed, rename
  keeps keys, metadata expander), new `GeneralizationSetCard.spec.ts`.

## Phase 4 — Self-model + docs + QC

- [ ] **WU-4.1 Self-model** (ENG-ARCH-REPO) — update datatype-diagram capability model
  (GeneralizationSet, keys, per-type schemata) via MCP `artifact_*` tools only.
- [ ] **WU-4.2 MCP read** — `query_datatype_tools.py` / `_type_catalog.py`: surface
  GeneralizationSets + keys; drop unique_constraints.
- [x] **WU-4.3 Dogfooding diagram** (usability/sensibility check, user-requested) — author a
  real datatype diagram via MCP modelling a few of this system's own aggregates/entities and
  their relational structure (identity/unique keys, a sum type with a generalization_set,
  attribute roles/criteria). At least one or two classifiers from the **architecture
  meta-ontology** domain (e.g. Artifact / Entity / Connection / Diagram / EntityType /
  Binding — see `plans/meta-ontology-v2/`), given its centrality. Bind classifiers to their
  Data Object entities where they exist. Exercises the full surface end-to-end and serves as a
  worked example. Do after backend restart + GUI land so it can be created/edited live.
- [ ] **WU-4.4 Full QC** — pytest + ruff + zuban + vitest; Playwright route-walk on the
  datatype editor; `artifact_verify` clean on the dogfooding diagram + on ENG-ARCH-REPO.

---

## Resume protocol
1. Read this ledger + the PLAN. 2. `git status` / `git diff --stat`. 3. Find the first
unchecked WU; verify prior WUs by their acceptance criteria before continuing. 4. Backend
behaviour changes only take effect after the user restarts arch-backend; MCP surface changes
need a Claude session restart. 5. Run the QC gates after each phase. 6. No phase refs in
code/test content (memory: no_phase_refs_in_code).

## Progress log
- 2026-06-22: Ledger created; exploration complete.
- 2026-06-22: Phase 1 backend contracts CODE COMPLETE (WU-1.1–1.7). Ontology (kinds, GeneralizationSet entity, identity/unique_keys, attribute ids + metadata, removed variant/is_id/is_unique/unique_constraints/generalization_set-prop), renderer (is_abstract, key markers, composite-key note, gen-set note), verifier (E337/E338 keys, E339 gen-set; old E337 unique_constraints repurposed), tests rewritten. types.generated.ts unaffected (nested diagram schemas live in useDatatypeModel.ts). Full QC green: pytest 3332 passed/2 skipped, ruff clean, zuban clean. WU-1.6: confirmed no generated-types diff. **Awaiting user backend restart before Phase 2/3.**
- 2026-06-22: Phases 2&3 (GUI) DONE. Model adds GeneralizationSet + keys CRUD, stable attr ids (local uid), gen-set id via allocateDiagramEntityId GSET. Decomposed ClassifierCard 344→221 LoC into AttributeRow (chevron→optional/role/provenance), KeysSection+OrderedAttrPicker (identity + unique_keys ordered attr-id chips), ClassifierMetadata (role required marker + criteria/tags/provenance), StringListEditor (replaces JSON-textarea array UX = WU-2.3), GeneralizationSetCard + DatatypeEditor wiring, ConnRow gen-set selector on dt-generalization. WU-2.1: attribute schema is ontology-declared, rendered bespoke (classifier editor is a full type_ui_slot). WU-2.2: attr ids intra-classifier only → local uids suffice. Found+fixed DEAD tests: both .spec.ts never matched the vitest glob src/**/*.test.ts → renamed to .test.ts. GUI gates green: typecheck, eslint --max-warnings=0, vitest 325 passed (29 files); all datatype Vue <350 LoC. **Needs backend restart before live MCP/GUI + Phase 4 (self-model, MCP read, dogfooding diagram).**
- 2026-06-22 (post-restart): Phase 4 in progress. **Dogfooding diagram created** (DATATY@1782085920.9Nrbqf.artifact-persistence-model, group meta-ontology): Artifact abstract sum-type general end + Entity/Connection/Diagram/Document cases in a {complete,disjoint} generalization_set, Frontmatter value-object datatype composed in; composite identity on Connection, named unique key on Artifact.path, optional attrs, roles + consistency criteria + tags, DOB bindings on the 4 cases + Frontmatter. Verifies clean (valid, 0 issues). **Two real defects found+fixed via dogfooding:** (1) datatype type-ref resolution broken on write — verifier_for built no committed_repo (cross-diagram) AND temp-file verify had no overlay (same-write); fixed by wiring committed_repository into verifier_for + compile_projection now merging the under-verification diagram's own classifiers (label falls back to committed/binding-derived). (2) renderer emitted `class "X" <<stereo>> as alias` — invalid PlantUML (stereotype must follow alias); reordered to `as alias <<stereo>>` (PlantUML checkonly rc:0). Fixed stale 'Variant' in config.yaml guidance. Full QC green: pytest 3333 passed, ruff+zuban clean. **Backend restart needed** for verifier_for + renderer fixes to take effect live (then PNG render + classifier-typed-attr resolution work live). Remaining: WU-4.1 self-model, WU-4.2 MCP read surface, MCP tooling optimisation review (user ask), WU-4.4 full QC + Playwright.
