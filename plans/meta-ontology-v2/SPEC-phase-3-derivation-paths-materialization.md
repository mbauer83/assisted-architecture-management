# Phase 3 Specification — Paths, Scope-Projection, Materialization

Companion to `PLAN-meta-ontology-v2.md`. This document fully specifies the Phase 3
deferred work so it can be implemented without further research or open decisions.
Read the main plan's "Derived Views", "Connection Bindings", and "Identity, Integrity,
and Verifier Rules" sections first; this document only adds the concrete algorithms.

Phase 3 has three deliverables:

1. `path-projection/v1` strategy + connection-path target form + path refresh/equivalence.
2. `scope-projection/v1` strategy + the `c4.scope-projection/v1` module extension with
   concrete projection tables.
3. The materialization operation (diagram element → new model entity/connection).

---

## 1. Connection-path targets and `path-projection/v1`

### 1.1 Target form

```yaml
target:
  connection_path:                  # ordered, orientation-tagged steps
    - {id: id1, reversed: false}    # traversed in canonical model edge direction
    - {id: id2, reversed: true}     # traversed against the model edge direction
```

Each `id` is the existing canonical `{src}---{tgt}@@{type}`. The `reversed` flag resolves
the orientation ambiguity that arises once `direction: any`/`inbound` traversal exists: a
step's effective `from`/`to` is the model `(source, target)` when `reversed: false`, and
the swap when `reversed: true`. Well-formedness (verifier):

- every `id` exists in scope; `reversed` defaults to `false`;
- the list is a **contiguous chain under orientation**: for consecutive steps `a, b`,
  `to(a) == from(b)`, where `from`/`to` honor each step's `reversed` flag;
- the path endpoints `from(step1)` and `to(step_last)` equal the model targets of the bound
  diagram edge's source/target diagram elements (resolved through their `represents`
  bindings).

A path needs no new identity scheme: it *is* its ordered `(id, reversed)` list. Two path
targets are **equal** iff those lists are identical. For purely directed traversal
(`direction: outbound`) every `reversed` is `false` and the form degenerates to a plain
ordered id-list.

### 1.2 Strategy signature

`strategy: path-projection`, `strategy_version: 1`. Parameters:

| Param | Required | Meaning |
|---|---|---|
| `source_entity_ids` | yes | path start endpoints |
| `target_entity_ids` | no | path end endpoints; if omitted, any node reachable within `max_path_length` is an endpoint candidate |
| `max_path_length` | yes | maximum number of edges (hops) |
| `allowed_connection_types` / `allowed_connection_classes` | no | edge filter; at least one form should be set in practice |
| `direction` | no (default `outbound`) | `outbound` / `inbound` / `any` |
| `path_policy` | no (default `shortest`) | `shortest` / `all-simple` / `class-priority` |
| `dedupe_parallel` | no (default `true`) | collapse multiple policy-equivalent paths per endpoint pair |
| `repo_scope` | no (default `both`) | `engagement` / `enterprise` / `both` |

Supported `pre_filters` (validation rejects any others): `connection_types`,
`connection_classes`, `direction`, `max_path_length`, `repo_scope`.

### 1.3 Candidate generation

For each ordered endpoint pair `(s, t)` with `s ∈ source_entity_ids` and `t` an allowed
target, enumerate paths `s → … → t` of length `≤ max_path_length` whose every edge passes
the connection filter, traversing edges according to `direction` (`outbound` follows model
direction, `inbound` follows against it, `any` follows either and records `reversed` per
step). Select per `path_policy`:

- `shortest`: the minimum-edge path.
- `all-simple`: every simple (no repeated entity) path.
- `class-priority`: the path minimizing the summed `ConnectionTypeInfo.hierarchy_priority`
  of its edges (lower = preferred), then by length.

**Deterministic tie-break (mandatory for stable refresh).** Whenever the policy leaves a
tie, pick the path whose ordered `(id, reversed)` list is lexicographically smallest
(compare step by step). This makes candidate generation a pure deterministic function of
the model graph + parameters, which is what makes refresh idempotent (see §1.5).

### 1.4 Projection

Each selected path projects to one candidate diagram connection of the diagram type's
edge type, with `correspondence_kind: abstracts`, `target.connection_path: [{id, reversed},
...]`, and `derived_from: <view_derivations.id>`. The endpoint diagram elements must already be
`represents`-bound to the path endpoints; if absent, the derivation either also proposes
those endpoint nodes (when the projection covers them) or drops the path candidate and
logs it.

### 1.5 Refresh / equivalence (the previously-deferred core)

A stored path binding `b` is classified against a freshly recomputed candidate set
`C' = path-projection(params)`:

- **unchanged**: `b.path ∈ C'` (id-list equality) → keep, no diff entry.
- **drifted**: `b.path ∉ C'` but `b.path` is still well-formed (ids exist, chain intact).
  The abstraction still exists in the graph but is no longer policy-preferred. Diff entry
  offering: `{keep-as-manual-abstracts, replace-with-preferred(C' path for same
  endpoints), demote-to-traces-to, remove}`.
- **broken**: `b.path` is no longer well-formed (an id vanished or the chain is severed).
  Diff entry offering: `{replace-with-preferred(if a path between the same endpoints still
  exists), demote-to-traces-to(on the surviving endpoints), remove}`.
- **new**: `c' ∈ C'` matches no stored binding and is not excluded → propose addition.

**Path selection state.** Add typed selection fields to `view_derivations.selection`:
`included_paths` / `excluded_paths`, whose entries are the canonical joined step string
(`id1@fwd|id2@rev|...`, encoding each step's orientation). These keys are stable precisely
because of the §1.3 deterministic ordering, so they satisfy the main plan's "no generic
candidate_ids" rule — they are typed path keys, not opaque candidate ids. An excluded path
stays excluded across refreshes until explicitly re-included.

**Testable properties** (implement as property-based tests, see `FORMALIZATION.md` §4):
determinism of candidate generation; refresh idempotence (unchanged model + no new
selection ⇒ empty diff); selection monotonicity; and no model mutation during refresh.

---

## 2. `scope-projection/v1` and `c4.scope-projection/v1`

### 2.1 Generic strategy

`strategy: scope-projection`, `strategy_version: 1`. Parameters: `scope_entity_id`
(derived from the diagram's `scoped-by` binding), `diagram_type`, `projection_id` +
`projection_version` (names the module projection), the four typed selection fields, and
`repo_scope`. The generic strategy resolves the named module projection and delegates the
actual node/edge/drill-down logic to it. A diagram-module projection is a 5-tuple:

1. **scope resolution** — `scope_entity_id → root`; validate `type(root)` is admissible for
   the module's declared scope (directly or through a registered bridge, see Phase 4).
2. **node projection** `nodeProj(model_entity) → (diagram_entity_type, correspondence_kind) | ∅`.
3. **edge projection** `edgeProj(model_connection | path) → (diagram_conn_type, correspondence_kind) | ∅`.
4. **drill-down** `childDiagrams(diagram_element) → [(child_diagram_type, scope_entity_id)]`.
5. **selection policy** — reuse the typed `included_*` / `excluded_*` selection fields.

### 2.2 Containment without model mutation

The old `c4-contains` *model* connection is removed (Phase 0). Containment is recomputed at
projection time as a **derived** relation: an entity `x` is *internal* to `root` iff `x` is
reachable from `root` along ArchiMate structural relations of the diagram type's
`layout.nesting_connection_classes` (composition / aggregation; assignment for behavior),
within `max_depth` hops. `max_depth` is a projection parameter defaulting to **1** for all
three C4 levels (direct structural children — the C4 convention that a container/component
view shows one level of decomposition); a deeper value is opt-in per derivation. Internal
entities render nested inside the boundary; the nesting is diagram-local and/or derived,
never a stored model edge. If the user wants a real model relationship they materialize it
explicitly (§3).

### 2.3 `c4.scope-projection/v1` concrete tables

Derived from the current C4 `ontology.yaml` `permitted_mappings`, reframed as projection.
"Internal" = reachable from `root` via nesting classes (§2.2). "Neighbor" = connected to
`root` or an internal node by a serving/flow/triggering/access edge but not internal.

**c4-container** (scope type `software-system`; `root` = the application-component or
service the in-scope `software-system` represents):

| Source model entity | Role | → C4 node | kind |
|---|---|---|---|
| application-component / service (internal) | internal | `container` | represents |
| data-object (internal) | internal | `container` | represents |
| node (internal, technology) | internal | `container` | represents |
| application-component / service (neighbor) | neighbor | `software-system` (external) | represents |
| business-actor / role (neighbor) | neighbor | `person` | represents |

Edge projection: a direct serving/flow/triggering/access connection between two projected
nodes → `c4-uses` with `represents` + `target.connection_id`. A serving/flow/access
*path* that traverses hidden (non-projected) intermediate entities between two projected
nodes → `c4-uses` with `abstracts` + path target (§1; in Phase 2 this is a `connection_ids`
set, in Phase 3 a `connection_path`). Drill-down: `childDiagrams(container bound to E) =
[(c4-component, E)]` when `E` is an application-component.

**c4-component** (scope type `container`; `root` = the application-component the container
represents): node projection application-component / function / service (internal) →
`component` (represents); neighbors → `software-system` (represents). Edge projection as
above. Drill-down: none (code level is out of scope).

**c4-system-context** (scope type `software-system`; `root` = the application-component or
service): the `root` projects to the central in-scope `software-system` node; neighbors
reachable by serving/flow within one hop → `software-system` (external, represents);
business-actor / role → `person` (represents). Edge projection as above. Drill-down:
`childDiagrams(in-scope system) = [(c4-container, root)]`.

These tables are the complete `c4.scope-projection/v1` definition; no further mapping
decisions are required to implement it.

---

## 3. Materialization (diagram element → model entity/connection)

The only path that creates model content from a diagram. Always dry-run first, identical
semantics across GUI / REST / MCP. No new tool family — extend the existing creation tools.

**Atomicity (authoritative — the main plan defers to this).** Materialization is a single
transaction: creating the model element/connection and attaching the binding succeed or
fail together. There is no window in which a freshly created model element exists without
its binding, and no separate "caller binds afterwards" step. If the binding cannot be
attached (e.g. a concurrent edit removed the diagram element), the model create rolls back.

### 3.1 Entity materialization

Extend `artifact_create_entity` with an optional `from_diagram_element`:

```yaml
from_diagram_element:
  diagram_id: DGR@...
  diagram_element_id: c4-container-web
  diagram_element_kind: entity
target_type: application-component        # the model entity type to create
correspondence_kind_after: represents     # binding attached in the same transaction (default represents)
# normal create_entity args (name, domain, properties) default from the diagram element's
# label/properties but may be overridden.
```

- **Dry-run** returns the proposed entity (with the artifact_id the existing id-generator
  would assign), and the binding that will be attached.
- **Commit** (one transaction) calls the existing `create_entity` internals and attaches a
  `represents` binding from the diagram element to the new id, **replacing** any prior
  `refines` / `abstracts` binding on that element (it was a sketch; it is now a view of a
  real model element). `traces-to` bindings are left intact.

### 3.2 Connection materialization

Extend `artifact_add_connection` with the same `from_diagram_element`
(`diagram_element_kind: connection`) plus `connection_type`.

- Both endpoint diagram elements MUST already be `represents`-bound to model entities (you
  cannot create a model edge between non-model things). Validate `connection_type` is
  permitted between the two endpoint model types via the existing `permits_connection`.
- Dry-run returns the proposed connection (canonical `{src}---{tgt}@@{type}` id). Commit
  (one transaction) creates it via existing `add_connection` and attaches a `represents`
  binding to the diagram edge, replacing any prior `abstracts` / `refines` binding.

### 3.3 Invariants

- Materialization is explicit and previewed; no diagram write (create/edit/refresh) may
  reach it implicitly.
- After commit the diagram element is a normal `represents` binding indistinguishable from
  a model-first one. A future write-event log may record `created_from`; not required for
  Phase 3.
