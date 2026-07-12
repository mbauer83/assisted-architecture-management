# ArchiMate 4.0 Conformance

This page states, per the ArchiMate 4.0 specification's own conformance section, what this
implementation supports and in which implementation-defined manner — concisely, and only
where behavior is stated elsewhere in these docs does it link out rather than repeat. It is
not a usage guide; see the linked pages for how to use any of this.

> The model aims for conformance with the **ArchiMate 4.0** standard; conformance has not
> been independently verified, so no conformance claim is made. The Open Group's own
> conformance section lists six requirements for an implementation; each is addressed below.

&nbsp;

## 1 — Language structure, relationships, domains, and cross-domain dependencies

The `archimate-4` ontology module (`src/ontologies/archimate_4/`) ships 45 entity types
across every domain the standard names — Motivation, Strategy, Business, Application,
Technology, and Implementation & Migration — plus the cross-layer "Other" elements
(Location, Grouping, and the And/Or junctions).

Several concepts the standard generalizes across layers (Service, Process, Function, Event,
Role, Collaboration) are modeled as **one base type each**, differentiated by layer through
an ArchiMate 4 specialization slug (`business-service`, `application-service`,
`technology-service`, …) rather than three duplicate types — a direct implementation of the
standard's own Common Domain generalization, not a shortcut around it. See
[Ontology modules](../05-extensibility/ontology-modules.md) for the module structure and
[Specializations](../05-extensibility/ontology-modules.md#specializations) for how a
layer is assigned.

Relationship-end **multiplicity** uses that exact term (renamed from "cardinality" for
terminology alignment with the standard); see the [CLI & backend](cli-and-backend.md)
deprecation note for the migration path from the old field name.

&nbsp;

## 2 — Standard iconography

40 dedicated SVG glyphs (`tools/gui/src/ui/lib/archimateGlyphs.json`) drive both the GUI's
entity rendering and the generated PlantUML diagram notation, following the standard's
shapes (the role banner, the rounded service pill, the process arrow, the function block,
the notched event, the motivation glyphs, …). A specialization without its own dedicated
glyph renders as a guillemet stereotype badge on its base type's shape — `«Business
Collaboration»`, e.g. — never a generic unlabeled box. See
[Diagramming](../03-modeling/diagramming.md) for the rendering pipeline and
[Specializations → Rendering](../05-extensibility/ontology-modules.md#rendering) for the
stereotype-badge rule.

&nbsp;

## 3 — The viewpoint mechanism

A `ConceptScope` primitive (entity types + connection types + a criteria tree) is the one
thing diagram-type filters, binding admissibility, and viewpoint scope all compile to.
`ViewpointDefinition`s are versioned and either module-shipped (a small informative starter
library — Motivation, Application Structure, Layered, Technology Usage) or repo-authored;
`ViewpointApplication`s pin a diagram to a specific definition version, non-destructively
(`off`/`warn`/`ghost` enforcement, never a hard block), and flag drift the moment the pinned
version and the diagram's actual content disagree. Four representations — table, matrix,
diagram, and graph exploration — read the same scope. See
[Viewpoints](../03-modeling/viewpoints.md) for the full concept and how-to, and
[Viewpoints — schema reference](viewpoints-schema.md) for the declaration grammar and the
`artifact_viewpoint`/`artifact_query_viewpoint` MCP tools.

**Known gap — indirect relationship handling.** The standard lets a viewpoint work with
relationships derived across intermediate elements, not only direct ones. This
implementation currently supports only the weaker case: a **path-based projection**
(`src/application/derivation/path_projection.py`) that finds and displays an existing chain
of real relationships between two entities in a generated view. It does **not** yet compute
a new *derived* relationship from that chain per the standard's derivation rules, and there
is no impact-analysis feature built on that computation. Closing this is tracked as
follow-on work, not part of this compliance effort.

&nbsp;

## 4 — Language customization mechanisms (implementation-defined)

Customization is **concept-level**: one unified specialization catalog covers both entity
and connection types (`concept_kind: entity | connection`), enumerated in
`specializations.yaml` at two tiers — a module-shipped informative library (names and
notation only, license-clean) and a repo-level extension (`.arch-repo/specializations.yaml`,
enterprise baseline / engagement superset, enforced at promotion). A specialization may
narrow — never widen — what its parent type permits (`restrict_relationships`,
`restrict_endpoints`). Attribute constraints compile 1:1 from a specialization's own inline
`attributes:` (or an attached schema file) into a JSON Schema fragment — a specialization
and its profile are one concept, not two; a profile is never independently reusable or
shared across specializations. See
[Ontology modules → Specializations](../05-extensibility/ontology-modules.md#specializations)
for the full mechanism and
[Attribute profiles & frontmatter schemata](../05-extensibility/schemata-and-profiles.md)
for the compiled-schema shape.

Separately, **authoring guidance** (`create_when`/`never_create_when` prose per type) is a
deployment-level, license-gated import (`arch-import-guidance`) layered over this
mechanism — an authoring aid, not itself part of the standard's customization requirement.

&nbsp;

## 5 — Relationship rules (Appendix B)

125 permitted `(source type, target type, relationship type)` rows drive both authoring-time
validation and the GUI's relationship picker (`src/ontologies/archimate_4/connections.yaml`,
`src/domain/permitted_relationships.py`). One deliberate correction from the informative
pre-release snapshot this ontology started from: per the final published standard's
§5.1.2, **composition is permitted everywhere aggregation is** — verified by diffing the
two relationship types' permitted rows directly, with a standing structural test
(`composition permitted ⊇ aggregation permitted`) that fails if a future rule addition ever
regresses it.

&nbsp;

## 6 — Example viewpoints (Appendix C) — optional

The module ships four starter `ViewpointDefinition`s (§3 above) informed by the standard's
example-viewpoint concepts — not a re-implementation of the full Appendix C set, which the
standard itself marks optional (**"may support"**). The viewpoint mechanism is fully open to
repo-authored definitions, so covering more of Appendix C is an authoring exercise, not a
code change.

&nbsp;

## Also supported: model exchange (not part of the language conformance section)

C19C v3.1 model-exchange import/export (a separate Open Group interoperability standard,
not part of the ArchiMate language conformance section above) is available via the
`arch-exchange` CLI: import applies the standard's Appendix E.4 migration table (3.x
layer-specific types → the ArchiMate 4 base type plus specialization); export inverts it.
Composition is never downgraded to association on either path, and every unmapped or
out-of-scope item is reported by kind and reason, never silently dropped. See
[Model exchange](cli-and-backend.md#model-exchange) for usage.

&nbsp;

## Deferred, explicitly

Persistent diagrams generated from a viewpoint execution, the fuller presentation-rule
engine (label/tooltip rules, attribute-driven heat maps beyond match/range styling), saved
executions as first-class view artifacts, viewpoint publishing/pinning, parameterized
viewpoints, and dedicated catalog/report view artifact kinds (today's table/matrix
executions are ephemeral renderings, not new artifact types) are all deferred — the
query/presentation split in the underlying model means they compose later without rework,
but none of them exist today.

---

*See also: [Ontology modules](../05-extensibility/ontology-modules.md) ·
[Interfaces & MCP](../03-modeling/interfaces-and-mcp.md) ·
[CLI & backend](cli-and-backend.md)*
