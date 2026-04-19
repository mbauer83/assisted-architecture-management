# Research Guide: Designing an ArchiMate Modeling Skill

This file enumerates the minimally sufficient set of files to read — with
line ranges where the file is long — in order to understand the system's
conventions, tooling, and modeling constraints well enough to design an
effective ArchiMate modeling skill.

> **Critical framing — two distinct audiences for this guide:**
>
> 1. **The skill designer** (you, reading this now) needs to understand the
>    system deeply: ontology concepts, what the MCP tools expose, how the data
>    is structured.  For that purpose, reading Python source and YAML config is
>    appropriate.
>
> 2. **The skill being designed** should interact with the repository through
>    MCP tools (`model_*`) as the strong default.  Direct file or directory
>    reads are acceptable in edge cases where the MCP tools genuinely do not
>    suffice — prefer targeted reads (specific sections of specific files) over
>    broad exploration in those cases.  Writing and all repository mutations
>    must go through MCP tools without exception.
>
> Where this guide references Python source, that is reading material for the
> designer — not API surface the skill should routinely use.

Read the sections in the order given.

---

## 1. Modeling ontology — concepts the skill must internalise

These files define *what to model* and *when*.  The skill designer must
understand them thoroughly because this knowledge is baked into the skill's
reasoning, not looked up at runtime.  The skill calls
`model_write_modeling_guidance` at runtime to retrieve the same information
for the types currently under consideration — it does not re-read these files.

### 1a. Entity types
`config/entity_ontology.yaml` (full file, 433 lines)

**Learn:** Every entity type, its ArchiMate domain, abstract element classes,
and the `create_when` / `never_create_when` guidance for each.  This is the
primary reference for *which type to choose and why*.

Note: the YAML also contains `domain`, `subdir`, and `prefix` fields that are
filesystem / ID concerns handled entirely by the tools.  The skill only needs
to know the entity-type *name* (e.g. `requirement`) and the modeling guidance.
Directory layout is not the skill's concern.

### 1b. Connection types and permitted relationships
`config/connection_ontology.yaml` (full file, 267 lines)

**Learn:** Every supported connection type name (e.g. `archimate-realization`),
its symmetry, and the `permitted_relationships` rules encoding which ArchiMate
connections are valid between which entity types.  The skill needs to know
*which connection type to choose*; the tools enforce validity.

Note: `directory` fields in the YAML are filesystem implementation details.
The skill uses connection-type *names* only.

### 1c. Type dataclasses
`src/common/model_write_catalog.py` (full file, 38 lines)

**Learn:** `EntityTypeInfo` and `ConnectionTypeInfo` field names and their
meaning.  This is the typed shape of what `model_write_modeling_guidance`
returns — reading it gives precise vocabulary for interpreting tool output.

---

## 2. Ontology APIs — understand what the guidance tool exposes

Read these to understand the data structures behind the MCP guidance tool.
**The skill must not call these Python functions directly.**

### 2a. Ontology loader — exported registries
`src/common/ontology_loader.py` (full file, 128 lines)

**Learn:** Which registries exist (`ENTITY_TYPES`, `CONNECTION_TYPES`,
`PERMITTED_RELATIONSHIPS`, `RULES_BY_SOURCE`, `RULES_BY_TARGET`,
`CLASS_MEMBERS`), how `@class` references expand to concrete type names, and
what `SYMMETRIC_CONNECTIONS` means.  This explains the data underlying the
`permitted_connections` field returned by the guidance tool.

### 2b. Relationship query API
`src/common/connection_ontology.py` (full file, 79 lines)

**Learn:** What `classify_connections` returns — the `outgoing / incoming /
symmetric` structure that `model_write_modeling_guidance` includes per type.
Reading this clarifies how to interpret the guidance tool's output at runtime.

---

## 3. MCP tool surface — the skill's entire runtime API

These are the tools the skill calls.  Read the MCP registration files to
learn parameter names, defaults, and tool descriptions.  Do not read the
underlying implementation files in `src/tools/model_write/`; those are
internal to the server.

### 3a. Guidance and entity creation
`src/tools/model_mcp/write/entity.py` (full file, 86 lines)

**MCP tools exposed:**
- `model_write_help` — full type catalog (use once for orientation)
- `model_write_modeling_guidance(filter)` — focused guidance per type or
  domain; `filter` is a list of entity-type names OR domain names, never
  mixed; omit for all types.  **This is the skill's primary oracle at
  runtime.**
- `model_create_entity` — creates an entity file; always call with
  `dry_run=true` first

### 3b. Connection creation
`src/tools/model_mcp/write/connection.py` (full file, 129 lines)

**MCP tool exposed:** `model_add_connection` — parameters include
`src_cardinality` / `tgt_cardinality` (format: `"1"`, `"0..1"`, `"1..*"`,
`"*"`), `dry_run`, and automatic GRF proxy creation for global entities.

### 3c. Edit tools
`src/tools/model_mcp/edit_tools.py` (lines 1–100)

**MCP tools exposed:** `model_edit_entity` (updatable fields) and
`model_edit_connection` (`operation="update"` to change description or
cardinalities, `operation="remove"` to delete).

### 3d. Query — list and read
`src/tools/model_mcp/query_list_read_tools.py` (full file, 99 lines)

**MCP tools exposed:** `model_query_list_artifacts` (filter by domain, type,
status) and `model_query_read_artifact` (mode: `"summary"` or `"full"`).
These are the skill's only way to inspect existing model content — never read
files directly.

### 3e. Query — graph traversal
`src/tools/model_mcp/query_graph_tools.py` (full file, 95 lines)

**MCP tools exposed:** `model_query_find_connections_for` and
`model_query_find_neighbors`.  Use to verify whether a connection already
exists before adding one.

### 3f. Query — search and stats
`src/tools/model_mcp/query_search_tools.py` (full file, 85 lines)
`src/tools/model_mcp/query_stats_tools.py` (full file, 65 lines)

**MCP tools exposed:** `model_query_search_artifacts` (keyword search) and
`model_query_stats` (counts by domain/type — useful for initial orientation).

---

## 4. File format — for interpreting dry_run previews only

The skill never reads or writes model files.  The one exception to needing
format knowledge is interpreting the `content` field returned by write tools
when `dry_run=true` — this is a human/AI-readable preview of what *would* be
written.

`src/common/model_write_formatting.py` lines 1–128

**Learn:** The markdown structure of entity files (`§content`, `§display`
sections) and outgoing connection files (`§connections` section, header format
`### conn-type [src_card] → [tgt_card] target_id`).  Understanding this lets
the skill meaningfully review a dry-run preview before committing.

---

## 5. Repo scoping — understanding MCP tool parameters

`src/tools/model_mcp/context.py` lines 1–52

**Learn:** The `repo_root`, `repo_preset`, and `repo_scope` parameters that
appear on every write tool, what `RepoPreset` values are available, and the
difference between `"engagement"`, `"enterprise"`, and `"both"` scopes.  The
skill passes these parameters but never resolves paths itself.

---

## 6. What NOT to read for skill design

- `src/common/model_verifier*.py` — verification is done server-side; the
  tools report issues in their return value
- `src/tools/model_write/*.py` — I/O implementations; the skill never calls
  these directly
- `src/tools/gui_routers/` — REST API for the GUI, not the MCP surface
- `src/common/model_query*.py` — internal query engine wrapped by the MCP tools
- `tests/` — test infrastructure
- Model files on disk (`model/**/*.md`, `*.outgoing.md`, `*.puml`) — prefer
  `model_query_read_artifact`; direct reads are a fallback for cases the tool
  does not cover

---

## 7. Recommended reading sequence

1. `config/entity_ontology.yaml` — full read; internalise types and guidance
2. `config/connection_ontology.yaml` — full read; internalise relationships
3. `src/common/model_write_catalog.py` — skim; learn field vocabulary
4. `src/common/connection_ontology.py` — skim; understand guidance tool output
5. `src/tools/model_mcp/write/entity.py` — read; learn guidance + create API
6. `src/tools/model_mcp/write/connection.py` — read; learn connection API
7. `src/tools/model_mcp/query_list_read_tools.py` + `query_graph_tools.py`
   — read; learn existence-check tools
8. `src/tools/model_mcp/context.py` lines 1–52 — skim; learn repo scoping

Total estimated reading: ~850–950 lines.

---

## 8. Key design constraints for the skill

**MCP-first — strongly preferred:**
The skill should access model content and perform all writes through `model_*`
MCP tools as the default.  Direct file or directory reads are acceptable when
MCP tools genuinely do not cover the need — in those cases prefer reading
targeted sections of specific files over broad exploration.  All writes and
repository mutations must go through MCP tools without exception.

**Workflow discipline:**
- Call `model_write_modeling_guidance` with the relevant types or domain
  before deciding what to model — do not rely on baked-in knowledge alone.
- Use `model_query_search_artifacts` or `model_query_list_artifacts` to check
  for duplicates before creating.
- Always call write tools with `dry_run=true` first; review the `content`
  preview; only commit with `dry_run=false` after validation.

**Modeling rules:**
- Use `archimate-*` connection types for ArchiMate entities; ER, sequence,
  activity, and usecase connections belong to specific diagram types only.
- Add `src_cardinality` / `tgt_cardinality` only when multiplicity is
  architecturally significant — leave absent otherwise.
- GRF proxy creation is automatic when connecting to enterprise entities; the
  skill does not need to handle it.
- Symmetric connections (e.g. `archimate-association`) may be stored from
  either end; the tools handle canonicalisation.
