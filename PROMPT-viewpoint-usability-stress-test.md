# /goal: Staged, persona-based stress test of the Viewpoints feature (v2 — post-review)

Execute a staged expert inspection of the viewpoint system (catalog, editor, query
builder, presentation styling, execution surfaces, Save As) and produce an actionable,
evidence-classified findings report. Persona behavior is generated in **isolated
contexts** and reported as *synthetic-persona hypotheses*; system correctness claims are
grounded in **independent task oracles** and DOM/API evidence. This version supersedes
v1 after an external methodology review; its constraints are binding.

**You are the ORCHESTRATOR/EVALUATOR.** You see this whole file. Persona work happens in
fresh subagent contexts (Agent tool) that receive ONLY their persona brief (§5) — never
this file, never §3's feature inventory, never oracles or candidate routes, never
another persona's results. If you cannot spawn isolated contexts, you MUST downgrade all
persona-behavior outputs (scent, lostness, abandonment, steps, time-to-first-wow) to
"contaminated — hypothesis only" and say so in the report.

---

## 1. Environment, safety, and the run manifest

- Backend `http://127.0.0.1:8000`; frontend `http://localhost:5173` (persona surface).
  **Never restart, stop, or spawn backend/frontend instances.** If either is down, stop
  and ask the user. Freeze source/model changes for the whole run: if `git status` or
  the catalog changes unexpectedly mid-run, abort and ask.
- **RUN_ID**: generate once (e.g. `date +%y%m%d%H%M` style token). Create the run
  directory up front: `mkdir -p test-results/usability/<RUN_ID>/logs`. All created
  viewpoint slugs MUST begin `usability-<RUN_ID>-`. Before every save: re-read the slug
  field from the GUI and verify the prefix; if it does not match (e.g. an untouched
  Save-As suggestion like `<slug>-copy`), fix it before clicking Save. Record every
  successful create in `test-results/usability/<RUN_ID>/run-manifest.json` as
  `{"run_id": "<RUN_ID>", "created_slugs": [...]}` immediately after each save. The
  cleanup helper enforces all of: manifest-listed, run-prefixed, absent from baseline —
  and refuses `--apply` without `--baseline`.
- Write policy: creating `usability-<RUN_ID>-*` viewpoints and dry-run previews only.
  **Never** edit or delete any pre-existing definition (including old `usability-*`
  leftovers — report them, don't touch them). **Never** write entities, connections,
  diagrams, documents, groups, or module/enterprise files. **Pin state (star buttons)
  must not be changed** — PJ3 is assessment-only.
- **Run manifest** (write to `test-results/usability/<RUN_ID>/environment.json` in S0):
  commit SHA, `git status --porcelain` output, `git diff HEAD --binary | sha256sum`,
  sha256 of every pre-existing untracked file under `engagements/` and `spec/`
  (explicitly including the engagement `.arch-repo/viewpoints.yaml` byte hash), catalog
  baseline path, model `index_generation` (from any probe), browser viewport, evaluator
  model identity, persona execution order, timestamps, and preflight results (§6-S0).
  **Worktree restoration check (S6)**: after cleanup, re-run the same captures; the ONLY
  permitted differences are `test-results/usability/<RUN_ID>/**` and the final
  `REPORT-viewpoint-usability-stress-test.md`. Any other changed path (tracked or
  untracked) = failed restoration → stop and ask the user.
- Helper scripts (`uv run python …`):
  - `tools/usability_test/viewpoint_inventory.py --baseline test-results/usability/<RUN_ID>/baseline.json`
    — catalog rows for you + restoration checksum (per-definition canonical hashes +
    pin list). Run FIRST in S0.
  - `tools/usability_test/execution_probe.py SLUG [--param k=v] [--limit N] [--out FILE]`
    — FULL raw execution + projection (all entity/connection records, provenance:
    version, executed_at, index_generation, repo_scope, entity_limit, truncation,
    per-item style maps) + derived summary. This is oracle input and invariant evidence.
  - `tools/usability_test/cleanup_usability_viewpoints.py --manifest <run-manifest>
    --baseline <baseline> [--apply]` — deletes ONLY manifest-listed slugs, then verifies
    the post-run catalog and pins are byte-identical to baseline. Any verification
    failure: stop and ask the user; never improvise repairs.

## 2. Evidence classes (mandatory on every finding, metric, and claim)

- **Observed system fact** — API/DOM/model evidence attached (probe output, screenshot,
  console log). May be reported as confirmed.
- **Expert inspection finding** — evaluator judgement citing a named principle
  (heuristic, walkthrough failure). May be reported as an inspection finding.
- **Synthetic-persona hypothesis** — role-specific behavior produced by an LLM persona.
  MUST be labeled as requiring human confirmation; never presented as measured
  usability. This includes ALL scent hit rates, lostness, abandonment, confidence,
  time-to-first-wow, and vocabulary findings.
- **Human-confirmed finding** — none will exist in this session; the class exists so
  the report's schema survives a later human round.

Terminology discipline: metrics are "ISO-9241-11-informed synthetic task descriptors",
not usability measurements. No satisfaction or adoption claims. "Quotes" from personas
are *illustrative simulated utterances* and are not evidence.

## 3. Feature surface (EVALUATOR-ONLY — never include in persona briefs)

Viewpoints management (`/viewpoints`): merged module/enterprise/engagement catalog;
engagement editable; other tiers open editable but persist only via **Save as…** (fork →
suggested `<slug>-copy`, version 1 — you must rename to the run prefix). Editor tabs:
General, Scope, Query (criteria builder; reserved `group (project)` path with slug
picker + `in`/`not_in` chips; parameters; derived attributes; neighbor inclusions; live
preview counts; Test run), Presentation (representation exploration/table/matrix/
diagram; style rules match/range/scale; token swatches + custom `#rrggbb`; per-capability
defaults; derived legend; exploration `layout` auto/clusters/radial/force). Execution:
graph exploration (anchored → BFS hop coloring + legend, radial layout, halo-marked
centered anchor, layout toolbar), ad-hoc ArchiMate diagram (style overlays, violet
dashed anchor halo + "◎ anchor" badge), matrix, table (renders in entity browser).
Parameterized viewpoints prompt with an entity picker. Derived connections render dashed
with certain/potential density difference. Baseline (2026-07-17): 409 entities, 778
connections, 34 effective viewpoints (28 module, 6 engagement, 0 enterprise); no
strategy-domain or implementation-domain population (several tasks are fixture-gapped
for exactly this reason — see catalog preconditions).

## 4. Independent task oracles (S0A — the truth layer)

For EVERY persona question, create an evaluator-only oracle row BEFORE any persona runs:

`Oracle ID (=question id) | data preconditions (verified how) | expected answer class |
exact expected entity ids/types (or defined set query) | required relationship/path
properties | known exclusions | acceptable alternative routes | fit_kind | oracle
derivation method | index_generation at derivation`

Derivation independence is about the *evaluation implementation*, not just the
definition: for correctness oracles derive expected sets from **primitive artifact and
connection records** (read-only MCP tools: `artifact_query_search_artifacts`,
`artifact_query_find_neighbors`, `artifact_query_find_connections_for`,
`artifact_query_list_artifacts`) with the traversal/set operation you specify yourself.
Probing a DIFFERENT viewpoint through the same viewpoint evaluator is **corroborating
evidence only** — two views sharing the derivation engine share its failure modes; when
oracle and subject share an evaluator implementation, record that dependency and do not
claim independent correctness. For path-completeness questions preserve the **witness
paths and relationship semantics** in the oracle, not just endpoint sets. For coverage
questions ("all unrealized requirements", "dead technology") enumerate the exact
expected set. Where an exact oracle is infeasible, mark the question **exploratory**:
its adequacy may be discussed but silent-incompleteness claims may NOT be stated as
confirmed. Store oracles in `test-results/usability/<RUN_ID>/oracles.json`; no persona
context ever receives them.

Fixture preflight (part of S0A): for every question whose catalog entry declares
`preconditions`, verify them (probe/MCP). A failed precondition marks the question
**fixture-invalid**: run it only as a catalog-honesty observation ("does the system
communicate that the data isn't there?"), never as a usability failure of the interface.

## 5. Personas — canonical source and isolation protocol

**Canonical catalog: `spec/personas/personas.yaml`** (12 personas PA–PL; schema 3).
Compose each persona brief with
`uv run python tools/usability_test/compose_persona_brief.py <ID>` — the allowlist-based
composer is the ONLY sanctioned composition path (tested to never leak
`candidate_routes`, `fit_kind`, `preconditions`, `expected_catalog_action`). Never
compose briefs by hand. Briefs carry the persona's **numeric action budgets**
(`max_task_actions` per question, `max_authoring_actions` for the challenge) — the
abandonment rule is budget exhaustion, counted in ordinal actions, never simulated
minutes.

Isolation protocol (binding):
- Each persona runs in a **fresh, zero-history subagent context** (a NEW spawn whose
  prompt you author — never a fork/continuation that inherits this conversation)
  receiving only: the composed brief, the frontend URL, permission to browse
  `http://localhost:5173` and read `README.md` + `docs/` (nothing else — no source, no
  spec/, no this-file, no scripts), the failure decision table (§7), the
  action/recording definitions (§8), and the run prefix rule for anything it saves.
  **Harness mechanics and the role→model/effort matrix live in
  `tools/usability_test/EXECUTION.md`** — Claude Code: spawn `subagent_type:
  "vp-persona-runner"` (its tool allowlist enforces no-writes/no-source); Codex: fresh
  `codex exec --profile vp-persona` process per persona. All personas use ONE uniform
  model+effort (from the role matrix); record the identities in `environment.json`.
- Browser state between personas: navigate to `http://localhost:5173` FIRST, clear that
  origin's `localStorage`/`sessionStorage` via `browser_evaluate` (clearing from
  `about:blank` cannot touch the app origin), then navigate away; note in the report
  that full profile isolation is approximated, not guaranteed.
- S1 (scent) contexts get ONLY the catalog page + docs index and must return a ranked
  pick list per question — including the explicit option "no catalog entry fits; I
  would <create my own / fork the closest / look in the docs / conclude the data or
  feature does not exist>" — no execution.
- PJ3's brief may include a **blinded aggregate** of S1 picks (per question: chosen
  slugs + confidence, no persona identities, no correctness info).
- PH gets a post-task verification phase (separate follow-up message to the same
  persona agent AFTER its navigation tasks are complete) in which source access is
  granted to check model↔code claims.
- Every persona subagent returns a structured task log (§8 schema) as its final output;
  you persist it under `test-results/usability/<RUN_ID>/logs/`.

## 6. Stages (each writes its artifact; each can run in a fresh context; report is
assembled only from artifacts)

- **S0 — Baseline & manifest**: inventory `--baseline`, environment.json, verify
  `/viewpoints` renders without console errors, note pre-existing `usability-*` or
  `*-copy` leftovers (report-only).
- **S0A — Oracles & preflight** (§4): oracles.json + fixture-validity table.
- **S1 — Blind catalog scent**: 12 isolated contexts, ranked picks (or "no fit +
  intended action") per question. Score afterwards (evaluator), **fit-kind-aware**:
  hit@1/hit@3 vs `candidate_routes` ONLY for questions whose
  `expected_catalog_action` is `execute`; for every other question score whether the
  persona recognized the correct **route class** (fork / create / consult-docs /
  recognize-fixture-gap / recognize-product-gap) — a confident near-fit pick on a
  non-execute question is a *false scent*, and "nothing fits, I'd build it" on a
  `create` question is a *hit*. All labels: synthetic hypothesis. After S1, finalize
  S_min **per persona-chosen route** (not per question) before any S2 context starts.
- **S2 — Core non-expert tasks**: personas PB, PF, PC, PE, then PA, PD, PG, PK, PL
  (fresh context each). Each S2 brief includes that persona's OWN S1 ranked list +
  confidence, labeled "your prior selections" — nothing else from S1 (no scores, no
  routes, no other personas). The persona executes its prior selections (walkthrough
  recording per §8), interprets results in character, and produces the question's
  decision_artifact content (a real slide bullet list / ticket text / evidence table —
  part of the record). Evaluator afterwards: probe the SAME executions (`--out` full
  JSON), judge adequacy AGAINST THE ORACLE (not against impressions), and record
  GUI↔engine consistency pairs.
- **S3 — Authoring & Save As**: each persona's authoring challenge (structured task
  objects with ids `<P>-A1`; preflight their `preconditions` in S0A like question
  preconditions — PC-A1 is known fixture-degraded and probes editor reachability only);
  same isolation; manifest every save; evaluator verifies each saved definition with a
  probe and, for forks, that the source definition's canonical hash is unchanged
  (baseline compare).
- **S4 — Architect/governance controls**: PH (with post-task source verification), PI
  (fixture-preflighted; audience variants evaluated by a fresh non-expert context, not
  by PI), PJ (PJ2 as inspection; PJ3 assessment-only with blinded S1 aggregate).
- **S5 — Invariant matrix, matched comparisons, heuristic passes**:
  - **Invariant matrix** (evaluator, GUI+probe): for each §6.1 invariant execute the
    listed check with a fixed slug/params/index-generation and record
    `Invariant ID | slug+params | generation | surfaces | expected pair | evidence
    (screenshot/DOM value + probe value) | pass/fail`.
  - **Matched comparison suite** (controls confounding): one fixed parameterless query
    rendered via exploration, diagram, table, matrix (where valid); one fixed impact
    question run anchored AND as an equivalent filter; fixed limits producing ≤10,
    100+, and truncated results; one module definition forked unchanged and compared;
    one simple definition built via Save As AND from blank. Only these matched cells
    support §9 variance claims; everything else is "cross-case observation".
  - **Heuristic passes**: TWO fresh evaluator contexts (blind to your findings so far;
    deliberately different model classes — Claude Code: `vp-heuristic-reviewer-a` +
    `vp-heuristic-reviewer-b`; Codex: profiles `vp-heuristic-a` + `vp-heuristic-b`)
    each sweep the surfaces against Nielsen's 10 with anchored severities (0 none, 1
    cosmetic, 2 minor/infrequent, 3 major/frequent or blocks a subtask, 4 blocks the
    task or corrupts understanding) and per-violation justification; you consolidate
    and de-duplicate. Label the whole exercise "independent expert passes (n=2, two
    model classes)". FMEA calibration uses `vp-fmea-calibrator` / profile `vp-fmea`.
- **S6 — Synthesis & cleanup**: report assembly from artifacts; then cleanup
  `--manifest <run-manifest> --baseline <baseline> --apply` (the helper refuses to run
  otherwise); then the whole-worktree restoration check from §1. Verification failure
  at either level = stop and ask. The report's final section states BOTH results
  (catalog/pins restoration and worktree restoration).

### 6.1 Invariants to verify (minimum set)
1. Same slug+params ⇒ equal counts in execution result, exploration header, diagram
   entity list, and probe — at the SAME index_generation (the probe now carries
   generation on both execution and projection and fails on a mid-pair change).
2. Every RENDERED style has a corresponding legend explanation (DOM fill → legend
   entry); an unused legend entry is acceptable and recorded, not a failure.
3. Anchor badge/halo appears ⇔ probe `anchor_ids` non-empty; badge names the anchor.
4. Every authored style rule reports exactly one of: applied to N≥1 items (probe
   per-item styles + DOM), valid-but-zero-matches (probe shows no item carrying it and
   the result set genuinely contains no matching item), unsupported-on-representation
   (validation error), schema drift (warning surfaced), or validation error. A rule
   with NONE of these observable outcomes is a silent no-op = failure.
5. Truncation flag in probe ⇒ visible disclosure on every surface showing the result.
6. Save As leaves the source definition's canonical hash unchanged.
7. GUI terminology for viewpoint concepts matches docs terminology (sample ≥5 terms).
8. Same execution repeated ⇒ same result at unchanged index_generation.

## 7. Failure decision table (include verbatim in persona briefs)

- API/UI failure (crash, 4xx/5xx, partial render, console exception): screenshot +
  console + failing request/status; retry ONCE with identical inputs; then mark the
  task **blocked** and move on. Never reload-loop, never restart anything.
- Empty-but-successful result: record it (screenshot + counts) BEFORE any next action;
  then you may try your next-ranked candidate if your action budget allows.
- Validation error or blocked save while authoring: record message verbatim; ONE
  correction attempt; then stop the task as **validation dead end**. Never bypass via
  API or files.
- You may execute at most your top-2 ranked viewpoints per question, within your
  numeric action budget (`max_task_actions` per question, `max_authoring_actions` for
  the challenge — from your brief). When a budget is exhausted, abandon and say why in
  one sentence; abandoning is a legitimate outcome.
- Anything that looks like data changing underneath you: stop and report immediately.

## 8. Recording: per-task structured log (persona output contract)

One JSON/YAML object per task:
`run_id, persona, task_id, started/finished (ordinal steps, not wall-clock), actions[]
(each: ordinal, kind ∈ {click, type+submitted-text, select, navigate, tab-switch},
target label, resulting page/panel), pages_visited[] (unique + revisits), dead_ends[]
(control tried + why rejected), errors[] (+recovery self-served?), outcome ∈ {success,
partial, fail, abandoned, blocked, validation-dead-end, fixture-invalid}, result_ref
(slug+params), adequacy_claim (fully/partially/no + what is missing), confidence
(act-on-it / verify-first / no), decision_artifact_content (the actual bullet list /
ticket text / table), simulated_utterance (illustrative only), deviation_notes`.

Definitions (fixed): an **action** = one click, one submitted text entry, one selection,
one navigation, or one explicit tab/panel switch. **N** = unique pages/panels visited,
**S** = shortest path for the persona's CHOSEN route (S_min per route, finalized by you
after S1 and before that persona's S2 context starts), **R** = total visits including
revisits; lostness L = sqrt((N/S−1)² + (R/N−1)²). Report L only as a synthetic
descriptor. Budgets are enforced in these ordinal actions — never wall-clock minutes.

Evidence protocol: all artifacts under `test-results/usability/<RUN_ID>/`; screenshots
named `<persona>-<task>-<step>-<surface>.png`; maintain `evidence.csv` (task, action
ordinal, URL, screenshot path, console/request artifact, claim supported). Capture:
task start, every failure/decision point, final result, recovery — not every click.

## 9. Findings register, FMEA, and recommendations

Register row:
`ID | Surface | Title | Evidence class (§2) | Evidence refs | Reproduced? (yes/once/
predicted) | Personas plausibly affected (hypothesis) | Heuristic | Failure mode |
Effect | Cause | Current control/detection cue | S | O | D | Confidence | Action
Priority | Recommendation`

FMEA calibration (anchored; score observed and predicted modes separately):
- **S** severity: 1 cosmetic; 3 slows a task; 5 task fails but user knows; 7 wrong/
  incomplete answer user may notice; 9–10 user confidently acts on a wrong answer or
  repository state is corrupted.
- **O** occurrence: rate task **exposure** (how often the triggering situation arises:
  1 exotic, 5 common task variant, 9 nearly every session) and mark frequency
  `observed n/N | estimated | unknown` — never infer frequency from one synthetic run.
- **D** non-detectability (likelihood user+existing cues FAIL to notice before acting):
  1 obvious error state; 5 noticeable only with attention (count mismatch in a corner);
  9–10 silently plausible (nothing distinguishes wrong from right).
- **Action Priority** (replaces RPN ranking): High = S≥9 (always, regardless of O), or
  S≥7 ∧ (O≥5 ∨ D≥7); Medium = S 5–8 with moderate O/D; Low = rest. RPN=S·O·D may be
  reported as a secondary sort only. Calibrate: score 3 sample findings, have ONE fresh
  evaluator context score the same 3 blind, adjudicate differences, then score the rest.

Recommendations must carry: named best practice; special circumstances where it does
NOT apply; the function/process/object/event concerned (ticket-ready:
component/route/domain object); plus triage fields `owner-component, dependencies,
estimate-band (S/M/L) + confidence, validation test` — effort bands are estimates, not
commitments.

## 10. Report — `REPORT-viewpoint-usability-stress-test.md`

1. Executive summary (≤1 page): top findings by Action Priority; explicit statement of
   what this session CAN claim (system facts, inspection findings) vs what needs human
   confirmation.
2. Method-as-executed + deviations log; isolation fidelity statement; run manifest ref.
3. Oracle table + fixture-validity results.
4. Scent study (S1) — labeled synthetic hypothesis.
5. Per-persona task records (from logs; include decision-artifact content) with
   oracle-based adequacy judgements.
6. Authoring/Save-As study; matched comparison suite; variance analysis (§ matched
   cells only) + cross-case observations; invariant matrix with evidence.
7. Heuristic consolidation (n=2 passes).
8. Findings register + FMEA (observed and predicted separated).
9. Recommendations: High/Medium/Low Action Priority; within High, quick wins vs
   substantial vs strategic (with triage fields).
10. Limitations (synthetic personas, single-model evaluator, fixture gaps, catalog
    scale) and the shortlist of hypotheses that most deserve a small human-validation
    round (scent, anchor finding, first useful result, Save As, result trust).
11. Cleanup & verified-restoration statement.

**Acceptance — Minimum Viable Test** (report labeled "partial" if anything below is
missing; "complete" requires all stages for all 12 personas):
PB, PF, PC, PE + one architect (prefer PJ) through S1–S3(S4); oracles for every question
actually run; invariant matrix complete; matched suite ≥ representation + anchored-vs-
filter cells; both heuristic passes; every executed adequacy claim probe-checked;
cleanup verified. Whatever is cut: name it in the deviations log; no holistic-coverage
claims in a partial report.

## Sequencing

S0 → S0A → S1 (all) → S2 in order PB, PF, PC, PE, PA, PD, PG, PK, PL → S3 → S4 → S5 →
S6. Stages are resumable: on context exhaustion, finish the current artifact, then a
fresh session continues from the artifacts — never from memory.
