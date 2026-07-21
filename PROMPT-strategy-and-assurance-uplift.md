# PROMPT — Execute the Strategy & Assurance Uplift Plan

You are implementing `PLAN-strategy-and-assurance-uplift.md` with the execution
ledger `TASKS-strategy-and-assurance-uplift.md`. Read both in full before writing
any code or model content, then follow the ledger's resume protocol: streams
A/B/C/D/E/G/U proceed per the ledger dependency graph; within a stream, the
first unticked WU is current.

## Ground rules (non-negotiable)

1. **Guidance first.** Query `arch-repo-read` for coding guidelines / best
   practices / style guides and apply them. For Stream A additionally: call
   `artifact_authoring_guidance` for every entity type and connection pair before
   creating it — the tool output at execution time is authoritative.
2. **Verify before you build on it.** Every WU lists code facts; re-verify them
   at the named files before changing anything. Before extending or replacing any
   mechanism (schema resolution, exposure policy, search, rendering), first
   locate the existing implementation and extend it — WU-B0/D2 exist precisely
   because conventions and policies already in the code take precedence over the
   plan's prose. On contradiction: stop, record in the ledger, decide.
3. **Distinction & naming discipline (Stream A).** Every strategy-domain entity
   passes the PLAN §4.2 litmus tests pairwise before creation; names satisfy the
   T-N rule (self-contained, never near-duplicating a process/function name).
   Stage content comes verbatim from §4.7; IDs verbatim from §4.8. No
   GTM/marketing content (D1).
4. **Principled solutions only.** Fix at the correct layer: edge legality in the
   write use case; endpoint visibility via the EXISTING exposure predicate
   (omission, never a new redaction path); metrics/VEX in single application use
   cases consumed by every surface; the viewpoint capability as a configured/null
   port (`src/application/viewpoints/ports.py`) evaluated per call — never
   unlock-time injection; schema resolution through the existing
   `compute_effective_attribute_schema`. Every closed contract gap gets a
   delegation test plus a regression test.
5. **Confidentiality invariants are load-bearing.** I-B1 (omission — no
   placeholder, count, existence, type, or direction leakage), I-C1 (no
   **operational/live-store-derived** value under any repository path — visibly
   marked synthetic fixtures only via I-E1–I-E3), I-C11/§6.0(f) (all-or-none
   snapshot coherence), §6.0(e) (filter-before-aggregate — hidden rows influence
   nothing), I-E1 (fail-closed capture harness is the primary media-origin
   proof). Each requires negative tests at two independent levels. Locked,
   above-ceiling, and unknown-id responses stay indistinguishable where the PLAN
   says so.
6. **Data semantics are safety-relevant (Stream C).** PLAN §6.0 is the binding
   contract: the backend × operation matrix and D21 audit durability (all
   mutations on the co-located backend with data + audit in ONE SQLCipher
   transaction; public SQLite read-only in v1 — never claim atomicity across
   two databases); the single `RefreshSecuritySignals` command (the script
   never imports an infrastructure connector); the §6.0(c) lifecycle
   (`staging→complete→active→superseded`, `staging→failed`) with `request_id`
   retry identity and retain-all retention; the exact §6.0(d) VEX key +
   immutable revisions; filter-before-aggregate with closed states; the
   `SignalSnapshotToken`. Never fabricate CVSS scores;
   version-unqualified identifiers are `applicability_unknown`, never "affects
   all"; purl matching via a proper library; OSV is two-phase with pagination
   and result↔component mapping; aliases resolve to immutable canonical
   identities. When in doubt, surface an explicit unknown — silent precision is
   the failure mode.
7. **Model writes only via MCP tools**, `dry_run=true` first, `artifact_verify`
   per batch, save per coherent batch; never edit model files by hand; verify
   before retrying stalled parallel connection batches.
8. **No provenance in code — diff-scoped.** No WU/plan-section/decision
   references in any added or modified line of source, test content, filenames,
   or self-model content. PLAN/TASKS/PROMPT files are exempt.
9. **LoC policy** 250 soft / 350 hard per code file (markdown exempt); the canvas
   extraction must reduce the view's count.
10. **Typing.** Closed unions for states/sources/metric names; guidance level ids
    are validated registry-checked strings (extensibility forbids compile-time
    unions there); typed DTOs at boundaries — untrusted JSON/YAML may be handled
    in tightly isolated parser code, but no untyped value escapes an adapter;
    ternaries ≤ 1 nesting, expression position; `types.generated.ts` untouched
    (D14).
11. **Tests.** Separate test file per component/use case. The FMEA tables are the
    coverage contract: every RPN ≥ 100 mode has unit + integration coverage;
    S ≥ 8 modes get explicit negative tests at two levels. Real seeded SQLCipher
    stores for assurance integration; portable fixtures everywhere (no network,
    no `~/.arch-guidance-extract/` dependency in CI).
12. **Tooling.** `uv sync --all-groups`; `uv` never pip. Backend code is inert
    until the owner restarts `arch-backend` — ask, never restart yourself; queue
    restart-gated checks into WU-X1. Do not commit or push unless the owner asks.
    Never run `git checkout`/`git restore` on working-tree files.

## Gates (per the ledger's strategy)

Per WU: targeted tests only. Per stream boundary (A5/B5/C5/D2/E2/G2/U0b): full
relevant subsystem gates — each boundary names its upstream WUs, cross-stream
contract tests, model/doc deltas, and migration evidence. WU-C0 and WU-U0a:
full backend gates immediately. WU-X1: everything, once:

```
uv run python -m pytest --tb=short -q      # 0 failures
uv run ruff check src/ tests/              # 0 errors (incl. E501)
uv run zuban check
# tools/gui:
npm run lint && npm run typecheck && npx vitest run
```

## Settled semantics — do not re-litigate

- Stream A verdicts (§4.3), stage map (§4.7), IDs (§4.8), witness chains (§4.9
  — exact connection types/directions; W2 walks the stored parent→stage
  composition from target to source) are final; derivation rules are never
  weakened to make a trace pass; diagrams use explicit `entity_ids` populations
  (§4.6), exactly 8.
- Assurance relationships: the D6 kind taxonomy (edges vs `arch_refs` vs
  external references) precedes everything; `binds-to` is a reference type, not
  a matrix pair; the Q13 handbook-reconciled matrix + verifier alignment +
  store repair land together in WU-B0 before any enforcement; the loaded
  module catalog — not YAML bytes — is the contract; create + delete only;
  edge-catalog is configured-gated, traversal/search unlock-gated; traversal =
  size-budget partials + whole-request time abort, no continuation tokens.
- Exposure: omission semantics per the existing policy; the only policy signal is
  a coarse `visibility_limited` flag; dangling edges are verifier findings.
- Metrics vocabulary, units, and classification per D9/D11/D12/§6.0 — per-
  directness counts partition **findings**, not distinct vulnerabilities;
  `max_cvss_score` from parsed vectors only; no KEV; classification computed
  from visible contributors. Signal mutations are allowed ONLY under the
  §6.0(a) capability predicate (sqlcipher store + colocated signals + local
  standard/worm archive + unlocked — one transaction owns data + audit; cloud
  WORM and all other combinations deny with typed reasons); public
  `signals_backend=sqlite` metrics are DEPRECATED in v1 (Q10).
- Guidance v2: hierarchy-generic, OntologyModules only (DiagramTypeModules
  ignored), one canonical wire shape (declared level maps + adapted v1 leaf
  slots), additive serving with a structural v1-subset pin; extract restructure
  happens at an owner checkpoint.
- Schemata: existing dot convention + existing resolver; §7.1b is the exact
  persisted-key contract (only `investment_level` is lowercase); `format: uri`
  informative; enums single-sourced; Module has no Owner; dogfood values are
  discovered, never invented.
- Documentation media: synthetic TLP:WHITE fixtures with visible markers behind
  the fail-closed harness; media provenance manifest; stable entity IDs; README
  claim amended.
- Motivation coverage (Part G/D20/§10): **branch enumeration uses direct
  stored edges only** — `archimate-realization` for outcome/requirement
  branches plus the Q9 `archimate-influence` shortcut (association →
  `ambiguous_link` diagnostic); leaf coverage alone uses direct+derived
  realization chains. Never use derived relationships to enumerate branches.
  TAGGED obligation tuples incl. missing-outcome/missing-requirement (a mixed
  no-terminal branch is a gap); the authoritative row verdict = motivation
  branch completeness + `overall_realization` (registry-derived eligible
  realizer set across ALL legal families) — layer columns are DIAGNOSTICS
  whose result is a diagnostic observation (`observed | none_observed |
  not_applicable`) inside the ONE row projection DTO's discriminated
  `PatternResult` union, never an authoritative verdict; row sorting and
  `gaps_only` read the row verdict only; §10.2d status registry;
  §10.3a enum-set parameter schema; §10.3b post-projection pipeline (trace
  before filter/sort/limit; gaps_only and gaps-first global); §10.4's closed
  `branch-complete-realization` grammar (tagged variants; NO steps/
  alternatives/quantifier keywords — the schema in the PLAN is the format);
  §10.5 spike-derived budgets with the trace-inputs-only memo key (no
  assurance state) and all-or-none abort; §10.6 executed-table semantics;
  §10.7 format impact. Failed refresh runs are terminal: replay returns the
  stored failure, never resumes (§6.0c).
  PLAN §12b is the authoritative vocabulary — never restate contracts from
  memory.
- Upgrade coverage (D19/§9): U0a precedes every persisted-format change
  (including A0/D2 default schemata); targets are deployment-scoped
  (`--workspace` = repos only; operational targets via explicit deployment
  identity via the shared `DeploymentLayout` resolver with normative
  precedence; `deployment_settings` is itself a versioned atomic target;
  Docker cannot exclude configured active targets; physical dedup); the CLI
  evolves ADDITIVELY (all existing flags/guards/recovery/disclaimer preserved;
  default stays dry-run, no `--check`; `EXIT_UNRESOLVED_MIGRATION=3` kept, new
  codes 20/21; recovery writes classified honestly vs the preflight gate);
  per-target atomicity + all-target preflight (NEVER a cross-target
  transaction claim); Docker startup order per §9.2; guidance cache migrates
  by one-line header text patch + sidecar fields; quarantine + schema-meta +
  PK/payload encodings per the §9.2 appendix; additive JSON report; viewpoint
  grammar and config migrations are §9.1 rows.
- Proportionate security posture (PLAN §11): hard invariants are the one-way
  persistence rule, TLP ceiling, unlock gating, audit; already-rendered content
  after a user-initiated lock is accepted residual exposure — no purge machinery;
  flag high-assurance drift for an explicit owner decision.
- Q1–Q13 are resolved in PLAN §12 (the single authoritative ledger). Q13 is
  the reconciled STPA relationship model (D6) — never reintroduce `violates`,
  `satisfied-by`, `responsible-of`, or `accountable-to`. Q12
  scoping: the dev self-model/assurance store is pre-publication example
  content — migrate or recreate it freely when formats change (destructive
  re-refresh fine; B0 dev default = repair); prove legacy-preservation and
  confidentiality capabilities on synthetic fixtures, never by treating this
  store's content as genuinely sensitive or precious; do not reopen.

## Definition of done

Every §13 criterion (per-part + layered local/regional/global) verified with
evidence (WU-X1 needs an owner backend restart first), ledger fully ticked,
self-model synced — Part A; B5; C5; the Part D requirements (§7.1 Layered
Modelling Guidance + Shipped Default Attribute Schemata); Part F §9.4 (incl.
the NEW `Guidance Cache` data object and its exact connection witnesses);
Part G §10.8 (REQ-G1 AND REQ-G2, functions, projection object) — with
`artifact_verify` clean,
previous-release upgrade fixtures green (§9), the cross-document semantic
consistency check and documentation truth audit passed, and a closing
deviations note in the ledger.
