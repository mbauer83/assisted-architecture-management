# Plan Outline for ArchiMate 4 Compliance

This architecture repository management tool is currently based on the ArchiMate NEXT snapshot 1 draft for its central meta-ontology (configured in src/ontologies/archimate_next) and referenced in several places in the codebase (we tried to keep it as modular and clean as possible, but there are still other places referencing or hard-coding some aspect of the the meta-ontology). The tool is also not yet fully compliant, mostly because it's missing viewpoint mechanisms and some customization capabilities.

## Focus

We need to focus on:
- implmenting the changes from the ArchiMate NEXT snapshot 1 draft to the final ArchiMate 4 standard - which is mostly the re-appearance of the "composition"-relationship as a dedicated subtype of the "aggregation"-relationship. We need to gather all aggregations in the ENG-ARCH-REPO self-model and check if any of them should be changed to composition, and then implement the change.
- adding the archimate entity-type "specialization" concept, closely related to the "attribute profiles" capability. Those profiles should now optionally specify a (unique) specialization name, thus defining a finite enumeration of specialization types for each entity type. Specializations can also get custom representations (e.g. icons, colors). Some of that should be implemented as runtime customization in derived views / reports, but some (like different iconography) should be specifiable in the specialization-specification itself.
- integrating ArchiMate Model Exchange import / export functionality (using C19C, version 3.1) in an architecturally clean, principled, hexagonal manner.  
- renaming the meta-ontology consistently and thoroughly from ArchiMate NEXT to ArchiMate 4, including all references in the codebase, documentation, diagrams, examples etc.
- adding the "viewpoint" concept in the most architecturally clean, sensible, principled way possible.

## Differences between ArchiMate NEXT Snapshot 1 and ArchiMate 4.0

I compared the uploaded **ArchiMate NEXT Snapshot 1** against the uploaded **ArchiMate 4 Specification**. The blunt conclusion: **the final release is very close to the snapshot, but not identical; the one implementation-breaking difference is that `composition` is back.** A tool implementation based only on the snapshot would likely get this wrong. The snapshot explicitly said composition had been removed and should be replaced by aggregation; the final release defines Composition as a normal structural relationship again.  

### Highest-impact changes for tool implementers

#### 1. Composition relationship was restored

This is the big one.

In the snapshot, Appendix E said:

> “The composition relationship has been removed”

and advised translating it to aggregation. 

In the final ArchiMate 4 document, **§5.1.2 Composition Relationship exists again**. It is defined as a specialization of aggregation with an existence-dependency meaning; it is allowed in exactly the same cases as aggregation; and it appears in the relationship summary and derivation hierarchy. 

For Archi or similar tools, this means:

| Area          | Required final-release behavior                                                                                     |
| ------------- | ------------------------------------------------------------------------------------------------------------------- |
| Metamodel     | Keep/add `CompositionRelationship` as a first-class relationship type.                                              |
| Palette/UI    | Show composition as a structural relationship, with black-diamond notation.                                         |
| Validation    | Allow composition wherever aggregation is allowed.                                                                  |
| Derivation    | Include composition as the strongest structural relationship: realization < assignment < aggregation < composition. |
| Migration     | Do **not** auto-replace composition with aggregation when migrating to ArchiMate 4.                                 |
| Import/export | Preserve composition relationships. Snapshot-based serializers would be wrong if they drop or downgrade them.       |

This is the most relevant concrete delta.

#### 2. “Cardinality” became “Multiplicity”

Snapshot §5.6 was called **Cardinalities**; final §5.6 is **Multiplicity**. The mechanism is basically the same: relationship ends can carry constraints such as `n`, `*`, or `n..m`, except when connected to junctions. The final text is cleaner and adds an explicit explanation of optional versus mandatory participation. The snapshot also said relationships “can now have cardinalities”; final Appendix E says they “can now have multiplicity”.  

For tools: this is mostly a **terminology/API/UI/documentation change**, unless you exposed the name “cardinality” in model files, APIs, property panels, or validation messages. Semantically, I would not treat this as a new feature beyond what the snapshot already introduced.

#### 3. Specialization examples were substantially expanded

Final ArchiMate 4 adds **§14.2.1 Examples of Specializations of Common Domain Elements**. This is important because the final document makes the old layer-specific concepts usable as **informative specializations** of the new generic Common Domain elements. Examples include:

| Generic final concept | Informative specialization examples                  |
| --------------------- | ---------------------------------------------------- |
| Role                  | Business Role                                        |
| Collaboration         | Business/Application/Technology Collaboration        |
| Service               | Business/Application/Technology Service              |
| Process               | Business/Application/Technology Process              |
| Function              | Business/Application/Technology Function             |
| Event                 | Business/Application/Technology/Implementation Event |

In the snapshot, these examples were not gathered in a new Common Domain specialization section; the specialization examples started with Business Domain examples.  

For tool implementers: do **not** reintroduce these as core metamodel element types. They are informative specialization/profile guidance. But they are very relevant for migration support, model libraries, stereotypes/specializations, and backward-compatible UX.

#### 4. Migration guidance changed

Final Appendix E.4 differs materially from the snapshot:

The snapshot told you to replace composition by aggregation. Final ArchiMate 4 does **not** say that, because composition exists again.  

Final also adds more explicit migration advice:

| Legacy ArchiMate 3.x concept                                  | Final ArchiMate 4 direction                                   |
| ------------------------------------------------------------- | ------------------------------------------------------------- |
| Constraint                                                    | specialization of Requirement                                 |
| Contract                                                      | specialization of Business Object                             |
| Gap                                                           | specialization of Assessment or Deliverable                   |
| Representation                                                | specialization of Data Object, Artifact, or Material          |
| Business/Application/Technology Interaction                   | specialization of Function or Process                         |
| Implementation Event                                          | specialization of Event                                       |
| Invalid relationship                                          | replace by Association                                        |
| Aggregation from Path to Technology Internal Active Structure | replace by Realization from active structure element to Path  |
| Realization between services of different layers              | replace by Specialization or Aggregation, depending on intent |

That last service-realization migration note is in the final, not the snapshot, and it matters for automated migration tooling.

#### 5. Exchange-format reference changed

The snapshot references the ArchiMate Model Exchange File Format **C174, Version 3.0**. The final ArchiMate 4 document references **C19C, Version 3.1**.  

This is easy to miss. For Archi-like tools, it means: do not assume the snapshot’s exchange-format reference is final. Also, the ArchiMate 4 language spec itself still points to an existing exchange format standard rather than defining a new exchange schema inline.

#### 6. Conformance status changed, but the conformance obligations are mostly the same

The snapshot explicitly says it is **not an approved standard** and says not to claim conformance to it.  The final ArchiMate 4 document is the Open Group Standard. 

The concrete conformance list remains broadly the same: support the language structure, relationships, domains, iconography, viewpoint mechanism, customization mechanisms, and Appendix B relationship rules. For implementers, the practical difference is that the final release is now the target for conformance and certification; the snapshot is not.

### Sections with the most relevant differences

| Priority | Section(s)                                                              | Why it matters                                                                                                                                                                                |
| -------: | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|        1 | **§5 Relationships and Junctions**, especially §5.1.2, §5.6, §5.7, §5.8 | Composition is restored; multiplicity terminology changed; relationship summary and derivation logic must be updated.                                                                         |
|        1 | **Appendix B Relationships (Normative)**                                | This is the validator/relationship-matrix source of truth. Any implementation should regenerate or manually recheck relationship rules from final Appendix B, not the snapshot.               |
|        1 | **Appendix E.4 Changes from 3.2**                                       | Snapshot migration guidance is wrong for final composition handling; final adds migration advice for implementation event and cross-layer service realizations.                               |
|        2 | **§14.2 Specialization of Concepts**                                    | Final adds Common Domain specialization examples, important for backward compatibility and profile support.                                                                                   |
|        2 | **§1.3 Conformance + Referenced Documents**                             | Final is claimable as a standard; exchange-format reference changed from C174 to C19C.                                                                                                        |
|        3 | **Chapter 2 Definitions**                                               | “ArchiMate Core Framework” is gone; final adds “ArchiMate Full Language” and “Architecture Domain”; “Domain” is clarified as broader than TOGAF’s architecture domains.                       |
|        3 | **§3 Language Structure**                                               | Mostly editorial/structural: “framework” becomes “language”; domains/aspects are reorganized; §3.4 adds an example. Useful for documentation and UI terminology, less for the core metamodel. |
|        3 | **Chapter 10 Technology Domain**                                        | Final adds a separate §10.1 Technology Metamodel and shifts numbering. Mostly documentation/navigation, not a new element set.                                                                |

### Bottom line for Archi-style implementation

The final-release implementation checklist is:

1. **Support Composition** again. This is the main correction from the snapshot.
2. Rename or present relationship-end constraints as **Multiplicity**, not Cardinality.
3. Recheck the relationship validator and derivation rules against final **Appendix B**.
4. Update migration logic: do not downgrade composition; handle implementation event and service-realization migration as final Appendix E says.
5. Treat old layer-specific behavior/collaboration/service/process/function/event concepts as **specialization examples**, not base elements.
6. Update references/documentation from the snapshot’s C174 exchange-format reference to the final document’s C19C reference.

Everything else is comparatively minor: section renumbering, terminology cleanup, updated references, clearer examples, and improved explanatory text.

## Viewpoint & Customization mechanisms

The honest answer is: **ArchiMate 4 makes viewpoint and customization support mandatory for conforming implementations, but it does not define a precise tool API, file schema, or UI behavior for them.** The conformance clause says tooling **shall support** the Chapter 13 viewpoint mechanism and **shall support** Chapter 14 language customization mechanisms “in an implementation-defined manner”; it also says the Appendix C example viewpoints are optional, not mandatory. “Implementation-defined” means the implementer chooses the behavior but must document it. 

### 1. Viewpoint mechanism — Chapter 13

#### What the mechanism is

A **view** is the actual architecture presentation: a diagram, table, catalog, matrix, report, heat map, or some other representation. A **viewpoint** is the rule-set or perspective that governs that view: it specifies what concerns are addressed, for which stakeholders, using which concepts, notations, model kinds, analysis methods, and visualizations. The spec summarizes this as: a view is what you see; a viewpoint is where you are looking from. 

For tooling, do not treat “viewpoint” merely as a diagram type. It is broader than that.

A minimally credible implementation should support a viewpoint definition with at least:

| Viewpoint property                | Implementation meaning                                                                                 |
| --------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Name / identifier                 | The named viewpoint or viewpoint template.                                                             |
| Stakeholders                      | Who the viewpoint is intended for. Could reference Motivation `Stakeholder` elements or tool metadata. |
| Concerns                          | The concerns the view is meant to address. The spec treats concerns as central to viewpoint selection. |
| Purpose category                  | One of Designing, Deciding, Informing.                                                                 |
| Content category                  | One of Details, Coherence, Overview.                                                                   |
| Allowed concept set               | The ArchiMate element and relationship types relevant to the viewpoint.                                |
| Representation rule               | Diagram, catalog, matrix, report, heat map, custom visualization, etc.                                 |
| Optional analysis/operation rules | For example filtering, cross-reference generation, metrics, heat maps.                                 |

The spec does **not** require a particular storage format for these fields, but a tool claiming support should not reduce viewpoint support to “a string tag on a diagram”. That would be too weak to implement the mechanism described in Chapter 13.

#### The two mandatory viewpoint dimensions

Chapter 13 classifies viewpoints along **purpose** and **content**.

##### Purpose dimension

The tool should let viewpoint definitions classify the intended use as one of:

| Purpose       | Meaning for tooling                                                                                                                                                                    |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Designing** | Supports architects/designers from sketching to detailed design. Usually diagram-oriented.                                                                                             |
| **Deciding**  | Supports management decision-making through cross-domain relationships, projections, intersections, analysis, tables, maps, lists, and reports.                                        |
| **Informing** | Communicates architecture to stakeholders to create understanding, commitment, or persuasion. May use illustrations, simplified views, animations, or non-standard presentation forms. |

This matters because a tool should not assume every viewpoint is a diagramming viewpoint. Decision viewpoints are often tabular or analytical; informing viewpoints may be intentionally simplified or visually adapted. 

##### Content dimension

The content dimension classifies how much of the ArchiMate language is spanned:

| Content level | Meaning for tooling                                                                                                                   |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **Details**   | Usually one domain and one aspect. Example: application structure detail, process detail, technology structure detail.                |
| **Coherence** | Multiple domains or multiple aspects. Example: business process uses application service; application component accesses data object. |
| **Overview**  | Multiple domains and multiple aspects. Intended for enterprise architects and senior decision-makers.                                 |

For implementation, this suggests a viewpoint should be able to express scope over both **domains** and **aspects**, and not merely over a flat list of element classes. 

#### Creating and applying a viewpoint

The spec gives a two-step construction mechanism:

1. Select a subset of relevant concepts — elements and relationships — from the ArchiMate metamodel, based on the information needed for stakeholder concerns.
2. Define a representation for those concepts that stakeholders can understand: standard/custom ArchiMate diagram, catalog, matrix, or another visualization. 

Applying a viewpoint to a model means selecting the parts of the architecture model matching the chosen concept set and depicting them according to the selected representation.

For implementers, that means a useful viewpoint engine should support:

| Capability              | Implementation guidance                                                                                                         |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Concept filtering       | Restrict visible/allowed element and relationship types per viewpoint.                                                          |
| Relationship filtering  | Include relationship types explicitly; do not infer that all relationships between selected elements are automatically allowed. |
| View validation         | Warn when a view contains concepts outside its governing viewpoint.                                                             |
| View generation         | Optionally generate a diagram, matrix, catalog, or report from matching model content.                                          |
| Viewpoint metadata      | Store which viewpoint governs a view.                                                                                           |
| Representation binding  | Allow the same concept selection to be rendered as diagram, table, matrix, report, or other visualization.                      |
| Profile-aware rendering | Allow profile attributes to influence view representation, e.g. color-coded heat maps.                                          |

The spec explicitly says a view **does not have to be visual or graphical**. So a compliant tool should not bake in the assumption that “view = diagram”. 

#### Appendix C example viewpoints

The example viewpoints in Appendix C are **not mandatory**. The conformance clause says an implementation **may** support them. 

For a tool like Archi, the practical interpretation is:

| Feature                            |                                     Required? | Comment                                                                |
| ---------------------------------- | --------------------------------------------: | ---------------------------------------------------------------------- |
| Custom viewpoint mechanism         |                                           Yes | Required by Chapter 13.                                                |
| Purpose/content classification     | Yes, if implementing the mechanism faithfully | The mechanism is defined through these dimensions.                     |
| User-defined viewpoint definitions |                            Strongly advisable | Otherwise “support” is very shallow.                                   |
| Appendix C viewpoint library       |                                      Optional | Good UX, but not required for conformance.                             |
| Auto-generated views               |                         Not strictly required | But highly useful for Deciding/Overview viewpoints.                    |
| Non-diagram views                  |                            Strongly advisable | Required conceptually, because views may be matrices/catalogs/reports. |

### 2. Customization mechanisms — Chapter 14

Chapter 14 defines two actual customization mechanisms:

1. **Adding attributes to ArchiMate concepts through profiles**
2. **Specialization of concepts**, also implemented through the profile mechanism

This is important: ArchiMate 4 renamed this chapter from “extension mechanisms” to “customization mechanisms” because these mechanisms do **not** truly extend the language. They refine or annotate existing concepts; they do not create new metamodel classes. 

### 2.1 Profiles / adding attributes

#### What the mechanism is

Every ArchiMate concept — element or relationship — can have attributes attached. A **profile** is a separately defined data structure that can be dynamically coupled to a concept. Profiles are sets of typed attributes, and each attribute may have a default value that users can change. 

For implementers, the clean model is:

```text
ProfileDefinition
  id
  name
  applicableConceptTypes
  attributes[]

ProfileAttributeDefinition
  name
  type
  defaultValue?
  required?
  constraints?        // implementation-defined

ProfileAssignment
  targetConceptId
  profileDefinitionId
  attributeValues
```

The spec distinguishes:

| Profile type             | Meaning                                                                                                                   |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| **Predefined profile**   | Built into the tool or supplied by a library; useful for common analysis such as cost, performance, risk, lifecycle, etc. |
| **User-defined profile** | Defined by the user through some profile-definition mechanism.                                                            |

A compliant implementation should support both categories, though the precise UX is implementation-defined.

#### Required attribute types

The spec says at least the following basic data types are allowed:

| Type     |
| -------- |
| String   |
| Integer  |
| Real     |
| Boolean  |
| Currency |
| Date     |
| URL      |

And the following complex types:

| Type      | Meaning                                    |
| --------- | ------------------------------------------ |
| Structure | One or more fields of a basic type         |
| List      | List of elements of one of the other types |

One awkward detail: the example table in §14.1 uses a `Time` type for “Service time”, even though `Time` is not listed in the basic type list. Since the list says “at least”, an implementer should avoid hard-coding a closed enum that makes the spec’s own example impossible. 

#### Tool behavior to implement

| Capability                         | Implementation guidance                                                               |
| ---------------------------------- | ------------------------------------------------------------------------------------- |
| Define profiles                    | Let built-in or user-defined profiles declare typed attributes.                       |
| Apply profiles to concepts         | Allow profiles on elements and relationships.                                         |
| Store profile values               | Persist values per concept instance, not merely per visual occurrence.                |
| Support defaults                   | Attribute definitions may have defaults.                                              |
| Validate types                     | Enforce declared attribute types.                                                     |
| Support multiple profiles          | Especially needed because specializations also use profiles.                          |
| Expose profile attributes to views | Required for things like heat maps, reports, matrices, cost/performance calculations. |
| Exchange/import/export             | Align with the ArchiMate Model Exchange File Format reference where supported.        |

### 2.2 Specialization of concepts

#### What the mechanism is

Specialization lets users define a more specific version of a concrete ArchiMate concept. Example: define `Social Network` as a specialization of `Collaboration`, or `Business Service` as a specialization of the generic `Service`.

This is **not** the same as adding new metamodel classes. A specialized concept remains an instance of its parent ArchiMate concept. The spec is explicit that arbitrary additions to the abstract language structure would destroy the standard language. 

#### Inheritance rules

A specialized element inherits the properties of the element it specializes, including allowed relationships. A specialized relationship inherits the properties of its parent relationship, possibly with additional restrictions. 

For validation, that means:

| Rule                                           | Consequence                                                                                            |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Specialized element inherits parent rules      | `Business Service` as specialization of `Service` can use relationships valid for `Service`.           |
| Specialized relationship inherits parent rules | `Money Flow` as specialization of `Flow` behaves at least as a `Flow`.                                 |
| Specialization may restrict                    | A profile may narrow valid usage.                                                                      |
| Specialization must not broaden beyond parent  | A specialization should not make invalid ArchiMate relationships valid merely by renaming the concept. |

#### How specialization is represented

Specialization is done using the profile mechanism:

| Item                     | Rule                                                             |
| ------------------------ | ---------------------------------------------------------------- |
| Profile name             | The specialization name.                                         |
| Assigned to              | The general concept being specialized.                           |
| Optional attributes      | May define extra attributes relevant to the specialization.      |
| Default notation         | UML-style guillemets: `«specialization name»`.                   |
| Multiple specializations | Displayed as `«specialization 1, specialization 2»`.             |
| Alternative notation     | Icons, colors, fonts, symbols, or other notation may be defined. |

For tools, this means specializations should be serialized and validated as:

```text
element type = Service
profile/specialization = Business Service
```

not as:

```text
element type = BusinessService   // wrong as a core ArchiMate 4 metaclass
```

unless the tool clearly treats that as a UI alias over `Service + profile`.

#### Notation customization

The spec permits new graphical notation for specialized concepts, preferably resembling the generalized concept. It mentions adding icons or graphical markers, changing icons, colors, fonts, or symbols. 

So a tool should support at least:

| Capability               | Implementation guidance                                                            |
| ------------------------ | ---------------------------------------------------------------------------------- |
| Stereotype label         | Render `«name»` by default.                                                        |
| Custom icon/marker       | Optional but useful.                                                               |
| Custom color/font/symbol | Useful for heat maps and domain overlays.                                          |
| Parent fallback notation | If custom notation is unavailable, render as parent concept plus stereotype label. |
| Per-view rendering       | A specialization might be rendered differently in different viewpoints.            |

### 3. Informative specialization examples relevant to tooling

The final ArchiMate 4 release gives many informative examples. These are not new mandatory metaclasses, but they are highly relevant for migration, palettes, stereotypes, and backward-compatible UX.

Examples include:

| Parent concept                          | Example specializations                                                                                                                  |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `Role`                                  | Business Role                                                                                                                            |
| `Collaboration`                         | Business Collaboration, Application Collaboration, Technology Collaboration, Social Network                                              |
| `Service`                               | Business Service, Application Service, Technology Service, Business Decision, Processing Service, Storage Service, Communication Service |
| `Process`                               | Business Process, Application Process, Technology Process, Business/Application/Technology Interaction, Activity                         |
| `Function`                              | Business Function, Application Function, Technology Function                                                                             |
| `Event`                                 | Business Event, Application Event, Technology Event, Implementation Event, Threat Event, Loss Event                                      |
| `Business Object`                       | Contract                                                                                                                                 |
| `Assessment` or `Deliverable`           | Gap, depending on modeling intent                                                                                                        |
| `Requirement`                           | Constraint                                                                                                                               |
| `Data Object` / `Artifact` / `Material` | Representation-like specializations                                                                                                      |
| `Flow`                                  | Money Flow                                                                                                                               |
| `Assignment`                            | Responsibility Assignment, Behavior Assignment                                                                                           |

For an Archi-like tool, this is probably the most practical approach: keep the ArchiMate 4 core metamodel small, but ship a profile library that restores familiar ArchiMate 3.x concepts as specializations where the final spec recommends it.

### Implementation checklist

A conforming, useful implementation should have:

| Area                      | Minimum credible support                                                                                        |
| ------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Viewpoint definitions     | Store purpose, content, stakeholders/concerns, concept subset, representation type.                             |
| View creation             | Allow a view to be governed by a viewpoint.                                                                     |
| View filtering/validation | Select or validate elements and relationships against the viewpoint concept set.                                |
| Non-diagram views         | Support at least the model needed for catalogs, matrices, reports, or allow implementation-defined equivalents. |
| Profile definitions       | Support predefined and user-defined profiles.                                                                   |
| Profile assignment        | Attach profiles to any ArchiMate concept.                                                                       |
| Attribute typing          | Support the listed primitive and complex attribute types.                                                       |
| Specialization            | Implement as profile/stereotype on a concrete parent concept.                                                   |
| Inheritance               | Validate specializations according to parent concept/relationship rules.                                        |
| Notation                  | Default guillemet notation plus optional custom icon/color/font/symbol handling.                                |
| Documentation             | Document exactly how customization support is implemented, because the spec leaves it implementation-defined.   |

The trap to avoid: **do not implement customization as arbitrary metamodel extension.** ArchiMate 4 customization is deliberately conservative: profiles add typed data; specializations refine existing concrete concepts; viewpoints select and present subsets of the model for stakeholder concerns.

## Comparison & Inspiration from Archi & Bizzdesign Horizzon

I researched the public documentation I could access for **Archi** and **Bizzdesign Horizzon/Enterprise Studio**. The important lesson is this: real tools implement “viewpoint” in two rather different senses.

**Archi** treats a viewpoint mainly as an **authoring constraint on a diagram view**: it restricts what concepts should be used, changes the palette, and ghosts/greys concepts that do not belong. **Bizzdesign** treats viewpoints more broadly as **saved/generated view filters and presentation/analysis definitions**: colors, labels, tooltips, tables, charts, queries, reports, and site presentation. A good ArchiMate 4 implementation should support both patterns, because the ArchiMate notion of viewpoint is broader than “diagram type”: it can govern diagrams, catalogs, matrices, and other representations for stakeholder concerns. The Open Group’s ArchiMate 101 material puts this bluntly: a view may be “a diagram, a catalog, a matrix or any useful way” of describing a subset of the architecture for known stakeholders and concerns. ([GitLab][1])

### 1. Archi’s implementation pattern: dynamic diagram-constraining viewpoints

Archi’s user guide describes a viewpoint “in practice” as a **subset of elements and relationships aimed at a stakeholder**. It provides a built-in list of ArchiMate viewpoints, including Application Cooperation, Application Structure, Business Process Cooperation, Capability Map, Goal Realization, Layered, Motivation, Organization, Product, Project, Service Realization, Stakeholder, Strategy, Technology Usage, Value Stream, and others. ([ArchiMate Tool][2])

The most important design decision in Archi is that viewpoints are **dynamic**. A new Archi view defaults to **None**, meaning all concepts can be added. The user can later set or change the viewpoint at any time. When the viewpoint changes, Archi does not destructively remove non-conforming elements; instead, disallowed elements are “ghosted” in the view. ([ArchiMate Tool][2])

For implementation, this is a very good model:

| Mechanism                       | Archi behavior                                                                                                                                                                                                        | Implementation guidance                                                                            |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Viewpoint selection             | A view has a selected viewpoint, changeable later.                                                                                                                                                                    | Store `view.viewpointId` as mutable metadata. Do not require viewpoint selection at view creation. |
| Default viewpoint               | `None`, meaning unrestricted.                                                                                                                                                                                         | Provide a “None / unrestricted” option. It avoids forcing premature viewpoint choices.             |
| Allowed concept set             | Viewpoint determines which elements are available.                                                                                                                                                                    | Each viewpoint needs an allow-list of element types and relationship types.                        |
| Palette filtering               | Only permitted elements are available in the palette after selecting a viewpoint. ([ArchiMate Tool][2])                                                                                                               | Palette contents should be viewpoint-aware.                                                        |
| Existing non-conforming content | Non-permitted elements are ghosted, not removed. ([ArchiMate Tool][2])                                                                                                                                                | Never delete view contents merely because the viewpoint changed. Use warning/ghosting.             |
| Model tree feedback             | Non-permitted elements can be greyed in the model tree. ([ArchiMate Tool][2])                                                                                                                                         | Give feedback both in diagram and repository browser.                                              |
| Drag/drop behavior              | Archi still allows dragging disallowed concepts; they appear greyed as a reminder. ([ArchiMate Tool][2])                                                                                                              | Consider “soft enforcement” over hard blocking, especially for exploratory modeling.               |
| Explainability                  | Hints explain viewpoint constraints. ([ArchiMate Tool][2])                                                                                                                                                            | Every viewpoint should expose a human-readable rationale and rules.                                |
| Preferences                     | Archi lets users choose whether to grey disallowed tree concepts, hide disallowed palette concepts, hide disallowed concepts from the Magic Connector, and ghost disallowed concepts in a view. ([ArchiMate Tool][2]) | Make enforcement configurable: hide, grey, ghost, warn, or block.                                  |

This is useful but limited. Archi’s documented mechanism is essentially **diagram authoring support**. It helps users create cleaner ArchiMate diagrams, but it does not by itself implement the whole ISO/ArchiMate viewpoint idea of stakeholders, concerns, analysis techniques, matrices, catalogs, reports, and alternate visualizations.

### Implementer takeaway from Archi

An Archi-like implementation should have a **non-destructive viewpoint application engine**:

```text
ViewpointDefinition
  id
  name
  description
  allowedElementTypes[]
  allowedRelationshipTypes[]
  optionalAllowedSourceTargetRules[]
  rationale / hint text
  category / folder
```

```text
View
  id
  name
  viewpointId?       // null or "None" means unrestricted
  diagramObjects[]
  diagramConnections[]
```

Then apply it like this:

```text
for each diagram object/connection in view:
    if concept type is allowed:
        render normally
    else:
        render as ghosted / greyed / warning depending on user preference
```

Do **not** implement viewpoint application as a destructive filter that removes elements. That would make viewpoint experimentation unsafe.

### 2. Bizzdesign’s implementation pattern: generated view filters as viewpoints

Bizzdesign’s public Help material describes a different and richer approach. In Horizzon, a viewpoint is described as a **saved or unsaved generated view filter**; generated view filters automatically create viewpoints that appear in the Viewpoints pane, and those viewpoints can be saved. ([help.bizzdesign.com][3])

This is closer to a “query + presentation” model than to Archi’s “diagram type + palette restriction” model. Bizzdesign Help snippets describe viewpoints that can be saved in the model, managed in a Viewpoints pane, edited through a view filter window or Query Tool, included in reports, and activated in sites. ([help.bizzdesign.com][4])

Bizzdesign also exposes multiple presentation/filter forms: color, label, tooltip, table, and chart filters are mentioned in its site-viewpoint documentation; label views can use profile properties; timed values and compare/color views are also supported. ([help.bizzdesign.com][5])

For implementation, this suggests a second viewpoint model:

```text
GeneratedViewpoint
  id
  name
  sourceViewId?
  queryDefinition
  presentationType        // color, label, tooltip, table, chart, compare, etc.
  renderingRules[]
  parameterValues[]
  scope                   // current view, all open views, model/site/report
  savedState              // unsaved, saved in model, pinned/published
```

This is not just a static list of allowed concepts. It is a reusable, named way to **derive or transform a presentation from repository data**.

#### Bizzdesign-style capabilities worth implementing

| Capability                      | Why it matters                                                                                                                         |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Generated viewpoints            | A viewpoint can be created from a filter/query operation, not only manually defined.                                                   |
| Saved and unsaved state         | Let users experiment with temporary viewpoints before saving.                                                                          |
| Viewpoints pane/library         | Users need to browse, apply, rename, organize, and delete viewpoints.                                                                  |
| Query-backed viewpoints         | A viewpoint should be expressible as a query over model content and properties.                                                        |
| Presentation-backed viewpoints  | The result may be color coding, labels, tooltips, tables, charts, or comparison overlays.                                              |
| Profile-property use            | Viewpoints should use custom attributes/profiles for heat maps, labels, risk views, lifecycle views, etc.                              |
| Report/site reuse               | Saved viewpoints should be reusable in reports and published sites, not only in the modeling editor.                                   |
| Analysis settings as viewpoints | Some analysis configurations, such as derived relationship analyses, can be saved and re-run as viewpoints. ([help.bizzdesign.com][6]) |

Bizzdesign’s own blog also shows the more “classic ArchiMate viewpoint” side: a practical application-components viewpoint is described as allowing only **three concepts and two relationship types**, precisely to reduce complexity and guide model creation. ([Bizzdesign][7]) That reinforces the point: a mature tool needs both **allowed-concept constraints** and **presentation/query filters**.

### 3. What compliant tooling should implement, informed by both tools

#### A. Separate “viewpoint definition” from “viewpoint application”

This is the first architectural rule.

A viewpoint definition is reusable. A viewpoint application is a particular use of that definition on a view, report, matrix, catalog, chart, or site page.

```text
ViewpointDefinition
  describes what is allowed, selected, analyzed, or shown

ViewpointApplication
  applies a viewpoint to a specific view/report/site/chart at a specific time
```

Archi mostly stores viewpoint application as a property of a diagram view. Bizzdesign adds generated, saved, pinned, and reportable forms. A good implementation should support both.

#### B. Support at least three kinds of viewpoint

Do not collapse everything into one enum.

| Kind                                | Example                                                                                | Implementation behavior                                                                         |
| ----------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| **Authoring viewpoint**             | Archi’s Technology Usage viewpoint                                                     | Restricts palette, Magic Connector, allowed concepts, and validation feedback.                  |
| **Selection/filter viewpoint**      | Hide everything except selected application dependencies                               | Query selects a subset of model/view contents.                                                  |
| **Presentation/analysis viewpoint** | Color applications by lifecycle state; label interfaces by protocol; compare two views | Uses profile attributes, analysis output, labels, colors, tooltips, tables, charts, or reports. |

The standard’s idea of a viewpoint includes concepts, models, analysis techniques, and visualizations. A purely palette-based implementation is useful but thin. ([GitLab][1])

#### C. Store viewpoint metadata explicitly

A practical `ViewpointDefinition` should include:

```text
ViewpointDefinition
  id
  name
  description
  purpose              // designing, deciding, informing
  contentLevel         // detail, coherence, overview
  stakeholders[]
  concerns[]
  allowedElementTypes[]
  allowedRelationshipTypes[]
  allowedRelationshipEndpointRules[]
  allowedNestingRules[]
  representationTypes[]    // diagram, matrix, catalog, table, chart, report, map
  queryDefinition?
  renderingRules?
  analysisDefinition?
  profileDependencies[]
  helpText / rationale
  version
```

The **help text/rationale** is not decorative. Archi’s Hints window is a good design pattern: users need to know why a concept is disallowed, not merely that it is disallowed. ([ArchiMate Tool][2])

#### D. Make enforcement configurable

Archi’s preferences are a strong hint: different users want different enforcement levels. It supports greying disallowed model-tree concepts, hiding disallowed palette concepts, hiding disallowed Magic Connector concepts, and ghosting disallowed concepts in the view. ([ArchiMate Tool][2])

Implement these policies:

```text
enum ViewpointEnforcementMode {
  Off,
  WarnOnly,
  GhostDisallowed,
  GreyDisallowed,
  HideDisallowedFromPalette,
  HideDisallowedFromConnector,
  BlockCreation
}
```

My recommendation: default to **soft enforcement**. Hard blocking sounds clean but often frustrates architects during exploration.

#### E. Integrate viewpoints into creation tools

A viewpoint should affect:

| Tool area                                | Expected behavior                                                                |
| ---------------------------------------- | -------------------------------------------------------------------------------- |
| Palette                                  | Show, hide, or grey element/relationship types based on the viewpoint.           |
| Magic connector / relationship suggester | Suggest only relationships valid both in ArchiMate and in the current viewpoint. |
| Drag-and-drop from repository            | Allow but warn/ghost if the dropped concept is outside the viewpoint.            |
| Copy/paste                               | Preserve content but mark out-of-viewpoint objects.                              |
| Validator                                | Report viewpoint violations separately from ArchiMate metamodel violations.      |
| Hints/help                               | Explain viewpoint purpose, stakeholders, concerns, and allowed concepts.         |

Separate **language validity** from **viewpoint fit**. An element may be valid ArchiMate and still inappropriate for a particular viewpoint.

#### F. Support generated viewpoints and presentation filters

Bizzdesign’s approach shows that viewpoints are also reusable **view transformations**. Implement:

```text
ViewFilter
  sourceScope
  selectionQuery
  includeRules
  excludeRules
  expansionRules      // e.g. include related elements n hops away
  renderingRules
  presentationType
```

Rendering rules should support at least:

```text
ColorRule
LabelRule
TooltipRule
VisibilityRule
Shape/IconRule
LineStyleRule
TableColumnRule
ChartMappingRule
```

This is where ArchiMate profiles/custom attributes become genuinely useful. For example:

```text
Color applications by lifecycleStatus
Label flows by dataClassification
Tooltip business processes with owner + maturity
Generate matrix rows = capabilities, columns = applications, cells = serving/access relationships
```

#### G. Treat viewpoints as publishable assets

Bizzdesign’s documentation around saving viewpoints, including them in reports, and activating predefined viewpoints in sites points to an important enterprise feature: viewpoints are not just editor conveniences; they are reusable communication assets. ([help.bizzdesign.com][8])

For implementation:

```text
ViewpointPublication
  viewpointId
  target              // report, site, dashboard, exported model
  defaultParameters
  permissions
  pinned / unpinned
```

A saved viewpoint should be usable in:

| Target          | Expected use                                                                      |
| --------------- | --------------------------------------------------------------------------------- |
| Modeling editor | Authoring and validation.                                                         |
| HTML/PDF report | Render selected diagrams/tables/charts.                                           |
| Web portal/site | Let stakeholders switch filters or open links with a predefined viewpoint active. |
| Dashboard       | Use viewpoint as a reusable query/presentation definition.                        |
| Model review    | Compare, color, label, and highlight relevant changes.                            |

#### H. Support custom viewpoint definitions properly

Bizzdesign Help exposes custom viewpoint definitions in the metamodel package area, while Archi’s public guide mainly documents built-in viewpoints and dynamic switching. ([help.bizzdesign.com][9]) For an implementer, a real custom viewpoint mechanism should not require editing internal files or source-level metadata.

Minimum custom viewpoint UI:

| Feature               | Guidance                                                                   |
| --------------------- | -------------------------------------------------------------------------- |
| Create viewpoint      | Wizard or editor for name, purpose, content level, stakeholders, concerns. |
| Select concepts       | Multi-select element and relationship types.                               |
| Define endpoint rules | Relationship type alone is not enough; source/target constraints matter.   |
| Define presentation   | Diagram, matrix, catalog, color view, label view, report section, etc.     |
| Test on sample view   | Show what would be hidden, ghosted, or highlighted.                        |
| Save to library       | Reuse across models or workspaces.                                         |
| Import/export         | Share viewpoint libraries between users/teams.                             |
| Versioning            | Avoid silently changing old models when viewpoint definitions evolve.      |

#### I. Keep the model canonical and viewpoint-independent

This is the trap to avoid. A viewpoint must not become the model.

The canonical repository should store all ArchiMate concepts independently of views. Views and viewpoints are projections, filters, constraints, or presentations of that repository. Archi’s ghosting behavior gets this right: switching viewpoints does not mutate the model. ([ArchiMate Tool][2])

Bad implementation:

```text
Changing viewpoint deletes all disallowed objects from the view/model.
```

Good implementation:

```text
Changing viewpoint changes visibility, warnings, rendering, palette contents, and validation messages.
```

### Recommended implementation model

A robust ArchiMate 4-style implementation should have four layers:

```text
1. Repository model
   Elements, relationships, properties, profiles.

2. View model
   Diagram/canvas/matrix/catalog/report definitions and object placements.

3. Viewpoint definition
   Stakeholders, concerns, purpose, content, allowed concepts, queries, analysis, rendering rules.

4. Viewpoint application
   The selected/generated/saved/pinned use of a viewpoint on a specific view, report, dashboard, or site.
```

This design can support Archi-style dynamic viewpoints and Bizzdesign-style generated presentation viewpoints without conflating them.

### Concrete checklist

For an implementer building ArchiMate 4 tooling, I would implement the following:

| Priority | Feature                                                 | Rationale                                                                                                                                       |
| -------: | ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
|        1 | Built-in standard/example viewpoint library             | Users expect Organization, Application Structure, Layered, Technology Usage, Motivation, etc.; Archi ships many of these. ([ArchiMate Tool][2]) |
|        1 | Dynamic viewpoint switching                             | Lets users change their mind without recreating diagrams. ([ArchiMate Tool][2])                                                                 |
|        1 | Non-destructive ghost/grey/warn behavior                | Prevents accidental loss and supports experimentation.                                                                                          |
|        1 | Viewpoint-aware palette and connector                   | Guides valid modeling at the point of creation.                                                                                                 |
|        1 | Viewpoint validation separate from ArchiMate validation | “Invalid ArchiMate” and “not appropriate for this viewpoint” are different errors.                                                              |
|        2 | Custom viewpoint editor                                 | Needed for organization-specific architecture methods.                                                                                          |
|        2 | Query-backed generated viewpoints                       | Needed for Bizzdesign-like filters, analyses, and large repositories.                                                                           |
|        2 | Color/label/tooltip/table/chart presentation rules      | Needed for decision/informing viewpoints and profile-based visualizations.                                                                      |
|        2 | Save/pin/publish/report viewpoints                      | Needed for enterprise communication, portals, and recurring reports.                                                                            |
|        3 | Versioned viewpoint libraries                           | Needed when teams evolve modeling conventions.                                                                                                  |
|        3 | Parameterized viewpoints                                | Useful for “show dependencies for selected application” or “show capability map for business unit X”.                                           |
|        3 | Viewpoint import/export                                 | Needed for tool ecosystems and community viewpoint libraries.                                                                                   |

Bluntly: **copying Archi’s implementation alone is not enough for a high-end compliant tool**, because it mostly covers diagram authoring constraints. **Copying Bizzdesign’s generated-filter model alone is also not enough**, because you still need explicit ArchiMate concept/relationship allow-lists for guided modeling. The stronger architecture is to implement viewpoints as **reusable, stakeholder-oriented definitions that combine constraints, queries, analysis, and presentation rules**.

[1]: https://archimate-community.pages.opengroup.org/workgroups/archimate-101/ "ArchiMate 101: A Practical Introduction"
[2]: https://www.archimatetool.com/downloads/archi/Archi%20User%20Guide.pdf "Archi User Guide"
[3]: https://help.bizzdesign.com/articles/horizzon-help/working-with-viewpoints-in-a-site?utm_source=chatgpt.com "Working with viewpoints in a site"
[4]: https://help.bizzdesign.com/articles/horizzon-help/saving-viewpoints-in-the-model?utm_source=chatgpt.com "Saving viewpoints in the model"
[5]: https://help.bizzdesign.com/articles/horizzon-help/activating-predefined-viewpoints-on-views-in-a-site?utm_source=chatgpt.com "Activating predefined viewpoints on views in a site"
[6]: https://help.bizzdesign.com/articles/horizzon-help/deriving-relations?utm_source=chatgpt.com "Deriving relations"
[7]: https://bizzdesign.com/blog/practical-archimate-viewpoints-for-the-application-layer "Enterprise Architecture modeling: Practical ArchiMate® viewpoints for the application layer I Bizzdesign /image/enterprise-architecture-modeling-practical-archimate-viewpoints-application-layerwebp"
[8]: https://help.bizzdesign.com/articles/horizzon-help/viewpoints-in-reports/a/h1_629904574?utm_source=chatgpt.com "Viewpoints in reports"
[9]: https://help.bizzdesign.com/articles/horizzon-help/creating-a-custom-viewpoint-definition?utm_source=chatgpt.com "Creating a custom viewpoint definition"
