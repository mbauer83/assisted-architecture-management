# Scalable Architecture Management for Humans and AI

A system for managing software architecture in a structured, git-versioned, and discoverable way — designed to work equally well for human practitioners and AI agents.

## Purpose and Goals

Architecture knowledge typically lives in slide decks, Confluence pages, or siloed modelling tools. This project treats architecture as **code**: structured, version-controlled, queryable, and verifiable — using [ArchiMate NEXT](https://www.opengroup.org/archimate-forum) as the modelling language.

The key ideas:

- **Two-tiered repository model**: an *enterprise* repo holds the organisation-wide baseline; per-project *engagement* repos extend it with local decisions, designs, and trade-offs. Entities flow from engagement to enterprise via a promotion workflow.
- **AI-native access**: an MCP server exposes the model to AI agents as typed tools — query, search, graph-traverse, create, edit, promote — without the agent needing to know the file layout.
- **Human access**: a REST API, a CLI, and a browser GUI provide the same capabilities for humans.
- **Verified integrity**: a built-in verifier enforces referential integrity, schema conformance, diagram syntax, and cross-repo reference rules.
- **Self-describing**: this repository contains an ArchiMate model of its own architecture — the tooling, requirements, principles, components, and design decisions are all modelled using the repository itself (see `engagements/ENG-ARCH-REPO/`).

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

**Promotion** — a one-way transfer of an explicitly selected set of entities and connections from engagement to enterprise. Conflict detection matches by `(artifact_type, friendly_name)` so the same logical entity under different artifact IDs is recognised. Conflicts offer three resolution strategies: accept engagement version, accept enterprise version, or manual merge.

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
  tools/           # Entry-point servers: MCP/REST backend, GUI server wrapper, arch-init
tools/
  gui/             # Vue 3 + TypeScript SPA (hexagonal ports-and-adapters)
engagements/
  ENG-ARCH-REPO/   # Self-describing architecture model + docs
enterprise-repository/
                   # Enterprise baseline (initially empty)
arch-workspace.yaml
```

## Tooling

The repository exposes three interfaces over the same underlying artifacts.

### MCP Server (primary — AI agent access)

The MCP server is the primary interface for AI agents. It exposes typed `artifact_*` tools for querying, verification, authoring, and promotion across entities, connections, diagrams, and documents.

**Artifact query**

| Tool | Purpose |
|------|---------|
| `artifact_query_stats` | Repository counts and grouped breakdowns |
| `artifact_query_list_artifacts` | Metadata listing with domain/type/status filters |
| `artifact_query_read_artifact` | Read one artifact in summary or full mode; supports document section reads |
| `artifact_query_search_artifacts` | Ranked search across entities, connections, diagrams, and documents |
| `artifact_query_find_neighbors` | Graph traversal from a starting entity |
| `artifact_query_find_connections_for` | Connections touching an entity with direction/type filters |
| `artifact_diagram_scaffold` | Suggest diagram scope and PUML scaffolding from selected entities |

**Artifact write / edit**

| Tool | Purpose |
|------|---------|
| `artifact_write_help` | Catalog of valid entity and connection types |
| `artifact_write_modeling_guidance` | Focused modeling guidance by domain or entity type |
| `artifact_create_entity` | Create entity (with dry-run) |
| `artifact_edit_entity` | Edit existing entity fields |
| `artifact_delete_entity` | Delete an entity with dependency checks |
| `artifact_add_connection` | Add connection between entities (with dry-run) |
| `artifact_edit_connection` | Edit or remove an existing connection |
| `artifact_edit_connection_associations` | Add or remove `§assoc` second-order associations |
| `artifact_create_diagram` | Create an ArchiMate diagram from PUML |
| `artifact_edit_diagram` | Edit an existing diagram |
| `artifact_delete_diagram` | Delete a diagram and rendered siblings |
| `artifact_create_matrix` | Create connection matrix (structured table view) |
| `artifact_create_document` | Create a document from a configured doc type |
| `artifact_edit_document` | Edit an existing document |
| `artifact_delete_document` | Delete a document |
| `artifact_promote_to_enterprise` | Promote an explicitly selected entity/connection set to enterprise repo |

**Artifact verification**

| Tool | Purpose |
|------|---------|
| `artifact_verify` | Verify one file or the whole repo, with summary or full issue detail |

Configure in `.mcp.json` (Claude Code) or `.vscode/mcp.json` (VS Code):

```json
{
  "mcpServers": {
    "arch-repo": {
      "command": "uv",
      "args": ["run", "arch-mcp-stdio"]
    }
  }
}
```

`arch-mcp-stdio` auto-starts the unified `arch-backend` when needed and connects over `/mcp`, so GUI and MCP traffic share the same in-process cache and write queue.

This is intended to work well with MCP hosts that eagerly start configured servers when the IDE/app launches: the spawned command becomes a lightweight launcher/bridge, while `arch-backend` remains the single warm backend for the workspace.

When `arch-workspace.yaml` is present and `arch-init` has been run, the backend discovers both repos from `.arch/init-state.yaml`. The env var override is still supported for direct standalone server use.

By default, the launcher manages a local host backend. It does **not** guess that a Dockerized or otherwise external backend is already running just because something responds on port `8000`.

To attach MCP launchers to an externally managed backend instead, set:

```json
{
  "mcpServers": {
    "arch-repo": {
      "command": "uv",
      "args": ["run", "arch-mcp-stdio"],
      "env": {
        "ARCH_MCP_BACKEND_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
```

That makes the deployment choice explicit and avoids ambiguous startup behavior.

### REST API (GUI backend and programmatic access)

`arch-backend` exposes a REST API at `http://localhost:8000/api/` and MCP Streamable HTTP at `http://localhost:8000/mcp`:

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
| `POST /api/entity/remove` | Delete entity (`dry_run` supported) |

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
| `GET /api/diagram-download?id=&format=png|svg` | Download rendered diagram output |
| `POST /api/diagram` | Create diagram from entity/connection selection |
| `POST /api/diagram/edit` | Edit diagram entity/connection selection |
| `POST /api/diagram/preview` | Preview diagram as PNG + PUML without writing files |
| `POST /api/diagram/remove` | Delete diagram (`dry_run` supported) |

**Connections**

| Endpoint | Description |
|----------|-------------|
| `POST /api/connection` | Add connection (`dry_run` supported) |
| `POST /api/connection/edit` | Edit connection description/cardinalities |
| `POST /api/connection/associate` | Add or remove connection associations |
| `POST /api/connection/remove` | Remove connection (`dry_run` supported) |
| `POST /api/cleanup-broken-refs` | Find and optionally clean up broken GRF proxies |

**Documents**

| Endpoint | Description |
|----------|-------------|
| `GET /api/document-types` | List configured document types and required sections |
| `GET /api/document-schemata` | Read raw document-type schemata |
| `GET /api/documents` | List documents (`?doc_type=`, `?status=`, `?limit=`, `?offset=`) |
| `GET /api/document?id=` | Read one document |
| `POST /api/document` | Create document (`dry_run` supported) |
| `PUT /api/document/{id}` | Edit document (`dry_run` supported) |
| `DELETE /api/document/{id}?dry_run=` | Delete document |

**Promotion**

| Endpoint | Description |
|----------|-------------|
| `POST /api/promote/plan` | Compute promotion plan, conflicts, and warnings for an explicit selection |
| `POST /api/promote/execute` | Execute promotion for an explicit selection and replace engagement artifacts with GRF proxies |

**Admin mode**

When `arch-backend --admin-mode` is used, `/admin/api/*` exposes enterprise-repo write endpoints for entities, connections, diagrams, and `GET /admin/api/server-info`.

### GUI Tool — Browser Interface

`arch-backend` also serves the Vue SPA at `/`. `arch-gui-server` is a thin wrapper around the unified backend entry point.

Current GUI capabilities:

- **Home / overview** — engagement vs global summary cards, domain breakdown, connection-type breakdown
- **Entities catalog** — engagement and global views, domain filtering, type filter, sortable table, connection-weighted treemap, hierarchy display for specialization/composition/aggregation
- **Entity detail** — metadata, parsed content, connection counts, inline editing, deletion, and three connection panels with ontology-aware add/edit/remove flows
- **Entity creation** — grouped type selector, schema-aware properties, dry-run preview, create-and-open flow
- **Search** — full-text artifact search with typed result rows
- **Diagrams catalog** — engagement and global listings
- **Diagram detail** — interactive SVG viewer, entity/connection side panels, rendered download menu, raw PUML toggle, edit entry point
- **Diagram create/edit** — entity search with glyphs, row-level related-entity expansion, connection inclusion management, preview before save
- **Graph explorer** — force-directed interactive neighborhood exploration from any entity
- **Promotion view** — root entity picker, explicit entity/connection set curation, conflict strategy selection, execution to the global repository

The GUI is a human-facing client over the REST API. It does not expose every admin endpoint as dedicated screens, but it does cover normal engagement authoring, exploration, and promotion workflows.

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

# Preferred local default: run the unified backend on the host.
# It serves the built Vue app at http://localhost:8000/
arch-backend &

# Inspect / stop / restart it when needed
arch-backend --status
arch-backend --stop
arch-backend --restart

# Frontend development with Vite hot-reload:
# Vite serves the UI at http://localhost:5173/ and proxies /api to arch-backend on :8000
cd tools/gui && npm install && npm run dev
# → open http://localhost:5173
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

If you want host-started MCP clients to attach to a Dockerized backend instead of auto-starting a separate host backend:

- expose the container on `localhost:8000` as the compose file already does
- configure the MCP client to run `arch-mcp-stdio`
- set `ARCH_MCP_BACKEND_URL=http://127.0.0.1:8000` in that MCP config

In practice this means Dockerized backend and auto-started MCP servers can work together, but they are still two deployment modes:

- normal local-dev mode: host `arch-backend` + host MCP launchers
- containerized mode: Docker `arch-backend` + host MCP launchers explicitly attaching to the published port
