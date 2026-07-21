# PROMPT — next session

Continue work in `scalable-architecture-for-humans-and-ai`. Clean tree on `main`.
This session finished Stream R (viewpoint reference integrity) and the load-bearing
core of the attribute-profile-registry plan (Streams P, Q, R1, S1). What remains is
**three interlocking plans**; this file is the cross-plan conductor and exit-condition
spec so a `/goal` run finishes them in order, to spec, without dropping tasks.

## The three plans and their authoritative ledgers

Each ledger owns its per-WU detail and its own **Resume protocol** — read that protocol
first, and treat its checkboxes as authoritative EXCEPT where a `#### … PROGRESS` note or a
`READ FIRST` table says the boxes lag reality (they do, in named places). Do NOT re-derive
"what's left" from a truncated grep.

1. `TASKS-attribute-profile-registry.md` — named attribute profiles.
2. `TASKS-aibom-model-derived.md` — model-derived AI-BOM (depends on named profiles).
3. `TASKS-strategy-and-assurance-uplift.md` — its own remainder (the `⚠ READ FIRST`
   reconciled-state table is authoritative there; checkbox state lags in D1/G1/G2/U0a/U0b).

### Enumeration discipline (non-negotiable — a prior session got this wrong)

Count first, enumerate second, reconcile. Per ledger:
```
grep -c '^- \[ \]' <TASKS-file>      # open
grep -c '^- \[x\]' <TASKS-file>      # done
grep -c '^- \[~\]' <TASKS-file>      # partial/deviation (READ the note)
awk '/^## Stream|^### WU|^## WU/{s=$0} /^- \[ \]/{c[s]++} END{for(k in c) printf "%4d  %s\n",c[k],k}' <TASKS-file> | sort -rn
```
If the per-stream counts don't sum to the total, the enumeration is incomplete — say so.

## Global order (owner-agreed; reason each step sits where it does)

Do these in order. Within a plan, follow that plan's dependency graph.

1. **attribute-profile-registry: S2 → W → R2 → T** (the plan's own order, P/Q/R1/S1 done).
   - **WU-S2** GUI banner + disabled submit reading the `quarantined` flag WU-S1 added to
     `GET /api/entity-schemata`. Progressive enhancement — correctness is already
     guaranteed by the Q3 write gate (PLAN §3 P8); the acceptance test is "a GUI unaware of
     quarantine still cannot write ambiguous data". Vitest, separate file per component.
   - **Stream W** (W1→W2→W3) relationship/connection profiles — symmetric with entities,
     shares the resolver/classifier/quarantine machinery. Backend + one GUI editor.
   - **WU-R2** proposed resolutions (rename/align/unbind as manual instructions;
     auto-migrate ONLY when the operator file is byte-identical to an older shipped version).
   - **Stream T** docs (T1) + self-model (T2) — see the ADR note below; T2 is guidance-first,
     descriptions over new entities (motivation-entity discipline).
2. **attribute-profile-registry: Stream V** (V1→V4) — multiple specializations per concept.
   The resolution pipeline is already list-native (WU-P3/P2a), so V is the model-wide
   rollout (frontmatter list + scalar back-compat, guillemet list rendering, viewpoint
   grouping/styling over a set, write paths + multi-select GUI + `types.generated.ts`).
3. **attribute-profile-registry: Stream Y** (Y1/Y2) — owner-requested entity-authoring GUI
   fields (create-page real list widgets; edit-page profile fields with merge semantics).
   Pairs with S2 — do them together if convenient. Depends on the S1 schema endpoint.
4. **attribute-profile-registry: WU-U1** — confirm the AIBOM plan can execute on named
   profiles (one shared `ai-provenance` profile + small per-spec profiles; no re-declared
   inherited attributes). This is the bridge to plan 2.
5. **OpenAPI** (modeling/querying REST endpoints) — there is **no dedicated plan file**;
   scope it from the strategy plan's OpenAPI intent. It sits here because steps 1–4 and 6
   change entity/connection payload shapes, so publishing the contract earlier documents a
   shape about to break. If it needs more than a thin task, write a short PLAN/TASKS pair
   first and get owner sign-off.
6. **`TASKS-aibom-model-derived.md`** (Streams A→G) — hard-depends on named profiles (now
   available) and on WU-U1. **BLOCKED ON OWNER QUESTIONS** — do not guess:
   - Q1 (gates Stream A): ship all nine AI specializations, or start with a subset?
   - Q2 (gates WU-E2): the marking tool's server home (`arch-repo-write` vs the dangling
     `assurance_mark_ai_component`).
   - Q3: SPDX 3.0 AI Profile as a second emitter — "later" vs "never".
   Q4 recommends the ordering rename-sweep → profile-registry → OpenAPI → AIBOM (consistent
   with this list). Surface Q1/Q2 to the owner before starting Stream A/E2.
7. **strategy-and-assurance-uplift remainder** (mostly closure; per its READ FIRST table):
   - **D1** (guidance format v2) — GENUINELY OPEN (7 boxes).
   - **E1** (docs) may start anytime; **E2** (deterministic screenshots) needs the B/C/D/G
     UI surfaces — do E last so it doesn't capture shapes about to change (same logic as
     OpenAPI). **G1** is STALE-complete; **G2**'s only real remainder is the **crit-21b
     e2e G-S3 GUI walk** (Playwright; needs the running dev server).
   - **U0b** (previous-release / partial-failure / Docker upgrade coverage) — last in Stream U.
   - **WU-X1** (integrated closure) — LAST OVERALL; needs an owner backend restart; gathers
     every restart-gated verification below.

## Restart-gated verifications to run at the next restart (then tick + record)

- **Attribute-profile Q1/Q3 live**: startup Class-A abort (engagement hard-fail /
  enterprise warn) with a deliberately-broken registry in a **scratch** repo (never the
  live one); quarantine write rejection through MCP. (This session verified the *clean*
  paths live: backend booted clean, `entity-schemata` resolves with `conflicts: []`, a
  dry-run create is not falsely rejected.)
- **Strategy G2**: the crit-21b e2e G-S3 GUI walk (author a trace pattern live).
- The attribute-profile ledger's "Restart-gated live verification queue" section.

## Exit conditions (a plan is DONE when …)

- **attribute-profile-registry**: every WU box ticked or a recorded `[~]` deviation with a
  PROGRESS note; the owner-requested **ADR** authored (see below); full backend
  `pytest -q -n auto` + `ruff check src/ tests/` + `zuban check` green; frontend (from
  `tools/gui/`) `npm run lint && npm run typecheck && npx vitest run` green; self-model
  synced (`artifact_verify` clean); PLAN §8 acceptance satisfied; restart-gated items
  verified or explicitly queued to X1.
- **aibom**: owner Q1–Q3 resolved; all Stream A–G boxes ticked; the ML-BOM emits and
  schema-validates; coverage surface + REST/MCP + GUI panel land; self-model + docs +
  dogfooded export; gates green.
- **strategy-and-assurance-uplift**: D1 + E1 + E2 + G2-e2e + U0b closed; WU-X1 run over the
  integrated result at the final restart; the §13 acceptance criteria met.

## Owner-requested items NOT to forget

- **ADR for Stream Q failure semantics** (owner asked 2026-07-21): a new ADR in the
  self-model capturing blast-radius classification (Class A structural / Class B scoped),
  fail-hard-globally (engagement startup abort) vs quarantine-locally, single-write-boundary
  enforcement (P8), and no-persisted-quarantine. Author it during Stream T (self-model) via
  the MCP document tooling under `docs/adr/platform-core`; `artifact_verify` clean. Tracked
  as WU-Q4's last box.
- **Stream Y** (entity attribute-profile GUI fields) — now in the ledger; see step 3.

## Recorded deviations this session (do not "re-fix" as bugs)

- Q1's tier split lives in a new `_profile_registry_startup.py` (mirroring
  `_group_registry_startup.py`), NOT in `startup_validation.py` — the plan's §2 premise that
  `_schema_inventory_findings` already had the posture was wrong (it raises for both tiers).
- The Q3 write gate uses module specializations ∪ repo-level **profiles**; it does NOT merge
  repo-defined **specialization** bindings (per-alias loading produced ambiguous
  `SpecializationCatalog.get` keys). Repo-defined specialization bindings are not gated yet.
- R1 reconciliation reports conflicts but DEFERS content-version drift: no reusable profiles
  are shipped, so there's no baseline to drift from; the activation path (enrich
  `RepoUpgradeView` with the shipped registry) is recorded in the WU-R1 note.
- S1 MCP parity is via the shared Q3 gate + verifier E043, not a new MCP schema-read tool
  (small-tool-count discipline). No MCP entity-schema read surface exists.

## Gates & house rules (carried forward, all still current)

- Backend gates ONE AT A TIME, never concurrent (concurrent heavy jobs hang the WSL2 host);
  full `-n auto` xdist is fine. Frontend from `tools/gui/` — full `npm run lint`, never
  `lint:fast`; `npx vitest run` resolves the gui project even from repo root.
- **LoC policy bites repeatedly**: several files sit at the 350 hard limit
  (`arch_backend.py`, `artifact_verifier.py`, `viewpoints.ts`, `ViewpointsManagementView.vue`,
  `_loader.py` was split this session). Adding to one fails `tests/common/
  test_source_file_length_policy.py` — reclaim lines by collapsing a nearby verbose
  statement, or extract, rather than growing it. `//`-comment lines and blanks are NOT
  counted; `/** */` and `#`-doc lines ARE (backend) / are (frontend, `//` excluded). Line
  length ≤120 both stacks (`test_line_length_policy.py` for frontend).
- Never `git add -A`; stage explicitly. Never commit `.arch-assurance/`. `*.tsbuildinfo` is
  now gitignored. Commit per coherent WU with the full-suite gate line in the message.
- Model writes ONLY via `artifact_*` / `assurance_*` MCP tools, `dry_run=true` first,
  `artifact_verify` after each batch. Central clock (`src/domain/clock.py`) for timestamps.
- Backend code is inert until the owner restarts `arch-backend`; MCP *surface* changes also
  need a Claude session restart. Queue restart-gated verification; state plainly what needs
  a restart.

## This session's landing (context)

12 commits on top of `66cd965`. Attribute-profile order landed: P1 `733e1a0` · P2 `a66f713`
· P3 `6915fba` · P4 `964b490` · Q `e8552e7` · R1 `daf79c7` · S1 `873db2d`. Plus viewpoint
Stream R (`b349250`/`c8eb759`/`6635aee`) and model hygiene (`33d0d00`/`070911d`). Full
backend 6292 passed / 5 skipped at the S1 boundary.
