# TASKS — ArchiMate 4 Compliance

Execution ledger for `PLAN-archimate-4-compliance.md`. Checkbox work-units with file
anchors, acceptance criteria, and dependencies. Markdown — no LoC limit.

## Resume protocol

1. Read `PLAN-archimate-4-compliance.md` §3 (locked decisions) + the section for the phase
   you are in; do NOT re-litigate locked decisions.
2. Find the first unchecked WU whose deps are all checked; verify its anchors still exist
   (`rg` the symbols) before editing — anchors are a 2026-07-09 snapshot.
3. Quality gates after every WU: `python -m pytest --tb=short -q` (0 failures),
   `ruff check src/ tests/` (0 errors), `uv run zuban check`; frontend WUs additionally
   `npm run lint` + `npm run typecheck` in `tools/gui`; regenerate
   `uv run tools/generate_types.py` after any ontology/type change (pre-commit enforces).
4. All self-model writes via MCP tools only (never manual file edits). MCP tools run against
   the long-running backend — code changes need a backend restart (user does it); note it in
   the ledger entry and continue with non-MCP work if blocked.
5. Tick the WU, append one line under Progress notes (date, WU, outcome, surprises). No
   phase names in code/test content or filenames — use feature names.

## Locked decisions (see PLAN §3 for full text)

- D1 full three-token rename: pkg `archimate_4`, module `archimate-4-0`, alias
  `archimate-4`; fix `permitted_mappings` token inconsistency; no legacy alias.
- D2/D3 guidance = empty in-repo + gitignored overlay dir + CLI import; schema
  module→entity-type→specialization, connection keys reserved.
- D4 specializations enumerated in `specializations.yaml` (module + `.arch-repo/`); attribute
  schemas attach by naming convention, never define.
- D5 remove dormant `OntologyModule.attribute_profiles` after call-path verification;
  migrate assurance content to scaffolded repo schemata.
- D6 `specializations: [slug]` frontmatter list; artifact-type stays the parent type.
- D7 one `ConceptScope` primitive; diagram-type filters + binding admissibility + viewpoints
  all compile to it; old filter paths deleted, not paralleled.
- D8 non-destructive viewpoint application; enforcement `off|warn|ghost`, no hard block.
- D9 multiplicity rename scoped to ArchiMate relationship ends + one-time migration;
  diagram-type `cardinality_min/max` keeps its name.
- D10 exchange = `src/application/exchange/` use cases + `src/infrastructure/exchange/`
  adapter; defusedxml + XSD validation; CLI-first, no new MCP tools.
- D11 self-model via MCP; new ADR supersedes NEXT ADR (history preserved).

## Anchors (snapshot 2026-07-09)

- Ontology pkg: `src/ontologies/archimate_next/{__init__.py,_loader.py,entities.yaml,connections.yaml}`;
  module name `_loader.py:38`; glyphs path `_loader.py:21` → `tools/gui/src/ui/lib/archimateGlyphs.json`.
- Registration + aliases: `src/infrastructure/app_bootstrap.py:23-35` (`_ALL_ONTOLOGY_MODULES`),
  `:164-167` (`_META_ONTOLOGY_ALIASES`), `registered_meta_ontology_values()` `:170-188`.
- Registry: `src/domain/module_registry.py` (`find_ontology :48-58`, `all_entity_types :76`).
- Token consumers: `src/diagram_types/c4/_projection.py:341`;
  `src/diagram_types/archimate/*/config.yaml:2` (pkg name);
  `src/diagram_types/{activity,datatype,sequence}/ontology.yaml` sources (pkg name — WRONG,
  fix to module name); `src/diagram_types/c4/*/ontology.yaml` sources + bridges (module
  name); resolution `src/domain/permitted_mappings.py:24`.
- Frontend: `tools/gui/src/ui/lib/domains.ts:49,61` (`FRAMEWORK_GROUPS`, `DEFAULT_MODULES`);
  tests `domains.test.ts:10`, `ModelWizardView.helpers.test.ts:6`.
- Guidance: `EntityTypeInfo` `src/domain/ontology_types.py:73-97`; loaders
  `src/ontologies/*/_loader.py::_load_entity_types`; consumer
  `src/infrastructure/write/artifact_write/type_guidance.py::get_type_guidance` (`:84`,
  lru_cache `:49`); MCP `src/infrastructure/mcp/artifact_mcp/write/entity.py:20-25`; REST
  `src/infrastructure/gui/routers/authoring_guidance.py`.
- Profiles (declarative): `src/application/artifact_schema.py` (`load_attribute_schema`),
  `.arch-repo/schemata/attributes.{type}.schema.json`,
  `src/infrastructure/workspace/_repo_default_schemata.py`.
- Profiles (dormant): `src/domain/ontology_protocol.py:82`;
  `src/ontologies/assurance/_loader.py:20-106,115`; archimate `_loader.py:43`;
  sysml `_loader.py:28`; tests `tests/assurance/test_assurance_module.py:54-73`,
  `test_module_catalog.py`/`test_catalogs.py` stubs.
- Relationships: `src/ontologies/archimate_next/connections.yaml`
  (`archimate-composition`/`-aggregation` ~:37-51, `matrix_abbreviations`,
  `permitted_relationships`); `src/domain/permitted_relationships.py`;
  `src/domain/catalogs.py` (`ConnectionSemantics`); GUI `GET /api/ontology`
  `src/infrastructure/gui/routers/connections.py`.
- Multiplicity: `src/domain/artifact_types.py::ConnectionRecord.src_cardinality/tgt_cardinality`;
  `src/domain/archimate_relation_rendering.py::format_cardinality_label`;
  `include_cardinality` annotation (`src/diagram_types/archimate/_type.py` ~:35).
- Diagram-type filters: `src/diagram_types/_config_type.py::_build_entity_filter` (+ `:52`
  importlib); `DiagramTypeModule.accepts_entity_type/accepts_connection_type/effective_*`
  (`src/domain/ontology_protocol.py`, `src/diagram_types/_base.py`);
  bindings `src/domain/allowed_bindings.py`, `src/domain/bindings.py`;
  UI config endpoint `src/infrastructure/gui/routers/diagram_types.py`.
- Derivation engine (generated views): `src/application/derivation/`,
  `src/domain/view_derivations.py`, `src/domain/view_projection.py`.
- Write/CLI/verifier: `src/infrastructure/write/artifact_write/`;
  CLI pattern `src/infrastructure/cli/arch_assurance.py::main` (argparse subparsers) +
  `pyproject.toml [project.scripts]:23-37`; urllib idiom
  `src/infrastructure/bootstrap/get_plantuml.py:40-68`; repair pattern
  `src/infrastructure/cli/arch_repair.py`; verifier
  `src/application/verification/`; dep policy
  `tests/architecture/test_dependency_policy.py` (+ `architecture_baseline.json`).
- Self-model: 155 `archimate-aggregation` connections (stats 2026-07-09); ADR
  `ADR@1780761591._mseZr.adopt-archimate-next-ontology`; entity
  `REQ@1712870400.KeGCZE.archimate-next-model-ontology`.

---

## Phase A — Rename (D1)

- [ ] **WU-A1 Rename inventory** — `rg -i 'archimate[_-]?next'` across repo (excl.
  node_modules, historical PLAN-*/TASKS-* ledgers, `.git`). Produce the checklist grouped:
  machine tokens / display strings / docs / skills / self-model content. Confirm no
  `meta_ontology:` values exist in any `groups.yaml`. Acceptance: checklist committed into
  this file under Progress notes (or linked scratch file); zero unknown categories.
- [ ] **WU-A2 Package + module rename** — dir → `src/ontologies/archimate_4`; loader class +
  `load_archimate_4_module`; `name = "archimate-4-0"`; alias map →
  `{"archimate-4": "archimate-4-0"}`; imports in `app_bootstrap.py`; c4
  `_projection.py:341` tuple. Acceptance: full test suite green; `find_ontology("archimate-4-0")`
  works; no import of `archimate_next` remains. (deps: A1)
- [ ] **WU-A3 Config token reconciliation** — all `archimate/*/config.yaml` `ontology:` →
  `archimate_4` (pkg); ALL `permitted_mappings.sources[].ontology` + c4 bridge `to.module` →
  `archimate-4-0` (module name), including fixing activity/datatype/sequence which
  currently hold the pkg name. Add startup/verifier check: every `permitted_mappings`
  ontology token must resolve via `registry.find_ontology` (fail loud, listing offenders).
  Add a regression test for the check. Acceptance: check passes on the repo; test proves it
  fails on a bad token. (deps: A2)
- [ ] **WU-A4 Frontend + generated types** — `domains.ts` key `archimate-4`, moduleName
  `archimate-4-0`, label `ArchiMate 4`; update frontend tests; regenerate
  `types.generated.ts`. Acceptance: vitest + lint + typecheck green. (deps: A2)
- [ ] **WU-A5 Docs/skills/README sweep** — display-string rename in `docs/**`,
  `src/ontologies/README.md`, `src/diagram_types/README.md`,
  `.claude/skills/ontology-module-scaffold/SKILL.md`, `skills/reverse-architecture/SKILL.md`,
  README badge (`Model: ArchiMate 4`) + Status section wording (respect open question Q4 —
  keep "no conformance claim" wording until Q4 resolved). Historical ledgers untouched;
  add supersession note to `PLAN-archimate-next-rule-conformance-and-repository-cleanup.md`
  only if it reads as current guidance. Acceptance: WU-A1 checklist fully ticked;
  `rg -i 'archimate[_-]?next'` hits only historical ledgers + self-model content (Phase G).
  (deps: A1–A4)

## Phase B — License compliance: guidance externalization (D2/D3)

- [ ] **WU-B1 Guidance domain type** — `src/domain/guidance.py`: `GuidanceKey`,
  `GuidanceEntry`, `GuidanceOverlay` (frozen; pure merge; empty = no-op). Unit tests
  (merge precedence, specialization keys, unknown-key pass-through). Acceptance: dep-policy
  clean (domain-pure); tests green.
- [ ] **WU-B2 Loader threading** — `load_archimate_4_module(guidance=…)` applies overlay to
  `EntityTypeInfo` guidance fields; same optional param for sysml/assurance loaders
  (accepted, unused by default); `app_bootstrap` loads `<guidance_dir>/*.guidance.yaml`
  (default `ontology-guidance/`, gitignored; `config/settings.yaml`: `guidance_dir`,
  `guidance_default_source: ""`) and passes per-module slices. Acceptance: overlay applied in
  a bootstrap test; absent dir = current behavior. (deps: B1, A2)
- [ ] **WU-B3 Extraction + strip** — `tools/extract_guidance.py` emits the publishable v1
  YAML (PLAN §4.3 schema) from current `entities.yaml` texts to an **out-of-repo** path
  (default: scratch/home, never the workspace); then strip all `create_when`/
  `never_create_when` values in `src/ontologies/archimate_4/entities.yaml` to `""` in the
  same change. Verify the emitted file re-imports losslessly (B4 round-trip test fixture is
  a *small synthetic* file — the real extract stays out of repo and out of tests).
  Acceptance: zero guidance prose in archimate entities.yaml; extractor output validates;
  gitignore covers `ontology-guidance/` + `*.guidance.yaml`. (deps: B2)
- [ ] **WU-B4 Import CLI** — `src/infrastructure/cli/arch_import_guidance.py` +
  `[project.scripts] arch-import-guidance`. `--source <url|path>` (default from settings),
  `--module <alias>`, `--dry-run`, `--strict`. URL: HTTPS-only default (explicit
  `--allow-http`), urllib idiom, timeout, size cap; `yaml.safe_load`; schema validation;
  key validation against registry + `SpecializationCatalog` when present (unknown keys
  listed; skipped unless `--strict`); writes `<guidance_dir>/<alias>.guidance.yaml`; summary
  (matched/unmatched/bytes); prints restart note. Tests: happy path (tmp file), unknown
  keys, bad schema, oversize, http rejection. Acceptance: import → restart-equivalent
  rebootstrap in test → `get_type_guidance` returns imported text. (deps: B2, B3)
- [ ] **WU-B5 Empty-state surfacing + prose sweep** — `artifact_authoring_guidance` + REST
  guidance payload state explicitly when a module's guidance is empty and name the import
  command; GUI wizard shows the hint. Sweep docs/`own_entity_types` guidance for residual
  ArchiMate-spec-derived prose (expected: none — record conclusion). Acceptance: empty-state
  text asserted in MCP description test; sweep conclusion in Progress notes. (deps: B4)

## Phase C — Core semantics: composition, Appendix B, multiplicity

- [ ] **WU-C1 Composition semantics verification** — against final §5.1.2: composition
  permitted wherever aggregation is (diff the two types' rows in
  `permitted_relationships`); strength ordering realization < assignment < aggregation <
  composition everywhere relationship strength/classification is consumed
  (`hierarchy_priority`, `ConnectionSemantics.classify_connections`, derivation/preview
  logic). Fix deltas; add rule tests (incl. "composition permitted ⊇ aggregation
  permitted" as a structural test). Record section-number citations in Progress notes (spec
  not committed — no-PDF policy). Acceptance: structural test green. (deps: A3)
- [ ] **WU-C2 Appendix B matrix recheck** — systematic diff of
  `permitted_relationships` + `matrix_abbreviations` against final Appendix B. Produce the
  diff report FIRST (scratch), review, then apply rule edits + changed-rule tests.
  Self-model `artifact_verify` run after; regressions triaged before ticking. Acceptance:
  diff report recorded (link/summary in Progress notes); rules updated; verify clean or
  deltas explained. (deps: C1)
- [ ] **WU-C3 Multiplicity rename (code)** — `ConnectionRecord.src_multiplicity/tgt_multiplicity`,
  `format_multiplicity_label`, `include_multiplicity` annotation, parser/writer, GUI
  labels/fields, docs. Parser accepts legacy keys ONLY until C4 completes (tracked TODO
  referencing the migration, removed in C4). Acceptance: suite green with both key forms
  during window. (deps: A2)
- [ ] **WU-C4 Multiplicity migration + junction rule** — migration command (arch-repair
  subcommand or equivalent) rewriting legacy keys in both repos, idempotent, count report,
  through the standard write/index path; then remove legacy-key acceptance and add verifier
  warning for legacy keys. Add junction rule: warn when multiplicity set on a
  junction-attached connection end. Acceptance: both repos migrated (0 legacy keys);
  junction-rule test; re-run migration = 0 changes. (deps: C3)

## Phase D — Specializations (D4/D5/D6)

- [ ] **WU-D1 SpecializationCatalog (domain)** — `src/domain/specializations.py`:
  `SpecializationInfo` (slug, name, entity_type, module_alias, description, notation
  icon/color, restrict_relationships, guidance fields), `SpecializationCatalog`
  (uniqueness per (module, entity_type, slug); lookup by entity type; restriction-narrowing
  validation hook). Parser for the PLAN §4.2 YAML shape (pure function). Unit tests.
  Acceptance: dep-policy clean; tests green.
- [ ] **WU-D2 Loading + informative library** — module-level `specializations.yaml` loading
  in the archimate_4 loader; ship the §14.2.1 informative library (role/collaboration/
  service/process/function/event families + contract, constraint, gap, representation-like,
  money-flow, assignment variants; names + parents only, guidance empty); per-repo
  `.arch-repo/specializations.yaml` loading (workspace/bootstrap layer) merged into the
  catalog; guidance overlay (B1) applies to specialization entries. Acceptance: catalog
  contains library + repo entries in a fixture; duplicate slug rejected loudly. (deps: D1,
  B2)
- [ ] **WU-D3 Frontmatter + verifier** — entity frontmatter `specializations: [slug]`;
  parse/write round-trip; verifier rules: unknown slug (error), parent-type mismatch
  (error), `restrict_relationships` violation (warning), restriction-broadening in
  declaration (error at load). Scaffolded `frontmatter.entity.schema.json` gains the
  optional property. Acceptance: rule tests incl. round-trip. (deps: D2)
- [ ] **WU-D4 Attribute-schema attachment** — `attributes.{artifact_type}.{slug}.schema.json`
  convention in `artifact_schema.py` (merge over base type schema when entity carries the
  specialization; orphan schema file → verifier warning referencing D4 rule). Acceptance:
  validation uses merged schema in tests; orphan detection test. (deps: D3)
- [ ] **WU-D5 Rendering** — guillemet stereotype `«slug-display»` (multiple: comma-joined)
  in PUML output for entities carrying specializations; notation icon/color when declared,
  parent-notation fallback otherwise (respect existing `show_stereotype` heuristic
  conventions). Acceptance: renderer snapshot tests for labeled + icon + fallback cases.
  (deps: D3)
- [ ] **WU-D6 GUI + guidance exposure** — specialization picker on entity create/edit
  (options from catalog for the chosen type), display in entity detail/list;
  `artifact_authoring_guidance` includes per-type specialization enumeration + guidance;
  regenerate `types.generated.ts`. Acceptance: vitest for picker helpers; guidance payload
  test. (deps: D3)
- [ ] **WU-D7 Dormant profile surface removal (D5)** — call-path verification that
  `OntologyModule.attribute_profiles` has no live consumer (registry, routers, MCP,
  verifier, frontend; record method + result). If dead: remove protocol field + three class
  attributes + assertion-only tests; migrate assurance profile content into
  `_repo_default_schemata.py` as `attributes.{hazard,risk,unsafe-control-action,
  assurance-constraint,control-structure-node}.schema.json` scaffolding defaults; add a
  scaffolding test asserting new repos receive them. If a consumer is found: STOP, record
  in Progress notes, escalate to review. Acceptance: protocol slimmed, assurance schemas
  scaffolded, suite green. (deps: D4)

## Phase E — Viewpoints (D7/D8)

- [ ] **WU-E1 ConceptScope (domain)** — `src/domain/concept_scope.py`: frozen scope
  (explicit type sets + class/hierarchy predicates + connection types + endpoint rules),
  `admits_entity_type/admits_connection_type/admits_connection`, intersection `&`.
  Characterization test capturing current `effective_entity_types` +
  `accepts_connection_type` behavior per registered diagram-type module (pre-refactor
  snapshot for E2). Unit tests. Acceptance: dep-policy clean; snapshot recorded.
- [ ] **WU-E2 Re-base diagram-type filters (replacement)** — reimplement
  `_config_type.py::_build_entity_filter` + `DiagramTypeBase.accepts_entity_type/
  accepts_connection_type/effective_*` over a module-derived `ConceptScope`; binding-target
  admissibility (`permitted_mappings` source eligibility) evaluates through the same
  primitives (correspondence semantics in `allowed_bindings.py` unchanged). DELETE the
  superseded ad-hoc filter code (no parallel path). Acceptance: E1 characterization
  snapshot unchanged; existing diagram-type suites green; dep-policy baseline not grown.
  (deps: E1)
- [ ] **WU-E3 ViewpointDefinition + persistence** — `src/domain/viewpoints.py` (PLAN §4.4
  shape: purpose/content enums, stakeholders, concerns, scope, representation_types,
  derivation_defaults); YAML parsing; module `viewpoints.yaml` (small starter library —
  e.g. motivation, application-structure, layered, technology-usage) + `.arch-repo/viewpoints.yaml`
  loading into a `ViewpointCatalog` (slug-unique); scope may reference specializations
  (member-of predicate) — catalog validation. Acceptance: catalog fixture tests; duplicate/
  unknown-type declarations rejected loudly. (deps: E1, D2)
- [ ] **WU-E4 Application + verifier** — diagram/matrix frontmatter `viewpoint: <slug>`;
  effective authoring scope = diagram-type scope ∩ viewpoint scope; verifier contribution:
  out-of-scope element/connection ⇒ warning (distinct code, never error; distinct from
  metamodel violations); enforcement setting `off|warn|ghost` in `config/settings.yaml`.
  Scaffolded `frontmatter.diagram.schema.json` gains the optional property. Acceptance:
  warning fires in tests; `off` silences; unknown viewpoint slug = verifier error. (deps:
  E2, E3)
- [ ] **WU-E5 GUI** — viewpoint selector on diagram create/edit (default: none =
  unrestricted); palette + entity-picker filtering via narrowed scope (extend
  `ui-config`/`/api/ontology` with optional `viewpoint` param); ghosting (not removal) of
  out-of-scope existing content per enforcement setting; viewpoints management view
  (list/create/edit repo definitions; module ones read-only). Acceptance: vitest helper
  tests; route-walk smoke passes; manual screenshot in Progress notes. (deps: E4)
- [ ] **WU-E6 MCP/guidance exposure** — viewpoint enumeration + per-viewpoint scope summary
  in `artifact_authoring_guidance`; `artifact_create_diagram`/`artifact_edit_diagram`
  accept the frontmatter field (no new tools); tool-description test updated. Acceptance:
  guidance payload test; description test green. (deps: E4)

## Phase F — Model Exchange (C19C v3.1) (D10)

- [ ] **WU-F1 Mapping table + XSD acquisition** — `exchange_mapping.yaml` in the adapter
  package: bidirectional element/relationship mapping incl. Appendix E.4 rows
  (3.x type → archimate-4 type + specialization slug; invalid-relationship → association;
  composition preserved both ways; multiplicity mapping; property/profile mapping).
  Dev-time XSD fetch script (gitignored target, pinned checksum) — resolves open question
  Q3 before implementation. Acceptance: mapping table review-complete; every §14.2.1
  library slug referenced by at least the forward direction or explicitly marked
  no-3.x-equivalent. (deps: D2, C1; blocked-by: Q3)
- [ ] **WU-F2 Codec adapter** — `src/infrastructure/exchange/archimate_model_exchange/`:
  defusedxml-based reader (XSD validation, size cap) + writer; application-defined ports
  `ExchangeDocumentReader/Writer` in `src/application/exchange/ports.py`. Round-trip unit
  tests on synthetic documents. Acceptance: dep-policy clean (application imports no infra);
  malformed/oversize/XXE fixtures rejected. (deps: F1)
- [ ] **WU-F3 Import/export use cases** — `src/application/exchange/import_model.py`
  (dry-run default: report created/updated/skipped/unmappable with reasons; commit path
  through `artifact_write` layer; `exchange_id` identity mapping so re-import updates) and
  `export_model.py` (read ports + catalog mapping; specialization → 3.x type; domain
  fallback; stable identifiers). Acceptance: fixture model export→import round-trip
  lossless for mapped concepts; E.4 migration cases covered; composition never downgraded
  (explicit test). (deps: F2)
- [ ] **WU-F4 CLI** — `arch-exchange import/export` (`src/infrastructure/cli/arch_exchange.py`
  + script entry): import `--source <path> [--commit] [--repo …]`, export
  `--out <path> [--scope …]`; report printing. Acceptance: CLI tests (tmp repo);
  docs/reference CLI page updated. (deps: F3)

## Phase G — Self-model & docs (D11)

- [ ] **WU-G1 Composition review of self-model aggregations** — query all 155
  `archimate-aggregation` connections via MCP; classify existence-dependent
  (part cannot exist without whole) vs. catalog/grouping aggregation; produce the review
  list FIRST (scratch or model document), then convert approved ones via
  `artifact_edit_connection` in batches (mind the parallel-batch stall pattern — verify
  before retrying). Acceptance: review list recorded; conversions applied; `artifact_verify`
  clean. (deps: C1, C2; backend restarted on post-C code)
- [ ] **WU-G2 ADR + naming in self-model** — author "Adopt ArchiMate 4.0 ontology" ADR via
  MCP (context: standard release; decision: D1 tokens; consequences incl. guidance
  externalization), mark the NEXT-adoption ADR superseded (status edit, content preserved);
  rename draft-era entities (e.g. `REQ@1712870400.KeGCZE` name/slug) via the rename
  machinery; sweep self-model prose mentions. Acceptance: ADR pair linked; verify clean;
  no active self-model artifact named "ArchiMate NEXT" except historical ADR body. (deps:
  A5, G1)
- [ ] **WU-G3 Conformance documentation** — new docs page (e.g.
  `docs/reference/archimate-4-conformance.md` or under 03-modeling) documenting every
  implementation-defined mechanism as the standard requires: viewpoint mechanism (scope,
  enforcement modes, representation kinds), customization (specializations + per-repo
  attribute schemata), guidance import, multiplicity, exchange support + mapping fallbacks,
  explicitly listing deferred capabilities (PLAN §4.4 deferred list). Wording per Q4
  resolution. Acceptance: page linked from docs index + README. (deps: all phases
  substantially complete)
- [ ] **WU-G4 Final sweep + gates** — `rg -i 'archimate[_-]?next'` (active surfaces = 0),
  `rg -i cardinalit` (only diagram-type structural config + historical ledgers), full
  quality gates, frontend gates, `types.generated.ts` current, README status/badges final,
  memory file `project_archimate4_compliance_plan` updated with outcome. Acceptance: all
  green; PLAN §11 checklist walked and ticked. (deps: everything)

---

## Progress notes

(append-only; date — WU — outcome — surprises)
