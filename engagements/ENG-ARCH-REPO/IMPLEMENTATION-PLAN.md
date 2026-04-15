# ENG-ARCH-REPO Implementation Plan

## Overview

Self-describing architecture repository: an ArchiMate NEXT model of the architecture-repository
system itself, with adapted tooling for the new conventions.

**Status**: Core model and tooling are complete. One workstream remains: the GUI tool (WS-E).

---

## Confirmed Design Decisions

### D1. Filename Convention

Entity: `TYPE@epoch.random.friendly-name.md`
Example: `DRV@1712870400.Qw7Er1.codegen-velocity-exceeds-planning-review.md`

Artifact-id = full filename stem (everything before `.md`)

### D2. Connection Representation: `.outgoing.md` Files

One file per entity, adjacent to the entity file, same name but `.outgoing.md` suffix.

Format:

```markdown
---
source-entity: DRV@1712870400.Qw7Er1.codegen-velocity-exceeds-planning-review
version: 0.1.0
status: draft
last-updated: '2026-04-12'
---

<!-- §connections -->

### archimate-influence → GOL@1712870400.Po1Qw3.maintain-coherence-and-traceability

Description of the relationship.
```

**Parsing rules:**
- File frontmatter: `source-entity` identifies the source of all connections in the file
- `<!-- §connections -->` marker delimits the connection section
- Each `### {connection-type} → {target-entity-id}` heading defines one connection
- Optional YAML fence block after heading for connection-specific metadata
- Connection ID reconstructed as: `{source}---{target}@@{type}`

### D3. Entity Frontmatter Schema

```yaml
---
artifact-id: DRV@1712870400.Qw7Er1.codegen-velocity-exceeds-planning-review
artifact-type: driver
name: "Code Generation Velocity Exceeds Planning & Review"
version: 0.1.0
status: draft
keywords: [codegen, velocity, planning, review]
last-updated: '2026-04-12'
---
```

Statuses: `draft | active | deprecated`

### D4. ArchiMate NEXT Domain Structure

```
model/
  motivation/     # stakeholders, drivers, assessments, goals, outcomes, principles, requirements, constraints, values
  strategy/       # capabilities, value-streams, resources, courses-of-action
  business/       # actors, objects, interfaces, collaborations, contracts, representations, products
  common/         # services, processes, functions, events, interactions, roles (behavioral — shared across domains)
  application/    # components, collaborations, interfaces, data-objects
  technology/     # nodes, devices, system-software, artifacts, paths, networks
  implementation/ # (future: work-packages, deliverables)
```

All behavioral elements (services, processes, functions, events, interactions) and roles go in
`model/common/`, not under business/application/technology.

### D5. Requirement Specialization Hierarchy

Modeled via `archimate-specialization` connections in `.outgoing.md` files.

Parent → Children:
- `discovery-tools` → `semantic-full-text-search`, `metadata-based-querying`, `graph-based-relationship-discovery`
- `authoring-tools` → `write-access-only-via-tools`, `gui-exploration-and-authoring-for-humans`
- `verification-tools` → `verified-referential-integrity-model-diagrams-documents`, `verify-diagram-syntax-automatically`

### D6. Configurability Principle

New principle: "Extensibility & Configurability"
- Git-based configuration for enterprise + engagement repositories
- Configurable frontmatter schemata (per file-type; required fields cannot be removed)
- Configurable attribute schemata for content sections (per entity-type and connection-type)
- Extensible ontology

Requirements: `configurable-frontmatter-schemata`, `configurable-model-attribute-schemata`, `git-based-repository-configuration`

JSON Schemas live in `.arch-repo/schemata/` (9 schemas, Draft 2020-12).

### D7. Non-Model Documentation Structure (`docs/`)

Architecture repositories contain three kinds of content:

| Directory | Purpose |
|-----------|---------|
| `model/` | ArchiMate NEXT entities |
| `diagram-catalog/` | PlantUML diagrams and rendered PNGs |
| `docs/` | Semi-structured textual documentation |

`docs/` is subdivided by doc-type:

```
docs/
  adrs/        # Architecture Decision Records
  standards/   # Coding/design standards and guidelines
  specs/       # Technical specifications
  README.md    # Conventions for this directory
```

**No frontmatter.** The `doc-id` is the filename stem (e.g., `adr-001-archimate-next-adoption`).
Metadata (status, authors, date) is expressed inside the required section headings.

**Enforced section headings by doc-type:**

| `doc-type` | Required top-level sections (in order) |
|------------|----------------------------------------|
| `adr` | Status · Context · Decision · Consequences |
| `standard` | Purpose · Scope · Rules · Rationale |
| `spec` | Overview · Requirements · Specification · Acceptance Criteria |
| `guideline` | Purpose · Guidance · Examples |

**Cross-reference syntax** (parsed by the framework query server):

```markdown
[@DOC:target-doc-id#section-id](relative/path/to/doc.md)
```

- `target-doc-id` = filename stem of the target document
- `section-id` = slugified heading (lowercase, spaces → hyphens)

**Framework server integration:** `sdlc-mcp-framework` is configured with
`SDLC_MCP_FRAMEWORK_DOC_ROOT=<repo root>` and `SDLC_MCP_FRAMEWORK_SCAN_DIRS=docs`,
enabling section-level search and reference graph traversal via the `framework_query_*` MCP tools.

---

## Current State (as of 2026-04-15)

| Workstream | Status | Key facts |
|-----------|--------|-----------|
| WS-A: Architecture Content | **COMPLETE** | 117 entities, 119 connections, 7 diagrams, all 6 domains |
| WS-B: Tooling Adaptation | **COMPLETE** | Types, parsing, registry, verification, write, macros, MCP tools |
| WS-C: Schema Validation | **COMPLETE** | 9 JSON Schemas, Draft 2020-12, W041/W042 rules |
| WS-D: Diagram Layout | **COMPLETE** | Auto-layout engine, ortho routing, direction heuristics |
| WS-G: Edit Tools | **COMPLETE** | `model_edit_entity`, `model_edit_connection`, `model_edit_diagram` |
| WS-F: Framework Server | **COMPLETE** | Configurable scan roots; `docs/` structure (D7); 2 seed ADRs; framework server wired in `.mcp.json` |
| WS-H: Two-Tiered Repos | **COMPLETE** | Connection ontology, arch-init CLI, asymmetric enforcement, cross-repo macros, promotion mechanism |
| WS-E: GUI Tool | **COMPLETE** | B-stream done: ontology-driven connection panels, entity create/edit, three-section layout |
| WS-I: YAML Ontology Config | **COMPLETE** | Entity + connection ontology as YAML; entity-level relationship rules; centralized EntityTypeInfo/ConnectionTypeInfo |

**Verification**: 173 files, 0 errors, 0 warnings (W350 resolves on MCP server restart — `tools/plantuml.jar` symlink + code fix in place).

**MCP servers** (configured in `.mcp.json` / `.vscode/mcp.json`):
- `sdlc-mcp-model` — `SDLC_MCP_MODEL_REPO_ROOT=engagements/ENG-ARCH-REPO/architecture-repository`
- `sdlc-mcp-framework` — `SDLC_MCP_FRAMEWORK_DOC_ROOT=engagements/ENG-ARCH-REPO/architecture-repository`, `SDLC_MCP_FRAMEWORK_SCAN_DIRS=docs`

**Two-tiered repo config**: `arch-workspace.yaml` at project root, `arch-init` CLI writes `.arch/init-state.yaml`. MCP + GUI servers auto-discover both repos from init state.

**GUI** (`sdlc-gui-server` + `tools/gui/` Vue SPA):
- Stack: Vue 3 + TypeScript + Vite + Effect; FastAPI REST backend
- Hexagonal: `domain/` → `ports/` → `adapters/http/` → `application/` → `ui/`
- Dockerized: `docker compose up --build` → http://localhost:8000
- Dev: `sdlc-gui-server --repo-root <path>` + `npm run dev` in `tools/gui/` → http://localhost:5173

---

## Completed GUI Features (2026-04-14)

### Diagram Explorer (E4-D)
- ✓ `GET /api/diagrams` — list with type filtering
- ✓ `GET /api/diagram?id=` — detail with PUML source + rendered PNG filename
- ✓ `GET /api/diagram-image/{filename}` — serve rendered PNG
- ✓ `GET /api/diagram-refs` — find diagrams referencing a connection
- ✓ `DiagramsView.vue` — grid listing with diagram-type filter bar
- ✓ `DiagramDetailView.vue` — rendered image, metadata, toggleable PUML source
- ✓ Search results link to diagram detail pages
- ✓ "Diagrams" added to nav bar

### Connection Editor (E4-4)
- ✓ `GET /api/write-help` — type catalog endpoint
- ✓ `POST /api/connection` — add connection (wraps model write + verify)
- ✓ `POST /api/connection/remove` — remove connection (wraps model write + verify)
- ✓ `ConnectionsPanel.vue` — grouped by target-entity-type, +/× buttons per group/item
- ✓ `EntitySearchInput.vue` — searchable by friendly name and random-id-part, filtered by entity type
- ✓ Remove checks diagram references and shows confirmation dialog

### Graph Explorer (E4-G)
- ✓ `GraphExploreView.vue` — force-directed SVG graph rooted at selected entity
- ✓ Click node to select → sidebar shows frontmatter and attributes
- ✓ Double-click / "+" badge to expand (load neighbors)
- ✓ Drag nodes, pan canvas, scroll to zoom
- ✓ Domain-colored nodes with type labels
- ✓ "Explore graph" button on entity detail view
- ✓ `useForceGraph.ts` composable — custom force simulation (no external dependency)

---

## Completed Two-Tiered Repo Infrastructure (WS-H, 2026-04-14)

| Task | Key files |
|------|-----------|
| H1: Connection Ontology | `src/common/connection_ontology.py` — element categories, RELATIONSHIP_RULES, symmetric detection, `permissible_connection_types()`, `classify_connections()` |
| H2: Config + CLI Init | `src/tools/workspace_init.py`, `arch-workspace.yaml` — `arch-init` validates/clones repos, writes `.arch/init-state.yaml` |
| H3: Gate Tooling on Init | `src/tools/model_mcp/context.py`, `src/tools/mcp_model_server.py` — init state loaded on startup, fallback to env vars |
| H4: Asymmetric Enforcement | `src/common/model_verifier.py` — E130 (enterprise target refs non-enterprise), E131 (enterprise source refs non-enterprise) |
| H5: Cross-Repo Macros | `src/tools/generate_macros.py` — `enterprise_root` param, scans both model/ dirs, deduplicates aliases |
| H6: Promotion Mechanism | `src/tools/model_write/promote_to_enterprise.py` (types + plan), `promote_execute.py` (execute + rollback), `src/tools/model_mcp/write_tools.py` (MCP tool) |
| H7: README Rewrite | `README.md` — describes two-tiered architecture, arch-workspace.yaml, promotion workflow |

Backend endpoints already in place for GUI work:
- `GET /api/ontology?source_type=&target_type=` — returns `classify_connections` or `permissible_connection_types`
- `GET /api/write-help` — returns valid entity types and connection types
- `POST /api/connection` and `POST /api/connection/remove` — already wired

---

## Completed: Ontology-Driven GUI (Stream B, 2026-04-14)

### B1: Ontology Types + Port + Adapter + Service

Add ontology and entity-write capabilities through the hexagonal stack.

#### B1a: Domain types — `tools/gui/src/domain/schemas.ts`

Add after existing schemas:

```typescript
// Ontology: permissible connection targets grouped by direction
export const OntologyClassification = Schema.Struct({
  source_type: Schema.String,
  outgoing: Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) }),
  incoming: Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) }),
  symmetric: Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) }),
})
export type OntologyClassification = Schema.Schema.Type<typeof OntologyClassification>

// Ontology: permissible connection types for a specific source→target pair
export const OntologyPair = Schema.Struct({
  source_type: Schema.String,
  target_type: Schema.String,
  connection_types: Schema.Array(Schema.String),
  symmetric: Schema.Array(Schema.String),
})
export type OntologyPair = Schema.Schema.Type<typeof OntologyPair>
```

`WriteResult` already exists and is sufficient for entity create/edit responses.

#### B1b: Port — `tools/gui/src/ports/ModelRepository.ts`

Add to the `ModelRepository` interface:

```typescript
readonly getOntologyClassification: (sourceType: string) => Effect<OntologyClassification, RepoError>
readonly getOntologyPair: (sourceType: string, targetType: string) => Effect<OntologyPair, RepoError>
readonly createEntity: (body: {
  artifact_type: string; name: string; summary?: string;
  properties?: Record<string, string>; notes?: string;
  keywords?: string[]; version?: string; status?: string;
  dry_run?: boolean;
}) => Effect<WriteResult, RepoError>
readonly editEntity: (body: {
  artifact_id: string; name?: string; summary?: string;
  properties?: Record<string, string>; notes?: string;
  keywords?: string[]; version?: string; status?: string;
  dry_run?: boolean;
}) => Effect<WriteResult, RepoError>
```

#### B1c: Adapter — `tools/gui/src/adapters/http/HttpModelRepository.ts`

Implement the new port methods using existing `fetchJson`/`postJson` helpers:

```typescript
getOntologyClassification: (sourceType) =>
  fetchJson(`/ontology?source_type=${encodeURIComponent(sourceType)}`, OntologyClassificationSchema),
getOntologyPair: (sourceType, targetType) =>
  fetchJson(`/ontology?source_type=${enc(sourceType)}&target_type=${enc(targetType)}`, OntologyPairSchema),
createEntity: (body) => postJson('/entity', body, WriteResultSchema),
editEntity: (body) => postJson('/entity/edit', body, WriteResultSchema),
```

#### B1d: Service — `tools/gui/src/application/ModelService.ts`

Pass through all four new methods (same delegation pattern as existing methods).

---

### B2: Backend Endpoints for Entity Create/Edit

**File: `src/tools/gui_server.py`**

Two new FastAPI endpoints:

```python
@app.post("/api/entity")
def create_entity(body: dict[str, Any]) -> dict[str, Any]:
    # Extract: artifact_type, name, summary, properties, notes, keywords, version, status, dry_run
    # Resolve repo root from init state / env
    # Call model_write_ops.create_entity(repo_root, verifier, ...)
    # Return WriteResult-shaped dict

@app.post("/api/entity/edit")
def edit_entity(body: dict[str, Any]) -> dict[str, Any]:
    # Extract: artifact_id + optional field overrides + dry_run
    # Call model_write_ops.edit_entity(repo_root, registry, verifier, ...)
    # Return WriteResult-shaped dict
```

Follow the same pattern as existing `POST /api/connection`: resolve repo, get verifier/registry, call ops module, return result dict. Check `model_write_ops.edit_entity` signature — the `model_edit_entity` MCP tool exists, so the ops function should be available.

---

### B3: Three-Section Connection Layout

**File: `tools/gui/src/ui/components/ConnectionsPanel.vue`** — major rewrite

Currently receives `direction` prop ("outbound"/"inbound"), groups connections by entity-type prefix.

**New design:** Three instances rendered from `EntityDetailView.vue`:
1. `<ConnectionsPanel direction="outgoing" />` — directed, this entity is source
2. `<ConnectionsPanel direction="incoming" />` — directed, this entity is target
3. `<ConnectionsPanel direction="symmetric" />` — undirected associations

Each panel:
1. On mount, call `svc.getOntologyClassification(entityDetail.artifact_type)` to get all permissible target types for this direction
2. Also call `svc.getConnections(entityId, direction)` for existing connections
3. Build sections: one per permissible target type (from ontology), even if 0 existing connections
4. Each section header: type badge + count + "+" add button
5. Each connection row: connection-type badge, entity name (RouterLink), "×" remove button
6. Existing connections that don't match any ontology section go in an "Other" group

**Props change:** Replace `direction: 'outbound' | 'inbound'` with `direction: 'outgoing' | 'incoming' | 'symmetric'`.

**EntityDetailView.vue change:** Replace current two-column outbound/inbound grid with three panels. Symmetric panel only appears if ontology returns non-empty symmetric entries.

---

### B4: Ontology-Driven Connection Creation Flow

**File: `tools/gui/src/ui/components/ConnectionsPanel.vue`** (same file, add-connection form)

When "+" is clicked on a section header (target type known from the section):

1. **Connection type dropdown** — call `svc.getOntologyPair(sourceType, targetType)` → populate `<select>` with permissible connection types. Pre-select if only one option.
2. **Target entity search** — reuse `EntitySearchInput`, pass `prefixFilter={targetType}` to scope search to that entity type. Backend `GET /api/entities?artifact_type=` already supports this.
3. **Description field** — optional textarea.
4. **Confirm button** — `svc.addConnection({source_entity, connection_type, target_entity, description, dry_run: false})`.
5. **Symmetric panel** — source/target labels are irrelevant for display; default connection type to `archimate-association`.

Key difference from current: connection type is now a constrained dropdown (not free text), and target search is scoped by entity type.

---

### B5: Entity Creation View

**New file: `tools/gui/src/ui/views/EntityCreateView.vue`** (~200 lines)

**Route:** Add `{ path: '/entity/create', component: EntityCreateView }` to `tools/gui/src/ui/router/index.ts`.

**Layout:**
1. **Form section** (left/top):
   - `artifact_type` — grouped `<select>` populated from `svc.getWriteHelp()` response (`entity_types` dict keyed by domain)
   - `name` — text input (required)
   - `summary` — textarea
   - `keywords` — comma-separated text input → split to array
   - `status` — select: draft/approved/deprecated (default: draft)
   - `version` — text input (default: 0.1.0)
   - `properties` — dynamic key-value pairs with add/remove rows
   - `notes` — textarea
2. **Preview section** (right/bottom):
   - "Preview" button → calls `svc.createEntity({...fields, dry_run: true})`
   - Shows: would-be `path`, `artifact_id`, rendered `content`, verification warnings/errors
3. **Confirm section:**
   - "Create" button (disabled until preview passes verification)
   - Calls `svc.createEntity({...fields, dry_run: false})`
   - On `wrote: true` → `router.push({ path: '/entity', query: { id: result.artifact_id } })`

**Navigation:** Add "+ Create Entity" button to `EntitiesView.vue` header that links to `/entity/create`.

---

### B6: Entity Editing (inline in detail view)

**File: `tools/gui/src/ui/views/EntityDetailView.vue`**

Add edit mode toggle:

1. **"Edit" button** in header (next to "Explore graph" button)
2. Click toggles `editing` ref (boolean)
3. When `editing`:
   - Name → text input (prefilled)
   - Summary → textarea (prefilled)
   - Keywords → comma-separated input (prefilled)
   - Status → select dropdown (prefilled)
   - Properties → editable key-value pairs
   - Notes → textarea
   - "Save" and "Cancel" buttons appear
4. **Save flow:**
   - Dry-run: `svc.editEntity({artifact_id, ...changed_fields, dry_run: true})`
   - Show verification result
   - If clean → `svc.editEntity({...same, dry_run: false})`
   - On `wrote: true` → reload entity detail, exit edit mode
5. **Cancel:** Reset form fields to original values, exit edit mode

---

### B-Stream File Summary

| File | Action | Task |
|------|--------|------|
| `tools/gui/src/domain/schemas.ts` | Add `OntologyClassification`, `OntologyPair` types | B1a |
| `tools/gui/src/ports/ModelRepository.ts` | Add 4 methods: `getOntologyClassification`, `getOntologyPair`, `createEntity`, `editEntity` | B1b |
| `tools/gui/src/adapters/http/HttpModelRepository.ts` | Implement 4 new port methods | B1c |
| `tools/gui/src/application/ModelService.ts` | Delegate 4 new methods | B1d |
| `src/tools/gui_server.py` | Add `POST /api/entity`, `POST /api/entity/edit` | B2 |
| `tools/gui/src/ui/components/ConnectionsPanel.vue` | Major rewrite: 3-section ontology layout + constrained add flow | B3, B4 |
| `tools/gui/src/ui/views/EntityDetailView.vue` | Three panels instead of two-column grid + edit mode toggle | B3, B6 |
| `tools/gui/src/ui/views/EntityCreateView.vue` | **Create** ~200 lines: form + dry-run preview + confirm | B5 |
| `tools/gui/src/ui/views/EntitiesView.vue` | Add "+ Create Entity" button in header | B5 |
| `tools/gui/src/ui/router/index.ts` | Add `/entity/create` route | B5 |

### B-Stream Implementation Order

```
B1 (types + port + adapter + service)  ──┐
                                         ├──→ B3+B4 (connection layout + creation)
B2 (backend POST /api/entity endpoints) ─┤
                                         ├──→ B5 (entity creation view)
                                         └──→ B6 (entity editing)
```

B1 and B2 are independent (frontend ports vs backend endpoints) and can be done in parallel. B3+B4 share a file (ConnectionsPanel.vue). B5 and B6 are independent but both need B1+B2.

### B-Stream Verification

1. **Ontology in GUI**: Open entity detail for a `goal` → outgoing section shows subsections for all permissible target types (requirement, outcome, etc.) even if empty
2. **Add connection**: Click "+" on a `requirement` subsection → dropdown shows only valid connection types for goal→requirement → search filters to requirement entities only
3. **Entity create**: `/entity/create` → fill form → preview shows dry-run content → confirm creates entity → navigates to detail
4. **Entity edit**: Entity detail → Edit → change summary → Save → dry-run validates → writes → reloads
5. **Symmetric**: Association connections appear in "Symmetric" panel, not in outgoing/incoming
6. **Verifier**: `model_verify_all` on ENG-ARCH-REPO still returns 0 errors after all changes

---

## Completed: YAML Ontology Config (WS-I, 2026-04-15)

### D8. YAML-Based Ontology Configuration

Entity types, connection types, and ArchiMate NEXT relationship rules are encoded as declarative YAML in `config/`:

| File | Purpose |
|------|---------|
| `config/entity_ontology.yaml` | Entity types: prefix, domain, subdir, archimate_element_type, element_category, element_classes |
| `config/connection_ontology.yaml` | Connection types: language, directory, symmetric flag, archimate_relationship_type; **permitted_relationships** rules |

**Element classes** — each entity type declares its ArchiMate NEXT abstract classification classes (e.g., `active-structure-element`, `internal-behavior-element`). The loader inverts these to build class→member maps used for rule expansion.

**Permitted relationship rules** — encoded as `[source, target, [connection-short-names]]` triples where source/target can be:
- A specific entity type name
- A list of entity types
- `@class-name` — expanded to all members of the named element class
- `@all` / `@same` — all entity types / same type as source

Rules are additive; the loader merges all rules per (source, target) pair into a `frozenset[str]` of permitted connection types. The resulting entity-level rules replace the previous category-level `RELATIONSHIP_RULES` dict.

### Centralized DataClasses

`EntityTypeInfo` extended with `element_category` and `element_classes` fields. `ConnectionTypeInfo` extended with `symmetric` field. Both loaded from YAML via `ontology_loader.py`; all downstream modules (`archimate_types.py`, `connection_ontology.py`, `model_write.py`) derive registries from these.

| Key file | Role |
|----------|------|
| `src/common/model_write_catalog.py` | Defines `EntityTypeInfo`, `ConnectionTypeInfo` dataclasses |
| `src/common/ontology_loader.py` | Loads YAML, builds `ENTITY_TYPES`, `CONNECTION_TYPES`, `PERMITTED_RELATIONSHIPS`, indexed lookups |
| `src/common/archimate_types.py` | Derives flat registries (`ALL_ENTITY_TYPES`, etc.) from loaded data |
| `src/common/connection_ontology.py` | Query API (`permissible_connection_types`, `classify_connections`) using entity-level rules |

### GUI: Three-Column Connection Layout

Connection panels in `EntityDetailView.vue` ordered as **[INCOMING] [SYMMETRIC] [OUTGOING]**. On wide screens (>1000px) with symmetric connections, all three panels display side-by-side. Falls back to 2-column (>700px) and 1-column (mobile).

---

## Future: Schema-Driven Forms (E4-5)

Not part of the B-stream but still relevant. After B-stream is complete:

- `GET /api/schemata?entity_type=` endpoint — returns JSON Schema for entity attributes from `.arch-repo/schemata/`
- Drive form field generation (required/optional fields, enum constraints) from schema
- Used in both entity create/edit and connection creation forms
- Potentially different attribute schemas per connection-type

---

## Tool-Based Authoring Principle

**All creation and editing of model entities, connections, and diagrams must go through tools.**
Tools handle ID generation, schema scaffolding, auto-layout, verification, and rendering.
Fixing tool output quality is always preferable to manual file editing.

**Prefer MCP tools over raw file reads** — they provide filtered, paginated, aggregated access
that is far more token-efficient than scanning files directly.

| Task | Tool |
|------|------|
| Count artifacts by type/domain | `model_query_stats` |
| List entities with filtering | `model_query_list_artifacts` |
| Read one entity in full | `model_query_read_artifact` |
| Search across model | `model_query_search_artifacts` |
| Find connected entities | `model_query_find_neighbors` |
| Verify model integrity | `model_verify_all` |
| Create new entity | `model_create_entity` |
| Edit entity | `model_edit_entity` |
| Add connection | `model_add_connection` |
| Edit/remove connection | `model_edit_connection` |
| Create diagram | `model_create_diagram` |
| Edit diagram | `model_edit_diagram` |
| Type catalog | `model_write_help` |

**Anti-patterns**: Don't glob `model/**/*.md`, don't grep `.outgoing.md` files, don't manually
construct/edit model files, don't manually edit diagram layout, don't import Python modules
directly for verification.

---

## WS-J: GUI Bug-Fix & Feature Wave (2026-04-15)

### J1: Backend Data Enrichment ✓
- [x] `src/common/model_query_types.py` — add `keywords: tuple[str, ...]` to `EntityRecord`
- [x] `src/common/model_query_parsing.py` — extract keywords in `parse_entity`
- [x] `src/common/model_query_repository.py` — include `keywords` + conn counts in `_read_entity` (full)
- [x] `src/tools/model_write/boundary.py` — remove overly-strict `engagements` path check (keep enterprise-repository check only); fixes Docker + dev-mode write errors
- [x] `src/tools/gui_server.py` — enrich `GET /api/entity` response with `keywords`, `summary`, `properties`, `notes` (via `parse_entity_file`); add `GET /api/entity-schemata?artifact_type=`; add `GET /api/diagram-entities?id=`

### J2: Frontend Schema + Entity Detail View ✓
- [x] `schemas.ts` — extend `EntityDetailSchema` with `keywords`, `summary`, `properties`, `notes`, `conn_in/sym/out`; extend `ConnectionRecordSchema` with `description` (alias of `content_text`); add `EntitySchemaInfoSchema`
- [x] `ports/ModelRepository.ts`, `adapters/http/HttpModelRepository.ts`, `application/ModelService.ts` — wire `getEntitySchemata` and `getDiagramEntities`
- [x] `EntityDetailView.vue` — fix `startEdit` to populate keywords from `keywords` field, summary from `summary` field, properties from `properties` field, notes from `notes` field

### J3: Connection Info Tooltip ✓
- [x] `ConnectionsPanel.vue` — add ⓘ icon next to connections that have `content_text`; on mouseover show a small tooltip with the description

### J4: Entity Search Fix ✓
- [x] `EntitySearchInput.vue` — add `artifactType` prop; pass it to backend `listEntities` instead of fetching all and filtering client-side by prefix (the prefix comparison was wrong: "GOAL@" vs actual "GOL@")
- [x] `ConnectionsPanel.vue` — update EntitySearchInput usage to pass `artifactType={typeKey}`

### J5: Graph Explorer Improvements ✓
- [x] `useForceGraph.ts` — add `totalConns?` + `addedBy?` to `GraphNode`; add `description?` to `GraphEdge`; add `collapseNode`; `applyClusterLayout` returns center coords and uses growing canvas size
- [x] `GraphExploreView.vue`:
  - Selectable edges: click on edge path → show full connection details in the sidebar: connection type, source entity, target entity, description/summary (`content_text`)
  - Collapse on dblclick: track `addedBy` per node; dblclick expanded node removes its subtree
  - `+` badge: only show if `totalConns` is unknown or > 0 (set from entity detail on domain resolve)
  - Cluster centering: after expansion, pan viewport to center on the expanded node

### J6: Diagram Detail Entity List ✓
- [x] `DiagramDetailView.vue` — add right-side entity list (identified by alias in PUML); clicking an entity shows its details (same fields and order as graph sidebar) + graph-explore link

### J7: Entity Create Fixes ✓
- [x] `EntityCreateView.vue` — widen form (max-width: 1160px, centered); Create button now enabled after clean preview (boundary fix in J1 unblocks preview)
- [x] `EntityCreateView.vue` — on `artifact_type` change, fetch `GET /api/entity-schemata` and pre-populate properties table from schema-required fields; required fields' remove buttons disabled

---

## Acceptance Criteria

1. ✓ All entity files have complete frontmatter + content + display blocks
2. ✓ All domains populated: motivation, strategy, common, business, application, technology
3. ✓ Requirement specialization hierarchy explicit via .outgoing.md connections
4. ✓ Configurability principle with git-config requirements present
5. ✓ Cross-domain connections modeled (motivation→strategy→common→application→technology)
6. ✓ At least 7 diagrams covering all populated domains + cross-domain view
7. ✓ Tooling parses new filename convention and .outgoing.md format
8. ✓ `ModelVerifier.verify_all()` passes with 0 errors, 0 warnings
9. ✓ `generate_macros()` produces valid _macros.puml (115 macros)
10. ✓ Common domain elements render in warm grey, distinct from business/application colors
11. ✓ Configurable JSON Schema validation for frontmatter and attributes (WS-C)
12. ✓ Diagram auto-layout with ortho routing and direction heuristics (WS-D)
13. ✓ Edit tools for entities, connections, and diagrams (WS-G)
14. ✓ Framework server serves `docs/` with section search and reference graph (WS-F)
15. ✓ E1 model entities + E4 Phase 1+2 (read-only explorer + search) (WS-E in progress)
