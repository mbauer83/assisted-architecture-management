# Promotion And Verification Plan

## Goal

Restore a stricter model invariant while keeping the new runtime-shared index:

- one shared runtime model index per mounted-roots set
- centralized runtime reuse in the unified backend
- strict uniqueness for all **visible** indexed artifacts
- promotion implemented via staging so duplicate IDs never appear in the live indexed model
- verification performed against committed or explicitly staged content, not against temporarily inconsistent live roots

This document is intended as a handoff for a future session that should rework promotion and tighten verification again.

## Current State

### Runtime index

The current implementation introduced a shared runtime index service in:

- [src/common/model_index.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_index.py)
- [src/common/model_query_repository.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_query_repository.py)
- [src/common/model_verifier_registry.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_verifier_registry.py)

Key properties:

- `shared_model_index(...)` returns one process-shared runtime index for a given mounted roots set.
- Storage is runtime SQLite in memory.
- FTS is used for model search when available.
- relation queries such as direct connection lookup and neighbor traversal use SQL.
- `ModelRepository` and `ModelRegistry` are facades over the shared runtime index.

### Watch/refresh path

Current refresh coordination lives in:

- [src/tools/model_mcp/watch_tools.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/model_mcp/watch_tools.py)
- [src/tools/model_mcp/context.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/model_mcp/context.py)
- [src/tools/gui_routers/state.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/gui_routers/state.py)

Important limitation:

- the shared runtime index is centralized and reused, but refresh is still largely full-refresh driven
- watcher-triggered updates currently refresh the shared index rather than applying file-level delta upserts/deletes into SQLite

### Promotion

Promotion execution currently lives in:

- [src/tools/model_write/promote_to_enterprise.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/model_write/promote_to_enterprise.py)
- [src/tools/model_write/promote_execute.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/model_write/promote_execute.py)

Current behavior:

- entities are copied directly into the enterprise repo under their final artifact IDs
- enterprise verification is then run
- after success, engagement entities are replaced by GRFs

This means there is a transient window where the same artifact ID can exist in both engagement and enterprise roots.

### Why the current workaround is not ideal

To keep promotion working with the shared runtime index, `ModelIndex` was relaxed so that duplicate artifact IDs across mounted roots are tolerated by preserving mount order, while duplicates within a single mounted root still raise.

That logic is in:

- [src/common/model_index.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_index.py)

This is a pragmatic compatibility fix, but it weakens the core invariant of the live indexed model to accommodate one write workflow.

## Desired Invariant

The live indexed model should satisfy:

- every visible entity artifact ID is globally unique across mounted roots
- every visible connection artifact ID is globally unique across mounted roots
- every visible diagram artifact ID is globally unique across mounted roots

The runtime index should not need special duplicate-resolution semantics for promotion.

Promotion should instead ensure that all intermediate states are either:

- invisible to the index, or
- already valid under the normal uniqueness rules

## Recommended Design

### 1. Stage promotion outputs outside the visible index

Promotion should write into a staging area first, for example:

- `.arch/staging/promotion/...`
- or temporary filenames/extensions that are not scanned by the runtime index

The runtime index should only scan the normal visible roots:

- `model/**/*.md`
- `model/**/*.outgoing.md`
- `diagram-catalog/diagrams/*`

Staged files must not match those scan patterns.

### 2. Verify the staged enterprise result before commit

Promotion should build a staged enterprise candidate and verify that candidate, instead of verifying an already-mutated live enterprise tree that may still depend on live engagement cleanup steps.

Two acceptable approaches:

1. Materialize a temporary verification root containing:
   - enterprise live content
   - staged replacements/additions
   - rewritten outgoing files

2. Extend verifier/index loading with an explicit “overlay” input:
   - base visible roots
   - plus staged overrides

Approach 1 is simpler and keeps the runtime index semantics cleaner.

### 3. Commit atomically

After staged verification passes:

- move staged enterprise entity/outgoing files into final enterprise paths
- replace promoted engagement entities with GRFs
- rewrite engagement outgoing references
- regenerate macros
- refresh the shared runtime index once after commit

The commit step should minimize intermediate visible states.

### 4. Re-tighten `ModelIndex`

After promotion is staged:

- remove the cross-mounted-root duplicate tolerance from `ModelIndex`
- make duplicate artifact IDs across mounted visible roots fail again

That keeps the runtime service simple and strict.

## Concrete Refactor Plan

### A. Promotion staging

Refactor [src/tools/model_write/promote_execute.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/model_write/promote_execute.py):

1. Introduce an explicit staging model.
2. Copy/add/merge enterprise outputs into staging, not directly into live enterprise paths.
3. Rewrite outgoing files in staging.
4. Verify the staged candidate.
5. Commit on success.
6. Roll back by deleting staging only; do not need to restore live enterprise files unless commit already began.

Suggested internal modules:

- `src/tools/model_write/promotion_stage.py`
  staging paths, staged copy/write helpers, commit helpers
- `src/tools/model_write/promotion_verify.py`
  build temporary verification root from live + staged content

### B. Tighten runtime index constraints

Refactor [src/common/model_index.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_index.py):

- remove mounted-root duplicate preservation
- revert to strict duplicate detection for visible indexed content
- keep mount ordering only for non-conflicting reads

### C. Verification overlay or temp-root verification

Refactor:

- [src/common/model_verifier.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_verifier.py)
- [src/common/model_verifier_registry.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_verifier_registry.py)

Needed capability:

- verify a candidate repo state that is not yet the visible committed runtime state

Preferred implementation:

- build a temporary verification root and use ordinary `ModelRegistry` / `ModelVerifier` on that root

Reason:

- no need to complicate the shared runtime index with overlay semantics
- preserves verifier simplicity

### D. Refresh path

Keep the current watcher/refresh path for now, but after commit:

- perform one explicit shared-index refresh for affected roots

Future optimization:

- replace full refresh with staged delta application into the SQLite runtime index

That is a separate improvement and should not be coupled to the promotion correctness fix.

## Why staging is the better solution

Compared with tolerating duplicate IDs across mounted roots in the shared runtime index:

### Pros

- preserves strict live-model invariants
- keeps index semantics simple
- localizes complexity to promotion rather than leaking it into the core index
- easier to reason about verification and failure handling
- better fit for future stronger SQL constraints if uniqueness is enforced at index level

### Cons

- promotion implementation becomes more complex
- commit sequencing must be more deliberate
- staged verification root or overlay logic must be added

This tradeoff is still favorable. Promotion is the exceptional workflow; the shared runtime index is core infrastructure and should stay strict.

## Related Files

Core runtime index:

- [src/common/model_index.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_index.py)
- [src/common/model_query_repository.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_query_repository.py)
- [src/common/model_verifier_registry.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_verifier_registry.py)

Verifier:

- [src/common/model_verifier.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_verifier.py)
- [src/common/model_verifier_rules.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_verifier_rules.py)
- [src/common/model_verifier_incremental.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/common/model_verifier_incremental.py)

Promotion:

- [src/tools/model_write/promote_to_enterprise.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/model_write/promote_to_enterprise.py)
- [src/tools/model_write/promote_execute.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/model_write/promote_execute.py)
- [src/tools/model_write/global_entity_reference.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/model_write/global_entity_reference.py)

Watcher / refresh:

- [src/tools/model_mcp/watch_tools.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/model_mcp/watch_tools.py)
- [src/tools/model_mcp/context.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/model_mcp/context.py)
- [src/tools/gui_routers/state.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/gui_routers/state.py)
- [src/tools/arch_backend.py](/home/mb/workspace/scalable-architecture-for-humans-and-ai/src/tools/arch_backend.py)

## Suggested Sequence For The Next Session

1. Implement staging for promotion writes.
2. Verify staged enterprise state via a temp verification root.
3. Commit staged enterprise outputs and engagement GRF replacements atomically.
4. Reintroduce strict duplicate detection in `ModelIndex`.
5. Add regression tests that prove:
   - promotion never exposes duplicate visible IDs
   - runtime index remains strict
   - verification still passes for successful promotion
   - failed promotion leaves visible roots unchanged

## Minimum Regression Tests To Add

- promotion creates staged files that are not discovered by the runtime index before commit
- promotion commit succeeds without duplicate visible IDs across mounted roots
- shared runtime index raises on visible duplicate IDs again
- verifier passes on staged-then-committed promotion result
- rollback leaves both enterprise and engagement visible roots unchanged when staged verification fails
