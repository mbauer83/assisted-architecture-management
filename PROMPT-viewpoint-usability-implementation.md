# /goal: Implement the viewpoint-usability improvement proposals

You are the IMPLEMENTATION agent for `PROPOSALS-viewpoint-usability-improvements.md`.
That document is decision-complete and authoritative: every proposal carries evaluation,
options, an owner-adjudicated recommendation, an implementation sketch, and acceptance
criteria; a verified **Implementation code map** at the end names the exact files.
Owner adjudications recorded in the document are BINDING — do not relitigate them.
Context (read-only, only when a proposal's rationale is unclear):
`REPORT-viewpoint-usability-stress-test.md` and evidence under
`test-results/usability/2607171252/`.

## Ledger and resumability (do this first)

Create `TASKS-viewpoint-usability-implementation.md` on your first run (or resume it if
it exists — trust the ledger over memory after any compaction). One checkbox row per
work unit below, with columns: status, files touched, acceptance evidence (test names /
probe output), notes. Update it after EVERY work unit, before starting the next. If you
approach context limits: finish the current work unit, commit nothing half-done, write
a RESUME note at the top of the ledger, and stop cleanly.

## Order of work (dependency-derived — follow it)

Phase 1 — semantics users can trust (backend-heavy, independently shippable):
1. **P-05 investigation FIRST** (blocks P-05 and finalizes P-01 wording): determine
   what `traversal` value the GUI builder emits today for 'has a connection…'
   predicates (the stress test observed a derived-only match although the schema
   default is `direct`). Record the answer in the ledger before touching code.
2. **P-01** truthful summaries + `anchor_modeled_distance` + ring legend + grammar fix.
3. **P-05** `both` traversal (union-before-negation, dedup), builder selector,
   summary wording, Test-run matched-entity list, upgrade-CLI default-stamping.
4. **P-04** style-rule outcome taxonomy (unresolvable / expected-empty / shadowed /
   applied) + scale-attribute combobox + numeric Auto bounds.
5. **P-03** projection status/version + typed column_values (+ last_updated decision:
   verify whether the read index has it; if not, drop it and note in the ledger).
6. **P-06** ordered witness_steps + edge selection + edge legend.

Phase 2 — definitions that mean what they say:
7. **P-02** selection_mode + editor mode switch + GUI empty-query fix + W-code +
   deployment-atomic upgrade-CLI migration (`--resolve-selection`, distinct
   unresolved-migration exit status, byte-identical on refusal).
8. **P-09** target-population declaration + honest-empty header + cancel-state fix.
9. **P-17** realization-family contract + re-scoped requirements-realization + the
   two coverage viewpoints (depends on P-03, P-05).
10. **P-13** fork lineage (content digest + generation, one stamping service for GUI
    and MCP) + staleness badge.
11. **P-07** URL state (viewpoint + params + layout) + live-vs-verified links +
    editor routes.

Phase 3 — surfaces and polish:
12. **P-08** graph/diagram ergonomics bundle (fit/zoom, layout freeze before
    hit-testing, radial guard, label wrap + legend, diagram initial fit, F7 friendly
    render-limit fallback).
13. **P-11** table rows/sort + server-generated complete generation-pinned export.
14. **P-12 + P-12a + P-14** catalog columns/search, create entry point, picker and
    terminology polish, F11 banner fix, F16 discard/cancel.
15. **P-10** fork-safe validation (quarantine inherited drifted rules; edit-time
    condition validation). **P-15** endpoint criteria on connection style rules.
16. **P-16** scale-adaptive presentation, phased per the proposal (mitigation pass
    first; AggregateItem projection capability; expand/collapse UI last).

Self-model batch (independent of product phases; MCP tools only, never manual file
edits): **SM-01** (merged motivation-convention review — follow its 5-step procedure
exactly, including remove+recreate for retyping), **SM-04** (assurance-store
realization edges; check pair-legality via `artifact_authoring_guidance` first),
**SM-05** (conformance worklist with the four-status disposition register), **SM-06**
(drop capability-map's drifted rule — module yaml), **SM-07** (orphan triage),
**SM-08** (status bulk pass per project, dry-run + verify each batch).

## Acceptance validation (per work unit, before ticking the box)

- Implement the proposal's own **Validation** list as automated tests wherever it
  names counts, sets, or invariants; run them.
- Where a validation names a probe scenario, run
  `uv run python tools/usability_test/execution_probe.py <slug> [--param k=v]` and
  record the relevant numbers in the ledger. Reference values live in
  `test-results/usability/2607171252/probe-*.json`.
- Quality gates after every batch, all must pass before the ledger is updated:
  `uv run python -m pytest --tb=short -q` · `ruff check src/ tests/` ·
  `uv run zuban check` · in `tools/gui/`: `npm run lint` (cold, authoritative;
  use `npm run lint:fast` only for the inner loop) + `npm run typecheck` +
  `npm run test`.

## Hard rules (repo policy — violations are rework)

- Never reference phases, decision IDs, work-unit numbers, or "the proposal/plan" in
  CODE, test content, or filenames — code comments state constraints, not provenance.
  (PLAN/TASKS/PROMPT files are exempt.)
- Source-file length policy: 250 soft / 350 hard counted lines;
  `SOURCE_FILE_BASELINE_LIMITS` in `src/infrastructure/quality/source_file_length.py`
  lists grandfathered files that may NOT grow — GraphExploreView.vue, EntitiesView.vue
  and other named GUI targets are in it, so surface work there must extract
  subcomponents, and you remove a file's baseline entry when you bring it under 350.
- Principled solutions only: fix contracts at the correct layer; no workarounds; add a
  regression test for every defect-class fix. All model writes via `artifact_*` MCP
  tools with `dry_run=true` first; `artifact_verify` after each model batch.
- `uv sync` / `uv run`, never pip. No `Any` typing. No `if TYPE_CHECKING` to paper
  over types. Timestamps via `src/domain/clock.py`.
- Schema changes to definitions require the docs (`docs/reference/viewpoints-schema.md`)
  and `types.generated.ts` regeneration (`uv run tools/generate_types.py`) in the same
  work unit.
- MCP surface or backend-behavior changes need a backend restart to observe — note in
  the ledger when a work unit's live verification is deferred to the user's restart.

## Delegation policy (Sonnet 5 subagents)

Use the Agent tool with `model: "sonnet"` (subagent_type `general-purpose`) for
MECHANICAL, fully-specified work; keep everything contract-bearing in your own
context. Rules:

- **Delegate:** component extraction to satisfy the length ratchet (e.g. splitting
  GraphExploreView.vue / EntitiesView.vue along boundaries YOU specify); test
  scaffolding from an acceptance list you write out; repetitive plumbing across many
  files after you have done the first instance yourself (the "one worked example"
  pattern); catalog-column/badge wiring; docs + `types.generated.ts` regeneration
  chores; read-only reconnaissance summaries.
- **Never delegate:** semantics and contracts (P-02 atomic migration + mode
  semantics, P-05 union-before-negation and the builder-default investigation,
  P-09/P-17 target-population decisions, P-16 aggregate identity, anything touching
  `src/domain/viewpoint_criteria*.py` schema), model writes (SM-*), ledger
  decisions, or anything where the proposal offers options.
- **Brief contract:** subagents inherit NOTHING. Every brief must contain: the exact
  file paths, the expected behavior/diff shape (or the worked example to imitate),
  the repo hard rules that apply (length policy incl. the baseline-ratchet rule,
  no `Any`, no phase/plan references in code, comment style), and the exact commands
  the subagent must run and report before returning (targeted pytest/vitest, ruff,
  `npm run lint:fast`).
- **Verification stays yours:** re-run the full gates yourself and review the diff
  before ticking any ledger box for delegated work; record `delegated: sonnet` in
  the ledger row. A subagent's "done" is a claim, not evidence.
- **Parallelism:** at most 2–3 subagents concurrently, only on disjoint file sets;
  if two tasks touch the same file, serialize them. Never let a subagent and
  yourself edit the same file concurrently.

## Scope discipline

Implement what the proposals specify — no opportunistic refactors beyond the length
policy's forced extractions, no new features, no dependency additions without a
ledger note explaining why the proposal is unimplementable without one. When a
proposal under-specifies something despite the code map, make the smallest decision
consistent with its Applied Principles, record it in the ledger under "decisions",
and continue — do not stall.
