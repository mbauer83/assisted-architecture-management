# Implementation Plan — Hexagonal Architecture Conformance & Dependency Policy

**Mode:** [PLAN] · **Status:** Ready · **Date:** 2026-06-07
**Supersedes:** the earlier "Domain Layer Purity" draft (its `_registry_accessor` service-locator decision is **rejected** — see §3).
**Execution ledger:** `TASKS-architecture-conformance.md` — work units, status, and the per-session resume protocol live there. This PLAN is the *what/why*; the TASKS file is the *how-to-execute-across-sessions*.

---

## 1. Context and Motivation

A soundness review found that the project's stated hexagonal architecture is sound in *direction* but not yet *consistently enforced*. A second review deepened the findings: the original quick-fix plan (relocate `DiagramTypeBase`, rename `diagram_types.py`, fix README, add a domain-only grep) addressed real problems but **understated** the systemic issues and proposed a solution (a global registry accessor relocated into `domain/`) that would remove an *import* violation while preserving the underlying *dependency* — a service locator with hidden dependencies, global mutable state, init-order coupling, and cross-test contamination.

This plan replaces that approach with **explicit dependency injection from composition roots**, a **complete and enforced dependency policy** across all six packages, and a **frozen runtime catalog** built once at startup. It folds the original quick wins into their correct architectural position and addresses the full set of concerns.

**Scope boundary (locked):** No change may alter the **REST API**, **MCP tool surface**, or **CLI command surface**. These are the system's published contracts. Internal API changes — constructors, ports, module layout, injection wiring — are explicitly in scope, and larger cleanups are sanctioned where they stay behind those three surfaces.

---

## 2. Concern → Phase Traceability

| # | Concern (from review) | Phase(s) |
|---|---|---|
| 1 | No service locator in domain; inject focused catalogs from composition root | **B, C** |
| 2 | Define & enforce the complete dependency policy (all 6 packages, incl. lazy imports) | **A** |
| 3 | `ModuleRegistry` as aggregate with frozen runtime state; split builder/catalog; kill import-time snapshots; same for derivation registry | **B** |
| 4 | Split oversized `ArtifactStorePort` and verifier responsibilities | **F, G** |
| 5 | Refine the `DiagramTypeBase` move; classify `diagram_types` as a plugin/adapter package | **D, E** |
| 6 | Strengthen real immutability; publish immutable views; pure rule cores | **H** (+ B, G) |
| 7 | Clarify domain language; glossary; incremental (not cosmetic) renames | **I** (+ E) |
| 8 | Synchronize the self-model & README as architectural deliverables | **J** |

Phases are ordered by dependency. **A → B → C** are the foundation and must land in order. **D, E** are small and can land alongside C. **F, G, H** are larger structural refactors that depend on C and may be staged/scheduled independently. **I, J** are finishing work that must reflect whatever the earlier phases actually changed.

---

## 3. Approach Decision — Dependency Inversion Style

Three options were on the table for breaking the `domain → infrastructure` registry dependency:

1. **Pass `ModuleRegistry` to every function (functional/reader threading).** Rejected as the *sole* mechanism: ~40 catalog functions across 3 modules rely on `@lru_cache`, which breaks under per-call parameters; threading a never-changing singleton through 16 call sites and infrastructure constructors adds verbosity without inversion benefit.
2. **A global accessor relocated to `domain/_registry_accessor.py`** (the earlier draft's choice). **Rejected.** Moving the singleton into `domain/` removes the *import* arrow but keeps the *dependency*: hidden coupling, global mutable state, initialization-order fragility, cross-test contamination, inability to host two configured registries in one process, and caches that outlive registry replacement. A service locator in the domain violates dependency inversion and GRASP low-coupling regardless of which package the file sits in.
3. **Focused, injectable catalog objects built at the composition root.** **Chosen.**

### Chosen design (concern #1)

Define narrow **domain Protocols** describing registry *semantics*, with **immutable implementations** backed by a frozen `ModuleCatalog`:

- `OntologyCatalog` — entity/connection type lookups, element classes, domain ordering, prefixes, stereotype maps (absorbs today's `src/domain/ontology_catalog.py` free functions).
- `ConnectionSemantics` — permitted relationships, symmetry, classification, permissibility (absorbs `src/domain/connection_ontology.py`).
- `DiagramTypeCatalog` — diagram-type lookup, domain inference, relation-label suppression tokens (absorbs `src/infrastructure/diagram_types.py` and the registry-using parts of `src/domain/archimate_relation_rendering.py`).

These three are bundled into a frozen **`RuntimeCatalogs`** value (in `application/`) and **injected**:

- **FastAPI**: keep the existing app-state installation (`src/infrastructure/app_bootstrap.py:62` `install_module_registry`); extend it to install `RuntimeCatalogs`; expose via a `Depends(...)` dependency. Routers receive catalogs as parameters, not via module-level imports.
- **MCP**: the stdio bridges connect to the same unified backend over HTTP, so MCP tool logic resolves catalogs from the shared backend context object (`src/infrastructure/mcp/artifact_mcp/context.py`), not from a global.
- **CLI**: `src/infrastructure/cli/artifact_query_cli.py` and the assurance CLI construct the catalogs explicitly at `main()` and pass them down.

Derived values are cached **inside each catalog instance** (e.g. `functools.cached_property` or a frozen pre-computed map), not in module-level `@lru_cache`. Replacing the catalog replaces its caches atomically; tests construct a catalog from a fake/minimal `ModuleCatalog` with zero global state.

**Net effect:** `src/domain/` ends with **no** import — eager or lazy — of `src/infrastructure/` or `src/config/`. The catalog free-function modules either become the homes of the immutable implementations (pure, domain-only) or are deleted in favour of methods.

---

## 4. Locked Decisions

| # | Decision |
|---|---|
| D1 | **No global service locator** anywhere (domain, application, or infrastructure module scope). Runtime configuration flows by constructor/parameter injection from the three composition roots. |
| D2 | Split `ModuleRegistry` into a mutable **`ModuleCatalogBuilder`** (`register_*`, `replace_*`, `unregister_*`) and an immutable **`ModuleCatalog`** (all query methods). `build()`/`freeze()` produces the catalog; the builder rejects further registration after build. Naming follows the *product*: it catalogs **modules**, so `ModuleCatalog` + `ModuleCatalogBuilder` (not "Model…"). |
| D3 | Focused catalog **Protocols** (`OntologyCatalog`, `ConnectionSemantics`, `DiagramTypeCatalog`) live in `src/domain/`; their immutable implementations live in `src/domain/` (pure, backed by `ModuleCatalog`); the `RuntimeCatalogs` bundle lives in `src/application/`. |
| D4 | Remove import-time snapshots `ENTITY_TYPES` / `CONNECTION_TYPES` (`src/application/verification/artifact_verifier_types.py:94`). Validation contexts derive their valid-type sets from the injected catalog at verification time. |
| D5 | Apply the same freeze/build lifecycle to the global derivation registry (`src/application/derivation/strategy_registry.py:27`): a builder populated at startup, an immutable lookup injected into verifier rule E412 and the refresh dispatcher. |
| D6 | Author an explicit **dependency matrix** (§5) and enforce it with an **AST-based architecture test** covering all six packages and **lazy/in-function imports**. The test ships in a baseline mode that records current violations and fails on *new* ones, then violations are burned down phase by phase until the baseline is empty. |
| D7 | `domain → config` (`src/domain/artifact_types.py:5` → `infer_repo_scope`) is removed: the pure path-classification helper moves into `domain/`; YAML/workspace-file reading stays in `config/`. |
| D8 | `domain → ontologies` (`src/domain/ontology_catalog.py:9` → `matrix_abbreviations`) is removed: the ArchiMate matrix-abbreviation data is supplied through the injected `OntologyCatalog`, not imported from a concrete ontology package. |
| D9 | `DiagramTypeBase` relocates to `src/diagram_types/_base.py` **and** `src/diagram_types/` is **formally classified as a plugin/adapter package** (may depend on infrastructure renderers). Stage 2 (split declarative descriptor from renderer adapter, inject a renderer factory at bootstrap) is a flagged follow-on, not required for this plan's DoD. |
| D10 | `src/infrastructure/diagram_types.py` → `src/infrastructure/diagram_type_registry.py` (its lookup logic is largely absorbed by `DiagramTypeCatalog`; any residue is an infrastructure adapter). |
| D11 | `ArtifactStorePort` is segregated into role-focused contracts (§Phase F). The concrete store implements all of them; each consumer depends only on the narrow contract it uses. |
| D12 | Verifier is refactored toward **pure rule functions over parsed inputs**, with filesystem loading, PlantUML/Java execution, worker pools, and incremental-state persistence behind **application-owned ports** with infrastructure adapters (§Phase G). May be staged. |
| D13 | Public contract return types use immutable views (`Mapping`, `tuple`, `frozenset`); mutable builders stay local to parsing/indexing/validation; config is copied+frozen when published into a catalog (§Phase H). |
| D14 | Renames are **responsibility-driven, not cosmetic** — applied only to modules whose boundaries this work changes. A glossary (§Phase I) records the canonical vocabulary. |
| D15 | The self-model and README are updated **in the same change set** as the code that invalidates them; a verifier check flags self-model `Module:` properties that point at non-existent source paths (§Phase J). |

---

## 5. Dependency Matrix (the policy — concern #2)

```
package          may import from
──────────────   ────────────────────────────────────────────────
domain        →  domain only
application   →  domain, application
ontologies/*  →  domain (contracts + types) only            [plugin]
diagram_types/* → domain (contracts + types), infrastructure renderers   [adapter/plugin — see D9]
config        →  config, domain (value types only)          [leaf]
infrastructure → application, domain, plugins, config
composition   →  all packages   (app_bootstrap, cli/main, mcp server modules)
```

Notes:
- **`config` is a leaf**: it may use domain value types but nothing else; domain must not import config (D7).
- **`ontologies/*` are pure plugins**: domain contracts only — no infrastructure, no application.
- **`diagram_types/*` are adapter-plugins** (D9): explicitly permitted to touch infrastructure renderers, distinguishing them from pure ontology plugins.
- **"composition"** is not a package but a role: the entry-point modules that wire everything (`app_bootstrap`, CLI `main()`s, MCP server bootstrap). They alone may import across all layers.

---

## 6. Phases & Checklist

### Phase A — Dependency policy & architecture test (foundation)

- [x] **A1** Write the dependency matrix (§5) into a short architecture doc (`docs/architecture/dependency-policy.md` or a `## Architecture` section in README — TBD with R6/J).
- [x] **A2** Implement an AST-based architecture test `tests/architecture/test_dependency_policy.py`:
  - Walk every `*.py` under `src/`, parse with `ast`, collect **all** `Import`/`ImportFrom` nodes **including those nested inside functions** (lazy imports).
  - Classify each module into a package role; assert its imports obey the matrix.
  - Run in **baseline mode**: a checked-in `architecture_baseline.json` enumerates current known violations; the test fails only on violations **not** in the baseline.
- [x] **A3** Seed the baseline from the current tree (so CI is green at the start), then remove entries as each phase eliminates them. **DoD for the whole plan includes an empty baseline.**
- [x] **A4** Quality gates green (pytest, ruff, zuban).

### Phase B — Immutable `ModuleCatalog` + focused catalogs (concerns #1, #3)

- [x] **B1** Add `ModuleCatalogBuilder` (mutable; current `register_*`/`replace_*`/`unregister_*`) and immutable `ModuleCatalog` (all query methods) in `src/domain/module_catalog.py`. Builder `.build()` returns a `ModuleCatalog` and refuses subsequent registration. Keep `ModuleRegistry` temporarily as a thin alias only if needed to stage callers; remove by end of C.
- [x] **B2** Define Protocols `OntologyCatalog`, `ConnectionSemantics`, `DiagramTypeCatalog` in `src/domain/` and immutable implementations backed by a `ModuleCatalog`, caching derived values per-instance (`cached_property`/precomputed frozen maps). Port the logic currently in `ontology_catalog.py`, `connection_ontology.py`, and the registry-using parts of `archimate_relation_rendering.py`.
- [x] **B3** Remove import-time snapshots `ENTITY_TYPES`/`CONNECTION_TYPES` (`artifact_verifier_types.py:94`); the verifier derives these from the injected catalog (lands fully in C when the verifier receives the catalog).
- [x] **B4** Split the derivation registry (`strategy_registry.py`) into a `DerivationStrategyCatalogBuilder` + immutable `DerivationStrategyCatalog`; remove module-level `_registry`/`_derive_fns` globals.
- [x] **B5** Unit tests: build a `ModuleCatalog` from a minimal fake; assert builder rejects post-build registration; assert catalogs expose immutable views.
- [x] **B6** Quality gates green.

### Phase C — Composition-root injection (concern #1)

- [x] **C1** Add `RuntimeCatalogs` (frozen dataclass) in `src/application/runtime_catalogs.py` bundling the three catalogs (+ `DerivationStrategyCatalog`).
- [x] **C2** `app_bootstrap.py`: build `ModuleCatalog` via the builder, construct `RuntimeCatalogs`, install on FastAPI app-state (extend existing `install_module_registry` at line 62 → `install_runtime_catalogs`). Add a `Depends` provider `runtime_catalogs_dependency(request)`.
- [x] **C3** Migrate FastAPI routers and application/infrastructure consumers off the deleted free-function modules onto injected catalogs (constructor params or `Depends`). Enumerated call sites (16) from the dependency audit:
  - `application/artifact_parsing.py`, `application/modeling/artifact_write.py`, `application/modeling/matrix_builder.py`, `application/verification/artifact_verifier.py` (+`_verifier_rules_semantic.py`, `artifact_verifier_types.py`)
  - `infrastructure/artifact_index/_sqlite_store.py`, `infrastructure/gui/routers/connections.py`, `infrastructure/rendering/{archimate_puml_renderer,diagram_builder,generate_static_includes,generic_puml_renderer}.py`, `infrastructure/write/artifact_write/{connection,diagram_references,type_guidance}.py`
- [x] **C4** CLI composition roots (`cli/artifact_query_cli.py`, `cli/arch_assurance.py`) construct catalogs in `main()` and pass down.
- [x] **C5** MCP: resolve catalogs from the shared backend context (`mcp/artifact_mcp/context.py`); no module-global lookups in tool logic.
- [x] **C6** Delete `src/domain/ontology_catalog.py`, `src/domain/connection_ontology.py` free-function APIs and the registry-coupled parts of `archimate_relation_rendering.py`; remove `get_module_registry` global from `app_bootstrap.py` (or reduce to a composition-root-only builder helper). **No `@lru_cache(maxsize=1)` registry singletons remain.**
- [x] **C7** Architecture-test baseline: remove all `domain → infrastructure` entries; they must now pass.
- [x] **C8** Quality gates green; full regression run.

### Phase D — `config` / `ontologies` dependency cleanup (concerns #2, #5)

- [x] **D1** Move the pure repo-scope/path-classification helper out of `config.workspace_paths` into `domain/` (e.g. `domain/repo_scope.py`); leave YAML/workspace-file reading in `config/`. Update `domain/artifact_types.py:5`.
- [x] **D2** Remove `domain/ontology_catalog.py`'s import of `src.ontologies.archimate_next.matrix_abbreviations` — supply matrix abbreviations through `OntologyCatalog` (sourced from the ontology modules at build time).
- [x] **D3** Architecture-test: classify `ontologies/*` (pure plugin) and `diagram_types/*` (adapter-plugin, D9); remove the corresponding baseline entries.
- [x] **D4** Quality gates green.

### Phase E — `DiagramTypeBase` relocation + registry rename (concern #5)

- [x] **E1** Create `src/diagram_types/_base.py`; move `DiagramTypeBase` from `ontology_protocol.py` (keep its `GenericPumlRenderer` import — `diagram_types` is now a classified adapter package). Remove `DiagramTypeBase` from `ontology_protocol.__all__`; only Protocols/types remain there.
- [x] **E2** Update the 8 diagram-type module imports + `tests/domain/test_bridges.py`.
- [x] **E3** Rename `src/infrastructure/diagram_types.py` → `diagram_type_registry.py`; update the 12 import sites; fold its lookup logic into `DiagramTypeCatalog` where it duplicates B2, leaving only genuine infra adapter code.
- [x] **E4** Regression test asserting `src.domain.ontology_protocol` imports cleanly with **no** `src.infrastructure` import on any path.
- [ ] **E5** (Flagged follow-on, not in DoD) Stage 2: split declarative diagram descriptor from renderer adapter; inject a renderer factory at bootstrap.
- [x] **E6** Quality gates green.

### Phase F — Interface segregation of `ArtifactStorePort` (concern #4)

- [x] **F1** Split the ~40-method `ArtifactStorePort` (`application/ports.py:18`) into role contracts: `ArtifactLookup`, `ArtifactSearch`, `RelationshipGraph`, `RepositoryScopeResolver`, `ArtifactIndexLifecycle`, `ArtifactMutationObserver`.
- [x] **F2** The concrete index/store implements all; each consumer's type hints narrow to the contract(s) it actually uses.
- [x] **F3** Update `ArtifactRepository` and consumers to depend on the narrow contracts.
- [x] **F4** Quality gates green. (Independent of G; runs as its own work unit WU-09 — in DoD.)

### Phase G — Verifier pipeline refactor (concerns #4, #6)

- [ ] **G1** Extract pure rule functions operating on already-parsed inputs (frontmatter dicts, parsed PUML, catalog) returning `Issue` lists; orchestration composes them.
- [ ] **G2** Define application-owned ports for: filesystem inventory/loading, PlantUML/Java syntax execution, worker-pool scheduling, incremental-state persistence; move existing infra code behind adapters.
- [ ] **G3** Reduce `artifact_verifier.py` (822 lines) and `artifact_verifier_rules.py` (542 lines) below the policy hard limit where feasible; update `source_file_length.py` baselines downward as files shrink.
- [ ] **G4** Quality gates green. (Largest phase; split across dedicated work units WU-10..WU-12, executed after A–E land — **in DoD**.)

### Phase H — Immutability hardening (concern #6)

- [ ] **H1** Audit `@dataclass(frozen=True)` records carrying mutable `dict`/`list` (e.g. `EntityRecord.extra`, `display_blocks`); publish immutable views (`Mapping`, `tuple`, `frozenset`) across architectural boundaries; keep mutable builders local.
- [ ] **H2** Copy+freeze configuration when publishing it into a catalog.
- [ ] **H3** Ensure verification accumulates issues via returned values from pure functions rather than mutating shared result objects (overlaps G).
- [ ] **H4** Quality gates green.

### Phase I — Glossary & responsibility-driven renames (concern #7)

- [ ] **I1** Add a glossary (architecture doc / README §) distinguishing: ontology-&-diagram **Module Catalog**; **Artifact Index**; **Artifact Repository**; **Application Composition Root**; **Runtime Host**; **Verification Policy** vs **Verification Executor**.
- [ ] **I2** Rename only modules whose responsibilities changed in A–H (e.g. confirm `ModuleCatalog` vs self-model "Model Registry"; `diagram_type_registry`); avoid cosmetic churn elsewhere.
- [ ] **I3** Quality gates green.

### Phase J — Self-model & README sync (concern #8)

- [ ] **J1** Update self-model entities `APP@…yNhgdh` (**Model Registry**) and `APP@…ca3vm7` (**Model Verifier**) via MCP tools: their `Module:` properties cite `src/common/model_verifier_registry.py` / `src/common/model_verifier.py`, which **no longer exist**. Either remove implementation paths from these conceptual components or replace with accurate role-oriented descriptions + traceability properties pointing at real modules. Reconcile "Model Registry" naming with `ModuleCatalog` (D14/I2).
- [ ] **J2** Fix README `Repository Layout` to the real six-package structure (`domain/ application/ infrastructure/ config/ diagram_types/ ontologies/`) and correct the `Repository Layout` prose; also correct stale module-doc headers (e.g. `mcp_artifact_server.py` docstring referencing `src/common/` and `src/tools/`).
- [ ] **J3** Add a verifier check that flags self-model `Module:` source-path properties pointing at non-existent files (conformance guard).
- [ ] **J4** Quality gates green.

---

## 7. Quality Gates (every phase, run in order)

```bash
python -m pytest --tb=short -q          # 0 failures
ruff check src/ tests/                  # 0 errors (incl. E501)
uv run zuban check                      # passes
python -m pytest tests/architecture/test_dependency_policy.py -q   # policy holds
```

---

## 8. Definition of Done

- [ ] **No service locator / global registry singleton** remains (no `@lru_cache(maxsize=1)` registry accessors; no module-level mutable registries).
- [ ] `src/domain/` imports **only** `src/domain/` — verified by the AST architecture test, lazy imports included.
- [ ] The dependency matrix (§5) holds for **all six packages**; `architecture_baseline.json` is **empty**.
- [ ] `ModuleCatalogBuilder` + immutable `ModuleCatalog` exist; the builder rejects post-build registration; import-time `ENTITY_TYPES`/`CONNECTION_TYPES` snapshots are gone; the derivation registry has the same lifecycle.
- [ ] `RuntimeCatalogs` is built at all three composition roots (FastAPI app-state, CLI `main()`, MCP backend context) and injected; no consumer reaches a global.
- [ ] `DiagramTypeBase` lives in `src/diagram_types/_base.py`; `ontology_protocol.py` exports only Protocols/types; `infrastructure/diagram_type_registry.py` replaces `diagram_types.py`.
- [ ] `ArtifactStorePort` is segregated into role contracts; consumers depend on narrow ones. *(Phase F)*
- [ ] Verifier is a pipeline of pure rules over parsed inputs with I/O behind application-owned ports. *(Phase G)*
- [ ] Public contracts expose immutable views; configuration is frozen on publication. *(Phase H)*
- [ ] Glossary published; renames are responsibility-driven only. *(Phase I)*
- [ ] Self-model (`Model Registry`, `Model Verifier`) and README reflect the real implementation; a verifier conformance check guards self-model source paths. *(Phase J)*
- [ ] **No change to REST, MCP, or CLI surfaces.**

---

## 9. Sequencing & Feasibility Notes

- **Land first (low risk, high leverage):** A → B → C, with D and E folded in. This eliminates the entire `domain → infrastructure/config/ontologies` class of violations and removes all global state — the core of concerns #1–#3 and #5.
- **Larger, lower coupling — still in DoD:** **Phase F** (port segregation) and **Phase G** (verifier pipeline) are sizable and touch hot paths. They are **not** deferred out of scope; they run as their own work units (WU-09 for F; WU-10–12 for G) in later sessions once the foundation is in place. Their session boundaries are organisational, not scope boundaries.
- **Always last:** **I** and **J** must reflect the final shape of the code; doing them earlier risks re-drift.
- **Open follow-on (out of DoD):** E5 (diagram descriptor/renderer split) and Phase 3-style "every modification yields a new registry value" (vs freeze-after-build) are recorded as future refinements.

---

## 10. Open Questions

| # | Question | Default if unanswered |
|---|---|---|
| ~~OQ1~~ | ~~Do you want **F** and **G** inside this plan's DoD?~~ | **RESOLVED 2026-06-07: both F and G are in DoD.** Executed as their own work units (WU-09 = F; WU-10–12 = G) across later sessions per the execution ledger. |
| OQ2 | Glossary/dependency-policy home: dedicated `docs/architecture/` vs README section? | `docs/architecture/` + README pointer. |
| OQ3 | Confirm `ModuleCatalog`/`ModuleCatalogBuilder` naming (vs a "Model…" lineage aligned to the self-model's current "Model Registry"). | Use `ModuleCatalog`; reconcile self-model name to match. |
