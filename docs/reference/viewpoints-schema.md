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
```

A timeout is a typed error, never a silently partial result.

&nbsp;

## MCP tools

- **`artifact_viewpoint`** (`arch-repo-write`) — `action: create | edit | delete`. `definition`
  (create/edit) is the full mapping above; `slug` (delete only). Engagement-repo scope only —
  enterprise/module-shipped definitions are read-only here. `dry_run` (default `true`)
  validates and reports without writing.
- **`artifact_query_viewpoint`** (`arch-repo-read`) — `action: list | execute`. `list` returns
  every catalog entry's identity fields plus `scope_summary`/`query_summary`. `execute` runs
  `slug=...` (a saved definition) or `query=...` (an ad-hoc query, same shape as above) and
  returns the execution result described above; `limit` (entities) and `repo_scope`
  (`engagement | enterprise | both`, default `both`) are optional.

&nbsp;

## Verifier codes

E180/W180/W181/W182 check a diagram/matrix's `viewpoint:` application — see
[Viewpoints → Applying a viewpoint](../03-modeling/viewpoints.md#applying-a-viewpoint-to-an-existing-diagram-or-matrix)
for what each one means and how enforcement modes affect them.

---

*Part of the [Reference](configuration.md) section.*
