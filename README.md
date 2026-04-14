# Scalable Architecture Management for Humans and AI

A framework for managing software architecture in a structured, git-versioned, and discoverable way — designed to work equally well for human practitioners and AI agents.

## Purpose and Goals

Architecture knowledge typically lives in slide decks, Confluence pages, or siloed modelling tools. This project treats architecture as **code**: structured, version-controlled, queryable, and verifiable — using [ArchiMate NEXT](https://www.opengroup.org/archimate-forum) as the modelling language.

The key ideas:

- **Single source of truth**: one git repository contains the full architecture model as plain Markdown files with structured frontmatter (entities, connections, diagrams).
- **AI-native access**: an MCP server exposes the model to AI agents as typed tools — query, search, graph-traverse, create, edit — without the agent needing to know the file layout.
- **Human access**: a REST API, a CLI, and a browser GUI provide the same capabilities for humans.
- **Verified integrity**: a built-in verifier enforces referential integrity, schema conformance, and diagram syntax.
- **Self-describing**: this repository contains an ArchiMate model of its own architecture — the tooling, requirements, principles, components, and design decisions are all modelled using the framework itself (see `engagements/ENG-ARCH-REPO/`).

## The Architecture Model of Its Own Design

The engagement at `engagements/ENG-ARCH-REPO/architecture-repository/` is a fully populated ArchiMate model that describes **this system** — its drivers, goals, requirements, application components, services, and technology. It covers all six ArchiMate domains (motivation, strategy, business, common, application, technology) with 117+ entities, 119+ connections, and 7 diagrams.

Exploring it through the GUI or the MCP tools is the quickest way to understand both the framework's capabilities and the architectural decisions behind it.

## Repository Layout

```
src/
  common/          # Core library: parsing, verification, query, write
  tools/           # Entry-point servers: MCP model, MCP framework, GUI REST
tools/
  gui/             # Vue 3 + TypeScript SPA (hexagonal ports-and-adapters)
  plantuml.jar     # Symlink — diagram syntax verification
engagements/
  ENG-ARCH-REPO/   # Self-describing architecture model + docs
```

## Tooling

The framework exposes three interfaces over the same underlying model. They are complementary, not alternatives.

### MCP Server (primary — AI agent access)

The MCP server is the intended interface for AI agents (Claude, Copilot, etc.). It exposes typed tools for querying and authoring the model:

| Tool | Purpose |
|------|---------|
| `model_query_stats` | Count entities, connections, diagrams |
| `model_query_list_artifacts` | List with domain/type filtering |
| `model_query_read_artifact` | Read one entity in full |
| `model_query_search_artifacts` | Full-text + keyword search |
| `model_query_find_neighbors` | Graph traversal |
| `model_create_entity` | Create entity (with dry-run) |
| `model_add_connection` | Add connection (with dry-run) |
| `model_create_diagram` | Create diagram |
| `model_edit_entity/connection/diagram` | Edit existing artefacts |
| `model_verify_all` | Verify referential integrity and schema |

Configure in `.mcp.json` (Claude Code) or `.vscode/mcp.json` (VS Code):

```json
{
  "mcpServers": {
    "sdlc-mcp-model": {
      "command": "sdlc-mcp-model",
      "env": { "SDLC_MCP_MODEL_REPO_ROOT": "path/to/architecture-repository" }
    }
  }
}
```

A second MCP server (`sdlc-mcp-framework`) provides section-level search and cross-reference traversal over the `docs/` directory (ADRs, standards, specs).

### REST API (GUI backend and programmatic access)

`sdlc-gui-server` exposes a REST API at `http://localhost:8000/api/`:

| Endpoint | Description |
|----------|-------------|
| `GET /api/stats` | Model statistics |
| `GET /api/entities` | List entities (`?domain=`, `?artifact_type=`, `?status=`) |
| `GET /api/entity?id=` | Full entity detail |
| `GET /api/connections?entity_id=&direction=` | Connections for an entity |
| `GET /api/neighbors?entity_id=&max_hops=` | Neighbour graph |
| `GET /api/search?q=` | Full-text search |

### CLI

Direct Python entry points for scripting and CI pipelines:

```bash
# Verify the full model
python -m src.common.model_query --help

# Generate PlantUML macros (_macros.puml)
python -m src.tools.generate_macros --repo-root path/to/architecture-repository
```

## Setup

**Requirements**: Python ≥ 3.13, Node ≥ 18 (for GUI development), `uv` or `pip`.

```bash
# Python environment
pip install -e ".[gui]"          # or: uv sync --extra gui

# Install MCP servers into your AI tool's config
# (edit .mcp.json — see Tooling section above)

# GUI development (hot-reload)
sdlc-gui-server --repo-root engagements/ENG-ARCH-REPO/architecture-repository &
cd tools/gui && npm install && npm run dev
# → http://localhost:5173
```

## GUI — Dockerized

The GUI packages the Vue SPA and the FastAPI REST server into a single container. The repository is mounted from the host at runtime, so no rebuild is needed when model files change (the server re-reads on each request).

**Start with the bundled self-describing model:**

```bash
docker compose up --build
# → http://localhost:8000
```

**Point at a different repository:**

```bash
ARCH_REPO_ROOT=/path/to/your/architecture-repository docker compose up --build
```

**Or run the image directly:**

```bash
docker build -t arch-gui .
docker run -p 8000:8000 -v /path/to/architecture-repository:/repo:ro arch-gui
# → http://localhost:8000
```

The container serves the Vue SPA at `/` and the REST API at `/api/`. The `--host 0.0.0.0` flag is set in the default `CMD` so the port binding works out of the box.
