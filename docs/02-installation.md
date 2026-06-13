# Installation & Setup

> Full setup, per operating system. For the five-minute path, see the
> [Quickstart in the README](../README.md#quickstart).

- [System requirements](#system-requirements)
- [Per-environment prerequisites](#per-environment-prerequisites) — macOS · Debian/Ubuntu · WSL2 · Docker
- [1. Install Python dependencies](#1-install-python-dependencies)
- [2. Diagram runtime](#2-diagram-runtime)
- [3. Initialise the workspace](#3-initialise-the-workspace)
- [4. Start the backend](#4-start-the-backend)
- [5. Configure MCP access for AI agents](#5-configure-mcp-access-for-ai-agents)
- [6. Frontend development (optional)](#6-frontend-development-optional)
- [7. Quality checks](#7-quality-checks)
- [Running in Docker](#running-in-docker)
- [Assurance store setup](#assurance-store-setup)

For backend ports, log paths, schemata, and storage backends, see
[Configuration Reference](reference/configuration.md).

---

&nbsp;

## System requirements

| Dependency | Minimum | Purpose |
|---|---|---|
| Python | 3.13 | All server and CLI components |
| `uv` | any recent | Python environment and script runner |
| Java | 11 | PlantUML diagram rendering and verification |
| Graphviz | 2.49.0 | Diagram layout engine |
| Node.js | 18 | Frontend development only (not needed to run) |
| npm | 9 | Frontend development only |
| SQLCipher (system lib) | 4 | Assurance store (optional) |

---

&nbsp;

## Per-environment prerequisites

### macOS

```bash
# Core
brew install python@3.13 openjdk graphviz
curl -LsSf https://astral.sh/uv/install.sh | sh

# Frontend development (optional)
brew install node

# Assurance store (optional)
brew install sqlcipher
```

Java from Homebrew needs a symlink for the system `java` command:

```bash
sudo ln -sfn $(brew --prefix openjdk)/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk.jdk
```

Assurance-store credentials live in **macOS Keychain** automatically — no extra setup.

### Linux (Debian / Ubuntu)

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

For credential storage the assurance store uses **SecretService (D-Bus / gnome-keyring)**
when a desktop session is running. On headless servers (CI, SSH-only), set a master password
instead — see [Assurance: credential storage](04-assurance/storage-and-confidentiality.md#credential-storage).

### WSL2 on Windows

Run every command in the WSL2 Debian/Ubuntu shell and follow the Debian/Ubuntu steps above.

SQLCipher needs the native system library inside WSL2, even though the Windows host has no
equivalent:

```bash
sudo apt-get install -y libsqlcipher-dev
```

Credentials are kept in **Windows DPAPI** through PowerShell interop
(`Export-Clixml` / `Import-Clixml`), encrypting each key with the Windows user's login
credentials — machine-and-user-scoped, with no setup beyond having PowerShell reachable from
WSL2 (the default on Windows 11).

### Docker

No local prerequisites beyond Docker. The image bundles Java, Graphviz, and all Python
dependencies. See [Running in Docker](#running-in-docker).

The assurance store is **not** enabled in the default image because it needs host-level
credential storage. To use it in Docker, mount credentials or supply
`ARCH_ASSURANCE_MASTER_PASSWORD` as an environment variable.

---

&nbsp;

## 1. Install Python dependencies

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

> Use `uv sync`, not `pip install`. The `zuban` type checker requires
> `uv sync --all-groups` before it will run.

&nbsp;

## 2. Diagram runtime

```bash
# Download and verify plantuml.jar from Maven Central
get-plantuml                   # → tools/plantuml.jar (gitignored)

# Pull the supported local diagram runtime (PlantUML + Graphviz)
get-diagram-runtime

# Verify local Graphviz/PlantUML compatibility for rendering
check-diagram-runtime          # requires Graphviz >= 2.49.0
```

&nbsp;

## 3. Initialise the workspace

An `arch-workspace.yaml` at the workspace root declares the two repositories. The simplest
form keeps a single explicit engagement:

```yaml
engagement:
  local: engagements/ENG-ARCH-REPO/architecture-repository
  # or git: { url: "https://...", branch: main, path: .arch/repos/engagement }

enterprise:
  local: enterprise-repository
  # or git: { url: "https://...", branch: main, path: .arch/repos/enterprise }
```

Then resolve and validate it:

```bash
arch-init                      # reads arch-workspace.yaml, writes .arch/init-state.yaml

# If a configured git repo exists locally but is still empty / uninitialised
arch-init --initialize-engagement-repo-if-empty
arch-init --initialize-enterprise-repo-if-empty
```

For workspaces that hop between multiple engagement repos, and for `arch-switch-engagement`
usage, see [CLI & Backend Reference](reference/cli-and-backend.md).

&nbsp;

## 4. Start the backend

```bash
# Unified backend: REST API at :8000, MCP at :8000/mcp, GUI at /
arch-backend --daemon

# Inspect / stop / restart
arch-backend --status
arch-backend --stop
arch-backend --restart --daemon
```

`--daemon` starts the backend in a new session, redirects stdin from `/dev/null`, and writes
to `backend.log_path`. This avoids the shell job-control stops that can happen with a raw
`arch-backend &` when a background process reads from the terminal. (`arch-backend &` still
works and detaches stdin when it detects a background TTY job; `--daemon` is the preferred
operational form.)

If the GUI hangs on "Loading...", diagnose the transport before assuming a lock — see
[CLI & Backend Reference](reference/cli-and-backend.md#troubleshooting).

&nbsp;

## 5. Configure MCP access for AI agents

Add the servers to `.mcp.json` (Claude Code) or `.vscode/mcp.json` (VS Code):

```json
{
  "mcpServers": {
    "arch-repo-read":  { "command": "uv", "args": ["run", "arch-mcp-stdio-read"] },
    "arch-repo-write": { "command": "uv", "args": ["run", "arch-mcp-stdio-write"] }
  }
}
```

The MCP surface is split into two servers so an agent can be constrained by capability
(read-only vs. authoring). Both STDIO bridges auto-start the unified backend when needed and
connect over HTTP, so GUI and MCP traffic share the same in-process cache and write queue.

To attach to an already-running external backend instead, set
`"env": { "ARCH_MCP_BACKEND_URL": "http://127.0.0.1:8000" }` on the server entry.

For the optional assurance MCP servers, see
[Assurance MCP tools](04-assurance/mcp-tools.md). For inspecting the live tool surface with
the MCP Inspector, see [Interfaces & MCP](03-modeling/interfaces-and-mcp.md).

&nbsp;

## 6. Frontend development (optional)

For active frontend work with Vite hot-reload:

```bash
cd tools/gui
npm install
npm run dev
# → open http://localhost:5173  (API calls proxy to arch-backend on :8000)
```

&nbsp;

## 7. Quality checks

Python lint and type checks from the workspace root:

```bash
uv run ruff check src
uv run zuban check
uv run pytest --tb=short -q
```

`ruff` covers import sorting plus core error detection and ignores the model/content repos,
the test tree, and the Vue tree. `zuban` runs in Mypy-compatible mode against `src/`.

Coverage is opt-in (the default run stays fast):

```bash
uv run pytest --cov                       # terminal summary with missing lines
uv run pytest --cov --cov-report=html     # browsable htmlcov/ report
```

One run yields three figures because branch coverage is enabled. The **canonical, reported
number is statement/line coverage (~79%)** — this is what Codecov shows. coverage.py's own
headline (`percent_covered`, and therefore the `fail_under` ratchet) is the **branch-inclusive
combined** metric (~76%); branch-only coverage is ~66%. Quote the same basis everywhere to
avoid apparent discrepancies between the badge and a local run.

Frontend lint and type checks from `tools/gui`:

```bash
cd tools/gui
npm run lint
npm run typecheck
```

The frontend uses ESLint 9 with the Vue and TypeScript flat-config presets plus type-aware
rules, and `vue-tsc` / `tsc` for application and Vite config type-checking.

---

&nbsp;

## Running in Docker

```bash
# Start with the bundled self-describing model
docker compose up --build
# → http://localhost:8000

# Or point at a different repository
ARCH_REPO_ROOT=/path/to/your/architecture-repository docker compose up --build
```

The container includes the system dependencies for PlantUML rendering (Java, Graphviz,
fonts). To attach host-started MCP clients to the Dockerised backend, publish the container
on `localhost:8000` (the compose file does this) and set
`ARCH_MCP_BACKEND_URL=http://127.0.0.1:8000` in your MCP config so the launcher attaches to
the published port instead of starting its own.

---

&nbsp;

## Assurance store setup

The assurance store is an encrypted evidence store for safety analysis (STPA, CAST),
governance (GRC), and supply-chain security. It is optional, and the default SQLCipher
backend needs `libsqlcipher-dev` on the host (see prerequisites above).

```bash
# Create the encrypted database and store the key in the OS credential backend
arch-assurance init

# Verify the key round-trips and activate auto-unlock on backend start
arch-assurance unlock

# Save the recovery key offline (store it in a password manager)
arch-assurance export-key
```

On later backend starts the store unlocks automatically from the OS credential backend. The
full backend matrix, credential storage per OS, WORM archives, and the CLI reference live in
[Assurance: storage & confidentiality](04-assurance/storage-and-confidentiality.md).

---

*Next: [Architecture Modeling →](03-modeling/index.md)*
