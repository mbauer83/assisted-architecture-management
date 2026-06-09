# Scalable Architecture Management for Humans and AI

A system for managing software architecture in a structured, git-versioned, and discoverable way — designed to work equally well for human practitioners and AI agents.

## Purpose and Goals

Architecture knowledge typically lives in slide decks, Confluence pages, or siloed modelling tools. This project treats architecture as **code**: structured, version-controlled, queryable, and verifiable. The built-in canonical model ontology is currently [ArchiMate NEXT](https://www.opengroup.org/archimate-forum), while the extension model also supports additional ontologies and diagram-type families such as UML activity views and C4 zoomed architecture views.

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

An `arch-workspace.yaml` at the workspace root declares the two repositories. The simplest form keeps a single explicit engagement:

```yaml
engagement:
  local: engagements/ENG-ARCH-REPO/architecture-repository
  # or git: { url: "https://...", branch: main, path: .arch/repos/engagement }

enterprise:
  local: enterprise-repository
  # or git: { url: "https://...", branch: main, path: .arch/repos/enterprise }
```

For workspaces that need to hop between multiple engagement repositories, use an engagement catalog with an active selector:

```yaml
engagements:
  active: ENG-ARCH-REPO
  available:
    ENG-ARCH-REPO:
      local: engagements/ENG-ARCH-REPO/architecture-repository
    CLIENT-B:
      git:
        url: "git@github.com:your-org/client-b-architecture.git"
        branch: main
        path: ../client-b-architecture

enterprise:
  local: enterprise-repository
```

Run `arch-init` to validate paths (or clone git repos) and write `.arch/init-state.yaml` with resolved absolute paths. All tooling reads this state file on startup.

Backend settings (port, log path, log level) are configured in `config/settings.yaml`, not in `arch-workspace.yaml`. See **Configuration Reference** below.

## Repository Layout

```
src/
  domain/          # Pure domain protocols, value types, module catalog, focused catalogs
  application/     # Use cases, runtime catalogs, verification engine, derivation strategies
  config/          # Workspace and settings configuration readers
  infrastructure/  # FastAPI REST, MCP servers, CLI, rendering, artifact index, write I/O
  ontologies/      # Ontology plugins (ArchiMate NEXT; extend for SysML, TOGAF, etc.)
  diagram_types/   # Diagram-type adapter plugins (C4, UML activity, matrix, etc.)
tools/
  gui/             # Vue 3 + TypeScript SPA (hexagonal ports-and-adapters)
engagements/
  ENG-ARCH-REPO/   # Self-describing architecture model + docs
enterprise-repository/
                   # Enterprise baseline (initially empty)
arch-workspace.yaml
```

### Content Organisation (Grouping)

Growing repositories are navigable via **three independent grouping axes**, one per artifact family:

| Axis | Artifact family | Directory layout |
|---|---|---|
| **Model-project** | Entities + connections | `projects/<slug>/model/<domain>/<type>/…` |
| **Diagram-collection** | Diagrams | `diagram-catalog/diagrams/<slug>/…` (+ `rendered/<slug>/`) |
| **Document-collection** | Documents | `docs/<doc-type-subdir>/<slug>/…` |

Axes are **mutually independent** — a diagram collection is never tied to a model-project. Grouping is a **soft partition**: it never constrains search, linking, or verification; it only controls where files live.

**Migrate existing content** (idempotent, per-repo):
```bash
uv run python -m src.infrastructure.workspace.migrate_to_groups
```

**Group lifecycle** — via `artifact_group` MCP tool or REST `POST/PUT/DELETE /api/group*`:
- `create` — register a new group (target = slug)
- `rename` — change display name or slug (safe subtree `git mv`)
- `archive` / `unarchive` — hide/restore from default pickers
- `delete` (diagram/document collections) — remove folder + contents, typed confirm required
- `delete` (model-project, `dry_run=True` first) — two-stage cascade: preflight impact report, then apply

**Create/edit with a group** — `artifact_create_entity`, `artifact_create_diagram`, `artifact_create_document` and their `edit_*` counterparts all accept an optional `group` param:
- create-time: places the artifact in that group's directory
- edit-time: re-homes (safe `git mv`) the artifact to a new group

**CLI is out of scope** for group authoring; use MCP tools or the REST/GUI surface.

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
- **Extensible view families**: diagram types may be ontology-bound or diagram-owned, so teams can add notation-specific views without changing the canonical model store
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

### System Requirements

| Dependency | Minimum | Purpose |
|---|---|---|
| Python | 3.13 | All server and CLI components |
| `uv` | any recent | Python environment and script runner |
| Java | 11 | PlantUML diagram rendering and verification |
| Graphviz | 2.49.0 | Diagram layout engine |
| Node.js | 18 | Frontend development only (not needed to run) |
| npm | 9 | Frontend development only |
| SQLCipher (system lib) | 4 | Assurance store (optional) |

### Per-Environment Prerequisites

#### macOS

```bash
# Core
brew install python@3.13 openjdk graphviz
curl -LsSf https://astral.sh/uv/install.sh | sh

# Frontend development (optional)
brew install node

# Assurance store (optional)
brew install sqlcipher
```

Java from Homebrew needs to be symlinked for the system `java` command:

```bash
sudo ln -sfn $(brew --prefix openjdk)/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk.jdk
```

Credentials for the assurance store are kept in **macOS Keychain** automatically — no extra configuration needed.

#### Linux (Debian / Ubuntu)

```bash
# Core
sudo apt-get update
sudo apt-get install -y python3.13 python3.13-dev default-jre graphviz curl

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Frontend development (optional) — use nvm or NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Assurance store (optional)
sudo apt-get install -y libsqlcipher-dev
```

For credential storage the assurance store uses **SecretService (D-Bus / gnome-keyring)** when a desktop session is running. On headless servers (CI, SSH-only) set a master password instead — see [Assurance: Credential Storage](#assurance-credential-storage) below.

#### WSL2 on Windows

Run all commands in the WSL2 Debian/Ubuntu shell. Follow the Debian/Ubuntu steps above.

SQLCipher requires the native system library inside WSL2, even though the Windows host has no equivalent:

```bash
sudo apt-get install -y libsqlcipher-dev
```

Credentials are kept in **Windows DPAPI** via PowerShell interop (`Export-Clixml`/`Import-Clixml`). This encrypts each key with the Windows user's login credentials — it is machine-and-user-scoped and does not require any extra setup beyond having PowerShell accessible from WSL2 (the default in any WSL2 installation on Windows 11).

#### Docker

No local prerequisites beyond Docker. The container image bundles Java, Graphviz, and all Python dependencies. See [Running in Docker](#running-in-docker).

The assurance store is **not** enabled in the default Docker image because it requires host-level credential storage. To use it in Docker, mount credentials or supply `ARCH_ASSURANCE_MASTER_PASSWORD` as an environment variable (see [Assurance: Credential Storage](#assurance-credential-storage)).

### 1. Install Python Dependencies

```bash
# Core runtime
uv sync                           # core dependencies
uv sync --group dev               # + pytest, ruff, zuban  (alias: --dev)
uv sync --group gui               # + FastAPI / uvicorn for the GUI server
uv sync --group dev --group gui   # full local developer setup

# Assurance store (optional — needs libsqlcipher-dev on the host)
uv sync --all-groups              # installs all dependency groups

# Cloud archive backends (optional — pick what you need)
uv sync --extra s3-archive        # + boto3 for S3 Object Lock archive
uv sync --extra azure-archive     # + azure-storage-blob + azure-identity for Azure archive
uv sync --extra cloud-archive     # both S3 and Azure
```

```bash
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

# If a configured git repo already exists locally but is still empty / uninitialized
arch-init --initialize-engagement-repo-if-empty
arch-init --initialize-enterprise-repo-if-empty

# Switch to another configured engagement and restart the backend if it is running
arch-switch-engagement CLIENT-B

# Register a new git-backed engagement; by default place it beside the current engagement
arch-switch-engagement CLIENT-C --url git@github.com:your-org/client-c-architecture.git

# Create a brand-new local engagement repo with default schemata and document types
arch-switch-engagement CLIENT-D --local ../client-d-architecture --create

# Create a brand-new git-backed engagement repo locally and attach origin
arch-switch-engagement CLIENT-E --url git@github.com:your-org/client-e-architecture.git --create
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

### 6. Assurance Store (Optional)

The assurance store is an encrypted evidence store for safety analysis (STPA, CAST), governance (GRC), and supply-chain security. The live store is fully mutable; an append-only audit log and optional WORM layer are separate concerns — see [Using Assurance Features](#using-assurance-features) for details. The default backend requires `libsqlcipher-dev` on the host — see [Per-Environment Prerequisites](#per-environment-prerequisites) above.

After installing the system library, initialise and activate the store once:

```bash
# Create the encrypted database and store the key in the OS credential backend
arch-assurance init

# Verify the key round-trips and activate auto-unlock on backend start
arch-assurance unlock

# Save the recovery key offline (print to stdout — store this in a password manager)
arch-assurance export-key
```

On subsequent backend starts the store is unlocked automatically from the OS credential backend (macOS Keychain, Windows DPAPI, or SecretService). No manual unlock is needed after the first `arch-assurance unlock`.

#### Assurance: Credential Storage {#assurance-credential-storage}

The assurance store uses platform-appropriate credential storage — selected automatically in this order:

| Environment | Backend | Notes |
|---|---|---|
| macOS | macOS Keychain | Always available; no setup needed |
| WSL2 on Windows | Windows DPAPI | Uses `powershell.exe`; user-and-machine-scoped |
| Linux desktop | SecretService (D-Bus) | Requires gnome-keyring or kwallet running |
| Headless Linux / CI | Fernet-encrypted vault | Set `ARCH_ASSURANCE_MASTER_PASSWORD` env var |

For headless Linux (SSH-only servers, CI pipelines):

```bash
export ARCH_ASSURANCE_MASTER_PASSWORD="your-long-random-passphrase"
arch-assurance init
arch-assurance unlock
```

Add `ARCH_ASSURANCE_MASTER_PASSWORD` to `~/.bashrc`, a systemd service unit, or your CI secrets store so it is available on every start.

#### Assurance MCP Servers (Optional)

To expose assurance tools to AI agents, add the assurance MCP servers to `.mcp.json`:

```json
{
  "mcpServers": {
    "arch-repo-read": { "command": "uv", "args": ["run", "arch-mcp-stdio-read"] },
    "arch-repo-write": { "command": "uv", "args": ["run", "arch-mcp-stdio-write"] },
    "arch-assurance-read": {
      "command": "uv",
      "args": ["run", "arch-mcp-stdio-assurance-read"]
    },
    "arch-assurance-write": {
      "command": "uv",
      "args": ["run", "arch-mcp-stdio-assurance-write"]
    }
  }
}
```

The assurance MCP servers require the store to be unlocked. Auto-unlock applies as long as `arch-assurance unlock` has been run at least once.

### 7. Quality Checks

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

### Git Authentication

Both SSH and HTTPS remotes are supported. Credentials are never stored on disk; they are kept in process memory and injected into git subprocesses at runtime via a temporary askpass helper.

**Interactive prompting (recommended)**: `arch-backend` and `arch-init` detect which configured remotes need authentication, probe silently, and prompt on the terminal if credentials are required:

```
SSH key passphrase:         (invisible input — only asked when probe fails without credentials)
Git username:               (HTTPS only)
Git password/token:         (invisible input — HTTPS only)
```

For `arch-backend --daemon`, prompting happens in the foreground parent process before the daemon forks; the daemon subprocess inherits the credentials silently.

**CI / non-interactive override**: set environment variables to skip prompting entirely:

```bash
export ARCH_GIT_SSH_PASSWORD="my passphrase"   # SSH key passphrase
export ARCH_GIT_HTTPS_USERNAME="my-user"        # HTTPS username
export ARCH_GIT_HTTPS_PASSWORD="my-token"       # HTTPS password or token
arch-backend --daemon
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

repo_init:
  default_branch: main
  commit_author_name: arch-switch-engagement
  commit_author_email: arch-switch-engagement@local.invalid
  engagement:
    # optional per-repo-kind overrides used by arch-switch-engagement --create
    default_branch: main
    commit_author_name: Architecture Bot
    commit_author_email: architecture-bot@example.com

storage:
  assurance:
    store_backend: sqlcipher        # sqlcipher | private-git | pocketbase
    signals_backend: sqlcipher-colocated  # sqlcipher-colocated | sqlite | encrypted
    archive_backend: standard       # standard | worm | s3-worm | azure-blob-worm
    max_classification: TLP:RED     # TLP:WHITE | TLP:GREEN | TLP:AMBER | TLP:RED
```

These settings apply globally and are read by `arch-backend` at startup. They are **not** configurable via `arch-workspace.yaml`.

`repo_init` controls git defaults used when scaffolding a new engagement repository via `arch-switch-engagement --create`. `default_branch`, `commit_author_name`, and `commit_author_email` may be set globally or overridden for `engagement`.

`storage.assurance` controls the assurance module backends. These keys are written automatically by `arch-assurance init` and `arch-assurance use-backend`, so manual editing is rarely needed. The `max_classification` ceiling controls the highest TLP level the assurance MCP servers will expose to AI agents; entries above the ceiling are withheld from tool responses. See [Storage Architecture](#storage-architecture) for a description of each backend option.

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

### Multi-Engagement Workspace Switching

`arch-workspace.yaml` may define either:

- `engagement:` — a single active engagement repo, or
- `engagements.active` + `engagements.available` — a named catalog of engagement repos

`arch-switch-engagement <name>` updates the active entry, rewrites the derived workspace state in `.arch/init-state.yaml`, and restarts a running backend so the GUI, REST API, and MCP servers all rebuild against the new engagement root.

When registering a new git-backed engagement with `--url`, the default clone destination is a sibling directory of the current workspace (for example `../client-b-architecture`). Passing `--create` scaffolds a new engagement repository in place instead of cloning. New repos are created with:

- the standard directory structure (`model/`, `docs/`, `diagram-catalog/`, `.arch-repo/`)
- a git repository initialized on the configured branch (`main` by default)
- an initial scaffold commit
- default frontmatter schemata
- default attribute-profile schemata for key motivation and strategy entities
- default document-type specifications for ADRs, standards, and specifications

### Entity Types and Connection Types

Entity types, connection types, and permitted relationship rules are defined in *ontology modules* under `src/ontologies/`. The shipped module is `src/ontologies/archimate_next/` (ArchiMate NEXT Snapshot 1). Each module consists of:

- `entities.yaml` — one entry per entity type with `prefix`, `domain`, `subdir`, `element_classes`, `create_when`, `never_create_when`
- `connections.yaml` — one entry per connection type, plus `permitted_relationships` rules using `[source, target, [conn-short-names]]` with `@class` / `@all` wildcards
- `__init__.py` — exposes a `module` object satisfying the `OntologyModule` protocol

New ontologies (SysML, TOGAF, domain-specific languages) can be added without touching the core. See `src/ontologies/README.md` for the full extension contract and a SysML skeleton example.

### Diagram Types

Diagram views are declared as *diagram type modules* under `src/diagram_types/`. Each kind has a `config.yaml` declaring its name, accepted entity type domains, PlantUML includes, grouping, and layout hints. The `GenericPumlRenderer` handles rendering for all standard ArchiMate-style views. Custom renderers are only needed for non-PlantUML diagram formats (e.g. the matrix kind).

See `src/diagram_types/README.md` for the full `config.yaml` schema and extension guide.

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

## Using Assurance Features

The assurance module stores safety, security, and compliance evidence separately from the architecture model. This keeps sensitive findings (hazard analyses, incident data, risk registers) out of the main model git history while keeping them linked to the architecture entities they describe.

### Store and Archive: two independent concerns

Every assurance deployment has exactly **two active components** that run in parallel: a **store** and an **archive**. They serve different purposes and are configured with separate keys (`store_backend` and `archive_backend`). You do not choose between them — you choose *how* to deploy each one.

**The store** (`ConfidentialAssuranceStore`) is your working dataset. It is a fully mutable encrypted graph of nodes and edges: you create hazards, update their status, link them to controls, delete draft entries. This is where ongoing STPA, STPA-sec, CAST, and GRC work lives while analysis is in progress. The store has no immutability guarantees — that is intentional. Safety analysis evolves; forcing immutability on a live model would make the tool unusable for iterative work.

**The archive** (`AssuranceArchive`) is a parallel evidence trail. It is append-only: every significant operation is automatically recorded as a hash-chained entry. No entry is ever modified or deleted. Its purpose is regulatory and forensic — to prove after the fact what was known, when, and in what state. The EU AI Act (Art. 12 and related provisions) requires exactly this kind of tamper-evident log for high-risk AI systems. The archive runs automatically alongside the store; you do not interact with it directly during normal analysis work.

The key implication: **confidentiality is a store concern; immutability is an archive concern**. The store is encrypted but mutable. The archive is append-only but may or may not be encrypted at the storage layer depending on the backend. WORM (hardware/cloud-enforced immutability) is an opt-in extension to the archive for deployments where the hash-chain alone is not a sufficient guarantee — typically regulated incident records, finished accident reports, or records subject to legal hold.

| Component | Config key | Default | Role |
|---|---|---|---|
| Store | `store_backend` | `sqlcipher` | Mutable encrypted workspace for live analysis |
| Archive | `archive_backend` | `standard` | Append-only tamper-evident evidence trail |

The two backends are configured independently. There is one constraint: `archive_backend: worm` (local SQLCipher WORM) requires `store_backend: sqlcipher` because it shares the same database file. The cloud archive backends (`s3-worm`, `azure-blob-worm`) have no such constraint — they write to their own storage and work with any store backend.

### Archive backends

The archive backend controls where audit entries are written and what immutability guarantees the storage layer enforces:

| `archive_backend` | Storage | Immutability mechanism | Required dependency |
|---|---|---|---|
| `standard` (default) | Co-located with the store | SHA-256 hash chain (software) | none |
| `worm` | SQLCipher (same DB as store) | Hash chain + per-subject AES-256-GCM DEK + legal holds | `store_backend: sqlcipher` |
| `s3-worm` | Amazon S3 | S3 Object Lock (GOVERNANCE or COMPLIANCE mode) | `boto3`; S3 bucket with Object Lock enabled |
| `azure-blob-worm` | Azure Blob Storage | Container-level immutability policy | `azure-storage-blob`, `azure-identity` |

`standard` is sufficient for most teams — the hash chain detects any tampering, and the store encryption protects confidentiality. Upgrade to a WORM backend when you need storage-layer enforcement: cloud-provider guarantees that even a compromised account cannot delete or overwrite records, legal holds that survive key rotation, per-subject crypto-shredding for GDPR right-to-erasure, or RFC 3161 timestamp tokens for non-repudiation.

**`worm`** (on-premises / local, requires SQLCipher store):

```bash
arch-assurance use-backend sqlcipher --archive-backend worm
```

**`s3-worm`** (AWS — independent of store backend):

```bash
uv sync --extra s3-archive
export ARCH_S3_BUCKET="my-worm-bucket"          # must have Object Lock enabled at bucket creation
export ARCH_S3_REGION="eu-west-1"               # optional
export ARCH_S3_OBJECT_LOCK_MODE="GOVERNANCE"    # or COMPLIANCE for stricter legal enforcement
export ARCH_S3_RETENTION_DAYS="730"             # default: 365
arch-assurance use-backend sqlcipher --archive-backend s3-worm
```

AWS credentials follow the standard boto3 chain (env vars, `~/.aws/credentials`, EC2 instance profile, ECS task role, etc.). No credential configuration is needed in the assurance store when using an IAM role.

**`azure-blob-worm`** (Azure — independent of store backend):

```bash
uv sync --extra azure-archive
export ARCH_AZURE_STORAGE_ACCOUNT="myaccount"
export ARCH_AZURE_CONTAINER="arch-assurance"    # must have immutability policy applied
export ARCH_AZURE_STATE_CONTAINER="arch-assurance-state"   # optional; default: {container}-state
# Omit ARCH_AZURE_STORAGE_KEY to use DefaultAzureCredential (managed identity, az login, etc.)
arch-assurance use-backend sqlcipher --archive-backend azure-blob-worm
```

The `azure-blob-worm` adapter uses **two containers**: the archive container (WORM, covered by the immutability policy) and a state container (mutable; holds chain head pointer, holds index, and DEKs). Apply the time-based immutability policy only to the archive container and lock it for compliance-grade enforcement.

### Store on cloud infrastructure

The mutable store is a local file (`sqlcipher`) or a service (`pocketbase`). For cloud deployments:

- **AWS**: run in a container or EC2 instance with an EBS volume encrypted at rest via AWS KMS. The SQLCipher file sits on that volume — application-layer AES-256 encryption stacks on top.
- **Azure**: run in a container with Azure Disk Encryption or Managed Disk with SSE. PocketBase can run as an Azure Container App.

No new store adapter is needed for AWS or Azure. The cloud archive backends (`s3-worm`, `azure-blob-worm`) handle the immutability requirement; the store backend choice remains independent.

### Prerequisites

The assurance store must be initialised and unlocked before use. If you have not done this yet, follow the [Assurance Store (Optional)](#6-assurance-store-optional) setup steps. Verify the current state at any time:

```bash
arch-assurance status
```

A healthy, active store reports:

```
archive_backend: standard
db_exists: true
db_path: /workspace/.arch-assurance/store.db
key_in_keychain: true
max_classification: TLP:RED
setup_confirmed: true
signals_backend: sqlcipher-colocated
status: unlocked
store_backend: sqlcipher
unlocked: true
```

### CLI Reference

| Command | Description |
|---|---|
| `arch-assurance init` | Create the encrypted store; generate and save the encryption key |
| `arch-assurance init --force` | Re-initialise, replacing an existing store |
| `arch-assurance init --backend <B>` | Choose store backend: `sqlcipher` (default), `private-git`, `pocketbase` |
| `arch-assurance init --archive-backend <A>` | Choose archive backend: `standard` (default), `worm`, `s3-worm`, `azure-blob-worm` |
| `arch-assurance unlock` | Verify the key, report store stats, and activate auto-unlock |
| `arch-assurance status` | Show all backends, DB path, lock state, and key presence |
| `arch-assurance export-key` | Print the recovery key (store this offline in a password manager) |
| `arch-assurance rotate-key` | Generate a new encryption key and re-encrypt the database |
| `arch-assurance backup` | Copy the encrypted DB to a timestamped backup file |
| `arch-assurance export -o out.json` | Export all assurance data as plaintext JSON |
| `arch-assurance verify` | Backend-aware chain integrity check (all archive backends) |
| `arch-assurance verify-chain` | Verify the audit log hash chain (SQLCipher only) |
| `arch-assurance use-backend <B>` | Switch store backend in `config/settings.yaml` |
| `arch-assurance use-backend <B> --archive-backend <A>` | Switch both store and archive backends |
| `arch-assurance import-sbom` | Ingest a CycloneDX or SPDX bill-of-materials file |
| `arch-assurance export-aibom` | Emit a CycloneDX 1.6 AI-BOM from component data |
| `arch-assurance scan-ai-candidates` | Heuristic scan of architecture entities for AI-BOM relevance |

### Encryption Key Management

The encryption key is stored in the OS credential backend (see [Assurance: Credential Storage](#assurance-credential-storage)) and never written to disk in plaintext. The recovery key is a separate, randomly generated token that can decrypt the database if the OS credential entry is lost (e.g. after migrating to a new machine):

```bash
# Print the recovery key — run once after init and store it offline
arch-assurance export-key
```

To restore from a recovery key on a new machine, re-initialise the store against the existing database file and supply the recovery key when prompted (or contact the relevant `arch-assurance rotate-key` workflow for your team).

To rotate the encryption key (for example, after an operator leaves a team):

```bash
arch-assurance rotate-key
arch-assurance export-key   # save the new recovery key
```

### Backup and Recovery

```bash
# Create a timestamped encrypted backup (the backup is still encrypted)
arch-assurance backup

# Specify an explicit backup path
arch-assurance backup --backup-path /safe/location/store-backup.db

# Export plaintext JSON for migration or archival (handle with care)
arch-assurance export -o assurance-export.json
```

Backups are encrypted with the same key as the live database. Keep at least one backup and the recovery key in separate, durable locations.

### Storage Architecture

Three adapter dimensions, each independently configurable:

```
  ┌──────────────────────────────────────────────────────────────┐
  │              Assurance store  (store_backend)                │
  │       sqlcipher │ private-git │ pocketbase                   │  ← mutable encrypted workspace
  └──────────────────────────────────────────────────────────────┘
                      ↑ key lookup
  ┌──────────────────────────────────────────────────────────────┐
  │              Encryption keys  (credential backend)           │
  │       Keychain │ DPAPI │ SecretService │ Fernet vault        │  ← auto-selected per OS
  └──────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────┐
  │              Archive  (archive_backend)                      │
  │       standard │ worm │ s3-worm │ azure-blob-worm            │  ← append-only evidence trail
  └──────────────────────────────────────────────────────────────┘
```

The store and archive run in parallel — configuring one does not constrain the other (except `archive_backend: worm`, which shares the SQLCipher DB file and requires `store_backend: sqlcipher`). The credential backend is selected automatically based on OS and is not configurable separately.

#### Store Backends (simple → complex)

**`sqlcipher` (default)** — a single AES-256 encrypted SQLite file collocated with the workspace at `.arch-assurance/store.db`. Best choice for individuals and small teams working in a single workspace. Setup is a single `arch-assurance init`.

```bash
arch-assurance init                # creates .arch-assurance/store.db
arch-assurance unlock              # verifies key, activates auto-unlock
```

**`private-git`** — Fernet-encrypted JSON files in a local directory tree (`.arch-assurance-git/`). Each assurance entity is a separate `.enc` file; the directory is git-trackable (history is ciphertext). Suited to teams that want file-level encryption with a browsable, diffable history.

```bash
arch-assurance init --backend private-git
arch-assurance unlock
```

No `libsqlcipher-dev` system library is required for the `private-git` backend — it uses only the Python `cryptography` package.

**`pocketbase`** — delegates storage to a [PocketBase](https://pocketbase.io) REST API. Suited to shared team deployments where multiple workstations should access the same assurance evidence. Requires a running PocketBase instance and three environment variables:

```bash
export ARCH_POCKETBASE_URL="http://localhost:8090"
export ARCH_POCKETBASE_ADMIN_EMAIL="admin@example.com"
export ARCH_POCKETBASE_ADMIN_PASSWORD="..."

arch-assurance pocketbase-init --base-url http://localhost:8090 --admin-token <token>
arch-assurance use-backend pocketbase
arch-backend --restart --daemon
```

PocketBase authentication is session-based (env-var HTTP credentials) and does not use the OS credential backend for key storage — the PocketBase server handles its own encryption.

#### Switching Backends

```bash
# Switch the active backend (writes config/settings.yaml)
arch-assurance use-backend sqlcipher
arch-assurance use-backend private-git
arch-assurance use-backend pocketbase

# Then restart the backend
arch-backend --restart --daemon
```

Data is not migrated automatically when switching backends. Use `arch-assurance export -o backup.json` before switching if you need to preserve existing entries.

### MCP Tools for AI Agents

When the assurance MCP servers are configured (see [Assurance MCP Servers](#assurance-mcp-servers-optional)), AI agents have access to tools for creating and querying assurance content — STPA hazards, losses, UCAs, CAST incidents, GRC obligations, risk entries, and supply-chain signals — all linked to architecture entities via cross-references.

The store must be unlocked before the MCP tools become operational. Auto-unlock handles this on every backend start after the initial `arch-assurance unlock` activation.

The assurance MCP surface is intentionally split from the architecture MCP servers so agents can be granted read-only or read-write assurance access independently of their architecture repository permissions.

## Further Reading

- **[ArchiMate Forum](https://www.opengroup.org/archimate-forum)** — the modelling language
- **`engagements/ENG-ARCH-REPO/`** — a self-describing model of this system's own architecture
- **`src/ontologies/README.md`** — how to add a new ontology module (extension contract + SysML skeleton)
- **`src/diagram_types/README.md`** — how to add a new diagram type (`config.yaml` schema + extension guide)
- **`.arch-repo/documents/`** — structured documentation templates (ADR, Standard, Specification)
