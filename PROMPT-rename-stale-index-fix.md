# (Re-)entry prompt — Rename Stale-Index Fix implementation

Paste this to start or continue the work. It is idempotent: it always resumes from the first
incomplete task.

---

You are implementing the write-consistency / canonical-identity fix for this architecture-management
system. Authoritative docs (read in this order, only what you need):

1. `TASKS-rename-stale-index-fix.md` — the trackable checklist. **Task selection each session:** if a
   task is `[~]` (in-progress), resume it; otherwise pick the **first `[ ]` task whose `Deps` are all
   `[x]`**; report any `[!]` (blocked) tasks separately with their blocker and move on to the next
   eligible `[ ]`. Never spin on a `[!]` task while independent work is available.
2. `PLAN-rename-stale-index-fix.md` — condensed build spec (invariants INV-1..5, mechanisms M1..M6,
   workstream order, out-of-scope list).
3. `ANALYSIS-rename-stale-index.md` §6 + §6.6 — the design rationale and the crash-correctness proof.
   Consult only when a task references it.

Working rules:
- **Minimise codebase exploration.** Each task lists the exact files (with line anchors) to read and
  change. Read those; do not wander. If a referenced anchor has drifted, grep for the symbol named in
  the task, not the whole tree.
- **One task at a time, in order.** WS1–WS9 are one consistency unit and must all land before release;
  WS10–WS14 are independent. Respect each task's `Deps`.
- Set the task to `[~]` when you start, `[x]` when done; keep the `Progress:` line current.
- **Before marking `[x]`:** run `python -m pytest --tb=short -q` (0 failures), `ruff check src/ tests/`
  (0 errors incl. E501), `uv run zuban check` (pass). Write the task's named test file.
- Honour project doctrine: principled fix at the owning layer; `application/` must not import
  `infrastructure/` (`tests/architecture/test_dependency_policy.py`); central clock
  (`src/domain/clock.py`) for timestamps; ≤250 soft/350 hard LoC per Python file; "arch" naming.
- The identity switch (WS6) must be **atomic** — never leave a half-migrated equality relation across a
  commit boundary. **No data migration** (existing long ids already embed the short id).
- **Do not build** anything in the PLAN "Out of scope" list (deferred queue, generalized OCC, leasing,
  WAL platform). Offline/async is not a requirement; guaranteed write consistency is.
- Model writes go through MCP tools / the gate, never hand-edit model files. If the backend must be
  restarted to pick up changes, ask the operator (SSH passphrase required).
- Observe coding standards and guidelines (engagements/ENG-ARCH-REPO/architecture-repository/docs/standard/STD@1777137196.ItT-3l.general-coding-guidelines.md, enterprise-repository/model/motivation/requirement/REQ@1776423712.KG27vK.write-code-using-expressive-typing-where-available.md).

Start now: open `TASKS-rename-stale-index-fix.md`, report the selected task (per the selection rule
above) plus any blocked tasks, then implement the selected one. If there is sufficient context window token space left, you may proceed to the next work-item.
