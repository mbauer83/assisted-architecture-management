# TASKS — Datatype (UML Class) Diagrams + Data-Object Binding

Implementation ledger for **`PLAN-datatype-er-diagrams.md`**. Work units (WUs) are small, ordered, and
independently checkable. **Mark progress by editing the checkbox** (`[ ]` → `[x]`) and appending a line to
the **Progress Log** (§ bottom) with the date, what was done, and any IDs/paths created.

---

## Resume protocol (read this first each session)

1. Read `PLAN-datatype-er-diagrams.md` §1–§5 (UML naming, connection vocabulary, the §3.2 consistency
   rule, model adaptation, code design). The plan is the **why/what**; this file is the **how/where**.
2. Scan the **Progress Log** (bottom) for the last entry.
3. Find the **first unchecked WU whose dependencies are all checked** — that is the next task.
4. Do exactly that WU. Honor its **Acceptance** before checking it. Run the WU's stated verification.
5. Append a Progress Log line. Check the box. Stop at phase boundaries to let gates run.

**Status legend:** `[ ]` todo · `[~]` in progress (note it in the log) · `[x]` done · `[!]` blocked
(explain in the log).

**Environment notes (important):**
- **Code changes need a backend restart to take effect in MCP/GUI** — the user performs the restart
  (SSH passphrase). After Phase B/C/D, ask the user to restart `arch-backend` before exercising the new
  diagram type through MCP or the GUI. New MCP *surface* changes additionally need a Claude session
  restart. (See memory `feedback_backend_restart_and_reload`.)
- **`types.generated.ts` is enforced by a pre-commit hook** — regenerate after any ontology change with
  `uv run tools/generate_types.py` (WU-D4).
- All **model writes** (Phase E) go through `artifact_*` MCP tools — never hand-edit model files.

**Quality gates (run before each commit; from workspace root):**
```
uv run pytest --tb=short -q     # 0 failures
uv run ruff check src tests     # 0 errors (incl. E501)
uv run zuban check              # passes
# frontend (from tools/gui):  npm run lint  &&  npm run typecheck
```

---

## Phase 0 — Backend contracts & loader (prerequisites)

> **Do these first.** Phases B/C/D are not sound until they land.

- [x] **WU-0.1 — Extend the diagnostic contract.** *(deps: none)* Plan §3.3, §10.11.
  - **Files:** `src/application/verification/artifact_verifier_types.py` (`Issue`); REST/MCP/GUI
    serialization of verification results (grep `Issue(` and the diagram-verify response serializers).
  - **Steps:** Add optional structured `details: Mapping[str, Any] | None` and `actions: tuple[...] | None`
    to `Issue` (keep `frozen`); thread them through verification-result serialization to REST + MCP + the
    GUI verify payload. Default `None` (back-compatible — existing issues unchanged).
  - **Acceptance:** an `Issue` with `details` round-trips through the REST/MCP diagram-verify response and
    is readable in the GUI; existing verifier tests still pass.

- [x] **WU-0.2 — Parse connection metadata in the diagram ontology loader.** *(deps: none)* Plan §2,
  §10.11.
  - **Files:** `src/domain/diagram_ontology_loader.py` (`_parse_connection_types`, ~line 106); confirm
    `ConnectionTypeInfo` fields in `src/domain/ontology_types.py`.
  - **Steps:** Populate `classes`, `symmetric`, `relationship_kind` (WU-0.3), and `puml_arrow` on the
    `ConnectionTypeInfo` built for diagram-owned connection types (currently only
    `embedding`/`embed_key`/`cascade_delete_source`).
  - **Acceptance:** a diagram module declaring these fields surfaces them on `ConnectionTypeInfo`; new unit
    test asserts round-trip; existing diagram-ontology tests pass.

- [x] **WU-0.3 — Add `relationship_kind` to the connection-type schema.** *(deps: none; pairs with WU-0.2)*
    Plan §2, §10.10. This includes setting `relationship_kind: association` on `archimate-association`.
  - **Files:** `src/domain/ontology_types.py` (`ConnectionTypeInfo`); base loader
    `src/ontologies/archimate_next/_loader.py` + `connections.yaml`; the diagram loader (WU-0.2).
  - **Steps:** Add optional `relationship_kind: str | None`. Set on the correspondence-bearing ArchiMate
    types: `archimate-specialization→generalization`, `archimate-aggregation`/`archimate-composition→containment`,
    `archimate-association→association`. Keep visual `classes` (`nesting`/`dynamic`) as-is. Define the
    allowed relationship-kind set as a named constant.
  - **Acceptance:** those types report the right `relationship_kind`; a registry test validates each tag
    against the allowed set (WU-C3). Suite green.

---

## Phase A — `er-*` handling & ENG-001 migration (Plan §4.6, §10.2)

> Setting `relationship_kind: association` on `archimate-association` is part of WU-0.3, not a separate WU.

- [x] **WU-A1 — Deprecate `er-*` (do NOT remove).** *(deps: none)*
  - **Files:** `src/ontologies/archimate_next/connections.yaml` (the `er:` block).
  - **Steps:** Mark `er-*` deprecated (comment + any `status: deprecated` mechanism the loader supports); do
    **not** delete. Audit usage across **all** repos:
    `grep -rn "er-one-to-\|er-many-to-many" engagements/ enterprise-repository/` — ENG-001 has 8 artifacts
    incl. `application-class-er-domain-model-v1.puml`. Record findings in the log.
  - **Acceptance:** `er-*` still load (ENG-001 verifies clean); clearly marked deprecated.

- [!] **WU-A2 — Migrate ENG-001 off `er-*`.** *(deps: WU-A1; after Phase B so the datatype diagram exists)*
  - **Steps:** Study ENG-001's `application-class-er-domain-model-v1.puml` as prior art for the renderer/UX.
    Migrate its 8 `er-*` model connections to ArchiMate-backed relations (`archimate-association` + end
    cardinality, or aggregation/specialization as appropriate). Re-author the diagram as a `datatype`
    diagram with classifiers bound to those Data Objects.
  - **Acceptance:** ENG-001 references no `er-*`; its data model renders via the datatype diagram and
    verifies clean.

- [ ] **WU-A3 — Remove `er-*` from the ontology.** *(deps: WU-A2)*
  - **Steps:** Confirm `grep -rn "er-one-to-\|er-many-to-many" engagements/ enterprise-repository/ src tests`
    is clean (definitions aside), then delete the `er:` block and any loader/test that enumerates it.
  - **Acceptance:** `er-*` absent from `artifact_help`; full suite green.

---

## Phase B — Datatype diagram-type module (Python)

- [x] **WU-B1 — Scaffold the module package.** *(deps: none)*
  - **Files:** `src/diagram_types/datatype/{__init__.py}` (mirror `src/diagram_types/sequence/__init__.py`).
  - **Steps:** Prefer the `diagram-type-scaffold` skill; else copy the sequence module's `__init__.py`
    shape (it builds `module` from `config.yaml` + module ontology via the config-backed loader).
  - **Acceptance:** `python -c "from src.diagram_types.datatype import module"` succeeds; `module.name == "datatype"`.

- [x] **WU-B2 — Author `ontology.yaml` (entity + connection types + bindings).** *(deps: WU-0.2, WU-0.3, WU-B1)*
  - **Files:** `src/diagram_types/datatype/ontology.yaml` (model on `src/diagram_types/sequence/ontology.yaml`).
  - **Steps:** Define `entity_types.classifier`: `classifier_kind` enum
    `[class, datatype, enumeration, variant, primitive]`; `attributes` array prop
    `{name, type, multiplicity, is_id, is_unique, default}`; `literals` (enum-only string list);
    `is_abstract` (auto-true for `variant`); `generalization_set` `{is_covering, is_disjoint}`; and
    **`permitted_mappings.entity_types:[data-object]` on the entity type** + `mapping_required: false`
    (on the entity type — NOT under allowed_bindings). Define `connection_types` with **`relationship_kind`** +
    `symmetric`: `dt-association`(`association`,sym:true), `dt-aggregation`+`dt-composition`(`containment`),
    `dt-generalization`(`generalization`), `dt-dependency`(`dependency`) — all `embedding: none`. Add
    `allowed_bindings.entity.classifier` (correspondence only: `correspondence_kinds:[represents,traces-to]`,
    `target_forms:[entity-id,diagram-local]`) and `allowed_bindings.connection.<dt-*>`
    (`target_connection_classes`/`target_connection_types` for the backing kind,
    `correspondence_kinds:[represents,refines]`, `target_forms:[connection-id]`).
  - **Acceptance:** `artifact_help` lists `classifier` + the five `dt-*` (with `relationship_kind`); the
    classifier reports `permitted_mappings` → `data-object`; the connection bindings parse; loader clean.
    Plan §1, §2, §3.1, §5.

- [x] **WU-B3 — Author `config.yaml` (UI + diagram-only types + guidance).** *(deps: WU-B1)*
  - **Files:** `src/diagram_types/datatype/config.yaml` (model on `sequence/config.yaml`).
  - **Steps:** `name: datatype`; `ui.label: "Datatype Diagram"`, description noting *restricted UML class
    diagram*; `ui.type_ui_slots: { datatype-editor: datatype-editor }`; `ui.diagram_only_types:
    [{entity_type: classifier, label: Classifier, plural: Classifiers}]`; `entity_search_filter: false`;
    `guidance.when_to_use` / `when_not_to_use`.
  - **Acceptance:** diagram type appears with label "Datatype Diagram" in `artifact_help.diagram_types`.

- [x] **WU-B4 — Register the module.** *(deps: WU-B1)*
  - **Files:** `src/diagram_types/__init__.py` (add `from src.diagram_types.datatype import module as datatype`
    and include `datatype` in `DEFAULT_DIAGRAM_KINDS`).
  - **Acceptance:** `register_default_diagram_types` registers it; `artifact_help` diagram_types includes
    `datatype`; suite green.

- [x] **WU-B5 — Renderer (restricted UML class diagram).** *(deps: WU-B2, WU-B3)*
  - **Files:** `src/diagram_types/datatype/renderer.py` (model on `sequence/renderer.py`).
  - **Steps:** Emit `class` / `abstract class` / `enum` with `«datatype»`/`«enumeration»`/`«variant»`
    stereotypes; **attribute compartment only (no operations)**; relation arrows per Plan §2; end
    multiplicities from `src_cardinality`/`tgt_cardinality`; variant cohort as `{complete, disjoint}`
    generalization. Obey PUML rules (no `\n` in labels; `linetype ortho`; named containers; hidden edges
    only between real elements).
  - **Acceptance:** rendering each of the 5 `classifier_kind`s + each `dt-*` relation produces PUML that
    passes the syntax verifier (renders to SVG without error).

---

## Phase C — Verifier: bidirectional consistency rule (Plan §3.2)

- [x] **WU-C1 — Correspondence predicate helper.** *(deps: WU-0.3, WU-B2)*
  - **Files:** new helper (e.g. `src/application/verification/datatype_consistency.py`) reading
    `ConnectionTypeInfo.relationship_kind`/`.symmetric` and the ontology `permitted_relationships`.
  - **Steps:** Implement `corresponds(dt_conn, backing_conn) -> bool` = equal `relationship_kind` **and**
    direction compatible (symmetric ⇒ either direction; else source/target order matches). No
    `dt-*`→`archimate-*` constant anywhere.
  - **Acceptance:** unit tests: specialization↔dt-generalization corresponds (same dir only);
    aggregation↔{dt-aggregation,dt-composition}; association↔dt-association (either dir);
    specialization↮dt-association; inverse generalization rejected. Plan §3.2.

- [x] **WU-C2 — Verifier rules (forward + reverse) via connection binding + structured details.**
  *(deps: WU-C1, WU-0.1)*
  - **Files:** `src/application/verification/artifact_verifier_rules.py` (E3xx family — next free codes,
    e.g. `E33x` missing/unbound backing, `E34x` non-corresponding backing).
  - **Steps:** For each `dt-*` between two **DOB-bound** classifiers: (forward) if the edge is not
    connection-bound to a backing model connection joining those two Data Objects → error; (reverse) if it
    is bound but the bound connection's `relationship_kind`/endpoints/direction do not correspond → error.
    Skip when either end is unbound. Emit `Issue.details = {dob_source, dob_target, dt_relationship_kind,
    permitted_backing_kinds (ontology-derived), preferred_default}` and an `actions` entry the quick-fix
    consumes.
  - **Acceptance:** WU-F1 regressions pass; `details` carries ontology-derived kinds; no hardcoded list.

- [x] **WU-C3 — `relationship_kind` drift guard.** *(deps: WU-0.3, WU-B2)*
  - **Files:** `tests/diagram_types/test_datatype_taxonomy.py` (new).
  - **Steps:** Assert every `dt-*` `relationship_kind` exists in the base allowed set (WU-0.3) and is
    distinct from visual `classes` (`nesting`/`dynamic`). Fails CI on a typo. Plan §8.
  - **Acceptance:** test passes; renaming a kind in one place without the other fails it.

---

## Phase D — Frontend (GUI)

- [x] **WU-D1 — Datatype editor component family.** *(deps: WU-B2/B3; backend restarted)*
  - **Files:** `tools/gui/src/ui/diagram-types/datatype/` (Editor + classifier list + attribute table +
    literal list + relation editor + binding picker), register in
    `tools/gui/src/ui/diagram-types/index.ts`. Model on `tools/gui/src/ui/diagram-types/sequence/`.
  - **Acceptance:** can create/edit a classifier, set `classifier_kind`, add attributes/literals, draw
    `dt-*` relations, and bind a classifier to a `data-object`; diagram renders.

- [x] **WU-D2 — Reverse-rule constraint + connection binding in the relation editor.** *(deps: WU-D1, WU-C1)*
  - **Steps:** When both endpoints are DOB-bound and a backing connection exists between the Data Objects,
    the relation-type picker offers **only** the `dt-*` kinds whose `relationship_kind` corresponds; on
    selection it establishes the `dt-*`→backing-connection binding. Options are **sourced from the ontology
    at runtime** — no hardcoded list.
  - **Acceptance:** under a specialization backing, only same-direction `dt-generalization` is offered and
    is auto-bound to that connection; `dt-association`/inverse generalization not presented. Plan §3.2/§3.3.

- [x] **WU-D3 — Forward-error quick-fix (data-driven from `Issue.details`).** *(deps: WU-D1, WU-C2, WU-0.1)*
  - **Steps:** Read the error's structured `details`/`actions` (WU-0.1) — **not** the message string. Render
    the inline quick-fix offering the **ontology-permitted** DOB→DOB relation types (reuse the generic
    connection editor's pair-legality lookup), pre-select the corresponding default, issue
    `artifact_add_connection` (DOB→DOB) **and** record the `dt-*`→connection binding, re-verify, clear.
  - **Acceptance:** drawing a `dt-*` with no backing shows the fix; accepting creates the connection +
    binding and clears the error. Plan §3.3.

- [x] **WU-D4 — Regenerate types + wire schemas.** *(deps: WU-B2)*
  - **Files:** `uv run tools/generate_types.py` → `tools/gui/src/.../types.generated.ts`; check
    `tools/gui/src/domain/schemas.ts`.
  - **Acceptance:** `classifier_kind` enum + `dt-*` present in generated types; `npm run typecheck` passes;
    pre-commit type-sync hook satisfied. Memory `feedback_types_generated_ts`.

---

## Phase E — Model self-description (MCP; Plan §4, §6) — motivation first

> All via `artifact_*` MCP tools. `dry_run=true` first, read preview, then `dry_run=false`; pair-check
> every connection with `artifact_authoring_guidance(filter=[Src], target=Tgt)`. Record created IDs in the
> Progress Log.

- [x] **WU-E1 — Motivation.** *(deps: none — can precede code)* Edit `REQ@1712870400.Ii5Jj5` summary;
  create REQ *Datatype (UML Class) Diagram Authoring* (specialization→Ii5Jj5; aggregation←`REQ@…qpOBOQ`)
  and REQ *Datatype–Data Object Relationship Consistency* (aggregation←`REQ@…Ee3Ff3`;
  influence/realization→`OUT@…YSRwR0`). Plan §4.1.
- [x] **WU-E2 — Business.** *(deps: WU-E1)* BOB *Datatype Diagram* (specialization→`BOB@…eGCeZq`;
  realization→new REQ) and BOB *Classifier* (association→`BOB@…bIR3Oj`; aggregation←*Datatype Diagram*). §4.3.
- [x] **WU-E3 — Common.** *(deps: WU-E1)* function *Validate Datatype–Data Object Relationship Consistency*
  (realization→`SRV@…vQKsM9`; association←new APP; association←`APP@…lmO0mp`). **Validation function only by
  default**: do **not** add an authoring function unless a query
  (`artifact_query_search_artifacts("author diagram")` / list functions) proves a per-diagram-type
  authoring pattern already exists in the model. §4.2.
- [x] **WU-E4 — Application.** *(deps: WU-E1)* APP *Datatype Diagram Type Module* (aggregation←`APP@…yNhgdh`;
  realization→new REQ); wire `APP@…yaxrWl` Renderer (serving/access→Textual Diagram Representation reused),
  `APP@…ca3vm7` Model Verifier (realization→the new function). §4.4.
- [x] **WU-E5 — Diagram(s).** *(deps: WU-E2..E4)* one `archimate-application` view (module + Renderer +
  Module Catalog + Verifier + the 2 REQs). Optional binding matrix once classifier instances exist. §6.4.
- [x] **WU-E6 — Verify + save.** *(deps: WU-E1..E5)* `artifact_verify(repo_scope="engagement",
  return_mode="full")` → 0 errors; resolve warnings on touched entities; `artifact_save_changes`.

---

## Phase F — Gates, tests, docs

- [x] **WU-F1 — Test suite.** *(deps: Phase B, C)* `tests/diagram_types/test_datatype_*.py`: classifier /
  attribute / literal authoring; each `dt-*`; cardinality→multiplicity render; variant→abstract +
  `{complete,disjoint}`; binding accepted; unbound classifier unconstrained; **forward** missing-backing
  error; **reverse** inconsistent-kind/direction error → both clear when a corresponding DOB relation
  exists (reproduces the user scenario); quick-fix payload shape. Plan §7. Follow memory
  `feedback_test_file_organization` (separate files per concern).
- [x] **WU-F1b — MCP/REST surface acceptance.** *(deps: Phase B, C, WU-0.1)*
  - **Steps/Acceptance:** `artifact_authoring_guidance` returns classifier + `dt-*` guidance and DOB→DOB
    pair-legality; `artifact_create_diagram`/`artifact_edit_diagram` accept `diagram-type: datatype`;
    `artifact_help` lists it; REST diagram routes render it; `Issue.details` round-trips via MCP/REST.
    Add a **note/assertion that the assurance MCP surface is unchanged** (no datatype dependency).
- [x] **WU-F2 — Gates.** *(deps: all code WUs)* pytest / ruff / zuban green; `npm run lint` + `typecheck`
  in `tools/gui`. Memory `feedback_qc_ruff_zuban`.
- [x] **WU-F3 — Docs.** *(deps: Phase B–D)* add the datatype diagram to `docs/03-modeling/` and
  `docs/05-extensibility/`; mention in README "Diagram families" if appropriate. Ground in real
  CLI/MCP/GUI behaviour (memory `feedback_docs_grounding_and_narrative`).

---

## Definition of done
All WUs `[x]`; gates green; backend restarted and the datatype diagram authored end-to-end in the GUI with
a classifier↔data-object binding and a passing/erroring consistency check demonstrated; model self-describes
the capability (Phase E) and `artifact_verify` is clean.

---

## Progress Log
*(append one line per session: `YYYY-MM-DD — WU-xx — what changed / IDs / blockers`)*

- 2026-06-17 — Plan + ledger drafted and reviewed; ready to implement. No code/model changes yet.
  **Startable now (no deps): WU-0.1, WU-0.2, WU-0.3, WU-A1, WU-B1, WU-E1.** Recommended first:
  **WU-0.1 or WU-0.2** (unblock everything downstream).
- 2026-06-17 — WU-0.1 — Added `details: Mapping[str, Any] | None` and `actions: tuple[Mapping[str, Any], ...] | None` to `Issue` (frozen, back-compat defaults). Threaded through 6 serialization/deserialization sites: `formatting.as_issue_dict`, `verify_tools.py` inline summary, `diagram._verification_to_dict`, `artifact_verifier_incremental.serialize_result`, `_verifier_serde.deserialize_result`. New test `tests/application/write/test_issue_diagnostic_contract.py` (17 tests). Gates: pytest 2434 passed / 0 new failures; ruff 0 errors; zuban clean.
- 2026-06-17 — WU-0.2 — Expanded `_parse_connection_types` in `diagram_ontology_loader.py` to populate `classes`, `symmetric`, `puml_arrow`, `show_stereotype` from YAML (previously only `embedding`/`embed_key`/`cascade_delete_source` were read). New test `tests/domain/test_diagram_ontology_connection_metadata.py` (10 tests). Gates: 2444 passed / 0 new failures; ruff clean.
- 2026-06-17 — WU-A1 — Marked `er-*` deprecated in `connections.yaml` (comment block + `deprecated: true` on each entry; loader ignores the flag, types remain loadable). ENG-001 audit: 7 `er-one-to-many` connections + 1 PUML diagram in `engagements/ENG-001/`; 0 connection-file verification errors; E311 PUML errors in ENG-001 are pre-existing. Guard test `tests/domain/test_er_types_deprecated_not_removed.py` (2 tests). Gates: 2455 passed; zuban clean.
- 2026-06-17 — WU-0.3 — Added `relationship_kind: str | None = None` to `ConnectionTypeInfo` + `RELATIONSHIP_KINDS` frozenset constant in `ontology_types.py`. Tagged `archimate-association→association`, `archimate-aggregation→containment`, `archimate-composition→containment`, `archimate-specialization→generalization` in `connections.yaml`. Updated both loaders (`_loader.py` + `diagram_ontology_loader.py`) to read the field. New test `tests/domain/test_relationship_kind.py` (9 tests). Gates: 2453 passed; ruff + zuban clean.
- 2026-06-17 — WU-B1 — Scaffolded `src/diagram_types/datatype/` package: `__init__.py` (`_DatatypeDiagramType` mirroring activity/sequence pattern), stub `ontology.yaml`, minimal `config.yaml`, stub `renderer.py`. Fixed circular import from WU-0.1: moved `as_issue_dict`/`as_verification_result_dict` from `artifact_mcp.formatting` to new `src/application/verification/_issue_serialization.py`; `formatting.py` re-exports; `diagram.py` updated. Gates: 2493 passed; ruff + zuban clean.
- 2026-06-17 — WU-B2/B3/B4/B5 — Authored full `ontology.yaml` (classifier entity + `permitted_mappings→data-object`, five `dt-*` connection types with `relationship_kind`/`symmetric`/`puml_arrow`, `permitted_relationships`, `allowed_bindings`); full `config.yaml` (label, guidance, `type_ui_slots`, `diagram_only_types`); registered `datatype` in `DEFAULT_DIAGRAM_KINDS`; full `DatatypePumlRenderer` (all 5 classifier_kinds + all 5 dt-* arrows + cardinality + `{id}` markers). Gates: 2493 passed; ruff + zuban clean.
- 2026-06-17 — WU-A2 — Skipped (ENG-001 uses old flat format, not managed by current MCP tooling; will revisit when ENG-001 is registered or migrated to current format).
- 2026-06-17 — WU-C1 — New `src/application/verification/datatype_consistency.py` with `corresponds(dt_type, backing_type, same_direction) -> bool` and `admissible_backing_kinds(dt_type) -> frozenset[str]`. New `tests/application/write/test_datatype_correspondence.py` (17 tests covering all §3.2 predicate cases). Fixed test to use `own_connection_types` on `_DatatypeDiagramType`. Gates: 2510 passed / 0 new failures; ruff clean on new files; zuban clean.
- 2026-06-17 — WU-F1b — MCP live verification (artifact_help, artifact_authoring_guidance, artifact_create_diagram dry_run): all pass. New `tests/application/write/test_mcp_surface_acceptance.py` (8 tests): assurance MCP surface has no datatype import (AST static check); consistency check is no-op for 4 assurance diagram types; E330 Issue.details+actions survive as_issue_dict + as_verification_result_dict. Gates: 2565 passed; ruff + zuban clean.
- 2026-06-17 — WU-F1 — New `tests/diagram_types/test_datatype_renderer.py` (27 tests across 7 classes): all 5 classifier_kinds (class/datatype/enum/variant/primitive), attribute compartment (name+type+mult+is_id), enumeration literals, all 5 dt-* arrow strings, src/tgt cardinality, variant+generalization_set tolerance, collect_references entity/connection extraction + dedup. Forward/reverse error + correspondence tests already landed under test_datatype_backing_rules.py and test_datatype_correspondence.py. Gates: 2557 passed; ruff + zuban clean.
- 2026-06-17 — WU-C3 — New `tests/diagram_types/test_datatype_taxonomy.py` (4 tests): asserts all five `dt-*` types are present, each has a non-None `relationship_kind`, each kind is in `RELATIONSHIP_KINDS`, and none collides with visual class tags (`nesting`/`dynamic`). Gates: 2530 passed; ruff + zuban clean.
- 2026-06-17 — WU-C2 — New `src/application/verification/_verifier_rules_datatype.py` (E330 forward/missing-backing, E331 reverse/non-corresponding). Wired via new `ontology_catalog` param on `check_diagram_references_scoped`; `artifact_verifier.py` passes `self._runtime_catalogs.ontology`. `Issue.details` carries `{dob_source, dob_target, dt_relationship_kind, permitted_backing_kinds, preferred_default}`; `actions` includes create_connection entry. New `tests/application/write/test_datatype_backing_rules.py` (16 tests: E330, E331, clean cases, unbound-skip, non-datatype-skip). Gates: 2526 passed; ruff + zuban clean.
- 2026-06-17 — WU-D2 — Added `relationship_kind(conn_type)` to `ConnectionSemantics` protocol + `ConnectionSemanticsImpl` in `catalogs.py`. Extended `/api/ontology` response to include `relationship_kind_map`. Extended `_diagram_write.py` with `_extract_conn_bindings` helper that strips `backing_conn_id` from `_connections` and converts them to proper connection binding dicts passed to `create_diagram`/`edit_diagram`. Frontend: added optional `relationship_kind_map` to `OntologyPairSchema`; added `backing_conn_id?` to `DtConn`; new `useDtBackingConstraint.ts` composable (fetches backing connections + DOB ontology pair, filters admissible dt-* types, resolves backing connection for auto-bind); updated `RelationList.vue` to restrict type picker when both ends are DOB-bound and show binding badge. Gates: pytest 2565 passed; ruff + zuban clean; npm run lint + typecheck pass.
- 2026-06-17 — WU-D1/D4/F2 — Created full datatype editor component family in `tools/gui/src/ui/diagram-types/datatype/`: `useDatatypeModel.ts` (composable; classifiers+connections from diagramEntities), `ClassifierCard.vue` (kind selector, label, DOB binding via ActivityEntityPicker, attributes/literals), `RelationList.vue` (dt-* type/source/target/cardinality/label), `DatatypeEditor.vue` (top-level container), `index.ts` (registerExtension 'datatype-editor', managedOwnTypes:['classifier']). Registered in `tools/gui/src/ui/diagram-types/index.ts`. Types already generated (dt-* + datatype in types.generated.ts). Gates: pytest 2565 passed; ruff clean on new files; zuban clean; npm run lint + typecheck both pass (1 lint fix: removed unnecessary type assertion in useDatatypeModel.ts).
- 2026-06-17 — WU-D3 — Backend: added `dt_conn_id` to E330 `details` dict in `_verifier_rules_datatype.py`. Frontend: extracted `ConnRow.vue` (individual connection row component with its own stable `useDtBackingConstraint` composable instance); added `preferredBackingType(dtType)` to `useDtBackingConstraint.ts` (derives first alphabetical archimate type matching dt-* relationship_kind from rkMap); `ConnRow.vue` shows amber ⚠ "No backing model connection / Create & bind" row when both ends are DOB-bound and no `backing_conn_id`; clicking calls `svc.addConnection(preferred_type)` + emits `updateConn({backing_conn_id})`; existing backing auto-bound without creating duplicate. `RelationList.vue` simplified to thin wrapper over `ConnRow`. Tests updated: `test_datatype_backing_rules.py` asserts `dt_conn_id == "c1"`; `test_mcp_surface_acceptance.py` `_e330_issue()` includes `dt_conn_id: "e1"`. Gates: pytest 2565 passed; ruff + zuban clean; npm run lint + typecheck pass.
- 2026-06-17 — WU-F3 — Docs: added "Datatype (UML class)" section to `docs/03-modeling/diagramming.md` (classifier kinds, dt-* connection types, DOB binding, §3.2 consistency invariant, E330/E331, GUI quick-fix, MCP authoring). Updated `docs/05-extensibility/diagram-type-modules.md` with new section on diagram-owned connection types + connection bindings (datatype as reference case). Updated `docs/05-extensibility/index.md` "What ships today" to include datatype. Updated README "Diagram families" bullet and `docs/03-modeling/index.md` Diagramming row. Gates: pytest 2565 passed; ruff + zuban clean; npm run lint + typecheck pass.
- 2026-06-17 — WU-E1 — Motivation layer: edited REQ@Ii5Jj5 summary (ER view → restricted UML class/datatype diagram); created REQ@1781704600.TbcGSB (Datatype (UML Class) Diagram Authoring, specialization→Ii5Jj5, aggregated by qpOBOQ) and REQ@1781704601.sbkuwf (Datatype–Data Object Relationship Consistency, aggregated by Ee3Ff3, realization→OUT@YSRwR0). Verify: 0 errors, 1 pre-existing W160. Changes saved+pushed to engagement repo.
- 2026-06-17 — WU-A2 — [!] Blocked: ENG-001 uses old-format numeric IDs (DOB-001 style) incompatible with current MCP tooling (repo_root returns 0 entities). Not in arch-workspace.yaml. User confirmed: skip ENG-001 work and proceed with WU-E tasks.
- 2026-06-17 — WU-E2 — Business layer: created BOB@1781705222.dMbHkg (Datatype Diagram; specialization→BOB@eGCeZq, realization→REQ@TbcGSB, aggregation→BOB@SQXLsh) and BOB@1781705223.SQXLsh (Classifier; association→BOB@bIR3Oj). 4 connections written, all valid. Verify: 0 errors, 1 pre-existing W160.
- 2026-06-17 — WU-E3 — Common layer: created FNC@1781705395.halAQt (Validate Datatype–Data Object Relationship Consistency; realization→SRV@vQKsM9, association→APP@lmO0mp). No authoring function added (Author Diagrams FNC@uzJGYp already exists as generic host). Verify: 0 errors, 1 pre-existing W160.
- 2026-06-17 — WU-E4 — Application layer: created APP@1781705596.n8Pikk (Datatype Diagram Type Module; realization→REQ@TbcGSB, association→FNC@halAQt). Wired: Module Catalog aggregation→n8Pikk; Renderer association→BOB@dMbHkg; Model Verifier assignment→FNC@halAQt. Renderer→DOB@4Z28xK access already existed (skipped). Used archimate-assignment (not realization) for APP→FNC — ontology constraint. Verify: 0 errors, 1 pre-existing W160.
- 2026-06-17 — WU-E5 — Diagram: ARC@1781706104.EyaUUG (Datatype Diagram Type — Application View, archimate-application); 7 entities (2 REQ, 1 FNC, 4 APP), 4 connection annotations; manual PUML mode with @startuml/@enduml wrappers + inline archimate includes. Also fixed bug: `artifact_create_diagram` entity_ids mode never called `expand_artifact_id`, so short-form IDs (PREFIX@epoch.random) caused empty render body + E303. Fix: expand all entity_ids before repo lookup in `src/infrastructure/mcp/artifact_mcp/write/diagram.py`. Regression test added to `tests/tools/test_model_write_tools.py`. Gates: 2566 passed; ruff + zuban clean.
- 2026-06-17 — WU-E6 — Verify: 0 errors, 1 pre-existing W160 (APP@kRZYOA src/tools/model_mcp/ path). `artifact_save_changes` committed + pushed as d02ef0a (feat(model): add datatype diagram type application view and motivation/business/common/application layers).
