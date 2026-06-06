# PLAN - ArchiMate NEXT Rule Conformance, Verification, and Repository Cleanup

Status: draft / prerequisite to the C4 self-model narrative
Scope: ArchiMate NEXT ontology, all architecture write paths, and ENG-ARCH-REPO
Normative source: `ArchiMate-NEXT-Snapshot-1-connection-rules.pdf`
Created: 2026-06-06

---

## 1. Purpose

Make the repository's declared relationship rules conform to the normative
ArchiMate NEXT Snapshot 1 relationship tables, enforce those rules consistently,
and repair content that existing validation allowed to drift.

This is a prerequisite to revising `PLAN-c4-self-model-narrative.md`. The C4
views must project a valid ArchiMate model rather than compensate for invalid
relationships.

The normative tables are read as stated on their first page:

- columns are relationship sources (`From`);
- rows are relationship targets (`To`);
- uppercase letters denote direct relationships;
- lowercase letters denote derived relationships.

For the service realization issue specifically:

- `function --realization--> service` is permitted;
- `process --realization--> service` is permitted;
- `service --serving--> application-component` is permitted;
- `service --association-- application-component` is permitted;
- direct `application-component --realization--> service` is not permitted;
- direct `service --realization--> application-component` is not permitted.

When several realizers are jointly required to realize one target, the model
must express that conjunction through a grouping or an AND-junction. Multiple
uncoordinated realization relationships must not silently imply "all required".

## 2. Current Findings

### 2.1 The declaration is not demonstrably matrix-complete

`src/ontologies/archimate_next/connections.yaml` is a hand-compressed rule set.
It contains the correct direct `function/process -> service` realization rule
and the correct `service -> application-component` serving rule, but it has no
automated parity check against the normative matrix.

The rule set also mixes direct metamodel relationships and derived
relationships without retaining their provenance. This makes later review and
diagnostics unnecessarily difficult.

### 2.2 Grouping and junction rules are broadly permissive, but not unconditional

Appendix B.6 deliberately allows Grouping and Junction concepts to connect very
broadly. The current declarations are therefore directionally close, but their
unconditional Cartesian expansion is wider than the table:

- `grouping -> grouping` may use any relationship;
- `grouping -> element` may use any relationship for which that element is a
  possible target somewhere in the B.5 tables;
- `element -> grouping` may use any relationship for which that element is a
  possible source somewhere in the B.5 tables;
- Grouping and Location may aggregate any concept;
- Junction connections may use the relationship families listed in B.6,
  subject to the analogous possible-source/possible-target footnotes;
- Junction does not include every relationship indiscriminately: for example,
  the B.6 `afinortv` set does not include aggregation;
- all relationships incident on one junction must have the same type.

The Appendix B.6 conditions are endpoint-role tests. They do **not** say that
the two eventual non-junction endpoint types must themselves permit the same
direct relationship as a pair. The plan must not impose that stronger rule.

These endpoint-role conditions cannot be represented correctly as
`grouping/@junction <-> @all` with every relationship type. They require either
expanded rules generated from the B.5 possible-source/possible-target sets or
semantic validation at authoring time.

### 2.3 Write-time validation does not enforce endpoint-type legality

`src/infrastructure/write/artifact_write/connection.py::_validate_inputs`
currently verifies:

- the relationship type exists;
- source and target IDs exist; and
- a directly touched junction appears homogeneous.

It does not verify that the selected relationship is permitted between the
source and target entity types. This affects MCP, bulk, and administrative write
paths that use the shared writer.

The GUI filters offered relationship types through
`permissible_connection_types()`, but UI filtering is not an integrity boundary.

### 2.4 Repository verification does not audit semantic legality

`ArtifactVerifier.verify_outgoing_file()` checks syntax, references,
duplicates, and schemas, but does not validate the source-type,
relationship-type, target-type triple against the active ontology.

Consequently, legacy and manually authored invalid relationships remain valid
according to repository verification.

### 2.5 Known ENG-ARCH-REPO drift

Known invalid or suspect relationships include:

- service-to-application-component realization edges for Authoring,
  Verification, and Discovery;
- application-component-to-Assurance-Service realization edges;
- `Model Verifier --realization--> Python Runtime`;
- other realization edges whose direction or endpoint categories have not yet
  been checked against the matrix.

The repository-wide audit must inspect every connection, not only this known
sample.

The current baseline also contains:

- six PlantUML diagrams with `E350` syntax/rendering failures;
- one diagram with two `E312` relationships absent from the model;
- three legacy documents with `E011` missing frontmatter;
- one standard with `E155` missing required traceability and `W155` broken link;
- requirement attribute warnings, mainly `MUST` instead of `Must`, plus one
  requirement missing `Priority` and `Category`.

## 3. Required Changes

### 3.1 Establish a machine-readable normative fixture

Create a reviewed fixture representing the Snapshot 1 tables as triples:

```text
(source entity type, target entity type, relationship type, provenance)
```

`provenance` is `direct` or `derived`. Normalize specification names to local
names explicitly, for example `Node -> technology-node`.

Do not generate the normative fixture from the current YAML. It must be an
independent transcription so parity tests can detect both omissions and
over-permissions.

Definition of done:

- every matrix cell is transcribed or explicitly marked not represented;
- a second-person review checks row/column orientation;
- the fixture records the Snapshot identifier and source pages;
- a test reports a readable set difference between the fixture and ontology.

### 3.2 Correct the declared ArchiMate rules

Reconcile `connections.yaml` with the fixture.

Required corrections include:

- preserve `function/process -> service` realization;
- disallow both component/service realization directions;
- preserve `service -> application-component` serving and symmetric
  association;
- replace unconditional grouping/junction Cartesian permissions with the
  broad but footnote-constrained Appendix B.6 permissions;
- correct the Grouping and Junction authoring guidance so it describes
  possible-source/possible-target eligibility rather than pairwise permission
  between eventual non-Grouping/non-Junction endpoints;
- respect Product and Plateau aggregation restrictions;
- distinguish ordinary static permissions from conditional grouping/junction
  semantics.

Choose one explicit policy for derived relationships:

1. permit both direct and derived relationships, matching all lowercase and
   uppercase table entries; or
2. permit only direct relationships for authoring and calculate derived
   relationships rather than storing them.

Recommendation: permit direct relationships for normal authoring, retain
derived relationships in the fixture/query layer, and require an explicit
advanced operation if a derived relationship is persisted. This avoids opaque
redundant edges while preserving specification completeness.

### 3.3 Add one authoritative semantic validation API

Introduce or extend a domain service that returns a structured decision:

```text
validate_relationship(source_type, relationship_type, target_type, context)
```

The result must distinguish:

- permitted direct;
- permitted derived;
- permitted by Appendix B.6 Grouping endpoint-role semantics;
- permitted by Appendix B.6 Junction endpoint-role semantics;
- prohibited;
- unknown type or relationship.

All authoring guidance, GUI filtering, MCP writes, bulk writes, administrative
writes, diagram connection inference, and verification must use this service.
Do not duplicate relationship logic in adapters.

### 3.4 Enforce relationship legality on every write

Add endpoint-type validation to the shared connection writer before content is
generated. Bulk operations must preflight all triples and fail atomically when
one is invalid.

For junctions:

- require one homogeneous relationship type across the connected junction
  structure;
- verify that each adjacent non-junction source is a possible source of that
  relationship according to B.5;
- verify that each adjacent non-junction target is a possible target of that
  relationship according to B.5;
- permit the broad combinations Appendix B.6 intentionally enables; do not
  require each eventual source-target type pair to support a direct
  relationship;
- reject cardinalities at junction ends, retaining the existing rule.

For groupings:

- when Grouping is the source, require the other element to be a possible
  target of the relationship;
- when Grouping is the target, require the other element to be a possible
  source of the relationship;
- permit any relationship between two Groupings;
- permit Grouping and Location aggregation to any concept.

### 3.5 Add repository-wide semantic verification

Add an error for every existing connection whose triple is illegal under the
active ontology. The diagnostic must contain:

- source name and type;
- relationship type;
- target name and type;
- whether the likely issue is direction or relationship kind;
- the permitted alternatives for that source-target pair.

Reserve distinct codes for:

- invalid endpoint-type relationship;
- invalid derived relationship policy;
- mixed junction relationship types;
- junction endpoint that cannot be a source/target of the relationship;
- invalid Appendix B.6 Grouping endpoint role.

Incremental verification must recheck connections when:

- the outgoing file changes;
- either endpoint entity changes type or is replaced;
- ontology relationship rules change;
- a junction-connected relationship changes.

### 3.6 Add realization-specific quality guidance

The generic legality check is mandatory. Add narrowly scoped advisory checks
for realization quality:

- flag service-to-structure realization with a targeted explanation;
- explain that functions/processes realize services;
- when multiple independent realizers target one service, do not assume they
  are jointly required;
- optionally warn when descriptions indicate joint realization but no grouping
  or AND-junction expresses the conjunction.

Do not make "multiple realizers require a junction" a blanket error: multiple
elements may each completely realize the same target. The hard rule applies
only when their combined contribution is required.

## 4. ENG-ARCH-REPO Cleanup

Run cleanup only after the corrected rules and verifier are available, so the
audit produces a complete inventory.

### 4.1 Relationship cleanup

For each invalid realization:

1. identify the actual internal behavior;
2. connect the `function` or `process` to the service with realization;
3. retain or add the valid structure-to-behavior path required by the
   metamodel, potentially via a role;
4. use grouping or an AND-junction only when several behaviors jointly realize
   the complete service;
5. remove invalid direct structure/service realization edges.

Specific required audits:

- Authoring Service;
- Verification Service, including both Model Verifier and Frontmatter Parser;
- Discovery, Querying & Stats Service;
- Assurance Service and its five structural modules;
- runtime/deployment relationships such as Model Verifier and Python Runtime;
- every remaining realization connection in the engagement repository.

Do not replace invalid realization mechanically with serving. Determine the
intended semantic statement first.

### 4.2 Diagram cleanup

- Replace unsupported `Rel_*` macro calls with the repository's supported
  PlantUML relationship syntax or restore one centrally supported mechanism.
- Reconcile the two `E312` triggering arrows with the actual model; remove stale
  arrows unless the missing model relationships are independently justified.
- Regenerate rendered outputs and verify that no rendered error image remains.

### 4.3 Document cleanup

- Migrate the two ADRs to registered architecture document types.
- Decide whether `docs/README.md` is a managed architecture document; either
  migrate it or exclude/move it outside the managed document tree.
- Correct the standard's requirement link and restore its required trace.

### 4.4 Schema-warning cleanup

- Normalize requirement `Priority` values to the declared enum.
- Add the missing `Priority` and `Category`.
- Re-run full verification and leave no avoidable warnings in touched files.

## 5. Tests

Required automated coverage:

- complete ontology-versus-normative-fixture parity;
- row/column orientation sentinel cases:
  - function to service realization allowed;
  - process to service realization allowed;
  - application component to service realization rejected;
  - service to application component realization rejected;
  - service to application component serving allowed;
- symmetric association accepted in either stored orientation;
- all single and bulk write paths reject illegal triples;
- Grouping's broad Appendix B.6 permissions and endpoint-role conditions;
- homogeneous and heterogeneous junction paths;
- Junction's broad Appendix B.6 permissions and endpoint-role conditions;
- full and incremental repository verification;
- diagnostics include legal alternatives;
- existing valid model connections remain valid.

## 6. Delivery Sequence

1. Transcribe and review the normative fixture.
2. Add parity tests and reconcile `connections.yaml`.
3. Implement the shared semantic validator.
4. Integrate it into all write paths.
5. Integrate it into full and incremental verification.
6. Add realization-quality guidance.
7. Run the full ENG-ARCH-REPO audit.
8. Repair relationships, diagrams, documents, and warnings.
9. Re-run repository verification and the complete test suite.
10. Only then revise and implement the C4 self-model narrative.

## 7. Completion Criteria

- The declared ontology has no unexplained difference from the selected
  normative authoring policy.
- Every connection write path rejects illegal endpoint-type triples.
- Full repository verification detects all illegal existing triples.
- Grouping and junctions enforce their conditional semantics.
- ENG-ARCH-REPO has zero verification errors.
- All modified files have zero avoidable warnings.
- The C4 narrative plan contains no application-component/service realization
  and uses functions/processes for service realization.
