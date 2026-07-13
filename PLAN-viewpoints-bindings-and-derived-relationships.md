# Viewpoints II: Typed Query Bindings, Derived Relationships & Impact Analysis, Default Library

Companion plan to `PLAN-viewpoints-query-model.md` (which stays authoritative for the shipped
criteria engine, projection contract, presentation model, validation modes, and MCP surface)
and successor to two explicitly deferred items of `PLAN-archimate-4-compliance.md`:
**Q7** (general named-binding / query-expression layer for `ValueRef`) and the **Q6
remainder** (deferred viewpoint scope). It additionally delivers the planned
**indirect-relationship derivation and impact analysis** capability (ArchiMate 4.0
Appendix B) and an **executable default viewpoint library** (ArchiMate 4.0 Appendix C).

Execution ledger: `TASKS-viewpoints-bindings-and-derived-relationships.md` (authoritative
for work-unit numbering, dependencies, and acceptance wording).

**Status: draft for review.** All decisions below are proposed-and-argued; §16 lists the
genuinely open points.

## 1. Why this document exists

Four forces converge:

1. **Q7 is unblocked.** The parent plan shipped (2026-07-12) and confirmed the direction:
   build the *general* named-binding layer — named sub-queries with a declared result type,
   reference-only or result-included, usable as a `ValueRef` target anywhere (the
   BiZZdesign Query Language precedent) — rather than a narrow `attribute_of_anchor` patch.
   `ValueRefKind` was deliberately left an open union (companion plan §3, non-foreclosure
   note) so this lands without breaking any shipped definition.
2. **The viewpoint/query/reporting system cannot see indirect relationships.** Every
   selection, matrix cell, and exploration edge today is a *modeled* connection. ArchiMate
   4.0 Appendix B defines when a chain of modeled relationships entails a derived
   relationship (and of which type, at which certainty); without it, impact analysis
   ("what is transitively affected if this element changes?") and honest cross-layer
   matrices ("which components ultimately realize which requirements?") are inexpressible.
3. **The shipped default viewpoints are scope-only and therefore not executable.**
   Diagnosed 2026-07-13 against the running backend: the evaluator itself is correct (an
   ad-hoc `type = application-component` query returns 40 entities on the dogfood repo with
   correct counts/summaries via `artifact_query_viewpoint execute`), but all four shipped
   definitions (`motivation`, `application-structure`, `layered`, `technology-usage`) carry
   `query: null` — so the GUI's Query tab has nothing to show and executing them selects
   nothing. This is a content/design gap on top of any frontend rendering defects (the
   frontend is being reworked concurrently by another effort; §10 defines the contract that
   rework must meet, this plan does not patch the current components).
4. **Q6 left named features on the table** (persistent generated diagrams, label/tooltip
   rules, chart rules, continuous heat-map scales, saving executions, publishing/pinning,
   user-defined parameterized viewpoints). Each is critically evaluated in §7 — several are
   included here because the binding/derivation work makes them cheap and coherent; others
   are rejected or re-deferred with stated reasons.

### 1.1 Specification grounding

- `spec/viewpoints/viewpoints-spe-and-examples.md` — ArchiMate 4.0 Chapter 13 (viewpoint
  mechanism: purpose/content classification, ISO/IEC 42010 alignment, view creation) and
  Appendix C in full for the core set: the C.1 basic-viewpoint framework (Table C-1's
  composition/support/cooperation/realization categories; the note that grouping and
  junctions are usable in *every* viewpoint; the "examples, not normative" caveat) and
  example-viewpoint tables C-2 … C-26. Figures 13-1, 13-2, 6-1 are stored alongside as
  JPGs; they are contextual (ISO 42010 conceptual model, concern-framing flow) and impose
  no additional normative content beyond the text.
- `spec/viewpoints/appendix-b-relationships-derivation.md` — Appendix B in full: derivation
  rules DR 1–8 (valid), PDR 1–12 (potential), the two strength orderings (structural:
  realization < assignment < aggregation < composition; dependency: association < influence
  < access < serving), and §B.4's restriction lists (14 single-relation restrictions + 2
  intermediate-element restrictions).
- **Coverage flags (for the spec owner):**
  - C.2's intro names six motivation viewpoints, but only four subsections with tables
    follow (C-15 Stakeholder, C-16 Goal Realization, C-17 Requirements Realization,
    C-18 Motivation). **Goal contribution** and **principles** appear in the intro list
    only — legacy text from ArchiMate 2.x, where they existed as separate viewpoints;
    the 3.x/4.0 appendix carries no tables for them. Resolution (Q1): ship without
    dedicated definitions — influence-relationship analysis is in `goal-realization`'s
    scope and principles are among its elements; `motivation` covers the rest.
  - Appendix B's worked examples (B-3, B-9, B-11, B-17) are described precisely enough
    in prose to encode as test fixtures. Example B-12's figure is stored alongside
    (`Figure-B-12.jpg`, added 2026-07-13): Suite aggregates Front-End and Back-End;
    Database Hosting and Website Hosting serve Suite; PDR 5 derives serving candidates
    onto the aggregated parts, of which the architect accepts only some (red) and
    rejects the rest (gray) — the spec's clearest statement of *why potential
    derivations need per-occurrence human judgment*, and the direct precedent for the
    §5.7 accept/reject flow and the GUI's certainty rendering.

### 1.2 Current-implementation inventory (verified 2026-07-13)

| Concern | Where it lives today |
|---|---|
| Criteria trees, `ValueRef` (3 kinds), incident predicate, neighbor inclusion, connection selection | `src/domain/viewpoint_criteria.py` |
| Leaf condition evaluation incl. `ValueRef` resolution | `src/domain/viewpoint_condition_evaluation.py` (`_resolve_value`) |
| Tree evaluation, direction/symmetric normalization | `src/domain/viewpoint_criteria_evaluation.py` |
| Population widening + connection selection (structural/bridging invariants) | `src/domain/viewpoint_population_evaluation.py` |
| Read surface for evaluation | `src/domain/viewpoint_evaluation_context.py` (`CriteriaReadAccess`), `src/application/viewpoints/ports.py` (`RepositoryReadAccess`) |
| Definition model, presentation, capability registry | `src/domain/viewpoints.py` |
| Parsing / serialization (Appendix-A canonical form) | `viewpoint_criteria_parsing.py`, `viewpoint_query_parsing.py`, `viewpoint_presentation_parsing.py` + `*_serialization.py` |
| Three-mode validation + issue contract | `viewpoint_validation.py`, `viewpoint_condition_validation.py`, `viewpoint_criteria_validation.py`, `viewpoint_presentation_validation.py`, `viewpoint_validation_issue.py` |
| Plain-language summary | `src/domain/viewpoint_summary.py` (`render_query_summary`) |
| Use case + execution result + projection | `src/application/viewpoints/evaluate_viewpoint.py`, `execution_result.py`, `repository_projection.py`, `artifact_projection.py` |
| REST | `src/infrastructure/gui/routers/viewpoints.py` (`/api/viewpoints/execute`, `/execute-projection`, `/execute-diagram`, `/api/diagrams/{id}/viewpoint-projection`), `viewpoint_authoring.py` (CRUD, `/summarize`, `/criteria-catalog`, `/referencers`) |
| MCP | read `artifact_query_viewpoint` (`query_viewpoint_tools.py`), write `artifact_viewpoint` (`write/viewpoint.py`), graph tool `artifact_query_find_neighbors` (`query_graph_tools.py`), GUI graph endpoint `GET /api/neighbors` (`routers/connections.py`) |
| Settings | `config/settings.yaml` → `src/config/settings.py` (`viewpoints_execution_max_entities`, `..._default_entity_limit_mcp`, `..._timeout_seconds`, `validation.viewpoint_query_depth_cap`) |
| View-derivation strategies (diagram generation, *distinct concept* — see §5.0 naming note) | `src/domain/view_derivations.py`, `src/domain/derivation_types.py`, `src/application/derivation/` (`strategy_registry.py`, `local_neighborhood.py`, `path_projection.py`, `incident_connections.py`, `explicit_selection.py`, `refresh.py`) |
| Ontology metadata | `src/ontologies/archimate_4/{entities,connections,specializations,viewpoints}.yaml`, `src/domain/ontology_types.py` (`EntityTypeInfo.hierarchy[0]` = domain, `.classes` incl. `passive-structure-element`/`junction`; `ConnectionTypeInfo.archimate_relationship_type`, `.symmetric`, `.relationship_kind`) |
| Fitness functions | `tests/architecture/` (`test_dependency_policy.py`, `test_ontology_protocol_purity.py`, `test_combined_index_fitness.py`, `test_index_broadcast_policy.py`) |
| GUI (being rewritten concurrently) | `tools/gui/src/ui/views/Viewpoints{Management,Matrix,Diagram}View.vue`, `components/Viewpoint*`, `components/CriteriaTreeBuilder.vue`, `GraphExploreView.vue`, domain mirrors under `tools/gui/src/domain/viewpoint*` |

## 2. What stays unchanged (locked by the companion plan, not reopened)

- Criteria trees, comparator vocabulary (no new comparators — `eq neq in exists absent lt
  lte gt gte`), per-condition `negate`, §3.4 evaluation semantics for existing constructs.
- One attribute-path namespace (§3.3 reserved paths ⊕ D13 effective schema) used for
  filters, columns, `ValueRef` references, summaries — this plan *extends* the namespace
  (`derived.` prefix, §4.3) but adds no parallel vocabulary.
- `ViewpointProjection` as the one contract for repository execution and artifact-local
  ghosting; occlusion dominates styling; enforcement `off|warn|ghost`.
- Three-mode validation (`load|save|persist_edit`) + `ViewpointValidationIssue`
  (severity/code/path/expected/found); load never rejects for registry findings.
- Entity-denominated limits, timeout as typed error, four counts, MCP boundary (descriptive
  content only — no styling parameters on `execute`).
- MCP read/write tool split; **no new MCP tools** (standing tool-count discipline). All new
  capability rides on existing tools' parameters and the `artifact_help` topic.
- Lifecycle & governance (§10 of the companion plan): version bumps on semantic edit, no
  version history, slug uniqueness, delete-blocked-while-referenced, two-tier authoring,
  D14 exact-version promotion.
- Executions remain ephemeral by default; §7's "save as diagram" creates an *ordinary
  artifact* via the existing view-derivation mechanism — it does not persist executions as
  a new artifact kind.

## 3. Locked design decisions (this plan)

- **D1 — Three value scopes, three concepts.** Query-scoped **bindings** (`let`, evaluated
  once per execution), item-scoped **derived attributes** (per-candidate computed values in
  the `derived.` path namespace), execution-scoped **parameters** (typed inputs supplied at
  execution time). Never conflated: a binding is a constant during matching; a derived
  attribute is a per-row function; a parameter is a caller input. This resolves the
  "binding scoping" question Q7 flagged.
- **D2 — Explicit result types, checked statically.** Every binding carries a declared
  result type from the §4.1 algebra; the validator infers the expression's type and errors
  on mismatch. No implicit coercion anywhere, extending §3.4's discipline.
- **D3 — Set values are never implicitly scalar.** Comparing against a set/list-typed
  binding requires an explicit `aggregate` (count/sum/avg/min/max) or `quantifier`
  (any/all). An unquantified set reference is a save-time error, and the plain-language
  renderer therefore always has a sane English reading — the intelligibility risk Q7 named.
- **D4 — No text/formula escape hatch.** Bindings, derived attributes, and parameters are
  structured YAML + structured GUI editors reusing `CriteriaTreeBuilder`. The UX research's
  strongest anti-pattern (forcing complex logic into a formula box) stays banned.
- **D5 — Derivation classification is ontology data.** Appendix B's relationship taxonomy
  (structural/dependency/dynamic/other + strength) is declared per connection type in
  `connections.yaml` and exposed on `ConnectionTypeInfo` — not hardcoded in domain logic,
  so a future ontology module can supply its own table or opt out (no classification ⇒ no
  derivation over that module's types).
- **D6 — Derived relationships are ephemeral, typed, certainty-tagged values; diagrams may
  persist accepted *witness paths*, never fabricated connections.** A derived relationship
  is `(source, target, type, certainty ∈ {certain, potential}, hops,
  path-of-connection-ids)`. It is never persisted or indexed as model content; synthetic id
  `derived::<type-slug>::<canonical-path-key>` (reusing the established `id@fwd|id@rev`
  path-key format from `view_derivations.py`). A *generated diagram* that shows derived
  connections records the **accepted paths** in its existing `view_derivations` selection
  (`included_paths`/`excluded_paths`) and re-computes the derived connections from them —
  re-derivable, refresh-checkable, honest (§5.7). Potential derivations (PDR 1–12) are
  **opt-in per query** (`include_potential`) and additionally **subject to per-occurrence
  architect acceptance** when persisted into a view (§5.7) — the spec's "might be
  derived … the modeler decides" is a first-class decision point, not a global flag.
  Certain derivations (DR 1–8) are the default and pre-accepted, but remain deselectable
  (view scoping is still the architect's call).
- **D7 — Derived traversal is a mode of existing query constructs, not a parallel engine.**
  `IncidentConnectionCondition`, `NeighborInclusion`, and `ConnectionSelection` gain
  `traversal: direct | derived` (selection additionally `both`). Criteria against a derived
  relationship may address only the reserved derived paths `type`, `certainty`, `hops`
  (validated). One evaluator, one builder widget, one summary renderer.
- **D8 — Impact analysis ships as parameterized default viewpoints + parameters on existing
  graph surfaces.** `element-dependents` (impact of change) and `element-dependencies`
  ship in the module library, parameterized by `anchor`; `artifact_query_find_neighbors`
  and `GET /api/neighbors` gain `traversal`/`include_potential` parameters. No new tools,
  no bespoke impact subsystem — impact analysis *is* a query.
- **D9 — Scope-only definitions become executable via scope fallback.** Executing a
  definition without a `query` derives an implicit query from its `ConceptScope`
  (`type in scope.entity_types`, connections narrowed to `scope.connection_types`;
  unrestricted scope ⇒ match-all). The result's `query_summary` states the derivation
  ("Selection derived from the viewpoint's concept scope: …"). Fixes the observed
  "execution finds no entities"; `_NO_QUERY_SUMMARY` path is retired.
- **D10 — `query_schema` 1, single current grammar.** This pre-release repository has no
  query-format compatibility commitment: parser and serializer use schema 1 only. Every
  persisted query is migrated with the implementation; unknown keys remain parse errors.
- **D11 — Every included Q6 feature reuses an existing mechanism.** Persistent results →
  the view-derivation strategy system; pinning → a repo-local sidecar, not definition
  content; heat maps → a third `StyleRule` mode; labels → a validated display option.
  Nothing gets a new subsystem (§7).
- **D12 — GUI work is contract-first and gated on the concurrent frontend rewrite.** This
  plan specifies REST/domain contracts and acceptance criteria (including the empty-state
  and non-empty-execution behaviors the 2026-07-13 defect report exposed); the Vue
  implementation WUs land only after the rewrite stabilizes, against those contracts
  (§10, Phase H in the ledger).

## 4. Feature I — the typed value & binding layer (Q7)

New domain modules (all pure; existing files are near their LoC soft limits, so new
concepts get new files): `src/domain/viewpoint_value_types.py` (result-type algebra +
inference), `src/domain/viewpoint_bindings.py` (binding/parameter/derived-attribute value
objects), `src/domain/viewpoint_binding_evaluation.py` (evaluation),
`src/domain/viewpoint_binding_validation.py` (static checks), with parsing/serialization
added beside the existing `viewpoint_*_parsing/serialization.py` files.

### 4.1 The result-type algebra

```python
ScalarKind = Literal["string", "integer", "number", "date", "boolean", "slug"]

@dataclass(frozen=True)
class EntityInstanceType:      # exactly ONE entity of a type-union
    type_slugs: frozenset[str]          # empty = any entity type

@dataclass(frozen=True)
class ConnectionInstanceType:  # exactly one connection of a type-union
    type_slugs: frozenset[str]

@dataclass(frozen=True)
class EntitySetType:      # ordered set (any cardinality) of entities of a type-union
    type_slugs: frozenset[str]

@dataclass(frozen=True)
class ConnectionSetType:  # ordered set of connections of a type-union
    type_slugs: frozenset[str]

@dataclass(frozen=True)
class ScalarType:
    kind: ScalarKind

@dataclass(frozen=True)
class OptionalType:       # zero-or-one of the wrapped type
    element: "QueryResultType"

@dataclass(frozen=True)
class ListType:           # homogeneous, arbitrary length
    element: "QueryResultType"

@dataclass(frozen=True)
class TupleType:          # typed heterogeneous tuple, FIXED arity
    elements: tuple["QueryResultType", ...]

QueryResultType = (EntityInstanceType | ConnectionInstanceType | EntitySetType
                   | ConnectionSetType | ScalarType | OptionalType | ListType | TupleType)
```

Cardinality **is** a type distinction: `entity[a]` (exactly one), `optional[entity[a]]`
(zero-or-one), `entities[a]` (any cardinality, ordered set), `tuple[entity[a],
entity[a], entity[a]]` (fixed arity 3) and `list[entity[a]]` (arbitrary-length
homogeneous list) are five different types with different comparison semantics. A
binding's **declared** instance/tuple type is simultaneously a static type for checking
and a **runtime cardinality assertion**: a binding declared `entity[τ]` whose selection
resolves to zero or several entities fails execution with the typed error
`binding-cardinality-violation` (loud, like parameter errors — never a silent
first-of-set); declared `optional[…]` admits zero-or-one, with the empty case following
§3.4's missing-value semantics (comparisons no-match before `negate`). Set types carry no
assertion. The payoff is at reference sites: projection over an instance type yields a
**scalar** directly (no aggregate/quantifier needed — cardinality is statically one),
while D3's explicit-aggregate/quantifier rule applies to set/list types only; `eq`
between same-arity tuple types is element-wise; arity mismatch is a static error.
Aggregating over an instance type is a static error (`aggregate-over-instance` — nothing
to reduce).

This covers the full requested surface: a specific single entity of a type or union
(`entity[a|b]`), ordered sets and lists of entities of a (union-)type, typed heterogeneous
fixed-arity tuples, typed entity attributes (`ScalarType`), optionals, and lists/tuples
thereof. Canonical string form for serialization and error messages: `entity[a]`,
`entities[a|b]`, `connection[x]`, `connections[x]`, `optional[entity[a]]`,
`list[number]`, `tuple[entity[a], entity[a], number]`, `date`, … (one printer + one
parser in `viewpoint_value_types.py`; round-trip tested). Set results are materialized in
stable item-id order, so set-typed and list-typed values share deterministic iteration;
the type distinction is uniqueness + provenance (selection results are sets; projections
are lists, preserving per-item multiplicity).

**Type inference & checking rules** (pure function `infer_binding_type`; the declared
type is checked against the inferred one):

- `select: entities` + criteria ⇒ inferred `EntitySetType(τ)` where τ = the type-union
  statically implied by the criteria tree: the union of `type` values from positive
  `eq`/`in` type conditions on conjunctive spines; any tree without such a narrowing
  infers the open union (empty frozenset = any). Inference is deliberately conservative —
  it never claims a narrower union than provable.
- **Declared-vs-inferred compatibility**: declared `entities[σ]` requires σ ⊆ τ-compatible
  (σ within the inferred union, or the inferred union open); declared `entity[σ]` or
  `optional[entity[σ]]` is the same static check **plus** the runtime cardinality
  assertion (§ above) — declaring an instance type over a set-shaped selection is exactly
  how "the single entity satisfying these criteria" is expressed. Incompatible unions are
  `binding-type-mismatch`.
- `project: <path>` over `EntitySetType(τ)` ⇒ `ListType(ScalarType(k))`; over
  `EntityInstanceType(τ)` ⇒ `ScalarType(k)` (singular in, singular out); over
  `OptionalType(EntityInstanceType(τ))` ⇒ `OptionalType(ScalarType(k))` — where k is the
  attribute's schema type resolved against the D13 merged effective schema of **every**
  member type of τ; if members disagree on k, save-time error
  `binding-attribute-type-ambiguous` (the author narrows τ or picks another attribute).
  Projecting a reserved path (`id`, `name`, …) uses the §3.3 table's types. Projection
  over an open union is only legal for reserved paths (schema attributes need a type to
  resolve against).
- `aggregate:` over `ListType(ScalarType(k))` ⇒ `ScalarType(k′)`: `count` ⇒ `integer`
  (also legal directly on a set type without `project`); `sum` ⇒ k (integer/number only);
  `avg` ⇒ `number`; `min`/`max` ⇒ k (numeric or date). Over instance/optional types:
  `aggregate-over-instance` (static error).
- `tuple:` of previously declared binding references ⇒ `TupleType(their types)` — fixed
  arity; `eq` between tuples requires identical arity and element-wise compatible types
  (arity mismatch is static, `tuple-comparator-unsupported` covers non-`eq`/`in` use).

### 4.2 Query bindings (`let`)

```python
@dataclass(frozen=True)
class QueryBinding:
    name: str                                  # kebab-case, unique within the query
    result_type: QueryResultType               # DECLARED; canonical form always writes it
    select: Literal["entities", "connections"] | None = None
    criteria: EntityCriteriaGroup | ConnectionCriteriaGroup | None = None
    project: str | None = None                 # attribute path (§3.3 namespace)
    aggregate: Literal["count", "sum", "avg", "min", "max"] | None = None
    tuple_of: tuple[str, ...] = ()             # names of earlier bindings (tuple form)
    include_in_result: bool = False            # entity-valued shapes only: entity[…],
                                               # optional[entity[…]], entities[…] (§4.2)
```

`ExecutableViewpointQuery` gains `bindings: tuple[QueryBinding, ...] = ()` (and
`parameters`, §4.4; `derived`, §4.3).

**Semantics (normative):**

- **Evaluated once per execution**, before any candidate matching, in dependency order.
  A binding's criteria may contain `ValueRef`s referencing *earlier* bindings and
  parameters; referencing a later or unknown binding is a save-time error
  (`unknown-binding`), a reference cycle is `binding-cycle` (deterministic topological
  order; ties broken by declaration order). Binding criteria may **not** reference
  `derived.` paths (`binding-derived-reference-unsupported`) — derived attributes are
  per-candidate and evaluate after bindings (§4.5 pipeline).
- Binding selection uses the same repo-scope population and the same criteria evaluator as
  the primary query; results are stable-sorted by item id.
- **Hexagonal boundary, stated precisely**: the domain binding evaluator does **not**
  enumerate the repository — `CriteriaReadAccess` deliberately has no `entity_ids()`.
  The application layer (`EvaluateViewpoint`) resolves the repo-scope candidate id sets
  once via `RepositoryReadAccess` (as it already does for the primary population) and
  passes them into the pure evaluator as a `BindingEvaluationInput` value (candidate
  entity ids + candidate connection ids + read access + registries). Domain evaluates
  criteria over the supplied candidates; application owns scope partitioning. One
  enumeration per execution, shared between primary matching and all bindings — no
  duplicated scans, no new domain port, no dependency-policy pressure.
- **Connection candidates have a real acquisition path**, not an implied one:
  `RepositoryReadAccess` gains `connection_ids()` / `enterprise_connection_ids()` /
  `engagement_connection_ids()`, mirroring its entity enumeration — the underlying
  artifact index already exposes connection enumeration (`ModelQuery.connection_ids()`
  precedent), so this is the standing add-the-delegation rule, not a new capability.
  Scope semantics: a connection belongs to the repo whose file declares it (same rule as
  entities); `select: connections` bindings evaluate over the scoped connection
  candidates; a candidate with an unresolvable endpoint still evaluates its own
  attribute criteria, while endpoint `ValueRef`s on it resolve per §3.4's dangling rule
  (no match). The single-enumeration guarantee covers connections identically (one
  connection enumeration per execution, shared by all connection-selecting bindings).
- **`include_in_result` is legal for every entity-valued result shape** — `entity[…]`,
  `optional[entity[…]]`, `entities[…]` (and `list[entity[…]]` should inference ever
  produce it) — a singleton binding must not be forced into a set declaration just to be
  included. It is a save-time error (`include-in-result-shape-unsupported`) on scalar,
  connection-valued, and tuple shapes: connections enter results only through
  `ConnectionSelection`'s structural invariant (never by membership fiat), and tuple
  flattening is deliberately undesigned.
- An **empty** binding result is a legal value: projections yield empty lists; `count` = 0;
  `sum` = 0; `avg`/`min`/`max` over empty = *missing* (conditions comparing against them
  are no-match before `negate`, per §3.4's missing rule); quantifiers: `any` over empty =
  false, `all` over empty = true. Stated here so the tests can pin it.
- **`include_in_result`** (the Q7 "result-included" mark): the binding's entities join the
  included population with membership `expanded` (same vocabulary as neighbor inclusion —
  no third membership value; truncation ordering unchanged: primaries retained first). The
  per-item summary and `ProjectedOccurrence` gain `via: tuple[str, ...]` — the names of
  the inclusion sources (binding names; the literal `"neighbor-inclusion"` for §4.1 terms;
  `"derived-traversal"` for §5 inclusions) — empty for primary members. Additive field,
  defaults empty, so existing consumers are untouched.
- Cap: `viewpoints.max_query_bindings` (settings, default 8) — save-mode only, like the
  depth cap; each binding's criteria tree is subject to the existing depth cap
  independently.

### 4.2.1 `ValueRef` extension

```python
ValueRefKind = Literal["literal", "attribute_of_self", "attribute_of_endpoint",
                       "binding", "parameter"]

# new fields on ValueRef (all defaulted, additive):
binding: str | None = None                      # kind == "binding"
parameter: str | None = None                    # kind == "parameter"
project: str | None = None                      # kind == "binding": late projection
aggregate: Literal["count","sum","avg","min","max"] | None = None
quantifier: Literal["any", "all"] | None = None # list-typed comparisons only
```

Canonical YAML (extends the existing `{from: self|source|target}` mapping form):
`{from: binding, name: critical-processes, project: threshold, aggregate: max}` and
`{from: parameter, name: anchor}`.

**Typing rules (save-time, D2/D3):** after applying `project`/`aggregate`, the reference's
type must fit the comparator — scalar comparators need `ScalarType` (numeric ones need
numeric/date, matching the left-hand attribute's schema type exactly), `in` needs
`ListType(ScalarType)` whose element kind matches the left-hand attribute, `eq`/`in`
against tuples per §4.1's tuple rules (eq: element-wise against a tuple literal/binding of
identical `TupleType`; `in`: membership in `list[tuple[…]]`). A list-typed reference under
a scalar comparator without `quantifier` or `aggregate` is `unquantified-set-comparison`.
Quantifier semantics: the condition (before `negate`) holds for `any`/`all` elements
respectively. Set-membership tests need no new node kind — `id in {from: binding, name: x,
project: id}` expresses "entity is in set x" with existing machinery (one spelling per
meaning).

Bindings are legal as `ValueRef` targets **everywhere a `ValueRef` appears**: primary/
incident/inclusion criteria, connection-selection criteria, style-rule match criteria,
matrix axis criteria — the Q7 requirement "usable as a ValueRef target anywhere".

### 4.3 Derived attributes (item-scoped computed values)

Discharges the companion plan's §5.3 `DerivedMetricRef` non-foreclosure at the right
altitude: not a new column source union member, but a new **path namespace prefix** —
`derived.<name>` — usable wherever a path is usable (conditions, `ColumnSpec.source`,
`range_attribute`/`scale_attribute`; **not** `group_by` in v1 — grouping needs
discreteness guarantees deferred until real demand).

```python
@dataclass(frozen=True)
class DerivedAttribute:
    name: str                                   # addressed as "derived.<name>"
    direction: IncidentDirection = "either"
    traversal: Literal["direct", "derived"] = "direct"
    connection_criteria: ConnectionCriteriaGroup | None = None
    endpoint_criteria: EntityCriteriaGroup | None = None
    reduce: Literal["count", "sum", "avg", "min", "max"] = "count"
    of: str | None = None    # "connection.<attr>" | "endpoint.<attr>" |
                             # "relationship.hops"; None iff reduce=count
```

Semantics: for the candidate entity, enumerate incident connections (direct) or derived
relationships (derived, bounded per §5.3) matching the criteria/direction — exactly the
incident predicate's hop semantics, including symmetric-type direction normalization —
then reduce. `count` ⇒ integer; otherwise the schema type of the referenced attribute
(validated). The `of` source has three head forms: `connection.<attr>` (attribute of the
traversed connection — direct traversal only), `endpoint.<attr>` (attribute of the far
endpoint entity), and the reserved `relationship.hops` (the derived relationship's hop
count, integer — **valid only with `traversal: derived`**;
`derived-of-source-traversal-mismatch` otherwise). `relationship.hops` is what the
shipped `derived.impact-distance` default reduces (`reduce: min`) — expressible in the
grammar, no special-casing. Certainty is deliberately *not* an `of` source (it is
non-numeric and non-reducible); filter on it via `connection_criteria` instead. Missing/empty per §4.2's empty-reduction rules — so `derived.x` participates
in `exists/absent` naturally. Values are memoized per (entity, attribute) within one
execution; evaluation stays pure. Cap: `viewpoints.max_derived_attributes` (default 8).
Derived-attribute criteria may reference bindings/parameters, never other derived
attributes (`derived-attribute-reference-unsupported` — no recursion, v1).

### 4.4 Query parameters (user-defined parameterized viewpoints — Q6 item, promoted)

```python
@dataclass(frozen=True)
class QueryParameter:
    name: str
    value_type: ScalarKind | Literal["entity-id"]   # entity-id = validated artifact id
    required: bool = True
    default: object = None                          # typed like value_type when present
    description: str = ""                           # shown by GUI prompt + MCP help
```

`ValueRef(kind="parameter")` resolves the supplied value; execution requests
(`ViewpointExecutionRequest`, REST body, MCP `execute` arguments) gain
`parameters: Mapping[str, object]`. Missing required parameter or type mismatch is a
**typed execution error** (like the timeout — never a silent empty result); unknown
supplied names error too. `entity-id` values are checked to resolve in the current
repo scope at execution time (warning + no-match, not error, when dangling — consistent
with §3.4's dangling-reference rule). The catalog `list` output includes each definition's
parameter signature so agents and the GUI can prompt correctly. Cap:
`viewpoints.max_query_parameters` (default 4).

### 4.5 Evaluation pipeline (normative order)

1. Resolve definition (or ad-hoc query); scope fallback per D9 if `query is None`.
2. Validate + bind supplied **parameters**.
3. Evaluate **bindings** in topological order (each once).
4. Evaluate **primary criteria** per candidate (derived attributes computed lazily,
   memoized).
5. **Neighbor inclusions** and `include_in_result` bindings widen the population
   (membership `expanded`, `via` recorded).
6. **Connection selection** (structural invariant; §5.4 for derived traversal).
7. Presentation projection (axes, styles, columns) — unchanged flow.

Timeout covers the whole pipeline (existing setting); the four counts and truncation
semantics are unchanged.

### 4.6 Plain-language summary (§9.1 parity, extended)

`render_query_summary` gains, in order: parameter sentences ("Takes a required element
input ⟨anchor⟩."), binding sentences ("Let critical-processes be all entities where type is
process and threshold is at least 7."), and reference phrasing inside conditions ("strength
is at least the maximum threshold of critical-processes", "id is one of the ids of
critical-processes", "matches the supplied ⟨anchor⟩"). Quantifiers render as "any of"/"all
of". Derived attributes render as "its number of outgoing serving connections" (count) /
"the maximum strength of its …". One renderer, all surfaces, tested per node kind — as
today.

### 4.7 Validation additions

New stable codes (extending the existing set — `unknown-attribute`, `depth-cap-exceeded`,
`operator-type-mismatch`, `value-ref-*`, etc.): `unknown-binding`, `binding-cycle`,
`duplicate-binding-name`, `binding-type-mismatch` (declared vs inferred),
`binding-attribute-type-ambiguous`, `binding-count-exceeded`,
`binding-derived-reference-unsupported`, `aggregate-over-instance`,
`include-in-result-shape-unsupported`, `unquantified-set-comparison`,
`tuple-comparator-unsupported`, `unknown-parameter`, `duplicate-parameter-name`,
`parameter-type-mismatch`, `parameter-count-exceeded`, `derived-attribute-unknown`,
`derived-attribute-reference-unsupported`, `derived-of-missing`,
`derived-reduce-type-mismatch`, plus §5's traversal codes. Issue **paths** extend into the
new trees (`query.bindings[1].criteria.children[0]`, `query.parameters[0]`,
`query.derived[2].connection_criteria…`) — same JSON-pointer style, GUI-mappable. Mode
split unchanged: registry findings warn at `load`, error at `save`; the new caps are
save-mode ergonomics checks like the depth cap.

## 5. Feature II — derived relationships & impact analysis (Appendix B)

### 5.0 Naming note (unambiguous vocabulary)

The codebase already uses "derivation" for **view derivation** (generating diagram content
via `DerivationStrategyCatalog`). This feature is **relationship derivation** (ArchiMate
Appendix B semantics). Modules, docs, and GUI copy use the two-word forms consistently;
the glossary entry lands with the docs WU. New domain modules:
`src/domain/relationship_derivation.py` (classification model + pairwise composition),
`src/domain/relationship_derivation_rules.py` (DR/PDR rule tables),
`src/domain/relationship_derivation_restrictions.py` (§B.4),
`src/domain/relationship_reachability.py` (bounded traversal/enumeration).

### 5.1 Ontology classification data (D5)

`connections.yaml` gains one block per connection type:

```yaml
archimate-composition:
  derivation: {role: structural, strength: 4}
archimate-aggregation:
  derivation: {role: structural, strength: 3}
archimate-assignment:
  derivation: {role: structural, strength: 2}
archimate-realization:
  derivation: {role: structural, strength: 1}
archimate-serving:
  derivation: {role: dependency, strength: 4}
archimate-access:
  derivation: {role: dependency, strength: 3}
archimate-influence:
  derivation: {role: dependency, strength: 2}
archimate-association:
  derivation: {role: dependency, strength: 1}
archimate-triggering:
  derivation: {role: dynamic}
archimate-flow:
  derivation: {role: dynamic}
archimate-specialization:
  derivation: {role: specialization}
```

`ConnectionTypeInfo` gains `derivation_role: Literal["structural", "dependency",
"dynamic", "specialization"] | None = None` and `derivation_strength: int | None = None`
(loader-validated: strength required for structural/dependency, forbidden otherwise;
strengths unique within a role). Types without a `derivation` block never participate in
derivation — modules opt in by declaring. `tools/generate_types.py` regeneration and the
ontology-protocol purity fitness test must stay green.

Entity-side classification is an **explicit derivation-domain classifier**, not a raw
hierarchy read. Naming note: "domain" is the metamodel's own term — the restriction
rules are quantified over the domains Motivation, Strategy, Core, Implementation &
Migration, and Relationships — so the type carries the ubiquitous language, qualified by
its consumer. `DerivationDomain` is a *coarsening* of the existing per-entity `domain`
facet (`hierarchy[0]`, the reserved `domain` path): business/application/technology/
common collapse into `core`, and the junction override applies — the qualifier is what
keeps the two domain notions distinct. (The relationship-type counterpart is
`derivation_role`/`derivation_strength` — role for relationship types, domain for
element types; the two partitions are deliberately not named alike.)

```python
DerivationDomain = Literal["motivation", "strategy", "core",
                           "implementation_migration", "relationships"]

def derivation_domain(info: EntityTypeInfo) -> DerivationDomain: ...
```

- `"junction" in info.classes` ⇒ `relationships` — **regardless of storage hierarchy**.
  This repo stores `and-junction`/`or-junction` under `common/` for directory purposes,
  but Appendix B places junctions in its own "Relationships" domain (§B.4's dedicated
  restriction bullets); the classifier is the single place that divergence is absorbed.
- otherwise by `hierarchy[0]`: `business/application/technology/common → core`,
  `motivation → motivation`, `strategy → strategy`,
  `implementation → implementation_migration`. Unknown heads are a classifier error
  (loud), never a silent `core` default.
- Passive-structure membership = `"passive-structure-element" in classes`; the
  special-cased elements are identified by type slug (`grouping`, `location`, `plateau`).

The classifier lives in `relationship_derivation.py` with its own test file asserting the
mapping for **every** shipped entity type (an exhaustive table test, so a new type added
to `entities.yaml` without a classifiable hierarchy fails loudly).

### 5.2 The pure derivation engine

Core operation: **pairwise composition** — `compose(first: OrientedRelation, second:
OrientedRelation, intermediate: EntityTypeInfo) -> DerivedStep | None`, where an
`OrientedRelation` is (connection-type info, orientation relative to the chain) and a
`DerivedStep` carries the resulting relationship type + certainty. The DR/PDR tables encode
exactly the spec's rules, each tagged with its spec id:

| Rule | Encoding |
|---|---|
| DR1 | specialization ∘ specialization → specialization (certain) |
| DR2 | structural ∘ structural → weaker-of (certain) |
| DR3 | structural ∘ dependency → the dependency (certain) |
| DR4 | structural(a,b) ∘ dependency(c,b) → dependency(c,a) (certain; opposing join) |
| DR5 | structural ∘ dynamic → the dynamic (certain) |
| DR6 | structural(a,b) ∘ flow(c,b) → flow(c,a) (certain; opposing join) |
| DR7 | triggering(a,b) ∘ structural(b,c) → triggering(a,c) (certain) |
| DR8 | triggering ∘ triggering → triggering (certain) |
| PDR1–4 | specialization joins with structural/dependency/dynamic → that relation (potential; four orientation cases exactly as specified) |
| PDR5–6 | structural/dependency source-joins → dependency (potential) |
| PDR7 | dependency ∘ dependency → weaker-of (potential) |
| PDR8–9 | flow/structural and structural/dynamic source-joins (potential) |
| PDR10 | flow ∘ flow → flow (potential) |
| PDR11 | triggering(a,b) ∘ structural(c,b) → triggering(a,c) (potential) |
| PDR12 | aggregation-from-Grouping ∘ realization/assignment → that relation (potential, only if the permitted-relationship table allows it from a to c) |

Chains **fold left**: certainty of a chain = `potential` if any step is potential, else
`certain`; `potential_steps` is counted (surfaced in provenance — the spec notes stacked
potential derivations weaken confidence). Chains never pass **through** junction elements
(documented v1 limitation; junction relaying is diagram-notation sugar, not Appendix-B
input). Self-loops (`source == target`) are dropped.

**Restrictions (§B.4)** are a final admissibility filter, encoded as data — one predicate
per spec bullet, applied to every derived relation `p(a,b): S` (and, for `RJ*`, to each
composition step's intermediate element `c`). Explicit metamodel relationships are allowed
by definition — the restrictions apply only to derived results, exactly as the spec notes.
Normative transcription (derivation **disallowed** when the row matches; "Assoc" =
Association, "I&M" = Implementation & Migration, "PSE" = passive structure element):

| id | a (source) | b (target) | disallowed unless S ∈ |
|---|---|---|---|
| R1 | I&M / Core / Strategy | Motivation | Assignment, Realization, Influence, Assoc |
| R2 | Motivation | I&M / Core / Strategy | Assoc |
| R3 | I&M / Core | Strategy | Realization, Assoc |
| R4 | Strategy | I&M / Core | Assoc |
| R5 | I&M | Core | Realization, Assoc |
| R6 | Core | I&M | Assignment, Assoc |
| R7 | Grouping / Location / Plateau | Relationships domain | Aggregation, Assoc |
| R8 | not Grouping/Location/Plateau | Relationships domain | Assoc |
| R9 | Relationships domain | any | Assoc |
| R10 | any | b not in Motivation | S ≠ Influence (i.e. Influence requires b ∈ Motivation) |
| R11 | any | b not PSE | S ≠ Access (Access requires b PSE) |
| R12 | not PSE | PSE | Access, Assignment, Assoc |
| R13 | PSE | PSE | Realization, Assoc |
| R14 | PSE | not PSE | Realization, Influence, Assoc |
| RJ1 | — | — | intermediate c's domain must equal a's or b's domain, **except** a ∈ I&M ∧ c ∈ Core ∧ b ∈ Motivation/Strategy |
| RJ2 | a ∈ I&M | b ∈ Motivation/Strategy | c must not be Location or Grouping |

The rule tables and this restriction table are the code — the implementation transcribes
them as data structures with these ids; a reviewer diffs implementation against this
table, not against re-derived prose.

**Direct-versus-derived boundary (spec fidelity):** the Appendix-B relationship tables
are the allowed-relationship closure obtained by applying direct metamodel relationships,
derivation rules, and restrictions. The YAML `permitted_relationships` data intentionally
records only directly modelable relationships; the engine derives the indirect portion of
that closure rather than redundantly listing it. Appendix B's Financial Application
example therefore derives a realization from an application component to an application
service even though that realization may not be modeled directly. PDR12 is deliberately
narrower: its own rule requires its result to be permitted directly, and the engine
enforces that explicit precondition.

Correctness is established by an **exhaustive metamodel-level generated test**, not by
fixtures alone: enumerate every permitted input relationship pair `p(a,b): S`,
`q(b,c): T` (and each opposing-join orientation) over all shipped entity types ×
classified connection types, apply `compose` + restrictions, and assert the result has
the rule's stated classification, certainty, and restriction behaviour. The sweep also
asserts the PDR12-specific direct-permission guard. Worked-example fixtures (§WU-B5)
pin *specific expected outputs* and the distinction between directly modeled and
indirectly derived relationships.

### 5.3 Bounded reachability & enumeration

Policy travels as **value objects, not parameter sprawl** (per the coding standard's
too-many-parameters / boolean-flag guidance):

```python
DerivationCertaintyPolicy = Literal["certain_only", "include_potential"]

@dataclass(frozen=True)
class DerivationBounds:
    max_hops: int
    max_relationships: int

@dataclass(frozen=True)
class RelationshipDerivationRequest:
    anchors: frozenset[str]
    direction: IncidentDirection
    certainty: DerivationCertaintyPolicy = "certain_only"
    bounds: DerivationBounds = ...   # settings-derived default at the composition edge
```

`derive_relationships(request, *, read_access, registries) -> DerivedRelationshipSet` —
transport-level booleans (`include_potential` on REST/MCP/query fields) are translated
into `DerivationCertaintyPolicy` at the boundary before domain code is entered; every
internal consumer (query evaluation, graph tools, strategies, rendering/reconstruction)
passes the request/policy objects. The algorithm: BFS from the anchor set over classified
connections, folding rules per step, deduplicating per `(source, target, type)`:
certainty = certain if **any** witnessing chain is certain; `hops` = minimal; the recorded
`path` = the minimal-hop, lexicographically-smallest canonical path key (determinism).
Bounds, all settings-backed: `viewpoints.derivation_max_hops` (default 4, hard-capped by
validation), `viewpoints.derivation_max_relationships` (default 2000 — enumeration aborts
with a typed error advising narrower criteria, mirroring the entity-limit philosophy), plus
the existing execution timeout. Complexity O(V·E) with per-execution memoization of the
frontier — fine at dogfood scale (~300 entities) and bounded for 10⁴-entity repos.

**Path reconstruction (the persisted-path contract, prerequisite for §5.7)**: the inverse
operation is first-class, not implied — `derive_relationship_for_path(path_key, *,
read_access, registries) -> PathDerivationOutcome`, a pure function turning a canonical
`id@fwd|id@rev|…` key back into the derived relationship it witnesses. Outcome is a
discriminated union: `Derived(source, target, type, certainty, hops)` — the fold
re-applied over the recorded chain in recorded orientation; `Broken(detail)` — a chain
link no longer resolves (missing connection or dangling endpoint); `NoLongerDerives
(reason)` — every link resolves but the fold now yields nothing admissible (connection
retyped, classification changed, restriction now fires). Enumeration (BFS) and
reconstruction share the same fold — reconstruction is the fold over one explicit chain,
so the two can never disagree. Rendering and refresh (§5.7) consume only this function;
a certainty or type differing from what was accepted, or a non-`Derived` outcome, are
exactly the staleness signals refresh reports.

### 5.3a Rule-correctness verification protocol (normative — this is the crux of the feature)

A wrongly-encoded derivation rule produces *plausible-looking wrong architecture analysis*
— the worst failure mode this plan can have. Correct encoding is therefore established by
**five independent methods**, each catching what the others miss; all five are acceptance
gates, none is optional:

1. **Traceable transcription.** Every rule/restriction datum carries a `spec_ref` field
   (`"B.2.2 DR2"`, `"B.4 R11"`, …) and the PLAN's §5.2 tables (themselves diff-checked
   against `spec/viewpoints/appendix-b-relationships-derivation.md` during review) are the
   transcription source. Review is a mechanical three-way diff — spec text ↔ PLAN table ↔
   code data — never a re-derivation from memory.
2. **Dual encoding.** The test suite contains a second, *independently authored*
   transcription of DR/PDR/restrictions (written from the spec file directly, by a
   different author/agent/session than the runtime tables, as flat expected-outcome data
   — not by importing the runtime structures). A structural comparison test asserts the
   two encodings agree on every (S, T, orientation, domain-combination) cell. Divergence
   means one transcriber misread the spec — exactly the error class single encodings
   cannot catch.
3. **Exhaustive metamodel sweep.** The §5.2 generated test over every permitted input
   pair × orientation verifies each rule's result classification, certainty, and
   restrictions, including PDR12's explicit direct-permission precondition. It also
   verifies that an indirect result is never reclassified as a directly modeled edge.
4. **Semantic invariants, encoding-independent.** Property tests asserting restriction
   *meanings* directly on engine output over generated random models, without reference
   to the rule tables: no derived Access whose target is not passive-structure; no derived
   Influence whose target is outside Motivation; no derived relation sourced from a
   junction except Association; certainty never `certain` when any chain step used a PDR;
   derived structural strength never exceeds the weakest chain link. These hold even if
   both encodings share a transcription bug of a *different* rule.
5. **Worked-example fixtures.** B-3, B-9, B-11, B-12, B-17 pin exact expected outputs —
   the spec's own concrete cases, including expected *absences* (no uncited derivation at
   the tested hop bounds).

The ledger's Phase B closeout additionally requires a recorded line-by-line review pass
(spec file open next to the two encodings) before Phase D may consume the engine.

### 5.4 Query integration (D7)

- `IncidentConnectionCondition` + `NeighborInclusion` + `DerivedAttribute` gain
  `traversal: Literal["direct", "derived"] = "direct"` and, when `derived`,
  `include_potential: bool = False` and `max_hops: int | None = None` (None ⇒ setting).
- `ConnectionSelection` gains `traversal: Literal["direct", "derived", "both"] = "direct"`
  (+ the same two knobs): with `derived`/`both`, derived relationships between **included**
  entities join the displayed connection set — the structural invariant and the matrix
  bridging invariant apply to them verbatim (both endpoints must be included / bridge the
  axes). A requirements × components matrix over `archimate-realization` with
  `traversal: both` is the canonical cross-layer coverage report.
- **Criteria over derived relationships** address only reserved paths `type` (derived type
  slug), `certainty` (`certain|potential`), `hops` (integer) — anything else (schema
  attributes, `specialization`, endpoint `ValueRef`s) is save-time
  `derived-traversal-path-unsupported`. Rationale: a derived relationship has no profile
  and no persisted identity; pretending otherwise would corrupt the namespace's meaning.
- Direction is anchor-relative exactly as for direct traversal; symmetric normalization is
  irrelevant (derived types are all directed by construction; association as a derived
  *type* is reported in authoring orientation of the fold).
- Depth-cap interaction: a `traversal: derived` node still counts as **one** relational
  level in the §3.2 cap (its multi-hop nature is bounded by `max_hops`, a different axis).
- **Diagrams are a first-class consumer.** The `diagram` representation (ad-hoc ArchiMate
  notation rendering) draws derived connections in the **notation of their derived type**
  (a derived serving renders as a serving arrow — the renderer receives the type slug and
  needs no derived-specific notation), visually marked as derived (dashed/annotated per
  the surface's token vocabulary) with certainty distinguished. This is what makes the
  motivating case expressible: a layered view of specific business processes and the
  technology elements that (indirectly) support them, with the intermediate application
  layer omitted and the support shown as derived serving/realization connections —
  Appendix B's own "omit the functions and services" abstraction use case (Example B-3).

### 5.5 Execution result & projection extensions

- `ConnectionItemSummary` gains `certainty: Literal["certain", "potential"] | None = None`,
  `hops: int | None = None`, `via_connection_ids: tuple[str, ...] = ()` (the witnessing
  path) — `None`/empty for modeled connections, so existing consumers see no change.
  Derived ids use the D6 synthetic scheme and sort stably with the rest.
- `EntityItemSummary` and `ProjectedOccurrence` gain `via` (§4.2).
- **Hitting `derivation_max_relationships` is a typed error, never a warning or partial
  result**: `DerivationLimitError` aborts the whole execution, exactly like the timeout —
  impact analysis must never return partial graph facts dressed as a result. (The entity
  `limit`/truncation machinery is unrelated: it truncates a *complete* result for
  transport, with honest counts.) Derived relationships are reported as derivation
  results, not rejected or warned on merely because their type pair is not directly
  modelable.
- MCP `execute` output includes the new summary fields (descriptive content — the D15
  boundary is intact; certainty/hops/path are selection facts, not styling).

### 5.6 Impact-analysis surfaces (D8)

1. **Default parameterized viewpoints** (module library): `element-dependents` — "what is
   affected if ⟨anchor⟩ changes": primary = `id eq ⟨anchor⟩`; one neighbor inclusion,
   `traversal: derived`, `direction: incoming`, neighbor-criteria match-all; connections
   `traversal: both`; presentation `exploration` with `edge_emphasis` style rules keyed on
   `certainty` and a scale-mode band on `hops` (§7). `element-dependencies` mirrors it
   outgoing. Both carry honest `purpose: [deciding]`, stakeholders/concerns, and
   descriptions.
2. **`artifact_query_find_neighbors`** (MCP) and **`GET /api/neighbors`** (REST,
   `routers/connections.py`) gain `traversal: "direct" | "derived"` (default direct) and
   `include_potential: bool` — same engine, same bounds; responses carry
   type/certainty/hops/path per derived neighbor. Tool description stays short; depth
   lives in the `artifact_help` viewpoints topic.
3. **View-derivation strategy** `derived_relationships` (v1) registered in the existing
   catalog (`src/application/derivation/`): parameters `{root_entity_ids, direction,
   include_potential, max_hops}`, emitting `CandidateSet` with `paths` — so a *persistent*
   impact diagram is generated/refreshed through the machinery diagrams already use
   (selection review, refresh staleness) rather than a parallel path.
4. **Materializing a potential relationship as a modeled connection** (the spec's "the
   modeler decides", model-level form): GUI-only convenience that pre-fills the existing
   connection-creation flow (type + endpoints + a description noting the witnessing
   chain); no new write tool, no automatism — agents already have
   `artifact_add_connection`.

### 5.7 Derived relationships on genuine, persisted diagrams (accept/reject flow)

The view-level form of "the modeler decides", and the mechanism behind the layered
"processes supported by technology" requirement:

- **Generation**: the `viewpoint_execution` and `derived_relationships` view-derivation
  strategies (§5.6.3, §7) emit derived connections as **candidates**, each identified by
  its canonical witness-path key — flowing through the strategy contract's existing
  `CandidateSet.paths` field, which `path_projection` already exercises.
- **Decision**: the existing selection-review step (GUI derivation flow +
  `DerivationSelection.included_paths` / `excluded_paths` on the diagram's
  `view_derivations` frontmatter) records the architect's per-occurrence choice.
  Defaults: **certain** candidates pre-accepted, **potential** candidates pre-rejected
  until explicitly accepted — the DR/PDR split rendered as a decision default, with the
  certainty, derived type, and witness chain shown at review time.
- **Persistence & rendering**: the diagram persists *accepted paths only* (D6 — never
  fabricated connection artifacts). At render time the derived connection is re-computed
  from its recorded path and drawn in its derived type's notation, marked derived (+
  certainty) — same rendering contract as the ad-hoc `diagram` representation (§5.4).
- **Staleness, honestly**: on refresh (existing `refresh.py` flow), a recorded path whose
  chain no longer exists — or no longer derives the same type under the rules — is
  reported as a stale selection entry (never silently redrawn or silently dropped); the
  architect re-reviews. A materialized model connection (§5.6.4) is the escape from this
  maintenance loop when the relationship is judged architecturally real rather than
  view-specific.
- **Boundary**: hand-authored (non-generated) diagrams do not gain free-floating derived
  connections in this plan — derived content enters a persisted view only through a
  recorded, refreshable derivation. (The ad-hoc `diagram` representation needs no
  acceptance step: it is ephemeral, and `include_potential` governs it.)

## 6. Feature III — executable default viewpoints (Appendix C) & scope fallback

### 6.1 Scope fallback (D9) — remediation

`EvaluateViewpoint` derives the implicit query for query-less definitions from
`ConceptScope`: `entity_criteria = type in sorted(scope.entity_types)` (match-all when
`entity_types is None`; class/hierarchy predicates compile to the same admissibility the
scope already enforces — reuse `admits_entity_type` via a scope-predicate evaluation hook
rather than re-encoding classes as criteria), `connections.criteria = type in
scope.connection_types` when restricted. Ad-hoc queries are unaffected. The projection/
verifier paths are unaffected (they already consume scope directly). Tests pin: every
shipped scope-only definition returns a non-empty population on a seeded fixture repo.

### 6.2 Library uplift

`src/ontologies/archimate_4/viewpoints.yaml` grows from 4 scope-only entries to the full
covered Appendix-C set (25 standard + 3 custom definitions), each with scope + executable
query + presentation + verbatim purpose/content/stakeholders/concerns from its spec table.
Per the C.1 intro: `grouping` and junction elements are admitted in **every** default
scope, and each definition's description notes its Table C-1 category
(composition/support/cooperation/realization) and the spec's "starting point, not
normative" framing.

- Uplifted (version bump): `motivation` (C-18), `technology-usage` (C-10),
  `application-structure` (C-3), `layered` (C-6 — "all core elements and all
  relationships": scope = Core-domain type union, query = domain-membership criteria;
  the spec's own note that this viewpoint supports **impact-of-change analysis** is
  reflected by shipping it with `connections.traversal: both` available in the GUI toggle
  but defaulting to `direct`).
- New, basic set: `organization` (C-2), `information-structure` (C-4), `technology`
  (C-5), `physical` (C-7), `product` (C-8), `application-usage` (C-9),
  `process-cooperation` (C-11), `application-cooperation` (C-12), `service-realization`
  (C-13), `implementation-and-deployment` (C-14).
- New, motivation/strategy/implementation: `stakeholder` (C-15), `goal-realization`
  (C-16), `requirements-realization` (C-17), `strategy` (C-19), `capability-map` (C-20),
  `value-stream` (C-21), `outcome-realization` (C-22), `resource-map` (C-23), `project`
  (C-24), `migration` (C-25), `implementation-and-migration` (C-26).
- New, custom (this plan's capabilities, clearly described as tool-specific additions
  beyond the standard's example set): `element-dependents` / `element-dependencies`
  (§5.6) and `process-technology-support` — the layered cross-domain motivating case:
  parameterized by a business-process anchor (or executed broad), selecting the
  process(es) plus technology-domain elements with a derived structural/dependency
  relationship to them (`traversal: derived`), connections `traversal: both`,
  presentation `diagram` — the intermediate application layer omitted, indirect support
  shown as derived connections per §5.4/§5.7.

Element-name → type-slug mapping is specified in the ledger WU as an **explicit table
against this repo's normalized ontology** — critically: `process`/`function`/`service`/
`event`/`role`/`collaboration` are domain-neutral **common** entities here (`hierarchy:
[common]`, so their reserved `domain` value is `common`), and a `domain: business`-style
condition would silently exclude them. The mapping rules are therefore: (1) spec element
names with explicit layer prefixes ("Business object", "Application interface") map to the
dedicated slugs (`business-object`, `application-interface`); (2) unqualified behavior/
role/collaboration names — which is how the C tables themselves list them — map to the
common slugs **with no domain filter**; (3) where a viewpoint's prose is clearly
layer-scoped despite generic naming, narrow by the **shipped specializations**
(`specialization in [business-process, …]` OR `specialization absent` — never exclude
unspecialized elements from a default); (4) "Core element" → the Core-domain type union
via `domain in [business, application, technology, common]`. Never use a `domain`
condition to layer-scope a common type. Presentation defaults follow purpose:
designing ⇒ `diagram`/`exploration`; deciding ⇒ `table` or `matrix` where the spec text
names a cross-reference intent (e.g. `capability-map` ships a scale-mode heat capability
per C.3.2's explicit heat-map use). A **spec-fidelity test** asserts, per definition, that
stakeholders/concerns/purpose/scope element lists match the table contents recorded in a
fixtures file — spec comparison as an executable gate, not a review claim. Module-tier
definitions stay read-only; version = 1 for new entries, uplifted entries bump.

## 7. Feature IV — the Q6 remainder, critically evaluated

| Q6 item | Verdict | Rationale & mechanism |
|---|---|---|
| User-defined parameterized viewpoints | **Include** (§4.4) | Same mechanism the binding layer needs anyway (`ValueRef` resolution at execution); unlocks impact-analysis defaults; without it every anchored analysis is an ad-hoc query no catalog entry can capture. |
| Persistent generated diagrams / saving executions as view artifacts | **Include, via view derivation** (§5.6.3, §5.7 + WU) | Real demand (keep a result, re-run later; layered views showing indirect support across omitted layers). A new `viewpoint_execution` derivation strategy (params: slug+version or inline query + parameters) turns an execution into an ordinary generated diagram with refresh/staleness via the existing `view_derivations` flow — snapshot honesty for free, no new artifact kind, no second persistence path. Derived connections persist as accepted witness paths with per-occurrence architect review (§5.7). |
| Publishing / pinning | **Pinning yes, publishing no** | Pinning = repo-local quick access: `.arch-repo/viewpoint-pins.yaml` (list of slugs; not definition content, so read-only module definitions are pinnable and D14 promotion is untouched), REST CRUD, Home/management surfacing. A HoriZZon-style publishing portal presumes an audience-facing multi-user web product this tool deliberately is not — **rejected**, not deferred; revisit only if the product scope itself changes. |
| Continuous heat-map scales | **Include** (small) | Appendix C explicitly motivates heat maps (C.3.2/C.3.5); range bands force arbitrary thresholds. Third `StyleRule` mode `scale`: `scale_attribute` (numeric/date), `scale_min`/`scale_max` (None ⇒ data-driven from the result, deterministic), two endpoint tokens `scale_tokens`; adapters interpolate; legend derives min/max/gradient. Validation mirrors range mode. |
| Label rules | **Include as display option, not rule system** | BiZZdesign's label *filter* is conditional; the converged need is "show attribute X under the name". `display_options.label_attribute` (validated §3.3/`derived.` path) for `exploration`/`diagram` — one option, no rule engine. Conditional label rules stay out (styling already signals conditions; two mechanisms for one visual channel would fight). |
| Tooltip rules | **Reject** | Tooltips render the fixed per-item summary — a locked D15 boundary (descriptive content is not configurable presentation). Making them configurable reopens a settled decision with no new evidence. |
| Chart rules | **Defer** (explicitly, again) | Genuine reporting value, but it is a new rendering surface with real design weight (dataviz correctness, theming) in a frontend mid-rewrite; nothing in Ch. 13 requires charts for conformance (views need not be graphical, and table/matrix/exploration cover the deciding purpose). Revisit after the rewrite stabilizes — the §4.3 derived attributes already provide the aggregations a chart layer would consume, so deferral costs no rework. |

## 8. Presentation model changes (consolidated)

- `StyleConditionMode = Literal["match", "range", "scale"]`; `StyleRule` gains
  `scale_attribute`, `scale_min`, `scale_max`, `scale_tokens` (§7). Validation:
  scale-mode fields mutually exclusive with the other modes' fields
  (`style-mode-field-mismatch`), numeric/date attribute only, exactly two tokens.
- `REPRESENTATION_CAPABILITIES`: no new capability names needed for scale (it rides
  `node_color`/`edge_color`/`cell_emphasis`/`badges` via mode); `label_attribute` is a
  validated display option (extends the existing `unsupported-display-option` check) on
  `exploration` and `diagram`.
- `ColumnSpec` unchanged — `derived.<name>` flows through `source` because it is a path
  (§4.3), which is the whole point of the namespace design.

## 9. Application layer, REST, MCP

- **`EvaluateViewpoint`**: pipeline per §4.5; new typed errors
  (`ViewpointParameterError`, `BindingCardinalityError` — a declared instance-type
  binding resolving to ≠1 item, error naming the binding and the actual count —
  `DerivationLimitError`) beside the existing timeout error;
  duration/warning logging unchanged in shape.
- **REST** (`routers/viewpoints.py`): `execute`/`execute-projection`/`execute-diagram`
  bodies gain `parameters`; error mapping for the new typed errors (400 with issue-shaped
  payload); `viewpoint_authoring.py` `POST /api/viewpoints/summarize` and
  `/criteria-catalog` extended (catalog additionally lists binding/parameter/derived
  authoring vocabulary + derivation classification so the builder renders pickers without
  hardcoding). New: `GET/PUT /api/viewpoints/pins` (§7). `GET /api/neighbors` gains
  `traversal`/`include_potential` (§5.6).
- **MCP**: `artifact_query_viewpoint execute` gains `parameters` (and honors definitions'
  parameter signatures in `list`); `artifact_viewpoint create/edit` validates the full new
  grammar (persist_edit mode); `artifact_query_find_neighbors` per §5.6. The
  `artifact_help` **viewpoints topic** documents: binding/parameter/derived grammar +
  worked examples, the result-type algebra strings, quantifier semantics, derived-traversal
  knobs + reserved paths, certainty semantics, and the impact-analysis recipe. Tool
  descriptions stay short; `uv run tools/generate_mcp_docs.py` regenerated (CI `--check`).
- **Determinism**: unchanged guarantees — stable sorts everywhere, no wall-clock reads
  outside `src/domain/clock.py`.

## 10. GUI implications (contract-first; implementation gated on the frontend rewrite — D12)

Contracts the rewritten frontend must satisfy (Phase H acceptance tests are written against
REST + Playwright, not against current components):

- **Query tab**: definitions without a query show an explicit empty state ("Scope-only
  viewpoint — executes via its concept scope. Add a query to refine.") with the derived
  scope summary — never a blank pane (the 2026-07-13 report).
- **Execution**: running any catalog definition against the dogfood repo yields the
  non-empty population the backend returns (Playwright smoke asserts ≥1 entity for a known
  definition; regression for the second reported defect), including parameter prompting for
  parameterized definitions (typed inputs, `entity-id` via the existing entity picker).
- **Full authoring lifecycle, actually usable** (the current GUI's viewpoint editing is
  not — this is a requirement, not a nice-to-have): definitions are creatable and
  editable end-to-end in the GUI — metadata, **scope (domain/type filter)**, query,
  presentation — at parity with `artifact_viewpoint`; semantic edits surface the version
  bump; delete shows referencers. The Query tab renders the existing query of every
  catalog definition (regression of the 2026-07-13 defect report).
- **Scope editor is a designed picker, not an unstyled checkbox list**: entity/connection
  type selection grouped by domain in collapsible sections with per-domain
  select-all/none, type-ahead search across names and slugs, selected types as removable
  chips, live counts ("12 of 61 types") and a live scope summary sentence, and a clear
  visual distinction between entity types and connection types (and between
  unrestricted-vs-restricted axes). Visual grammar consistent with the existing
  entity-picker patterns; specific layout is the frontend rewrite's call, but "flat
  unstyled checkbox list" is explicitly a rejected implementation.
- **Builder**: bindings/parameters/derived-attributes panels reuse `CriteriaTreeBuilder`;
  binding references appear in the `ValueRef` picker with quantifier/aggregate selects;
  live summary shows the §4.6 sentences; validation issues map by path into the new
  panels. No formula/text escape hatch (D4).
- **Impact exploration**: `GraphExploreView` gains a derived-traversal toggle +
  potential-inclusion checkbox + hop bound; derived edges render dashed with certainty
  badge and a "show chain" affordance (path ids from the summary); "materialize
  connection" pre-fills the creation flow (§5.6.4). Legends derive from style rules incl.
  scale gradients.
- **Derived-candidate review (§5.7)**: the generated-diagram flow presents derived
  connections as reviewable candidates — certain pre-accepted, potential pre-rejected —
  showing derived type, certainty, and witness chain at decision time; refresh staleness
  findings on accepted paths are surfaced and actionable, never auto-resolved.
- **Pins**: pin/unpin on the management list; pinned definitions on Home.
- **Failure-mode UX is part of the contract**, not an afterthought: validation-400
  payloads render as path-addressed errors on the offending widget; execution timeout,
  `DerivationLimitError`, parameter errors, and `BindingCardinalityError` each display
  as a distinct, actionable error state (never an empty result); stale-path refresh
  findings (§5.7) are listed and actionable; failed saves surface a retry affordance
  without losing edits; empty scope-picker search shows an explicit no-matches state.
  Accessibility basics hold throughout the authoring surfaces: labelled controls,
  coherent focus order through the picker and criteria builder, keyboard-operable chip
  removal and typeahead.
- Frontend mirrors (`tools/gui/src/domain/viewpoint*`) re-derive from the extended
  canonical grammar; `types.generated.ts` regenerated; Vitest per component per the
  test-file-organization convention.

## 11. Lifecycle, governance, compatibility

- **Versioning/promotion**: bindings/parameters/derived/traversal/presentation additions
  are semantic content — edits bump versions exactly as today; D14 exact-version promotion
  is unchanged (one new test: promoting a diagram whose pinned definition uses schema-1
  constructs). Pins are repo-local state and never promote.
- **Serialization**: D10. Round-trip identity (`parse ∘ serialize = id`) extends over
  every new construct; unknown keys remain parse errors; defaults omitted on write.
- **D17 coverage invariant**: every persisted query uses the current schema-1 grammar;
  migration is explicit and regression-tested; the new
  `viewpoint-pins.yaml` sidecar is a *new* optional file (absence = no pins), no upgrade
  step required.
- **Security/auth**: no new trust boundaries — all new surfaces ride existing REST/MCP
  servers and their existing access models; read tools stay read-only (derivation is pure
  computation over the read model); the only new writes are pins (repo-local YAML via the
  existing single-writer backend write path) and the GUI materialize flow (existing
  connection-creation path, existing validation). No secrets, no new inputs interpreted as
  code; parameters are typed scalars validated before use.
- **Data consistency**: no multi-artifact writes introduced; derived relationships are
  never persisted (D6), so no staleness class is created; generated impact diagrams reuse
  the derivation-refresh staleness model.
- **Observability**: the *success* log line gains `binding_count` and
  `derived_edge_count` — there is deliberately no `derivation_truncated` field, because
  relationship derivation never truncates (§5.5: limit overflow is `DerivationLimitError`,
  no result). The *error* path logs `error_code=derivation-limit`, the configured limit,
  and the count at failure — with no result payload. Ordinary entity truncation (a
  complete result cut for transport, with honest counts) is a separate, unchanged
  mechanism. New warnings enumerated in §5.5; verifier codes unchanged
  (E180/W180/W181/W182 untouched — definitions validate at save, artifacts at verify).

## 12. Documentation plan (Diátaxis; no plan/decision-ID references in pages)

- `docs/03-modeling/viewpoints.md` — extend: bindings ("compare against another
  selection"), parameters, derived attributes, worked examples; scope-only execution
  behavior.
- `docs/03-modeling/impact-analysis.md` — **new** explanation + how-to: derived
  relationships (certain vs potential, with the strength orderings), impact workflows
  (GUI, MCP, generated impact diagrams), materializing potential relationships; glossary
  note distinguishing relationship derivation from view derivation.
- `docs/reference/viewpoints-schema.md` — extend: full new grammar, result-type strings,
  quantifier/empty-value semantics tables, derived reserved paths, new validation codes,
  new settings, parameter signatures in tool outputs.
- Conformance page (`docs/…` per parent plan's Appendix-B page): new rows — Appendix B
  derivation rules (engine + per-rule tests), Appendix C example viewpoints (library +
  fidelity tests), profile-based heat maps (scale mode). Wording stays "aims for
  conformance…, not independently verified".
- `README.md` capability list: impact analysis + executable default viewpoints, same
  weight as sibling capabilities.
- Tutorial: the deferred "first viewpoint" tutorial (companion plan §14) gains a step for
  executing a default viewpoint and one for an impact query — still gated on the rebuilt
  GUI shipping.

## 13. Self-model plan (MCP-authored only)

Following the standing modeling discipline (guidance-first, descriptions-over-connections,
no argumentative entities): add application components `Relationship Derivation Engine`
and `Query Binding Evaluator` under the existing Query Engine context
(`APP@1712870400.v9LvfK.query-engine`), functions for `Derive Indirect Relationships` and
`Evaluate Query Bindings`, a requirement `Impact Analysis over Derived Relationships`
realized by them and serving `REQ@1783870981.mdH8Uv.viewpoint-based-model-presentation`;
enrich `BOB/DOB Viewpoint Definition` descriptions with bindings/parameters. Exact entity
cut is decided at WU time against `artifact_authoring_guidance` (read-before-propose);
verify with `artifact_verify` after each batch.

## 14. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Derivation explosion on dense models | Hop cap + relationship cap + timeout, all typed/loud (§5.3); BFS memoization; per-rule tables are O(1) lookups. |
| Rule-table transcription errors vs the spec | The §5.3a five-method protocol: spec_ref-traceable data, independently-authored dual encoding, exhaustive metamodel sweep, encoding-independent semantic invariants, worked-example fixtures — plus a recorded line-by-line review pass gating Phase D. PDR12 retains its explicit direct-permission guard; other derived results remain indirect values. |
| Type-inference too clever / opaque errors | Conservative inference only (§4.1); every mismatch error carries expected/found type strings; declared types are always written back canonically. |
| Binding evaluation cost on large repos | Bindings evaluated once (D1); count cap; same entity population machinery as the primary query (no second scan path). |
| GUI churn against the concurrent rewrite | D12: contracts + REST first, Vue last, acceptance via Playwright against the rewritten shell; no edits to legacy components. |
| Summary renderer intelligibility degrades with lets | Dedicated per-construct rendering tests incl. quantifier/negate interactions; the D3 no-implicit-sets rule exists precisely to keep sentences honest. |
| Namespace confusion ("derivation") | §5.0 naming rule; glossary; module names reviewed in the ledger's naming checklist. |

## 15. Work breakdown

Reconciled into `TASKS-viewpoints-bindings-and-derived-relationships.md` — Phases A–I,
WU-A1 … WU-I5, each with anchors, dependencies, local acceptance, plus the global
acceptance gate (quality gates, fitness functions, spec-fidelity suites, dogfood
executable checks). The ledger is authoritative for numbering and sequencing.

## 16. Open questions

- [x] **Q1 — Goal contribution / principles viewpoints**: resolved 2026-07-13 — the
  extract is complete; those two names appear only in C.2's intro list (legacy from
  ArchiMate 2.x), no 4.0 tables exist. Shipped without dedicated definitions; covered by
  `goal-realization` and `motivation` (§1.1).
- [x] **Q2 — Example B-12 figure**: resolved 2026-07-13 — `Figure-B-12.jpg` added; the
  red/gray acceptance split grounds the §5.7 flow and the WU-B5 fixture.
- [x] **Q3 — `layered`/`application-structure` query uplift**: resolved 2026-07-13 —
  tables C-3 and C-6 added to the extract (with the rest of C.1); §6.2 specifies both
  from the spec tables directly.
- [ ] **Q4 — Frontend rewrite handshake**: which branch/PR to target for Phase H, and
  whether the rewrite adopts the §10 contracts directly. — Owner: Michael + frontend
  effort
- [ ] **Q5 — Junction traversal**: v1 excludes chains through junctions (§5.2); confirm
  acceptable or schedule junction-aware derivation as a follow-up. Note the C.1 intro
  admits junctions into every viewpoint's *scope* — that is unaffected (junctions remain
  placeable); only derivation *chains through* them are excluded. — Owner: review

---

## Appendix A — Canonical serialized form additions (YAML, executable fixtures)

Same two-layer validation regime as the companion plan's Appendix A (shipped catalog for
slugs; fixture profiles installed into the test repo's `.arch-repo/schemata/` — reuse
`tests/fixtures/viewpoints/schemata/`, adding `attributes.requirement.schema.json` with
`{"properties": {"priority": {"type": "integer"}}}`). Every example below must pass
save-mode validation in the test suite; an example that stops validating is a build
failure.

```yaml
viewpoints:
  # 1. Let-binding + aggregate comparison + set membership + result inclusion
  - slug: components-above-fleet-risk
    version: 1
    name: Components Above Fleet Median Risk
    query:
      query_schema: 1
      bindings:
        - name: all-components
          result_type: entities[application-component]
          select: entities
          criteria:
            kind: group
            conjunction: and
            children:
              - {kind: condition, attribute: type, comparator: eq, value: application-component}
        - name: risk-ceiling
          result_type: number
          select: entities
          criteria:
            kind: group
            conjunction: and
            children:
              - {kind: condition, attribute: type, comparator: eq, value: application-component}
          project: risk_score
          aggregate: avg
      entity_criteria:
        kind: group
        conjunction: and
        children:
          - kind: condition
            attribute: id
            comparator: in
            value: {from: binding, name: all-components, project: id}
          - kind: condition
            attribute: risk_score
            comparator: gt
            value: {from: binding, name: risk-ceiling}

  # 2. Parameterized impact analysis with derived traversal (the shipped default's shape)
  - slug: element-dependents
    version: 1
    name: Element Dependents (Impact of Change)
    purpose: [deciding]
    content: [coherence]
    stakeholders: [enterprise-architects, operational-managers]
    concerns: [what is affected if this element changes]
    query:
      query_schema: 1
      parameters:
        - {name: anchor, type: entity-id, required: true,
           description: The element whose dependents are analyzed}
      entity_criteria:
        kind: group
        conjunction: and
        children:
          - kind: condition
            attribute: id
            comparator: eq
            value: {from: parameter, name: anchor}
      include_connected:
        - traversal: derived
          include_potential: false
          max_hops: 4
          direction: incoming
      connections:
        enabled: true
        traversal: both
    presentation:
      representation: exploration
      styling_rules:
        - capability: edge_emphasis
          mode: match
          match_criteria:
            kind: group
            conjunction: and
            children:
              - {kind: condition, attribute: certainty, comparator: eq, value: potential}
          value: emphasis-dashed-caution
        - capability: node_color
          mode: scale
          scale_attribute: derived.impact-distance
          scale_min: 1
          scale_max: 4
          scale_tokens: [heat-near, heat-far]
      default_style:
        edge_emphasis: emphasis-normal
    # the derived attribute the scale rule sources (inside query.derived):
    #   - name: impact-distance
    #     traversal: derived
    #     direction: incoming
    #     reduce: min
    #     of: relationship.hops

  # 3. Derived attribute as column + condition (query.derived declaration)
  - slug: requirement-load
    version: 1
    name: Requirement Realization Load
    query:
      query_schema: 1
      derived:
        - name: realizer-count
          direction: incoming
          traversal: derived
          connection_criteria:
            kind: group
            conjunction: and
            children:
              - {kind: condition, attribute: type, comparator: eq, value: archimate-realization}
          reduce: count
      entity_criteria:
        kind: group
        conjunction: and
        children:
          - {kind: condition, attribute: type, comparator: eq, value: requirement}
          - {kind: condition, attribute: derived.realizer-count, comparator: gte, value: 1}
    presentation:
      representation: table
      columns:
        - {label: Requirement, source: name}
        - {label: Priority, source: priority}
        - {label: Realized by (incl. indirect), source: derived.realizer-count}
```

(Example 2's `derived.impact-distance` declaration is shown inline in its comment —
`traversal: derived`, `reduce: min`, `of: relationship.hops` — pinning both that scale
rules may source `derived.` paths and that the reserved `relationship.hops` source makes
the default expressible without special-casing.)

Serialization rules carry over: defaults omitted, unknown keys error, `query_schema`
explicit, `parse ∘ serialize = id`.

## Appendix B — Conformance mapping additions

| Obligation (ArchiMate 4.0) | Implemented by | Verified by |
|---|---|---|
| Appendix B derivation rules DR 1–8 | rule tables + fold (§5.2) | one test per rule + worked-example fixtures |
| Appendix B potential rules PDR 1–12, opt-in modeler judgment | certainty model + `include_potential` + materialize flow | per-rule tests; GUI/Playwright certainty rendering |
| §B.4 restrictions | restriction predicates R1–R14, RJ1–RJ2 | one test per bullet |
| Direct versus indirect relationship boundary | direct-table boundary and PDR12 guard | Financial Application regression + PDR12 property test |
| Appendix C example viewpoints | module library (§6.2) | library load + spec-fidelity fixture test |
| §13.4.2 profile-based representations (heat maps) | scale-mode style rules | style evaluation + legend tests |
| §13.4.1 purpose/content classification on all defaults | library metadata | fidelity test |

## Appendix C — BiZZdesign Query Language correspondence (informative)

| BQL concept | This plan |
|---|---|
| Named intermediate result sets | `QueryBinding` (`select` + criteria) |
| Fixed object references | `id eq` condition (optionally via parameter) |
| Attribute projection | `project:` |
| Aggregation functions (count/sum/avg/min/max) | `aggregate:` / `DerivedAttribute.reduce` |
| Set membership tests | `in` + binding `project: id` |
| Traversal to related objects | incident predicate / neighbor inclusion (direct), derived traversal (indirect) |
| Script/formula text | **deliberately absent** (D4) — structured trees only |

## Appendix D — Required test matrix (delta; companion-plan Appendix C stays in force)

**Result types & inference** — printer/parser round-trip for every algebra shape; inference
per §4.1 rule (union narrowing, ambiguous-attribute error, reserved-path projection over
open unions, aggregate kind table); declared-vs-inferred mismatch.

**Bindings** — topological evaluation incl. forward-reference and cycle errors; evaluated
exactly once (spy read-access); empty-set semantics table (count/sum/avg/min/max,
any/all); `include_in_result` membership + `via` + truncation ordering across every legal
shape — `entity[…]`, `optional[entity[…]]` both empty (nothing included) and present
(one entity, membership `expanded`), `entities[…]` — plus rejected shapes
(scalar/connection/tuple ⇒ `include-in-result-shape-unsupported`); caps; binding
refs in every criteria position (primary, incident, inclusion, connection-selection,
style-match, matrix-axis).

**ValueRef extension** — every new kind × comparator typing rule (incl.
`unquantified-set-comparison`, tuple rules); quantifier evaluation; parameter resolution,
missing/mistyped/unknown-parameter typed errors; dangling `entity-id` → warning +
no-match; unsupported query-schema payloads → parse error naming the version.

**Derived attributes** — count/sum/avg/min/max over connection- and endpoint-sourced
attributes; direct vs derived traversal; memoization (call-count spy); `derived.` paths in
conditions/columns/range/scale; rejection in `group_by` and in binding criteria.

**Relationship derivation** — one test case per DR/PDR rule and per restriction bullet,
with **role-functional test names** (`test_structural_chain_derives_weakest_relationship`,
not a spec-id name) and traceability carried by `spec_ref` parametrization data / pytest
case ids — names say what the behavior is, data says where it's specified;
strength-ordering tables; fold certainty + `potential_steps`;
junction/self-loop exclusion; dedup (min hops, certain-wins, deterministic witness path);
worked examples B-3, B-9, B-11, B-12, B-17 as fixtures;
bounds (hop cap honored, relationship cap → typed error, setting overrides); the
derivation-domain classifier over every shipped entity type (junctions ⇒ `relationships`).

**Rule-verification battery (§5.3a)** — dual-encoding cell-by-cell agreement
(independently authored, no runtime imports); exhaustive metamodel sweep (every permitted
input pair × orientation ⇒ outputs permitted); encoding-independent semantic invariants
over generated random models (Access⇒PSE target, Influence⇒Motivation target,
junction-source⇒Association only, PDR-step⇒potential, structural strength ≤ weakest
link).

**Path reconstruction** — round-trip property (enumerated path reconstructs identically);
`Broken` on missing connection / dangling endpoint / orientation mismatch;
`NoLongerDerives` on retype and newly-firing restriction; certainty-drift surfaced.

**Cardinality (typed bindings)** — instance-type declarations: 0/1/>1 resolution against
`entity[…]` (error/ok/error) and `optional[…]` (ok-missing/ok/error); singular projection
scalar typing; tuple arity mismatch static; `aggregate-over-instance`.

**Query integration** — traversal flags on all three constructs; derived reserved paths
only (`derived-traversal-path-unsupported`); matrix bridging over derived connections;
depth-cap counts derived node as one level; symmetric normalization not applied to derived
edges.

**Execution & result** — pipeline order observable via fixtures; new summary fields
None/empty for modeled connections; synthetic id format + stable sort; new warnings; four
counts unchanged; REST/MCP parity fixture extended with parameters.

**Derived connections on diagrams (§5.4/§5.7)** — ad-hoc `diagram` representation renders
a derived connection in its derived type's notation with derived marker + certainty;
generated diagrams persist accepted witness paths only (no fabricated connection
artifacts — asserted on the written frontmatter); certain pre-accepted / potential
pre-rejected defaults; refresh reports broken-chain and changed-derived-type staleness
(never silent redraw/drop); layered fixture (process supported by technology, application
layer omitted) end-to-end.

**Scope fallback** — restricted scope, unrestricted scope, class-predicate scope; shipped
scope-only definitions return non-empty populations on the fixture repo; summary states
scope derivation.

**Default library** — loads; every definition passes save-mode validation; spec-fidelity
fixture comparison (purpose/content/stakeholders/concerns/element lists); every default
returns a non-empty population against the seeded fixture repo; `element-dependents`
returns known transitive dependents on a crafted chain fixture.

**Presentation** — scale mode: interpolation bounds, data-driven min/max determinism,
missing attribute → default style, validation errors; `label_attribute` validation.

**Pins** — sidecar CRUD, absence = empty, not promoted, unknown slug pruned with warning.

**Summary renderer** — every new construct; quantifier + negate phrasing; parameter
placeholders; identical string across REST and MCP (shared fixture).

**Intelligibility/paths** — every new validation code carries a resolvable path; snapshot
test extended for code stability.
