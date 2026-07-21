# TASKS — Named Attribute Profiles: Registry, Lifecycle, and Failure Semantics

Execution ledger for `PLAN-attribute-profile-registry.md`. The plan is
normative; this file tracks execution and records what was verified.

## Resume protocol

1. Read `PLAN-attribute-profile-registry.md` §3 (locked decisions) and §4
   (failure semantics) first — they are not re-litigated.
2. Find the first unticked WU whose dependencies are ticked.
3. Gates before every commit: `uv run python -m pytest -q -n auto` (one at a
   time, never concurrent), `uv run ruff check src/ tests/`, `uv run zuban
   check`; frontend from `tools/gui/`: `npm run lint && npm run typecheck &&
   npx vitest run` (full `npm run lint`, never `lint:fast`).
4. Backend changes are inert until the owner restarts `arch-backend`; MCP
   surface changes also need a Claude session restart. Queue live verification.

## Questions

None open.

RETRACTED — a previous Q1 proposed reconciling the assurance relations
`responsible-for` / `accountable-for` with the ArchiMate assignment
specializations `responsibility-assignment` / `behavior-assignment`. Verified
false: different modules, different endpoint type systems, different semantics
(GRC accountability vs ArchiMate active-structure-to-behavior assignment), and
different persistence and exposure (confidential SQLCipher store vs public
markdown). They share vocabulary and nothing else. See PLAN §10.

Carry the scope note from PLAN §10 into every stream: `SpecializationCatalog`
keys by `(module, kind, parent, slug)`, so the mechanism is module-agnostic —
never hardcode `archimate_4`.

## Stream P — Registry and resolution

### WU-P1 — Registry format and loader
- [x] Declaration format with `profile_schema: <int>` (format version) and per
      profile `version: <int>` (content version) — PLAN §3 P4.
- [x] An unrecognised `profile_schema` is a typed error, never a best-effort
      parse (follow the `QUERY_SCHEMA_VERSION` precedent).
- [x] Shipped registry in the ontology module; optional repo-level registry.
- [x] Tests: valid load; unknown format version rejected; absent registry is a
      valid "no named profiles" state (regression guard for existing repos).

#### WU-P1 PROGRESS (2026-07-21)
- Domain: `src/domain/profile_registry.py` — `PROFILE_SCHEMA_VERSION`, `NamedProfile`
  (name + content `version` + compiled `ProfileDefinition`), `ProfileRegistry` (unique
  by name; `.empty()` = the no-named-profiles state), `profile_registry_from_mapping`
  (typed `ProfileRegistryError` on non-mapping / missing-or-unknown `profile_schema` /
  non-int version / missing per-profile `version`), `merge_profile_registries` (union;
  raises on a duplicate name across shipped modules). Attribute parsing factored out of
  `profiles.py` as `attributes_from_mapping` and reused so named-profile attributes read
  identically to inline specialization attributes.
- Loaders: `src/application/profile_registry_loading.py::load_repo_profile_registry`
  reads optional `.arch-repo/profiles.yaml` (absent → empty; malformed → ProfileRegistryError).
  Shipped module registry: `src/ontologies/archimate_4/profiles.yaml` (empty `profiles: {}`,
  documents the format) loaded by `_load_module_profiles` in the module loader.
- Wiring (parallels `specialization_catalog` exactly): `OntologyModule.profile_registry`
  added to the protocol + all three module impls (archimate loads its file; sysml/assurance
  return empty); `RuntimeCatalogs.profiles` field + `merge_profile_registries` in
  `build_runtime_catalogs`.
- NOT DONE here (later WUs): binding a specialization to a named profile (P2), folding
  bound profiles into `compute_effective_attribute_schema` (P3), conflict classification
  (P4). Repo loader is standalone until P3 consumes it. `.arch-repo/profiles.yaml` lives
  OUTSIDE `schemata/`, so `_schema_inventory_findings` does not flag it (Class-A teaching is Q1).
- Tests: `tests/domain/test_profile_registry.py` (11) + `tests/application/test_profile_registry_loading.py`
  (6, incl. the shipped-empty regression guard through `build_runtime_catalogs`). ruff + zuban clean.

### WU-P2 — Binding declaration (needs P1)
- [ ] A specialization may bind named profiles by name, in declaration order.
- [ ] A binding to an undefined profile is Class A (structural) — see WU-Q1.
- [ ] Tests: single binding; multiple bindings; binding the same profile to
      several (type, specialization) pairs contributes to all of them.

### WU-P3 — Resolution order (needs P2)
- [ ] Extend `compute_effective_attribute_schema` to append bound-profile
      fragments between the base schema and specialization profiles
      (PLAN §3 P2). The merge itself is already N-ary — do not modify it.
- [ ] **Accept an ordered list of applied specializations, not a scalar**
      (PLAN §3 P2a) even before Stream V rolls out multiple specializations
      model-wide. Retrofitting scalar→list through the merge, verifier, and
      conflict classifier later is far more expensive than accepting a list now.
- [ ] Tests: order holds (specialization overrides shared profile overrides
      base); parent-attribute inheritance still works (regression — this
      already works today via fragment 1 and must not break); two
      specializations contributing an incompatible attribute is an ordinary
      Class B conflict.

### WU-P4 — Conflict classification (needs P3)
- [ ] Classify each conflict as Class A (structural) or Class B (scoped) per
      PLAN §4.
- [ ] Identical redefinition composes silently; only incompatible `type`
      redefinition conflicts (PLAN §3 P3 — today's semantic, keep it).
- [ ] Tests: identical redefinition across two profiles is NOT a conflict;
      differing types IS; each class is assigned correctly.

## Stream Q — Failure semantics

### WU-Q1 — Class A startup validation (needs P4)
- [ ] **Extend `startup_validation.py`** (`validate_repo_compatibility` /
      `_schema_inventory_findings` / `RepoCompatibilityError`) — it already
      implements this exact posture (hard errors raise, tolerable ones warn).
      Do NOT build a parallel validator.
- [ ] Validate attached repos at startup, before the index build, under the
      privileged write gate — mirroring `_group_registry_startup.py`.
- [ ] Engagement (writable) repo: hard fail with the file, the reason, and the
      fix. Enterprise (attached, read-only): log and continue.
- [ ] **Only attached repos** (PLAN §3 P6) — never a filesystem scan.
- [ ] Tests: malformed registry in the engagement repo aborts startup; the same
      defect in the enterprise repo does not; an unattached repo with a broken
      registry is never read.

### WU-Q2 — Class B quarantine set (needs P4)
- [ ] Compute the quarantined (entity-type, specialization) pairs at load.
- [ ] The effective schema for a quarantined pair resolves to the unambiguous
      fragment set, flagged `quarantined` with reasons.
- [ ] Tests: quarantine is confined to the affected pair; sibling
      specializations of the same base type are unaffected; reads of existing
      entities in a quarantined pair still work.

### WU-Q3 — Write-boundary gate (needs Q2) — LOAD-BEARING
- [ ] Reject creates/edits for a quarantined pair with a typed error naming the
      colliding profiles, the field, and the conflicting types.
- [ ] **Close the verified gap**: the write path uses `load_attribute_schema`
      (base only) and never sees specialization profiles
      (`artifact_write_formatting.py:336`). The gate must sit where every
      transport passes through it.
- [ ] Tests: the write is rejected through REST, MCP, **and** CLI (PLAN §8
      acceptance 5 — per-transport, since a gate that only covers one is not a
      gate); a non-quarantined pair writes normally.

### WU-Q4 — Stream Q boundary
- [ ] Full backend gates green. No entity can be written against an ambiguous
      schema through any transport.

## Stream R — Reconciliation

### WU-R1 — Conflict and drift reporting (needs Q2)
- [ ] Upgrade step reporting each conflict (profiles, field, types, resulting
      quarantined pairs) and content-version drift (shipped profile advanced
      past a customisation — the capability P4's content version exists for).
- [ ] Non-destructive: never overwrite operator content
      (`DefaultSchemataEnsureStep`'s contract).
- [ ] Tests: conflicts reported; drift reported with the intervening changes;
      operator customisations preserved.

### WU-R2 — Proposed resolutions (needs R1)
- [ ] Propose rename / align-type / unbind as manual instructions.
- [ ] Auto-migrate only where unambiguous (operator file byte-identical to an
      older shipped version).
- [ ] Tests: ambiguous cases are never auto-migrated.

## Stream S — Surfaces

### WU-S1 — Quarantine on the schema endpoint (needs Q2)
- [ ] Extend the existing conflicts channel (`entities.py:221` already returns
      `conflicts`) with quarantine state — do not add a parallel channel.
- [ ] REST + MCP parity, parity-tested.

### WU-S2 — GUI surfacing (needs S1)
- [ ] Banner on affected entity types; submit disabled with the reconciliation
      message.
- [ ] Progressive enhancement only — correctness is already guaranteed by WU-Q3
      (PLAN §3 P8). Verify by testing that a GUI unaware of quarantine still
      cannot write ambiguous data.
- [ ] Vitest coverage, separate file per component.

## Stream W — Relationship profiles (needs P3, Q2)

Symmetric with entities. The specialization dimension is already wired for
connections through every layer (PLAN §9) — only the schema side is entity-only.
Land WITH the entity work, not after: both share the resolver, conflict
classifier, quarantine machinery, and reconciliation step.

### WU-W1 — Specialization-scoped connection schemata (needs P3)
- [ ] `connection-metadata.{type}.{slug}.schema.json` filename convention.
- [ ] `list_schema_files` classifies it (today `specialization-attachment` is
      entity-only), and `startup_validation._schema_inventory_findings`
      validates its subject.
- [ ] `compute_effective_connection_metadata_schema`, mirroring the entity
      resolver including named-profile bindings and resolution order.
- [ ] Tests: mirror the entity resolution tests.

### WU-W2 — Verifier merge for connections (needs W1)
- [ ] `check_connection_metadata_schema` validates against the MERGED effective
      schema and reports conflicts, mirroring E043.
- [ ] Tests: conflict reported; quarantine applies to a (connection-type,
      specialization) pair exactly as for entities.

### WU-W3 — Surfaces (needs W1)
- [ ] Effective merged connection-metadata schema in the authoring-guidance
      payload (REST + MCP parity).
- [ ] GUI renders it through the existing `TypedPropertyInput` — the connection
      specialization picker already exists
      (`specializationOptionsForConnectionType`). No new GUI concept.
- [ ] Tests: Vitest for the connection metadata editor.

## Stream T — Docs and self-model

### WU-T1 — Reference documentation
- [ ] Profile authoring, binding, versioning, resolution order, and the failure
      semantics — the quarantine behaviour especially, since an operator who
      meets one must be able to act on it.

### WU-T2 — Self-model sync
- [ ] Model the profile-registry capability in ENG-ARCH-REPO: guidance-first,
      descriptions over new entities.

## Stream V — Multiple specializations per concept (P9)

Rewrites D6. ArchiMate 3.1 §15.2 verbatim: *"multiple specialization profiles
may be assigned to the same generalized concept; in the default notation, these
are shown as a comma-separated list"*. Sequenced after P–S; the DECISION is
already locked because WU-P3 depends on it.

### WU-V1 — Storage and back-compatibility
- [ ] Frontmatter accepts a list; a bare scalar keeps working and is read as a
      one-element list. No repo migration required.
- [ ] Tests: scalar form round-trips unchanged (regression).

### WU-V2 — Rendering (needs V1)
- [ ] `format_specialization_guillemet` renders the spec's comma-separated list
      («a, b»). It is singular today.
- [ ] Tests: single and multiple render per spec.

### WU-V3 — Querying and styling (needs V1)
- [ ] Viewpoint grouping by `specialization` and style/scale `applies_to`
      matching over a set. Both already compare via `frozenset`
      (`viewpoint_style_evaluation.py`, `viewpoint_scale_styling.py`), so this
      extends naturally — verify rather than assume.
- [ ] Decide and document what grouping by specialization MEANS for a concept in
      several groups (appears in each, versus a composite bucket).
- [ ] Tests: grouping and style matching with multiple specializations.

### WU-V4 — Write paths and GUI (needs V1)
- [ ] Entity and connection write paths accept multiple; `promote_schema_check`
      handles the set across repos.
- [ ] GUI picker single-select → multi-select; `types.generated.ts` regenerated.
- [ ] Tests: per-transport write coverage; Vitest for the picker.

## Stream U — AIBOM handoff

### WU-U1 — Unblock the AIBOM plan
- [ ] Confirm `PLAN-aibom-model-derived.md` D3 can be executed on named
      profiles: one shared `ai-provenance` profile bound to the AI
      specializations, plus small per-specialization profiles for what genuinely
      differs.
- [ ] Verify the AIBOM schemata no longer redeclare attributes inherited from
      their base types (inheritance already works — PLAN §2).

## Restart-gated live verification queue

- [ ] Startup Class A behaviour on the restarted backend (engagement hard fail,
      enterprise warn) — verify with a deliberately broken registry in a
      scratch repo, never the live one.
- [ ] Quarantine write rejection through MCP after a session restart.
