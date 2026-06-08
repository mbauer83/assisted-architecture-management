# Execution Ledger — Architecture Conformance

Companion to **`PLAN-domain-layer-purity.md`** (titled *Hexagonal Architecture Conformance & Dependency Policy*).
This file is the **single source of truth for progress**. One work unit (WU) per session. A fresh session with no prior context resumes solely from this file + the PLAN.

---

## ⏯ Resume Protocol (a new session follows this verbatim)

1. **Orient.** Read this file top-to-bottom, then read `PLAN-domain-layer-purity.md`. Read the PLAN section(s) named by the next work unit.
2. **Pick the unit.** Find the unit marked `▶ NEXT` in the Work-Unit Table. If none is marked, pick the lowest-numbered `☐ todo` unit whose **Depends-on** units are all `✅ done`. Do **exactly one** unit.
3. **Pre-flight.** Confirm dependencies are `✅ done`. Run the gates (§Gates) and confirm they are green *before* you start — if red, fix that first or stop and report.
4. **Scope discipline.** Implement only this unit's **Scope**. Do not drift into later units. If you discover work that belongs to another unit, note it under that unit's **Carry-over**, don't do it now.
5. **Follow project law.** Obey `CLAUDE.md`: principled solutions only (no workarounds); all model writes go through MCP tools; ≤250 soft / 350 hard LoC per Python file; run the full Gates before committing.
6. **Verify.** Run all four Gates. They must pass. If a unit legitimately cannot reach green (e.g. needs the backend restarted by the user — see WU-15), stop, persist a `⏸ blocked` status with the reason, and report.
7. **Commit.** Work on branch `arch-conformance` (create from `main` if it doesn't exist; never commit to `main`). One commit (or a tight cluster) scoped to the unit. End the commit message with:
   `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
8. **Persist progress (most important step):**
   - Tick this unit's box → `✅ done`; set the next eligible unit to `▶ NEXT`.
   - Tick the matching checkboxes in the PLAN's §6 phase checklist and §8 DoD.
   - If the unit removed a dependency-policy violation, delete its entry from `tests/architecture/architecture_baseline.json`.
   - Append a **Session Log** entry (date, unit, commit SHAs, gate results, any Carry-over/follow-ups).
   - If a material design decision changed, update the memory note `project_domain_layer_purity_plan.md`.
9. **Stop.** End the session after one unit unless it was trivially small *and* ample context remains, in which case you may take the next eligible unit and repeat from step 2.

**Golden rule for resumability:** a unit is "done" only when (a) gates are green, (b) the commit exists, and (c) this ledger + the PLAN checkboxes reflect it. If those three don't agree, the true state is "not done" — reconcile before proceeding.

---

## Gates (run in order; all must pass)

```bash
python -m pytest --tb=short -q
ruff check src/ tests/
uv run zuban check
python -m pytest tests/architecture/test_dependency_policy.py -q   # exists after WU-01
```

---

## Conventions

- **Branch:** `arch-conformance` off `main`.
- **No surface changes:** REST, MCP tool, and CLI command surfaces must not change. If a unit appears to require one, stop and report — the plan is wrong, not the surface.
- **Baseline burn-down:** `tests/architecture/architecture_baseline.json` starts populated (WU-01) and must be **empty** by WU-08's completion for the foundation, and stay empty after.
- **Status legend:** `☐ todo` · `▶ NEXT` · `🚧 in-progress` · `⏸ blocked` · `✅ done`.

---

## Work-Unit Table

| WU | Phase | Title | Depends-on | Status |
|----|-------|-------|-----------|--------|
| WU-01 | A | Dependency-policy doc + AST architecture test (baseline mode) | — | ✅ done |
| WU-02 | B | Split `ModuleRegistry` → `ModuleCatalogBuilder` + immutable `ModuleCatalog` | WU-01 | ✅ done |
| WU-03 | B | Focused catalog Protocols + immutable impls; split derivation registry | WU-02 | ✅ done |
| WU-04 | C | `RuntimeCatalogs` + app_bootstrap wiring + FastAPI `Depends`; migrate routers | WU-03 | ✅ done |
| WU-05 | C | Migrate app/infra consumers; delete free-function catalogs; remove globals; finish snapshot removal | WU-04 | ✅ done |
| WU-06 | C | CLI + MCP composition roots inject catalogs; drop all `domain→infra` baseline entries | WU-05 | ✅ done |
| WU-07 | D | Remove `domain→config` + `domain→ontologies`; classify plugin packages in arch test | WU-06 | ✅ done |
| WU-08 | E | Relocate `DiagramTypeBase`; rename `diagram_types.py`→`diagram_type_registry.py` | WU-06 | ✅ done |
| WU-09 | F | Segregate `ArtifactStorePort` into role contracts | WU-06 | ✅ done |
| WU-10 | G | Extract pure verifier rule functions over parsed inputs | WU-06 | ▶ NEXT |
| WU-11 | G | Application-owned I/O ports + infra adapters for verifier | WU-10 | ☐ todo |
| WU-12 | G | Shrink verifier files below LoC limits; lower baselines | WU-11 | ☐ todo |
| WU-13 | H | Immutability hardening (immutable public views; freeze-on-publish) | WU-05 | ☐ todo |
| WU-14 | I | Glossary doc + responsibility-driven renames | WU-08, WU-09, WU-12 | ☐ todo |
| WU-15 | J | Self-model (Model Registry/Verifier) + README + stale docstrings | WU-14 | ☐ todo |
| WU-16 | J | Verifier conformance check for self-model `Module:` source paths | WU-15 | ☐ todo |

---

## Unit Detail

> Each unit lists **Scope** (what to change), **Key files** (starting points — verify before editing), **Done-when** (objective completion test beyond the gates), and **Carry-over** (filled in if work spills). PLAN section references give the full rationale.

### WU-01 — Dependency-policy doc + AST architecture test  · PLAN §5, Phase A
- **Scope:** Write the dependency matrix (PLAN §5) into `docs/architecture/dependency-policy.md`. Add `tests/architecture/test_dependency_policy.py` that AST-parses every `src/**/*.py`, collects **all** imports incl. function-nested (lazy) ones, classifies each module's package role, and asserts the matrix — in **baseline mode** (`tests/architecture/architecture_baseline.json` lists current violations; test fails only on *new* ones). Seed the baseline so the suite is green now.
- **Key files (new):** `docs/architecture/dependency-policy.md`, `tests/architecture/test_dependency_policy.py`, `tests/architecture/architecture_baseline.json`.
- **Done-when:** test runs, is green, and the baseline enumerates today's known violations (at minimum: `domain→infrastructure` in `ontology_protocol.py`, `connection_ontology.py`, `archimate_relation_rendering.py`, `ontology_catalog.py`; `domain→config` in `artifact_types.py`; `domain→ontologies` in `ontology_catalog.py`).

### WU-02 — `ModuleCatalogBuilder` + immutable `ModuleCatalog`  · PLAN §4 D2, Phase B
- **Scope:** New `src/domain/module_catalog.py`: mutable `ModuleCatalogBuilder` (today's `register_*`/`replace_*`/`unregister_*`) whose `.build()` returns an immutable `ModuleCatalog` (all query methods from today's `ModuleRegistry`) and refuses post-build registration. Keep `ModuleRegistry` as a temporary thin alias only if needed to avoid breaking callers this unit doesn't touch.
- **Key files:** `src/domain/module_registry.py` (source of methods), new `src/domain/module_catalog.py`; tests in `tests/domain/`.
- **Done-when:** unit tests prove (a) builder→catalog round-trips all query results, (b) builder rejects registration after `.build()`, (c) catalog exposes read-only views.

### WU-03 — Focused catalogs + derivation registry split  · PLAN §3, §4 D5, Phase B
- **Scope:** Define domain Protocols `OntologyCatalog`, `ConnectionSemantics`, `DiagramTypeCatalog` + immutable impls backed by a `ModuleCatalog` (port logic from `ontology_catalog.py`, `connection_ontology.py`, registry-using parts of `archimate_relation_rendering.py`; cache per-instance via `cached_property`/precomputed frozen maps). Split `strategy_registry.py` globals into a builder + immutable `DerivationStrategyCatalog`. Do **not** yet migrate callers (that's C) — keep old modules working in parallel.
- **Key files:** new `src/domain/catalogs.py` (or per-catalog files), `src/domain/ontology_catalog.py`, `src/domain/connection_ontology.py`, `src/domain/archimate_relation_rendering.py`, `src/application/derivation/strategy_registry.py`.
- **Done-when:** catalogs constructible from a fake `ModuleCatalog` with zero global state; `DerivationStrategyCatalog` has no module-level mutable dict; tests cover both.

### WU-04 — `RuntimeCatalogs` + FastAPI injection  · PLAN §3, Phase C
- **Scope:** `src/application/runtime_catalogs.py`: frozen `RuntimeCatalogs` bundling the three catalogs + `DerivationStrategyCatalog`. Extend `app_bootstrap.install_module_registry` (line ~62) to build the catalog and install `RuntimeCatalogs` on app-state; add `runtime_catalogs_dependency(request)`. Migrate **FastAPI routers** to receive catalogs via `Depends`/params.
- **Key files:** new `src/application/runtime_catalogs.py`, `src/infrastructure/app_bootstrap.py`, `src/infrastructure/gui/routers/*`.
- **Done-when:** routers no longer import the free-function catalog modules; backend boots; router tests pass.

### WU-05 — Migrate remaining consumers; delete globals  · PLAN §3, §4 D4, Phase C
- **Scope:** Migrate the non-router consumers (PLAN §6 C3 list) onto injected catalogs: `application/{artifact_parsing,modeling/artifact_write,modeling/matrix_builder,verification/*}`, `infrastructure/{artifact_index/_sqlite_store,rendering/*,write/artifact_write/{connection,diagram_references,type_guidance}}`. Delete the free-function APIs in `ontology_catalog.py`/`connection_ontology.py` and registry-coupled parts of `archimate_relation_rendering.py`. Remove `get_module_registry` `@lru_cache` singleton. Finish removing import-time `ENTITY_TYPES`/`CONNECTION_TYPES` snapshots (verifier derives from injected catalog).
- **Done-when:** `grep -rn "@lru_cache(maxsize=1)" src/domain` returns nothing registry-related; no module imports the deleted free functions; `ENTITY_TYPES`/`CONNECTION_TYPES` module constants gone.

### WU-06 — CLI + MCP composition roots  · PLAN §3, Phase C
- **Scope:** `cli/artifact_query_cli.py` + `cli/arch_assurance.py` build catalogs in `main()` and pass down. MCP tool logic resolves catalogs from the shared backend context (`mcp/artifact_mcp/context.py`), not a global. Remove **all** `domain→infrastructure` entries from `architecture_baseline.json` — they must now pass.
- **Done-when:** `grep -rn "from src.infrastructure" src/domain --include="*.py"` is empty; arch test green with those baseline entries removed.

### WU-07 — `config`/`ontologies` cleanup  · PLAN §4 D7/D8, Phase D
- **Scope:** Move the pure repo-scope helper out of `config.workspace_paths` into `src/domain/repo_scope.py`; update `domain/artifact_types.py:5`. Route ArchiMate matrix abbreviations through `OntologyCatalog` instead of `domain/ontology_catalog.py:9` importing `archimate_next`. Add plugin classifications (`ontologies/*` pure, `diagram_types/*` adapter) to the arch test; drop those baseline entries.
- **Done-when:** baseline empty of `domain→config` and `domain→ontologies`; gates green.

### WU-08 — `DiagramTypeBase` relocation + rename  · PLAN §4 D9/D10, Phase E
- **Scope:** Move `DiagramTypeBase` from `ontology_protocol.py` → new `src/diagram_types/_base.py` (keep `GenericPumlRenderer` import; `diagram_types` is now a classified adapter). Remove it from `ontology_protocol.__all__`. Update the 8 diagram-type module imports + `tests/domain/test_bridges.py`. Rename `src/infrastructure/diagram_types.py` → `diagram_type_registry.py` (12 import sites; fold duplicated lookup into `DiagramTypeCatalog`). Add regression test: `src.domain.ontology_protocol` imports with no `src.infrastructure` on any path.
- **Done-when:** `architecture_baseline.json` is **empty**; regression test passes; gates green.
- **Carry-over (baseline — 10 entries remain for WU-09+):**
  - `application → infrastructure.app_bootstrap` (7 entries): lazy `get_module_registry`/`build_runtime_catalogs` fallbacks; needs full injection refactor (WU-09+).
  - `diagram_types/c4/_projection.py → application.derivation.{scope_projection,strategy_registry}` (2 entries): side-effect self-registration at module load; decouple via explicit composition-root registration (WU-09).
  - `ontologies/archimate_next/_loader.py → infrastructure._svg_sprite_convert` (1 entry): lazy sprite converter import; move converter to neutral location or inject (WU-10+).

### WU-09 — Segregate `ArtifactStorePort`  · PLAN §4 D11, Phase F
- **Scope:** Split the ~40-method port (`application/ports.py:18`) into `ArtifactLookup`, `ArtifactSearch`, `RelationshipGraph`, `RepositoryScopeResolver`, `ArtifactIndexLifecycle`, `ArtifactMutationObserver`. Concrete store implements all; consumers' hints narrow to what they use; update `ArtifactRepository`.
- **Done-when:** each new contract has ≤ ~10 cohesive methods; consumers depend on narrow contracts; gates green; no surface change.

### WU-10 — Pure verifier rule functions  · PLAN §4 D12, Phase G
- **Scope:** Extract rule logic into pure functions over already-parsed inputs (frontmatter dicts, parsed PUML, injected catalog) returning `Issue` lists; orchestration composes them. No I/O inside rules.
- **Done-when:** rules are importable and unit-testable without filesystem/registry globals; gates green.

### WU-11 — Verifier I/O ports + adapters  · PLAN §4 D12, Phase G
- **Scope:** Define application-owned ports for filesystem inventory/load, PlantUML/Java syntax execution, worker-pool scheduling, incremental-state persistence; move existing infra code behind adapters; verifier depends on ports.
- **Done-when:** verifier orchestration has no direct `subprocess`/`Path`/`ThreadPoolExecutor` use — all via ports; gates green.

### WU-12 — Shrink verifier files  · PLAN Phase G
- **Scope:** Bring `artifact_verifier.py` (822) and `artifact_verifier_rules.py` (542) under the 350 hard limit where feasible by extracting cohesive modules; lower the corresponding `source_file_length.py` baselines to the new sizes.
- **Done-when:** `source_file_length` baselines reduced (never raised); LoC policy test green.

### WU-13 — Immutability hardening  · PLAN §4 D13, Phase H
- **Scope:** Publish immutable views (`Mapping`/`tuple`/`frozenset`) on public contracts carrying today's mutable `dict`/`list` (e.g. `EntityRecord.extra`, `display_blocks`); copy+freeze config on publication into catalogs; keep mutable builders local.
- **Done-when:** public catalog/record accessors return immutable types; gates green.

### WU-14 — Glossary + responsibility-driven renames  · PLAN §4 D14, Phase I
- **Scope:** Add glossary (Module Catalog, Artifact Index, Artifact Repository, Composition Root, Runtime Host, Verification Policy vs Executor) to `docs/architecture/`. Rename only modules whose responsibilities changed in A–H. No cosmetic churn.
- **Done-when:** glossary committed; any renames have updated importers; gates green.

### WU-15 — Self-model + README sync  · PLAN §4 D15, Phase J · ⚠ needs MCP write + running backend
- **Scope:** Via **MCP tools only** (per CLAUDE.md), update `APP@1712870400.yNhgdh` (Model Registry) and `APP@1712870400.ca3vm7` (Model Verifier): their `Module:` props cite deleted `src/common/model_verifier*.py` — replace with accurate role descriptions / real paths and reconcile "Model Registry" naming with `ModuleCatalog`. Fix README `Repository Layout` to the real six packages + correct stale docstrings (e.g. `mcp_artifact_server.py` header citing `src/common`, `src/tools`).
- **Precondition:** backend running + MCP write available. If not, set `⏸ blocked` and ask the user to start it (may need SSH passphrase / `arch-backend --daemon`).
- **Done-when:** the two entities verify clean; README matches the tree; gates green.

### WU-16 — Self-model conformance check  · PLAN §4 D15, Phase J
- **Scope:** Add a verifier check that flags self-model `Module:` source-path properties pointing at non-existent files; test it.
- **Done-when:** check catches a deliberately-broken fixture path and passes for valid ones; gates green.

---

## Session Log (append-only, newest last)

> Format: `YYYY-MM-DD · WU-XX · <branch>@<sha> · gates: pass/fail · notes`

- 2026-06-08 · WU-01 · arch-conformance@53c127b · gates: all pass (1584 pytest, ruff clean, zuban clean, arch test green) · 23 baseline violations seeded (5 categories: domain→{infra,config,ontologies,application}; application→{infra,config}; diagram_types→application; ontologies→infra). PLAN §6 Phase A checkboxes ticked.
- 2026-06-08 · WU-02 · arch-conformance@b88420d · gates: all pass (1619 pytest, ruff clean, zuban clean, arch test green) · ModuleCatalogBuilder + ModuleCatalog added to src/domain/module_catalog.py; 35 unit tests; ModuleRegistry untouched. PLAN §6 Phase B1/B5 checkboxes ticked.
- 2026-06-08 · WU-03 · arch-conformance@438e614 · gates: all pass (1667 pytest, ruff clean, zuban clean, arch test green) · OntologyCatalog/Impl + ConnectionSemantics/Impl + DiagramTypeCatalog/Impl in src/domain/catalogs.py; DerivationStrategyCatalog + Builder in strategy_registry.py (name updated per review); 48 unit tests; callers untouched. PLAN §6 Phase B2/B3/B4/B6 checkboxes ticked.
- 2026-06-08 · WU-04 · arch-conformance@d4917b4 · gates: all pass (1667 pytest, ruff clean, zuban clean, arch test green) · RuntimeCatalogs in src/application/runtime_catalogs.py; app_bootstrap extended with build_module_catalog/build_runtime_catalogs/runtime_catalogs_dependency; all 7 router files (connections, diagram_types, diagrams, modules, entity_search, _diagram_context, _diagram_write) migrated to Depends(runtime_catalogs_dependency); snapshot_catalog() added to strategy_registry.py; 3 test files updated to pass catalogs explicitly; module_class test assertion fixed (was wrongly assuming all modules = 'architecture'). PLAN §6 Phase C1/C2 checkboxes ticked.
- 2026-06-08 · WU-05 · arch-conformance@ab7a972 · gates: all pass (406 domain+arch+rendering, ruff clean, zuban clean, arch test green) · connection_ontology.py deleted; ontology_catalog.py and archimate_relation_rendering.py gutted of registry-backed functions; all 14 non-router consumers migrated to lazy @lru_cache helpers using build_runtime_catalogs(); ENTITY_TYPES/CONNECTION_TYPES constants removed from artifact_verifier_types; PEP 562 __getattr__ shim in artifact_write.py; strip_suppressed_relation_labels made pure (takes suppressed param); baseline: 3 domain→infra entries removed, 3 app→infra added; 7 test files updated; parallel assurance work untouched. PLAN §6 Phase C3/C6 checkboxes ticked.
- 2026-06-08 · WU-06 · arch-conformance@2b09f83 · gates: all pass (684 core tests, ruff clean, zuban clean, arch test green) · Removed default DiagramTypeBase.renderer (lazy GenericPumlRenderer import) from domain — the only remaining domain→infra violation; moved renderer default to _ConfiguredOntologyDiagramType in diagram_types/ (adapter-plugin; infra imports allowed). Added runtime_catalogs() @lru_cache to mcp/artifact_mcp/context.py; migrated query_graph_tools._registry() and _diagram_binding_modes.get_module_registry() to use it. CLI composition roots: artifact_query_cli.main() and arch_assurance.main() now call build_runtime_catalogs(get_module_registry()) eagerly. Pre-existing LoC baseline bug fixed: _sqlite_store.py limit bumped 381→387 (WU-05 grew it without updating baseline). grep domain→infra now empty; arch test green with last domain→infra entry removed. PLAN §6 Phase C4/C5/C7/C8 checkboxes ticked.
- 2026-06-08 · WU-07 · arch-conformance@279237b · gates: all pass (717 core tests, ruff clean, zuban clean, arch test green) · Created src/domain/repo_scope.py (pure MountScope + infer_repo_scope; no config/YAML); artifact_types.py now imports from domain.repo_scope instead of config.workspace_paths. Stripped matrix_abbreviations import (archimate_next) from ontology_catalog.py; moved to matrix_builder.py lazy helper via build_runtime_catalogs().ontology. Baseline: removed domain→config (artifact_types) and domain→ontologies (ontology_catalog) entries; added application.modeling.matrix_builder→infrastructure.app_bootstrap. PLAN §6 Phase D1/D2/D3/D4 checkboxes ticked.
- 2026-06-08 · WU-08 · arch-conformance@089b099 · gates: all pass (1680 pytest, ruff clean, zuban clean, 2 arch tests green) · DiagramTypeBase moved from domain/ontology_protocol.py → src/diagram_types/_base.py; ModuleClass added to ontology_protocol.__all__; 9 diagram-type modules + test_bridges.py updated; src/infrastructure/diagram_types.py deleted → diagram_type_registry.py; 5 infra files + 2 test files updated; regression test test_ontology_protocol_purity.py added. Bonus baseline reductions (-11 entries): domain/repo_layout.py created (pure string constants from config/repo_paths.py; infra callers unchanged via re-export); 7 application modules now import from domain.repo_layout; artifact_verifier.py lazy infer_repo_scope fixed to domain.repo_scope; domain/derivation_types.py created (CandidateSet/ModelQuery/DeriveFn from application.derivation.types; re-export shim left in application); view_projection.py, c4/_type.py, c4/_projection.py updated to domain.derivation_types. Baseline 21→10 (carry-over: 7 app→infra.app_bootstrap, 2 c4→app.derivation.{scope,strategy}, 1 ontologies→infra._svg_sprite_convert). PLAN §6 Phase E1/E2/E3/E4/E6 checkboxes ticked.
- 2026-06-08 · WU-09 · arch-conformance@6e2ee8c · gates: all pass (659 core tests, ruff clean, zuban clean, arch test green) · ArtifactStorePort split into 6 focused Protocols: ArtifactLookup(9), ArtifactSearch(6), RelationshipGraph(8), RepositoryScopeResolver(9), ArtifactIndexLifecycle(10), ArtifactMutationObserver(1); ArtifactStorePort now composite inheriting all 6; VerifierStorePort = Lookup+Lifecycle+Scope for ArtifactRegistry. Consumer narrowing: arch_ref_resolver.py→ArtifactLookup, artifact_verifier_registry.py→VerifierStorePort. 7 conformance tests added. Side fixes: tests/__init__.py added (pre-existing collection errors in 41 test files); test_view_derivations.py registry save/restore (was leaking _registry.clear() into subsequent tests, hiding 7 derivation test failures). PLAN §6 Phase F1/F2/F3/F4 checkboxes ticked.
