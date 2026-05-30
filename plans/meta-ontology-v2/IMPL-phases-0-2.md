# Implementation Guide — Phases 0–2 (non-deferred work)

Companion to `PLAN-meta-ontology-v2.md`. This is the pick-up-and-build guide for the work
that is **not** deferred: removing implicit model mutation, making bindings the single
correspondence mechanism, and adding module-declared bindings + id-only derivations. It
names concrete files, functions, data shapes, and verification steps so a later session
can start without re-discovery.

## Project conventions (apply throughout)

- All model/diagram authoring goes **through the tools/write path**, never by editing
  artifact files by hand. If output is wrong, fix the tool, not the artifact.
- Naming uses the `arch` prefix (not `sdlc`).
- Python files: 250-line soft / 350-line hard limit. Split modules before they grow past it.
- Tests: one file per component/use-case, not an omnibus file.
- Deps: `uv sync --all-groups`. Type-check: `zuban check`. Tests: `uv run pytest tests/`.
- After ANY ontology/type-shape change regenerate the TS contract:
  `uv run tools/generate_types.py` (a pre-commit hook enforces `types.generated.ts` is in
  sync). The GUI editors and REST contracts must move in lockstep.
- Keep the MCP tool count small and descriptions short; add arguments/modes to existing
  tools rather than new tools (see main plan, Realistic Engagement Modes).

---

## Phase 0 — Groundwork: unify `classes`, remove implicit mutation, migrate repos

**Goal:** the type vocabulary uses a single `classes` membership field; no diagram write
creates or changes model content; `c4-contains` model connections cease to exist; legacy
`entity_id` / `_scope_entity_id` become bindings. Do §0.0 first — it is independent of
§0.1/§0.2 and leaves the tree clean before any binding work begins.

### 0.0 Unify `classes` on entity + connection types (do this first — mechanical codemod)

Today entity types carry class membership in `EntityTypeInfo.element_classes` and
connection types in `ConnectionTypeInfo.classifications`. Unify the **membership** field
name to `classes` for both (main plan, "Types, Classes, and Classes of Connections"). The
top-level `element_classes:` **declaration** block (the class vocabulary, at YAML
column 0) is intentionally left unchanged — only per-type membership fields are renamed, so
"declare the element classes; this type's `classes` are […]" stays readable.

This is many files but purely mechanical. The two design insights that make it safe as
regex replacement: **indentation** separates the per-type membership field (always indented
under a type) from the column-0 declaration block; **word boundaries** protect the concept
names `ElementClassName`, `ElementClassInfo`, and the registry method `all_element_classes`
(none has a `.`/`=` adjacent, and `_` suppresses `\b` inside `all_element_classes`).

Ordered recipe — run each group, then `git diff` + `rg` to validate before the next:

1. **Dataclass fields (manual, 3 lines).** In `src/domain/ontology_types.py`:
   `EntityTypeInfo.element_classes` → `classes`; `ConnectionTypeInfo.classifications` →
   `classes`. In `src/domain/ontology_protocol.py`:
   `DiagramOwnEntityTypeUiConfig.element_classes` → `classes`.
2. **YAML membership keys (indented only).** Across `src/ontologies/**/*.yaml` and
   `src/diagram_types/**/{ontology,config}.yaml`:
   `s/^(\s+)element_classes:/\1classes:/` and `s/^(\s+)classifications:/\1classes:/`.
   The leading `\s+` is load-bearing: it excludes the column-0 declaration block.
3. **Python attribute + kwarg access (word-boundaried).** Across `src/`:
   `s/\.element_classes\b/.classes/g`, `s/\belement_classes=/classes=/g`,
   `s/\.classifications\b/.classes/g`, `s/\bclassifications=/classes=/g`.
4. **Connection accessor rename (symmetry).** `connection_types_with_classification` →
   `connection_types_with_class` (the `OntologyModule` Protocol in `ontology_protocol.py`,
   every module implementation, and all call sites); its `classification` parameter → `cls`.
5. **Loaders.** Confirm `src/domain/diagram_ontology_loader.py` (`_parse_entity_types`,
   `_parse_connection_types`) and `src/ontologies/archimate_next/_loader.py` read the new
   `classes` key.
6. **Docs.** Update `src/ontologies/README.md` and `src/diagram_types/README.md`.

Validation gates (all must pass before §0.1):

- `rg -n '\belement_classes\b' src` returns only the column-0 declaration blocks and the
  `ElementClass*` / `all_element_classes` concept names — no per-type membership or
  attribute hits.
- `rg -n 'classifications|with_classification' src` returns nothing.
- `zuban check` clean; `uv run pytest tests/` green (protocol-compliance tests exercise
  every module's `classes`); `uv run tools/generate_types.py` regenerated and committed.

### 0.1 Delete the scope-connection mechanism

- Delete `apply_scope_connections` — `src/infrastructure/write/artifact_write/scope_connections.py`.
- Delete the `build_scope_connections` override in `src/diagram_types/_c4_type.py` (~L264)
  and the default + protocol method `build_scope_connections` in
  `src/domain/ontology_protocol.py` (DiagramTypeBase ~L372 and the `DiagramTypeModule`
  Protocol ~L275). The `c4:` config block's `internal_entity_types` is no longer used for
  connection emission (containment becomes derived — see SPEC-phase-3 §2.2).
- Remove call sites: `src/infrastructure/mcp/artifact_mcp/write/diagram.py` (~L145–159),
  `src/infrastructure/mcp/artifact_mcp/edit_tools.py`, and
  `src/infrastructure/gui/routers/_diagram_write.py` (two call sites).
- The `c4-contains` connection type definition (`_c4_type.py` own_connection_types) is
  removed as a *model* connection type. (Containment is recomputed at projection time in
  Phase 3; if a visual-only nesting type is needed before then, it is diagram-local.)

### 0.2 One-time migration tool

New script `tools/migrate_diagrams_to_bindings.py` (run against engagement + enterprise
repos, including `engagements/ENG-ARCH-REPO/`):

1. For each diagram artifact, read `diagram-entities` items: for each item with `entity_id`,
   emit a top-level `represents` binding `{subject: {kind: entity, id: item.id},
   correspondence_kind: represents, target: {entity_id}}`; drop the inline `entity_id`. For
   `_scope_entity_id`, emit a diagram-level `scoped-by` binding `{subject: {kind: diagram},
   correspondence_kind: scoped-by, target: {entity_id}}` and drop the raw key.
2. Find and **report then delete** model connections of type `c4-contains`. Print every
   deletion (id, source, target); never delete silently.
3. Re-run the verifier; abort the migration if any diagram references a missing diagram
   element or model target.

Output a summary (diagrams migrated, bindings created, connections deleted). This is a
one-shot tool; it does not need to be reversible.

---

## Phase 1 — Bindings as the single correspondence mechanism

(The `classes` unification that was groundwork for this phase is now Phase 0 §0.0.)

### 1.1 Binding data model + schema

- New `src/domain/bindings.py`: a frozen `Binding` dataclass —
  `id: str`, `subject: BindingSubject`, `correspondence_kind: str`, `target: Target`,
  optional `derived_from: str | None`, optional `visual_role: str | None`.
  - `BindingSubject` = `{kind: Literal["entity","connection","diagram"], id: str | None}`
    (`id` is `None` only when `kind == "diagram"`).
  - `Target` is a tagged union over `{entity_id} | {connection_id} | {connection_ids:[...]}
    | {diagram_local: {diagram_id?: str, element_id: str}} | {connection_path: [{id,
    reversed}]}` (the path variant validated only in Phase 3).
  - **No** `sync_policy` / `derivation_basis` fields (deferred — main plan, "Binding
    Semantics"). **No** `query_result` target — query results are proposal-only, never
    persisted.
- Top-level `bindings:` JSON-schema fragment, generated next to the diagram-entities schema
  in `src/domain/diagram_entities_schema.py` (which currently injects the per-item
  `entity_id`, ~L48–59 — that injection is removed here).

### 1.2 Nested-shorthand normalization

- New `src/application/modeling/binding_normalize.py`: `normalize_bindings(diagram_entities,
  bindings) -> list[Binding]`. Reads any nested `binding:` on a diagram-entities item,
  rewrites it to a top-level `Binding` with a generated stable `id`, validates it is not
  ambiguous (nested shorthand only expresses single-element `represents`/`scoped-by`/
  `traces-to`/`refines` to one target — reject connection-path or multi-target shorthand),
  and merges with explicit top-level `bindings`. Persisted output is always top-level.

### 1.3 Write + parse paths

- `src/application/modeling/artifact_write_formatting.py` `format_diagram_puml` (~L158–211):
  add `bindings` to the ordered frontmatter keys; write normalized bindings.
- `src/infrastructure/write/artifact_write/diagram.py` `create_diagram` and
  `diagram_edit.py` `edit_diagram` (~L36–172): accept a `bindings` argument and nested
  shorthand; call `normalize_bindings`; persist.
- `src/infrastructure/write/artifact_write/parse_existing.py` `parse_diagram_file`
  (~L98–111): surface a typed `bindings` list alongside the raw frontmatter.

### 1.4 Verifier rules

Add to `src/application/verification/artifact_verifier_rules.py`, beside
`_check_entity_ids_used` (~L238) / `_check_connection_ids_used` (~L291), a `_check_bindings`
implementing the rules in the main plan's "Identity, Integrity, and Verifier Rules":
`subject` resolves (element subject → live element of that kind; `kind: diagram` → no id),
`target` resolves (reuse the existing entity/connection-id checks for scope; `diagram_local`
→ live element), ≤1 `represents` per element subject, ≤1 diagram-level `scoped-by` per
diagram, ≤1 `represents` occurrence per target per diagram unless the module declares
`visual_roles` (then distinct `visual_role` labels), admissible `correspondence_kind`
(needs Phase 2's `allowed_bindings`; until then accept the core five), `derived_from`
resolves (Phase 2). Cascade: deleting a diagram
element drops its bindings — enforce in the diagram-edit/delete path and assert no dangling
bindings here.

### 1.5 Rewire renderers + `collect_references`

The renderer must learn an element's model target from its `represents` binding instead of
the deleted inline `entity_id`:

- `src/diagram_types/_c4_resolve.py` `_items_from_diagram_entities` (~L244–268): resolve
  each item's model entity from the represents-binding map (pass bindings into resolution).
- `src/diagram_types/c4_renderer.py` `collect_references` (~L130–146): derive
  `entity_ids` / `connection_ids` from `represents` bindings.
- `src/infrastructure/write/artifact_write/diagram_references.py` (~L13–44): the
  renderer-references path now reads bindings; the PUML-alias inference path is unchanged.
- `src/diagram_types/activity/renderer.py`: swimlane→model mapping (was
  `permitted_mappings` via `entity_id`) now reads represents bindings.
- Regenerate `types.generated.ts`; update GUI binding display.

### Phase 1 done-when

`uv run pytest tests/` green (new tests: binding schema, normalization, each verifier rule,
renderer-reads-binding); `zuban check` clean; `tools/generate_types.py` produces no diff;
migrated self-model (`ENG-ARCH-REPO`) verifies.

---

## Phase 2 — Module-declared bindings + id-only derivations

### 2.1 `allowed_bindings` in diagram modules

Extend diagram `ontology.yaml` with an `allowed_bindings` block (main plan, "Connection
Bindings" example) for both entity and connection diagram types: `target_*_types`,
`target_*_classes`, `correspondence_kinds`, `target_forms`, and a **required**
`default_correspondence_kind` (must be a member of `correspondence_kinds` — machine-checked
at load). Parse in `src/domain/diagram_ontology_loader.py` into a new
`AllowedBindingsSpec`; expose via the diagram-type module and through
`artifact_authoring_guidance`. This is what lets the agent omit `correspondence_kind` and
take the module default.

### 2.2 `view_derivations` frontmatter

Add the `view_derivations:` block (main plan, "Derived Views") with schema validation:
`id`, `strategy`, `strategy_version`, `source_model_snapshot` (`repo_scope`, root ids),
`parameters` (with `pre_filters`), `selection` (typed `included_*` / `excluded_*` fields),
`generated_at`. Validate: strategy registered, version matches, all `pre_filters` supported
by that strategy (unsupported ⇒ error, not ignored).

### 2.3 Strategy registry + three id-only strategies

New `src/application/derivation/` package: a `Strategy` protocol (`signature`, `version`,
`supported_filters`, `derive(model_query, params) -> CandidateSet`) and a registry. Implement
the three that need no path identity, reading via the artifact index
(`src/infrastructure/artifact_index/` query helpers, e.g. `connection_ids_for`,
`connection_ids_by_types_for_entity_set`):

- `explicit-selection/v1` — candidate set = supplied `entity_ids` (+ optional
  `connection_ids`) + required helper entities (e.g. junctions). Projects to `represents`.
- `local-neighborhood/v1` — bounded BFS from `root_entity_ids` to `max_hops` with
  type/class/direction filters. Projects reached entities/connections to `represents`.
- `incident-connections/v1` — connections incident to `entity_ids` (+ endpoint entities),
  edge incidence only (no recursion). Projects incident connections as candidate edges.

`abstracts` in this phase targets an explicit `connection_ids` **set** (not a path); set
refresh is a membership diff. (`path-projection`, `scope-projection`, and path targets are
Phase 3 — see SPEC-phase-3.)

### 2.4 Refresh / diff + proposals

- Refresh runs on the read/query surface. Add a `refresh-derivation` mode to
  `artifact_edit_diagram`: recompute the strategy, diff candidates against the stored
  snapshot + selection, and return a **self-contained diff + `base_revision`** (the
  diagram's content hash). Apply via the `apply-diff` mode, which echoes the (optionally
  trimmed) diff back; the server applies it only if the diagram's current revision still
  equals `base_revision`, else returns a stale-diff conflict (the precise stateless
  concurrency rule is in the main plan's tool-surface mapping). Conflict rules per the main
  plan ("Conflict prevention and resolution"): manual beats refresh; never silently change
  a manually altered binding/label/type.
- `propose-bindings` mode + enrich existing search/traversal/guidance to return binding
  proposals **without** persisting them.

### Phase 2 done-when

Tests: `allowed_bindings` load + default-kind validation; `view_derivations` schema +
unsupported-filter rejection; each strategy's candidate set on a fixture; refresh
idempotence (unchanged model ⇒ empty diff) and selection monotonicity (these are the F4
property tests from `FORMALIZATION.md`); manual-beats-refresh conflict. `zuban check` clean;
TS regenerated.
