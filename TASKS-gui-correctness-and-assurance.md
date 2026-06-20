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
| F1 | Datatype attribute type selectable | F | done (interim) | — | **superseded by Type-Resolution plan** (`PLAN-datatype-type-resolution.md`): interim local-only/free-text combobox replaced by closed cross-repo picker in that plan's WU-5.2 |
| F2 | Datatype relabel mult / src-tgt cardinality | F | todo | — | **moved → Type-Resolution WU-5.4** (folded into the P5 editor rework; labels only) |
| F3 | Datatype unique constraints (+ mandatory verifier ext) | F | todo | TypeRes P0/P1 | verifier ext built as a **datatype verification contribution** on the new hook (Type-Resolution WU-0.7), not central wiring; see that plan's WU-5.4 note |
| F4 | Datatype notes on classifiers/relations | F | todo | — | **moved → Type-Resolution WU-5.4** (folded into P5; ontology `note` + NoteSection + PUML) |
| F5 | Datatype create/edit UX consistency pass | F | todo | TypeRes P5, F3 | capstone over the new combobox + F2 + F3 + F4 |
| G-INV | Capability matrix + exposure policy + benchmark + analysis aggregate + GSN dual-home | G | todo | — | decisions settled (OQ-5/OQ-8); design-only, first in G |
| G0 | Governing principle: assurance grounded in architecture | G | todo | G-INV | cross-cuts G1–G6 |
| G1 | Unlock-gated read endpoints + exposure policy + 423/404 | G | todo | G-INV | with G2 = one milestone |
| G2 | Navigable assurance browse + arch↔assurance lens | G | todo | G1 | ships with G1 |
| G3 | Assurance search (direct or ephemeral index) | G | todo | G-INV(benchmark),A1 | no-plaintext-persistence |
| G4 | Write endpoints + mutation policy + forms | G | todo | G-INV | needs missing use cases first |
| G5 | Method wizards (STPA/CAST/GRC/GSN/supply-chain/model-this) | G | todo | G4,G-INV | per-analysis scope |
| G6 | Assurance diagram views (3 sources) + baselines | G | todo | G1 | — |
| G7 | GSN renderer + reusable PUML shapes | G* | todo | OQ-7 | *architecture-subsystem; may run with E/F |
| G8 | Rework GSN exemplar (via artifact_edit_diagram) | G | todo | G7,G-INV(#5 bridge) | needs user domain input |

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
