# SysML v2 Extensibility Evaluation Plan

## Context

The entity-spec refactor and activity-diagram authoring work are implemented. The
remaining useful work from the original entity-spec refactor plan is an evaluation of
whether the current ontology and diagram-type extension points are sufficient for a
future SysML v2 / KerML implementation.

The implemented baseline includes:

- `EntityTypeInfo.hierarchy` as the type-owned filesystem/domain path.
- Ontology-owned display sections via `display_section_id`,
  `render_display_section()`, and `extract_display_section()`.
- Ontology-owned sprites through `sprite_for()`.
- Diagram-type modules with `ui_config`, diagram-owned entity types, and
  `diagram_entities` persistence.
- Activity and C4 diagram-owned data models using flat per-entity-type collections.
- Static ArchiMate include generation instead of per-entity `_macros.puml`.

## Evaluation Scope

Evaluate; do not implement SysML yet.

Questions to answer:

- Can `OntologyModule` accommodate KerML's type system without ArchiMate-specific leakage?
- Does the diagram-owned entity/mapping mechanism generalize to SysML parts, ports,
  item flows, binding connectors, and nested part structures?
- Does `element_classes` plus `permitted_relationships` cover SysML multiplicity,
  direction, endpoint typing, and containment constraints?
- Does `display_section_id` plus `render_display_section()` extend cleanly to SysML
  notation and metadata blocks?
- Is the current flat `diagram_entities` structure sufficient for SysML diagrams, or
  would SysML require a grouped/rooted structural schema?

## Expected Output

Produce a short gap report with:

- Findings against each evaluation question.
- Specific examples using representative SysML concepts.
- Recommended changes, ordered by priority.
- A clear decision on whether to implement SysML as a new ontology module, a diagram
  type family, or both.

## Non-Goals

- Do not implement a SysML ontology.
- Do not add KerML parsing.
- Do not change the current activity or C4 diagram data format as part of the evaluation.
- Do not reintroduce `_macros.puml` or macro-based rendering.
