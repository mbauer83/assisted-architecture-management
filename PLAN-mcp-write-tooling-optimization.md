# PLAN — MCP Write-Tooling Optimization

## Context

A review of the MCP tool surface (66 tools across four servers) found three servers healthy
(`arch-repo-read`, `arch-assurance-read`, `arch-assurance-write` — small parameter lists,
concise descriptions, clear DSL) and one hot spot: **`arch-repo-write`**, driven by two
diagram tools:

- `artifact_edit_diagram` — **21 parameters**, with a `mode` discriminator multiplexing four
  binding/derivation operations onto content/frontmatter editing. The four operations have
  *different safety semantics* (two read-only, one modifying, one destructive — see
  `src/infrastructure/mcp/artifact_mcp/_diagram_binding_modes.py`), so a single tool cannot
  carry accurate MCP `readOnlyHint`/`destructiveHint` annotations.
- `artifact_create_diagram` — **19 parameters, 1923-char description**.

### Why this shape (current best-practice basis)

The relevant shift is **dynamic tool discovery / MCP Tool Search** — which this harness uses
(deferred tools + `ToolSearch`). It replaces the `tools/list` upfront dump with on-demand
loading, keeping upfront cost roughly constant as tool count grows. Consequences:

- **Tool *count* is no longer the primary lever** — making a few extra *focused* tools cheap.
- **Per-tool correctness/clarity is the lever**: exact (non-conditional) parameters, accurate
  tool-level safety annotations, and names/descriptions that drive correct tool selection.
  (Tool-level `readOnlyHint`/`destructiveHint`: MCP Tools spec, 2025-06-18.)

### Locked decisions

- **D1 — Do NOT split `arch-repo-write` into `…-write-model` + `…-write-diagram`.** Server
  boundaries pay off only for *differential* loading/gating (as the gated assurance server
  shows); model- and diagram-writes are always co-needed, and dynamic discovery removes the
  upfront-cost motive. A split would add process/registration overhead and fragment workflows.
  The principled trigger for a new server is a capability/gating boundary, not sub-domain tidiness.

- **D2 — Decompose by responsibility into FOUR focused tools, not one mode-multiplexer.**
  Correctness by construction: each tool gets exactly its required parameters (no
  conditionally-relevant params, no structurally-valid-but-invalid combinations), a precise
  name, and an accurate safety annotation. Each is a thin MCP adapter over the existing handler
  in `_diagram_binding_modes.py` (which already wraps the transport-neutral use cases in
  `src/application/derivation/`):

  | New tool | From mode | Annotation | Required params |
  |---|---|---|---|
  | `artifact_propose_diagram_bindings` | propose-bindings | READ_ONLY | artifact_id, (entity_ids/connection_ids) |
  | `artifact_refresh_diagram_derivation` | refresh-derivation | READ_ONLY | artifact_id, derivation_id |
  | `artifact_apply_diagram_derivation_diff` | apply-diff | LOCAL_WRITE | artifact_id, diff, base_revision |
  | `artifact_detach_diagram_binding` | detach-binding | DESTRUCTIVE_LOCAL_WRITE | artifact_id, binding_id |

  `artifact_edit_diagram` then sheds `mode` + all seven binding/derivation params (21 → ~14),
  becoming a pure content/frontmatter editor (keeps `puml` incl. `auto-sync`, `diagram_entities`,
  `diagram_connections`, `view_derivations`, declarative `bindings`, frontmatter, `edge_labels`).

  **Registration discipline:** the two READ_ONLY tools (propose, refresh) are registered
  **unqueued** — they must NOT pass through the single-worker write queue (`queued(...)`), or they
  would consume the write worker, surface as active writes, be rejected by write-block checks, and
  fire write-completed notifications. Only the two mutation tools (apply, detach) are `queued`.
  This argues for a dedicated `diagram_binding_tools.py` with separate read/mutation registration
  rather than reusing `edit_tools.py`'s queue-wrapping pattern.

  **Layering accuracy:** propose and refresh delegate to transport-neutral use cases in
  `src/application/derivation/` (`binding_proposals.py`, `refresh.py`). apply and detach
  *orchestration* (parse file → construct verifier → invoke the infra writer) currently lives in
  the MCP glue (`_apply_diff`/`_detach_binding`); extracting those into application services is a
  noted follow-up (D6), not part of this surface-only change.

- **D3 — Trim descriptions of explanatory prose ONLY; never of safety- or selection-critical
  semantics.** The following MUST remain in the (still-concise) tool descriptions because
  `artifact_authoring_guidance` is diagram-type-specific and does not carry generic tool
  semantics: TLP/confidential-storage consequences, `auto-sync` deletion behaviour, the three
  mutually-exclusive create authoring forms (`entity_ids` | `puml` | `diagram_entities`),
  `connection_inference` behaviour, `edge_labels` clearing semantics, and binding normalization.
  Only redundant explanation is removed. (Future direction, not this change: a common
  diagram-authoring contract that generates both guidance and descriptions from one source.)

- **D4 — Explicit breaking change with full migration; no compatibility shim.** Justification:
  this is a single-owner deployment with no external API consumers; the only MCP client is the
  agent, which re-discovers tools each session; the GUI uses REST, which does **not** expose
  these operations (verified — no REST caller of the derivation/binding use cases). A shim would
  also retain the binding params on `edit_diagram`, defeating the decomposition. Instead: remove
  cleanly and migrate every reference (code, tests, docs, skills, self-model, changelog). The
  self-model + interface docs ARE the migration record this repo requires. (A deprecation shim
  was considered and rejected on the above grounds.)

- **D5 — Do not touch the healthy servers/tools** (`arch-repo-read`, assurance read/write).

- **D6 — These derivation/binding operations are MCP-only today, with partial application-layer
  factoring.** `_diagram_binding_modes.py` is MCP-adapter glue, NOT a REST-shared service.
  *propose* and *refresh* compute via transport-neutral use cases in `src/application/derivation/`
  (`binding_proposals.py`, `refresh.py`); *apply* and *detach* orchestration (file parse +
  verifier + infra writer) currently lives in the MCP glue. Two noted **follow-ups**, both out of
  scope here: (a) extract apply/detach orchestration into application services; (b) expose REST
  equivalents adapting the same use cases. (Corrects the earlier, unsupported "shared helper /
  REST parity" claim and the overstated "all four wrap transport-neutral use cases".)

- **D7 — Drop `render_options`.** Grouping three typed params into an object is speculative
  (no evidence they cause failures), adds nesting, and creates another breaking contract. Keep
  this change focused on responsibility decomposition + contract quality.

## Success criteria (what "optimal" means here)

Replaces the earlier arbitrary character budget. Hard gates:

1. **Structural correctness (scoped to the four extracted operations):** none of the four new
   tools carries a param that is relevant only for a *different* operation — every cross-operation
   invalid combination from the old `mode` design (e.g. `detach` + `diff`, `refresh` without
   `derivation_id`) is now *unrepresentable* by construction. Within `propose`, both ID lists are
   optional, so it MUST add a runtime guard requiring at least one non-empty list. NOT claimed:
   exclusivity of `create_diagram`'s three authoring forms (currently precedence, not enforced —
   `entity_ids` used only when `puml` is empty); enforcing that is a recorded **follow-up**, since
   `create_diagram` is not being decomposed here.
2. **Annotation accuracy:** each tool carries the correct tool-level safety hint
   (READ_ONLY / LOCAL_WRITE / DESTRUCTIVE_LOCAL_WRITE) per the table above.
3. **No behavioural regression:** automated characterization tests prove the four operations and
   the slimmed `edit_diagram` behave identically to today (WU-7/8).
4. **Description completeness:** all safety- and selection-critical semantics in D3 remain
   present; descriptions are concise but not lossy.
5. **Migration completeness:** no stale reference to the old surface remains anywhere (WU-6).

Optional, non-blocking: a small agent-task benchmark (representative create/edit/auto-sync/
propose/refresh/apply/detach tasks) recording valid-first-call rate, completion, and repair
turns, with "no regression vs. baseline" as the bar. A full metrics harness is judged
disproportionate for a responsibility-decomposition and is not mandated.

## Scope boundaries (non-goals)

No server split (D1); no changes to assurance servers or `arch-repo-read`; no behaviour change
to the underlying use cases (only the tool boundary, names, annotations, descriptions move);
no `render_options` (D7); no REST extension (D6 follow-up); no `create_diagram` param-splitting
(its three authoring forms are legitimately one-of inputs — description revision only).

## Risks & safety

- MCP signatures are durable agent contracts: changes take effect only after a **session
  restart**, with no live validation until then; treat as a deliberate, tested, fully-migrated
  pass.
- Breaking change (D4): mitigated by comprehensive migration WUs + contract-snapshot tests, not
  a shim.
- The four dispatch paths currently have **no automated behavioural tests** — added here (WU-7).

## Verification

1. `python -m pytest --tb=short -q` (0 failures), `ruff check src/ tests/`, `uv run zuban check`.
2. **Behavioural (automated), characterization-first:** *before* the surface change, add unit
   tests pinning the current behaviour of the four handler paths (propose/refresh read-only + no
   write; apply: dry-run vs commit, stale-revision conflict, manual-binding preservation, verifier
   failure + cache finalization; detach: missing-id, destructive removal). *After* the change, add
   MCP-adapter tests (each tool's schema, annotation, output schema, dry-run/write/conflict/failure,
   **and queueing**: propose/refresh unqueued, apply/detach queued). This gives parity evidence
   without brittle golden-output fixtures.
3. **Contract manifest (normalized), not byte-exact:** a normalized manifest of `arch-repo-write`
   (property order + nullable representation normalized) plus targeted semantic assertions —
   required params, enums, annotations, and the presence of critical description phrases (D3) —
   rather than exact description/schema snapshots that fail on harmless wording or
   dependency-generated schema changes. Assert `arch-repo-read` + assurance surfaces unchanged.
4. **Post-restart manual smoke** (one pass): exercise each new tool + an `edit_diagram` content
   edit/auto-sync via live MCP; confirm parity.
