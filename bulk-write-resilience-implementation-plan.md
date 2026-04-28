# Bulk Write / Edit Resilience Implementation Plan

## Current Status

Implemented already:

- authoritative writes now apply exact-path index/cache updates synchronously
- background reconciliation is separated from authoritative mutation paths
- per-item macro regeneration was removed from normal entity/GAR write flows
- macro regeneration is batched through mutation context finalization
- bulk delete now handles implicit internal connection removal and finalizes as one authoritative batch update
- `artifact_bulk_write()` now uses staged temp-repo execution for live all-or-nothing commit semantics
- `artifact_bulk_delete()` now also uses staged temp-repo execution for live all-or-nothing commit semantics
- staged bulk-write verification now defaults to `impacted` scope
- bulk write/delete now emit `operation_id`, support completed-result reuse via `idempotency_key`, and expose operation lookup
- bulk MCP tooling has been split into focused submodules; the `bulk_tools.py` compatibility wrapper is now 15 LoC
- targeted atomicity, index-consistency, staging-isolation, and observability tests have been added

The planned resilience work in this document is now implemented.

## Updated Runtime Guidance

For this codebase in April 2026:

- use high-level async/thread offload where possible
- prefer `asyncio.to_thread()` or `loop.run_in_executor()` for normal blocking work
- use `asyncio.TaskGroup` over `gather()` when structured async subtask orchestration matters
- treat `asyncio.Future` / `wrap_future()` as low-level bridge tools only
- prefer explicit loop/future bridging only when we fully control the boundary and the runtime behavior is proven stable under tests

Current pragmatic decision:

- the write queue remains the commit boundary
- the queue wait path stays on the proven polling implementation for now because both `wrap_future()` and explicit future-bridging attempts showed flaky behavior under the dedicated queue tests in this environment
- queue waiting should be revisited during the later queue/observability refactor rather than coupled to the current bulk-write work

## Residual Follow-Up

1. Queue waiting still uses polling.
   - This remains the pragmatic path until a future `to_thread()` / executor-native refactor is proven stable under the queue tests.

2. Verification scope is reduced but not caller-configurable.
   - Bulk operations default to `impacted`; exposing scope control can wait unless another workflow needs it.

3. Bulk operations may need optional diagram auto-sync.
   - Done: opt-in bulk write/delete auto-sync now reconciles affected diagrams, including delete-on-empty behavior.

4. Source-file size policy now has an automated gate.
   - New non-test Python files over 350 counted lines fail validation; existing oversized files are baseline-capped until refactored.

5. Load-testing for bulk operations is intentionally deferred.
   - Transaction behavior and safety coverage landed first; broader performance/soak work is still open.

## Delivery Order

Completed.

## Phase A: Transactional Bulk Write

### Status

Implemented in first form.

### Objective

Make `artifact_bulk_write` all-or-nothing for live writes.

### Strategy

Implement a staged temp-repository batch engine:

1. Build the ordered mutation plan in memory.
2. Copy the writable repository content into a temp workspace.
3. Execute create/edit/connection mutations against the temp repo using low-level write ops.
4. Verify the staged post-state once.
5. If verification succeeds, copy staged file changes back to the live repo in one commit wave.
6. Finalize one authoritative mutation context on the live repo.

### Notes

- This is intentionally pragmatic.
- It reuses existing low-level writers instead of immediately introducing a full content-map mutation DSL.
- It preserves the existing single write queue as the serialized commit boundary.

### Acceptance

- no partial live repo mutation when a later bulk-write item fails
- one authoritative index/cache update wave per successful batch
- one macro regeneration wave per successful batch

### Follow-up Still Needed

Done in this tranche.

- removed the remaining monolithic `bulk_tools.py` implementation and kept only a thin compatibility wrapper
- retained temp-staging isolation at the bulk-write boundary and kept index/cache publication on the live authoritative finalize path only
- extended coverage across staged bulk write/delete commit-failure paths, index consistency, diagram auto-sync, and source-file policy enforcement

## Phase B: Verification Scope Reduction

### Status

Done.

- bulk-write staged verification uses `impacted` scope
- bulk-delete post-commit verification uses `impacted` scope
- delete-connection preflight now blocks dangling diagram `connection-ids-used` references unless those diagrams are deleted in the same batch
- unrelated broken diagrams no longer block valid bulk write/delete batches

### Objective

Avoid repo-wide verification for every successful bulk operation while preserving correctness.

### Changes

- add verification scopes: `changed`, `impacted`, `full`
- default bulk operations to `impacted`
- reserve `full` for explicit/admin/CI usage
- verify only affected diagrams for syntax by default

### Acceptance

- normal bulk operations no longer verify every diagram by default
- affected artifacts and impacted references still verify correctly

### Follow-up Still Needed

- make verification scope explicit in bulk-tool inputs if caller control becomes necessary later
- extend changed/impacted verification beyond the current bulk paths if other long-running write workflows need it

## Phase C: Durable Operation Tracking

### Status

Done.

- added in-process operation registry
- bulk write/delete accept `idempotency_key`
- completed operations can be fetched by `operation_id`
- retry with the same completed key reuses the prior result without re-mutating the repo

### Objective

Make long-running bulk operations observable, retrievable, and retry-safe.

### Changes

- add `src/infrastructure/write/operation_registry.py`
- track:
  - `operation_id`
  - tool name
  - enqueue/start/end times
  - current phase
  - final payload
- accept optional idempotency keys on bulk operations
- expose read APIs for operation status/result lookup

### Acceptance

- a completed bulk operation can be queried after the original caller stops waiting
- retry with the same idempotency key returns the previous completed result

## Phase D: Watchdog And Queue Observability

### Status

Done.

- write-queue state now carries active tool / operation id / phase metadata
- operation-registry phase updates feed queue-state observability during active writes
- the backend emits a 5-second structured slow-request warning and only escalates to a later thread dump
- targeted queue-state and backend-warning tests cover the new metadata path

### Objective

Make long-running writes diagnosable without treating healthy work as a stall.

### Changes

- queue state should publish:
  - active jobs
  - pending jobs
  - current operation id
  - current tool
  - current phase
- backend watchdog should:
  - emit a structured slow-request warning at 5 seconds
  - escalate to full thread dump only at a longer threshold or explicit stall
- log one batch summary line on completion

### Acceptance

- healthy 6-10 second bulk writes do not immediately produce thread dumps
- real stalls still produce enough context to diagnose phase and ownership

## Target Tests Still Needed

None in this plan tranche.

## Current Validation Snapshot

Current state after the latest implementation pass:

- `pytest -q`: `396 passed`
- `ruff check .`: green
- `zuban check`: green

## End-State Validation

Before closing this work:

- targeted and broad test suites must be green
- type-checking must be green
- linting must be green
