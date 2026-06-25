# PLAN — Rename Stale-Index Fix (canonical identity + single index + coarse mutation gate)

Source of truth: `ANALYSIS-rename-stale-index.md` (§6 authoritative, §6.6 the consistency proof).
This PLAN is the condensed build spec; `TASKS-rename-stale-index-fix.md` is the trackable checklist.

## Goal
Make every model write **fully and consistently applied or absent** (disk ≡ index, no torn multi-file
state, no crash leaving a referentially-broken model), and make the original incident
(write-index drift after a slug rename) structurally impossible. Offline/async writes are **out of
scope**; rejecting a write during git sync with a retriable `423` is acceptable.

## Two root problems → two fixes
1. **Mutable slug treated as identity** → make the **stable short id** (`PREFIX@epoch.random`) the
   canonical identity; the slug is a readable, non-authoritative **hint** in long ids/filenames.
2. **Multiple independent caches of one repo** → **one canonical workspace index** behind scoped
   read facades; one coarse **mutation gate** serializes all mutators + writes through that index.

## Invariants the build must uphold (verbatim from §6.6)
- INV-1 every reference resolves to exactly one entity **by short id** (stale slug = cosmetic).
- INV-2 serving index ≡ working tree.
- INV-3 no two live files share a short id within a scope.
- INV-4 no reader observes a partially-applied multi-file write.
- INV-5 after recovery every durable op is fully present in disk+index or absent (indeterminate
  outcome to the caller is allowed; caller re-reads before retry — no exactly-once acks).

## Mechanisms (what to build)
- **M1** one per-workspace RW mutex (`WorkspaceMutationGate`); all mutators take WRITE, fs-dependent
  reads take READ; fixed lock order **gate → `ArtifactIndex._rwlock`**, never reversed.
- **M2** write-through: file change + index update in one WRITE section.
- **M3** rename = entity **+ its `.outgoing.md` sidecar** (path derived from filename) → via M4; a
  sidecar-less entity is a lone atomic `os.rename`.
- **M4** the single crash-correct publish primitive (durable manifest; see §6.6 ⚠ for the exact
  state machine — persistent `.arch-repo/transactions/<id>/`, hashed manifest with create/replace/
  delete + optional `(branch,old-sha,new-sha)` ref, fsync at every dir-entry transition, `done` = the
  one durable commit point, idempotent twice-safe recovery, fail-closed third state). Used by **bulk
  commits, entity+sidecar rename, AND git sync** (fetch→worktree→verify→diff manifest→M4→ref→index).
- **M5** startup order: recover-txns → group-registry repair → build index → duplicate/ambiguity scan
  (fail closed) → serve.
- **M6** short-id identity makes any un-propagated slug cosmetic.

## Hard constraints
- This is **one consistency unit**: WS1–WS9 must all land before release (the §6.6 proof assumes the
  single index + gate + M4 + atomic identity all present). WS10–WS14 are independent features that can
  land in the same release in any order.
- The identity switch (WS6) is **atomic behind one flag** — never a half-migrated equality relation.
- **No data migration**: existing long ids already embed the short id; resolution keys on the short id.
- Project doctrine: principled fix at the owning layer; `application/` may not import `infrastructure/`
  (dep-policy `tests/architecture/test_dependency_policy.py`); central clock for timestamps; every
  change ships a delegation test + a regression test. Quality gates per task:
  `python -m pytest --tb=short -q` (0 fail) → `ruff check src/ tests/` (0) → `uv run zuban check`.

## Workstreams (dependency order; detail + acceptance in TASKS file)
| WS | Title | Depends on | Core files |
|----|-------|-----------|-----------|
| 1 | Domain identity module (`EntityId`, `ConnectionKey`, parse) | — | `src/domain/artifact_id.py` (new) |
| 2 | Index identity multimap + canonical resolution | 1 | `artifact_index/`, `artifact_verifier_registry.py` |
| 3 | One canonical `WorkspaceIndex` + scoped facades | 1 | `artifact_index/bootstrap.py`, `service.py`, `context.py` |
| 4 | `WorkspaceMutationGate` (coarse RW + 423 + routing) | 3 | `write_queue.py`, `gui/.../state.py`, sync_ops, group ops |
| 5 | M4 durable transaction (replace `batch_transaction`) | 4 | `batch_transaction.py`, new recovery module |
| 6 | Atomic canonical-key migration (all consumers) | 1,2 | see TASKS WS6 list (10+ files) |
| 7 | Entity + sidecar rename via M4 | 5,6 | `_entity_rename.py`, `entity_edit.py` |
| 8 | Git sync via worktree → M4 | 5 | `git_sync.py` |
| 9 | Startup ordering + duplicate scan | 2,3,5 | `arch_backend.py` |
| 10 | Watcher project-subdir coverage | 3 | `watch_tools.py` |
| 11 | Reindex MCP tool | 2,4 | `artifact_mcp/` |
| 12 | Git author/committer identity | — | `enterprise_git_ops.py`, sync_ops, config |
| 13 | Static mediation (adapter pkg + fitness test) | 4 | new package, `test_dependency_policy.py` |
| 14 | `arch-repair` CLI command (for runbook auth) | 12 | new CLI entry; reuses `git_auth.py` |

## Test plan (maps 1:1 to invariants/mechanisms — see TASKS WS-T)
§8.1 canonical equality (entities+connections) · §8.2 one index + facades + reader atomicity ·
§8.3 gate serialize + 423 all surfaces · §8.4 M4 crash recovery at every boundary (incl. delete unlink,
ref transition, replay×2) · §8.5 entity+sidecar rename · §8.6 git-sync-via-worktree kills · §8.7
startup ordering + duplicate fail-closed · §8.8 incident regression (`repro_stale_index.py`) · §8.9
author/committer identity · §8.10 static mediation.

## Out of scope (do not build)
Durable deferred-command queue, generalized per-op OCC, fine-grained leasing, async inbox, general WAL
platform. (All serve offline/async, which is not required.)
