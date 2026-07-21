# PROMPT — Execute the Navigation & Tier Transparency Plan

You are implementing `PLAN-navigation-and-tier-transparency.md` with the execution ledger
`TASKS-navigation-and-tier-transparency.md`. Read both in full before writing any code,
then follow the ledger's resume protocol: the first unticked WU is the current one.

## Ground rules (non-negotiable)

1. **Guidance first.** If the `arch-repo-read` MCP server is available, query it for
   coding guidelines / best practices / style guides and apply them (the general coding
   guidelines standard and the hexagonal/unified-backend/MCP-topology ADRs are directly
   relevant to S1/S2).
2. **No provenance in code — diff-scoped.** No phase/WU/decision ids, plan-section
   references, or "companion plan" wording in any line you add or modify (source, test
   content, filenames). Pre-existing occurrences elsewhere are not your cleanup unless a
   WU lists them. PLAN/TASKS/PROMPT files are exempt.
3. **Principled solutions only.** Fix at the correct layer; complete missing port/facade
   contracts instead of routing around them (client-side filtering around a missing API
   parameter is a forbidden workaround); every closed contract gap gets a delegation
   test plus a regression test.
4. **Layer discipline.** Search visibility and write authorization are application
   policies: injected/explicit, never service-located from adapters, never encoded in a
   shared resolver or by hiding UI controls. Storage executes filters passed as data.
5. **LoC policy.** 250 soft / 350 hard counted lines; recorded baselines must not grow.
   The ledger names the near-limit files — reduce by extraction; put new policy in new
   focused modules.
6. **Typing.** No `Any`/`any` in changed lines; closed unions over raw strings for
   states/tiers; ternaries ≤ 1 nesting, expression position.
7. **Tests.** Separate test file per component/use-case; real-git/real-file tests for
   git/filesystem behavior; matrix tests as specified per WU (branch-complete for
   search, inventory-based for mutators, row-complete for the status matrix).
8. **Tooling.** `uv sync --all-groups` for deps. Model writes (if any self-model
   description is touched) only via `artifact_*` MCP tools with `dry_run` first.

## Quality gates per WU (targeted tests first, then all of these, before ticking)

```
uv run python -m pytest --tb=short -q      # 0 failures
uv run ruff check src/ tests/              # 0 errors (incl. E501)
uv run zuban check
# when tools/gui touched (cold, from tools/gui/):
npm run lint && npm run typecheck && npx vitest run
```

## Environment & restart protocol

- MCP tools run against a long-lived `arch-backend`; backend code changes are inert
  until the **owner** restarts it (ask; never restart yourself). The GUI dev server
  hot-reloads.
- The enterprise repository is a separate git repo under `enterprise-repository/` with a
  branch-review state machine (`.arch/enterprise-sync.json`; handlers in
  `src/infrastructure/git/git_sync_enterprise.py`). Never run
  `git checkout`/`git restore` on working-tree files anywhere; the working tree may hold
  unsaved work.
- Do not commit or push unless the owner asks.

## Settled semantics — do not re-litigate

- Promotion (including enterprise save/submit/withdraw) is the only enterprise write
  outside admin mode; standard authoring tools are engagement-only in **every** mode and
  accept only the configured active engagement root; admin mode enables direct
  enterprise authoring only via the admin operations surface. Enforcement: pure policy +
  snapshot provider in `src/application`, concrete AuthorizedMutationExecutor adapter in
  `src/infrastructure`, wired at composition roots; the executor REPLACES old queue
  wrappers (one submission, gate acquired once inside the worker after a fresh
  re-check); registration factory makes the manifest structurally unavoidable.
  `boundary.py` guards stay as narrow context-free invariants. Assurance-store
  mutations keep their own unlock gating (out of scope). Save commits run the artifact
  verifier; only content-neutral git ops (Submit's push, Discard) are exempt.
  (PLAN D9/D10)
- Authority is per-action (`denied_intents(reason, target)`), never a scalar, and
  enterprise Save/Submit/Discard are distinct intents: a dirty working tree is
  lifecycle state — `enterprise_save` stays available; fetch/upstream/divergence faults
  allow local save and local discard while denying promotion, submit, and
  pending-remote discard; read-only denies all external repository intents;
  maintenance is always allowed. The health-reason type is owned by the application
  policy; the aggregate only serializes it (PLAN D9/D11/§12).
- Authority is never cached: the status cache holds only expensive measurements; every
  status request composes the fresh projection from the snapshot provider, so direct
  `gate.blocking_writes()` transitions are visible immediately — tests go through the
  real production path, not `block_repo` shims (PLAN D11).
- GAR visibility: one eligibility predicate (visible ∧ type ∧ domain) across FTS,
  fallback, and semantic refill; empty effective set → zero entity hits; FTS
  prepared-SQL pushdown; raw id/list access stays untouched (PLAN D7).
- Sync state: one PURE versioned lifecycle+health aggregate (typed
  load/transition/atomic persist only; no GUI cache/event imports); orchestrator and
  executor publish/invalidate via injected ports after successful persistence;
  `ReconcileOutcome.completed` gates health clearing; persisted-health transitions
  invalidate cached measurements; the frontend is fail-closed until its first
  successful authority response; SSE triggers re-reads only (PLAN D6/D11).
- Discard requires a clean tree; pending Discard is an idempotent desired-state
  transition (remote ref absent → main → local branch absent → aggregate cleared;
  already-absent = step success; aggregate stays pending until all postconditions
  hold; retries converge — fault-injection tested); dirty states offer Save;
  destructive cleanup of uncommitted changes is out of scope (PLAN §12).
- Tier vocabulary: URL `tier` ∈ {absent=All, engagement, enterprise, module}, validated
  per surface (module is viewpoints-only); API keeps `scope=global`. User-facing copy
  says "Enterprise", never "Global".

## Sequencing constraints

- Slices land in ledger order: S1 and S2 (policy/security) before any UI slice; S3/S4
  (codec + contracts) before S5 (adoption); S6 before S7 (the cluster is what makes the
  nav consolidation shippable); S8 closes. Within S6: aggregate (S6a) before the
  authority read model (S6b) before the cluster (S6c).
- Shared components are introduced exactly where the ledger says and consumed
  immediately; do not pre-build ahead of the owning WU.
- If a WU's stated facts contradict the code you find, stop and record the discrepancy
  in the ledger before proceeding — do not improvise around it.

## Definition of done

Every acceptance criterion in PLAN §10 verified (S8b needs an owner backend restart
first), ledger fully ticked with evidence (commands + key outputs), counted-line
records for all touched near-limit files, and a short closing note of deviations in the
ledger.
