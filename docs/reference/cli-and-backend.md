# CLI & Backend Reference

All commands are installed as console scripts by `uv sync` (defined in `pyproject.toml`).

&nbsp;

## Workspace & setup

| Command | Purpose |
|---|---|
| `arch-init` | Resolve `arch-workspace.yaml`, write `.arch/init-state.yaml` |
| `arch-init --initialize-engagement-repo-if-empty` | Scaffold a configured-but-empty engagement git repo |
| `arch-init --initialize-enterprise-repo-if-empty` | Scaffold a configured-but-empty enterprise git repo |
| `get-plantuml` | Download and verify `tools/plantuml.jar` from Maven Central |
| `get-diagram-runtime` | Pull the supported PlantUML + Graphviz runtime |
| `check-diagram-runtime` | Verify Graphviz ≥ 2.49.0 / PlantUML compatibility |

&nbsp;

## Engagement switching

```bash
arch-switch-engagement CLIENT-B                                   # switch active engagement, restart backend
arch-switch-engagement CLIENT-C --url git@github.com:org/c.git    # register a git-backed engagement (clones beside workspace)
arch-switch-engagement CLIENT-D --local ../client-d --create      # scaffold a new local engagement
arch-switch-engagement CLIENT-E --url git@github.com:org/e.git --create   # scaffold + attach origin
```

`--create` scaffolds the standard directory structure (`model/`, `docs/`, `diagram-catalog/`,
`.arch-repo/`), a git repo on the configured branch, an initial commit, and default
frontmatter / attribute-profile / document-type schemata.

&nbsp;

## Backend

```bash
arch-backend --daemon              # serve REST at :8000, MCP at :8000/mcp, GUI at /
arch-backend --status
arch-backend --stop
arch-backend --restart --daemon
```

| Mode | Flag | Effect |
|---|---|---|
| Normal (default) | — | Read/write engagement; enterprise read-only via promotion |
| Admin | `--admin-mode` | Direct enterprise writes via GUI/REST; GUI shows a banner |
| Read-only | `--read-only` | All writes blocked globally; MCP write server rejects mutations |

`--daemon` starts a detached session, redirects stdin from `/dev/null`, and writes to
`backend.log_path`. `arch-backend &` also works and detaches stdin when it detects a
background TTY job, but `--daemon` is the preferred operational form.

&nbsp;

## Other entry points

| Command | Purpose |
|---|---|
| `arch-mcp-stdio-read` / `arch-mcp-stdio-write` | Architecture MCP servers (stdio bridges) |
| `arch-mcp-stdio-assurance-read` / `arch-mcp-stdio-assurance-write` | Assurance MCP servers |
| `arch-write-cli` | Command-line authoring against the write pipeline |
| `arch-assurance …` | Assurance store/archive management — see [Assurance CLI](../04-assurance/storage-and-confidentiality.md#cli-reference) |

&nbsp;

## Troubleshooting

If the GUI hangs on "Loading...", diagnose the transport before assuming a lock:

```bash
arch-backend --status
curl --max-time 5 http://127.0.0.1:8000/api/stats
curl --max-time 5 http://127.0.0.1:5173/api/stats   # if using the Vite dev server
tail -n 100 .arch/backend.log                        # or the configured backend.log_path
```

If `--status` reports `process state: T`, the backend is stopped while still holding the
port. Recover with:

```bash
arch-backend --stop
arch-backend --daemon
```
