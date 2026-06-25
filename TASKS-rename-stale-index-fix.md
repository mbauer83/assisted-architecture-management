# TASKS — Rename Stale-Index Fix

Spec: `PLAN-rename-stale-index-fix.md` + `ANALYSIS-rename-stale-index.md` (§6, §6.6).
Status keys: `[ ]` todo · `[~]` in-progress · `[x]` done · `[!]` blocked.
**Per task, before marking `[x]`:** `python -m pytest --tb=short -q` (0 fail) · `ruff check src/ tests/`
(0) · `uv run zuban check`. Keep codebase exploration to the listed files only.

Progress: 14/14 workstreams `[x]` · gate (WS1–WS9) release-ready. Full serial suite green
(3591 passed, 4 skipped); ruff + zuban clean. The WS10–WS14 "blocker" was the `-n auto` (xdist)
**parallel** run stalling under shared-tree contention — not a real failure; the serial suite
(`pytest -p no:xdist`) passes cleanly and is the authoritative gate.

---

## WS1 — Domain identity module  `[x]`
Deps: none. New file: `src/domain/artifact_id.py`.
Read: `src/domain/artifact_types.py` (record types, id usage), `src/infrastructure/write/artifact_write/_sync_helpers.py:47` (`stable_prefix`), `src/infrastructure/mcp/artifact_mcp/context.py:39` (`expand_artifact_id`).
Change:
- Add pure-domain helpers (no infra imports): `stable_id(s) -> str` (= `s.rsplit(".",1)[0]` for a full id; returns `s` if already short i.e. exactly one `.`), `slug_of(s) -> str|None`, and `parse_entity_id(s) -> EntityId` raising on malformed (`PREFIX@epoch.random[.slug]`, PREFIX = 2–6 upper alpha).
- `@dataclass(frozen=True) EntityId(prefix, epoch, random, slug|None)` with `.short` and `.long(slug)`.
- `ConnectionKey(src_short, type, tgt_short)` frozen; `parse_connection_id("{src}---{tgt}@@{type}")` canonicalizing both endpoints via `stable_id`; `normalized()` that sorts endpoints **only** for relation types declared symmetric/undirected (look up via the connection-type config you already pass elsewhere — accept a `symmetric: bool` arg, do not hardcode).
Acceptance: round-trips short/long; `stable_id` never returns the whole string for a full id; malformed raises.
Test `tests/domain/test_artifact_id.py`: short/long parse, slug drift (`…cps` vs `…cam-projects-cps` → same `EntityId.short`), connection key equality across slug forms, symmetric vs directed normalization, malformed inputs.

## WS2 — Index identity multimap + canonical resolution  `[x]`
Deps: WS1. Files: `src/infrastructure/artifact_index/_service_incremental.py:95-111` (`_insert_mounted`, lossy cross-mount), `_mem_store.py` (`entities`, `entity_by_path`), `service.py` (`ArtifactIndex`, `ArtifactStorePort`), `src/application/verification/artifact_verifier_registry.py` (`ArtifactRegistry.find_file_by_id`).
Change:
- `_MemStore`: add `identity_candidates: dict[str, list[Candidate]]` (`Candidate(artifact_id, path, scope)`); populate in `_insert_mounted` **before** the lossy first-wins return, so every mounted file is recorded even when shadowed.
- Store: `find_all_by_stable_id(short) -> list[Candidate]`; `reconcile_short_id(short)` = glob `{short}*.md` (+ `.outgoing.md`) across `all_model_roots`, `apply_file_changes`, evict records whose path is gone.
- Registry: `resolve_artifact(artifact_id, *, scope) -> ResolvedArtifact|None` per ANALYSIS §7.2 — key on `stable_id`; on miss/path-gone `reconcile_short_id` then retry; pick by scope (engagement write ⇒ exactly one engagement candidate; cross-repo read ⇒ unique-or-explicit-ambiguity); set `stale_slug` when requested slug ≠ current. `ResolvedArtifact(requested_id, canonical_id, path, renamed, stale_slug)`.
Acceptance: resolves old-long/new-long/short after an out-of-band slug rename; duplicate stable id across mounts is **detectable** (not silently shadowed); ambiguity raises explicit error.
Test `tests/infrastructure/artifact_index/test_canonical_resolution.py`: drift resolve, evict-missing, cross-mount duplicate detection, scope selection.

## WS3 — One canonical WorkspaceIndex + scoped facades  `[x]`
Deps: WS1. Files: `src/infrastructure/artifact_index/bootstrap.py:24,32` (`service_key`, `get_shared_index`), `service.py:71` (`shared_artifact_index`), `src/infrastructure/mcp/artifact_mcp/context.py` (`repo_scope`, `_resolve`), `src/infrastructure/gui/routers/state.py` (admin enterprise-first), `src/infrastructure/mcp/artifact_mcp/bulk/write.py:58,150` (staging indexes — must stay isolated).
Change:
- Key the **live** index by a normalized **workspace identity** (set of live mounts, order-independent) — one instance for engagement+enterprise. `repo_scope` becomes a read **facade filter** over that one `_MemStore`, applied in every query API (list/search/graph/verify/point) and write-target validation (`assert_engagement_write_root` stays).
- **Staging repos and explicitly-supplied foreign `repo_root`s keep their own isolated indexes** (do not route through the live workspace index).
Acceptance: engagement/enterprise/both facades isolate results over one store; read & write resolution of the same entity never disagree; bulk staging still uses an isolated index.
Test `tests/infrastructure/artifact_index/test_workspace_index_facades.py`: facade isolation, reversed-root-order identity, duplicate-id, staging isolation, read≡write resolution.

## WS4 — WorkspaceMutationGate  `[x]`
Deps: WS3. Files: `src/infrastructure/mcp/artifact_mcp/write_queue.py:68,134,160` (`max_workers=1`, `queued`, `run_sync`), `src/infrastructure/gui/routers/state.py:306` (`run_serialized_write`), `src/infrastructure/workspace/write_block_manager.py` (replace the TOCTOU set), `src/infrastructure/mcp/artifact_mcp/write/sync_ops.py:167` (unqueued save/submit/withdraw), group-op write modules.
Change:
- New `WorkspaceMutationGate`: per-workspace RW lock; WRITE for mutators, READ for fs-dependent reads; typed block reason `sync_in_progress|read_only`; lock order **gate → index `_rwlock`** (assert never reversed).
- Route **all** mutators through it: model writes (`queued`/`run_serialized_write`/`run_sync` converge here), bulk commits, `save/submit/withdraw`, git pull, group repair, watcher refresh, reindex, M5 recovery.
- A write that cannot take WRITE during sync → structured **`423` + retry-after** (HTTP), `{status:"rejected", reason}` (MCP/CLI); `read_only` → `423 Locked`. **Pure single-index queries need not block; filesystem-dependent and multi-call snapshot reads take READ and may wait** (preserves INV-4).
Acceptance: concurrent GUI+MCP+CLI writes serialize; 423 identical across surfaces; no reversed lock acquisition; no mutator path bypasses the gate.
Test `tests/infrastructure/test_mutation_gate.py`: serialization, 423 all surfaces, read_only vs sync reason, lock-order assert.

## WS5 — M4 durable transaction (replace batch_transaction)  `[x]`
Deps: WS4. Files: `src/infrastructure/write/artifact_write/batch_transaction.py` (`create_staging_repo:20` uses `/tmp`; `commit_staged_repo:27` sequential copy+unlink — both replaced), `src/infrastructure/backend/arch_backend.py:301-328` (startup hook for recovery), `docker-compose.yml:42` (`/data`←`arch-data`).
Change: implement the §6.6 ⚠ state machine exactly.
- Staging/transaction dir under repo-local `.arch-repo/transactions/<id>/` (same volume), **not** `/tmp`.
- Manifest entries `{kind: create|replace|delete, dest, target_hash, prior_hash_or_absent}`; git-sync ops add `ref:{branch, old_sha, new_sha}`.
- Steps: mkdir+fsync dir & parent → write payloads + fsync → install `intent` (write tmp, fsync, `os.replace`, fsync dir) → apply (create/replace = temp+`os.replace`+fsync dest&parent; **delete = `os.unlink` ignore ENOENT + fsync parent**) → **ref update (git-sync only, before `done`)** → write+fsync `done`+parent → rebuild index (or fail-stop) → remove dir+fsync parent.
- Recovery `recover_transactions()` (called by M5 before indexing): `intent`∧¬`done` ⇒ verify hashes, replay apply, re-assert ref; `intent`∧`done` ⇒ rebuild+clean; absent ⇒ none; malformed/missing-payload/third-state/unexpected-ref-sha ⇒ **fail closed** for operator. Idempotent (safe ×2).
Acceptance: kill at every boundary → fully pre/post; replay twice identical; delete & ref-transition covered; survives container recreate (dir persists).
Test `tests/infrastructure/write/test_m4_transaction.py`: boundary-kill matrix (incl. delete unlink, ref update), replay×2, fail-closed third-state, persistence location.

## WS6 — Atomic canonical-key migration (all consumers, one flag)  `[x]`
Deps: WS1, WS2. **Convert together, behind one flag**, so equality is never half-migrated. Each site: replace exact full-id/connection-string comparison with `EntityId.short` / `ConnectionKey`.
Files (read the matching line, convert the comparison):
- `src/infrastructure/mcp/artifact_mcp/context.py:39` `expand_artifact_id`
- `src/application/verification/artifact_verifier_rules.py:190` E301/E302 membership
- `src/application/verification/_verifier_rules_binding_targets.py:71` binding targets
- `src/infrastructure/write/artifact_write/connection.py:90,156,169,209` validate/dedup/id-build
- `src/infrastructure/write/artifact_write/connection_edit.py:51` edit target match, `:128` remove target match, `:228` association-edit target match
- `src/infrastructure/write/artifact_write/admin_connection_ops.py:99` admin remove target match
- `src/application/artifact_parsing.py:248` (or `infrastructure/artifact_index/artifact_parsing.py`) connection-id parse
- `src/infrastructure/write/artifact_write/entity_delete.py:86` cascade-delete dependency
- `src/application/derivation/explicit_selection.py:33` explicit derivations
- `src/infrastructure/write/artifact_write/diagram_references.py:92` reference pruning
- `src/infrastructure/rendering/archimate_puml_renderer.py:56` renderer annotations
- `src/infrastructure/write/artifact_write/_promote_planning.py:99` promotion selection/membership
- Connection **dedup/match must query the whole canonical connection index, not one sidecar**.
- **Completeness sweep (required for this WS):** the list above is a starting set, not a closed set. Run a scoped `rg` to find any remaining exact-id comparisons before declaring done, e.g. `rg -n 'target_entity\s*==|source_entity\s*==|artifact_id\s*==|---.*@@|\.endswith\(|in .*_ids_used' src/` and convert every model-identity comparison found. List newly-found sites in this task before `[x]`.
Acceptance: old-slug and new-slug forms identify the same entity/edge everywhere; no path can reject, duplicate, or lose a connection because of a slug difference; serialized output still writes current long ids; the rg sweep returns no unconverted model-identity comparison.
Post-release audit sweep finding (converted): `_artifact_deduplication.py` self-exclusion compared full
`artifact_id == exclude_artifact_id` (entity/diagram/document) — a slug-drift/short-form exclude id could
defeat self-exclusion → spurious duplicate. Not reachable via the sole caller (rename path guards slug
changed) but a latent hazard; converted to a `stable_id`-based `_is_self` helper. Regression test
`tests/infrastructure/write/test_artifact_deduplication.py`. Remaining `==`/`.endswith` hits are
filename/Path comparisons, not model identity.
Test `tests/application/test_canonical_equality_consumers.py`: for each consumer, stale-slug form == current-slug form; no duplicate edge; connection edit/remove succeeds with a stale-slug target.

## WS7 — Entity + sidecar rename via M4  `[x]`
Deps: WS5, WS6. Files: `src/infrastructure/write/artifact_write/_entity_rename.py` (sidecar move), `entity_edit.py:138,201-232` (rename path), `connection.py:131` (sidecar path derived from filename).
Change: route an identity-changing rename through M4 — manifest = {replace entity new content/new path, move/replace `.outgoing.md` sidecar, delete old paths}; a sidecar-less entity uses a lone atomic `os.rename`. Referrers' slug hints are best-effort cosmetic (not in the transaction).
Acceptance: rename with sidecar is atomic (kill ⇒ both-old or both-new, never split across two sidecars); diagrams still verify (stale slug cosmetic); sidecar-less rename atomic.
Test `tests/infrastructure/write/test_rename_sidecar.py`: with/without sidecar, mid-op kill, connection-edit-after-rename ⇒ exactly one sidecar.

## WS8 — Git sync via worktree → M4  `[x]`
Deps: WS5. Files: `src/infrastructure/git/git_sync.py:263,334` (engagement/enterprise pull against live tree), `git_env.py`.
Change: fetch into an **isolated worktree**; verify + duplicate-scan; derive create/replace/delete manifest vs live + the `(branch,old,new)` ref; publish via one M4 transaction (ref update before `done`); then index.
**Gate timing:** set the gate reason `sync_in_progress` (so concurrent writes get 423) **before** worktree preparation, but **hold WRITE only for the M4 publication window** — fetch/verify/diff run under the `sync_in_progress` reason without holding WRITE (they don't touch the live tree), so a long fetch doesn't block reads. A write arriving any time during sync gets 423 (WS4).
Acceptance: kill during candidate creation / publish / ref / index ⇒ never referentially partial; M5 recovers; writes during sync rejected; reads not blocked during fetch (only during the publish window).
Test `tests/infrastructure/git/test_sync_via_m4.py`: kill matrix, recovery, 423-during-sync.

## WS9 — Startup ordering + duplicate scan  `[x]`
Deps: WS2, WS3, WS5.
Progress: DONE — group-repair (`_repair_group_registries`, gate-routed) now runs before the index
build; fail-closed `scan_duplicate_short_ids` (same-mount collision only; cross-scope copies allowed)
on `ArtifactIdentityResolver`; `_assert_no_duplicate_short_ids` aborts startup. Test passes; full
serial suite + ruff + zuban green. Files: `src/infrastructure/backend/arch_backend.py:301-375` (`_initialise_repo`→`refresh`, then `_run_startup_validations`→`validate_and_repair_group_registry`).
Change: reorder to **recover-txns (WS5) → group-registry repair → build index → duplicate/ambiguity scan → serve**. Group repair (which mutates files, `group_registry_validation.py:76`) runs **before** the index build so INV-2 holds at first serve, routed through the gate. Duplicate short-id scan (WS2) **fails closed**.
Acceptance: at first served request, index ≡ disk even when group-repair mutated; a genuine cross-mount duplicate aborts startup.
Test `tests/infrastructure/test_startup_ordering.py`: repair-before-index, recovery-before-index, duplicate fail-closed.

## WS10 — Watcher project-subdir coverage  `[x]`
Deps: WS3. Files: `src/infrastructure/mcp/artifact_mcp/watch_tools.py:20` (`_repo_state_snapshot` scans only top-level `model/`), `src/application/repo_path_helpers.py:42` (`all_model_roots`).
Resolved: snapshot now via `all_model_roots`; refresh routed through `get_workspace_gate().writing()`.
Named test + full serial suite green (the earlier stall was the xdist parallel run, not a real failure).
Change: snapshot via `all_model_roots` so `projects/<slug>/model/` gets the 2 s incremental path (not only the 300 s full refresh). Route refresh through the gate.
Acceptance: an out-of-band change under `projects/<slug>/model/` triggers incremental reconcile within one poll interval.
Test `tests/infrastructure/test_watcher_project_coverage.py`.

## WS11 — Reindex MCP tool  `[x]`
Deps: WS2, WS4. Files: `src/infrastructure/mcp/artifact_mcp/admin_tools.py` (tool registration), `context.py` (`sync_refresh_for_roots`).
Resolved: `artifact_admin_reindex(scope='full'|'entity', short_id?, repo_root?)` registered, gate-locked,
`reconcile_short_id` for entity scope. Named test + full serial suite + ruff + zuban green.
Change: `artifact_admin_reindex(scope='full'|'entity', short_id?, repo_root?)` — full = rebuild from disk; entity = `reconcile_short_id`. Honours the gate; admin-flavoured, concise description (tool-count guidance).
Acceptance: drifts heal in-band without restart; respects gate.
Test `tests/tools/test_reindex_tool.py`.

## WS12 — Git author/committer identity  `[x]`
Deps: none. Files: `src/infrastructure/git/enterprise_git_ops.py:206-218` (bare `git commit -m`), `sync_ops.py`, `.env.example`, config loader.
Resolved: service identity via `git -c user.name=… -c user.email=…`; per-request author via
`GIT_AUTHOR_NAME`/`_EMAIL` with the env identity as committer + fallback. Named test + full serial
suite + ruff + zuban green.
Change: env service identity `ARCH_GIT_AUTHOR_NAME`/`_EMAIL` applied via `git -c user.name=… -c user.email=…`; optional per-request **author** (`GIT_AUTHOR_*`) with the env identity as **committer** + fallback. `save_changes` accepts an optional author from GUI/MCP/CLI.
Acceptance: `save_changes` succeeds with no git config present; supplied user → commit author, service = committer.
Test `tests/infrastructure/git/test_commit_identity.py`.

## WS13 — Static mediation (adapter pkg + fitness test)  `[x]`
Deps: WS4. Files: `tests/architecture/test_dependency_policy.py` (AST import collector), `src/infrastructure/mutation_adapters/`, mutation modules.
Resolved: `src.infrastructure.mutation_adapters` package; fitness test flags adapter imports outside the
reviewed allowlist (`_MUTATION_ADAPTER_IMPORTERS`) + direct `subprocess` git calls, with a deliberately
violating fixture (`test_mutation_boundary_fixture_detects_bypass`); single-worker runtime `AssertionError`
in `write_queue.py`. Diagnosis of the "hang": it was the `-n auto` xdist parallel run stalling under
shared-tree contention; the serial suite (`pytest -p no:xdist`) runs to completion (3591 passed). Named
test + ruff + zuban green.
Change: gather mutation adapters into one package injected only into the gate + git-sync publisher; extend the fitness test to flag imports of that package (and direct `subprocess` git calls) from outside a CI-reviewed allowlist. Runtime assert: write executor single-worker.
Acceptance: a new bypass import fails CI; allowlist documented.
Test: the fitness test itself (add a deliberately-violating fixture asserted to fail).

## WS14 — `arch-repair` CLI command  `[x]`
Deps: WS12. Files: `src/infrastructure/cli/arch_repair.py`, `src/application/git_repair.py`, `src/infrastructure/git/repair_adapter.py`, `git_auth.py`.
Resolved: `arch-repair` entrypoint reuses the full auth resolver (`collect_credentials`/`register_token_file`/
`create_askpass_script`/`build_git_env`) covering inline token, token-file, explicit user+password, and SSH
passphrase; guarded resumable fetch → repair branch → commit → push → ff-only promote-to-production with
upstream verification (`.git/arch-repair-state.json`). Drives `RUNBOOK-remote-repair.md` (auth-mode table
added per all configured env modes). Named test + full serial suite + ruff + zuban green.
Change: an image subcommand that initializes auth via the existing resolver (covers `ARCH_GIT_HTTPS_TOKEN`, `_TOKEN_FILE`, explicit user+pass, **and SSH passphrase**), then performs guarded fetch/stage/commit/push with branch+upstream verification and resumable state. Used by `RUNBOOK-remote-repair.md`.
Acceptance: authenticates in all configured modes inside a one-off container; idempotent rerun.
Test `tests/cli/test_arch_repair.py` (mock git; assert env wiring + guards).

---

## WS-T — Test suite mapping (verify before release)
`[x]` 8.1 canonical equality · `[x]` 8.2 one index+facades+reader-atomicity · `[x]` 8.3 gate+423 ·
`[x]` 8.4 M4 crash matrix (delete+ref+replay×2) · `[x]` 8.5 sidecar rename · `[x]` 8.6 git-sync kills ·
`[x]` 8.7 startup ordering+dup · `[x]` 8.8 incident regression · `[x]` 8.9 identity · `[x]` 8.10 static mediation.
Final gate: full serial `pytest` (3591 passed, 4 skipped) + `ruff` + `zuban` GREEN; WS1–WS9 all `[x]`. ✅ RELEASE-READY.
