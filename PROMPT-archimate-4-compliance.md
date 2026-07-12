# PROMPT — ArchiMate 4 Compliance Implementation Session

Reusable kickoff prompt. Paste everything below the line into a fresh agent session to
continue implementation. Re-usable across sessions: it derives all state from the
authoritative documents, never from prior conversations.

---

You are implementing the ArchiMate 4 compliance plan for this repository. Your authoritative documents are:

- `PLAN-archimate-4-compliance.md` — WHY and WHAT: locked decisions D1–D17, design
  evaluations, acceptance criteria. Decisions there are settled. Do not re-litigate,
  redesign, or "improve" them. If you believe a decision is impossible or wrong, STOP and
  record why in the ledger's Progress notes instead of working around it.
- `PLAN-viewpoints-query-model.md` — the **viewpoints companion plan**: the design
  authority for Phase E's pending WUs (E5*/E6a/E7*/E11–E17). It supersedes the parent
  plan's inner D15 query/presentation design. Bare §-references in those WUs (e.g. §3.4,
  §7.2, Appendix A/C) point into THIS document. Same rule: decisions are settled
  (go-reviewed after three review rounds) — implement, don't redesign.
- `TASKS-archimate-4-compliance.md` — the execution ledger: phases A–G, checkbox work
  units (WUs) with anchors, acceptance criteria, and dependencies. This file is your only
  memory between sessions. Where a WU's text and a plan disagree on detail, the WU's
  acceptance list wins; record the discrepancy in Progress notes.

## Session loop

Repeat until you must stop (see Stop conditions):

1. **Select**: read the ledger's "Resume protocol" and "Locked decisions" sections, then
   find the FIRST unchecked WU whose listed deps are all checked. Phases are ordered
   A → B → C → D → E → F → G, but any dep-satisfied WU is eligible — deps drive order,
   not file position (Phase E's foundation chain E11 → E13 → {E12, E14} → E15 → {E16, E7}
   sits *after* E5–E10 in the file). Skip WUs marked as gated/blocked (e.g. WU-F2+ before
   the WU-F1 sign-off is recorded; WUs whose stop condition awaits user review; WU-E17
   until the GUI builder ships). When several WUs are eligible, prefer the one that
   continues the chain you just finished — warm context beats a cold subsystem switch.
2. **Budget check**: estimate whether you can COMPLETE the WU — implementation, tests,
   quality gates, ledger update — within your remaining context. If not, do not start
   it. Write a handoff note (see Stop conditions) and end. A finished small WU beats a
   half-done large one, every time.
3. **Verify anchors**: the WU's file/line anchors are a snapshot. `rg` each symbol before
   editing. If an anchor moved, use the current location. If an anchor's code is
   materially different from what the WU assumes, STOP on that WU, record the discrepancy
   in Progress notes, and pick the next eligible WU.
4. **Implement** exactly what the WU says — its acceptance list is the definition of
   done. No scope creep; no drive-by refactors; if you notice adjacent problems, note
   them in Progress notes instead of fixing them.
   Work efficiently: the WU's anchors tell you where to look — do NOT survey the
   codebase, read whole modules "for context", or re-derive architecture the plans/ledger
   already state. Read only the files the WU touches plus their immediate call sites;
   use targeted `rg` for symbols, not broad exploration. Read plans selectively, never
   front-to-back: parent PLAN = §3 + the WU's section; **companion plan = ONLY the §§
   the WU cites**, plus, for any WU that writes tests, the matching Appendix C cluster
   (the WU's acceptance names it) — Appendix C is the required test matrix, its clusters
   map 1:1 onto WUs. For WU-E12 also read Appendix A in full (it is the canonical format
   the parser implements, and its examples are executable fixtures — fixture attribute
   profiles are spelled out verbatim there). One verification read of an anchor is
   enough — don't re-read files you just edited. Context spent exploring is context
   unavailable for completing the WU (step 2).
5. **Gate** (must ALL pass before ticking):
   - `python -m pytest --tb=short -q` → 0 failures
   - `ruff check src/ tests/` → 0 errors
   - `uv run zuban check` → pass
   - frontend WUs: `npm run lint` + `npm run typecheck` in `tools/gui`
   - after ontology/type changes: `uv run tools/generate_types.py`
   - after MCP tool-description changes: `uv run tools/generate_mcp_docs.py`
   Never tick a WU with a failing gate. Never weaken, skip, or delete a test to make a
   gate pass; fix the code, or un-tick and record the failure.
6. **Record**: change the WU's `- [ ]` to `- [x]`, and append ONE line to Progress notes:
   `YYYY-MM-DD — WU-xx — done — <one sentence: outcome + any surprise>`. If you deviated
   from an anchor or made a judgment call, say so in that line.
7. Go to 1.

## Hard rules (violations invalidate the work)

- **Principled solutions only.** Fix at the correct architectural layer; never route
  around a missing abstraction. When a facade/port lacks a method, add it — with a
  delegation unit test and a regression test.
- **Dependency policy**: domain imports domain only; application imports domain +
  application; adapters in infrastructure. `tests/architecture/test_dependency_policy.py`
  must not gain new violations.
- **All model (self-model) writes via MCP tools** — never edit files under
  `engagements/ENG-ARCH-REPO/` or `enterprise-repository/` by hand. If an MCP tool is
  wrong, fix the tool.
- **Backend reality**: MCP tools run against a long-running backend. Your code changes do
  NOT take effect there until the user restarts it (you cannot; it needs an SSH
  passphrase). When a WU needs a restarted backend, record "blocked on backend restart"
  in Progress notes and continue with non-MCP work.
- **Code style**: follow the repo's coding-guidelines standard (query
  `artifact_authoring_guidance` / search the arch-repo for "coding guidelines" once per
  session before writing code). Key points: ≤250 lines per Python file (350 hard), no
  `Any`, expressive types, expressions over statements, no phase names ("Phase C" etc.)
  in code/test content or filenames, all timestamps via `src/domain/clock.py`, no PDFs
  committed ever.
- **License rule (Phase B)**: the extracted guidance text must NEVER be committed to this
  repository — not in fixtures, not in tests, not in docs. Test fixtures use small
  synthetic guidance files.
- **History is immutable**: completed PLAN-*/TASKS-* ledgers of other efforts and
  superseded ADRs are records — never rewrite them.
- **Model authoring discipline** (Phase G): read `artifact_authoring_guidance` first;
  read every artifact before proposing changes to it; prefer enriching descriptions over
  adding connections, and connections over new entities; large connection batches can
  stall on the last 1–2 items — VERIFY with a read before retrying any write.
- **Viewpoints rework discipline (Phase E, WU-E11+)**: the old inner query/presentation
  shapes (`ExecutableViewpointQueryV1`, `ExpansionRule`, `EntityQueryFilter`,
  `IncludeConnectionsPolicy`, old `StyleRule`) are superseded — WU-E11 DELETES them; no
  back-compat shims, no parallel paths, no preserving their tests (rework the tests to
  the new shapes). The `ConceptScope`/definition/application/catalog machinery from
  WU-E1–E4 is load-bearing: do NOT touch it beyond what a WU explicitly says. Evaluation
  logic lives in exactly one place per contract: the WU-E14 evaluator, the WU-E15
  projection service, the WU-E15 summary renderer — GUI, verifier, REST, and MCP consume
  them; if you find yourself re-implementing matching/summary logic in a surface, stop —
  that is the wrong layer. Separate test files per component, as the ledger's WUs
  already assume.

## Stop conditions

End your turn (after writing the ledger + a short summary for the user) when:

- The next eligible WU has an explicit **user-review stop condition** that is not yet
  satisfied (WU-F1 sign-off, WU-G1a rubric review, WU-E5-UX design review — note E5-UX
  is a FULL REDO; its pre-redesign wireframe artifact is superseded and its review never
  happened — WU-G2a change-set review). State plainly what you need reviewed.
- **Remaining context cannot complete** the next WU end-to-end (step 2). Do NOT start
  and abandon work mid-WU.
- A gate fails and you cannot fix it within the WU's scope, an anchor discrepancy blocks
  the WU, or a locked decision appears infeasible — record it, then continue with a
  different eligible WU if one exists, else stop.
- All WUs are checked: run WU-G4's final sweep, then report completion against PLAN §11.

When stopping, always leave the ledger in a state from which a fresh session (with zero
conversation memory) can continue using only this prompt and the two documents: every
completed WU ticked, every discovery in Progress notes, no uncommitted half-done edits —
finish or revert partial work before ending.

## Start now

Read `TASKS-archimate-4-compliance.md`'s Resume protocol, Locked decisions, the Phase
sections with unchecked WUs, and the tail of Progress notes — then select. Read plan
sections only for the WU you selected (parent PLAN §3 at minimum; companion-plan §§ as
the WU cites them). Nothing else up front; open code files only once a WU is selected
and only as its anchors direct. Then execute the session loop.