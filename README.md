# Scalable Architecture Management for Humans and AI

A system for managing software architecture in a structured, git-versioned, and discoverable way — designed to work equally well for human practitioners and AI agents.

## Purpose and Goals

Architecture knowledge typically lives in slide decks, Confluence pages, or siloed modelling tools. This project treats architecture as **code**: structured, version-controlled, queryable, and verifiable — using [ArchiMate NEXT](https://www.opengroup.org/archimate-forum) as the modelling language.

The key ideas:

- **Two-tiered repository model**: an *enterprise* repo holds architecture content that is valid organisation-wide and represents a deliberately shared state; per-project *engagement* repos are used both for adding specific local detail for teams / individuals and to draft and develop architecture models before promoting them to the enterprise repository via a specific workflow.
- **AI-native access**: an MCP server exposes the model to AI agents as typed tools — without the agent needing to know the file layout, it can query, search, navigate relationships, create/edit/delete artifacts, and promote decisions to shared repositories.
- **Human access**: a REST API, a CLI, and a browser GUI provide the same capabilities for humans.
- **Verified integrity**: a built-in verifier enforces referential integrity, schema conformance, diagram syntax, and cross-repo reference rules. Models stay consistent as humans and AI edit them together.
- **Self-describing**: this repository contains an ArchiMate model of its own architecture — the tooling, requirements, principles, components, and design decisions are all modelled using the repository itself (see `engagements/ENG-ARCH-REPO/`).

## Two-Tiered Architecture

```
enterprise-repository/        ← organisation-wide baseline (read-only during engagement)
  model/
    motivation/  strategy/  business/  application/  technology/  ...

engagements/
  ENG-ARCH-REPO/              ← per-project repo
    architecture-repository/
      model/                  ← engagement-specific entities and connections
      diagram-catalog/        ← diagrams (may reference enterprise entities via macros)
      documents/              ← ADRs, standards, specifications, and other structured docs
```

**Enterprise repo** — curated, long-lived entities shared across all engagements. Engagement tools can read it but not write to it directly.

**Engagement repo** — project-specific work. New entities, connections, diagrams, and documents are created here. When ready, they are *promoted* to enterprise.

**Promotion** — a one-way transfer of an explicitly selected set of entities and connections from engagement to enterprise. Conflict detection matches by both `(artifact_type, normalized_name)` and `(artifact_type, id_suffix)` — the same entity renamed in one repo is caught by the ID match, and the same name with a different ID is caught by the name match. Conflicts offer three resolution strategies: accept engagement version, accept enterprise version, or manual merge. Promotion is blocked when the engagement repo's schemata are not supersets of the enterprise schemata (see **Configuration Reference** below).

**Asymmetric references** — enterprise entities can only reference other enterprise entities. Engagement entities may reference both engagement and enterprise entities. This is enforced by the verifier.

### Workspace Configuration

An `arch-workspace.yaml` at the workspace root declares the two repositories:

```yaml
engagement:
  local: engagements/ENG-ARCH-REPO/architecture-repository
  # or git: { url: "https://...", branch: main, path: .arch/repos/engagement }

enterprise:
  local: enterprise-repository
  # or git: { url: "https://...", branch: main, path: .arch/repos/enterprise }
```

Run `arch-init` to validate paths (or clone git repos) and write `.arch/init-state.yaml` with resolved absolute paths. All tooling reads this state file on startup.

Backend settings (port, log path, log level) are configured in `config/settings.yaml`, not in `arch-workspace.yaml`. See **Configuration Reference** below.

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

## Affordances for Humans and AI Agents

The system provides three complementary interfaces (REST API, MCP server, browser GUI) over the same underlying artifacts. This section describes what's possible; the interfaces differ only in ease of use for each audience.

### Discovery and Exploration

**Search and Filter**
- Full-text search across all artifacts (entities, connections, diagrams, documents) with relevance ranking
- Filter by domain, type, status, keyword
- Browse hierarchies (specialization, composition, aggregation)
- Explore relationship graphs with interactive navigation: "What connects to this? How many hops to reach that concept?"

**Consistent Metadata**
- Every artifact has uniform attributes: name, version, status (draft/active/retired), keywords, creation/modification timestamps
- Entities are scoped to a domain (motivation, strategy, business, application, technology, implementation) and classified by type (Goal, Requirement, Capability, Service, Application Component, Technology, etc.)
- Connections are typed (realizes, supports, composes, specializes, depends-on, etc.) with optional source/target cardinality and free-form descriptions

This consistency means both humans and AI can rely on predictable structure for exploration and analysis.

### Verification and Integrity Checks

The system continuously verifies:
- **Schema conformance**: entity properties match their type definition
- **Referential integrity**: every connection endpoint exists and is of the expected type
- **Cross-repo consistency**: enterprise entities don't reference engagement entities; GRF (global-entity-reference) proxies correctly track promoted entities
- **Diagram syntax**: PlantUML is valid; referenced entities are present
- **Document frontmatter**: required fields match schema

Verification runs:
- On every write (blocks invalid operations immediately)
- On demand for the whole repository (CI/CD, pre-promotion review)
- In real time in the GUI (validation issues highlight as you type)

AI agents receive verification results in structured form (error codes, locations, remediation hints). Humans see clear error messages and suggestions in the UI.

### Authoring and Editing

**For Humans:**
- **Form-driven entity creation**: schema-aware form fields with guided property entry
- **Inline connection editing**: drag-and-drop connection pickers with ontology-guided relationship types
- **Diagram authoring**: visual entity picker with related-entity expansion, side-by-side connection management, live PUML preview
- **Document authoring**: type-specific templates with required sections and frontmatter fields pre-populated
- **Preview before commit**: dry-run every write operation to see validation results before saving
- **Interactive SVG diagrams**: click into entities from diagram views, follow relationships visually

**For AI Agents:**
- **Typed tools**: every creation/edit operation is a typed tool with schema validation built in
- **Dry-run mode**: agents can preview changes before committing
- **Guided namespace**: write tools offer autocomplete over existing entity IDs and types
- **Structured feedback**: verification errors return codes and locations, not just prose

**For Both:**
- **Atomic transactions**: writes are serialized to prevent conflicts between concurrent human and AI edits
- **Version control**: every change is committed to git with authorship; history is queryable
- **Explicit promotion**: edits stay local to the engagement repo; promotion to enterprise is explicit and traced

### Write-Block and Sync Safety

When multiple sources (humans, AI agents, scheduled syncs) need to coordinate:
- **Write blocking**: repos can be temporarily blocked during git sync operations without losing data
- **Auto-recovery**: if a sync fails, the system automatically unblocks after a timeout to prevent deadlock
- **Real-time notifications**: the GUI subscribes to `GET /api/events` (SSE) and displays sync progress and write-lock state via toast notifications; AI agents poll REST endpoints or read write-block state from operation responses rather than receiving push events

### Modeling Guidance

The system exposes:
- **Entity type catalog**: valid types per domain, create-when/never-create guidance, valid outgoing/incoming connections
- **Connection ontology**: for a given source entity type, which target types and connection types are permissible
- **Domain reference models**: example entities and connection patterns per domain (motivation, strategy, business, application, technology)

Humans can browse this guidance in the GUI; AI agents request it as structured data before authoring.

## Interfaces

The system exposes three complementary interfaces to the same artifact store:

### MCP Server (AI Agents)

Configure in `.mcp.json` (Claude Code) or `.vscode/mcp.json` (VS Code):

```json
{
  "mcpServers": {
    "arch-repo-read": {
      "command": "uv",
      "args": ["run", "arch-mcp-stdio-read"]
    },
    "arch-repo-write": {
      "command": "uv",
      "args": ["run", "arch-mcp-stdio-write"]
    }
  }
}
```

The MCP interface is split into two separate servers so agents can be constrained by capability (read-only access vs. authoring).

Both STDIO bridges auto-start the unified backend when needed and connect to it via HTTP, so GUI and MCP traffic share the same in-process cache and write queue. This avoids conflicts and ensures humans and AI see the latest state.

To attach MCP clients to an external backend instead:

```json
{
  "mcpServers": {
    "arch-repo-read": {
      "command": "uv",
      "args": ["run", "arch-mcp-stdio-read"],
      "env": { "ARCH_MCP_BACKEND_URL": "http://127.0.0.1:8000" }
    }
  }
}
```

### REST API (Programmatic Access)

`arch-backend` exposes a REST API at `http://localhost:<backend-port>/api/` for querying and authoring. This is the same interface the browser GUI uses, so it covers the full feature set.

### Browser GUI

`arch-backend` also serves the Vue SPA at `/`. The GUI covers:

- **Overview** — engagement vs. enterprise summary, domain and connection-type breakdowns
- **Exploration** — entity and diagram catalogs with filtering, search, treemap views, graph navigation
- **Authoring** — entity/diagram/document creation and editing with schema-aware forms and live preview
- **Verification** — real-time validation feedback, conflict detection on promotion
- **Promotion** — explicit entity/connection curation with conflict resolution strategies

The GUI is built over the REST API, so anything a human can do in the browser can also be automated via API calls or MCP tools.

## Installation and Setup

**Requirements**: Python ≥ 3.13, Java ≥ 11 (for diagram verification and rendering), Node ≥ 18 (for GUI development), `uv`.

### 1. Install Dependencies

```bash
# Python environment
uv sync                        # core dependencies
uv sync --dev                  # + pytest, ruff, zuban
uv sync --extra gui            # + GUI server dependencies
uv sync --dev --extra gui      # full local developer setup

# Download and verify plantuml.jar from Maven Central
get-plantuml                   # → tools/plantuml.jar (gitignored)

# Pull the supported local diagram runtime
get-diagram-runtime            # PlantUML + Graphviz runtime for this repo

# Verify local Graphviz/PlantUML compatibility for rendering
check-diagram-runtime          # requires Graphviz >= 2.49.0
```

### 2. Initialise Workspace

```bash
# Create or validate arch-workspace.yaml (see Two-Tiered Architecture section above)
# Then run:
arch-init                      # reads arch-workspace.yaml, writes .arch/init-state.yaml
```

### 3. Start the Backend

```bash
# Run the unified backend (serves API at :8000 and MCP at :8000/mcp)
arch-backend --daemon

# Inspect / stop / restart
arch-backend --status
arch-backend --stop
arch-backend --restart --daemon
```

The backend also serves the built Vue app at `http://localhost:8000/`.

`arch-backend --daemon` starts the backend in a new session, redirects stdin from
`/dev/null`, and writes output to `backend.log_path`. This avoids shell
job-control stops that can happen with raw `arch-backend &` if a background
process reads from the terminal. `arch-backend &` is still supported and also
detaches stdin when a background TTY job is detected, but `--daemon` is the
preferred operational form.

To inspect the current MCP tool surface with the latest MCP Inspector:

```bash
# Inspect the read-only MCP server via stdio transport
tmp_cfg="$(mktemp)"
cat >"$tmp_cfg" <<JSON
{
  "mcpServers": {
    "default-server": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "$(pwd)", "run", "arch-mcp-stdio-read"]
    }
  }
}
JSON
npx -y @modelcontextprotocol/inspector@latest --config "$tmp_cfg" --server default-server

# Inspect the write-capable MCP server via stdio transport
tmp_cfg="$(mktemp)"
cat >"$tmp_cfg" <<JSON
{
  "mcpServers": {
    "default-server": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "$(pwd)", "run", "arch-mcp-stdio-write"]
    }
  }
}
JSON
npx -y @modelcontextprotocol/inspector@latest --config "$tmp_cfg" --server default-server
```

Connection type: `stdio`

This launches the Inspector with an explicit `stdio` server configuration, so the
UI does not depend on any previously persisted localStorage state such as an old
Streamable HTTP URL. The local MCP bridge entrypoints then connect to the unified backend.

If the frontend appears stuck on "Loading...", diagnose the actual transport
path before assuming an application lock:

```bash
arch-backend --status
curl --max-time 5 http://127.0.0.1:8000/api/stats
curl --max-time 5 http://127.0.0.1:5173/api/stats
tail -n 100 .arch/backend.log  # or the configured backend.log_path
```

If status reports `process state: T`, the backend process is stopped while still
holding the port. Stop and restart it with:

```bash
arch-backend --stop
arch-backend --daemon
```

### 4. Configure MCP Access for AI Agents

Edit `.mcp.json` or your IDE's MCP config (see **MCP Server** section above).

If using Claude Code, the default config already points to the auto-starting backend.

### 5. Frontend Development (Optional)

For active frontend development with Vite hot-reload:

```bash
cd tools/gui
npm install
npm run dev
# → open http://localhost:5173
# API calls are proxied to arch-backend on :8000
```

### 6. Quality Checks

Run the Python lint and type checks from the workspace root:

```bash
uv run ruff check src tests gen_id.py
uv run zuban check
```

`ruff` is configured for import sorting plus core error detection and ignores the
model/content repositories and the Vue frontend tree. `zuban` runs in
Mypy-compatible mode against `src/`, `tests/`, and `gen_id.py`.

Run the frontend lint and type checks from `tools/gui`:

```bash
cd tools/gui
npm run lint
npm run typecheck
```

The frontend uses ESLint 9 with the Vue and TypeScript flat-config presets plus
type-aware rules, and `vue-tsc`/`tsc` for application and Vite config
type-checking.

## Running in Docker

The GUI packages the Vue SPA and FastAPI server into a single container:

```bash
# Start with the bundled self-describing model
docker compose up --build
# → http://localhost:8000

# Or point at a different repository
ARCH_REPO_ROOT=/path/to/your/architecture-repository docker compose up --build
```

The container includes system dependencies for PlantUML diagram rendering (Java, Graphviz, fonts).

If you want host-started MCP clients to attach to the Dockerized backend:

1. Ensure the container is published on `localhost:8000` (the compose file does this by default)
2. In your MCP config, set `ARCH_MCP_BACKEND_URL=http://127.0.0.1:8000`
3. The MCP launcher will skip starting its own backend and attach to the published port instead

## Modes and Permissions

**Normal mode (default)**
- Humans and AI agents can read/write the engagement repository
- The enterprise repository is read-only (accessed via promotion)

**Admin mode** (`arch-backend --admin-mode`)
- Enables direct enterprise repository writes via the GUI and REST API
- Intended for curating the shared baseline; normally not needed during engagement work
- The browser GUI shows a banner when admin mode is active

**Read-only mode** (`arch-backend --read-only`)
- All write operations are blocked globally (useful for review/audit deployments)
- The browser GUI shows a banner and disables write buttons
- The MCP write server remains available but rejects all mutations

## Saving and Sharing Work

Architecture changes accumulate as file edits. They are persisted to git in two explicit steps: *saving* (committing locally) and, for enterprise changes, *submitting for review* (pushing a branch for team review).

### Engagement Repository

Changes in the engagement repo are saved via:

- **GUI**: "Save Changes" button → commits all uncommitted changes with a message; optionally pushes to the remote immediately.
- **MCP tool**: `artifact_save_changes(message="…", target="engagement")`.
- **REST API**: `POST /api/sync/engagement/save` `{"message": "…", "push": true}`.

If `push=true` (default), the commit is pushed to the remote branch immediately after committing.

### Enterprise Repository — Branch-Based Review Workflow

Enterprise changes (e.g. after promoting engagement artifacts) follow a three-step lifecycle designed to work with any git hosting platform (GitHub, GitLab, Gitea, etc.) without requiring API integration:

```
 Make changes          Save changes         Submit for review
 (promote artifacts)   (commit to           (push branch →
                        working branch)      create PR manually)
        │                    │                    │
        ▼                    ▼                    ▼
  [accumulating] ──────► [accumulating] ──────► [pending]
                                                   │
                              ◄────────────────────┘
                         [synced]   ← auto-detected when branch
                                      is merged into main
```

**Accumulating** — when the first enterprise write (promotion) happens, the system automatically creates an isolated working branch (e.g. `arch/work-20260425-143012`). Subsequent promotions accumulate on the same branch. The enterprise read view always reflects the branch content, so all queries are consistent with your in-progress work.

**Saving** — commits the working branch without pushing. Use this to checkpoint progress:
- **GUI**: "Save Enterprise Changes" → commit dialog.
- **MCP**: `artifact_save_changes(message="…", target="enterprise")`.
- **REST**: `POST /api/sync/enterprise/save`.

**Submitting for review** — pushes the branch and marks it as pending. No API integration needed; the returned branch name is used to open a PR manually in your hosting platform:
- **GUI**: "Submit for Review" → shows branch name and guidance.
- **MCP**: `artifact_submit_for_review()`.
- **REST**: `POST /api/sync/enterprise/submit`.

**Auto-merge detection** — the background sync polls `origin/main` every cycle. When the working branch content is detected in `origin/main` (via content diff, which handles squash/rebase merges), the system automatically checks out `main`, pulls, and transitions back to the *synced* state. The GUI notifies with "Your changes have been merged".

**Discarding changes** — to abandon a working branch without merging:
- **GUI**: "Discard Changes" (requires confirmation).
- **MCP**: `artifact_withdraw_changes(confirm=True)`.
- **REST**: `POST /api/sync/enterprise/withdraw` `{"confirm": true}`.

The sync state for the enterprise repo is persisted in `.arch/enterprise-sync.json` and survives backend restarts.

### SSH Key Passphrases

If the git remote requires an SSH key with a passphrase, supply it via environment variable or startup argument. The passphrase is never stored on disk; it is passed to git subprocesses via a temporary `SSH_ASKPASS` helper at runtime:

```bash
# Via environment variable (inherited by auto-started backends)
export ARCH_GIT_SSH_PASSWORD="my passphrase"
arch-backend --daemon

# Via explicit argument (overrides env var)
arch-backend --git-ssh-password "my passphrase" --daemon
```

## Continuous Git Sync

When a repository is configured as a git repo (not just a local path), the backend runs a background sync loop every 60 seconds (configurable). Behavior differs by repository role:

**Engagement repository**
- Fetches from origin on every cycle.
- If behind and the workspace is clean: `git pull --ff-only`.
- If behind and there are local commits: `git pull --rebase` (rebases local work on top of team changes).
- If a rebase conflict is detected: aborts cleanly, emits a conflict event, and waits for manual resolution.

**Enterprise repository**
- *Synced*: fetches and fast-forward pulls as normal (main is always clean).
- *Accumulating*: fetches only; emits a divergence event if `origin/main` has moved ahead.
- *Pending*: fetches and runs a content diff to detect whether the working branch has been merged into `origin/main`. When detected, transitions automatically back to *synced* (checks out main, pulls, deletes local branch).

In all cases:
- Writes are temporarily blocked during pull/checkout operations to prevent corruption.
- If a sync operation fails, the write block is automatically lifted after 60 seconds.
- After any pull or merge transition, the artifact index is refreshed and the GUI is notified via the SSE event bus.

## Configuration Reference

### Backend Settings (`config/settings.yaml`)

```yaml
backend:
  port: 8000                  # TCP port for arch-backend (default 8000)
  log_path: .arch/backend.log # Log file path; relative paths are workspace-relative
  min_log_level: INFO         # DEBUG | INFO | WARNING | ERROR | CRITICAL

diagrams:
  archimate_type_markers: icons   # icons | labels
  sprite_scale: 1.5
  render_dpi: 150
  plantuml_limit_size: 16384
```

These settings apply globally and are read by `arch-backend` at startup. They are **not** configurable via `arch-workspace.yaml`.

### Per-Repository Schemata (`.arch-repo/schemata/`)

Each repository (engagement and enterprise) may contain a `.arch-repo/schemata/` directory with JSON Schema files that extend or constrain the global ontology for that repo:

```
.arch-repo/schemata/
  attributes.{entity-type}.schema.json   # additional required/optional fields per entity type
  frontmatter.entity.schema.json          # constraints on entity frontmatter fields
  frontmatter.outgoing.schema.json        # constraints on connection outgoing frontmatter
  frontmatter.diagram.schema.json         # constraints on diagram frontmatter
```

**Attribute profiles** (`attributes.{type}.schema.json`) define JSON Schema constraints on the `properties:` section of entities of that type. The `required` list enforces mandatory fields; `properties` declares their types and allowed values.

**Frontmatter schemas** (`frontmatter.{entity|outgoing|diagram}.schema.json`) constrain the YAML frontmatter fields common to all entities, connections, or diagrams in the repo.

**Promotion superset rule**: an engagement repo's schemata must be *supersets* of the enterprise repo's schemata. That is, every property and required field defined in an enterprise schema must also appear in the corresponding engagement schema. Promotion is blocked — with a per-violation error message — if this invariant is not met. This ensures promoted entities always satisfy the enterprise constraints after transfer.

### Entity Types (`config/entity_ontology.yaml`)

Each entry defines one ArchiMate NEXT entity type:

```yaml
requirement:
  prefix: REQ           # short ID prefix, e.g. REQ@epoch.random.slug
  domain: motivation    # filesystem domain directory under model/
  subdir: requirements  # subdirectory within the domain
  archimate_element_type: Requirement   # CamelCase element type for diagram blocks
  element_classes: [motivation-element] # ArchiMate classification classes
  has_sprite: true      # whether a diagram sprite exists for this type
  create_when: "…"      # guidance on when to use this type
  never_create_when: "…"
```

Internal/meta types that should not appear in domain groupings or catalogs carry `internal: true`.

### Connection Types (`config/connection_ontology.yaml`)

Each entry defines one connection type, grouped by diagram language (`archimate`, `er`, `sequence`, `activity`, `usecase`):

```yaml
archimate-realization:
  archimate_relationship_type: Realization  # ArchiMate stereotype name
  puml_arrow: "..|>"    # PlantUML arrow syntax
  symmetric: false      # true for bidirectional relationships (e.g. association)
```

Permitted relationships between entity types are defined in the `permitted_relationships:` section using `[source, target, [connection-short-names]]` rules with `@class` and `@all` wildcards.

### Document Types (`.arch-repo/documents/*.json`)

Each file defines one document type. The filename (without `.json`) is the `doc-type` frontmatter value used in document files.

```json
{
  "abbreviation": "STD",
  "name": "Standard",
  "subdirectory": "standards",
  "frontmatter_schema": {
    "type": "object",
    "required": ["title", "status"],
    "properties": {
      "title":      { "type": "string" },
      "status":     { "type": "string", "enum": ["draft", "accepted", "rejected", "superseded"] },
      "applies_to": { "type": "array", "items": { "type": "string" } },
      "date":       { "type": "string" }
    }
  },
  "required_sections": ["Scope", "Motivation", "Summary", "Specification"],
  "required_entity_type_connections": ["requirement", "@internal-behavior-element"],
  "suggested_entity_type_connections": ["principle", "goal", "@all"]
}
```

**`frontmatter_schema`** — JSON Schema for the document's YAML frontmatter. Fields outside the built-in set (`title`, `status`, `keywords`) are rendered as type-specific form fields in the GUI and validated on write.

**`required_sections`** — Section headings (matching `## Heading`) that must be present in the document body. Missing sections are reported as E154 verification errors.

**`required_entity_type_connections`** — Entity type terms of which at least one matching entity must be linked (via a Markdown link in the body) for verification to pass. Terms may be a concrete entity type (`requirement`), `@all`, or any element class from `config/entity_ontology.yaml` prefixed with `@` (for example `@internal-behavior-element`, using the same syntax as `config/connection_ontology.yaml`). Missing links are reported as E155 errors and block writes.

**`suggested_entity_type_connections`** — Entity type terms whose linking is recommended but not enforced. The GUI displays these as blue "Suggested entity links" notices to prompt the author.

## Further Reading

- **[ArchiMate Forum](https://www.opengroup.org/archimate-forum)** — the modelling language
- **`engagements/ENG-ARCH-REPO/`** — a self-describing model of this system's own architecture
- **`src/common/ontology_loader.py`** — entity types, connection types, and domain definitions
- **`.arch-repo/documents/`** — structured documentation templates (ADR, Standard, Specification)
