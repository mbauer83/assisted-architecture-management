# ArchiMate Exchange Readiness

This note is the WU-F1 review packet for the C19C v3.1 exchange gate. It records the
mapping, XSD acquisition decision, and lossy-case policy that must be signed off before any
F2+ codec/import/export code starts.

## Local Sources

Use the local `spec/` directory as the working authority for this effort:

- `spec/c19c-model-exchange_compressed.pdf`
- `spec/c19c-view-exchange_compressed.pdf`
- `spec/c19c-diagram-exchange_compressed.pdf`
- `spec/c19c-examples/*.xml`
- `spec/c19c-examples/*.pdf`

The committed repository must not copy those PDFs or example payloads. Future tests should
use small synthetic XML fixtures shaped from the local examples, not verbatim snippets.

This document is intentionally prose, not adapter configuration. WU-F2 can later extract a
small machine-readable table from the reviewed decisions, but the gate artifact itself is a
review document.

## Q3: XSD Acquisition

Decision for review: do not vendor or redistribute the C19C XSD files. Fetch them from The
Open Group into the gitignored `spec/c19c-xsd/` directory and verify pinned checksums:

```sh
sh tools/fetch_c19c_xsds.sh
```

The Open Group index at `https://www.opengroup.org/xsd/archimate/` lists the ArchiMate 3.1
model, view, and diagram XSDs and states "Copyright 2015-2019 The Open Group, All Rights
Reserved." That is enough for local acquisition, but not enough to justify committing the
XSDs to this repository.

The script fetches:

- `archimate3_Model.xsd`
- `archimate3_View.xsd`
- `archimate3_Diagram.xsd`
- `dc.xsd`

The local XML examples use the same namespace and schema family in their
`xsi:schemaLocation` values.

## Compatibility Policy

C19C remains the boundary format. The adapter should emit schema-valid C19C XML wherever the
standard has a native field. Fully compatible extensions are allowed only through standard
extension points such as `propertyDefinitions`, `properties`, `modelingNote`, and
non-Open-Group namespace attributes where the schema permits them.

Use extensions for ArchiMate 4 and repository concepts that C19C cannot express natively:

- ArchiMate 4 entity and relationship specialization slugs
- non-default meta-ontology identity
- viewpoint query/presentation YAML
- viewpoint application `pinned_version`
- relationship-end multiplicity
- abstract style tokens when a concrete palette mapping is unavailable
- exact repository file content for lossless round-trip between systems that understand the
  `arch-repo` extension contract

Other meta-ontologies and diagram types must not be guessed from names. They need explicit
mapping sections or must be reported as unmappable. This keeps C19C conformance intact while
allowing compatible extension data for our richer model.

## Lossless Extension Contract

Standard C19C remains the interoperable representation. For lossless import/export between
systems that understand this repository, export additionally carries exact file content as
standard C19C root-level properties:

- `propertyDefinition identifier="archrepo-preservation-manifest"` (`type="string"`):
  canonical JSON manifest with exporter version, format version, repository roots,
  normalized relative paths, byte sizes, SHA-256 hashes, media types, and the hash of the
  archive payload.
- `propertyDefinition identifier="archrepo-preservation-bundle"` (`type="string"`):
  base64-encoded deterministic `tar.gz` containing the exact repository files named in the
  manifest.

The extension properties are ordinary C19C properties. Generic C19C tools can ignore them
and still consume the model/view/diagram projection. Our importer uses them only when the
operator requests lossless restoration or imports into a repository type that declares this
extension supported.

Safe import rules for F3a:

- reject absolute paths, `..` segments, symlinks, hard links, device files, and duplicate
  paths in the bundle;
- verify every file hash against the manifest before writing anything;
- size-cap the decoded archive and each file;
- dry-run by default and report create/update/skip for every file;
- use the ordinary repository write/upgrade paths for model artifacts where feasible;
- never let extension content override a valid standard C19C parse silently. If standard
  C19C and preservation bundle disagree, report a conflict and require an explicit choice.

This gives two modes from one export:

- **interoperable mode**: generic C19C consumers read the standard model/view/diagram
  projection and ignore `archrepo-*` properties;
- **lossless mode**: arch-repo-aware consumers verify the preservation bundle and restore the
  exact files, including PUML source, frontmatter, custom viewpoint files, profiles,
  specializations, repo config, and non-ArchiMate diagram/document artifacts.

## Mapping Summary

Element and relationship mapping starts from the C19C model XSD's `ElementTypeEnum` and
`RelationshipTypeEnum`. Import maps C19C 3.x concrete types to ArchiMate 4 base types plus
specialization where the repository ships a specialization. Export emits the most specific
C19C type available and carries ArchiMate 4 specialization as an extension property when
C19C has no native type.

Examples:

- `BusinessService` <-> `service` + `business-service`
- `ApplicationService` <-> `service` + `application-service`
- `TechnologyService` <-> `service` + `technology-service`
- `Contract` <-> `business-object` + `contract`
- `Constraint` <-> `requirement` + `constraint`
- `Gap` <-> `assessment` + `gap`
- `Composition` <-> `archimate-composition`, preserved as composition
- `Assignment` <-> `archimate-assignment`, with shipped assignment specializations carried
  as extension properties

Profiles and attributes map through C19C `propertyDefinitions` / `properties`. Unknown
foreign properties are not silently discarded: preserve them when feasible, otherwise report
them as unmappable.

Shipped ArchiMate 4 specialization coverage:

- `business-role` -> `BusinessRole`
- `application-role` -> C19C-compatible extension on a role concept; no 3.x concrete
  application role type
- `technology-role` -> C19C-compatible extension on a role concept; no 3.x concrete
  technology role type
- `business-collaboration` -> `BusinessCollaboration`
- `application-collaboration` -> `ApplicationCollaboration`
- `technology-collaboration` -> `TechnologyCollaboration`
- `business-service` -> `BusinessService`
- `application-service` -> `ApplicationService`
- `technology-service` -> `TechnologyService`
- `business-process` -> `BusinessProcess`
- `application-process` -> `ApplicationProcess`
- `technology-process` -> `TechnologyProcess`
- `business-function` -> `BusinessFunction`
- `application-function` -> `ApplicationFunction`
- `technology-function` -> `TechnologyFunction`
- `business-event` -> `BusinessEvent`
- `application-event` -> `ApplicationEvent`
- `technology-event` -> `TechnologyEvent`
- `contract` -> `Contract`
- `representation` -> `Representation`
- `constraint` -> `Constraint`
- `gap` -> `Gap`
- `service`, `module`, `endpoint` on `application-component` -> `ApplicationComponent`
  plus extension property; no 3.x equivalent
- `responsibility-assignment`, `behavior-assignment` -> `Assignment` plus extension
  property; no 3.x relationship subtype

One ledger discrepancy is intentional: WU-F1 mentions `money-flow` as an example, but the
current shipped ArchiMate 4 specialization catalog does not include it, and earlier progress
notes explicitly say not to assume that illustrative plan example is implemented.

## Diagram Round-Trip Policy

The normal diagrams in `ENG-ARCH-REPO` are PlantUML source files. They use relative layout
constraints (`top to bottom direction`, hidden edges, grouping rectangles, direction-specific
arrows, macros, sprites, skinparams) rather than persistent absolute geometry.

C19C Diagram Exchange is geometry-oriented. It can represent diagram nodes, connections,
styles, source/target attachments, bendpoints, and absolute bounds such as `x`, `y`, width,
and height. It has no native representation for PlantUML layout constraints, macros,
skinparams, hidden layout edges, or source-level grouping tricks.

Therefore:

- A standard C19C diagram export can be a conformant visual/semantic projection of a PUML
  diagram only after assigning concrete coordinates and bendpoints.
- That export can be useful to other C19C tools, but importing it back cannot reconstruct
  the original PUML source losslessly.
- A lossless round-trip between two systems that understand this repository format is
  feasible only if the exported C19C package also carries the preservation bundle described
  above.
- Import preference should be: if a verified preservation bundle exists and the operator
  selected lossless mode, restore the original PUML diagram; otherwise import the standard
  C19C diagram as a generated coordinate-based diagram and report that original PUML layout
  constraints were unavailable.

This means ENG-ARCH-REPO-style diagrams are not lossless through pure standard C19C diagram
fields. They can be lossless through a compatible C19C extension understood by our tooling.

## Lossy Cases

The cases requiring explicit review are:

- C19C 3.x `BusinessInteraction`, `ApplicationInteraction`, and `TechnologyInteraction`
  have no shipped ArchiMate 4 interaction specialization here; import maps them to the
  matching layer process specialization with a warning.
- C19C `ImplementationEvent` has no shipped `implementation-event` type; import maps it to
  generic `event` with a warning.
- ArchiMate 4 `application-component` specializations `service`, `module`, and `endpoint`
  export as C19C `ApplicationComponent` plus an extension property.
- ArchiMate 4 assignment specializations `responsibility-assignment` and
  `behavior-assignment` export as C19C `Assignment` plus an extension property.
- C19C `Access@accessType`, `Influence@modifier`, and directed `Association@isDirected`
  are preserved as properties when recognized; otherwise they warn because the current
  repository model has no first-class field.
- Relationship-end multiplicity has no C19C relationship-native field; preserve it through
  extension properties.
- Viewpoint concern-to-stakeholder association granularity is not preserved exactly by our
  current flat viewpoint model.
- Abstract style tokens can export to concrete RGB through a palette, but imported RGB is
  not reverse-mapped to tokens.
- Pure C19C diagram fields cannot preserve PlantUML source-level layout constraints; lossless
  PUML round-trip requires the preservation bundle extension.
- Repository artifacts outside the C19C ArchiMate model/view/diagram scope, such as ADR
  documents or non-ArchiMate diagram types, are lossless only through the preservation bundle;
  they are not made lossless by C19C alone.

## Review Gate

Before F2+ implementation starts, a reviewer must sign off on:

- this mapping and compatibility policy
- the no-vendored-XSD Q3 decision and checksum script
- the lossy cases above
- lossless repository round-trip via the `archrepo-preservation-*` compatible extension
- whether Q4 conformance wording makes exchange implementation release-blocking
