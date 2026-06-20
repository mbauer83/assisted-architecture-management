# Orchestration prompt — implement the Datatype Type-Resolution plan via subagents

Paste the block below into a fresh session to drive (or resume) implementation. It is **idempotent and
resumable**: durable state lives in the `## Progress Log` of `TASKS-datatype-type-resolution.md`, so a new
orchestrator with empty context reconstructs where things stand from that section + the DAG embedded here.

---

You are the **orchestrator** for implementing `PLAN-datatype-type-resolution.md` via the
`TASKS-datatype-type-resolution.md` work units (WUs). You dispatch one implementer subagent per WU and
track progress. **You do not write code, read source files, or read PLAN/TASKS in full.** Your only
inputs are: this prompt (the DAG + rules) and the `## Progress Log` section of
`TASKS-datatype-type-resolution.md`. Keep your own messages terse; never echo subagent diffs or code.

## Context economy (hard rules)
- Never open source files or the full PLAN/TASKS. Implementers read what they need themselves.
- Per turn, read at most: the `## Progress Log` section of the TASKS file (use `Read` with an offset, or
  `grep -n "^- \[WU" TASKS-datatype-type-resolution.md`). Nothing else.
- Trust the gate contract: a WU is DONE only if its subagent reported all gates PASS **and** appended its
  Progress Log line + committed. If a report claims DONE without gates, treat it as NOT done and re-dispatch.
- Do not debug failures yourself. A BLOCKED/NEEDS-DECISION report → record it, dispatch the missing
  prerequisite if obvious, else surface to the user. Stay small.

## Durable state & resume protocol
On every invocation (including the first):
1. Ensure git is on branch `feat/datatype-type-resolution` (create off `main` if missing; never work on `main`).
2. Read the Progress Log. Each completed/blocked WU has a line in this exact format (implementers write it):
   `- [WU-x.y] DONE <iso-date> commit=<sha> — <≤12-word summary>`
   `- [WU-x.y] BLOCKED <iso-date> — <reason>`
3. Compute: `done` = WUs with a DONE line; `blocked` = WUs with a BLOCKED line and no later DONE.
4. `ready` = WUs not in done/blocked whose **every dep is in done**.
5. If `ready` is empty and `done` ≠ all WUs → stop and report the blockers to the user.
6. Else dispatch (below), collect reports, then loop from step 2.
7. When all WUs are DONE → run the final full gate once, post a one-paragraph summary, stop.

## Dependency DAG (WU → deps → lane)
Lanes are conflict domains; two WUs may run in parallel **only if their lanes differ**.
Lanes: `core`=domain+central-verification, `dt`=datatype module, `idx`=artifact_index+ports,
`write`=write/artifact_write(+promote), `fe`=tools/gui, `rt`=gui-router+mcp-tool, `tool`=one-off scripts,
`model`=MCP self-model.

| WU | deps | lane |
|----|------|------|
| 0.1 | — | core |
| 0.2 | 0.1 | dt |
| 0.3 | 0.1 | core+rt |
| 0.3b | 0.3 | write |
| 0.4 | 0.1, 0.2 | idx |
| 0.5 | 0.4 | core |
| 0.7 | 0.5 | core |
| 0.7b | 0.5 | core |
| 0.6 | 0.4, 0.5, 0.7b | core |
| 0.8 | 0.7 | dt |
| 1.1 | 0.3, 0.6 | write |
| 1.2 | 0.8 | dt |
| 1.3 | 0.5, 0.8 | dt |
| 1.4 | 1.3 | dt |
| 1.5 | 1.4 | dt |
| 1.6 | 1.4, 0.5 | dt |
| 2.1 | 1.2 | idx |
| 2.2 | 2.1 | idx |
| 2.3 | 1.4, 2.2 | dt+rt |
| 3.1 | 0.7b, 1.5, 2.2 | dt+write |
| 4.1 | 0.4 | write |
| 4.2 | 2.2, 3.1 | write |
| 5.1 | 1.2 | fe |
| 5.2 | 5.1, 2.3, 0.3 | fe |
| 5.3 | 5.2 | fe |
| 5.4 | 5.2 | fe+dt |
| F3 | 0.7, 1.3 | dt |
| 6.1 | 1.1,1.2,1.3,1.4,1.5,1.6,2.1,2.2,2.3,3.1 | tool+write |
| 7.1 | 6.1 | core |
| 8.1 | 7.1, F3, 5.4, 4.2 | model |

`F3` = GUI-plan F3 (datatype unique-constraints verifier as a contribution); its spec is the note beside
WU-5.4 in the TASKS file. On finishing 5.4 and F3, the implementer also ticks GUI-plan F2/F4 (in 5.4) and
F3 in `TASKS-gui-correctness-and-assurance.md`.

## Dispatch
- **Default: sequential.** Pick the lowest-numbered ready WU, dispatch one implementer, await its report,
  loop. This guarantees clean gates and trivial resume.
- **Optional parallel fast-path** (use only when you want speed): from `ready`, pick a set whose lanes are
  **pairwise disjoint**, max 3. Dispatch each with `isolation: "worktree"`, instructing it to commit to a
  child branch `feat/dtr-wu-<id>` and report the branch. Then **integrate sequentially**: for each
  returned branch, `git merge --no-ff` it into `feat/datatype-type-resolution`, run the full gate; on
  conflict or gate failure, abort that merge and re-dispatch the WU sequentially in the main tree. The
  highest-value disjoint window is after P1 completes: chain `{2.1→2.2→2.3}` (idx/rt) ∥ `{4.1}` (write) ∥
  `{5.1}` (fe).
- Use `subagent_type: "general-purpose"` (fresh context). Pass the implementer template below with the
  WU id substituted. Do not use `fork` (you want small, fresh contexts, not your context copied).

## Human checkpoints (pause and ask the user; do not attempt yourself)
- **WU-6.1 migration**: after the implementer produces the dry-run report, surface it and get explicit
  go-ahead before the apply step (it rewrites real model/diagram files in ENG-ARCH-REPO + ENG-001).
- **WU-8.1 self-model**: needs the implemented backend running + MCP write tools; requires a backend
  restart (user does it; SSH passphrase) and possibly a Claude session restart for MCP-surface changes
  (WU-2.3 added a tool). Hand off to the user to restart, then run 8.1 (or have the user run it).
- If any implementer returns NEEDS-DECISION, relay the question to the user before proceeding.

## Implementer subagent prompt (substitute {WU})
> You are implementing exactly one work unit, **{WU}**, of `TASKS-datatype-type-resolution.md` in
> `/home/mb/workspace/scalable-architecture-for-humans-and-ai`. Work only on git branch
> `feat/datatype-type-resolution` (it already exists). Scope discipline: implement {WU} and nothing more.
>
> 1. Read: the `### {WU}` section of `TASKS-datatype-type-resolution.md`; the **Appendix A** anchors it
>    cites; only the PLAN `§`/decisions {WU} references in `PLAN-datatype-type-resolution.md`; and
>    `CLAUDE.md` once. Do **not** read the whole PLAN/TASKS.
> 2. Open only the files the WU + Appendix A name. Minimal extra exploration — if a line anchor drifted,
>    `grep` the named symbol; don't survey the codebase. Do not refactor beyond the WU.
> 3. Implement the WU's **Do** steps. Obey project rules: Python files ≤250 soft/350 hard LoC (md exempt);
>    `ruff` incl. E501; `zuban` strict; **never hand-edit model files** (model changes go through MCP, but
>    {WU} should not need them unless it is WU-8.1); choose the principled fix at the right layer, never a
>    workaround; add the unit + regression tests the WU lists.
> 4. Gates (fix until all green): `uv run pytest --tb=short -q` → 0 failures; `ruff check src/ tests/` → 0;
>    `uv run zuban check` → pass. If you touched `tools/gui`, also `cd tools/gui && npm run lint && npm run
>    typecheck`. If the WU changed the ontology/types, run `uv run tools/generate_types.py`.
> 5. On all-green: append exactly one line to the `## Progress Log` of `TASKS-datatype-type-resolution.md`:
>    `- [{WU}] DONE <today> commit=<pending> — <≤12-word summary>`, then `git add -A && git commit -m
>    "{WU}: <summary>"` and replace `<pending>` with the short sha in a follow-up amend (or commit the log
>    line in the same commit and report the sha).
>    (Parallel mode only, if told: first `git switch -c feat/dtr-{WU}` and commit there; report the branch.)
> 6. Report back in this schema **only** (≤12 lines, no diffs, no code):
>    ```
>    WU: {WU}
>    STATUS: DONE | BLOCKED | NEEDS-DECISION
>    GATES: pytest=PASS|FAIL ruff=PASS|FAIL zuban=PASS|FAIL [npm=PASS|FAIL|n/a]
>    COMMIT: <sha>  (BRANCH: <name> if parallel)
>    FILES: <n> changed
>    DISCOVERED-DEPS: none | <WU/file that must change first>
>    DEVIATIONS: none | <what differed from the WU spec and why>
>    FOLLOWUPS: none | <small leftover>
>    NOTES: <≤2 lines the next WUs/orchestrator need>
>    ```
> If you cannot make gates pass, or find a missing prerequisite, contract gap, or genuine ambiguity:
> **stop, do not hack around it, do not weaken a test**, leave the tree clean (or committed-but-flagged),
> and report STATUS: BLOCKED / NEEDS-DECISION with the specific reason and what would unblock it.

## After each report
- Parse the schema. If DONE + gates PASS + a Progress Log line exists → continue.
- If DISCOVERED-DEPS names a real prerequisite not in the DAG → record it as a BLOCKED note on {WU} and
  dispatch the prerequisite (or escalate). Update the DAG note in your working memory; the durable record
  is the Progress Log.
- If BLOCKED/NEEDS-DECISION → write a BLOCKED line to the Progress Log (one `Edit`), then surface to the user.
- Then loop (recompute ready set; dispatch next). Keep going autonomously through DONE WUs; only pause at
  the human checkpoints above or on BLOCKED/NEEDS-DECISION.

## Completion
When every WU in the DAG has a DONE line: run `uv run pytest --tb=short -q`, `ruff check src/ tests/`,
`uv run zuban check`, and `cd tools/gui && npm run lint && npm run typecheck` once; report a one-paragraph
summary (WUs done, any deviations/followups, branch ready for review). Do not merge to `main` or open a PR
unless the user asks.
