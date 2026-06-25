# Incident & Failure-Mode Analysis — Stale Model Index after Entity Rename

> Subject: `arch-repo` write server holds an entity under its **pre-rename** slug while
> the working tree and the read server hold the **post-rename** slug, wedging the entity
> against all edit operations and leaving dangling references in diagrams.
> Author: diagnosis session, 2026-06-25.
> Remote evidence: gathered live from the affected instance's read MCP endpoint
> (`http://10.20.20.34:8000/mcp/read`). Code evidence: this repository.

---

## 0. Brief, requirements, constraints, drivers, and facts of record

This section makes the document self-contained: it records the task, the constraints the solution
must satisfy, the design invariants it must uphold, and the facts established during diagnosis
(observed vs inferred). An independent reviewer should be able to judge goal-adequacy,
solution-optimality, and constraint-completeness from this document alone.

### 0.1 Task / goal
Diagnose, on a principled basis, an incident in which an entity rename left the `arch-repo` write
server's model index inconsistent with the working tree (and with the read server), making the
entity un-editable; then plan an architecturally sound fix and the steps to repair the affected
remote instance. The diagnosis must explain the failure mode, not just patch the symptom.

### 0.2 Investigation method & access constraints
- **No filesystem/SSH access** to the remote during diagnosis. Live evidence was gathered through a
  read-only diagnostic MCP connection configured for this purpose: `arch-repo-read-diag` =
  `npx -y mcp-remote http://10.20.20.34:8000/mcp/read --allow-http` (verified Connected). Because
  the remote tools are not bound into the running session, queries were also issued via a minimal
  streamable-HTTP JSON-RPC client. A session restart can surface the diag server's tools natively if
  needed (optional, not required for the diagnosis).
- **Behavioural-only sources are quarantined.** A prior exploratory agent produced architectural
  speculation *without* codebase access; only its *behavioural* observations are relied on. Every
  architectural claim here was re-verified against this repository's source.

### 0.3 Deliverable requirements (what this report must contain)
Observed error; minimal **and safely reproducible** conditions; principled analysis of the incident
and failure mode; root causes; options for alleviation/mitigation; the drivers / best practices that
apply; and a recommendation with reasoning plus enough implementation and testing detail to be
judged in full.

### 0.4 Design invariants the fix must uphold (stated system intent)
The system is supposed to: **(i) serialize all writes; (ii) validate all changes; (iii) trigger
automated, centralized, principled but incremental re-indexing on write.** The incident is a
violation of (iii) in spirit — re-indexing happened, but not for every in-memory view of the repo.
The fix must restore (iii) as a *total* property (every loaded view stays consistent) without
weakening (i) or (ii).

**Hard requirement — guaranteed write consistency.** A write that reports success must be **fully and
consistently applied**: disk and the serving index agree, no partial/torn multi-file state is
observable, and no crash leaves a *referentially* inconsistent or ambiguous model. This is a
correctness requirement, not best-effort. **Non-requirement:** offline or asynchronous writes are
**not** needed — so the system may **reject** a write it cannot apply consistently right now (e.g.
during a git sync) with a structured retry, and need **not** build durable deferred-command
persistence, an async inbox, or a generalized offline-OCC framework. Consistency over availability;
reject-and-retry is an acceptable way to preserve it.

### 0.5 Facts of record (established during diagnosis)
Observed (confirmed against the live system or this codebase):
- The affected entity is in the **engagement** repo, under a **project subdirectory**
  (`projects/autocam/model/application/application-component/…`). The engagement-vs-enterprise
  *scope* split is **not** the source of divergence — it only explains how two in-memory index
  instances can hold different state; the relevant divergence is between two views of the *same*
  engagement repo.
- A **background reconciler exists** (polling watcher + periodic full refresh; git-sync poller). It
  is auto-started but scoped so that it reconciles the read/`both` (and GUI) index instances and
  **not** the write/`engagement` instance (see §3.1). This corrects an earlier impression that no
  watcher existed.
- The artifact index is **in-memory only** (SQLite `mode=memory`), rebuilt from the working tree on
  process start; it is **not** persisted to any volume.
- The deployment is Docker Compose: single service **`app`**; the **container** runtime base is
  `python:3.13-slim-bookworm` (Debian, GNU userland; `git`/`ssh`/`curl` present). Repos live in the
  `arch-data` volume; credentials in `arch-home`; encrypted assurance store in `arch-assurance`.
- The **host** that runs Docker Compose has an **unknown OS/userland** — the repair runs on the host,
  so it must not assume advanced host-side CLI tools; all text processing is pushed into the
  container instead (see §9.0). The image tag is `architectonic:local`, but the project/repo is **not
  yet** renamed to "architectonic" at the git level.
- A separate **commit/push failed on the engagement repo** due to a **missing git author identity
  (only a PAT in env)**. Consequently the renamed work is **uncommitted/unpushed** local state.
- **Coordination is check-then-act, and some write paths are unqueued:** MCP model writes
  (`write_queue.queued`) **and** GUI writes (`run_serialized_write` → `is_blocked` + `run_sync`,
  `gui/routers/state.py:306`, `entities.py:267`) *both* serialize on the single-worker queue and
  *both* check the block — so GUI is **not** a wholesale bypass (an earlier draft claimed it was; that
  was wrong). The real defects are: (a) the block is **TOCTOU** (a synchronized set checked then acted
  on; `write_block_manager.py:14`), and git pulls/refreshes run **outside** the write queue, so they
  can mutate `/data` concurrently with the write worker; (b) **git persistence tools are unqueued** —
  `artifact_save_changes`/`submit`/`withdraw` call `enterprise_git_ops` directly without `queued()`
  (`sync_ops.py:167`), as do some group ops; (c) the bare `commit_engagement_work` sets no git author
  identity. The fix must replace the gate with a real mutation lease and bring **all** mutators
  (model, group, git) under it (§6.3/§7.1, §5.7).

Inferred (explicitly uncertain):
- The drifting rename was **most likely independent** of the failed commit attempt — but this is
  **not confirmed**. The analysis and fix are designed to hold regardless of which channel
  (first-party write, `git pull`, or external edit) introduced the drift.

### 0.6 Solution & deployment constraints
- **Two phases, in order:** fix the **code** first; then repair/deploy to the **remote**. No
  separate pre-fix hot restart — the index is cleared as a side effect of deploying the fixed image.
- **Remote repair is CLI-only:** performed over the shell with **no MCP and no Claude** available on
  the remote, and must be **simple**.
- **Volume safety:** never discard volumes (`docker compose down -v` / `docker volume rm`). The
  `arch-data` (repos, with uncommitted work), `arch-home` (credentials), and `arch-assurance`
  (encrypted store) volumes are irreplaceable. The in-memory index needs no volume, so a container
  recreate alone clears it.
- **Name independence:** the repo/project is **not yet** renamed to "architectonic" at the git/repo
  level even though some scaffolding presumes that name; the fix and runbook must not depend on it
  (the only occurrence is the local image tag, and Compose prefixes volume names with the project
  dir — so volume-name assumptions are forbidden; key off the service `app`).
- **Project-subdirectory safety:** the entity lives under `projects/<slug>/model/…`; all repair and
  code paths must cover project subdirectories, not just the repo's top-level `model/`.
- **Cheap, simple backup / redo:** the rename+commit can simply be redone, so the backup step must
  be trivial and recovery is low-cost.
- **Reproduction must be executed and observed**, and must leave the configured engagement/enterprise
  repos **unchanged** (done — see §2.1, run against throwaway temp repos).

### 0.7 Project-doctrine constraints (from `CLAUDE.md`, binding on the code fix)
- **Principled solution, never a workaround**; add the missing capability **at the correct layer**;
  do not route around a gap with a less-appropriate API.
- **All model writes go through tools** — never hand-edit model files in normal operation (the
  CLI `sed` repair in §9 is an explicit, one-off out-of-band recovery on a tool-less remote, called
  out as such).
- **Quality gates before commit:** `python -m pytest -q` (0 failures) → `ruff check src/ tests/`
  (0 errors, incl. E501) → `uv run zuban check`. Each fix ships a **delegation unit test** and a
  **regression test reproducing the original failure**.
- Keep MCP **tool count small** with clear descriptions; respect LoC limits (250 soft / 350 hard,
  Python); use central clock for timestamps; "arch" naming.

### 0.8 Evaluation criteria (the bar for judging this document)
Goal-adequacy (does the recommendation actually resolve the incident and its class?);
solution-optimality (is the recommended option the most principled among the alternatives, with the
trade-offs made explicit?); and constraint-completeness (are all of §0.4–§0.7 accounted for, with
nothing in the problem or its constraints left unaddressed?). §10 cross-checks the recommendation
against these constraints.

---

## 1. Observed error (confirmed, not inferred)

The affected entity is **CPS**, short-id `APP@1782278054.OPaZCl`, in the **engagement** repo
(`/data/engagement/projects/autocam/...`). It was renamed *CAM Projects (CPS)* → *CPS*, which
changed the slug `…cam-projects-cps` → `…cps` and, with it, the on-disk filename.

Two complementary write-server lookups of the *same* entity fail for *opposite* reasons —
the smoking gun:

| Call (write server) | Result | Meaning |
|---|---|---|
| `edit_entity(id="…OPaZCl.cps")` | `Entity '…cps' not found in model` | the write index does **not** know the new slug |
| `edit_entity(id="…OPaZCl.cam-projects-cps")` | `[Errno 2] No such file or directory: …cam-projects-cps.md` | the write index **does** know the old slug, but the file is gone |

I verified the *current* truth directly against the remote **read** endpoint:

- `search_artifacts("CPS")` → `artifact_id: APP@1782278054.OPaZCl.cps`, `name: CPS`,
  `path: …/APP@1782278054.OPaZCl.cps.md`. **The read index and the working tree agree on the new slug.**
- `verify(ARC@1782278684.yUXoze)` (CFCS – Application Layer, *pre-existing*) and
  `verify(ARC@1782365608.c3xIZY)` (MIRA – Application Layer, *new*) both report:
  - `E301 entity-ids-used references unknown entity 'APP@1782278054.OPaZCl.cam-projects-cps'`
  - `E302 connection-ids-used references unknown connection '…cam-projects-cps---…@@archimate-serving'` (×2)

So three views disagree about one entity:
**working tree = new**, **read index = new**, **write index = old**, **referencing diagrams = old**.

A commit/push in the engagement repo was separately reported to have failed (missing git author
identity; only a PAT in env). The rename that drifted the index was **most likely independent** of
that failed commit — but this is **not confirmed**, and the analysis below deliberately does not
depend on it either way: the fix must hold whether the drifting change arrived via a first-party
write, a `git pull`, or an external edit. (One plausible, unproven path: a rename made elsewhere
and `git pull`ed in by the sync poller, which refreshes the read/GUI view but never the write
index — see §3.1.)

---

## 2. Minimal, safe reproduction

This reproduces the *failure shape* (index drifts from the working tree, entity becomes
un-editable, referencing diagrams dangle) without needing the production data. Run against a
throwaway engagement repo.

1. Create entity `A` (slug `…a`); reference it from a diagram via its alias.
2. Rename it: `edit_entity(name="B")` → file/slug become `…b`; the *writer's* index is updated.
3. Now make the writer's index drift from disk **by any channel that does not flow through that
   exact index's `apply_file_changes`** — pick whichever is convenient to script:
   - rename the file on disk directly (simulating a git pull / external edit / another process), **or**
   - drive the rename through a *different* index instance than the one that later serves the
     lookup (e.g. a read-scope vs write-scope instance — see §3.2), **or**
   - have the post-write index-update step not run (skipped/raised) while the file write already
     landed.
4. `verify` (read view) the referencing diagram → `E301 unknown entity …a`.
5. `edit_entity("…b")` → *not found in model*; `edit_entity("…a")` → *No such file*.

Step 3 is the essential ingredient: **a disk change the long-lived index never heard about.**
The point of the analysis below is that the system makes step 3 both *easy to hit* and
*impossible to recover from in-tool* — that is the defect, independent of which channel caused it.

### 2.1 Executed verification (not just a paper repro)

The above was **run and observed** against throwaway temp repos using the real production code
(`shared_artifact_index`, `ArtifactRegistry.find_file_by_id`, `apply_file_changes`,
`notify_paths_changed`) — the configured engagement/enterprise repos were never referenced or
modified. The script: creates the entity under the old slug; loads the write index (`[engagement]`)
and read index (`[engagement, enterprise]`); renames the file out of band; reconciles **only** the
read index (mimicking the default `repo_scope="both"` watcher); then inspects both indices.

Observed output (verbatim, abridged):

```
[setup]  both indices resolve OLD slug -> …OPaZCl.cam-projects-cps.md
[event]  disk renamed: …cam-projects-cps.md -> …cps.md
[watcher] reconciled the READ (both) index only
read  .cps               -> …/…OPaZCl.cps.md
read  .cam-projects-cps  -> None
write .cps               -> None                       (=> 'not found in model')
write .cam-projects-cps  -> …/…OPaZCl.cam-projects-cps.md
   ...path exists on disk? False                       (=> '[Errno 2] No such file or directory')
[REPRODUCED] write index stale vs disk/read; entity un-editable under either id.
-- after notify_paths_changed (fan-out fix) --
write .cps               -> …/…OPaZCl.cps.md
write .cam-projects-cps  -> None
[FIX VERIFIED] write index now resolves the new slug; old slug gone.
```

**Scope of this evidence (precise claim).** This proves the *mechanism is sufficient* to produce the
exact observed state — when one index instance is reconciled and another is not, you get the precise
two-opposite-errors smoking gun — **and** that re-applying the change to the stale index heals it (the §6 fix makes this structural). It does
**not** prove the watcher was the *historical* cause on the remote: the script reconciles the read
index directly rather than running the live `_watcher_loop`, and the production channel that
introduced the drift remains *inferred* (§0.5). A stronger test (§8) runs the *actual* watcher over a
project-subdir rename and separates the mutation channels. The script currently lives in the session
scratchpad (`repro_stale_index.py`); it must be **committed as the §8 regression test** for the
"independently reviewable" claim to hold, or the claim dropped.

---

## 3. Principled analysis of the failure mode

### 3.1 Background reconciliation exists, but it heals the wrong index instance

The source of truth is the git working tree (the `*.md` files). The serving truth is an
in-memory `_MemStore` inside a per-process `ArtifactIndex`
(`src/infrastructure/artifact_index/service.py`), built lazily on first access (`_ensure_loaded`)
and thereafter mutated by `apply_file_changes(paths)`.

Contrary to a first impression, the system **does** ship a working-tree reconciler. It is a
**polling filesystem watcher** (`infrastructure/mcp/artifact_mcp/watch_tools.py`):

- `_watcher_loop` snapshots `(mtime_ns, size)` every `interval_s` (default **2.0 s**), diffs against
  the previous snapshot, and enqueues a background refresh of the changed paths — **but
  `_repo_state_snapshot` (`watch_tools.py:20`) scans only the *top-level* `model/` and
  `diagram-catalog/diagrams/`; it does not use `all_model_roots`, so it omits
  `projects/<slug>/model/`.** The affected CPS file lives under `projects/autocam/model/…`, so the
  2 s *incremental* path never sees it;
- it also forces a **periodic full refresh** every `periodic_refresh_s` (default **300 s**), which
  *does* go through `refresh()` → `scan_mount` → `all_model_roots` and therefore *does* pick up
  project-subdir changes. So the read index reconverges on the rename within ≤300 s (full refresh),
  **not** within 2 s — correcting an earlier overstatement that the watcher "observes it" promptly;
- echo-suppression (`coordination.suppress_redundant_refresh_paths`) stops it re-applying changes
  a first-party write already incorporated;
- `auto_start_default_watcher()` is started at backend boot (`backend/arch_backend_app.py:225`).

There is additionally a **git-sync poller** (`infrastructure/git/git_sync.py`, 60 s) that pulls and,
on change, calls `_on_repo_changed` → `gui_state.maybe_get_repo().refresh()`.

**The defect is the *scope* of this reconciliation, not its absence.** Every channel refreshes a
*different index instance from the one the write tools use*:

- `auto_start_default_watcher()` runs with its default **`repo_scope="both"`**
  (`watch_tools.py:170`). So it polls and calls `enqueue_background_refresh([engagement,
  enterprise], …)`, which refreshes `shared_artifact_index([engagement, enterprise])` — the
  **read** index (key `eng|ent`).
- `_on_repo_changed` refreshes `gui_state.maybe_get_repo()` — the **GUI** repo.
- The write path resolves against `shared_artifact_index([engagement])` (key `eng`) — a **separate,
  third instance** (see §3.2).

The watcher literally *observes* the engagement file change on disk (it snapshots the engagement
root), but it reconciles the `eng|ent` instance and **never the `eng` instance**. The write index
therefore has **no** background reconciliation whatsoever — not the 2 s poll, not the 300 s full
refresh, not git-sync. It is current only immediately after its own authoritative writes, and
**permanently stale** for any change that arrives by another channel, until the process restarts.

Two further reconciliation gaps compound this:

- **No reindex/reload MCP tool.** `sync_refresh_for_roots` exists in `context.py` but is not exposed
  as a tool, so there is no in-band recovery for a drifted index.
- **A fan-out primitive that is dead code.** `notify_paths_changed` (`bootstrap.py:43`) iterates
  *every* loaded index and applies changes to each index whose mount covers a path — exactly what
  would keep all instances consistent. It is **never called** (only defined and re-exported).

This — background reconciliation that covers some index instances but not the write instance — is
the core architectural defect. Everything below is either a way the drift gets introduced, or a way
the drift turns into a hard failure instead of a self-healing one.

### 3.2 Multiple index instances cover the same repository, and writes update only one of them

`shared_artifact_index(roots)` returns a **distinct singleton per root-combination**
(`bootstrap.py:service_key = "|".join(roots)`). The two MCP surfaces request different
combinations for the **same** engagement files:

- read tools default to `repo_scope="both"` → `[engagement, enterprise]` → key `eng|ent`
  (`query_*_tools.py`, `RepoScope = "both"`),
- write tools hardcode `repo_scope="engagement"` → `[engagement]` → key `eng`
  (`edit_tools.py:_resolve`).

These are two `_MemStore`s that both index the engagement entity. The authoritative write path
(`context.apply_authoritative_changes` → `_apply_paths_now`) calls
`shared_artifact_index(roots).apply_file_changes(paths)` for **one** key only and then clears
`registry_cached`. It does **not** fan the change out to the other live instances that index the
same files. (`notify_paths_changed`, which would, is the dead code from §3.1.)

This is *how two views of the same engagement entity can hold different slugs at the same time.*
It is not about enterprise vs engagement semantics — it is that **the same repo is represented by
more than one in-memory index, and a write reconciles only the writer's own copy.**

### 3.3 Slug is load-bearing identity, so a rename is a cross-cutting operation, not a field edit

The `artifact_id` embeds the slug (`PREFIX@epoch.random.slug`) **and** is the filename. A name
change therefore mutates identity, path, the entity's own `*.outgoing.md` files, the connection
ids derived from it (`…cps---…@@archimate-serving`), and every reference to all of those. The
resolver mixes two notions of identity:

- `expand_artifact_id` (`context.py:39`) treats the slug as cosmetic — but only for **short** ids
  (it expands `PREFIX@epoch.random` → full). A **full** id with a stale slug is passed through
  unchanged and then looked up verbatim.
- `find_file_by_id` (`_scope_registry.py`) is a pure dict lookup keyed by the **full** id, with no
  fallback to the stable short-id and no check against disk.

So drift in the cosmetic slug is fatal to resolution even though the stable short-id is right there.

### 3.4 `edit_entity` hard-fails on index/disk divergence instead of reconciling

`edit_entity` (`entity_edit.py:138-140`) resolves via the index and then opens the returned path:

- stale index + new full-id → `find_file_by_id` returns `None` → **"not found in model"**;
- stale index + old full-id → returns the **old** path → `parse_entity_file` opens a missing file → **"No such file"**.

The entity is editable under **no** id. A recoverable drift becomes an unrecoverable lock-out,
and tool-side self-repair is impossible. (The bug report's "Lookup-Deadlock".)

### 3.5 Verification is not single-source-of-truth

Write-side verification runs against the (stale) writer index and reports `valid: true`;
read-side verification runs against the (current) read index and reports `E301`. Two verifiers,
two answers, for the same files. This is a direct symptom of §3.2 — once the indexes converge,
the verifiers agree.

### 3.6 Rename has incomplete referential integrity

`rename_entity_identity` (`_entity_rename.py`) rewrites old-id → new-id in the entity's own
`*.outgoing.md` and in every other `*.outgoing.md` that mentions it. It does **not** rewrite
diagram sources' `entity-ids-used` / `connection-ids-used`. So referencing diagrams keep dangling
ids — precisely the pre-existing CFCS diagram's `E301`/`E302`, and any new diagram authored
against a stale index inherits the same bad ids.

### 3.7 Summary of root causes

The surface root causes (A–F) all reduce to **two underlying design problems** — fix those two and
most of the incident class disappears (this reframing supersedes the heavy machinery earlier drafts
accreted; see §6):

- **Problem 1 — mutable slugs are treated as identity.** The `artifact_id` embeds the slug and is
  the filename, and references store the full slugged id; a display-name edit therefore mutates
  identity, filenames, connection ids, and every reference. This is what makes a rename a graph-wide
  transaction (C, D, F).
- **Problem 2 — multiple caches represent the same repository independently.** Per-root-combo index
  singletons (`eng` for writes, `eng|ent` for reads), each tended by a different reconciliation
  channel. This is what lets views diverge and verifiers disagree (A, B, E).

| # | Surface root cause | Reduces to | Evidence | Severity |
|---|---|---|---|---|
| A | Background reconciliation reaches the read/GUI index instances, not the write instance | Problem 2 | §3.1 | Primary |
| B | Multiple index instances per repo; each channel tends a different one | Problem 2 | §3.2 | Primary |
| C | Slug is part of persisted identity + filename; resolver is slug-sensitive | Problem 1 | §3.3 | Primary |
| D | `edit_entity` hard-fails on index/disk divergence instead of reconciling | Problem 1 | §3.4 | Contributing |
| E | Write- and read-side verification use different indexes | Problem 2 | §3.5 | Symptom of B |
| F | Rename does not rewrite diagram references | Problem 1 | §3.6 | Contributing |

---

## 4. Drivers & best practices that apply

- **Single source of truth.** The working tree is authoritative; in-memory state is a cache.
  Caches must be derivable from, and reconcilable to, the source — never a second truth.
- **Idempotent reconciliation over event-perfect propagation.** A system that depends on *every*
  mutation reaching *every* cache exactly once is brittle. Being able to cheaply rebuild the
  correct state from disk (and doing so on doubt) is robust. (CQRS read-model rebuild; "crash-only"
  thinking.)
- **Stable identity vs cosmetic labels.** Identity should be immutable; human-facing labels should
  be free to change without breaking references. Embedding a mutable slug in the identity violates
  this.
- **Fail toward recovery, not toward lock-out.** When state is internally inconsistent, prefer a
  bounded self-heal to a hard error — especially when the hard error blocks the very tool that
  could repair it.
- **One verification authority.** Read and write verdicts on the same files must come from the same
  resolved view.
- **Referential integrity is atomic with the rename that triggers it.** Renaming an identity must
  carry all references in the same operation, or not rename at all.
- **Operability: recovery without restart.** Long-running servers need an in-band repair command.
- **Project doctrine (CLAUDE.md): principled fix at the correct layer; add the missing capability,
  do not route around it; cover each fix with a delegation unit test and a regression test that
  reproduces the original failure.**

---

## 5. Options (alleviation / mitigation), with trade-offs

### Recovery, right now (operational, no code) — to unwedge the affected instance
- **Restart the backend** → all indexes rebuild from disk → drift gone. Then repair the two diagrams'
  references (the §9 runbook). Cheap, immediate, but recurs until the code fix ships. *(Once §6.1
  lands, the stale refs are non-fatal — they resolve by short id — so even this becomes optional.)*

### 5.0–5.5 Identity & index options — settled in §6
The structural options for the two root problems — single canonical index vs. multi-index fan-out;
slug-as-identity vs. slug-as-hint; rename-as-graph-transaction vs. cosmetic refs — were weighed and
**decided in §6** (one canonical index §6.2; canonical short-id identity §6.1; coarse mutex §6.3).
The per-option trade-offs and the rejected alternatives are in §6 and §6.5; not duplicated here.

### 5.6 Harden the existing watcher
The watcher is polling (2 s) with a 300 s full refresh, and its 2 s snapshot **omits project-subdir
model roots** (`watch_tools.py:20` scans only top-level `model/` + diagram sources, not
`all_model_roots`). Fixes: (a) snapshot via centralized `all_model_roots` so `projects/<slug>/model/`
gets incremental (not just 300 s) coverage; (b) ensure coverage includes whatever index the write
path uses (automatic with the one canonical index, §6.2); (c) event-based backend (watchdog/inotify)
only if poll latency/`rglob` cost becomes a problem — not required for correctness, not the cause.

### 5.7 Git author/committer identity for app-initiated commits (independent normal-operation bug)
The app's commit path (`enterprise_git_ops.commit_engagement_work`) runs a bare `git commit -m` with
**no configured/declared identity**, so `artifact_save_changes` fails whenever git has no
`user.name`/`user.email` — which is the observed "missing author identity (PAT only)" failure, in
*normal* operation (not just this incident). `.env` supplies push **auth** (`ARCH_GIT_HTTPS_*`) but
**no author identity**, and there is no per-user plumbing (`save_changes` takes only `message`).
- **Option A — env service identity:** add `ARCH_GIT_AUTHOR_NAME`/`_EMAIL`, applied by the commit
  helpers (`git -c user.name=… -c user.email=…`) or written once via `git config` at init. Minimal;
  headless-correct; but all commits share one identity (no attribution).
- **Option B — per-user author, service committer:** propagate the GUI's authenticated user (or an
  MCP-supplied author param / client identity) as `--author`/`GIT_AUTHOR_*`, with the env service
  identity as `GIT_COMMITTER_*` and as fallback for automation. Proper audit attribution +
  headless-robust; needs identity plumbed from request → commit helper.
- **Option C — require `git config` on the host volume:** operator sets identity in `arch-home`.
  Zero code; but undiscoverable and easily forgotten (this incident).
- **Recommendation:** **B**, with **A** as the fallback path — author = acting user, committer =
  service identity from env; default to the env identity when no user context exists. This both fixes
  the failure and gives a correct multi-user audit trail. (Answers: yes, set a service identity via
  env for normal/headless operation; and yes, a GUI/MCP user *should* be able to set the author —
  today they cannot, which is the gap to close.)

---

## 6. Recommendation — fix the two root problems, minimally

**Considered and rejected (do not re-propose):** a distributed-systems control plane — fine-grained
read/write leases with a fairness scheduler, generalized optimistic-concurrency on every operation, a
durable deferred-command inbox, a rename-specific write-ahead-log platform, and a coordinator exposing
a method per operation. All of it serves offline/async semantics that are **not a requirement** (§0.4)
and is complexity creep in a **single-process, filesystem-backed** app. The architectural test —
*after fixing the two root problems (§3.7), which of those are still necessary?* — answers: none. The
plan below is the simpler, principled design. What **is** non-negotiable is
**guaranteed write consistency** (§0.4): the simpler design must — and does (§6.3) — deliver it.

### 6.1 Identity contract — stable short id is canonical; slug is a display hint (Problem 1)

Demote the slug from identity to **denormalized, validated presentation metadata**, uniformly across
**MCP, GUI, and CLI** (one shared resolution layer, not three):

- **Canonical identity = the stable short id** `PREFIX@epoch.random` (e.g. `APP@1782278054.OPaZCl`).
  Equality, lookup, and *referential integrity* key on this. It never changes on a display-name edit.
- **Persisted/serialized form = the current long id** `PREFIX@epoch.random.slug` (e.g.
  `…OPaZCl.cps`) — kept in frontmatter `artifact-id`, diagram `entity-ids-used`/`connection-ids-used`,
  and connection ids — so files, diagrams, and connection sources stay **human-readable**.
- **Tool input (MCP, GUI, CLI) accepts short *or* long ids;** all three resolve through the same
  layer to the canonical short id.
- **A stale long id (old slug) still resolves** to the canonical entity; it is **not** an error but a
  repairable **stale-slug warning** with an offered auto-fix. Two integrity levels:
  *referential* (stable id exists + unambiguous → mandatory) vs *presentation* (slug matches current
  → cosmetic, auto-reconcilable).
- **Typed canonical keys, not string prefixes.** Identity is value-typed in the domain:
  `EntityId = short id`; `ConnectionKey = (source_short_id, type, target_short_id)` (with symmetric
  normalization where the relation is undirected). A connection id today is the string
  `{src_long}---{tgt_long}@@{type}` (`connection.py:209`) compared **exactly** for dedup
  (`connection.py:169`), so a bare `stable_prefix()` is **insufficient** — both endpoints must be
  parsed and canonicalized. Endpoint matching/dedup uses the typed key; the serialized form keeps the
  current long endpoint ids for readability.
- **Rename is a *two-file* op (entity + its outgoing sidecar), not single-file.** The sidecar path is
  derived from the entity filename — `source_file.with_suffix(".outgoing.md")` (`connection.py:131`) —
  so renaming only the entity orphans the old sidecar and a later write would resolve a *new* sidecar,
  **splitting one entity's connections across two files**. Therefore an entity rename moves the entity
  **and** its sidecar together, through the crash-correct multi-file commit protocol (§6.6 M4). A
  sidecar-less entity is the only true single-file `os.rename` case. (Referrers' slug hints remain
  best-effort/cosmetic.)
- **No *data* migration, but a coordinated *code* migration.** No artifact files need rewriting — every
  long id already embeds its short id, so existing references resolve once the code keys on the short
  id (the incident's dangling CPS refs become **non-fatal**; the §9 `sed` becomes optional cosmetic
  cleanup). But the runtime identity schema and **every exact-match consumer** must be migrated
  together: `expand_artifact_id` (`context.py:39`), connection validation/dedup (`connection.py:90,156,169`),
  connection-id construction/parsing (`connection.py:209`, `artifact_parsing.py:248`), promotion
  selection/endpoint membership (`_promote_planning.py:99`), verification (E301/E302), diagram
  bindings, and association annotations — all routed through **one** application resolver shared by
  MCP, GUI, and CLI. (Optional idempotent cosmetic "refresh slug hints" pass for readable diffs.)

This dissolves root causes C, D, F and the "rename is a graph transaction" premise — and with it the
need for a rename WAL and generalized OCC — but it is a real, coordinated code change, not a one-liner.

### 6.2 One canonical live-workspace index (Problem 2)

One `ArtifactIndex` per live workspace behind engagement/enterprise/both **scoped read facades**;
staging/foreign-root indexes stay isolated. One generation, one source of serving truth → no
fan-out, no cross-index publication, no verifier disagreement (A, B, E). **This must ship *with* the
mutex as one unit, not be deferred** — the §6.6 proof and §6.3's "pure index queries need no lock"
both assume a single canonical index; deferring it while Phase 1 keeps per-root-combo fan-out would
mean the incident release does **not** satisfy its own consistency proof (a reader could still observe
two generations mid-fan-out). So §6.2 is part of the incident-release consistency unit (§6.4).

### 6.3 One coarse repository mutation mutex — how write consistency is *guaranteed* (§0.4)

Writes are infrequent, so prefer **correctness over fine-grained concurrency**. A single coarse
**read/write mutex** per workspace makes the consistency guarantee simple and provable:

- **Serialize all mutation** — model writes, git pulls, commits, reindex all take the **write** side;
  no two mutators ever run concurrently (kills the original TOCTOU/divergence without a scheduler).
- **One crash-correct publish primitive (M4) for *every* multi-file working-tree mutation — including
  git sync.** A `git pull` does **not** mutate the live tree directly (today it does —
  `git_sync.py:263,334` — and a kill leaves a partial tree that breaks INV-1/4); it fetches into an
  isolated worktree, is verified there, and its diff vs live is published through the same M4 manifest
  (§6.6 ⚠). This is the single primitive the whole guarantee rests on.
- **Write-through to the one canonical index inside the same critical section** — disk and index are
  updated together under the mutex, so they can never diverge (the original incident is structurally
  impossible). On restart the in-memory index rebuilds from disk, so disk stays authoritative.
- **No torn reads** — filesystem-dependent reads (verification, file-resolution) take the **read**
  side; pure index queries are consistent because the index only changes under the write side. One
  index = one generation, so no reader sees a half-applied multi-file change.
- **Crash-atomic writes** — a *single-file* edit/rename is `write-then-atomic-os.replace/os.rename`
  (§6.1): a crash leaves the old or the new file, never both/neither; any un-propagated slug hint is
  *cosmetic*. *Multi-file* commits (bulk creates, rename + outgoing/diagram hints) need slightly more,
  because a hard kill between files could leave a new entity referencing a not-yet-written one
  (INV-1). The minimum that still avoids a general WAL: a single durable **commit marker** + **idempotent
  roll-forward from a persistent repo-local transaction dir** (`.arch-repo/transactions/<id>/`, not
  `/tmp`) with a hashed manifest (see §6.6 ⚠ for the exact protocol).
  Backup/rollback covers in-process exceptions; the marker covers hard kill. This is the irreducible
  cost of guaranteed consistency for multi-file commits — and far smaller than a per-file undo-WAL.
- **Reject, don't defer** — a write that cannot take the mutex now (git sync in progress) returns a
  structured **retriable** response (`423` + retry-after); it is **never** reported as committed
  unless disk+index are consistently updated. Since offline/async is out of scope (§0.4), there is
  **no** deferred-command persistence, async inbox, or generalized OCC.

This is the whole concurrency design — no lease scheduler, no generalized OCC, no deferred-op state
machine.

### 6.4 Phasing

1. **Incident release = ONE consistency unit (ships together).** Per the §6.6 proof, these are
   inseparable: **(a)** the single canonical workspace index + scoped read facades (§6.2), staging
   isolated; **(b)** the coarse RW mutex via a small **WorkspaceMutationGate** with the fixed lock order
   *workspace-lock → index `_rwlock`*, routing model writes, bulk commits, `save/submit/withdraw`,
   pull, group repair, **watcher refresh/reindex**, and recovery (§6.3); **(c)** the **complete,
   atomic canonical-identity switch** — typed `EntityId` **and** `ConnectionKey`, flipped behind one
   flag so equality is never half-migrated: every exact-match consumer converts together (resolver
   §7.2; verification E301/E302 `artifact_verifier_rules.py:190`; bindings
   `_verifier_rules_binding_targets.py:71`; connection dedup/validation/id-build `connection.py:156`,
   `artifact_parsing.py`; **connection edit/remove target matching `connection_edit.py:51`** and
   **admin connection ops `admin_connection_ops.py:99`** (both compare slug-bearing `target_entity`
   exactly today → a stale-slug target would silently fail to match); cascade-delete
   `entity_delete.py:86`; explicit derivations `explicit_selection.py:33`; reference pruning
   `diagram_references.py:92`; renderer annotations `archimate_puml_renderer.py:56`; promotion
   `_promote_planning.py:99`; **dedup/match query the whole canonical connection index, not one
   sidecar**); **(d)** the M4 **durable transaction** for every
   multi-file op — including **entity + outgoing-sidecar rename** and **git pull via worktree**
   (§6.6 M4); **(e)** startup order recover-txns → group-repair → build-index → duplicate-scan (fail
   closed) → serve (§6.6 M5); **(f)** reindex command (§7.3); **(g)** safe quiesced runbook (§9);
   **(h)** git author/committer identity (§5.7); **(i)** watcher project-subdir coverage (§5.6).
   (No fan-out, no half-migrated identity epoch: one index, one equality relation.)
2. **Cleanup/strategic:** scoped-facade polish, duplicate-id diagnostics, render-label refinements,
   optional cosmetic "refresh slug hints" pass. **No data migration** (long ids already embed the
   short id).
3. **Dropped (not merely deferred):** offline/async is **not a requirement** (§0.4), so durable
   deferred-command persistence, async inbox, generalized per-op OCC, fine-grained leasing, and a
   general WAL platform are **out of scope** — §6.3 already *guarantees* write consistency. Revisit
   only if a genuine offline/async product requirement appears later.

### 6.5 What the two fixes dissolve, and what still needs doing

- **Dissolved by §6.1/§6.2/§6.3:** the fine-grained read/write lease + fairness scheduler (→ one
  coarse mutex), cross-index reader atomicity (→ one index = one generation), the deferred-op
  at-most-once/inbox problem (offline/async out of scope; reject-and-retry preserves consistency), and
  the graph-wide rename transaction (rename is `write-then-atomic-rename`, or entity+sidecar via M4).
  Write **consistency is still guaranteed** (§0.4/§6.3) — the simplification removes machinery, not the
  guarantee.
- **Retained (still real under the simpler design):** the **runbook quiesce/auth** fix — stop the
  service **before** backup, and set up an askpass in the one-off container so push authenticates
  (§9); **canonical-id duplicate detection** via a scan-time identity multimap, since making the short
  id canonical requires detecting exact cross-mount shadowing (`_insert_mounted` is lossy at
  `_service_incremental.py:101`); and the **startup-mutation boundary** — group-registry repair runs
  **before** the index build (§6.6 M5), routed through the mutation gate.

### 6.6 Consistency guarantee — invariants, interleavings, and crash analysis (auditable)

This section discharges the §0.4 hard requirement by construction. Single-file edits are atomic via
`os.replace`/`os.rename`; multi-file ops (bulk, entity+sidecar rename, git sync) need the small
durable transaction in M4 — the irreducible cost, far short of a general WAL platform.

**Invariants (the definition of "consistent"):**
- **INV-1 Referential:** every reference (`entity-ids-used`, `connection-ids-used`, connection
  endpoints) resolves to **exactly one** canonical entity **by short id**. A slug that differs from the
  entity's current slug is *allowed* (cosmetic), not a violation.
- **INV-2 Index≡disk:** the serving index agrees with the working tree on the short-id→path map.
- **INV-3 Unambiguous:** no two *live* files share a short id within a scope.
- **INV-4 Atomic visibility:** no reader observes a partially-applied multi-file write.
- **INV-5 Durability (not acknowledgment):** after recovery, every durable operation is **either fully
  reflected in both disk and the rebuilt index, or absent** (modulo cosmetic slug staleness). A caller
  may receive an **indeterminate** outcome after a process/connection failure and must **re-read before
  retrying** — §0.4 requires consistency of successful writes, *not* exactly-once response semantics
  (which would need durable acknowledgment machinery — out of scope, §0.4).

**Mechanisms:** M1 one per-workspace **RW mutex** via a small `WorkspaceMutationGate` (all mutators
take WRITE; fs-dependent reads take READ; fixed lock order **workspace-lock → index `_rwlock`**);
M2 **write-through** (file change + index update in one WRITE section); M3 rename = **multi-file** op
via M4 (entity **+ its `.outgoing.md` sidecar**, whose path derives from the filename —
`connection.py:131`; a sidecar-less entity reduces to `write-into-old → atomic os.rename`); M4
multi-file = **staged-verify + durable transaction manifest + idempotent recovery** (see ⚠); M5 startup
= **recover transactions → group-registry repair → build index from disk → duplicate/ambiguity scan →
serve** (repair *before* the build so INV-2 holds); M6 **short-id identity** makes any un-propagated
slug a cosmetic hint, never a referential break.

**Interleavings** (two actors at once), under M1:

| A \ B | model write | git pull | reindex | fs-read (verify) | index query |
|---|---|---|---|---|---|
| **mutator** | serialized (WRITE) | serialized | serialized | reader waits → sees pre/post | consistent (index only changes under WRITE; multi-entity snapshot takes READ) |

No two mutators ever overlap → the original TOCTOU/divergence is impossible **without** a scheduler.

**Crash analysis** (process killed at the worst moment of each operation):

| Op | Crash point | On-disk result | INV | Recovery |
|---|---|---|---|---|
| Field edit (sidecar-less) | before `os.replace` | unchanged | ok | none (no-op; not committed) |
| Field edit (sidecar-less) | after `os.replace`, before index update | disk new, index old | INV-2 transient | M5 rebuild |
| Rename / any op with a sidecar | any crash | governed by the M4 manifest (below) | INV-1 holds | M5 roll-forward/back |
| Reindex | mid-rebuild | disk unchanged | ok | M5 rebuild |
| **Git pull** | mid-checkout/rebase | **partial tree (INV-1/4 not satisfied by git alone)** | **published via M4** | prepared in a worktree, published as a manifest (below) → M5 recovers like any commit |
| **Multi-file commit (no marker)** | mid copy of N files | k of N applied → a new entity may reference a not-yet-copied one | **INV-1 VIOLATED** | ⚠ M4 (below) makes this recoverable |

⚠ **M4 — the single crash-correct publish primitive (an executable state machine, not prose).**
*Every* multi-file working-tree mutation — bulk commits, entity+sidecar rename, **and git
synchronization** — publishes through M4. (Git ref updates are atomic but a working-tree
checkout/rebase is **not** a multi-file transaction; a killed `git pull` against the live tree
— `git_sync.py:263,334` — leaves a partial tree that index-rebuild merely *reflects*, not repairs.
So git sync fetches into an **isolated worktree**, verifies + duplicate-scans it, derives a
create/replace/delete manifest vs live **plus the branch-ref transition**, and publishes all of it
through one M4 transaction — the ref update is a manifest step, not an unrecoverable action after
`done`.) Location: a **persistent repo-local** dir on the same volume —
`.arch-repo/transactions/<id>/` (all repos live under `/data` ⇐ `arch-data`, `docker-compose.yml:42`;
**not** `/tmp`, which `batch_transaction.py:21` uses today and is lost on recreate).

State machine (fsync at every directory-entry transition; `done` is the single durable commit point):
1. `mkdir` + **fsync** `transactions/<id>/`, then **fsync** `transactions/`.
2. For each change, write payload + **fsync** the payload and its dir. Manifest entry =
   `kind ∈ {create, replace, delete}`, dest, target hash, **expected-prior** hash-or-absence.
   For a **git-sync** op the manifest also records `ref` = `(branch, expected-old-sha, new-sha)` so the
   branch-ref transition is part of the same durable transaction (not an unrecoverable step after it).
3. Write `intent.tmp`, **fsync it**, `os.replace(intent.tmp → intent)`, **fsync** `transactions/<id>/`.
4. Apply each manifest entry (idempotent + fail-closed):
   - `create`/`replace`: write a same-filesystem temp + `os.replace(temp → dest)`; **fsync** dest and
     its parent dir.
   - `delete`: `os.unlink(dest)` ignoring `ENOENT` (idempotent), then **fsync** the parent dir.
   Replay predicate per kind:
   - `create`: dest absent **or** already == target hash; else **abort for operator**.
   - `replace`: dest == prior **or** == target; else abort.
   - `delete`: dest == prior **or** already absent; else abort.
   A dest matching **neither** prior nor target is the "third state" → **abort startup, never
   overwrite**.
5. **(git-sync only)** update the branch ref to `new-sha` (idempotent: skip if already there); this is
   inside the transaction, *before* `done`.
6. Write+**fsync** `done`, **fsync** parent.
7. Rebuild the index **before** cleanup/serving; if index publication fails, rebuild under the gate
   **or fail-stop** — never release WRITE with a stale serving index.
8. remove `transactions/<id>/`, **fsync** parent.
**M5 recovery (before indexing/serving):** `intent`∧¬`done` ⇒ verify payload hashes, replay step 4,
then re-assert the `ref` transition (step 5) if present — safe to run **twice**; `intent`∧`done`
(crash between `done` and cleanup) ⇒ ref already correct, just rebuild + clean up; `intent` absent ⇒
nothing pending; malformed marker / missing payload / third-state / ref at an unexpected third sha ⇒
fail-closed for operator. Only **sidecar-less single-file edits** skip M4 (their `os.replace` is
atomic).

**Why the incident itself cannot recur:** M2 makes index≡disk by construction (INV-2); M6 makes the
stale-slug references resolve (INV-1) so the wedged-entity lock-out and the diagram E301/E302 become
cosmetic; M1 removes the cross-actor races; M5 rebuilds a correct index on every start.

---

## 7. Implementation detail (for review)

> **Scope note.** §6 is authoritative; this section is the implementation detail under it. The
> incident release is: §7.0/§7.1 one canonical workspace index + `WorkspaceMutationGate`; §6.6 M4 the
> single crash-correct publish primitive (bulk, entity+sidecar rename, git-pull-via-worktree); §7.2
> canonical-id resolution; §5.6 watcher project-subdir coverage; §7.3 reindex; §7.4 static mediation;
> §5.7 identity; §9 runbook; and the atomic identity migration (§6.4 phase 1).

All file paths are under `src/`. Each change is at the layer that owns the capability, per project
doctrine, and each ships with a delegation unit test plus a regression test reproducing the
original failure.

### 7.0 One canonical workspace index + scoped facades (implementation design)

This replaces the prior "deferred to an ADR / fan-out interim / do not implement" text — that
contradicted authoritative §6.2. The incident release builds exactly one live index; there is no
fan-out and no `notify_paths_changed` multi-index reconciliation.

- **Workspace identity, not ordered-root strings.** Replace per-root-combo keying
  (`bootstrap.py:24` `service_key = "|".join(roots)`) with a single `WorkspaceIndex` constructed over
  the live engagement + enterprise mounts, keyed by a normalized **workspace identity** (set of
  mounts, order-independent). `shared_artifact_index(...)` returns this one instance for any live-scope
  request; **staging repos and explicitly-supplied foreign `repo_root`s get their own isolated indexes**
  (bulk transactions rely on that — `bulk/write.py:58,150`).
- **Scope is a facade filter, not a separate store.** `repo_scope=engagement|enterprise|both` is a
  thin read facade over the one `_MemStore`, applied at **every** query API
  (list/search/graph/verify/point) and at write-target validation (`assert_engagement_write_root`
  stays). Admin's enterprise-first ordering (`state.py`) becomes a facade ordering, not a different
  index.
- **All index mutation goes through the gate (§6.3).** `apply_file_changes`/`refresh` are invoked
  only under the workspace WRITE side (lock order **workspace-lock → `ArtifactIndex._rwlock`**, never
  reversed). The watcher's `_refresh_worker` (`context.py:323`), explicit reindex, M5 recovery, and
  every disk/git mutator route through `WorkspaceMutationGate`; the index never mutates on a path that
  did not hold the gate. **If a disk mutation succeeds but the index update fails, rebuild under the
  gate or fail-stop — never release WRITE with a stale serving index.**
- **One generation.** Because there is a single index, INV-2/INV-4 hold by construction; multi-call
  logical read requests that must be consistent take the workspace READ side for their duration.

### 7.1 The mutation gate (`WorkspaceMutationGate`)

A small application-level gate — not a per-operation god-coordinator (its contract is only:
read/write exclusion, sync-state rejection, lock-order enforcement, M4 publish). Every mutator
acquires it: model writes, bulk commits, `save/submit/withdraw`, git pull (worktree→M4), group repair,
watcher refresh, explicit reindex, and M5 recovery. A write that cannot take WRITE during a sync
returns `423` + retry-after (§6.3). Statically enforced per §7.4 (mutation-adapter package + reviewed
allowlist + fitness test).

### 7.2 Self-healing resolution by short-id — index + registry

Add a bounded reconcile to the index (the layer that owns the working-tree↔memory mapping), and a
resolve-or-reconcile to the registry. **Do not** add ad-hoc disk pokes in `edit_entity`.

`infrastructure/artifact_index/service.py` (and its `ArtifactStorePort`):

```python
def reconcile_short_id(self, short_id: str) -> None:
    """Re-derive index entries for *short_id* from the working tree (bounded self-heal).

    short_id is PREFIX@epoch.random — stable across slug renames. Globs the model roots for
    files named '{short_id}*.md' (and their .outgoing.md) and applies them, so a slug/filename
    drift the index missed is corrected from the source of truth.
    """
    paths: list[Path] = []
    for mount in self.repo_mounts:
        for mroot in all_model_roots(mount.root):
            paths += mroot.rglob(f"{short_id}*.md")
    self.apply_file_changes([p for p in paths])
    # also drop stale entries whose recorded path no longer exists:
    self._evict_missing_for_short_id(short_id)
```

**Canonicalization, not just resolution (corrects an unsafe earlier sketch).** Resolving an
*old* full id to the *new* file is not enough: `_resolve_target_identity` keeps the caller's id for
non-name edits (`entity_edit.py:44`) and `_render_entity` writes that id into the file
(`entity_edit.py:83`) — so silently resolving a stale full id would **regress the identity** (write
the old slug back into the renamed file) and desync filename↔frontmatter. Resolution must therefore
return the **canonical** id and all mutators must use it; a stale full id is either canonicalized or
rejected, never carried through. **Two separate concerns — keep them in the right layer:**
- *Syntax* (domain): move ID parsing into a **domain identifier module** — a typed parser exposing
  `canonical_full_id`, `stable_id` (= `rsplit(".",1)[0]`), `slug`, rejecting **malformed** ids — since
  `application/` may not import `infrastructure/`'s `stable_prefix` (dep policy
  `application → {domain, application}`, `test_dependency_policy.py:43`). Repoint `_sync_helpers`,
  `expand_artifact_id`, connection-id parsing, resolver, and tests at it. (Never `split(".", 0)`.)
- *Ambiguity* (index/registry, **not** the parser): a domain parser cannot know whether two files or
  mounts share a stable id — that needs repository context. Today `_insert_mounted` can silently
  retain the first cross-mount record (`_service_incremental.py:95`). So add
  **`find_all_by_stable_id() → [(artifact_id, path, scope)]`** on the store, and have resolution apply
  **scope-aware** rules: an engagement write requires **exactly one** engagement candidate; a
  cross-repo read requires global uniqueness or returns an explicit **ambiguity** result (never a
  silent shadow). Add startup diagnostics for same-project / cross-project / engagement-vs-enterprise
  duplicate stable-ids.

`application/verification/artifact_verifier_registry.py` (`ArtifactRegistry`):

```python
@dataclass(frozen=True)
class ResolvedArtifact:
    requested_id: str
    canonical_id: str   # the id as it exists on disk now (slug may differ from requested)
    path: Path
    renamed: bool       # True if canonical_id != requested_id

def resolve_artifact(self, artifact_id: str, *, scope: Scope) -> ResolvedArtifact | None:
    """Self-healing, canonicalizing resolution against working-tree drift (§6.1 contract).

    Equality/lookup key on the stable short id; the slug is a display hint. On a miss or a
    recorded-path-that-is-gone, reconcile that short-id from disk and retry once. Returns the
    CANONICAL id/path, with `stale_slug` set when the requested long-id slug != the current one.
    Ambiguity is resolved by the scope-aware multimap, not the parser.
    """
    from src.domain.artifact_id import stable_id, slug_of   # domain identifier module
    short = stable_id(artifact_id)
    cands = self._store.find_all_by_stable_id(short)         # scope-aware multimap (not lossy entities)
    if not cands or all(not c.path.exists() for c in cands):
        self._store.reconcile_short_id(short)               # under the coarse mutation mutex (§6.3)
        cands = self._store.find_all_by_stable_id(short)
    rec = pick_for_scope(cands, scope)                       # engagement write ⇒ exactly one eng candidate;
    if rec is None:                                          # cross-repo read ⇒ unique-or-explicit-ambiguity
        return None
    stale = slug_of(artifact_id) not in (None, slug_of(rec.artifact_id))
    return ResolvedArtifact(artifact_id, rec.artifact_id, rec.path,
                            renamed=rec.artifact_id != artifact_id, stale_slug=stale)
```

This one resolver is the shared layer behind **all** surfaces (§6.1): MCP tools, GUI routers, and CLI
all canonicalize input through it; `stale_slug=True` becomes a warning + offered auto-fix everywhere,
never a hard error.

`infrastructure/write/artifact_write/entity_edit.py:138` resolves, then **uses the canonical id**
for all downstream identity/render logic (never the caller's stale id):

```python
resolved = registry.resolve_artifact(artifact_id)
if resolved is None:
    raise ValueError(f"Entity '{artifact_id}' not found in model")
artifact_id = resolved.canonical_id          # canonicalize before _resolve_target_identity/_render
entity_file = resolved.path
```

Apply the same canonicalizing resolution to the other write ops that resolve by id
(`promote_entity`, `edit_connection`, `remove_connection`, `delete_entity`) so the whole write
surface is drift-resilient *and* identity-safe. `find_by_id_or_short_id` / `reconcile_short_id` are
the principled missing delegations on the store (short-id is the stable key) — add them there rather
than globbing the disk in callers.

### 7.3 Reindex/reload MCP tool — `infrastructure/mcp/artifact_mcp/`

Expose recovery in-band. Prefer one small admin tool with a mode rather than several:

```python
def artifact_admin_reindex(*, scope: str = "drifted", short_id: str | None = None,
                           repo_root: str | None = None) -> dict[str, object]:
    """Recover from index/working-tree drift without a restart.
    scope='entity'   + short_id → targeted reconcile_short_id across all loaded indexes
    scope='full'                → sync_refresh_for_roots for the resolved roots (rescan from disk)
    """
```

`scope='full'` calls the already-present `sync_refresh_for_roots`; the entity scope calls
`reconcile_short_id` via `notify_paths_changed` semantics so all loaded indexes heal. Annotate as
a local-write/admin tool with a precise description (mind the tool-count guidance).

### 7.4 Static mediation — one enforced mutation path

All mutators route through the `WorkspaceMutationGate` (§6.3/§7.1). To make that structural, not a
convention — without overclaiming "impossible" (any Python module can construct `Path`/`subprocess`):

- **Mutation-adapter package:** move every repository-mutation adapter (`artifact_write` mutators,
  `enterprise_git_ops`, group-op writers, `batch_transaction` commit) into one package whose mutate
  APIs are injected *only* into the gate and the git-sync worktree publisher; other code receives
  read/resolve capabilities only.
- **Architecture fitness test:** extend `tests/architecture/test_dependency_policy.py` to flag imports
  of the mutation-adapter package — and direct `subprocess` git calls — from any module outside a
  small CI-reviewed allowlist (gate + git-sync). Raw `pathlib`/`shutil`/`os` writes are not reliably
  decidable by the import collector, so rely on the package boundary + allowlist, not a blanket AST
  rule. Plus a runtime assert that the write executor is single-worker (§8.10).

---

## 8. Testing (so the fix can be judged in full)

Per project doctrine, every fix gets a **delegation/behaviour unit test** and a **regression test
reproducing the original failure**. Quality gates: `pytest`, `ruff check`, `uv run zuban check`. This
suite is **rewritten for the v6 consistency unit** — the prior fan-out/lease/OCC/deferred tests are
withdrawn (those mechanisms are out of scope, §6). Each test maps to an invariant (INV-1..5) or
mechanism (M1..M6); all run against throwaway temp repos and leave configured repos untouched.

### 8.1 Canonical identity equality (INV-1, INV-3 / M6) — entities **and** connections
- An entity resolves identically from its **old-long**, **current-long**, and **short** id; a non-name
  edit issued with the *stale* long id writes the **current** long id into the file (no identity
  regression, no filename↔frontmatter mismatch).
- A connection resolves/dedups by `ConnectionKey=(src_short,type,tgt_short)`: old-slug and new-slug
  endpoint forms identify the **same** edge and cannot create a duplicate; symmetric relations
  normalize endpoint order for equality while persisting source orientation. Cover every converted
  consumer (verification E301/E302, bindings, cascade-delete, derivations, pruning, render
  annotations, promotion) — each treats old/new slug forms as equal.

### 8.2 One canonical index + scoped facades (INV-2, INV-4 / M1, M2)
- Engagement/enterprise/both facades isolate results over a **single** `_MemStore`; admin
  enterprise-first ordering is a facade, not a second index. Staging/foreign-root indexes stay
  isolated. Assert read and write resolution of the same entity never disagree (the incident's E
  symptom).
- **Reader atomicity:** a continuously-running logical read (taking workspace READ) observes only the
  pre- or post-commit graph across a multi-file publish, never a mixed graph.

### 8.3 Gate serialization + 423 reject, all surfaces (M1 / §6.3)
- Concurrent GUI + MCP + CLI writes serialize through `WorkspaceMutationGate`; lock order
  workspace→`_rwlock` enforced (a reversed acquisition is statically/architecturally rejected).
- During a simulated sync (gate held by pull), a write on **each** of HTTP/MCP/CLI returns the same
  retriable `423`/sync-busy outcome; a `read_only` policy block returns `423 Locked`. Pure single-index
  queries are not blocked; a filesystem-dependent/snapshot read taking READ **may wait** during the M4
  publish window (INV-4) — assert it observes only the pre- or post-publish graph.

### 8.4 M4 durable transaction — crash recovery at every boundary (INV-1/INV-5 / M4, M5)
- For **create/replace/delete** manifests, kill the process after each durability boundary (payload
  fsync, `intent` install, each dest `os.replace`/`unlink`, parent-dir fsync, **ref update**, `done`,
  cleanup) and assert M5 recovery yields a fully-pre or fully-post state; **replay recovery twice** →
  identical result. Include a `delete` entry (idempotent `unlink`+parent fsync) and a git-sync op whose
  manifest carries the `(branch, old-sha, new-sha)` ref transition.
- Fail-closed cases: malformed/torn marker, missing payload, and a destination matching **neither**
  prior nor target hash → startup aborts for operator, never overwrites.
- Persistence: the transaction dir is `.arch-repo/transactions/` (same volume), **survives a
  container recreate**; a `/tmp` location is rejected by the test.

### 8.5 Entity + outgoing-sidecar rename (M3 via M4)
- Rename an entity **with** an `.outgoing.md` sidecar; assert entity and sidecar move atomically (a
  mid-op kill leaves both-old or both-new — never connections split across two sidecars), the
  referenced diagrams verify clean, and referrers' stale slug hints are *cosmetic* (warning, resolves).
- Rename a **sidecar-less** entity; assert the lone `os.rename` path (no manifest) still atomic.

### 8.6 Git sync via worktree → M4 (INV-1/INV-4 / M4)
- Kill the process during candidate-worktree creation, during M4 publish of the pull diff, during the
  branch-ref update, and during the index update; assert the live tree is never left referentially
  partial and M5 recovers. Assert a write attempted during sync gets `423` (M1).

### 8.7 Startup ordering & duplicate scan (M5)
- Assert startup runs **recover-txns → group-registry repair → build index → duplicate/ambiguity scan
  → serve**; a group-repair that mutates files does so **before** the build (INV-2 holds at first
  serve). A genuine duplicate short id (exact cross-mount shadow, `_insert_mounted` lossy at
  `_service_incremental.py:101`) makes the scan **fail closed**, not silently shadow.

### 8.8 The exact incident, reproduced via real components (regression)
- Commit `repro_stale_index.py`. Assert the pre-fix smoking gun (`new_id` → "not found",
  `old_id` → "No such file") and that under the v6 build the entity resolves via short id (lock-out
  gone) and the diagrams' stale refs are non-fatal/auto-fixable.

### 8.9 Git author/committer identity (§5.7)
- With no git identity configured, `save_changes` succeeds using the env service identity; a supplied
  GUI/MCP/CLI user appears as commit **author** while committer is the service identity. Regression
  for the observed "missing author identity" failure.

### 8.10 Static mediation (M1 / §7.4)
- Architecture fitness test: no module outside the CI-reviewed allowlist (gate + git-sync) imports the
  **mutation-adapter package** (`artifact_write` mutators, `enterprise_git_ops`, group-op writers,
  `batch_transaction` commit) or makes direct `subprocess` git calls. Runtime assert: the write
  executor is single-worker and all surfaces route through the gate.

---

## 9. Repairing the affected remote instance — CLI-only runbook

**Constraints that shape this runbook:** the remote repair is performed **over the CLI only** —
no MCP tools, no Claude. So every step is `ssh` + `git` + `docker compose` + `sed`/`grep`; nothing
relies on `artifact_edit_*` or `artifact_verify`. And the code is fixed **first**, then deployed
**once** — there is no separate pre-fix hot restart.

Two facts decide the mechanics:

- **The artifact index is in-memory only** (`_sqlite_store.py`: `file:…?mode=memory&cache=shared`) —
  never persisted; rebuilt from the `/data` working tree every time the process starts. So
  recreating the container *is* the index repair; **no volume needs discarding.**
- **The `arch-data` volume holds the cloned engagement/enterprise repos**, and the rename + diagram
  work there was **never committed/pushed** (the commit failed — PAT only, no author identity). So
  `arch-data` (plus `arch-home` = credentials, `arch-assurance` = encrypted store) is irreplaceable.

> ⚠️ **Never `docker compose down -v` or `docker volume rm arch-data`.** That destroys the
> uncommitted rename/diagram work and the credential/assurance state. "Rebuild" = rebuild the
> *image* / recreate the *container*, never wipe a data volume.

### 9.0 Required CLI tools — host vs container

**Important distinction.** The runbook is executed **on the host** that runs Docker Compose, and we
**do not know that host's OS/userland** — so the runbook must *not* assume any advanced text-tools
exist on the host. It is designed accordingly: **all text processing (`grep`/`sed`/`xargs`/`tar`/
`gzip`/`test`) runs *inside* the `app` container** via `docker compose exec` (service running) or
`docker compose run --rm` (service quiesced — as the repair does), where the environment *is* known
(Debian `python:3.13-slim-bookworm`, GNU userland). The host therefore needs only the
container/orchestration and code-sync tools, not a rich shell userland.

**On the host (only what we genuinely require there):**

| Tool | Why | Notes / if absent |
|---|---|---|
| `docker` + **Compose v2** (`docker compose`) | recreate/build the container; `exec`/`cp` into the service | the deployment substrate — necessarily present (the system runs on it). If only legacy `docker-compose` v1 exists, substitute that spelling. |
| `git` | `git pull` the fixed code in the deployment checkout before `docker compose build` | **Only needed if the host builds the image from source.** If the image is delivered from a registry instead, use `docker compose pull` and `git` is not required on the host. |
| a shell + `ssh`/console access | reach the host and run the commands | `ssh` runs on the *operator's* workstation, not the host; any login shell on the host suffices. |

Deliberately **not assumed on the host:** GNU `grep`/`sed`/`xargs`/`tar`, a specific shell, etc.
They are used only via `docker compose exec/run app sh -lc '…'`, so the host's userland is irrelevant.

**Inside the `app` container (known-good — no installation needed):** `sh`, `grep`, `sed`, `xargs`,
`tar`, `gzip`, `test`, `git`. The GNU-specific flags used — `grep --exclude-dir`, `sed -i`,
`xargs -r` — are valid in that Debian image (they would not be portable to BusyBox, but the runtime
is Debian, so this is safe).

> Net host-side requirement: **Docker + Compose v2** (a given), plus **git** *only if building on the
> host*. Everything else is inside the container. If even `git` is undesirable on the host, deliver
> the fixed image via registry (`docker compose pull`) and drop step 3's `git pull`/`build`.

Run these in order on the remote host, from the deployment directory that holds
`docker-compose.yml`. **Everything is keyed off the compose *service* `app`** — no command assumes
the image tag, the git repo name, or the volume name is "architectonic". (Compose prefixes volume
names with the project/dir name, so `docker run -v arch-data:…` is *not* safe; the steps below stay
compose-relative instead.) Paths are the real ones from the live verify output.

All repair steps run in **one-off containers** (`docker compose run --rm --no-deps --entrypoint sh
app`) **while the service is stopped**, so git-sync/GUI/MCP cannot mutate the repo during the repair.
The one-off container mounts the same named volumes (it's the `app` service), so repo state persists
across invocations. `R()` below is just shorthand for that invocation.

```sh
R() { docker compose run --rm --no-deps --entrypoint sh app -lc "$1"; }
# AUTH for the push/fetch in step 4b. The app installs an askpass at startup
# (git_auth.create_askpass_script/build_git_env — git_auth.py:240,252, invoked from git_sync.py:61);
# a `--entrypoint sh` one-off container BYPASSES that, so env vars alone do NOT authenticate.
#
# PRINCIPLED PRIMARY (recommended): add a purpose-built `arch-repair` subcommand to the image that
# reuses the app's own resolver — collect_credentials() + create_askpass_script() + build_git_env() —
# so it supports ALL configured modes: ARCH_GIT_HTTPS_TOKEN, _TOKEN_FILE (k8s/docker secret),
# explicit _USERNAME/_PASSWORD, and SSH via SSH_ASKPASS/SSH_ASKPASS_REQUIRE. Then run step 4b through
# `docker compose run --rm --no-deps arch-repair …` instead of RGIT.
#
# STOPGAP only (HTTPS inline/token-file; NOT SSH): RGIT below wires GIT_ASKPASS from an inline token
# or a token *file*. It deliberately does NOT cover SSH passphrases — use the arch-repair command for
# SSH deployments. (Reimplementing the app's full auth in shell is exactly what arch-repair avoids.)
RGIT() { R 'TOK="${ARCH_GIT_HTTPS_TOKEN:-$([ -n "$ARCH_GIT_HTTPS_TOKEN_FILE" ] && cat "$ARCH_GIT_HTTPS_TOKEN_FILE")}"; printf "#!/bin/sh\ncase \$1 in Username*) printf %s \"${ARCH_GIT_HTTPS_USERNAME:-x-access-token}\";; Password*) printf %s \"${ARCH_GIT_HTTPS_PASSWORD:-$TOK}\";; esac" >/tmp/ap && chmod +x /tmp/ap && export GIT_ASKPASS=/tmp/ap GIT_TERMINAL_PROMPT=0 && '"$1"; }

# 0. QUIESCE FIRST: stop the live service so git-sync (60 s poll) and GUI/MCP writes cannot mutate the
#    repo during backup or repair. Backup of a live volume could otherwise be inconsistent.
docker compose stop app

# 1. Insurance backup of the now-quiesced repo (tar to host stdout — '>' is a POSIX shell builtin).
#    Recovery is cheap: restore this, or simply redo the repair.
R 'tar cz -C /data/engagement .' > eng-backup.tgz

# 2. Record the ORIGINAL production branch ONCE, durably (host file), and never overwrite on rerun;
#    refuse to proceed if it looks like the repair branch (guards a partial earlier run).
[ -f orig-branch.txt ] || R 'cd /data/engagement && git rev-parse --abbrev-ref HEAD' > orig-branch.txt
case "$(cat orig-branch.txt)" in repair/*) echo "ABORT: orig-branch.txt is a repair branch"; exit 1;; esac

# 3. Repair the dangling references on disk (old slug -> new slug), scanning the WHOLE engagement
#    repo so the project subdir (projects/autocam/...) and the diagram catalog are both covered. The
#    old id is a unique substring, so this also fixes slug-bearing connection ids
#    (…cam-projects-cps---…@@archimate-serving).
R 'cd /data/engagement &&
   grep -rl --exclude-dir=.git "APP@1782278054.OPaZCl.cam-projects-cps" . |
   xargs -r sed -i "s/APP@1782278054\.OPaZCl\.cam-projects-cps/APP@1782278054.OPaZCl.cps/g"'

# 4a. STAGE + INSPECT (stops for human approval — no commit). `git add -A` stages the untracked
#     new-slug file and the new MIRA diagram too (a `commit -am` would commit the old deletion but
#     omit them). `switch -C` is rerun-safe. Nothing here is irreversible; READ the diff.
R 'cd /data/engagement &&
   git switch -C repair/cps-rename &&
   git add -A &&
   git diff --cached --check &&
   git ls-files --error-unmatch \
     "projects/autocam/model/application/application-component/APP@1782278054.OPaZCl.cps.md" &&
   ! git grep --cached -qI "APP@1782278054.OPaZCl.cam-projects-cps" &&
   echo "=== staged change set — review before step 4b ===" &&
   git diff --cached --name-status'
#     >>> OPERATOR: proceed to 4b only if the staged list is exactly as expected. <<<

# 4b. COMMIT on the repair branch, push it, then return to prod, fast-forward, and verify upstream.
#     Push auth = the .env credential helper (ARCH_GIT_HTTPS_TOKEN/_USERNAME/_PASSWORD or
#     _SSH_PASSWORD) — never on the CLI. Only the AUTHOR IDENTITY is supplied (none is configured).
#     ORIG comes from the durable host file. Prefer your normal PR/merge over the direct ff-merge.
#     RGIT (not R) so push/fetch authenticate via the askpass set up from the .env token.
#     Each step is guarded so a rerun after a partial 4b RESUMES rather than hard-fails (e.g. a
#     no-op `git commit` would otherwise abort the chain). EXP_UP is the upstream you expect for prod.
EXP_UP="origin/$(cat orig-branch.txt)"
RGIT "cd /data/engagement && ORIG=\"$(cat orig-branch.txt)\" && EXP_UP=\"$EXP_UP\" &&
   { git diff --cached --quiet || \
     git -c user.name=\"\${ARCH_GIT_AUTHOR_NAME:-Arch Bot}\" \
         -c user.email=\"\${ARCH_GIT_AUTHOR_EMAIL:-\${ARCH_GIT_HTTPS_USERNAME:-arch-bot}@local}\" \
         commit -m 'fix(model): repair CPS slug references after rename (CFCS, MIRA diagrams)'; } &&
   git push -u origin repair/cps-rename &&
   git fetch origin \"\$ORIG\" &&
   git switch \"\$ORIG\" &&
   git merge --ff-only repair/cps-rename &&
   git push origin \"\$ORIG\" &&
   test -z \"\$(git status --porcelain)\" &&                                  # working tree clean
   UP=\"\$(git rev-parse --abbrev-ref --symbolic-full-name @{u})\" &&
   [ \"\$UP\" = \"\$EXP_UP\" ] || { echo \"ABORT: upstream \$UP != \$EXP_UP\"; exit 1; }"   # ASSERT, not print
#     Prod checkout is back on its branch with the fix merged — not left on repair/* (git-sync pulls
#     the current branch's upstream, so a stuck repair/* checkout would mis-sync prod). Idempotent:
#     `commit` is skipped when nothing is staged; `merge --ff-only` and `push` are no-ops if already done.

# 5. Deploy the fixed code and bring the service back. Pull the merged fix in THIS deployment
#    checkout, rebuild the image, and start — volumes persist, NEVER pass -v. Recreating the
#    container rebuilds the in-memory index from the now-correct /data AND loads the fix.
git pull
docker compose build app
docker compose up -d app

# 6. Verify (CLI, no MCP) against the now-running service.
docker compose exec app sh -lc '
  cd /data/engagement &&
  ! grep -rq --exclude-dir=.git "cam-projects-cps" . &&
  test -f projects/autocam/model/application/application-component/APP@1782278054.OPaZCl.cps.md &&
  echo "OK: no stale refs, entity file present"
'
rm -f orig-branch.txt   # clear the durable marker only after a clean, verified completion
```

Notes / ordering rationale:
- **Quiesce first (no live races):** the service is **stopped** (step 1) before any repair, so
  git-sync (60 s poll) and GUI/MCP writes cannot mutate the repo mid-repair. Repairs run in **one-off
  containers** (`docker compose run --rm --no-deps`) over the same volumes; only step 5 brings the
  service back. This is the maintenance isolation a live `exec` could not provide.
- **Rerun safety:** the original production branch is captured **once** into a durable host file
  (`orig-branch.txt`, init-only-if-absent) and the run **aborts** if it looks like `repair/*` — so a
  partial earlier run cannot later record the repair branch as "production". `switch -C` is
  idempotent; the marker is deleted only after a clean, verified finish.
- **Staging untracked files (critical):** a `commit -am` would commit the old entity's deletion but
  omit the untracked new-slug file and new MIRA diagram → a commit that loses CPS. Step 4 uses
  `git add -A` + staged-diff inspection + presence/absence assertions, on a `repair/cps-rename`
  branch, pushed only after the operator approves; then fast-forwarded into prod and the checkout
  returned to the prod branch (verified via `@{u}`).
- **Auth vs identity:** push auth comes from the `.env` credential helper
  (`ARCH_GIT_HTTPS_TOKEN`/`_USERNAME`/`_PASSWORD` or `_SSH_PASSWORD`) — never on the CLI. Only the
  **author identity** is supplied (none is stored anywhere — the root of the "missing author identity"
  failure). Persist it once in `arch-home` to prevent recurrence (`git config --global user.name/…`),
  and see §5.7 for the proper author-vs-committer design.
- **Naming independence:** keyed off the service `app` and `docker compose run/exec/build` only; no
  image/repo/volume name assumption.
- **Project subdir:** step 3 scans the whole engagement tree, covering `projects/autocam/model/…` and
  `diagram-catalog/…`. (The code fix's M4 transaction uses `all_model_roots`, covering `projects/*/model`.)
- If the repair ever looks wrong, restore `eng-backup.tgz` or redo it — recovery is cheap.
- After the code fix is live, future drift clears via the reindex tool (§7.3), no redeploy.

### 9.5 Optional independent verification (with MCP, not required for the repair)
Our read-only `arch-repo-read-diag` connection can confirm the outcome out-of-band: re-run
`artifact_verify` on `ARC@1782278684.yUXoze` and `ARC@1782365608.c3xIZY` and expect no `E301`/`E302`.
This is a convenience check from our side, not part of the CLI runbook.

---

## 10. Constraint cross-check (does the plan satisfy §0?)

| Constraint / requirement (§0) | Addressed by | Status |
|---|---|---|
| Diagnose principally; explain the failure mode, not just the symptom (§0.1) | §3 root-cause analysis; §2.1 executed repro | ✅ |
| Read-only remote access; quarantine behavioural-only speculation (§0.2) | §1 live read-MCP evidence; all architecture claims re-verified in code | ✅ |
| Report contains error / safe repro / failure-mode analysis / root causes / options / drivers / recommendation + impl + tests (§0.3) | §1, §2, §3, §3.7, §5, §4, §6–§8 | ✅ |
| Restore invariant (iii) as a *total* property + **guaranteed write consistency** (§0.4) | §6.2 one canonical index + §6.3 coarse RW mutex (write-through) + §6.6 proof; (i) serialization kept, (ii) validation kept | ✅ |
| Entity in engagement repo; don't treat eng/ent scope as the cause (§0.5) | §3.1–§3.2 frame it as multiple views of the *same* repo | ✅ |
| Watcher exists but is mis-scoped — say to what extent, and what's still needed (§0.5) | §3.1 (what exists); §6.2 one canonical index + §5.6 project-subdir coverage (what's needed) | ✅ |
| Index in-memory; deployment = Compose service `app` (§0.5) | §9 mechanics built on these facts | ✅ |
| Commit/push failed (PAT, no author identity); rename *likely but not certainly* independent (§0.5) | §1 note; §9 step 2 fixes identity; fix is channel-agnostic | ✅ |
| Two phases: code first, then deploy once (§0.6) | §9 sequencing note + runbook step 3 | ✅ |
| Remote repair CLI-only, no MCP/Claude, simple (§0.6) | §9 runbook; §9.0 tools | ✅ |
| Host OS/userland unknown — don't assume advanced host CLI tools; repair runs on the host (§0.5/§0.6) | §9.0 host-vs-container split: only Docker/Compose (+git if building) on host; all text-tools run in-container via `docker compose exec`/`run` | ✅ |
| Volume safety — never discard volumes (§0.6) | §9 warning; container-recreate-only; in-memory index | ✅ |
| Name-independence re "architectonic" (§0.6) | §9 keyed off service `app`; no image/repo/volume-name assumption (verified: only the image tag uses it) | ✅ |
| Project-subdirectory safety (§0.6) | §9 step 1 scans whole repo; code paths use `all_model_roots` (incl. `projects/<slug>/model/`) | ✅ |
| Cheap backup / redo (§0.6) | §9 step 0 one-liner + restore/redo note | ✅ |
| Repro executed & observed, repos unchanged (§0.6) | §2.1 (ran against throwaway temp repos; verified) | ✅ |
| Principled fix at correct layer; no workaround; writes via tools; quality gates; delegation+regression tests; tool-count/LoC/clock/naming (§0.7) | §6 design lands at owning layers (domain identity, index, mutation gate); §8 tests; §9 CLI edit flagged as explicit out-of-band recovery | ✅ |

**Residual / explicitly out of scope:** offline/async writes and their machinery (durable deferred
queue, generalized OCC, fine-grained leasing) are out of scope (§0.4) — the coarse mutex already
guarantees consistency. The exact historical channel that introduced the drift remains *inferred, not
proven* (§0.5); the fix is designed to be correct for all candidate channels, so closing that gap is
not a prerequisite.
