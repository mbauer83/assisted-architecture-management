# Phase 4 Specification — Sequence Module, SysML/KerML Slice, Bridge Coherence

Companion to `PLAN-meta-ontology-v2.md`. Specifies the Phase 4 deferred work to a level
that needs no further research before implementation. Phase 4 has three deliverables plus
the activity-module clarification (which is small and stated inline in the main plan):

1. A sequence diagram-type module.
2. A bounded SysML v2 / KerML model ontology module (`sysml_v2_min`).
3. The first concrete cross-module coherence check: named bridge morphisms.

---

## 1. Sequence diagram module (`src/diagram_types/sequence/`)

Custom renderer (PlantUML sequence), same shape as `activity/`. Diagram-owned entity and
connection types; ordering is diagram-local; bindings are optional.

### 1.1 Diagram-owned entity types (`ontology.yaml`)

| Type | classes | Binding (optional) | Notes |
|---|---|---|---|
| `lifeline` | `participant` | `represents` → business-actor, role, application-component, application-service, node (and SysML `part-usage` once that module exists) | one column |
| `message` | `message` | `represents` → a model connection (serving/flow/triggering between the two lifelines' model targets), or `abstracts` over a connection set (Phase 3: a path), or none | carries `sequence_index: int` (total order) |
| `fragment` | `grouping` | none (diagram-local) | `kind ∈ {opt, alt, loop, par}`, `from_index`, `to_index` |
| `execution-spec` | `activation` | none | covers an index range on one lifeline |
| `note` | `annotation` | none | reuse annotation pattern (`embedding: property`) |

### 1.2 Diagram-owned connection types

- `seq-message` — the visible message edge; `embedding: none`. `permitted_relationships:
  [lifeline, lifeline, [seq-message]]`. The `message` entity owns required connections
  `seq-from` (→ lifeline, 1:1) and `seq-to` (→ lifeline, 1:1) — diagram-local, like
  activity's `step-in-lane`.

### 1.3 Temporality

Ordering is carried entirely by `message.sequence_index` (and fragment `from_index` /
`to_index`); the renderer sorts by it. The binding framework does **not** model time — this
is the concrete discharge of the main plan's requirement to "support ordered/event-like
diagram elements without forcing every visual occurrence into the model graph." Message
occurrences and execution specifications are always diagram-local in this slice; promoting
them to model behavior is out of scope until a behavior-ontology decision is made.

### 1.4 Renderer / references

`collect_references` reads `represents` bindings on lifelines and messages to populate
`entity-ids-used` / `connection-ids-used` (same mechanism as the rewired C4/activity
renderers in Phase 1). No scope-connection hook (that mechanism is deleted in Phase 0).

---

## 2. `sysml_v2_min` model ontology module

SysML v2 is large. This module is the **bounded first slice** that (a) interoperates with
ArchiMate behavior/structure and (b) lets C4 act as a lightweight authoring surface for
systems engineering. It is a normal `OntologyModule` under `src/ontologies/sysml_v2_min/`
following `src/ontologies/README.md`.

### 2.1 In-scope entity types (definition/usage pairs)

| Type | prefix | classes |
|---|---|---|
| `part-definition` | PDF | `definition`, `structure-element` |
| `part-usage` | PU | `usage`, `structure-element` |
| `action-definition` | ADF | `definition`, `behavior-element` |
| `action-usage` | AU | `usage`, `behavior-element` |
| `port-definition` | PODF | `definition`, `interface` |
| `port-usage` | POU | `usage`, `interface` |
| `item-definition` | IDF | `definition`, `passive-structure-element` |
| `item-usage` | IU | `usage`, `passive-structure-element` |
| `requirement-definition` | RDF | `definition`, `requirement` |
| `requirement-usage` | RU | `usage`, `requirement` |

### 2.2 In-scope connection types (with `classes`)

| Type | source → target | classes |
|---|---|---|
| `feature-membership` | definition → usage | `containment`, `membership` |
| `specialization` | definition → definition | `specialization` |
| `feature-typing` | usage → definition | `typing` |
| `flow-connection` | usage → usage | `flow` |
| `allocation` | usage → usage | `allocation`, `trace` |
| `satisfy` | requirement-usage → (usage \| definition) | `trace`, `satisfy` |

`permitted_relationships` follow directly from the source→target columns (use `@class`
wildcards: e.g. `["@definition", "@usage", [feature-membership]]`). All classes listed
here are declared in the module's `element_classes:` block (type/class-separation
discipline).

### 2.3 Bridges to ArchiMate (alignment only — see §3)

- `action-usage` ↔ ArchiMate business/application/technology behavior (`abstracts` /
  `represents` from activity & C4 diagrams).
- `part-usage` ↔ application-component / node.
- `satisfy` ↔ ArchiMate realization/influence is an **alignment**, not a subtype claim.

### 2.4 Explicitly out of the first slice

KerML expression/calculation semantics; the views & viewpoints engine; the SysML textual
notation parser; the SysML v2 REST/OSLC API surface; analysis/verification cases. These are
named here so a later session knows they were deliberately excluded, not forgotten.

---

## 3. Bridge morphisms and the first *minimum* bridge check

A bridge is the evolution of `permitted_mappings.sources` (main plan, "Module Specification
Responsibilities") with an identity, a version, and a checkable preservation claim. The
Phase 4 deliverable is the **first minimum bridge check** — a real executable check, but
deliberately not full module coherence (see §3.3).

### 3.1 Declaration

Declared by a diagram or ontology module (e.g. in the C4 module):

```yaml
bridges:
  - name: c4-container-to-archimate
    version: 1
    from: {module: c4, type: container}          # diagram-owned type
    to:
      module: archimate-next-snapshot1
      types: [application-component, service, data-object]
    preserves_classes: [structure-element]        # the claim to be checked
    correspondence_kind: represents
```

### 3.2 The minimum check (runs at registry build / `startup_validation.py`)

A structure-preservation law on the bridge map `β: from-type ⇀ ℘(to-types)`:

1. `from.type` exists in `from.module`.
2. every `to.type` exists in `to.module`.
3. **class preservation**: for each `c ∈ preserves_classes`, every `t ∈ to.types` has `c`
   in its `classes`. Violation ⇒ startup abort naming `(bridge, type, missing-class)`.
4. `correspondence_kind` is one of the core five or a module-declared kind.
5. **descent-style overlap**: the bridge `to.types` agree with that diagram type's
   `allowed_bindings` target types for the same element (two declarations of the same
   fact must not contradict). Disagreement ⇒ abort.

### 3.3 What the minimum check does NOT yet validate (deferred)

This is a first check, not full coherence. It deliberately does **not** validate, and a
later coherence pass must add:

- **endpoint compatibility** — that a bridged connection mapping respects the source/target
  entity types each connection type permits (`permitted_relationships`);
- **property / cardinality constraints** — that required properties and
  `required_connections` / cardinalities are preserved or satisfiable across the bridge;
- **directionality** — that a directed source relation maps to a directed target relation
  with consistent orientation;
- **connection-type mappings** — bridges between *connection* types (not just entity
  types), with their class and endpoint preservation.

Naming it the "minimum bridge check" keeps the plan honest: it is the first executable
slice of coherence, not a claim of full module coherence. The broader institution /
descent / colimit machinery in the main plan's categorical section stays vocabulary until
this proves out (see `FORMALIZATION.md` F2).

Implement the minimum predicate as a registry validation rule with unit tests over a
coherent fixture and a deliberately-incoherent fixture (a bridge claiming a class a target
type lacks).
