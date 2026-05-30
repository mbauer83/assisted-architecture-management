# Meta-Ontology V2 Plan: Diagram/Model Bindings

**Status**: design replacement for `PLAN-meta-ontology__SUPERSEDED.md`  
**Scope**: ontology modules, diagram modules, diagram-only entity and connection types, model bindings, C4 drill-down, UML activity/sequence diagrams, SysML/KerML integration.  
**Basis**: clean redesign. No backward compatibility with current C4/diagram handling is preserved; engagement and enterprise repos are migrated by a one-time tool (see "Redesign Constraints and Migration"). The verifier may therefore be strict from day one.

## Companion Documents

This file is the conceptual specification (the core model and the "why") **and** the live
progress checklist (see "Implementation Plan (live checklist)" below — the agent ticks
tasks off there). The reusable kickoff prompt lives in the project memory
`project_meta_ontology_v2_plan`. Detailed, pick-up-ready specs live alongside this file
under `plans/meta-ontology-v2/` so future sessions load only what they need:

- `IMPL-phases-0-2.md` — context-rich, file-level implementation guide for the
  non-deferred work (remove implicit mutation; bindings as the single correspondence
  mechanism; module-declared bindings + id-only derivations).
- `SPEC-phase-3-derivation-paths-materialization.md` — full spec for `path-projection`,
  connection-path refresh/equivalence, `scope-projection` + the concrete
  `c4.scope-projection` tables, and materialization.
- `SPEC-phase-4-sequence-sysml-bridges.md` — sequence diagram module, the bounded
  SysML/KerML model ontology slice, and the bridge-morphism coherence check.
- `FORMALIZATION.md` — the four categorical formalizations we actually implement (and why
  the rest stays vocabulary).

## Decision Summary

Do not tie how a diagram entity or diagram connection relates to the model to its
diagram entity type or diagram connection type. That relation is situative: it can
vary per diagram and often per element instance. The diagram module should define
what kinds of model entities or model connections an element may bind to, what
semantic correspondence kinds are meaningful, and what interaction defaults the UX
should offer. The chosen correspondence must live on the diagram element or on an
explicit binding record, not on the type.

Retain the current flat per-entity-type `diagram_entities` schema. Do not revive
`kind_data_root` as a storage model. The older plan's `kind_data_root` grouped
diagram elements by element class (`steps`, `swimlanes`, etc.); the current flat
schema stores each diagram-only entity type in its own top-level array. This is
simpler, stable under adding new types, and avoids conflating structural role with
persistence shape. Element classes should still exist, but as declared semantic
classes used for validation, rendering, creation guidance, and binding constraints.

## Redesign Constraints and Migration

This is a clean redesign. No backward compatibility with the current diagram/model
handling is preserved, which lets the "no silent model mutation" invariant be
satisfied by removing the offending code path rather than by layering a compatibility
shim over it:

- The current implicit model mutation — `build_scope_connections` /
  `apply_scope_connections` emitting `c4-contains` *model* connections as a side
  effect of every C4 diagram create/edit (called from MCP `write/diagram.py`, MCP
  `edit_tools.py`, and GUI `_diagram_write.py`) — is removed entirely. It directly
  violates the no-silent-mutation invariant and has no compatibility replacement.
- Diagram scope becomes a `scoped-by` binding, not a `_scope_entity_id` side effect.
  `_scope_entity_id` is not retained as runtime state; the migration converts it to a
  `scoped-by` binding.
- Per-item `entity_id` on diagram entities is not retained as stored data; the
  migration converts it to a `represents` binding. Nested `binding` shorthand (see
  "Core Conceptual Model") remains only as an authoring *input* convenience, normalized
  to top-level `bindings` on write — that is ergonomics, not stored compatibility.
- `c4-contains` is never written to the model implicitly. Inside a view it is a
  diagram-local or derived containment relation; when the user genuinely wants a model
  relationship it is produced only through the explicit materialization dry-run/commit
  path.

Migration is a one-time, repository-level operation run against both engagement and
enterprise repos (including this repo's own self-model under `engagements/ENG-ARCH-REPO/`):

1. For each diagram, synthesize `represents` bindings from legacy `entity_id` fields
   and a `scoped-by` binding from `_scope_entity_id`; assign stable binding ids.
2. Report and remove model connections that were previously auto-emitted as scope side
   effects (`c4-contains`), unless a specific one is explicitly retained as a real model
   connection. The migration must list every deletion; it must not silently drop model
   data.
3. Re-run the verifier and reject the migration if any diagram references a non-existent
   diagram element or model target.

Because there is no compatibility path, a diagram either uses the new `bindings` model
or fails validation.

## Core Conceptual Model

The system should treat architecture work as two primary graphs plus explicit
correspondence data:

1. **Model graph `M`**: persistent architectural/system entities and relationships,
   loaded from ontology modules such as ArchiMate, future SysML/KerML modules, C4
   semantic modules, or local domain modules.
2. **Diagram graph `D`**: diagram-owned nodes, diagram-owned edges, layout,
   diagram-role state, visual representation, and interaction-local data.
3. **Bindings/correspondences `B`**: first-class records implementing spans,
   profunctor-like relations, or selected functorial projections between `D` and
   `M`. `B` is an engineering representation of the relation between the graphs,
   not a third ontology peer.

The local `entity_id` field remains a convenient simple case, but the future
design needs richer bindings for diagram roles, model paths, selected model sets,
reproducible derivation bases, and connection correspondence. Pending creation is
an explicit command/transaction, not a persisted binding property.

Canonical bindings are top-level in diagram frontmatter:

```yaml
bindings:
  - id: bind-1
    subject: {kind: entity, id: c4-container-web}   # kind: entity | connection | diagram
    correspondence_kind: represents
    target:
      entity_id: APP@...

  - id: bind-2
    subject: {kind: connection, id: dep-web-db}
    correspondence_kind: abstracts
    target:
      connection_ids:                       # v1: an explicit set of model connections
        - APP@...---APP@...@@flow
        - APP@...---DOB@...@@access
      # connection_path: [...]  # Phase 3 ordered-path form; see SPEC-phase-3

  - id: bind-3                               # diagram-level scope (the whole diagram)
    subject: {kind: diagram}                 # no id — the diagram itself is the subject
    correspondence_kind: scoped-by
    target:
      entity_id: APP@...
      # or, for an unbound C4 drill-down sketch:
      # diagram_local: {element_id: sketch-system-1}
```

A binding has three structural parts. `subject` says what the binding is *about*:
`{kind: entity|connection, id: <diagram-local id>}` for a diagram-owned element, or
`{kind: diagram}` (no id) for a diagram-level binding such as C4 scope. `target` is the
union described under "Binding Semantics" — a model entity/connection/set/(Phase 3) path,
or a `diagram_local` element reference for diagram-local scope (e.g. an unbound drill-down
whose scope is a sketch element, not yet a model entity). `correspondence_kind` is the
claim relating subject to target.

`correspondence_kind` is the semantic claim the binding makes. It answers "what
does this diagram element mean with respect to the model?" It is not a process
state and not a derivation mechanism.

For authoring convenience, tools may accept nested shorthand on diagram elements:

```yaml
diagram_entities:
  container:
    - id: c4-container-web
      label: Web App
      binding:
        correspondence_kind: represents
        target: {entity_id: APP@...}
```

The write path should normalize nested shorthand into top-level `bindings`.
Renderers and validators should consume the normalized form.

Nested binding shorthand is especially useful for AI agents. It lets an agent
produce one local object at a time:

- create a diagram-owned entity;
- state its intended model target next to it;
- avoid manually coordinating a separate top-level binding list while drafting;
- rely on the write path to assign/validate binding ids, normalize references,
  reject ambiguous shorthand, and return the canonical form.

This improves authoring ergonomics without weakening the canonical model. The
agent-facing guidance should explicitly say: nested `binding` is accepted for
simple one-element bindings, but canonical persisted output is top-level
`bindings`.

Comparative evaluation:

| Representation | Strengths | Weaknesses | Recommendation |
|---|---|---|---|
| Top-level `bindings` | Handles entity and connection bindings uniformly; supports many-to-many bindings, one diagram element to multiple model targets, multiple diagram elements to one model target, connection-path targets, diagram-level scope bindings, and cross-element bindings. Easier to validate globally and refresh/diff derived views. | Slightly less convenient for hand-authoring a single node; requires stable diagram element ids. | Use as canonical persistence format. |
| Nested per diagram entity/connection | Easy to read and edit locally; natural for simple one-to-one bindings; UI forms map directly to the edited element. | Breaks down for connection paths, one-to-many/many-to-one correspondences, diagram-level scope, derived-view refresh, and bindings involving several diagram elements. Harder to validate uniqueness and global consistency. | Allow only as input shorthand if useful; normalize on write. |
| Hybrid canonical + shorthand | Good UX without losing formal clarity; existing tools can accept concise element-local binding specs while storage remains uniform. | Requires a normalization step and clear error messages when shorthand cannot express a binding. | Preferred implementation path. |

Top-level bindings also make the category-theoretic interpretation cleaner:
bindings are a relation/span/profunctor between diagram elements and model
targets, not hidden properties of diagram nodes. Nested shorthand is syntax; the
semantic object is still the global correspondence relation.

Core correspondence kinds:

| Kind | Semantics | Needed for | Not for |
|---|---|---|---|
| `represents` | The diagram element is a view occurrence of the target model entity or connection. The model target is the identity-bearing subject; the diagram element supplies diagram role, notation, layout, aliases, and visual properties. | Directly using model entities/connections in a diagram, including C4 boxes or UML lifelines with diagram-specific SVGs/notation for existing ArchiMate/SysML elements. | Summaries of several elements, drill-down scope, weak references, or future creation intent. |
| `abstracts` | The diagram element intentionally summarizes, collapses, or projects one or more model targets into a less detailed diagram element. The target may be a set of model elements or a connection path; identity is not one-to-one. | C4 `uses` edges derived from ArchiMate dependency paths; a high-level C4 software system summarizing several lower-level model elements; overview diagrams hiding detail. | A direct one-to-one view occurrence; use `represents` instead. |
| `refines` | The diagram element adds more specific structure, behavior, or scenario detail for an existing model target without yet claiming identity with a newly created model element. It is the diagram-side counterpart of a model element at a less detailed level. | Sketch-first drill-down, activity/sequence scenarios that elaborate an ArchiMate behavior element, or C4 component sketches elaborating an application component before materialization. | Model elements that already exist at the refined level; bind those with `represents`. |
| `scoped-by` | The diagram or diagram element is interpreted within the boundary/context of the target model entity. The target is not being drawn by this binding; it defines the view context. | C4 drill-down scope: a container diagram scoped by a software system, a component diagram scoped by a container, or a behavior diagram scoped by a process/service. | A visible node/edge for that model target; use `represents` for the visible occurrence. |
| `traces-to` | Weak traceability: the diagram element is relevant to the model target for navigation, impact analysis, evidence, or audit, but no identity, abstraction, refinement, or scope claim is made. | Linking diagram-local notes, imported observations, scenarios, tickets, requirements, or discovered facts to model elements when a stronger correspondence would be false. | Any case where `represents`, `abstracts`, `refines`, or `scoped-by` applies. |

Selection rule:

1. Use `represents` when the diagram occurrence is exactly a view of the target.
2. Use `scoped-by` when the target supplies context/boundary rather than a visible
   occurrence.
3. Use `abstracts` when the diagram element is deliberately less detailed than
   the model target set or path.
4. Use `refines` when the diagram element is deliberately more detailed than the
   model target and should not yet be treated as a model element in its own right.
5. Use `traces-to` only as the residual weak relation for navigation/evidence.

These five kinds are intentionally not a replacement for model relationships.
SysML `satisfy`, ArchiMate `serving`, UML `dependency`, allocation, containment,
composition, and similar domain relations should be model connections when the
system is making a model claim. A binding only states how a diagram element
corresponds to model content.

Module-defined correspondence kinds are allowed only when a module can state a
semantics not expressible by the core five and provide validation rules or
guidance. Examples that should usually remain module/domain model relations, not
core binding kinds: `satisfies`, `allocated-to`, `annotates`, `depends-on`,
`contains`, and `realizes`.

Keep binding metadata orthogonal:

- No persisted `mode`: semantic meaning is `correspondence_kind`; derivation,
  materialization, synchronization, and review state are separate concerns.
- No binding `status`: a canonical binding exists only after acceptance. Store
  unaccepted matches as proposals only if a saved review queue is needed.
- No required per-binding `provenance` or `evidence`: current audit/impact data
  already lives in diagram frontmatter, dry-run write results, query outputs, and
  git history. Add actor-level audit at a write-event log if needed.
- Use diagram-level `view_derivations` for generated bindings, referenced per binding by
  `derived_from`. A per-binding `derivation_basis` is deferred out of the v1 schema (see
  "Binding Semantics"); it returns only if a binding ever needs a recipe differing from
  every diagram-level derivation.
- No generic `query_id`: derivations name a registered `strategy` +
  `strategy_version` with explicit parameters. Opaque query strings are not
  valid derivation specs.
- `renderer-reference-collection` is not a derivation. It is an implementation
  side effect for collecting `entity-ids-used` and `connection-ids-used`.

## Derived Views

The plan must support diagrams that are auto-derived from the model and later
edited by inclusion/exclusion, layout, diagram-only annotations, and binding
changes. This requires a first-class diagram-level view specification, not only
per-element bindings.

Add optional `view_derivations` to diagram frontmatter:

```yaml
view_derivations:
  - id: derive-main
    strategy: c4.scope-projection
    strategy_version: 1
    source_model_snapshot:
      repo_scope: both
      root_entity_id: APP@...
    parameters:
      diagram_type: c4-container
      max_hops: 1
      pre_filters:
        connection_classes: [serving, flow, access]
        direction: outbound
    selection:
      included_entity_ids: [APP@..., DOB@...]
      excluded_entity_ids: [APP@...]
      included_connection_ids: []
      excluded_connection_ids: []
    generated_at: "2026-05-30"
```

Use plural `view_derivations` to avoid painting the format into a corner, not
because multiple derivations should be common. Normal diagrams have zero
derivations (manual/sketch) or one derivation (model-derived view with manual
additions/overrides). Multiple derivations are exceptional and intentional, e.g.
a C4 scope projection plus a separately derived risk overlay; the UI should
discourage accidental multiple derivations because refresh/conflict handling is
harder.

`view_derivations` defines how the system can recompute candidates. The existing
`entity-ids-used` and `connection-ids-used` remain the persisted snapshot of what
the diagram currently references. They are not enough by themselves for refresh,
because they do not say how the view was derived or which candidates were
deliberately excluded.

Terminology:

- A **model entity** is a persisted model element with a canonical artifact id.
- A **model connection** is a persisted model relationship with a canonical
  connection id.
- A **diagram entity/connection** is a persisted diagram-local element or visual
  occurrence with a diagram-local id.
- A **candidate** is an ephemeral proposed diagram item produced by evaluating a
  `view_derivations` strategy before the user/tool caller accepts, rejects, or
  edits it. In v1, candidates correspond only to model entities and canonical model
  connections, each addressed by an existing `artifact_id`. Path targets are deferred —
  but the reason is refresh semantics, not identity; see "Connection-path targets and
  the real deferral". Do not use `subgraph` as a target/selection concept until it is
  specified elsewhere.

Do not persist generic `candidate_ids` unless the system defines a stable
candidate-id scheme. Prefer typed selection fields:

- `included_entity_ids` / `excluded_entity_ids` for model entity candidates;
- `included_connection_ids` / `excluded_connection_ids` for model connection
  candidates.

This avoids confusing candidate identity with model or diagram identity.

Semantics of each `view_derivations` entry:

- `id` is a stable local id referenced by bindings generated from that derivation.
- `strategy` identifies the candidate-selection strategy.
- `strategy_version` pins refresh behavior to a versioned definition.
- `source_model_snapshot` identifies the model scope and repository scope used
  for derivation; later implementations may add model revision/hash metadata.
- `parameters` are strategy-specific inputs and filters.
- `projection` is supplied by the diagram module or explicitly referenced by the
  strategy; it maps model entity/connection types/classes and accepted
  connection paths to diagram entity/connection types and default correspondence
  kinds.
- `selection` records user/tool inclusion and exclusion decisions so refresh can
  distinguish new candidates from deliberately rejected candidates.
- `generated_at` is informational; it is not provenance for individual bindings.

Filtering semantics:

- `pre_filters` constrain candidate generation before traversal/projection. They
  are strategy inputs and should use stable model/module concepts: entity
  types/classes, connection types/classes, direction, hop/path limits, status,
  repo scope, and diagram-module projection options.
- `selection` is post-generation curation. It records user/tool decisions after
  candidates have been proposed: include this entity, exclude that connection,
  keep this manual element, or override a default correspondence.
- Refresh must reapply the same `pre_filters`, recompute candidates, then apply
  `selection` as persisted user intent. New candidates appear as proposed
  additions; excluded candidates stay excluded unless explicitly re-included.
- Strategy definitions must state which filters they support. Unsupported filters
  are validation errors, not ignored hints.

Per-binding derivation reference:

```yaml
bindings:
  - id: bind-web
    subject: {kind: entity, id: c4-container-web}
    correspondence_kind: represents
    target: {entity_id: APP@...}
    derived_from: derive-main
```

`derived_from` is the lightweight per-binding source reference and the only derivation
field in v1. It should point to a `view_derivations.id`; it must not duplicate the full
strategy parameters. Bindings without `derived_from` are manual, imported, or
diagram-local correspondences. A per-binding `derivation_basis` (a self-contained recipe
differing from every diagram-level entry) is deferred out of the v1 schema and added only
if that case becomes real.

Mixed-source diagrams:

- Diagram-only entities have no binding and no `derived_from`.
- Manually bound model entities have bindings without `derived_from`.
- Elements created by a derivation have bindings with `derived_from`.
- Elements created by one derivation and then manually reclassified keep
  `derived_from` for refresh/explanation but may override correspondence kind or
  diagram type if the user explicitly changed it.
- Elements materialized from diagram-local elements receive a normal `represents` binding
  to the newly created model target atomically on the materialization commit; they may
  record `created_from` in a future write-event log, but do not need a derivation reference.

Conflict prevention and resolution:

- A diagram element may have multiple bindings only when the correspondence kinds
  and target forms are compatible. Example: one `represents` binding to a model
  entity plus one `traces-to` binding to a requirement may be valid; two
  competing `represents` bindings to different model entities are invalid unless
  the diagram type explicitly allows a composite representation.
- A model target may appear in multiple diagram elements only when the diagram
  module permits multiple visual roles. Otherwise the write path should reject
  duplicate `represents` bindings or require the user/tool caller to mark one as
  an intentional duplicate role.
- A derived candidate that conflicts with a manual element must not overwrite it.
  Refresh should report a conflict: keep manual, replace with derived, merge
  binding, or keep both as separate visual roles.
- Manual edits beat refresh by default. A refresh can propose changes, but it
  must not silently change a manually altered correspondence kind, diagram type,
  label, visual role, or diagram-local property.
- If two derivations propose the same model entity/connection, the system should
  de-duplicate to one diagram occurrence by default and record both derivation
  sources only if both matter for refresh/explanation. If their projections
  disagree on diagram type or correspondence kind, present a conflict.
- If two derivations propose different diagram edges for the same model
  connection/path, de-duplicate only when the diagram module says the projections
  are equivalent. Otherwise keep them separate or require user resolution.
- Selection exclusions are strategy-local. Excluding an entity from one
  derivation does not globally ban manual use or use by another derivation.

Core derivation strategies:

| Strategy | Candidate-set semantics | Required/typical parameters | Projection semantics | Use-cases |
|---|---|---|---|---|
| `explicit-selection` | Candidate set is exactly the supplied model entities and optionally supplied model connections, plus required helper entities such as valid ArchiMate junctions. | `entity_ids`, optional `connection_ids`, `repo_scope`, diagram type. | Direct model entities/connections normally project to diagram occurrences with `represents` bindings. | User chooses exact model elements for a view. |
| `local-neighborhood` | Candidate set is found by bounded graph traversal from one or more roots. | `root_entity_ids`, `max_hops`, optional type/class filters, `direction`, `repo_scope`. | Reached model entities/connections normally project directly; filters determine what is visible. | "Show the context around this component/process/system." |
| `incident-connections` | Candidate set is the connections incident to selected entities, plus required endpoint entities. It is edge incidence, not recursive traversal. | `entity_ids`, `direction`, optional connection type/class filters, `repo_scope`. | Incident model connections project as visible edges or as candidates for inclusion in an existing view. | Add/show relationships touching selected elements. |
| `path-projection` | Candidate set is canonical model connections found on constrained paths between roots/endpoints. Accepted bindings may record the resulting connection path. | `source_entity_ids`, optional `target_entity_ids`, `max_path_length`, allowed connection types/classes, path policy, `repo_scope`. | Paths usually project to abstract diagram connections with `abstracts` bindings and `target.connection_path`. | C4 dependency edges from ArchiMate paths, impact paths, trace paths. |
| `scope-projection` | Candidate set is produced by a diagram-module projection from a model scope root. | `scope_entity_id`, `diagram_type`, module projection id/version, included/excluded ids, `repo_scope`. | Diagram module defines node projection, edge projection, scope binding, drill-down rules, and default bindings. | C4 container/component views, SysML internal views, bounded ArchiMate views. |

These strategies are orthogonal by candidate-selection principle:

- `explicit-selection` starts from user-provided sets.
- `local-neighborhood` starts from recursive traversal around roots.
- `incident-connections` starts from non-recursive edge incidence.
- `path-projection` starts from constrained paths between endpoints.
- `scope-projection` starts from a scoped diagram-module projection.

Diagram modules may register extension strategies, but each extension must
declare its strategy signature, version, selection semantics, parameters,
projection rules, output target forms, default correspondence kinds, and refresh
behavior. `c4-scope-graph` should therefore become a C4 module extension of
`scope-projection`, for example `strategy: c4.scope-projection`, formally
defined by C4 node projection, edge projection, drill-down, and selection
policies.

A `view_derivations` entry specifies the view; its strategy is only the
candidate-selection/projection algorithm inside that view recipe, not an
independent view specification.

Derived view process:

1. Evaluate a `view_derivations` strategy such as `explicit-selection/v1`,
   `local-neighborhood/v1`, `incident-connections/v1`, `path-projection/v1`,
   `scope-projection/v1`, or a diagram-module extension such as
   `c4.scope-projection/v1`.
2. Produce candidate diagram nodes, candidate diagram connections, bindings, and
   a proposed `view_derivations` entry.
3. Let the user/tool caller include, exclude, reclassify, or keep elements
   diagram-local.
4. Persist the diagram snapshot, bindings, and selection state.
5. On refresh, rerun the strategy, compare the new candidate set to the stored
   snapshot and selection state, and present a diff. Do not silently mutate the
   diagram or model.

Derived connections must be explicit about their target form:

- If the diagram edge directly views one model connection, bind with
  `correspondence_kind: represents` and `target.connection_id`.
- If the diagram edge summarizes several model connections, bind with
  `correspondence_kind: abstracts` and `target.connection_ids` (an explicit set).
  Summarizing a *path* (`target.connection_path`) is Phase 3, together with its
  refresh semantics (see `plans/meta-ontology-v2/SPEC-phase-3...`).
- If the edge is diagram-local despite being suggested by traversal, persist no
  binding or use `traces-to` only if weak traceability is useful.
- If the user chooses to create a model connection from the diagram edge, use the explicit
  materialization transaction (dry-run preview, then atomic create-and-bind); see
  SPEC-phase-3 §3.

C4 model-derived views specifically need module-provided derivation rules:

- scope resolution: how the diagram's `scoped-by` binding determines the model root;
- node projection: which model entity types/classes become C4 people, systems,
  containers, or components;
- edge projection: which model connection types/classes or paths become C4
  relations;
- drill-down: which child diagrams can be derived from a selected C4 element;
- selection policy: how included/excluded ids are persisted and refreshed.

The concrete projection tables for all three C4 levels are fully specified in
`plans/meta-ontology-v2/SPEC-phase-3-derivation-paths-materialization.md` §2.3.

The implementation still needs concrete schemas, validators, write-tool
extensions, refresh diffing, and connection-path binding support. Refresh runs on the
read/query surface — it only proposes a diff — and should reuse the existing artifact
index rather than rescanning repos; large-scope `local-neighborhood` / `path-projection`
derivations must bound traversal via their declared filters, and the UI should warn when
a derivation's candidate set is large rather than silently truncating it.

## Types, Classes, and Classes of Connections

Keep entity types and entity classes conceptually separate:

- An **entity type** is a concrete authoring and persistence type, for example
  `application-component`, `business-process`, `c4 container`, `uml action`,
  `sysml part definition`, or `sysml action usage`.
- An **element class** is a declared meta-class/tag used for constraints and
  generic behavior, for example `structure-element`, `behavior-element`,
  `passive-structure-element`, `step`, `lifeline`, `message-end`, `requirement`,
  `definition`, or `usage`.
- A type can have multiple classes. A class is not a substitute for a type.
- Ontology modules and diagram modules must explicitly declare the classes they
  introduce before types can use them.

Generalize this from entity-only classes to **classes** covering both entity
types and connection types. Connection types need the same discipline:

- A **connection type** is a concrete persisted relation or diagram relation,
  for example ArchiMate `serving`, C4 `uses`, UML `control-flow`, UML `message`,
  SysML/KerML `feature membership`, or `flow connection usage`.
- A **connection class** is a semantic/structural class for relations, for
  example `dependency`, `containment`, `flow`, `trace`, `message`, `control-flow`,
  `refinement`, `allocation`, or `view-correspondence`.
- Use the field name `classes` for both entity types and connection types. The
  enclosing declaration determines whether the classes apply to entities or
  connections. If a class is valid for only one element kind, declare that in the
  class definition; do not encode it in a different field name.

## Module Specification Responsibilities

Ontology modules should specify:

- Declared entity types, connection types, entity/connection classes,
  properties, permitted relationships, and creation policy for the model graph.
- Creation guidance, required properties, required relationships, defaults, and
  validation constraints for each model entity type and connection type.
- Optional view hints, but not diagram-instance binding decisions.

All model entity types and connection types are creatable through the same unified
API/GUI/MCP creation paths unless the repository's global write policy forbids
model mutation. Ontology modules must not create per-channel creatability rules.

Diagram modules should specify:

- Diagram-owned entity and connection types.
- Allowed model target entity types/classes for each diagram entity type.
- Allowed model target connection types/classes, paths, or graph queries for each
  diagram connection type.
- Allowed `correspondence_kind` values and target forms for those elements, plus
  defaults and UX guidance.
- Registered view-derivation strategies, including strategy signature, version,
  candidate-selection semantics, projection rules, parameters, output target
  forms, default correspondence kinds, and refresh behavior.
- Rendering roles and visual representations, including per-diagram-type SVGs or
  PlantUML rendering templates.
- Required diagram-local relationships independent of model persistence, for
  example activity steps in lanes or sequence messages between lifelines.

Diagram modules may constrain admissible correspondence kinds and target forms,
but should rarely force a single one. For example, a regulatory traceability
diagram may require every node to have a model target; a sketch-oriented C4
context diagram should allow unbound elements, direct model elements, diagram
roles over model elements, and explicit materialization from diagram elements.

Two clarifications keep this aligned with the existing module system rather than
introducing parallel concepts:

- **Bridges are the evolution of `permitted_mappings.sources`, not a new mechanism.**
  The existing `MappingSourceSpec` (`ontology` + `entity_type`/`entity_class` +
  `transparent`, in `src/domain/ontology_types.py`) already expresses "this diagram
  type may map to model types from ontology X." A bridge adds a name, a version, and a
  declared class-preservation claim the registry can check; it does not replace the
  YAML mechanism diagram modules already use. Implementers should extend
  `permitted_mappings.sources`, not build a second alignment system beside it.
- **Diagram-owned connection types are diagram-local by default.** The connection types
  a diagram module declares in its `ontology.yaml` (e.g. activity's `step-flow`,
  `step-in-lane`, `step-note-of`) are never model connections and need no binding. A
  connection binding is the *exception*, used only when a diagram edge corresponds to
  model content. "Connection bindings are first-class" means they are supported, not
  that every diagram edge requires one.

## Binding Semantics

Persist bindings using orthogonal fields:

- `subject`: what the binding is about — `{kind: entity|connection, id: <diagram-local
  id>}` for a diagram-owned element, or `{kind: diagram}` (no id) for a diagram-level
  binding such as C4 scope.
- `correspondence_kind`: semantic relation between subject and target, one of the core
  kinds (`represents`, `abstracts`, `refines`, `scoped-by`, `traces-to`) or a
  module-defined kind with explicit semantics.
- `target`: a tagged union — `entity_id`, `connection_id`, `connection_ids` (explicit
  set), `connection_path` (Phase 3; see SPEC-phase-3), or `diagram_local`
  (`{diagram_id?, element_id}`, defaulting to the current diagram) for diagram-local
  scope such as an unbound drill-down. Model-entity/connection targets reuse the existing
  canonical ids.
- `derived_from`: optional lightweight reference to a diagram-level `view_derivations.id`.
  Manual/imported bindings omit it.

Two fields are **deliberately deferred out of the v1 schema** because no concrete
semantics exists for them yet, and adding them now would invite silent-sync assumptions:

- `derivation_basis` (a per-binding replay recipe) — only needed if a binding ever has a
  recipe differing from every diagram-level derivation; until that case is real, use
  `derived_from`.
- `sync_policy` — returns only when an explicit synchronization semantics is designed and
  implemented. Until then derived views are refreshed by the explicit refresh/diff
  operation and bindings carry no sync state.

A query-result target form is **not** a persisted target. Query/traversal results are
proposal-only: returned by guidance to suggest candidate bindings, never stored as a
binding `target`, consistent with the "no generic `query_id`" decision. A query that
should be replayable must be expressed as a registered `view_derivations` strategy.

Silent mutation of the model from diagram edits is forbidden. Creating or changing
model entities/connections from diagram interactions must be an explicit command
with a preview/diff in GUI, REST, and MCP.

Unbound diagram elements do not need bindings. They are simply diagram elements
without model targets. Candidate matches produced by search or traversal should be
returned by guidance/proposal operations and applied only when the user/tool caller
accepts them.

## Identity, Integrity, and Verifier Rules

Top-level bindings reference diagram elements and model targets by id, so identity and
referential integrity are first-class, not implied. The system already enforces
referential integrity for `entity-ids-used` / `connection-ids-used`
(`src/application/verification/artifact_verifier_rules.py`); bindings extend that
discipline rather than bypassing it.

Diagram element id contract:

- Every diagram-owned entity and connection has a diagram-local `id` that is stable for
  the life of the element. The write path preserves existing ids on edit and never
  regenerates them; new ids are assigned only to new elements.
- A binding's `subject` must resolve: for `kind: entity|connection`, `subject.id` is a
  live diagram element of that kind; for `kind: diagram` there is no element to resolve
  (the diagram itself is the subject). Deleting a diagram element cascades to the bindings
  whose subject is that element; a binding must never outlive its subject element.

Verifier rules (strict from day one, since no compatibility path exists). These are
verifier *rules*, not only tests — the running verifier rejects violating artifacts on
index and on write:

- `binding.subject` resolves per the contract above; no dangling element-subject bindings.
- `binding.target` resolves: `entity_id` is a known entity id in scope; `connection_id`
  is a known connection `artifact_id`; every member of a `connection_ids` set is present;
  a `diagram_local` target resolves to a live diagram element (in the named diagram, or
  the current one); (Phase 3) a `connection_path` is a valid orientation-tagged path in
  scope.
- `correspondence_kind` is one of the core five or a module-declared kind, and is listed
  in the diagram type's `allowed_bindings` for that subject's type and target form.
- At most one `represents` binding per element subject, unless the diagram type
  explicitly allows a composite representation.
- At most one `scoped-by` binding with `kind: diagram` subject per diagram.
- A model target has at most one `represents` occurrence per diagram **unless** the module
  declares the subject's entity type in `visual_roles` (see below). When it does, multiple
  `represents` bindings to the same target are allowed, each carrying a distinct
  `visual_role` label; the verifier requires the labels to be distinct and drawn from the
  declared role set. This replaces ad-hoc duplicate exceptions with one explicit mechanism.
- `derived_from` references an existing `view_derivations.id`; each
  `view_derivations.strategy` is registered with a matching `strategy_version`, and all
  of its `pre_filters` are supported by that strategy (unsupported filters are errors,
  not ignored hints).
- No diagram write produces or mutates a model entity or connection. Model mutation is
  reachable only through the explicit materialization command with a preview/diff.

## Binding UX

The UI must make correspondence kinds understandable without making users learn
category theory or ontology jargon. Diagram creation and editing should expose
intent-first choices:

- **Use existing model element/connection** -> create a `represents` binding.
- **Summarize selected model detail** -> create an `abstracts` binding to a model
  target set or connection path.
- **Elaborate this model element in a new diagram/local detail** -> create a
  `refines` binding.
- **Set this diagram's scope/boundary** -> create a `scoped-by` binding.
- **Add weak trace/reference** -> create a `traces-to` binding.
- **Keep diagram-local only** -> no binding.
- **Create model element/connection from this diagram element** -> show a dry-run using
  existing model write semantics; commit atomically creates the model target and attaches
  the selected correspondence (`represents` by default) in one transaction.

The editor should prefer defaults from the diagram module, but every binding
operation should show the selected correspondence kind, target, and consequences:
whether the model will be mutated, whether the diagram can be refreshed from the
model, and whether the binding is one-to-one or abstracts/refines multiple
targets. MCP and REST should expose the same choices as compact enum fields in
existing create/edit tools, backed by guidance output.

## Connection Bindings

Connection bindings are first-class. A diagram connection may be diagram-local
(no binding), directly `represents` a canonical model connection, `abstracts` over
an explicit connection set (Phase 3: a path), `refines` an abstract relationship with
scenario detail, `traces-to` a weak audit/impact target, or become input to explicit
model connection materialization. Binding targets therefore need variants for
`connection_id`, an explicit `connection_ids` set, endpoint pair plus connection type
for validation/search, and connection path (Phase 3). Query/traversal results are
proposal-only and are never a persisted target. Persisted model connection targets reuse
the **existing** canonical connection id — the
`ConnectionRecord.artifact_id` already produced throughout the codebase
(`src/application/artifact_parsing.py:238`,
`src/infrastructure/write/artifact_write/connection.py:196`):

```text
{source_entity_id}---{target_entity_id}@@{connection_type}
```

This is not a new identity scheme. A binding targets the connection's existing
`artifact_id`; the `---`/`@@` string is that id's format, not a parallel address.
Validation reuses the existing connection-id checks (`_check_connection_ids_used` in
`artifact_verifier_rules.py`). If the model later permits multiple same-type edges
between the same source and target, extend the canonical id with an occurrence id
rather than inventing anonymous triples.

The module-level policy should describe allowed target forms and correspondence
kinds, not process states:

```yaml
allowed_bindings:
  connection:
    c4-uses:
      target_connection_types: [serving, flow, access, association]
      target_connection_classes: [dependency, flow]
      correspondence_kinds: [represents, abstracts, traces-to]
      target_forms: [connection-id, connection-ids]   # connection-path added in Phase 3
      default_correspondence_kind: abstracts
  entity:
    container:
      visual_roles: [primary, replica]    # optional; omit to forbid duplicate represents
```

`model_mutation` is not a per-binding policy: no-silent-mutation is a global invariant
(materialization is always the only explicit path), so an `explicit_only` flag here would
be redundant. `target_path_queries` / `query-result` are likewise absent — query results
are proposal-only (above). `visual_roles`, when present on an entity type, is the explicit,
module-declared mechanism that permits multiple `represents` bindings to one model target,
each tagged with a distinct `visual_role` from the list; omitting it keeps the strict
one-occurrence default.

`default_correspondence_kind` is **required** for every `allowed_bindings` entry and is
machine-checked: it must be a member of that entry's `correspondence_kinds`. It is the
backbone of the AI-authoring path. An agent creating a diagram element normally omits
`correspondence_kind` and lets the module default apply, overriding only when it
deliberately means something other than the default. The same default drives the human
"intent-first" UX (see "Binding UX"). Guidance tools surface the default and the
admissible set per (diagram-entity-type, target-form) so neither humans nor agents must
infer correspondence semantics. This keeps the agent's hardest decision — which of the
five kinds applies — a deliberate override rather than a mandatory per-element choice.

Binding a C4 `uses` edge to an ArchiMate path should not automatically create an
ArchiMate relationship. Conversely, creating an ArchiMate serving/flow/access
relationship from a C4 edge is valid only after an explicit user/tool decision
selects the connection type, endpoints, and required properties.

### Connection-path targets and the real deferral

The original deferral was framed as "stable path identity." That framing is wrong: a
path target needs no new id. Every model connection already has a canonical
`artifact_id` (`{source}---{target}@@{type}`), so a path is simply an *ordered list* of
existing connection ids — `target.connection_path: [id1, id2, ...]`. Identity is
solved by reuse.

What is genuinely deferred to Phase 3 is path **refresh/equivalence semantics**: when
the underlying graph changes (an intermediate hop is added, removed, or rerouted), the
system must decide whether an `abstracts`-over-path binding still corresponds to "the
same" abstraction or has gone stale, and present that as a diff. Defining that
equivalence relation — and the `path-projection` strategy that produces and re-derives
such paths — is the deferred work.

Consequently, **v1 `abstracts` targets an explicit connection *set***
(`target.connection_ids`), whose refresh is a straightforward set-membership
diff: members that vanished are flagged, new incident connections are proposed,
excluded ones stay excluded. Path targets are added only together with their refresh
semantics in Phase 3. This keeps the central C4 use case (a `uses` edge abstracting
several ArchiMate dependencies) expressible from day one, without committing to
path re-derivation before it is specified.

## Realistic Engagement Modes

The architecture must support these modes without changing conceptual model:

- **Sketch-first C4**: user creates C4 context/container/component diagrams with
  diagram-only entities and edges. Later they accept candidates or materialize
  selected entities/connections into ArchiMate, C4 semantic model elements, or
  SysML/KerML elements.
- **Model-first diagramming**: user starts from an existing ArchiMate/SysML model,
  runs a graph query/traversal, accepts or filters candidates, and creates a C4,
  ArchiMate, activity, sequence, or SysML view.
- **Reverse architecture**: imported/runtime/discovered dependencies become model
  candidates; diagrams are used to curate and promote selected facts into the
  model graph.
- **Progressive enrichment**: a diagram begins with unbound or sketch entities,
  selected elements are bound, and later drill-down diagrams introduce new
  lower-level entities.
- **Strict governance**: diagram elements must be model-backed before publication;
  unbound elements are allowed only as draft candidates.
- **Diagram-local documentation**: diagrams intentionally contain local notes,
  grouping, layout, aliases, summaries, and views that should never become model
  entities.

GUI/REST/MCP should expose the same conceptual capabilities through existing
guidance, model-write, and diagram-write surfaces wherever possible:

- model and diagram guidance tools must expose module-provided binding guidance,
  target constraints, correspondence kinds, and visual-role guidance;
- existing model creation/edit tools remain the unified way to create model
  entities and connections, with dry-run previews;
- existing diagram creation/edit tools should accept diagram-owned elements,
  direct model references, and binding records;
- graph traversal/search can return candidate binding proposals as part of
  diagram authoring guidance or diagram dry-runs;
- materializing model elements/connections from diagram elements is an explicit
  dry-run/commit path layered onto existing creation tools, not a new family of
  MCP tools;
- refreshing derived views is a diagram edit/preview operation that shows a diff
  before changing persisted diagram data.

Avoid creating a new MCP tool family unless existing tools cannot be minimally
extended. Tool descriptions should remain short and refer to schema-backed module
guidance instead of embedding long ontology explanations.

Concretely, the new verbs fold into existing tools as arguments and modes, not new
tools — keeping the tool count and description length small, which the agent-facing
design depends on:

- `artifact_create_diagram` / `artifact_edit_diagram` gain an optional `bindings`
  argument (top-level form) and accept nested `binding` shorthand on diagram elements.
- `artifact_edit_diagram` gains a `mode` for binding-only operations:
  `propose-bindings` (returns candidates + a diff, persists nothing),
  `refresh-derivation` (re-derives a `view_derivations` entry, returns a diff),
  `apply-diff`, and `detach-binding`.
  **Statelessness + concurrency rule** (this is the precise stale-write contract):
  `propose-bindings` / `refresh-derivation` return a *self-contained* diff — the full set
  of proposed binding/selection changes plus a `base_revision` (the diagram artifact's
  content hash at derivation time). The server persists no review queue. `apply-diff`
  echoes that diff back (the client holds the state, optionally after trimming individual
  proposals it rejects) and the server applies it **only if** the diagram's current
  revision still equals `base_revision`; otherwise it returns a stale-diff conflict and
  the client must re-run propose/refresh against the new revision. Any `diff_id` is a
  content hash for logging/idempotency, never a server-held handle.
- Materialization is one explicit transaction layered on `artifact_create_entity` /
  `artifact_add_connection` via a `from_diagram_element` reference: the dry-run previews
  the new model element/connection *and* the binding; commit creates the model content and
  attaches the `represents` binding **atomically** — never a two-step where the caller
  binds afterwards. See SPEC-phase-3 §3.
- `artifact_authoring_guidance` returns the module `allowed_bindings`, default
  correspondence kinds, and admissible target forms, so tool descriptions stay short.

Every schema change here regenerates `types.generated.ts` (pre-commit-enforced) and
must update the GUI binding editors and REST contracts in lockstep; the typed frontend
contract is part of the change, not a follow-up.

## Cross-Repo Bindings and Promotion

The two-tier repository model (engagement drafts; enterprise shared state) is the
system's defining feature, so bindings and derivations must define cross-repo behavior
explicitly rather than leaving it implicit.

- A binding's `target` may resolve in the engagement repo, the enterprise repo,
  or — for derivations with `repo_scope: both` — either. The verifier resolves targets
  against the same scope rules the existing entity/connection-id checks use: an
  enterprise target is valid from an engagement diagram, but an engagement-only target
  is not valid from an enterprise diagram.
- Promotion of a diagram from engagement to enterprise must revalidate its bindings:
  every `target` must resolve in enterprise scope after promotion. A binding to an
  engagement-only entity blocks promotion until that entity is itself promoted,
  mirroring the existing connection-promotion conflict handling.
- Promotion never silently materializes model content from diagram bindings. An
  `abstracts` / `refines` / `traces-to` binding carries no model claim and is promoted
  as diagram data; only explicitly materialized model entities/connections travel
  through the model promotion workflow.
- A derivation's `source_model_snapshot.repo_scope` is part of its replay recipe. After
  promotion, or after the enterprise model changes, refresh re-derives candidates in the
  new scope and presents a diff; it does not assume the old candidate set still holds.
- Detecting that a bound enterprise entity moved or changed is the same staleness
  problem as derived-view refresh: surface it as a diff, never auto-rewrite.

## C4 Drill-Down and ArchiMate Interoperation

C4 has an explicit drill-down workflow: system context -> container -> component
and sometimes code. A C4 diagram element can therefore be:

- a diagram-local sketch of a potential model element;
- a role/view of an existing ArchiMate application component/service/data object;
- a C4 semantic entity if we add a C4 ontology module;
- a derived projection from an ArchiMate graph;
- a pending request to create an underlying ArchiMate or C4 semantic entity.

Recommended policy:

- C4 diagram modules should remain permissive for early sketching.
- C4 `person`, `software-system`, `container`, and `component` types should
  declare allowed model targets by entity type and element class.
- C4 drill-down scope is a `scoped-by` binding to a model entity (or to a diagram
  entity for unbound sketches), never a raw `_scope_entity_id`. `_scope_entity_id`
  survives only as write-time input shorthand normalized to a `scoped-by` binding; it is
  not stored.
- Creating a lower-level C4 diagram from an unbound higher-level entity should be
  allowed, but the new diagram must record that its scope is diagram-local until
  materialized or bound.
- Creating a lower-level C4 diagram from a bound model entity derives candidates from the
  model graph via `c4.scope-projection` and allows user filtering before persistence (see
  `plans/meta-ontology-v2/SPEC-phase-3...`).
- `c4-contains` is **not** a model connection. Containment is recomputed at projection
  time from existing ArchiMate structural relations (composition/aggregation), rendered as
  diagram-local nesting; a real model relationship is produced only by explicit
  materialization. The old auto-emitted `c4-contains` model edge is removed (Phase 0).

For ArchiMate, C4 containers may map to application components, application
services, technology nodes, artifacts, or data objects depending on intent. That
choice is not inherent in the C4 diagram type alone; the module should specify
allowed targets and the instance should record the selected target and
correspondence kind.

## UML Activity and Sequence Diagrams

Activity diagrams require behavior modeling, not just visual flow. ArchiMate
already has behavior, active structure, passive structure, groupings, and junctions
including AND/OR-style helpers. Therefore activity diagram nodes should be able
to bind to ArchiMate business/application/technology behavior elements, active
structure performers, passive data/object elements, and grouping/junction helpers
where appropriate.

Activity-specific recommendations:

- `action`, `decision`, `fork`, `partition`, `swimlane`, and `note` remain
  diagram-owned types.
- Activity edges such as flow, then/else, fork branch, containment, and lane
  membership remain diagram-local by default.
- Selected actions may bind to ArchiMate behavior elements or SysML actions.
- Swimlanes may bind to active structure elements or roles.
- Fork/decision nodes may bind to ArchiMate junction-like helpers only when the
  user explicitly wants model-level control semantics; otherwise they stay
  diagram-local.

Sequence diagrams introduce temporality and event ordering. A lifeline can be a
role/view of an ArchiMate actor/component/service, SysML part/port, or diagram-only
participant. A message can bind to a model relationship, operation, flow, service
call, event, or an abstract path. Message occurrences and execution specifications
are usually diagram-local unless the ontology module explicitly supports them as
model behavior elements.

The binding framework must support ordered/event-like diagram elements without
forcing every visual occurrence into the underlying model graph. The sequence diagram
module — diagram-owned types, `sequence_index` ordering, and which elements may bind — is
fully specified in `plans/meta-ontology-v2/SPEC-phase-4-sequence-sysml-bridges.md` §1.

## SysML and KerML Integration

SysML v2 is based on KerML and has a more formal semantic core than SysML v1.
OMG lists SysML v2.0 and KerML 1.0 formal specifications with September 2025
publication dates. SysML v2 also standardizes textual syntax and an API, which
matches this repository's need for machine-actionable modules and MCP/REST access.

Design implications:

- Treat KerML as a candidate high-rigor ontology foundation, not merely another
  diagram notation.
- Represent SysML/KerML definitions/usages, memberships, features, actions,
  requirements, flows, allocations, and views as model ontology types and
  connection types/classes.
- Do not encode SysML/KerML semantics only as diagram-only types. Diagrams should
  be views over a model where possible, with diagram-local elements only for
  notation, layout, temporary sketches, or incomplete authoring.
- Binding records should be able to target SysML/KerML entities and relationships
  the same way they target ArchiMate.
- C4 diagrams should be able to create or bind to SysML/KerML elements when a
  systems-engineering engagement wants C4 as a lightweight authoring surface.

SysML/KerML also strengthens the case for explicit type/class separation:
definition-vs-usage, membership, feature typing, and specialization should not be
flattened into ad hoc diagram entity types.

The bounded first slice — the in-scope definition/usage entity types, the KerML
membership/relation connection types with their classes, the ArchiMate alignment bridges,
and what is deliberately excluded — is specified in
`plans/meta-ontology-v2/SPEC-phase-4-sequence-sysml-bridges.md` §2.

## Categorical/Formalization Research Synthesis

The main category-theoretic value is not "drawing diagrams with category theory";
it is designing a coherent specification language for ontology modules, diagram
modules, bindings, and derivation rules. The formalization target is the
meta-ontology and module system.

Useful mathematical frames for the specification language:

- **Institutions and heterogeneous specification**: the right high-level model
  for supporting ArchiMate, SysML/KerML, UML-like diagrams, C4, and local domain
  modules without pretending they share one logic. An institution separates
  signatures, sentences/constraints, models, and satisfaction. This maps well to
  module specs: signatures are entity/connection types and classes; sentences
  are permitted relationships, cardinalities, binding admissibility constraints,
  and creation/validation rules; models are repository instances and diagram
  instances; satisfaction is validation.
- **Specification morphisms / interpretations**: a module import, refinement, or
  bridge should be a structure-preserving map between signatures/theories. This
  is the principled home for "C4 container may represent ArchiMate
  application-component or service" and "SysML action can refine ArchiMate
  behavior".
- **Sketches and finite-limit/finite-colimit sketches**: useful for the concrete
  shape of the specification language. Entity types, connection types, endpoint
  maps, required properties, required connections, and binding target forms can
  be represented as a typed sketch whose models are valid ontology/diagram module
  instances.
- **Fibrations and indexed categories**: central, not peripheral. They model
  instances typed over module signatures: for each ontology or diagram signature
  there is a fiber of valid instances; changing/importing/interpreting a module
  reindexes instances along a morphism. This is the categorical form of "all
  model entities, diagram entities, and bindings are checked against the module
  that types them."
- **Polynomial functors / containers / indexed containers**: relevant to the
  ontology-description language because module declarations are structured
  containers: a type has property slots, endpoint slots, role slots, child slots,
  binding target slots, and renderer slots. Indexed containers are especially
  relevant because allowed slots depend on the entity/connection/diagram type.
  This can guide JSON Schema generation, recursive diagram-owned structures, and
  future type-theoretic formalization.
- **Structured/decorated cospans**: relevant to module composition when modules
  are treated as open theories with declared interfaces. A module can expose an
  import/export boundary of shared classes, types, or bridge concepts; composing
  modules then resembles gluing open systems along their interfaces. Decorated
  cospans are also relevant when a diagram module contributes an internal
  structure/renderer/derivation decoration over a boundary shared with model
  ontology modules.
- **Colimits/pushouts for module composition**: merging ontology modules or
  combining a diagram module with imported model ontologies should be expressed
  as a pushout/colimit over explicitly shared concepts, not by global name
  merging. This gives a formal account of conflict detection: two modules cohere
  only when their shared mappings make the relevant diagrams commute and the
  combined theory has models.
- **Descent / sheaf-like gluing**: relevant for coherence checking across local
  module views. If a diagram module, ArchiMate ontology, SysML ontology, and C4
  bridge each specify overlapping constraints, the registry should verify that
  these local specifications agree on overlaps and can be glued into a consistent
  global module context. This is the conceptual basis for "local module validity
  plus compatible overlaps implies global validity"; it does not require
  implementing full stack semantics initially.
- **Pullbacks for constrained views**: a diagram view can be seen as a selection
  constrained by both the diagram module and the model ontology. Pullbacks over
  shared type/class/binding constraints are a useful model for computing the
  admissible diagram elements and connections.
- **Profunctors/spans/relations**: appropriate for bindings and alignments where
  correspondence is partial, many-to-many, or abstraction-like rather than a
  total structure-preserving interpretation.

Useful mathematical frames for diagram/view behavior:

- **Diagrams as functors**: categorically, a diagram of shape `J` in a category
  `C` is a functor `J -> C`; morphisms of diagrams are natural transformations.
  This is directly relevant: a concrete visual diagram can be treated as a
  diagram-shaped selection/projection over a model category or typed graph.
- **Ologs**: categorical knowledge-representation diagrams provide a lightweight
  way to document ontology concepts and typed relationships without starting with
  a heavy theorem-prover formalization.
- **Functorial projections and natural transformations**: model-derived diagrams
  can be described by view/projection functors. Refreshing or comparing two
  diagram derivations can be understood as naturality/coherence conditions between
  such functors when the mapping is sufficiently structure-preserving.
- **Limits and colimits**: pullbacks are a useful model for combining diagram and
  model facts through shared bindings; pushouts are a useful model for explicit
  materialization/merge operations when diagram-created elements are committed
  into the model.
- **Structured/decorated cospans**: relevant for compositional open systems. A
  cospan can represent a system with an interface/boundary; decorations carry
  internal structure or behavior. This fits C4/SysML drill-down better than a
  plain graph when diagrams expose a scoped boundary and internal components.
  For example, a C4 container diagram scoped by a software system can be read as
  an open system whose boundary is the system interface and whose decoration is
  the internal container/dependency graph. This is also relevant to the
  specification-language level when diagram modules are open modules composed
  with model ontology modules along shared interfaces.
- **Behavioral mereology**: useful as a warning and a possible future formal
  lens. Part-whole structure of behavior is not identical to structural
  containment of entities. Activity partitions, sequence fragments, C4
  drill-downs, ArchiMate behavior elements, and SysML actions all raise questions
  about when a behavior is a part, refinement, scenario, trace, or projection of
  another behavior. This supports keeping `abstracts`, `refines`, and `scoped-by`
  separate, and avoiding automatic conversion of diagram containment into model
  composition.
- **Triple graph grammars**: still useful operationally for source graph, target
  graph, and correspondence data, but this should be treated as an implementation
  technique for spans/correspondences, not as the primary conceptual ontology.
- **Bidirectional transformations/lenses**: useful for controlled get/put
  semantics, but dangerous if interpreted as automatic write-back. Use lenses
  only where an explicit sync policy exists.
- **Double-pushout graph rewriting / adhesive categories**: useful for formally
  specifying graph edits, materialization rules, and safety conditions for create,
  delete, and rewrite operations.

Pragmatic recommendation:

- Treat each ontology or diagram module as a small theory/signature with models.
- Use institution-inspired structure without implementing a full theorem prover:
  signatures, constraints, models, satisfaction/validation, and morphisms.
- Use sketches or typed attributed graphs as the implementable substrate.
- Treat the registry as a fibration-like index from module signatures to valid
  instances; every model entity, connection, diagram element, and binding lives
  over a type in a module signature.
- Use polynomial/container thinking for the schema language: declarations should
  describe shape plus typed positions/slots, because this directly maps to
  validation schemas, authoring forms, and recursive diagram structures.
- Use descent-style checks for module coherence: validate local modules, validate
  declared overlaps/bridges, and reject combinations whose overlap constraints
  cannot be glued consistently.
- Use colimits/pushouts only for explicit module composition over declared
  shared concepts, never for accidental name merging.
- Use pullbacks/intersections for computing admissible diagram/model bindings.
- Use spans/profunctors for general bindings; use functors only for mappings that
  truly preserve structure.
- Use decorated or structured cospans as the leading formal candidate for scoped
  open modules, scoped open-system views, and drill-down composition, especially
  C4 and SysML.
- Treat behavioral mereology as a modeling discipline for behavior part-whole and
  refinement claims, not as a new persistence mechanism.
- Use lenses only for explicitly synchronized views.
- Defer topos-level or full dependent type semantics until there is a smaller
  executable core worth proving.

At the higher module level, model ontologies and diagram ontologies should be
treated as typed signatures/categories over a shared meta-ontology. A module
contributes a category/signature `O_i` with a structure-preserving map
`O_i -> Meta`. Coherence between modules is then expressed by commuting diagrams,
shared subtheories, pullbacks over common concepts, and explicit bridge functors
or profunctors where concepts intentionally correspond without being identical.
This is a better fit than forcing all ontology modules into one global flat type
hierarchy.

Specification-language consequences:

- A module must declare its signature: entity types, connection types, classes,
  properties, endpoint kinds, binding target forms, and view-derivation
  strategies.
- A module should distinguish its boundary/interface from its internal
  declarations. Imports, exported classes/types, and bridge points are explicit
  interfaces, not incidental YAML references.
- A module must declare constraints separately from guidance: permitted
  relationships, required relationships, cardinalities, required properties,
  admissible correspondence kinds, and valid target forms.
- A module import/extension must be a named morphism, not a textual include.
- Cross-ontology reuse must happen through explicit bridge morphisms or
  alignments. Example: C4 `container` maps to a set of allowed ArchiMate
  application/technology/passive-structure types through a bridge, not by making
  C4 a subtype of ArchiMate.
- The registry validates coherence by checking that all referenced types/classes
  exist, endpoint constraints are satisfiable, bridge mappings preserve declared
  classes/relationships where they claim to, and the combined module has at least
  one model under the repository's validation semantics.
- Coherence is not only global name resolution. It includes descent-like overlap
  checks: if two modules both constrain a shared type/class/bridge concept, their
  constraints must agree or have an explicit resolving refinement.
- Recursive and dependent schema fragments should be represented as typed
  containers: for each declared type, list its typed positions/slots, their
  cardinalities, and the index/type family that determines allowed fillers.
- Diagram guidance and MCP guidance are generated from the same module theory:
  create/never-create text is documentation, but permitted bindings,
  relationships, and derivation rules are machine-checkable constraints.

Which of these we actually implement now — and which stay vocabulary — is decided in
`plans/meta-ontology-v2/FORMALIZATION.md` (F1–F4: signature/instance typing, bridge
morphism with class preservation, bindings as a constrained relation, and derivation as
a pure function with testable refresh laws). Each maps 1:1 onto phase work and yields a
verifier rule or a property test. The steps below are the broader roadmap that subset is
drawn from.

Lean 4 or cubical Agda can be useful later, but not as the first implementation
step. A realistic formalization path is:

1. Define a small institution-inspired and fibration-aware core: signatures,
   constraints, models, satisfaction, module morphisms, bridge alignments, and
   instance fibers over module signatures.
2. Specify validity predicates: type membership, class membership, permitted
   relationships, binding target admissibility, view-derivation validity,
   cardinality, and no-silent-mutation.
3. Define module/interface composition using explicit interfaces and pushouts
   over declared shared concepts; add descent-style overlap checks before
   accepting combined module contexts.
4. Define schema declarations as typed containers/indexed containers where useful
   for properties, endpoints, child positions, and binding target positions.
5. Define view-derivation strategies as morphisms/relations from model instances to
   diagram instances, plus stored selection state.
6. Model scoped diagrams as structured/decorated cospans where this improves the
   account of boundaries, interfaces, and drill-down composition.
7. Specify operations: propose binding, accept binding, materialize entity,
   materialize connection, refresh derived view, detach binding.
8. Prove preservation for these operations against the validity predicates.
9. Only then evaluate whether Lean 4, Agda, or a lighter property-test/model-check
   harness gives the best cost/benefit.

## Current Flat Schema vs. `kind_data_root`

Do not revive `kind_data_root` as persistence shape. It stores by structural
class, which mixes storage, role, and class membership; multi-class entity types
become ambiguous and class changes become data migrations. Keep the current flat
per-entity-type schema:

```yaml
diagram_entities:
  swimlane:
    - id: lane-1
      label: Customer
  action:
    - id: step-1
      label: Submit order
  decision:
    - id: dec-1
      label: Valid?
```

This is easier to validate, easier to migrate, and better aligned with
situative per-instance bindings. Renderers and validators can still query by
class through ontology metadata. If authoring needs class-grouped views, add
derived read models or renderer helpers, not persistent `kind_data_root` arrays.

## Implementation Plan (live checklist)

This is a clean redesign (see "Redesign Constraints and Migration"). The phases are
ordered so each is independently shippable and verifiable, and so the hardest dependency —
connection-path refresh semantics — is isolated to a later phase rather than blocking the
core binding work.

**This checklist is the single source of truth for progress.** The implementing agent
marks a task `[x]` here once it is done *and* its gates pass, appending
` — YYYY-MM-DD, <commit>, <one-line note>`. Execute top-to-bottom; a task tagged
`(after #N)` waits for #N. The reusable kickoff prompt is stored in the project memory
`project_meta_ontology_v2_plan` (deliberately not here — this is the file the agent edits,
so keeping the prompt elsewhere avoids a doc that both instructs and is the mutation
target). **Model:** default Opus 4.8 / high; the one task tagged `(Sonnet 4.6 / extended)`
is mechanical and gate-fenced. Build-ready detail: Phases 0–2 → `IMPL-phases-0-2.md`;
Phase 3 → `SPEC-phase-3-...`; Phase 4 → `SPEC-phase-4-...`; property tests → `FORMALIZATION.md`.

### Phase 0 — Groundwork
- [x] **1.** Unify `classes` (mechanical codemod) — rename per-type membership
  `element_classes`/`classifications` → `classes` via scoped, validated regex (indentation
  separates the column-0 declaration block; word boundaries protect `ElementClass*`). Full
  recipe + gates: IMPL §0.0. *(Sonnet 4.6 / extended.)* — 2026-05-30, 7e9c547, 604 tests green, zuban clean; types.generated.ts unchanged (fields not in TS schema)
- [x] **2.** Delete `build_scope_connections`/`apply_scope_connections` and call sites (MCP
  `write/diagram.py`, `edit_tools.py`, GUI `_diagram_write.py`); no diagram write may touch
  a model connection. IMPL §0.1. — 2026-05-30, 4b71cf0, 604 tests green, zuban clean; c4-contains removed from TS types
- [x] **3.** *(after #4)* Migration tool + run on engagement + enterprise repos: legacy
  `entity_id`→`represents`, `_scope_entity_id`→diagram-level `scoped-by`, report+remove
  auto-emitted `c4-contains`. IMPL §0.2. — 2026-05-30, 6aeb1ea, 663 tests green, zuban clean; repos already clean (0 changes needed)

### Phase 1 — Bindings as the single correspondence mechanism
- [x] **4.** `Binding`/`BindingSubject`/`Target` model + top-level `bindings` schema;
  accept nested `binding` shorthand normalized on write. IMPL §1.1–1.2. — 2026-05-30, 0e812c7, 654 tests green, zuban clean; bindings.py + binding_normalize.py; entity_id removed from entity schema guidance
- [x] **5.** `entity_id`/`_scope_entity_id` are write-time input shorthand only; persisted
  output is always top-level `bindings`. IMPL §1.3. — 2026-05-30, fd5706e, 681 tests green, zuban clean; bindings wired through create/edit/parse; strip_diagram_shorthand added
- [x] **6.** Verifier rules (`_check_bindings`) per "Identity, Integrity, and Verifier
  Rules". IMPL §1.4. — 2026-05-30, 318d224, _verifier_rules_bindings.py E401–E408; wired into check_diagram_references_scoped; 27 tests green
- [x] **7.** Rewire renderers + `collect_references` to read `represents` bindings; regen
  `types.generated.ts`; update GUI editors. IMPL §1.5. — 2026-05-30, 9bcec71, bindings param added to collect_references Protocol + all renderers; scope injection in diagram.py/edit.py; 14 tests; types.generated.ts unchanged

### Phase 2 — Module-declared bindings and id-only derivations
- [x] **8.** `allowed_bindings` (target types/classes, correspondence kinds, target forms,
  required `default_correspondence_kind`) + `visual_roles`. IMPL §2.1. — 2026-05-30, d7ce3e9, AllowedBindingsSpec + parser + C4/activity YAML declarations; E406 uses module kinds per entity type; E408 respects visual_roles; 761 tests green, zuban clean
- [x] **9.** `view_derivations` frontmatter + validation. IMPL §2.2. — 2026-05-30, 71cf06e, ViewDerivation model + StrategyRegistry stub + E409–E413 verifier rules; full write/parse/MCP path; 799 tests green, zuban clean
- [x] **10.** Strategy registry + `explicit-selection`/`local-neighborhood`/
  `incident-connections`; `abstracts` targets connection sets. IMPL §2.3. — 2026-05-30, b5c6165, CandidateSet + ModelQuery protocol; 3 strategies self-register; 44 tests; 843 total green, zuban clean
- [x] **11.** Refresh/diff with `base_revision` stale-write rule + `propose-bindings`. IMPL §2.4. — 2026-05-30, 1b8fa70, compute_revision+DerivationDiff+SelectionDelta+4 modes on artifact_edit_diagram; replace_bindings param; 17 tests; 860 green, zuban clean
- [x] **12.** Enrich guidance/search/traversal to return binding proposals without
  persisting. IMPL §2.4. — 2026-05-30, 8fe9ddc, binding_proposals.py; propose-bindings enriched with allowed_bindings+index; find_neighbors gains diagram_type param; 9 tests; 869 total green, zuban clean

### Phase 3 — Paths, scope projection, materialization (specs complete)
- [x] **13.** `connection_path` target (`{id, reversed}`) + `path-projection/v1` +
  refresh/equivalence. SPEC-phase-3 §1. — 2026-05-30, 0d1eef7, E409/E410 verifier + path-projection/v1 BFS/DFS + drifted/broken path diff + included/excluded_paths selection; 26 tests; 895 total green, zuban clean
- [x] **14.** `scope-projection/v1` + `c4.scope-projection/v1` tables. SPEC-phase-3 §2. — 2026-05-30, c092279, scope_projection.py (generic dispatcher + module projection registry) + c4_scope_projection.py (3 C4 levels, nesting via archimate-composition/aggregation); 20 tests; 915 total green, zuban clean
- [x] **15.** Materialization atomic transaction (entity + connection). SPEC-phase-3 §3. — 2026-05-30, 7b7c66e, materialization.py + from_diagram_element on artifact_create_entity/artifact_add_connection; entity rollback on diagram update failure; 18 tests; 933 total green, zuban clean

### Phase 4 — New ontologies and coherence (specs complete)
- [ ] **16.** Activity clarification + sequence diagram module. SPEC-phase-4 §1.
- [ ] **17.** `sysml_v2_min` ontology module. SPEC-phase-4 §2.
- [ ] **18.** *(after #8, #17)* Bridge declaration + minimum bridge check. SPEC-phase-4 §3.
- [ ] **19.** Cross-phase property/validation tests (F1–F4). FORMALIZATION.md.

## References

- ISO/IEC/IEEE 42010 architecture description correspondences and correspondence
  rules:
  https://standards.iteh.ai/catalog/standards/iso/838cdce5-fc0d-4e32-9b4e-b0cfd11c5a2d/iso-iec-ieee-42010-2011
- UML abstraction, refine, and trace terminology:
  https://www.uml-diagrams.org/abstraction.html
- Institutions and heterogeneous specification:
  https://ncatlab.org/nlab/show/institution and
  https://www.lfcs.inf.ed.ac.uk/reports/86/ECS-LFCS-86-10/
- Colimit-based specification/module structuring:
  https://era.ed.ac.uk/handle/1842/6633
- Category-theoretic ontology merging and alignments:
  https://corescholar.libraries.wright.edu/cse/26/ and
  https://www.dfki.de/en/web/research/projects-and-publications/publication/3849
- Sketches for specification:
  https://ncatlab.org/nlab/show/sketch and
  https://www.epatters.org/wiki/algebra/sketches
- Fibrations and indexed categories:
  https://www.epatters.org/wiki/algebra/fibered-category-theory and
  https://ncatlab.org/nlab/show/categorical%2Bsemantics%2Bof%2Bdependent%2Btype%2Btheory
- Polynomial functors / containers:
  https://mat.uab.cat/~kock/cat/datatypes.html and
  https://topos.institute/blog/2021-07-01-jump-monads/
- Descent and gluing:
  https://ncatlab.org/nlab/show/descent
- Diagrams, functors, and natural transformations:
  https://ncatlab.org/nlab/show/diagram and
  https://categorytheory.gitlab.io/functor_and_natural_transformation.html
- Decorated and structured cospans:
  https://arxiv.org/abs/2304.00447 and
  https://ncatlab.org/nlab/show/decorated%2Bcospan
- Behavioral mereology:
  https://arxiv.org/abs/2101.10490 and
  https://golem.ph.utexas.edu/category/2019/06/behavioral_mereology.html
- Ologs as categorical knowledge representation:
  https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0024274
- Multilevel typed graph transformation:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC7314735/
- Triple graph grammars and correspondence graphs:
  https://link.springer.com/article/10.1007/s10270-024-01238-1
- Bidirectional transformations/lenses overview:
  https://en.wikipedia.org/wiki/Bidirectional_transformation
- Double-pushout graph rewriting and adhesive graph transformation:
  https://handwiki.org/wiki/Double_pushout_graph_rewriting and
  https://journals.sagepub.com/doi/abs/10.3233/FUN-2006-74102
- OMG SysML v2 and KerML specification index:
  https://sysml.org/sysml-specs/ and https://www.omg.org/spec/SysML/
