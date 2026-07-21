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

- **Q1 (gates WU-A1) — Specialization breadth.** Ship all nine specializations
  (PLAN §4 D2), or start with `ai-model` / `ai-dataset` / `ai-inference-service`
  and extend later? OPEN.
- **Q2 (gates WU-E2) — Marking tool placement.** Marking is an architecture
  write; the principled home is `arch-repo-write`, contradicting the dangling
  `assurance_mark_ai_component` name. Confirm the cross-server move. OPEN.
- **Q3 — SPDX 3.0 AI Profile as a second emitter.** Out of scope for this plan;
  confirm "later" vs "never". OPEN.
- **Q4 — Stream ordering.** Recommended: rename sweep → profile registry →
  OpenAPI → AIBOM. OPEN.

## Stream A — Ontology foundation

### WU-A1 — AI specializations (needs Q1)
- [ ] Declare the agreed specializations in
      `src/ontologies/archimate_4/specializations.yaml` (slug + name per base
      type, per PLAN §4 D2).
- [ ] Verify each base type accepts specializations and that the slugs collide
      with nothing existing (the `application-component` list already has
      `service` and `module`).
- [ ] Tests: the module loader exposes every new specialization; the guidance
      layer surfaces them for authoring.

### WU-A2 — Shared and specific profiles (needs A1, and the profile registry's WU-P2)
- [ ] Declare shared named profiles (provenance, licensing, supplier) once and
      bind them to the AI specializations (PLAN §4 D3).
- [ ] Per-specialization profiles for what genuinely differs only.
- [ ] **Declare no attribute the base type already provides** (D3a) — base-type
      inheritance already works. `componentData.classification` /
      `sensitiveData` derive from the existing base `Sensitivity` attribute and
      its specified TLP mapping; do not add a parallel AI sensitivity field.
- [ ] Attribute set per PLAN §3, Title Case (D8), flat scalars + string arrays
      only (D4). Required/recommended levels set deliberately — required means
      *the AIBOM is invalid without it*, not merely *nice to have*.
- [ ] Register shipped defaults in `DEFAULT_SCHEMATA`, keeping that module
      within the source-length policy — split as
      `repo_default_assurance_schemata.py` already does if needed.
- [ ] Tests: every payload is valid JSON Schema; no orphan attachment schemata
      (verifier rule W044); a specialization's effective schema contains its
      base-type attributes without redeclaring them.

### WU-A3 — Derivation-role vocabulary and bindings (needs A1)
- [ ] Declare the closed role vocabulary (PLAN §5) and the default
      role→(connection type, target specialization) bindings as a YAML file in
      the ArchiMate module.
- [ ] Support a repository-level override in `.arch-repo/`, merged over the
      shipped defaults.
- [ ] Tests: defaults load; an override replaces exactly the bound role and
      leaves the rest; an unknown role name in an override is a typed error, not
      a silent ignore.

### WU-A4 — Upgrade path (needs A2)
- [ ] Verify `DefaultSchemataEnsureStep` picks up the new entries with no code
      change (expected — it iterates `DEFAULT_SCHEMATA`).
- [ ] Regression test: an existing repo without AIBOM schemata gains them on
      upgrade; a customised AIBOM schema is preserved and reported, never
      overwritten.
- [ ] Confirm and record: a repo with no AI specializations in use is a
      *truthful empty* AIBOM state, requiring no migration.

### WU-A5 — Stream A boundary
- [ ] Full backend gates green. Fresh-repo scaffolding and upgraded-repo paths
      both verified.

## Stream B — Derivation engine

### WU-B1 — Derivation core (needs A3)
- [ ] New pure application module: entities + connections + bindings → typed
      AIBOM component set. No IO, no store access, no HTTP.
- [ ] Resolve `modelParameters.datasets` from `trained-on` / `evaluated-on` /
      `fine-tuned-from` bindings; `componentData.governance` from
      accountability connections; the BOM `dependencies[]` graph from AI-to-AI
      relations.
- [ ] Per-field provenance: every value is marked derived or authored, with the
      authored value winning (PLAN §4 D5).
- [ ] Tests: each derivation role in isolation; authored-overrides-derived;
      cycles in the dependency graph terminate; an entity with no relations
      yields a valid but sparse component.

### WU-B2 — Considerations from the motivation layer (needs B1)
- [ ] Derive `considerations.users` / `useCases` from stakeholders/drivers/goals
      reachable from the AI component, bounded by an explicit traversal depth —
      not an unbounded graph walk.
- [ ] Tests: depth bound honoured; unreachable motivation yields empty, not
      error.

### WU-B3 — Coverage evaluation (needs B1)
- [ ] Per-AI-component report: missing required attributes, unbound derivation
      roles, missing governance edge, missing dataset linkage.
- [ ] Tests: a fully-specified component reports clean; each gap class is
      detected independently.

### WU-B4 — Stream B boundary
- [ ] Backend gates green; derivation covered by unit tests with no store
      dependency.

## Stream C — Exporter rewrite

### WU-C1 — Full ML-BOM emission (needs B1)
- [ ] Rewrite `_aibom_exporter._cdx_component`: populated `modelCard`
      (`modelParameters`, `quantitativeAnalysis`, `considerations`),
      `componentData` with `classification` / `sensitiveData` / `governance`,
      `supplier` / `licenses` / `hashes` where authored.
- [ ] Emit a real `dependencies[]` graph.
- [ ] Keep the CycloneDX envelope and `AI_BOM_ROLES` vocabulary surface intact
      (the GUI consumes the roles endpoint).

### WU-C2 — Schema-validated tests (needs C1)
- [ ] Validate emitted documents against the CycloneDX 1.6 JSON schema in tests
      (vendored schema; no network in CI).
- [ ] Tests: a model with datasets and governance emits a document that
      validates and contains the derived relationships.

### WU-C3 — Reconcile on the new shape (needs C1)
- [ ] Revisit `reconcile_aibom` against the richer component shape — identity
      keying (purl-else-name) is thin for models without purls.
- [ ] Tests: drift detection over model-derived components.

## Stream D — Coverage surface

### WU-D1 — Coverage read use case (needs B3)
- [ ] Application read surface for the coverage report, following the segregated
      read-port convention.
- [ ] Tests: unit-level over fake model reads.

## Stream E — REST + MCP surfaces

### WU-E1 — Export and coverage endpoints (needs C1, D1)
- [ ] REST: AIBOM export + coverage. MCP: the same, at parity.
- [ ] Both call one application layer; only denial/error rendering differs.
- [ ] Cross-surface parity test (same request ⇒ same body), per the convention
      established for signal ingest.

### WU-E2 — Marking tool (needs A1, Q2)
- [ ] Build the marking capability on the server Q2 selects — applying an AI
      specialization to an entity, with its profile attributes.
- [ ] **Fix the dangling reference**: `security_read_tools.py:146` currently
      tells agents to call the nonexistent `assurance_mark_ai_component`. Update
      it to the real tool name.
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
