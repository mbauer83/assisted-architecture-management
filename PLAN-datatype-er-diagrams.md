# PLAN — Datatype (UML Class) Diagrams + Data-Object Binding

**Mode:** [PLAN] · **Status:** Approved 2026-06-17 — ready to implement (see `TASKS-datatype-er-diagrams.md`) · **Owner:** Michael Bauer · **Date:** 2026-06-17

> **Scope.** Add a new **pluggable diagram-type module** — a *datatype diagram*, i.e. a **UML class
> diagram restricted to data structure** (classifiers + typed attributes + structural relations, **no
> operations**) — and integrate its **creation and management** into the system. A classifier
> (record / enumeration / variant) can be **bound to an ArchiMate `data-object`** so the fine-grained
> schema traces to the architectural data element it details.
>
> This document does two things:
> 1. **Adapts the self-describing ENG-ARCH-REPO model** to describe the new capability across the
>    **motivation, common, business, and application** domains (the user-requested deliverable).
> 2. Specifies the **code / ontology design** that the model describes (the thing being built), so the
>    model edits are grounded in a real implementation shape.
>
> **Template precedent:** the existing **`sequence`** diagram-type module (`src/diagram_types/sequence/`)
> — a module with its own `ontology.yaml` (diagram-local entity + connection types), `config.yaml`
> (UI + `type_ui_slots` for a bespoke editor), `renderer.py`, and an **`allowed_bindings`** block that
> maps each diagram entity to model entities via correspondence kinds (`represents`, `traces-to`).
> The datatype module follows this shape exactly; the binding mechanism is how a classifier links to a
> Data Object.
>
> **Companion plans:** `PLAN-meta-ontology-v2.md` (diagram↔model bindings — the correspondence machinery
> we reuse), `PLAN-diagram-puml-editing.md` (body-authoring + render/validate pipeline we reuse),
> `PLAN-sequence-diagram-authoring.md` (the bespoke-editor pattern via `type_ui_slots`).

---

## 0. Framing & anchoring

The existing model is the architecture of the **Architecture Management System**. Diagramming is an
already-modelled capability: `BOB@1777230085.eGCeZq` *Diagram* is specialized by *ArchiMate Diagram*
and *Matrix Diagram*; `BOB@1777390172.7gJz0U` *Diagram Type Definition* realizes `REQ@1777370410.qpOBOQ`
*Configurable diagrams* (itself aggregated by `REQ@1777369404.aDohcf` *Extensibility & Configurability*).
Diagram-type modules are loaded by `APP@1712870400.yNhgdh` *Module Catalog* and rendered by
`APP@1777293136.yaxrWl` *PlantUML Renderer* into `DOB@1777239791.4Z28xK` *Textual Diagram Representation*.

The motivation layer **already names this view**: `REQ@1712870400.Ii5Jj5` *"ArchiMate and UML
ER/Sequence/Activity Diagrams"* explicitly scopes *"ER diagrams (for data models)… reference model
entities… maintaining traceability."* Sequence and activity are realized; **ER / datatype is not** — and
the user has clarified it should be implemented as a **restricted UML class diagram**. The `er`
**connection language** (`er-one-to-one`, `er-one-to-many`, `er-many-to-many`) already exists in
`src/ontologies/archimate_next/connections.yaml` but is **orphaned** — no diagram type consumes it and
the model has **0** connections of those types. So the work is: add the diagram surface, the classifier
element vocabulary, the Data-Object binding, and the **backing-relation integrity rule** — then anchor
all of it into the model.

**Do NOT model** (Pareto / "model only what is built"): one entity per classifier-kind enum value; one
entity per UML metaclass; per-PUML-directive elements; the strategy or technology domains (this change
concerns neither the business structure nor infrastructure). Keep to motivation + common + business +
application.

---

## 1. UML naming — precise, with the gaps named

The user requires **UML-official naming where possible**, and **first-class Class, DataType, Enum and
Variant** kinds. UML 2.5.1 reality, stated exactly:

| Concept | Is it a UML metaclass? | UML-precise representation | How we author it |
|---|---|---|---|
| **Class** — *entity* (identity) | ✅ **`Class`** | a classifier **whose instances have identity** (two instances with identical attribute values are still distinct); owns attributes (operations suppressed in this restricted view) | `classifier_kind: class` — DDD *entity* / identity-bearing type |
| **DataType** — *value object* (value equality) | ✅ **`DataType`** | a classifier **whose instances are identified only by their value** (no identity; conceptually immutable); a *structured* DataType owns attributes | `classifier_kind: datatype` — DDD *value object*; the home of "records" |
| **Enum** | ✅ **`Enumeration`** (a kind of `DataType`) | `Enumeration` owning ordered **`EnumerationLiteral`**s | `classifier_kind: enumeration` — literals authored as a string list |
| **Variant** (sum / tagged union) | ❌ no `Variant`/`Union` metaclass | an **abstract `Classifier`** specialized by its case classifiers via **`Generalization`**, grouped in a **`GeneralizationSet {complete, disjoint}`** — the canonical UML way to say *"a value is exactly one of these cases"* | `classifier_kind: variant` (renders abstract, `«variant»`); each case is a classifier linked by a `dt-generalization`; the cohort carries `{complete, disjoint}` |
| **Primitive** | ✅ **`PrimitiveType`** (a kind of `DataType`) | a `DataType` with no internal structure (Integer, String, …) | `classifier_kind: primitive` (optional, for field types) |

**Class vs. DataType is the entity / value-object axis** (confirmed): `Class` = identity-bearing
*entity*; `DataType` = value-equality *value object*. Both are **co-equal first-class kinds** — neither is
a fallback for the other. "Record" is not a UML metaclass; it is a loose product-type label that lands on
`DataType` (a structured value object) — or on `Class` if the record needs identity.

**Naming decisions (locked):**
- The diagram-local element type is a single **`classifier`** entity carrying a **`classifier_kind`**
  enum: `class | datatype | enumeration | variant | primitive`. One shape (name + attribute
  compartment), one renderer, one binding rule — kinds differ only in keyword/stereotype, abstractness,
  and which compartments render. This keeps Enums and Variants **first-class authoring kinds** without an
  entity-type explosion (mirrors how `sequence`'s `message` uses a `kind` discriminator rather than N
  message types). **`class` and `datatype` are both first-class** — the editor surfaces them as equal
  choices with their identity/value semantics, not as a default + fallback.
- An **attribute** is the UML term for a field; attributes are a **property array** on the classifier
  (per the locked decision: *fields as properties, not entities*), each `{ name, type, multiplicity,
  is_id (PK), is_unique, default? }`. `multiplicity` uses UML notation (`1`, `0..1`, `1..*`, `*`).
- **`EnumerationLiteral`s** are a separate string list property on `enumeration` classifiers.
- "Record" / "ER" / "datatype" are kept only as **purpose labels** in UI copy and docs; the **element
  vocabulary is UML-official**.

**Diagram-type slug:** `datatype` (label *"Datatype Diagram"*, subtitle *"a UML class diagram restricted
to data structure"*). Rationale: the official UML diagram is the *Class Diagram*, but this is a
deliberately **restricted** profile (data only) and "datatype" matches both the user's framing and the
Bizzdesign Horizzon convention. The element names remain UML-official, so precision is preserved where it
matters. *(Decision §10.1 records the `class` alternative.)*

---

## 2. Connection vocabulary — UML structural relations

The orphaned `er-one-to-one/-one-to-many/-many-to-many` types are **ER/crow's-foot** terms, not UML, and
encode cardinality in the *type name*. The UML-precise model expresses cardinality as **Association-end
multiplicity**, which the system already supports as first-class connection fields
(`src_cardinality`/`tgt_cardinality`, values `1` / `0..1` / `1..*` / `*`). We therefore define a
**module-owned, UML-named** relation set and represent cardinality via those fields:

Each `dt-*` type declares an explicit **`relationship_kind`** (the semantic correspondence axis) plus
`symmetric`. `relationship_kind` is a **first-class field separate from the visual `classes`** tags
(`nesting`, `dynamic`, …) so correspondence never depends on excluding layout tags by hand:

| Connection type | UML metaclass | `relationship_kind` | `symmetric` | Renders | Cardinality |
|---|---|---|---|---|---|
| `dt-association` | `Association` | `association` | true | solid line | end multiplicity via `src_cardinality`/`tgt_cardinality` → subsumes 1:1, 1:N, N:M |
| `dt-aggregation` | `Association` (aggregationKind = shared) | `containment` | false | hollow diamond | whole/part, shared |
| `dt-composition` | `Association` (aggregationKind = composite) | `containment` | false | filled diamond | whole/part, exclusive (DOB-bound ⇒ refinement of an aggregation backing — §3.2) |
| `dt-generalization` | `Generalization` | `generalization` | false | hollow triangle | class inheritance **and** variant cases |
| `dt-dependency` | `Dependency` («use») | `dependency` | false | dashed arrow | optional, e.g. field-type reference |

**`relationship_kind`:** an explicit scalar on the connection-type schema, set on the
correspondence-bearing ArchiMate types (`archimate-specialization → generalization`,
`archimate-aggregation`/`-composition → containment`, `archimate-association → association`) and on the
`dt-*` types above. Visual tags stay in `classes`. Correspondence (§3.2) matches on `relationship_kind`
equality.

**Loader prerequisite:** the diagram ontology loader drops connection metadata today —
`_parse_connection_types` (`diagram_ontology_loader.py:106`) populates only
`embedding`/`embed_key`/`cascade_delete_source`. It must be expanded to populate
`relationship_kind`/`symmetric`/`classes`/`puml_arrow` on `ConnectionTypeInfo` before any of the above is
observable for diagram-owned types (Phase 0, WU-0.2).

**`er-*` relationship to this work (§10.2):** `dt-*` are **diagram-local** relations between diagram-local
`classifier`s — a *different layer* from the base-ontology `er-*` types, which are **model-level
connections between `data-object` entities** and are **in active use in ENG-001** (8 artifacts incl.
`application-class-er-domain-model-v1.puml`). `er-*` are therefore **deprecated, not removed**, in this
change; ENG-001 is migrated to ArchiMate-backed model relations (§4.6), after which `er-*` are removed.
The new datatype diagram does **not** depend on `er-*`.

---

## 3. Data-Object binding + the backing-relation integrity rule (the crux)

### 3.1 Binding (entity binding + connection binding)
A `classifier` binds to a model `data-object`; a `dt-*` edge binds to the **backing model connection**
between the bound Data Objects. The metadata lives in **two distinct config locations**:
`permitted_mappings` on the **entity type**, while `allowed_bindings` carries **correspondence semantics
only** — exactly as the `sequence` module already splits them.

```yaml
entity_types:
  classifier:
    # ... classifier_kind, attributes, literals, is_abstract ...
    permitted_mappings:               # ← on the entity type
      entity_types: [data-object]
    mapping_required: false           # binding is optional

allowed_bindings:
  entity:
    classifier:                        # ← correspondence semantics only
      correspondence_kinds: [represents, traces-to]
      default_correspondence_kind: represents
      target_forms: [entity-id, diagram-local]
  connection:                          # ← dt-* edge ↔ backing model connection
    dt-association:                    # (one block per dt-* type)
      target_connection_classes: [association]   # by relationship_kind (§2)
      correspondence_kinds: [represents, refines]
      default_correspondence_kind: represents
      target_forms: [connection-id]
```

Semantics: the **classifier is the fine-grained schema**; the **Data Object is the architectural data
element** it details. Entity binding is **optional** — a classifier may be a pure diagram-local schema
detail and carry no binding. When **both** ends of a `dt-*` edge are DOB-bound, the edge **must** also be
connection-bound to a backing model connection (§3.2). Connection binding uses the `connection-id` target
form, which `ConnectionBindingSpec` already supports and the c4/sequence modules already use (only
`connection-path` is deferred to `PLAN-meta-ontology-v2.md` Phase 3).

### 3.2 The consistency rule (bidirectional, via connection binding)
> When **two classifiers are both bound to Data Objects**, the `dt-*` edge between them **must be
> connection-bound to exactly one backing model connection** that (a) joins those two Data Objects and
> (b) has a **matching `relationship_kind` and compatible direction**. Enforced both ways:
> - **Forward** — a `dt-*` edge with no corresponding backing connection is a **verification error** with
>   a quick-fix to create the connection **and** the binding.
> - **Reverse** — an existing backing connection **constrains which `dt-*` kinds are admissible**; a
>   non-corresponding kind/direction is rejected. *(Data Objects linked by specialization admit only
>   `dt-generalization` in the same direction — no `dt-association`, no inverse generalization.)*

**Binding to the exact connection removes the multiplicity ambiguity.** If two Data Objects carry several
relations (e.g. association *and* aggregation), the rule is not "any backing permits" vs. "all must
match" — the `dt-*` edge names the **one** connection it corresponds to, and verification checks *that*
connection. This also gives the quick-fix a precise artifact to create and bind.

**Derivation — no hardcoded `dt-*`→`archimate-*` table.** Correspondence is computed from ontology
metadata. Each connection type declares `relationship_kind` (§2) and `symmetric`. The predicate is:

1. **Kind match:** `dt-edge.relationship_kind == backing.relationship_kind`.
2. **Endpoint match:** the backing connection's endpoints are exactly the two bound Data Objects.
3. **Direction match:** for `symmetric: false`, the classifier-edge direction equals the Data-Object-edge
   direction (child→parent, whole→part); for `symmetric: true` (`association`), either direction satisfies.

The only thing in **code** is this abstract predicate — *matching `relationship_kind` + endpoints +
compatible direction*. Which DOB→DOB relations are *legal* comes from `permitted_relationships`; which
`dt-*` kinds correspond comes from `relationship_kind`. Adding/retagging a relationship type changes
behaviour with **no verifier or GUI code change**.

Worked through the current ontology (illustrative, **not** a constant): DOB→DOB legally permits
`specialization` (kind `generalization`), `aggregation` (kind `containment`), `association` (kind
`association`). So: a specialization backing ⇒ only same-direction `dt-generalization`; an aggregation
backing ⇒ `dt-aggregation` or `dt-composition` (both kind `containment`, whole→part); an association
backing ⇒ `dt-association` (either direction).

**`dt-composition` is a refinement of an aggregation backing.** DOB→DOB does not permit
`archimate-composition`, so a DOB-bound `dt-composition` binds to an `archimate-aggregation` (same
`containment` kind) and the verifier message states it is recorded as a *containment refinement* (exclusive
ownership is asserted at the schema level, not the architectural level). For **unbound** classifiers,
`dt-composition` is unconstrained.

**Scope of the rule (precise):**
- Fires **only when both ends are DOB-bound.** A `dt-*` touching an unbound classifier (pure diagram-local
  schema detail) is unconstrained and needs no connection binding.
- Checks the **named backing connection** (kind + endpoints + direction), not direction-blind graph
  presence.
- A **diagram-verification** concern (datatype diagram's verifier), realized through the existing
  verification capability — see §6. Emits the extended diagnostic of §3.3.

### 3.3 Diagnostic contract + authoring/quick-fix (ontology-sourced)
**Diagnostic contract (prerequisite).** `Issue` carries only `severity/code/message/location` today; extend
it with optional structured `details` and `actions` (and serialize through REST/MCP/GUI) so the quick-fix
is **data-driven, never parsed from message strings**. The forward error's `details` carry
`{dob_source, dob_target, dt_relationship_kind, permitted_backing_kinds (ontology-derived), preferred_default}`.

**Authoring + quick-fix — option sets sourced from the live ontology at runtime, exactly as every other
relation-create/edit component (no hardcoded list):**
- **Backing connection already exists:** the relation editor offers only the `dt-*` kinds whose
  `relationship_kind` corresponds (per §3.2); a non-corresponding choice is never presented, and selecting
  a kind auto-establishes the connection binding to that backing connection.
- **No backing connection yet:** drawing a `dt-*` raises the forward error; the quick-fix offers the
  relation types the **ontology permits between the two Data Objects** (reusing the generic connection
  editor's pair-legality lookup — `artifact_authoring_guidance(filter=[DOB], target=DOB)` / its in-GUI
  equivalent), pre-selecting the kind matching the drawn `dt-*`. Accepting issues `artifact_add_connection`
  (DOB→DOB) **and** records the `dt-*`→connection binding, then re-verifies and clears the error.

This reuses the existing verifier-in-the-authoring-loop pattern (`APP@…ca3vm7` *Model Verifier* serves the
GUI tool).

---

## 4. Model adaptation — per domain

IDs below are existing anchors unless marked **NEW** / **EDIT**. All connection types are pair-checked at
authoring (`artifact_authoring_guidance(filter=[Src], target=Tgt)`); where a REQ→REQ/OUT relation is
uncertain it is noted as *pair-check at authoring*.

### 4.1 Motivation
| Action | Element | Wiring |
|---|---|---|
| **EDIT** | `REQ@1712870400.Ii5Jj5` *ArchiMate and UML ER/Sequence/Activity Diagrams* | Update summary: ER/data view is realized as a **restricted UML class (datatype) diagram**; no other change. |
| **NEW REQ** | *Datatype (UML Class) Diagram Authoring* — "The system shall provide a datatype diagram: a UML class diagram restricted to data structure, supporting Class, DataType, Enumeration and Variant classifiers with typed attributes and UML structural relations (association, aggregation, composition, generalization)." | `archimate-specialization` → `REQ@…Ii5Jj5`; `archimate-aggregation` ← `REQ@1777370410.qpOBOQ` *Configurable diagrams* (new pluggable type) |
| **NEW REQ** | *Datatype–Data Object Relationship Consistency* — "A classifier may be bound to a Data Object; a structural relation between two Data-Object-bound classifiers and the ArchiMate relation between their Data Objects must correspond in semantic class and direction — enforced bidirectionally on verification and in authoring, with permitted relation types derived from the configured ontology, never hardcoded." | `archimate-aggregation` ← `REQ@1712870400.Ee3Ff3` *Verified Referential Integrity* (a specific integrity rule, part of the whole); `archimate-influence`/`archimate-realization` → `OUT@1776629109.YSRwR0` *…Hand-Off Points Explicitly Verifiable* (*pair-check at authoring*) |

### 4.2 Common (behaviour)
| Action | Element | Wiring |
|---|---|---|
| **NEW function** | *Validate Datatype–Data Object Relationship Consistency* — evaluates the §3.2 bidirectional class/direction correspondence on every datatype-diagram write (deriving permitted kinds from the ontology) and emits the error + ontology-sourced quick-fix payload. | `archimate-realization` → `SRV@1776699512.vQKsM9` *Diagram Verification Service*; `archimate-association` ← the new application module (§4.4); `archimate-association` ← `APP@1776149382.lmO0mp` *GUI Authoring Tool* (surfaces + remediates) |
| **NEW function** | *Author Datatype Diagram* — create/edit classifiers, attributes, literals, relations, and Data-Object bindings. *(Create only if no existing generic diagram-authoring function fits; otherwise extend that one — confirm at authoring to avoid duplication.)* | `archimate-realization` → existing Diagram Authoring service/function; `archimate-association` ← new application module (§4.4) |

*Rationale for minimalism:* the genuinely new behaviour is the **integrity validation**. Authoring,
rendering, preview, and persistence reuse existing capability (Diagram Scaffolder `APP@…SCKD2U`, PlantUML
Renderer, body-authoring pipeline). We add at most one authoring function and only if no host exists.

### 4.3 Business (concepts)
| Action | Element | Wiring |
|---|---|---|
| **NEW business-object** | *Datatype Diagram* — the conceptual datatype/class view. | `archimate-specialization` → `BOB@1777230085.eGCeZq` *Diagram* (parallel to ArchiMate Diagram / Matrix Diagram); `archimate-realization` → new REQ *Datatype (UML Class) Diagram Authoring* |
| **NEW business-object** | *Classifier* — the UML classifier concept (Class / DataType / Enumeration / Variant) with typed attributes. | `archimate-association` → `BOB@1777239017.bIR3Oj` *Attribute Schema* (attributes follow a schema); `archimate-aggregation` ← *Datatype Diagram* (a diagram aggregates its classifiers) |

*Deliberately excluded:* a business "Data Object" concept and a "Binding" concept. The Data Object already
exists as an **application** element (`data-object`); the binding is a diagram-level correspondence, not a
business concept — modelling it here would be redundant cross-layer duplication.

### 4.4 Application (software)
| Action | Element | Wiring |
|---|---|---|
| **NEW application-component** | *Datatype Diagram Type Module* — the pluggable code unit `src/diagram_types/datatype/` (ontology, config, renderer, bindings). | `archimate-aggregation` ← `APP@1712870400.yNhgdh` *Module Catalog* (loaded as a registered diagram type); `archimate-realization` → new REQ *Datatype (UML Class) Diagram Authoring* |
| **WIRE existing** | `APP@1777293136.yaxrWl` *PlantUML Renderer* | `archimate-serving` → *Datatype Diagram* concept / `archimate-access` → `DOB@1777239791.4Z28xK` *Textual Diagram Representation* (reused; **no new DOB**) |
| **WIRE existing** | `APP@1712870400.ca3vm7` *Model Verifier* | `archimate-realization` → new function *Validate Datatype–Data Object Relationship Consistency* (enforces §3.2); already `archimate-serving` → GUI Authoring Tool (quick-fix surface) |

**Application inventory:** 1 new component + 3 wiring connections to existing components. Reuses Renderer,
Textual Diagram Representation, Model Verifier, Module Catalog, GUI Authoring Tool — no duplication.

### 4.5 Totals
≈ **7 new entities** (2 REQ, 2 function, 2 BOB, 1 APP) + **1 edit** + **≈14 connections** — the second
common-domain function is conditional (only if no existing authoring host fits). Small, Pareto-focused,
all anchored to existing narrative.

### 4.6 ENG-001 migration (in scope)
ENG-001 holds the prior, file-based attempt at this capability: 8 `er-*` model connections between
`data-object` entities plus `application-class-er-domain-model-v1.puml`. This work **migrates it**:

1. Study `application-class-er-domain-model-v1.puml` as prior art for the renderer and editor UX.
2. Replace each `er-*` model connection with an ArchiMate-backed relation between the Data Objects
   (`archimate-association` carrying end cardinality, or `aggregation`/`specialization` as appropriate).
3. Re-author the ER domain model as a `datatype` diagram, with classifiers bound to those Data Objects.
4. Once no repository loads `er-*`, remove the `er-*` connection types from the ontology.

Until step 4, `er-*` remain **deprecated but loadable** so ENG-001 verifies cleanly throughout.

---

## 5. Code / ontology design (what the model describes)

New module `src/diagram_types/datatype/`, mirroring `sequence/`:

```
src/diagram_types/datatype/
  __init__.py        ← exports `module`; registers the diagram type
  config.yaml        ← name, ui label/description, type_ui_slots (bespoke classifier/attribute editor),
                       diagram_only_types (classifier), guidance (when_to_use / when_not_to_use)
  ontology.yaml      ← classifier entity type (+ permitted_mappings → data-object on the ENTITY type),
                       dt-* connection types (relationship_kind, symmetric), allowed_bindings
                       (entity correspondence + connection→backing-connection)
  renderer.py        ← restricted UML class-diagram PUML emitter (no operation compartment)
```

> **Phase 0 prerequisites.** Before the module can work as designed: (a) extend the `Issue` diagnostic
> contract with structured `details`/`actions` + REST/MCP/GUI serialization; (b) expand
> `diagram_ontology_loader._parse_connection_types` to populate `relationship_kind`/`symmetric`/`classes`/
> `puml_arrow`; (c) add the `relationship_kind` field to the connection-type schema and set it on the
> correspondence-bearing ArchiMate types.

**`ontology.yaml` highlights:**
- `entity_types.classifier` with `classifier_kind` enum (`class|datatype|enumeration|variant|primitive`),
  `attributes` (array of `{name, type, multiplicity, is_id, is_unique, default}`), `literals` (enum only),
  `is_abstract` (auto-true for `variant`), `generalization_set` (`{is_covering, is_disjoint}`), and
  **`permitted_mappings.entity_types: [data-object]` on the entity type** + `mapping_required: false`.
- `connection_types`: `dt-association`, `dt-aggregation`, `dt-composition`, `dt-generalization`,
  `dt-dependency` (`embedding: none`), each declaring **`relationship_kind`** + `symmetric` (§2) so the
  §3.2 correspondence is derivable, not hardcoded.
- `allowed_bindings.entity.classifier` → correspondence semantics only; `allowed_bindings.connection.<dt-*>`
  → `target_connection_classes`/`target_connection_types` (the backing relationship kind) + `target_forms:
  [connection-id]` so a `dt-*` edge binds to its exact backing model connection (§3.1).

**`config.yaml` highlights:** `type_ui_slots` pointing at a `datatype-editor` Vue slot (the
classifier/attribute table editor — same mechanism as `sequence-editor`); `diagram_only_types: [{entity_type: classifier, label: Classifier, plural: Classifiers}]`; `entity_search_filter: false`.

**Renderer:** emits `class`/`enum`/`abstract class` with `<<datatype>>`/`<<enumeration>>`/`<<variant>>`
stereotypes, attribute compartment only (operations suppressed), crow's-foot-free UML notation, relation
arrows per §2, end multiplicities from cardinality fields. Obeys the project PUML rules (no `\n` in
labels, `linetype ortho`, named containers, real-element hidden edges only).

**Verifier:** new error code(s) implementing the §3.2 bidirectional rule in the diagram verifier — e.g.
*missing corresponding backing relation* (forward) and *datatype relation inconsistent with existing Data
Object relation* (reverse, wrong class/direction). Returns a structured payload (the two DOB ids + the
ontology-derived permitted/corresponding relation kinds + preferred default) that the GUI quick-fix
consumes. The verifier consumes `ConnectionTypeInfo.relationship_kind`/`.symmetric` +
`permitted_relationships`; it contains **no** `dt-*`→`archimate-*` constant.

**Cross-cutting:** regenerate `tools/generate_types.py` → `types.generated.ts` (ontology change, pre-commit
hook enforces); add the `datatype-editor` Vue component + quick-fix UI in `tools/gui`; deprecate `er-*`
and migrate ENG-001 (§4.6); register the module in the diagram-type registry.

---

## 6. Build order

> **Execution ledger:** `TASKS-datatype-er-diagrams.md` breaks this order into checkbox work units
> (WU-A1 … WU-F3) with file paths, per-unit acceptance criteria, dependencies, a resume protocol, and a
> progress log — the actionable, session-resumable form of the steps below.

**Code track** (backend contracts before GUI):
0. **Phase 0 — contracts & loader.** Extend `Issue` (`details`/`actions` + serialization); add
   `relationship_kind` to the connection schema + base ArchiMate types; expand the diagram ontology
   loader to parse connection metadata. Nothing downstream is sound until these land.
1. **Module + verifier.** Scaffold `src/diagram_types/datatype/`; ontology/config/renderer; correspondence
   **predicate** + verifier integration (forward + reverse) emitting the structured diagnostic.
2. **GUI against stable fixtures.** Editor + connection-binding + quick-fix, built on the now-frozen
   diagnostic/guidance API; regenerate types.
3. **er-* / ENG-001.** Deprecate `er-*`; migrate ENG-001 (§4.6); remove `er-*` once no repo loads them.

**Model track (MCP, can proceed in parallel with code):**
1. **Motivation first → confirm.** Edit `REQ@…Ii5Jj5`; create the two REQs; wire. *(Stop gate per skill.)*
2. **Business + common.** Datatype Diagram + Classifier BOBs; the **validation function** (authoring
   function only if a query proves a per-type pattern exists).
3. **Application.** Datatype Diagram Type Module; wire Renderer / Model Verifier / Module Catalog / GUI.
4. **Diagrams.** A small `archimate-application` view (module + Renderer + Module Catalog + Verifier + the
   two REQs). Optionally a classifier→data-object binding matrix once instances exist.
5. **Verify + save.** `artifact_verify(repo_scope="engagement", return_mode="full")` → 0 errors; resolve
   warnings on touched entities; `artifact_save_changes`.

Gates after each code phase (pytest / ruff / zuban; frontend lint + typecheck). Full WU breakdown +
dependencies in `TASKS-datatype-er-diagrams.md`.

---

## 7. Verification plan (code track)
- **Phase 0 contracts:** `Issue.details`/`actions` round-trip through REST/MCP/GUI serialization;
  `relationship_kind` parsed on base + diagram-owned connection types; loader populates
  `relationship_kind`/`symmetric`/`classes`/`puml_arrow`.
- **Unit:** classifier/attribute/literal authoring; each `dt-*` relation; cardinality→multiplicity render;
  variant → abstract + `{complete, disjoint}` generalization set.
- **Binding:** classifier→data-object entity correspondence accepted; `dt-*`→backing-connection binding
  accepted; unbound classifier unconstrained.
- **Consistency (regression, reproduces the user scenario):** two DOB-bound classifiers with a
  `dt-association` and **no** backing connection → **forward error**; after creating + binding an
  `archimate-association` → **clean**. Specialization backing + `dt-association` (or inverse
  `dt-generalization`) → **reverse error**. Multiple backings (assoc + aggr): the edge binds to the named
  one and verifies against *that* (no ambiguity).
- **Quick-fix:** structured `details` carry the ontology-derived permitted kinds + preferred default;
  accepting creates the connection **and** the binding and clears the error.
- **`dt-composition` refinement:** DOB-bound `dt-composition` binds to an aggregation backing and the
  message states "containment refinement"; unbound `dt-composition` unconstrained.
- **Renderer:** PUML validates (no operations compartment; renders for all five `classifier_kind`s).
- **MCP/REST surface:** `artifact_authoring_guidance` returns classifier/`dt-*` guidance + DOB
  pair-legality; `artifact_create_diagram`/`artifact_edit_diagram` accept the datatype type;
  `artifact_help` lists it; REST diagram routes render it; type-gen emits the new enums. **Assurance MCP:
  asserted unchanged** (no datatype dependency).

---

## 8. Risks & mitigations
- **Dual source of truth** (diagram relation vs. model relation) → mitigated: the model connection is
  **authoritative**; the `dt-*` edge is invalid unless connection-bound to it (§3.2), so they cannot diverge.
- **Over-modelling the schema** → fields/literals are **properties**, not entities; classifiers bind only
  when architecturally significant.
- **Composition refinement** (DOB→DOB forbids `archimate-composition`) → `dt-composition` binds to an
  aggregation backing as an explicit *containment refinement*; stated in the verifier message and docs so
  the weaker architectural semantics are visible, not silent.
- **Cross-module `relationship_kind` drift** → the relationship-kind vocabulary is the one cross-module
  contract; a registry test asserts every `dt-*` `relationship_kind` exists in the base set and is distinct
  from visual `classes`, so a typo fails CI rather than silently disabling correspondence.
- **`er-*` in active use** → ENG-001 uses `er-*` (incl. a diagram); **deprecate, do not remove**; migrate
  ENG-001 (§4.6); remove only once no repo loads them. The migration greps all repos before removal.

---

## 9. Out of scope
- Reverse-engineering datatypes from source code or DB schemas (future).
- Operation/method modelling (this is a **restricted** class diagram — structure only).
- Generating Data Objects automatically from classifiers (binding is explicit, human/agent-driven).
- Strategy/technology-domain model changes.

---

## 10. Decisions
- **§10.1 Diagram slug `datatype`** (vs `class`) — for purpose-clarity + Bizzdesign alignment; element
  names stay UML-official.
- **§10.2 Deprecate `er-*`, do not remove.** `er-*` are model-level DOB connections in active use in
  ENG-001; the datatype diagram uses diagram-local `dt-*` and does not depend on them. Migrate ENG-001 to
  ArchiMate-backed relations (§4.6), then remove `er-*`.
- **§10.3 Single `classifier` entity + `classifier_kind` enum** (vs distinct entity types per kind) — one
  shape/renderer/binding; Enums & Variants remain first-class authoring kinds.
- **§10.4 Variant = abstract Classifier + `GeneralizationSet {complete, disjoint}`** — the UML-canonical
  sum type; there is no UML `Variant` metaclass.
- **§10.5 Fields/literals as properties, not entities.**
- **§10.6 Rule fires only when both ends are DOB-bound**; unbound classifiers need no backing/binding.
- **§10.7 `Class` and `DataType` are co-equal first-class kinds on the entity / value-object axis:**
  `Class` = identity-bearing entity; `DataType` = value-equality value object. Neither is the other's
  fallback.
- **§10.8 Permitted relations sourced from the live ontology, never hardcoded.** Verifier and GUI derive
  DOB→DOB legality from the configured ontology's pair-legality (same source as all relation-create/edit
  components).
- **§10.9 Bidirectional rule enforced via connection binding.** A `dt-*` edge between two DOB-bound
  classifiers binds to the **exact backing model connection**; verification checks *that* connection's
  `relationship_kind` + endpoints + direction. Forward (missing) and reverse (non-corresponding) both
  enforced.
- **§10.10 Explicit `relationship_kind` field** on the connection-type schema, separate from visual
  `classes` (`nesting`/`dynamic`). Set on the correspondence-bearing ArchiMate types + `dt-*`;
  correspondence matches on it.
- **§10.11 Phase 0 backend prerequisites:** extend the `Issue` diagnostic contract with structured
  `details`/`actions` (+ serialization); expand the diagram ontology loader to parse connection metadata.
- **§10.12 `permitted_mappings` on the entity type, not `allowed_bindings`;** connection binding (`dt-*` →
  backing connection) via `ConnectionBindingSpec`/`connection-id`.
- **§10.13 `dt-composition` (DOB-bound) = explicit refinement of an aggregation backing;** unconstrained
  for unbound classifiers.
- **§10.14 Validation function only in the self-model;** route authoring through the existing concept
  unless a query proves a per-type authoring pattern. Assurance MCP unchanged.
