# Scalable Architecture Management for Humans and AI

A framework for managing software architecture in a structured, git-versioned, and discoverable way — designed to work equally well for human practitioners and AI agents.

## Purpose and Goals

Architecture knowledge typically lives in slide decks, Confluence pages, or siloed modelling tools. This project treats architecture as **code**: structured, version-controlled, queryable, and verifiable — using [ArchiMate NEXT](https://www.opengroup.org/archimate-forum) as the modelling language.

The key ideas:

- **Two-tiered repository model**: an *enterprise* repo holds the organisation-wide baseline; per-project *engagement* repos extend it with local decisions, designs, and trade-offs. Entities flow from engagement to enterprise via a promotion workflow.
- **AI-native access**: an MCP server exposes the model to AI agents as typed tools — query, search, graph-traverse, create, edit, promote — without the agent needing to know the file layout.
- **Human access**: a REST API, a CLI, and a browser GUI provide the same capabilities for humans.
- **Verified integrity**: a built-in verifier enforces referential integrity, schema conformance, diagram syntax, and cross-repo reference rules.
- **Self-describing**: this repository contains an ArchiMate model of its own architecture — the tooling, requirements, principles, components, and design decisions are all modelled using the framework itself (see `engagements/ENG-ARCH-REPO/`).

## Two-Tiered Architecture

```
enterprise-repository/        ← organisation-wide baseline (read-only during engagement)
  model/
    motivation/  strategy/  business/  application/  technology/  ...

engagements/
  ENG-ARCH-REPO/              ← per-project engagement repo
    architecture-repository/
      model/                  ← engagement-specific entities and connections
      diagram-catalog/        ← diagrams (may reference enterprise entities via macros)
```

**Enterprise repo** — curated, long-lived entities shared across all engagements. Engagement tools can read it but not write to it directly.

**Engagement repo** — project-specific work. New entities and connections are created here. When ready, they are *promoted* to enterprise.

**Promotion** — a one-way transfer of entities (with transitive closure of connections) from engagement to enterprise. Conflict detection matches by `(artifact_type, friendly_name)` so the same logical entity under different artifact IDs is recognised. Conflicts offer three resolution strategies: accept engagement version, accept enterprise version, or manual merge.

**Asymmetric references** — enterprise entities can only reference other enterprise entities. Engagement entities may reference both engagement and enterprise entities. This is enforced by the verifier (errors E130/E131).

### Workspace Configuration

An `arch-workspace.yaml` at the workspace root declares both repos:

```yaml
engagement:
  local: engagements/ENG-ARCH-REPO/architecture-repository
  # or git: { url: "https://...", branch: main, path: .arch/repos/engagement }

enterprise:
  local: enterprise-repository
  # or git: { url: "https://...", branch: main, path: .arch/repos/enterprise }
```

Run `arch-init` to validate paths (or clone git repos) and write `.arch/init-state.yaml` with resolved absolute paths. All tooling reads this state file on startup.

## Repository Layout

```
src/
  common/          # Core library: parsing, verification, query, write, connection ontology
  tools/           # Entry-point servers: MCP model, MCP framework, GUI REST, arch-init
tools/
  gui/             # Vue 3 + TypeScript SPA (hexagonal ports-and-adapters)
engagements/
  ENG-ARCH-REPO/   # Self-describing architecture model + docs
enterprise-repository/
                   # Enterprise baseline (initially empty)
arch-workspace.yaml
```

## Tooling

The framework exposes three interfaces over the same underlying model.

### MCP Server (primary — AI agent access)

The MCP server is the intended interface for AI agents (Claude, Copilot, etc.). It exposes typed tools for querying and authoring the model:

**Query**

| Tool | Purpose |
|------|---------|
| `model_query_stats` | Count entities, connections, diagrams |
| `model_query_list_artifacts` | List with domain/type/status filtering |
| `model_query_read_artifact` | Read one artifact in full |
| `model_query_search_artifacts` | Full-text + keyword search |
| `model_query_find_neighbors` | Graph traversal from an entity |
| `model_query_find_connections_for` | Connections for an entity (direction + type filter) |
| `model_query_count_artifacts_by` | Count grouped by a field |

**Write**

| Tool | Purpose |
|------|---------|
| `model_create_entity` | Create entity (with dry-run) |
| `model_edit_entity` | Edit existing entity fields |
| `model_add_connection` | Add connection between entities (with dry-run) |
| `model_edit_connection` | Edit or remove an existing connection |
| `model_create_diagram` | Create ArchiMate diagram (with dry-run + PNG render) |
| `model_edit_diagram` | Edit existing diagram (regenerate PUML + PNG) |
| `model_create_matrix` | Create connection matrix (structured table view) |
| `model_promote_to_enterprise` | Promote entity + transitive closure to enterprise repo |
| `model_write_help` | List valid entity types and connection types |

**Verification and lifecycle**

| Tool | Purpose |
|------|---------|
| `model_verify_all` | Verify referential integrity and schema across all files |
| `model_verify_file` | Verify a single file |
| `model_tools_watch_start` | Start file watcher for live reload |
| `model_tools_watch_stop` / `model_tools_watch_status` | Manage file watcher |
| `model_tools_refresh` | Manually refresh cached model state |

Configure in `.mcp.json` (Claude Code) or `.vscode/mcp.json` (VS Code):

```json
{
  "mcpServers": {
    "sdlc-model": {
      "command": "uv",
      "args": ["run", "sdlc-mcp-model", "--transport", "stdio"],
      "env": {
        "SDLC_MCP_MODEL_REPO_ROOT": "engagements/ENG-ARCH-REPO/architecture-repository"
      }
    }
  }
}
```

When `arch-workspace.yaml` is present and `arch-init` has been run, the MCP server automatically discovers both repos from `.arch/init-state.yaml`. The env var override is still supported for single-repo use.

A second MCP server (`sdlc-mcp-framework`) provides section-level search and cross-reference traversal over the `docs/` directory (ADRs, standards, specs).

### REST API (GUI backend and programmatic access)

`sdlc-gui-server` exposes a REST API at `http://localhost:8000/api/`:

**Entities**

| Endpoint | Description |
|----------|-------------|
| `GET /api/stats` | Model statistics |
| `GET /api/entities` | List entities (`?domain=`, `?artifact_type=`, `?status=`, `?limit=`, `?offset=`) |
| `GET /api/entity?id=` | Full entity detail with summary, properties, notes, keywords, connection counts |
| `GET /api/connections?entity_id=&direction=` | Connections for an entity |
| `GET /api/neighbors?entity_id=&max_hops=` | Neighbour graph |
| `GET /api/search?q=` | Full-text search |
| `GET /api/ontology?source_type=` | Connection classification for a source entity type |
| `GET /api/ontology?source_type=&target_type=` | Permissible connection types for a source/target pair |
| `GET /api/write-help` | Valid entity types and connection types |
| `GET /api/entity-schemata?artifact_type=` | JSON attribute schema for an entity type |
| `GET /api/entity-display-search?q=` | Entity search enriched with ArchiMate display metadata |
| `POST /api/entity` | Create entity (`dry_run` supported) |
| `POST /api/entity/edit` | Edit entity fields (`dry_run` supported) |

**Diagrams**

| Endpoint | Description |
|----------|-------------|
| `GET /api/diagrams` | List diagrams (`?diagram_type=`, `?status=`) |
| `GET /api/diagram?id=` | Diagram detail with PUML source |
| `GET /api/diagram-image/{filename}` | Serve rendered PNG |
| `GET /api/diagram-svg?id=` | Render diagram PUML to interactive SVG on demand |
| `GET /api/diagram-entities?id=` | Entities referenced in a diagram (with display aliases) |
| `GET /api/diagram-connections?id=` | Connections between entities present in a diagram |
| `GET /api/diagram-refs?source_id=&target_id=` | Find diagrams referencing a connection |
| `POST /api/diagram` | Create diagram from entity/connection selection |
| `POST /api/diagram/edit` | Edit diagram entity/connection selection |
| `POST /api/diagram/preview` | Preview diagram as PNG + PUML without writing files |

**Connections**

| Endpoint | Description |
|----------|-------------|
| `POST /api/connection` | Add connection (`dry_run` supported) |
| `POST /api/connection/remove` | Remove connection (`dry_run` supported) |

### GUI Tool — Browser Interface

`sdlc-gui-server` also serves the Vue SPA at `/`. The GUI provides a full read/write interface for human users and is backed by the REST API above.

**Entity management**
- **Entity list** — filterable by domain, artifact type, and status; connection count badges; "+ Create Entity" button
- **Entity detail** — metadata, parsed summary/properties/notes, three-column connection layout (Incoming / Symmetric / Outgoing); each panel shows ontology-permissible groups with per-group add ("+") and per-connection remove ("×") buttons; connection description tooltips
- **Entity edit** — inline edit mode on the detail view; type-aware property fields; dry-run preview before commit
- **Entity create** — form with grouped type selector, schema-driven required property fields, dry-run preview, navigate to created entity on confirm
- **Search** — full-text search with type and domain chips per result

**Diagram management**
- **Diagram list** — grid with diagram-type filter bar
- **Diagram detail** — interactive SVG viewer rendered on demand from stored PUML:
  - Pan (drag), zoom (scroll wheel), reset (double-click)
  - Clickable entity nodes → entity metadata in sidebar (name, type, domain, status, content summary)
  - Clickable connection arrows → connection type and source → target detail in sidebar
  - Toggleable raw PUML source
  - "Edit" button links to diagram editor
- **Diagram create** — live entity search with ArchiMate-type glyphs, auto-detection of connections between selected entities, PNG preview, save to repository
- **Diagram edit** — pre-loads entities from the existing diagram, same UI as creation

**Graph explorer**
- Force-directed SVG graph rooted at any entity
- Click node to select → sidebar shows metadata; double-click to expand neighbors
- Click edge for connection detail in sidebar
- Drag nodes, pan canvas, scroll to zoom; collapse expanded subtrees on double-click

### CLI

```bash
# Initialise workspace (validate repos, write .arch/init-state.yaml)
arch-init

# Generate PlantUML macros (_macros.puml)
python -m src.tools.generate_macros path/to/architecture-repository
```

## Setup

**Requirements**: Python ≥ 3.13, Java ≥ 11 (for diagram verification and rendering), Node ≥ 18 (for GUI development), `uv`.

```bash
# Python environment
uv sync                        # core dependencies
uv sync --extra gui            # + GUI server dependencies

# Download plantuml.jar (SHA-256-verified from Maven Central, pinned version)
get-plantuml                   # → tools/plantuml.jar (gitignored)
# To upgrade: edit PLANTUML_VERSION in src/tools/get_plantuml.py, re-run

# Initialise workspace
arch-init                      # reads arch-workspace.yaml, writes .arch/init-state.yaml

# Install MCP servers into your AI tool's config
# (edit .mcp.json — see Tooling section above)

# GUI development (hot-reload)
sdlc-gui-server &
cd tools/gui && npm install && npm run dev
# → http://localhost:5173
```

> **plantuml.jar** is downloaded on demand and gitignored. The Docker build fetches and verifies it automatically. For local development, `get-plantuml` places it at `tools/plantuml.jar`, which is the path the verifier and diagram renderer expect.

## GUI — Dockerized

The GUI packages the Vue SPA and the FastAPI REST server into a single container. The repository is mounted from the host at runtime, so no rebuild is needed when model files change.

```bash
# Start with the bundled self-describing model
docker compose up --build
# -> http://localhost:8000

# Point at a different repository
ARCH_REPO_ROOT=/path/to/your/architecture-repository docker compose up --build
```

The container serves the Vue SPA at `/` and the REST API at `/api/`. System dependencies for PlantUML SVG/PNG rendering (Java, Graphviz, fonts) are included in the image.
