# Executing the viewpoint usability stress test — harness setup

How to run `PROMPT-viewpoint-usability-stress-test.md` with the intended mixed
model-class / reasoning-effort assignment, on either harness. The role→model matrix is
the same everywhere:

| Role | Claude family | GPT-5.6 family | Effort | Isolation mechanism |
|---|---|---|---|---|
| Orchestrator / evaluator | Fable 5 | Sol | high (xhigh for S0A oracles + S6 synthesis) | main session |
| ALL persona contexts (S1–S4) | Opus 4.8 | Terra | medium — **uniform across personas, never varied** | fresh subagent / fresh process |
| Heuristic pass A | Fable 5 | Sol | high | fresh subagent / fresh process |
| Heuristic pass B | Opus 4.8 | Terra | high | fresh subagent / fresh process |
| FMEA calibration scorer | Opus 4.8 | Terra | high | fresh subagent / fresh process |
| Sonnet 5 / Luna tier | — | — | — | mechanical glue only; never personas or judgement |

Record the exact model identity per role in `environment.json` (the run manifest
requires it); model uniformity across personas is a validity requirement, not a
preference — a mid-run model change breaks every cross-persona comparison.

Prerequisites (both harnesses): backend on :8000 **restarted on current code** (the
probe must report `generation_consistency: same-snapshot`, not "unverifiable"),
frontend dev server on :5173, Playwright browser automation available, and the four
files consistent with each other: the PROMPT, `spec/personas/personas.yaml`,
`tools/usability_test/*.py`, and this directory's configs.

---

## Claude Code

The role definitions already exist as project subagents (checked in):

- `.claude/agents/vp-persona-runner.md` — `model: opus`, `effort: medium`, tools
  restricted to `Read` + Playwright only (no Bash/Write/MCP-arch tools: the isolation
  and no-writes rules are enforced by the tool allowlist, not just by prompt text).
- `.claude/agents/vp-heuristic-reviewer-a.md` — `model: fable`, `effort: high`.
- `.claude/agents/vp-heuristic-reviewer-b.md` — `model: opus`, `effort: high`.
- `.claude/agents/vp-fmea-calibrator.md` — `model: opus`, `effort: high`, Read-only.

Run it:

1. Start a **fresh** session in this repo: `claude --model fable --effort high`
   (or `/model fable` + `/effort high` inside the session).
2. First message: `Execute PROMPT-viewpoint-usability-stress-test.md as the
   orchestrator/evaluator. Use the vp-* subagent types for persona, heuristic, and
   calibration contexts as specified in tools/usability_test/EXECUTION.md.`
3. The orchestrator spawns personas via the Agent tool with
   `subagent_type: "vp-persona-runner"`, passing ONLY the composed brief
   (`uv run python tools/usability_test/compose_persona_brief.py <ID>`) plus the §7
   failure table, §8 recording rules, and (for S2+) that persona's own S1 selections.
   Custom subagents start with a clean context (no conversation inheritance) — this is
   the zero-history spawn the plan requires. Never use a fork.
4. Heuristic passes: `subagent_type: "vp-heuristic-reviewer-a"` and `"-b"`; FMEA
   calibration: `subagent_type: "vp-fmea-calibrator"`.
5. For S0A and S6 the orchestrator may switch itself to `/effort xhigh`, returning to
   `high` afterwards (note the switch in the deviations log).
6. Model/effort per role must NOT be overridden at spawn time (`model:` parameter on
   the Agent call) — the definitions are the single source of truth.

Caveat: all Claude Code subagents share one Playwright MCP browser. The prompt's
storage-clearing step between personas is the mitigation; record this as
"approximated isolation" in the report (the prompt already requires that).

## Codex CLI (GPT-5.6 family)

1. Merge `tools/usability_test/codex-profiles.toml` into `~/.codex/config.toml` and
   substitute the real GPT-5.6 model ids (Sol/Terra) for your tenant. Verify key names
   against your `codex --help` version (see the caveat in that file).
2. Orchestrator (interactive): from the repo root,
   `codex --profile vp-orchestrator`
   with the same first message as above (steps/stage logic is harness-neutral).
3. Isolated contexts are **separate processes** — Codex has no in-session subagent
   registry, and that is fine: a fresh `codex exec` process is a stronger zero-history
   guarantee, and each process spawns its own Playwright MCP server → own browser
   (better than shared-browser isolation; note it in the report). The orchestrator
   shells out per persona:

   ```bash
   uv run python tools/usability_test/compose_persona_brief.py PB > /tmp/vp-brief-PB.md
   cat /tmp/vp-brief-PB.md /tmp/vp-protocol.md \
     | codex exec --profile vp-persona --skip-git-repo-check \
         --output-last-message test-results/usability/$RUN_ID/logs/PB-s2.md -
   ```

   where `/tmp/vp-protocol.md` contains the §7 failure table + §8 recording rules +
   run-prefix rule (and, for S2, that persona's own S1 selections). `sandbox_mode =
   "read-only"` enforces that personas cannot write files or run repo commands; their
   log comes back as the final message.
4. Heuristic passes: `codex exec --profile vp-heuristic-a - < surfaces-and-anchors.md`
   (likewise `vp-heuristic-b`); FMEA calibration via `--profile vp-fmea` with the
   sample findings embedded in stdin.
5. Effort bump for S0A/S6: run those orchestrator phases with
   `-c model_reasoning_effort=xhigh` (or a dedicated profile), and log the switch.
6. The persona GUI save steps (S3, and any S2 execution that saves) need write access
   to the *backend via the browser*, which read-only sandboxing does not block (it is
   an HTTP call from the browser, not a file write) — the run-prefix + manifest rules
   from the prompt still apply verbatim.

## Shared rules regardless of harness

- One harness for the WHOLE run — do not mix Claude Code and Codex within a run; a
  cross-harness comparison would be a separate study with its own manifest.
- Personas: same profile/agent, same model, same effort, all twelve. If you must
  change anything mid-run, abort and restart the run.
- The report must state, per role: harness, model id, effort, and (for Claude Code)
  that browser isolation was approximated / (for Codex) per-process browsers.
