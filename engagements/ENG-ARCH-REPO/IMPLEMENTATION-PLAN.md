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

## Current State (as of 2026-04-14)

| Workstream | Status | Key facts |
|-----------|--------|-----------|
| WS-A: Architecture Content | **COMPLETE** | 117 entities, 119 connections, 7 diagrams, all 6 domains |
| WS-B: Tooling Adaptation | **COMPLETE** | Types, parsing, registry, verification, write, macros, MCP tools |
| WS-C: Schema Validation | **COMPLETE** | 9 JSON Schemas, Draft 2020-12, W041/W042 rules |
| WS-D: Diagram Layout | **COMPLETE** | Auto-layout engine, ortho routing, direction heuristics |
| WS-G: Edit Tools | **COMPLETE** | `model_edit_entity`, `model_edit_connection`, `model_edit_diagram` |
| WS-F: Framework Server | **COMPLETE** | Configurable scan roots; `docs/` structure (D7); 2 seed ADRs; framework server wired in `.mcp.json` |
| WS-E: GUI Tool | **IN PROGRESS** | E1–E4-phase2 done; authoring phases remain |

**Verification**: 173 files, 0 errors, 0 warnings (W350 resolves on MCP server restart — `tools/plantuml.jar` symlink + code fix in place).

**MCP servers** (configured in `.mcp.json` / `.vscode/mcp.json`):
- `sdlc-mcp-model` — `SDLC_MCP_MODEL_REPO_ROOT=engagements/ENG-ARCH-REPO/architecture-repository`
- `sdlc-mcp-framework` — `SDLC_MCP_FRAMEWORK_DOC_ROOT=engagements/ENG-ARCH-REPO/architecture-repository`, `SDLC_MCP_FRAMEWORK_SCAN_DIRS=docs`

**GUI** (`sdlc-gui-server` + `tools/gui/` Vue SPA):
- Stack: Vue 3 + TypeScript + Vite + Effect; FastAPI REST backend
- Hexagonal: `domain/` → `ports/` → `adapters/http/` → `application/` → `ui/`
- Dockerized: `docker compose up --build` → http://localhost:8000
- Dev: `sdlc-gui-server --repo-root <path>` + `npm run dev` in `tools/gui/` → http://localhost:5173

---

## Remaining Work

### WS-E: GUI Authoring Phases (E4-3 through E4-5)

**Prerequisite — write endpoints for `gui_server.py`** (before any authoring UI):
1. `GET /api/write-help` → type catalog (artifact types, connection types, domains) for populating forms
2. `POST /api/entity` body `{artifact_type, name, summary, keywords, status, dry_run}` → create entity (wraps model write + verify)
3. `POST /api/connection` body `{source, connection_type, target, description, dry_run}` → add connection
4. `POST /api/entity/{id}/verify` → verify single entity file

**E4-3: Entity creation view**
- Form: artifact_type selector (from write-help), name, summary, keywords, status
- Dry-run preview panel showing would-be file content + verification result
- Confirm → POST to `/api/entity` with `dry_run=false`
- On success: navigate to new entity detail view

**E4-4: Connection authoring**
- On entity detail view: "Add connection" button
- Form: connection_type selector, target entity search/select
- Dry-run preview, confirm → POST `/api/connection`

**E4-5: Schema-aware forms**
- Fetch attribute schemata from JSON Schema files (`.arch-repo/schemata/`)
- Drive form field generation (required/optional fields, enum constraints) from schema
- Expose via `GET /api/schemata?entity_type=` endpoint

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
