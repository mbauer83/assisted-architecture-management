# Incremental Entity Context Read Model


Goal: make entity-page connection refreshes scale to thousands or low tens of thousands of entities by replacing full rebuild + multi-request read patterns with an incremental entity-centered read model.

## Problem

Current post-write path for connection changes on entity-page:

1. write succeeds
2. GUI cache clear performs synchronous `_repo.refresh()` in [src/tools/gui_routers/state.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/gui_routers/state.py:184)
3. entity page reloads:
   - `outbound`
   - `inbound`
   - `any`
   in [tools/gui/src/ui/views/EntityDetailView.vue](/home/mb/workspace/scalable-architecture-for-humans-and-ai/tools/gui/src/ui/views/EntityDetailView.vue:42)
4. each request hits [src/tools/gui_routers/connections.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/gui_routers/connections.py:11)

Measured on this repo:

- full repo refresh: about `0.20s`
- three post-refresh connection reads combined: about `0.24s` to `0.26s`
- total steady-state server cost after one connection write: about `0.45s`

This is rebuild-centric and will not scale.

## Decision

Implement:

1. an incremental denormalized entity-centered read model inside `ModelIndex`
2. a REST-only `GET /api/entity-context?id=...` endpoint for the GUI entity page
3. synchronous incremental write updates to the index/read-model

Do not implement in phase 1:

- a new MCP tool
- async-only write visibility
- client-only correctness

## Rationale

- REST and MCP should diverge here:
  - REST wants one page-oriented response
  - MCP should remain fine-grained and token-efficient
- writes should stay synchronous for correctness, but the index rebuild afterwards must become maximally incremental
- a first-hop entity-centered projection fits the expected graph shape well because most entities have low degree

## Target Architecture

### 1. Extend `ModelIndex`

Add an incremental projection layer to [src/common/model_index.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_index.py:24).

Keep:

- normalized entity records
- normalized connection records
- normalized diagram records
- full rebuild capability

Add:

- entity-centered first-hop projection
- targeted mutation APIs
- monotonic generation counter

### 2. New projection tables

Recommended SQLite tables:

`entity_context_edges`

- `entity_id`
- `connection_id`
- `direction_bucket`
  - `outbound`
  - `inbound`
  - `symmetric`
- `other_entity_id`
- `conn_type`
- `connection_status`
- `source_id`
- `target_id`
- `source_name`
- `target_name`
- `source_artifact_type`
- `target_artifact_type`
- `source_domain`
- `target_domain`
- `source_scope`
- `target_scope`

`entity_context_stats`

- `entity_id`
- `conn_in`
- `conn_out`
- `conn_sym`

Recommended shape is row-wise, not one large JSON blob per entity.

### 3. New read API inside `ModelIndex`

Add:

- `read_entity_context(entity_id: str) -> dict`

Expected result content:

- base entity detail
- first-hop denormalized connections grouped by:
  - `outbound`
  - `inbound`
  - `symmetric`
- aggregate counts
- optional generation/fingerprint

### 4. New REST endpoint

Add:

- `GET /api/entity-context?id=<artifact_id>`

Recommended response:

```json
{
  "entity": {},
  "connections": {
    "outbound": [],
    "inbound": [],
    "symmetric": []
  },
  "counts": {
    "conn_in": 0,
    "conn_out": 0,
    "conn_sym": 0
  },
  "generation": 0
}
```

This endpoint is for REST/GUI only.

Do not add an MCP equivalent in phase 1.

## Write-Path Requirements

### Keep writes synchronous

Immediate post-write reads must be correct.

Therefore:

- keep synchronous write completion semantics
- replace full synchronous repo refresh with synchronous incremental updates

### Add targeted update methods

Recommended `ModelIndex` mutation surface:

- `apply_entity_file_change(path)`
- `apply_outgoing_file_change(path)`
- `apply_connection_upsert(...)`
- `apply_connection_delete(...)`
- `rebuild_entity_context_for(entity_id)`

Connection changes must update both endpoints:

- source entity
- target entity

For `.outgoing.md` changes:

1. parse old outgoing state
2. parse new outgoing state
3. diff connection ids
4. update normalized `connections`
5. update `entity_context_edges` for affected entities only
6. update `entity_context_stats` for affected entities only

Full rebuild remains as fallback and repair path.

## GUI Changes

### Entity page

Replace this read pattern:

- `/api/entity`
- `/api/connections?direction=outbound`
- `/api/connections?direction=inbound`
- `/api/connections?direction=any`

With:

- `/api/entity-context`

Update [tools/gui/src/ui/views/EntityDetailView.vue](/home/mb/workspace/scalable-architecture-for-humans-and-ai/tools/gui/src/ui/views/EntityDetailView.vue:42) to load one response instead of three.

### Client-side local mutation

Allowed later as a UX optimization.

Not the correctness foundation for phase 1.

If added later:

- local patch visible state
- optionally background-refetch `/api/entity-context`

## REST vs MCP

### REST

Add the new page-oriented endpoint.

Reason:

- reduces request fan-out
- matches GUI access pattern
- can evolve later toward SSE/WebSocket invalidation

### MCP

Keep existing tools:

- `model_query_read_artifact`
- `model_query_find_connections_for`

Reason:

- smaller payloads
- lower token cost
- avoid widening the tool surface without a proven need

Backend projection can still be reused later if an MCP tool becomes justified.

## Watcher / Rebuild Strategy

Current watcher-driven refresh logic is in [src/tools/model_mcp/watch_tools.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/model_mcp/watch_tools.py:53).

Target behavior:

- changed-file incremental apply for:
  - entity `.md`
  - `.outgoing.md`
  - diagram files as needed
- full rebuild only on:
  - parser failure
  - missing previous state
  - explicit repair

Do not remove full rebuild support.

## Phased Plan

### Phase 1

1. extend `ModelIndex` with entity-context projection tables
2. add `read_entity_context(entity_id)`
3. add `GET /api/entity-context`
4. switch GUI entity page to it

### Phase 2

1. add targeted `ModelIndex` mutation methods
2. replace GUI write-path full refresh with incremental synchronous updates
3. keep full rebuild fallback

### Phase 3

1. update watcher path to apply changed files incrementally
2. use full rebuild only as fallback

### Phase 4

1. optional client-side optimistic updates
2. optional SSE/WebSocket invalidation later

## Tests

Add tests for:

- full rebuild vs incremental update parity
- connection add updates only affected entities
- connection remove updates only affected entities
- connection edit updates only affected entities
- `entity-context` response correctness
- immediate post-write read correctness
- GUI entity page using one context request instead of three connection requests

## References

- full refresh bottleneck:
  - [src/common/model_index.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_index.py:83)
  - [src/tools/gui_routers/state.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/gui_routers/state.py:184)
- entity-page reload pattern:
  - [tools/gui/src/ui/views/EntityDetailView.vue](/home/mb/workspace/scalable-architecture-for-humans-and-ai/tools/gui/src/ui/views/EntityDetailView.vue:42)
- current connections endpoint:
  - [src/tools/gui_routers/connections.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/gui_routers/connections.py:11)
- current entity read endpoint:
  - [src/tools/gui_routers/entities.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/gui_routers/entities.py:40)
- current query path:
  - [src/common/model_query_repository.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_query_repository.py:288)
  - [src/common/model_index.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_index.py:546)
- watcher coordination:
  - [src/tools/model_mcp/watch_tools.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/model_mcp/watch_tools.py:53)
