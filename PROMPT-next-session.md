# PROMPT — next session

Continue work in `scalable-architecture-for-humans-and-ai`. Clean tree on `main`
at `eab3fff`.

## Read first, in this order

1. `CLAUDE.md` — quality gates, architectural discipline, tool-based authoring.
2. **`TASKS-strategy-and-assurance-uplift.md`, the `⚠ READ FIRST` section at the
   top** — the reconciled true state and the cross-plan sequencing. Checkbox
   state in that file lags reality in three WUs; the table there is
   authoritative, not the boxes.
3. The plan(s) for whichever step you are on (below).

## Enumeration discipline (non-negotiable — a prior session got this wrong)

A previous session was asked what work remained, ran a `grep … | head -20`,
derived a follow-up line-range from that truncated output, and then presented a
*complete* remaining-work list and a sequencing recommendation from it. It missed
`## Stream R` entirely — 9 open checkboxes, the largest untouched stream, and
directly relevant to the sequencing it was recommending.

**Count first, enumerate second, reconcile the two:**

```
grep -c '^- \[ \]' TASKS-strategy-and-assurance-uplift.md    # total open
grep -c '^- \[x\]' TASKS-strategy-and-assurance-uplift.md    # total done
grep -n  '^## Stream\|^### WU' TASKS-strategy-and-assurance-uplift.md
```

If a per-stream enumeration doesn't sum to the total, it is incomplete — say so
rather than presenting it. Never apply `head`/line caps to a search whose purpose
is completeness; aggregate programmatically instead. A truncated search supports
only a bounded claim, never an unbounded one.

## Agreed sequencing

1. **Security-signals backlog items 2–7** ← start here
2. Stream R — viewpoint reference integrity (its own focused session)
3. `PLAN-attribute-profile-registry.md` — Streams P, Q (+R1), S, W, then R2, T
4. Profile-registry Stream V — multiple specializations per concept
5. OpenAPI — modeling/querying endpoints first
6. `PLAN-aibom-model-derived.md`

Rationale is recorded in the `⚠ READ FIRST` section; do not re-derive it.

## This session's task: security-signals backlog 2–7

The backlog is at the very end of `TASKS-strategy-and-assurance-uplift.md`.
Item 1 is done (MCP ingest tool + REST parity, live-verified).

**Start with item 2, the rename sweep**, and co-land the defect below.

### Locked naming (do not re-litigate)

The act = **ingest** (`IngestSecuritySignals`, `tools/ingest_security_signals.py`,
CLI verb `ingest`). The data = **SecuritySignalSnapshot** (table
`security_signal_snapshots`, `SnapshotStore`, `snapshot_id` / `_components` /
`_findings`, lifecycle staging→complete→active→superseded). "An ingest produces a
snapshot."

Rename across domain / store / command / bundle / script / MCP / REST / CLI /
docstrings, ~30 tests, and the sizing spike. Rename the DDL table + columns in
the v2 DDL — **no data migration**; recreate the dev store (Q12: pre-alpha, no
assurance user, no data to preserve).

### Co-land with the rename: the finding_count defect

`RefreshActivated.finding_count` reports the **submitted** bundle count, not what
was **persisted**. Live evidence: an ingest reported 41 findings for
`APP@1777293133.OYEmP1`; the snapshot holds 24 (`withheld` 0, `suppressed` 0 — so
neither TLP nor VEX).

Root cause verified in `_refresh_run_store.populate_run`: `finding_id =
_stable_id("FND", run_id, component_row_id, canonical_id)` with `INSERT OR
REPLACE`, so bundle findings whose alias sets resolve to the same canonical
vulnerability for the same component collapse. **The collapse is correct; the
reporting is not** — the CLI prints 41 and the MCP tool returns 41 while the
caller reads back 24.

Fix: return persisted counts from `populate_run` and report both submitted and
persisted, naming the delta as alias collapse so dedup stays visible. This
touches the command's result type, which the rename already touches — hence
co-landing. Affects `security_write_tools.py` (MCP), `_assurance_signals_routes.py`
(REST), and `tools/refresh_security_signals.py`.

### Then items 3–7

3. `arch-assurance seed [--with-signals]` (loads `seed-assurance.json`; opt-in
   signal ingest for the frontend `APP@1776149382.lmO0mp` and backend
   `APP@1777293133.OYEmP1` anchors) + Quickstart/README/docs.
4. Directness fix: capture the python (`cyclonedx-py`) dependency graph so
   directness isn't all `unknown`. npm already classifies transitive; the live
   python snapshot shows `directness: "unknown"` on every finding.
5. GUI: component-vulnerability details view fed by `/security-findings`, reached
   **primarily by a link from `EntityDetailView`** (the anchor entity), secondarily
   from the wizard. Rework `AssuranceSupplyChainWizardView` (calls removed
   endpoints → 404) to view the active snapshot; drop the aibom-coverage panel bits.
6. Docs: `reference/cli-and-backend` + configuration for the removed import/list
   endpoints and the new snapshot list endpoints; regenerate MCP docs after the
   rename.
7. Live re-verify (restart-gated). Mostly done — see the dated entries; the TLP
   flag, restored read tools, MCP ingest, and REST ingest are all live-verified.
   What remains is whatever the rename and the GUI work change.

## Gates

Backend, **one at a time, never concurrent** (concurrent heavy jobs have hung the
WSL2 host):

```
uv run python -m pytest -q -n auto
uv run ruff check src/ tests/
uv run zuban check
```

Frontend from `tools/gui/`: `npm run lint && npm run typecheck && npx vitest run`
— full `npm run lint`, never `lint:fast`.

Baseline at handoff: 6124 passed / 5 skipped; ruff + zuban clean.

## Environment notes

- Backend and frontend were restarted recently; the MCP + REST signal surfaces
  are live and the assurance store auto-unlocks via the OS keychain.
- Backend code changes are inert until the owner restarts `arch-backend`; MCP
  *surface* changes also need a Claude session restart. Queue live verification
  rather than blocking on it.
- **Never commit `.arch-assurance/`.** Stage files explicitly; never `git add -A`.
- Two throwaway anchors (`APP@live-check-ingest-tool`, `APP@live-check-rest-ingest`)
  exist in the dev store from live verification. No snapshot-delete capability
  exists on any surface; the seed work in item 3 recreates the store.

## Other plans (context, not this session's work)

- `PLAN-attribute-profile-registry.md` + TASKS — named reusable profiles, their
  lifecycle and failure semantics (Class A hard-fail / Class B quarantine),
  relationship profiles, and the D6 rewrite for multiple specializations.
- `PLAN-aibom-model-derived.md` + TASKS — model-derived AIBOM; depends on named
  profiles.
