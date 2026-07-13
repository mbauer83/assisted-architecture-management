# TASKS — Viewpoints II: Typed Query Bindings, Derived Relationships & Impact Analysis

Execution ledger for `PLAN-viewpoints-bindings-and-derived-relationships.md` (the PLAN owns
design rationale and normative semantics; this file owns sequencing, anchors, and
acceptance). Markdown — no LoC limit.

## Resume protocol

1. Read the PLAN §3 (locked decisions D1–D12) plus the PLAN section named by the WU you
   are about to execute; do NOT re-litigate locked decisions. The shipped criteria engine's
   semantics live in `PLAN-viewpoints-query-model.md` §3–§7 — read §3.4 and §7.2 before
   touching evaluation or validation.
2. Find the first unchecked WU whose deps are all checked; verify its anchors still exist
   (`rg` the symbols) before editing — anchors are a 2026-07-13 snapshot.
3. Quality gates after every WU (all via `uv run` for reproducible environments —
   `uv sync --all-groups` first): `uv run pytest --tb=short -q` (0 failures),
   `uv run ruff check src/ tests/` (0 errors incl. E501), `uv run zuban check` (pass). Frontend
   WUs additionally `npm run lint`, `npm run typecheck`, `npx vitest run` in `tools/gui`.
   After any ontology/type change: `uv run tools/generate_types.py` (pre-commit enforces).
   After any MCP tool-description change: `uv run tools/generate_mcp_docs.py` (CI
   `--check` gates staleness).
4. Architectural fitness functions run with the suite — a WU is not done while any of
   `tests/architecture/test_dependency_policy.py`, `test_ontology_protocol_purity.py`,
   `test_combined_index_fitness.py`, `test_index_broadcast_policy.py` fails. New domain
   modules must import nothing from `src/application`/`src/infrastructure` (the dependency
   policy test enforces this — design for it, don't fight it).
5. All self-model writes via MCP tools only (never manual file edits). MCP tools run
   against the long-running backend — code changes need a backend restart (user does it);
   note it in the ledger entry and continue with non-MCP work if blocked.
6. Python files: 250 LoC soft / 350 hard. No `Any` unless strictly unavoidable. No
   `datetime.now()`/localtime — `src/domain/clock.py` only. Frozen dataclasses for value
   objects. Test files per component, not omnibus.
7. **Never** reference phases, WU ids, plan §-numbers, or "companion plan" in code,
   docstrings, test content, or filenames — use feature names ("query bindings",
   "relationship derivation"). `rg -i "WU-|phase [A-I]|companion plan" src/ tests/ tools/gui/src/`
   must stay clean; run it before ticking any WU.
8. Tick the WU, append **exactly one line** under Progress notes: `date — WU-id —
   outcome (+ surprise/deviation only if one occurred)`. Hard cap ~2 lines per WU; no
   narration, no restating the WU's changes or acceptance (the ledger already holds
   them), no test-count play-by-play. Multi-line entries are reserved for genuine
   deviations from the plan (what differed and why). Past ledgers grew unusably long
   from verbose notes — conciseness here is a rule, not a preference.

## Release cut (independent, individually shippable increments)

Each release closes with the full quality-gate + fitness-function sweep and may ship
without the later ones; a WU belongs to exactly one release:

- **R1 — Remediation hotfix**: A1, A3 (scope fallback; fixes the empty-execution defect).
- **R2 — Relationship-derivation engine + impact surfaces**: A2, B1–B7, D1a, D2, E3a,
  E5. Gated by WU-B6 (rule-verification battery) — a dependency of every engine
  consumer. No Phase C dependency anywhere in R2.
- **R3 — Typed binding layer**: C1–C5, D1b, E1, E2, E3b, E4.
- **R4 — Standard viewpoint library**: G1 (no presentation-feature deps), then G2
  (needs R2+R3).
- **R5 — Presentation & persistence enhancements**: F1–F6, G3.
- **R6 — GUI** (Phase H; gated on the frontend rewrite) and **docs/self-model closeout**
  (Phase I; I1–I4 may trail each release incrementally, I5 closes the whole plan).

Cross-release dependencies are exactly those named in the WUs; nothing in R1/R2 waits on
the binding layer, and G1 waits on neither derivation nor presentation work.

## Naming checklist (PLAN §5.0)

- "relationship derivation" = ArchiMate Appendix-B semantics (new modules
  `src/domain/relationship_*.py`).
- "view derivation" = existing diagram-generation strategies (`src/application/derivation/`).
- Never abbreviate either to bare "derivation" in public names, docs, or GUI copy.
- **Role-functional names only** — no spec-structure identifiers (appendix letters,
  section numbers, table numbers) in type, function, module, or test-file names:
  `DerivationDomain`, not a name citing where the concept is specified. The same rule
  covers **test function names**: name the behavior
  (`test_structural_chain_derives_weakest_relationship`), never the rule id
  (`test_dr2_…`). The sanctioned
  traceability channel is the `spec_ref` *data field* on rule/restriction/parametrization
  data, pytest case ids, and spec
  citations in docstrings/comments — citation is metadata, never identity.

---

## Phase A — Foundations & remediation

- [x] **WU-A1 — Settings for bindings & derivation bounds**
  - Files: `config/settings.yaml`, `src/config/settings.py` (`_DEFAULTS["viewpoints"]`,
    accessor functions beside `viewpoints_execution_max_entities`),
    `tests/common/test_viewpoints_execution_settings.py` (extend in place — same concern).
  - Changes: add `viewpoints.max_query_bindings: 8`, `max_query_parameters: 4`,
    `max_derived_attributes: 8`, `derivation_max_hops: 4`,
    `derivation_max_relationships: 2000`; typed accessors
    (`viewpoints_max_query_bindings()` etc.) with default fallback like the existing ones.
  - Acceptance: accessors return YAML overrides and defaults; invalid values rejected the
    same way existing viewpoint settings are; docs for `config/settings.yaml` reference
    section updated in WU-I2 (note only here).
  - Deps: none.

- [x] **WU-A2 — Ontology derivation classification**
  - Files: `src/ontologies/archimate_4/connections.yaml`,
    `src/domain/ontology_types.py` (`ConnectionTypeInfo`),
    `src/ontologies/archimate_4/_loader.py`, new
    `tests/domain/test_connection_derivation_classification.py`.
  - Changes: per PLAN §5.1 — `derivation: {role, strength}` blocks on all 11 ArchiMate
    connection types (exact strengths from the PLAN table);
    `ConnectionTypeInfo.derivation_role: Literal["structural","dependency","dynamic","specialization"] | None = None`,
    `derivation_strength: int | None = None`; loader validation (strength required for
    structural/dependency, forbidden otherwise; strengths unique per role; unknown role =
    load error). Run `uv run tools/generate_types.py`.
  - Acceptance: loader tests for valid/invalid blocks; all 11 types classified per the
    PLAN table (test asserts the exact table — spec comparison anchor); types without a
    block yield `None` roles; `test_ontology_protocol_purity.py` green;
    `types.generated.ts` regenerated & committed.
  - Deps: none.

- [x] **WU-A3 — Scope-fallback execution (D9, defect remediation)**
  - Files: `src/application/viewpoints/evaluate_viewpoint.py` (retire
    `_NO_QUERY_SUMMARY` path), new helper in `src/application/viewpoints/` (e.g.
    `scope_query.py`) so `evaluate_viewpoint.py` stays under LoC limits;
    `tests/application/viewpoints/test_evaluate_viewpoint.py` + new
    `tests/application/viewpoints/test_scope_fallback.py`.
  - Changes: when the resolved definition has `query is None`, build the implicit query
    from `ConceptScope` per PLAN §6.1 — `type in sorted(entity_types)` (match-all when
    `None`), connection narrowing from `connection_types`; class/hierarchy predicates
    enforced via `ConceptScope.admits_entity_type` (post-filter hook in the population
    evaluation, NOT re-encoded as criteria); `query_summary` prefixed
    "Selection derived from the viewpoint's concept scope: …".
  - Acceptance: executing each of the four currently-shipped scope-only definitions
    against a seeded fixture repo returns a non-empty, scope-correct population;
    unrestricted scope = match-all; ad-hoc queries unaffected (regression); REST/MCP
    surfaces need no change (they already call the use case) — verified by the existing
    parity fixture still passing.
  - Deps: none.

## Phase B — Relationship-derivation engine (pure domain)

- [x] **WU-B1 — Derivation-domain classifier & pairwise composition (DR 1–8)**
  - Files: new `src/domain/relationship_derivation.py`,
    `src/domain/relationship_derivation_rules.py`; new
    `tests/domain/test_relationship_derivation_rules.py`,
    `tests/domain/test_derivation_domain.py`.
  - Changes: `DerivationDomain` classifier per PLAN §5.1 — junction class ⇒
    `relationships` regardless of storage hierarchy; `hierarchy[0]` mapping otherwise;
    unknown head = loud error, never a silent `core`. `OrientedRelation`, `DerivedStep`,
    `compose(...)` implementing DR1–DR8 exactly per the PLAN §5.2 table (weakest-of via
    `derivation_strength`; opposing-join orientation handling for DR4/DR6); left-fold
    `fold_chain(...)` with certainty + `potential_steps`. **Every rule datum carries a
    `spec_ref` field** (PLAN §5.3a method 1).
  - Acceptance: classifier table test covers EVERY shipped entity type (incl.
    `and-junction`/`or-junction` ⇒ `relationships` despite `common/` storage); one named
    test case per DR rule with **role-functional names**
    (`test_structural_chain_derives_weakest_relationship`, never a spec-id name) and
    traceability via `spec_ref` parametrization data / pytest case ids — this applies to
    every Phase-B test (behavior in the name, citation in the data); strength-order
    tables asserted verbatim;
    fold determinism; junction/self-loop exclusion; modules import domain-only
    (dependency-policy fitness green).
  - Deps: A2.

- [x] **WU-B2 — Potential rules (PDR 1–12) & certainty**
  - Files: `relationship_derivation_rules.py` (extend),
    `tests/domain/test_relationship_derivation_potential.py`.
  - Changes: PDR1–PDR12 per the PLAN table incl. the four specialization orientation
    cases and PDR12's grouping + permitted-check precondition; chain certainty =
    potential if any step potential.
  - Acceptance: one test case per PDR with a behavior-describing name (e.g.
    `test_specialization_source_inherits_target_relationships`); the PDR id appears only
    in `spec_ref` parametrization data / pytest case ids, never in the function name;
    grouping-aggregation blocked when `permitted_relationships` disallows the target
    pair; certain/potential mixing pinned.
  - Deps: B1.

- [x] **WU-B3 — §B.4 restrictions**
  - Files: new `src/domain/relationship_derivation_restrictions.py`,
    `tests/domain/test_relationship_derivation_restrictions.py`.
  - Changes: predicates R1–R14 + RJ1–RJ2 transcribed **from the PLAN §5.2 restriction
    table** (which is the reviewed spec transcription — do not re-derive from prose),
    each datum with `spec_ref`; applied as final admissibility filter in
    `compose`/`fold_chain`, RJ* per composition step against the intermediate element.
  - Acceptance: one test case per bullet (14 + 2), each with an admitting and a
    rejecting case, behavior-named (e.g.
    `test_derived_influence_requires_motivation_target`); restriction ids live only in
    `spec_ref` parametrization data / pytest case ids, never in function names; the code
    table diffs 1:1 against the PLAN table (reviewer checklist item recorded in the
    ledger note).
  - Deps: B1, B2.

- [x] **WU-B4 — Bounded reachability & enumeration**
  - Files: new `src/domain/relationship_reachability.py`,
    `tests/domain/test_relationship_reachability.py`.
  - Changes: the PLAN §5.3 policy value objects — `RelationshipDerivationRequest`,
    `DerivationBounds`, `DerivationCertaintyPolicy` (transport booleans translate to the
    policy at API edges, never inside domain code) — and
    `derive_relationships(request, *, read_access: CriteriaReadAccess, registries)`:
    BFS, memoized frontier, dedup (certain-wins, min-hops, deterministic lexicographic
    witness path in the `id@fwd|id@rev` canonical format), synthetic ids
    `derived::<type>::<path-key>`; typed `DerivationLimitError` at
    `bounds.max_relationships`.
  - Acceptance: dedup/certainty/witness determinism pinned; hop/limit bounds honored;
    direction semantics (incoming/outgoing/either from anchors); dangling endpoints never
    traversed; pure (no I/O beyond `read_access`).
  - Deps: B1–B3.

- [x] **WU-B5 — Spec worked examples & direct-model boundary**
  - Files: new `tests/domain/test_relationship_derivation_worked_examples.py`,
    `tests/fixtures/viewpoints/derivation_examples.py` (fixture model builders).
  - Changes: encode Appendix-B examples B-3 (assignment–aggregation–realization ⇒
    realization), B-9 (flow endpoint transfer), B-11 (Sales/Shipping triggering chain
    incl. the aggregated Billing case), B-12 (PDR5 — Suite aggregates Front-End and
    Back-End, Database/Website Hosting serve Suite; all four serving candidates
    derivable, tagged potential; `spec/viewpoints/Figure-B-12.jpg` shows the spec's
    accepted/rejected split, the precedent for the per-occurrence acceptance defaults),
    B-17 (project-team specialization cases PDR1–4) as executable fixtures; regression
    test that the B-3 Financial Application realization remains an indirect result even
    though the same type pair is not directly admitted by `permitted_relationships`.
  - Acceptance: all five examples produce exactly the spec's stated derivations (and no
    uncited extras at the tested hop bounds); direct-model-boundary regression green.
  - Deps: B4.

- [x] **WU-B6 — Rule-correctness verification battery (PLAN §5.3a — the crux gate)**
  - Files: new `tests/domain/test_relationship_derivation_dual_encoding.py`,
    `tests/domain/test_relationship_derivation_exhaustive.py`,
    `tests/domain/test_relationship_derivation_invariants.py`; test-only fixture module
    `tests/fixtures/viewpoints/derivation_rules_independent_encoding.py`.
  - Changes: (a) **dual encoding** — an independently authored transcription of
    DR/PDR/restrictions written directly from
    `spec/viewpoints/appendix-b-relationships-derivation.md`. The enforceable conditions
    are **structural**: the fixture module contains only literal expected-outcome data
    (no imports from `src/domain/relationship_*` — asserted by a test inspecting the
    fixture module's imports, so it cannot silently regress into re-exporting the
    runtime tables), and the ledger review note records transcriber + reviewer
    identities and date. Authoring by a different agent/session than WU-B1–B3 is the
    stated preference, not an acceptance gate. A structural comparison test asserts
    cell-by-cell agreement with the runtime tables;
    (b) **exhaustive metamodel sweep** — generated over every permitted input pair ×
    orientation across all shipped types, asserting each composition output's stated
    classification, certainty, and restrictions, with the direct-permission condition
    enforced specifically for PDR12; (c) **semantic invariants** on engine output over generated
    random models, stated independently of any rule table: derived Access ⇒ target is
    passive-structure; derived Influence ⇒ target ∈ Motivation; junction-sourced derived
    relations only Association; any PDR step ⇒ certainty `potential`; derived structural
    strength ≤ weakest chain link.
  - Acceptance: all three batteries green; a ledger note records the line-by-line
    spec-vs-both-encodings review pass (who/when/findings). **Phase D must not start
    before this WU is ticked.**
  - Deps: B1–B5.

- [ ] **WU-B7 — Path reconstruction (`derive_relationship_for_path`)**
  - Files: `src/domain/relationship_reachability.py` (extend — same fold, one explicit
    chain); new `tests/domain/test_relationship_path_reconstruction.py`.
  - Changes: PLAN §5.3 reconstruction contract — parse canonical `id@fwd|id@rev|…` key,
    resolve each link via read access, re-apply the fold in recorded orientation, return
    the `Derived | Broken | NoLongerDerives` discriminated union. Shared fold with BFS
    (no second rule path).
  - Acceptance: round-trip property (every path emitted by `derive_relationships`
    reconstructs to the same (source, target, type, certainty, hops)); `Broken` on
    missing connection and on dangling endpoint; orientation-mismatch key ⇒ `Broken`;
    `NoLongerDerives` on connection retype and on a restriction newly firing;
    certainty-changed case (chain edited so a certain path becomes potential) surfaces
    the new certainty.
  - Deps: B4.

## Phase C — Typed value & binding layer (pure domain)

- [ ] **WU-C1 — Result-type algebra & inference**
  - Files: new `src/domain/viewpoint_value_types.py`,
    `tests/domain/test_viewpoint_value_types.py`.
  - Changes: PLAN §4.1 types **incl. cardinality as a type distinction** —
    `EntityInstanceType`/`ConnectionInstanceType` (exactly one), `OptionalType`
    (zero-or-one), set types (any cardinality), fixed-arity `TupleType`, `ListType`;
    canonical string printer/parser (`entity[a]`, `entities[a|b]`,
    `optional[entity[a]]`, `list[number]`, `tuple[…]`, …); `infer_binding_type` with
    conservative union narrowing, declared-vs-inferred compatibility (instance type over
    set-shaped selection = static check + runtime cardinality assertion), singular
    projection (`project` over instance ⇒ scalar, over optional-instance ⇒ optional
    scalar), ambiguous-attribute detection against the D13 merged schema surface (reuse
    `resolve_attribute_path`), aggregate kind table, `aggregate-over-instance`.
  - Acceptance: printer/parser round-trip for every shape incl. instance/optional/tuple
    arity; each inference rule pinned (union narrowing, open-union reserved-path
    projection, ambiguity error, aggregate kinds incl. `avg ⇒ number`, `min/max` on
    date, singular projection, tuple arity mismatch static error).
  - Deps: none (parallel to Phase B).

- [ ] **WU-C2 — Binding/parameter/derived value objects + parsing/serialization**
  - Files: new `src/domain/viewpoint_bindings.py`; `src/domain/viewpoint_criteria.py`
    (`ValueRef` new kinds/fields, `VALID_VALUE_REF_KINDS`),
    `viewpoint_criteria_parsing.py`/`viewpoint_criteria_serialization.py` (ValueRef
    mapping forms `{from: binding|parameter, …}`),
    `viewpoint_query_parsing.py`/`viewpoint_query_serialization.py` (top-level
    `bindings`/`parameters`/`derived`, `query_schema` 2/3 rules per D10);
    `src/domain/viewpoints.py` (`ExecutableViewpointQuery` fields); tests:
    `test_viewpoint_criteria_parsing.py`, `test_viewpoint_serialization.py` (extend), new
    `tests/domain/test_viewpoint_bindings_parsing.py`.
  - Changes: `QueryBinding`, `QueryParameter`, `DerivedAttribute` (PLAN §4.2–§4.4)
    with `traversal`/`include_potential`/`max_hops` fields (used from Phase D) and the
    three-headed `of` grammar (`connection.<attr>` | `endpoint.<attr>` |
    `relationship.hops` — the reserved derived-hop source, PLAN §4.3);
    schema-2 payload using any new construct ⇒ parse error naming the construct;
    serializer writes minimal schema (2 when no new construct). (The base
    accept-schema-2-and-3 parser change is shared with WU-D1a — whichever of the two
    lands first introduces it; the other extends the construct list.)
  - Acceptance: `parse ∘ serialize = id` over maximal new-shape definitions AND all
    pre-existing Appendix-A fixtures byte-stable at schema 2; unknown keys error;
    Appendix-A examples 1–3 of the new PLAN parse.
  - Deps: C1.

- [ ] **WU-C3 — Validation: codes, caps, modes, paths**
  - Files: `src/domain/viewpoint_binding_validation.py` (new),
    `viewpoint_validation.py`, `viewpoint_condition_validation.py` (ValueRef typing),
    `viewpoint_criteria_validation.py` (traversal path restrictions);
    tests: new `tests/domain/test_viewpoint_binding_validation.py`, extend
    `test_viewpoint_validation.py`.
  - Changes: every binding/parameter/derived-attribute code in PLAN §4.7
    (`unknown-binding`, `binding-cycle`, …; the traversal codes
    `derived-traversal-path-unsupported`/`derivation-hops-exceeded` live in WU-D1a, and
    `style-mode-field-mismatch` in WU-F1); D2/D3 typing
    rules (declared-vs-inferred, comparator×type incl. tuples and
    `unquantified-set-comparison`); `include_in_result` shape validation (entity-valued
    shapes only — instance/optional/set; scalar/connection/tuple ⇒
    `include-in-result-shape-unsupported`); caps as save-mode ergonomics checks; JSON-pointer
    paths into `query.bindings[i]…`/`parameters[i]`/`derived[i]…`; load-mode: registry
    findings warn, structure rejects (unchanged split).
  - Acceptance: same definition through all three modes matrix extended; code snapshot
    test updated (stability); every new error carries resolvable path + expected/found.
  - Deps: C2.

- [ ] **WU-C4 — Evaluation: bindings pipeline, ValueRef resolution, derived attributes**
  - Files: new `src/domain/viewpoint_binding_evaluation.py`;
    `viewpoint_condition_evaluation.py` (`_resolve_value` gains binding/parameter kinds +
    quantifier application), `viewpoint_criteria_evaluation.py` (threading an immutable
    `EvaluationEnvironment` — resolved bindings + parameters + derived-attribute memo —
    through the recursion; extend `read_attribute_value` for `derived.` paths);
    tests: new `tests/domain/test_viewpoint_binding_evaluation.py`,
    `tests/domain/test_viewpoint_derived_attributes.py`, extend
    `test_viewpoint_condition_evaluation.py`.
  - Changes: PLAN §4.2 semantics (once-per-execution, topo order, empty-value table),
    §4.2.1 quantifiers, §4.3 derived attributes (direct traversal now; derived traversal
    + `relationship.hops` activate in WU-D1b) with per-(entity, attribute) memoization;
    environment is positional context, evaluator stays pure. **Boundary per PLAN §4.2**:
    the domain evaluator receives a `BindingEvaluationInput` (candidate entity ids +
    candidate connection ids + read access + registries) — it never enumerates the
    repository; `CriteriaReadAccess` gains no `entity_ids()`. Application
    (`EvaluateViewpoint`, WU-E1) resolves scope-partitioned candidates once via
    `RepositoryReadAccess` and shares them between primary matching and all bindings.
    Runtime cardinality assertion for instance-typed bindings (raises the domain error
    WU-E1 wraps as `BindingCardinalityError`).
  - Acceptance: Appendix-D delta rows for bindings/ValueRef/derived (direct) all pinned;
    evaluated-exactly-once spy test; single-repository-enumeration spy test (one
    candidate resolution shared across primary + N bindings); cardinality assertion
    (0, 1, >1 items against `entity[…]` and `optional[…]` declarations); empty-set
    semantics table verbatim; §3.4 regression suite untouched and green;
    dependency-policy fitness green (no application imports from domain).
  - Deps: C2, C3.

- [ ] **WU-C5 — Plain-language summary extension**
  - Files: `src/domain/viewpoint_summary.py` (split a
    `viewpoint_summary_bindings.py` helper if LoC demands),
    `tests/domain/test_viewpoint_summary.py` (extend).
  - Changes: PLAN §4.6 sentences (Let-bindings, parameter placeholders, quantified
    references, derived-attribute phrases, derived-traversal phrasing "connected directly
    or indirectly (up to N steps[, including potential derivations])").
  - Acceptance: every new construct rendered; quantifier+negate interaction phrasing
    pinned; REST/MCP shared-fixture parity test extended.
  - Deps: C4 (types only; may start after C2).

## Phase D — Derived traversal in the query model

- [ ] **WU-D1a — Derived traversal on incident predicate & neighbor inclusion**
  - Files: `src/domain/viewpoint_criteria.py` (`IncidentConnectionCondition`,
    `NeighborInclusion` gain `traversal`/`include_potential`/`max_hops` — parsed but
    inert until here), `viewpoint_criteria_evaluation.py`,
    `viewpoint_population_evaluation.py` (`resolve_neighbor_inclusions` derived branch
    via `relationship_reachability`, building the `RelationshipDerivationRequest` VO);
    tests: new `tests/domain/test_viewpoint_derived_traversal.py`.
  - Changes: PLAN §5.4 — derived branch enumerates derived relationships from the
    candidate/anchor; criteria against them restricted to `type|certainty|hops`.
    **Parsing and save-mode validation of the traversal fields land HERE** (extending
    the shipped `viewpoint_criteria_parsing.py`/`viewpoint_criteria_validation.py`):
    `derived-traversal-path-unsupported`, `derivation-hops-exceeded`, and the schema-3
    gating for `traversal != direct` — independent of the Phase-C binding grammar, so R2
    is self-contained. Depth cap counts the node as one level; `via` =
    `"derived-traversal"` for derived-included neighbors. No binding/derived-attribute
    machinery involved (that is WU-D1b) — this WU is implementable straight after the
    engine.
  - Acceptance: incident + inclusion over a crafted chain fixture (component
    →assignment→ function →realization→ service: derived realization found at 2 hops);
    potential opt-in honored; hop bound honored; direct-mode behavior byte-identical to
    pre-change (regression).
  - Deps: B4, B6 (the rule-verification battery gates ALL consumers of the engine —
    enforced as a dependency, not just prose). (No Phase C dependency.)

- [ ] **WU-D1b — Derived traversal for derived attributes (`relationship.hops`)**
  - Files: `viewpoint_binding_evaluation.py` (derived-attribute derived branch);
    tests: extend `tests/domain/test_viewpoint_derived_attributes.py`.
  - Changes: the derived-attribute derived branch + the `relationship.hops` source
    become evaluable (validation: derived traversal only,
    `derived-of-source-traversal-mismatch`).
  - Acceptance: `reduce: min` over `relationship.hops` on the chain fixture yields the
    minimal hop count; direct-traversal derived attributes unaffected (regression).
  - Deps: C4, D1a.

- [ ] **WU-D2 — Connection selection, matrix bridging, provenance fields**
  - Files: `viewpoint_criteria.py` (`ConnectionSelection.traversal`),
    `viewpoint_population_evaluation.py` (`select_connections`/
    `select_matrix_connections` derived/both branches),
    `src/domain/viewpoint_projection.py` (`ProjectedOccurrence.via`),
    `src/application/viewpoints/execution_result.py` (summary fields per PLAN §5.5),
    `repository_projection.py`; tests: extend
    `test_viewpoint_population_evaluation.py`, new
    `tests/application/viewpoints/test_derived_connections_result.py`.
  - Changes: derived relationships between included entities join the display set under
    both invariants; synthetic ids sort stably; `certainty`/`hops`/`via_connection_ids`
    on connection summaries (None/empty for modeled); `via` on entity summaries +
    occurrences; derived results remain distinct from direct modeled connections even
    when their type pair is not directly permitted. **Hitting `derivation_max_relationships` is
    `DerivationLimitError` — typed error, whole execution aborts, no partial result
    (PLAN §5.5)** — there is no derivation-truncation warning anywhere.
  - Acceptance: matrix bridging over derived edges (requirements × components realization
    fixture); structural invariant holds for derived edges; limit overflow during
    selection raises the typed error with no result; existing consumers see
    unchanged shapes for modeled-only results (golden regression).
  - Deps: D1a, B6.

## Phase E — Application layer & transports

- [ ] **WU-E1 — `EvaluateViewpoint` pipeline, parameters, typed errors**
  - Files: `src/application/viewpoints/evaluate_viewpoint.py` (+ split helpers),
    `execution_result.py`; tests: extend `test_evaluate_viewpoint.py`, new
    `test_viewpoint_parameters.py` under `tests/application/viewpoints/`.
  - Changes: PLAN §4.5 pipeline order; **connection-candidate acquisition** —
    `src/application/viewpoints/ports.py` `RepositoryReadAccess` gains
    `connection_ids()` / `enterprise_connection_ids()` / `engagement_connection_ids()`
    mirroring entity enumeration (verify the real index adapter and the verifier's
    `ArtifactRegistry` satisfy it; where a delegation is missing, add it at the correct
    layer per the standing rule — never route around); scope = declaring repo, same as
    entities; `ViewpointExecutionRequest.parameters`;
    `ViewpointParameterError` (missing/mistyped/unknown), `DerivationLimitError`
    surfaced as typed errors like the timeout; dangling `entity-id` → warning +
    no-match; success log line gains `binding_count`/`derived_edge_count` (NO
    `derivation_truncated` — derivation never truncates); error path logs
    `error_code=derivation-limit` + configured limit + count-at-failure, no result
    payload.
  - Acceptance: pipeline-order fixture; parameter error matrix; `select: connections`
    binding end-to-end (scoped enumeration; dangling-endpoint candidate evaluates own
    attributes, endpoint ValueRef no-match; enterprise/engagement/both partitions
    pinned; one connection enumeration shared across all connection bindings — spy
    test); timeout still covers the whole pipeline (slow-binding fixture); four counts +
    *entity* truncation unchanged (transport-level cut of a complete result — entirely
    separate from the derivation limit, which is a typed error).
  - Deps: C4, D2 (A3 already merged into this path).

- [ ] **WU-E2 — REST surface**
  - Files: `src/infrastructure/gui/routers/viewpoints.py`,
    `viewpoint_authoring.py` (`/summarize`, `/criteria-catalog` additions; new
    `GET/PUT /api/viewpoints/pins` lands in WU-F3); tests:
    `tests/tools/test_gui_router_viewpoints.py` (extend).
  - Changes: `parameters` on the three execute bodies; typed-error → 400 with
    issue-shaped payload (code/path/message); criteria-catalog exposes binding/parameter/
    derived vocabulary + derivation classification + result-type strings (PLAN §9).
  - Acceptance: REST/MCP parity fixture extended (same §7.1 content incl. new summary
    fields for one parameterized + one derived-traversal query); error payload shape
    pinned for every typed error (parameter, cardinality, derivation-limit, timeout) —
    each returns the error payload and NO partial result.
  - Deps: E1.

- [ ] **WU-E3a — MCP graph tool: derived-neighbor mode**
  - Files: `src/infrastructure/mcp/artifact_mcp/query_graph_tools.py`
    (`artifact_query_find_neighbors` gains `traversal`/`include_potential`, translated
    to `DerivationCertaintyPolicy`/`RelationshipDerivationRequest` at the boundary);
    tests: extend the find_neighbors tool tests.
  - Changes: derived mode returns type/certainty/hops/path per neighbor within existing
    limits; `DerivationLimitError` maps to a typed MCP error payload (no partial
    result). Run `uv run tools/generate_mcp_docs.py`.
  - Acceptance: derived neighbors with certainty fields on the chain fixture; limit
    overflow returns the typed error and no result; description stays short; generated
    docs check green.
  - Deps: B4, B6.

- [ ] **WU-E3b — MCP viewpoint read tool & help topic**
  - Files: `src/infrastructure/mcp/artifact_mcp/query_viewpoint_tools.py`, the
    `artifact_help` viewpoints topic source, `edit_tool_descriptions.py` if touched;
    tests: `test_viewpoint_query_tool.py`, `test_viewpoint_query_tool_descriptions.py`
    (extend).
  - Changes: `execute` gains `parameters`; `list` includes parameter signatures +
    pinned flags (flag read lands F3 — keep field optional until then); typed execution
    errors (parameter, cardinality, derivation-limit, timeout) map to consistent MCP
    error payloads; help topic per PLAN §9. Run `uv run tools/generate_mcp_docs.py`.
  - Acceptance: MCP execute of the Appendix-A example-2 definition (fixture repo) returns
    dependents with certainty fields; each typed error surfaces as an error payload with
    no partial result, REST-parity asserted via the shared fixture; descriptions short
    (existing description-length test); generated docs check green.
  - Deps: E1.

- [ ] **WU-E4 — MCP write tool & lifecycle**
  - Files: `src/infrastructure/mcp/artifact_mcp/write/viewpoint.py`,
    `src/application/viewpoints/persist_definition.py`; tests:
    `test_viewpoint_write_tool.py`, `test_promote_viewpoints.py` (extend).
  - Changes: persist_edit mode over the full new grammar (nothing structural — the
    shared validator does the work; verify paths surface); version-bump classification:
    `bindings`/`parameters`/`derived`/traversal/presentation-scale are semantic content.
  - Acceptance: create→error→fix loop over a binding-cycle payload converges on paths;
    semantic-vs-descriptive bump matrix extended; D14 exact-version promotion regression
    with a schema-3 definition.
  - Deps: C3, E1.

- [ ] **WU-E5 — `GET /api/neighbors` derived mode**
  - Files: `src/infrastructure/gui/routers/connections.py`; tests:
    `tests/tools/` router test beside existing neighbors coverage (extend or add
    `test_gui_router_neighbors_derived.py`).
  - Changes: `traversal`/`include_potential` query params; response derived-neighbor
    metadata mirroring E3a.
  - Acceptance: parity with find_neighbors on the same fixture — reusing the
    B6-verified fixture/expected data, never independently hand-authored expectations;
    limit overflow returns the typed error payload, no result.
  - Deps: B4, B6 (independent of E1–E4).

## Phase F — Presentation additions & persistence integrations

- [ ] **WU-F1 — Scale-mode style rules**
  - Files: `src/domain/viewpoints.py` (`StyleRule` scale fields, mode literal),
    `viewpoint_presentation_parsing.py`/`_serialization.py`/`_validation.py`,
    `viewpoint_style_evaluation.py`; tests: `test_viewpoint_style_evaluation.py`,
    presentation parsing/validation tests (extend).
  - Changes: PLAN §7/§8 — `scale_attribute` (numeric/date incl. `derived.` paths),
    `scale_min/max` (None ⇒ data-driven, deterministic over the result set),
    `scale_tokens` (exactly two), interpolation contract for adapters (normalized 0–1
    position emitted with the two tokens — adapters interpolate, domain stays
    token-opaque); `style-mode-field-mismatch` validation.
  - Acceptance: Appendix-D presentation rows; data-driven bounds determinism; missing/
    out-of-range attribute ⇒ default style; legend derivation data present in projection
    output.
  - Deps: C4 (for `derived.` sources).

- [ ] **WU-F2 — `label_attribute` display option**
  - Files: `viewpoint_presentation_validation.py` (validated display option for
    `exploration`/`diagram`), docs note; tests: presentation validation (extend).
  - Acceptance: valid §3.3/`derived.` path accepted; unknown path = save error via the
    existing `unsupported-display-option`/`unknown-attribute` machinery; other
    representations reject it.
  - Deps: C4.

- [ ] **WU-F3 — Viewpoint pins**
  - Files: new `src/application/viewpoints/pins.py` (load/save via existing repo-write
    port), `.arch-repo/viewpoint-pins.yaml` convention, `viewpoint_authoring.py`
    (`GET/PUT /api/viewpoints/pins`), `query_viewpoint_tools.py` (`list` pinned flag);
    tests: new `tests/application/viewpoints/test_viewpoint_pins.py`, router test.
  - Changes: PLAN §7 — engagement-repo-local slug list; unknown slugs pruned on read
    with a warning; never promoted (assert in promotion test).
  - Acceptance: CRUD round-trip; absence = empty; module-shipped (read-only) definitions
    pinnable; promotion untouched.
  - Deps: E2/E3b for surfacing (storage part independent).

- [ ] **WU-F4 — `viewpoint_execution` view-derivation strategy (persistent results)**
  - Files: new `src/application/derivation/viewpoint_execution.py`, registration at the
    composition root (`src/infrastructure/app_bootstrap.py`, beside existing strategy
    registrations); tests: new `tests/application/derivation/test_viewpoint_execution_strategy.py`.
  - Changes: PLAN §7/§5.7 — `StrategySpec(name="viewpoint_execution", version=1)`; params
    `{slug, version} | {query: <canonical mapping>}` + `parameters`; derive fn calls the
    `EvaluateViewpoint` use case surface exposed to strategies via the existing
    `ModelQuery`-compatible read access (inject the use case, don't re-evaluate) and
    emits `CandidateSet(entity_ids, connection_ids, paths)` — modeled connections by id,
    **derived connections as candidate witness paths** (canonical path keys). Acceptance
    defaults per §5.7: certain candidates pre-included, potential candidates pre-excluded
    (require explicit acceptance); the decision persists via the existing
    `DerivationSelection.included_paths`/`excluded_paths`.
  - Acceptance: generate→review→refresh cycle over a fixture repo; certain/potential
    acceptance defaults pinned; staleness after definition version bump reported by the
    existing refresh flow.
  - Deps: E1, D2.

- [ ] **WU-F5 — `derived_relationships` view-derivation strategy**
  - Files: new `src/application/derivation/derived_relationships.py` + registration;
    tests: new `tests/application/derivation/test_derived_relationships_strategy.py`.
  - Changes: PLAN §5.6.3/§5.7 — params `{root_entity_ids, direction, include_potential,
    max_hops}`; emits reachable entities, the modeled connections along witness chains,
    **and derived-connection candidates as witness paths** (canonical keys; same §5.7
    certain/potential acceptance defaults as WU-F4).
  - Acceptance: impact diagram generation over the B5 chain fixture (reusing the
    B6-verified fixture/expected data, never independently hand-authored expectations);
    selection include/exclude round-trip via existing `DerivationSelection`; potential
    candidates excluded until accepted.
  - Deps: B4, B6.

- [ ] **WU-F6 — Rendering derived connections on genuine diagrams (+ refresh staleness)**
  - Files: `src/infrastructure/rendering/` (ArchiMate renderer path —
    `archimate_puml_renderer.py` / `archimate_occurrences.py`; verify exact seam with
    `rg "connection" src/infrastructure/rendering/` before editing),
    `src/application/derivation/refresh.py`; tests: renderer tests beside existing
    rendering coverage + new `tests/application/derivation/test_derived_path_refresh.py`.
  - Changes: PLAN §5.4 (diagram consumer) + §5.7 — a derived connection renders in its
    **derived type's** standard notation with a derived marker (dashed/annotated per the
    existing token-opaque styling contract; certainty distinguished); applies to both the
    ad-hoc `diagram` representation and persisted generated diagrams (accepted paths
    re-computed at render time via WU-B7's `derive_relationship_for_path` — rendering
    consumes ONLY that function). Refresh maps the reconstruction outcomes: `Broken` and
    `NoLongerDerives` (and certainty/type drift vs the accepted record) are reported as
    stale selection entries — never silently redrawn or dropped.
  - Acceptance: layered fixture (business process ← derived serving ← technology node,
    application layer omitted) renders the derived connection with serving notation +
    derived marker in both contexts; deleting a chain link makes refresh report the
    stale path; rule-change staleness case pinned (fixture flips a connection type).
  - Deps: D2, B7, F4/F5 (any one).

## Phase G — Default viewpoint library

- [ ] **WU-G1 — Appendix-C library uplift**
  - Files: `src/ontologies/archimate_4/viewpoints.yaml`, new
    `tests/fixtures/viewpoints/standard_viewpoint_tables.py` (transcription of the
    standard's viewpoint-description tables), new
    `tests/domain/test_default_viewpoint_library.py`.
  - Changes: PLAN §6.2 — 21 new + 4 uplifted standard definitions (Tables C-2 … C-26)
    with scope + query + presentation + verbatim metadata; every default scope also
    admits `grouping` and junction elements (C.1 intro); each description carries its
    Table C-1 category where applicable; `layered` (C-6) = Core-domain type union via
    `domain` criteria. Element-name → slug mapping fixed here:
    Node→`technology-node`, Device→`device`, System software→`system-software`,
    Equipment→`equipment`, Facility→`facility`, Distribution
    network→`distribution-network`, Material→`material`, Product→`product`,
    Technology interface→`technology-interface`, Communication network→
    `communication-network`, Path→`path`, Artifact→`artifact`, Application
    component→`application-component`, Application/Business interface→ the respective
    interface slugs, **Process/Function/Service/Event/Role/Collaboration→ the common
    slugs (`process`, `function`, `service`, `event`, `role`, `collaboration`) with NO
    `domain` condition** — these are domain-neutral common entities in this ontology
    (`hierarchy: [common]`; a `domain: business`-style filter would exclude them
    entirely, PLAN §6.2 rule 2); where a viewpoint is clearly layer-scoped despite
    generic naming, narrow via shipped specializations as
    `(specialization in [business-process, …]) OR (specialization absent)` — never
    exclude unspecialized elements (rule 3), Data object→`data-object`, Business object→
    `business-object`, Business actor→`business-actor`, Role→`role`,
    Location→`location`, Stakeholder→`stakeholder`, Driver→`driver`,
    Assessment→`assessment`, Goal→`goal`, Outcome→`outcome`, Principle→`principle`,
    Requirement→`requirement`, Value→`value`, Meaning→`meaning`, Course of
    action→`course-of-action`, Capability→`capability`, Value stream→`value-stream`,
    Resource→`resource`, Work package→`work-package`, Deliverable→`deliverable`,
    Plateau→`plateau`, Core element→ Core-domain type union (via `domain in
    [business, application, technology, common]`). **Verify each slug against
    `entities.yaml` before writing; a slug mismatch is a WU failure, not a rename
    opportunity.** Heat-map styling for `capability-map`/`resource-map` is deliberately
    NOT in this WU (ships in WU-G3, decoupling this library release from the scale-mode
    presentation work).
  - Acceptance: library loads; every definition passes save-mode validation with the
    fixture profiles installed; spec-fidelity test compares purpose/content/stakeholders/
    concerns/element lists against the transcription fixture; every definition returns a
    non-empty population on the seeded fixture repo (scope fallback not needed — all now
    have queries); the common-type mapping is proven by a dedicated test: a fixture repo
    whose processes/services carry NO layer specialization is still selected by
    `process-cooperation`/`application-usage` etc.; version bumps on the four uplifted
    entries.
  - Deps: A3, C2 (grammar). (No F1 dependency — heat rules moved to WU-G3.)

- [ ] **WU-G2 — Impact & cross-layer defaults**
  - Files: `viewpoints.yaml` (append `element-dependents`, `element-dependencies` per
    PLAN Appendix A example 2 incl. the `derived.impact-distance` derived attribute
    (`traversal: derived`, `reduce: min`, `of: relationship.hops` — the reserved source
    from PLAN §4.3, no special-casing), and
    `process-technology-support` per PLAN §6.2: business-process anchor parameter,
    derived-traversal inclusion restricted to technology-domain neighbors,
    `connections.traversal: both`, presentation `diagram`); tests: extend
    `test_default_viewpoint_library.py`.
  - Acceptance: executing `element-dependents` with a fixture anchor returns the known
    transitive dependents with certainty/hops; `process-technology-support` over the
    layered fixture (process ← serving ← app service ← realization ← app component ←
    serving ← tech service ← realization ← node) returns the process + technology
    elements with the derived support connections and NO application-layer elements;
    parameter signatures listed via MCP `list`; all three execute end-to-end via the
    REST parity fixture.
  - Deps: G1, E1, E2, E3b, D1a, D1b, D2.

- [ ] **WU-G3 — Heat-map defaults (`capability-map`, `resource-map`)**
  - Files: `viewpoints.yaml` (add the scale-mode heat rule on a documented profile
    attribute path — present only when the repo defines it; drift rules cover absence);
    tests: extend `test_default_viewpoint_library.py`.
  - Acceptance: both definitions validate with fixture profiles installed; heat legend
    data present in projection output; absence of the profile attribute degrades to
    default style with a drift warning (not an error); version bump on both.
  - Deps: G1, F1.

## Phase H — GUI (GATED: starts only after the frontend rewrite stabilizes — PLAN §10/D12, open question Q4)

Phase-H file anchors name today's components as *expected* locations; the concurrent
frontend rewrite may rename or replace them. **Before starting any H WU, re-verify its
Files list against the rewritten frontend and re-expand the WU in this ledger if the
anchors moved** — the PLAN §10 contracts and each WU's acceptance are the invariants;
component names are not.

- [ ] **WU-H0 — Definition editor: full lifecycle + designed scope picker**
  - Files: `tools/gui/src/ui/` viewpoint editor views/components (against the rewritten
    component set), `tools/gui/src/domain/viewpoint*` mirrors.
  - Changes: PLAN §10 — create/edit/delete of complete definitions (metadata, scope,
    query, presentation) at MCP parity; semantic-edit version-bump surfacing; delete
    shows referencers. Scope (domain/type filter) editor per the PLAN contract:
    domain-grouped collapsible sections, per-domain select-all/none, type-ahead search
    over names+slugs, removable selection chips, live counts and scope-summary sentence,
    entity-vs-connection-type distinction. **A flat unstyled checkbox list fails this
    WU.** Load the frontend-design guidance before building.
  - Acceptance (Playwright unless noted): create a definition with a restricted scope
    via the picker **plus a query containing type/domain criteria**; save, reload, and
    assert the **exact semantic payload round-trips** (serialized definition equality,
    not just visual presence); edit a semantic field and verify the version-bump surface
    appears (and a descriptive-only edit does not bump); submit an invalid query and
    verify the path-addressed error renders on the offending widget; attempt delete of a
    referenced definition and verify the blocked state lists the referencers actionably;
    Query tab renders the existing query for EVERY shipped catalog definition (defect
    regression); scope picker driven by keyboard end-to-end (typeahead, chip removal,
    per-domain bulk select); Vitest per component; lint/typecheck green.
  - Deps: E2, E4, frontend-rewrite gate.

- [ ] **WU-H1 — Builder: bindings, parameters, derived attributes**
  - Files: `tools/gui/src/domain/viewpoint*` mirrors, builder components (against the
    rewritten component set; reuse `CriteriaTreeBuilder` or its successor).
  - Acceptance: author Appendix-A example 1 entirely in the GUI; validation issues map
    by path into the new panels; live summary shows Let-sentences; no text/formula input
    exists anywhere (D4); Vitest per component; `npm run lint`/`typecheck` green.
  - Deps: H0.
- [ ] **WU-H2 — Execution UX: parameters, empty states, non-empty smoke**
  - Files (expected; verify against the rewritten frontend per the phase preamble):
    execution views/composables — today's `ViewpointsManagementView.vue`,
    `ViewpointMatrixView.vue`, `ViewpointDiagramView.vue`,
    `composables/useViewpointExecution.ts`, `ViewpointExecutionDiagnostics.vue` or
    their successors; domain mirrors under `tools/gui/src/domain/viewpoint*`.
  - Changes: parameter-prompt dialog (typed inputs per the `list` parameter signatures,
    `entity-id` via the entity picker); scope-fallback summary rendering; typed-error
    states wired per PLAN §10.
  - Acceptance: parameterized execution prompts typed inputs; scope-only definitions
    show the D9-derived summary and execute non-empty; Playwright smoke: pick a shipped
    default → execute → ≥1 entity rendered (regression for the 2026-07-13 defect
    report); Query tab never renders a blank pane for query-less definitions.
  - Deps: E2, G1, frontend-rewrite gate.
- [ ] **WU-H3 — Impact exploration, derived-candidate review, materialization**
  - Files (expected; verify per preamble): `GraphExploreView.vue` +
    `GraphExploreView.helpers.ts` or successors (derived-edge rendering, toggle
    controls); the generated-diagram/derivation review flow components; the
    connection-creation dialog (pre-fill entry point); `viewpointStyleTokens.ts` or
    successor for certainty/derived edge tokens + scale-legend rendering.
  - Changes: derived-traversal toggle + potential checkbox + hop bound on the explore
    surface (wired to `/api/neighbors`); candidate accept/reject review per §5.7
    defaults; materialize pre-fill; witness-chain popover from `via_connection_ids`.
  - Acceptance: derived edges dashed + certainty badge + witness-chain popover;
    per-occurrence accept/reject with certain pre-accepted / potential pre-rejected and
    type/certainty/witness chain visible at decision time; stale-path refresh findings
    actionable; "materialize connection" pre-fills type/endpoints/description;
    scale-mode legend renders gradient endpoints.
  - Deps: E5, F1, F4–F6, frontend-rewrite gate.
- [ ] **WU-H4 — Pins UI**
  - Files (expected; verify per preamble): `ViewpointsManagementView.vue` (or
    successor) list rows; `HomeView.vue` pinned section; a small pins API adapter in
    the frontend ports/adapters layer.
  - Changes: pin/unpin action per definition row against `GET/PUT
    /api/viewpoints/pins`; Home pinned-definitions section.
  - Acceptance: pin/unpin in management view; pinned list on Home; Playwright covers
    pin → Home roundtrip.
  - Deps: F3, frontend-rewrite gate.

- [ ] **WU-H5 — Failure-mode & accessibility coverage (PLAN §10 failure contract)**
  - Files: Playwright + Vitest suites across the H0–H4 surfaces.
  - Acceptance: validation-400 payload renders as path-addressed inline errors;
    execution timeout, derivation-limit, parameter, and cardinality errors each display
    a distinct actionable error state with no phantom empty result; stale-path refresh
    findings listed and actionable (accept/re-review/remove); failed save (network
    error injected) surfaces retry without losing edits; scope-picker empty search shows
    an explicit no-matches state; accessibility basics asserted — labelled controls,
    focus order through picker and criteria builder, keyboard chip removal.
  - Deps: H0–H3 (may land incrementally per surface; ticked only when all covered).

## Phase I — Docs, self-model, closeout

- [ ] **WU-I1 — Modeling docs**
  - Files: `docs/03-modeling/viewpoints.md` (extend), new
    `docs/03-modeling/impact-analysis.md`, `docs/03-modeling/index.md` (link).
  - Acceptance: PLAN §12 content; worked examples runnable against the dogfood repo via
    MCP; glossary distinguishes relationship vs view derivation; no plan/WU references.
  - Deps: E3a, E3b, G2.
- [ ] **WU-I2 — Reference docs & regenerated surfaces**
  - Files: `docs/reference/viewpoints-schema.md` (extend: grammar, type strings,
    semantics tables, codes, settings incl. WU-A1 keys, parameter signatures),
    regenerated MCP docs.
  - Acceptance: every new validation code and setting documented; `generate_mcp_docs.py
    --check` green; `generate_types.py` current.
  - Deps: E3a, E3b, E4, F1–F3.
- [ ] **WU-I3 — Conformance page & README**
  - Acceptance: PLAN Appendix-B rows added with test-suite pointers; "aims for
    conformance … not independently verified" wording preserved; README capability list
    updated.
  - Deps: B5, G1.
- [ ] **WU-I4 — Self-model sync (MCP only; backend restart may be needed first)**
  - Acceptance: PLAN §13 entities/connections created via MCP after
    `artifact_authoring_guidance` read; `artifact_verify` clean afterwards; no
    argumentative/bundled motivation entities (standing discipline); ledger notes the
    entity ids created.
  - Deps: E1–E4 shipped (model what exists, not intent).
- [ ] **WU-I5 — Closeout sweep (global acceptance)**
  - Run and record: full `pytest` (0 failures), `ruff` (0), `zuban` (pass); all four
    `tests/architecture/` fitness tests green; spec-fidelity suites green (Appendix-B
    per-rule tests + worked examples; Appendix-C table fidelity; direct-model-boundary
    and PDR12-guard properties); round-trip identity suite green incl. schema-2 byte-stability; dogfood
    verification via MCP against the restarted backend — `artifact_query_viewpoint list`
    shows the full library with `query_summary` non-null for every entry,
    `execute` of `element-dependents` on a real entity returns non-empty dependents,
    `artifact_verify` reports no new findings; `rg -i "WU-|phase [a-i]\b|companion plan"
    src/ tests/ tools/gui/src/` clean; frontend gates (lint/typecheck/vitest/Playwright
    smoke) green if Phase H shipped, or Phase H explicitly re-gated in the ledger.
  - Deps: all prior (Phase H may be outstanding only with an explicit gate note).

## Plan exit condition (definition of done)

The plan is **fully implemented** exactly when all of the following hold, evidenced in
the WU-I5 closeout note:

1. Every WU checkbox in Phases A–G and I is ticked. Phase H is either fully ticked, or
   explicitly re-gated with a dated ledger note naming the blocking frontend-rewrite
   state (the only permitted outstanding phase).
2. Every checkbox under "Global acceptance criteria" and "Consistency & failure-mode
   invariants" below is ticked, each backed by a named test/suite or a recorded
   verification step — no criterion is satisfied by assertion alone.
3. The WU-I5 dogfood sweep passed against the restarted backend on the date recorded.

Anything short of this is "in progress", regardless of how many WUs are ticked.

## Global acceptance criteria (plan-level; verified at WU-I5, monitored throughout)

- [ ] Every DR (1–8), PDR (1–12), restriction bullet (R1–R14, RJ1–RJ2), and worked
  example (B-3, B-9, B-11, B-12, B-17) has a named, passing test — spec comparison is
  executable, not asserted.
- [ ] The PLAN §5.3a five-method verification protocol is fully discharged: traceable
  `spec_ref` data, independently-authored dual encoding agreeing cell-by-cell, exhaustive
  metamodel sweep, encoding-independent semantic invariants, worked-example fixtures —
  plus the recorded line-by-line review pass (WU-B6). No Phase D/R2 ship without it.
- [ ] Every shipped viewpoint definition is executable and returns a non-empty population
  on the seeded fixture repo; on the dogfood repo, catalog `list` shows no
  `query_summary: null`.
- [ ] Bindings/parameters/derived attributes are authorable and intelligible on all three
  surfaces (YAML, MCP, GUI-when-shipped) with one shared summary renderer and
  path-addressed validation errors.
- [ ] No new MCP tools; no formula/text query input anywhere; derived relationships are
  never persisted or indexed.
- [ ] All quality gates + all four architectural fitness functions green; generated
  types/MCP docs current; schema-2 definitions parse and re-serialize byte-stable.
- [ ] Zero references to plan/phase/WU identifiers in shipped code, tests, or docs pages.

### Consistency & failure-mode invariants (hold at every release cut, asserted by tests)

- [ ] **Layer invariants**: `src/domain/` imports nothing from application/
  infrastructure (dependency-policy fitness); the domain evaluator never enumerates the
  repository (candidates arrive via `BindingEvaluationInput`); policy crosses the domain
  boundary only as value objects (`RelationshipDerivationRequest`/`DerivationBounds`/
  `DerivationCertaintyPolicy`), transport booleans only at API edges.
- [ ] **No partial results, ever**: timeout, `ViewpointParameterError`,
  `BindingCardinalityError`, and `DerivationLimitError` abort the whole execution with a
  typed error; REST and MCP map every typed error to the same error payload shape (parity
  fixture) with no result content alongside.
- [ ] **Derived relationships never become model state**: no synthetic
  (`derived::…`) id is ever written to a model file, the artifact index, or a
  `CandidateSet.connection_ids`; generated diagrams persist witness *paths* only
  (asserted on written frontmatter); rendering/refresh consume reconstruction outcomes
  only (`Derived | Broken | NoLongerDerives`) — staleness is reported, never
  auto-resolved.
- [ ] **Serialization stability**: schema-2 definitions parse and re-serialize
  byte-stable; `parse ∘ serialize = id` over every valid definition; schema-3 constructs
  in a schema-2 payload are parse errors naming the construct.
- [ ] **Evaluation determinism**: stable item-id ordering everywhere (results, binding
  values, witness-path selection); no wall-clock/randomness outside
  `src/domain/clock.py`; identical model state ⇒ identical execution result.
- [ ] **Membership/provenance consistency**: every non-primary included entity carries
  `via` naming its inclusion source; primary members retained before expanded under
  truncation; connections appear only under the structural/bridging invariants
  regardless of traversal mode.

## Progress notes

- 2026-07-13 — Ledger created from PLAN-viewpoints-bindings-and-derived-relationships.md.
  Backend defect triage: evaluator healthy via MCP ad-hoc execute; shipped defaults are
  scope-only (query_summary null) — remediation = WU-A3 + WU-G1; GUI-side behavior gated
  on the concurrent frontend rewrite (Phase H).
- 2026-07-13 — WU-A1 — Settings accessors and fallback validation shipped; pre-existing file-length-policy failures remain user-authorized non-blocking baseline.
- 2026-07-13 — WU-A3 — Scope-only definitions now execute through an implicit, scope-admissible query; baseline file-length-policy failures remain user-authorized non-blocking.
- 2026-07-13 — WU-A2 — Source Appendix B confirms strength orderings only for structural/dependency relationships; dynamic roles now intentionally carry no strength and the plan table was corrected.
- 2026-07-13 — WU-B1 — Shipped taxonomy classification and all certain pairwise composition rules are covered by pure-domain tests; every ontology now exposes optional YAML-loaded derivation rules, with no ontology-specific rule table or predicate in the evaluator.
- 2026-07-13 — WU-B2 — YAML rules now cover all potential compositions; the Grouping aggregation rule requires a permitted result, and chain certainty records potential steps.
- 2026-07-13 — WU-B3 — Declarative restriction review passed: R1–R14 and RJ1–RJ2 were checked line-by-line against Appendix B and exercised with admitting and rejecting cases.
- 2026-07-13 — WU-B4 — Bounded relationship enumeration now emits deterministic, deduplicated ephemeral witness paths and raises a typed limit error before any partial result.
- 2026-07-13 — WU-B5 — Appendix-B examples are executable; Financial Application proves DR2-derived realization is indirect rather than a direct-table defect.
- 2026-07-13 — WU-B6 — Transcriber/reviewer: Codex; line-by-line spec-to-literal-fixture/runtime review passed with exhaustive and invariant batteries.
