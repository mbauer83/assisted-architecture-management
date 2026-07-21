# PROMPT — next session

Continue work in `scalable-architecture-for-humans-and-ai`. Clean tree on `main`
at `dd10c62`.

## Read first, in this order

1. `CLAUDE.md` — quality gates, architectural discipline, tool-based authoring.
2. **`TASKS-strategy-and-assurance-uplift.md`, the `⚠ READ FIRST` section** — the
   reconciled state and cross-plan sequencing. Checkbox state lags reality in some
   WUs; that table is authoritative, not the boxes.
3. **`## Stream R`** in the same file — this session's work. Read the whole section
   including its locked decisions, not just the checkboxes.

## Enumeration discipline (non-negotiable — a prior session got this wrong)

A session once capped a completeness grep with `head -20`, missed Stream R
entirely, and reported an unbounded conclusion from the truncated output. Count
first, enumerate second, reconcile the two:

```
grep -c '^- \[ \]' TASKS-strategy-and-assurance-uplift.md    # 46 open at handoff
grep -c '^- \[x\]' TASKS-strategy-and-assurance-uplift.md    # 87 done at handoff
awk '/^## Stream|^### WU|^## WU/{s=$0} /^- \[ \]/{c[s]++} END{for(k in c) printf "%4d  %s\n", c[k], k}' \
  TASKS-strategy-and-assurance-uplift.md | sort -rn
```

If the per-stream counts do not sum to the total, the enumeration is incomplete —
say so rather than presenting it. Verified at handoff: 8+7+6+6+5+5+3+3+2+1 = 46.

## Where the plan stands

The **security-signals backlog is COMPLETE (items 1–9)**, landed across 11 commits:
the refresh→ingest/snapshot rename, persisted-vs-submitted count reporting,
anchor-identity normalization, `arch-assurance seed`, the directness fix, snapshot
deletion, vulnerability→affected-entities, the GUI views, documentation, and GUI
ingest with enforced anchor validation. All live-verified against the running
backend.

Remaining, in the ledger's agreed order:

1. **Stream R — viewpoint reference integrity** ← start here (9 open)
2. `PLAN-attribute-profile-registry.md` — Streams P, Q (+R1), S, W, then R2, T
3. Profile-registry Stream V — multiple specializations per concept
4. OpenAPI — modeling/querying endpoints first
5. `PLAN-aibom-model-derived.md` — depends on named profiles

Also open, unsequenced: D1 (7), E1 (2), E2 (3), G1 (8 — likely stale, see the
table), G2 (6 — mostly stale; the crit-21b Playwright walk is the real remainder),
U0b (5), X1 (6, restart-gated closure).

## This session's task: Stream R

**The problem in one line:** a viewpoint definition references model elements that
can disappear underneath it, and today only style rules report breakage. Every
other reference class fails silently, so a broken query is indistinguishable from a
legitimately empty result.

**The invariant that matters — I-R1: broken ≠ inactive.** An unset optional
parameter DROPS its term (widens; legitimate — WU-G1 §10.3a). A broken reference
must NEVER drop, because that silently widens results. It keeps not-matching
(narrowing, visible), is reported, AND suppresses absence claims. *A broken query
returning zero gaps must never read as a clean bill of health.* Same discipline as
`target_population: null` refusing to claim "nothing is missing".

**Locked decisions — do not re-litigate** (full text in the Stream R section):

- GENERALIZE the existing mechanism — `StyleRuleOutcomeKind`
  (`applied`/`expected-empty`/`shadowed`/`unresolvable`/`disabled`), the execution
  `warnings` channel, `_downgrade_registry_findings` (warning at load, error at
  save), `ForkStatus` digest staleness. Do NOT build a parallel sync-status
  subsystem, and do NOT introduce a second vocabulary.
- NO persisted broken-reference buffer. It is a pure function of (definition,
  current model); persisting it repeats the rename-stale-index failure mode, would
  not self-clear when the model changes back, and adds ack state + git churn +
  cross-tier promotion conflicts. Compute on demand, memoised by
  `index_generation` + definition digest.
- Acknowledgement = saving a new version; the version + digest is the audit record.
  `disabled` is the existing "keep it, make it inert, stop nagging" quarantine.
- Severity ladder: ontology refs (entity/connection type, specialization, attribute
  path) → error on save · warning on load · LOUD at execute; entity-id refs
  (anchors, `entity-id` params) → warning; dynamic vocabulary (`group`) → advisory
  (§10.2e mandates a typed empty result, not an error).
- Exploit STABLE SHORT IDS: a rename rewrites only the trailing slug, so comparing
  on `PREFIX@epoch.random` makes renames a non-event. Real breakage reduces to
  deletion and cross-tier promotion.

Work R1 → R2 → R3. **Write R1's fixture first** — it is the acceptance test for the
whole stream: retire a referenced entity type, assert the result is loudly degraded
rather than a silent empty pass.

## Tooling added this session that you should use

- **`tests/common/test_documentation_claims.py`** — a drift detector resolving what
  the docs NAME against the code: HTTP endpoints, `arch-assurance` subcommands, MCP
  tool names, repository paths, the assurance capability inventory's HTTP column,
  and the frontend↔backend anchor-type vocabularies. Doc claims of those kinds are
  now checked automatically; extend it rather than hand-checking. It caught its own
  author's regression within the hour.
- **`tools/gui/tests/media/media.spec.ts`** (`npm run media`) — the deterministic
  screenshot harness, fixed 1440×900 @2x, writing to `docs/media/`. Its `watch()`
  fails a capture on any page error or 5xx, so captures double as smoke tests.
  R2's UI surfacing can add a block here; that also serves WU-E2.
- `arch-assurance seed --with-signals` rebuilds a demo store with real dogfooded
  snapshots for the anchors declared in `seed-assurance.json`.

## Gates

Backend, **one at a time, never concurrent** (concurrent heavy jobs have hung the
WSL2 host):

```
uv run python -m pytest -q -n auto
uv run ruff check src/ tests/
uv run zuban check
```

Frontend **from `tools/gui/`**: `npm run lint && npm run typecheck && npx vitest run`
— full `npm run lint`, never `lint:fast`. Running vitest from the repo root resolves
a different config and reports spurious failures; check `pwd` before believing a
frontend failure.

Baseline at handoff: **6215 passed / 5 skipped**; ruff + zuban clean; frontend
**1148 tests** across 112 files; lint + typecheck clean.

## Environment notes

- Backend code changes are inert until the owner restarts `arch-backend`; MCP
  *surface* changes (new or renamed tools) also need a Claude session restart.
  Queue restart-gated verification rather than blocking, and state plainly what
  needs a restart.
- **Never commit `.arch-assurance/`.** Stage files explicitly; never `git add -A`.
- The assurance store is CO-LOCATED: signals share `store.db` with the authored
  STPA/CAST/GRC model. Any repair must be scoped to the signal tables — deleting
  the database destroys authored content that is not regenerable.
- Dev store at handoff: 4 snapshots / 2 active, for the two real anchors.

## Process notes worth carrying (earned the hard way this session)

- **Assert that an edit applied.** Three string-replacement edits silently matched
  nothing and were caught only later, by a test or a type error. An unverified edit
  is indistinguishable from a completed one.
- **Verify a check is non-vacuous.** The first cut of the docs drift detector
  checked 3 of 17 paths and passed, because fenced code blocks break backtick
  pairing. A check that passes because it found nothing is worse than no check.
  Self-refute by injecting the failure it is supposed to catch.
- **Repair means repair.** Asked to fix a 404ing view, I removed the capability and
  wrote the removal into a design document. If you are arguing a removal in prose
  rather than writing a repair in code, stop and ask.
- **Check the design record, not only the code.** `gui-capability-design.md` holds
  normative contracts (architecture model as the navigation spine for assurance,
  `AssuranceExposurePolicy` in the application layer, adapters as thin transports).
  Its capability *inventory* is descriptive and follows the code; its *contracts*
  bind.
- **Prefer generation over prose** for anything enumerable. The MCP tool table
  cannot go stale because it is generated; that is the strongest fix for
  documentation drift, and the drift detector is second best.
- A handoff's stated diagnosis can be wrong. Backlog 4 said "capture the python
  dependency graph"; the graph was always present and the missing piece was the BOM
  *root*. Reproduce the symptom before implementing the described fix.
