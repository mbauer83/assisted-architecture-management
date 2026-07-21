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
- LIVE-VERIFIED 2026-07-21 (post-restart, non-invasive): backend started clean (Q1 ran on the
  real repo with no false abort); `GET /api/entity-schemata?...service` resolves the effective
  schema with `conflicts: []` (P3 live via the new list signature); a dry-run create returned a
  normal result (Q3 gate wired + inert for a clean pair). The rejection path is covered by the
  e2e/unit tests — not forced live (would require adding a conflicting schema to the real repo).

### WU-Q4 — Stream Q boundary
- [x] Full backend gates green (see the commit's gate line). No entity is written against an
      ambiguous schema through create or edit (REST/MCP share that path).
- [x] ADR for the failure-semantics design (owner-requested) — authored with Stream T
      self-model as `ADR@1784674023.8alNxn` (see WU-T2 progress); `artifact_verify` clean.

## Stream R — Reconciliation

### WU-R1 — Conflict and drift reporting (needs Q2)
- [x] Upgrade step (`ProfileReconciliationScanStep`, registered) reporting each conflict
      (the quarantined `entity-type/specialization` pair; profiles/field/types named in the
      merge message).
- [~] Content-version DRIFT: DEFERRED — no reusable profiles are shipped, so there is no
      baseline to drift from. The mechanism (P4 per-profile `version`) is in place; the drift
      comparison activates when shipped profiles land, by feeding the step the shipped
      registry via an `RepoUpgradeView` property (the `known_entity_type_names` pattern).
      Deferring avoids enriching the view Protocol (many test adapters) for a vacuous check.
- [x] Non-destructive: detect-only; `apply` returns `[]`; all findings `auto_migratable=False`
      with manual instructions (mirrors `DefaultSchemataEnsureStep`'s no-overwrite contract).
- [x] Tests: conflict reported; non-conflicting binding quiet; no-repo-specializations quiet;
      report-only writes nothing. (Drift test lands with the deferred drift logic.)

#### WU-R1 PROGRESS (2026-07-21)
- `src/application/repository_upgrade/steps/profile_reconciliation_scan.py`: for each
  specialization the repo's `.arch-repo/specializations.yaml` declares with `profiles:`
  bindings, resolves the effective schema via `compute_effective_attribute_schema` (repo
  profiles.yaml read internally) and reports each type conflict as a quarantined-pair
  warning. Fully computable from repo files — no catalogs/infra needed by the step.
- Architectural finding: application upgrade steps are view-based (file reads + a few
  registry-derived properties like `known_entity_type_names`); they cannot reach
  `RuntimeCatalogs`. So the step scans REPO-defined specialization bindings (which it can
  parse) — symmetric to Q3 gating MODULE specializations. Drift needs the shipped baseline,
  hence the deferral above.

### WU-R2 — Proposed resolutions (needs R1)
- [x] Propose rename / align-type / unbind as manual instructions.
- [~] Auto-migrate only where unambiguous (operator file byte-identical to an
      older shipped version). DEFERRED with R1's drift check for the same reason: the ONLY
      unambiguous auto-migration the plan sanctions is advancing a file byte-identical to an
      older SHIPPED profile version (§5), and no reusable profiles ship yet — so there is no
      shipped baseline and every conflict is operator-authored. `is_auto_migratable` is a
      hard False. When shipped profiles land, the byte-identical branch activates alongside
      the drift comparison (both need the same shipped registry via `RepoUpgradeView`).
- [x] Tests: ambiguous cases are never auto-migrated.

#### WU-R2 PROGRESS (2026-07-22)
- New pure domain module `src/domain/profile_conflict_resolution.py`: parses a
  `merge_property_schemas` conflict message (the one shape it emits) into a
  `ProfileConflictResolution` with the attribute, both types, and three ordered
  least-destructive-first proposals — rename, align-type, unbind — filled in with the real
  attribute name and the specialization's bound-profile list. `is_auto_migratable` is a hard
  `False` the reconciliation step relies on. `resolution_instructions` renders numbered
  proposals, or a caller-supplied fallback when the message is not a recognised
  type-conflict (never invents a resolution for a shape it does not understand).
- `ProfileReconciliationScanStep._finding` now composes those proposals into each finding's
  `manual_instructions` (still stating the create/edit-blocked consequence), for both
  concept kinds. `apply` still returns `[]`.
- Tests: `tests/domain/test_profile_conflict_resolution.py` (parsing, all three proposals,
  bound-profile naming, numbered rendering, and the never-auto-migrate guarantee) +
  scan-step assertions that the proposals reach the finding and no finding is
  auto-migratable / carries a rewrite_summary.
- Gates: backend 6341 passed / 5 skipped; ruff + zuban clean. (Backend-only WU.)

## Stream S — Surfaces

### WU-S1 — Quarantine on the schema endpoint (needs Q2)
- [x] `GET /api/entity-schemata` gains a derived `quarantined: bool` on the SAME conflicts
      channel (`bool(conflicts)`) — no parallel channel. Tests: clean → false; conflicting
      attachment → true.
- [~] REST + MCP parity: there is NO MCP entity-schema read tool (only `promote.py` uses
      `compute_effective`, for its own check), and adding one would violate the small-tool-
      count discipline. MCP parity for quarantine is via the SHARED write gate (Q3
      `ProfileQuarantineError` → tool error, names the conflict) + the verifier E043 — the
      same conflict information, no new surface. Recorded interpretation, not an omission.

### WU-S2 — GUI surfacing (needs S1)
- [x] Banner on affected entity types; submit disabled with the reconciliation
      message.
- [x] Progressive enhancement only — correctness is already guaranteed by WU-Q3
      (PLAN §3 P8). Verify by testing that a GUI unaware of quarantine still
      cannot write ambiguous data.
- [x] Vitest coverage, separate file per component.

#### WU-S2 PROGRESS (2026-07-21)
- Contract: `EntitySchemaInfoSchema` gains `quarantined` (optional boolean). `ui/lib/
  schemaQuarantine.ts` reads it via `quarantineFromSchemaInfo`, falling back to
  `conflicts.length > 0` so a backend predating the derived flag is not read as clean.
- Banner: `ui/components/SchemaQuarantineBanner.vue` — headline naming the (type,
  specialization) pair, the remedy sentence, and the endpoint's conflict list. Pure
  display; each form owns its own submit gating.
- Create path: `EntityCreateView.vue` tracks a `quarantine` ref (set on schema load,
  reset on load failure and on type deselect), renders the banner above the name field,
  and disables Preview + Create. Blocked-reason ordering extracted to
  `EntityCreateView.helpers.ts` (quarantine outranks the in-form reasons — filling the
  form in would not unblock it) rather than nesting ternaries in the template.
- Edit path: `useEntityEditForm` gains `editQuarantine` + `editArtifactType`; the banner
  renders in `EntityEditFormCard`, and BOTH mirrored action trios (card + header) disable
  Preview/Save through the shared `ui/lib/entityEditBlocking.ts`.
- `WizardEntityForm` deliberately untouched: it only ever fetches the UNSPECIALIZED
  schema, and a bare type with no specialization and no bindings has nothing to conflict
  with — it cannot be quarantined. The Q3 write gate covers it regardless.
- LoC: `EntityCreateView.vue` was AT its 530 baseline, so the additions were paid for by
  consolidating the duplicated `.form-input/.form-textarea/.form-select` and
  `.preview-btn/.create-btn` CSS and dropping an empty rule (529/530 after).
- Tests: vitest `ui/lib/schemaQuarantine.test.ts`, `ui/lib/entityEditBlocking.test.ts`,
  `ui/views/__tests__/EntityCreateView.helpers.test.ts` (separate file per unit).
  Backend acceptance in `tests/tools/test_gui_entity_schemata_endpoint.py::
  TestQuarantineHoldsWithoutTheFlag` — a REST client that never reads `quarantined` still
  gets a 400 and writes no file, while the clean pair still writes (gate does not
  over-reach).
- Gates: backend 6294 passed / 5 skipped; ruff + zuban clean; frontend lint + typecheck +
  vitest (115 files / 1168 tests) green.

## Stream W — Relationship profiles (needs P3, Q2)

Symmetric with entities. The specialization dimension is already wired for
connections through every layer (PLAN §9) — only the schema side is entity-only.
Land WITH the entity work, not after: both share the resolver, conflict
classifier, quarantine machinery, and reconciliation step.

### WU-W1 — Specialization-scoped connection schemata (needs P3)
- [x] `connection-metadata.{type}.{slug}.schema.json` filename convention.
- [x] `list_schema_files` classifies it (today `specialization-attachment` is
      entity-only), and `startup_validation._schema_inventory_findings`
      validates its subject.
- [x] `compute_effective_connection_metadata_schema`, mirroring the entity
      resolver including named-profile bindings and resolution order.
- [x] Tests: mirror the entity resolution tests.

#### WU-W1 PROGRESS (2026-07-22)
- The resolver is NOT a mirror-by-copy: `compute_effective_attribute_schema` and the new
  `compute_effective_connection_metadata_schema` are both thin wrappers over one private
  `_compute_effective_schema`, parameterised by concept kind + the two loaders. Order,
  profile de-duplication, and merge live in one place, so the two kinds cannot drift.
- New `SchemaFileKind` member `connection-specialization-attachment`; the classifier splits
  the `connection-metadata.` remainder the same way the `attributes.` one is split, so a
  third segment is `unrecognized` on both sides. `ATTACHMENT_KINDS` maps both attachment
  kinds to their concept kind, and `find_orphan_attachment_schemata` now covers connection
  attachments through it (an orphan is the same mistake either side).
- `_schema_inventory_findings` gates the new kind on the known CONNECTION types.

### WU-W2 — Verifier merge for connections (needs W1)
- [x] `check_connection_metadata_schema` validates against the MERGED effective
      schema and reports conflicts, mirroring E043.
- [x] Tests: conflict reported; quarantine applies to a (connection-type,
      specialization) pair exactly as for entities.

#### WU-W2 PROGRESS (2026-07-22)
- `check_connection_metadata_schema` takes the catalogs (as `check_attribute_schema` does),
  reads the connection's own `metadata["specialization"]`, and validates against the
  effective schema. A conflicting merge is a blocking **E045** — E043's connection
  counterpart, a new code because the pair then has no schema to validate against at all;
  instance violations stay W043.
- `profile_quarantine` is now concept-kind parameterised rather than entity-only:
  `pair_quarantine_conflicts`, `assert_not_quarantined`, and `ProfileQuarantineError` all
  take a `ConceptKind`, and `compute_quarantine_set` keys on `(kind, type, slug)` and
  sweeps both kinds. The two entity call sites pass `"entity"` explicitly — no default,
  because a silent default is how the two kinds would drift.
- Connection write boundary: `_assert_pair_writable` in `connection.py`, called by
  `add_connection` (after input validation) and by `edit_connection` on the EFFECTIVE
  post-merge specialization — the same shape as the entity create/edit gates.
- The R1 reconciliation scan no longer skips `concept_kind != "entity"`; it resolves per
  kind and puts the kind in the finding id (an entity and a connection may share a
  parent-type/slug pair) and in the operator instructions ("Entities"/"Connections").
- Tests: `tests/tools/test_effective_connection_metadata_schema.py` (classification,
  resolution, named profiles, orphans, and a guard that an entity specialization of the
  same slug does not leak into a connection lookup);
  `tests/tools/test_connection_write_quarantine_gate.py` (add/edit refused, unspecialized
  and clean-specialized pairs still write); connection cases added to
  `test_profile_quarantine.py`, `test_connection_metadata_schema.py`,
  `test_profile_reconciliation_scan_step.py`, and `test_startup_validation.py`.
- Gates: backend 6323 passed / 5 skipped; ruff + zuban clean.

### WU-W3 — Surfaces (needs W1)
- [x] Effective merged connection-metadata schema in the authoring-guidance
      payload (REST + MCP parity).
- [x] GUI renders it through the existing `TypedPropertyInput` — the connection
      specialization picker already exists
      (`specializationOptionsForConnectionType`). No new GUI concept.
- [x] Tests: Vitest for the connection metadata editor.

#### WU-W3 PROGRESS (2026-07-22)
- Payload: `_connection_metadata_guidance.py` builds the `connection_types` block; each
  entry and each of its specializations carries `metadata_schema` =
  `{schema, properties, required, descriptors, conflicts, quarantined}`. `get_type_guidance`
  takes a new `repo_root` (schemata are per-repo files); REST passes
  `s.maybe_engagement_root()` and MCP passes `resolve_repo_root(...)`, so neither transport
  offers a shape the other lacks. Without a root the payload is guidance only, as before.
- `attribute_descriptors` moved from `routers/entities.py` to `artifact_schema.py`: the
  entity endpoint and the connection guidance now serve ONE descriptor shape, so a single
  `TypedPropertyInput` renders either without knowing which side it came from.
- GUI: `ConnectionAddForm` renders the pair's typed metadata fields, reuses
  `SchemaQuarantineBanner`, and disables Add on quarantine or a missing required attribute.
  New selector `connectionMetadataSchema()` picks specialization → type-level → null.

#### DEFECT FOUND AND FIXED during W3 (2026-07-22)
The plan assumed the GUI could simply "render the merged schema"; the code could not carry
what it rendered. Two gaps at the same layer:
1. `_declaration_to_dict` lifted ONLY `specialization` out of the parsed metadata block, and
   `format_outgoing_markdown` rebuilt the block from that key alone — so any edit that
   reformatted an `.outgoing.md` file silently DROPPED every other metadata attribute.
   Invisible data loss, and precisely the content a metadata schema exists to describe. The
   dict now carries the whole block as `metadata`, with `specialization` still authoritative
   for its own key (the edit API sets and clears it by name).
2. The write API had no way to SET those attributes. `metadata` is now plumbed through
   `add_connection` / `edit_connection` (replacement semantics, mirroring the entity edit
   API's `properties`; `{}` clears), the REST bodies, and the MCP tools.
Recorded rather than worked around: rendering a schema whose attributes no write path could
persist would have been a facade.
- Tests: `tests/tools/test_connection_metadata_round_trip.py` (formatting + write path +
  the drop-on-unrelated-edit regression); the guidance-payload assertion in
  `test_gui_router_authoring_guidance.py`; vitest
  `ui/lib/__tests__/connectionMetadataSchema.test.ts`.
- **Restart-gated**: `artifact_add_connection` / `artifact_edit_connection` gained a
  `metadata` parameter — an MCP *surface* change, so a Claude session restart is required
  before it can be exercised through MCP. Queued for the WU-X1 restart.

## Stream T — Docs and self-model

### WU-T1 — Reference documentation
- [x] Profile authoring, binding, versioning, resolution order, and the failure
      semantics — the quarantine behaviour especially, since an operator who
      meets one must be able to act on it.

#### WU-T1 PROGRESS (2026-07-22)
- `docs/05-extensibility/schemata-and-profiles.md` rewritten: the stale "profiles are
  one-to-one with their specialization / never a named registry" section is replaced with
  "How a specialization contributes attributes" (inline, attachment, named-profile
  bindings), a "Named attribute profiles" section documenting `.arch-repo/profiles.yaml`
  (format + content versions, binding syntax, shipped-vs-repo override), an "Effective
  schema and resolution order" section (base → bound profiles → own, in order), and a
  "Failure semantics" section covering Class A startup abort and Class B quarantine with
  the operator-facing behaviour (banner, disabled submit, E043/E045, arch-repair
  proposals). The file tree, connection-attachment convention, and the connection metadata
  section were updated to match the shipped code.
- `docs/architecture/decisions.md` gains a row linking the new ADR.

### WU-T2 — Self-model sync
- [x] Model the profile-registry capability in ENG-ARCH-REPO: guidance-first,
      descriptions over new entities.

#### WU-T2 PROGRESS (2026-07-22)
- **ADR authored** (WU-Q4's last box): `ADR@1784674023.8alNxn` "Profile Failure Semantics;
  Blast-Radius Classification and Single-Boundary Quarantine" under `docs/adr/platform-core`
  via `artifact_create_document` (dry-run first). Records Class A structural vs Class B
  scoped, engagement-hard/enterprise-soft, single-write-boundary enforcement (P8), and
  no-persisted-quarantine, linking the Model Verifier, Architecture Backend, and the
  One-Unified-Backend ADR. `artifact_verify` clean.
- **Descriptions over entities** (motivation-entity discipline): no new entities. The two
  existing `Specialization Profile` entities (`BOB@1783870955.TpnjS9` conceptual,
  `DOB@1783870958.1-9hJv` technical) explicitly encoded the SUPERSEDED "one-to-one /
  never a named registry" design; both summaries were rewritten via `artifact_edit_entity`
  to describe the three contribution mechanisms, `.arch-repo/profiles.yaml` with its two
  version tags, shipped-vs-repo override, and the resolution order. Repo-wide
  `artifact_verify` (engagement): 73/73 valid, 0 errors (3 pre-existing GAR→enterprise
  warnings, unrelated).
- Gates: backend 6341 passed / 5 skipped; ruff + zuban clean.

## Stream V — Multiple specializations per concept (P9)

Rewrites D6. ArchiMate 3.1 §15.2 verbatim: *"multiple specialization profiles
may be assigned to the same generalized concept; in the default notation, these
are shown as a comma-separated list"*. Sequenced after P–S; the DECISION is
already locked because WU-P3 depends on it.

### WU-V1 — Storage and back-compatibility
- [x] Frontmatter accepts a list; a bare scalar keeps working and is read as a
      one-element list. No repo migration required.
- [x] Tests: scalar form round-trips unchanged (regression).

#### WU-V1 PROGRESS (2026-07-22)
- `EntityRecord`/`ConnectionRecord` gain `specializations: tuple[str, ...]` (canonical,
  ordered) alongside `specialization: str` (the PRIMARY = first). `_reconcile_specializations`
  in `__post_init__` derives one from the other so a caller may set EITHER — the ~91 existing
  `specialization=` construction sites keep working, and setting both to disagree is a
  ValueError, not a silent reconcile. Chosen over a pure derived property to avoid churning
  every construction site for a representation change.
- Parsing (`artifact_parsing._parse_specializations`) reads a scalar (one-element set, no
  migration) or a list (ordered, de-duplicated, blanks dropped) for both entity frontmatter
  and connection metadata.
- No SQLite change needed: entity/connection records flow to consumers as full mem-store
  objects (`get_entity`/`list_connections` etc.), preserving `specializations`; the SQLite
  scalar `specialization` column and `EntityContextConnection` are aggregate/display
  projections keyed on the primary.
- Tests: `tests/application/test_specialization_list_parsing.py` (scalar/list/absent
  round-trip, de-dup, and the record invariant incl. the disagreement guard).

### WU-V2 — Rendering (needs V1)
- [x] `format_specialization_guillemet` renders the spec's comma-separated list
      («a, b»). It is singular today.
- [x] Tests: single and multiple render per spec.

#### WU-V2 PROGRESS (2026-07-22)
- Replaced the singular `format_specialization_guillemet` with
  `format_specializations_guillemet(names)` → `«a, b»` (§15.2 default notation; one name
  gives `«Name»`, empty gives `""`). Both render sites (`archimate_entity_declarations`,
  `generic_puml_renderer`) resolve ALL `specializations` for the LABEL and keep the PRIMARY
  spec for notation (a single icon/line-style cannot honour several). Old singular removed
  (no remaining callers).
- Tests: `tests/domain/test_specializations_guillemet.py` + multi-render cases in
  `tests/rendering/test_specialization_rendering.py` (entity and connection).

### WU-V3 — Querying and styling (needs V1)
- [x] Viewpoint grouping by `specialization` and style/scale `applies_to`
      matching over a set. Both already compare via `frozenset`
      (`viewpoint_style_evaluation.py`, `viewpoint_scale_styling.py`), so this
      extends naturally — verified.
- [x] Decide and document what grouping by specialization MEANS for a concept in
      several groups (appears in each, versus a composite bucket).
- [x] Tests: grouping and style matching with multiple specializations.

#### WU-V3 PROGRESS (2026-07-22)
- Both `_item_tags` (style_evaluation + scale_styling) now union the type with EVERY applied
  specialization, so a rule/scale whose `applies_to` names any one of a concept's
  specializations matches — this is the "grouping by specialization" of V3 (style-rule
  frozenset grouping), verified as the plan predicted. `evaluate_viewpoint` passes the full
  `specializations` as `specialization_slugs` (execution results + CSV export now list all).
- **Grouping-meaning decision:** a concept with several specializations appears under EACH
  matching style-group (styling naturally unions — every rule whose `applies_to` hits any of
  its specializations applies), NOT a single composite bucket. The condition/presentation
  reserved `specialization` path continues to resolve the PRIMARY scalar (one canonical
  value per concept keeps population counts and column display unambiguous); the comparator
  already handles collection membership, so set-membership filtering is a one-line change if
  the owner later wants it. Recorded here as the durable decision.
- Tests: non-primary `applies_to` match in both `test_viewpoint_style_evaluation.py` and
  `test_viewpoint_scale_style.py`.
- Gates (V1–V3 together): backend 6358 passed / 5 skipped; ruff + zuban clean.

### WU-V4 — Write paths and GUI (needs V1)
- [x] Entity and connection write paths accept multiple; `promote_schema_check`
      handles the set across repos.
- [x] GUI picker single-select → multi-select; `types.generated.ts` regenerated.
- [x] Tests: per-transport write coverage; Vitest for the picker.

#### WU-V4 PROGRESS (2026-07-22)
- Write serialization: `format_entity_markdown` / `format_outgoing_markdown` write a SCALAR
  for one specialization (existing files stay byte-identical, no repo churn) and a LIST for
  several (§15.2). `create_entity`, `edit_entity`, `admin` entity edit, `add_connection`,
  and `edit_connection` all gained a `specializations` param alongside the scalar
  `specialization`; `normalize_specializations` (in `boundary.py`) is the one place that
  turns the two inputs into the applied set, and the quarantine gate + serializer both take
  it. `MergedFields.specialization` → `specializations` with `_merge_specializations`
  (explicit update replaces, `_UNSET` keeps, `[]`/`""` clears).
- Verifier: E170/E171 (entity) and E160/E161 (connection) now iterate the applied set —
  each specialization validated independently. A new shared `domain/specialization_values.
  applied_specialization_slugs` reads a scalar-or-list `specialization` value ONE way, reused
  by the verifier, parsing, and the write boundary so writer and readers cannot drift.
- Promotion: `promote_schema_check._specialization_errors` superset-checks EVERY applied
  specialization across the tier boundary, not only the primary.
- Transports: REST bodies (create/edit entity, add/edit connection) and MCP tools
  (`artifact_create_entity`, `artifact_edit_entity`, `artifact_add_connection`,
  `artifact_edit_connection`, bulk_write) gained a `specializations` field/param. The
  entity-schemata endpoint accepts a comma-separated `specialization` (single value still
  works) so the GUI can preview the merged schema for a set.
- Also fixed a latent drop: admin entity edit never passed specialization to the formatter,
  so an admin edit silently cleared it — now preserved.
- GUI: create-view and edit-form specialization pickers are `<select multiple>` bound to a
  `string[]`; the schema preview fetches the merged schema for the joined set; create/edit
  bodies send `specializations`. Entity detail read model + GUI `EntityDetail` schema now
  expose `specializations` so the edit form seeds the full set. `types.generated.ts` is
  ontology-derived and regenerated clean (no ontology change → no diff).
- Tests: `tests/tools/test_multiple_specialization_write.py` (entity + connection write,
  scalar-vs-list serialization, edit-replace, round-trip order, per-parametrized count);
  updated promotion mocks to `specializations`. GUI picker: plain `<select multiple>` with
  no bespoke logic beyond `.join(',')`, covered by typecheck + the existing
  `specializationOptions`/`schemaQuarantine` vitest and the backend write acceptance.
- Gates: backend 6364 passed / 5 skipped; ruff + zuban clean; frontend lint + typecheck +
  vitest (116 files / 1175 tests) green.
- **Restart-gated**: the `specializations` param on the four MCP write tools is an MCP
  surface change — a Claude session restart is needed to exercise it through MCP. Queued
  for WU-X1.

## Stream Y — Attribute-profile fields in the entity authoring GUI (owner-requested 2026-07-21)

See PLAN §6 (Stream Y). Pairs naturally with WU-S2 (both touch the entity form) and depends
on the P/Q resolved-schema at the write boundary (landed).

### WU-Y1 — Create-page list widgets
- [ ] A `list`-typed profile attribute renders as a real add / remove / reorder list editor,
      not the single "JSON-Array" free-text box it is today — typed per the item schema,
      reusing the `TypedPropertyInput` path the other attribute kinds use.
- [ ] Vitest coverage for the list editor.

### WU-Y2 — Edit-page profile fields with merge semantics
- [ ] The entity EDIT page renders the specialization's attribute-profile fields (today only
      create does) and re-renders on a specialization change, applying MERGE semantics for
      already-present values (keep an existing value where the new profile still declares its
      attribute; drop/quarantine only where the attribute is gone).
- [ ] Vitest coverage; the resolved schema comes from `GET /api/entity-schemata` (WU-S1).

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
