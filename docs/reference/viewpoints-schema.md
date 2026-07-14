# Viewpoints — Schema Reference

Reference material for authoring a `ViewpointDefinition` by hand (`.arch-repo/viewpoints.yaml`)
or through the `artifact_viewpoint`/`artifact_query_viewpoint` MCP tools. For what a viewpoint
is and how to apply one, see [Viewpoints](../03-modeling/viewpoints.md).

&nbsp;

## Canonical YAML shape

`viewpoints.yaml` (module-shipped and `.arch-repo/` tiers), the MCP `create`/`edit` payload,
and the round-trip tests all use this shape. Unknown keys are a parse error, not silently
ignored — a typo like `comparater` is caught, not swallowed. Field defaults are omitted on
write, so a minimal definition stays minimal.

```yaml
viewpoints:
  # A flat filter
  - slug: application-components
    version: 1
    name: Application Components
    purpose: informing        # informing | designing | deciding
    content: overview          # overview | coherence | details
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

  # Nested boolean logic + a relational predicate + neighbor inclusion + a table
  - slug: components-serving-processes
    version: 2
    name: Components Serving Processes
    query:
      query_schema: 1
      entity_criteria:
        kind: group
        conjunction: and
        children:
          - {kind: condition, attribute: type, comparator: eq, value: application-component}
          - kind: incident
            direction: outgoing            # outgoing | incoming | either
            connection_criteria:
              kind: group
              conjunction: and
              children:
                - {kind: condition, attribute: type, comparator: eq, value: archimate-serving}
                - {kind: condition, attribute: strength, comparator: gte, value: 3}
            endpoint_criteria:
              kind: group
              conjunction: and
              children:
                - {kind: condition, attribute: type, comparator: eq, value: process}
      include_connected:
        - direction: outgoing               # relative to the primary (anchor) entities
          connection_criteria:
            kind: group
            conjunction: and
            children:
              - {kind: condition, attribute: type, comparator: eq, value: archimate-serving}
          neighbor_criteria:
            kind: group
            conjunction: and
            children:
              - {kind: condition, attribute: type, comparator: eq, value: process}
      connections:
        enabled: true
        criteria:
          kind: group
          conjunction: and
          children:
            - kind: condition
              attribute: strength
              comparator: gte
              value: {from: target, attribute: threshold}   # ValueRef, not a literal
    presentation:
      representation: table
      columns:
        - {label: Name, source: name}
        - {label: Risk, source: risk_score}
      styling_rules:
        - capability: badges
          mode: match
          match_criteria:
            kind: group
            conjunction: and
            children:
              - {kind: condition, attribute: status, comparator: eq, value: deprecated}
          value: badge-warning
        - capability: badges
          mode: range
          range_attribute: risk_score
          range_bands:
            - {minimum: null, maximum: 4, value: badge-ok}       # [-inf, 4)
            - {minimum: 4, maximum: 7, value: badge-caution}     # [4, 7)
            - {minimum: 7, maximum: null, value: badge-danger}   # [7, inf)
      default_style:
        badges: badge-neutral

  # A disjoint-population matrix (requirements x components)
  - slug: requirement-coverage
    version: 1
    name: Requirement Coverage
    query:
      query_schema: 1
      entity_criteria: {kind: group, conjunction: and, children: []}   # match-all base
      connections:
        enabled: true
        criteria:
          kind: group
          conjunction: and
          children:
            - {kind: condition, attribute: type, comparator: eq, value: archimate-realization}
    presentation:
      representation: matrix
      row_criteria:
        kind: group
        conjunction: and
        children:
          - {kind: condition, attribute: type, comparator: eq, value: requirement}
      column_criteria:
        kind: group
        conjunction: and
        children:
          - {kind: condition, attribute: type, comparator: eq, value: application-component}
```

&nbsp;

## Criteria nodes

Every node in `entity_criteria`/`connection_criteria`/`neighbor_criteria`/`endpoint_criteria`/
`match_criteria` is discriminated by `kind`:

| `kind` | Applies to | Fields |
|---|---|---|
| `condition` | entity or connection | `attribute`, `comparator`, `value`, `negate` |
| `group` | entity or connection | `conjunction` (`and`\|`or`), `children`, `negate` |
| `incident` | entity only | `connection_criteria`, `direction`, `endpoint_criteria`, `negate` — matches an entity with an incident connection satisfying both criteria |

`negate` is the strict logical complement of the node's own match result — including the
missing-attribute case (see the comparator table below). An empty root group is match-all; an
empty non-root group is a save-time validation error (it's almost never intentional).

**`value`** is either a literal (scalar or list) or a `ValueRef` mapping `{from: ..., attribute: ...}`:

| `from` | Reads | Valid on |
|---|---|---|
| *(bare literal)* | the literal itself | any condition |
| `self` | another attribute on the same entity/connection being evaluated | any condition |
| `source` / `target` | that attribute on the connection's source/target entity | connection conditions only |

&nbsp;

## Comparator semantics

| comparator | value shape | attribute missing | present, scalar | present, multi-valued |
|---|---|---|---|---|
| `eq` | scalar | no match | `==` | any element `==` |
| `neq` | scalar | no match | `!=` | **no** element `==` |
| `in` | non-empty list | no match | value ∈ list | any element ∈ list |
| `exists` | none | no match | match | match |
| `absent` | none | match | no match | no match |
| `lt` / `lte` / `gt` / `gte` | scalar, numeric/date | no match | typed compare | any element satisfies |

Missing attributes match only `absent` — never `neq` ("no value" is not "trivially unequal").
Nothing is coerced at evaluation time: comparator/type mismatches (`lt` on a string attribute,
`in` with a scalar value, …) are save-time validation errors against the effective attribute
schema, not runtime surprises. An attribute path that validated at save time but no longer
exists at evaluation time (schema drift — a profile removed, an attribute renamed) behaves as
*missing* and adds a warning to the execution result, never a silent wrong answer.

Symmetric connection types (e.g. `archimate-association`) ignore `direction` on an incident
condition or neighbor inclusion — source/target order for those types is authoring order, not
semantics, so direction can never discriminate them regardless of what's written.

&nbsp;

## Reserved attribute paths

One namespace, used everywhere a path appears — filter conditions, table `columns`, `ValueRef`
references, style-rule criteria:

| path | applies to | notes |
|---|---|---|
| `id` | entity + connection | artifact id |
| `name` | entity | |
| `type` | entity + connection | type slug |
| `specialization` | entity + connection | specialization slug |
| `group` | entity | directory-facet group |
| `domain` | entity | |
| `subdomain` | entity | |
| `status` | entity | lifecycle status |
| `version` | entity | string comparators only |
| anything else | entity or connection | dotted path into the effective attribute schema (base-type profile ⊕ the entity's own specialization profile) |

A connection's endpoints are not addressable as left-hand condition paths (no `source.type`)
— reach an endpoint's attributes only via `ValueRef(from: source|target)` on a connection
condition, or via an incident/neighbor node's `endpoint_criteria`/`neighbor_criteria` from the
entity side.

&nbsp;

## Bindings, parameters & derived attributes

Extends the query grammar above without a formula/text escape hatch — every field here is
also authorable through the GUI's query builder. See
[Viewpoints → Parameters](../03-modeling/viewpoints.md#parameters-the-same-definition-different-anchors)
and the sections following it for explanation and worked examples; this is the field-level
grammar.

**`parameters[]`** (`QueryParameter`):

| Field | Type | Notes |
|---|---|---|
| `name` | string | unique within the definition |
| `type` | `string` \| `integer` \| `number` \| `date` \| `boolean` \| `slug` \| `entity-id` | |
| `required` | bool | default `true` |
| `default` | matches `type` | only meaningful when `required: false` |
| `description` | string | shown in the GUI's parameter prompt and every tool's `list` output |

**`bindings[]`** (`QueryBinding`):

| Field | Type | Notes |
|---|---|---|
| `name` | string | unique within the definition; referenced as `{from: binding, name: ...}` |
| `select` | `entities` \| `connections` | which population `criteria` selects over |
| `criteria` | criteria tree | same grammar as `entity_criteria`/`connection_criteria` |
| `result_type` | see below | checked statically wherever the binding is referenced |
| `project` | attribute path | optional; projects the selection down to one attribute per item |
| `aggregate` | `count` \| `sum` \| `avg` \| `min` \| `max` | optional; collapses a set to a scalar |
| `tuple_of` | list of binding names | optional; combines other bindings into one tuple-typed value |
| `include_in_result` | bool | default `false`; entity-valued bindings only — folds the binding's matched entities into the primary result set as `membership: expanded`, same as a neighbor inclusion |

**`derived[]`** (`DerivedAttribute`):

| Field | Type | Notes |
|---|---|---|
| `name` | string | unique; referenced as `derived.<name>` in styling-rule criteria/range bands |
| `direction` | `outgoing` \| `incoming` \| `either` | default `either` |
| `traversal` | `direct` \| `derived` | default `direct` |
| `include_potential` | bool | `derived` traversal only |
| `max_hops` | int ≥ 2 | `derived` traversal only |
| `connection_criteria` / `endpoint_criteria` | criteria tree | narrow which incident connections/endpoints count |
| `reduce` | `count` \| `sum` \| `avg` \| `min` \| `max` | default `count` |
| `of` | attribute path, or the special value `relationship.hops` | required unless `reduce: count`; `relationship.hops` requires `traversal: derived` |

**Result-type strings** (bindings) and **value-reference kinds** (any condition's `value`):

| Result type | Shape | `in`/`not_in` valid? |
|---|---|---|
| `entity[type]` / `connection[type]` | one item | no — scalar |
| `entities[type]` / `connections[type]` | a list | yes |
| `scalar` | one comparable value (from `project`/`aggregate`) | no |

| `value.from` | Reads |
|---|---|
| *(bare literal)* / `literal` | the literal itself |
| `attribute_of_self` | another attribute on the same entity/connection |
| `attribute_of_endpoint` | an attribute on the connection's source/target — connection conditions only |
| `parameter` | a declared parameter's supplied value |
| `binding` | a declared binding's value, optionally `project`-ed and/or `quantifier`-ed |

A list-typed reference used with a comparator other than `in`/`not_in` needs an explicit
`quantifier` (`any` | `all`) — `any` over an **empty** set is `false` (nothing to satisfy
"any of nothing"); `all` over an empty set is `true` (vacuously — nothing violates it). This
is standard set-logic convention, not a special case this system invented, but worth stating
plainly since it surprises people the first time a binding legitimately resolves empty.

&nbsp;

## Traversal & derivation

`traversal: derived` (on an `incident` condition, a neighbor inclusion, `connections`, or a
derived attribute) composes indirect relationships from real ones per the ArchiMate
derivation rules — see
[Impact analysis](../03-modeling/impact-analysis.md) for the semantics (certain vs.
potential, role/strength composition, why Association can't be composed through).

| Field | Applies to | Notes |
|---|---|---|
| `include_potential` | any `derived`-traversal node | default `false` — potential (PDR-rule) derivations excluded unless opted in |
| `max_hops` | any `derived`-traversal node | integer ≥ 2; `derivation-hops-exceeded` below that |

A derived connection's summary carries `certainty` (`certain` \| `potential`), `hops`
(integer), and `via_connection_ids` (the witnessing real connections, in an order the
consuming code reconstructs into a path — not guaranteed to already be source-to-target
order in the raw list). These three fields are `null`/empty on a directly modeled
connection, so existing consumers that only handle direct connections see no shape change.

A `derived`-traversal node's own `connection_criteria` may only reference `type`,
`certainty`, or `hops` — a derived relationship has no single connection artifact backing it
for endpoint-attribute references (`derived-traversal-path-unsupported` otherwise).

&nbsp;

## Representations & styling capabilities

| Representation | Capabilities |
|---|---|
| `exploration` | `node_shape`, `node_icon`, `node_color`, `edge_color`, `edge_emphasis`, `cluster_grouping` |
| `table` | `columns`, `badges`, `sort`, `row_grouping` |
| `matrix` | `row_by`, `column_by`, `cell_emphasis` |
| `diagram` | `node_color`, `edge_color`, `edge_emphasis`, `cluster_grouping` (fixed notation — no `node_shape`/`node_icon`) |

A `StyleRule.capability` prefixed `node_*`/`cluster_*`/a table capability takes
`EntityCriteriaGroup` match criteria; `edge_*` takes `ConnectionCriteriaGroup` — a mismatch is
a save-time error. `RangeBand.minimum`/`maximum` are `[minimum, maximum)` — inclusive lower
bound, exclusive upper bound, `null` for unbounded.

`display_options.label_attribute` (`exploration`/`diagram` only) names an attribute path —
a reserved path, a declared profile attribute, or a `derived.` path — shown under an
occurrence's name. Other representations reject it; an unresolvable path is a save-time
`unknown-attribute` error, same as any other attribute reference.

&nbsp;

## Lifecycle & validation

Three validation modes, one validator:

| Mode | When | Checks |
|---|---|---|
| `load` | Catalog load, including hand-edited YAML | Structural parse only; unknown-attribute/type/capability drift is a warning, not a rejection — a definition authored under a looser deployment still loads and evaluates elsewhere. |
| `save` | GUI builder / MCP `create`/`edit` | Everything `load` warns about becomes an error, plus authoring-ergonomics checks: criteria-tree depth cap (fixed at 4 today — 3 boolean levels plus one relational hop), empty non-root groups, range-band overlap, matrix axis-mode exclusivity, style-rule capability/criteria-kind agreement. |
| `persist_edit` | The write path only | `save` plus lifecycle rules: a semantic edit (`scope`/`query`/`presentation`/`representation_types`) requires a version bump; slug uniqueness against the effective merged catalog; delete blocked while any diagram/matrix references the slug. |

Direct YAML edits only ever receive `load`-mode guarantees — there is no "prior state" to
check a version bump or a delete reference against outside the write path. Every issue
reported at any mode carries a stable `code`, a JSON-pointer-style `path` into the definition,
and `expected`/`found` values, so both the GUI and an agent can converge on the same fix.

**Validation codes for bindings, parameters, derived attributes, and derived traversal**
(all `error` severity, `save`/`persist_edit` modes, except where noted):

| Code | Fires when |
|---|---|
| `depth-cap-exceeded` | combined boolean-nesting + relational-hop depth exceeds the configured cap |
| `symmetric-direction-ineffective` (*warning*) | an incident condition's `direction` is non-`either` but its `connection_criteria` restricts to only symmetric connection types — direction can't discriminate those |
| `derivation-hops-exceeded` | a `derived`-traversal node's `max_hops < 2` |
| `derived-traversal-path-unsupported` | a `derived`-traversal node's `connection_criteria` references an attribute other than `type`/`certainty`/`hops`, or uses an endpoint-attribute reference |
| `unexpected-value` | `exists`/`absent` given a non-null value |
| `value-ref-missing-endpoint` / `value-ref-endpoint-outside-connection` / `value-ref-missing-attribute` | `attribute_of_endpoint`/`attribute_of_self` used incorrectly (see [Value references](#bindings-parameters--derived-attributes) above) |
| `unsupported-value-shape` | `in`/`not_in` given a non-list literal, or `like`/`ilike` given a non-string literal |
| `unknown-value` | a literal `type`/`specialization` value isn't a known slug |
| `unknown-binding` / `unknown-parameter` | a `{from: binding\|parameter}` reference names an undeclared binding/parameter |
| `derived-attribute-unknown` | a `derived.<name>` path names an undeclared derived attribute (also reused for a duplicate derived-attribute name) |
| `binding-type-mismatch` / `binding-attribute-type-ambiguous` | a binding's declared or inferred type can't be resolved statically |
| `aggregate-over-instance` | `aggregate` applied to a binding that isn't a set/projected-list type |
| `unquantified-set-comparison` | a list-typed reference used without `quantifier`, on a comparator other than `in`/`not_in` |
| `operator-type-mismatch` | catch-all comparator/reference-type mismatch (non-scalar list elements, `in`/`not_in` against a non-list, `like`/`ilike` against a non-string, reference type disagrees with the compared attribute) |
| `tuple-comparator-unsupported` | a tuple-typed reference used with a comparator other than `eq`/`in`/`not_in` |
| `duplicate-parameter-name` / `duplicate-binding-name` | name collision within `parameters`/`bindings` |
| `parameter-type-mismatch` | a parameter's `default` doesn't match its `type` |
| `parameter-count-exceeded` / `binding-count-exceeded` / `derived-attribute-count-exceeded` | list length exceeds the configured cap |
| `binding-derived-reference-unsupported` | a binding's `criteria` references a `derived.*` path (bindings can't depend on derived attributes) |
| `include-in-result-shape-unsupported` | `include_in_result: true` on a binding whose `result_type` isn't entity-valued |
| `binding-cycle` | the bindings' reference graph (via `tuple_of`/criteria references) has a cycle |
| `derived-reduce-type-mismatch` | `reduce: count` given an `of` source, or `of`'s type can't be reduced |
| `derived-of-missing` | a non-`count` reduction has no `of` |
| `derived-of-source-traversal-mismatch` | `of: relationship.hops` used without `traversal: derived` |
| `derived-attribute-reference-unsupported` | a derived attribute's own criteria references another `derived.*` path |

**Execution-time errors** (typed, never a silent empty/partial result; mapped to a REST
`{code, path, message}` body and the equivalent MCP error shape):

| Code | HTTP | Fires when |
|---|---|---|
| `missing-parameter` | 400 | a required parameter has no supplied value and no default |
| `unknown-parameter` | 400 | a supplied parameter name isn't declared |
| `parameter-type-mismatch` | 400 | a supplied value doesn't match its parameter's declared type |
| `binding-cardinality-violation` | 400 | a binding declared exactly-one/zero-or-one resolved to a different actual count |
| `derivation-limit` | 400 | the `derivation_max_relationships` hard memory ceiling was hit — the ordinary case (a slow-but-tractable search) instead stops gracefully at the time budget and returns a genuine partial result flagged `truncated`, with a warning, not this error |
| `execution-timeout` | 504 | whole-pipeline elapsed time exceeds `execution_timeout_seconds` |

&nbsp;

## Execution result & bounds

`artifact_query_viewpoint`'s `execute` action (and the GUI's table/matrix/diagram execution
views) returns: sorted entity/connection ids, a fixed per-item summary (id/name/type/
specializations/group/membership for entities; id/type/source/target for connections), four
counts (`total_entity_count`, `returned_entity_count`, `total_connection_count`,
`returned_connection_count`), a `truncated` flag, `matrix_axes` (criteria-axes matrix only),
warnings, and the plain-language `query_summary`. No presentation/styling/column parameters
are ever part of an execution result — that boundary is intentional (agents and humans see
identical descriptive content; only the GUI additionally renders it styled).

The limit is entity-denominated (connections are a derived, re-filtered set — never
independently capped); truncation drops **expanded members first**, in reverse stable order,
keeping the primary selection intact. Configured in `config/settings.yaml`:

```yaml
viewpoints:
  execution_max_entities: 500              # hard cap, all transports
  execution_default_entity_limit_mcp: 200  # MCP default when execute's limit argument is omitted
  execution_timeout_seconds: 10
  max_query_bindings: 8                    # save-time ergonomics cap
  max_query_parameters: 4                  # save-time ergonomics cap
  max_derived_attributes: 8                # save-time ergonomics cap
  derivation_max_hops: 4                   # default max_hops when a derived-traversal node omits it
  derivation_max_relationships: 20000      # hard memory-protection ceiling — raises derivation-limit
  derivation_time_budget_seconds: 2.0      # the practical enforcement: derivation stops gracefully here
```

A timeout is a typed error, never a silently partial result. Derivation-relationship search
is the one place a genuinely partial, *warned* result is correct behavior rather than a typed
error — see [Traversal & derivation](#traversal--derivation) above and
[Impact analysis](../03-modeling/impact-analysis.md).

&nbsp;

## MCP tools

- **`artifact_viewpoint`** (`arch-repo-write`) — `action: create | edit | delete`. `definition`
  (create/edit) is the full mapping above; `slug` (delete only). Engagement-repo scope only —
  enterprise/module-shipped definitions are read-only here. `dry_run` (default `true`)
  validates and reports without writing.
- **`artifact_query_viewpoint`** (`arch-repo-read`) — `action: list | execute`. `list` returns
  every catalog entry's identity fields plus `scope_summary`/`query_summary` and a
  `parameters` array — one entry per declared parameter (`name`, `type`, `required`, and
  `description` when non-empty), so an agent can see what a parameterized definition needs
  before attempting to execute it, without a failed call first. `execute` runs `slug=...` (a
  saved definition) or `query=...` (an ad-hoc query, same shape as above) and returns the
  execution result described above; `limit` (entities) and `repo_scope`
  (`engagement | enterprise | both`, default `both`) are optional.

&nbsp;

## Verifier codes

E180/W180/W181/W182 check a diagram/matrix's `viewpoint:` application — see
[Viewpoints → Applying a viewpoint](../03-modeling/viewpoints.md#applying-a-viewpoint-to-an-existing-diagram-or-matrix)
for what each one means and how enforcement modes affect them.

---

*Part of the [Reference](configuration.md) section.*
