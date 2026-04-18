# Two-Tiered Repo System + Global Entity Reference — Implementation Plan

## Status: Core implementation complete. Frontend work remaining.

---

## Completed

### Two-Tiered Repo — Backend

- **`arch-workspace.yaml`** — configured with both `engagement` (local) and `enterprise` (git) repos.
- **`src/tools/workspace_init.py`** — `arch-init` writes both `engagement_root` and `enterprise_root` to `.arch/init-state.yaml`.
- **`src/tools/gui_server.py`** — thin bootstrap (~75 lines); loads both repos via `ModelRepository([eng, ent])`.
- **`src/tools/gui_routers/state.py`** — shared server state, `init_state()`, `is_global()`, `get_write_deps()`, `resolve_grf()`.
- **`src/tools/gui_routers/entities.py`** — entity read/write endpoints; scope filter (global/engagement), GRF filtering from default view.
- **`src/tools/gui_routers/connections.py`** — connection endpoints; transparent GRF routing on add_connection.
- **`src/tools/gui_routers/diagrams.py`** — all diagram endpoints including preview/create/edit/svg/download; entity-display-search excludes GRFs.
- **`src/tools/gui_routers/promote.py`** — `/api/promote/plan` and `/api/promote/execute`.
- **`/api/entities?scope=global|engagement`** — scope filter; default hides GRFs.
- **`is_global` field** — on entity summary and detail responses for both GUI and MCP contexts.

### MCP Tools

- **`src/tools/model_mcp/write/entity.py`** — `model_write_help`, `model_create_entity`.
- **`src/tools/model_mcp/write/connection.py`** — `model_add_connection` with transparent GRF routing; `enterprise_root` optional param (defaults to init-state; engagement-only when explicit `repo_root` given without `enterprise_root`).
- **`src/tools/model_mcp/write/diagram.py`** — `model_create_matrix`, `model_create_diagram`.
- **`src/tools/model_mcp/write/promote.py`** — `model_promote_to_enterprise` with GRF replacement, `exclude_entities`/`exclude_connections` params.
- **`src/tools/model_mcp/write_tools.py`** — thin re-export facade (~30 lines).
- **`src/tools/mcp_model_server.py`** — re-exports `model_promote_to_enterprise`.

### Promotion Improvements

- **`PROMOTION_TRAVERSAL_TYPES`** in `promote_to_enterprise.py` — bidirectional closure traversal over structural/dependency relations.
- **`exclude_entity_ids`, `exclude_connection_ids`** — caller-prunable plan.
- **GRF exclusion from closure** — GRFs (`GRF@…`) are never promoted.
- **`promote_execute.py`** — full redesign with:
  - `make_target_resolver()` — functional closure resolver (GRF→real, keep, drop).
  - `_ConflictHandler` protocol + `_AcceptEnterpriseHandler`, `_AcceptEngagementHandler`, `_MergeHandler` via `_build_handler()`.
  - `_rewrite_outgoing()` — rewrites GRF targets in enterprise copy of outgoing files.
  - `_replace_engagement_entity_with_grf()` — after successful promotion, replaces original engagement entity with GRF proxy.
  - `_update_outgoing_references()` — regex-based update of engagement outgoing cross-references.

### Global Entity Reference (GRF)

- **`config/entity_ontology.yaml`** — `global-entity-reference` type: `prefix=GRF`, `domain=common`, `subdir=global-references`, no ArchiMate element type.
- **`src/common/model_write_formatting.py`** — `extra_frontmatter` param for non-standard frontmatter fields.
- **`src/tools/model_write/global_entity_reference.py`** — `ensure_global_entity_reference()`, `find_existing_grf()`, `build_grf_map()`.
- **`src/tools/model_write/entity.py`** — blocks direct creation of `global-entity-reference`.
- **`src/common/_verifier_rules_grf.py`** — E140 (missing `global-entity-id`), E141 (bad global ID), W141 (enterprise not loaded).
- **`src/common/_verifier_rules_schema.py`** — JSON Schema and attribute validation rules (split from model_verifier_rules.py).
- **`src/common/model_verifier_rules.py`** — imports from split files; down to ~270 lines.
- **`src/common/model_verifier.py`** — calls `check_global_entity_reference` for GRF entities.
- **GRF transparency** — `_connection_to_dict()` resolves GRF targets to global entity IDs; `entity_display_search` excludes GRFs; default entity list excludes GRFs.
- **Attribute schema** — `attributes.global-entity-reference.schema.json` in engagement repo.

### Refactoring (line-count reduction)

| File | Before | After | How |
|---|---|---|---|
| `src/tools/gui_server.py` | 959 | 75 | Extracted to `src/tools/gui_routers/` |
| `src/tools/model_mcp/write_tools.py` | 468 | 30 | Extracted to `src/tools/model_mcp/write/` |
| `src/tools/generate_macros.py` | 482 | 239 | SVG conversion to `_svg_sprite_convert.py` |
| `src/common/model_verifier_rules.py` | 439 | 273 | Schema/GRF rules to separate files |
| `src/common/model_query_repository.py` | 692 | 524 | Helper functions to `_model_query_helpers.py` |

Remaining over 350 lines (internally modular, no clean split boundary):
- `promote_execute.py` (491) — cohesive single operation
- `model_verifier.py` (486) — incremental logic tightly coupled to verifier state
- `framework_query/index.py` (382) — pre-existing, not in scope

### Tests (81 total, all passing)

New test files:
- **`tests/tools/test_two_repo_and_grf.py`** — 21 tests: two-repo loading, GRF creation/reuse, verifier rules E140/E141/W141, `model_add_connection` transparent routing, promotion plan/execute round-trip.
- **`tests/tools/test_verifier.py`** — 16 tests: `verify_entity_file`, `verify_outgoing_file`, `verify_all` (single and two-repo).
- **`tests/tools/test_edit_tools.py`** — 12 tests: entity edit (name/status/keywords/nonexistent), connection remove, diagram edit.
- **`tests/tools/test_workspace_init.py`** — 11 tests: config parsing, repo resolution, state write/load.
- **`tests/tools/test_promotion_mcp.py`** — 8 tests: dry-run plan, conflict detection, live execution, GRF outgoing rewrite.
- **`tests/tools/conftest.py`** — `autouse` fixture clearing MCP context LRU caches and init-state between tests.

Test infrastructure:
- `ARCH_SKIP_PUML_SYNTAX=1` set in conftest — prevents JVM resource contention from causing flaky failures when running full suite.
- `src/common/model_verifier_syntax.py` — respects `ARCH_SKIP_PUML_SYNTAX` env var.

---

### Admin Mode

- **`src/tools/model_write/boundary.py`** — `assert_enterprise_write_root()` added (inverse of engagement guard).
- **`src/tools/model_write/admin_ops.py`** — completely separate implementation of entity/connection/diagram writes targeting the enterprise root. Calls `assert_enterprise_write_root` at every entry point. Never called by MCP tools or standard GUI endpoints.
- **`src/tools/gui_routers/admin.py`** — admin-mode write endpoints at `/admin/api/*`: entity create/edit, connection add/remove, diagram create. Gated by `_require_admin()` (403 if not in admin mode). All write calls go through `admin_ops.py` only.
- **`src/tools/gui_routers/state.py`** — `_admin_mode` flag, `is_admin_mode()`, `get_admin_write_deps()` (returns enterprise root; raises 403 if admin mode off).
- **`src/tools/gui_server.py`** — `--admin-mode` CLI flag; logs warning at startup; prints `git commit` reminder. Admin router always registered but endpoints gate on admin mode.
- **`App.vue`** — fetches `/admin/api/server-info` on mount; shows a persistent dark-red banner with `git commit` reminder when admin mode is active.
- **`EntityDetailView.vue`** — Edit button visible for global entities when admin mode active; routes to admin endpoint; dark-red button style for admin edits.

**Boundary invariant** — `assert_engagement_write_root` is unconditional in all standard write functions (entity.py, connection.py, entity_edit.py, connection_edit.py, diagram.py). `admin_ops.py` never calls those functions — it calls the shared formatting/verification layer directly and asserts `assert_enterprise_write_root` at its own entry. No bypass parameter exists anywhere.

### Broken-Reference Cleanup

- **`src/tools/model_write/cleanup_broken_refs.py`** — finds GRFs whose `global-entity-id` no longer exists in the enterprise repo; removes all connections pointing to broken GRFs; deletes the GRF files. Dry-run by default.
- **Entry points**:
  - CLI: `uv run python -m src.tools.model_write.cleanup_broken_refs [--execute] [--json]`
  - REST: `POST /api/cleanup-broken-refs` (GUI, not MCP)
- **`tests/tools/test_admin_mode.py`** — 9 tests: boundary guard correctness (both directions), admin_ops dry-run success, cleanup dry-run reporting, cleanup execution, non-broken GRFs untouched, empty-report case.

## Remaining Work

### Additional Test Coverage

- **`generate_macros`** — macro generation for both single and dual-repo setups.
- **`model_verifier_incremental`** — incremental state detection and cache usage.
- **GUI endpoints** — integration tests via Docker/TestClient (FastAPI not locally available).

### Frontend (GUI — Docker) — Completed

- **`App.vue`** — nav split: Engagement (Browse / Diagrams / Search / ↑ Promote) and Global (Browse / Search) sections with amber highlight for global entries.
- **`HomeView.vue`** — side-by-side engagement + global stats cards; engagement domain breakdown; links into both scopes; shows "no global entities yet" message with promotion hint.
- **`EntitiesView.vue`** — accepts `scope` prop; shows "Global" badge and read-only subtitle; hides Create button in global scope; amber row tint + "global" chip for global entities mixed into engagement view.
- **`SearchView.vue`** — accepts `scope` prop; shows "global" chip on hits from enterprise repo.
- **`PromoteView.vue`** — 3-step promotion flow: (1) pick entity via search, (2) review/prune closure with checkboxes for entities and connections, resolve conflicts per-entity (keep global / replace with engagement), (3) execute with file summary. Pre-populates when navigated to with `?entity_id=`.
- **`EntityDetailView.vue`** — "↑ Promote to Global" button for engagement entities; "Global" badge for enterprise entities; back link goes to correct scope.
- **`domain/schemas.ts`** — `is_global` on `EntitySummarySchema`, `EntityDetailSchema`, `SearchHitSchema`; `PromotionPlanSchema`, `PromotionResultSchema`, `PromotionConflictSchema`.
- **`ports/ModelRepository.ts`** — `scope` on `ListParams`; `planPromotion`, `executePromotion`.
- **`adapters/http/HttpModelRepository.ts`** — all new calls wired.
- **`application/ModelService.ts`** — passthrough for all new methods.
- **`/api/search`** — now includes `is_global` on entity hits.
- **Pre-existing build error fixed** — `npm install` ensures `d3-hierarchy` (declared in `package.json`) is present in `node_modules`.

### MCP Context Scope Semantics

The `model_add_connection` enterprise-root detection logic (engagement-only when `repo_root` is explicit but `enterprise_root` is not) is a pragmatic test-isolation fix. Reconsider whether to always load init-state enterprise root for production use — currently: when only `repo_root` is given explicitly, enterprise is not loaded (correct for tests; acceptable for production since MCP users typically call without explicit `repo_root`).

### Additional Test Coverage

- **`generate_macros`** — macro generation for both single and dual-repo setups.
- **`model_verifier_incremental`** — incremental state detection and cache usage.
- **GUI endpoints** — integration tests via Docker/TestClient (FastAPI not locally available).

---

## Architecture Decisions

### GRF as a per-engagement proxy (not a global concept)
GRFs are local stubs so the engagement repo stays self-consistent. They are auto-created transparently when a connection to a global entity is requested. Promoted entities are replaced by GRFs so all existing connections in the engagement repo continue to resolve.

### Transparent GRF in all tool interfaces
All tool interfaces (MCP `model_add_connection`, GUI `/api/connection`, `_connection_to_dict`, `entity_display_search`) handle GRFs transparently — users and AI agents see global entity IDs, not GRF IDs.

### Strategy pattern in promote_execute.py
`_ConflictHandler` protocol with three implementations dispatched via `_build_handler(resolution)`. Extensible without modifying the main execution loop.

### Functional `TargetResolver` in outgoing rewrite
`make_target_resolver(grf_map, promoted_ids, enterprise_ids)` builds a `str → str | None` function encoding all target-mapping logic. Independently testable from the file-walking logic.

### `ARCH_SKIP_PUML_SYNTAX` env var
PlantUML syntax checking is a JVM-based integration concern. Setting this env var in tests prevents flaky failures from JVM resource contention when many tests run in the same process.
