# PLAN — ArchiMate 4 Compliance (Functional + License)

**Status**: draft — awaiting review
**Scope**: migrate the central meta-ontology from ArchiMate NEXT Snapshot 1 to the final
ArchiMate 4.0 standard (functional compliance), and remove all ArchiMate-derived authoring
guidance from the shipped source in favour of an externally hosted, importable guidance file
(license compliance).
**Companion**: `TASKS-archimate-4-compliance.md` (execution ledger),
`PLAN-OUTLINE-archimate-4-compliance.md` (spec-delta research basis; superseded by this plan
as the working document).

---

## 1. Problem Statement & Business Context

The tool's central meta-ontology (`src/ontologies/archimate_next`) implements the ArchiMate
NEXT Snapshot 1 *draft*. The Open Group has now released **ArchiMate 4.0** as the approved
standard, superseding the snapshot. Two compliance obligations follow:

1. **Functional compliance** — the final standard differs from the snapshot in ways that are
   implementation-relevant (composition restored, multiplicity terminology, specialization
   mechanism, viewpoint mechanism now mandatory for conforming tools, exchange-format
   reference moved to C19C v3.1). The README currently disclaims conformance ("geared toward
   the ArchiMate NEXT draft; no conformance claim"); after this plan the tool should be able
   to document alignment with ArchiMate 4.
2. **License compliance** — the `create_when` / `never_create_when` authoring-guidance prose
   in the ontology YAML derives from the ArchiMate specification text and cannot ship inside
   this MIT-licensed repository. It must be extracted to a separately hosted YAML file,
   initialized empty in-repo, and made importable via CLI from a configurable source.

The self-model (ENG-ARCH-REPO) must follow: its 155 `archimate-aggregation` connections need
a composition review, its ADRs record the ontology adoption decision, and its naming
references the draft.

## 2. Current State (verified 2026-07-09)

Facts the design rests on, from code survey:

- **Three identifier tokens** name the ontology, resolved in different namespaces:
  - package/dir `archimate_next` — Python imports + diagram `config.yaml` `ontology:` field
    (resolved via importlib, `src/diagram_types/_config_type.py:52`);
  - module name `archimate-next-snapshot1` — `ModuleRegistry` key
    (`src/ontologies/archimate_next/_loader.py:38`), used by c4 `ontology.yaml` sources and
    bridges, `c4/_projection.py:341`, frontend `tools/gui/src/ui/lib/domains.ts:49,61`;
  - meta-ontology alias `archimate-next` — `_META_ONTOLOGY_ALIASES`
    (`src/infrastructure/app_bootstrap.py:164-167`), the only token persisted in repo data
    (`meta_ontology:` in `.arch-repo/groups.yaml`; **no repo currently sets it**).
  - **Latent defect**: `activity/datatype/sequence` `ontology.yaml` `permitted_mappings.sources[].ontology`
    use the *package* name where resolution (`src/domain/permitted_mappings.py:24` →
    `registry.find_ontology`) keys on the *module* name. The c4 configs use the module name.
- **Entity/connection type names** (`business-actor`, `archimate-aggregation`, …) are what
  artifact frontmatter persists. They do **not** change under ArchiMate 4 → the rename needs
  **no model-artifact data migration**.
- **Composition already exists** as `archimate-composition` in
  `src/ontologies/archimate_next/connections.yaml` (`hierarchy_priority: 1`,
  `relationship_kind: containment`), but the self-model uses zero of them (155 aggregations).
  Snapshot-era assumptions must be re-verified against final §5.1.2 / Appendix B.
- **Guidance** (`create_when`/`never_create_when`) lives only in
  `src/ontologies/*/entities.yaml` (archimate_next, sysml_v2_min, assurance) and in
  diagram-type `own_entity_types` (`src/diagram_types/*/ontology.yaml`). One loader path per
  module (`_load_entity_types`) and one consumer
  (`src/infrastructure/write/artifact_write/type_guidance.py::get_type_guidance`, cached via
  `@lru_cache` on `_registry()`), surfaced by MCP `artifact_authoring_guidance` and REST
  `GET /api/authoring-guidance`. Connection types carry **no** guidance fields.
- **Attribute profiles** exist twice:
  - the **active, declarative, per-repo** mechanism: `.arch-repo/schemata/attributes.{artifact_type}.schema.json`
    (+ `connection-metadata.{type}.schema.json`), loaded by
    `src/application/artifact_schema.py`, scaffolded by
    `src/infrastructure/workspace/_repo_default_schemata.py`;
  - a **dormant** ontology-module surface: `OntologyModule.attribute_profiles`
    (`src/domain/ontology_protocol.py:82`) with a hardcoded Python dict only in the assurance
    module (`src/ontologies/assurance/_loader.py:20-106`) — no registry aggregation, no
    GUI/MCP consumer found.
- **Multiplicity** partially exists as `ConnectionRecord.src_cardinality` /
  `tgt_cardinality` (`src/domain/artifact_types.py`), rendered by
  `format_cardinality_label`, surfaced via the `include_cardinality` diagram annotation.
- **No model-exchange import/export** exists. Adapter families live under
  `src/infrastructure/{git,rendering,write,…}`; read ports in `src/application/ports.py`;
  the dependency policy is AST-enforced (`tests/architecture/test_dependency_policy.py`).
- **Diagram→model relation mechanisms** that overlap with the viewpoint concept:
  per-diagram-type entity filters (`_config_type.py::_build_entity_filter`,
  `filter.hierarchy_level`), `DiagramTypeModule.accepts_entity_type/accepts_connection_type`
  + `effective_entity_types`/`effective_permitted_relationships`, and binding-target
  admissibility (`permitted_mappings` / `src/domain/allowed_bindings.py`). The GUI consumes
  these via `GET /api/diagram-types/{t}/ui-config` and `GET /api/ontology`.

## 3. Locked Decisions

These are the load-bearing choices; §4 gives the rationale and alternatives for the
non-obvious ones.

- **D1 — Full three-token rename.** Package → `src/ontologies/archimate_4`, module name →
  `archimate-4-0`, meta-ontology alias → `archimate-4`. The alias layer stays the
  version-absorbing seam (a future 4.1 = new module name, same alias). No legacy
  `archimate-next` alias is retained (no deployed `meta_ontology:` values exist; pre-1.0
  clean break). The `permitted_mappings` token inconsistency is fixed as part of the rename:
  **module name is the only valid value** for `permitted_mappings.sources[].ontology` and
  bridge `to.module`, enforced by a startup/verifier check.
- **D2 — Guidance becomes an overlay, empty by default.** `EntityTypeInfo.create_when` /
  `never_create_when` remain, but ship as `""` for the ArchiMate module. A domain
  `GuidanceOverlay` is loaded at bootstrap from a local, gitignored guidance directory and
  merged into the module's entity types at load time. Import happens via a new CLI command
  from a configurable URL/path. The extracted guidance file is **never committed** to this
  repository.
- **D3 — Guidance file schema is module-scoped and specialization-aware** (see §5.2): keyed
  by meta-ontology alias → entity type → optional specializations, with reserved keys for
  connection-type guidance (not populated now).
- **D4 — Specializations are enumerated in dedicated declaration files, not implicitly by
  attribute-profile files.** Ontology modules ship a `specializations.yaml` (the ArchiMate 4
  §14.2.1 informative library, guidance empty); repositories may add their own in
  `.arch-repo/specializations.yaml`. Attribute-profile schema files *attach to* a
  specialization by naming convention; they do not *define* it. Rationale in §4.2.
- **D5 — One profile mechanism.** The dormant `OntologyModule.attribute_profiles` protocol
  surface is verified dead (call-path analysis, not grep alone) and removed; the assurance
  module's hardcoded profiles migrate to the declarative per-repo schemata mechanism via the
  repo-scaffolding defaults (`_repo_default_schemata.py`). No parallel mechanisms.
- **D6 — Specialization is data on the entity, not a new artifact type.** Entities keep
  their concrete `artifact-type`; frontmatter gains `specializations: [slug, …]`
  (list — ArchiMate allows multiple). Verifier enforces catalog membership and parent-type
  match. Never a synthetic `BusinessService`-style metaclass.
- **D7 — Viewpoints and diagram-type constraints share one core admissibility component.**
  A domain `ConceptScope` (allowed entity types, connection types, endpoint rules) is the
  single primitive; diagram-type filters, binding-target admissibility, and viewpoint
  concept-sets are all expressed as / compiled to `ConceptScope`. Existing bespoke filter
  paths are refactored onto it (replacement, not a second mechanism).
- **D8 — Viewpoint application is non-destructive and soft-enforced.** A diagram/matrix
  references `viewpoint:` in frontmatter; violations are verifier *warnings* and GUI
  ghosting/filtering, never deletion or hard blocks. Enforcement mode is configurable
  (`off | warn | ghost`), default `ghost` in GUI, `warn` in verifier.
- **D9 — Multiplicity rename is scoped to ArchiMate relationship ends.** Persisted
  connection fields `src_cardinality`/`tgt_cardinality` → `src_multiplicity`/`tgt_multiplicity`
  with a one-time repo migration; the `include_cardinality` annotation →
  `include_multiplicity`. Diagram-type structural participation config
  (`RequiredConnection.cardinality_min/max`) is internal, non-ArchiMate surface and keeps its
  name (documented decision, out of scope).
- **D10 — Exchange format is a hexagonal adapter family** under
  `src/infrastructure/exchange/`, driven by application use cases
  (`src/application/exchange/`) over the existing read ports and the write layer; XML parsing
  uses `defusedxml` (or hardened stdlib equivalent). CLI-first exposure (`arch-exchange`);
  no new MCP tools in this plan (tool-count discipline).
- **D11 — Self-model follows through MCP tools only** (never manual file edits): composition
  review of the 155 aggregations, a new "Adopt ArchiMate 4" ADR superseding the NEXT-adoption
  ADR (history preserved, not rewritten), and rename of draft-era entity names/slugs via the
  rename machinery.
- **D12 — No changelog bloat**: this document states current intent only.

## 4. Design Evaluations (the non-obvious choices)

### 4.1 Rename tokens (D1)

| Alternative | Assessment |
|---|---|
| Display-only rebrand (labels/docs say "ArchiMate 4", machine tokens stay `archimate-next*`) | Cheapest, zero migration — but permanently misleading identifiers in a self-describing tool, and the token inconsistency defect stays. Rejected. |
| Rename alias only, keep package/module tokens | Splits the vocabulary three ways forever. Rejected. |
| **Full rename of all three tokens (chosen)** | One mechanical, well-scoped change; zero artifact-data migration because entity/connection type names are stable; the only persisted token (`meta_ontology:` alias) has no deployed values. |

Naming: package `archimate_4` (Python-safe), module name `archimate-4-0` (dash-only tokens,
version-carrying like `…-snapshot1`), alias `archimate-4` (version-agnostic, user-facing).

### 4.2 Specialization enumeration: declaration files vs. attribute-profile files (D4)

The question raised in the outline: should specializations be enumerated *only* via their
attribute-profile files, or should configuration enumerate them explicitly?

| Option | Assessment |
|---|---|
| Enumerate via attribute-profile files only (`attributes.{type}.{spec}.schema.json` existing ⇒ specialization exists) | Minimal file count, but conflates two concerns: a specialization is an ontological identity (name, parent type, notation, guidance, optional relationship restrictions); a profile is a data schema. Pure-stereotype specializations (no extra attributes — most of the §14.2.1 library) would need empty schema files as existence markers. Module-shipped predefined specializations would have no natural home (schemata are per-repo). Enumeration/uniqueness validation would be a filesystem-glob side effect. Rejected. |
| Enumerate in the meta-ontology `entities.yaml` under each entity type | Puts per-repo user-defined specializations out of reach (module YAML is shipped code), or forces a merge of two syntaxes inside one file family. Rejected. |
| **Dedicated `specializations.yaml` at both sources, profiles attach by reference (chosen)** | Module-level file ships the informative ArchiMate 4 library (names/notation only, guidance empty — license-clean); repo-level file (`.arch-repo/specializations.yaml`) holds org-specific ones, promotable like other repo config; the aggregate `SpecializationCatalog` gives one enumeration point for validation, GUI pickers, guidance import targeting, and exchange-format mapping. An attribute schema `attributes.{artifact_type}.{specialization-slug}.schema.json` is *optional* and is validated to reference a declared specialization. |

This mirrors ArchiMate 4's own framing: the profile mechanism *implements* specialization,
but the specialization's identity is a definition in its own right.

Specialization declaration shape (both sources):

```yaml
# specializations.yaml — module-shipped or .arch-repo/
specializations:
  service:                       # parent entity type (must exist in the module)
    - slug: business-service
      name: Business Service
      description: ""            # optional
      notation:                  # optional; parent notation + «slug» is the fallback
        icon: ""                 # sprite/glyph key
        color: ""
      restrict_relationships: [] # optional allow-list narrowing (never broadening)
      create_when: ""            # populated only by guidance import, or by repo authors
      never_create_when: ""
```

Inheritance rules per spec: a specialized entity keeps its parent `artifact-type`, hence
parent relationship rules apply automatically; `restrict_relationships` may only narrow
(verifier rejects entries not permitted for the parent).

### 4.3 Guidance externalization architecture (D2/D3)

Constraints: multiple meta-ontologies; specialization-level guidance importable "to the right
place"; in-repo default empty; configurable source; the extracted text must never re-enter
the repo (gitignored landing zone).

Chosen architecture:

- Domain: `src/domain/guidance.py` — `GuidanceKey(module_alias, entity_type, specialization?)`,
  `GuidanceEntry(create_when, never_create_when)`, `GuidanceOverlay(Mapping[GuidanceKey, GuidanceEntry])`,
  pure merge semantics (overlay wins over module-inline text; empty overlay = no-op).
- Loading: module loaders accept an optional overlay parameter
  (`load_archimate_4_module(guidance=…)`); `app_bootstrap` reads
  `<workspace>/ontology-guidance/*.guidance.yaml` (directory configurable via
  `config/settings.yaml: guidance_dir`, gitignored by default) and passes per-module slices.
  `SpecializationCatalog` construction consumes the same overlay for specialization-level
  entries. Bootstrap-time load means the existing `@lru_cache` registry pattern is untouched;
  a guidance import takes effect on backend restart (consistent with the established ops
  model; the CLI prints this).
- Import CLI: `arch-import-guidance --source <url|path> [--module <alias>] [--dry-run]`
  (new `src/infrastructure/cli/arch_import_guidance.py`, argparse-subcommand style, urllib
  idiom from `get_plantuml.py`). Validates schema + guidance keys against the registry
  (unknown module/type/specialization ⇒ listed, non-matching entries skipped or `--strict`
  fails), writes `<guidance_dir>/<alias>.guidance.yaml`, prints an import summary
  (matched/unmatched counts).
- Extraction (one-time, done first): `tools/extract_guidance.py` reads the *current*
  `entities.yaml` texts and emits the publishable guidance file to an **out-of-repo** path;
  the same commit strips the YAML values to `""`. The published file's hosting location is
  the owner's choice (open question Q2); `config/settings.yaml` gains
  `guidance_default_source: ""` so a hosted URL can be preconfigured.

Guidance file schema (v1):

```yaml
guidance_format: 1
meta_ontologies:
  archimate-4:
    entity_types:
      stakeholder:
        create_when: "…"
        never_create_when: "…"
        specializations:            # optional
          business-service:
            create_when: "…"
            never_create_when: "…"
    connection_types: {}            # reserved (no connection guidance today)
```

Scope note: only the ArchiMate module's guidance is license-encumbered and extracted. The
mechanism is generic (keyed by alias) so other modules *may* adopt it, but `sysml_v2_min`,
`assurance`, and diagram-type `own_entity_types` guidance stays inline (not spec-derived
text). A one-off review confirms no ArchiMate spec prose hides in docs or diagram-type YAML.

### 4.4 Viewpoints: unification with diagram-type constraints (D7/D8)

The project already has "viewpoint-shaped" machinery: per-diagram-type concept filters,
binding-target admissibility, and the derivation engine (query-backed view generation).
Following the user's direction, the design introduces **one core component** and re-bases the
existing mechanisms on it rather than adding a parallel one:

- **Domain, new**: `src/domain/concept_scope.py` — `ConceptScope` (frozen): allowed entity
  types (explicit set and/or class/hierarchy predicates, mirroring today's
  `filter.hierarchy_level` semantics), allowed connection types, optional endpoint rules
  (source/target constraints), with `admits_entity_type`, `admits_connection_type`,
  `admits_connection(source_type, target_type, conn_type)`, and intersection composition
  (`scope_a & scope_b`).
- **Domain, new**: `src/domain/viewpoints.py` — `ViewpointDefinition`: `slug`, `name`,
  `description/rationale`, `purpose ∈ {designing, deciding, informing}`,
  `content ∈ {details, coherence, overview}` (the two mandatory Chapter-13 dimensions),
  `stakeholders: [str]`, `concerns: [str]`, `scope: ConceptScope`,
  `representation_types: [diagram-type slug | "matrix"]`, optional
  `derivation_defaults` (strategy id + params for generated views via the existing
  `src/application/derivation/` engine).
- **Re-basing existing mechanisms** (the replacement work):
  - `_config_type.py::_build_entity_filter` and `DiagramTypeModule.accepts_entity_type` /
    `accepts_connection_type` are reimplemented over a `ConceptScope` the module *derives
    from its existing config* (behavior-preserving; existing tests must stay green).
  - Binding-target admissibility (`permitted_mappings` source lists) evaluates through the
    same scope primitives; `AllowedBindingsSpec` keeps its correspondence semantics (what a
    binding *means*) but its "which model types are eligible" facet becomes a `ConceptScope`.
  - Effective authoring scope for a diagram = `diagram_type.scope & viewpoint.scope`
    (viewpoint absent ⇒ diagram-type scope alone — Archi's "None" default).
- **Persistence**: built-in viewpoint definitions may ship with modules
  (`viewpoints.yaml`, optional library — Appendix C is non-mandatory); user-defined ones live
  in `.arch-repo/viewpoints.yaml`. A diagram/matrix stores `viewpoint: <slug>` in
  frontmatter.
- **Surfaces**: verifier contribution (viewpoint-violation *warnings*, distinct from
  metamodel violations); GUI — viewpoint selector on diagram create/edit, palette + entity
  picker filtering through the narrowed scope from the existing
  `ui-config`/`/api/ontology` endpoints (extended with an optional `viewpoint` parameter),
  ghosting for out-of-scope existing content; a viewpoints management view (list/create/edit
  per-repo definitions); MCP — viewpoint fields included in `artifact_authoring_guidance`
  output and accepted by `artifact_create_diagram`/`artifact_edit_diagram` frontmatter (no
  new tools; guidance-first for agents).
- **Deferred (explicitly out of scope here, candidate follow-up plan)**: Bizzdesign-style
  presentation/analysis rules (color/label/tooltip/chart rules), viewpoint
  publishing/pinning, parameterized viewpoints, catalog/report view artifact kinds. The
  `ViewpointDefinition` shape reserves nothing for them beyond `derivation_defaults`; they
  compose later without rework because scope/selection (this plan) is already separated from
  presentation (follow-up).

Spec fidelity notes: purpose/content classification is mandatory-shaped and included from the
start; "view ≠ diagram" is honoured minimally by making matrices viewpoint-governable and by
`derivation_defaults` for generated views; the conformance docs (§5.7) document the
implementation-defined manner, as the standard requires.

### 4.5 Exchange format (D10)

- **Placement**: use cases `src/application/exchange/{import_model.py, export_model.py}`
  orchestrate via existing ports (`ArtifactLookup`, `RelationshipGraph`,
  `RepositoryScopeResolver`) plus a narrow new port pair for the format codec
  (`ExchangeDocumentReader/Writer` protocols, application-defined, implemented in
  `src/infrastructure/exchange/archimate_model_exchange/`). Writes go through the existing
  `artifact_write` layer (same validation as GUI/MCP), never raw file emission.
- **Mapping**: the exchange format (C19C v3.1) enumerates ArchiMate **3.x** concrete types;
  ArchiMate 4 generalizes several into Common Domain elements. Therefore:
  - **Import** applies the Appendix E.4 migration table: layer-specific 3.x types map to the
    ArchiMate 4 type **plus** the corresponding predefined specialization (e.g.
    `BusinessService` → `service` + `business-service`); `Contract` → `business-object` +
    `contract`; invalid relationships → `archimate-association` (reported); composition is
    **preserved as composition** (never downgraded).
  - **Export** inverts it: an entity carrying a layer specialization exports as the 3.x
    concrete type; otherwise the domain (`hierarchy[0]`) selects the default layer variant; a
    documented fallback covers unmappable cases. Multiplicity exports to the format's
    relationship-end fields where representable; profiles/attribute values export as exchange
    `properties` with `propertyDefinitions`.
  - A single declarative mapping table (`exchange_mapping.yaml` inside the adapter package)
    drives both directions; round-trip tests assert import∘export stability on a fixture
    model.
- **Identity**: exchange `identifier` ↔ artifact ID mapping is stored on import (frontmatter
  `exchange_id:` extra or a sidecar map — decided in implementation WU) so re-import updates
  instead of duplicating; export emits stable identifiers derived from artifact IDs.
- **Security**: XML parsing via `defusedxml` (XXE/entity-expansion hardening); imports are
  size-capped; schema-validated against the C19C XSD before any write; import is a normal
  write-path operation (dry-run supported, verifier runs, nothing bypasses validation).

### 4.6 Dormant profile surface (D5)

Evaluation obligation (per the verify-architecture-claims discipline): confirm by call-path
analysis — registry construction, GUI routers, MCP tool payloads, verifier rules, tests —
that `OntologyModule.attribute_profiles` has no live consumer. Survey indicates: protocol
declaration + three module class attributes + existence-assertion tests only; no registry
aggregation, no serialization into `get_type_guidance`, no endpoint. If confirmed:

- Remove the protocol field and the three class attributes; delete the assertion-only tests.
- Migrate the assurance profiles' *content* (they define real, useful schemas: `hazard`,
  `risk`, `unsafe-control-action`, `assurance-constraint`, `control-structure-node`) into
  `_repo_default_schemata.py` as scaffolded per-repo `attributes.*.schema.json` defaults, so
  new repos still get them — through the one declarative mechanism.
- If a live consumer *is* found, stop and record it in the TASKS ledger before proceeding
  (decision escalates back to review).

## 5. Proposed Solution — Workstream Summary

Ordered for dependency and risk; details above.

- **WS-A Rename** (D1): package, module name, alias, c4/_projection tuple, all
  `ontology.yaml`/`config.yaml` tokens (fixing the package-vs-module inconsistency),
  frontend `domains.ts`, tests, docs, skills, README badge; regenerate
  `types.generated.ts`; startup check for unresolvable `permitted_mappings` ontology tokens.
- **WS-B License compliance** (D2/D3): extraction script + publishable YAML (out-of-repo),
  strip `entities.yaml` guidance to empty, `GuidanceOverlay` domain type + loader threading,
  gitignored `ontology-guidance/` dir + `guidance_dir`/`guidance_default_source` settings,
  `arch-import-guidance` CLI, prose sweep of docs for residual spec text.
- **WS-C Core semantics**: composition semantics verification against final §5.1.2/Appendix B
  (permitted wherever aggregation is; derivation-strength ordering
  realization < assignment < aggregation < composition wherever `hierarchy_priority` or
  relationship classification is consumed); full `permitted_relationships` matrix recheck
  against final Appendix B; multiplicity rename (D9) with one-time repo migration
  (`arch-repair`-style) + junction rule (warn when multiplicity is set on a
  junction-attached end).
- **WS-D Specializations** (D4/D5/D6): `SpecializationCatalog` (domain), module + per-repo
  `specializations.yaml` loading, ArchiMate 4 §14.2.1 informative library shipped
  (guidance-empty), frontmatter `specializations:` + verifier rules (existence, parent match,
  restriction narrowing), attribute-schema attachment by naming convention, guillemet
  stereotype + notation rendering (icon/color with parent-notation fallback), GUI picker +
  display, `artifact_authoring_guidance` + `types.generated.ts` exposure, dormant-surface
  removal + assurance profile migration.
- **WS-E Viewpoints** (D7/D8): `ConceptScope` + `ViewpointDefinition` (domain), re-basing of
  diagram-type filters and binding admissibility onto `ConceptScope`
  (behavior-preserving), per-repo + module viewpoint definitions, frontmatter `viewpoint:`,
  verifier warnings, GUI selector/palette-filtering/ghosting + management view, guidance/MCP
  exposure, built-in starter library (small, e.g. layered/application/motivation — Appendix C
  is optional).
- **WS-F Exchange** (D10): mapping table, codec adapter (defusedxml, XSD validation),
  import/export use cases with dry-run, identity mapping, `arch-exchange` CLI, round-trip +
  migration-table tests.
- **WS-G Self-model & docs** (D11): composition review of the 155 aggregations (assess via
  MCP queries, convert existence-dependent ones), "Adopt ArchiMate 4" ADR superseding the
  NEXT ADR, rename of draft-era self-model entity names/slugs, conformance documentation page
  (documents every "implementation-defined manner": viewpoints, customization, guidance
  import), README/badges/status update, docs sweep.

## 6. Security & Auth Considerations

- **Guidance import (new input path)**: fetches YAML from a user-configured URL/path.
  Mitigations: HTTPS-only by default for URLs (plain HTTP requires an explicit flag),
  `yaml.safe_load`, response size cap, schema validation before write, content is inert prose
  (rendered as text in GUI/MCP — no HTML injection into the Vue frontend, which renders text
  nodes; verify no `v-html` sink on guidance fields), no code paths execute imported content.
- **Exchange import (new input path)**: XML with attacker-controllable structure if a user
  imports an untrusted file. Mitigations: `defusedxml`, XSD validation, size caps, dry-run
  default in CLI (explicit `--commit`), all writes through the validated write layer.
- **No new network listeners, endpoints requiring auth changes, or trust-boundary moves**:
  new REST surface (viewpoints CRUD, guidance status) sits behind the existing local backend
  with the same access model as current routers. MCP surface unchanged in tool count.
- Existing threat posture (local single-user backend) is unchanged; the assurance
  confidential store is untouched.

## 7. Data & Consistency Considerations, Migrations

- **No model-artifact migration for the rename** (type names stable; no deployed
  `meta_ontology:` values). The alias validator's accepted set changes — any external repo
  that *did* set `meta_ontology: archimate-next` would fail validation loudly at startup;
  release notes state the manual one-line fix.
- **Multiplicity field rename**: one-time migration command rewrites
  `src_cardinality`/`tgt_cardinality` keys in `.outgoing.md` frontmatter and
  `include_cardinality` annotations across engagement + enterprise repos; parser accepts the
  legacy keys only during the migration window (removed in the same plan; verifier flags
  legacy keys after). Migration is idempotent, reports counts, and runs under the standard
  write/index reconcile machinery.
- **Self-model composition conversions** are ordinary model edits through MCP (aggregation →
  composition where existence-dependency holds), reviewed in batches; no schema change.
- **Frontmatter additions** (`specializations:`, `viewpoint:`, optional `exchange_id:`) are
  optional keys — absent means today's behavior; frontmatter schemata
  (`frontmatter.entity/diagram.schema.json`) gain the optional properties in scaffolding
  defaults.
- **Atomicity**: all writes ride the existing single-write-queue/index machinery; the
  migration and exchange import use the same path (no bypass).
- **No aggregate-event machinery exists in this codebase**; mutation observation flows
  through `ArtifactMutationObserver` as today — no new event obligations introduced.

## 8. Observability

- Guidance import: structured summary (source, matched/unmatched keys, bytes) to stdout +
  log; `GET /api/authoring-guidance` exposes whether guidance is loaded vs. empty (so the GUI
  wizard can hint "guidance not imported").
- Exchange import/export: per-run report (created/updated/skipped/unmappable, with reasons);
  dry-run produces the same report without writes.
- Verifier: new warning categories get distinct codes (viewpoint-violation,
  multiplicity-on-junction, legacy-cardinality-key, specialization-unknown) so reports are
  filterable.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Appendix B recheck reveals rule deltas beyond composition (matrix drift from snapshot) | WS-C treats the matrix recheck as its own WU with a diff report before any rule edit; self-model verify run after. |
| Exchange-format 3.x↔4 mapping has genuinely lossy cases | Declarative mapping table + explicit documented fallbacks + round-trip tests; lossy cases reported, never silent. |
| The spec documents (ArchiMate 4, C19C 3.1, XSDs) can't be committed (no-PDF policy, licensing) | Verification WUs cite section numbers and record conclusions in the ledger; XSDs fetched at dev time (gitignored) with a pinned checksum; open question Q3 covers XSD redistribution. |
| `ConceptScope` re-basing regresses existing diagram-type filtering | Behavior-preserving refactor gated by the existing diagram-type test suites + a characterization test snapshotting `effective_entity_types` per module before/after. |
| Guidance stripping degrades agent authoring quality until import is configured | `artifact_authoring_guidance` states explicitly when guidance is empty + how to import; default source URL preconfigured once hosted (Q2). |
| Dormant profile surface has a hidden consumer | D5 verification step with an explicit stop-and-record escalation. |

## 10. Open Questions

- [ ] **Q1 — Module naming**: confirm `archimate_4` / `archimate-4-0` / `archimate-4`
  (§4.1). — Owner: review
- [ ] **Q2 — Guidance hosting**: where will the extracted guidance YAML live (public repo,
  gist, site)? Determines `guidance_default_source`. — Owner: Michael
- [ ] **Q3 — C19C XSD acquisition/licensing**: confirm the exchange-format XSDs may be
  fetched at dev/test time and whether they may ship in the repo (default assumption: fetch,
  don't commit). — Owner: Michael
- [ ] **Q4 — Conformance wording**: "implements/aligned with ArchiMate 4" vs. a conformance
  claim (certification/trademark implications) in README/docs. — Owner: Michael
- [ ] **Q5 — Multiple specializations per entity**: plan supports a list per spec; confirm
  the GUI/UX should too, or restrict to one initially. — Owner: review
- [ ] **Q6 — Deferred viewpoint scope**: agree that presentation/analysis rules
  (color/label/chart), publishing, and parameterized viewpoints go to a follow-up plan.
  — Owner: review

## 11. Acceptance Criteria (plan-level)

- [ ] No string `archimate_next` / `archimate-next` / "ArchiMate NEXT" remains in active
  code, config, tests, docs, skills, or generated types (historical PLAN/TASKS ledgers
  excepted, per convention); startup check rejects unresolvable `permitted_mappings` tokens.
- [ ] `src/ontologies/archimate_4/entities.yaml` contains zero ArchiMate-derived guidance
  prose; `artifact_authoring_guidance` returns imported guidance after
  `arch-import-guidance` + restart, and a clear empty-state before.
- [ ] The extracted guidance YAML exists outside the repo, validates against the v1 schema,
  and round-trips through the import CLI (including at least one specialization entry).
- [ ] Composition passes the Appendix-B-derived rule tests; derivation ordering includes it
  as strongest; the self-model contains deliberate composition connections after review.
- [ ] Multiplicity terminology is consistent in code/UI/docs; migration leaves zero legacy
  keys in both repos; junction rule fires in tests.
- [ ] Specializations: informative library loaded, per-repo declarations validated, entity
  frontmatter round-trips, stereotype + notation render, GUI picker works, dormant profile
  surface removed with assurance schemas migrated.
- [ ] Viewpoints: `ConceptScope` is the single admissibility path (old filter code deleted),
  viewpoint selection filters palette/pickers non-destructively, verifier warns on
  violations, definitions ship + per-repo CRUD works.
- [ ] Exchange: fixture model round-trips (export→import) losslessly for mapped concepts;
  Appendix E.4 migration cases covered by tests; composition never downgraded on either path.
- [ ] Conformance documentation page describes every implementation-defined mechanism.
- [ ] Quality gates green throughout: `pytest` 0 failures, `ruff` 0 errors, `zuban check`
  pass, frontend `lint`/`typecheck`, `types.generated.ts` regenerated where required.

## 12. Implementation Checklist

Maintained as checkbox work-units with anchors, acceptance criteria, dependencies, and a
resume protocol in **`TASKS-archimate-4-compliance.md`**.
