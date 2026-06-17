# Diagram-Type Modules

A diagram-type module declares which entity and connection types a view accepts and how it
renders. Most ArchiMate views are config-only; families with their own notation bring a
custom renderer. Full contract:
[`src/diagram_types/README.md`](../../src/diagram_types/README.md).

&nbsp;

## The `config.yaml` contract

```yaml
name: archimate-application      # registry key; matches diagram_type in artifacts
ontology: archimate_next         # ontology package supplying the base vocabulary
filter:
  hierarchy_level: { index: 0, values: [application, common] }   # which entity types appear
grouping:
  by_field: hierarchy_0
  stereotype_pattern: "{hierarchy_0|capitalize}Grouping"
layout:
  nesting_connection_classes: [nesting]   # draw children inside parent frames
  flow_connection_classes: [dynamic]      # draw directed flow arrows
guidance:
  when_to_use: "…"                         # returned to agents via artifact_authoring_guidance
  when_not_to_use: "…"
ui:
  label: "Application View"
  diagram_only_types: []                   # types that live only in the diagram
```

Only `name` is required; every other field falls back to a built-in default.

&nbsp;

## Rendering: config first, custom only when needed

The `GenericPumlRenderer` handles baseline config-backed PlantUML, and the shared
`ArchimatePumlRenderer` layers ArchiMate behaviour on top. You do **not** write a renderer for
a new domain view, a different filter, or different grouping/layout.

A custom renderer (implementing the `DiagramRenderer` protocol) is needed when the format is
not PlantUML ArchiMate (matrix tables, sequence, ER), when rendering needs entity-specific
logic config cannot express, or when the diagram owns diagram-scoped state that affects
rendering (activity swimlanes, C4 boundaries). The `matrix` type is the reference case: it
renders Markdown instead of PlantUML.

&nbsp;

## Diagram-only entity types

Some types exist only inside a diagram's `diagram-entities:` frontmatter and are never written
to the model store (swimlanes, sequence participants, C4 boundaries). They are declared in
`ontology.yaml` (structure and semantics) plus `config.yaml` (UI label and plural). Structural
links between them live in the diagram's `connections:` list, not as entity properties.

&nbsp;

## Diagram-owned connection types and connection bindings

A diagram module can declare **diagram-only connection types** — structural edges that live
in the diagram's `connections:` list rather than as model connections. They are declared in
`ontology.yaml` alongside entity types, and they carry the same metadata fields
(`relationship_kind`, `symmetric`, `puml_arrow`).

The `datatype` module is the reference case. It owns five `dt-*` connection types
(`dt-association` through `dt-dependency`), each tagged with a `relationship_kind` matching
the ArchiMate backing type family. When a `dt-*` edge connects two classifiers that are each
bound to a Data Object, the verifier checks that a backing model connection with a
corresponding `relationship_kind` exists — and surfaces structured `details` and `actions` in
the error payload when it does not.

**Connection bindings** record this correspondence. In the diagram's `bindings:` list, a
connection binding entry looks like:

```yaml
bindings:
  - id: bind-e1
    subject: { kind: connection, id: e1 }
    correspondence_kind: represents
    target: { connection_id: "DOB@1---DOB@2@@archimate-association" }
```

The GUI write path strips `backing_conn_id` from `_connections` items and converts them to
proper binding entries before persisting, so MCP callers can pass `backing_conn_id` as a
convenience field and the storage layer normalises it.

&nbsp;

## Model-backed projection (C4)

Diagram types that derive content from the ArchiMate graph may implement the `ViewProjector`
capability. C4 uses one projection engine for preview, render, and refresh, so the live
preview an author sees is structurally identical to the saved render — visible in the
"Create Diagram" screen as auto-derived entities with an inline "Verification passed" check
and a "Show PUML source" toggle.

&nbsp;

## Rules the registry enforces

Every module satisfies the `DiagramTypeModule` protocol; `name` matches its registry key;
`effective_entity_types()` and `effective_connection_types()` only return types present in
the registry. A protocol-compliance test checks every registered type on each run. A scaffold
helper generates a new diagram-type package wired into the registry.

---

*Next: [Hexagonal architecture →](hexagonal-architecture.md)*
