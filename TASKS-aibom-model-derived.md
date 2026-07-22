# TASKS — Model-Derived AIBOM

Execution ledger for `PLAN-aibom-model-derived.md`. The plan is normative; this
file tracks execution and records what was verified.

**Dependency:** WU-A2 onward needs named reusable profiles from
`PLAN-attribute-profile-registry.md` (its Streams P and Q). Starting AIBOM first
would mean writing nine near-duplicate schema files and refactoring them away
immediately. WU-A1 (specializations) has no such dependency and can proceed.

## Resume protocol

1. Read `PLAN-aibom-model-derived.md` §4 (locked decisions) and §5 (mapping
   flexibility) before touching anything — they are not re-litigated.
2. Read the Questions section below; Q1/Q2 gate Stream A and Stream E
   respectively.
3. Find the first unticked WU whose dependencies are ticked.
4. Gates before every commit: `uv run python -m pytest -q -n auto` (one at a
   time, never concurrent), `uv run ruff check src/ tests/`, `uv run zuban
   check`; frontend from `tools/gui/`: `npm run lint && npm run typecheck &&
   npx vitest run` (full `npm run lint`, never `lint:fast`).
5. Backend code changes are inert until the owner restarts `arch-backend`; MCP
   surface changes additionally need a Claude session restart. Queue live
   verification rather than blocking on it.

## Questions

All RESOLVED by the owner 2026-07-21 (persisted into PLAN §9 and the gated WUs):

- **Q1 (gated WU-A1) — Specialization breadth → EIGHT** (D2 refined with the owner
  2026-07-22). Originally "all nine"; on review two refinements landed:
  - **`ai-agent` and `ai-orchestrator` MERGE into one `ai-agent`** (application-component).
    Both are application-components coordinating model calls + tools; the only line is
    control flow (autonomous loop vs deterministic pipeline), a spectrum, and NEITHER is a
    distinct CycloneDX component type — so the split bought architectural nuance, not BOM
    fidelity. Merged; the pipeline-vs-loop nuance is captured in the specialization
    description / an attribute.
  - **`ai-inference-service` specializes the `service` entity type**, not "application-service"
    — `application-service` is itself a specialization of `service`, not a base entity type,
    so a specialization cannot attach to it. `service` is the correct application-layer base;
    AIBOM component type = service. (D2 label reconciled; the intent "a served inference
    endpoint" is unchanged.)
  The final EIGHT: application-component → `ai-model`, `ai-agent`; service →
  `ai-inference-service`; data-object → `ai-dataset`, `ai-prompt-asset`, `ai-vector-store`;
  system-software → `ai-runtime`; application-interface → `ai-tool-interface`. The
  named-profile registry (landed) removes the near-duplicate-schema cost.
- **Q2 (gated WU-E2) — Marking placement → `arch-repo-write`, REUSE `artifact_edit_entity`.**
  Marking = setting an AI specialization on an existing entity (an architecture write);
  reuse the existing edit tool's `specialization` field rather than add a tool
  (small-tool-count discipline), and DROP the dangling `assurance_mark_ai_component` name.
- **Q3 — SPDX 3.0 AI Profile → DEFER (later, not never).** CycloneDX ML-BOM is the v1
  emitter; SPDX 3.0 AI Profile is a documented future second emitter, revisited when a
  regulatory filing needs it.
- **Q4 — Ordering → CONFIRMED:** profile registry (done) → OpenAPI → AIBOM, so AIBOM is
  built on reusable profiles under finished schema discipline; any pending rename sweep
  lands before AIBOM's ontology changes.

## Stream A — Ontology foundation

### WU-A1 — AI specializations (Q1 resolved: EIGHT — see Questions)
- [x] Declare the eight specializations in
      `src/ontologies/archimate_4/specializations.yaml` (slug + name +
      description + create/never guidance per base type).
- [x] Verify each base type accepts specializations and that the slugs collide
      with nothing existing.
- [x] Tests: the module loader exposes every new specialization; the guidance
      layer surfaces them for authoring.

#### WU-A1 PROGRESS (2026-07-22)
- Eight AI specializations shipped (owner refined D2 from nine — see Questions): `ai-model`,
  `ai-agent` on `application-component`; `ai-inference-service` on `service`; `ai-dataset`,
  `ai-prompt-asset`, `ai-vector-store` on `data-object`; `ai-runtime` on `system-software`;
  `ai-tool-interface` on `application-interface`. Each carries a description + create_when /
  never_create_when that draws the model/service/runtime and data distinctions, so the
  authoring surfaces explain when to reach for each.
- `ai-orchestrator` deliberately NOT shipped (merged into `ai-agent`); a regression asserts
  its absence. `ai-inference-service` attaches to the `service` entity type (the correct
  application-layer base; "application-service" is itself a specialization of `service`).
- No `types.generated.ts` change (it carries type names + reserved paths, not specialization
  slugs). Profiles/bindings are WU-A2; roles WU-A3.
- Tests: `tests/domain/test_archimate_4_specializations.py::test_ships_the_eight_ai_specializations_on_their_base_types`.
- Gates: backend 6378 passed / 5 skipped; ruff + zuban clean.

### WU-A2 — Shared and specific profiles (needs A1, and the profile registry's WU-P2)
- [x] Declare shared named profiles and bind them to the AI specializations (D3).
- [x] Per-specialization profiles for what genuinely differs only.
- [x] **Declare no attribute the base type already provides** (D3a).
- [x] Attribute set per PLAN §3, Title Case (D8), flat scalars + typed arrays (D4).
- [~] Register shipped defaults in `DEFAULT_SCHEMATA` — DEVIATION: the AIBOM attributes ship
      in the MODULE (profiles.yaml + inline on specializations.yaml), not as per-repo
      attachment files, so they need no `DEFAULT_SCHEMATA` entry and no per-repo migration
      (the named-profile registry supersedes the attachment-file approach the box assumed).
      The one `DEFAULT_SCHEMATA` addition is the `data-object` BASE schema (Sensitivity +
      Provenance) — a latent ontology gap, not AI-specific — so `ai-dataset` inherits
      Sensitivity per D3a (data-object had no base schema; business-object was the precedent).
- [x] Tests: profiles are valid JSON Schema; no orphan AI attachment schemata; ai-model's
      effective schema = base ⊕ shared profiles ⊕ model card with no redeclaration; ai-dataset
      inherits the base data-object attributes.

#### WU-A2 PROGRESS (2026-07-22)
- Shared profiles in `src/ontologies/archimate_4/profiles.yaml`: `ai-supplier`
  (Supplier, Publisher) and `ai-licensing` (Licenses, Hashes) — bound via `profiles:
  [ai-supplier, ai-licensing]` from ai-model, ai-agent, ai-inference-service, ai-runtime,
  ai-dataset.
- Model card inline on `ai-model` (Approach enum, Task, Architecture Family, Model
  Architecture, Inputs, Outputs, and the six list attributes); small inline attributes on
  ai-agent (Control Flow enum) and ai-dataset (Dataset Role enum). Prompt-asset / vector-store
  / tool-interface carry no authored profile (base + relations suffice).
- **Profile-format fix (owner-flagged 2026-07-22): array attributes now declare `items`.**
  `ProfileAttribute` gained `items`; `attributes_from_mapping` parses it and
  `compile_profile_schema` emits `items` for `type: array` — so every list attribute
  declares its element type (verified end-to-end: profile → effective schema → GUI
  descriptor, which the WU-Y1 list editor already consumes). A bare untyped array is no
  longer produced. All six model-card lists + Licenses/Hashes carry `items: {type: string}`.
- The `data-object` base schema (Sensitivity + Provenance) added to
  `repo_default_attribute_schemata.py`; source-length policy still green.
- Tests: `tests/domain/test_aibom_profiles.py`, `test_profiles.py` (array items +
  non-array ignore), and the updated shipped-registry test.
- Gates: backend 6383 passed / 5 skipped (+ the one updated test); ruff + zuban clean.

### WU-A3 — Derivation-role vocabulary and bindings (needs A1)
- [x] Declare the closed role vocabulary (PLAN §5) and the default
      role→(connection type, target specialization) bindings as a YAML file in
      the ArchiMate module.
- [x] Support a repository-level override in `.arch-repo/`, merged over the
      shipped defaults.
- [x] Tests: defaults load; an override replaces exactly the bound role and
      leaves the rest; an unknown role name in an override is a typed error, not
      a silent ignore.

#### WU-A3 PROGRESS (2026-07-22)
- Domain: `src/domain/aibom_roles.py` — `AIBOM_DERIVATION_ROLES` (the closed nine),
  `RoleBinding` / `DerivationRoleBindings`, `role_bindings_from_mapping` (typed
  `DerivationRoleError` on an unknown role or a binding with no connection type),
  `merge_role_bindings` (per-role override), and `unbound_roles()` for the coverage finding
  (an unbound role is a finding, never a silently-empty BOM — PLAN §5).
- Shipped defaults: `src/ontologies/archimate_4/aibom_roles.yaml`, loaded by
  `load_module_aibom_roles`. Repo override `.arch-repo/aibom-roles.yaml` merged per-role by
  `src/application/aibom_role_loading.resolve_aibom_role_bindings` (mirrors the profile-registry
  repo-override loader; absent file = shipped unchanged).
- The three dataset roles share a default connection binding (model→access→ai-dataset);
  the Training/Evaluation/Fine-tuning distinction is the dataset's `Dataset Role` attribute,
  not three connection types — a repo may still override each separately.
- **STREAM-B NOTE (spec-vs-code tension, recorded not worked around):** PLAN §3 sources
  `componentData.governance` from `accountable-for` / `responsible-for`, which are
  CONFIDENTIAL assurance (GRC) relations the PUBLIC AIBOM derivation cannot read. The
  `governed-by` default binds to the architecture-layer `archimate-assignment`. Whether
  Stream B's governance derivation should additionally consult assurance-store accountability
  edges (and how, given the confidentiality boundary) is a WU-B1 decision — flag for the
  owner there if it materially changes governance coverage.
- Not wired into the module protocol / RuntimeCatalogs: WU-B1 takes bindings as a parameter,
  so the export use case (Stream E) resolves them via the loader and passes them in — no
  speculative runtime plumbing.
- Tests: `tests/domain/test_aibom_roles.py`.
- Gates: backend 6393 passed / 5 skipped; ruff + zuban clean.

### WU-A4 — Upgrade path (needs A2)
- [x] Verify `DefaultSchemataEnsureStep` picks up the new entries with no code
      change (it iterates `DEFAULT_SCHEMATA`; the data-object base is now an entry).
- [x] Regression test: an existing repo without the schema gains it on upgrade;
      a customised copy is preserved and reported, never overwritten.
- [x] Confirm and record: a repo with no AI specializations in use is a
      *truthful empty* AIBOM state, requiring no migration.

#### WU-A4 PROGRESS (2026-07-22)
- The only shipped-schema-file addition is the `data-object` base (A2); the AIBOM attributes
  themselves live in the module (profiles.yaml + inline specializations), so there are NO AI
  attachment files to ensure and NO per-repo migration for the attribute layer. The ensure
  step needed zero code change — confirmed it iterates `DEFAULT_SCHEMATA`.
- Truthful-empty confirmed by test: a repo carrying the defaults but using no AI
  specialization writes no `ai-*` schema files and a second ensure run is clean — no AI
  content is invented; absence of AI specializations simply means no AI components.
- Tests: `tests/application/test_default_schemata_ensure_step.py::TestAibomUpgradePath` (4).

### WU-A5 — Stream A boundary
- [x] Full backend gates green. Fresh-repo scaffolding and upgraded-repo paths
      both verified.

#### WU-A5 PROGRESS (2026-07-22)
- Stream A complete: eight specializations (A1), shared+inline profiles with typed arrays
  (A2), the data-object base + upgrade path (A4), and the derivation-role vocabulary+bindings
  (A3). Fresh-repo scaffolding ships the schemata via `DEFAULT_SCHEMATA`; the upgrade path
  adds them to existing repos and preserves customisations — both test-covered.
- Gates: backend 6397 passed / 5 skipped; ruff + zuban clean.

## Stream B — Derivation engine

### WU-B1 — Derivation core (needs A3)
- [x] New pure application module: entities + connections + bindings → typed
      AIBOM component set. No IO, no store access, no HTTP.
- [x] Resolve datasets from `trained-on`/`evaluated-on`/`fine-tuned-from`; governance from
      the `governed-by`/`guarded-by` bindings; the `dependencies[]` graph from AI-to-AI
      relations.
- [x] Per-field provenance: authored attributes carried as `authored`; relational facts
      `derived`; authored wins for a same-named field (D5).
- [x] Tests: each role in isolation; wrong-target rejected; dependency graph + cycle
      termination; sparse no-relations component; drift guard (ontology slugs ↔ type map).

#### WU-B1 PROGRESS (2026-07-22)
- `src/application/aibom_derivation.py` — pure `derive_aibom(entities, connections, bindings)`
  → `tuple[AibomComponent]`. `AI_COMPONENT_TYPE` maps each AI specialization to its CycloneDX
  component type (and IS the "which specializations are AI" set); a drift test pins it against
  the shipped ontology. Datasets/governance are role matches; dependencies are AI→AI edges
  (emitted once per target, no traversal, so cycles terminate). Authored attributes come from
  the decoded Properties with `authored` provenance.
- **GOVERNANCE (recorded A3 note carried through):** the pure core derives governance from the
  `governed-by`/`guarded-by` bindings over ARCHITECTURE connections only. It does NOT read the
  confidential assurance accountability store — that boundary is respected. If the owner later
  wants assurance-edge governance, it enters as a separate input to this pure function; not
  done, and flagged.

### WU-B2 — Considerations from the motivation layer (needs B1)
- [x] Derive `considerations.users` (stakeholders) / `use_cases` (drivers/goals) reachable
      from the AI component, bounded by an explicit `consideration_depth` (bounded BFS, never
      an unbounded walk).
- [x] Tests: depth bound honoured; unreachable motivation yields empty, not error.

### WU-B3 — Coverage evaluation (needs B1)
- [x] Per-AI-component report: missing required attributes, unbound derivation roles, missing
      governance edge, missing dataset linkage — in TWO tiers (blocking vs advisory).
- [x] Tests: fully-specified reports clean; each gap class detected independently; the
      recommended (advisory) tier does not block validity.

#### WU-B3 PROGRESS (2026-07-22)
- `src/application/aibom_coverage.py` — `evaluate_coverage(components, required, bindings,
  recommended_attributes=…)` → `AibomCoverage`. Per-component gaps: required-missing +
  dataset + governance are BLOCKING (`clean` is false); recommended-missing is ADVISORY
  (`complete` is false but `clean` stays true) — the "handle optional/unavailable sensibly"
  tiering. Repo-wide `unbound_roles` from `bindings.unbound_roles()`.
- **OWNER NOTE (2026-07-22) for Streams D/F:** the AI-BOM creation wizard should surface
  modeling gaps (from this coverage) and help remedy them on the fly, possibly via a NEW
  ANCHORED VIEWPOINT anchored on AI components that renders coverage. Optional/unavailable
  info must be handled sensibly — this coverage's required(blocking) / recommended(advisory) /
  optional(untracked) tiers are the data model for exactly that. Carry into WU-F3 (coverage
  view) and WU-D1.
- **DECISION (owner, 2026-07-22): coverage is ENGINE ONLY — no anchored viewpoint.** After a
  critical evaluation (viewpoints suit graph-structure predicates + presentation; AIBOM
  coverage is schema-relative "required by this spec's effective schema", binding-relative
  "linked via a bound role", and repo-wide "unbound role" — none of them graph-structure
  predicates — and the exporter/endpoint need a TYPED verdict a viewpoint cannot supply), the
  owner chose dedicated code end to end. WU-F3's coverage view renders findings DIRECTLY from
  `evaluate_coverage`; NO anchored coverage viewpoint is built. Any neighborhood exploration
  is a bespoke panel, not a reusable viewpoint.

### WU-B4 — Stream B boundary
- [x] Backend gates green; derivation + coverage covered by unit tests with no store
      dependency.

#### WU-B4 PROGRESS (2026-07-22)
- Stream B (derivation core + considerations + coverage) is pure application-layer, no IO/
  store/HTTP — every test constructs records directly. Gates: backend 6417 passed / 5
  skipped; ruff + zuban clean.

## Stream C — Exporter rewrite

### WU-C1 — Full ML-BOM emission (needs B1)
- [x] Full ML-BOM node builder: populated `modelCard` (`modelParameters`,
      `quantitativeAnalysis`, `considerations`), `componentData` with
      `classification` / `governance`, `supplier` / `licenses` where authored.
- [x] Emit a real `dependencies[]` graph.
- [x] Keep the CycloneDX envelope intact.

#### WU-C1 PROGRESS (2026-07-22)
- New focused module `src/infrastructure/assurance/mlbom_builder.py` — `build_mlbom(
  components: Sequence[AibomComponent])`. Consumes the TYPED derived components (not the
  legacy caller-confirmed dicts), so the exporter is fed by the derivation core. Rather than
  rewrite the dict-based `_cdx_component` in place (its `build_cyclonedx_16` is the legacy
  scan→confirm path Stream E will retire), the typed builder is the C1 deliverable and E
  rewires the surfaces to it.
- DEVIATIONS from the box, kept schema-valid and honest: `sensitiveData` is not emitted (our
  model has no structured sensitive-data content; `classification` from `Sensitivity` covers
  the tier). `hashes` and model-level `governance` (CycloneDX has no governance slot on a
  model, only on `componentData`) are emitted as `arch:`/`ai:` PROPERTIES rather than forced
  into ill-fitting fields. `notes` moved from the invalid `metadata.notes` (the legacy path's
  latent bug) to a `metadata` property.
- `AI_BOM_ROLES` (the component-TYPE vocabulary at `/api/assurance/aibom/roles`) is untouched
  — the derivation-role vocabulary (A3) is a distinct concept and does not replace it.

### WU-C2 — Schema-validated tests (needs C1)
- [x] Validate emitted documents against the CycloneDX 1.6 JSON schema in tests
      (the vendored `cyclonedx` package's `bom-1.6` schema; no network).
- [x] Tests: a model with datasets, governance, considerations, supplier, and licenses
      emits a document that VALIDATES and contains the derived relationships.

#### WU-C2 PROGRESS (2026-07-22)
- `tests/assurance/test_mlbom_builder.py` validates every emitted shape against
  `cyclonedx/schema/_res/bom-1.6.SNAPSHOT.schema.json` (bundled with the installed cyclonedx
  lib; the test skips if absent). Minimal model, full model card, data component with
  classification+governance, the dependencies graph, and model-governance-as-property all
  validate with zero schema errors.

### WU-C3 — Reconcile on the new shape (needs C1)
- [x] `reconcile_aibom` verified against the richer ML-BOM node shape — its purl-else-name
      keying works over derived AI components (which carry name, no purl).
- [x] Tests: drift detection over `build_mlbom` component output.

#### WU-C3 PROGRESS (2026-07-22)
- `reconcile_aibom` needed no change: it keys by purl-else-name and the ML-BOM nodes carry
  `name`, so a discovered extra AI component shows as `added`. Covered by
  `test_aibom_exporter.py::TestReconcileAiBom::test_reconcile_over_the_new_mlbom_component_shape`.
- Gates (C1–C3): backend 6423 passed / 5 skipped; ruff + zuban clean.

## Stream D — Coverage surface

### WU-D1 — Coverage read use case (needs B3)
- [x] Application read surface for the coverage report, following the segregated
      read-port convention.
- [x] Tests: unit-level over fake model reads.

#### WU-D1 PROGRESS (2026-07-22)
- `src/application/aibom_projection.py` — `project_aibom(search: ArtifactSearch, bindings, *,
  required_by_spec, recommended_by_spec)` → `AibomProjection{components, coverage}`. Pure
  composition over the segregated `ArtifactSearch` read port (list_entities + list_connections)
  plus the passed-in attribute levels — no schema/store IO, so it unit-tests over a fake
  search. This is the one read result every AIBOM surface (Stream E export + coverage
  endpoints, Stream F wizard) consumes.
- `aibom_schema_levels(repo_root, catalogs)` is the thin resolver that reads required /
  recommended (x-recommended) per AI specialization from the effective schemata — the caller
  passes its output into `project_aibom`, keeping the use case pure.
- Tests: `tests/application/test_aibom_projection.py` (projection composition over a fake
  search; empty when no AI entities; the schema-levels resolver over the real catalogs).
- Gates: backend 6426 passed / 5 skipped; ruff + zuban clean.

## Stream E — REST + MCP surfaces

### WU-E1 — Export and coverage endpoints (needs C1, D1)
- [ ] REST: AIBOM export + coverage. MCP: the same, at parity.
- [ ] Both call one application layer; only denial/error rendering differs.
- [ ] Cross-surface parity test (same request ⇒ same body), per the convention
      established for signal ingest.

### WU-E2 — Marking tool (needs A1; Q2 resolved: arch-repo-write, reuse edit)
- [ ] Marking = applying an AI specialization to an entity on `arch-repo-write` (Q2
      decided). Prefer REUSING the existing `artifact_edit_entity` (its
      `specialization` field) over a new tool; add a thin arch-repo-write tool only if a
      distinct affordance proves necessary. Do NOT implement `assurance_mark_ai_component`.
- [ ] **Fix the dangling reference**: `security_read_tools.py:146` currently
      tells agents to call the nonexistent `assurance_mark_ai_component`. Point it at the
      real arch-repo-write path (edit-entity specialization).
- [ ] Tests: marking persists; the scanner's skip-branch for already-marked
      entities now actually fires (regression test for the previously
      unreachable branch).

### WU-E3 — Docs regeneration (needs E1, E2)
- [ ] Regenerate MCP tool docs; group AIBOM tools sensibly rather than letting
      them fall into "Other" (the signal tools hit exactly this).
- [ ] REST reference entries.

## Stream F — GUI

### WU-F1 — Panel repair (needs E1)
- [ ] `AssuranceAibomPanel.vue`: remove the dead `aibom_coverage` calls (404
      today) and the panel bits that depend on them.
- [ ] Fix per-component role assignment — `selectedAiComponents` receives `{}`
      as `roleById`, so every component currently exports with the same default
      role.

### WU-F2 — Model-card authoring (needs A2)
- [ ] Author AIBOM attributes through the existing `TypedPropertyInput`
      (string/array/enum already supported — no new widget).
- [ ] Surface on the entity detail view, so a model card is authored where the
      entity lives rather than inside a wizard.
- [ ] Vitest coverage per the separate-file-per-component convention.

### WU-F3 — Coverage view (needs D1)
- [ ] Per-entity "what is missing for a valid AIBOM", replacing the promise the
      current help text makes and cannot keep.

### WU-F4 — Stream F boundary
- [ ] Frontend gates green: full `npm run lint`, `npm run typecheck`,
      `npx vitest run`.

## Stream G — Self-model, docs, dogfooding

### WU-G1 — Self-model sync
- [ ] Model the AIBOM derivation capability in ENG-ARCH-REPO: guidance-first,
      read-before-propose, descriptions over new entities, no argumentative or
      bundled motivation entities.

### WU-G2 — Documentation
- [ ] `docs/04-assurance/aibom.md`: what an AIBOM is, why model-derived beats
      manifest-scanned, how to mark components and author model cards, and what
      the coverage report means.
- [ ] README touch deferred to the owner (PLAN §7).

### WU-G3 — Dogfooding export
- [ ] Mark this repository's own AI components (MCP servers, agent-facing tool
      surfaces, the LLM-facing interfaces) with the new specializations.
- [ ] Generate our own AIBOM, review whether a procurement or audit reader would
      accept it, and commit it as an artefact.
- [ ] **This is the real acceptance test** for whether the derivation produces
      something meaningful rather than merely schema-valid. Record the verdict
      honestly here, including what the model could not supply.

## Restart-gated live verification queue

- [ ] AIBOM REST endpoints against the restarted backend.
- [ ] AIBOM MCP tools after a Claude session restart.
- [ ] Marking tool round trip: mark → derive → export.
