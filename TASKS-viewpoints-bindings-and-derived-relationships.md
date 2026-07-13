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

- [x] **WU-B7 — Path reconstruction (`derive_relationship_for_path`)**
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

- [x] **WU-C1 — Result-type algebra & inference**
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

- [x] **WU-C2 — Binding/parameter/derived value objects + parsing/serialization**
  - Files: new `src/domain/viewpoint_bindings.py`; `src/domain/viewpoint_criteria.py`
    (`ValueRef` new kinds/fields, `VALID_VALUE_REF_KINDS`),
    `viewpoint_criteria_parsing.py`/`viewpoint_criteria_serialization.py` (ValueRef
    mapping forms `{from: binding|parameter, …}`),
    `viewpoint_query_parsing.py`/`viewpoint_query_serialization.py` (top-level
    `bindings`/`parameters`/`derived`, schema-1 query grammar per D10);
    `src/domain/viewpoints.py` (`ExecutableViewpointQuery` fields); tests:
    `test_viewpoint_criteria_parsing.py`, `test_viewpoint_serialization.py` (extend), new
    `tests/domain/test_viewpoint_bindings_parsing.py`.
  - Changes: `QueryBinding`, `QueryParameter`, `DerivedAttribute` (PLAN §4.2–§4.4)
    with `traversal`/`include_potential`/`max_hops` fields (used from Phase D) and the
    three-headed `of` grammar (`connection.<attr>` | `endpoint.<attr>` |
    `relationship.hops` — the reserved derived-hop source, PLAN §4.3);
    parser and serializer use schema 1 only. (The base parser change is shared with
    WU-D1a — whichever of the two lands first introduces it; the other extends the
    construct list.)
  - Acceptance: `parse ∘ serialize = id` over maximal new-shape definitions; unknown keys error;
    Appendix-A examples 1–3 of the new PLAN parse.
  - Deps: C1.

- [x] **WU-C3 — Validation: codes, caps, modes, paths**
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

- [x] **WU-C4 — Evaluation: bindings pipeline, ValueRef resolution, derived attributes**
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

- [x] **WU-C5 — Plain-language summary extension**
  - Files: `src/domain/viewpoint_summary.py` (split a
    `viewpoint_summary_bindings.py` helper if LoC demands),
    `tests/domain/test_viewpoint_summary.py` (extend).
  - Changes: PLAN §4.6 sentences (Let-bindings, parameter placeholders, quantified
    references, derived-attribute phrases, derived-traversal phrasing "connected directly
    or indirectly (up to N steps[, including potential derivations])").
  - Acceptance: every new construct rendered; quantifier+negate interaction phrasing
    pinned; REST/MCP shared-fixture parity test extended.
  - Deps: C4 (types only; may start after C2).

- [x] **WU-C6 — Expressive typed comparison operators**
  - Files: `src/domain/viewpoint_criteria.py`, `viewpoint_criteria_parsing.py`,
    `viewpoint_condition_validation.py`, `viewpoint_condition_evaluation.py`,
    `viewpoint_value_reference_validation.py`, `viewpoint_summary.py`; tests: new
    `tests/domain/test_viewpoint_comparator_evaluation.py`, extend parsing/validation/
    summary tests.
  - Changes: add `not_in`, case-sensitive `like`, and case-insensitive `ilike` to the
    schema-1 grammar. Patterns use SQL-style `%`/`_` wildcards with backslash escaping.
    Apply the same comparator semantics to literal and `ValueRef` operands everywhere
    criteria are accepted. Membership is type-checked for scalar arrays and fixed-arity
    tuples, including `list[tuple[…]]`; tuple membership compares whole tuples.
  - Acceptance: case and escaping behavior; missing-value and negate semantics; literal,
    parameter, binding, and attribute-reference operands; typed list/tuple positive and
    rejected mismatch cases; parser/serializer round-trip and plain-language summaries.
  - Deps: C3, C4.

## Phase D — Derived traversal in the query model

- [x] **WU-D1a — Derived traversal on incident predicate & neighbor inclusion**
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
    `derived-traversal-path-unsupported`, `derivation-hops-exceeded`, and the schema-1
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

- [x] **WU-D1b — Derived traversal for derived attributes (`relationship.hops`)**
  - Files: `viewpoint_binding_evaluation.py` (derived-attribute derived branch);
    tests: extend `tests/domain/test_viewpoint_derived_attributes.py`.
  - Changes: the derived-attribute derived branch + the `relationship.hops` source
    become evaluable (validation: derived traversal only,
    `derived-of-source-traversal-mismatch`).
  - Acceptance: `reduce: min` over `relationship.hops` on the chain fixture yields the
    minimal hop count; direct-traversal derived attributes unaffected (regression).
  - Deps: C4, D1a.

- [x] **WU-D2 — Connection selection, matrix bridging, provenance fields**
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

- [x] **WU-E1 — `EvaluateViewpoint` pipeline, parameters, typed errors**
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

- [x] **WU-E2 — REST surface**
  - Files: `src/infrastructure/gui/routers/viewpoints.py`,
    `viewpoint_authoring.py` (`/summarize`, `/criteria-catalog` additions; new
    `GET/PUT /api/viewpoints/pins` lands in WU-F3); tests:
    `tests/tools/test_gui_router_viewpoints.py` (extend).
  - Changes: `parameters` on the three execute bodies; typed-error → 400 with
    issue-shaped payload (code/path/message); criteria-catalog exposes binding/parameter/
    derived vocabulary + derivation classification + result-type strings (PLAN §9).
  - Acceptance: REST execution supports parameterized and derived-traversal queries, and
    error payload shape is pinned for every typed error (parameter, cardinality,
    derivation-limit, timeout) with no result content. Cross-transport parity for the
    parameterized and derived-traversal fixtures is completed in WU-E3b, where MCP gains
    the matching parameter input.
  - Deps: E1.

- [x] **WU-E3a — MCP graph tool: derived-neighbor mode**
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

- [x] **WU-E3b — MCP viewpoint read tool & help topic**
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
    no partial result, REST parity asserted via the shared fixture for parameterized and
    derived-traversal queries; descriptions short
    (existing description-length test); generated docs check green.
  - Deps: E1.

- [x] **WU-E4 — MCP write tool & lifecycle**
  - Files: `src/infrastructure/mcp/artifact_mcp/write/viewpoint.py`,
    `src/application/viewpoints/persist_definition.py`; tests:
    `test_viewpoint_write_tool.py`, `test_promote_viewpoints.py` (extend).
  - Changes: persist_edit mode over the full new grammar (nothing structural — the
    shared validator does the work; verify paths surface); version-bump classification:
    `bindings`/`parameters`/`derived`/traversal/presentation-scale are semantic content.
  - Acceptance: create→error→fix loop over a binding-cycle payload converges on paths;
    semantic-vs-descriptive bump matrix extended; D14 exact-version promotion regression
    with a schema-1 definition.
  - Deps: C3, E1.

- [x] **WU-E5 — `GET /api/neighbors` derived mode**
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

- [x] **WU-F1 — Scale-mode style rules**
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

- [x] **WU-F2 — `label_attribute` display option**
  - Files: `viewpoint_presentation_validation.py` (validated display option for
    `exploration`/`diagram`), docs note; tests: presentation validation (extend).
  - Acceptance: valid §3.3/`derived.` path accepted; unknown path = save error via the
    existing `unsupported-display-option`/`unknown-attribute` machinery; other
    representations reject it.
  - Deps: C4.

- [x] **WU-F3 — Viewpoint pins**
  - Files: new `src/application/viewpoints/pins.py` (load/save via existing repo-write
    port), `.arch-repo/viewpoint-pins.yaml` convention, `viewpoint_authoring.py`
    (`GET/PUT /api/viewpoints/pins`), `query_viewpoint_tools.py` (`list` pinned flag);
    tests: new `tests/application/viewpoints/test_viewpoint_pins.py`, router test.
  - Changes: PLAN §7 — engagement-repo-local slug list; unknown slugs pruned on read
    with a warning; never promoted (assert in promotion test).
  - Acceptance: CRUD round-trip; absence = empty; module-shipped (read-only) definitions
    pinnable; promotion untouched.
  - Deps: E2/E3b for surfacing (storage part independent).

- [x] **WU-F4 — `viewpoint_execution` view-derivation strategy (persistent results)**
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

- [x] **WU-F5 — `derived_relationships` view-derivation strategy**
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

- [x] **WU-F6 — Rendering derived connections on genuine diagrams (+ refresh staleness)**
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

- [x] **WU-F7 — Wire `label_attribute` into actual rendering**
  - Files: `src/infrastructure/rendering/archimate_entity_declarations.py`,
    `generic_puml_renderer.py`, `diagram_builder.py`,
    `src/infrastructure/gui/routers/viewpoints.py`; tests:
    `tests/rendering/test_generic_puml_renderer.py`, `tests/tools/test_gui_router_viewpoints.py`
    (extend).
  - Changes: WU-F2 validated `display_options.label_attribute` as an accepted display
    option but never consumed it anywhere — an entity never actually showed the
    attribute value, only the styling side of "control display by attribute value"
    (`StyleRule`) was wired. `entity_declaration`/`entity_nest_declaration`/
    `entity_label_and_stereotype` gain an optional `label_attribute` parameter, reusing
    the shared domain `read_attribute_value` reader (never re-deriving attribute-path
    resolution); the value, when present, appends as a second PUML label line
    (`Label\nvalue`). Threaded through `render_body` → `generate_archimate_puml_body` →
    the ad-hoc `execute-diagram` REST endpoint, which reads the option off the resolved
    definition's `presentation.display_options` when executing by slug (an ad-hoc query
    has no saved presentation to read one from, so it never shows one).
  - Acceptance: entity renders with the attribute value as a second label line when
    present on the entity; silent no-op (never a crash) when the attribute is absent or
    no `label_attribute` is configured; slug-executed diagrams pick up the definition's
    saved option; ad-hoc queries never do.
  - Known follow-ups (explicitly out of this WU's scope, not silently dropped):
    `derived.*` label attributes validate (WU-F2) but do not yet render — no derived
    per-candidate value data reaches the renderer at all, which would need an
    `EvaluationEnvironment`-shaped structure threaded through to render time; persisted
    (non-ad-hoc) diagrams do not read `label_attribute` yet, since — per WU-F6 — no
    "regenerate a persisted diagram from its viewpoint definition" pipeline exists in the
    codebase at all; only a single attribute is supported, never a multi-attribute list.
  - Deps: none (extends WU-F2's validated-but-unwired option).

## Phase G — Default viewpoint library

- [x] **WU-G1 — Appendix-C library uplift**
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

- [x] **WU-G2 — Impact & cross-layer defaults**
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
    REST parity fixture. The same generic support-exploration fixture is reconfigured
    with a requirement anchor and process/function/event/service/application neighbor
    types; it proves indirect support and that changing the certainty policy includes or
    omits potential derived relationships without obscuring which relationship is which.
  - Deps: G1, E1, E2, E3b, D1a, D1b, D2.

- [x] **WU-G3 — Heat-map defaults (`capability-map`, `resource-map`)**
  - Files: `viewpoints.yaml` (add the scale-mode heat rule on a documented profile
    attribute path — present only when the repo defines it; drift rules cover absence);
    tests: extend `test_default_viewpoint_library.py`.
  - Acceptance: both definitions validate with fixture profiles installed; heat legend
    data present in projection output; absence of the profile attribute degrades to
    default style with a drift warning (not an error); version bump on both.
  - Deps: G1, F1.

## Phase H — GUI (ungated 2026-07-13, Q4 resolved — see PLAN §10/D12)

Q4 resolved: the only concurrent frontend effort was a LoC-limit file-splitting refactor,
deliberately paused until this plan completes — not a competing UI redesign. Phase H
targets today's `tools/gui/` components directly, in normal ledger order once each WU's
own deps are met. File anchors below still name today's components as *expected*
locations; **before starting any H WU, re-verify its Files list against the current
codebase and re-expand the WU in this ledger if a file has moved or been split** (the
paused LoC refactor may still resume mid-Phase-H and rename/split files without changing
behavior) — the PLAN §10 contracts and each WU's acceptance are the invariants; exact
file paths are not.

- [x] **WU-H0 — Definition editor: full lifecycle + designed scope picker**
  - Files: `tools/gui/src/ui/` viewpoint editor views/components (against the rewritten
    component set), `tools/gui/src/domain/viewpoint*` mirrors.
  - Changes: create/edit/delete of complete definitions (metadata, scope, query,
    presentation) at MCP parity; semantic-edit version-bump surfacing; delete shows
    referencers. Scope editor is hierarchy-aware across domain/category/type and has
    explicit unrestricted / include-only / exclude-from-all modes. Parent selections may
    be expanded and overridden by child decisions; inherited and explicit decisions remain
    visible. It separates entity from connection types, supports type-ahead, selected and
    excluded chips, branch-local bulk actions, live included/excluded counts, and a scope
    summary. It also exposes the retained grouping and styling options by type,
    specialization, group, and discrete profile attribute. **A flat checkbox list with an
    all/none toggle fails this WU.** Load the frontend-design guidance before building.
  - Acceptance (Playwright unless noted): create a definition with a restricted scope
    via the picker **plus a query containing type/domain criteria**; save, reload, and
    assert the **exact semantic payload round-trips** (serialized definition equality,
    not just visual presence); edit a semantic field and verify the version-bump surface
    appears (and a descriptive-only edit does not bump); submit an invalid query and
    verify the path-addressed error renders on the offending widget; attempt delete of a
    referenced definition and verify the blocked state lists the referencers actionably;
    Query tab renders the existing query for EVERY shipped catalog definition (defect
    regression); scope picker driven by keyboard end-to-end (typeahead, include/exclude
    mode, parent selection, child override, chip removal, branch bulk action); Vitest per
    component; lint/typecheck green.
  - Deps: E2, E4, frontend-rewrite gate.

- [x] **WU-H1 — Builder: bindings, parameters, derived attributes**
  - Files: `tools/gui/src/domain/viewpoint*` mirrors, builder components (against the
    rewritten component set; reuse `CriteriaTreeBuilder` or its successor).
  - Changes: replace entity-only wording such as "Show entities where" with a query
    structure that distinguishes primary entity selection, connection selection,
    neighboring context, named bindings, parameters, and derived attributes. Bindings
    visibly declare entity or connection selection and whether their result is included.
  - Acceptance: author a declaration containing an entity binding, a connection binding,
    a parameter, and a derived attribute entirely in the GUI; validation issues map by
    path into the relevant panels; live summary explains each construct; no text/formula
    input exists anywhere; Vitest per component; `npm run lint`/`typecheck` green.
  - Deps: H0.
- [x] **WU-H2 — Execution UX: parameters, empty states, non-empty smoke**
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
- [x] **WU-H3 — Impact exploration, derived-candidate review, materialization**
  - Files (expected; verify per preamble): `GraphExploreView.vue` +
    `GraphExploreView.helpers.ts` or successors (derived-edge rendering, toggle
    controls); the generated-diagram/derivation review flow components; the
    connection-creation dialog (pre-fill entry point); `viewpointStyleTokens.ts` or
    successor for certainty/derived edge tokens + scale-legend rendering.
  - Changes: derived-traversal toggle + potential checkbox + hop bound on the explore
    surface (wired to `/api/neighbors`); candidate accept/reject review per §5.7
    defaults; materialize pre-fill; witness-chain popover from `via_connection_ids`.
    This also supports a non-persisted layered diagram: select named processes/services
    or use criteria, include indirectly connected technology entities, and render only
    those elements plus derived arrows. The same controls also support motivation
    analysis: select requirements or other motivation elements and choose supporting
    process/function/event/service/application neighbor types before rendering a report
    or diagram.
  - Acceptance: derived edges dashed + certainty badge + witness-chain popover;
    Playwright quality flow selects processes/services by name/id (and repeats using
    criteria), chooses a layered diagram without saving, asserts that only the selected
    elements plus indirectly connected technology elements render, and selects a derived
    arrow to see generated witness-chain prose with every entity name as a clickable
    sidebar link; no YAML or formula/text query input is required; Playwright
    motivation-support flow selects a requirement, renders its indirect supporting
    elements, changes the certainty inclusion control, and verifies the result and
    legend distinguish certain from potential relationships;
    per-occurrence accept/reject with certain pre-accepted / potential pre-rejected and
    type/certainty/witness chain visible at decision time; stale-path refresh findings
    actionable; "materialize connection" pre-fills type/endpoints/description;
    scale-mode legend renders gradient endpoints.
  - Deps: E5, F1, F4–F6, frontend-rewrite gate.
- [x] **WU-H4 — Pins UI**
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
    and PDR12-guard properties); round-trip identity suite green for schema 1; dogfood
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
   explicitly re-gated with a dated ledger note naming the specific blocking condition
   (the only permitted outstanding phase) — e.g. if the paused LoC-limit refactor resumes
   mid-Phase-H and genuinely disrupts a WU's anchors before that WU is done.
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
  types/MCP docs current; schema-1 definitions parse and re-serialize byte-stable.
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
- [ ] **Serialization stability**: schema-1 definitions parse and re-serialize
  byte-stable; `parse ∘ serialize = id` over every valid definition; unsupported schema
  versions are parse errors naming the version.
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
- 2026-07-13 — WU-B7 — Recorded witness paths reconstruct through the shared composition logic; broken and no-longer-derived states are explicit.
- 2026-07-13 — WU-C1 — Canonical result types and conservative inference cover cardinality, projections, aggregates, and tuple compatibility.
- 2026-07-13 — WU-C2 — Bindings, parameters, derived attributes, and ValueRefs now parse and serialize declaratively; the pre-release query language is explicitly schema 1 only, with all persisted examples and GUI fixtures migrated.
- 2026-07-13 — WU-C3 — Typed declarations and ValueRefs validate across query and presentation criteria with stable paths, mode-aware caps, and declared-type checks.
- 2026-07-13 — WU-C4 — Pure binding execution, runtime cardinality checks, ValueRef environments, and direct derived attributes are deterministic and covered.
- 2026-07-13 — WU-C5 — Shared summaries now describe parameters, bindings, ValueRef forms, and derived attributes for every surface.
- 2026-07-13 — WU-D1a — Derived incident and neighbor traversal use bounded relationship derivation with declarative grammar, validation, and direct-mode regressions.
- 2026-07-13 — WU-D1b — Relationship-derived attributes now reduce bounded witnesses, including minimum hop counts, without changing direct attributes.
- 2026-07-13 — WU-D2 — Derived connections remain ephemeral while selection, matrices, projection, and execution summaries retain deterministic witness provenance.
- 2026-07-13 — WU-E1 — Execution binds typed parameters, resolves scoped candidates once, and shares binding/derived values throughout criteria evaluation.
- 2026-07-13 — WU-E2 — REST execution and builder discovery expose typed parameters, derived traversal, ontology derivation metadata, and uniform issue payloads.
- 2026-07-13 — WU-E3a — MCP neighbor queries expose bounded derived witnesses and fail atomically on derivation limits.
- 2026-07-13 — WU-E3b — MCP viewpoint execution accepts typed parameters, surfaces structured errors, and matches REST for parameterized derived traversal.
- 2026-07-13 — WU-E4 — Shared persist validation accepts the full query grammar and lifecycle tests cover binding cycles and parameter version bumps.
- 2026-07-13 — WU-E5 — REST neighbor traversal shares MCP's derived witness metadata and atomic derivation-limit behavior.
- 2026-07-13 — WU-F1 — Scale styles now emit deterministic bounds, opaque endpoint tokens, normalized adapter positions, and projection legend data.
- 2026-07-13 — WU-C6 — Blocked before implementation: PLAN §2 locks the comparator vocabulary as `eq neq in exists absent lt lte gt gte` ("no new comparators … not reopened"), directly contradicting WU-C6's proposal to add `not_in`/`like`/`ilike`; the runtime already omits `not_in` on purpose (`negate`+`in` covers it, "one spelling per meaning"). Escalated to the user rather than improvising around a locked decision.
- 2026-07-13 — WU-C6 — User resolved the escalation: reopen the lock narrowly for `not_in`/`like`/`ilike` (PLAN §2 updated accordingly); comparators added end-to-end (parse/validate/evaluate/summarize) with SQL-style pattern matching applied uniformly to scalar and multi-valued attributes, and to literal/parameter/binding/attribute-reference operands alike.
- 2026-07-13 — WU-F2 — `label_attribute` validated as a display option distinct from the styling-capability namespace: allowed only on `exploration`/`diagram`, its value resolved through the same reserved/profile/`derived.` attribute-path machinery as every other attribute reference.
- 2026-07-13 — WU-F3 — Pins are an engagement-repo-local sidecar list (CRUD via REST, surfaced on MCP `list`); a direct `plan_promotion`/`execute_promotion` run (no git dependency at that layer) confirms the sidecar is never copied to the enterprise repo.
- 2026-07-13 — WU-F4 — Design gap: the shared `DeriveFn`/`ModelQuery` contract every strategy implements against carries no repo-root paths, so a pure `derive()` cannot reach a `ViewpointCatalog`/`RegistrySnapshot`. User-approved resolution: generation-time `params["repo_roots"]` (plain data, no shared-type change) plus a composition-root closure (`src/infrastructure/derivation_strategy_wiring.py`) that builds the real catalog/registries/read-access and calls the pure `evaluate_candidates`/`default_selection` in `viewpoint_execution.py`; entity/connection inclusion still follows the read-access's own cross-repo enumeration, only the catalog/registries load is roots-scoped.
- 2026-07-13 — WU-F5 — Reused the same composition-root-closure resolution as WU-F4 for the ontology `ModuleCatalog` (roots-independent, but still infra-built); reachable entities also pull in every witness-chain hop (not just each derived relationship's own endpoints) so included connections always satisfy the structural invariant.
- 2026-07-13 — WU-F6 — User-approved data-model extension (`DerivationSelection.path_provenance`) closed the certainty/type-drift gap; refresh now reconstructs every accepted path for real. Both render contexts (ad-hoc diagram, and a resolve-accepted-paths function proven against the real renderer) draw derived connections dashed/dotted with certainty distinguished — the "regenerate and persist a diagram from a strategy" orchestration itself doesn't exist anywhere in the codebase yet (confirmed by investigation, not introduced or removed here), so the resolver is built and tested standalone pending that wiring.
- 2026-07-13 — WU-G1 — 25 definitions transcribed (4 uplifted to v2, 21 new); no viewpoint needed the specialization-narrowing fallback since no spec table actually said "Business Process" unqualified. Fixed a genuine pre-existing regression in `test_scope_fallback.py`, which hardcoded the shipped catalog's now-obsolete scope-only shape; replaced with synthetic fixtures preserving the same D9 coverage.
- 2026-07-13 — WU-F7 — User flagged that "showing attribute values with entities" (as distinct from styling by attribute value, already wired) had no renderer consumer despite WU-F2 validating it; added and closed same-session. `derived.*` label attributes and persisted-diagram rendering remain explicit, undropped follow-ups (both blocked on data/pipelines that don't exist yet, not on this WU).
- 2026-07-13 — SESSION HANDOVER (session ended on low budget): WU-G2 was dispatched to a background fork (prompt: author `element-dependents`/`element-dependencies`/`process-technology-support` per Appendix A example 2 + §6.2) but **no completion notification was received before this session ended** — working tree is clean (git status empty), so the fork had not yet written files, or its result is sitting unclaimed. Next session: check whether that fork is still resumable (it may have finished after this session ended); if not recoverable, just re-run WU-G2 from its ledger entry (unmodified, still accurate) using the same approach as WU-G1 (delegate to a fork with the Appendix A Example 2 YAML + §6.2 text inlined in the prompt — see the WU-G1/WU-G2 dispatch prompts in this session's transcript for the template if available, otherwise reconstruct from the ledger + PLAN §6.2 + PLAN Appendix A directly). All WUs through WU-G1 and WU-F7 are ticked, verified (gates green modulo the 3 known pre-existing baseline failures), and committed — safe to build on. Remaining ledger work after WU-G2: G3, all of Phase F2/F3 already done, F4-F6 done; Phase H (gated on frontend rewrite — check its status before starting), Phase I (docs/self-model/closeout).
- 2026-07-13 — WU-G2 — The fork from the handover above completed after session resume; reviewed and verified independently before landing. Three real, verified deviations surfaced (not fixture choices): (1) PLAN Appendix A Example 2's certainty/hops-keyed `edge_emphasis` style rule doesn't save-mode-validate — `certainty`/`hops` are reserved only inside derived-traversal match criteria, never registered as general style-rule paths; dropped that one rule, kept the `derived.impact-distance` scale rule, which does validate. (2) The ledger's literal serving→realization chain does not compose past 3 hops under the real DR/PDR table; test fixtures use an all-`archimate-assignment` chain instead (production YAML unaffected — this is a test-fixture-only substitution). (3) `element-dependents`/`element-dependencies`'s locked `traversal: derived`-only `include_connected` excludes the anchor's immediate 1-hop neighbor by construction (a derived relationship needs 2+ composed links) — flagged as a possible "impact of change should include direct dependents too" gap, not fixed (would mean changing that inclusion's `traversal` from `derived` to `both`); left locked, decision deferred. `process-technology-support`'s "(or executed broad)" anchor shipped as **required**, not optional — the query grammar has no conditional-branch mechanism for an unsupplied optional parameter (an unresolved `{from: parameter}` reference just yields empty, not "broad"), a real grammar limitation, not silently worked around.
- 2026-07-13 — WU-G3 — Fixed a genuine pre-existing bug surfaced while testing: `_scale_value` (scale-mode per-item styling) read raw `extra` data directly, bypassing the schema-drift contract every other comparator/style path honors (`resolve_attribute_path` first, treat unresolvable as absent) — an entity happening to carry a stray `investment_level`-shaped key would silently render a heat position even in a repo that never declared the attribute. Fixed at the source (`viewpoint_style_evaluation.py`), mirroring `_range_token`'s existing pattern; added fixture profile schemas (`attributes.capability.schema.json`/`attributes.resource.schema.json`) so the shared library-wide save-mode-validation test covers the new attribute path.
- 2026-07-13 — WU-H0 groundwork (design gap, user-approved) — `ConceptScope` (the domain type the scope picker's "exclude-from-all" mode must serialize to) had no exclusion/negation primitive at all: purely allow-list-style admission. Extended it with `excluded_entity_types`/`excluded_hierarchy_predicates`/`excluded_connection_types` (subtraction, not a second allow-list — a domain-level exclusion predicate keeps excluding new types added to the ontology later, unlike a frozen enumerated deny-list), `__and__` unioning exclusions from both sides, and threaded the new authoring grammar (`excluded_entity_types`/`excluded_domains`/`excluded_connection_types`) through parsing/serialization/validation/guidance-summary. Also fixed a real, separately-discovered gap while wiring validation: `validate_viewpoint_definition` never threaded `entity_type_infos` through to the `RegistrySnapshot` it builds, even though every real caller already has it available — domain-level validation (new or old) was silently impossible through the public entry point; fixed at all 3 production call sites. This is backend groundwork only — WU-H0 itself (the actual Vue scope-picker component + Playwright coverage) is not yet started.
- 2026-07-13 — WU-H0 — Rebuilt `ViewpointScopeTab.vue` as a hierarchy-aware, domain-grouped picker (unrestricted/include-only/exclude-from-all per entity and connection types, type-ahead, branch bulk actions, inherited-vs-explicit exclusion chips, full keyboard operability) plus full create/edit/delete lifecycle wiring (semantic-edit version-bump hint, path-addressed validation highlighting, referenced-delete blocking). Independently verified rather than trusted at face value: the delegated build's own Playwright spec initially had 4 failing tests, all genuine test-authoring bugs (ambiguous `getByRole('button', {name:'Save'})` matching the pre-existing nav-bar save indicator too; asserting on `Test run`'s unstyled ad-hoc `/execute` path instead of `Save`'s real `persist_edit` validation for path-addressed errors; an ambiguous row locator matching multiple catalog entries whose names/scopes substring-contain the target slug; keyboard-nav test focusing the wrong radio before counting `ArrowRight` presses) — fixed all four in the spec. That run also caught one genuine pre-existing bug, unrelated to this WU and predating this session (frontend `QUERY_SCHEMA_VERSION` was `2`, backend's is `1`, so any GUI save carrying a query was rejected with `unsupported query_schema`) — fixed at the source in `viewpointCriteria.ts`. All 6 new e2e tests, the full 38-test smoke suite, 646 Vitest tests, typecheck, and lint are green; also cleaned two stray "WU-H0"-prefixed naming violations in the new spec and a leftover "companion plan §7.1" comment in `ViewpointQueryTab.vue`, and removed test-run pollution (a leaked test viewpoint + orphaned rendered-diagram byproducts) that an earlier uncleaned run had left in the real `ENG-ARCH-REPO` self-model repo.
- 2026-07-13 — WU-H1 — Built on a background fork's partial, independently-verified groundwork (`ValueRef` binding/parameter kinds, `not_in`/`like`/`ilike` comparator exposure, the picker plumbing) by adding the three authoring panels themselves (`QueryBindingsPanel`/`QueryParametersPanel`/`QueryDerivedAttributesPanel`, each with a `.helpers.ts`/test pair), wiring them into `ViewpointQueryTab.vue` in pipeline order (parameters → bindings → primary criteria → derived attributes → neighbor inclusions → connections), extending `resolveIssuePathNodeId` for path-addressed validation into the new panels, and threading real attribute types into every `definitionToMapping`/`queryToMapping` call site (a `project`ed binding's declared type was silently defaulting to `string` otherwise). Live-browser verification (not just automated gates) caught two real, independent bugs, both fixed at the source: (1) the criteria-catalog's `connection_derivation[...].strength` REST field is an `int`, but the frontend schema declared it `Schema.String`, making the entire viewpoints page fail to decode and load at all — fixed in `schemas/viewpoints.ts`; (2) a genuine backend defect in `_validate_reference_type` (`viewpoint_value_reference_validation.py`): a `ListType` reference was unwrapped to its scalar element before the `in`/`not_in`-requires-a-list check ran, so a correctly-typed binding-projected list (`id in {from: binding, name: x, project: id}` — the exact PLAN §4.2.1 "no new node kind" use case) was always rejected; the one existing test for this path only asserted the wrong error code was absent (`unquantified-set-comparison`) and missed that a different one (`operator-type-mismatch`) was always present, so it passed while the feature was completely broken — fixed the validator and tightened the test to assert zero issues (verified failing pre-fix via `git stash`, passing post-fix). Also added GUI authoring for binding references inside `in`/`not_in` conditions (`ConditionRow.vue`), which the fork's own scope didn't cover but is the most natural use of a binding. The backend fix awaits a process restart (deferred to the user per convention) to be observable live in the GUI; it is proven correct independently via a pytest regression test. 9/9 new Playwright tests (6 WU-H0 regression + 3 new WU-H1), 44/44 combined e2e including full smoke, 693/693 Vitest, 4904/4907 pytest (3 pre-existing unrelated baseline failures, unchanged), ruff/zuban clean.
- 2026-07-13 — WU-H2 — Built on a background fork's independently-verified execution UX (shared `useViewpointParameterPrompt` gate + typed `{code,path,message}` error display wired consistently across all 4 execution surfaces — table/matrix/diagram/exploration; typed entity-id inputs via the existing entity picker). The fork also found and fixed a real, separately-discovered bug while testing: `execute_viewpoint`/`execute_viewpoint_projection`/`execute_viewpoint_diagram`/the diagram-projection endpoint all read `viewpoints` from the `app.state`-cached `RuntimeCatalogs` snapshot frozen at process startup, so an engagement-repo definition created (or semantically edited) through the GUI could never be executed by slug until a full backend restart — `viewpoint_authoring.py`'s own endpoints already avoided this staleness; the execution routes now share the same request-scoped `fresh_viewpoints_runtime_catalogs_dependency`, proven via a new regression test that fails pre-fix and passes post-fix. My own follow-up investigation (prompted directly by the stated ~100k-entity/12-concurrent-user scaling requirement) found a second, independent, more serious defect while probing this same execution path: `_prepare_query_environment` computed every `traversal: derived` derived attribute eagerly for the *entire scoped population* before primary-criteria filtering ever ran, contradicting the pipeline's own documented "lazily, memoized" contract — for `element-dependents` (a real shipped definition) this meant 289 seconds against the ~300-entity dogfood repo even when the supplied parameter matched *zero* entities, since the eager sweep ran regardless of match count. Fixed in two parts, both proven against the real dogfood repo (289s → 1.3s) and via new regression tests spying on `derive_relationships` call counts: (1) `viewpoint_derived_attribute_deferral.py` statically splits a query's derived attributes into criteria-referenced (must stay eager, needed for filtering) versus presentation-only (deferred to just the retained population, computed in `repository_projection.py` right before style-token evaluation); (2) `viewpoint_derived_relationship_batch.py` folds every entity needing a given `traversal: derived` attribute into one combined `derive_relationships` call instead of one call per entity — verified safe both empirically (a bridging-topology probe: batched multi-anchor results identical to solo single-anchor results) and structurally (the BFS/queue design processes every anchor's own local neighborhood before any anchor's deeper frontier, so no anchor's own relationships are ever shadowed by another's traversal — the same guarantee `resolve_neighbor_inclusions` has relied on for its own multi-entity anchor sets since it shipped), restoring the PLAN's own stated "O(V·E)... bounded for 10⁴-entity repos" complexity claim (a single combined call, not one call times the retained-population size). `BindingEvaluationInput` and the `count|sum|avg|min|max` reduction moved to neutral shared modules to keep this acyclic. Also fixed, at the user's explicit instruction that no pre-existing gate failures beyond the tracked LoC backlog are acceptable: a real zuban type error in `artifact_projection.py` (a local variable typed `Mapping[str, str]` was actually assigned `Mapping[str, str | ScaleStyleValue]` from `evaluate_item_style`) and a real broken test in `test_pair_legality_guidance.py` (`get_ontology` had been moved from `connections.py` to a nested closure in `connection_read_routes.py` during an earlier reorganization, leaving two tests importing a name that no longer existed there; rewritten against the real REST endpoint via `TestClient`, matching the established sibling-file pattern). 50/50 e2e (38 smoke + 6 WU-H0 + 3 WU-H1 + 3 new WU-H2, one unknown-slug scenario dropped after direct browser inspection showed the GUI silently falls back to unrestricted for an unmatched viewpoint slug rather than attempting execution — a real UX question flagged, not fixed, out of this WU's scope), 732/732 Vitest, 4910/4910 pytest (0 unrelated failures; only the tracked LoC backlog remains), ruff/zuban both fully clean.
- 2026-07-13 — WU-H2 follow-up — Live end-to-end verification against the just-restarted backend (both scaling and staleness fixes reconfirmed live: the exact dangling-anchor query that took 289s pre-fix now completes in ~3ms; a real anchor match completes in ~5s and returns the correct 11 entities) surfaced three more real, previously-undiscoverable bugs, all fixed: (1) `EntityPickerInput`'s dropdown never closed after a selection — deliberate for its 9 other multi-add consumers, but inside the compact `ViewpointParameterPrompt` dialog it left a domain-filter chip covering the Run button, blocking the click; fixed via a new opt-in `closeOnSelect` prop (default off) used only by the parameter prompt. (2) The client-side fetch timeout was a flat 10s for every REST call including viewpoint execution — too short for a real derived-relationship query against a cold post-restart index (confirmed live: the exact same anchor that returns correctly via direct curl timed out from the browser at 10s); the four execution routes now use a dedicated 60s timeout, leaving the fast-fail 10s default everywhere else. (3) Most importantly, that same timeout was being silently misreported: when execution actually failed, the diagnostics panel still rendered "No entities in the current model match this viewpoint's criteria" *simultaneously* with the "Execution failed" error banner — a real request failure was indistinguishable from a genuine empty result, which is exactly what made the timeout look like a data/scoping bug during live testing rather than a network-layer one. Fixed by gating the diagnostics panel on the absence of an execution error across all four execution surfaces (exploration/table/matrix/diagram). All three proven via a new Playwright regression test (confirmed failing pre-fix, passing post-fix by reverting the diagnostics-gating change locally, not via `git stash`). 51/51 e2e, 732/732 Vitest, typecheck/lint clean, 4910/4910 pytest (only the tracked LoC backlog remains), ruff/zuban clean.
- 2026-07-13 — WU-H3 — Scoped to the ephemeral, non-persisted flow only (user-confirmed): a "build a layered view / motivation-support view" surface at `/graph/layered` built entirely on the already-complete ad-hoc `query` viewpoint-execution path — no new persistence orchestration, since the full "generate+persist a diagram from a strategy" machinery (`view_derivations.py`/`refresh.py`/`path_staleness.py`) remains unwired from WU-F6 and stays out of scope. New: `layeredViewQuery.ts` (ad-hoc query construction), `derivedCandidateReview.ts` (ephemeral accept/reject state, certain-pre-accepted/potential-pre-rejected, stale-on-rerun detection — no persistence at all, by design), `witnessChainProse.ts` (chain reconstruction + prose), `LayeredExplorationView.vue`/`LayeredViewBuilderPanel.vue`/`CandidateReviewPanel.vue`/`WitnessChainPopover.vue`/`MaterializeConnectionDialog.vue`. Extended the frontend's own criteria-authoring model to add real `traversal`/`include_potential`/`max_hops` fields to `NeighborInclusionNode`/`ConnectionSelectionNode` (previously entirely unrepresented — no one had authored a derived-traversal query through the visual builder before). Witness-chain reconstruction uncovered a real, non-obvious domain finding: `via_connection_ids` is not guaranteed in source-to-target order (the derivation engine can extend a composed chain from either end as it discovers adjacent connections — confirmed against a real 4-hop derived relationship, scrambled order reproduced as a regression test), so the walk reconstructs the path from the unordered edge set via a proper graph walk instead of trusting array order. Live verification surfaced and fixed three further defects: (1) the layout put the entity-picker (whose dropdown is fixed-positioned and fills the remaining viewport while open) directly above the certainty/hop-bound/Render controls, blocking them; reordered so root selection is last, preserving multi-add. (2) A far more serious, previously-undiscovered bug: `mode: "scale"` style rules (e.g. `element-dependents`' real shipped heat-map coloring) were completely broken on the frontend — the wire payload for a scale-styled item is `{position, tokens}`, but `ProjectedOccurrenceSchema.style` only accepted strings, so decoding failed wherever such a viewpoint rendered; proven via a schema regression test using the exact real payload captured live, fixed by adding `ScaleStyleValueSchema`/a proper `scale` mode (distinct from `range`) across `viewpointPresentation.ts`/serialization/legend/`resolveStyleColor` (RGB interpolation between the rule's two declared endpoint tokens). (3) A real Vite dev-proxy bug: `vite.config.ts`'s `/api` proxy context had a flat 10s timeout that silently killed concurrent viewpoint-execution requests (every execution surface fires content+projection concurrently) even though the backend itself answers in ~5-6s — reproduced directly with two simultaneous curl requests through the proxy (both dying at exactly 10s); fixed with a longer-timeout exception mirroring the existing SSE pattern. That investigation led to a substantially more consequential finding, pursued at the user's explicit direction to look for genuinely optimal graph algorithms/data structures rather than accept the ~5-6s per-query cost: direct cProfile profiling of `element-dependents` against the real dogfood repo found `derive_relationships`'s BFS had no memoization at all — `_adjacent_connections` re-fetched the same entity's connections from the underlying (dual-repo, thread-dispatched) store every time that entity was revisited across different partial paths (18,010 real calls for a traversal touching a few dozen entities), and `compose`'s rule-matching linearly scanned every declared composition rule for each of 121,267 candidate compositions (2.97M `_matches` calls). Fixed with the standard techniques for each: a call-scoped `_MemoizedReadAccess` wrapper (correctness rests entirely on it never outliving one call — documented in its own docstring) cutting real store round-trips 18,010→894, and a `(first_role, second_role)`-keyed discrimination index narrowing candidate rules before matching (2.97M→175K `_matches` calls) — combined, 12.2s→1.94s (6.3x) on the same real query, verified via a new regression test proving each entity's adjacency is fetched at most once (confirmed failing pre-fix with a diamond-topology graph, passing post-fix). 57/57 e2e (54 prior + 3 new layered-exploration specs, the motivation-support one spanning business/application/common domains for one goal per explicit direction to prove the neighbor-type criteria isn't domain-narrow), 766/766 Vitest, 4911/4911 pytest (only the tracked LoC backlog remains), ruff/zuban/typecheck/lint all clean.
- 2026-07-13 — WU-H4 — Pins UI: `getViewpointPins`/`setViewpointPins` added to the `ModelRepository` port/adapter/service (the REST endpoints already existed from F3), pin/unpin star button per row in `ViewpointDefinitionsList.vue`, a self-contained `PinnedViewpointsSection.vue` mounted on `HomeView.vue`, and a shared `executionRouteFor` helper (extracted from the list's own execution routing) so a pinned slug always lands on its representation-appropriate surface. A fresh-restart user bug report ("viewpoint execution seems completely broken... disconcerting that any e2e tests succeeded") was investigated claim-by-claim with live evidence before any fix, surfacing four real, independent, previously-undiscovered defects, all fixed: (1) opening any non-engagement-tier definition via "View" showed a fully editable form with an enabled Save button that errored on click — no tier gating existed in `ViewpointsManagementView.vue`; added a `viewingTier`/`isReadOnly` gate that hides Save and explains why. (2) `GraphExploreView.vue`'s own in-page viewpoint dropdown executed every selection as graph-exploration regardless of the definition's declared representation (unlike the management list's already-correct `executionRouteFor` routing); fixed via a new pure `explorationRedirectFor` helper redirecting non-exploration picks to their real surface. (3) The most severe: the `group_by`-driven cluster layout (`applyGroupClusterLayout` in `useForceGraph.ts`) reused the root-anchored dendrogram algorithm built for expand/collapse adjacency trees, where Y is purely `depth * levelGap` — but its synthetic group-tree puts every leaf entity at the same depth (2) regardless of group, so an entire population collapsed onto one shared Y coordinate spread across a pathologically wide X (confirmed live: 97-entity Goal Realization rendered as one line requiring horizontal scroll); replaced with a proper 2D shelf-packed box layout (`buildClusterBoxes`/`layoutGroupClusters`) giving each group its own grid region, proven via a regression test confirmed failing pre-fix (all nodes collinear) and passing post-fix (multiple Y bands, bounded canvas, no scroll overflow). This also fully explained the user's fourth claim ("unusably slow for larger results, application structure, goal-realization") — both named viewpoints hit this exact bug (one via claim #2's redirect gap, one directly), not a separate performance regression; real backend timing (<150ms per call, matching WU-H3's earlier profiling fix) ruled out a backend cause. A further live bug report arrived mid-fix (ephemeral ArchiMate diagrams render too big with no resize, and entities/connections aren't selectable/no sidebar) — confirmed both: `ViewpointDiagramView.vue` had no pan/zoom/fixed-viewport and no click-to-select at all, unlike `DiagramDetailView.vue`'s established UX for a real persisted diagram. Fixed at the correct layer rather than duplicating: `useFittedPanZoom`/`useSidebarResize` are already fully generic and reused verbatim; `useDiagramSvgSelection`'s `detail` parameter was narrowed from the full `DiagramContext['diagram']` type to a new minimal structural `DiagramSvgSelectionDetail` (`diagram_type` + optional `diagram_entities`) since those are the only two fields it ever reads — letting the ephemeral, never-persisted rendering satisfy the contract honestly instead of forcing fake `artifact_id`/`version`/`status` placeholders onto it; `toDiagramConnectionStub` gained an optional name-lookup so the sidebar's connection-flow line shows real entity names; the edge-label editor naturally stays hidden with no extra gating since the stub never carries a real `edge_key`. Live-verified end to end (large `technology-usage` diagram now renders in a bounded, pannable/zoomable container with a working 186-entity sidebar; clicking an entity fetches and shows its real detail). 15 new e2e tests across `viewpoint-editor.spec.ts`/`viewpoint-execution-ux.spec.ts`/new `viewpoint-pins.spec.ts`/new `viewpoint-diagram-view.spec.ts`, all confirmed failing pre-fix and passing post-fix; one unrelated pre-existing e2e failure (`viewpoint-editor.spec.ts`'s ambiguous `getByRole('button', {name:'Edit'})` substring-matching the new pin button's `aria-label` on slugs containing "editor") fixed with `exact: true`; also cleaned up orphaned test-viewpoint artifacts a prior failed run had left in the real repo. 61/61 e2e, 779/779 Vitest, typecheck/lint clean; backend untouched this WU (pytest/ruff/zuban re-confirmed clean modulo the tracked LoC backlog).
- 2026-07-13 — Post-H4 hardening — Helped construct a real bulk motivation-support use case ("all motivation entities + connected application/common entities, direct or derived") and hit `derivation-limit` immediately: profiling `derive_relationships` directly against the real repo (109 real anchors, 4 hops, include-potential) proved the algorithm itself is efficient (2,783 already-deduplicated relationships in 1.16s) — the `max_relationships=2000` hard-stop was an arbitrary count with no relationship to actual cost, rejecting a perfectly tractable multi-anchor query. Replaced the primary enforcement mechanism with a wall-clock time budget (`DerivationBounds.time_budget_seconds`, default 2.0s, user-confirmed): `derive_relationships` now stops gracefully at the budget and returns a genuine partial result flagged `truncated`, propagated as a warning through `NeighborInclusionResult`/`ConnectionSelectionResult` into `ViewpointProjection.warnings` (and from there into every execution surface's warnings, since they all read `projection.warnings`); `max_relationships` stays only as a hard memory-protection ceiling, raised 2000→20000 so it shouldn't realistically fire once the time budget is in place. Threaded `derivation_time_budget_seconds`/raised `derivation_max_relationships` through every `DerivationBounds`/`RegistrySnapshot`/`build_registry_snapshot` call site (population evaluation, criteria evaluation, derived-attribute batching, connection-neighbors REST, MCP graph/viewpoint tools). A live click-to-select report on the ephemeral diagram view led to a second real, confirmed bug: `execute_viewpoint_diagram`'s rendered SVG node/edge ids are PlantUML's own generated aliases (`normalize_puml_alias(entity.display_alias)`), never the raw artifact id — contradicting `toEntitySummaryStub`'s prior "alias === artifact_id" assumption, which held for real persisted diagrams (whose `display_alias` the backend already resolves correctly) but not for this ephemeral, execution-result-only path where the frontend never received the real alias at all. Fixed by having `execute_viewpoint_diagram` return a new `entity_aliases` map (entity id → normalized alias) alongside `svg`/`warnings`, threaded through `toEntitySummaryStub`/`toDiagramConnectionStub`'s new alias-lookup parameter — live-verified 84/84 and 205/205 entities now correctly clickable. A further live report ("arrows invisible until hover") uncovered a second, more severe bug in the SAME view: `applyNodeColorOverlay`/`applyEdgeHighlightOverlay`'s `setOrClearStroke` called `shape.style.removeProperty('stroke')` whenever no viewpoint style applied to a node/edge (the common case) — but PlantUML's native stroke lives in that SAME `style="..."` attribute, so "clearing an absent overlay" was silently deleting the renderer's own native styling on every unstyled connection (invisible, since connector paths are `fill="none"` and depend entirely on stroke) and every unstyled entity border; only visible on hover because the hover CSS injects its own `!important` stroke. Fixed by never clearing, only ever setting an override when a real style value exists — sound because this view always renders a fresh SVG per execution (`v-html` replaces the whole tree), so there is never a stale prior overlay on any element to revert. Both fixes are backend/frontend regression-tested (profiling-derived time-budget test, alias-lookup unit tests, and two native-stroke-preservation tests proven failing pre-fix). Also fixed, found while re-running full gates: (1) a genuine LoC-policy regression I introduced earlier this WU (`useForceGraph.ts` crossed 350 lines) — extracted the cluster/dendrogram layout helpers into a new pure `useForceGraphLayout.ts`; (2) two settings-monkeypatch tests broken by the `settings.py`→`viewpoints_settings.py` split (a `from X import name` binds its own reference at import time, invisible to a later `monkeypatch.setattr(settings, name, ...)` — fixed by having the new module read `settings.load_settings()`/`settings._DEFAULTS` through the module object, never as directly-imported names); (3) a third real, confirmed staleness bug in the SAME class WU-H2 fixed for execution routes: `/api/authoring-guidance` (which `GraphExploreView.vue`'s own viewpoint dropdown reads to resolve a `?viewpoint=` slug) still used the app-state-cached `runtime_catalogs_dependency`, so a just-created engagement viewpoint was invisible there until a restart, silently leaving the dropdown on "None (unrestricted)" with an empty result — confirmed live (`motivation-technology-support`, created moments earlier, didn't resolve). Fixed by extracting the fix's own `fresh_viewpoints_runtime_catalogs_dependency` out of `viewpoints.py` into a shared `_viewpoint_freshness.py` (both routers now depend on the same one function, not two copies) and switching `authoring_guidance.py` to it; new regression test confirmed failing pre-fix. 4911/4911 pytest (only the tracked LoC backlog remains, two more transient timing flakes confirmed passing in isolation), ruff/zuban clean; frontend typecheck/lint/Vitest clean (781 tests). Still open: the user separately asked that derived-relationship arrows be selectable with their witness chain shown in the sidebar — not yet implemented; requires a backend restart before any of this segment's fixes are live-testable.
