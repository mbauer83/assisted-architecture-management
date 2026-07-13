# Viewpoints: Query, Projection, Presentation & Tooling Model

Companion plan to `PLAN-archimate-4-compliance.md` §4.4 (D7/D8/D15). That section's original
query/presentation design (`ExecutableViewpointQueryV1`, `ExpansionRule`, the discrete-only
`StyleRule`, a single combined `artifact_viewpoint` MCP tool) is **superseded by this
document**. `PLAN-archimate-4-compliance.md` should carry only a short pointer to this file;
this document is the authoritative design for everything under it — including the D15
execution-result contract, restated in §7.1 so this file is self-contained.

## 1. Why this document exists

`ConceptScope`, `ViewpointDefinition`, `ViewpointApplication`, the two-tier
module/`.arch-repo` catalog loading, per-diagram/matrix version-pinning with staleness
warnings (E180/W180/W181), and the definition/application-vs-ad-hoc-execution split were
implemented (WU-E1–E4) and are **not** in question — they are load-bearing and stay as-is.
What is in question is everything inside `ExecutableViewpointQueryV1` and `PresentationSpec`:
a design review found the flat `all_of`-only query, the `ExpansionRule`/`execution_anchor`
concept, the uniform `include_connections` enum, and the discrete-value-map-only `StyleRule`
inadequate for real use. This document replaces that inner model. Nothing shipped depends on
the old shape: the committed starter library (`src/ontologies/archimate_4/viewpoints.yaml`)
only ever populated `scope`/`purpose`/`content`/`stakeholders`/`concerns`, never `query` or
`presentation` — so this is a clean redesign, not a data migration.

The design is organized around one central abstraction: the **viewpoint projection** (§6).
One evaluator, two execution contexts — full-repository query (ephemeral generated views)
and artifact-local application (ghosting/hiding/highlighting on an existing diagram or
matrix). Criteria (§3), presentation (§5), the verifier, the GUI, and the MCP surface all
consume that single contract, so the two halves of the feature cannot drift apart.

**Status: independently reviewed and adapted; all design decisions resolved. Ready for
reconciliation into the task ledger (§14) and implementation.**

### 1.1 Research grounding

Three lines of research informed the redesign (full detail was reported in-session, summarized
here for traceability):

- **BiZZdesign Enterprise Studio / HoriZZon** (closest commercial precedent): filtering is a
  flat condition list, AND by default with a single set-level OR toggle (no per-group nesting);
  NOT is a per-condition "exclusive" toggle, not a boolean operator; there are seven named
  *view filter types* (label, tooltip, color, compare, relation color, relation roles,
  highlight) — color/label filters style content **already present** in a view, they don't
  decide relationship inclusion; a separate "relationships between (sets of) objects" analysis
  computes a cross-reference table between two arbitrary populations; no documented concept of
  N-hop/expansion-style traversal as a filter condition (only Archi's separate, non-filter
  Visualiser has depth-limited traversal).
- **UI/UX precedent for nested boolean builders** (Airtable, Notion, Jira, Metabase,
  Salesforce): the converged good pattern is flat-AND by default, with **explicit, opt-in**
  boxed/indented OR-groups capped at ~3 levels, distinct "Add condition" vs. "Add condition
  group" actions, and a live plain-language summary of the resulting logic. The converged
  **anti-pattern**, found independently in both Metabase and Salesforce, is forcing OR/complex
  logic out of the visual tree into a text/formula/numbered-expression escape hatch — this is
  the single clearest, most-repeated usability failure in the research and must not be
  repeated here. Conditional formatting/coloring (Airtable record coloring, Google Sheets,
  Grafana thresholds) converges on: reuse the *same* condition-builder widget used for
  filtering, an ordered/drag-reorderable rule list evaluated first-match-wins, an explicit
  default/fallback, and treating "single condition → style" and "gradient/threshold range" as
  two separate, simple modes rather than one general rule language.
- **Python criteria/rule-evaluation libraries**: no existing library fits end-to-end.
  `rule-engine` is well-typed but string-DSL-first (bad fit for a GUI that must introspect/edit
  a tree). `json-logic-py` is JSON-tree-first (good structural fit) but the canonical package is
  dormant and forks are fragmented, with no typed attributes and no relational/graph predicate.
  `business-rules` is action-triggering with single-fact scope. None support a graph-incidence
  predicate ("has an incident connection of type T to/from an entity matching X"); that is a
  one-hop traversal plus recursive sub-criteria evaluation, well short of general subgraph
  isomorphism (NetworkX VF2 et al. would be substantial overkill). **Conclusion: build a small,
  custom, JSON-serializable criteria engine** rather than adopt a library.

## 2. What stays unchanged (locked by earlier phases, not reopened here)

- `ConceptScope` as the scope-intersection primitive (diagram-type scope ∩ viewpoint scope).
- `ViewpointDefinition` / `ViewpointApplication` split; version pinning + stale-application
  warning (W180); two-tier module + `.arch-repo/viewpoints.yaml` catalog loading; enforcement
  setting (`off|warn|ghost`) with per-application override. Enforcement keeps exactly these
  three values — "hide" is a per-surface display option layered on the projection (§6.3),
  not a fourth enforcement level.
- The **definition vs. ad-hoc execution** distinction: executing a query needs no artifact and
  no `ViewpointApplication`; only a diagram/matrix's *persisted* narrowing does.
- Executions are ephemeral and read-only — never persisted as a diagram (a "generated view
  filter" in the Horizzon sense). Generating a *persistent* diagram from an execution stays
  explicitly out of scope (candidate follow-up, unaffected by this redesign).
- The MCP execution boundary principle: *customizable presentation* (representation, styling,
  column/group_by choice) is GUI-only, meaningless without a renderer; the *descriptive content*
  of a result (which entities/connections matched, plus a fixed per-item summary) is always
  present, unstyled and unconfigurable, for every consumer including agents.
- `purpose` (values `designing|deciding|informing`), `content` (values
  `details|coherence|overview`), `stakeholders`, `concerns`: these are ArchiMate's own
  descriptive viewpoint metadata (§5.7 conformance), not executable configuration —
  clarified in §8 below. Their role is untouched; the one shape change is cardinality
  (§8: purpose/content become tuples, aligning with the C19C exchange schema —
  Appendix D).
- Promotion governance (D14): enterprise definitions are the baseline, engagement repos may
  extend; promoted artifacts carrying a `ViewpointApplication` require the exact pinned
  definition version to exist enterprise-side. Restated with the rest of the lifecycle rules
  in §10.

## 3. The criteria engine (replaces the flat `all_of` query)

New module: `src/domain/viewpoint_criteria.py`. Two parallel small type families — one for
entities, one for connections — rather than one generic-over-leaf-type structure, since the
leaf shapes genuinely differ (entities gain a relational predicate; connections don't need
one, they gain endpoint-attribute references instead).

```python
Conjunction = Literal["and", "or"]
Comparator = Literal["eq", "neq", "in", "exists", "absent", "lt", "lte", "gt", "gte"]
# Exactly today's VALID_OPERATORS set — this redesign restructures the TREE, it does not
# expand the comparator vocabulary. There is deliberately no `not_in`: per-condition
# `negate` (below) already expresses it as `in` + negate, and one spelling per meaning
# keeps the GUI builder and the semantics table (§3.4) smaller. NUMERIC_ATTRIBUTE_TYPES
# gating (lt/lte/gt/gte only valid against numeric/date attributes) carries over unchanged.

ValueRefKind = Literal["literal", "attribute_of_self", "attribute_of_endpoint"]

@dataclass(frozen=True)
class ValueRef:
    """A condition's comparison value: a literal, or a reference to another attribute.

    ``attribute_of_self`` compares against another attribute on the SAME entity/connection
    being evaluated (e.g. ``end_date >= start_date``). ``attribute_of_endpoint`` is valid only
    on connection conditions, and reads an attribute off the source or target entity (e.g.
    ``weight > source.threshold``).
    """
    kind: ValueRefKind
    literal: object = None
    attribute: str | None = None                       # kind != literal
    endpoint: Literal["source", "target"] | None = None  # kind == attribute_of_endpoint only
```

**Non-foreclosure note (deferred — Q7, see parent plan §10)**: `ValueRefKind` is an open union
with exactly three members implemented now. It deliberately cannot express "this entity's
attribute compared against a *specifically referenced* other entity's attribute" (e.g. "risk
score greater than the risk score of that other entity over there") — `attribute_of_self` only
reaches the same item, and `attribute_of_endpoint` only reaches a connection's own two
endpoints from a connection condition. Reaching an arbitrary related entity's attribute from an
entity condition needs either a narrow addition (a fourth kind, `attribute_of_anchor`, valid
only inside `IncidentConnectionCondition.endpoint_criteria`, naming the anchor entity of that
specific hop) or — the direction actually wanted — a **general named-binding / query-expression
layer**: named sub-queries with a declared result type (entity, set of entities, connection, set
of connections, or a typed attribute), each markable reference-only or result-included, usable
as a `ValueRef` target anywhere in the definition (the BiZZdesign Query Language precedent).
That general form is real graph-query-engine territory — dependency-ordered evaluation with
cycle detection, an aggregation vocabulary the moment a binding is set-valued (`max`/`any`/…),
and a nontrivial extension to §7.2's type-checking and the §9.1 plain-language renderer (an
unquantified set reference doesn't summarize sanely) — comparable in size to this whole
companion plan, not a §3 patch. Confirmed direction (2026-07-10): build the **general** form,
but only after the rest of the ArchiMate 4 compliance plan ships; its own design (binding
scoping, aggregation semantics, intelligibility of named-set summaries) gets a dedicated
follow-up plan, not a retrofit here. Noted so the omission is visibly a decision, not an
oversight — same pattern as §5.3's `ColumnSpec`/`DerivedMetricRef` note.

```python
@dataclass(frozen=True)
class AttributeCondition:
    attribute: str                  # dotted path, §3.3
    comparator: Comparator
    value: ValueRef = ValueRef(kind="literal", literal=None)
    negate: bool = False            # NOT is a per-condition toggle, not a separate node type
                                     # — BiZZdesign's "exclusive" toggle precedent. Strict
                                     # logical complement; see §3.4 for the missing-attribute
                                     # interaction.

@dataclass(frozen=True)
class IncidentConnectionCondition:
    """Entity-only predicate, replacing ExpansionRule/execution_anchor/roots entirely: "this
    entity has (or, negated, does not have) at least one incident connection matching
    ``connection_criteria``/``direction`` whose OTHER endpoint matches ``endpoint_criteria``."
    Fully criteria-based on BOTH legs of the hop: the traversed connection is narrowed by a
    ``ConnectionCriteriaGroup`` — type, specialization, and profile attributes via the same
    §3.3 path namespace as everywhere else, not a bare type set — and the far endpoint by an
    ``EntityCriteriaGroup``. So "has an outgoing serving connection with strength >= 3 and
    specialization S to a business process matching X" is directly expressible. Recursive —
    ``endpoint_criteria`` may itself contain further ``IncidentConnectionCondition`` nodes,
    bounded by the depth-cap validation (§3.2), which also counts boolean nesting inside
    ``connection_criteria``. This is a one-hop graph-incidence test with recursive
    sub-criteria, not general subgraph matching — deliberately short of a graph-query
    engine, per the library research above.
    """
    connection_criteria: "ConnectionCriteriaGroup | None" = None  # None = any connection
    direction: Literal["outgoing", "incoming", "either"] = "either"
    # Symmetric connection types (ConnectionTypeInfo.symmetric — e.g. association) are
    # authored with arbitrary source/target order, so a direction filter against them would
    # silently depend on authoring order. The evaluator therefore treats symmetric-type
    # connections as direction-agnostic regardless of ``direction`` (normalized to "either"
    # per connection, by the connection's actual type). Save-time validation warns,
    # best-effort, when direction != "either" and ``connection_criteria`` restricts the
    # connection type to only symmetric types (see §3.4).
    endpoint_criteria: "EntityCriteriaGroup | None" = None  # None = any entity
    negate: bool = False

EntityCriteriaNode = "AttributeCondition | IncidentConnectionCondition | EntityCriteriaGroup"

@dataclass(frozen=True)
class EntityCriteriaGroup:
    conjunction: Conjunction = "and"
    children: tuple[EntityCriteriaNode, ...] = ()   # empty root = match-all; see §3.4
    negate: bool = False

ConnectionCriteriaNode = "AttributeCondition | ConnectionCriteriaGroup"

@dataclass(frozen=True)
class ConnectionCriteriaGroup:
    conjunction: Conjunction = "and"
    children: tuple[ConnectionCriteriaNode, ...] = ()
    negate: bool = False
```

Both `EntityCriteriaGroup` and `ConnectionCriteriaGroup` are the **same type reused** for
query-time filtering and for style-rule matching (§5.2) — one condition-building concept at
the domain level, not just one widget at the GUI level.

### 3.1 Connection inclusion (replaces `IncludeConnectionsPolicy`)

```python
@dataclass(frozen=True)
class ConnectionSelection:
    enabled: bool = True                              # False => no connections at all
    criteria: ConnectionCriteriaGroup = ConnectionCriteriaGroup()  # additional constraint
```

**Structural invariant, not user-configurable**: a connection is included only if *both* its
source and target entities are in the included entity set — primary matches plus neighbor
inclusions, §4.1 (for the matrix representation with axis criteria, the sharper bridging
form in §5.4 applies instead). This
is fixed evaluator behavior, not an expressible/overridable criterion — matching the
BiZZdesign precedent that relation filters style/label content already scoped into a view
rather than independently deciding inclusion. `criteria` narrows *within* that structural
set (e.g., "only `archimate-serving` connections, and only where `strength >= 3`"); it can
never *widen* past it. `enabled=False` covers what the old enum's `"none"` meant.

### 3.2 Depth cap

`validate_viewpoint_definition` (existing registry-aware validator) gains a check computing
total tree depth — boolean nesting **and** relational (`IncidentConnectionCondition`) hops
combined, since both are forms of query complexity a GUI/human must read back. The cap is a
**system-level setting**, `validation.viewpoint_query_depth_cap` in `config/settings.yaml`
(same section as `viewpoint_enforcement`), **default 4** — 3 boolean levels, per the
converged UX research, plus one relational hop as the common case.

The cap is an **authoring-ergonomics gate, enforced in save-mode validation only** (§7.2) —
never at catalog load or evaluation. A definition authored under a deployment with a looser cap still
loads, evaluates, and promotes everywhere: two backends with different settings can disagree
about what may be *newly saved*, never about what is *valid*. This is what makes a
deployment-level setting safe here (no promotion hazard, no cross-backend validity split).
It is a validation error, not a dataclass-level invariant — the domain type stays simple and
the limit tunes without a structural change.

### 3.3 Addressable properties (the attribute-path namespace)

The old `EntityQueryFilter` had `entity_types`/`specializations`/`groups`/`domains`/
`statuses` as dedicated first-class fields. In the tree model those become ordinary
`AttributeCondition`s against a set of **reserved paths** covering the read-model fields
(`EntityRecord`/`ConnectionRecord`), so the GUI builder, the validator, and the evaluator
have exactly one condition shape. This is **one namespace, used everywhere a path appears**:
filter conditions, table `columns`, `ValueRef` references, and the fixed per-item summaries
— no separate column vocabulary, no special cases.

| path | applies to | value type | notes |
|---|---|---|---|
| `id` | entity + connection | string | artifact id |
| `name` | entity | string | |
| `type` | entity + connection | slug string | entity/connection type slug |
| `specialization` | entity + connection | slug string | specialization slug (multi-valued where the model allows several) |
| `group` | entity | string | directory-facet group |
| `domain` | entity | slug string | |
| `subdomain` | entity | string | |
| `status` | entity | string | lifecycle status |
| `version` | entity | string | string comparators only (`lt`/`gte`/… stay gated to numeric/date schema types) |
| anything else | per schema | per schema | dotted path into the D13 merged effective schema (base-type profile ⊕ specialization profiles) |

Every reserved path is both **filterable and display-usable** (a legal `ColumnSpec.source`).
A connection's endpoints are deliberately *not* addressable as left-hand condition paths
(no `source.type`): endpoint attributes are reachable only as comparison values via
`ValueRef(attribute_of_endpoint)`, and endpoint-type constraints on displayed connections
are already the structural invariant's job (§3.1) plus the incident predicate's from the
entity side. If a genuine "only connections whose target matches X" display-filtering need
emerges, an `EndpointCondition` node can join the `ConnectionCriteriaNode` union later
without breaking any existing definition — noted so the omission is a decision, not an
oversight.

Validation resolves the head of the dotted path against this table first, then against the
effective schema; unknown paths are a save-mode error exactly as today (§7.2 for modes).
The reserved names are validated against the runtime catalogs (unknown
type/specialization/domain slugs in a `value` are save-mode errors too, preserving current
`viewpoint_validation.py` behavior).

### 3.4 Evaluation semantics (normative)

The evaluator is a pure recursive function; these rules are the contract its tests pin down.
"No match" below means the condition evaluates false *before* `negate` is applied.

| comparator | value shape | attribute missing | present, scalar | present, multi-valued |
|---|---|---|---|---|
| `eq` | scalar | no match | `==` | any element `==` |
| `neq` | scalar | no match | `!=` | **no** element `==` |
| `in` | non-empty list | no match | value ∈ list | any element ∈ list |
| `exists` | none (error if given) | no match | match | match |
| `absent` | none (error if given) | match | no match | no match |
| `lt/lte/gt/gte` | scalar, numeric/date | no match | typed compare | any element satisfies |

- **Missing attributes match only `absent`** (carried over verbatim from the D15 rule). Note
  `neq` on a missing attribute is *no match* — not "trivially unequal".
- **`negate` is the strict logical complement** of the condition's result after the table
  above — so `eq` + `negate` on a *missing* attribute matches. This is deliberate ("exclude
  everything marked X" should also exclude nothing-marked... is wrong; it should *include*
  unmarked items, which is what strict complement does). The GUI's plain-language summary
  must render this correctly ("is not X, or has no value").
- **Group semantics**: `and` over zero children is match-all; `or` over zero children is
  match-nothing. To keep authors out of that trap, an **empty root group is allowed**
  (match-all, today's default) and an **empty non-root group is a save-time validation
  error**. Group `negate` complements the group result. Evaluation may short-circuit
  (evaluation is pure, so this is unobservable).
- **Type discipline, no coercion**: comparator/type mismatches (e.g. `lt` on a string
  attribute, `in` with a scalar value, list literal where a scalar is required) are
  save-time validation errors against the effective schema. Dates are compared as dates
  (ISO-8601 in serialized form), numbers as numbers. Nothing is coerced at evaluation time.
- **`ValueRef` resolution**: `attribute_of_self` / `attribute_of_endpoint` resolve at
  evaluation time; if the referenced attribute is missing on the referent, the condition is
  *no match* (then `negate` applies as usual). `attribute_of_endpoint` outside a connection
  condition is a save-time error. Type compatibility between the two attribute paths is
  checked at save time against the effective schema.
- **Schema drift at evaluation time**: a saved definition can outlive a schema (profile
  removed, attribute renamed). An attribute path that validated at save time but is unknown
  at evaluation time behaves as *missing* (no match) **and** contributes a warning to the
  execution result / projection (§6, §7.1) — degraded loudly, never silently.
- **`IncidentConnectionCondition`**: matches when at least one incident connection satisfies
  (connection matches `connection_criteria`, match-all when `None`) ∧ (direction) ∧ (other
  endpoint matches `endpoint_criteria`, match-all when `None`). Within an incident node's
  `connection_criteria`, `ValueRef` referents are relative to the traversed connection:
  `attribute_of_self` reads the connection's own attributes, `attribute_of_endpoint`
  (source/target) reads that connection's endpoint entities. Connections whose other
  endpoint cannot be resolved (dangling reference) never match. `negate` = strict
  complement ("has no such connection").
- **Symmetric-type direction normalization**: when the incident connection's actual type is
  symmetric (`ConnectionTypeInfo.symmetric`), the direction test always passes regardless of
  the condition's `direction` — source/target order is authoring order, not semantics, for
  those types. Directed types honor `direction` literally; evaluation is always correct
  because normalization is per-connection by actual type. The save-time warning is
  best-effort static analysis on top: it fires when `direction != "either"` and a
  conjunctive top-level `type` condition in `connection_criteria` restricts matching to
  only symmetric types (the direction can then never discriminate). It never errors — a
  criteria tree admitting both symmetric and directed types is legitimate.
- **Determinism**: given the same model state, evaluation is deterministic; result sets are
  ordered by stable item-id sort (§7.1).

## 4. Query top level (replaces `ExecutableViewpointQueryV1`)

```python
@dataclass(frozen=True)
class ExecutableViewpointQuery:
    query_schema: int = 1                     # pre-release current grammar; no compatibility path
    entity_criteria: EntityCriteriaGroup = EntityCriteriaGroup()
    include_connected: tuple["NeighborInclusion", ...] = ()   # additive neighbor terms, §4.1
    connections: ConnectionSelection = ConnectionSelection()
    repo_scope: RepoScope = "both"             # unchanged
```

One query selects one **included entity population** — the primary `entity_criteria`
matches plus any `include_connected` neighbors (§4.1) — and its constrained connections.
Representation-specific projection (columns for a table, axes for a matrix) lives in
`PresentationSpec` (§5) — with one carefully bounded exception: matrix axis criteria (§5.4)
may *narrow* the included population per axis, never widen it, so the query remains the
authoritative superset of everything any representation can show.

### 4.1 Neighbor inclusion (additive population terms)

```python
@dataclass(frozen=True)
class NeighborInclusion:
    """Include entities matching ``neighbor_criteria`` that are connected — by a connection
    matching ``connection_criteria``, in ``direction`` relative to the anchor — to at least
    one entity of the PRIMARY result set (``entity_criteria``)."""
    connection_criteria: "ConnectionCriteriaGroup | None" = None  # None = any connection
    direction: Literal["outgoing", "incoming", "either"] = "either"  # relative to the anchor
    neighbor_criteria: "EntityCriteriaGroup | None" = None           # None = any entity
```

This is the complement of `IncidentConnectionCondition`, and the two are deliberately not
one mechanism: the incident condition is a **filter** (narrows which entities match), a
neighbor inclusion **widens** the population — "and also include all entities (matching X)
connected by connections (matching Y) to our primarily selected entities". The thing a
criteria tree cannot express is the anchor: a reference to *the query's own primary result
set*. Without this term the pattern requires OR-ing the primary criteria with a duplicate of
themselves inside an `endpoint_criteria` sub-tree — two copies of the primary selection that
silently diverge on edit, plus burned depth levels. The first-class term removes both
hazards and is the declarative successor of the withdrawn `ExpansionRule` (no strategies, no
`execution_anchor` — criteria only).

Semantics:

- A neighbor is included iff it matches `neighbor_criteria` and at least one connection
  matching `connection_criteria` links it to a primary entity, with `direction` evaluated
  *from the anchor's perspective* (`outgoing` = anchor→neighbor). Symmetric-type direction
  normalization (§3.4) applies identically.
- **Anchors are always the primary set.** Inclusions never chain off other inclusions'
  results — one evaluation pass, deterministic. Multi-hop/transitive reach stays deferred
  with the rest of the graph-query territory (Q6).
- **Membership is tracked, not blended**: every included entity carries
  `membership: primary | expanded` (an entity satisfying both is `primary`; an entity
  matched by several inclusion terms appears once). Exposed in the projection (§6) and
  per-item summary (§7.1) so surfaces can render neighbors as context rather than as
  first-class selection. Membership is deliberately **not** criteria-addressable (no
  reserved `membership` path): criteria are pure functions of an entity and the model,
  while membership is a property of *this query's result* — making it matchable would let
  style rules depend on evaluation order and would blur filter semantics. Rendering
  expanded members distinctly is therefore a per-representation `display_options` choice
  (e.g. `expanded_member_treatment: normal | muted`), while *conditional* styling by
  relationship remains the job of relational predicates in style-rule criteria (§5.2) —
  two different asks, two honest mechanisms.
- The structural invariant (§3.1) and matrix bridging (§5.4) operate on the combined
  included set; `connections.criteria` narrows within it as usual — the connection that
  *justified* a neighbor's inclusion is not automatically displayed if it fails the
  connection selection (selection of entities and display of connections stay independent
  judgments).
- The depth cap (§3.2) applies to each inclusion's two criteria trees independently, same
  setting, same save-time-only enforcement.

## 5. Presentation redesign

### 5.1 Representations

```python
Representation = Literal["exploration", "table", "matrix", "diagram"]

REPRESENTATION_CAPABILITIES: Mapping[Representation, frozenset[str]] = {
    "exploration": frozenset({"node_shape", "node_icon", "node_color", "edge_color",
                              "edge_emphasis", "cluster_grouping"}),
    "table":       frozenset({"columns", "badges", "sort", "row_grouping"}),
    "matrix":      frozenset({"row_by", "column_by", "cell_emphasis"}),
    "diagram":     frozenset({"node_color", "edge_color", "edge_emphasis",
                              "cluster_grouping"}),
}
```

**`diagram` is new**: an *ad-hoc* ArchiMate-notation rendering of the query result — same
rendering engine as a real diagram (fixed shape/notation per type, so `node_shape`/`node_icon`
are not overridable capabilities here, unlike `exploration`), but never persisted as a `.puml`
artifact and needs no `ViewpointApplication`. `node_color` stays overridable because that is
exactly BiZZdesign's "color view filter" pattern: a highlight overlay on top of fixed notation,
not a notation change.

**Edges are first-class styling targets**: `edge_color` and `edge_emphasis` (an opaque token
a surface resolves to e.g. thickness/highlight) mirror BiZZdesign's "relation color" filter
type, already noted in the research (§1.1). A `StyleRule` (§5.2) targets nodes or edges
according to its capability prefix — `node_*`/`cluster_*`/table capabilities take
`EntityCriteriaGroup` match criteria, `edge_*` takes `ConnectionCriteriaGroup`; a mismatch
is a save-time validation error. Selection/visibility is **never** a style capability:
which items appear (and whether excluded items ghost or hide) is the projection's job
(§6), keeping BiZZdesign's separation — style filters decorate content already scoped in.

**What is deliberately not a capability**: legends are *derived* — every surface renders its
legend mechanically from `styling_rules` + `range_bands` + `default_style`, nothing to
author. Tooltips/hovers show the fixed per-item summary (§7.1) — descriptive content, not
configurable presentation, consistent with the locked MCP boundary (§2). A matrix cell's
summary is likewise fixed: the count of selected connections between the row and column
entity plus their type slugs (`cell_emphasis` styles it; it does not define its content).
Configurable node/edge *label* rules (BiZZdesign's "label filter") stay deferred with the
other Q6 items — noted so the omission is visibly a decision, not an oversight.

**Table vs. matrix**: both project the queried population; `table` is a flat list, one row
per matched entity, with `columns` (§5.3) projecting attributes across. `matrix` is a
relationship grid — its axis model is specified in §5.4.

### 5.2 Style rules (replaces the discrete-only `StyleRule`)

```python
StyleConditionMode = Literal["match", "range"]

@dataclass(frozen=True)
class RangeBand:
    minimum: float | None     # None = unbounded below; inclusive
    maximum: float | None     # None = unbounded above; exclusive (half-open bands)
    value: str                # opaque style token, resolved only by surface adapters

@dataclass(frozen=True)
class StyleRule:
    capability: str
    applies_to: frozenset[str] = frozenset()   # entity/connection type or specialization slugs
                                                # this rule is scoped to; empty = applies to any
                                                # type the representation renders
    mode: StyleConditionMode = "match"
    match_criteria: EntityCriteriaGroup | ConnectionCriteriaGroup | None = None  # mode=="match"
    range_attribute: str | None = None         # mode=="range": numeric/date attribute path
    range_bands: tuple[RangeBand, ...] = ()    # mode=="range": explicit, non-overlapping bands
    value: str | None = None                   # mode=="match": token applied when matched

@dataclass(frozen=True)
class PresentationSpec:
    representation: Representation
    display_options: Mapping[str, Any] = field(default_factory=dict)
    columns: tuple["ColumnSpec", ...] | None = None      # table only, §5.3
    row_by: str | None = None                            # matrix only, §5.4
    column_by: str | None = None                         # matrix only, §5.4
    row_criteria: "EntityCriteriaGroup | None" = None    # matrix only, §5.4
    column_criteria: "EntityCriteriaGroup | None" = None # matrix only, §5.4
    group_by: str | None = None                          # exploration/table row_grouping
    styling_rules: tuple[StyleRule, ...] = ()             # ordered, first-match-wins
    default_style: Mapping[str, str] = field(default_factory=dict)  # capability -> fallback token
```

`styling_rules` is evaluated in declaration order, first match wins per capability, falling
back to `default_style` — the Airtable/Grafana pattern from the research. `mode="match"` reuses
the **identical** `EntityCriteriaGroup`/`ConnectionCriteriaGroup` types from §3 (not a parallel
structure) so a definition author (or a GUI widget) works with one condition-building concept
for both filtering and styling, the UX research's strongest cross-cutting finding. Because
match criteria are full §3 trees, **relational styling is directly expressible with no
separate mechanism**: a node rule whose criteria contain an `IncidentConnectionCondition`
means "display entity X this way when X has a connection matching Y to an entity matching Z"
— same depth cap, same evaluator, same GUI builder widget as query filtering.
`mode="range"` is the separate, simple threshold/gradient case: explicit half-open
`[minimum, maximum)` bands rather than an ordered "last threshold met wins" list, which avoids
the ambiguity risk the Grafana pattern carries and is easy to validate (bands must be
non-overlapping — a save-time error) and to render in a GUI legend. An item whose
`range_attribute` is missing or falls outside every band takes the `default_style` fallback
for that capability.

### 5.3 Column selection (table)

```python
AttributeRef = str   # dotted attribute path (§3.3) — the only supported column source today

@dataclass(frozen=True)
class ColumnSpec:
    label: str
    source: AttributeRef
```

**Non-foreclosure note**: `source` is documented as an open union with exactly one member
implemented now. A future `DerivedMetricRef` (a named, type-specific computed value — e.g.,
"count of matching incident connections", an aggregate) can be added to that union later
without a breaking change to `ColumnSpec` or to any already-authored definition. No
speculative code for this is added now — this note exists solely so the door is not
architecturally closed.

### 5.4 Matrix axes

A matrix has two axis modes, mutually exclusive (mixing them is a save-time error):

- **Grouped axes** (`row_by`/`column_by`): one population, split into two axes by group
  keys (type, specialization, group, or a discrete profile attribute) — what the existing
  matrix builder does today. Cell populated when a selected connection exists between the
  row entity and the column entity.
- **Criteria axes** (`row_criteria`/`column_criteria`, both required together): each axis is
  its own entity population, evaluated as `entity_criteria ∧ row_criteria` and
  `entity_criteria ∧ column_criteria` respectively. Disjoint-population matrices
  (requirements × components, stakeholders × concerns, capabilities × applications) are the
  motivating case: leave the base `entity_criteria` at match-all and put the full selection
  in each axis. Because axis criteria can only *narrow* the base query, the query stays the
  authoritative superset (§4) and selection/presentation orthogonality survives: the axes
  are a representation-local refinement, meaningless outside the matrix, which is why they
  live in `PresentationSpec` and not in the query.

**Bridging invariant** (the criteria-axes form of §3.1's structural invariant): a connection
appears in a cell iff one endpoint is in the row set and the other is in the column set
(either orientation), and it passes `connections.criteria`. Save-time validation warns when
`connections.enabled` is false for a matrix (a matrix of guaranteed-empty cells is almost
certainly an authoring mistake). Entities matching neither axis simply don't appear —
they're still in the query result (§7.1 reports the base population), just not on this
representation.

## 6. The viewpoint projection (unifying contract)

New module: `src/domain/viewpoint_projection.py` (deliberately parallel to the existing
`src/domain/view_projection.py` opacity contract — same philosophy: opaque display tokens,
generic code never interprets them; different concern: derivation preview vs. viewpoint
evaluation). This is the contract both halves of the feature consume, so the GUI's ghosting,
the verifier's warnings, and MCP/REST execution results can never disagree — they are
different renderings of one projection.

```python
ProjectionTarget = Literal["repository", "diagram", "matrix"]
OcclusionState = Literal["visible", "ghosted"]
ExclusionReason = Literal[
    "out_of_scope",        # fails effective ConceptScope (diagram-type scope ∩ viewpoint scope)
    "criteria_mismatch",   # fails the definition's entity/connection criteria
    "endpoint_excluded",   # connection whose source/target is itself excluded
]

@dataclass(frozen=True)
class ProjectedOccurrence:
    item_id: str
    item_kind: Literal["entity", "connection"]
    state: OcclusionState
    membership: Literal["primary", "expanded"] = "primary"  # §4.1; connections always primary
    reasons: tuple[ExclusionReason, ...] = ()   # empty iff the item fully matches
    style: Mapping[str, str] = field(default_factory=dict)  # capability -> opaque token;
                                                            # always empty when reasons is
                                                            # non-empty (§6.2)

@dataclass(frozen=True)
class ViewpointProjection:
    target: ProjectionTarget
    items: tuple[ProjectedOccurrence, ...]
    stale_pin: bool = False          # artifact-local only: pinned_version < current
    warnings: tuple[str, ...] = ()   # schema drift, capability drift, unresolved refs
```

### 6.1 Repository context (ephemeral generated views)

Population = all entities/connections admitted by `repo_scope`. The projection contains
**only matched items**, all `visible`, with `style` computed from `styling_rules`. Excluded
items are simply absent (reporting every non-match in a large repository would be absurd).
This feeds §7.1's execution result and the four representations.

### 6.2 Artifact-local context (applying a viewpoint to an existing diagram/matrix)

Population = the artifact's placed occurrences (`entity-ids-used`/`connection-ids-used`,
resolved exactly as the verifier already does). **Every occurrence appears** in the
projection with a state:

- Fully matching (in effective scope, satisfies criteria): `visible`, styled.
- Out of effective scope: reason `out_of_scope` — the existing WU-E4 behavior, now expressed
  through this contract.
- In scope but failing the definition's query criteria (only when the definition has a
  query): reason `criteria_mismatch`.
- A connection either of whose endpoints is excluded: reason `endpoint_excluded` (in
  addition to its own reasons, if any).

The effective enforcement setting maps reasons to state: `ghost` → non-matching occurrences
are `ghosted`; `warn` → everything stays `visible` but reasons are populated (surfaces may
badge them); `off` → identity projection *for occlusion* (all visible, no reasons emitted).

**Occlusion dominates styling, sharply**: style tokens are computed **only for fully
matching occurrences** (`reasons` empty) — an excluded occurrence carries an empty `style`
map in every enforcement mode, including `warn` where it stays visible. Style rules express
the viewpoint's semantics, which an excluded item by definition does not satisfy; a ghosted
element wearing a highlight color would make the visual language incoherent. At render
time, ghost/hide treatment visually dominates everything — a surface must never let a style
token override or soften the exclusion rendering. (What *does* apply in all three
enforcement modes is the styling of matching occurrences — enforcement governs occlusion of
non-matches, never whether matches are styled.) Surfaces wanting diagnostic decoration of
excluded items (e.g. a "why excluded" badge) key it off `reasons`, which is exactly what
that field is for — not off style rules.

Per-surface, the GUI offers a "hide instead of ghost" toggle that renders `ghosted` items as
hidden; that is a rendering choice over the same projection, not a contract state, which is
how the locked three-value enforcement vocabulary (§2) supports the hide use case.

Unresolved references degrade loudly, never silently: unknown viewpoint slug → identity
projection + warning (the verifier's E180 remains the error surface); pinned version older
than current → projection is computed against the **current** definition (historical
versions are not retained — pin + drift warning is the mechanism, per WU-E3) with
`stale_pin=True`; attribute paths lost to schema drift behave per §3.4.

### 6.3 Verifier integration

`_verifier_rules_viewpoint.py` already states the governing principle: a CI/`arch-repo
verify` run should see the same signal the GUI ghosts. With criteria in the model, that
principle extends: the verifier obtains the artifact-local projection from the same
application service the GUI uses (never re-implementing evaluation) and emits:

- **E180 / W180 / W181 unchanged** (unknown slug; stale pin; out-of-scope placement — W181
  stays purely scope-based and cheap).
- **W182 (new): criteria-mismatch placement** — one warning per occurrence whose reasons
  include `criteria_mismatch`, emitted only when the definition has a query and effective
  enforcement is not `off`. Distinct code because it is *data-dependent* (an attribute edit
  elsewhere can newly trigger it) — filterable separately from the structural W181, exactly
  why the codes are split.

## 7. Application layer

- **`EvaluateViewpoint` is a new use case** (`src/application/viewpoints/…` — there is no
  existing evaluation code; D15 execution was never implemented, only the WU-E1–E4
  scope/catalog machinery). It orchestrates: resolve definition (or accept an ad-hoc query),
  evaluate criteria trees against the read ports, assemble the `ViewpointProjection` (§6)
  for the requested context, and — for repository context — wrap it in the execution result
  (§7.1). The evaluator itself is a pure domain function of (criteria tree, entity/connection
  read access, effective schema) — no I/O beyond what the read ports provide.
- `IncidentConnectionCondition` evaluation needs adjacency (an entity's incident connections)
  from the same read ports already used for connection resolution — no new port method should
  be needed if `get_connection`/entity-neighbor lookups already exist (verify against
  `ArtifactRegistry` from WU-E4); if a genuine gap exists, add the delegation at the correct
  layer per this project's standing rule — never route around it.
- `ValueRef` resolution (`attribute_of_self`, `attribute_of_endpoint`) is evaluated inline
  during criteria evaluation, not pre-resolved into literals beforehand — keeps the evaluator a
  single recursive function over the tree.
- Attribute-path validation (unknown attribute, comparator/type mismatch, empty non-root
  groups, depth cap, style-rule capability/criteria-kind agreement, range-band overlap,
  matrix axis-mode exclusivity) happens at definition-save time in `viewpoint_validation.py`,
  exactly as today, extended to walk the new tree shape (recursive, not flat iteration).
- Nothing about the hexagonal boundary changes: domain owns the criteria/projection/
  presentation value objects and the pure evaluator function; application owns
  `EvaluateViewpoint` orchestration over ports; infrastructure owns the REST endpoint, GUI
  adapters, verifier wiring (§6.3), and the two MCP tools (§9) — all call the same use case,
  none re-implement evaluation.

### 7.1 Execution result contract (updated from D15 for schema v2)

`ViewpointExecutionResult` (application DTO — ephemeral, never persisted):

- **Identity & provenance**: viewpoint slug + definition version (absent for ad-hoc
  queries), `query_schema`, `repo_scope`, `executed_at` (via `src/domain/clock.py`),
  model/index revision where the index provides one — for later drift diagnosis.
- **Content**: **sorted** (stable item-id order) entity ids and connection ids, plus the
  fixed, non-customizable per-item summary — entity: id, name, type, specialization slugs,
  group, membership (`primary|expanded`, §4.1); connection: id, type, source id, target id.
  This is the descriptive content of §2's MCP boundary: always present, unstyled, for every
  consumer including agents.
- **Counts & truncation**: **the limit is denominated in entities** — connections are a
  derived set (re-filtered to the retained entities, §3.1), never independently truncated,
  so limits have one unambiguous meaning across REST and MCP. The result always carries
  four counts: `total_entity_count`, `returned_entity_count`, `total_connection_count`,
  `returned_connection_count` (totals are pre-truncation; `truncated` is true iff returned
  < total entities, with the applied entity limit echoed). Entity truncation applies after
  stable ordering **with primary members retained before expanded members** — the primary
  selection is authoritative, so context neighbors are dropped first (deterministically, in
  reverse stable order). A dedicated connection cap is deliberately absent: the connection
  set is bounded by the retained entities, and one could be added as a settings-only change
  later without touching the schema.
- **Matrix axis metadata**: when the executed definition's presentation is a criteria-axes
  matrix (§5.4), the result additionally carries `matrix_axes: {row_entity_ids,
  column_entity_ids}` (sorted, subsets of the returned entities). This is selection-derived,
  descriptive content — which entities sit on which axis — not styling, so the D15 boundary
  (§2) is intact; without it, a consumer could not explain why an included entity (in the
  base population but on neither axis) is absent from the rendered grid. Unrendered
  entities are exactly the returned set minus the union of the two axis lists — derivable,
  so not duplicated into the DTO (tests assert the complement property instead).
- **Warnings**: schema drift (§3.4), capability drift (a saved definition using
  capabilities unknown to the current registry — save-time rejection covers the current
  registry; runtime warns for legacy definitions and app up/downgrade, unchanged from D15's
  precise drift rule), stale pin (when executed via an application).
- **Bounds**: execution enforces a max result size and a timeout with clean cancellation —
  on timeout the result is a typed error, never a partial result silently presented as
  complete. All bounds are system-level settings in `config/settings.yaml` (accessors in
  `src/config/settings.py`), tunable without a schema change:

  ```yaml
  viewpoints:
    execution_max_entities: 500              # hard cap, all transports; the GUI/REST default
    execution_default_entity_limit_mcp: 200  # MCP default when no limit argument is given
    execution_timeout_seconds: 10
  ```

  Both limits count **entities** (see Counts & truncation above — connections are derived,
  never independently capped). The MCP `execute` action takes an optional `limit` argument,
  clamped to the hard cap; its smaller default protects agent context windows (per the
  standing MCP-surface guidance), while GUI/REST default to the cap itself — sized so a
  realistic repository (the dogfood repo holds ~277 entities) does not truncate a broad
  query, without permitting unbounded payloads. The old max-expansion-hops limit is gone
  with `ExpansionRule`: traversal depth is now statically bounded at save time (§3.2).
- Duration (ms), for the per-run structured log line the parent plan's observability
  section requires.

### 7.2 Validation modes and the issue model

`validate_viewpoint_definition` currently returns plain strings; this plan's requirements
(severities, stable codes, paths agents can converge on — §9.1) need a structured issue,
and the plan's own rules need **modes**, because "validated at catalog load" and "the depth
cap is save-time only" would otherwise contradict each other:

```python
@dataclass(frozen=True)
class ViewpointValidationIssue:
    severity: Literal["error", "warning"]
    code: str            # stable kebab-case id, e.g. "unknown-attribute", "depth-cap-exceeded"
    path: str            # JSON-pointer-style path into the definition (§9.1)
    message: str
    expected: str | None = None
    found: str | None = None
```

Deliberately distinct from the artifact verifier's `Issue` (E180/W180/W181/W182): the
verifier judges *artifacts against the model*; this type judges *definitions against the
catalogs* — different lifecycles, different consumers, no shared code space.

Three validation modes, one validator with a mode parameter (not three validators):

- **`load`** (catalog load, incl. hand-edited YAML): structural parse failures reject the
  definition (a malformed tree cannot be constructed); registry-correctness findings
  (unknown attribute paths, type slugs, capabilities) are **catalog warnings, not
  rejections** — the definition loads and evaluation degrades loudly per §3.4's drift
  semantics. No authoring-ergonomics checks, no lifecycle checks. This is what keeps §3.2's
  promise that an over-cap or drifted definition still loads, evaluates, and promotes.
- **`save`** (GUI builder + MCP `create`/`edit` payload validation): everything `load`
  warns about becomes an **error**, plus the authoring-ergonomics checks — depth cap, empty
  non-root groups, range-band overlap, axis-mode exclusivity, capability/criteria-kind
  agreement — and the advisory warnings (symmetric-direction, matrix-without-connections).
- **`persist_edit`** (the write path only): `save` plus the lifecycle rules of §10 against
  prior state — semantic-edit version bump, slug collision, delete-while-referenced.

Consequence, stated plainly: **direct YAML edits get `load` guarantees only** — they cannot
be version-bump-enforced or reference-checked (there is no "prior state" at load time).
That is an accepted property of the escape hatch, not a gap: the governed surfaces are the
GUI and MCP tools, and W180 staleness still catches un-bumped semantic drift downstream.

## 8. Purpose / Content / Stakeholders — role clarified, cardinality aligned

These four fields (`purpose`, `content`, `stakeholders`, `concerns`) are ArchiMate's own
viewpoint metadata (the mandatory Chapter-13 dimensions plus the informative stakeholder/
concern fields). Their *relationship* to the query/presentation engine is: **purely
descriptive** — shown in the GUI viewpoint card, in `artifact_authoring_guidance` output,
and in MCP `list` results, to help a human or agent choose the right definition. They never
drive query construction, presentation defaults, or evaluation in any way.

One shape change, driven by the C19C view-exchange schema (verified against
`spec/c19c-view-exchange_compressed.pdf`, Appendix D): the exchange format's `viewpointPurpose` and
`viewpointContent` are **lists** of their enums — a viewpoint legitimately serves several
purposes (the standard's own Layered viewpoint is the classic example). Our single-valued
`purpose`/`content` would make round-tripped custom viewpoints silently lossy. So:

```python
purpose: tuple[Purpose, ...] = ("informing",)
content: tuple[Content, ...] = ("overview",)
```

The YAML parser accepts a **singular string as shorthand** for a one-element tuple, so the
shipped starter library (all singular today) and every existing repo file stay valid with
no migration; the serializer writes the singular form back when the tuple has one element.
Evaluation is unaffected — the fields remain purely descriptive.

## 9. MCP tool surface (replaces the single combined `artifact_viewpoint` tool)

Two tools, one per existing server, matching the read/write split already established for
every other capability in this codebase:

- **`arch-repo-write` — `artifact_viewpoint`**: authoring only. Actions `create` / `edit` /
  `delete`, engagement-repo scope (enterprise/module-shipped definitions stay read-only,
  mirroring the specialization-library pattern). Runs the same validate/persist path as the
  GUI builder and enforces the lifecycle rules in §10.
- **`arch-repo-read` — `artifact_query_viewpoint`**: read-only. Actions `list` (browse the
  effective merged catalog: slug, version, name, purpose/content/stakeholders/concerns, scope
  summary) and `execute` (run a definition's query — or an ad-hoc query supplied inline — against
  the live model). `execute` returns the §7.1 result: counts, warnings, truncation,
  version-drift info, sorted ids, fixed per-item summaries — no representation/styling/column
  parameters, unchanged from the already-locked D15 boundary decision (§2). It takes an
  optional `limit` argument counting entities (default
  `execution_default_entity_limit_mcp`, clamped to `execution_max_entities`, §7.1) so an
  agent can page up deliberately rather than receive the full population by accident.

### 9.1 Intelligibility parity (MCP and GUI are peer surfaces, not GUI-first)

Every §3–§5 construct must be *authorable and understandable* by an agent over MCP with the
same fidelity the GUI gives a human. Three mechanisms, all shared rather than duplicated:

- **One plain-language summary renderer.** The live summary the UX research demands for the
  GUI builder ("Application Components that serve at least one Business Process, and all
  Business Processes they serve") is a pure domain function over the query (criteria trees +
  inclusions + connection selection), not a frontend feature. The GUI live-preview calls it
  via REST; `artifact_query_viewpoint list` returns it per definition; `execute` echoes it
  for ad-hoc queries. An agent reading a catalog therefore sees *what a viewpoint means*,
  not just its YAML. One renderer, three surfaces — they can never disagree, and its
  correctness (incl. the §3.4 `negate` phrasing) is tested once.
- **Schema discoverability via the existing help surface.** The canonical serialized shape
  (Appendix A), the comparator/semantics table, reserved paths, and worked examples are
  exposed as an `artifact_help` topic — tool *descriptions* stay short per the standing
  MCP-surface guidance; depth lives one deliberate hop away where an agent can fetch it on
  demand.
- **Validation errors that agents can converge on.** Every save-time error/warning carries a
  path into the definition (`query.entity_criteria.children[2].endpoint_criteria`,
  JSON-pointer-style), what was found, and what was expected. The GUI maps the same paths
  onto builder widgets; an agent iterates create → error → fix without guessing. One
  validator, one error contract, two renderings.

## 10. Lifecycle & governance

Consolidated here so the MCP tools, the GUI builder, and promotion cannot diverge; items
marked (D14) or (WU-E3/E4) restate locked decisions rather than reopen them.

- **Version bumps**: an edit changing semantic content (`scope`, `query`, `presentation`,
  `representation_types`) requires a version bump — enforced in the shared validate/persist
  path, not left to author discipline. Edits touching only descriptive fields (`name`,
  `description`, `rationale`, `purpose`, `content`, `stakeholders`, `concerns`) do not bump.
  The bump is what makes W180 staleness meaningful (WU-E3).
- **No version history**: only the current version of a definition is stored. An application
  pinned to an older version projects against the current definition with an explicit stale
  warning (§6.2) — drift is loud, never silent, and never silently reinterpreted.
- **Slug uniqueness**: creation validates against the *effective merged catalog*
  (module ⊕ enterprise ⊕ engagement) — `ViewpointCatalog` already raises on duplicates;
  create/edit surfaces the check as a validation error before persist.
- **Delete**: blocked while any diagram/matrix in the workspace references the slug in a
  `ViewpointApplication`; the error lists the referencing artifacts. Detach the applications
  first — no force flag, so a repository can never be driven into E180 by its own tooling.
- **Authoring scope**: module-shipped and enterprise definitions are read-only in an
  engagement context; engagement repos author their own definitions in
  `.arch-repo/viewpoints.yaml` (two-tier model, WU-E2).
- **Promotion (D14)**: unchanged — promoting an artifact whose `ViewpointApplication`
  references an engagement-only definition requires the definition (at the exact pinned
  version) to be promoted with it; promoted applications are re-pinned to the enterprise
  version as a reviewed promotion step.
- **One validator, three modes** (§7.2): GUI builder and `artifact_viewpoint` run
  `persist_edit` mode (all checks incl. the lifecycle rules above); catalog load — the only
  validation direct YAML edits receive — runs `load` mode (structural rejection, registry
  findings as warnings, no ergonomics/lifecycle).

## 11. GUI implications (pointer only)

The WU-E5-UX wireframe spike predates this redesign and needs a full redo, not a patch — most
visibly the flat "Entity filters" section and the single "include connections" dropdown. The
redo should produce, at minimum: one reusable criteria-tree builder component (used for query
filtering, neighbor-inclusion terms, `mode="match"` style rules, and matrix axis criteria,
per §4.1/§5.2/§5.4) rather than separate widgets — with anchor-relative direction worded
carefully in the inclusion UI ("connections *from* the selected entities"); the live plain-language summary the UX research converged on (including
correct rendering of `negate` per §3.4); the derived legend (§5.1); and the ghost/hide toggle
over the artifact-local projection (§6.2). This is a separate follow-up deliverable; this
document defines the model the redone wireframes must be built against, not the wireframes
themselves.

## 12. Documentation plan (Diátaxis)

Viewpoints get their own page(s) rather than a subsection of an existing page, matching how
`docs/03-modeling/` already splits `diagramming.md` / `views-and-exploration.md` /
`projects-and-grouping.md` as flat sibling pages under one index:

- **`docs/03-modeling/viewpoints.md`** (new) — explanation + how-to, following the house style
  of its siblings: what a viewpoint is (ArchiMate Chapter 13 grounding), definitions vs.
  applications vs. ad-hoc execution, applying a viewpoint to an existing diagram
  (ghost/hide/highlight) vs. executing one, the criteria model with worked examples (a simple
  type-only filter, a nested AND/OR example, an incident-connection example), the four
  representations, styling (match vs. range mode), and where to author one (GUI builder, MCP
  `artifact_viewpoint`, or a repo YAML file) — concise, complete, no plan/decision-ID references
  per this project's standing rule.
- **`docs/reference/viewpoints-schema.md`** (new) — reference material: the full YAML shape
  (Appendix A), the comparator/semantics table (§3.4), the reserved paths (§3.3), the
  `ValueRef` kinds, the two MCP tools' parameters and return shapes, the
  `REPRESENTATION_CAPABILITIES` table, verifier codes E180/W180/W181/W182. Mirrors the
  existing flat `docs/reference/*.md` pattern (`cli-and-backend.md`, `docker-compose.md`,
  `git-sync-promotion.md`).
- **`docs/03-modeling/index.md`** — add `viewpoints.md` to the "On this page set" list.
- **`docs/05-extensibility/ontology-modules.md`** and/or **`schemata-and-profiles.md`** — a
  short cross-reference where the two-tier module/`.arch-repo` catalog pattern is already
  documented, pointing at the new viewpoints page rather than re-explaining the pattern.
- **`README.md`** — add viewpoints to wherever the capability list/feature overview currently
  lives, at the same weight as other modeling capabilities already listed there.

No new top-level docs section is needed — the Diátaxis split is achieved across the existing
`03-modeling` (explanation/how-to) and `reference` (reference) directories.

**Tutorial: deferred, not dropped.** The feature's complexity (four representations, two
styling modes, a relational predicate) does warrant a "first viewpoint" tutorial, but
tutorials serve newcomers, who will arrive via the GUI — and the GUI builder is itself a
follow-up deliverable (§11). Writing the tutorial against the YAML/MCP surface now would
target the wrong audience and churn as soon as the builder lands. The tutorial is therefore
a fully specified deferred work unit (§14), gated on the redone GUI builder shipping.

## 13. Migration / compatibility note

No committed data uses the old `ExecutableViewpointQueryV1`/`PresentationSpec` shape (confirmed
by inspection of `src/ontologies/archimate_4/viewpoints.yaml` — only scope-level fields are
populated). The already-implemented parsing/validation/serialization code for the old shape
(`viewpoint_parsing.py`, `viewpoint_validation.py`, `viewpoint_serialization.py`) and its tests
will need to be reworked to the new tree shape wholesale; this is a rework of unshipped
plumbing, not a data migration, and carries no rollback/versioning concern beyond the normal
gates (tests/ruff/zuban) already in force for every change in this repository. Round-trip
discipline is normative: parse(serialize(x)) == x for every definition, against the canonical
serialized form in Appendix A — the parser and serializer implement that appendix; they do not
define the format by accident.

## 14. Work breakdown (reconciled into `TASKS-archimate-4-compliance.md`, 2026-07-10)

Reconciled: the ledger's Phase E carries these as WU-E11–E17 (new foundation chain +
deferred tutorial) plus in-place reworks of WU-E5-UX/E5a/E5b/E5c/E6a/E7/E7a/E8/E9; the
ledger is authoritative for numbering, dependencies, and acceptance wording. The list
below remains the design-side statement of the cut:

Units are cut along stable contracts so each is independently implementable and reviewable
(each lands with its Appendix-C test cluster); the `ConceptScope`/definition/application
portions of WU-E3 are untouched throughout:

- domain value objects: criteria trees (§3), query top level + neighbor inclusion (§4),
  presentation (§5), projection contract (§6) — pure shapes and their invariants, no
  behavior;
- parser + serializer to the Appendix-A canonical form, incl. the executable-fixture
  round-trip tests (shipped catalog for slugs, Appendix-A fixture profiles installed into
  the test repo's `.arch-repo/schemata/` for attributes);
- `ViewpointValidationIssue` + the three-mode validator (§7.2): depth cap, ergonomics
  checks, path/expected/found contract, load-vs-save severity split;
- the pure criteria evaluator (§3.4 semantics, inclusions, connection selection);
- the projection service (§6: both contexts, enforcement mapping, occlusion-dominates-
  styling) + the plain-language summary renderer (§9.1) — one work unit, since the renderer
  is the projection's human-readable twin;
- `EvaluateViewpoint` use case + execution result DTO + REST endpoint (§7, §7.1: bounds,
  counts, matrix axis metadata, timeout);
- verifier: W182 + re-basing the existing rule onto the shared projection service (§6.3) —
  E180/W180/W181 behavior unchanged;
- MCP write tool `artifact_viewpoint` (persist_edit mode, lifecycle rules §10);
- MCP read tool `artifact_query_viewpoint` (list/execute, limit clamping, `artifact_help`
  topic §9.1);
- GUI: ghost/hide/highlight overlay on existing diagrams from the artifact-local projection
  (§6.2);
- the WU-E5-UX builder redo (§11) — last of the GUI units, consuming everything above;
- a documentation work unit (§12), feeding the parent plan's conformance documentation page
  (Appendix B);
- **deferred: the viewpoints tutorial** — a separate work unit, gated on the redone GUI
  builder (§11) shipping, specified now so it is scheduled rather than forgotten:
  - **Page**: `docs/03-modeling/viewpoints-tutorial.md`, sibling of `viewpoints.md`, linked
    from the `03-modeling` index and cross-linked both ways with the how-to page.
  - **Arc** ("define and execute your first viewpoint", worked against the dogfood
    repository's real content): create a definition in the GUI builder with a simple type
    filter → add an opt-in OR-group and a negated condition (observe the plain-language
    summary update) → add an incident-connection condition → add one match-mode and one
    range-mode style rule (observe the derived legend) → execute as table, then matrix →
    apply the definition to an existing diagram and toggle warn/ghost/hide → save, note the
    version pin on the diagram.
  - **Closing section**: the same definition authored via `artifact_viewpoint` and executed
    via `artifact_query_viewpoint`, showing YAML/MCP parity for agent-driven use.
  - **Media**: screenshots/clips generated through the scripted Playwright media pipeline
    (the repo's established docs-media convention), never hand-captured.
  - **Acceptance**: every step reproducible against the shipped GUI by following the text
    alone; media regenerated by script; no plan/decision-ID references in the page.

---

## Appendix A — Canonical serialized form (YAML)

Normative for `viewpoints.yaml` (module and `.arch-repo` tiers), the REST/MCP `create`/`edit`
payloads, and the round-trip tests. The examples are **executable fixtures**, validated in
two layers that mirror how real repositories work:

- **Type, specialization, and connection slugs** validate against the shipped `archimate_4`
  catalog (entity types are unprefixed — `application-component`, `process`, `requirement`;
  `archimate-*` names connection types; `business-process` is a shipped specialization of
  `process`).
- **Profile attributes** (`strength`, `threshold`, `risk_score`) are deliberately *not*
  shipped — per D13, attribute profiles are repo-level configuration
  (`.arch-repo/schemata/attributes.{type}.schema.json`), and the shipped module defines
  none of these. The executable tests install the three **fixture profiles** below into the
  test repository's `.arch-repo/schemata/` before running save-mode validation, exercising
  the real D13 merged-schema path rather than a shortcut. The fixture files live with the
  test suite (proposed: `tests/fixtures/viewpoints/schemata/`) and are copied verbatim:

  ```json
  // attributes.application-component.schema.json
  {"type": "object", "properties": {"risk_score": {"type": "number"}}}
  // attributes.process.schema.json
  {"type": "object", "properties": {"threshold": {"type": "number"}}}
  // attributes.archimate-serving.schema.json
  {"type": "object", "properties": {"strength": {"type": "integer"}}}
  ```

The test suite loads this appendix's definitions through the real parser and save-mode
validator with those profiles in place — an example that stops validating is a build
failure, not doc rot. Criteria nodes are discriminated by `kind`:
`condition | incident | group`. A condition's `value` is a plain scalar/list (literal
shorthand) or a mapping with `from: self | source | target` (a `ValueRef` reference —
`self` ⇒ `attribute_of_self`, `source`/`target` ⇒ `attribute_of_endpoint`).

```yaml
viewpoints:
  # 1. Simple: all application components (flat AND, one condition)
  - slug: application-components
    version: 1
    name: Application Components
    purpose: informing
    content: overview
    query:
      query_schema: 1
      entity_criteria:
        kind: group
        conjunction: and
        children:
          - kind: condition
            attribute: type
            comparator: in
            value: [application-component]

  # 2. Nested boolean + negation: active elements that are NOT deprecated,
  #    in either the application or technology domain
  - slug: active-app-tech
    version: 1
    name: Active Application & Technology
    query:
      query_schema: 1
      entity_criteria:
        kind: group
        conjunction: and
        children:
          - kind: group
            conjunction: or
            children:
              - kind: condition
                attribute: domain
                comparator: eq
                value: application
              - kind: condition
                attribute: domain
                comparator: eq
                value: technology
          - kind: condition
            attribute: status
            comparator: eq
            value: deprecated
            negate: true            # matches when status != deprecated OR status missing

  # 3. Incident predicate (criteria on BOTH legs of the hop) + neighbor inclusion +
  #    endpoint ValueRef: components with at least one strong serving connection to a
  #    business process; also include those served processes as context ("expanded"
  #    membership); display only serving connections at least as strong as the
  #    target's threshold
  - slug: components-serving-processes
    version: 2
    name: Components Serving Processes
    query:
      query_schema: 1
      entity_criteria:
        kind: group
        conjunction: and
        children:
          - kind: condition
            attribute: type
            comparator: eq
            value: application-component
          - kind: incident
            direction: outgoing
            connection_criteria:
              kind: group
              conjunction: and
              children:
                - kind: condition
                  attribute: type
                  comparator: eq
                  value: archimate-serving
                - kind: condition
                  attribute: strength
                  comparator: gte
                  value: 3
            endpoint_criteria:
              kind: group
              conjunction: and
              children:
                - kind: condition
                  attribute: type
                  comparator: eq
                  value: process
                - kind: condition
                  attribute: specialization
                  comparator: eq
                  value: business-process
      include_connected:
        - direction: outgoing        # relative to the primary (anchor) entities
          connection_criteria:
            kind: group
            conjunction: and
            children:
              - kind: condition
                attribute: type
                comparator: eq
                value: archimate-serving
          neighbor_criteria:
            kind: group
            conjunction: and
            children:
              - kind: condition
                attribute: type
                comparator: eq
                value: process
              - kind: condition
                attribute: specialization
                comparator: eq
                value: business-process
      connections:
        enabled: true
        criteria:
          kind: group
          conjunction: and
          children:
            - kind: condition
              attribute: type
              comparator: eq
              value: archimate-serving
            - kind: condition
              attribute: strength
              comparator: gte
              value: {from: target, attribute: threshold}

  # 4. Presentation: table with columns, match-mode + range-mode styling
  - slug: component-lifecycle-table
    version: 1
    name: Component Lifecycle
    query:
      query_schema: 1
      entity_criteria:
        kind: group
        conjunction: and
        children:
          - kind: condition
            attribute: type
            comparator: eq
            value: application-component
    presentation:
      representation: table
      columns:
        - {label: Name, source: name}
        - {label: Status, source: status}
        - {label: Risk, source: risk_score}
      styling_rules:
        - capability: badges
          mode: match
          match_criteria:
            kind: group
            conjunction: and
            children:
              - kind: condition
                attribute: status
                comparator: eq
                value: deprecated
          value: badge-warning
        - capability: badges
          mode: range
          range_attribute: risk_score
          range_bands:
            - {minimum: null, maximum: 4, value: badge-ok}      # [-inf, 4)
            - {minimum: 4, maximum: 7, value: badge-caution}    # [4, 7)
            - {minimum: 7, maximum: null, value: badge-danger}  # [7, inf)
      default_style:
        badges: badge-neutral

  # 5. Matrix with disjoint criteria axes (requirements x components)
  - slug: requirement-coverage
    version: 1
    name: Requirement Coverage
    query:
      query_schema: 1
      entity_criteria:
        kind: group        # match-all base: each axis carries the full selection
        conjunction: and
        children: []
      connections:
        enabled: true
        criteria:
          kind: group
          conjunction: and
          children:
            - kind: condition
              attribute: type
              comparator: eq
              value: archimate-realization
    presentation:
      representation: matrix
      row_criteria:
        kind: group
        conjunction: and
        children:
          - kind: condition
            attribute: type
            comparator: eq
            value: requirement
      column_criteria:
        kind: group
        conjunction: and
        children:
          - kind: condition
            attribute: type
            comparator: eq
            value: application-component
```

Serialization rules: field defaults are omitted on write (a minimal file stays minimal);
unknown keys are a parse error (not ignored — catches typos like `comparater`); `negate` is
written only when true; `query_schema` is always written explicitly. `parse ∘ serialize`
must be the identity on every valid definition (§13).

## Appendix B — ArchiMate 4.0 conformance mapping (viewpoint mechanism)

The parent plan owns the overall conformance documentation page; this table traces just the
viewpoint-mechanism obligations to their implementation so "supports the viewpoint mechanism"
is demonstrable, not asserted. Section numbers cite the ArchiMate 4.0 specification.

| Obligation (ArchiMate 4.0) | Implemented by | Verified by |
|---|---|---|
| Viewpoint = conventions for view creation/usage (Ch. 13) | `ViewpointDefinition` (WU-E1) | catalog load + validation tests |
| Purpose & content dimensions (§13.2) | `purpose`/`content` fields, descriptive (§8) | parsing tests; shown in GUI/MCP `list` |
| Stakeholders & concerns per viewpoint (Ch. 13, §5.7) | `stakeholders`/`concerns` fields (§8) | parsing tests; shown in GUI/MCP `list` |
| Concept selection per viewpoint (§13.1) | `ConceptScope` (locked) + criteria engine (§3) | Appendix C evaluator tests; W181/W182 |
| View conforms to its viewpoint | artifact-local projection + enforcement (§6.2/§6.3) | verifier tests (E180/W180/W181/W182); GUI ghosting |
| Views on the model (view ≠ diagram) | repository execution, four representations (§5.1, §6.1) | execution/representation tests |
| Notation/presentation conventions | `PresentationSpec` + capability registry + opaque tokens (§5) | capability-drift save/runtime tests |
| Customization: user-defined viewpoints (§13.3, implementation-defined) | two-tier catalog + GUI/MCP authoring (§9, §10) | lifecycle tests; docs (§12) |
| Example viewpoints library (Appendix C, informative) | `src/ontologies/archimate_4/viewpoints.yaml` starter library | library load test |
| Documentation of implementation-defined behavior (§5.7) | §12 pages + parent plan's conformance page | docs review gate |

## Appendix C — Required test matrix

The minimum semantic test set; structural (parsing/serialization) and integration tests are
listed with it because the failure modes concentrate there. Organize per the standing
test-file-per-component convention.

**Criteria evaluator (domain, pure)**
- Every comparator × {attribute missing, present scalar, present multi-valued} per the §3.4
  table — including `neq` on missing (no match) and `absent` with a value (save-time error).
- `negate` complement — including the `eq`+`negate`+missing-attribute → match case.
- Empty root group (match-all) vs. empty non-root group (validation error); empty `or`
  matches nothing; group `negate`.
- `ValueRef`: `attribute_of_self`, `attribute_of_endpoint` (source and target), unresolvable
  reference → no match; `attribute_of_endpoint` on an entity condition → save-time error.
- No coercion: `lt` on string attribute, scalar `in` value, list `eq` value → save-time
  errors; date compare via schema type.
- Reserved paths (§3.3): every reserved path filterable and usable as a `ColumnSpec.source`
  (incl. `name`, `version`, `subdomain`, `id`); numeric comparators rejected on `version`;
  unknown path head → save-mode error; endpoint fields rejected as left-hand paths.
- `IncidentConnectionCondition`: direction variants; `connection_criteria` narrowing by
  type, specialization, and profile attributes together; `ValueRef` inside
  `connection_criteria` resolving against the traversed connection and its endpoints;
  recursive `endpoint_criteria`, negated ("has no such connection"), dangling endpoint never
  matches; symmetric-type normalization (direction ignored for symmetric types, honored for
  directed types in the same evaluation; best-effort save-time warning fires only when a
  top-level type condition restricts to all-symmetric types).
- `NeighborInclusion`: widens the population (entity failing primary criteria but matching
  an inclusion is included as `expanded`); anchored on the primary set only (a neighbor of a
  neighbor is NOT included — no chaining); anchor-relative direction incl. symmetric
  normalization; membership precedence (entity matching primary and inclusion → `primary`);
  entity matched by two inclusion terms appears once; connections span the combined included
  set; the justifying connection is not displayed when it fails `connections.criteria`.
- Depth cap: boolean-only, relational-only, and mixed trees at the cap and one past it;
  cap read from `validation.viewpoint_query_depth_cap` (non-default value honored);
  save-time-only enforcement (an over-cap definition still loads and evaluates).
- Schema drift: valid-at-save attribute unknown at evaluation → no match + warning.

**Connection inclusion & matrix**
- Structural invariant: connection included iff both endpoints selected; `enabled=False`;
  narrowing criteria cannot widen.
- Matrix grouped axes vs. criteria axes; mixing modes → validation error; one axis criteria
  without the other → validation error; disjoint populations (empty base) produce correct
  row/column sets; bridging invariant (row↔column only); `connections.enabled=False` on a
  matrix warns.

**Style rules**
- First-match-wins ordering per capability; `default_style` fallback; `applies_to` scoping.
- Range bands: half-open boundaries (value == minimum in; value == maximum out); overlap →
  validation error; missing/out-of-band attribute → default.
- Relational styling: a node rule whose match criteria contain an
  `IncidentConnectionCondition` styles exactly the entities satisfying the relational
  predicate (and counts toward the depth cap).
- Capability/criteria-kind agreement (`edge_*` needs connection criteria) → validation error;
  unknown capability for the representation → save-time rejection; legacy-definition
  capability drift → runtime warning.

**Projection**
- Repository context: only matches present, styled, deterministic order.
- Artifact-local: every occurrence present; reason assignment (`out_of_scope`,
  `criteria_mismatch`, `endpoint_excluded` incl. combinations); enforcement mapping
  off/warn/ghost; occlusion-dominates-styling (style map empty whenever reasons non-empty,
  in every enforcement mode incl. `warn`; matching occurrences styled in every mode);
  stale pin → current definition + `stale_pin`; unknown slug → identity projection +
  warning.
- Verifier: W182 emitted per criteria-mismatch occurrence, suppressed when enforcement `off`
  or definition has no query; E180/W180/W181 behavior unchanged (regression); verifier and
  GUI projection agree (same service, one shared fixture asserted from both surfaces).

**Execution result**
- Sorted ids; fixed per-item summaries incl. membership; entity-denominated truncation
  (flag + limit echoed; four counts total/returned × entity/connection with totals
  pre-truncation; expanded members dropped before primary; connections re-filtered to
  retained entities); matrix axis metadata present iff criteria-axes matrix, axis lists
  sorted subsets of returned entities, unrendered = returned minus axis union (complement
  property asserted); timeout → typed error, no partial result; repo_scope filtering; index
  revision passthrough; duration + structured log line.

**Validation modes (§7.2)**
- Same definition through all three modes: registry finding = load warning but save error;
  depth cap and empty non-root group ignored at load, errors at save; lifecycle rules fire
  only in persist_edit; malformed structure rejects at load.
- `ViewpointValidationIssue`: severity/code/path/expected/found populated; codes stable
  across releases (snapshot test); paths resolve into entity, connection, inclusion,
  style-rule, and axis trees.

**Intelligibility (MCP/GUI parity, §9.1)**
- Plain-language summary renderer: covers every node kind (condition incl. negate phrasing,
  incident, group, inclusion terms, connection selection); identical string via REST and
  MCP `list`/`execute` (one shared fixture, all surfaces).
- Validation-error contract: every error/warning carries a resolvable path into the
  definition; path targets the offending node for nested criteria (entity, connection,
  inclusion, style-rule, and axis trees).

**Serialization / parsing**
- Round-trip identity for every Appendix-A example plus a maximal-shape definition; unknown
  key → parse error; defaults omitted on write; `ValueRef` shorthand vs. mapping forms.
- Appendix-A executability: fixture profiles from `tests/fixtures/viewpoints/schemata/`
  installed into the test repo's `.arch-repo/schemata/`, then every example passes
  save-mode validation (slugs against the shipped catalog, attributes against the merged
  effective schemas); removing a fixture profile makes the corresponding example fail —
  proving validation is real, not weakened.

**Purpose/content cardinality (§8)**
- Parser: singular string shorthand ≡ one-element tuple; multi-valued lists parse;
  serializer writes singular form for one-element tuples (round-trip preserves the
  shorthand); starter library loads unchanged.

**Lifecycle & tools**
- Version bump enforced on semantic edit, not on descriptive edit; slug collision across
  merged catalog; delete blocked with referencing artifacts listed; enterprise/module
  definitions read-only via engagement-scoped tools; promotion exact-version check
  (regression on the existing D14 test).
- MCP/REST parity: `artifact_query_viewpoint execute` and the REST endpoint return the same
  §7.1 content for the same query (one shared fixture, both transports).
- Bounds settings: MCP default limit vs. explicit `limit` argument vs. clamp at
  `execution_max_entities`; GUI/REST default equals the hard cap; timeout setting honored;
  limits denominated in entities (a result with few entities but many connections never
  truncates).

## Appendix D — C19C view-exchange mapping (informative; feeds the parent plan's exchange work)

Verified against `spec/c19c-view-exchange_compressed.pdf` — the Open Group's schema
documentation for `archimate3_View.xsd` — and the worked example
`spec/c19c-examples/Model_View.xml`. Note the PDFs under `spec/` are **local-only**
(`*.pdf` is gitignored per the standing no-PDFs-in-git rule): an implementer without them
obtains the C19C documents from the Open Group; the XSD itself is not vendored either
(licensing is gated by the parent plan's WU-F1 sign-off). The companion
`spec/c19c-diagram-exchange_compressed.pdf` and `spec/c19c-model-exchange_compressed.pdf`
cover the node/connection style and model layers referenced in the mapping table. This
appendix records how
this plan's concepts map onto the Open Group exchange format so the parent plan's exchange
work units implement viewpoints without re-deriving the correspondence. Nothing here is a
runtime dependency: exchange import/export is a separate adapter, XML never leaks inward,
and — per the standing preference — our own persistence stays YAML; the exchange format is
spoken only at the boundary. Apart from the §8 cardinality alignment, nothing in this
appendix changes the domain model.

| this plan | C19C view exchange | mapping notes |
|---|---|---|
| `ViewpointDefinition` (standard, from the starter library) | `ViewType@viewpoint` — a **name** from the informative `ViewpointsEnum` (27 names, open string union) | export: emit the standard name, no definition body; import: resolve by name against the shipped library; unknown names import as name-only references with a warning |
| `ViewpointDefinition` (custom / repo-authored) | `ViewpointType` element + `ViewType@viewpointRef` (IDREF) | full definition travels inside the model file; `slug` ↔ `identifier`, `name` ↔ `name` |
| `purpose` / `content` (tuples, §8) | `viewpointPurpose` / `viewpointContent` (**lists** of enums) | 1:1 after the §8 widening — the reason for it |
| `stakeholders` + `concerns` (flat siblings) | `concern*`, each with optional **nested** `stakeholders` | import: concerns ← labels, stakeholders ← union of all nested lists; export: each concern carries the full stakeholder list (approximately true at viewpoint granularity — we do not model the per-concern association). Import∘export is idempotent; the association granularity is documented as not preserved |
| `ConceptScope` | `allowedElementType*` / `allowedRelationshipType*` | bidirectional and lossless in both directions (both are type-level lists); type-name mapping reuses the exchange codec's element/relationship tables |
| `ExecutableViewpointQuery` + `PresentationSpec` | `modelingNote*` (documentation with a free-form `type` attribute — the spec's own extension point, "could contain rules or constraints", OCL cited as an example) | export TWO notes: the §9.1 plain-language summary (`type="text/plain"` — any conforming tool shows a human-readable account of the query) and the canonical Appendix-A YAML (`type="application/x-arch-viewpoint-query+yaml"`). Import recognizes our own media type and round-trips the query losslessly; foreign tools degrade gracefully to the prose note. The criteria tree is deliberately **never re-encoded as XML** |
| `ViewpointApplication` | `ViewType@viewpoint` / `@viewpointRef` on the exported view | `pinned_version` has no exchange analog → exported as a property via `propertyDefinitions`; on import, applications re-pin to the imported definition's current version as a reviewed step (consistent with §10's no-version-history rule) |
| Style tokens (§5.2) | per-node/connection `style` (concrete RGB `lineColor`/`fillColor`, font) | export may resolve tokens to concrete colors through a surface palette (a diagram-exchange concern, outside this plan); import does **not** reverse-map colors to tokens — lossy by design, documented |
| Enforcement, projection, W-codes | — | no exchange analog; never exported |

Two cautions for the exchange work unit: `ViewpointsEnum` is explicitly *informative* — the
`@viewpoint` attribute is a union with `xs:string`, so imports must tolerate arbitrary
names; and `ModelingNoteType` ordering inside `ViewpointType` is not significant, so the
importer must locate our YAML note by `type`, not by position.
