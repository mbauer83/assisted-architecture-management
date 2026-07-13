/goal: Implement PLAN-viewpoints-bindings-and-derived-relationships.md to completion by
  executing its ledger TASKS-viewpoints-bindings-and-derived-relationships.md, WU by WU,
  until the ledger's "Plan exit condition (definition of done)" is fully satisfied.

  SETUP (once per session/resume):
  1. Read TASKS-viewpoints-bindings-and-derived-relationships.md in full — the Resume
     protocol, Release cut, Naming checklist, and exit condition are binding.
  2. Read PLAN-viewpoints-bindings-and-derived-relationships.md §3 (locked decisions
     D1–D12) and skim the section map. Never re-litigate locked decisions; when a WU cites
     a PLAN section, read that section in full before writing code.
  3. Read PLAN-viewpoints-query-model.md §3.4 and §7.2 before touching evaluation or
     validation code. Read spec/viewpoints/appendix-b-relationships-derivation.md in full
     before any Phase-B WU.
  4. Run `uv sync --all-groups`, then the three quality gates once to confirm a green
     baseline before the first WU.

  WORK LOOP — repeat until exit condition or hard block:
  1. SELECT: the first unchecked WU (ledger order) whose listed Deps are ALL ticked.
     Dependency metadata is the only gate authority — never start a WU with an unticked
     dep, even if it "looks independent". Respect the release cut: prefer finishing the
     current release before starting the next.
  2. VERIFY ANCHORS: `rg` every file/symbol the WU names. If an anchor moved, adapt and
     record the deviation; if the WU's premise no longer holds, re-expand the WU in the
     ledger (edit it) before implementing — the PLAN contracts are the invariant, anchors
     are a snapshot.
  3. IMPLEMENT exactly the WU's Changes, honoring: role-functional naming (spec ids only
     in spec_ref data/pytest case ids); no phase/WU/plan-§ references in code, tests,
     docstrings, or filenames; 250/350 LoC; no `Any`; src/domain/clock.py for all time;
     frozen dataclasses for value objects; test files per component.
  4. ACCEPT: implement every item in the WU's Acceptance as real tests/checks — an
     acceptance bullet without a corresponding executed verification is not satisfied.
     Then run ALL gates: `uv run pytest --tb=short -q` (0 failures), `uv run ruff check
     src/ tests/` (0 errors), `uv run zuban check` (pass); frontend WUs also lint/
     typecheck/vitest in tools/gui; regenerate types/MCP docs when the WU touches them.
     Run `rg -i "WU-|phase [a-i]\b|companion plan" src/ tests/ tools/gui/src/` — must be
     clean.
  5. CLOSE: tick the WU checkbox; append EXACTLY ONE progress-note line
     (`date — WU-id — outcome`), two lines max and only for genuine deviations; commit the
     WU as one commit (conventional message naming the feature, not the phase). Then loop.

  SPECIAL RULES:
  - WU-B6 dual encoding: author the independent fixture directly from the spec file,
    literal data only, BEFORE re-reading your own runtime rule tables; the no-import
    structural test is the enforceable condition. Record transcriber+reviewer in the
    ledger note. B6 gates every engine consumer — do not proceed past it on failure.
  - MCP/self-model WUs: all model writes via arch-repo-write tools only. If tools error
    because the backend needs a restart, do NOT retry-hammer: note "blocked on backend
    restart" in the ledger, skip to the next non-MCP WU, and ask the user for a restart
    only when no unblocked WU remains.
  - Phase H is gated on the concurrent frontend rewrite. If the rewrite is not stable when
    you reach it, do NOT implement against the old components: write a dated re-gate note
    in the ledger and continue with Phase I (I1–I4 may trail; the exit condition permits
    Phase H as the only outstanding phase, explicitly re-gated).
  - If a WU exposes a genuine design gap (not an anchor drift), stop that WU, write the
    problem + proposed resolution into the ledger's Progress notes, and ask the user —
    do not improvise around a locked decision.

  EXIT — stop and report ONLY when the ledger's "Plan exit condition (definition of done)"
  holds: (1) all WUs A–G and I ticked, Phase H ticked or explicitly re-gated with a dated
  note; (2) every Global-acceptance and Consistency-invariant checkbox ticked with a named
  test/suite or recorded verification step; (3) the WU-I5 dogfood sweep passed against a
  restarted backend on a recorded date. Your final report: releases shipped, WUs ticked,
  any re-gated/blocked items, and the WU-I5 evidence — concise, no play-by-play.