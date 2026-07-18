# Improvement Proposals — Viewpoint Usability Stress Test (RUN 2607171252)

Derived from `REPORT-viewpoint-usability-stress-test.md` and the evidence in
`test-results/usability/2607171252/`. Grounded in the architecture-modelling skill's
principles and the repository's authoring guidance (`artifact_authoring_guidance`,
motivation domain). Each proposal is self-contained: evaluation (evidence), judgement,
applied principles, options considered, recommendation, and implementation — so it can
be assessed and implemented independently.

Two parts: **A. Product** (features / UI / UX / workflows) and **B. Self-model**
(changes to ENG-ARCH-REPO content). Finding IDs (F*) and persona/probe evidence refer
to the report and run artifacts.

---

## Part A — Product proposals

### P-01 Truthful query summaries for traversal semantics (F1) — Priority: High, quick win

- **Evaluation.** The impact/dependency viewpoints traverse derived relationships with
  `max_hops: 4`; executed results contain derived edges with `hops` 2 and 4
  (`probe-PG3-dependents-gui.json`, `probe-PL1-deps-store.json`). The generated
  summary above every result says "(up to 1 steps)" — the bound of the *derived
  attribute* clause, not the traversal. Four independent persona contexts concluded a
  1-hop cap exists and wrote that limitation into tickets/design notes.
- **Judgement.** The one sentence users rely on to understand a result misstates its
  semantics; correct results are systematically misinterpreted. FMEA: S8–9 (literal
  anchor) / S7 (primary-result-correct reading) · O9 · D9 — severity anchor
  deliberately unresolved (owner adjudication); priority within the High band is
  ordered by technical dependency, not by this score.
- **Applied principles.** Match between system and the real world (Nielsen #2); "the
  summary must describe executed semantics, not schema internals"; least surprise.
- **Options.** (a) Render each query clause with its own bound and label the derived
  attribute separately ("Derived impact-distance (min hops)…" vs "includes entities
  connected up to 4 steps (derived)"); (b) suppress numeric bounds entirely; (c) fix
  only the number.
- **Recommendation.** (a). (b) hides load-bearing information; (c) leaves the clause
  conflation in place and will regress again.
- **Implementation.** In the query-summary builder (the component that emits
  "Derived impact-distance: … Entity selection: … Also include entities where …"),
  emit the `include_connected` clause with `traversal` mode and `max_hops` ("also
  include entities connected via derived relationships, up to 4 steps incoming"), and
  scope the derived-attribute sentence to its own definition. Add a unit test per
  clause type asserting the rendered numbers come from the right AST node; add a
  regression test for element-dependents' exact summary. Validation: PB1's ticket
  scenario re-run — the "direct ring only" caveat should no longer be derivable.
- **Companion decision (owner adjudication): hop-distance presentation must use
  MODELED hops.** When distance/color conveys number-of-hops, an indirectly
  connected entity must be colored/positioned by its witness-chain length (the
  derived edge's `relationship.hops` — 2, 4, …), never flattened to "distance 1"
  because the derived edge is one traversal step. Today the exploration legend shows
  "Anchor / 0 hops / 1 hop" for results that contain 2- and 4-hop entities — the
  ring coloring evidently counts derived edges, not modeled hops, even though every
  derived edge already carries its `hops` value. The legend must show the real ring
  set (Anchor / 1 / 2 / 4). Same units-collision as the summary text; cross-ref P-06
  (the witness chain that justifies each ring is one edge-selection away).
- **Distance-computation contract (review adjudication, R-05).** The number is
  anchor-relative and execution-scoped, so it CANNOT be the existing global
  `impact-distance` derived attribute reused as-is: define a projection-time
  `anchor_modeled_distance` per entity — 0 for the anchor, 1 for a direct modeled
  edge to the anchor, otherwise the minimum ordered-witness-chain length across all
  connecting derived edges; specify tie-breaking (minimum wins) and the no-witness
  case (attribute absent, node styled as unranked, never silently 0/1). Styling and
  the ring legend bind ONLY to this attribute. Validation: rings 0/1/2/4 render on
  the GUI-anchor fixture; a node reachable by both a 2-hop and a 4-hop witness ranks
  as 2. Also fold in here: fix the summary generator's grammar ("via an connection")
  while touching it (F31).

### P-02 Scope and query as switchable alternatives (F2) — Priority: High, substantial
*(Owner adjudication: scope and query were originally intended as ALTERNATIVE
selection mechanisms — simple vs. extended — and should be presented as switchable
alternatives, not merged; interacting filter layers were judged usability-hostile.)*

- **Evaluation.** Editing included entity types on the Scope tab rewrites
  `scope.entity_types` (also what the catalog row displays) but not
  `query.entity_criteria`. A fork saved with 5 declared types executes all 7
  (file-level proof during the run; probes `probe-PA-A1.json`,
  `probe-PI-A1-exec.json`). CORRECTED by review verification (R-03): a scope→query
  fallback ALREADY EXISTS — `definition_with_scope_query` in
  `src/application/viewpoints/scope_query.py` builds an implicit query from
  `scope.entity_types` when `definition.query is None` (test-covered). The GUI
  defeats it by always persisting a query object (empty criteria ⇒ "any entity",
  409/409, as PI-A1 showed). So the "alternatives" intent is half-implemented:
  scope-only definitions work; GUI-authored definitions never take that path, and
  dual-layer definitions can contradict themselves.
- **Judgement.** Persisted definitions become internally contradictory; the catalog
  asserts one thing, execution does another. S9 (repository state corrupted). The fix
  must implement the original alternative-modes intent, not fuse the two layers.
- **Applied principles.** Single ACTIVE representation of intent at any time;
  progressive complexity disclosure (simple mode → extended mode); error prevention.
- **Options.** (a) Explicit mode switch in the editor — "Simple selection (entity
  types)" vs. "Extended selection (query)"; exactly one mode is active and persisted
  (e.g. `selection_mode: scope | query`); the engine evaluates scope when mode=scope;
  switching modes offers a one-way conversion (scope → generated `type in [...]`
  query) with the inactive layer greyed and clearly labeled. (b) Merge (rejected by
  owner). (c) Validation-only backstop.
- **Recommendation.** (a), plus (c) as an INFORMATIONAL backstop (corrected in
  review round 2: an inactive-layer disagreement is the NORMAL state of a definition
  whose user chose one mode and kept the other layer for history/conversion, so it
  must never be an execution-blocking or save-blocking error). Catalog rows must
  display the ACTIVE selection's summary, never the inactive layer.
- **Implementation.** Definition schema: add persisted `selection_mode`. Engine:
  route mode=scope through the EXISTING `query_from_scope` fallback (don't build a
  second path); GUI stops persisting empty query objects. Editor: mode switch with
  one-way conversion affordance; inactive tab visibly disabled. Verifier: a
  W-class (informational) divergence code only — surfaced in the editor and in
  migration reports; execution and save always follow the active layer and are
  never blocked by the inactive one.
  **Migration (owner-adjudicated):** the deployment upgrade/repair CLI command must
  migrate any pre-change deployment's viewpoints cleanly — this is a standing
  requirement of the change, independent of how divergent cases are handled.
  Mechanics: scope-only and query-only definitions are converted mechanically (mode
  stamped, no semantic change); dual-EQUIVALENT definitions are stamped mode=query
  mechanically; dual-DIVERGENT definitions (the PA-A1 class) are NOT guessed. The
  explicit choice is recorded non-interactively (review round 2): the CLI accepts
  `--resolve-selection <slug>=scope|query` (repeatable, or an equivalent reviewed
  resolutions input file), and each resolution writes ONLY `selection_mode` — never
  a semantic conversion of either layer. The migration is DEPLOYMENT-ATOMIC: the
  CLI pre-scans ALL definitions first; if any divergent definition lacks a
  resolution it exits with a DISTINCT unresolved-migration status code, reports the
  divergent slugs with both populations, and writes NOTHING ANYWHERE in that
  deployment — not even the mechanical conversions — so a non-interactive
  deployment upgrade either completes in full or changes nothing and fails loudly
  with an actionable worklist. That report is ordinary
  ephemeral command output; there is NO per-viewpoint-definition manifest as a
  persisted concept, schema field, or reader in the software — long-term the
  definition carries only its `selection_mode`. The upgrade command is idempotent
  (re-running on a migrated deployment is a no-op; re-supplying the same resolutions
  is a no-op). Tests: PA-A1 recipe in both modes; scope-only definition executes its
  declared types; catalog row shows the active summary; upgrade-CLI fixture with
  scope-only / query-only / dual-equivalent / dual-divergent / parameterized
  definitions migrates cleanly and idempotently; a mixed fixture (mechanical
  candidates + one unresolved divergent) exits with the unresolved-migration status
  and leaves EVERY definition in the deployment byte-identical (atomicity); the
  same fixture WITH `--resolve-selection` migrates everything and stamps only
  selection_mode on the divergent one. Dependencies: definition schema docs; module definitions review
  (they carry both layers today). Estimate M–L (medium-high confidence).

### P-03 Status (and lifecycle fields) in the result projection (F3) — Priority: High

- **Evaluation.** `status` filters work (PE-A1: 104 draft motivation elements,
  oracle-exact) but projection records carry only
  id/name/type/specialization_slugs/group/membership (`probe-PE-A1.json`), so authored
  Status columns render "—" for every row. A compliance persona drafted the false
  claim "no status recorded in the model" into audit evidence (PK-A1).
- **Judgement.** A queryable attribute that silently cannot be displayed produces
  confident wrong conclusions about data quality. FMEA: S8–9 / S7 dual reading
  (anchor unresolved, owner adjudication) · O5 · D9.
- **Applied principles.** What can be queried can be shown; visibility of system
  status; audit outputs need provenance-complete rows.
- **Options.** (a) Add status/version/last-updated to projection entity records;
  (b) resolve column sources at render time via a second entity fetch; (c) error when
  a column source is not in the projection.
- **Recommendation.** (a), with (c) as the general guard for arbitrary unresolvable
  column sources (same family as the scale-attribute no-op, P-04). (b) duplicates the
  read path and drifts.
- **Implementation (tightened per review, R-08).** Server-resolved, typed
  `column_values` in the projection: the result payload carries each authored
  column's values with explicit missing-value marking — no client-side second fetch
  (N+1, snapshot-inconsistent). Add `status` and `version` to the projection entity
  record (both exist in the read index). `last_updated` needs a decision first: it
  exists in entity frontmatter and write paths, but the reviewer could not find it in
  the read-index schema — either persist it into the index with defined semantics
  (modification vs. authoring date) or drop it from this proposal; do not promise it
  unverified. Table renderer maps token styles for status values; guard: a column
  whose source is absent from the projection gets a header warning ("source 'x' not
  available in results") — same outcome family as P-04. Tests: probe asserts
  status/version present and typed; missing-source column warns; GUI test for the
  PE-A1 recipe shows per-row draft badges. Estimate M (high confidence).

### P-04 No silent no-op style rules (F4, F19) — Priority: High

- **Evaluation.** A saved scale rule with `scale_attribute: derived.conn_count`
  produced a legend with −∞/∞ bounds and near-uniform node color; the probe shows
  `styled_items_by_capability: {}` and `scale_legends: []` — the rule resolved on
  nothing, with no error or warning anywhere (`probe-PH-A1.json`). Contrast: an
  unknown scale attribute *inherited from a module rule* hard-blocks save (PC-A1).
- **Judgement.** Violates the run's invariant "every authored style rule reports one
  observable outcome". The same mistake is either a save-blocker or a silent no-op
  depending on where it lives — the worst of both worlds.
- **Applied principles.** Error prevention; consistent validation altitude; a rule
  with no observable outcome is a defect by contract.
- **Options.** (a) Validate scale_attribute references at edit/save time against
  known numeric attributes + declared derived names (the editor knows them);
  (b) execution-time warning when a rule styles zero items ("valid but matched
  nothing" vs "attribute unresolvable" distinguished); (c) both.
- **Recommendation.** (c). Edit-time validation catches typos ("derived." prefix
  confusion); execution-time warnings catch drift (the capability-map
  `investment_level` case shows attributes rot after save).
- **Implementation.** Editor: turn `scale_attribute` free-text into a combobox fed by
  numeric entity attributes + `derived.<name>` entries declared in the Query tab;
  validate on save (error) for unknown references in ENGAGEMENT definitions, warning
  for inherited/module rules (see P-10). Engine: per-rule outcome in the execution
  payload with a FOUR-WAY taxonomy (review adjudication, R-13):
  `unresolvable` (attribute/reference cannot resolve) · `expected-empty` (valid rule,
  zero matches — a legitimate state, e.g. a P-17 gap rule when no gaps exist) ·
  `shadowed` (matches exist but a higher-precedence rule claimed every item) ·
  `applied(N)`. Default WARNINGS only for `unresolvable` and `shadowed`;
  `expected-empty` renders as a quiet legend badge ("0 matches"), never a warning —
  otherwise healthy conformance views cry wolf. Auto scale bounds resolve to observed
  min/max with numeric endpoint labels (F19). Tests: PH-A1 recipe yields an
  `unresolvable` warning; a healthy zero-gap rule yields `expected-empty` with no
  warning; two overlapping rules yield `shadowed`; legend shows real bounds.
  Estimate M.

### P-05 Derived-edge disclosure in predicates and Test run (F5, F28) — Priority: High

- **Evaluation.** An authored "layering leak" query matched 1 entity where the raw
  model has 0 direct cross-layer edges — the predicate evaluated a *derived* access
  edge (witness chain in `probe-PL1-deps-store.json`); Test run showed only counts, so
  the persona could neither name the match nor see its provenance and drafted a ticket
  against a modeled dependency that does not exist (PH1; self-refuted only with source
  access).
- **Judgement.** Governance/conformance queries — the highest-stakes authored use —
  silently mix derived facts into what users read as modeled facts. FMEA: S8–9 / S7
  dual reading (anchor unresolved, owner adjudication) · O3 · D9.
- **Applied principles.** Provenance before citation; conformance results must be
  auditable; visibility of system status.
- **Options.** (a) `connection scope: direct | indirect (derived) | both` selector on
  the 'has a connection…' predicate; (b) keep semantics, add disclosure text only;
  (c) Test run lists matched entities (first N names + ids) with a per-entity
  matched-via tag.
- **Recommendation** *(owner adjudication: no single default can be committed — the
  user must be able to state which is meant, as separate conditions)*: (a) as an
  EXPLICIT, always-visible part of the condition (not a buried default) + (c). The
  builder should read "has a direct connection…" / "has a direct or derived
  connection…" in both the condition row and the plain-language summary, so two
  predicates with different traversal read as two different conditions.
- **Implementation (corrected by review verification, R-06).** The schema field
  ALREADY EXISTS: `IncidentConnectionCondition.traversal: direct|derived` (default
  `direct`), and parsing rejects `both`. The work is therefore: (1) add `both` to
  the predicate's accepted values with defined semantics — union of direct and
  derived incident sets computed BEFORE negation, de-duplicated by connection
  identity, provenance retained; (2) expose the selector in the builder, rendered
  inline in the predicate phrase; (3) summary generator names the traversal in
  words. **Open investigation (must precede implementation):** the run's PH1
  predicate matched a derived-only edge although the schema default is `direct` —
  determine what traversal value the GUI builder actually emits today (if it writes
  `derived` undisclosed, that sharpens the original finding and defines what
  "current behavior" means for migration). Migration: no blanket rewrite to `both`;
  saved predicates keep their parsed value, and the deployment upgrade/repair CLI
  stamps the implicit default explicitly (idempotent, no semantic change) so future
  default changes cannot silently alter saved recipes. Test run panel: collapsible
  matched-entity list (names, types, cap ~50) with "matched via derived (N hops)"
  tags. Tests: union-before-negation (a negated `both` predicate excludes entities
  with EITHER kind of connection); duplicate suppression; PH1 recipe names the store
  and tags the edge derived; PD3 recipe names File System Service; saved
  parameterized recipes unchanged after upgrade; summary regression per traversal
  value. Estimate M–L (medium confidence).

### P-06 Surface edge provenance in results (F6) — Priority: High

- **Evaluation.** The execution API already carries everything: `derived::` ids,
  `certainty`, `hops`, `via_connection_ids` witness chains (verified in probes and by
  the architect persona's source check). No GUI surface exposes any of it: edges are
  not selectable in diagram or graph, there is no edge legend, and dashed styling is
  ambiguous against ArchiMate's dashed modeled types (PH3).
- **Judgement.** Pure presentation gap with the data one selection away; blocks
  before-citation verification, the professional workflow the feature exists for.
- **Applied principles.** Recognition rather than recall; don't hide provenance the
  engine has; evidence must be inspectable where it is displayed.
- **Options.** (a) Edge selection + detail panel (type, certainty, hops, witness chain
  with links to the underlying modeled connections); (b) edge legend mapping style →
  modeled/derived(certain/potential); (c) hover tooltips only.
- **Recommendation.** (a) + (b). (c) fails on touch and on dense graphs.
- **Implementation.** Graph explorer: make edges hit-testable (wider invisible stroke),
  Details panel gains a connection mode; diagram surface: clickable edge labels or a
  result-side connection list keyed by source→target. Legend: one entry per rendered
  connection style incl. modeled vs derived-certain vs derived-potential (density
  difference already exists — label it). **Witness ordering contract (review
  adjudication, R-16):** raw `via_connection_ids` are documented as NOT guaranteed
  source-to-target ordered (`docs/reference/viewpoints-schema.md`), so the detail
  panel must not render them as-is: the projection emits ordered `witness_steps`
  (connection_id, source, target, relationship type, direction, hop index) with a
  deterministic shortest-path tie-break and access to alternates where several
  witnesses exist; ID membership alone is not a readable path. Dependencies: shares
  edge-selection work with P-08 ergonomics; witness_steps feed P-01's
  anchor_modeled_distance. Estimate M–L. Validation: PH3 walkthrough discoverable
  end-to-end; a witness stored in reversed ID order renders source→target correctly.

### P-07 Addressable, honest execution URLs (F8) — Priority: High

- **Evaluation.** Anchored executions never encode the anchor (reload → empty dialog);
  switching viewpoints via the in-graph dropdown leaves the previous
  `?viewpoint=` in the URL, so a copied link opens a *different* view than the one on
  screen (PG3, heuristic passes HA-15/HB-14). Editor state is likewise unaddressable
  (HA-5/HB-5).
- **Judgement.** Sharing is a core persona workflow (CONTRIBUTING.md links, review
  handoffs); today's links are lossy at best and actively wrong at worst.
- **Applied principles.** URL = state for primary surfaces; user control and freedom.
- **Options.** (a) Encode viewpoint + parameters (+ layout) as query params and keep
  them in sync on every in-page switch; (b) a "copy link to this result" button that
  serializes state without changing routing; (c) both.
- **Recommendation.** (c) — (a) is correct baseline; (b) gives an explicit affordance
  and a place to warn when a result is non-reproducible (e.g. model changed).
- **Implementation.** SPA router: `/graph?viewpoint=<slug>&param.anchor=<id>&layout=…`;
  dropdown switch triggers router replace; parameter dialog pre-fills from URL. Editor
  routes: `/viewpoints/<slug>/edit`. **Live vs verified links (review adjudication,
  R-15):** a URL of slug+parameters is a LIVE link — it re-executes against current
  model and definition state and silently changes as they change. Label it as such
  and keep it as the default; for evidence/reproduction use-cases offer a "copy
  verified reference" that additionally carries definition version/digest and model
  generation, and on open shows "re-executed at a different generation — results may
  differ" when state has moved (complements P-13 lineage; no result archival implied).
  Tests: reload reproduces result; link copied after dropdown switch names the
  on-screen viewpoint; verified reference opened after a model change shows the
  generation-mismatch notice. Estimate M.

### P-08 Graph/diagram readability & interaction floor (F7, F12, F13, F30, F32) — Priority: High (bundle)

- **Evaluation.** Dense views: no zoom/fit/minimap; radial layout without an anchor
  flings all nodes off-viewport into a blank canvas (HA-12); node clicks blocked by a
  full-page overlay or unstable force layout (PH2); labels truncate into misreadings
  that reached a persona's design-review artifact (PG3: an assessment read as a
  component); active-layout button label invisible (HA-13); Spacing controls vanish
  once a graph renders (HA-18). Diagrams: initial render is a tiny illegible strip
  with gesture-only controls (HA-19/HB-17); at full model scale PlantUML fails
  ("Error line 767") with no graceful degradation (PI-A1, F7).
- **Judgement.** The exploration surface is strong for ≤20-node anchored views and
  degrades into unusable/misleading beyond that — precisely where overview personas
  live.
- **Applied principles.** Flexibility and efficiency; visibility of status; graceful
  degradation at scale.
- **Options / Recommendation.** Ship as one ergonomics bundle: fit-to-view + zoom
  buttons + (optional) minimap; freeze layout before enabling hit-testing; disable
  radial when no anchor exists (tooltip why); label wrap + full-name tooltip + type
  legend (F13); fix active-button contrast; keep Spacing visible post-render. Diagram
  surface: fit-to-width initial zoom; pre-flight size estimate with "result too large
  for diagram rendering — try exploration/table or narrow the scope" instead of a
  PlantUML stack error.
- **Implementation.** Contained in the two execution surfaces; no schema changes.
  Estimate L (multiple small fixes, medium confidence in aggregate). Validation:
  HA-12/13/18/19 scenarios + PH2 node inspection on the 183-node view + PI-A1 renders
  a friendly limit message.

### P-09 Honest empty/degenerate results (F9, F10) — Priority: High

- **Evaluation.** Views over unpopulated domains return junction/grouping noise with
  non-zero counts and no statement that the substantive types are absent (capability:
  "22/22 · 0/0" + drift warning; migration: 7 junctions; PI1/PI2, HA-24, HB-22).
  Cancelling a parameter dialog shows "No entities in the current model match this
  viewpoint's criteria" for a query that never ran (HA-17).
- **Judgement.** The empty-and-noise states actively misinform; catalog honesty was
  the single differentiator between personas correctly recognizing fixture gaps vs
  confidently misreading them.
- **Applied principles.** Say what is absent, not just what is present; error states
  must be true statements.
- **Options / Recommendation (corrected per review, R-02 — the original example copy
  was itself false).** Classify a result's entities three ways against the
  definition's scope: TARGET types (the substantive types the viewpoint is about),
  INCIDENTAL substantive content (in-scope, populated, but not the target — e.g.
  capability-map's 15 motivation `outcome` elements, which must never be called
  "structural"), and STRUCTURAL helpers (junctions/groupings). Result-header logic:
  when target types have zero instances, say exactly that and name what IS shown —
  e.g. "This model contains no capability or resource elements; showing 15 outcomes
  and 7 structural elements (junctions/groupings)." Optionally suppress helper-only
  results behind a disclosure toggle. Param-dialog cancel → neutral "not executed"
  state. Target-population declaration (corrected in review round 2 — "scope minus
  helper types" is unsafe under P-02, where scope may be the INACTIVE, absent, or
  stale layer, and an expressive query cannot generally be reduced to a type set):
  every definition carries a PRESENTATION-level target-population declaration. In
  scope mode it may be generated mechanically from the ACTIVE scope; in query mode
  it must be declared explicitly (`target_types` or a separately defined target
  expression evaluated like any criteria group). When the target population is
  UNKNOWN (no declaration, or not mechanically derivable), honest-empty messaging is
  SUPPRESSED — the header shows plain counts and makes no absence claims, because a
  guessed absence claim is exactly the false copy this proposal exists to prevent.
  The ontology's junction/grouping distinction still classifies helpers. Tests:
  target-empty with incidental content; helpers-only; target-present; parameterized
  definitions; both selection modes (P-02); a query-mode fixture whose INACTIVE
  scope differs from the query's selection must take its target population from the
  declaration, not the stale scope; an undeclared query-mode definition renders
  counts with no absence claim.
- **Implementation.** Execution result header component + one classification helper
  (substantive vs structural types — the ontology knows junction/grouping); param flow
  state fix. Estimate S–M. Validation: capability-map/migration honesty scenario;
  cancel scenario.

### P-10 Fork-safe validation (F17, F18) — Priority: Medium

- **Evaluation.** Forking capability-map inherits its schema-drifted
  `investment_level` scale rule; Save is then blocked by "unknown-attribute … unknown
  scale attribute" — an error the fork author never wrote, surfaced only at save time;
  a second error ("exists takes no value") also appeared only at save (PC-A1,
  validation dead end for a CTO persona).
- **Judgement.** Drift is a warning on execution but a hard error on save of an
  untouched inherited rule — inconsistent altitude that dead-ends the flagship
  copy-and-modify flow.
- **Applied principles.** Error prevention at edit time; never block users on faults
  they didn't author; consistent severity for the same fault.
- **Options.** (a) On fork, auto-quarantine unresolvable inherited rules (disabled +
  notice, saveable); (b) demote unknown-attribute to warning on save; (c) validate
  conditions as they are edited (comparator/value coherence — catches 'exists takes no
  value' immediately).
- **Recommendation.** (a) + (c). (b) alone would let silent no-ops proliferate
  (conflicts with P-04).
- **Implementation.** Save-as pipeline: pre-validate; move failing inherited rules to
  `disabled: true` with a banner ("1 inherited style rule disabled — attribute no
  longer resolvable"); inline condition validation in the criteria row component.
  Estimate M. Validation: PC-A1 recipe completes with a visible quarantine notice.

### P-11 Table representation as a first-class output (F21, F22) — Priority: Medium

- **Evaluation.** Table rows are inert (no entity links, no sort); a permanently empty
  "Style" column ships by default; there is no export anywhere (PA3, PK1, PE2 — three
  audit/report personas ended with "screenshot a graph" as their only evidence path).
- **Judgement.** The representation whose whole purpose is reports/evidence packs is
  the least finished; export absence blocks the compliance workflow entirely.
- **Applied principles.** Every listed entity is a link (consistency with Browse);
  evidence needs provenance-complete export.
- **Options / Recommendation.** Linked rows (entity page), sortable columns, hide
  empty Style column unless a rule targets `columns`; CSV export carrying a provenance
  footer/header block (viewpoint slug+version, parameters, executed_at,
  index_generation, counts) — the probe already assembles exactly these fields;
  optional PNG export for graph/diagram surfaces later.
- **Implementation (tightened per review, R-08).** Table renderer + a
  SERVER-generated export endpoint. Export contract: the export is COMPLETE (the full
  result at the execution's generation, not the visible page) and generation-pinned;
  if a page-only export is ever offered it must be prominently labeled as partial.
  Client-side CSV of the rendered page is rejected as the primary mechanism — a
  242-row result exported from a paginated view would silently look complete.
  Depends on P-03's column_values (exports carry the same server-resolved values).
  Estimate M. Validation: PK1 ends with a citable CSV containing all 31 rows +
  provenance block; a 242-row export is complete; export during a generation change
  either completes at the pinned generation or fails loudly.

### P-12 Catalog as a decision surface (F14, F15, F24, H1, H2) — Priority: Medium (design-level)

- **Evaluation.** The catalog offers slug/name/version/tier/scope-dump only: no
  description column, no representation indicator, no parameter marker, no search/
  sort/filter, no population signal; duplicate display names are indistinguishable in
  pickers; an e2e leftover row was flagged by 12/12 personas. Scent data shows two
  systematic failure clusters that better metadata would address: realization-named
  views read as gap-analysis tools, and empty-domain views collecting confident picks.
- **Judgement.** Selection quality is carried entirely by naming; every persona
  compensated. This is the highest-leverage *pre-execution* improvement.
- **Applied principles.** Recognition rather than recall; progressive disclosure
  (dense scope dumps collapse behind a summary); catalog curation as governance.
- **Options / Recommendation.** Add columns: one-line description (already in
  definitions), representation icon, "needs input" marker for parameterized
  definitions, tier badge reused in all pickers; search + sort + tier filter;
  collapse scope lists ("14 types ▸"); lint/sweep test-artifact slugs from the
  engagement catalog (F24). Description text for realization views should state
  "shows existing realization links — does not isolate gaps" (directly attacks H1;
  see also P-17). *Population hints: owner decision — the overview shows NO counts
  at all. Population signaling is handled exclusively by honest-empty messaging at
  execution time (P-09) and the counts already shown on the view/edit page.* Also fold in: rename
  the module-row "View" action (it opens an editable fork-preparation surface —
  heuristic HA-1); "Customize…" or "Open (read-only master)" both fix the mislabel.
- **Implementation.** Catalog list + picker components; NO counts of any kind in the
  overview (owner decision; the earlier count-cache idea is withdrawn — R-02 caught
  the leftover). Estimate M. Validation: re-run the S1 scent protocol on 3 personas
  (human or synthetic) and compare false-scent rates.

### P-13 Fork/pin provenance and staleness (F27, PJ governance) — Priority: Medium (strategic)

- **Evaluation.** A fork records no origin slug/version; the catalog cannot show which
  engagement rows fork which module definitions; viewpoint version is a manual
  spinbutton; no changelog/last-modified surface exists anywhere (PI3/PI4); PJ's
  governance verdict: "Save-As is fine for authoring but unauditable at scale."
- **Judgement.** Fork-per-audience (a natural publishing model) is currently a
  governance liability: forks silently diverge and nothing detects drift.
- **Applied principles.** Provenance by construction; two-tier governance needs
  lineage; staleness must be visible where the stale thing is used.
- **Options.** (a) `forked_from: {slug, version}` recorded by Save-as + catalog badge
  + "origin has newer version" indicator; (b) full inheritance/overlay model (forks
  reference the origin and override deltas); (c) out-of-band process only.
- **Recommendation.** (a) now — strengthened per review (R-11): a mutable
  slug+version label alone cannot establish what a fork was forked FROM, because
  versions are hand-edited integers. Lineage must bind to immutable content:
  `forked_from: {slug, version, definition_digest}` where the digest is a canonical
  content hash of the origin definition at fork time, plus the model
  `index_generation` at creation and (for parameterized recipes) normalized
  parameters. (b) stays a separate proposal cycle; (c) contradicts the
  self-describing ambition.
- **Implementation.** Definition schema addition (descriptive, no version bump
  needed); ONE lineage-stamping service used by every authoring route (GUI Save-as
  AND the MCP `artifact_viewpoint` tool — a GUI-only stamp would make MCP-created
  forks second-class); catalog renders lineage + staleness badge computed by digest
  comparison, not version comparison. Estimate M. Validation: PJ2 hygiene walk names
  forks without guesswork; editing the ORIGIN after forking flips the fork's badge
  to stale even if the origin's version integer was not bumped; GUI- and MCP-created
  forks carry identical lineage.

### P-14 Picker and terminology polish (F23, F25, F26, F33, F34) — Priority: Medium/Low (bundle)

- **Evaluation & judgement.** Entity picker ranks diagram-internal constructs above
  model entities, confirms selection with a raw artifact id, and shows unexplained
  fuzzy matches (PI2, PL1, HA-16, HB-15/16); `global-artifact-reference` is
  selectable in the Scope picker contrary to the standing internal-type exclusion rule
  (HB-10); execution surfaces title by slug and highlight the wrong nav item (HA-20/
  HB-18); token swatches are unlabeled and color values are offered for shape/icon
  channels (HA-8/9, HB-9); docs vocabulary diverges from GUI ("forking"/"live
  preview"/"styling rules" vs "Save as…"/"Test run"/"style rule") and no in-app help
  link exists (Inv-7, HA-27). Added per review (R-12 — previously unowned findings):
  a spurious developer-formatted "read-only-definition (/slug)" error banner appears
  on the module View editor after a mere Test run, contradicting the adjacent
  "adjust it freely" guidance (F11, HA-6/HB-8); and the editor silently discards
  unsaved work on "← Back" with no confirmation, while Save-as mode has no Cancel
  (F16-part, HA-10/HB-7).
- **Recommendation / implementation.** One polish pass: model entities ranked first
  with a "diagram-internal" divider; confirmation echoes the display name (id
  secondary); "showing best matches" note; remove GAR (and other internal types) from
  the Scope picker via the existing guidance-layer filter; title executions
  "Name (slug) — representation"; nav highlight follows origin; label swatches, offer
  per-channel value sets; align docs terms with GUI labels and add a help link from
  the editor to `docs/03-modeling/viewpoints.md`; suppress the read-only-definition
  banner unless a WRITE was actually attempted, and phrase it in user language (F11);
  dirty-state confirm on Back and an explicit Cancel in Save-as mode (F16). Estimate
  M in aggregate; each item independently S. Validation: heuristic re-inspection of
  the affected surfaces; Test run on a module View raises no error banner; Back with
  unsaved edits prompts.

### P-12a Explicit create-route from the catalog (H3) — Priority: Medium

- **Evaluation (review round 2, closing the H3 ownership gap).** Five non-expert
  personas whose correct route was "build it in the query builder" chose docs or
  gave up at the catalog page; the builder's capabilities (group filters, absence
  predicates, boundary queries) later proved MORE than sufficient in every case. The
  catalog's only creation affordance is an unexplained "+ New viewpoint" button, and
  the empty/near-miss states never suggest creation at all. Catalog metadata and the
  "View"-label rename (P-12/P-14) do not, by themselves, add or validate a create
  route.
- **Judgement.** The gap is first-contact information scent for CREATION as a route,
  distinct from selection metadata. Synthetic hypothesis, endorsed as plausible;
  retains its human-validation residue.
- **Options.** (a) Permission-aware "Create viewpoint" entry point on the catalog
  (prominent button with one line of capability copy: "build your own view — filter
  by type, project, status, or connections") AND on empty/zero-result states ("no
  viewpoint fits? create one"); starts a NEW blank definition at a dedicated route
  (`/viewpoints/new`, consistent with P-07's editor routing). (b) Template-first
  creation (pick a starting pattern: inventory / anchored impact / coverage-gap /
  boundary). (c) Copy-first only (steer everyone through Save As).
- **Recommendation.** (a) now, with (b) as its natural follow-up once P-17's
  coverage recipes exist as templates. Distinction from Save As stated in the UI:
  Create starts from blank (or template) with no lineage; Save As forks an existing
  definition and records lineage (P-13). Hidden/disabled with an explanatory tooltip
  when the user lacks engagement-write permission (permission-aware, not
  permission-blind).
- **Implementation.** Catalog header + empty-state components; route `/viewpoints/
  new`; capability copy string shared with the docs. Estimate S–M. Validation: the
  H3 SCENT protocol re-run (S1-style, catalog page only): non-expert contexts given
  create-class questions must now select the create route at a materially higher
  rate — not merely improved catalog false-scent rates (P-12's metric).

### P-16 Scale-adaptive result presentation (owner-raised) — Priority: High (design-level)

- **Evaluation.** Most shipped viewpoints return hundreds of items (layered 242/461,
  service-realization 228/443, technology-usage 188/336, motivation 117/210 — and
  motivation-technology-support 110/1318 with derived edges). No persona ever explored
  a whole dense graph: they read the counters, sampled ≤2 nodes, and judged by
  density ("spider web of acronyms — can't paste this into a deck" PA3; "a 300-edge
  picture isn't a risk register" PC2; "242 boxes on a first-time contributor and
  they'll bounce" PG1); on dense views node inspection was physically blocked
  (off-viewport, unstable layout — PH2/PE1). The run addressed the *interaction
  floor* (P-08) and *steering* (P-11/P-12) but not the underlying question: whole-
  layer viewpoints rendered as one flat graph are beyond human working scale.
- **Judgement.** This is a design problem, not a rendering bug: the default
  presentation for >~100-node results produces confident glance-level judgements and
  zero deep reading — the worst combination for a tool whose outputs feed decisions.
- **Applied principles.** Overview first, zoom and filter, details on demand
  (Shneiderman); progressive disclosure of the GRAPH itself, not just the editor;
  match representation to result cardinality (skill guidance: many small diagrams
  beat one large one; matrices for dense many-to-many).
- **Options.** (a) Aggregate-first exploration: above a legibility budget (~100
  nodes), open with group/domain super-nodes (counts on the aggregate, edges
  bundled between aggregates) and expand on demand — builds on the existing
  clusters/anchor/distance machinery; (b) legibility-budget prompt: render nothing
  dense by default; offer "filter to subgroup / switch to table or matrix / pick an
  anchor" choices; (c) hard render caps with pagination of the graph (rejected —
  paginated graphs are incoherent); (d) author-side fix only: curate small
  overview viewpoints and steer dense ones to table/matrix representations.
- **Recommendation** *(owner adjudication: a scalable, long-term, UI/UX-optimal and
  architecturally sound fix is wanted — this is the committed direction, not an
  option)*: (a) as the default behavior with the budget from (b) as its trigger,
  plus (d) as immediate mitigation (re-declare dense module viewpoints' default
  representation, suppress junction/grouping types in overview scopes).
- **Architectural soundness requirements.** Aggregation must live in the
  projection/presentation pipeline (server side), not as a client-side rendering
  hack: (1) the projection gains an aggregation capability (`aggregate_by: group |
  domain | …`, producing aggregate items with member counts and bundled inter-
  aggregate edges) so ALL surfaces — exploration, diagram, probe — share one
  implementation and the behavior stays invariant-testable (same counts on every
  surface, per the run's Invariant 1); (2) expand/collapse is client state over
  server-provided aggregates, with drill-down fetching the member subgraph through
  the same execution path (no second query language); (3) the legibility budget is a
  presentation property of the definition (`presentation.legibility_budget`, default
  ~100), so curators can tune it per viewpoint and the probe can assert it;
  (4) aggregate rendering composes with existing style rules (a rule's matches
  roll up to a count badge on the aggregate) rather than bypassing them — no second
  styling system. This keeps the hexagonal layering intact (projection logic in the
  core, surfaces as thin renderers) and makes the dense-view behavior testable
  without a browser.
- **Aggregation contract (review adjudication, R-07; identity corrected in review
  round 2 — the key must include ENDPOINT aggregate identities, or same-typed edges
  between different group pairs collapse into one bundle and change the graph's
  topology).** Node aggregate identity = (aggregation dimension, dimension value,
  entity type). Edge aggregate identity = (source_aggregate_id,
  target_aggregate_id, connection_type, direction, provenance/certainty class —
  modeled vs derived-certain vs derived-potential). Each `AggregateItem` carries its
  immutable identity tuple, member count, and a stable member reference for
  drill-down. HOMOGENEITY rule: no aggregate may mix modeled and derived edges, mix
  directions, mix connection types, or span more than one (source, target) aggregate
  pair; the run's motivation-technology-support case (1318 derived-dominated
  connections over 778 raw) is the regression fixture. ORDERING rule: aggregation
  operates on the COMPLETE projection before any entity/connection limit is applied
  — a truncated-then-aggregated result is not a faithful overview. Drill-down
  (expand) fetches members through the same execution path (feeds P-06's detail
  panel). Tests: membership conservation (Σ member counts = flat counts); no
  heterogeneous aggregate exists; TOPOLOGY preservation — a fixture with two
  same-typed/same-direction/same-provenance edges between DIFFERENT aggregate pairs
  (e.g. platform-core→assurance and platform-core→motivation-narrative) must yield
  two separate bundles; aggregation with limit=10 aggregates the full
  result, not the first 10; P-06 drill-down from an aggregate edge reaches the
  witness detail. Also owned here (R-12): F20 — the current group_by+Clusters
  visual no-op is subsumed by this work; the fixture with 4 groups
  (probe-PG-A1.json) must render visibly separated clusters or aggregates.
- **Implementation.** Phase 1 (mitigation, S): module definition pass — junction/
  grouping exclusion in overview scopes, representation re-declarations. Phase 2
  (core, L): projection aggregation capability + budget trigger + choice prompt
  (filter / switch representation / pick an anchor) when aggregation cannot apply.
  Phase 3 (surface, M): expand/collapse UI, aggregate badges, drill-down. Validation:
  PA3/PG1/PC2 scenarios produce a readable first screen; probe asserts aggregate
  counts equal flat counts; re-run the S2 protocol on one overview persona.

### P-17 Realization views must separate realized from unrealized (owner-endorsed H1) — Priority: High

- **Evaluation.** Five personas expected realization-named views to expose the gap
  set; the shipped views render only existing links as one undifferentiated graph
  (goal-realization 97/142) or the whole model (requirements-realization 352/731 —
  mis-scoped; report F-note). The owner's stated expectation matches the personas':
  anchored → realization of the selected entities; unanchored → both realized AND
  unrealized elements, visibly separated.
- **Judgement.** With owner endorsement this graduates from synthetic hypothesis to
  accepted design gap: the realization family answers "what realizes what" but every
  stakeholder question observed in the run was "what is NOT realized".
- **Applied principles.** Views should answer the question their name promises;
  absence is data (gap marking); defaults must serve the dominant question.
- **Options.** (a) Add gap-marking style rules to the shipped realization viewpoints
  (a match rule with a negated 'has an incoming realization connection' condition →
  Critical token) — pure definition change IF style-rule match criteria support
  connection predicates; (b) two-band presentation (realized / unrealized groupings)
  as a rendering feature; (c) new dedicated "Realization coverage" viewpoints (the
  PJ-A1/PK-A1 recipes, promoted into the module catalog) alongside the existing ones;
  (d) fix requirements-realization's scope (it currently selects six domains — the
  entire model — instead of requirements + realizers).
- **Recommendation (widened per review, R-01 — adjudicated Major): this is a
  realization-FAMILY contract, not a requirements-only fix.** The owner-endorsed
  behavior (anchored → realization of the selected entities; unanchored → realized
  AND unrealized visibly separated) applies to goal-realization,
  outcome-realization, AND requirements-realization alike — today goal-realization
  is a bare type filter (97/142, no realization predicate, no separation) and
  outcome-realization a domain dump (242/461), so a requirements-only gap view would
  leave two of three family members dishonest. Sequence: (d) immediately
  (requirements-realization's six-domain scope is a definition bug); (c) now (the
  oracle-validated coverage recipes); then apply the family contract to all three:
  anchor parameter resolution, an explicitly-stated traversal condition per P-05
  (direct/derived/both), and mutually exclusive realized/unrealized bands when
  unanchored. If a broad "everything with realization edges" overview is worth
  keeping, it gets a distinct slug and description, by owner approval — it must not
  squat on the family name. (a) if the style grammar permits connection predicates
  in match criteria — verify first; else (b) via P-16's banding.
- **Implementation.** Module definition changes across the family (three
  definitions + two new coverage viewpoints "Requirements coverage (gaps)" and
  "Component traceability (gaps)", table default representation, status/group
  columns — depends on P-03). Style-grammar check for (a): one probe with a
  negated-connection match rule. Estimate M (was S–M; family scope). Validation:
  per family member — realized ∪ unrealized = ASSESSED TARGETS and realized ∩
  unrealized = ∅ (band exclusivity over targets only), anchored and unanchored
  screenshots; PA1's built-vs-aspirational question answerable in one execution of
  goal-realization; PK1's coverage table producible without authoring; a contextual
  realizer never appears in the unrealized band.
- **Population and orientation contract (review round 2 — "population" was
  undefined and would misclassify realizers).** Per family member, the definition
  states: (1) the ASSESSED TARGET population — the elements whose realization status
  the view judges (goal-realization: goals; outcome-realization: outcomes;
  requirements-realization: requirements) — this is also the P-09 target-population
  declaration; (2) the CONTEXTUAL REALIZERS included for explanation (the elements
  on the realizing side), which are displayed but NEVER banded — a realizer with no
  incoming realization of its own is not "unrealized", it is context; (3) the
  realization ORIENTATION: a target is realized iff it has an INCOMING
  `archimate-realization` (chain) — realizer→target direction, per ArchiMate; and
  (4) the traversal applied to that incoming relation (direct / derived / both, the
  P-05 selector), stated in the definition and echoed in the summary. Band
  exclusivity and the union invariant apply to assessed targets only.

### P-15 Boundary-aware connection styling (F29) — Priority: Low (enhancement)

- **Evaluation.** Edge style rules condition on the connection's own attributes and
  cannot express "endpoints in different groups", so a trust-boundary view can only
  accent nodes, not the boundary edges (PL-A1 fallback).
- **Judgement.** Real security/team-boundary use case; today's workaround is
  acceptable but second-best.
- **Options / Recommendation.** Add endpoint sub-criteria to connection style rules
  (`source_criteria` / `target_criteria`, same grammar as connection predicates) —
  consistent with the query language rather than a bespoke "boundary" flag.
- **Implementation.** Style-rule schema + evaluator + builder UI; reuse the criteria
  row component. Estimate M. Validation: PL-A1 recipe emphasizes exactly the 28
  cross-boundary connections (oracle set exists).

---

## Part B — Self-model proposals (ENG-ARCH-REPO)

All writes via `artifact_*` MCP tools; guidance-first, descriptions-over-connections-
over-entities; verify with `artifact_verify` after each batch.

### SM-01 Motivation-layer convention review (merges former SM-01/02/03; corrected per review R-09) — Priority: High

- **Corrected facts** (verified against `oracle-data-2.json` after the review caught
  errors in the original three cards): the model has **5** drivers (not 6); the
  **7 driver→goal edges are typed `archimate-influence`** (directed — the original
  SM-03 claim that they were symmetric associations was wrong; only the 8
  stakeholder–driver edges are associations); assessment-mediated driver→goal paths
  EXIST for several drivers (e.g. via assessments into the assurance and
  autonomy goals), so "the driver→goal leg is missing" holds only per-driver, not
  layer-wide; and the two assurance stakeholders (Risk & Compliance Officer,
  Safety / Security Analyst) each carry goal associations but **no driver link** —
  that specific guidance gap ("stakeholders should be associated with one or more
  drivers and one or more goals") stands.
- **Judgement.** One coherent convention review beats three edge-adding cards: the
  earlier split double-counted legitimate assessment mediation as a gap and
  contradicted itself (add direct edges "only where no assessment path exists" and
  simultaneously "×3").
- **Applied principles.** Motivation domain first; guidance-first; descriptions over
  connections over entities; no mechanical edge decoration.
- **Procedure (one session).**
  1. Decide and record the convention: is assessment mediation an ACCEPTED
     driver→goal trace (recommended: yes — it is richer, and guidance sanctions
     driver→assessment→goal), and when is a direct influence edge additionally
     warranted?
  2. Per driver (all 5): list its retained trace path (direct influence,
     assessment-mediated, or none) and add a direct `archimate-influence` edge only
     where no path exists AND the causal claim is real — with a one-sentence
     description stating it.
  3. Stakeholder legs: add the missing stakeholder↔driver links for the two
     assurance stakeholders (`archimate-association` for hub consistency, or
     influence where a directional claim is stated).
  4. Association→influence retyping ONLY where a connection's description already
     states a direction — and note (review-verified): `artifact_edit_connection`
     CANNOT change a connection's type; retyping = remove + recreate with the same
     endpoints and description, preserving provenance in the new description.
  5. Record the convention in the motivation project's documentation; run
     `artifact_verify`.
- **Validation.** Every driver has a stated disposition; the two stakeholders have
  driver links; no association was retyped without a direction stated in its
  description; verify passes. Estimate S.

### SM-04 Govern the Confidential Assurance Store: realization edges to its requirements — Priority: High

- **Evaluation.** Oracle + persona PL1 + probe: the store realizes NO requirement and
  no motivation element sits within 2 hops, while requirements that *name* the store
  exist ("Pluggable, Confidential Assurance Storage", "Tamper-Evident Assurance…",
  "Assurance Content Is Confidential by Default" principle, etc.). The security
  persona correctly flagged governance invisibility.
- **Judgement.** For the model's flagship security component this is the single most
  visible traceability gap; it also feeds the untraced-components list (SM-05).
- **Options.** (a) store —realization→ requirement(s); (b) requirement —association→
  store; (c) model an intermediate application service.
- **Recommendation.** (a) — realization is the guidance-sanctioned "component
  fulfils requirement" relation and is what every realization viewpoint queries.
- **Implementation.** `artifact_add_connection` ×2–3 (store → the pluggable-storage
  and confidentiality requirements; check pair-legality first with
  `artifact_authoring_guidance filter=['application-component'] target='requirement'`),
  descriptions stating what property of the store fulfils the requirement; verify.

### SM-05 Traceability uplift for the 27 untraced application components — Priority: Medium (worklist)

- **Evaluation.** Conformance oracle (set-identical with the authored PJ-A1 view):
  27 of 42 application components (21 platform-core, 6 assurance — list in
  `oracle-data.json components_without_goal_or_req_trace`) have neither a realization
  chain nor any direct edge to a goal/requirement.
- **Judgement.** Some are legitimately internal modules whose parent traces (e.g.
  sub-components composed into the backend); others (Promotion Engine already
  realizes a requirement — not in the list; but e.g. diagram-type modules) genuinely
  lack motivation anchoring. A blanket edge-adding pass would violate the
  motivation-entity discipline (no mechanical bundling).
- **Convention research (post-run, owner-requested).** Three candidate semantics were
  computed against the raw model:
  1. *Part-inherits-whole* (composition ancestor traces ⇒ part conforms — the
     intuitive reading): rescues **0 of 27**, because the composition roots
     (Architecture Backend, Architecture Management Platform) do not trace either.
     Note this is also not an ArchiMate-valid derivation (it traverses composition
     against its direction; relationships of a composite do not formally propagate
     to parts).
  2. *ArchiMate-valid derived realization* (forward chains of composition /
     aggregation / assignment / realization — the Appendix-B-style rule the
     product's own derivation engine models): rescues **4 of 27** (Architecture
     Backend, Architecture Management Platform, AI Agent Host, Module Catalog),
     leaving **23** genuine gaps.
  3. *Liberal* (also through serving — NOT a valid realization derivation, since
     serving is a dependency relation): rescues 8, leaving 19.
- **Recommended convention.** Semantics 2: "a component conforms iff a forward
  structural chain (composition/aggregation/assignment/realization) reaches a goal or
  requirement." It is spec-clean, matches the product's derivation engine, and is
  exactly what P-05's `traversal` selector will make expressible in the conformance
  viewpoint. Record it in the model conventions doc.
- **Options for the residual 23.** (a) Add realization edges from genuinely governed
  components to existing requirements (the assurance family: its FUNCTIONS realize
  requirements but its components hang unanchored — often one assignment edge
  function→component or component→requirement realization closes the chain);
  (b) create new requirements only where a real constraint exists; (c) accept
  plumbing components (bulk handlers, parsers) as intentionally untraced and document
  that class.
- **Recommendation.** (a) for the assurance components and the platform services
  layer, (c) explicitly for infrastructure plumbing — a documented "internal
  mechanism, governed via its parent's requirements" class beats 23 decorative edges
  (motivation-entity discipline).
- **Implementation.** One modelling session over the 23-item worklist
  (list reproducible from `oracle-data.json` + the two scripts in this review); the
  saved conformance recipe (PJ-A1 definition with P-05's derived traversal once
  available) is the recurring audit view; re-run after the batch to measure the
  residual set.
- **Disposition register (review adjudication, R-10 — no permanent unactionable
  debt).** Every one of the 27 candidates gets exactly one recorded status:
  `conforming` (with its ordered witness chain under the adopted forward-derivation
  rule), `repair-needed` (with the specific relationship to add, per this card's
  options), `waived` (owner + rationale + expiry — this is the honest form of the
  "plumbing, governed via parent requirements" class: a waiver, not a proof), or
  `false-positive` (with the conformance-rule correction it implies). Completion
  criterion: the four statuses exactly partition the 27; re-run the conformance view
  after P-05 lands and assert the partition still holds. Waivers expire and get
  re-reviewed; nothing sits unclassified across scans.

### SM-06 Decide the empty domains: populate minimally or prune the pinned surface — Priority: Medium

- **Evaluation.** Strategy domain: 0 entities; implementation/migration content
  types: 0 (junction-only results). Five viewpoints over these domains produce the
  misleading noise results of F9; two personas' questions were unanswerable by
  design.
- **Judgement.** Skill guidance: Strategy "only for structural changes to the
  business itself"; Implementation & Migration "only when the engagement explicitly
  plans or tracks change". For ENG-ARCH-REPO (a self-describing product model), a
  *minimal* capability layer is defensible (the product's own capabilities:
  modelling, viewpoints, assurance, promotion — realized by existing services), and
  migration modeling is plausibly justified by the ongoing plan/TASKS-driven change
  streams — but neither should be populated just to make viewpoints non-empty.
- **Owner adjudication: the self-model does not need these domains.** Resolved to
  option (b) — honest-empty. Consequences to implement:
  1. P-09's honest-empty messaging becomes the load-bearing fix for these viewpoints
     (they stay in the catalog but must say the substantive types are absent).
  2. The curated starter-pin set must exclude capability/migration/implementation
     views (matches PJ's proposed 8-pin set, which already does).
  3. The `investment_level` schema drift on capability-map is resolved by REMOVING
     the drifted scale rule in the module definition (populating the attribute is
     off the table with an empty strategy layer).
- **Implementation.** Module definition update (drop the drifted rule); no model
  writes; P-09 covers the rest.

### SM-07 Reconnect or retire the orphans — Priority: Low

- **Evaluation.** Oracle: 5 disconnected model entities — File System Service (the
  one "dead technology" element), Entity Summary (BOB), Model Verification Completed
  (EVT), Confidential Assurance Repository (BOB), and the enterprise-repo requirement
  "Write code using expressive typing (where available)".
- **Judgement.** Each is either a stub worth one connection or content that belongs
  elsewhere (the enterprise requirement is a coding standard, not architecture —
  candidate for a standards document instead).
- **Recommendation.** Per-entity triage in one short session: connect File System
  Service to the components that actually use the filesystem (backend, git sync);
  connect or delete the two BOBs and the event; propose moving the enterprise coding
  requirement into a standards document (needs owner sign-off — enterprise repo).
- **Implementation.** `artifact_query_find_neighbors`/read per entity, then
  `artifact_add_connection` or `artifact_bulk_delete` (dry-run) as decided; verify.

### SM-08 Lifecycle hygiene: statuses and the status-driven workflows — Priority: Low (policy)

- **Evaluation.** 343 of 352 model entities are `draft`; 9 `active`. The DD persona
  correctly reported "predominantly draft, no currency provenance" as an
  audit-readiness flag.
- **Judgement.** Either the draft→active transition is under-used (content that has
  been stable for months is still draft) or the lifecycle field genuinely reflects
  immaturity — the model cannot say which today, which is itself the finding.
- **Owner adjudication.** Keeping statuses current was too much work; the content
  should read `active`/released, and the lifecycle concept itself may be
  under-integrated (though probably not ill-advised).
- **Options.** (a) One reviewed bulk transition draft→active across the model (the
  343), keeping `draft` only for genuinely in-flight items; (b) additionally
  integrate status with existing workflows so it maintains itself — REFINED per
  review (R-14): ordinary `artifact_save_changes` must PRESERVE status (saving is
  not reviewing; silent activation of unreviewed drafts is the failure mode);
  activation happens only through the explicit review/promotion transitions, and
  deprecation stays a separate explicit act — status becomes a byproduct of the
  review flows, never of mere editing; (c) simplify the concept to two states and
  hide it from surfaces until (b) exists.
- **Recommendation.** (a) now (it makes the field truthful and lets P-03's status
  columns pay rent immediately), (b) as the durable fix — a status that no workflow
  maintains will drift back to meaningless within months. Explicitly NOT (c): the DD
  and compliance personas both wanted lifecycle signals; the concept earned its keep,
  the maintenance model didn't.
- **Implementation.** Bulk pass via `artifact_bulk_write`/`artifact_edit_entity`
  (dry-run, per-project batches, verify after each); one convention paragraph in
  `docs-conventions.md` stating the transition rules; workflow integration as a
  follow-up product change (save/review/promote hooks). Estimate S for the pass,
  M for the workflow integration.

---

## Cross-cutting sequencing note

Highest joint leverage: P-01 + P-05 + P-06 (semantics users can trust), P-02/P-03/P-04
(definitions that mean what they say), then SM-01 (merged motivation-convention review)/SM-04 (the motivation spine the
viewpoints project). P-17's re-scoped/coverage viewpoints depend on P-03 (status
column) and P-05 (derived traversal in predicates); P-16 should phase its cheap
mitigation (representation re-declaration + junction suppression) before the
aggregate-rendering work. The conformance convention adopted in SM-05 (forward
structural chains) is the exact semantics P-05's traversal selector must offer —
one decision, two implementations.

## Owner adjudications incorporated (review round)

- Scope/query = switchable alternatives, not a merged filter stack (P-02 rewritten;
  engine must actually evaluate scope-mode; a scope→query fallback already exists in
  `src/application/viewpoints/scope_query.py` for scope-only definitions — the gap is
  that GUI-authored definitions always persist a query object and so never take it).
- Connection predicates: traversal is user-stated per condition, no committed global
  default (P-05 rewritten).
- Conformance semantics: forward structural-chain derivation adopted; the intuitive
  part-inherits-whole reading rescues 0 of 27 and is not ArchiMate-valid (SM-05).
- Strategy/implementation domains stay empty by design; honest-empty messaging is
  load-bearing; drop capability-map's drifted scale rule (SM-06 resolved).
- Status: bulk-correct to active, then integrate maintenance into save/review/promote
  workflows (SM-08 rewritten).
- Realization views should separate realized from unrealized (owner expectation
  matches persona expectation) — new P-17.
- Dense results are a first-class design problem — new P-16 (scale-adaptive
  presentation).
- Catalog overview shows no counts at all; population signaling lives in execution-
  time honest-empty messaging and the view/edit page only (P-12 final).
- Save As belongs in the editor (placement endorsed); the "View" action label is the
  discoverability fix (P-14/P-12).
- Hop-distance presentation must convey MODELED hops: indirectly connected entities
  colored/positioned by witness-chain length, never flattened to "distance 1"
  (P-01 companion decision).
- Scale-adaptive presentation (P-16) confirmed as a committed long-term direction
  with architectural-soundness requirements: server-side aggregation in the
  projection layer, shared by all surfaces, invariant-testable, composing with
  style rules.
- FMEA severity anchor: UNRESOLVED by design. The owner cannot judge whether
  synthetic-persona "confident wrong action" warrants the S≥8 reading, because it is
  unknown how agent tasking/prompts/capabilities shape that confidence — a valid
  methodological objection (synthetic confidence may be a model artifact, in either
  direction). Handling: findings whose S depends on persona confidence rather than
  on system behavior (F1, F3, F5) carry BOTH readings — S8–9 under the literal
  anchor, S7 under the primary-result-correct reading; the priority ORDER inside the
  High band is therefore provisional; the High/Medium boundary is unaffected (all
  three stay High under either reading via the S≥7 ∧ D≥7 rule). Resolution path:
  the human-validation shortlist (report §10) — items 1 and 5 directly test whether
  real users act on the wrong claim.

## Adversarial-review adjudication (second review round)

An independent adversarial review (`REVIEW-viewpoint-usability-proposals.md`, 4
Critical / 8 Major / 4 Moderate issues) was adjudicated by the evaluator with source
verification and by the owner. Outcome, now folded into the proposals above:

- **Accepted and applied:** R-02 (P-09 population classification — the original
  example copy was false; P-12 count-cache leftover removed), R-03 (P-02 corrected:
  a scope→query fallback already exists in `scope_query.py`; migration via the
  deployment upgrade/repair CLI), R-04 (FMEA dual readings restored on P-01/P-03/
  P-05; no "highest priority" claims), R-05 (P-01 anchor_modeled_distance contract),
  R-06 (P-05 corrected: predicate `traversal` field already exists, default
  `direct`; work = add `both` with union-before-negation + builder exposure; open
  investigation into what the builder emits today), R-07 (P-16 AggregateItem/
  homogeneity/aggregate-before-limit contract), R-08 (P-03 server-resolved
  column_values + last_updated decision; P-11 complete generation-pinned export),
  R-09 (SM-01/02/03 merged into one corrected motivation-convention review — 5
  drivers, influence-typed driver→goal edges, assessment mediation respected,
  remove+recreate instead of type edit), R-10 (SM-05 four-status disposition
  register), R-11 (P-13 lineage bound to immutable content digest + generation, one
  stamping service for GUI and MCP), R-12 (orphans housed: F11 & F16-part → P-14,
  F20 → P-16, F31 → P-01, H3 → P-12), R-13 (P-04 four-way outcome taxonomy; warn
  only unresolvable/shadowed), R-14 (SM-08: save preserves status; only review/
  promotion activates), R-15 (P-07 live vs verified links), R-16 (P-06 ordered
  witness_steps).
- **Accepted with corrections:** R-01 — family-wide realization contract applied to
  P-17, severity adjudicated **Major** (not Critical) by the owner; the review's
  evidence misread `gui-engine-pairs.csv` (352/731 is requirements-realization;
  goal-realization is 97/142) and the persona-count nit is contestable. R-05's
  quoted probe command could not have run as written; its conclusion was re-grounded
  on this run's own probes.
- **Owner constraints applied:** the upgrade/repair CLI must migrate pre-change
  deployments' viewpoints cleanly — a standing requirement of P-02 (and P-05's
  default-stamping), independent of any manifest; there is NO per-viewpoint-
  definition manifest as a persisted long-term concept — divergent cases surface
  only as ephemeral upgrade-run report output requiring explicit choices.
- **Review reliability note:** the review's coverage-matrix appendix is misaligned
  against the report's F-numbering (e.g. F19→P-17, F13→P-12 are wrong rows) — its
  orphan CLAIMS were independently re-verified and are correct; the matrix itself
  should not be used as a record. Two probe filenames cited in evidence do not
  exist under those names.

### Review round 2 (adequacy re-check) — all five issues accepted and applied

1. P-02: inactive-layer divergence demoted to a W-class informational code (never
   execution/save-blocking — divergence is the normal state of a migrated
   definition); non-interactive resolution specified (`--resolve-selection
   <slug>=scope|query` or a reviewed resolutions file, writing ONLY selection_mode;
   unresolved divergent definitions ⇒ distinct exit status, zero partial
   conversion).
2. H3: new P-12a — permission-aware "Create viewpoint" entry point (catalog +
   empty states, `/viewpoints/new`, blank-or-template start, explicit contrast with
   Save As), validated by re-running the H3 scent protocol, not by catalog
   false-scent rates.
3. P-16: aggregate identity corrected — node identity (dimension, value, entity
   type); edge identity (source_aggregate_id, target_aggregate_id,
   connection_type, direction, provenance class); topology-preservation fixture
   (two same-typed edges between different aggregate pairs ⇒ two bundles).
4. P-09: target population is a per-definition presentation declaration —
   mechanical from ACTIVE scope in scope mode, explicit in query mode; honest-empty
   messaging suppressed when the target population is unknown; stale-inactive-scope
   fixture added.
5. P-17: population/orientation contract added — assessed targets vs contextual
   realizers (only targets are banded), incoming-realization orientation, and the
   P-05 traversal stated per family member.

### Findings disposition register (completes R-12)

Every report finding/hypothesis and its owning proposal (dispositions: proposal /
accepted-risk / closed-by-adjudication):

F1→P-01 · F2→P-02 · F3→P-03 · F4→P-04 · F5→P-05 · F6→P-06 · F7→P-08 · F8→P-07 ·
F9→P-09 · F10→P-09 (cancel state) · F11→P-14 · F12→P-08 · F13→P-08 (legend) ·
F14→P-12 · F15→P-12 (tier badges) · F16→P-07 (routing) + P-14 (discard/cancel) ·
F17→P-10 · F18→P-10 · F19→P-04 (bounds) · F20→P-16 · F21→P-11 · F22→P-11 ·
F23→P-14 · F24→P-12 (sweep/lint) · F25→P-14 (GAR filter) · F26→P-14 · F27→P-13 ·
F28→P-05 (Test-run entity list) · F29→P-15 · F30→P-08 · F31→P-01 · F32→P-08 ·
F33→P-14 · F34→P-14 · H1→P-17 + P-12 (closed as design gap by owner endorsement) ·
H2→P-09 + SM-06 (closed: empty-by-design + honest messaging) · H3→P-12a (explicit
create-route; residual = human validation via the H3 scent protocol) · H4→P-14
("View" label; placement endorsed as-is). No finding is unowned; H3/H4 retain
their human-validation residue per the report's shortlist.

## Implementation code map (verified against the tree at commit 3eea9b0)

Backend — domain:
- `src/domain/viewpoint_summary.py` — generated plain-language query summary (P-01).
- `src/domain/viewpoint_criteria.py` (+ `_parsing` / `_serialization` / `_validation` /
  `_evaluation` siblings) — `IncidentConnectionCondition` (existing `traversal` field,
  P-05), `ConnectionSelection` (already knows `both`), criteria grammar (P-15).
- `src/domain/viewpoint_projection.py` — projection items, per-item styles,
  scale_legends, stale_pin (P-03, P-06 witness_steps, P-16 AggregateItem).
- `src/domain/viewpoint_style_evaluation.py`,
  `src/domain/viewpoint_presentation_validation.py` — style-rule resolution and
  validation (P-04 outcome taxonomy, P-15 endpoint criteria).
- `src/domain/viewpoints.py` — ViewpointDefinition (P-02 `selection_mode`,
  P-13 `forked_from`).

Backend — application:
- `src/application/viewpoints/scope_query.py` — existing scope→query fallback
  (`definition_with_scope_query`, `query_from_scope`) — P-02 routes mode=scope here.
- `src/application/viewpoints/evaluate_viewpoint.py` — execution orchestration
  (P-01 summary wiring, P-05 traversal evaluation, P-09 target-population check).
- `src/application/viewpoints/execution_result.py` — `EntityItemSummary` /
  `ConnectionItemSummary` fixed shapes (P-03 status/version + column_values).
- `src/application/viewpoints/persist_definition.py` — save path (P-02 mode
  persistence, P-13 lineage stamping service).
- `src/application/viewpoints/parameter_binding.py` — parameters (P-07 URL params,
  P-17 anchor resolution).
- `src/application/viewpoints/pins.py` — pin state (P-13 staleness surface).

Backend — infrastructure:
- `src/infrastructure/gui/routers/viewpoints.py`, `_viewpoint_scope.py` — REST
  surface for execution/definitions (P-03/P-09/P-11 export endpoint/P-16 API).
- `src/infrastructure/cli/arch_repair_upgrade.py` (+ `arch_repair.py`) — the
  deployment upgrade/repair CLI that P-02's migration and P-05's default-stamping
  ride on.
- `src/infrastructure/mcp/artifact_mcp/write/` — `artifact_viewpoint` MCP tool
  (P-13 lineage parity with the GUI; P-02 W-code on MCP-authored definitions).

Definitions & fixtures:
- `src/ontologies/archimate_4/viewpoints.yaml` — module catalog (P-17 family
  changes; SM-06 removal of capability-map's drifted `investment_level` rule).
- `tools/usability_test/execution_probe.py` — probe used by acceptance validation;
  reference evidence lives in `test-results/usability/2607171252/`.
- `tests/application/viewpoints/test_scope_fallback.py` — existing scope-fallback
  characterization (extend for P-02).

GUI (`tools/gui/src/ui/`):
- `views/ViewpointsManagementView.vue` — catalog list (P-12 columns/search, P-12a
  create entry, P-14 tier badges, F24 sweep target).
- `components/ViewpointScopeTab.vue`, `components/ViewpointPresentationTab.vue`,
  `components/CriteriaTreeBuilder.vue`, `components/QueryParametersPanel.vue`,
  `components/QueryDerivedAttributesPanel.vue`, `components/QueryBindingsPanel.vue`,
  `components/StyleRuleEditor.vue` — editor tabs (P-02 mode switch, P-04 combobox +
  edit-time validation, P-05 traversal selector, P-10 fork quarantine).
- `views/GraphExploreView.vue` — exploration surface (P-01 rings, P-06 edge
  selection, P-08 ergonomics bundle, P-16 aggregates). NOTE: 804 counted lines,
  already over the length-policy baseline — P-08/P-16 work MUST split it into
  subcomponents rather than growing it (the baseline ratchet will fail CI otherwise).
- `views/ViewpointDiagramView.vue` (+ `.helpers.ts`) — diagram execution surface
  (P-06 edge detail, F7 render-failure fallback, P-08 initial fit).
- `views/EntitiesView.vue` — table representation host (P-03 status rendering,
  P-11 linked rows/sort/export). Also over-baseline (664 lines): same split rule.
- `views/ViewpointMatrixView.vue` — matrix surface (P-16 representation cell).

Several other named GUI targets (`EntityPickerInput.vue` for P-14 picker ranking,
`SaveChangesDialog.vue`) are in the length-policy baseline too — treat every
baseline file touched as "refactor down, never grow".
