# Viewpoints

A **viewpoint** (ArchiMate 4.0 Chapter 13) is a saved, reusable way of looking at a slice of
the model — which entities and connections it covers, and how they're presented. Instead of
hand-curating a diagram's entity list every time a question comes up ("which application
components serve a business process, and which processes do they serve?"), a viewpoint
definition answers it on demand, against whatever the model currently contains.

This page is the explanation and how-to; the full YAML shape, comparator semantics, and MCP
tool parameters are in [Viewpoints — schema reference](../reference/viewpoints-schema.md).

&nbsp;

## Definitions, applications, and ad-hoc execution

Three related but distinct things share the word "viewpoint":

- **`ViewpointDefinition`** — the reusable, versioned thing: a slug, a name, a purpose/content/
  stakeholders/concerns description, a **query** (which entities/connections match), and a
  **presentation** (how to show them). Definitions live in a two-tier catalog — a small,
  informative starter library shipped by the `archimate_4` module (Motivation, Application
  Structure, Layered, Technology Usage), plus repo-authored definitions in
  `.arch-repo/viewpoints.yaml` at the enterprise and engagement tiers, merged the same way
  [specializations](../05-extensibility/ontology-modules.md#specializations) are.
- **`ViewpointApplication`** — pinning an *existing* diagram or matrix to a definition (at a
  specific version), non-destructively. The diagram's own placed entities/connections don't
  change; the application adds an overlay that flags which of them fall outside the
  definition's scope or fail its query, so the artifact and the viewpoint's intent can be
  compared over time as both evolve.
- **Ad-hoc execution** — running a definition's query (or a query supplied inline, with no
  saved definition at all) directly against the live model, with no diagram involved. This is
  what `artifact_query_viewpoint`'s `execute` action and the GUI's table/matrix/diagram
  execution views do.

&nbsp;

## Applying a viewpoint to an existing diagram or matrix

Set a `viewpoint:` block in a diagram or matrix's frontmatter (`slug`, `version`, and
optionally `enforcement_override`) to pin it to a definition. Every placed entity and
connection is then classified against that definition:

- **Fully matching** (in scope, satisfies the query) — rendered normally, and styled per the
  definition's styling rules if it has any.
- **Out of scope** — the entity/connection type isn't in the definition's scope at all.
- **Criteria mismatch** — in scope, but fails the query's criteria (only checked when the
  definition has a query).
- **Endpoint excluded** — a connection whose source or target is itself excluded.

The **enforcement setting** (`off | warn | ghost`, defaulting to `warn`, overridable per
application) decides what happens to non-matching items:

| Enforcement | Non-matching items |
|---|---|
| `off` | Rendered normally — no ghosting, no reasons reported. |
| `warn` | Rendered normally, but the reason is recorded and surfaced (verifier warning, GUI badge). |
| `ghost` | Visually de-emphasized (or, with the GUI's "hide instead of ghost" toggle, hidden). |

Styling never applies to an excluded item, in any enforcement mode — a ghosted element
wearing a highlight color would contradict its own exclusion. A pinned version older than
the definition's current version is a **stale pin**: the diagram is still evaluated against
the *current* definition (no old versions are retained), with a distinct warning rather than
a silent reinterpretation. An unknown viewpoint slug is always an error, never silently
ignored.

The verifier (`artifact_verify` and every write path) checks a diagram's `viewpoint:`
application on every run, using the exact same evaluation the GUI's ghost/hide overlay uses
— a CI check and what a human sees in the browser can never disagree:

| Code | Severity | Meaning |
|---|---|---|
| E180 | error | Unknown viewpoint slug. |
| W180 | warning | Pinned version is older than the definition's current version. |
| W181 | warning | A placed entity/connection is out of the definition's scope. |
| W182 | warning | A placed entity/connection is in scope but fails the definition's query. |

&nbsp;

## The criteria model

A viewpoint's `query` selects entities (and, through them, connections) with a **criteria
tree**: `AND`/`OR` groups of conditions, each optionally negated. Every condition compares one
attribute (a reserved read-model field like `type`/`status`/`group`, or a repo-specific
attribute from that entity's effective schema) against a value using a comparator (`eq`,
`neq`, `in`, `exists`, `absent`, `lt`, `lte`, `gt`, `gte`).

**A simple filter** — every application component:

```yaml
query:
  entity_criteria:
    kind: group
    conjunction: and
    children:
      - {kind: condition, attribute: type, comparator: in, value: [application-component]}
```

**Nested boolean logic with negation** — active elements, in either the application or
technology domain, that are *not* deprecated:

```yaml
query:
  entity_criteria:
    kind: group
    conjunction: and
    children:
      - kind: group
        conjunction: or
        children:
          - {kind: condition, attribute: domain, comparator: eq, value: application}
          - {kind: condition, attribute: domain, comparator: eq, value: technology}
      - {kind: condition, attribute: status, comparator: eq, value: deprecated, negate: true}
```

Negation is the strict logical complement — "not deprecated" also matches an entity with no
`status` set at all, since "has no value" is not "equals deprecated" either. Missing
attributes match only the `absent` comparator; every other comparator treats a missing
attribute as no match, before `negate` is applied.

**A relational predicate** — this is where viewpoints go beyond a flat filter. An
`IncidentConnectionCondition` matches an entity that has (or, negated, does not have) at
least one incident connection satisfying criteria on *both* legs of the hop — the connection
itself, and the entity on the other end:

```yaml
query:
  entity_criteria:
    kind: group
    conjunction: and
    children:
      - {kind: condition, attribute: type, comparator: eq, value: application-component}
      - kind: incident
        direction: outgoing
        connection_criteria:
          kind: group
          conjunction: and
          children:
            - {kind: condition, attribute: type, comparator: eq, value: archimate-serving}
        endpoint_criteria:
          kind: group
          conjunction: and
          children:
            - {kind: condition, attribute: type, comparator: eq, value: process}
```

"Application components that serve at least one process." Add `include_connected` (a
**neighbor inclusion**) to widen the result to include those served processes too, as
context — the complement of the incident condition: an incident condition *filters* (narrows
which entities match), a neighbor inclusion *widens* (adds entities connected to the primary
result). Included neighbors carry `membership: expanded` rather than `primary`, so a surface
can render them distinctly.

A connection appears in the result only when **both** its source and target entities are
included (primary or expanded) — this is a fixed evaluator rule, not something a query can
override. `connections.criteria` narrows *within* that structural set (e.g., "only serving
connections with `strength >= 3`"); it can never widen past it.

&nbsp;

## The four representations

| Representation | Shows | Styling capabilities |
|---|---|---|
| `exploration` | Graph navigation over the matched population | node shape/icon/color, edge color/emphasis, cluster grouping |
| `table` | A flat list, one row per matched entity, with `columns` projecting attributes | columns, badges, sort, row grouping |
| `matrix` | A relationship grid between two entity populations | row/column axis, cell emphasis |
| `diagram` | An ad-hoc ArchiMate-notation rendering — same rendering engine as a real diagram, but never persisted and needs no `ViewpointApplication` | node/edge color, edge emphasis, cluster grouping (fixed notation — shape/icon aren't overridable here) |

A matrix has two axis modes: **grouped** (`row_by`/`column_by` split one population by a
type/specialization/group key — the traditional relationship-matrix shape) or **criteria**
(`row_criteria`/`column_criteria` define two independent entity populations — requirements ×
components, stakeholders × concerns — for a disjoint-population matrix). The two modes are
mutually exclusive on one definition.

&nbsp;

## Styling: match mode and range mode

`styling_rules` are evaluated in order, first match wins per capability, falling back to
`default_style`:

- **`mode: match`** — reuses the exact same criteria-tree type as query filtering, so a style
  rule can express "highlight this entity when it has a connection matching Y to an entity
  matching Z" with no separate mechanism.
- **`mode: range`** — a numeric/date attribute mapped through explicit, non-overlapping
  half-open bands (`[minimum, maximum)`) to a style token — the threshold/gradient case
  (e.g., risk score → ok/caution/danger).

Legends are always derived from `styling_rules` + `range_bands` + `default_style` — there's
nothing to separately author.

&nbsp;

## Authoring a definition

Three equivalent surfaces write the same catalog file and run the same validation:

- **GUI** — the viewpoints management view builds a definition through structured fields
  (identity, criteria groups, connection selection, presentation) rather than hand-written
  YAML, and previews the plain-language summary live as you edit.
- **MCP** — `artifact_viewpoint` (`arch-repo-write`), actions `create`/`edit`/`delete`. The
  `definition` parameter is the full Appendix-A mapping; see
  [Viewpoints — schema reference](../reference/viewpoints-schema.md) for the grammar, or ask
  `artifact_help` for the `viewpoints` topic directly.
- **Direct YAML** — hand-editing `.arch-repo/viewpoints.yaml`. This is the one path that only
  gets *load*-time validation (structural correctness; registry drift is a warning, not a
  rejection) rather than the fuller save-time checks the GUI/MCP path enforces — see
  [Lifecycle & validation](../reference/viewpoints-schema.md#lifecycle--validation).

Module-shipped and enterprise-tier definitions are read-only from an engagement context; an
engagement repo authors its own definitions in its own `.arch-repo/viewpoints.yaml`. An edit
that changes `scope`, `query`, `presentation`, or `representation_types` requires a version
bump (enforced, not left to author discipline) — that's what makes the stale-pin warning
(W180) meaningful. Deleting a definition is blocked while any diagram/matrix still applies
it; detach those applications first.

Every MCP `artifact_query_viewpoint` `list` entry and every `create`/`edit` response through
`artifact_viewpoint` carries a **plain-language `query_summary`** — the same renderer the
GUI's live preview uses — so an agent (or a person reading raw YAML) sees what a viewpoint
*means*, not just its structure.

---

*Next: [Interfaces & MCP →](interfaces-and-mcp.md)*
