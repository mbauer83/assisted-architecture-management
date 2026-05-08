# Implementation Plan: Entity-Spec Refactor + Activity Diagrams

**Status tracking:** check boxes below — tick as each step completes.
**Resume guidance:** find the first unchecked box and continue from there.
**Constraints:** no backwards compatibility; migrate everything; ruff + zuban + tests green.

**Phase 1 status: COMPLETE** — all steps ✅, tests green, entities and PUML files migrated.  
**Phase 2 design: COMPLETE** — full design in `diagram-kind-ui-authoring-rfc.md` (approved).  
**Next action:** implement Phase 2 starting at Step 2.1.

---

## Key Design Decisions

### `hierarchy` field
- `EntityTypeInfo.hierarchy: tuple[str, ...]` — full path from `model/` to type-specific dir.
- **YAML specifies only domain-level segments** — e.g. `hierarchy: [motivation]`.
- **Loader appends `artifact_type` as final element** — e.g. stored as `("motivation", "stakeholder")`.
- Filesystem path: `MODEL / Path(*info.hierarchy) / f"{eid}.md"` → `model/motivation/stakeholder/{id}.md`
- `hierarchy[0]` replaces `domain_dir`; `hierarchy[-1]` replaces `subdir`.

### `archimate_element_type` removal
- Removed from `EntityTypeInfo` entirely.
- Sprite/stereotype key derived as `artifact_type.replace("-", "_")` (e.g. `system_software`).
- No override field needed — we control both sprite naming and the stylesheet.

### `has_sprite` removal
- Removed from `EntityTypeInfo`.
- Predicate becomes `ontology.sprite_for(artifact_type) is not None`.

### `OntologyModule` protocol additions
```python
display_section_id: str          # e.g. "archimate" → ### archimate in entity MD
render_display_section(artifact_type, name, alias) -> str   # generates display block content
extract_display_section(section_content) -> dict | None     # parses it back out
sprite_for(artifact_type) -> str | None                     # PlantUML sprite line or None
```

### `format_entity_markdown` change
- Signature changes: `display_archimate: dict[str, str]` → `display_section_id: str, display_content: str`.
- Hardcoded `### archimate` removed; section header uses `display_section_id`.

### Diagram-kind filter config
- `accepted_domains: [...]` replaced by expressive `filter:` block:
  ```yaml
  filter:
    hierarchy_level:        # structural: hierarchy[index] must be in values
      index: 0
      values: [motivation, common]
  ```
- Filters are evaluated by `accepts_entity_type()`.

### Sprite ownership
- ArchiMate ontology module provides `sprite_for(artifact_type)`.
- Module reads from `archimateGlyphs.json` (GUI source kept as-is; the layer violation is fixed by routing through the module).
- Sprite names change from PascalCase (`$archimate_Stakeholder`) to snake_case (`$archimate_stakeholder`).

### Display block after refactor
- Before: `domain:`, `element-type:`, `label:`, `alias:` in archimate block.
- After: only `label:` and `alias:` — `domain` and `element-type` derived at render time.
- Migration strips `domain:` and `element-type:` from all existing entity display blocks.

### MCP tool output
- `domain`/`subdir`/`archimate_element_type`/`archimate_domain` removed.
- `hierarchy: list[str]` and `ontology: str` added.

---

## Phase 1: Entity-Spec Refactor

### Step 1.1 — `EntityTypeInfo` dataclass ✅
- **File:** `src/domain/ontology_types.py`
- Remove: `domain_dir`, `subdir`, `archimate_element_type`, `has_sprite`
- Add: `hierarchy: tuple[str, ...]`
- Convenience properties: none — callers use `hierarchy[0]` / `hierarchy[-1]` directly.

### Step 1.2 — `OntologyModule` protocol ✅
- **File:** `src/domain/ontology_protocol.py`
- Add `display_section_id: str` property.
- Add `render_display_section(artifact_type: str, name: str, alias: str) -> str`.
- Add `extract_display_section(section_content: str) -> dict | None`.
- Add `sprite_for(artifact_type: str) -> str | None`.
- Update `DiagramKindBase` if affected.

### Step 1.3 — `ModuleRegistry` ✅
- **File:** `src/domain/module_registry.py`
- `domain_order()`: use `et.hierarchy[0]` instead of `et.domain_dir`.

### Step 1.4 — `ontology_catalog.py` ✅
- **File:** `src/domain/ontology_catalog.py`
- `known_domain_names()`: use `info.hierarchy[0]`.

### Step 1.5 — `format_entity_markdown` ✅
- **File:** `src/application/modeling/artifact_write_formatting.py`
- Change signature: `display_archimate: dict[str, str]` → `display_section_id: str, display_content: str`.
- Remove hardcoded `### archimate`; use `display_section_id` as section header.

### Step 1.6 — ArchiMate NEXT `entities.yaml` ✅
- **File:** `src/ontologies/archimate_next/entities.yaml`
- Replace `domain: X` + `subdir: Y` with `hierarchy: [X]` for each type.
- Remove `archimate_element_type` from all entries.
- Remove `has_sprite` from all entries.

### Step 1.7 — ArchiMate NEXT `_loader.py` ✅
- **File:** `src/ontologies/archimate_next/_loader.py`
- Parse `hierarchy` list; append `artifact_type` as final element → `EntityTypeInfo.hierarchy`.
- Remove parsing of `archimate_element_type` and `has_sprite`.
- Implement `display_section_id = "archimate"`.
- Implement `render_display_section`: returns `label: {name}\nalias: {alias}` YAML block.
- Implement `extract_display_section`: parses `###archimate` YAML block.
- Implement `sprite_for`: reads glyph data via `_load_archimate_sprites()` helper; returns PlantUML sprite line or None. Sprite key: `$archimate_{artifact_type.replace("-", "_")}`.

### Step 1.8 — Diagram-kind `config.yaml` files ✅
- **Files:** `src/diagram_kinds/archimate_*/config.yaml`, `src/diagram_kinds/matrix/config.yaml`
- Replace `accepted_domains: [...]` with `filter:\n  hierarchy_level:\n    index: 0\n    values: [...]`.
- Matrix diagram kind: no filter (accepts all, via `_FreeOntologyType`).

### Step 1.9 — `_archimate_kind.py` loader ✅
- **File:** `src/diagram_kinds/_archimate_kind.py`
- Update `accepts_entity_type()` to evaluate `filter.hierarchy_level`.
- Support `element_classes` and `entity_types` filter clauses (conjunctive).

### Step 1.10 — Entity creation paths ✅
- **Files:**
  - `src/infrastructure/write/artifact_write/entity.py`
  - `src/infrastructure/write/artifact_write/admin_ops.py`
  - `src/infrastructure/write/artifact_write/global_artifact_reference.py`
- Path: `MODEL / Path(*info.hierarchy) / f"{eid}.md"`.
- Display block: call `ontology.render_display_section(artifact_type, name, alias)` to get content; pass `display_section_id` and `display_content` to `format_entity_markdown`.
- Get ontology via `registry.ontology_for_entity_type(artifact_type)`.

### Step 1.11 — `GenericPumlRenderer` ✅
- **File:** `src/infrastructure/rendering/generic_puml_renderer.py`
- `_domain_dir(entity)` → `_grouping_key(entity)`: uses `info.hierarchy[0]`.
- `_entity_declaration`: sprite via registry's ontology `sprite_for()` result; stereotype key `artifact_type.replace("-", "_")`.
- Remove `info.has_sprite` and `info.archimate_element_type` references.
- Remove hardcoded `"archimate"` display section key → use `entity.display_blocks.get(display_section_id)` where `display_section_id` comes from the diagram kind's primary ontology.
- Refactor: renderer receives `display_section_id` via constructor (from diagram kind config) or fetches from ontology in context.

### Step 1.12 — `diagram_builder.py` (GUI) ✅
- **File:** `src/infrastructure/rendering/diagram_builder.py`
- Remove `_entity_archimate_element_type()`.
- Derive stereotype/sprite key from `artifact_type.replace("-", "_")`.
- Use `sprite_for()` via ontology module for sprite lookup.

### Step 1.13 — `generate_macros.py` ✅
- **File:** `src/infrastructure/rendering/generate_macros.py`
- `_generate_glyph_include`: use `registry.all_ontologies()` to iterate; call `om.sprite_for(artifact_type)` per type; sprite key `$archimate_{artifact_type.replace("-", "_")}`.
- `_extract_archimate_block`: delegate to ontology module's `extract_display_section`.
- Domain from `info.hierarchy[0]`, not `domain_dir`.
- Prefix ordering: update `_PREFIX_ORDER` list to match new prefix set.

### Step 1.14 — `_archimate_includes.py` ✅
- **File:** `src/infrastructure/rendering/_archimate_includes.py`
- `_load_sprite_map`: parse `$archimate_<snake_case>` names (no longer PascalCase).
- `_load_stereotype_map`: parse `<snake_case>` stereotype names.

### Step 1.15 — GUI routers ✅
- **File:** `src/infrastructure/gui/routers/_diagram_context.py`
- Replace `info.domain_dir` → `info.hierarchy[0]`.
- Replace `info.subdir` → `info.hierarchy[-1]`.
- Replace `info.archimate_element_type` → `artifact_type.replace("-", "_")` or remove.

### Step 1.16 — `help.py` and `type_guidance.py` ✅
- **Files:** `src/infrastructure/write/artifact_write/help.py`, `type_guidance.py`
- Remove: `domain`, `subdir`, `archimate_element_type`, `archimate_domain`.
- Add: `hierarchy: list` (full tuple as list), `ontology: str`.
- `type_guidance.py`: filter by `info.hierarchy[0]` instead of `domain_dir`.

### Step 1.17 — `diagram_kinds.py` infrastructure helper ✅
- **File:** `src/infrastructure/diagram_kinds.py`
- Fix any `domain_dir` references.

### Step 1.18 — Generate updated stereotype + glyph files ✅
- Run `uv run python -m src.infrastructure.rendering.generate_macros <repo>` after all changes.
- Confirms snake_case naming convention is consistent end-to-end.

### Step 1.19 — Migration script ✅
- **File:** `src/infrastructure/migration/entity_spec_v2_migration.py`
- For each entity `.md` file:
  - Strip `domain:` and `element-type:` from `### archimate` display block.
- Move files from old paths (`model/{domain}/{plural}/`) to new paths (`model/{domain}/{type}/`).
- Update path references in `.outgoing.md` files and documents.
- Run against both `enterprise-repository` and any test fixtures.

### Step 1.20 — Fix all tests ✅
- Update `EntityTypeInfo` constructor calls (add `hierarchy=`, remove old fields).
- Update path assertions (`domain_dir`/`subdir` → `hierarchy`).
- Update `config.yaml` fixture references.
- Ensure protocol compliance tests pass.

### Step 1.21 — Ruff + zuban + full test suite green ✅
- `uv sync --all-groups`
- `uv run ruff check src/ tests/`
- `uv run zuban check`
- `uv run pytest -x`

---

## Phase 2: Diagram-Kind UI Authoring + Activity Diagrams

> Full design in `diagram-kind-ui-authoring-rfc.md`. Implement the RFC's Groups A–I in order.
> Each group below maps directly to the checklist in RFC §10.

### Step 2.1 — Protocol + config infrastructure (RFC Group A)
- **File:** `src/domain/ontology_protocol.py`
  - Add `PermittedMappingSpec` dataclass (fields: `entity_types: tuple[str,...]`, `entity_classes: tuple[str,...]`).
  - Add `DiagramOwnEntityTypeUiConfig` dataclass (fields: `entity_type`, `label`, `plural`, `min`, `max`, `permitted_mappings`, `mapping_required`).
  - Add `DiagramKindUiConfig` dataclass (fields: `label`, `description`, `entity_search_filter`, `diagram_only_types`, `kind_ui_slots`).
  - Add `ui_config` property to `DiagramKindModule` protocol.
- **File:** `src/diagram_kinds/_archimate_kind.py`
  - Add `ui_config` default property to `DiagramKindBase` returning `DiagramKindUiConfig(label=..., entity_search_filter=True)`.
  - Extend YAML config loading to parse the optional `ui:` section into `DiagramKindUiConfig`.
- **File:** `src/infrastructure/rendering/generic_puml_renderer.py`
  - Before calling PlantUML: strip any leading `---…---` YAML block from the `.puml` content string.
  - Add configurable output size warning (default threshold 8 000 chars).

### Step 2.2 — New diagram-kind API endpoints (RFC Group B)
- **New file:** `src/infrastructure/gui/routers/diagram_kinds.py`
  - `GET /api/diagram-kinds` — iterate `get_module_registry().all_diagram_kinds()`; return `[{key, label, description}]`.
  - `GET /api/diagram-kinds/{diagram_type}/ui-config` — look up kind; serialise `kind.ui_config` to JSON.
- **File:** `src/infrastructure/gui/routers/__init__.py` — include the new router.

### Step 2.3 — `kind_data` in diagram read/write (RFC Group C)
- **File:** `src/infrastructure/gui/routers/diagrams.py`
  - Diagram detail response: add `kind_data: rec.extra.get("kind-data")` as a top-level JSON field. `DiagramRecord.extra` is **not** modified.
- **File:** `src/infrastructure/gui/routers/_diagram_write.py`
  - Add `kind_data: dict | None = None` to `CreateDiagramGuiBody` and `EditDiagramGuiBody`.
  - Pass `kind_data` through to the write-layer functions.
- **File:** `src/infrastructure/write/artifact_write/diagram.py`
  - Accept `kind_data` param; write as `kind-data:` frontmatter key; trigger PUML regeneration after write.
- **File:** `src/infrastructure/write/artifact_write/diagram_edit.py` — same for edit.

### Step 2.4 — Kind-scoped entity search (RFC Group D)
- **File:** `src/infrastructure/gui/routers/_diagram_context.py`
  - `fuzzy_entity_hits()`: add `accepted_entity_types: set[str] | None = None`; skip candidates whose `artifact_type` is not in the set when it is provided.
- **File:** `src/infrastructure/gui/routers/diagrams.py`
  - Entity-search endpoint: add optional `diagram_type` query param; when present, resolve kind via registry and derive `accepted_entity_types = set(kind.effective_entity_types().keys())`; pass to `fuzzy_entity_hits()`.

### Step 2.5 — MCP tool updates (RFC Group E)
- **File:** `src/infrastructure/mcp/artifact_mcp/write/diagram.py`
  - Add optional `kind_data: dict | None` param to `artifact_create_diagram` and `artifact_edit_diagram`; pass to write layer.
- **File:** `src/infrastructure/mcp/artifact_mcp/write_tools.py` — update tool description strings to document `kind_data`.
- **File:** `src/infrastructure/mcp/artifact_mcp/query_list_read_tools.py` — confirm `kind_data` appears in diagram read responses.

### Step 2.6 — Activity diagram kind (RFC Group F)
- **New dir:** `src/diagram_kinds/activity/`
  - `config.yaml`: per RFC §8 (all domains; `ui:` section with `swimlane` entity type, `permitted_mappings`, `kind_ui_slots: {entity_context_panel: swimlane-assignment}`).
  - `__init__.py`: register the kind.
  - `renderer.py`: `ActivityPumlRenderer` — swimlane `|Lane label|` partitions; unassigned entities in trailing "Unassigned" lane; resolve `model_entity_id` entity name from repo when available; render model connections between included entities; compact output.
- **File:** `src/diagram_kinds/__init__.py` — add `activity` to the registry.

### Step 2.7 — Tests (RFC Group G)
- **File:** `tests/tools/test_diagram_kind_routes.py` — extend: ui_config endpoint shape; `fuzzy_entity_hits` `accepted_entity_types` filter; `kind_data` round-trips create→read and edit→read.
- **New file:** `tests/rendering/test_activity_renderer.py` — swimlane partitions; unassigned fallback; frontmatter stripped; size warning fires at threshold.
- **File:** `tests/domain/test_protocol_compliance.py` — add `activity` kind to compliance checks.

### Step 2.8 — Frontend (RFC Group H)
Work through the frontend in dependency order:
1. **`tools/gui/src/domain/schemas.ts`** — add `PermittedMappingSpecSchema`, `DiagramOwnEntityTypeUiConfigSchema`, `DiagramKindUiConfigSchema`; add `kind_data: Schema.optional(Schema.Unknown)` to `DiagramDetailSchema`; remove `extra` if unused in views.
2. **`tools/gui/src/ports/ModelRepository.ts`** — add `listDiagramKinds()` and `getDiagramKindUiConfig(type)` methods.
3. **`tools/gui/src/adapters/http/HttpModelRepository.ts`** — implement the two new port methods.
4. **`tools/gui/src/ui/lib/diagramAuthoringExtensions.ts`** (NEW) — `Map<string, Component>` singleton; `registerExtension(key, component)` and `lookupExtension(key)`.
5. **`tools/gui/src/ui/components/DiagramTypeSelect.vue`** (NEW) — fetches `/api/diagram-kinds`; emits selected key + full summary.
6. **`tools/gui/src/ui/components/DiagramOwnEntityTypeSection.vue`** (NEW) — add/remove instances of one diagram-only entity type; `permitted_mappings` picker; min/max enforcement; `mapping_required` validation.
7. **`tools/gui/src/ui/components/KindConfigPanel.vue`** (NEW) — receives `uiConfig` and `kindData`; renders `DiagramOwnEntityTypeSection` per `diagram_only_types` entry; mounts slot component per `kind_ui_slots` entry via `lookupExtension`; emits `kindDataChange` patch.
8. **`tools/gui/src/ui/components/EntityPickerInput.vue`** — add `acceptedTypes: Set<string>` prop; client-side filter; pass `diagram_type` param to search endpoint.
9. **`tools/gui/src/ui/views/CreateDiagramView.vue`** — replace hardcoded `DIAGRAM_TYPES` with `DiagramTypeSelect`; fetch `ui-config` on type change; pass to `KindConfigPanel`; include `kind_data` in create payload.
10. **`tools/gui/src/ui/views/EditDiagramView.vue`** — fetch `ui-config` on load; integrate `KindConfigPanel`; hold `kindDataPatch: ref<Record<string, unknown>>`; deep-merge onto base `kind_data` on save.
11. **`tools/gui/src/ui/components/SwimlaneAssignmentPanel.vue`** (NEW) — slot component; shows lane assignment for focused entity; reassign dropdown; emits `kindDataChange`.
12. **`tools/gui/src/main.ts`** — register slot components into `DiagramAuthoringExtensions` at startup.

### Step 2.9 — Docs + quality gate (RFC Group I)
- [ ] `src/diagram_kinds/README.md` — replace `domain_dir` → `hierarchy[0]`; document `ui:` section and `DiagramAuthoringExtensions` pattern.
- [ ] `uv run ruff check src/ tests/`
- [ ] `uv run zuban check`
- [ ] `uv run pytest -x`

---

## Phase 3: SysML v2 Extensibility Evaluation

> Evaluate (do not implement) after Phase 1 is complete.

- Can `OntologyModule` accommodate KerML's type system?
- Does the swimlane/mapping mechanism generalize to SysML's parts, ports, binding connectors?
- Does `element_classes` + `permitted_relationships` cover SysML multiplicity and direction constraints?
- Does `display_section_id` + `render_display_section` extend to SysML box-and-line notation?
- Produce gap list with prioritized improvement recommendations.

---

## File Change Index (quick reference)

| File | Change |
|------|--------|
| `src/domain/ontology_types.py` | Remove old fields; add `hierarchy` |
| `src/domain/ontology_protocol.py` | Add 4 new protocol members |
| `src/domain/module_registry.py` | `domain_order()` uses `hierarchy[0]` |
| `src/domain/ontology_catalog.py` | Use `hierarchy[0]` |
| `src/application/modeling/artifact_write_formatting.py` | Injectable display section |
| `src/ontologies/archimate_next/entities.yaml` | Replace domain/subdir/archimate_element_type/has_sprite |
| `src/ontologies/archimate_next/_loader.py` | Parse hierarchy; implement new protocol methods |
| `src/diagram_kinds/archimate_*/config.yaml` | Replace accepted_domains with filter block |
| `src/diagram_kinds/_archimate_kind.py` | New filter logic |
| `src/infrastructure/write/artifact_write/entity.py` | New path; call render_display_section |
| `src/infrastructure/write/artifact_write/admin_ops.py` | New path; call render_display_section |
| `src/infrastructure/write/artifact_write/global_artifact_reference.py` | New path |
| `src/infrastructure/write/artifact_write/help.py` | hierarchy/ontology fields |
| `src/infrastructure/write/artifact_write/type_guidance.py` | hierarchy[0] filter |
| `src/infrastructure/rendering/generic_puml_renderer.py` | hierarchy[0]; sprite via ontology |
| `src/infrastructure/rendering/diagram_builder.py` | Remove archimate_element_type usage |
| `src/infrastructure/rendering/generate_macros.py` | Delegate to ontology modules |
| `src/infrastructure/rendering/_archimate_includes.py` | snake_case sprite/stereotype names |
| `src/infrastructure/gui/routers/_diagram_context.py` | hierarchy[0], hierarchy[-1] |
| `src/infrastructure/diagram_kinds.py` | Fix domain_dir refs |
| `src/infrastructure/migration/entity_spec_v2_migration.py` | NEW — migration script |
| `tests/**` | Update EntityTypeInfo construction; path assertions |
