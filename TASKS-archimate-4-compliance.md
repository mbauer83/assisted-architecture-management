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
   `uv run tools/generate_types.py` after any ontology/type change (pre-commit enforces);
   regenerate `uv run tools/generate_mcp_docs.py` after any MCP tool-description change
   (its `--check` mode gates CI on staleness).
4. All self-model writes via MCP tools only (never manual file edits). MCP tools run against
   the long-running backend — code changes need a backend restart (user does it); note it in
   the ledger entry and continue with non-MCP work if blocked.
5. Tick the WU, append one line under Progress notes (date, WU, outcome, surprises). No
   phase names in code/test content or filenames — use feature names.

## Locked decisions (see PLAN §3 for full text)

- D1 full three-token rename: pkg `archimate_4`, module `archimate-4-0`, alias
  `archimate-4`; fix `permitted_mappings` token inconsistency; no legacy alias.
- D2/D3/D3a guidance = empty in-repo + **repo-local** gitignored caches
  (`<repo>/.arch-repo/guidance-cache/`) + CLI import with `--repo-scope` + provenance
  sidecar (source, sha256, format version, counts). Precedence: module < enterprise cache <
  engagement cache; committed repo declarations never overridden. NO workspace tier —
  customization authority is enterprise + engagement only. Schema:
  module→(entity-type|connection-type)→specialization (connection base keys reserved).
- D4 specializations are **concept-level** (`concept_kind: entity | connection`), one
  unified catalog, enumerated in `specializations.yaml` (module + `.arch-repo/` at both
  tiers: enterprise baseline / engagement superset); attribute schemas attach by reference,
  never define.
- D5 remove dormant `OntologyModule.attribute_profiles` after call-path verification;
  migrate assurance content to scaffolded repo schemata.
- D6 `specializations: [slug]` on entity frontmatter; for connections: a NEW per-connection
  metadata block under each `###` heading in `.outgoing.md` (file frontmatter is shared —
  never per-connection; heading grammar not overloaded further); validated via
  `connection-metadata.{connection-type}` schema convention. Parent type stays; stereotypes
  render on boxes and relationships.
- D7 one `ConceptScope` primitive; diagram-type filters + binding admissibility + viewpoints
  all compile to it; old filter paths deleted, not paralleled.
- D8 `ViewpointApplication` (target kind/id, slug, pinned definition version, enforcement
  override); definitions versioned; stale application = distinct warning; non-destructive;
  enforcement `off|warn|ghost`, no hard block.
- D9 multiplicity rename scoped to ArchiMate relationship ends; REAL repository migration:
  dry-run default, backup/branch recommendation, idempotent report, index rebuild; legacy
  keys readable exactly one release w/ deprecation verifier code (external user repos
  migrate in that window); diagram-type `cardinality_min/max` keeps its name.
- D10 exchange split: readiness (mapping + XSD/legal, HARD GATE incl. Q3) on this plan's
  path; implementation only after gate sign-off AND stable Phase D semantics.
  `src/application/exchange/` use cases + `src/infrastructure/exchange/` adapter; defusedxml
  + XSD validation; CLI-first, no new MCP tools.
- D11 self-model via MCP; new ADR supersedes NEXT ADR (history preserved).
- D13 minimal `ProfileDefinition`; persistence DECIDED: named profiles in
  `.arch-repo/profiles.yaml` (two-tier); existing `attributes.{type}.schema.json` = base
  profiles; inline attributes = anonymous profile; levels required|recommended|optional
  compile to JSON Schema `required` + `x-recommended` (verifier warnings). Deterministic
  merge (base-type profile, then specializations in frontmatter order), property conflict =
  error, defaults last-writer-wins.
- D14 promotion superset rule extended from attribute profiles to specializations +
  specialization-attached schemata + profiles + **viewpoint definitions/versions used by
  promoted views**; engagement-only dependency ⇒ promotion fails loudly; viewpoint match is
  **EXACT-version** (newer enterprise version does NOT satisfy by itself — re-pin only as
  an explicit promotion step); promoted viewpoint definitions validate transitively.
- D15 executable viewpoints (Horizzon-style), tightened: `query` =
  `ExecutableViewpointQueryV1` (`query_schema: 1`; flat conjunctive `all_of`; separate
  entity_filters/connection_filters incl. **profile-attribute predicates** typed against
  the D13 merged effective schemas — operators eq|neq|in|exists|absent (+ lt|lte|gt|gte
  for numeric/date); missing attribute matches only `absent`; explicit
  `include_connections` between-selected|incident|none; explicit repo_scope; expansion
  rules {strategy, roots: selected_entities|execution_anchor, parameters, merge: union};
  `execution_anchor` =
  built-in execution input, NOT the deferred user-defined parameters; optional
  `strategy_version` resolved to current registered version at save and stored — matches
  existing machinery (`StrategySpec.version`, `ViewDerivation.strategy_version`, catalog
  keyed `(name, version)`); execution validates the pinned pair, fails loudly on unknown;
  no nested boolean DSL in v1). Result = `ViewpointExecutionResult` DTO (slug,
  definition_version, query_schema_version, executed_at, repo_scope, model/index revision
  where available, app/strategy-catalog version info for drift diagnosis, SORTED ids,
  counts, warnings, truncated+limits, duration; max results/hops + timeout enforced).
  `presentation` = `PresentationSpec`: representation (`exploration`|`table`|`matrix`) +
  per-representation display capabilities + optional `group_by`
  (type|specialization|group|discrete profile attribute); styling as ABSTRACT tokens in
  core, keyed by type/specialization/group/**discrete attribute values** (continuous
  heat-map scales deferred; renderer vocabulary stays in surface adapters, per
  view_projection opacity contract); unsupported
  options: save/edit = validation ERROR vs current capability registry; runtime WARNING
  only for the drift cases save-time can't cover (legacy definitions, app
  upgrade/downgrade capability drift, cross-surface execution) — never silent. Execution
  ephemeral + read-only, never persisted. Persistent generated diagrams,
  label/tooltip/chart rules, heat maps, saved executions, publishing, user-defined
  parameterization deferred (Q6).
- D16 ONE connection-declaration grammar: `src/domain/connection_declaration.py` (pure
  text↔structure, `ConnectionDeclaration` VO + parse/format; bindings.py precedent — name
  the concept, not the markdown layout); read parser, write parser, and formatter re-based
  as thin mappers, private regexes deleted; lands BEFORE both grammar changes
  (multiplicity rename C3, metadata block D3).
- D17 `arch-repair upgrade`: version-aware repo upgrade owning ALL persisted-format
  migrations. Registered, self-detecting, idempotent steps (D9 multiplicity rename =
  first); scans profiles, customizations (specializations/viewpoints/schemata/guidance
  caches), entity frontmatter, connection declarations, diagram frontmatter; per finding:
  what changes, auto-migratable?, planned rewrite. Findings without a registered step =
  manual-adaptation instructions, never silently skipped. **Coverage invariant**: every
  persisted-format change in this plan registers a step or read-only detector (WU-G3a).
  Compatibility identity = `format_contract_version` + applied step ids in
  `.arch-repo/config.yaml` (software version = metadata only; detection stays
  probe-based). Hexagonal: `EvaluateRepositoryUpgrade`/`ApplyRepositoryUpgrade` use cases
  over ports; pure `detect`, `apply` via write/index ports; CLI/probe/fs/index-rebuild in
  infrastructure. Safety: dry-run default; `--commit` refuses dirty worktree (prints
  touched files; `--allow-dirty` override) AND refuses while a backend serves the
  **target repo** — via a NEW `GET /api/backend-identity` endpoint (canonical
  realpath-normalized served repo roots + software version; REST `/api/stats` does NOT
  carry roots today); fail closed if unconfirmable (incl. pre-endpoint backends);
  unrelated backends don't block. Repo scope: unit = one repo root; `--repo-root`
  repeatable + `--workspace` (engagement+enterprise); per-root reports + aggregate
  summary; stamps per repo. CLI shape: subcommands `upgrade` + `git-repair`; legacy
  no-subcommand invocation = deprecated alias for git-repair for one release. Reports:
  human + `--json` stable contract per repo root incl. step-registry identity
  (available step ids/versions), applied_steps_before/after, unapplied required steps.

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
  `src/infrastructure/workspace/_repo_default_schemata.py`; scaffolded `.arch-repo/.gitignore`
  (extend for `guidance-cache/`).
- Promotion checks: `src/infrastructure/write/artifact_write/promote_schema_check.py`
  (existing attribute-profile superset rule — extend per D14),
  `promote_to_enterprise.py`.
- Connection records: `.outgoing.md` = ONE shared frontmatter + per-connection `###`
  headings (`_CONN_HEADER_RE` carries conn-type, multiplicity, target) + body with
  association markers (`_ASSOC_RE`). The declaration grammar is implemented ≥3× today
  (unify per D16/WU-C3a): read/index `src/application/artifact_parsing.py:238-295`
  (`parse_outgoing_file` → ConnectionRecord); write round-trip
  `src/infrastructure/write/artifact_write/parse_existing.py:248-295`
  (`parse_outgoing_file` → ParsedOutgoing; folds body minus assoc into `description` —
  would swallow a metadata block); formatter
  `src/application/modeling/artifact_write_formatting.py` (`format_outgoing*`); plus
  `connection_edit.py` round-trip assumptions. NO per-connection metadata block exists
  yet; WU-D3 introduces it (fenced YAML under the heading) via the D16 component.
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
- Viewpoint execution surfaces: cluster view `tools/gui/src/ui/views/GraphExploreView.vue` +
  `tools/gui/src/ui/composables/useForceGraph.ts` (`LayoutMode 'cluster'`,
  `applyClusterLayout`) + `tools/gui/src/ui/lib/graphvizElementMapping.ts`; catalog table
  `src/infrastructure/gui/routers/entity_listing.py` + `_entity_filter.py` (+ entities-list
  frontend view); matrix builder `src/application/modeling/matrix_builder.py`.
- Write/CLI/verifier: `src/infrastructure/write/artifact_write/`;
  CLI pattern `src/infrastructure/cli/arch_assurance.py::main` (argparse subparsers) +
  `pyproject.toml [project.scripts]:23-37`; urllib idiom
  `src/infrastructure/bootstrap/get_plantuml.py:40-68`; repair CLI
  `src/infrastructure/cli/arch_repair.py` (currently NO subcommands — flat args
  `--repo-root/--repair-branch/--confirm`, `main` :19; D17 restructures to
  `upgrade`/`git-repair`; tests `tests/cli/test_arch_repair.py`); backend liveness probe
  `src/infrastructure/backend/backend_probe.py` (`probe_backend_url` hits `/api/stats`
  :61 — liveness ONLY; REST `/api/stats` = `s.get_repo().stats()` in
  `gui/routers/entities.py:47` and carries NO repo roots — the `repo_roots` seen in MCP
  stats responses is added by the MCP envelope; D17 therefore ADDS
  `GET /api/backend-identity`); repo policy file `.arch-repo/config.yaml` (D17
  `format_contract_version` + applied-steps target, per repo); verifier
  `src/application/verification/`; dep policy
  `tests/architecture/test_dependency_policy.py` (+ `architecture_baseline.json`).
- Docs: generated MCP tool tables in `docs/03-modeling/interfaces-and-mcp.md` regions,
  produced by `tools/generate_mcp_docs.py` (`--check` staleness gate;
  `src/infrastructure/docs/mcp_docs.py`). Manual pages affected by this plan:
  `docs/03-modeling/{views-and-exploration,diagramming,projects-and-grouping}.md`,
  `docs/05-extensibility/{schemata-and-profiles,ontology-modules}.md`,
  `docs/reference/{cli-and-backend,configuration,git-sync-promotion}.md`.
- Self-model: 155 `archimate-aggregation` connections (stats 2026-07-09); ADR
  `ADR@1780761591._mseZr.adopt-archimate-next-ontology`; entity
  `REQ@1712870400.KeGCZE.archimate-next-model-ontology`.

---

## Phase A — Rename (D1)

- [x] **WU-A1 Rename inventory** — `rg -i 'archimate[_-]?next'` across repo (excl.
  node_modules, historical PLAN-*/TASKS-* ledgers, `.git`). Produce the checklist grouped:
  machine tokens / display strings / docs / skills / self-model content. Confirm no
  `meta_ontology:` values exist in any `groups.yaml`. Acceptance: checklist committed into
  this file under Progress notes (or linked scratch file); zero unknown categories.
- [x] **WU-A2 Package + module rename** — dir → `src/ontologies/archimate_4`; loader class +
  `load_archimate_4_module`; `name = "archimate-4-0"`; alias map →
  `{"archimate-4": "archimate-4-0"}`; imports in `app_bootstrap.py`; c4
  `_projection.py:341` tuple. Acceptance: full test suite green; `find_ontology("archimate-4-0")`
  works; no import of `archimate_next` remains. (deps: A1)
- [x] **WU-A3 Config token reconciliation** — all `archimate/*/config.yaml` `ontology:` →
  `archimate_4` (pkg); ALL `permitted_mappings.sources[].ontology` + c4 bridge `to.module` →
  `archimate-4-0` (module name), including fixing activity/datatype/sequence which
  currently hold the pkg name. Add startup/verifier check: every `permitted_mappings`
  ontology token must resolve via `registry.find_ontology` (fail loud, listing offenders).
  Add a regression test for the check. Acceptance: check passes on the repo; test proves it
  fails on a bad token. (deps: A2)
- [x] **WU-A4 Frontend + generated types** — `domains.ts` key `archimate-4`, moduleName
  `archimate-4-0`, label `ArchiMate 4`; update frontend tests; regenerate
  `types.generated.ts`. Acceptance: vitest + lint + typecheck green. (deps: A2)
- [x] **WU-A5 Docs/skills/README sweep** — display-string rename in `docs/**`,
  `src/ontologies/README.md`, `src/diagram_types/README.md`,
  `.claude/skills/ontology-module-scaffold/SKILL.md`, `skills/reverse-architecture/SKILL.md`,
  README badge (`Model: ArchiMate 4`) + Status section wording (respect open question Q4 —
  keep "no conformance claim" wording until Q4 resolved). Historical ledgers untouched;
  add supersession note to `PLAN-archimate-next-rule-conformance-and-repository-cleanup.md`
  only if it reads as current guidance. Acceptance: WU-A1 checklist fully ticked;
  `rg -i 'archimate[_-]?next'` hits only historical ledgers + self-model content (Phase G).
  (deps: A1–A4)

## Phase B — License compliance: guidance externalization (D2/D3)

- [x] **WU-B1 Guidance domain type** — `src/domain/guidance.py`: `GuidanceKey`
  (module_alias, concept_kind, type_name, specialization?), `GuidanceEntry`,
  `GuidanceOverlay` (frozen; pure merge; empty = no-op). Merge precedence per D2:
  module-inline < enterprise cache < engagement cache; committed declarations never
  overridden. Unit tests (precedence chain, entity + connection specialization keys,
  unknown-key pass-through). Acceptance: dep-policy clean (domain-pure); tests green.
- [x] **WU-B2 Loader threading** — `load_archimate_4_module(guidance=…)` applies overlay to
  `EntityTypeInfo` guidance fields; same optional param for sysml/assurance loaders
  (accepted, unused by default); `app_bootstrap` loads each active repo's
  `.arch-repo/guidance-cache/*.guidance.yaml` in tier order (enterprise, then engagement)
  and passes per-module slices; scaffolded `.arch-repo/.gitignore` gains `guidance-cache/`;
  `config/settings.yaml`: `guidance_default_source: ""` (operational default only — NO
  `guidance_dir`, no workspace tier). Acceptance: overlay applied in a bootstrap test with
  tier precedence asserted; absent caches = current behavior. (deps: B1, A2)
- [x] **WU-B3 Extraction + strip** — `tools/extract_guidance.py` emits the publishable v1
  YAML (PLAN §4.3 schema) from current `entities.yaml` texts to an **out-of-repo** path
  (default: scratch/home, never the workspace); then strip all `create_when`/
  `never_create_when` values in `src/ontologies/archimate_4/entities.yaml` to `""` in the
  same change. Verify the emitted file re-imports losslessly (B4 round-trip test fixture is
  a *small synthetic* file — the real extract stays out of repo and out of tests).
  Acceptance: zero guidance prose in archimate entities.yaml; extractor output validates;
  scaffolded `.arch-repo/.gitignore` covers `guidance-cache/` (workspace-root gitignore
  additionally guards stray `*.guidance.yaml`). (deps: B2)
- [x] **WU-B4 Import CLI** — `src/infrastructure/cli/arch_import_guidance.py` +
  `[project.scripts] arch-import-guidance`. `--source <url|path>` (default from settings),
  `--module <alias>`, `--repo-scope engagement|enterprise` (default engagement),
  `--dry-run`, `--strict`. URL: HTTPS-only default (explicit `--allow-http`), urllib idiom,
  timeout, size cap; `yaml.safe_load`; schema validation; key validation against registry +
  the **target repo's** `SpecializationCatalog` when present (unknown keys listed; skipped
  unless `--strict`); writes `<repo>/.arch-repo/guidance-cache/<alias>.guidance.yaml` PLUS
  provenance sidecar `<alias>.guidance.meta.yaml` (source, sha256, guidance_format,
  timestamp, matched/unmatched counts — D3a); summary printed; prints restart note. Tests:
  happy path (tmp file), repo-scope targeting, unknown keys, bad schema, oversize, http
  rejection, provenance content. Acceptance: import → restart-equivalent rebootstrap in
  test → `get_type_guidance` returns imported text; sidecar validates. (deps: B2, B3)
- [ ] **WU-B5 Empty-state surfacing + license audit** — `artifact_authoring_guidance` +
  REST guidance payload state explicitly when a module's guidance is empty and name the
  import command; GUI wizard shows the hint. **License audit across all shipped
  artifacts**: sample distinctive phrases from the extracted guidance file (B3) and sweep
  docs/**, skills (`.claude/skills/**`, `skills/**`), test fixtures, scaffolding defaults
  (`_repo_default_schemata.py`), diagram-type `own_entity_types` guidance, generated
  payloads (`types.generated.ts`), README + media captions. Record method + conclusion; any
  hit is stripped or rewritten in original words. Document the hosting location, terms, and
  expected hash/version of the published guidance file in docs (per Q2 resolution).
  Acceptance: empty-state text asserted in MCP description test; audit method + zero-hit
  conclusion in Progress notes; hosting provenance documented. (deps: B4)

## Phase C — Core semantics: composition, Appendix B, multiplicity

- [x] **WU-C1 Composition semantics verification** — against final §5.1.2: composition
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
- [ ] **WU-C3a Unified connection-declaration grammar (D16)** —
  `src/domain/connection_declaration.py`: `ConnectionDeclaration` value object (conn_type,
  src/tgt multiplicity, target, metadata mapping, associated entity ids, description) +
  `parse_connection_declarations(text)` / `format_connection_declaration(decl)` (pure, no
  I/O). Re-base as thin mappers and DELETE the private regexes in: read/index
  `artifact_parsing.py::parse_outgoing_file` (→ ConnectionRecord), write round-trip
  `parse_existing.py::parse_outgoing_file` / `_parse_connection_sections` (→
  ParsedOutgoing), formatter `artifact_write_formatting.py::format_outgoing*`; verify
  `connection_edit.py` round-trips through the shared component. Behavior-preserving:
  shared round-trip property test (heading + assoc + description; metadata block added in
  D3) + existing read/write suites green; both repos re-verify clean. Acceptance: exactly
  one grammar implementation (`rg` proves no duplicate header regex); property test green;
  dep-policy clean. (deps: A2)
- [ ] **WU-C3 Multiplicity rename (code, with formal legacy window)** —
  `ConnectionRecord.src_multiplicity/tgt_multiplicity`, `format_multiplicity_label`,
  `include_multiplicity` annotation, parser/writer, GUI labels/fields, REST/MCP payload
  fields, regenerate `types.generated.ts`, docs. Legacy-key read support is a **formal,
  tested compatibility path for exactly one release** (D9): parser normalizes
  `src_cardinality`/`tgt_cardinality` + `include_cardinality` on read, verifier emits a
  distinct deprecation code, release notes name the migration command and removal release.
  NOT an informal TODO. The heading-grammar change happens once, in the D16 component.
  Acceptance: suite green with both key forms; deprecation code fires; docs/release-note
  draft included. (deps: A2, C3a)
- [ ] **WU-C4a `arch-repair upgrade` framework (D17)** — hexagonal split: **application**
  — `EvaluateRepositoryUpgrade` / `ApplyRepositoryUpgrade` use cases over ports + the
  step registry; each `UpgradeStep` declares id, description, scanned surface (profiles /
  customizations / entity frontmatter / connection declarations / diagram frontmatter), a
  **pure** `detect(repo_view)` returning findings (finding id, location, what must
  change, severity, auto-migratable flag, planned rewrite or manual instructions), and
  `apply` through the write/index ports (idempotent). **Infrastructure** — CLI
  restructure of `arch_repair.py` into subcommands: `upgrade` (new) + `git-repair`
  (existing flow moved, behavior unchanged), with the legacy no-subcommand invocation
  kept as a **deprecated alias for git-repair for one release** (deprecation notice;
  `tests/cli/test_arch_repair.py` updated for all three shapes); backend probing,
  filesystem adapters, index rebuild. **Backend-identity endpoint (explicit sub-task)**:
  add `GET /api/backend-identity` returning canonical **realpath-normalized** served repo
  roots (engagement + enterprise mounts) + software version — REST `/api/stats` does not
  carry roots today; the guard consumes this endpoint. Repo scope: `--repo-root <path>`
  (repeatable) + `--workspace <path>` (resolves engagement + enterprise roots); each repo
  root is evaluated/stamped independently; per-root reports + one aggregate summary.
  Command behavior: dry-run/report default (always allowed, backend running or not);
  `--commit` (a) refuses a **dirty git worktree**, printing the files it would touch,
  `--allow-dirty` to override; (b) refuses when a backend serves the **target repo** —
  probe backend-identity, compare realpath-normalized roots against the target; **fail
  closed** when a backend responds but served roots can't be confirmed (incl. older
  backends without the endpoint); do NOT block on backends serving other repos; (c)
  prints backup/branch recommendation. Report: human output + `--json` stable contract
  per repo root (software version, format_contract_version, **step-registry identity:
  available step ids/versions**, **applied_steps_before / applied_steps_after**,
  unapplied required steps, per finding: step id, finding id, location, severity,
  auto_migratable, rewrite summary / manual instruction, outcome
  applied|skipped|error). On success: record **`format_contract_version` + applied step
  ids** in each repo's `.arch-repo/config.yaml` (software version as metadata only;
  detection stays probe-based — re-run safe). Acceptance: framework tests with a fixture
  step (detect/apply/idempotence); endpoint test incl. realpath normalization + combined
  engagement/enterprise roots; guard tests — dirty-tree refusal + allow-dirty,
  target-repo backend refusal, fail-closed on unconfirmable roots AND on
  endpoint-missing backends, unrelated backend does not block; multi-repo run
  (workspace) stamps both repos and aggregates the report; legacy alias test; `--json`
  schema test incl. registry/before-after fields; stamp written + re-run = clean;
  docs/reference CLI page section. (deps: A2)
- [ ] **WU-C4 Multiplicity migration step + junction rule** — implement the D9 rename as
  the **first registered D17 upgrade step**: detects legacy
  `src_cardinality`/`tgt_cardinality` keys + `include_cardinality` annotations, rewrites
  through the standard write/index path with index rebuild; works on any user repository,
  not only this workspace. Run `arch-repair upgrade --commit` on both workspace repos
  (backend stopped). Add junction rule: warn when multiplicity set on a junction-attached
  connection end. Legacy-key *removal* happens next release per D9 (record a dated
  follow-up note in Progress notes — the removal is NOT part of this plan's ticks).
  Acceptance: both workspace repos migrated (0 legacy keys); dry-run/commit/idempotency +
  junction-rule tests; step listed in the upgrade report; migration documented in
  docs/reference CLI page. (deps: C3, C4a)

## Phase D — Specializations & profiles (D4/D5/D6/D13/D14)

- [x] **WU-D1 SpecializationCatalog (domain, concept-level)** —
  `src/domain/specializations.py`: `SpecializationInfo` (slug, name,
  `concept_kind: entity | connection`, parent_type, module_alias, description, notation
  icon/color, restrict_relationships (entity) / restrict_endpoints (connection),
  profile ref or inline attributes (D13), guidance fields), `SpecializationCatalog`
  (uniqueness per (module, concept_kind, parent_type, slug); lookup by concept kind + type;
  restriction-narrowing validation hook). Parser for the PLAN §4.2 YAML shape
  (`specializations: {entity: …, connection: …}`, pure function). Unit tests for both
  kinds. Acceptance: dep-policy clean; tests green.
- [x] **WU-D2 Loading + informative library (two-tier)** — module-level
  `specializations.yaml` loading in the archimate_4 loader; ship the §14.2.1 informative
  library: entity specializations (role/collaboration/service/process/function/event
  families + contract, constraint, gap, representation-like) AND connection
  specializations (`money-flow` under `archimate-flow`,
  `responsibility-assignment`/`behavior-assignment` under `archimate-assignment`); names +
  parents only, guidance empty. Repo-level `.arch-repo/specializations.yaml` loading from
  **enterprise and engagement** repos (bootstrap layer, tier-aware) merged into the
  catalog; guidance overlay (B1) applies to specialization entries of both kinds.
  Acceptance: catalog contains library + both-tier repo entries in a fixture; duplicate
  slug rejected loudly; engagement may extend enterprise (superset direction asserted).
  (deps: D1, B2)
- [ ] **WU-D3 Persistence + verifier (both kinds)** — entity frontmatter
  `specializations: [slug]`; for connections: introduce the **per-connection metadata
  block** — a fenced YAML block immediately under each `###` connection heading in
  `.outgoing.md` (D6; file frontmatter is shared across connections and must NOT carry
  per-connection data; heading grammar not extended) — carrying `specializations:` and
  open to future per-connection metadata. The block is implemented ONCE in the D16
  `connection_declaration` component (parse + format; round-trip property test extended);
  both parser consumers, the formatter, `connection_edit.py` round-trips, index, and
  rename machinery pick it up through the shared component — explicitly verify the write
  path does not fold the block into `description` on edit. Parse/write round-trip for
  both kinds. Verifier rules: unknown slug (error), concept-kind or parent-type mismatch
  (error), `restrict_relationships` / `restrict_endpoints` violation (warning),
  restriction-broadening in declaration (error at load). Schemas: scaffolded
  `frontmatter.entity.schema.json` gains the optional property; connection block values
  validate via the `connection-metadata.{connection-type}.schema.json` convention
  (extended with optional `specializations`) — NOT `frontmatter.outgoing.schema.json`.
  Acceptance: rule tests incl. round-trips for entity and connection; a two-connection
  outgoing file carries different specializations per connection; an edit of one
  connection preserves the sibling's metadata block byte-exact. (deps: D2, C3a)
- [ ] **WU-D4 ProfileDefinition + deterministic merge (D13)** — minimal domain
  `ProfileDefinition` (slug, name, applicable concept types, typed attributes with
  optional defaults and `required|recommended|optional` levels). Persistence per D13
  (decided): named profiles in `.arch-repo/profiles.yaml` (two-tier loading like
  specializations); existing `attributes.{artifact_type}.schema.json` files recognized as
  base-type profiles unchanged; compilation emits JSON Schema `required` +
  `x-recommended: [names]` (verifier consumes for warnings); specialization `profile:`
  refs resolved against the catalog; inline `attributes:` compile to an anonymous
  profile. Effective-schema computation in `artifact_schema.py`:
  base-type profile ⊕ per-specialization profiles in frontmatter order (also the
  `attributes.{artifact_type}.{slug}.schema.json` attachment convention); property
  conflict (same name, incompatible schema) = load/verify **error**; defaults
  last-writer-wins; value violation = error, missing recommended = warning. Orphan
  attachment schema (no declared specialization) → verifier warning. Acceptance: merge
  determinism tests (order, conflict, defaults), orphan detection test, multi-
  specialization entity validates against merged schema. (deps: D3)
- [ ] **WU-D5 Rendering (boxes and relationships)** — guillemet stereotype
  `«slug-display»` (multiple: comma-joined) in PUML output for entities AND for
  connections carrying specializations (compose with the existing connection-type
  `show_stereotype` heuristic — specialization stereotype renders even where the type
  stereotype is suppressed); notation icon/color (entity) and line-style/label marker
  (connection) when declared, parent-notation fallback otherwise. Acceptance: renderer
  snapshot tests for entity labeled + icon + fallback and connection stereotype cases.
  (deps: D3)
- [ ] **WU-D6 GUI + guidance exposure** — specialization picker on entity create/edit and
  on the connection editing surface (options from catalog for the chosen type + kind),
  display in entity detail/list and connection listings; `artifact_authoring_guidance`
  includes per-type specialization enumeration + guidance for both kinds; regenerate
  `types.generated.ts`. Acceptance: vitest for picker helpers; guidance payload test
  covers entity + connection specializations. (deps: D3)
- [ ] **WU-D7 Dormant profile surface removal (D5)** — call-path verification that
  `OntologyModule.attribute_profiles` has no live consumer (registry, routers, MCP,
  verifier, frontend; record method + result). If dead: remove protocol field + three class
  attributes + assertion-only tests; migrate assurance profile content into
  `_repo_default_schemata.py` as `attributes.{hazard,risk,unsafe-control-action,
  assurance-constraint,control-structure-node}.schema.json` scaffolding defaults; add a
  scaffolding test asserting new repos receive them. If a consumer is found: STOP, record
  in Progress notes, escalate to review. Acceptance: protocol slimmed, assurance schemas
  scaffolded, suite green. (deps: D4)
- [ ] **WU-D8 Promotion superset checks (D14)** — extend the existing attribute-profile
  superset rule (`promote_schema_check.py`) to specializations and specialization-attached
  schemata/profiles: promotion fails, loudly listing engagement-only definitions, when a
  promoted entity or connection depends on a specialization/profile not present in the
  enterprise repo and not being promoted alongside. Cover connection specializations via
  promoted connection records. Acceptance: promotion tests — engagement-only dependency
  blocked with actionable message; definition-promoted-alongside path succeeds; baseline
  path (no specializations) unchanged. (deps: D3, D4)

## Phase E — Viewpoints (D7/D8)

- [x] **WU-E1 ConceptScope (domain)** — `src/domain/concept_scope.py`: frozen scope
  (explicit type sets + class/hierarchy predicates + connection types + endpoint rules),
  `admits_entity_type/admits_connection_type/admits_connection`, intersection `&`.
  Characterization test capturing current `effective_entity_types` +
  `accepts_connection_type` behavior per registered diagram-type module (pre-refactor
  snapshot for E2). Unit tests. Acceptance: dep-policy clean; snapshot recorded.
- [x] **WU-E2 Re-base diagram-type filters (replacement)** — reimplement
  `_config_type.py::_build_entity_filter` + `DiagramTypeBase.accepts_entity_type/
  accepts_connection_type/effective_*` over a module-derived `ConceptScope`; binding-target
  admissibility (`permitted_mappings` source eligibility) evaluates through the same
  primitives (correspondence semantics in `allowed_bindings.py` unchanged). DELETE the
  superseded ad-hoc filter code (no parallel path). Acceptance: E1 characterization
  snapshot unchanged; existing diagram-type suites green; dep-policy baseline not grown.
  (deps: E1)
- [ ] **WU-E3 ViewpointDefinition + ViewpointApplication (domain) + persistence** —
  `src/domain/viewpoints.py` (PLAN §4.4 shape): `ViewpointDefinition` with `version`
  (integer, bumped on semantic change), purpose/content enums, stakeholders, concerns,
  scope, representation_types, derivation_defaults; `ViewpointApplication` (target_kind
  `diagram|matrix` extensible, target_id, viewpoint_slug, pinned_version, optional
  enforcement_override + derivation_params). YAML parsing; module `viewpoints.yaml` (small
  starter library — e.g. motivation, application-structure, layered, technology-usage) +
  `.arch-repo/viewpoints.yaml` from **enterprise and engagement** repos (two-tier, like
  specializations) loading into a `ViewpointCatalog` (slug-unique); scope may reference
  specializations (member-of predicate) — catalog validation. Definitions may carry the
  D15 `query` block (`ExecutableViewpointQueryV1`: `query_schema: 1`, flat `all_of`,
  separate entity/connection filters, `include_connections` policy, `repo_scope`,
  expansion rules with `roots: selected_entities|execution_anchor` + `merge: union`) and
  `presentation` block (`PresentationSpec`: representation + per-representation display
  options + ABSTRACT style tokens). Save-time validation: unknown filter values, unknown
  strategy ids, unknown styling keys, unknown representations, and display options
  unsupported by the chosen representation are all rejected loudly (against the current
  capability registry — D15 drift rule); expansion rules resolve `strategy_version` to
  the current registered `(name, version)` and store it explicitly; references to
  specializations/profiles validate against the catalogs; **attribute references in
  filters, `group_by`, and styling rules validate against the D13 merged effective
  schemas** (unknown attribute = error; operator/type mismatch, e.g. `lt` on a string
  attribute = error). Acceptance: catalog fixture tests incl. query+presentation shapes;
  duplicate/unknown-type declarations, invalid query schema, unknown strategy,
  unsupported-display, unknown-attribute, and operator/type-mismatch cases rejected;
  strategy_version resolution asserted; version field round-trips. (deps: E1, D2, D4)
- [ ] **WU-E4 Application wiring + verifier** — diagram/matrix frontmatter persists the
  `ViewpointApplication` (`viewpoint: {slug, version, …}`); effective authoring scope =
  diagram-type scope ∩ applied viewpoint scope; verifier contributions (distinct codes,
  never errors except unknown slug): out-of-scope element/connection ⇒ warning (distinct
  from metamodel violations); **stale application** (pinned_version < definition version)
  ⇒ warning; unknown viewpoint slug ⇒ error; enforcement setting `off|warn|ghost` in
  `config/settings.yaml` (application-level override honored). Scaffolded
  `frontmatter.diagram.schema.json` gains the optional property. Acceptance: warning +
  stale-application tests; `off` silences; unknown slug errors. (deps: E2, E3)
- [ ] **WU-E5-UX Viewpoint UX design spike (checkpoint)** — wireframes/flows for the
  whole viewpoint UX per the PLAN §4.4 UX commitments: guided query builder (structured
  filter rows, catalog-fed pickers, typed operator/value inputs, debounced live
  result-count preview), progressive disclosure (simple case immediate; attribute
  predicates/expansion rules/metadata behind advanced sections), capability-driven output
  customization with live legend preview, integration flows (exploration picker,
  entities-list "save current filters as viewpoint", diagram-editor selector, active
  viewpoint chip with one-click clear), explainability ("why excluded/ghosted" hints,
  diagnostics as primary UI). Use the frontend-design skill for the design pass.
  **Stop condition**: user review of wireframes/flows before E5a/E5b/E8/E9 GUI
  implementation. Acceptance: reviewed design artifacts linked in Progress notes. (deps:
  E3; informs all Phase E GUI WUs)
- [ ] **WU-E5a GUI: selection + filtering** — viewpoint selector on diagram create/edit
  (default: none = unrestricted); palette + entity-picker filtering via narrowed scope
  (extend `ui-config`/`/api/ontology` with optional `viewpoint` param); ghosting (not
  removal) of out-of-scope existing content per enforcement setting — ghosted content
  carries a "why excluded" hint (which scope/filter); active viewpoint shown as a
  dismissible chip with one-click clear; stale-application indicator with an explicit
  "re-pin to current version" action (after user review — never automatic). Implements
  the E5-UX design. Acceptance: vitest helper tests; route-walk smoke passes; manual
  screenshot in Progress notes. (deps: E4, E5-UX)
- [ ] **WU-E5b GUI: viewpoints management view (CRUD + guided builder)** —
  list/create/edit repo definitions (engagement repo; enterprise + module ones read-only
  in the engagement context) through the **guided query builder from the E5-UX design**:
  structured filter rows with catalog-fed pickers (groups, types, specializations,
  profile attributes from effective schemas), typed operator/value inputs (enum values as
  choices), progressive disclosure of advanced sections, capability-driven presentation
  form with live legend preview — no raw YAML editing surface; **"save current filters as
  viewpoint"** entry point on the entities-list view; version bump on semantic edit with
  a hint listing views pinned to older versions. Acceptance: vitest helper tests
  (builder ↔ query serialization round-trip); CRUD round-trip against the backend in a
  test; save-filters-as-viewpoint flow covered; screenshot in Progress notes. (deps:
  E5a, E5-UX)
- [ ] **WU-E5c GUI: live preview + test-run before save** — debounced live result-count
  preview while building filters (tight-limit E7 executions); full test-run from the
  editor showing counts/warnings; save-time validation errors surfaced inline on the
  offending builder row before persisting. Acceptance: vitest helper tests; preview
  debounce + test-run paths covered incl. a failing-validation case mapped to its row.
  (deps: E5b, E7)
- [ ] **WU-E6 MCP/guidance exposure** — viewpoint enumeration + per-viewpoint scope summary
  in `artifact_authoring_guidance`; `artifact_create_diagram`/`artifact_edit_diagram`
  accept the application frontmatter (no new tools); tool-description test updated.
  Acceptance: guidance payload test; description test green. (deps: E4)
- [ ] **WU-E7 Viewpoint execution use case (D15)** — explicit hexagonal split inside one
  WU: **domain** — query/presentation/result value objects (incl.
  `ViewpointExecutionResult` fields per D15) and abstract style-token resolution;
  **application** — `EvaluateViewpoint` over the read ports + derivation-strategy catalog:
  conjunctive filter evaluation (entity_filters, connection_filters incl. typed
  profile-attribute predicates per D15 semantics — missing attribute matches only
  `absent`; attribute values sourced through the read ports from parsed entity properties
  / connection metadata, flagging in the WU if the index must be extended to carry them),
  `group_by` resolution emitting per-node group keys in the DTO,
  `include_connections` policy, repo_scope), expansion rules with
  `roots: selected_entities|execution_anchor` and union merge — pinned
  `(strategy, strategy_version)` validated against the catalog, failing loudly when
  unknown (never substituting) — enforced max result size / max hops / timeout with clean
  cancellation, SORTED ids + counts + warnings + truncated + duration +
  app/strategy-catalog version info in the DTO; **infrastructure** — read-only REST
  endpoint that calls the use case only (no write-queue involvement) + structured per-run
  log summary (same fields as the DTO). Contract tests, not just happy paths: per-filter
  + combined-filter, **attribute-predicate per operator incl. missing-attribute and
  type-coercion cases**, **group_by key resolution**, expansion-rule, styling/token
  resolution incl. attribute-keyed rules, **stable ordering**,
  **limit/truncation**, **timeout**, invalid query schema, unknown strategy, **unknown
  pinned strategy_version**, enterprise/engagement definition precedence, runtime
  capability-drift warning (legacy definition against a changed registry), and a
  **negative test proving no write-queue/artifact-file access**. Acceptance: all listed
  tests green; endpoint shape stable; dep-policy clean. (deps: E3)
- [ ] **WU-E8 Execution GUI: cluster view (D15)** — Execute action in the viewpoints
  management view + viewpoint picker on the graph-exploration page (page supplies
  `execution_anchor` where the definition's expansion rule requires it); declare the
  exploration surface's display capabilities (node shape/icon/color, cluster grouping —
  clusters follow the result's `group_by` keys when set) and map abstract style tokens,
  incl. attribute-keyed ones, onto them via the existing cluster layout
  (`GraphExploreView.vue` / `useForceGraph.ts::applyClusterLayout`). **Execution diagnostics UI**: result counts,
  truncation/omission warnings, active-filter summary, unsupported-display warnings,
  explained empty state (which filter/scope produced it), explicit "re-run against
  current model" action; clear ephemeral/read-only presentation; styling legend visible
  during execution. Implements the E5-UX design. Acceptance: vitest helper tests incl.
  diagnostics states (empty, truncated, unsupported-option warning); route-walk smoke
  passes; screenshot in Progress notes. (deps: E7, E5b, E5-UX)
- [ ] **WU-E9 Execution GUI: table + matrix (D15)** — `table`: drive the existing
  entities-list catalog view from the WU-E7 selection (same filters, viewpoint-labelled,
  read-only; capabilities: columns/badges/sort, row grouping by the result's `group_by`
  keys — incl. profile-attribute columns for attributes named in the definition);
  `matrix`: ephemeral matrix rendering of the selected entity/connection set via the
  existing matrix builder (capabilities: row/column grouping incl. by `group_by` keys,
  cell emphasis; no diagram artifact created). Same diagnostics UI
  as E8; implements the E5-UX design. Per-representation unsupported-display-option tests
  (an exploration-only styling rule executed as table ⇒ warning, not silent drop).
  Acceptance: vitest helper tests; both representations render a fixture viewpoint with
  diagnostics; unsupported-option tests; no write path touched (asserted). (deps: E7,
  E5-UX)
- [ ] **WU-E10 Promotion checks for viewpoint dependencies (D14)** — extend the promotion
  superset machinery (WU-D8 foundation): a promoted diagram/matrix whose
  `ViewpointApplication` references an engagement-only viewpoint definition, or a version
  the enterprise repo lacks, fails promotion unless the definition **at exactly the pinned
  version** is promoted alongside — a newer enterprise version does NOT satisfy the check
  by itself (D8: never silently reinterpret); the only alternative is an **explicit
  re-pin during promotion** (a reviewed choice surfaced in the promotion flow, recorded on
  the promoted application). Promoted viewpoint definitions validate transitively
  (referenced specializations, profiles, query schema version, pinned strategy versions,
  presentation capabilities) against the enterprise catalogs. Acceptance: promotion
  tests — engagement-only viewpoint blocked with actionable message; promoted-alongside
  path succeeds incl. transitive specialization dependency; **newer-version-present case
  still blocks without explicit re-pin**; explicit re-pin path covered. (deps: E4, D8)

## Phase F — Model Exchange (C19C v3.1) (D10)

**WU-F1 is a HARD GATE**: no F2+ code until F1's sign-off is recorded in Progress notes AND
Phase D is substantially complete (specialization/profile semantics stable — the mapping
depends on them).

- [ ] **WU-F1 Exchange readiness: mapping + XSD/legal review (gate)** —
  `exchange_mapping.yaml` draft: bidirectional element/relationship mapping incl. Appendix
  E.4 rows (3.x type → archimate-4 type + specialization slug — entity AND connection
  specializations, e.g. `money-flow`, assignment variants; invalid-relationship →
  association; composition preserved both ways; multiplicity mapping; profile/attribute ↔
  exchange `properties`/`propertyDefinitions` mapping). Documented lossy-case policy
  (every unmappable case + chosen fallback). Dev-time XSD fetch script (gitignored target,
  pinned checksum) — resolves open question Q3. If Q4's conformance wording requires
  exchange support, flag release-blocking status here. **Stop condition**: reviewer
  sign-off on mapping + lossy policy + Q3 recorded in Progress notes before any F2+ work.
  Acceptance: mapping table review-complete; every §14.2.1 library slug referenced by the
  forward direction or explicitly marked no-3.x-equivalent; sign-off recorded. (deps: D2,
  C1; blocked-by: Q3)
- [ ] **WU-F2 Codec adapter** *(gated by F1 sign-off)* —
  `src/infrastructure/exchange/archimate_model_exchange/`: defusedxml-based reader (XSD
  validation, size cap) + writer; application-defined ports
  `ExchangeDocumentReader/Writer` in `src/application/exchange/ports.py`. Round-trip unit
  tests on synthetic documents. Acceptance: dep-policy clean (application imports no
  infra); malformed/oversize/XXE fixtures rejected. (deps: F1)
- [ ] **WU-F3a Import use case** *(gated)* — `src/application/exchange/import_model.py`:
  dry-run default (report created/updated/skipped/unmappable with reasons); commit path
  through `artifact_write` layer; `exchange_id` identity mapping so re-import updates
  instead of duplicating; E.4 migration application incl. connection specializations.
  Acceptance: E.4 migration cases covered; composition never downgraded (explicit test);
  re-import idempotence test. (deps: F2, D3)
- [ ] **WU-F3b Export use case** *(gated)* — `src/application/exchange/export_model.py`:
  read ports + catalog mapping; entity/connection specialization → 3.x concrete type;
  domain (`hierarchy[0]`) fallback; stable identifiers derived from artifact IDs;
  multiplicity + properties export. Acceptance: fixture model export→import round-trip
  lossless for mapped concepts; unmappable cases reported per lossy policy, never silent.
  (deps: F3a)
- [ ] **WU-F4 CLI** *(gated)* — `arch-exchange import/export`
  (`src/infrastructure/cli/arch_exchange.py` + script entry): import `--source <path>
  [--commit] [--repo …]`, export `--out <path> [--scope …]`; report printing. Acceptance:
  CLI tests (tmp repo); docs/reference CLI page updated. (deps: F3a, F3b)

## Phase G — Self-model & docs (D11)

- [ ] **WU-G1a Composition classification spike (checkpoint)** — draft the classification
  rubric (existence-dependent: part cannot exist without whole ⇒ composition; catalog/
  grouping/shared membership ⇒ stays aggregation); apply it to a ~20-connection sample
  drawn across groups (platform-core, assurance, motivation-narrative, …) via MCP queries;
  record sample verdicts + rubric. **Stop condition**: user review of rubric + sample
  before G1b. Acceptance: rubric + reviewed sample recorded in Progress notes (or a scratch
  review doc). (deps: C1, C2; backend restarted on post-C code)
- [ ] **WU-G1b Composition batch conversion** — apply the approved rubric to all 155
  aggregations; produce the full review list FIRST, then convert approved ones via
  `artifact_edit_connection` in small batches with `artifact_verify` between batches (mind
  the parallel-batch stall pattern — verify before retrying). Acceptance: full list
  recorded; conversions applied; `artifact_verify` clean. (deps: G1a approved)
- [ ] **WU-G2 ADR + naming in self-model** — author "Adopt ArchiMate 4.0 ontology" ADR via
  MCP (context: standard release; decision: D1 tokens; consequences incl. guidance
  externalization), mark the NEXT-adoption ADR superseded (status edit, content preserved);
  rename draft-era entities (e.g. `REQ@1712870400.KeGCZE` name/slug) via the rename
  machinery; sweep self-model prose mentions. Acceptance: ADR pair linked; verify clean;
  no active self-model artifact named "ArchiMate NEXT" except historical ADR body. (deps:
  A5, G1b)
- [ ] **WU-G3 Conformance documentation (normative summary — ownership split with G3b)**
  — new docs page (e.g. `docs/reference/archimate-4-conformance.md` or under 03-modeling)
  documenting every implementation-defined mechanism as the standard requires: viewpoint
  mechanism (scope, enforcement modes, representation kinds), customization
  (specializations + per-repo attribute schemata), guidance import, multiplicity,
  exchange support + mapping fallbacks, explicitly listing deferred capabilities (PLAN
  §4.4 deferred list). Wording per Q4 resolution. **Ownership rule**: G3 is the
  *normative conformance summary* — what is supported and in which implementation-defined
  manner, concise, spec-facing; it does NOT explain operation. G3b owns the *user-facing
  operation docs* (how to use the features). Each mechanism entry in G3 links to its G3b
  page and vice versa — no duplicated explanations to drift. Acceptance: page linked from
  docs index + README; cross-links present both ways; no operational how-to content
  duplicated from G3b pages. (deps: all phases substantially complete)
- [ ] **WU-G2a Self-model alignment with this plan (investigate → propose → review →
  apply)** — bring ENG-ARCH-REPO up to date with the capabilities this plan adds, at the
  model's established granularity. All via MCP; strictly follow the modelling discipline:
  **read `artifact_authoring_guidance` first**, read-before-propose on every touched
  artifact, prefer **descriptions > connections > entities** (enrich an existing artifact
  before creating a new one; no argumentative/bundled motivation entities), coverage
  check at the end.
  *Step 1 — inventory (read-only)*: survey the affected groups (platform-core,
  motivation-narrative, diagram-authoring, promotion-and-tiering, meta-ontology diagrams)
  and produce a written change-set proposal FIRST. Grounded starting points (verified
  2026-07-09, re-verify ids): **description updates** —
  `DOB@1777293139.UjyXG3.architecture-ontology-configuration` (specializations/
  viewpoints/profiles declaration files, guidance-empty shipping),
  `DOB@1780656431.T8nsTi.architecture-modelling-guidance` (overlay precedence, repo-local
  import, provenance), `REQ@1712870400.6ZR3nk.configurable-model-attribute-schemata` +
  `REQ@1712870400.pSvaRl.configurable-frontmatter-schemata` (ProfileDefinition, merged
  effective schemas), `FNC@1712870400.B_F-Sq.attribute-schema-validation` (merge
  semantics), `APP@1712870400.yNhgdh.module-catalog` (SpecializationCatalog/
  ViewpointCatalog aggregation), `APP@1712870400.kjC6ex.cli-tool` +
  `AIF@1712870400.KxvY-B.cli-interface` (arch-import-guidance, arch-exchange,
  arch-repair upgrade/git-repair). **Candidate new entities** (evaluate each against
  guidance + granularity — reject if a description on an existing artifact suffices):
  requirements for viewpoint mechanism, concept customization (specialization+profile),
  license-separated guidance import, model exchange, repository format upgrade;
  application-components/functions for the viewpoint engine/evaluation, the exchange
  adapter, and the **repository-upgrade system (D17)** — evaluate/apply upgrade
  functions, the upgrade-step registry — with data-objects for viewpoint definition,
  specialization declaration, profile definition, guidance cache, exchange document,
  **format-contract stamp (`.arch-repo/config.yaml` identity), and the upgrade report**
  (each still subject to the enrich-first verdict — reject with reasons where a
  description on CLI Tool / existing artifacts suffices). **Connections**: realizations from new/
  updated components to the new requirements; access from functions to the new
  data-objects; serving where the GUI/MCP surfaces consume them. **Diagrams**: add new
  requirements to `MAT@1777452513.h0iI-_` (Format, Discovery & Extensibility) and/or
  `MAT@1777452513.W34qBm` (Authoring, Verification & Governance); update the promotion
  activity diagram action `ACT@1781338474.NTuMXo#action/a3` ("Check engagement schemata ⊇
  enterprise" → specializations/profiles/viewpoints per D14); evaluate ONE new
  application-view diagram for the viewpoint/customization subsystem (only if the
  existing views can't absorb it). **Documents**: covered by WU-G2's ADR; check whether
  the coding-guidelines/standard docs reference guidance authoring.
  *Step 2 — user review of the change-set (stop condition).*
  *Step 3 — apply* in batches via MCP (create entities before connections; mind the
  parallel-batch stall pattern), `artifact_verify` between batches.
  Acceptance: proposal recorded (scratch doc or Progress notes) with per-item
  keep/enrich/create verdicts incl. rejected candidates + why; user sign-off; applied;
  `artifact_verify` clean; coverage check confirms every D1–D17 capability is either
  modeled or explicitly assessed as below modeling granularity. (deps: G2; after Phases
  B–F substantially complete so the model reflects what was actually built)
- [ ] **WU-G3a Upgrade-coverage closure (D17 invariant)** — inventory every
  persisted-format change this plan introduced (multiplicity keys, per-connection
  metadata block, entity `specializations:`, diagram `viewpoint:` applications,
  `.arch-repo/{specializations,profiles,viewpoints}.yaml`, guidance caches + provenance
  sidecars, `exchange_id`, format stamps) and confirm each has a registered D17 upgrade
  step (where auto-migratable) or read-only detector (where new-optional or
  manual-only — e.g. an unknown-key/schema-drift detector for the new `.arch-repo` files).
  Add the missing ones. Add a **coverage test** that fails when a format surface named in
  the plan has neither step nor detector registered. Acceptance: inventory recorded in
  Progress notes; coverage test green; `arch-repair upgrade` on a pre-plan fixture repo
  reports every applicable finding. (deps: C4a+C4, B3+B5 [guidance caches/provenance],
  D3+D4 [metadata block, specializations/profiles files], E3+E4 [viewpoints files +
  applications], F4-if-implemented [exchange_id], and the config-stamp implementation —
  i.e. after ALL format surfaces exist; do not run early)
- [ ] **WU-G3b Documentation regeneration + feature docs** — two parts.
  *Regenerated*: run `tools/generate_mcp_docs.py` after all tool-description changes have
  landed (guidance empty-state B5, viewpoint/specialization guidance exposure D6/E6) and
  commit the refreshed tables; `--check` green in CI.
  *Authored*: (a) **new** user-facing docs for viewpoints — concept, definitions
  (two-tier + module library), applications + pinned versions, enforcement modes,
  executable viewpoints (query builder, representations, diagnostics, limits) — placed in
  `docs/03-modeling/views-and-exploration.md` or a sibling page per docs-tree fit; (b)
  **new** docs for specializations + profiles — concept-level specialization, declaration
  files, ProfileDefinition + merge semantics, notation/stereotypes, promotion superset
  rules — extending `docs/05-extensibility/schemata-and-profiles.md` +
  `ontology-modules.md`; (c) **updates** to the affected existing pages:
  `diagramming.md` (viewpoint on diagrams, specialization rendering, multiplicity term),
  `projects-and-grouping.md` (if group-scoped viewpoint queries touch it),
  `reference/cli-and-backend.md` (arch-import-guidance, arch-exchange, arch-repair
  upgrade/git-repair + deprecation), `configuration.md` (guidance_default_source,
  enforcement setting), `git-sync-promotion.md` (D14 superset checks incl. viewpoints).
  Ground every page in the real GUI/CLI behavior (docs-grounding discipline; screenshots
  where the docs pattern uses them). **Ownership rule (mirror of G3)**: G3b owns
  operational how-to content; conformance statements live only in the G3 page —
  cross-link instead of restating. Acceptance: `generate_mcp_docs.py --check` passes;
  new + updated pages linked from `docs/index.md`/section indexes and cross-linked with
  the G3 conformance page; no page documents pre-plan behavior (sweep with the WU-A1/G4
  term lists); docs build/link check green if configured. (deps: B5, C3, D6, E6, F4 as
  applicable; before G4)
- [ ] **WU-G4 Final sweep + gates** — `rg -i 'archimate[_-]?next'` (active surfaces = 0),
  `rg -i cardinalit` (only diagram-type structural config + historical ledgers), full
  quality gates, frontend gates, `types.generated.ts` current,
  `tools/generate_mcp_docs.py --check` green, README status/badges final, memory file
  `project_archimate4_compliance_plan` updated with outcome. Acceptance: all green; PLAN
  §11 checklist walked and ticked. (deps: everything)

---

## Progress notes

(append-only; date — WU — outcome — surprises)

2026-07-09 — WU-A1 — done — Full inventory of `rg -i 'archimate[_-]?next'` (excl.
node_modules, .git, PLAN-\*.md/TASKS-\*.md) below, grouped per acceptance criteria.
`meta_ontology:` check: only one `groups.yaml` exists
(`engagements/ENG-ARCH-REPO/architecture-repository/.arch-repo/groups.yaml`) and it has
zero `meta_ontology:` hits — confirmed clean, nothing to migrate there.

**Machine tokens** (pkg dir, loader symbols, registration, config `ontology:`/`module:`
tokens, alias map — all WU-A2/A3 scope):
- `src/ontologies/archimate_next/{__init__.py,_loader.py,entities.yaml,connections.yaml}`
  (dir + package name)
- `src/infrastructure/app_bootstrap.py:23,24,28,29,35` (`load_archimate_next_module`,
  `_archimate_next_module`, `_ARCH_PACKAGE_DIR` import path) and `:165`
  (`"archimate-next": "archimate-next-snapshot1"` alias entry)
- `src/diagram_types/c4/_projection.py:341` (`compatible_ontologies=("archimate-next-snapshot1", …)`)
- `src/diagram_types/archimate/{application,business,implementation,layered,motivation,strategy,technology}/config.yaml:2`
  (`ontology: archimate_next` — pkg name, correct token type, needs new pkg name)
- `src/diagram_types/c4/{component,container,system_context}/ontology.yaml`
  (`ontology: archimate-next-snapshot1` / `module: archimate-next-snapshot1` — module
  name, correct token type already, needs new module name)
- `src/diagram_types/{activity,datatype,sequence}/ontology.yaml`
  (`ontology: archimate_next` — **pkg name used where module name (`archimate-next-snapshot1`)
  is expected**, the pre-existing bug WU-A3 must fix, not just rename)
- `tools/gui/src/ui/lib/domains.ts:48-49,61` (`FRAMEWORK_GROUPS` key `archimate-next` /
  moduleName `archimate-next-snapshot1`; `DEFAULT_MODULES` name `archimate-next-snapshot1`)
- `src/ontologies/sysml_v2_min/entities.yaml:9` (comment referencing `archimate_next` as
  the module that declares shared classes — comment only, update wording in A2/A3 pass)

**Tests referencing tokens** (need updating alongside A2/A3/A4 renames):
`tests/application/write/test_datatype_correspondence.py`,
`tests/common/test_group_registry_validation.py`, `tests/common/test_startup_validation.py`,
`tests/domain/test_er_types_deprecated_not_removed.py`, `tests/domain/test_mapping_specs.py`,
`tests/domain/test_relationship_kind.py`, `tests/domain/test_sysml_v2_min.py`,
`tests/infrastructure/test_disabled_modules.py`, `tests/tools/test_backend_app_modules_route.py`,
`tests/tools/test_cardinality_and_guidance.py`, `tests/tools/test_group_ops.py`,
`tests/tools/test_module_consistency.py`, `tests/tools/test_unified_backend_runtime.py`,
`tools/gui/src/ui/lib/__tests__/domains.test.ts`,
`tools/gui/src/ui/views/__tests__/ModelWizardView.helpers.test.ts` (all WU-A4 for the two
frontend files, WU-A2/A3 for the Python ones).

**Display strings / docs** (WU-A5 scope):
- `README.md:20` badge `Model: ArchiMate NEXT (draft)`
- `docs/05-extensibility/{diagram-type-modules.md:14,index.md:38,ontology-modules.md:17,30}`
- `docs/architecture/dependency-policy.md:76` (table row citing `archimate_next/_loader.py`)
- `docs/architecture/decisions.md:12` (ADR link text "Adopt ArchiMate NEXT ontology" — link
  target is self-model, Phase G territory; display text here can rename now, target stays)
- `src/ontologies/README.md` (9,27,150,153,159,170,241,244), `src/diagram_types/README.md`
  (73,168)

**Skills** (WU-A5 scope):
- `.claude/skills/ontology-module-scaffold/SKILL.md:14,66,96` — needs update
- `skills/reverse-architecture/SKILL.md` — **zero hits**, already clean, nothing to do

**Self-model content** (out of scope for Phase A — Phase G, WU-G2 handles the rename):
- `engagements/ENG-ARCH-REPO/architecture-repository/docs/adr/platform-core/ADR@1780761591._mseZr.adopt-archimate-next-ontology.md`
- `engagements/ENG-ARCH-REPO/architecture-repository/docs/adr/platform-core/ADR@1780761609.GQWvwi.markdown-file-based-architecture-repository.md`
- `engagements/ENG-ARCH-REPO/architecture-repository/docs-conventions.md:20` (filename-stem
  example, prose only)
- `engagements/ENG-ARCH-REPO/architecture-repository/projects/motivation-narrative/model/motivation/principle/PRI@1712870400.uraDPR.extensibility-and-configurability.outgoing.md`
- `engagements/ENG-ARCH-REPO/architecture-repository/projects/motivation-narrative/model/motivation/requirement/REQ@1712870400.KeGCZE.archimate-next-model-ontology.{md,outgoing.md}`
  (the entity WU-G2 renames)

**Historical ledgers** (untouched, per plan — not `PLAN-*.md`/`TASKS-*.md` at repo root but
same category, completed/superseded feature ledgers):
- `plans/assurance-overlay/PHASE-0-module-extension.md`
- `plans/meta-ontology-v2/IMPL-phases-0-2.md`
- `plans/meta-ontology-v2/SPEC-phase-4-sequence-sysml-bridges.md`

No unknown categories — every hit above sorts into machine tokens / tests / display-docs /
skills / self-model / historical ledgers.

2026-07-09 — WU-A2 — done — `git mv src/ontologies/archimate_next → archimate_4`;
`_ArchiMateNextModule`→`_ArchiMate4Module`, `load_archimate_next_module`→
`load_archimate_4_module`, `name = "archimate-4-0"`; `__init__.py` docstring + import path;
`connections.yaml`/`entities.yaml` loader-path comments; `app_bootstrap.py` imports,
`_archimate_4_module` var, `_ALL_ONTOLOGY_MODULES`, `_META_ONTOLOGY_ALIASES` →
`{"archimate-4": "archimate-4-0"}`; `c4/_projection.py:341` `compatible_ontologies` tuple.
**Scope note (judgment call, recorded per session-loop step 4)**: keeping "full test suite
green" (a hard WU-A2 acceptance item) was not achievable with only the anchor-listed files —
three additional mechanical consequences of the rename had to land in this WU rather than
wait for WU-A3, because the existing (pre-plan) `validate_registry_consistency` /
`_load_ontology_module` machinery resolves these tokens *eagerly at bootstrap*, not lazily:
(1) `archimate/*/config.yaml` `ontology:` (7 files) — `_config_type._load_ontology_module`
does `importlib.import_module(f"src.ontologies.{package_name}")`, so leaving the old pkg name
here means every archimate diagram type fails to import, cascading into ~700 unrelated
failures; renamed pkg-name value only (`archimate_4`), same token type — this is the literal
WU-A3-listed acceptance item "archimate/*/config.yaml → archimate_4 (pkg)", just performed
now since it was unavoidable. (2) `c4/{component,container,system_context}/ontology.yaml`
`sources[].ontology` and `c4/container/ontology.yaml` bridge `module:` — already held the
*correct token type* (module name, `archimate-next-snapshot1`), just the stale value;
`_collect_bridge_errors` (in `src/application/startup_validation.py`, pre-existing, not new)
checks bridge `to.module` against the registry at every `build_module_registry()` call, so
this fails startup validation, not a single test, immediately after the module rename.
Value-only rename to `archimate-4-0`, no token-type change — the substantive WU-A3 work
(fixing activity/datatype/sequence's `ontology:` sources, which hold the **wrong token
type** — pkg name where module name is required, a pre-existing latent bug masked because
`permitted_mappings.sources[].ontology` is resolved lazily via `resolve_model_entity_types`,
only when a call site actually needs it, unlike bridges — and adding the new
startup/verifier check for `permitted_mappings` tokens generally) is untouched and remains
WU-A3's job. (3) ~13 Python test files asserting real registry/module content
(`from src.ontologies.archimate_next import module`, `find_ontology("archimate-next-snapshot1")`,
`meta_ontology="archimate-next"`, plus prose-only docstring/comment mentions) — updated to
match; left `tests/domain/test_mapping_specs.py` and
`tests/tools/test_cardinality_and_guidance.py:640` untouched — the former is pure
parsing-fixture data never resolved against a real registry, the latter asserts the actual
(still-buggy, pkg-name) value from `activity/ontology.yaml`, which WU-A3 will change. Full
suite (3791 passed, 9 skipped), ruff, zuban all green; `find_ontology("archimate-4-0")`
returns the module, old name resolves to `None`; zero remaining
`archimate_next`/`archimate-next` hits under `src/`/`tests/` except the WU-A3/A5-scoped
files enumerated in the WU-A1 inventory above (config.yaml pkg refs already fixed here don't
recount; activity/datatype/sequence ontology.yaml, READMEs, skills, self-model untouched as
planned).

2026-07-09 — WU-A3 — done — Remaining scope after WU-A2 already covered the config.yaml
pkg-token and c4 sources/bridge module-name renames: (1) fixed the actual pre-existing bug —
`src/diagram_types/{activity,datatype,sequence}/ontology.yaml` `permitted_mappings.sources[].ontology`
held the pkg name (`archimate_next`) where the module name is required; renamed to
`archimate-4-0` (5 occurrences activity, 1 datatype, 5 sequence); updated the one test
asserting the old (buggy) value, `tests/tools/test_cardinality_and_guidance.py:640`
(`archimate_next` → `archimate-4-0`). (2) Added the new startup/verifier check:
`src/application/startup_validation.py::_permitted_mapping_source_msgs` — iterates every
diagram type's `ui_config.diagram_only_types[].permitted_mappings.sources`, yields a message
when `registry.find_ontology(source.ontology)` is `None`; wired into
`_collect_consistency_errors`'s chain (runs inside `build_module_registry()`, so a bad token
fails loudly at startup like the existing bridge check, not silently at first lazy use).
(3) Regression tests in `tests/domain/test_bridges.py::TestPermittedMappingSourceValidation`
(new class, reusing the file's existing `_StubOntology`/`_StubDiagramType`/`_make_registry`
stubs) — known-token passes, unknown-token raises `RegistryConsistencyError` naming the bad
token. Left `tests/domain/test_mapping_specs.py` untouched (confirmed again: pure
`mapping_spec_from_config` parsing test, never resolved against a real registry, so the
placeholder string is inert). Full suite green (3793 passed, 9 skipped — +2 from the new
test class), ruff clean, zuban clean. `rg -i 'archimate[_-]?next'` under `src/`/`tests/` now
only hits the WU-A5-scoped READMEs and the untouched `test_mapping_specs.py` fixture, exactly
per the WU-A1 inventory.

2026-07-09 — WU-A4 — done — `domains.ts`: `FRAMEWORK_GROUPS` key `archimate-4`, moduleName
`archimate-4-0`, label `ArchiMate 4`; `DEFAULT_MODULES` name `archimate-4-0`. Updated
`domains.test.ts` (module fixture + expected group/meta-ontology-option keys) and
`ModelWizardView.helpers.test.ts` (module fixture). Ran `uv run tools/generate_types.py` —
no diff (the generated file enumerates entity/connection/diagram-type names, none of which
reference the module/pkg tokens this WU renames, so regeneration was a no-op; ran anyway per
the ledger's blanket rule). Zero remaining `archimate[_-]?next` hits under `tools/gui/src`.
Gates: `npm run lint` clean, `npm run typecheck` clean, `npx vitest run` 45 files / 480 tests
passed. Python suite unaffected by this frontend-only WU but re-verified green as a sanity
check (still 3793/9 skipped).

2026-07-09 — WU-A5 — done — Display-string + doc machine-token sweep per the WU-A1
inventory's "display strings/docs" and "skills" categories: `README.md` badge
(`ArchiMate NEXT (draft)` → `ArchiMate 4`), the two "It isn't (yet)" / "What you get" / status
lines (`ArchiMate NEXT draft` → `ArchiMate 4.0 standard`, keeping the "makes no conformance
claim" wording verbatim per Q4 — still open); `docs/05-extensibility/{ontology-modules.md,
index.md,diagram-type-modules.md}` (pkg-name examples `archimate_next`→`archimate_4`,
display prose `ArchiMate NEXT`→`ArchiMate 4`); `docs/architecture/dependency-policy.md:76`
(stale path `archimate_next/_loader.py`→`archimate_4/_loader.py` — the file physically moved
in WU-A2, this table would otherwise point at a nonexistent path); `src/ontologies/README.md`
and `src/diagram_types/README.md` (all `archimate_next` example tokens renamed, both token
types: pkg name where a package import is shown, module name `archimate-4-0` in the
`permitted_mappings.sources` example); `.claude/skills/ontology-module-scaffold/SKILL.md`
(module-name example, loader-path reference, registration snippet). Added a supersession
note (status line only, body untouched) to
`PLAN-archimate-next-rule-conformance-and-repository-cleanup.md`: it was still open/current
guidance (single commit, no companion TASKS ledger, never executed) and its purpose —
composition/service-realization/junction rule conformance against the normative
relationship tables — is now subsumed by this plan's WU-C1/C2 against the *final* ArchiMate
4.0 spec rather than the NEXT snapshot draft it targeted. **Left untouched, per explicit user
instruction mid-WU**: all other historical `PLAN-*.md`/`TASKS-*.md` ledgers at the repo root
(`TASKS-architecture-conformance.md`, `PLAN-OUTLINE-archimate-4-compliance.md`,
`TASKS-modeling-ux-and-self-model-uplift.md` + its PLAN, `PLAN-datatype-er-diagrams.md`,
`PLAN-c4-self-model-narrative.md`, `PLAN-assurance-stpa-grc.md`, `TASKS-c4-implementation.md`,
`TASKS-datatype-er-diagrams.md`, `PLAN-domain-layer-purity.md`) — user confirmed these do not
need updating to the new naming. Also deliberately left: `docs/architecture/decisions.md:12`
(ADR index row) — display text points at the *old* "Adopt ArchiMate NEXT ontology" ADR file
whose body still argues the NEXT-draft rationale; renaming the row's display text now would
misrepresent an unchanged historical record. WU-G2 supersedes that ADR with a new one and
should update this index row then, not here. `tests/domain/test_mapping_specs.py` also
deliberately left (pure fixture, confirmed again). Full sweep: `rg -i
'archimate[_-]?next'` outside historical ledgers + self-model + the one fixture file now
returns nothing. Full suite green (3793 passed, 9 skipped), ruff clean, zuban clean — no
Python semantics changed in this WU, docs/skills only. **Phase A (Rename, D1) is complete.**

2026-07-09 — WU-B1 — done — `src/domain/guidance.py`: `GuidanceKey` (module_alias,
concept_kind: entity|connection, type_name, specialization: str|None), `GuidanceEntry`
(create_when, never_create_when), `GuidanceOverlay` (frozen, `Mapping[GuidanceKey,
GuidanceEntry]`, `.get()`, `.is_empty()`, `.merge(*layers)` — later layers win on collision).
Per D2, module-inline text isn't itself an overlay layer (it's the loader's fallback on a
miss, wired in WU-B2); `merge()` takes exactly the two cache layers (enterprise, engagement)
in precedence order. Docstring notes the specializations.yaml-authored-guidance/overlay
separation (D2's "committed declarations never overridden") since that's a structural
non-interaction, not something this type enforces. 11 unit tests in
`tests/domain/test_guidance.py`: empty-overlay no-op, known/unknown key lookup, entity vs.
connection specialization keys are distinct (same type_name, different concept_kind),
merge precedence chain (single layer, later-wins collision, disjoint-key survival, empty
layer true no-op). Full suite green (3804 passed, +11 from this WU), ruff clean, zuban
clean, `tests/architecture/test_dependency_policy.py` green (2 passed) confirming
`src/domain/guidance.py` stays domain-pure (stdlib-only imports).

2026-07-09 — WU-B2 — done — Loader threading: `archimate_4/_loader.py` gains
`META_ONTOLOGY_ALIAS = "archimate-4"` constant, `_entity_guidance()` helper, and
`_load_entity_types(data, guidance=None)` / `load_archimate_4_module(..., guidance=None)`
params — overlay lookup wins over inline YAML text on a hit, falls through to inline text
on a miss (never blanks an unmatched type). `load_sysml_module`/`load_assurance_module`
gain the same `guidance: GuidanceOverlay | None = None` param, accepted and unused (both
modules' guidance is inline per PLAN §4.3, not spec-derived text). Added
`guidance_overlay_from_mapping()` to `src/domain/guidance.py` (pure v1-schema parser:
`meta_ontologies.<alias>.{entity_types,connection_types}.<type>` + nested
`specializations.<slug>`; a type entry with only a `specializations` block and no base
`create_when`/`never_create_when` — the reserved, not-yet-populated connection-base case —
deliberately produces NO base-level key, since an absent key means "fall back to
module-inline", not "override with empty text"). New infra module
`src/infrastructure/guidance_cache.py` (read-only; write side deferred to WU-B4 as its
natural owner) — `load_guidance_cache_file`/`load_guidance_overlay_for_repos`, absent file
⇒ empty overlay. `app_bootstrap.py`: `_load_archimate_guidance_overlay()` resolves workspace
roots via the existing `resolve_workspace_repo_roots()` seam (same idiom as
`generate_static_includes.py`/MCP `context.py`), loads enterprise-then-engagement caches,
passes the merged overlay into the top-level `_archimate_4_module` construction (still a
module-import-time singleton — guidance import takes effect on next backend restart,
matching the established `@lru_cache` registry ops model). `config/settings.yaml` +
`src/config/settings.py` gain `guidance: {default_source: ""}` +
`guidance_default_source()` accessor (defensive `.get`, matching `module_overrides()`'s
style rather than `datatype_type_references_blocking()`'s direct-index style, since a test
exercises a `load_settings()` mock without the key). **Deferred to WU-B3 (not B2)**: the
scaffolded `.arch-repo/.gitignore` `guidance-cache/` entry — its acceptance criterion lives
in WU-B3's own text, not B2's; B2 is read-only (no directory ever gets created by this
WU, so nothing to gitignore yet). Tests: 11 in `test_guidance.py` (parser: entity/connection
base + specialization, malformed-input tolerance, missing-meta_ontologies fallback) +
4 in `test_archimate_4_loader_guidance.py` (loader-level override, absent/empty-overlay
parity with current behavior) + 9 in `test_guidance_cache.py` (file read, tier precedence,
disjoint keys, missing root) + 3 in `test_guidance_bootstrap.py` (the actual "bootstrap
test" the acceptance criterion asks for: no-workspace fallback, engagement-overrides-
enterprise via a monkeypatched `resolve_workspace_repo_roots`, absent-caches-with-real-roots
parity) + 5 in `test_guidance_settings.py`. Full suite green (3827 passed, +34 from B1+B2
combined), ruff clean (one import-order autofix applied), zuban clean, dep-policy green (5
architecture tests). Surprise: the workspace already has live `arch-workspace.yaml` +
`.arch/init-state.yaml` at repo root, so `resolve_workspace_repo_roots()` resolves REAL
engagement/enterprise paths during ordinary test runs (not `None`) — verified this stays
safe because neither repo yet has a `guidance-cache/` dir, so the overlay is empty and
behavior is unchanged; this is the actual "absent caches = current behavior" path exercised
on every CI run, not just in the dedicated test.

2026-07-09 — WU-B3 — done — `tools/extract_guidance.py`: reads
`src/ontologies/archimate_4/entities.yaml`, extracts every non-empty entity type's
`create_when`/`never_create_when` into the v1 schema (`guidance_format: 1,
meta_ontologies.archimate-4.entity_types.<type>`), **verifies losslessness by round-tripping
the extracted doc through `guidance_overlay_from_mapping()` before writing anything**, then
writes it to an out-of-repo path (default `~/.arch-guidance-extract/archimate-4.guidance.yaml`,
`--out` override) — a hard guard (`_assert_out_of_repo`) refuses any `--out` that resolves
inside the repository, tested against a `./`-relative path. `--dry-run` extracts+verifies
without writing. The strip step is a targeted regex substitution
(`create_when: "..."` / `never_create_when: "..."` → `""`), not a full YAML re-dump, to
preserve the file's comments/blank-line formatting exactly — **surprise/bug caught before
committing**: the first regex used `\s*$` for trailing whitespace, and since `\s` matches
`\n`, it silently ate the blank line separating each entity-type block; verified via a
newline-count + diff check before/after, fixed to `[ \t]*$` (same-line whitespace only),
re-verified newline count identical (364) and diff shows only the two guidance lines
changed per entity, blank lines intact. Ran for real (not just dry-run): 43 entity types'
guidance extracted (44 total minus the already-empty `global-artifact-reference` internal
type), `entities.yaml` create_when/never_create_when now `""` for all 44 (88 lines), 0
guidance prose remains (`grep -c 'create_when: "[^"]'` → 0 non-empty hits). Fixed one
downstream test that assumed non-empty ArchiMate guidance text,
`tests/tools/test_cardinality_and_guidance.py::test_create_when_and_never_create_when_are_strings`
— now asserts the string *type* only (the emptiness itself is by design, WU-B5's job to
surface, not this test's to gate). **`.arch-repo/.gitignore` scaffolding** (this WU's own
acceptance item, not B2's): `src/infrastructure/guidance_cache.py` gains
`ensure_guidance_cache_gitignored(repo_root)` mirroring `m4_transaction.py`'s
`ensure_transactions_root` idempotent-append idiom (creates the cache dir, appends
`guidance-cache/` to `.arch-repo/.gitignore` once); not yet called from anywhere (its
caller is WU-B4's import CLI — the natural write-time owner) but fully implemented +
tested now (3 tests: creates dir+entry, idempotent, preserves pre-existing entries like
`transactions/`) so B4 only needs to invoke it. Also added a workspace-root `.gitignore`
guard (`*.guidance.yaml`, `*.guidance.meta.yaml`) as the belt-and-braces catch mentioned in
the WU-B3 anchor, against a stray extract/import landing outside any repo's own
`.arch-repo/`. Full suite green (3830 passed, +3 gitignore tests), ruff clean (verified the
gate scope is `src/ tests/` only — pre-existing unrelated import-order errors in
`tools/migrate_diagrams_to_bindings.py` are out of this gate's scope and untouched by this
WU), zuban clean (zuban's `files` config is `src` only, so `tools/extract_guidance.py`
isn't in its scope, consistent with other `tools/*.py` scripts). Extracted file confirmed
outside the repo (`git check-ignore` reports it as outside the repository entirely) and
absent from `git status`.

2026-07-09 — WU-B4 — done — `[project.scripts] arch-import-guidance` →
`src/infrastructure/cli/arch_import_guidance.py`, backed by a new pure-ish validation
module `src/infrastructure/guidance_import.py` (kept separate from the CLI file for
testability/LoC). Flow: `fetch_source` (HTTPS-only by default, `--allow-http` override,
10s timeout, 5MB size cap, local-path fallback) → `yaml.safe_load` → `validate_schema`
(`guidance_format: 1` + `meta_ontologies` mapping, else `GuidanceImportError`) →
`select_aliases` (`--module` restricts to one alias, else all present) →
`filter_alias_document` per alias (validates `entity_types`/`connection_types` keys
against the **module itself**, not just entity types — added the missing capability at
the correct layer: `app_bootstrap.resolve_meta_ontology_module(alias, registry)`, a small
new public function alongside the existing `resolve_meta_ontology_artifact_types`, since
that one only returns entity-type names and connection-type validation needs the full
module; added a delegation test in `test_disabled_modules.py` — known alias, unknown
alias, inactive-module cases). Unknown keys are listed and dropped unless `--strict`
(which aborts the whole import on any unknown key). Writes
`<repo>/.arch-repo/guidance-cache/<alias>.guidance.yaml` (filtered document) +
`<alias>.guidance.meta.yaml` sidecar (source, sha256 of the raw fetched bytes,
guidance_format, `imported_at` via `src/domain/clock.py::utc_now_iso` — central-clock rule
— matched/unmatched counts + keys) via `ensure_guidance_cache_gitignored` (the function
WU-B3 built and left uncalled for exactly this WU). `--repo-scope` resolves via the same
`resolve_workspace_repo_roots()` seam as B2. `--source` defaults from
`guidance_default_source()` (WU-B2's settings addition); errors when neither is set.
**Deferred by design, not oversight**: specialization-slug validation against "the target
repo's SpecializationCatalog when present" — that catalog doesn't exist in this codebase
yet (WU-D1 landed in a parallel worktree, not yet merged here; even once merged, the
*per-repo* catalog needs WU-D2, which itself depends on this WU's B2 foundation) — so
"when present" is correctly "not present yet" today; only entity/connection *type* keys are
validated for now, noted in the docstring so a future WU doesn't mistake the gap for a bug.
Tests: 17 in `tests/infrastructure/test_guidance_import.py` (schema validation, alias
selection, per-section key filtering incl. connection_types, fetch — local file, missing
file, oversize, plain-HTTP rejection) + 7 in `tests/cli/test_arch_import_guidance.py`
(happy path engagement scope, enterprise repo-scope targeting, dry-run writes nothing,
`--module` filtering, `--strict` failure, provenance sidecar content, and the acceptance
criterion's actual **restart-equivalent rebootstrap** test — surprise/gotcha caught and
fixed: `importlib.reload(app_bootstrap)` re-executes its
`from src.config.workspace_paths import resolve_workspace_repo_roots` line, which
silently un-does a monkeypatch applied to `app_bootstrap.resolve_workspace_repo_roots`
directly; fixed by patching `workspace_paths.resolve_workspace_repo_roots` instead — the
*source* module's attribute — so the re-import during reload picks up the patched
version; `monkeypatch.undo()` + a second reload in a `finally` block restores the process
to its pre-test state so no other test in the same worker sees the mutated singleton) + 3
delegation tests for `resolve_meta_ontology_module`. Full suite green (3857 passed, +27
from this WU), ruff clean, zuban clean (fixed two real zuban findings during development:
`yaml.safe_dump()`'s stub return type is `str | bytes | None`, needed explicit `str(...)`
before `Path.write_text`; and a genuinely unreachable `return 2` after
`argparse.ArgumentParser.error()`, which is typed `NoReturn`), dep-policy green. Verified
`uv run arch-import-guidance --help` resolves the registered entry point correctly.

2026-07-09 — session handoff — stopping here. Phases A (A1-A5) and B (B1-B4) are complete;
full quality gates green (3857 pytest passed / 9 skipped, ruff clean, zuban clean,
dep-policy clean); nothing uncommitted or half-done.

**Why stopping now rather than starting WU-B5**: WU-B5's own acceptance list has a hard
external blocker — "Document the hosting location, terms, and expected hash/version of the
published guidance file in docs (**per Q2 resolution**)" — and PLAN §10 Q2 ("Guidance
hosting: where will the extracted guidance YAML live... — Owner: Michael") is still an open
question, not yet answered. I cannot document a hosting location, terms, or hash/version
for a location that hasn't been chosen. The other parts of B5 (empty-state surfacing in
`artifact_authoring_guidance`/REST/GUI wizard, the license audit) do NOT depend on Q2 and
are real candidates for a future session, but ticking WU-B5 as done requires the full
acceptance list, so **this WU needs the user's Q2 answer before it can be completed**
(where should the extracted guidance file be hosted — a public repo? a gist? a docs site? —
and does the answer come with terms/license text and a way to compute an expected
hash/version?).

**Other reason to stop here**: the next phase-C WUs are content-risky without a source I
have access to. WU-C1/WU-C2 both require citing specific ArchiMate 4.0 spec section numbers
(§5.1.2, Appendix B) and diffing this repo's `permitted_relationships` against the
*normative* relationship tables. Per the no-PDF-in-git policy the spec itself is
deliberately never committed to this repo, and I do not have another source for the current
final-spec text in this session — attempting C1/C2 from general ArchiMate domain knowledge
risks getting a *compliance* plan's core semantic content wrong, which is exactly the kind
of mistake this plan exists to prevent. If the user can make the spec (or a scratch extract
of just §5.1.2 + Appendix B) available in this session, C1/C2 become tractable; otherwise
they need a session/agent with that access.

**What IS eligible and safe for another agent to pick up in parallel right now** (recorded
mid-session, still accurate): WU-C3a (unified connection-declaration grammar, deps: A2 —
touches `artifact_parsing.py`/`parse_existing.py`/`artifact_write_formatting.py`/
`connection_edit.py`, disjoint from anything touched this session) and WU-C4a
(`arch-repair upgrade` framework, deps: A2 — new CLI subcommand structure + backend-identity
endpoint, also disjoint). Per the user's direction, WU-D1 and WU-E1 were completed by
another agent in a separate worktree (branch `arch4-d1-e1`) during this session — once
merged, WU-D2 (deps: D1, B2 — B2 is now done) and WU-E2 (deps: E1) become the natural next
picks for that same line of work; D2 will touch `archimate_4/_loader.py` again (already
modified twice this session, for guidance threading), so merge/rebase onto this session's
commits first.

**Resume instructions for the next session**: read this ledger's Resume protocol + Locked
decisions, confirm Q2 has an answer (check Progress notes / ask the user) before touching
WU-B5, confirm whether spec section text is available before attempting C1/C2, and check
whether the `arch4-d1-e1` branch (WU-D1/E1) has merged before picking D2/E2.

2026-07-09 — WU-D1/WU-D2/WU-E1/WU-E2 — done — Verified in the parallel worktree
(`../scalable-architecture-for-humans-and-ai-arch4-d1-e1`, branch `arch4-d1-e1`) after
`uv sync --all-groups` (fresh worktree venv was missing fastapi/anyio/etc.): full suite
green (3839 passed / 49 skipped), ruff clean, zuban clean. Committed that worktree's
uncommitted WU-D2 tail (specialization_declarations.py, archimate_4/specializations.yaml
informative library, repo-level two-tier loading) as a separate commit, then merged the
whole branch into `main` (`git merge --no-ff`). One conflict in `app_bootstrap.py`
(this session's own concurrent WU-B2-completion commit — see below — vs. the branch's
`specializations=` param); resolved by keeping both: `_load_guidance_overlay(alias)` (this
session's rename) plus `specializations=_load_archimate_specializations()` (the branch's
addition). Post-merge: full suite green (3862 passed / 9 skipped — two
`test_entity_display_search_pagination` failures are pre-existing xdist-worker
cross-test pollution from an unrelated `importlib.reload(app_bootstrap)` in
`tests/cli/test_arch_import_guidance.py`, reproduced identically on a clean pre-merge
checkout; tracked separately, not caused by this merge), ruff clean, zuban clean,
`generate_types.py`/`generate_mcp_docs.py --check` both no-op (specializations not yet
GUI/MCP-exposed — that's WU-D6). Guidance overlay for specializations (both entity and
connection kind) is applied and tested in the merged commit
(`tests/domain/test_archimate_4_specializations.py`) — the "entity-type specialization
guidance" work the user had deferred pending this merge is therefore already satisfied by
what merged; the remaining related gap is WU-B4's specialization-slug key validation in
`arch_import_guidance`, tracked as a follow-up below.

2026-07-09 — WU-B2 (follow-up) — done — Completed the generalization WU-B2 left
"accepted, unused by default": `sysml_v2_min` and `assurance` loaders now apply their
`GuidanceOverlay` to entity-type `create_when`/`never_create_when` (previously accepted
but ignored); `app_bootstrap._load_archimate_guidance_overlay()` renamed to
`_load_guidance_overlay(alias)` and reused for all three modules;
`resolve_meta_ontology_module` falls back to treating the alias as a literal registered
module name for aliases outside `_META_ONTOLOGY_ALIASES` (e.g. `"assurance"`, which
carries its own guidance but isn't a selectable architecture-framework meta-ontology).
Fixed a stale caller in `tests/common/test_guidance_bootstrap.py` (referenced the
pre-rename function name). Full gates green pre-merge and post-merge.

2026-07-09 — WU-B4 (follow-up) — done — Closed the "deferred by design" gap
`filter_alias_document()` left in WU-B4: specialization-slug keys
(`entity_types.<type>.specializations.<slug>` / `connection_types.<type>.specializations.
<slug>`) are now validated against the target module's `SpecializationCatalog`, matching
the original acceptance criterion ("key validation against registry + the target repo's
SpecializationCatalog when present"). Added the missing capability at the correct layer
per this repo's architectural-discipline rule: `specialization_catalog` was only present
on the concrete `_ArchiMate4Module`, not declared on the `OntologyModule` Protocol, so
`guidance_import.py` had no generic way to reach it — added the property to the Protocol
plus an empty-catalog class-attribute default on `_SysmlV2MinModule`/`_AssuranceModule`
(neither ships specializations yet), so `isinstance(module, OntologyModule)` and the
existing `test_protocol_compliance.py` sweep stay satisfied for all three modules. Unknown
slugs are listed/dropped (or abort under `--strict`) exactly like unknown type keys; 5 new
tests in `tests/infrastructure/test_guidance_import.py` (known slug matched, unknown
slug dropped/strict, and a module-without-a-catalog case using sysml-v2's empty
catalog). Also applied the user's review of WU-D2's informative library while this was
in flight: removed `money-flow` (archimate-flow) as not needed, added `application-
component` → `service`/`module`/`endpoint` specializations (updated the one test that
asserted against real shipped content, `test_archimate_4_specializations.py`; the
generic-fixture tests in `test_specializations.py`/`test_guidance.py` still use
`money-flow` as illustrative parser data and were left alone). Separately fixed real
test-isolation flakiness (not caused by this session's changes, but blocking a clean
gate): `tests/cli/test_arch_import_guidance.py::TestRestartEquivalentRebootstrap` calls
`importlib.reload(app_bootstrap)`, which replaces that module's top-level function
objects in place; any router module already imported at collection time (holding
`Depends(<pre-reload object>)`) desyncs from a test fixture that re-imports
`app_bootstrap` fresh afterward on the same xdist worker — intermittently broke
`tests/tools/test_entity_display_search_pagination.py`. Fixed via sequencing, not
skipping: a new `tests/conftest.py::pytest_collection_modifyitems` hook pins that one
reload test to run strictly last in collection order, which — under xdist's default
`--dist=load` scheduler — guarantees no other test is ever dispatched to its worker
afterward, without serializing anything else. Full suite green across three consecutive
runs post-fix (3884-3888 passed depending on what else landed in the same pass), ruff
clean, zuban clean, `generate_types.py`/`generate_mcp_docs.py --check` both no-op.

2026-07-09 — WU-C1 — done — Source: `ArchiMate-4_compressed.pdf` (The Open Group, "ArchiMate®
4 Specification", Evaluation Copy — gitignored via `*.pdf` + `*.pdf:Zone.Identifier`, never
committed, confirmed via `git log --all -- '*.pdf'` = empty both before and after this WU).
§5.1.2 (p.31 of the PDF, printed page 31): "A composition relationship is allowed in exactly
the same cases where an aggregation relationship would be allowed." §B.5 Appendix B (Table
legend, p.139): letters `a(g)gregation/composition` — the normative tables use ONE shared
symbol for aggregation and composition, structurally proving the spec never distinguishes
them for permission purposes. §B.2.2 (p.126): structural-relationship strength order
confirmed verbatim — "Realization (weakest) < Assignment < Aggregation < Composition
(strongest)". Searched the codebase for every consumer of that ordering
(`hierarchy_priority`, `ConnectionSemantics.classify_connections`, "strength"/"derive"
hits): **`hierarchy_priority` has zero consumers anywhere in `src/`, `tests/`, or
`tools/gui`** — populated by both loaders, set for composition(1)/aggregation(2)/
specialization(0) in `connections.yaml`, read nowhere. Nothing to reorder (dormant, not
misordered); flagged here rather than removed — dead-surface removal needs the same
call-path-verification rigor as WU-D7, out of C1's scope.

Diffed `permitted_relationships` (composition-permitted pairs vs aggregation-permitted
pairs via the loaded module, not by eyeballing YAML): 387 aggregation pairs, only 255 also
had composition. Added composition alongside aggregation in `connections.yaml` wherever
missing (22 YAML rule lines, incl. the `@all/@same`, `@internal-behavior-element` self,
`role -> @external-active-structure-element`, `technology-node -> {system-software,
facility, device, equipment}`, `plateau -> ...` cross-domain rules, `location -> @all`).

**Per user direction, verified every added pair against the actual Appendix B relationship
matrices (images — the tables have no extractable text layer in this PDF build; rendered
via `pdftoppm` at 400 DPI and read directly)**, not just trusted the §5.1.2 general
statement. Caught and corrected my own row/column mixup early (`From →` labels the
**columns**, `To ↓` labels the **rows** — confirmed via the `location -> @all` blanket
rule, whose "any concept" only reproduces when read as a `Location` *column*). Checked all
~20 edited pairs (or their class expansions) directly: **21 of 22 fully confirmed** (a
direct "G" cell in the source-column/target-row position). **One exception found**:
`technology-node -> artifact` shows no "g"/"G" in either direction on the Technology-domain
table — reverted the composition addition for this one pair only (aggregation itself left
untouched; it may be a pre-existing rule the generic cross-domain table doesn't capture,
similar to the documented Product/Plateau composite-element figure-specific exception on
p.139 — needs the actual Chapter 10 metamodel figure to resolve, deferred to WU-C2's
systematic recheck). Final diff: 387 aggregation pairs, 386 composition pairs, exactly one
documented, tested exception.

Structural test added: `tests/domain/test_archimate_4_composition_semantics.py` —
`test_composition_permitted_wherever_aggregation_is` (asserts the diff is empty modulo the
one documented exception) + `test_known_exception_is_still_aggregation_only` (guards the
exception itself so a future fix is a deliberate, visible change to the exception set, not
a silent regression). Full suite green (3890 passed / 9 skipped), ruff clean, zuban clean,
`generate_types.py`/`generate_mcp_docs.py --check` both no-op (permitted-relationship data
isn't part of the generated-types surface).
