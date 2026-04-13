# ENG-ARCH-REPO Implementation Plan

## Overview

Self-describing architecture repository: an ArchiMate NEXT model of the architecture-repository
system itself, with adapted tooling for the new conventions.

**Two workstreams:**
- **WS-A**: Complete the architecture specification across all ArchiMate NEXT domains
- **WS-B**: Adapt `/src` tooling for new conventions (filename, connections, frontmatter)

---

## Confirmed Design Decisions

### D1. Filename Convention (NEW — differs from ENG-001)

Entity: `TYPE@epoch.random.friendly-name.md`
Example: `DRV@1712870400.Qw7Er1.codegen-velocity-exceeds-planning-review.md`

Artifact-id = full filename stem (everything before `.md`)

### D2. Connection Representation: `.outgoing.md` Files

One file per entity, adjacent to the entity file, same name but `.outgoing.md` suffix.
Example: `DRV@1712870400.Qw7Er1.codegen-velocity-exceeds-planning-review.outgoing.md`

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

### archimate-specialization → REQ@1712870400.Cc2Dd2.semantic-full-text-search

Description of the specialization.
```

**Parsing rules:**
- File frontmatter: `source-entity` identifies the source of all connections in the file
- `<!-- §connections -->` marker delimits the connection section
- Each `### {connection-type} → {target-entity-id}` heading defines one connection
- Optional YAML fence block after heading for connection-specific metadata (e.g., `access-type: read-write`)
- Body text after heading/metadata = human-readable description
- Connection ID reconstructed as: `{source}---{target}@@{type}`

### D3. Entity Frontmatter Schema (Reduced)

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

**Dropped** (vs ENG-001): `engagement`, `phase-produced`, `owner-agent`, `safety-relevant`, `produced-by-skill`
**Added**: `keywords`
**Changed**: statuses are `draft | active | deprecated` (not `baselined`)

### D4. ArchiMate NEXT Domain Structure (strict)

Directory: `model/` (not `model-entities/`)

```
model/
  motivation/     # stakeholders, drivers, assessments, goals, outcomes, principles, requirements, constraints, values
  strategy/       # capabilities, value-streams, resources, courses-of-action
  business/       # actors, objects, interfaces, collaborations, contracts, representations, products
  common/         # services, processes, functions, events, interactions, roles (behavioral — shared across domains)
  application/    # components, collaborations, interfaces, data-objects
  technology/     # nodes, devices, system-software, artifacts, paths, networksm (ArchiMate next merges "physical" into this layer)
  implementation/ # (future: work-packages, deliverables)
```

**Key NEXT change**: All behavioral elements (services, processes, functions, events, interactions)
and roles go in `model/common/`, not under business/application/technology.

### D5. Requirement Specialization Hierarchy

Modeled via `archimate-specialization` connections in `.outgoing.md` files.

Parent → Children:
- `discovery-tools` → `semantic-full-text-search`, `metadata-based-querying`, `graph-based-relationship-discovery`
- `authoring-tools` → `write-access-only-via-tools`, `gui-exploration-and-authoring-for-humans`
- `verification-tools` → `verified-referential-integrity-model-diagrams-documents`, `verify-diagram-syntax-automatically`

`support-models-diagrams-documents` stays standalone (no parent needed — confirmed).

### D6. Configurability Principle

New principle: "Extensibility & Configurability"
- Git-based configuration for enterprise repository and for engagement/project repositories
- Configurable frontmatter schemata
- Configurable attribute schemata for file sections (per entity-type and per connection-type)
- Extensible ontology

New requirements:
- `configurable-frontmatter-schemata` — covers frontmatter fields. Specific per file-type (entity, connections-files, diagram). Fields required for tools / processes in the concept are mandatory - schema can extend (but not override or remove).
- `configurable-model-attribute-schemata`  — covers attribute schemata for content sections (e.g., Properties table attributes per entity-type, connection metadata attributes per connection-type). Default is a free schema (no required attributes beyond frontmatter).
- `git-based-repository-configuration` (enterprise + engagement config)

---

## WS-A: Architecture Content

### Phase A1: Motivation Domain

**Write content for existing entities (all currently empty):**

Stakeholders (5): architect, developer, devops-engineer, product-owner, upper-technical-management
Drivers (5): codegen-velocity-exceeds-planning-review, increasing-autonomy-of-teams-systems, rising-complexity-and-interdependence, limited-central-governance-capacity, increasing-need-for-effective-llm-access
Goals (11, minus 1 duplicate = 10): maintain-coherence-and-traceability, enable-scalable-reuse, enable-cross-stakeholder-validation, support-architecture-planning-for-{humans,AI}, provide-development-guidance-for-{humans,AI}, support-product-design-evolution-and-validation-for-{humans,ai}, support-technology-design-evolution-and-validation-for-{humans,ai}
Requirements (25): all listed in existing files

**Add new entities:**

| Type | Name | Rationale |
|------|------|-----------|
| PRI (Principle) | extensibility-and-configurability | Core principle: git-config for enterprise + engagement repos |
| OUT (Outcome) | increased-architectural-coherence | Measurable outcome of the system |
| OUT (Outcome) | reduced-planning-overhead | Measurable outcome |
| REQ (Requirement) | configurable-frontmatter-schemata | Configurability requirement |
| REQ (Requirement) | git-based-repository-configuration | Enterprise + engagement config |

**Entity content pattern** (following ENG-001 format structure):

```markdown
---
artifact-id: {full-stem}
artifact-type: {type}
name: "{Display Name}"
version: 0.1.0
status: draft
keywords: [kw1, kw2]
last-updated: '2026-04-12'
---

<!-- §content -->

## {Display Name}

{Description paragraph(s)}

## Properties

| Attribute | Value |
|---|---|
| Key1 | Value1 |

## Notes

{Optional notes}

<!-- §display -->

### archimate

```yaml
layer: {Motivation|Strategy|Business|Application|Technology}
element-type: {ArchiMateElementType}
label: "{Display Name}"
alias: {ALIAS_WITH_UNDERSCORES}
```

**Alias convention**: Since we no longer have PREFIX-NNN IDs, aliases need a new convention.
Proposed: use the TYPE prefix + a short form, e.g., `DRV_Qw7Er1` (TYPE + random part of ID).
This keeps aliases short enough for PlantUML while remaining unique.

### Phase A2: Strategy Domain

New entities to create:

| Type | Friendly Name | Description |
|------|--------------|-------------|
| CAP | architectural-modeling | Ability to create and maintain architectural models |
| CAP | model-validation | Ability to verify model integrity and consistency |
| CAP | artifact-discovery | Ability to find, explore, and query artifacts |
| CAP | artifact-authoring | Ability to create new artifacts with tool support |
| CAP | repository-governance | Ability to manage two-tier structure, promotion, lifecycle |
| CAP | configuration-management | Ability to configure repository behavior via git-config |
| COA | markdown-file-based-approach | Decision: markdown + directory structure over database-only |
| COA | archimate-next-ontology-adoption | Decision: adopt ArchiMate NEXT over 3.x |

### Phase A3: Common Domain (ArchiMate NEXT Behavioral)

**Existing** (write content for):
- SRV: authoring-service, validation-service, discovery-querying-stats-service, repository-promotion-service

**New:**

| Type | Friendly Name | Description |
|------|--------------|-------------|
| SRV | configuration-service | Manages repo configuration via git-config |
| SRV | indexing-service | Runtime indexing into SQLite |
| PRC (Process) | create-entity | Create a new model entity with frontmatter + display block |
| PRC | create-connection | Add connection to .outgoing.md file |
| PRC | create-diagram | Create new PUML diagram with frontmatter |
| PRC | verify-model | Run verification across model, connections, diagrams |
| PRC | index-repository | Extract metadata into SQLite for querying |
| PRC | promote-artifact | Promote artifact from engagement to enterprise repo |
| PRC | query-model | Search/traverse the model via various interfaces |
| FNC (Function) | frontmatter-validation | Validate frontmatter against schema |
| FNC | attribute-schema-validation | Validate content-section attributes against per-type attribute schemata |
| FNC | referential-integrity-check | Verify all references resolve |
| FNC | puml-syntax-check | Validate PlantUML syntax |
| EVT (Event) | entity-created | Emitted when a new entity is created |
| EVT | model-verified | Emitted when verification completes |
| ROL | author | Human or AI creating artifacts |
| ROL | reviewer | Human or AI validating artifacts |

### Phase A4: Business Domain

**Existing** (write content for):
- ACT (5): architect, developer, devops-engineer, product-owner, upper-technical-management

**New:**

| Type | Friendly Name | Description |
|------|--------------|-------------|
| BIF | gui-interface | GUI for human exploration and authoring |
| BOB | entity-file | Markdown file representing one model entity |
| BOB | connection-file | .outgoing.md file representing entity connections |
| BOB | diagram-file | PUML file representing an architectural diagram |
| BOB | frontmatter-block | YAML frontmatter section of an artifact |
| BOB | architecture-model | Complete model spanning all domains |
| BOB | engagement-repository | Project/engagement-scoped repository |
| BOB | enterprise-repository | Enterprise-scoped repository |

### Phase A5: Application Domain

| Type | Friendly Name | Description |
|------|--------------|-------------|
| APP | frontmatter-parser | Parses YAML frontmatter from .md and .puml files |
| APP | model-verifier | Validates entities, connections, diagrams |
| APP | model-registry | In-memory index of entity/connection metadata |
| APP | macro-generator | Generates _macros.puml from entity display blocks |
| APP | sqlite-indexer | Indexes metadata into SQLite for querying |
| APP | query-engine | Supports full-text, metadata, and graph queries |
| APP | mcp-model-server | MCP server for model operations |
| APP | cli-tool | Command-line interface for model operations |
| AIF | mcp-interface | MCP protocol interface |
| AIF | cli-interface | CLI interface |
| AIF | rest-interface | REST API interface (future) |
| DOB | entity-metadata | Extracted entity frontmatter in index |
| DOB | connection-metadata | Extracted connection data in index |
| DOB | sqlite-index | SQLite database with indexed metadata |
| DOB | puml-macro-library | Generated _macros.puml file |

### Phase A6: Technology Domain

| Type | Friendly Name | Description |
|------|--------------|-------------|
| NOD | developer-workstation | Local developer machine running the tools |
| ART | git-repository | Git repo containing the architecture files |
| ART | sqlite-database | SQLite file for runtime indexing |
| SSW | python-runtime | Python 3.11+ runtime |
| SSW | plantuml-engine | PlantUML rendering engine |
| SSW | git-vcs | Git version control system |
| TSV | file-system-service | Local filesystem read/write |
| TSV | version-control-service | Git operations |

### Phase A7: Connections (.outgoing.md files)

**Within Motivation:**
- Stakeholders → (association) → Drivers, Goals
- Drivers → (influence) → Goals
- Goals → (realization) → Outcomes
- Requirements → (specialization) → child Requirements (hierarchy from D5)
- Requirements → (realization) → Goals
- Principle → (influence) → Requirements

**Motivation → Strategy:**
- Goals → (realization) → Capabilities
- Requirements → (realization) → Capabilities
- Courses of Action → (realization) → Capabilities

**Strategy → Common/Business:**
- Capabilities → (realization by) → Services, Processes
- Actors → (assignment) → Roles

**Common → Application:**
- Services → (realization by) → Application Components + Application Services
- Processes → (realization by) → Application Components

**Application → Technology:**
- Application Components → (serving/realization by) → Technology artifacts, nodes, system-software
- Data Objects → (realization by) → Technology artifacts

### Phase A8: Diagrams

| Diagram | Type | Content |
|---------|------|---------|
| motivation-overview | archimate-motivation | All stakeholders, drivers, goals, outcomes, principles, requirements with connections |
| strategy-capability-map | archimate-strategy | Capabilities, courses of action, connected to goals |
| business-actor-role-map | archimate-business | Actors, roles, business objects, interfaces |
| common-services-processes | archimate-common | Services, processes, functions, events with assignments |
| application-component-map | archimate-application | All application components, interfaces, data objects, services |
| technology-infrastructure | archimate-technology | Nodes, artifacts, system software, services |
| cross-domain-realization | archimate-layered | Full cross-domain view showing realization chain |

---

## WS-B: Tooling Adaptation

### Phase B1: Core Type System (`src/common/`)

**`model_verifier_types.py`:**
- Change `ENTITY_ID_RE` from `^[A-Z]+-\d{3}$` to match new convention: `^[A-Z]{2,6}@\d+\.[A-Za-z0-9_-]+\..+$`
- Update `entity_id_from_path()` to return full stem (not split on dot)
- Change `VALID_STATUSES` from `{draft, baselined, deprecated}` to `{draft, active, deprecated}`
- Update `ENTITY_REQUIRED` to remove `engagement`, `phase-produced`, `owner-agent`, `safety-relevant`; add `keywords` as optional
- Update `CONNECTION_REQUIRED` — adapt for .outgoing.md (no longer per-file connection frontmatter)
- Update `CONN_ID_ALLOWED_CHARS_RE` — entity IDs in connections now contain `@` and dots
- Update `connection_artifact_id_matches_shape()` for new entity ID format in connection IDs
- Add `AttributeSchema` type: dataclass with `required_attrs`, `optional_attrs`, `allowed_values` per attribute, loaded from config
- Add `ATTRIBUTE_SCHEMA_REGISTRY`: dict mapping `(schema_scope, type_name)` → `AttributeSchema` (scope = "entity" or "connection"; type_name = entity-type or connection-type; default = free schema)

**`archimate_types.py`:**
- Rename layer references to "domain" in comments/docstrings (ArchiMate NEXT)
- Add "common" domain to `ENTITY_TYPES_BY_LAYER` (behavioral elements)
- Existing type registries remain mostly valid

**`model_write_catalog.py`:**
- Update `EntityTypeInfo` — add common domain entries (services, processes, functions, events, roles, interactions)
- Change `ENTITY_TYPES` dict to route behavioral elements to `common/` subdirs
- Update `CONNECTION_TYPES` — connection info no longer maps to directory paths (connections are in .outgoing.md)

### Phase B2: Parsing (`src/common/`)

**`model_verifier_parsing.py`:**
- Add `parse_outgoing_file()` — new parser for .outgoing.md format:
  1. Parse file frontmatter (source-entity, version, status, last-updated)
  2. Find `<!-- §connections -->` marker
  3. Split by `### ` headers
  4. For each header: extract connection-type and target-entity-id
  5. Extract optional YAML fence block for connection metadata
  6. Extract body text as description
  7. Return list of parsed connections with reconstructed connection IDs
- Update `parse_connection_refs()` to work with new outgoing format
- Add `parse_attribute_schema_config()` — loads attribute schema definitions from git-tracked config files:
  1. Read schema config file(s) from `.arch-repo/` or configured path
  2. Parse per-entity-type and per-connection-type attribute definitions
  3. Return populated `AttributeSchema` instances for the schema registry
- Add `parse_properties_table()` — extracts attribute key-value pairs from a Properties table in content sections

### Phase B3: Registry (`src/common/`)

**`model_verifier_registry.py`:**
- `_scan_entity_meta()`: scan `model/` instead of `model-entities/`
- `_scan_connection_meta()`: scan for `*.outgoing.md` files instead of `connections/` directory
  - Parse each .outgoing.md using new parser
  - Extract individual connections and register each with its reconstructed ID
- `_ensure_entity_file_index()`: scan `model/` instead of `model-entities/`
- `_ensure_connection_file_index()`: index by .outgoing.md path + section offset
- `entity_id_from_path()`: return full stem for new-convention files

### Phase B4: Verification (`src/common/`)

**`model_verifier.py`:**
- Add `verify_outgoing_file()` method — verifies a .outgoing.md file:
  - Parse frontmatter, validate required fields
  - For each connection section: validate connection type, resolve target entity
  - Check for duplicate connections
- Update `_verify_all_full()` / `_verify_inventory_subset()` to handle outgoing files
- Remove/deprecate `verify_connection_file()` or keep it for backward compat

**`model_verifier_rules.py`:**
- `check_artifact_id_entity()`: update regex and filename-matching logic for new convention
- `check_artifact_id_connection()`: adapt for outgoing file connection IDs
- Relax enum checks: remove `phase-produced` and `owner-agent` validation when not in frontmatter
- Update `check_reference_resolution_scoped()` for new entity ID format
- Add `check_attribute_schema()`: validate content-section attributes against per-type attribute schemata:
  1. Determine entity-type or connection-type from frontmatter
  2. Look up applicable `AttributeSchema` from registry (default: free schema → skip)
  3. Parse Properties table / connection metadata attributes
  4. Verify required attributes present, values conform to allowed sets
  5. Report missing required attributes and invalid values as verification errors

**`model_verifier_incremental.py`:**
- `_index_entity_files()`: scan `model/` not `model-entities/`
- `_index_connection_files()`: scan for `*.outgoing.md` instead of `connections/**/*.md`
  - Parse outgoing files, extract individual connection refs
- `inventory_files()`: update classification logic

### Phase B5: Write System (`src/common/`)

**`model_write.py`:**
- `slugify()`: keep as-is (still useful)
- `prefix_num_from_id()` / `allocate_next_entity_id()`: replace with new ID generation using epoch + random
- `connection_id_from_endpoints()`: update for new entity ID format
- `infer_entity_ids_from_puml()`: update alias pattern matching for new convention
- `infer_archimate_connection_ids_from_puml()`: update for new ID format

**`model_write_formatting.py`:**
- `format_entity_markdown()`: update frontmatter fields (remove dropped, add keywords); when an attribute schema is configured for the entity-type, scaffold the Properties table with required/optional attributes
- `format_connection_markdown()` → replace with `format_outgoing_markdown()`: generates .outgoing.md; when an attribute schema is configured for the connection-type, scaffold metadata block with required/optional attributes
- `format_diagram_puml()`: update frontmatter (remove engagement, phase-produced, owner-agent)
- `format_matrix_markdown()`: same updates

### Phase B6: Macro Generation (`src/tools/`)

**`generate_macros.py`:**
- Scan `model/` instead of `model-entities/`
- Update alias extraction: new alias format (TYPE + random part, e.g., `DRV_Qw7Er1`)
- Update `_sort_key()`: new sorting that works with epoch-based IDs
- Update `_PREFIX_ORDER` if needed
- Update header comment from "ENG-001" to generic

### Phase B7: MCP Tools (`src/tools/model_mcp/`, `src/tools/model_write/`)

- `write_tools.py`: update entity/connection creation for new conventions
- `verify_tools.py`: update to use new verification methods
- `query_list_read_tools.py`: update file discovery paths
- `model_write/entity.py`: update path generation, ID allocation
- `model_write/connection.py`: rewrite for .outgoing.md (append to file instead of create new)

---

## Implementation Order

```
B1 (types) → B2 (parsing) → B3 (registry) → B4 (verification) → B5 (write) → B6 (macros)
    ↕ interleave with
A1 (motivation) → A2 (strategy) → A3 (common) → A4 (business) → A5 (application) → A6 (technology)
    then
A7 (connections) → A8 (diagrams) → B7 (MCP tools) → Final verification
```

**Practical approach**: Adapt core tooling first (B1-B4) so verification works, then write architecture
content (A1-A6), then connections (A7), then diagrams (A8), then remaining tooling (B5-B7).

---

## Completion Status (as of 2026-04-13)

### WS-A: Architecture Content — COMPLETE
- A1-A8 all done: 115 entities, 115 connections, 7 diagrams across all 6 domains
- Attribute-schema-validation function entity added
- Outgoing connections for all configurability requirements added
- All diagrams rendered to PNG in `diagram-catalog/diagrams/rendered/`

### WS-B: Tooling Adaptation — COMPLETE
- B1-B4: Core types, parsing, registry, verification — all adapted for new conventions
- B5-B6: Write system (entity/connection/diagram) + macro generation — done
- B7: MCP tools, query system, CLI — all cleaned up:
  - Removed: `phase-produced`, `owner-agent`, `safety-relevant`, `engagement`, `produced-by-skill` from all records/filters/CLI
  - Renamed: `layer` → `domain`, `LAYER_NAMES` → `DOMAIN_NAMES`, `conn_lang` removed
  - Query scan paths: `model-entities/` → `model/`, `connections/` → `*.outgoing.md` in `model/`
  - Query parsing: `parse_connection()` → `parse_outgoing_file()` returning multiple `ConnectionRecord`s per file
  - Diagram parsing: standard `---` YAML only, removed `' ---` comment-style parser
  - MCP server imports/descriptions updated
- Verification: 170 files, 0 errors, 14 warnings
- Macros: 115 macros generated

### Common Domain Visual Treatment — COMPLETE
- Added `<<Service>>`, `<<Process>>`, `<<Function>>`, `<<Interaction>>`, `<<Event>>`, `<<Role>>` stereotypes in warm grey (#E0D8CC bg, #8C7E6A border)
- Added `<<CommonGrouping>>` container stereotype
- Fixed 3 diagrams (common-services-processes, cross-domain-realization, business-actor-role-map) to use common stereotypes
- All 7 diagrams re-rendered with updated colors

---

## Remaining Work (WS-C, WS-D, WS-E)

### WS-C: Configurable Schema Validation

**Design decision: JSON Schema** for both frontmatter and attribute schemata.
Rationale: language-agnostic standard; schema files stored in git as `.json`; any tooling can validate; avoids coupling to Python-specific Pydantic. Python validation via `jsonschema` library.

#### C1: Schema Infrastructure
- Define schema config location: `.arch-repo/schemata/` in repo root
- File convention: `frontmatter.{file-type}.schema.json` (e.g., `frontmatter.entity.schema.json`)
- File convention: `attributes.{entity-type}.schema.json` (e.g., `attributes.requirement.schema.json`)
- Connection metadata: `connection-metadata.{connection-type}.schema.json`
- Default: free schema (no file = no constraints beyond tool-required frontmatter)

#### C2: Schema Loading (`src/common/`)
- `model_schema.py`: `load_frontmatter_schema(repo_root, file_type)`, `load_attribute_schema(repo_root, entity_type)`
- Parse JSON Schema files, merge with tool-required base fields
- Cache loaded schemas per repo root

#### C3: Verification Integration
- `model_verifier_rules.py`: add `check_frontmatter_schema()` and `check_attribute_schema()`
- `check_frontmatter_schema()`: validate frontmatter dict against JSON Schema for file type
- `check_attribute_schema()`: extract Properties table, validate against per-type attribute schema
- Wire into `verify_entity_file()`, `verify_outgoing_file()`, `verify_diagram_file()`

#### C4: Write System Integration
- `model_write_formatting.py`: when attribute schema exists, scaffold Properties table with required/optional attributes
- `model_write/entity.py`, `connection.py`: pass schema info for scaffolding

#### C5: Update Requirements
- Update `REQ configurable-frontmatter-schemata` content: specify JSON Schema format, `.arch-repo/schemata/` location, extend-only semantics
- Update `REQ configurable-model-attribute-schemata` content: specify JSON Schema format for content-section attributes per entity-type/connection-type

### WS-D: Diagram Layout Conventions

#### D1: PlantUML Layout Directives
- Add layout directives to `_archimate-stereotypes.puml`:
  - `skinparam linetype ortho` for 90° circuit-board routing
  - `skinparam nodesep 60` and `skinparam ranksep 80` for spacing
- Update existing diagrams with `left to right direction` / `top to bottom direction` alternating per "container" (grouping, subdivided process or function) at the top level and per nesting level
- Use PlantUML `together { }` blocks and explicit `-left->`, `-right->`, `-up->`, `-down->` arrow directions to control flow

#### D2: Update Diagram Write Tool
- `model_write/diagram.py`: include layout directive hint in generated PUML scaffolding
- Document layout conventions in `model_write/help.py` catalog

### WS-E: GUI Discovery & Authoring Tool

#### E1: Architecture Model Entities
- New entities needed: `APP gui-authoring-tool`, `AIF web-interface`
- Connection: `BIF gui-interface` → served by → `APP gui-authoring-tool`
- Connection: `APP gui-authoring-tool` → uses → `APP query-engine`, `APP model-verifier`

#### E2: Technology Selection
- Web-based SPA (React/Vue/Svelte) or desktop (Electron/Tauri)
- Connects to MCP server or REST interface for all operations
- Requirements from `REQ gui-exploration-and-authoring-for-humans`

#### E3: Core Features
- Model explorer: browse entities by domain, view entity details + connections
- Graph navigator: interactive connection graph visualization (D3.js / Cytoscape)
- Entity authoring: create/edit entities via forms, dry-run preview
- Connection authoring: add connections via guided flow
- Diagram viewer: render and display PUML diagrams
- Search: full-text + metadata search across all artifacts

#### E4: Implementation Phases
1. Read-only explorer (entity list, detail view, connection graph)
2. Search + filtering
3. Entity creation (form-based, calling MCP write tools)
4. Connection + diagram authoring
5. Schema-aware forms (loading attribute schemata to generate form fields)

---

## Acceptance Criteria

1. ~~All entity files have complete frontmatter + content + display blocks~~ ✓
2. ~~All domains populated: motivation, strategy, common, business, application, technology~~ ✓
3. ~~Requirement specialization hierarchy explicit via .outgoing.md connections~~ ✓
4. ~~Configurability principle with git-config requirements present~~ ✓
5. ~~Cross-domain connections modeled (motivation→strategy→common→application→technology)~~ ✓
6. ~~At least 7 diagrams covering all populated domains + cross-domain view~~ ✓
7. ~~Tooling can parse new filename convention and .outgoing.md format~~ ✓
8. ~~`ModelVerifier.verify_all()` passes on ENG-ARCH-REPO with no errors~~ ✓ (0 errors, 14 warnings)
9. ~~`generate_macros()` produces valid _macros.puml from ENG-ARCH-REPO entities~~ ✓ (115 macros)
10. ~~Duplicate goal file resolved~~ ✓
11. Common domain elements render in warm grey, distinct from business/application colors ✓
12. Configurable JSON Schema validation for frontmatter and attributes (WS-C)
13. Diagram layout with ortho routing and alternating group directions (WS-D)
14. GUI discovery & authoring tool (WS-E)
