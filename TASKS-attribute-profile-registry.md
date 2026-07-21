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
- [x] A specialization may bind named profiles by name, in declaration order.
- [~] A binding to an undefined profile is Class A (structural) — see WU-Q1.
      (The binding is STORED here; the undefined-name check is WU-Q1's startup
      validation, per the ledger's own cross-reference — not enforced in P2.)
- [x] Tests: single binding; multiple bindings; binding the same profile to
      several (type, specialization) pairs contributes to all of them.

#### WU-P2 PROGRESS (2026-07-21)
- `SpecializationInfo.bound_profiles: tuple[str, ...]` (declaration order, de-duplicated),
  parsed from a specialization entry's `profiles: [name, ...]` list by `_bound_profiles`
  in `specialization_infos_from_mapping`. `overlay_specialization_guidance` preserves it
  (uses `replace`); there is no write-back serializer to update (specializations.yaml is
  hand-authored / scan-detected, not round-tripped through a to-mapping).
- The undefined-name → Class A check is deferred to WU-Q1 (startup validation) exactly as
  the box cross-references; storing an unresolvable name here is intentional so load never
  fails on it.
- Tests: `tests/domain/test_specialization_profile_bindings.py` (6). ruff + zuban clean.

### WU-P3 — Resolution order (needs P2)
- [x] Extend `compute_effective_attribute_schema` to append bound-profile
      fragments between the base schema and specialization profiles
      (PLAN §3 P2). The merge itself is already N-ary — do not modify it.
- [x] **Accept an ordered list of applied specializations, not a scalar**
      (PLAN §3 P2a) even before Stream V rolls out multiple specializations
      model-wide. Retrofitting scalar→list through the merge, verifier, and
      conflict classifier later is far more expensive than accepting a list now.
- [x] Tests: order holds (specialization overrides shared profile overrides
      base); parent-attribute inheritance still works (regression — this
      already works today via fragment 1 and must not break); two
      specializations contributing an incompatible attribute is an ordinary
      Class B conflict.

#### WU-P3 PROGRESS (2026-07-21)
- `compute_effective_attribute_schema` now takes `specialization_slugs: Sequence[str]`
  (list-native, P2a) + a `profile_registry` kwarg (shipped; default empty). Order is
  base → bound named profiles (declaration order across the applied specializations,
  deduped) → each specialization's own inline+attachment (declaration order) → one
  unchanged N-ary `merge_property_schemas`. The repo-level registry (loaded via a cached
  `_repo_profile_registry`, cleared by `clear_schema_cache`) overrides a shipped profile of
  the same name. An undefined bound name is LEFT UNRESOLVED (contributes nothing) — Class A
  is WU-Q1's startup check, never invented here.
- All three consumers pass the real registry from `RuntimeCatalogs.profiles`:
  registry_snapshot, GUI `entities.py`, and the verifier (`check_attribute_schema` gained a
  `profile_registry` param, threaded from `artifact_verifier`), so bound-profile attributes
  and conflicts flow through the snapshot AND the E043 verifier path once profiles ship.
- Existing scalar callers/tests updated to lists (`""`→`[]`, `"slug"`→`["slug"]`).
- Tests: `TestNamedProfileResolution` in test_effective_attribute_schema.py (order,
  parent-inheritance regression, Class-B conflict, undefined-name-unresolved). ruff + zuban clean.

### WU-P4 — Conflict classification (needs P3)
- [x] Classify each conflict as Class A (structural) or Class B (scoped) per
      PLAN §4.
- [x] Identical redefinition composes silently; only incompatible `type`
      redefinition conflicts (PLAN §3 P3 — today's semantic, keep it).
- [x] Tests: identical redefinition across two profiles is NOT a conflict;
      differing types IS; each class is assigned correctly.

#### WU-P4 PROGRESS (2026-07-21)
- `ConflictClass` (`structural`|`scoped`) + `ProfileConflict` + pure
  `classify_profile_conflicts(bound_names, effective_registry, merge_conflicts)` in
  `profile_registry.py`: an undefined binding → structural (Class A, reported first — it
  subsumes any scoped conflict because the schema is then indeterminable); a merge type
  conflict → scoped (Class B). Identical redefinition never produces a merge conflict, so it
  never appears. The `registry` argument must be the EFFECTIVE registry (shipped ∪ repo).
- This is the pure classification PRIMITIVE only; Q1 (startup Class A) and Q2 (Class B
  quarantine set) are its consumers. No consumer wired yet — compute_effective still returns
  the raw merge list for the existing E043 path; Q1/Q2 will assemble inputs and call this.
- Tests: 5 added to test_profile_registry.py (undefined→structural, defined→none,
  identical→none, type→scoped, both-in-one-pass with structural-first). ruff + zuban clean.

## Stream Q — Failure semantics

### WU-Q1 — Class A startup validation (needs P4)
- [~] **Extend `startup_validation.py`** — DEVIATION (recorded): `_schema_inventory_findings`
      does NOT distinguish engagement vs enterprise (`validate_repo_compatibility` raises on
      ANY error, aborting both tiers), so it is the WRONG host for a tier-split posture. The
      true tier-split template is `_group_registry_startup.py`. New sibling
      `_profile_registry_startup.py::validate_profile_registries` mirrors it exactly — not a
      "parallel validator" but the same posture the plan's §2 premise mislocated.
- [x] Validate attached repos before the index build (in `_initialise_repo`, right after
      `repair_group_registries`, with both roots in scope).
- [x] Engagement → `sys.exit(1)` with file/reason/fix; enterprise → `logger.warning`, continue.
- [x] Only the two attached roots are read — never a filesystem scan.
- [x] Tests: malformed engagement registry aborts; same in enterprise does not; undefined
      binding aborts engagement; unattached repo never read.

### WU-Q2 — Class B quarantine set (needs P4)
- [x] `compute_quarantine_set(repo_root, catalogs)` maps every quarantined
      (entity-type, specialization) pair → its scoped conflicts; per-pair
      `pair_quarantine_conflicts` computes on demand (never persisted — self-clears).
- [x] The effective schema for a quarantined pair still resolves to the unambiguous
      fragment set (merge drops the conflicting redefinition; reads continue).
- [x] Tests: confined to the affected pair; a sibling specialization is unaffected; the
      clean pair resolves.

### WU-Q3 — Write-boundary gate (needs Q2) — LOAD-BEARING
- [x] `assert_not_quarantined` raises the typed `ProfileQuarantineError` (a `ValueError` →
      HTTP 400 / MCP tool error) naming the field and conflicting types.
- [x] **Gap closed**: the gate sits in `create_entity` + `edit_entity` — the single write
      package REST and MCP both funnel through — and resolves via
      `compute_effective_attribute_schema`, so the write path now sees the specialization's
      profile contributions (not just the base schema). (CLI has no entity write path.)
- [x] Tests: rejection through the shared choke point (create + edit end-to-end); a
      non-quarantined pair writes normally.

#### STREAM Q PROGRESS (2026-07-21)
- SCOPE of the gate: uses the module `RuntimeCatalogs.specializations` (∪ repo-level
  *profiles* via `_repo_profile_registry`). It does NOT merge repo-level *specializations* —
  loading them per meta-ontology alias created ambiguous duplicate keys that
  `compute_effective`'s alias-less `.get` rejects. Repo-defined specialization bindings are
  thus not gated yet; shipped specializations + repo/shipped profiles are. Documented
  deviation from the mapping's "effective specialization catalog" idea.
- Every merge conflict IS Class B (scoped): Class A (undefined binding) contributes no
  fragment and aborts engagement startup (Q1), so it never reaches a running write boundary.
- Files: `src/application/profile_quarantine.py` (pair/set + `ProfileQuarantineError` +
  `assert_not_quarantined`); gate wired into `entity.py`/`entity_edit.py` (edit gates on the
  post-merge specialization); `src/infrastructure/backend/_profile_registry_startup.py` +
  wired into `arch_backend._initialise_repo`; domain helpers `ProfileRegistry.overlay` +
  `unresolved_profile_bindings`. Tests: application (5), startup (5), write-gate e2e (3),
  domain (overlay/bindings). ruff + zuban clean.
- RESTART-GATED: the Q1 startup abort and the Q3 gate are new backend code — inert until the
  next `arch-backend` restart; the logic is fully covered in-process.

### WU-Q4 — Stream Q boundary
- [x] Full backend gates green (see the commit's gate line). No entity is written against an
      ambiguous schema through create or edit (REST/MCP share that path).
- [ ] ADR for the failure-semantics design (owner-requested) — authored with Stream T
      self-model (task tracked).

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
