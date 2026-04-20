# Unified Backend — Architecture Rework Spec

**Status:** Ready for implementation  
**Scope:** Python backend + CLI only. Vue GUI frontend needs no structural changes (REST API surface stays stable; connection name resolution is a minor backend addition).

---

## Problem Summary

Four distinct architectural gaps:

1. **Split processes, split caches** — `arch-gui` (REST, `src/tools/gui_server.py`) and the MCP server (`src/tools/mcp_model_server.py`) are separate processes. Each holds its own `ModelRepository` in-memory cache. A write via MCP never invalidates the GUI cache; a write via GUI never invalidates the MCP cache.

2. **Write queue is MCP-only** — `src/tools/model_mcp/write_queue.py` serialises writes through a single-worker `ThreadPoolExecutor` inside the MCP process. The REST server calls write functions directly with no serialisation. Concurrent GUI writes race on shared `.md` files and the model index.

3. **Re-indexing unreliable** — The filesystem watcher (`src/tools/model_mcp/watch_tools.py`) lives only in the MCP process. The REST server has no watcher; it calls `clear_repo_caches()` inline after each write, but only for writes routed through REST. Cross-process writes are invisible.

4. **Entity rename leaves files stale** — `edit_entity` (`src/tools/model_write/entity_edit.py`) updates the `name:` frontmatter field in-place. It does not rename the `.md` file, does not rename the companion `.outgoing.md` file, and does not update the slug in the `artifact-id:` frontmatter field. After a rename, the filename still carries the old slug, the artifact-id still carries the old slug, and every connection file that references this entity by its old artifact-id is now mismatched. Git diffs become ambiguous; entity-browser displays stale labels.

---

## Resolution Summary

| Gap | Resolution |
|---|---|
| Split caches | Merge both servers into a single `arch-backend` process sharing one `ModelRepository` singleton |
| MCP-only write queue | All write paths (REST + MCP) route through the shared write queue |
| Unreliable reindex | Single watcher + post-write explicit `schedule_refresh` call in both REST and MCP paths |
| Stale filenames | `edit_entity` extended to rename files + update artifact-id + cascade to all referencing connection files |

**Entity rename strategy: full rename with cascade** (not dereferencing-only). Rationale: git diffs and file-browser navigation must reflect current entity names. The artifact-id slug is part of the canonical id and should stay consistent with the filename. The cost is a cascade scan of `.outgoing.md` files, which is bounded and can be done in-process.

---

## Key File Map (for implementation discovery)

```
src/
  tools/
    gui_server.py                  ← REST server entry point (FastAPI)
    mcp_model_server.py            ← MCP server entry point (FastMCP)
    workspace_init.py              ← arch-init state (.arch/init-state.yaml)
    model_write_cli.py             ← arch-model-write CLI (direct disk I/O today)
    gui_routers/
      state.py                     ← shared ModelRepository singleton + helper fns
      connections.py               ← REST connection endpoints (read + write)
      entities.py                  ← REST entity endpoints
      diagrams.py                  ← REST diagram endpoints
      admin.py                     ← admin-mode write endpoints
    model_mcp/
      __init__.py                  ← registers all MCP tools on FastMCP instance
      write_queue.py               ← single-worker ThreadPoolExecutor for writes
      watch_tools.py               ← filesystem watcher + schedule_refresh + _RefreshCoord
      write_tools.py               ← MCP write tool wrappers
      edit_tools.py                ← MCP edit tool wrappers
      query_tools.py               ← MCP query tool wrappers
      context.py                   ← resolve_repo_roots, RepoScope, clear_caches_for_repo
    model_write/
      entity_edit.py               ← edit_entity / promote_entity (needs rename extension)
      connection_edit.py           ← edit_connection / edit_connection_associations
      entity.py                    ← create_entity
      connection.py                ← add_connection
  common/
    model_write.py                 ← generate_entity_id, slugify, format_entity_markdown
    model_query_parsing.py         ← parse_outgoing_file, _CONN_HEADER_RE, parse_entity
    model_query_repository.py      ← ModelRepository class (_entities, _connections, _diagrams)
    model_query_types.py           ← ConnectionRecord, EntityRecord, DiagramRecord
```

---

## Phase 0 — Connection Name Resolution (quick win, no architecture change)

**Problem:** `GET /api/connections` returns connections where `source` and `target` are raw artifact-ids. The GUI derives a human-readable label from the slug portion of the id (e.g. `author-model-artifact` from `PRC@….0NPVDb.author-model-artifact`). After any rename the slug is stale.

**Fix:** In `src/tools/gui_routers/state.py`, extend `connection_to_dict` to resolve `source_name` and `target_name` by looking up `repo.get_entity(artifact_id)`.

```python
# state.py — extend connection_to_dict
def connection_to_dict(c: ConnectionRecord) -> dict[str, Any]:
    ...
    repo = get_repo()
    src_rec = repo.get_entity(c.source)
    tgt_rec = repo.get_entity(resolved_target)
    d["source_name"] = src_rec.name if src_rec else c.source
    d["target_name"] = tgt_rec.name if tgt_rec else resolved_target
    ...
```

`get_entity` is already defined on `ModelRepository` and returns `EntityRecord | None`. The lookup is O(1) against the in-memory dict. No new endpoints needed.

Also update `ConnectionsPanel.vue` (if it uses the slug to derive labels) to consume `source_name` / `target_name` from the API response.

---

## Phase 1 — Unified Backend

### 1.1 Mount FastMCP on FastAPI

FastMCP provides `FastMCP.streamable_http_app() -> Starlette` (confirmed available). This returns a Starlette ASGI app whose lifespan manages the MCP session manager. Mount it at `/mcp` on the FastAPI app.

```python
# In _make_app() inside gui_server.py (or new arch_backend.py):
from src.tools.mcp_model_server import mcp   # the FastMCP instance

mcp_sub = mcp.streamable_http_app()
app.mount("/mcp", mcp_sub)
```

**Important:** `streamable_http_app()` uses a Starlette `lifespan` that calls `self.session_manager.run()`. The FastAPI app must propagate this lifespan. Use `lifespan_manager` composition:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def combined_lifespan(app):
    async with mcp_sub.router.lifespan_context(app):  # or use anyio task group
        yield
```

Alternatively, call `mcp.run_streamable_http_async()` in a background task. Test which integrates more cleanly with uvicorn.

### 1.2 Shared ModelRepository

The REST layer already uses a global `_repo` in `src/tools/gui_routers/state.py`. The MCP tools currently resolve their own repo via `src/tools/model_mcp/context.py:resolve_repo_roots` + `clear_caches_for_repo`.

**Target:** MCP tools call `state.get_repo()` from `src/tools/gui_routers/state.py` instead of building their own. `clear_caches_for_repo` in `context.py` becomes a thin wrapper around `state.clear_caches(root)`.

Changes:
- `src/tools/model_mcp/context.py`: import and delegate to `state.get_repo()` / `state.clear_caches()`.
- MCP tool functions in `write_tools.py` and `edit_tools.py`: already receive `repo_root` — keep that pattern but resolve against `state._repo` when the root matches.
- `mcp_model_server.py`: no longer creates a separate repo; relies on `state` initialisation triggered by the shared startup.

### 1.3 Shared Write Queue

`write_queue.py` already implements a module-level singleton (`_executor`). Both REST and MCP paths importing `queued` from the same module automatically share the queue in-process. No code change needed once both run in the same process.

For REST write endpoints, wrap handlers with `queued()` or run them via `asyncio.get_running_loop().run_in_executor(write_queue._get_executor(), ...)`. The cleanest approach: create a `src/tools/model_write/write_queue_rest.py` helper that wraps FastAPI endpoint bodies in the same executor — or simply apply `queued` to the underlying write functions called by REST endpoints.

### 1.4 New entry point

Create `src/tools/arch_backend.py` (new file) as the unified entry point:

```
arch-backend (CLI command, registered in pyproject.toml)
  → starts uvicorn with the merged FastAPI+FastMCP app
  → writes .arch/backend.pid on startup
  → starts filesystem watcher (auto_start_default_watcher)
  → removes .arch/backend.pid on shutdown
```

Keep `gui_server.py` and `mcp_model_server.py` as thin wrappers / deprecated entry points that delegate to `arch_backend.py`. Remove duplication gradually.

---

## Phase 2 — Reliable Re-indexing

### 2.1 Post-write trigger

After every successful write operation (entity create/edit/delete, connection add/edit/remove, diagram create/edit/delete), call `schedule_refresh(roots)` explicitly. Currently REST handlers call `clear_repo_caches(repo_root)` which only clears the in-memory dict and forces a lazy reload on next access. Replace with (or supplement with) `schedule_refresh` from `watch_tools.py` so the background refresh happens immediately rather than on next request.

Location: in `src/tools/gui_routers/state.py:clear_caches()` — wrap the existing call with a `schedule_refresh`.

### 2.2 Single watcher at startup

In `arch_backend.py` main startup, call `auto_start_default_watcher(...)` once. The watcher already coalesces concurrent refresh requests via `_RefreshCoord` (see `watch_tools.py` lines `_RefreshCoord`, `schedule_refresh`, `_refresh_worker`). No additional debounce layer is needed — the watcher polls at `interval_s` (default 2 s) and fingerprints the repo state; changes within one poll interval are naturally batched.

Remove the separate watcher startup from `mcp_model_server.py:main()` — it moves to `arch_backend.py`.

---

## Phase 3 — Entity Rename with File Cascade

### 3.1 Artifact-id slug structure

```
TYPE@epoch_seconds.random6chars.slug-of-name
e.g.  PRC@1776635640.U4aAdh.architecture-modelling-planning
```

`slugify` in `src/common/model_write.py:44`: `lower + collapse-non-alphanum-to-dash + strip-leading-trailing-dashes`. The slug in the artifact-id is frozen at creation time. File rename must update it.

### 3.2 What changes on a name rename

Given old artifact-id `PRC@ts.hash.old-slug` and new name → new slug:

| Artifact | Change |
|---|---|
| `model/…/PRC@ts.hash.old-slug.md` | rename to `PRC@ts.hash.new-slug.md` |
| `model/…/PRC@ts.hash.old-slug.outgoing.md` | rename to `PRC@ts.hash.new-slug.outgoing.md` (if exists) |
| `artifact-id: PRC@ts.hash.old-slug` in `.md` frontmatter | update to `PRC@ts.hash.new-slug` |
| All `.outgoing.md` files across engagement repo containing `PRC@ts.hash.old-slug` | update every occurrence (connection target headers + `§assoc` annotations) |
| PUML diagram files | **no change** — diagrams reference entities by `display_alias` (e.g. `PRC_U4aAdh`), not by artifact-id |
| `.outgoing.md` **headers** format | `### conn-type [src] → [tgt] PRC@ts.hash.old-slug` → update target token |
| `<!-- §assoc PRC@ts.hash.old-slug -->` annotations | update inline |

### 3.3 Implementation in `edit_entity`

Extend `src/tools/model_write/entity_edit.py:edit_entity`:

```python
if name is not None and eff_name != str(fm.get("name", "")):
    new_slug = slugify(eff_name)
    old_slug = slugify(str(fm.get("name", "")))
    if new_slug != old_slug:
        # 1. Compute new artifact-id
        old_id = artifact_id
        new_id = artifact_id.rsplit(".", 1)[0] + "." + new_slug  # keep TYPE@ts.hash prefix
        # 2. Update artifact-id in content
        content = content.replace(f"artifact-id: {old_id}", f"artifact-id: {new_id}")
        # 3. Rename files (after writing new content)
        new_entity_file = entity_file.with_name(entity_file.name.replace(old_slug, new_slug, 1))
        old_outgoing = entity_file.with_suffix("").with_suffix(".outgoing.md")  # TYPE@ts.hash.old-slug.outgoing.md
        new_outgoing = new_entity_file.with_suffix("").with_suffix(".outgoing.md")
        # 4. Cascade: scan all .outgoing.md files in all repo roots for old_id references
        _cascade_artifact_id_rename(repo_root, old_id, new_id)
        # 5. Atomic: write new content to new filename, delete old filename
```

For the cascade scan (`_cascade_artifact_id_rename`), scan `model/` in the **engagement repo only**:
```python
for f in repo_root.glob("model/**/*.outgoing.md"):
    text = f.read_text(encoding="utf-8")
    if old_id in text:
        f.write_text(text.replace(old_id, new_id), encoding="utf-8")
```

Cross-repo cascade is not needed: nothing in the enterprise repo may reference engagement-repo entities (the dependency is one-directional), and engagement-repo references to enterprise entities are mediated by proxy entities (GRF files) whose artifact-ids are stable and separate from the enterprise originals.

The regex `_CONN_HEADER_RE` in `src/common/model_query_parsing.py` already parses the target token from headers. The cascade replace by string is safe because artifact-ids are globally unique tokens (no partial-match risk given the `TYPE@ts.hash.slug` format).

### 3.4 Dry-run cascade report

In dry-run mode, return a list of files that **would** be modified by the cascade, as part of `WriteResult.warnings` or a new `rename_cascade` field in the result dict.

---

## Phase 4 — Single-Instance Guarantee + stdio Bridge

### 4.1 PID file

On `arch-backend` startup:
- Write `{workspace_root}/.arch/backend.pid` containing `{"pid": os.getpid(), "port": port}`.
- On graceful shutdown (SIGTERM / SIGINT), remove the file.
- On startup, check for existing PID file: send `GET /api/stats` health probe to the running port. If healthy, log "backend already running on port X" and exit 0. If stale (no response), overwrite.

`workspace_root` = parent of `.arch/` = the directory containing `.arch/init-state.yaml` (from `src/tools/workspace_init.py`).

### 4.2 stdio Bridge (`arch-mcp-stdio`)

New command `arch-mcp-stdio` (registered in `pyproject.toml`). Thin script:

1. Read `.arch/backend.pid` → get `port`.
2. If no PID file or stale: optionally start `arch-backend` as a subprocess (detached) and wait for it to become healthy; or error out with a clear message.
3. Connect stdin/stdout to `http://localhost:{port}/mcp` using the MCP streamable-HTTP protocol.

Implementation: use `anyio` or `asyncio` + `httpx` to bridge stdio ↔ HTTP. Alternatively, use the MCP Python SDK's built-in stdio↔HTTP bridge if it exposes one.

**VSCode / Claude Code MCP config** (update `arch-init` to generate this):
```json
{
  "mcpServers": {
    "sdlc-model": {
      "command": "uv",
      "args": ["run", "arch-mcp-stdio"]
    }
  }
}
```

All clients launch the bridge; the bridge connects to the single running backend. Single-instance is enforced at the PID level.

### 4.3 CLI proxy (`arch-model-write`)

Extend `src/tools/model_write_cli.py`:
1. Detect running backend via `.arch/backend.pid`.
2. If backend healthy: proxy write commands as `POST /api/entity/remove` etc. (existing REST endpoints) instead of direct disk I/O.
3. If no backend: fall back to current direct `ModelRegistry` path (useful in CI / headless environments).

---

## Phase 5 — Connection Display: Resolved Names (completes Phase 0)

After Phase 3 (rename cascade) is in place, the connection display issue is fully resolved because:
- Artifact-ids in `.outgoing.md` headers are kept in sync with the entity's current name slug.
- `connection_to_dict` resolves `source_name` / `target_name` from the live index (Phase 0 fix).

No additional work needed.

---

## Non-Goals

- **File format changes** — `.md` + YAML frontmatter is unchanged.
- **Authentication** — no changes to the existing admin-mode convention.
- **Database / SQLite** — keep file-based model storage.
- **Docker changes** — the backend container remains the same; the stdio bridge on the host connects over the mapped port. No Docker-specific code paths.

---

## Implementation Order

```
Phase 0  (30 min)   connection_to_dict name resolution — immediate user-visible win
Phase 1  (2–3 h)    unified backend (merge servers, mount MCP on FastAPI, shared write queue)
Phase 2  (1 h)      post-write refresh trigger, move watcher to shared startup
Phase 3  (3–4 h)    entity rename cascade (most complex; dry-run report first)
Phase 4  (2–3 h)    PID file, stdio bridge, CLI proxy
```

Total estimate: ~1–1.5 person-days for a focused implementation session.

---

## Open Questions Before Starting

1. **FastMCP lifespan integration** — verify that `app.mount('/mcp', mcp.streamable_http_app())` correctly propagates the Starlette lifespan into uvicorn. Test with `run_streamable_http_async` as an alternative if mount lifespan doesn't compose cleanly.

2. **`arch-mcp-stdio` MCP SDK support** — check if `mcp` Python SDK already provides a stdio↔streamable-HTTP bridge utility; avoid reimplementing if so.
