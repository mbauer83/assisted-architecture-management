# Unified Backend — Revised Plan

**Status:** In progress  
**Decision:** Keep one long-lived HTTP backend process and let MCP clients attach through a short-lived stdio bridge.

## Why The Original Plan Needed Correction

The original direction was right, but a few details were too optimistic:

1. `FastMCP.streamable_http_app()` can be mounted on FastAPI, but the parent ASGI app must start `mcp.session_manager.run()` in its lifespan. Mounting alone is not enough.
2. Auto-loaded MCP servers in tools like Claude Code or VS Code will still spawn a process per registered shell command. If that command starts the whole backend, we are back to split processes and duplicate caches.
3. The GUI does need a small frontend adjustment: connection responses must expose `source_name` / `target_name`, and the connection panel should prefer those live names over slug-derived labels.
4. Showing users a raw list of entity-rename-affected files is not good default UX. The GUI should treat rename cascade as an internal consistency operation. A compact warning/count is enough for dry runs and logs.
5. Entity rename has one more required change than the original spec called out: the renamed entity’s own `.outgoing.md` file must update its `source-entity:` frontmatter, not just its filename and external references.

## Adopted Architecture

### Runtime model

- `arch-backend` is the primary process.
- It serves:
  - REST API
  - Vue static assets
  - MCP Streamable HTTP at `/mcp`
- It owns:
  - the shared `ModelRepository`
  - the shared write queue
  - the shared watcher / refresh loop

### MCP client integration

- Registered MCP shell commands should run `arch-mcp-stdio`, not `arch-mcp-model --transport stdio`.
- `arch-mcp-stdio` is a thin bridge:
  - ensure the unified backend is running
  - connect to `http://127.0.0.1:<port>/mcp`
  - proxy stdio JSON-RPC messages to Streamable HTTP
- This preserves good developer experience for auto-loaded MCP clients:
  - the client still launches a normal local command
  - the expensive backend stays warm and shared
  - multiple MCP clients do not create multiple model caches

### Auto-loaded IDE startup behavior

When Claude Code, VS Code, or another MCP host starts and eagerly launches configured MCP commands:

- the launched command should be a launcher, not a second full backend
- on first launch, the launcher starts `arch-backend` if it is not already healthy
- once the backend is healthy, the launcher attaches its stdio session to `/mcp`
- if the backend is already running, startup is just an attach

For compatibility, `arch-mcp-model --transport stdio` should also behave this way by default. A dedicated `--standalone-stdio` mode remains available for tests or explicit legacy use.

### Compatibility

- `arch-gui-server` delegates to `arch-backend`.
- `arch-mcp-model --transport streamable-http` delegates to `arch-backend`.
- `arch-mcp-model --transport stdio` attaches to `arch-backend` by default, so existing IDE configs keep working.
- `arch-mcp-model --transport stdio --standalone-stdio` remains available for explicit direct stdio hosting.

## Implemented Work

### Phase 0 — Live connection names

- Backend connection payloads now include `source_name` and `target_name`.
- The GUI connection panel now prefers those live names.

### Phase 1 — Shared in-process write serialization

- REST writes now use the same single-worker write queue module already used by MCP writes.
- This removes the worst local race between GUI writes and MCP writes once both paths share one process.

### Phase 2 — Shared cache/refresh behavior

- GUI state now exposes the shared repository roots and shared repository instance.
- MCP context reuses that in-process repository when the requested roots match the initialized backend roots.
- Post-write cache invalidation now schedules background refresh work instead of relying only on lazy reload.
- Watcher-triggered refresh uses immediate refresh logic and does not recursively reschedule itself.

### Phase 3 — Rename cascade

Entity rename now updates all of the following together:

- entity filename
- entity `artifact-id`
- companion `.outgoing.md` filename
- companion `.outgoing.md` `source-entity`
- all engagement-repo `.outgoing.md` references to the old entity id

Dry runs return a summary warning with the number of affected outgoing files. They do not return a file-by-file list for the GUI.

### Phase 4 — Unified runtime entry points

- Added `arch-backend`
- Added `arch-mcp-stdio`
- Added backend PID/state tracking in `.arch/backend.pid`
- `arch-model-write` now proxies to the backend when it is already running, and falls back to direct file operations otherwise

## Developer Experience Guidance

### Preferred local setup

Use this MCP config:

```json
{
  "mcpServers": {
    "arch-model": {
      "command": "uv",
      "args": ["run", "arch-mcp-stdio"]
    }
  }
}
```

This is better than registering `arch-mcp-model --transport stdio` directly because:

- it keeps a single warm backend process
- it avoids duplicate caches/watchers across clients
- GUI and MCP now see the same model state
- startup cost moves out of the critical path after the first launch

### Backend startup behavior

- `arch-backend` writes `.arch/backend.pid`
- if a healthy backend is already running for the workspace, a second backend exits cleanly
- `arch-mcp-stdio` autostarts the backend when needed

## Non-Goals

- no format change to model files
- no auth redesign
- no database migration
- no GUI surface for “rename cascade file lists”

## Remaining Follow-Ups

1. Update README examples and any generated MCP config templates to prefer `arch-mcp-stdio`.
2. Add focused tests around:
   - backend PID/autostart behavior
   - stdio bridge proxying
   - REST write serialization under contention
3. Consider whether `arch-init` should eventually emit recommended MCP config snippets, but do not block the runtime change on that.
