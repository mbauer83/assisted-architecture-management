# TASKS — MCP Write-Tooling Optimization

Execution ledger for `PLAN-mcp-write-tooling-optimization.md`. Checkbox work-units with file
anchors, acceptance criteria, deps, resume protocol. Markdown — no LoC limit.

## Locked decisions (see PLAN)
- D1 No server split; one `arch-repo-write`.
- D2 FOUR focused tools (not a `mode` multiplexer), each thin MCP adapter over the existing
  `_diagram_binding_modes` handlers / `application/derivation` use cases, with exact params +
  accurate annotation.
- D3 Trim descriptions of explanatory prose ONLY; keep all safety/selection-critical semantics.
- D4 Explicit breaking change + full migration; NO compatibility shim (single-owner, agent
  re-discovers, REST unaffected).
- D5 Don't touch healthy servers. D6 MCP-only scope (REST extension = follow-up). D7 No render_options.

## Tool map (old `mode` → new tool / annotation)
| New tool | mode | annotation | required params | handler |
|---|---|---|---|---|
| `artifact_propose_diagram_bindings` | propose-bindings | READ_ONLY | artifact_id, entity_ids?/connection_ids? | `_propose_bindings` |
| `artifact_refresh_diagram_derivation` | refresh-derivation | READ_ONLY | artifact_id, derivation_id | `_refresh_derivation` |
| `artifact_apply_diagram_derivation_diff` | apply-diff | LOCAL_WRITE | artifact_id, diff, base_revision, dry_run | `_apply_diff` |
| `artifact_detach_diagram_binding` | detach-binding | DESTRUCTIVE_LOCAL_WRITE | artifact_id, binding_id, dry_run | `_detach_binding` |

## Anchors (snapshot 2026-06-22)
- `artifact_edit_diagram` fn `src/infrastructure/mcp/artifact_mcp/edit_tools.py:156`; `mode`
  dispatch branch `:184-191`; registration `:345`.
- Handlers (reuse, unchanged): `src/infrastructure/mcp/artifact_mcp/_diagram_binding_modes.py`
  (`_propose_bindings`, `_refresh_derivation`, `_apply_diff`, `_detach_binding`).
- Transport-neutral use cases: `src/application/derivation/refresh.py`,
  `src/application/derivation/binding_proposals.py`.
- `artifact_create_diagram` fn `src/infrastructure/mcp/artifact_mcp/write/diagram.py:64`;
  registration `:177`.
- Annotations `src/infrastructure/mcp/artifact_mcp/tool_annotations.py`
  (`READ_ONLY`, `LOCAL_WRITE`, `DESTRUCTIVE_LOCAL_WRITE`).
- Description test `tests/tools/test_mcp_tool_descriptions.py`; server builder
  `src/infrastructure/mcp/mcp_artifact_server.py` (`mcp_write`).
- Docs to migrate: `docs/03-modeling/interfaces-and-mcp.md`, `docs/03-modeling/diagramming.md`,
  `docs/03-modeling/projects-and-grouping.md`, `docs/04-assurance/gui-capability-design.md`.

---

## Work units

- [ ] **WU-1 Migration inventory (active surfaces only)** — `rg` (not partial grep) for the old
  surface (`artifact_edit_diagram`, `mode=`, `propose-bindings|apply-diff|detach-binding|
  refresh-derivation`). **"Stale" = an *active* executable, test, current doc, skill, query-tool
  description, source docstring/comment, or *current* design reference** — explicitly:
  `CLAUDE.md`, `skills/**` (incl. `skills/architecture-modelling/SKILL.md` + `references/`),
  source descriptions/docstrings, the four `docs/03-modeling|04-assurance` pages, `.claude`
  permission allowlist, and the live MCP tool descriptions. **NOT stale:** completed PLAN-*/TASKS-*
  ledgers and other historical implementation records — these are history and MUST NOT be
  rewritten (corrupts the record); where one could be mistaken for *current* guidance, add a brief
  supersession note instead. Produce the checklist for WU-6. (REST confirmed not to expose these.)

- [ ] **WU-2 Add the four tools** in a dedicated `diagram_binding_tools.py` (not `edit_tools.py`,
  whose pattern queue-wraps everything). Each is a thin function with EXACT required params (table
  above) delegating to its existing `_diagram_binding_modes` handler; no `action`/`mode`
  discriminator. **Registration discipline:** register the READ_ONLY tools (propose, refresh)
  **unqueued**; wrap only the mutation tools (apply, detach) with `queued(...)`. Add a runtime
  guard in `propose` requiring ≥1 non-empty of `entity_ids`/`connection_ids`. Acceptance: each tool
  callable + routes to the same handler; propose/refresh do NOT enter the write queue (no worker
  consumption, not blocked by write-blocks, no write-completed notification); apply/detach do.

- [ ] **WU-3 Slim `artifact_edit_diagram`** — remove `mode`, `derivation_id`, `diff`,
  `base_revision`, `entity_ids`, `connection_ids`, `binding_id` and the `:184-191` dispatch
  branch. Keep content/frontmatter params incl. declarative `bindings` and `puml='auto-sync'`.
  Acceptance: schema ≤14 params, no binding-lifecycle params; content-edit + auto-sync unchanged.

- [ ] **WU-4 Descriptions (D3)** — revise `edit_diagram` + `create_diagram` descriptions:
  remove only redundant prose; **retain** TLP/confidential-storage consequences, `auto-sync`
  deletion behaviour, the three create authoring forms, `connection_inference`, `edge_labels`
  clearing, binding normalization. Add concise per-tool descriptions for the four new tools.

- [ ] **WU-5 Annotation audit** — confirm each new tool's annotation matches its real effect;
  verify `tool_annotations.py` has `DESTRUCTIVE_LOCAL_WRITE` (add if missing) for detach.

- [ ] **WU-6 Execute migration** (active surfaces from WU-1): update the four docs pages,
  `CLAUDE.md`, `skills/**` (SKILL.md + references), source docstrings/query-tool descriptions, the
  `.claude` permission allowlist, and add a CHANGELOG/release note with the old→new mapping.
  **Self-model:** do a *model impact assessment via MCP first* (the self-model does not enumerate
  individual MCP tools) — update only abstractions whose statements become false or materially
  incomplete; do NOT add a model element per tool; finish with `artifact_verify` on ENG-ARCH-REPO.
  Acceptance: no *active* stale reference remains; historical ledgers untouched (supersession note
  only where they could read as current guidance).

- [ ] **WU-7a Characterization tests (BEFORE WU-2/WU-3)** — pin current behaviour of the four
  `_diagram_binding_modes` handler paths while the old `mode` surface still exists: propose &
  refresh (read-only, no write); apply (dry-run vs commit, stale-revision conflict, manual-binding
  preservation, verifier-failure + cache finalization); detach (missing-id → not-found, destructive
  removal). These are the parity baseline. (Dep: must land before the surface change.)

- [ ] **WU-7b MCP-adapter tests (AFTER WU-2/WU-3)** — per new tool: schema, annotation, output
  schema, dry-run/write/conflict/failure, and **queueing** (propose/refresh unqueued; apply/detach
  queued). Result-parity against WU-7a where applicable. No brittle golden outputs.

- [ ] **WU-8 Contract manifest (normalized) + semantic invariants** — build a normalized manifest
  of `arch-repo-write` (normalize property order + nullable representation), then assert semantic
  invariants: required params, enums, per-tool annotations, and presence of the D3 critical
  description phrases. Do NOT byte-snapshot full descriptions/schemas. Assert `arch-repo-read` +
  assurance surfaces unchanged (names + required-param/annotation invariants).

- [ ] **WU-9 QC** — `python -m pytest --tb=short -q`, `ruff check src/ tests/`, `uv run zuban check`.

- [ ] **WU-10 (optional, non-blocking) agent-task benchmark** — a handful of representative
  tasks (create / edit / auto-sync / propose / refresh / apply / detach); record valid-first-call
  rate, completion, repair turns vs. a pre-change baseline; bar = no regression. Skip if
  disproportionate.

**>>> session restart required for the new MCP surface; then WU-11 <<<**

- [ ] **WU-11 Post-restart live smoke** (manual, one pass) — exercise the four new tools + an
  `edit_diagram` content edit/auto-sync via live MCP; confirm parity with pre-change behaviour.

## Resume protocol
1. Read this ledger + PLAN. 2. `git status` / `git diff --stat`. 3. First unchecked WU; verify
prior WUs by acceptance criteria. 4. The four `_diagram_binding_modes` handlers + the
`application/derivation` use cases stay behaviourally unchanged — this is a surface
decomposition + migration only. 5. MCP surface changes need a backend + Claude session restart
(WU-11). 6. Run QC (WU-9) before declaring done.

## Progress log
- 2026-06-22: PLAN + ledger created. Server split rejected (D1). Initial draft used a single
  `bind_diagram(action=...)`; revised (review round 1) to four focused tools (D2),
  breaking-change migration (D4), description safety-retention (D3), automated tests,
  render_options dropped (D7), REST-parity claim corrected (D6).
- 2026-06-22 (review round 2): structural-correctness claim narrowed to the four extracted ops +
  `propose` ≥1-input guard (create-form exclusivity = follow-up); READ_ONLY tools registered
  **unqueued** in a dedicated `diagram_binding_tools.py` (propose/refresh must not enter the write
  queue); migration redefined to *active surfaces only* (history preserved, not rewritten) +
  enumerated CLAUDE.md/skills/docstrings; self-model = impact-assessment-first; characterization
  tests moved BEFORE the rewrite (WU-7a/7b); contract test = normalized manifest + semantic
  invariants (not byte-exact); layering claim corrected (apply/detach orchestration still in MCP
  glue — extraction is a follow-up). No code changes yet; assessed implementation-ready.
