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
- **The `.outgoing.md` connection-section grammar is implemented independently at least
  three times**: the index/read parser (`src/application/artifact_parsing.py:238-295`), the
  write round-trip parser (`src/infrastructure/write/artifact_write/parse_existing.py:248-295`,
  which folds the section body minus assoc markers into `description`), and the formatter
  (`src/application/modeling/artifact_write_formatting.py`), each with its own header
  regex/assoc handling — a drift-prone duplication this plan must touch twice (multiplicity
  rename, per-connection metadata block).
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
- **D2 — Guidance becomes an overlay, empty by default; imported per repo, never a
  customization authority.** `EntityTypeInfo.create_when` / `never_create_when` remain, but
  ship as `""` for the ArchiMate module. A domain `GuidanceOverlay` is loaded at bootstrap
  from **repo-local, gitignored guidance caches** (`<repo>/.arch-repo/guidance-cache/*.guidance.yaml`)
  and merged at load time. Precedence (lowest → highest): module declarations (empty for
  ArchiMate) < enterprise repo cache < engagement repo cache. Non-encumbered, repo-authored
  guidance lives directly in committed declarations (`.arch-repo/specializations.yaml`),
  which the overlay never overrides. Imported guidance is authoring help for the active
  repositories — it is **not** a third governance tier beside enterprise/engagement and
  plays no role in promotion semantics beyond unknown-key rejection. Import happens via a
  new CLI command from a configurable URL/path with recorded provenance (D3a). The extracted
  guidance file is **never committed** to this repository.
- **D3 — Guidance file schema is module-scoped, concept-level, and specialization-aware**
  (see §4.3): keyed by meta-ontology alias → entity type or connection type → optional
  specializations. Connection-type base guidance keys are reserved (not populated now);
  connection-*specialization* guidance is supported from the start (D4).
- **D3a — Imports are auditable.** Every import writes a provenance sidecar next to the
  cache file: source URL/path, SHA-256 of the fetched content, guidance format version,
  timestamp, matched/unmatched key counts. Docs record where the published guidance file is
  hosted, under what terms, and its expected hash/version.
- **D4 — Specializations are concept-level (entity AND connection) and enumerated in
  dedicated declaration files, not implicitly by attribute-profile files.** One unified
  `SpecializationCatalog` with `concept_kind: entity | connection`. Ontology modules ship a
  `specializations.yaml` (the ArchiMate 4 §14.2.1 informative library — which includes
  relationship specializations such as `money-flow` and the assignment variants — guidance
  empty); repositories add their own in `.arch-repo/specializations.yaml` at **both tiers**:
  the enterprise repo defines the baseline vocabulary, an engagement repo may extend it
  (superset), and promotion enforces the same superset rule already used for attribute
  profiles (D14). Attribute-profile schema files *attach to* a specialization by reference;
  they do not *define* it. Rationale in §4.2.
- **D5 — One profile mechanism.** The dormant `OntologyModule.attribute_profiles` protocol
  surface is verified dead (call-path analysis, not grep alone) and removed; the assurance
  module's hardcoded profiles migrate to the declarative per-repo schemata mechanism via the
  repo-scaffolding defaults (`_repo_default_schemata.py`). No parallel mechanisms.
- **D6 — Specialization is data on the concept, not a new type.** Entities keep their
  concrete `artifact-type` and gain frontmatter `specializations: [slug, …]` (list —
  ArchiMate allows multiple). Connections gain the equivalent via a **per-connection
  metadata block** directly under each `###` connection heading in `.outgoing.md` — NOT
  via the file-level frontmatter (which is shared by all connections in the file) and NOT
  by further overloading the heading grammar (which already carries multiplicity). The
  block is a small fenced YAML section parsed/written per connection; it becomes the
  general home for future per-connection metadata, validated by the existing
  `connection-metadata.{connection-type}.schema.json` convention (extended with the
  optional `specializations` property), not by `frontmatter.outgoing.schema.json`.
  Verifier enforces catalog membership, `concept_kind`, and parent-type match for both
  kinds. Stereotypes render on both boxes and relationships. Never a synthetic
  `BusinessService`-style metaclass or connection-type clone.
- **D7 — Viewpoints and diagram-type constraints share one core admissibility component.**
  A domain `ConceptScope` (allowed entity types, connection types, endpoint rules) is the
  single primitive; diagram-type filters, binding-target admissibility, and viewpoint
  concept-sets are all expressed as / compiled to `ConceptScope`. Existing bespoke filter
  paths are refactored onto it (replacement, not a second mechanism).
- **D8 — Viewpoints are applied through a `ViewpointApplication`, non-destructively and
  soft-enforced.** A small domain concept — target kind, target id, viewpoint slug, pinned
  definition version, optional enforcement override and derivation parameters — persisted in
  the target's frontmatter. Diagrams and matrices are the first target kinds; catalogs/
  reports can consume applications later without rework. Definitions carry a `version`; an
  application whose pinned version lags the definition gets a distinct *stale-application*
  warning — a changed viewpoint never silently reinterprets old views. Violations are
  verifier *warnings* and GUI ghosting/filtering, never deletion or hard blocks. Enforcement
  mode is configurable (`off | warn | ghost`), default `ghost` in GUI, `warn` in verifier.
- **D9 — Multiplicity rename is scoped to ArchiMate relationship ends, executed as a real
  repository migration.** Persisted connection fields `src_cardinality`/`tgt_cardinality` →
  `src_multiplicity`/`tgt_multiplicity`; the `include_cardinality` annotation →
  `include_multiplicity`. The migration command is dry-run by default, recommends a
  backup/branch, is idempotent with a count report, and runs through the standard
  write/index machinery (index rebuild included). Legacy keys remain readable for **exactly
  one release** (documented deprecation, distinct verifier code) — external user
  repositories migrate on their own schedule within that window; REST/MCP payloads and
  generated types switch with the release notes. Diagram-type structural participation
  config (`RequiredConnection.cardinality_min/max`) is internal, non-ArchiMate surface and
  keeps its name (documented decision, out of scope).
- **D10 — Exchange is split into readiness (this plan's critical path) and implementation
  (gated milestone).** Readiness = the declarative mapping table, XSD acquisition/licensing
  resolution, and lossy-case policy — reviewed and signed off before any codec code.
  Implementation = a hexagonal adapter family under `src/infrastructure/exchange/`, driven
  by application use cases (`src/application/exchange/`) over the existing read ports and
  the write layer; XML parsing uses `defusedxml` (or hardened stdlib equivalent). CLI-first
  exposure (`arch-exchange`); no new MCP tools in this plan (tool-count discipline). Core
  compliance work (WS-A–E, G) does not wait on exchange.
- **D11 — Self-model follows through MCP tools only** (never manual file edits): composition
  review of the 155 aggregations, a new "Adopt ArchiMate 4" ADR superseding the NEXT-adoption
  ADR (history preserved, not rewritten), and rename of draft-era entity names/slugs via the
  rename machinery.
- **D12 — No changelog bloat**: this document states current intent only.
- **D13 — Profiles get a minimal first-class `ProfileDefinition`, with persistence decided
  now.** A domain concept (slug, name, applicable concept types, typed attributes with
  optional defaults), rendered/validated through JSON Schema. Persistence: named reusable
  profiles live in **`.arch-repo/profiles.yaml`** (per repo, two-tier like
  specializations); the existing `attributes.{artifact_type}.schema.json` files *are* the
  base-type profiles under this model (unchanged on disk); a specialization's inline
  `attributes:` compile to an anonymous profile. Attribute obligation levels are
  `required | recommended | optional` in the YAML; compilation emits JSON Schema `required`
  plus the extension keyword **`x-recommended: [names]`** (JSON Schema has no native
  "recommended"), which the verifier consumes for warnings. Merge semantics are
  deterministic: base-type profile first, then each carried specialization's profile in
  declared frontmatter order; a conflicting property definition (same name, incompatible
  schema) is a load/verify **error**, defaults resolve last-writer-wins along the same
  order, and validation severity is: schema violation on values = error, missing
  recommended attribute = warning. This keeps multiple specializations per concept
  unambiguous.
- **D14 — Promotion governance extends the existing superset rule.** Enterprise
  `.arch-repo/` declarations are the baseline; engagement declarations must be a superset
  for promoted content: promotion fails when a promoted artifact depends on an
  engagement-only specialization, profile, specialization-attached schema, **or viewpoint
  definition** unless that definition is promoted alongside or already exists in the
  enterprise repo (same governance model as today's attribute-profile superset check). For
  viewpoints this covers promoted diagrams/matrices whose `ViewpointApplication` references
  an engagement-only definition or a version the enterprise repo does not have; the match
  is **exact-version** — a newer enterprise version does not satisfy promotion by itself
  (that would silently weaken the D8 pin), unless the promoted artifact is explicitly
  re-pinned to the enterprise version as a reviewed promotion step. Promoted viewpoint
  definitions must themselves validate transitively (referenced specializations, profiles,
  query schema version, derivation strategies incl. pinned versions, presentation
  capabilities).
- **D15 — Viewpoints are also executable on demand (Bizzdesign-Horizzon-style), with a
  versioned query schema, a first-class result contract, and capability-checked
  presentation.**
  - *Query* (`ExecutableViewpointQueryV1`, explicit `query_schema: 1`): a declarative
    selection with **flat conjunctive (`all_of`) semantics** — separate `entity_filters`
    (group/project, entity type, specialization membership, domain, status, **profile
    attributes**) and `connection_filters` (connection type, specialization, **profile
    attributes**), an explicit `include_connections` policy
    (`between-selected | incident | none`), and explicit `repo_scope`. Attribute
    predicates are typed against the D13 merged effective schemas (base-type profile ⊕
    specialization profiles) with a small v1 operator set — `eq | neq | in | exists |
    absent` plus `lt | lte | gt | gte` for numeric/date attributes; a concept lacking the
    attribute matches only `absent`. Optional *expansion rules*:
    `{strategy, roots: selected_entities | execution_anchor, parameters, merge: union}` —
    reusing the derivation strategies; `execution_anchor` is a **built-in execution-time
    input** (e.g. "the entity I'm looking at" on the exploration page), which is not the
    deferred user-defined-parameter mechanism (Q6). Expansion rules carry an optional
    `strategy_version`, resolved to the current registered version at definition save and
    stored explicitly — consistent with the existing strategy machinery
    (`StrategySpec.version`, `ViewDerivation.strategy_version`, catalog keyed by
    `(name, version)`); execution validates the pinned pair against the catalog and fails
    loudly when it is unknown (never silently substitutes another version). No nested
    boolean DSL in v1.
  - *Result* (`ViewpointExecutionResult`, application DTO — ephemeral, never persisted):
    viewpoint slug + definition version + query schema version, executed_at, repo_scope,
    model/index revision where available, application/strategy-catalog version info (for
    later drift diagnosis), **sorted** entity/connection IDs, counts, warnings (incl.
    unsupported display options), `truncated` + applied limits, duration. Execution
    enforces max result size, max expansion hops, and a timeout with clean cancellation —
    trustworthy results without creating artifacts.
  - *Presentation* (`PresentationSpec`, representation-aware): the executed representation
    (`exploration` cluster view | `table` catalog | `matrix`) with per-representation
    display options, including an optional `group_by` (entity type, specialization, group,
    or a **discrete profile attribute**). Styling rules resolve to **abstract style
    tokens/roles** in the core — keyed by entity type, specialization, group, or
    **discrete profile-attribute values** (e.g. color by `lifecycle_status`); continuous
    value→color heat-map scales stay deferred (Q6). Renderer-specific vocabulary stays
    in the surface adapters, consistent with the existing `view_projection.py` opacity
    contract. Each surface declares its supported display capabilities (exploration:
    node shape/icon/color, cluster grouping; table: columns/badges/sort, row grouping;
    matrix: row/column grouping, cell
    emphasis); unsupported options are never silently ignored, with a precise drift rule:
    **save/edit rejects** options unsupported by the *current* capability registry
    (validation error), while **runtime warns** in the cases save-time checking cannot
    cover — legacy definitions saved under an older registry, capability drift across
    app upgrade/downgrade, or executing a definition on a different surface than its
    declared representation.
  - Executions are read-only and repeatable against current model state; no model artifact
    and no diagram is created. Generating *persistent* diagrams from executions,
    label/tooltip/chart rules and continuous heat-map scales (discrete attribute-keyed
    styling/grouping IS in scope), saving executions as artifacts, publishing, and
    user-defined parameterized viewpoints stay deferred (Q6).
- **D16 — One connection-declaration grammar component.** How a single connection is
  declared in `.outgoing.md` (heading incl. multiplicity, per-connection metadata block,
  `§assoc` markers, description) gets a single owner:
  `src/domain/connection_declaration.py` — a pure text↔structure module
  (`ConnectionDeclaration` value object + `parse_connection_declarations` /
  `format_connection_declaration`, no I/O), following the
  `src/domain/bindings.py::parse_bindings` precedent of naming the concept, not the
  textual layout. The index/read parser (`artifact_parsing.py`), the write round-trip
  parser (`parse_existing.py`), and the formatter (`artifact_write_formatting.py`) are
  re-based onto it as thin mappers to their consumer shapes; their private header/assoc
  regexes are deleted. This lands **before** the two grammar changes in this plan
  (multiplicity rename, metadata block) so each change is made exactly once. File I/O and
  frontmatter handling stay where they are.
- **D17 — `arch-repair` grows an `upgrade` command owning all persisted-format
  migrations.** It checks a repository against the *current* software's format
  expectations — profiles, customizations (specializations, viewpoints, attribute
  schemata, guidance caches), entity frontmatter, connection declarations, diagram
  frontmatter — and reports, per finding: what has to change, whether it can be migrated
  automatically, and the planned rewrite or manual instructions. Specifics:
  - *Steps*: migrations are **registered, self-detecting, idempotent upgrade steps** (the
    D9 multiplicity rename is the first; future format changes plug in). **Coverage
    invariant**: every persisted-format change this plan introduces registers either an
    auto-migration step or a read-only detector — enforced by a closing work unit, so
    "finding without a registered step" is a real category, not a dead branch. Findings no
    step can fix are listed as **manual-adaptation instructions** — never silently
    skipped.
  - *Compatibility identity*: the primary key is a **`format_contract_version`** plus the
    list of applied step ids recorded in `.arch-repo/config.yaml` — not the app version
    (semver/dev builds don't identify repo formats). The software version is stamped as
    metadata only; detection stays probe-based per step, so the command is safe to re-run
    anytime.
  - *Hexagonal shape*: application use cases `EvaluateRepositoryUpgrade` /
    `ApplyRepositoryUpgrade` over ports; step `detect` is pure where possible, `apply`
    goes through the write/index ports; CLI, backend probing, filesystem adapters, and
    index rebuild live in infrastructure.
  - *Safety*: dry-run/report is the default and always allowed. `--commit` (a) refuses a
    **dirty git worktree** by default, printing the files it would touch
    (`--allow-dirty` exists but the report/rollback story is then the user's); (b)
    refuses while a backend **serves the target repo**. The current REST surface cannot
    answer that (`/api/stats` returns index stats without repo roots), so D17 **adds a
    backend-identity endpoint** (e.g. `GET /api/backend-identity`: canonical
    realpath-normalized served repo roots — engagement + enterprise — plus software
    version); the guard probes it and fails **closed** with an actionable message when a
    backend responds but its served roots cannot be confirmed (including pre-D17 backends
    without the endpoint), and does not block on backends serving unrelated repos; (c)
    recommends a backup/branch.
  - *Repo scope*: the unit of upgrade is **one repository root** (each repo's
    `.arch-repo/config.yaml` carries its own format identity). The CLI accepts
    `--repo-root <path>` (repeatable) and `--workspace <path>` (resolves the workspace's
    engagement + enterprise roots); multi-repo runs report **per repo root** with one
    aggregate summary.
  - *CLI shape*: `arch-repair` gains subcommands — `upgrade` (new) and `git-repair` (the
    current guarded git flow); the existing no-subcommand invocation stays as a
    deprecated alias for `git-repair` for one release.
  - *Reports*: human-readable output plus `--json` with a stable contract — per repo
    root: software version, format contract version, **step registry identity**
    (available step ids/versions), **applied_steps_before / applied_steps_after**,
    unapplied required steps, and per finding: step id, finding id, location, severity,
    auto_migratable, planned rewrite summary or manual instruction, outcome
    applied/skipped/error.

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
| Enumerate via attribute-profile files only (`attributes.{type}.{spec}.schema.json` existing ⇒ specialization exists) | Minimal file count, but conflates two concerns: a specialization is an ontological identity (name, parent type, notation, guidance, optional relationship restrictions); a profile is a data schema. Pure-stereotype specializations (no extra attributes — most of the §14.2.1 library) would need empty schema files as existence markers. Module-shipped predefined specializations would have no natural home (schemata are per-repo). Enumeration/uniqueness validation would be a filesystem-glob side effect. Connection specializations would have no home at all (there is no per-specialization connection-schema convention). Rejected. |
| Enumerate in the meta-ontology `entities.yaml` under each entity type | Puts per-repo user-defined specializations out of reach (module YAML is shipped code), or forces a merge of two syntaxes inside one file family. Also entity-only by construction. Rejected. |
| Entity-only specialization catalog | Simpler, but inconsistent with the informative library itself (`money-flow` specializes Flow, `responsibility-assignment`/`behavior-assignment` specialize Assignment) and weaker than ArchiMate 4 customization, which applies to *concepts* — elements and relationships alike. Exchange mapping for the relationship rows of Appendix E.4 would have no target. Rejected. |
| **Unified concept-level `specializations.yaml` at both sources, profiles attach by reference (chosen)** | One `SpecializationCatalog` with `concept_kind: entity \| connection`. Module-level file ships the informative ArchiMate 4 library (names/notation only, guidance empty — license-clean); repo-level files (`.arch-repo/specializations.yaml` in **enterprise and engagement** repos, enterprise = baseline, engagement = superset per the promotion governance model, D14) hold org-specific ones; the aggregate catalog gives one enumeration point for validation, GUI pickers, guidance import targeting, and exchange-format mapping. An attribute schema `attributes.{artifact_type}.{specialization-slug}.schema.json` is *optional* and is validated to reference a declared entity specialization. |

This mirrors ArchiMate 4's own framing: the profile mechanism *implements* specialization,
but the specialization's identity is a definition in its own right.

Specialization declaration shape (both sources):

```yaml
# specializations.yaml — module-shipped or .arch-repo/ (enterprise/engagement)
specializations:
  entity:
    service:                       # parent entity type (must exist in the module)
      - slug: business-service
        name: Business Service
        description: ""            # optional
        notation:                  # optional; parent notation + «slug» is the fallback
          icon: ""                 # sprite/glyph key
          color: ""
        restrict_relationships: [] # optional allow-list narrowing (never broadening)
        profile: ""                # optional ProfileDefinition slug (D13), or:
        attributes: {}             # optional inline profile attributes
        create_when: ""            # populated by guidance import, or by repo authors
        never_create_when: ""
  connection:
    archimate-flow:                # parent connection type
      - slug: money-flow
        name: Money Flow
        notation: {}               # e.g. line style/label marker; «slug» fallback
        restrict_endpoints: []     # optional source/target narrowing (never broadening)
        create_when: ""
        never_create_when: ""
```

Inheritance rules per spec: a specialized concept keeps its parent type, hence parent
relationship/endpoint rules apply automatically; `restrict_relationships` /
`restrict_endpoints` may only narrow (verifier rejects entries not permitted for the
parent).

Profile semantics (D13): a `ProfileDefinition` is a named, typed attribute set persisted per
repo; the existing `attributes.{artifact_type}.schema.json` files are the base-type
profiles. An entity's effective attribute schema = base-type profile ⊕ each carried
specialization's profile (referenced or inline) in declared frontmatter order; incompatible
redefinitions of the same property are a load/verify error; defaults resolve
last-writer-wins along that order. This keeps «spec-a, spec-b» combinations deterministic.

### 4.3 Guidance externalization architecture (D2/D3)

Constraints: multiple meta-ontologies; specialization-level guidance (for both concept
kinds) importable "to the right place"; in-repo default empty; configurable source; the
extracted text must never re-enter the repo (gitignored landing zone); **no new governance
tier** — customization authority remains enterprise + engagement repositories only, and
imported guidance is authoring help, not configuration.

Chosen architecture:

- Domain: `src/domain/guidance.py` — `GuidanceKey(module_alias, concept_kind, type_name, specialization?)`,
  `GuidanceEntry(create_when, never_create_when)`, `GuidanceOverlay(Mapping[GuidanceKey, GuidanceEntry])`,
  pure merge semantics: module-inline text < enterprise-repo cache < engagement-repo cache;
  committed repo declarations (e.g. guidance authored in `.arch-repo/specializations.yaml`)
  are never overridden by an imported cache; empty overlay = no-op.
- Loading: module loaders accept an optional overlay parameter
  (`load_archimate_4_module(guidance=…)`); `app_bootstrap` reads each active repo's
  `.arch-repo/guidance-cache/*.guidance.yaml` (gitignored via the scaffolded
  `.arch-repo/.gitignore`) in tier order and passes per-module slices.
  `SpecializationCatalog` construction consumes the same overlay for specialization-level
  entries. Bootstrap-time load means the existing `@lru_cache` registry pattern is
  untouched; a guidance import takes effect on backend restart (consistent with the
  established ops model; the CLI prints this).
- Import CLI: `arch-import-guidance --source <url|path> [--module <alias>]
  [--repo-scope engagement|enterprise] [--dry-run] [--strict]`
  (new `src/infrastructure/cli/arch_import_guidance.py`, argparse-subcommand style, urllib
  idiom from `get_plantuml.py`; `--repo-scope` defaults to engagement). Validates schema +
  guidance keys against the registry and the **target repo's** specialization catalog
  (unknown module/type/specialization ⇒ listed, non-matching entries skipped or `--strict`
  fails), writes `<repo>/.arch-repo/guidance-cache/<alias>.guidance.yaml` plus a provenance
  sidecar `<alias>.guidance.meta.yaml` (source, SHA-256, format version, timestamp,
  matched/unmatched counts — D3a), prints an import summary.
- Extraction (one-time, done first): `tools/extract_guidance.py` reads the *current*
  `entities.yaml` texts and emits the publishable guidance file to an **out-of-repo** path;
  the same commit strips the YAML values to `""`. The published file's hosting location,
  terms, and expected hash/version are recorded in the docs (open question Q2);
  `config/settings.yaml` gains `guidance_default_source: ""` so a hosted URL can be
  preconfigured (an operational default, not a governance surface).
- Audit boundary: license cleanliness is proven against **all shipped artifacts**, not just
  `entities.yaml` — docs, skills, test fixtures, scaffolding defaults, generated type
  payloads, README/media captions — using distinctive-phrase sampling from the extracted
  file (see WU-B5).

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
    connection_types:               # base guidance reserved (not populated today);
      archimate-flow:               # specialization guidance supported from the start
        specializations:
          money-flow:
            create_when: "…"
            never_create_when: "…"
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
- **Domain, new**: `src/domain/viewpoints.py` — `ViewpointDefinition`: `slug`, `version`
  (integer, bumped on any semantic change to the definition), `name`,
  `description/rationale`, `purpose ∈ {designing, deciding, informing}`,
  `content ∈ {details, coherence, overview}` (the two mandatory Chapter-13 dimensions),
  `stakeholders: [str]`, `concerns: [str]`, `scope: ConceptScope`,
  `representation_types: [diagram-type slug | "matrix" | "table" | "exploration"]`,
  optional `query` (`ExecutableViewpointQueryV1` — the scope doubles as the type-level
  predicate; full shape, semantics, and limits in D15) and optional `presentation`
  (`PresentationSpec` — representation, display options, abstract style tokens; capability
  checking per D15); and `ViewpointApplication`: `target_kind`
  (`diagram | matrix`, extensible to catalogs/reports later), `target_id`,
  `viewpoint_slug`, `pinned_version`, optional `enforcement_override` and
  `derivation_params`. The definition/application split keeps definitions reusable and
  makes each use explicit — new target kinds later consume applications without rework.
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
  (`viewpoints.yaml`, optional library — Appendix C is non-mandatory); user-defined ones
  live in `.arch-repo/viewpoints.yaml` (enterprise = baseline, engagement may extend —
  same two-tier governance as specializations, D14). A diagram/matrix persists its
  `ViewpointApplication` in frontmatter (`viewpoint: {slug, version, …}`); a pinned version
  older than the current definition yields a distinct *stale-application* verifier warning
  and a GUI affordance to re-pin after review — never a silent reinterpretation.
- **Surfaces**: verifier contribution (viewpoint-violation *warnings*, distinct from
  metamodel violations); GUI — viewpoint selector on diagram create/edit, palette + entity
  picker filtering through the narrowed scope from the existing
  `ui-config`/`/api/ontology` endpoints (extended with an optional `viewpoint` parameter),
  ghosting for out-of-scope existing content; a viewpoints management view (list/create/edit
  per-repo definitions) with an **Execute** action per D15; MCP — viewpoint fields included
  in `artifact_authoring_guidance` output and accepted by
  `artifact_create_diagram`/`artifact_edit_diagram` frontmatter (no new tools;
  guidance-first for agents).
- **On-demand execution (D15)**: a viewpoint with a `query` is executable from the
  management view and selectable on the graph-exploration page (which supplies the
  `execution_anchor` input where a definition's expansion rule asks for one). Boundaries
  are explicit: the **domain** owns the query/presentation/result value objects; the
  **application** owns the `EvaluateViewpoint` use case over the read ports and the
  derivation-strategy catalog — including typed attribute-predicate evaluation and
  `group_by` resolution against the D13 effective schemas, with attribute references
  validated at definition save — producing the `ViewpointExecutionResult` DTO (sorted IDs,
  per-node group keys where `group_by` is set, counts, warnings, truncation, limits,
  duration — D15); **infrastructure** owns the read-only REST endpoint and the GUI
  adapters, which call the use case only. Three
  execution surfaces render the result, all reusing existing machinery and each declaring
  its display capabilities: `exploration` — the cluster layout of `GraphExploreView.vue` /
  `useForceGraph.ts`, mapping abstract style tokens to node shape/icon/color (defaults
  where no rule matches); `table` — the filtered catalog view the entities list already
  provides (columns/badges/sort); `matrix` — an ephemeral matrix rendering via the
  existing matrix builder (row/column grouping, cell emphasis). The GUI shows execution
  diagnostics: result counts, truncation/omission warnings, the active filter summary,
  unsupported-display warnings, an explained empty state, and an explicit "re-run against
  current model" action. Executions are ephemeral and read-only — a "generated view
  filter" in the Horizzon sense, never persisted as a diagram.
- **UX commitments (viewpoint selection, filtering, and output customization)** — the
  viewpoint feature succeeds or fails on usability, so these are design requirements, not
  polish:
  - *Guided query building, never raw YAML in the GUI*: filters are structured rows with
    dimension pickers populated from the live catalogs (groups, entity/connection types,
    specializations, and profile attributes from the effective schemas), typed
    operator/value inputs (enum attributes offer their values as choices), and a
    **debounced live result-count preview** (a tight-limit E7 execution) so "adjust filter
    → see effect" is one continuous flow.
  - *Progressive disclosure*: the common case (type + group filters, one representation)
    is immediate; attribute predicates, expansion rules, and purpose/content/stakeholder
    metadata sit behind clearly labeled advanced sections.
  - *Capability-driven output customization*: the representation picker exposes only the
    chosen surface's declared capabilities (the form cannot express an unsupported
    option); styling rules show a **live legend preview** (token → resolved
    shape/icon/color); `group_by` offers only valid keys.
  - *Integrated flows, both directions*: apply/execute a viewpoint from where the user
    already is (graph-exploration picker, entities-list, diagram editor) AND promote an
    ad-hoc state into a definition — notably **"save current filters as viewpoint"** from
    the entities-list view, which already has the filter vocabulary. An active viewpoint
    is always visible as a dismissible chip/badge with its name and a one-click clear.
  - *Explainability everywhere*: ghosted diagram content, excluded entities, and empty
    results each carry a "why" (which filter/scope excluded them — the Archi hints
    pattern); the diagnostics of WU-E8/E9 (counts, truncation, active-filter summary,
    drift warnings) are part of the primary UI, not a debug console.
  - A **design spike with user review precedes the viewpoint GUI work** (wireframes/flows
    for builder, selector, execution surfaces) — layout and flow are decided by design,
    not emergent from implementation order.
- **Deferred (explicitly out of scope here, candidate follow-up plan)**: generating
  *persistent* diagrams from executions, the fuller presentation-rule engine
  (label/tooltip/chart rules, attribute-driven heat maps), saving executions as
  first-class view artifacts, viewpoint publishing/pinning, parameterized viewpoints,
  catalog/report view *artifact kinds* (the ephemeral table/matrix executions above are
  renderings, not new artifact types). They compose later without rework because selection
  (`query`) and presentation are separate blocks on the definition.

Spec fidelity notes: purpose/content classification is mandatory-shaped and included from the
start; "view ≠ diagram" is honoured minimally by making matrices viewpoint-governable and by
`derivation_defaults` for generated views; the conformance docs (§5.7) document the
implementation-defined manner, as the standard requires.

### 4.5 Exchange format (D10)

Exchange is deliberately **two milestones**. Milestone 1 (readiness, on this plan's path):
the declarative mapping table, XSD acquisition + licensing resolution (Q3), and the
documented lossy-case policy — reviewed and signed off as a hard gate. Milestone 2
(implementation) starts only after that gate **and** after specialization/profile semantics
(WS-D) are stable, because the mapping depends on them (layer specializations, `money-flow`,
assignment variants, profile → `properties` mapping). If the desired conformance wording
(Q4) requires exchange support, the gate becomes release-blocking; otherwise core compliance
ships without waiting.

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
- **WS-B License compliance** (D2/D3/D3a): extraction script + publishable YAML
  (out-of-repo), strip `entities.yaml` guidance to empty, `GuidanceOverlay` domain type +
  loader threading, repo-local gitignored `.arch-repo/guidance-cache/` +
  `guidance_default_source` setting, `arch-import-guidance` CLI with `--repo-scope` and
  provenance sidecars, full shipped-artifact license audit (distinctive-phrase sampling).
- **WS-C Core semantics**: composition semantics verification against final §5.1.2/Appendix B
  (permitted wherever aggregation is; derivation-strength ordering
  realization < assignment < aggregation < composition wherever `hierarchy_priority` or
  relationship classification is consumed); full `permitted_relationships` matrix recheck
  against final Appendix B; multiplicity rename (D9) with one-time repo migration
  (`arch-repair`-style) + junction rule (warn when multiplicity is set on a
  junction-attached end).
- **WS-D Specializations & profiles** (D4/D5/D6/D13/D14): unified concept-level
  `SpecializationCatalog` (domain, `concept_kind: entity | connection`), module + two-tier
  repo `specializations.yaml` loading, ArchiMate 4 §14.2.1 informative library shipped
  (guidance-empty, incl. relationship specializations), entity frontmatter + connection
  record `specializations:` + verifier rules (existence, concept-kind/parent match,
  restriction narrowing), minimal `ProfileDefinition` + deterministic merge semantics,
  attribute-schema attachment by reference, guillemet stereotype + notation rendering on
  boxes and relationships (parent-notation fallback), GUI picker + display,
  `artifact_authoring_guidance` + `types.generated.ts` exposure, dormant-surface removal +
  assurance profile migration, promotion superset checks extended to specializations and
  attached schemata.
- **WS-E Viewpoints** (D7/D8): `ConceptScope` + versioned `ViewpointDefinition` +
  `ViewpointApplication` (domain), re-basing of diagram-type filters and binding
  admissibility onto `ConceptScope` (behavior-preserving), two-tier repo + module viewpoint
  definitions, frontmatter applications with pinned versions + stale-application warnings,
  verifier warnings, GUI selector/palette-filtering/ghosting + management view, on-demand
  execution (declarative selection + expansion rules) into the graph-exploration cluster
  view, filtered catalog table, and ephemeral matrix with shape/icon/color styling (D15),
  guidance/MCP exposure, built-in starter library (small, e.g.
  layered/application/motivation — Appendix C is optional).
- **WS-F Exchange** (D10): **F-readiness** (gate): mapping table incl. concept-level
  specializations, XSD acquisition/licensing (Q3), lossy-case policy, sign-off. Then
  **F-implementation**: codec adapter (defusedxml, XSD validation), import/export use cases
  with dry-run, identity mapping, `arch-exchange` CLI, round-trip + migration-table tests.
- **WS-G Self-model & docs** (D11): composition review of the 155 aggregations as
  spike-then-batch (classification rubric on a reviewed sample first, then full conversion
  via MCP), "Adopt ArchiMate 4" ADR superseding the NEXT ADR, rename of draft-era
  self-model entity names/slugs, **self-model alignment with this plan's new capabilities**
  (investigate → propose → review → apply at the model's established granularity:
  description enrichment first, then connections, new entities only where guidance and
  granularity warrant — requirements/components/functions/data-objects for viewpoints,
  customization, guidance import, exchange, and repo upgrade; matrix + promotion-activity
  diagram updates for D14), conformance documentation page (documents every
  "implementation-defined manner": viewpoints, customization, guidance import),
  **documentation regeneration and feature docs** — regenerate the MCP tool reference
  tables (`tools/generate_mcp_docs.py`, whose `--check` gate fails CI on staleness) after
  every tool-description change (guidance empty-state, viewpoint/specialization exposure);
  update the affected manual pages (`03-modeling/views-and-exploration.md`,
  `diagramming.md`, `05-extensibility/schemata-and-profiles.md`, `ontology-modules.md`,
  `reference/cli-and-backend.md`, `configuration.md`, `git-sync-promotion.md`); add new
  sections/pages for viewpoints (incl. executable viewpoints) and specializations +
  profiles — README/badges/status update, docs sweep.

## 6. Security & Auth Considerations

- **Guidance import (new input path)**: fetches YAML from a user-configured URL/path.
  Mitigations: HTTPS-only by default for URLs (plain HTTP requires an explicit flag),
  `yaml.safe_load`, response size cap, schema validation before write, content is inert prose
  (rendered as text in GUI/MCP — no HTML injection into the Vue frontend, which renders text
  nodes; verify no `v-html` sink on guidance fields), no code paths execute imported content.
  Provenance sidecars (D3a) record source + SHA-256, making a tampered or swapped source
  detectable against the documented expected hash.
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
- **All persisted-format migrations run through `arch-repair upgrade` (D17)** — one
  user-facing command that reports what must change, auto-migrates what it can (only on a
  clean worktree with no backend serving the target repo), and lists the rest as manual
  adaptations.
- **Multiplicity field rename**: a real repository migration (D9), implemented as the
  first registered D17 upgrade step — rewrites `src_cardinality`/`tgt_cardinality` keys
  and `include_cardinality` annotations; dry-run by default with a full report,
  recommends a backup/branch before `--commit`, idempotent (re-run = 0 changes), runs under
  the standard write/index reconcile machinery with an index rebuild. Legacy keys stay
  readable for exactly one release with a distinct deprecation verifier code, so **external
  user repositories** (not just this workspace's two) migrate on their own schedule;
  REST/MCP payload fields and `types.generated.ts` switch with the release; release notes
  document the command.
- **Promotion governance (D14)**: the existing attribute-profile superset check
  (`promote_schema_check.py`) is extended to specializations and specialization-attached
  schemata — promotion fails loudly listing engagement-only definitions a promoted artifact
  depends on. Connection specializations participate via the connection records being
  promoted.
- **Self-model composition conversions** are ordinary model edits through MCP (aggregation →
  composition where existence-dependency holds), reviewed in batches; no schema change.
- **Persisted-format additions** are optional — absent means today's behavior: entity
  frontmatter `specializations:` and diagram frontmatter `viewpoint:` applications
  (scaffolded `frontmatter.entity/diagram.schema.json` gain the optional properties);
  connection specializations live in the new per-connection metadata block under each
  connection heading (D6), validated via the `connection-metadata.{connection-type}`
  schema convention — **not** in `frontmatter.outgoing.schema.json`, which governs the
  shared file-level frontmatter only; optional `exchange_id:` extra on import.
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
  multiplicity-on-junction, legacy-cardinality-key, specialization-unknown,
  stale-viewpoint-application) so reports are filterable.
- Viewpoint execution: each run logs a structured summary (viewpoint slug + versions,
  repo_scope, counts, truncated, duration, warnings incl. capability drift) — the same
  data the `ViewpointExecutionResult` carries — so slow or truncated executions are
  diagnosable from logs without reproducing them.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Appendix B recheck reveals rule deltas beyond composition (matrix drift from snapshot) | WS-C treats the matrix recheck as its own WU with a diff report before any rule edit; self-model verify run after. |
| Exchange-format 3.x↔4 mapping has genuinely lossy cases | Declarative mapping table + explicit documented fallbacks + round-trip tests; lossy cases reported, never silent. |
| The spec documents (ArchiMate 4, C19C 3.1, XSDs) can't be committed (no-PDF policy, licensing) | Verification WUs cite section numbers and record conclusions in the ledger; XSDs fetched at dev time (gitignored) with a pinned checksum; open question Q3 covers XSD redistribution. |
| `ConceptScope` re-basing regresses existing diagram-type filtering | Behavior-preserving refactor gated by the existing diagram-type test suites + a characterization test snapshotting `effective_entity_types` per module before/after. |
| Guidance stripping degrades agent authoring quality until import is configured | `artifact_authoring_guidance` states explicitly when guidance is empty + how to import; default source URL preconfigured once hosted (Q2). |
| Dormant profile surface has a hidden consumer | D5 verification step with an explicit stop-and-record escalation. |
| Bulk composition conversion misclassifies aggregations | Spike-then-batch (WU-G1a sample rubric reviewed before WU-G1b executes); conversions batched with verify runs between batches. |
| Multiple specializations produce ambiguous effective schemas | D13 deterministic merge order + conflict-as-error; property-collision tests. |
| Exchange work delays core compliance | D10 gate: readiness only on the critical path; implementation starts after WS-D stabilizes and Q3 sign-off. |
| Executable-viewpoint queries degrade under large models or drift across app versions | Enforced max results/hops + timeout with clean cancellation (D15); per-run structured summaries; capability + strategy-version drift surfaced as explicit warnings/errors, never silent reinterpretation. |

## 10. Open Questions

- [ ] **Q1 — Module naming**: confirm `archimate_4` / `archimate-4-0` / `archimate-4`
  (§4.1). — Owner: review
- [ ] **Q2 — Guidance hosting**: where will the extracted guidance YAML live (public repo,
  gist, site)? Determines `guidance_default_source`. — Owner: Michael
- [ ] **Q3 — C19C XSD acquisition/licensing**: confirm the exchange-format XSDs may be
  fetched at dev/test time and whether they may ship in the repo (default assumption: fetch,
  don't commit). **Hard gate for exchange implementation (D10).** — Owner: Michael
- [ ] **Q4 — Conformance wording**: "implements/aligned with ArchiMate 4" vs. a conformance
  claim (certification/trademark implications) in README/docs. — Owner: Michael
- [ ] **Q5 — Multiple specializations per entity**: plan supports a list per spec; confirm
  the GUI/UX should too, or restrict to one initially. — Owner: review
- [ ] **Q6 — Deferred viewpoint scope**: executable viewpoints (declarative selection incl.
  profile-attribute predicates + expansion rules) rendering ephemerally into the
  graph-exploration cluster view, the filtered catalog table, and the matrix builder —
  with shape/icon/color styling and grouping keyed by type/specialization/group/discrete
  profile attributes — are IN scope (D15); agree that the rest — persistent generated
  diagrams, label/tooltip/chart rules, continuous heat-map scales, saving executions as
  view artifacts, publishing/pinning, *user-defined* parameterized viewpoints (the
  built-in `execution_anchor` input is in scope, D15) — goes to a follow-up plan.
  — Owner: review

## 11. Acceptance Criteria (plan-level)

- [ ] No string `archimate_next` / `archimate-next` / "ArchiMate NEXT" remains in active
  code, config, tests, docs, skills, or generated types (historical PLAN/TASKS ledgers
  excepted, per convention); startup check rejects unresolvable `permitted_mappings` tokens.
- [ ] Zero ArchiMate-derived guidance prose in **any shipped artifact** (entities.yaml,
  docs, skills, fixtures, scaffolding defaults, generated payloads — verified by
  distinctive-phrase audit); `artifact_authoring_guidance` returns imported guidance after
  `arch-import-guidance` + restart, and a clear empty-state before.
- [ ] The extracted guidance YAML exists outside the repo, validates against the v1 schema,
  and round-trips through the import CLI (including at least one entity and one connection
  specialization entry); every import leaves a provenance sidecar (source, SHA-256, version,
  counts); docs record the hosting location, terms, and expected hash.
- [ ] Composition passes the Appendix-B-derived rule tests; derivation ordering includes it
  as strongest; the self-model contains deliberate composition connections after review.
- [ ] Multiplicity terminology is consistent in code/UI/docs; migration (dry-run, backup
  recommendation, idempotent report, index rebuild) leaves zero legacy keys in this
  workspace's repos; legacy keys readable for exactly one release with a deprecation
  verifier code; junction rule fires in tests.
- [ ] `arch-repair upgrade` reports repo-format findings against the current format
  contract (profiles, customizations, frontmatter, connection declarations) with a stable
  per-repo-root `--json` shape incl. step-registry identity and
  applied-steps-before/after; supports repeatable `--repo-root` and `--workspace`
  (per-root reports + aggregate summary); auto-migrates registered steps only on a clean
  worktree with no backend serving the *target* repo — guarded via the new
  backend-identity endpoint with realpath normalization (guards tested, incl. fail-closed
  on unconfirmable roots/pre-endpoint backends and unrelated-backend-not-blocking); lists
  non-migratable findings with manual instructions; is idempotent; records
  `format_contract_version` + applied step ids per repo in `.arch-repo/config.yaml`
  (software version as metadata only); every persisted-format change in this plan has a
  registered step or detector (coverage test); the legacy no-subcommand `arch-repair`
  invocation still runs git-repair with a deprecation notice.
- [ ] Specializations: informative library loaded **including relationship
  specializations**, two-tier repo declarations validated, entity frontmatter and
  per-connection metadata blocks round-trip, stereotypes + notation render on boxes and
  relationships, GUI picker works, `ProfileDefinition` (`.arch-repo/profiles.yaml` +
  `x-recommended`) merge is deterministic with conflict errors, dormant profile surface
  removed with assurance schemas migrated, promotion superset checks cover specializations
  + attached schemata + profiles.
- [ ] Viewpoints: `ConceptScope` is the single admissibility path (old filter code deleted),
  viewpoint selection filters palette/pickers non-destructively, verifier warns on
  violations and on stale applications (pinned version < definition version), definitions
  ship + per-repo CRUD works; an executable viewpoint evaluates its `query_schema: 1`
  selection on demand within enforced limits (max results/hops, timeout) and renders
  ephemerally in the cluster view (abstract style tokens → shape/icon/color), as a
  filtered catalog table, and as a matrix — profile-attribute filters, grouping, and
  attribute-keyed styling behave per the typed predicate semantics, result IDs
  sorted/stable, diagnostics (counts, truncation, unsupported-display warnings) surfaced,
  no artifact created and no write path touched (negative test); promotion blocks
  engagement-only viewpoint
  dependencies of promoted views with **exact-version** matching (re-pin only as an
  explicit promotion step).
- [ ] The connection-declaration grammar has exactly one implementation
  (`src/domain/connection_declaration.py`); the read parser, write parser, and formatter
  delegate to it, and a shared round-trip property test covers heading + metadata block +
  assoc + description.
- [ ] Exchange readiness gate passed (mapping table signed off, Q3 resolved) before any
  codec code; then: fixture model round-trips (export→import) losslessly for mapped
  concepts; Appendix E.4 migration cases covered by tests (incl. relationship
  specializations); composition never downgraded on either path.
- [ ] Conformance documentation page describes every implementation-defined mechanism.
- [ ] The self-model reflects the plan: a reviewed change-set (enrich-first discipline)
  is applied via MCP; every D1–D17 capability is modeled or explicitly assessed as below
  granularity; the D14 promotion check appears in the promotion activity diagram;
  `artifact_verify` clean.
- [ ] Documentation is current: `tools/generate_mcp_docs.py --check` passes (tool tables
  regenerated after all description changes); viewpoints (incl. executable viewpoints)
  and specializations + profiles have dedicated user-facing docs; the affected existing
  pages (views/diagramming/schemata/ontology-modules/CLI/configuration/promotion) reflect
  the new mechanisms; no page still documents pre-plan behavior.
- [ ] Quality gates green throughout: `pytest` 0 failures, `ruff` 0 errors, `zuban check`
  pass, frontend `lint`/`typecheck`, `types.generated.ts` regenerated where required.

## 12. Implementation Checklist

Maintained as checkbox work-units with anchors, acceptance criteria, dependencies, and a
resume protocol in **`TASKS-archimate-4-compliance.md`**.
